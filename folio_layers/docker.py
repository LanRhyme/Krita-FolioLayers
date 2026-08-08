# -*- coding: utf-8 -*-
"""Folio Layer Docker - Native Qt Integration, Clean Dropdowns & Full Blending Modes"""

import sys
import os
import time
from collections import OrderedDict
from .qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QFrame, QMenu, QAction, QTimer,
    Qt, QSize, QRect, QCursor, QApplication, QHeaderView, QAbstractItemView, QColor, QPalette,
    QEvent, QPainter, QPen, QPoint, QPointF, QMouseEvent, QPropertyAnimation, QEasingCurve, QLayout, QDrag
)
from .lucide_icons import get_lucide_icon, get_lucide_pixmap, clear_icon_cache
from .hover_preview import HoverPreviewPopup, COLOR_LABEL_MAP
from .layer_item import LayerRowWidget
from .theme import get_theme, clear_theme_cache
from .opacity_bar import OpacityBarWidget
from .blending_modes import (
    create_categorized_blending_menu, get_blending_mode_name
)
from .settings_dialog import SettingsDialog
from .config import get_config
from .color_label_popup import build_color_label_menu

try:
    from krita import DockWidget, Krita
    IN_KRITA = True
except ImportError:
    IN_KRITA = False
    DockWidget = QWidget


class FlowLayout(QLayout):
    """自动换行布局：宽度不足时子项自动折行成多行显示（自适应双行工具栏）"""

    def __init__(self, parent=None, margin=0, h_spacing=2, v_spacing=2):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        # 不向任意方向扩展
        try:
            return Qt.Orientation(0)
        except Exception:
            return 0

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._flow(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._flow(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        m = self.contentsMargins()
        w = m.left() + m.right()
        h = m.top() + m.bottom()
        for item in self._items:
            wid = item.widget()
            if wid and not wid.isVisible():
                continue
            sz = item.sizeHint()
            if not sz.isValid():
                sz = item.minimumSize()
            w = max(w, m.left() + m.right() + sz.width())
            h = max(h, m.top() + m.bottom() + sz.height())
        return QSize(w, h)

    def _flow(self, rect, test_only):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_h = 0
        max_x = effective.right()
        for item in self._items:
            wid = item.widget()
            if wid and not wid.isVisible():
                continue
            sz = item.sizeHint()
            if not sz.isValid():
                sz = item.minimumSize()
            next_x = x + sz.width() + self._h_spacing
            # 放不下且当前行已有内容 → 换行
            if next_x - self._h_spacing > max_x + 1 and line_h > 0:
                x = effective.x()
                y = y + line_h + self._v_spacing
                next_x = x + sz.width() + self._h_spacing
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), sz))
            x = next_x
            line_h = max(line_h, sz.height())
        return y + line_h + m.bottom() - rect.y()


class LayerTreeWidget(QTreeWidget):
    """支持将拖拽事件转发给 Krita 原生 API 的图层树，及集中式 3 秒悬停预览处理"""
    def __init__(self, docker):
        super().__init__()
        self.docker = docker
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)
        # 数位笔：让无按钮的悬停移动（TabletMove）也投递到控件，Qt 才能合成
        # 悬停鼠标事件（部分 Qt 版本默认不投递悬停，导致笔 hover 无提示/无高亮）
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)
        w = self.window()
        if w is not None:
            w.setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)

        # 数位笔拖拽支持：笔按下时锁定的目标控件（模拟 Qt 鼠标抓取语义）
        self._pen_grab = None
        # 自定义笔拖拽状态（完全绕过 QDrag 拖拽循环，笔拖拽由本类自己驱动）
        self._pen_active = False  # 当前按压序列来自数位笔（事件传播会重建 QMouseEvent，标记会丢，故用实例状态）
        self._pen_dragging = False
        self._pen_drag_item = None
        self._pen_drag_pos = None
        # 笔拖拽幽灵：抓取被拖行渲染图为 pixmap，在 paintEvent 里跟随光标绘制
        # （不用独立 QLabel 窗口——高频 move 触发窗口重定位在 Wayland 合成器上开销大，是卡顿主因）
        self._ghost_pixmap = None

        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self._hover_item = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_hover_timeout)

        # 禁用 Qt 原生暴力的整行跳跃 autoScroll，改由 Python 像素级控速
        self.setAutoScroll(False)
        self._scroll_dir = 0
        self._scroll_step = 0
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(16)
        self._auto_scroll_timer.timeout.connect(self._do_auto_scroll)
        self._scroll_anim = None  # 滚轮平滑滚动动画

        # 记录滚动时间戳：滚动期间抑制 hover 预览，避免弹窗干扰滚动
        self.verticalScrollBar().valueChanged.connect(self._on_scrolled)
        self.horizontalScrollBar().valueChanged.connect(self._on_scrolled)

    def _on_scrolled(self, *args):
        """滚动发生时记录时间戳，用于滚动期间抑制 hover 预览"""
        self.docker._last_scroll_ts = time.monotonic()

    def _scroll_to(self, target):
        """平滑滚动到目标位置（OutCubic 缓动，约 160ms）"""
        sb = self.verticalScrollBar()
        if self._scroll_anim is not None:
            self._scroll_anim.stop()
            self._scroll_anim = None
        target = max(0, min(sb.maximum(), int(target)))
        if target == sb.value():
            return
        try:
            ease = QEasingCurve.Type.OutCubic
        except AttributeError:
            ease = QEasingCurve.OutCubic
        anim = QPropertyAnimation(sb, b"value", self)
        anim.setDuration(160)
        anim.setStartValue(float(sb.value()))
        anim.setEndValue(float(target))
        anim.setEasingCurve(ease)
        def _done():
            if self._scroll_anim is anim:
                self._scroll_anim = None
        anim.finished.connect(_done)
        self._scroll_anim = anim
        anim.start()

    def wheelEvent(self, event):
        self.docker._last_scroll_ts = time.monotonic()
        angle = event.angleDelta().y() if hasattr(event, 'angleDelta') else 0
        if angle != 0:
            # 滚轮：平滑动画滚动（每格约 3 行，与 Qt 默认一致）
            row_h = 30
            it = self.topLevelItem(0) if self.topLevelItemCount() > 0 else None
            if it is not None:
                s = it.sizeHint(0)
                if s.isValid() and s.height() > 0:
                    row_h = s.height()
            sb = self.verticalScrollBar()
            self._scroll_to(sb.value() + (-angle / 120.0) * 3 * row_h)
        else:
            # 触摸板：原生像素滚动（已平滑）
            super().wheelEvent(event)

    _TABLET_TYPES = None

    def _tablet_event_types(self):
        """兼容 PyQt5 (QEvent.TabletPress) 与 PyQt6 (QEvent.Type.TabletPress)"""
        if LayerTreeWidget._TABLET_TYPES is None:
            LayerTreeWidget._TABLET_TYPES = tuple(
                getattr(QEvent, name, getattr(getattr(QEvent, 'Type', None), name, None))
                for name in ('TabletPress', 'TabletMove', 'TabletRelease')
            )
        return LayerTreeWidget._TABLET_TYPES

    def _pen_log(self, msg):
        """数位笔调试日志：设置环境变量 FOLIO_PEN_DEBUG=1 后写入 ~/tmp/folio-pen.log"""
        if os.environ.get("FOLIO_PEN_DEBUG"):
            try:
                with open(os.path.expanduser("~/tmp/folio-pen.log"), "a") as f:
                    f.write("%.3f %s\n" % (time.time(), msg))
            except Exception:
                pass

    @staticmethod
    def _is_pen_device(event):
        """判断事件是否来自触控笔/橡皮等真实笔设备
        宽松策略：只明确排除鼠标型设备，其余一律按笔转译——
        笔事件被转译成鼠标事件是等效操作，而漏掉笔事件会退回不可靠的原生合成
        （注意不能用严格的 pointerType 判断：真实 Krita 里笔的 pointerType 名
        可能不匹配 Pen/Eraser，会把笔事件误判为鼠标导致完全无法拖拽）"""
        try:
            pt = event.pointerType()
            pname = getattr(pt, 'name', None)
            if pname is not None:
                pln = pname.lower()
                if pln in ('pen', 'eraser'):
                    return True
                # Qt5 枚举值 0=Pen 1=Eraser
            elif int(pt) in (0, 1):
                return True
        except Exception:
            pass
        try:
            dev = event.deviceType()
            name = getattr(dev, 'name', None)
            if name is not None:  # Qt6 QInputDevice.DeviceType
                ln = name.lower()
                return ln not in ('mouse', 'touchscreen', 'touchpad')
            return int(dev) != 6  # Qt5 QTabletEvent.TabletDevice: 6=Mouse
        except Exception:
            return True

    @staticmethod
    def _make_mouse_event(ev_type, local, global_pos, button, buttons, modifiers):
        """构造鼠标事件，兼容 PyQt6 / PyQt5 构造函数差异"""
        if hasattr(QEvent, 'Type'):  # PyQt6: (type, localPos, globalPos, button, buttons, modifiers)
            return QMouseEvent(ev_type, QPointF(local), QPointF(global_pos), button, buttons, modifiers)
        # PyQt5: (type, localPos, button, buttons, modifiers)
        return QMouseEvent(ev_type, QPointF(local), button, buttons, modifiers)

    def _handle_tablet_as_mouse(self, event):
        """把落在图层树上的触控笔事件转译为等价的鼠标事件注入，
        让 QAbstractItemView 的原生拖拽排序能用数位笔触发
        （Qt 仅在 tablet 事件未被 accept 时合成鼠标事件，某些平台/合成器下不可靠）"""
        viewport = self.viewport()
        press_t, move_t, rel_t = self._tablet_event_types()
        ev_type = event.type()

        # 按住移动事件节流（~60Hz）：笔事件可达 200Hz，全量转译+重绘会积压卡顿；
        # 节流的 move 仍被 filter accept，Qt 不会合成，位置以最近一次为准
        if ev_type == move_t and event.buttons() != Qt.NoButton:
            now = time.monotonic()
            last = getattr(self, '_last_pen_move_ts', 0.0)
            if now - last < 0.012:
                self._pen_log("[pen] throttled move")
                return
            self._last_pen_move_ts = now

        global_pos = event.globalPosition() if hasattr(event, 'globalPosition') else event.globalPos()

        if ev_type == press_t:
            self._pen_active = True
            # 笔按下：锁定触点下方最深控件，模拟 Qt 的 qt_button_down 抓取语义
            w = QApplication.widgetAt(global_pos.toPoint())
            if w is None or not (w == self or self.isAncestorOf(w)):
                w = viewport
            self._pen_grab = w
            self._pen_log("[pen] press grab=%s buttons=%s pos=%s" % (
                w.__class__.__name__ if w else None, event.buttons(), global_pos.toPoint()))

        receiver = self._pen_grab if self._pen_grab is not None else viewport

        mouse_type = {
            press_t: getattr(QEvent, 'MouseButtonPress', getattr(getattr(QEvent, 'Type', None), 'MouseButtonPress', None)),
            move_t: getattr(QEvent, 'MouseMove', getattr(getattr(QEvent, 'Type', None), 'MouseMove', None)),
            rel_t: getattr(QEvent, 'MouseButtonRelease', getattr(getattr(QEvent, 'Type', None), 'MouseButtonRelease', None)),
        }[ev_type]

        local = receiver.mapFromGlobal(global_pos.toPoint())
        me = self._make_mouse_event(mouse_type, local, global_pos, event.button(), event.buttons(), event.modifiers())
        try:
            me._folio_pen = True  # 标记为笔转译事件（自定义拖拽用）
        except Exception:
            pass
        self._pen_log("[pen] -> %s -> %s buttons=%s" % (getattr(mouse_type, 'name', mouse_type), receiver.__class__.__name__, event.buttons()))
        QApplication.sendEvent(receiver, me)

        if ev_type == rel_t:
            self._pen_grab = None
            self._pen_active = False

    def _tablet_in_viewport(self, event):
        """事件全局坐标是否落在图层树 viewport 内"""
        vp = self.viewport()
        if not vp.isVisible():
            return False
        gp = event.globalPosition() if hasattr(event, 'globalPosition') else event.globalPos()
        vp_tl = vp.mapToGlobal(QPoint(0, 0))
        return vp.rect().translated(vp_tl).contains(gp.toPoint())

    def _is_native_drag_active(self):
        """QDrag::exec 拖拽循环中：此时必须让 Qt 原生合成鼠标事件
        （spontaneous 事件才能被 QDragManager 消费），我们的注入事件到不了它"""
        try:
            return QDrag.activeDrag() is not None
        except Exception:
            return False

    def eventFilter(self, obj, event):
        ev_type = event.type()
        # —— 数位笔事件（app 级拦截：无论投递目标是谁，落在树内即转译）——
        if ev_type in self._tablet_event_types() and self._is_pen_device(event):
            dragging = self._pen_grab is not None
            if not dragging and not self._tablet_in_viewport(event):
                return super().eventFilter(obj, event)  # 树外（且未在拖拽中）：交给 Qt 原生处理
            press_t, _move_t, rel_t = self._tablet_event_types()
            if self._is_native_drag_active():
                # 拖拽循环中：让 Qt 原生合成 spontaneous 鼠标事件供 QDragManager 消费
                self._pen_log("[pen] drag-loop bypass %s buttons=%s" % (getattr(ev_type, 'name', ev_type), event.buttons()))
                return super().eventFilter(obj, event)
            if ev_type == _move_t and event.buttons() == Qt.NoButton:
                # 悬停移动：不拦截，让 Qt 原生合成 spontaneous 事件以触发 tooltip/高亮
                self._pen_log("[pen] hover bypass %s pos=%s" % (getattr(ev_type, 'name', ev_type), event.position().toPoint()))
                return super().eventFilter(obj, event)
            if ev_type == rel_t and self._pen_grab is None:
                # 无按压状态的释放（异常路径）：不处理
                return super().eventFilter(obj, event)
            # 按下 / 按住移动 / 释放：转译为鼠标事件注入
            self._handle_tablet_as_mouse(event)
            event.accept()
            return True
        # —— viewport 内其余事件 ——
        if obj == self.viewport():
            ev_mouse_move = getattr(QEvent, 'MouseMove', getattr(getattr(QEvent, 'Type', None), 'MouseMove', None))
            if ev_type == ev_mouse_move:
                global_pos = QCursor.pos()
                vp_pos = self.viewport().mapFromGlobal(global_pos)
                item = self.itemAt(vp_pos)
                if item:
                    w = self.itemWidget(item, 0)
                    if w and hasattr(self.docker, '_on_row_mouse_move'):
                        self.docker._on_row_mouse_move(w, global_pos)
        return super().eventFilter(obj, event)

    def _is_cursor_on_hover_item(self):
        """确认延迟到期时鼠标仍停留在原图层行上"""
        if not self._hover_item or not self.viewport().isVisible():
            return False
        vp_pos = self.viewport().mapFromGlobal(QCursor.pos())
        if not self.viewport().rect().contains(vp_pos):
            return False
        return self.itemAt(vp_pos) == self._hover_item

    def _on_hover_timeout(self):
        from .config import get_config
        cfg = get_config()
        if not cfg.enable_hover_preview or not self._hover_item:
            return
        # 延迟期间鼠标可能已经离开图层行；不能再使用旧目标弹出预览
        if not self._is_cursor_on_hover_item():
            self._hover_item = None
            return
        w = self.itemWidget(self._hover_item, 0)
        if w and w.node:
            self.docker.show_hover_preview(w.node, QCursor.pos())

    def _do_auto_scroll(self):
        if self._scroll_dir == 0 or self._scroll_step == 0:
            return
        vbar = self.verticalScrollBar()
        if vbar:
            vbar.setValue(vbar.value() + self._scroll_step)

    def paintEvent(self, event):
        super().paintEvent(event)

        # 自定义高对比度 6px 粗体拖拽插入指示线 + 圆点手柄
        if getattr(self, '_drag_active', False) and getattr(self, '_drag_target_item', None):
            item = self._drag_target_item
            drop_ind = getattr(self, '_drag_drop_ind', None)
            rect = self.visualItemRect(item)
            if not rect.isValid():
                return

            above = getattr(QAbstractItemView.DropIndicatorPosition, 'AboveItem', None)
            below = getattr(QAbstractItemView.DropIndicatorPosition, 'BelowItem', None)
            on_item = getattr(QAbstractItemView.DropIndicatorPosition, 'OnItem', None)

            from .theme import get_theme
            t = get_theme()
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            
            accent_col = QColor(t.ACCENT)

            if drop_ind == above:
                y = rect.top()
                # 6px 粗度中轴实线
                pen = QPen(accent_col, 6)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(rect.left() + 8, y, rect.right() - 4, y)

                # 左端点手柄 (10px 圆点)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(accent_col)
                p.drawEllipse(QPoint(rect.left() + 8, y), 5, 5)

            elif drop_ind == below:
                y = rect.bottom()
                pen = QPen(accent_col, 6)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(rect.left() + 8, y, rect.right() - 4, y)

                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(accent_col)
                p.drawEllipse(QPoint(rect.left() + 8, y), 5, 5)

            elif drop_ind == on_item:
                # 嵌入图层组：3px 边框 + 半透明蒙层
                pen = QPen(accent_col, 3)
                p.setPen(pen)
                p.setBrush(QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 50))
                p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 4, 4)

            # 拖拽虚影：被拖行渲染图跟随光标（半透明）
            gpix = getattr(self, '_ghost_pixmap', None)
            if gpix is not None and not gpix.isNull():
                drag_pos = getattr(self, '_pen_drag_pos', None)
                if drag_pos is None:
                    drag_pos = self.viewport().mapFromGlobal(QCursor.pos())
                p.setOpacity(0.85)
                p.drawPixmap(drag_pos.x() - gpix.width() // 2,
                             drag_pos.y() - gpix.height() // 2, gpix)
                p.setOpacity(1.0)

            p.end()

    def _clear_drag_indicator(self):
        self._drag_active = False
        self._drag_target_item = None
        self._drag_drop_ind = None
        if hasattr(self, '_active_drag_widget') and self._active_drag_widget:
            try:
                self._active_drag_widget.set_drop_indicator(None)
            except Exception:
                pass
            self._active_drag_widget = None
            self._active_drag_pos = None
        self.viewport().update()

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        margin = 55
        vp = self.viewport()
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        y = pos.y()

        if y < margin:
            dist = max(0, y)
            ratio = (margin - dist) / margin
            # 渐进平滑调速：2px ~ 8px 60FPS 顺滑滚屏
            self._scroll_step = -int(2 + ratio * 6)
            self._scroll_dir = -1
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        elif vp.height() - y < margin:
            dist = max(0, vp.height() - y)
            ratio = (margin - dist) / margin
            self._scroll_step = int(2 + ratio * 6)
            self._scroll_dir = 1
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        else:
            self._scroll_dir = 0
            self._scroll_step = 0
            self._auto_scroll_timer.stop()

        # 记录拖拽插入目标并重绘 viewport
        target_item = self.itemAt(pos)
        target_widget = self.itemWidget(target_item, 0) if target_item else None
        drop_ind = self.dropIndicatorPosition()
        
        self._drag_active = True
        self._drag_target_item = target_item
        self._drag_drop_ind = drop_ind
        
        above = getattr(QAbstractItemView.DropIndicatorPosition, 'AboveItem', None)
        below = getattr(QAbstractItemView.DropIndicatorPosition, 'BelowItem', None)
        on_item = getattr(QAbstractItemView.DropIndicatorPosition, 'OnItem', None)
        
        pos_str = "above" if drop_ind == above else ("below" if drop_ind == below else ("on" if drop_ind == on_item else None))

        if getattr(self, '_active_drag_widget', None) != target_widget or getattr(self, '_active_drag_pos', None) != pos_str:
            if hasattr(self, '_active_drag_widget') and self._active_drag_widget:
                try:
                    self._active_drag_widget.set_drop_indicator(None)
                except Exception:
                    pass
            if target_widget and hasattr(target_widget, 'set_drop_indicator'):
                target_widget.set_drop_indicator(pos_str)
                self._active_drag_widget = target_widget
                self._active_drag_pos = pos_str

        self.viewport().update()

    def dragLeaveEvent(self, event):
        self._scroll_dir = 0
        self._auto_scroll_timer.stop()
        self._clear_drag_indicator()
        super().dragLeaveEvent(event)

    def _close_all_swipes(self):
        for i in range(self.topLevelItemCount()):
            self._close_item_swipe_recursive(self.topLevelItem(i))

    def _close_item_swipe_recursive(self, item):
        if not item:
            return
        w = self.itemWidget(item, 0)
        if w and hasattr(w, 'close_swipe'):
            w.close_swipe()
        for i in range(item.childCount()):
            self._close_item_swipe_recursive(item.child(i))

    def startDrag(self, supportedActions):
        """记录拖拽启动（数位笔调试用）"""
        self._pen_log("[pen] START-DRAG actions=%s" % supportedActions)
        super().startDrag(supportedActions)

    def mousePressEvent(self, event):
        """记录点击起点，关闭其他划出的面板，并在点击空白区域时不取消选中"""
        self._pen_log("[pen] tree mousePress pos=%s buttons=%s" % (event.position().toPoint(), event.buttons()))
        self._close_all_swipes()
        item = self.itemAt(event.pos())
        if item is None:
            return
        self._press_pos = event.pos()
        self._is_horizontal_swipe = False
        # 自定义笔拖拽：新一轮按下重置状态
        self._pen_dragging = False
        self._pen_drag_item = None
        self._pen_drag_pos = None
        super().mousePressEvent(event)

    def _event_is_pen_synth(self, event):
        """Qt 由数位笔事件合成的鼠标事件（source == MouseEventSynthesizedByQt）——
        某些 Wayland 合成器不提供 tablet 协议，笔事件全部走 Qt 鼠标合成路径，
        此时同样走自定义拖拽（不依赖 QDragManager 消费 spontaneous 事件）"""
        try:
            src = event.source()
            return src == Qt.MouseEventSource.MouseEventSynthesizedByQt
        except Exception:
            return False

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        # —— 数位笔拖拽：自定义驱动（不依赖 Qt 原生 QDrag 拖拽循环）——
        # 触发条件：转译的 tablet press（_pen_active）或 Qt 合成的笔鼠标事件（_event_is_pen_synth）
        if (self._pen_active or self._event_is_pen_synth(event)) \
                and (event.buttons() & Qt.MouseButton.LeftButton) \
                and getattr(self, '_press_pos', None):
            dx = pos.x() - self._press_pos.x()
            dy = pos.y() - self._press_pos.y()
            if getattr(self, '_pen_dragging', False):
                # 拖拽中：更新插入指示线 / 边缘自动滚动
                self._pen_drag_update(pos)
                return
            # 笔路径：拖拽优先——左滑手势只在近乎纯水平（|dy| < 6px）时触发，
            # 避免笔拖拽轨迹稍带水平分量就被误判为滑动而截断拖拽
            if abs(dy) < 6 and dx < -10:
                self._pen_log("[pen] PEN-SWIPE dx=%d dy=%d" % (dx, dy))
                self._is_horizontal_swipe = True
                item = self.itemAt(self._press_pos)
                if item:
                    w = self.itemWidget(item, 0)
                    if w and hasattr(w, 'open_swipe'):
                        w.open_swipe()
                return
            if (pos - self._press_pos).manhattanLength() > QApplication.startDragDistance():
                self._pen_log("[pen] CUSTOM-DRAG start at %s" % pos)
                self._pen_dragging = True
                self._pen_drag_item = self.itemAt(self._press_pos)
                self._show_pen_ghost()
                self._pen_drag_update(pos)
                return
        if getattr(self, '_press_pos', None) and (event.buttons() & Qt.MouseButton.LeftButton):
            dx = pos.x() - self._press_pos.x()
            dy = pos.y() - self._press_pos.y()
            # 左划手势判断：水平位移明显大于垂直位移，且 dx < -15px
            if dx < -15 and abs(dx) > abs(dy) * 1.2:
                self._pen_log("[pen] SWIPE-TRIGGERED dx=%d dy=%d (drag blocked!)" % (dx, dy))
                self._is_horizontal_swipe = True
                item = self.itemAt(self._press_pos)
                if item:
                    w = self.itemWidget(item, 0)
                    if w and hasattr(w, 'open_swipe'):
                        w.open_swipe()
                # 吃掉事件，截断 Qt C++ 原生 QDrag 的拖拽启动
                return
            elif dx > 15 and getattr(self, '_is_horizontal_swipe', False):
                item = self.itemAt(self._press_pos)
                if item:
                    w = self.itemWidget(item, 0)
                    if w and hasattr(w, 'close_swipe'):
                        w.close_swipe()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """数位笔拖拽完成：执行重排序"""
        if (self._pen_active or self._event_is_pen_synth(event)) and getattr(self, '_pen_dragging', False):
            self._pen_log("[pen] CUSTOM-DROP release at %s" % (event.position().toPoint()))
            self._pen_dragging = False
            self._hide_pen_ghost()
            self._finish_pen_drop(event.position().toPoint())
            self._pen_drag_item = None
            self._pen_drag_pos = None
            self._scroll_dir = 0
            self._auto_scroll_timer.stop()
            self._clear_drag_indicator()
            # 交还 Qt 清理 QAbstractItemView 内部状态（pressedIndex 等）
            super().mouseReleaseEvent(event)
            return
        super().mouseReleaseEvent(event)

    def _pen_drag_update(self, pos):
        """自定义笔拖拽：更新插入指示线与边缘自动滚动（复刻 dragMoveEvent 逻辑）"""
        margin = 55
        vp = self.viewport()
        y = pos.y()
        if y < margin:
            dist = max(0, y)
            ratio = (margin - dist) / margin
            self._scroll_step = -int(2 + ratio * 6)
            self._scroll_dir = -1
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        elif vp.height() - y < margin:
            dist = max(0, vp.height() - y)
            ratio = (margin - dist) / margin
            self._scroll_step = int(2 + ratio * 6)
            self._scroll_dir = 1
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        else:
            self._scroll_dir = 0
            self._scroll_step = 0
            self._auto_scroll_timer.stop()

        # 记录当前视口坐标（paintEvent 按此绘制拖拽虚影）
        self._pen_drag_pos = pos

        # 计算插入位置：Above / Below / On（空白处回退到最近行）
        target_item = self._resolve_drop_target(pos)
        above = getattr(QAbstractItemView.DropIndicatorPosition, 'AboveItem', None)
        below = getattr(QAbstractItemView.DropIndicatorPosition, 'BelowItem', None)
        on_item = getattr(QAbstractItemView.DropIndicatorPosition, 'OnItem', None)
        drop_ind = self._compute_drop_indicator(pos, target_item)
        if drop_ind is not None:
            # 拖拽虚影跟随笔尖（全局坐标）
            self._move_pen_ghost(self.viewport().mapToGlobal(pos))

        self._drag_active = True
        self._drag_target_item = target_item
        self._drag_drop_ind = drop_ind

        target_widget = self.itemWidget(target_item, 0) if target_item else None
        pos_str = "above" if drop_ind == above else ("below" if drop_ind == below else ("on" if drop_ind == on_item else None))
        if getattr(self, '_active_drag_widget', None) != target_widget or getattr(self, '_active_drag_pos', None) != pos_str:
            if getattr(self, '_active_drag_widget', None) is not None:
                try:
                    self._active_drag_widget.set_drop_indicator(None)
                except Exception:
                    pass
            if target_widget and hasattr(target_widget, 'set_drop_indicator'):
                target_widget.set_drop_indicator(pos_str)
                self._active_drag_widget = target_widget
                self._active_drag_pos = pos_str
        self.viewport().update()

    def _show_pen_ghost(self):
        """拖拽激活时抓取被拖行渲染图作为拖拽虚影（paintEvent 绘制，跟随光标）"""
        try:
            item = getattr(self, '_pen_drag_item', None)
            if item is None:
                return
            w = self.itemWidget(item, 0)
            if w is None:
                return
            pix = w.grab()
            if pix is None or pix.isNull():
                return
            self._ghost_pixmap = pix
            self.viewport().update()
        except Exception:
            pass

    def _move_pen_ghost(self, global_pos):
        """拖拽虚影位置由 paintEvent 按光标位置绘制，这里仅触发重绘"""
        try:
            self.viewport().update()
        except Exception:
            pass

    def _hide_pen_ghost(self):
        """拖拽结束：清除虚影并重绘"""
        try:
            self._ghost_pixmap = None
            self.viewport().update()
        except Exception:
            pass

    def _nearest_item(self, pos):
        """空白落点兜底：找视觉上距离 pos 最近的行（拖到列表末尾/行间隙也能定位）"""
        best = None
        best_d = None

        def walk(item):
            nonlocal best, best_d
            r = self.visualItemRect(item)
            if r.isValid():
                d = abs(pos.y() - r.center().y())
                if best_d is None or d < best_d:
                    best_d = d
                    best = item
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.topLevelItemCount()):
            walk(self.topLevelItem(i))
        return best

    def _resolve_drop_target(self, pos):
        """解析落点目标行（空白处回退到最近的行）"""
        item = self.itemAt(pos)
        if item is not None:
            return item
        return self._nearest_item(pos)

    def _compute_drop_indicator(self, pos, target_item):
        """根据鼠标位置与目标行计算插入位置
        “中”(OnItem/嵌入)只在目标行正中央窄带判定，且仅图层组支持嵌入；
        其余全部是上/下——拖拽稍偏不会被当作嵌入组导致落点错乱"""
        above = getattr(QAbstractItemView.DropIndicatorPosition, 'AboveItem', None)
        below = getattr(QAbstractItemView.DropIndicatorPosition, 'BelowItem', None)
        on_item = getattr(QAbstractItemView.DropIndicatorPosition, 'OnItem', None)
        if target_item is None:
            return None
        rect = self.visualItemRect(target_item)
        if not rect.isValid():
            return None
        y = pos.y()
        mid_top = rect.top() + rect.height() * 0.45
        mid_bot = rect.top() + rect.height() * 0.55
        if y < mid_top:
            return above
        if y > mid_bot:
            return below
        tw = self.itemWidget(target_item, 0)
        is_group = bool(tw and tw.node and tw.node.type() == "grouplayer")
        return on_item if is_group else above

    def _finish_pen_drop(self, pos):
        """自定义笔拖拽落点：以释放位置重算目标与插入位置，再执行重排序
        （不再依赖最后 move 的缓存指示线位置，松手瞬间移动也不会落点错位）"""
        dragged_item = getattr(self, '_pen_drag_item', None)
        if dragged_item is None:
            self._pen_log("[pen] drop aborted: no drag source")
            return
        target_item = self._resolve_drop_target(pos)
        if target_item is None:
            self._pen_log("[pen] drop aborted: no target/selection")
            return
        if target_item == dragged_item:
            self._pen_log("[pen] drop aborted: same item")
            return
        drop_ind = self._compute_drop_indicator(pos, target_item)
        if drop_ind is None:
            self._pen_log("[pen] drop aborted: no drop indicator")
            return
        self._pen_log("[pen] execute reorder drag=%s target=%s ind=%s" % (
            dragged_item.text(0) if dragged_item else "?",
            target_item.text(0) if target_item else "?", drop_ind))
        self._execute_reorder(dragged_item, target_item, drop_ind)

    def _execute_reorder(self, dragged_item, target_item, drop_ind):
        """dropEvent 重排序核心逻辑（鼠标拖拽与自定义笔拖拽共用）"""
        dragged_widget = self.itemWidget(dragged_item, 0)
        target_widget = self.itemWidget(target_item, 0)
        drag_node = dragged_widget.node if dragged_widget else None
        target_node = target_widget.node if target_widget else None
        if not drag_node or not target_node:
            return
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            return

        def _backup_subtree(node):
            if node.type() != "grouplayer":
                return None
            backup = []
            for child in list(node.childNodes()):
                backup.append((child, _backup_subtree(child)))
            return backup

        def _reattach_subtree(group, backup):
            if group is None or not backup:
                return
            for child, sub_backup in backup:
                try:
                    cur_parent = child.parentNode()
                    if cur_parent is None or cur_parent.uniqueId() != group.uniqueId():
                        group.addChildNode(child, None)
                except Exception:
                    pass
                if sub_backup:
                    _reattach_subtree(child, sub_backup)

        def _reorder_with_children(drag_node, new_parent, above_sibling):
            # Krita 官方规则：如果被拖拽图层处于锁定状态 (locked)，保留原图层，在目标位置克隆副本（带 - 副本 后缀）
            if drag_node.locked():
                cloned_node = drag_node.duplicate()
                try:
                    cloned_node.setName(f"{drag_node.name()} - 副本")
                except Exception:
                    pass
                try:
                    cloned_node.setLocked(False)
                except Exception:
                    pass
                new_parent.addChildNode(cloned_node, above_sibling)
                doc.setActiveNode(cloned_node)
                return

            is_group = drag_node.type() == "grouplayer"
            saved_tree = _backup_subtree(drag_node) if is_group else None
            old_parent = drag_node.parentNode()
            if old_parent is None:
                return
            # 保护：above_sibling 恰好是被拖节点自身（拖到紧邻下方）→ 位置不变，直接返回
            if above_sibling is not None and above_sibling.uniqueId() == drag_node.uniqueId():
                return
            # 记录原位置（失败回滚用，防止 remove 后 add 失败导致图层丢失）
            old_siblings = list(old_parent.childNodes())
            old_idx = next((i for i, n in enumerate(old_siblings) if n.uniqueId() == drag_node.uniqueId()), -1)
            old_above = old_siblings[old_idx - 1] if old_idx > 0 else None
            try:
                old_parent.removeChildNode(drag_node)
            except Exception:
                return
            try:
                new_parent.addChildNode(drag_node, above_sibling)
            except Exception:
                # 回滚：把节点放回原父的原位置，绝不丢失
                try:
                    old_parent.addChildNode(drag_node, old_above)
                except Exception:
                    try:
                        old_parent.addChildNode(drag_node, None)
                    except Exception:
                        pass
                return
            if is_group and saved_tree:
                _reattach_subtree(drag_node, saved_tree)

        above = getattr(QAbstractItemView.DropIndicatorPosition, 'AboveItem', None)
        below = getattr(QAbstractItemView.DropIndicatorPosition, 'BelowItem', None)
        on_item = getattr(QAbstractItemView.DropIndicatorPosition, 'OnItem', None)

        if drop_ind == on_item:
            if target_node.type() == "grouplayer":
                if drag_node.uniqueId() == target_node.uniqueId():
                    return
                old_parent = drag_node.parentNode()
                if old_parent and old_parent.uniqueId() == target_node.uniqueId():
                    return
                children = list(target_node.childNodes())
                first_child = children[-1] if children else None
                _reorder_with_children(drag_node, target_node, first_child)
            else:
                return
        elif drop_ind == above:
            parent = target_node.parentNode()
            if not parent or parent.uniqueId() == drag_node.uniqueId():
                return
            _reorder_with_children(drag_node, parent, target_node)
        elif drop_ind == below:
            parent = target_node.parentNode()
            if not parent or parent.uniqueId() == drag_node.uniqueId():
                return
            siblings = parent.childNodes()
            idx = next((i for i, n in enumerate(siblings) if n.uniqueId() == target_node.uniqueId()), -1)
            if idx < 0:
                return
            above_sibling = siblings[idx - 1] if idx > 0 else None
            _reorder_with_children(drag_node, parent, above_sibling)

        doc.refreshProjection()
        QTimer.singleShot(50, self.docker.refresh_tree)

    def dropEvent(self, event):
        self._pen_log("[pen] dropEvent selected=%d source=%s" % (len(self.selectedItems()), getattr(event, 'source', lambda: None)() or 'None'))
        self._scroll_dir = 0
        self._auto_scroll_timer.stop()
        self._clear_drag_indicator()
        if hasattr(event, 'position'):
            pos = event.position().toPoint()
        else:
            pos = event.pos()
            
        target_item = self.itemAt(pos)
        dragged_items = self.selectedItems()
        if not target_item or not dragged_items:
            event.ignore()
            return

        dragged_item = dragged_items[0]
        if target_item == dragged_item:
            event.ignore()
            return
            
        drop_ind = self.dropIndicatorPosition()
        
        dragged_widget = self.itemWidget(dragged_item, 0)
        target_widget = self.itemWidget(target_item, 0)
        
        drag_node = dragged_widget.node if dragged_widget else None
        target_node = target_widget.node if target_widget else None
        
        if not drag_node or not target_node:
            event.ignore()
            return
            
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            event.ignore()
            return

        def _backup_subtree(node):
            """递归备份节点所有后代，包括嵌套子组的子组"""
            if node.type() != "grouplayer":
                return None
            backup = []
            for child in list(node.childNodes()):
                backup.append((child, _backup_subtree(child)))
            return backup

        def _reattach_subtree(group, backup):
            if group is None or not backup:
                return
            for child, sub_backup in backup:
                try:
                    cur_parent = child.parentNode()
                    if cur_parent is None or cur_parent.uniqueId() != group.uniqueId():
                        group.addChildNode(child, None)
                except Exception:
                    pass
                if sub_backup:
                    _reattach_subtree(child, sub_backup)

        def _reorder_with_children(drag_node, new_parent, above_sibling):
            # Krita 官方规则：如果被拖拽图层处于锁定状态 (locked)，保留原图层，在目标位置克隆副本（带 - 副本 后缀）
            if drag_node.locked():
                cloned_node = drag_node.duplicate()
                try:
                    cloned_node.setName(f"{drag_node.name()} - 副本")
                except Exception:
                    pass
                try:
                    cloned_node.setLocked(False)
                except Exception:
                    pass
                new_parent.addChildNode(cloned_node, above_sibling)
                doc.setActiveNode(cloned_node)
                return

            is_group = drag_node.type() == "grouplayer"
            saved_tree = _backup_subtree(drag_node) if is_group else None
            old_parent = drag_node.parentNode()
            if old_parent is None:
                return
            # 保护：above_sibling 恰好是被拖节点自身（拖到紧邻下方）→ 位置不变，直接返回
            if above_sibling is not None and above_sibling.uniqueId() == drag_node.uniqueId():
                return
            # 记录原位置（失败回滚用，防止 remove 后 add 失败导致图层丢失）
            old_siblings = list(old_parent.childNodes())
            old_idx = next((i for i, n in enumerate(old_siblings) if n.uniqueId() == drag_node.uniqueId()), -1)
            old_above = old_siblings[old_idx - 1] if old_idx > 0 else None
            try:
                old_parent.removeChildNode(drag_node)
            except Exception:
                return
            try:
                new_parent.addChildNode(drag_node, above_sibling)
            except Exception:
                # 回滚：把节点放回原父的原位置，绝不丢失
                try:
                    old_parent.addChildNode(drag_node, old_above)
                except Exception:
                    try:
                        old_parent.addChildNode(drag_node, None)
                    except Exception:
                        pass
                return
            if is_group and saved_tree:
                _reattach_subtree(drag_node, saved_tree)

        if drop_ind == QAbstractItemView.DropIndicatorPosition.OnItem:
            if target_node.type() == "grouplayer":
                if drag_node.uniqueId() == target_node.uniqueId():
                    event.ignore()
                    return
                old_parent = drag_node.parentNode()
                if old_parent and old_parent.uniqueId() == target_node.uniqueId():
                    event.ignore()
                    return
                children = list(target_node.childNodes())
                first_child = children[-1] if children else None
                _reorder_with_children(drag_node, target_node, first_child)
            else:
                event.ignore()
                return
        elif drop_ind == QAbstractItemView.DropIndicatorPosition.AboveItem:
            parent = target_node.parentNode()
            if not parent or parent.uniqueId() == drag_node.uniqueId():
                event.ignore()
                return
            _reorder_with_children(drag_node, parent, target_node)
        elif drop_ind == QAbstractItemView.DropIndicatorPosition.BelowItem:
            parent = target_node.parentNode()
            if not parent or parent.uniqueId() == drag_node.uniqueId():
                event.ignore()
                return
            siblings = parent.childNodes()
            idx = next((i for i, n in enumerate(siblings) if n.uniqueId() == target_node.uniqueId()), -1)
            if idx < 0:
                event.ignore()
                return
            above = siblings[idx - 1] if idx > 0 else None
            _reorder_with_children(drag_node, parent, above)

        doc.refreshProjection()
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        QTimer.singleShot(50, self.docker.refresh_tree)

class FolioLayersDocker(DockWidget if IN_KRITA else QWidget):
    """精简优雅、包含全套原生功能与全类混合模式菜单的 Krita 图层面板"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folio Layers")
        self.canvas = None

        self.hover_preview = HoverPreviewPopup(None)
        self.hover_preview.hide()
        # 悬停预览状态跟踪：首次停留需要延迟，之后移动到其它项就立即显示
        self._hover_active = False  # True 表示浮窗已在展示过

        self._updating_ui = False
        self._theme_refresh_scheduled = False
        self._last_theme_signature = None

        # 主容器
        self.main_widget = QWidget(self)
        self.setWidget(self.main_widget) if IN_KRITA else None

        main_layout = QVBoxLayout(self.main_widget if IN_KRITA else self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # 1. 精简型工具栏 (Height: 24px)
        self._build_toolbar(main_layout)

        # 2. 属性控制栏：分级混合模式菜单 + 原生风格不透明度条 (Height: 22px)
        self._build_property_bar(main_layout)

        # 3. 搜索/筛选框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索图层...")
        self.search_input.hide()
        self.search_input.textChanged.connect(self._filter_layers)
        main_layout.addWidget(self.search_input)

        # 4. 图层树形列表 (使用支持拖拽排序的自定义 TreeWidget)
        self.thumbnail_cache = OrderedDict()
        self.tree = LayerTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(0) # 缩进由 LayerRowWidget 内部接管，保证左侧对齐
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(True) # 行高固定时启用统一行高，大幅提升滚动性能
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.tree.itemExpanded.connect(self._on_item_expanded)

        main_layout.addWidget(self.tree, 1)

        # 数位笔：给面板各区域开启 TabletTracking——否则无按钮悬停 TabletMove
        # 会在控件层被 Qt 吞掉（不传播），笔 hover 工具栏/属性栏无 tooltip
        self._enable_tablet_tracking_recursive(self.main_widget if IN_KRITA else self)

        # 悬停预览守卫：补偿子控件/空白区不派发 leaveEvent 的情况，
        # 定期确认鼠标是否仍在图层列表或已显示的预览卡片内
        self._hover_guard_timer = QTimer(self)
        self._hover_guard_timer.setInterval(80)
        self._hover_guard_timer.timeout.connect(self._guard_hover_cursor)
        self._hover_guard_timer.start()

        # 加载批处理状态：当 Krita 加载/创建大图像时暂停所有同步，避免阻塞主线程
        self._loading = True
        self._loading_timer = QTimer(self)
        self._loading_timer.setSingleShot(True)
        self._loading_timer.timeout.connect(self._finish_loading)
        self._loading_timer.start(500)  # 启动时短暂延迟，等 Krita 完成初始化

        # 组展开状态：None=首次加载（默认展开），set()=已跟踪
        self._expanded_uids = None

        # 5. 定时刷新与 Krita 事件挂载
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(600)
        self.sync_timer.timeout.connect(self._sync_with_krita)
        self.sync_timer.start()

        # 内容变化节流：作画/编辑图像时批量刷新缩略图，避免 600ms 轮询全量重载
        self._content_flush_timer = QTimer(self)
        self._content_flush_timer.setSingleShot(True)
        self._content_flush_timer.setInterval(300)
        self._content_flush_timer.timeout.connect(self._flush_thumbnails)

        if IN_KRITA:
            try:
                notifier = Krita.instance().notifier()
                notifier.imageCreated.connect(self._on_image_created)
                # 防御性连接：Krita 6 的 Notifier 无 activeViewChanged/imageModified 信号
                if hasattr(notifier, 'activeViewChanged'):
                    notifier.activeViewChanged.connect(self._on_view_changed)
                if hasattr(notifier, 'imageModified'):
                    notifier.imageModified.connect(self._on_image_modified)
                # 主题切换信号：Krita 6 的 Notifier 没有 themeChanged（那是 Q_SLOTS 槽），
                # 真实信号在 Window（KisMainWindow）上，窗口创建时发射
                notifier.windowCreated.connect(self._connect_window_theme_signal)
            except Exception:
                pass

        self.apply_theme_qss()
        self.refresh_tree()
        if IN_KRITA:
            self._connect_window_theme_signal()

    def _connect_window_theme_signal(self, *args):
        """连接当前 Krita 主窗口的 themeChanged 信号（Krita 主题切换时触发）"""
        try:
            w = Krita.instance().activeWindow()
            if w and hasattr(w, 'themeChanged') and w.themeChanged is not None:
                # 先断开旧连接再重连，避免窗口重建时信号重复堆积
                try:
                    w.themeChanged.disconnect(self._on_krita_theme_changed)
                except TypeError:
                    pass  # 尚未连接
                w.themeChanged.connect(self._on_krita_theme_changed)
        except Exception:
            pass

    def _on_krita_theme_changed(self, *args):
        """Krita 深浅主题切换（含启动时首帧）：重新应用主题 QSS 并重建图层树"""
        try:
            self._hover_active = False
            self.hover_preview.hide()
            clear_theme_cache()
            self.apply_theme_qss()
            self.refresh_tree()
        except Exception:
            pass

    def update_tree_states(self, *args):
        """轻量级刷新：仅更新现有树节点的状态、缩略图和徽章，不重建整个树"""
        if self._updating_ui or not IN_KRITA or self._loading:
            return
        def _update(item):
            w = self.tree.itemWidget(item, 0)
            if w: w.refresh_state()
            for i in range(item.childCount()):
                _update(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            _update(self.tree.topLevelItem(i))

    def _on_image_modified(self, *args):
        """图像内容变化（作画/编辑）→ 节流批量刷新缩略图，避免轮询全量重载"""
        if self._loading:
            return
        self._content_flush_timer.start()

    def _flush_thumbnails(self):
        """内容变化节流到期：所有可见项重启缩略图定时器，覆盖更新缓存"""
        if self._updating_ui:
            self._content_flush_timer.start()
            return
        # 滚动中：推迟到滚动结束后再刷新缩略图
        if time.monotonic() - getattr(self, '_last_scroll_ts', 0.0) < 0.5:
            self._content_flush_timer.start(300)
            return
        # 同步清空悬停大图缓存，下次悬停生成最新内容
        self.hover_preview.clear_cache()
        def _touch(item):
            w = self.tree.itemWidget(item, 0)
            if w and w.node and w._is_tree_visible():
                w._thumb_timer.start()
            for i in range(item.childCount()):
                _touch(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            _touch(self.tree.topLevelItem(i))

    def _on_image_created(self, *args):
        """Krita 创建/加载新图像时进入批处理模式，暂停同步以避免阻塞主线程"""
        self._loading = True
        self._loading_timer.start(2000)

    def _on_view_changed(self, *args):
        """视图切换（含文件加载期间的早期信号）：防抖后重建树"""
        self._loading = True
        self._loading_timer.start(1000)

    def _finish_loading(self):
        """加载完成（防抖无新信号）后退出加载模式并重建树"""
        self._loading = False
        self._updating_ui = False
        clear_theme_cache()
        self.apply_theme_qss()
        self.refresh_tree()

    def canvasChanged(self, canvas):
        """Krita 内置接口，画布切换时自动调用"""
        self.canvas = canvas
        # 进入加载模式并防抖：文件加载时 canvasChanged 会连续触发多次，
        # 避免每次都重建整个图层树；apply_theme_qss 也延后到防抖结束
        self._loading = True
        self._loading_timer.start(1500)

    def apply_theme_qss(self):
        """应用平坦化、极简统一的主题 QSS 样式表"""
        t = get_theme()
        cfg = get_config()
        ui_font = self._ui_font_size()

        # 主题变更时清除图标缓存（颜色变了需要重新渲染）
        clear_icon_cache()

        # 系统 QToolTip 颜色修复（双重保障：QPalette + QSS）
        pal = QApplication.instance().palette()
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(t.BG_BASE))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(t.TOOLTIP_TEXT))
        QApplication.instance().setPalette(pal)

        self.setStyleSheet(f"""
            QWidget {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: {ui_font}px;
                color: {t.TEXT_MAIN};
            }}
            QToolTip {{
                background-color: {t.BG_BASE};
                color: {t.TOOLTIP_TEXT};
                border: 1px solid {t.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: {ui_font}px;
            }}
            QFrame#ToolbarFrame {{
                background-color: {t.BG_BASE};
                border-bottom: 1px solid rgba({t.ACCENT_RGB}, 0.16);
            }}
            QFrame#PropCard {{
                background-color: {t.BG_DARK};
                /* 属性栏外框不使用 Mid 深色线，避免浅色主题出现黑色描边 */
                border: none;
                border-radius: 4px;
                padding: 1px 4px;
            }}
            QFrame#PropCard QToolButton {{
                background-color: transparent;
                color: {t.TEXT_MAIN};
            }}
            QFrame#ToolbarFrame QToolButton {{
                color: {t.TEXT_MAIN};
            }}
            QLineEdit {{
                background-color: {t.BG_DARK};
                color: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                border-radius: 4px;
                padding: 3px 8px;
                font-size: {ui_font}px;
            }}
            QLineEdit:focus {{
                border: 1px solid {t.ACCENT};
            }}
            QToolButton, QPushButton {{
                background: transparent;
                color: {t.TEXT_MAIN};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 2px;
            }}
            QToolButton:hover, QPushButton:hover {{
                background-color: rgba({t.ACCENT_RGB}, 0.12);
                border: 1px solid rgba({t.ACCENT_RGB}, 0.25);
            }}
            QToolButton:pressed, QPushButton:pressed {{
                background-color: rgba({t.ACCENT_RGB}, 0.25);
            }}
            QMenu {{
                background-color: {t.BG_DARK};
                color: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                border-radius: 6px;
                padding: 4px 0px;
            }}
            QMenu::item {{
                padding: 5px 24px 5px 12px;
                border-radius: 3px;
                margin: 1px 4px;
                font-size: {ui_font}px;
            }}
            QMenu::item:selected {{
                background-color: rgba({t.ACCENT_RGB}, 0.18);
                color: {t.TEXT_MAIN};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {t.BORDER};
                margin: 4px 8px;
            }}
        """)

        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QTreeWidget::branch {{
                border-image: none;
                image: none;
                width: 0px;
            }}
            QTreeWidget::item {{
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
                margin: 0px;
            }}
            QTreeWidget::item:hover {{
                border: 1px solid rgba({t.ACCENT_RGB}, 0.35);
                background-color: rgba({t.ACCENT_RGB}, 0.08);
            }}
            QTreeWidget::item:selected {{
                border: 1px solid {t.ACCENT};
                background-color: rgba({t.ACCENT_RGB}, 0.18);
            }}
            QTreeWidget::drop-indicator {{
                background-color: {t.ACCENT};
                height: 6px;
                min-height: 6px;
                border-radius: 3px;
            }}
        """)

        # 工具栏图标在 QSS 应用前就已创建；主题切换/启动时序变化后必须重建，
        # 否则浅色背景上会残留深色主题的白色图标
        if hasattr(self, 'btn_new_paint'):
            self._rebuild_toolbar_icons()
        if hasattr(self, 'prop_card'):
            self._rebuild_property_bar_theme()
        self._last_theme_signature = self._theme_palette_signature()

    def _theme_palette_signature(self):
        """返回影响插件主题的 palette 摘要，用于 PaletteChange 去重"""
        t = get_theme()
        return (t.BG_DARK, t.BG_BASE, t.BG_ALT, t.TEXT_MAIN, t.TEXT_MUTED, t.ACCENT)

    def _refresh_after_palette_change(self):
        """QWidget palette 变化兜底：Krita Window 信号未到达时也刷新主题"""
        self._theme_refresh_scheduled = False
        self._refresh_theme_if_needed()

    def _refresh_theme_if_needed(self):
        """轮询检查主题摘要，覆盖 Krita/Qt 未向 dock 转发 palette 事件的情况"""
        if self._theme_palette_signature() != self._last_theme_signature:
            self._on_krita_theme_changed()

    def changeEvent(self, event):
        """监听 Qt palette 变化，覆盖 Krita 主题切换的所有时序"""
        super().changeEvent(event)
        try:
            event_type = event.type()
            event_types = []
            qt_event_type = getattr(QEvent, 'Type', QEvent)
            for name in ('PaletteChange', 'ApplicationPaletteChange'):
                value = getattr(qt_event_type, name, None)
                if value is not None:
                    event_types.append(value)
            if event_type in event_types and not self._theme_refresh_scheduled:
                self._theme_refresh_scheduled = True
                QTimer.singleShot(0, self._refresh_after_palette_change)
        except Exception:
            pass

    # ====== UI 结构构建 ======
    def _ui_font_size(self) -> int:
        """计算全局 UI 字号：配置优先，0 时跟随缩略图自动推导"""
        cfg = get_config()
        if cfg.font_size > 0:
            return max(8, min(20, cfg.font_size))
        return max(9, min(14, (cfg.thumb_size // 2) - 1))

    def _toolbar_icon_size(self) -> int:
        """顶部导航栏图标大小 (px)"""
        cfg = get_config()
        return max(10, min(48, cfg.toolbar_icon_size))

    def _toolbar_btn_size(self) -> int:
        """导航栏按钮外框大小 = 图标 + 内边距"""
        return self._toolbar_icon_size() + 6

    def _apply_responsive_toolbar(self):
        """自适应布局：所有按钮始终可见，宽度不足时自动折行成双行/多行显示，
        不再按优先级收起按钮（面板变窄时高度随之增高，腾出空间由换行解决）"""
        frame = getattr(self, 'toolbar_frame', None)
        if frame is None:
            return
        lay = frame.layout()
        if lay is None:
            return
        # 全部按钮保持可见（换行由 FlowLayout 处理）
        for btn, _prio in getattr(self, '_toolbar_buttons', []):
            btn.setVisible(True)
        cfg = get_config()
        if not cfg.adaptive_layout:
            # 关闭自适应：固定单行高度（FlowLayout 在极端窄宽下仍会折行）
            frame.setMinimumHeight(0)
            frame.setMaximumHeight(16777215)
            frame.setFixedHeight(self._toolbar_btn_size() + 4)
        else:
            # 自适应：高度交给 FlowLayout 的 heightForWidth 计算
            frame.setMinimumHeight(0)
            frame.setMaximumHeight(16777215)
            lay.invalidate()
            frame.updateGeometry()
        # 通知外层布局重新计算（工具栏高度变化会推动下方控件）
        outer = frame.parentWidget()
        while outer is not None:
            if outer.layout() is not None:
                outer.layout().invalidate()
            outer = outer.parentWidget()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_toolbar()

    @staticmethod
    def _enable_tablet_tracking_recursive(widget):
        """递归开启 widget 子树所有控件的 WA_TabletTracking
        （数位笔悬停事件不被 Qt 吞掉的前提，支持 tooltip 与高亮）"""
        if widget is None:
            return
        widget.setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)
        try:
            for w in widget.findChildren(QWidget):
                w.setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)
        except Exception:
            pass

    def _build_toolbar(self, parent_layout):
        self.toolbar_frame = QFrame()
        self.toolbar_frame.setObjectName("ToolbarFrame")
        icon_sz = self._toolbar_icon_size()
        btn_sz = self._toolbar_btn_size()

        # 自适应双行工具栏：宽度不足时按钮自动折行，不再隐藏
        tb_layout = FlowLayout(self.toolbar_frame, margin=0, h_spacing=2, v_spacing=2)
        tb_layout.setContentsMargins(2, 1, 2, 1)

        t = get_theme()
        self._toolbar_buttons = []

        def add_tb_btn(icon_name, tooltip, muted=True, prio=0, size=None):
            """创建导航栏按钮并登记到工具栏按钮列表"""
            b = QToolButton()
            b.setFixedSize(size or btn_sz, size or btn_sz)
            icon_color = t.TEXT_MUTED if muted else t.TEXT_MAIN
            b.setIcon(get_lucide_icon(icon_name, icon_color, icon_sz))
            b.setToolTip(tooltip)
            self._toolbar_buttons.append((b, prio))
            return b

        # 1. 新建颜料图层 (单独按钮) — 核心，永不收起
        self.btn_new_paint = add_tb_btn("plus", "新建颜料图层 (Paint Layer)", muted=False, prio=0)
        self.btn_new_paint.clicked.connect(lambda: self._create_layer("paintlayer"))
        tb_layout.addWidget(self.btn_new_paint)

        # 2. 新建图层组 (文件夹图标) — 核心
        self.btn_new_group = add_tb_btn("folder", "新建图层组 (Group Layer)", muted=False, prio=0)
        self.btn_new_group.clicked.connect(lambda: self._create_layer("grouplayer"))
        tb_layout.addWidget(self.btn_new_group)

        # 3. 更多图层类型 (纯下拉菜单) — 核心
        self.btn_new_more = add_tb_btn("chevron-down", "更多图层类型...", muted=False, prio=0)

        self.new_menu = QMenu(self)
        types = [
            ("vectorlayer", "矢量图层 (Vector Layer)", "type"),
            ("filterlayer", "滤镜图层 (Filter Layer)", "wand-2"),
            ("adjustmentlayer", "调整图层 (Adjustment Layer)", "sliders"),
            ("filllayer", "填充图层 (Fill Layer)", "palette"),
            ("clonelayer", "克隆图层 (Clone Layer)", "copy"),
            ("filelayer", "文件图层 (File Layer)", "layers"),
            ("SEP", "", ""),
            ("ACTION:add_new_transparency_mask", "透明度蒙版 (Transparency Mask)", "eye-off"),
            ("ACTION:add_new_filter_mask", "滤镜蒙版 (Filter Mask)", "wand-2"),
            ("ACTION:add_new_colorize_mask", "着色蒙版 (Colorize Mask)", "palette"),
            ("ACTION:add_new_transform_mask", "变换蒙版 (Transform Mask)", "move"),
        ]
        for t_code, t_name, t_icon in types:
            if t_code == "SEP":
                self.new_menu.addSeparator()
                continue
            act = QAction(get_lucide_icon(t_icon, t.TEXT_MAIN, icon_sz), t_name, self.new_menu)
            if t_code.startswith("ACTION:"):
                action_name = t_code.split(":", 1)[1]
                act.triggered.connect(lambda checked, a=action_name: self._trigger_action(a))
            else:
                act.triggered.connect(lambda checked, c=t_code: self._create_layer(c))
            self.new_menu.addAction(act)

        # 不使用 PopupMode 以避免原生绘制额外的箭头，直接监听点击弹出
        self.btn_new_more.clicked.connect(lambda: self.new_menu.exec(self.btn_new_more.mapToGlobal(self.btn_new_more.rect().bottomLeft())))
        tb_layout.addWidget(self.btn_new_more)

        # 复制图层
        self.btn_dup = add_tb_btn("copy", "复制当前图层", muted=True, prio=2)
        self.btn_dup.clicked.connect(self._duplicate_layer)
        tb_layout.addWidget(self.btn_dup)

        # 删除图层
        self.btn_del = add_tb_btn("trash-2", "删除当前图层", muted=True, prio=2)
        self.btn_del.clicked.connect(self._delete_layer)
        tb_layout.addWidget(self.btn_del)

        # 上移 / 下移图层
        self.btn_up = add_tb_btn("arrow-up", "向上移动图层", muted=True, prio=2)
        self.btn_up.clicked.connect(lambda: self._move_layer("up"))
        tb_layout.addWidget(self.btn_up)

        self.btn_down = add_tb_btn("arrow-down", "向下移动图层", muted=True, prio=2)
        self.btn_down.clicked.connect(lambda: self._move_layer("down"))
        tb_layout.addWidget(self.btn_down)

        # 颜色标记快捷按钮
        self.btn_color_label = add_tb_btn("tag", "设置当前图层颜色标记", muted=True, prio=1)
        self.btn_color_label.clicked.connect(self._show_color_label_picker)
        tb_layout.addWidget(self.btn_color_label)

        # 图层属性/操作菜单按钮 (对应右键菜单)
        self.btn_layer_menu = add_tb_btn("more-horizontal", "当前图层操作菜单", muted=True, prio=1)
        self.btn_layer_menu.clicked.connect(self._show_active_layer_menu)
        tb_layout.addWidget(self.btn_layer_menu)

        # 搜索按钮
        self.btn_search = add_tb_btn("search", "搜索图层名称", muted=True, prio=3)
        self.btn_search.clicked.connect(lambda: self.search_input.setVisible(not self.search_input.isVisible()))
        tb_layout.addWidget(self.btn_search)

        # 偏好设置按钮 ⚙️
        self.btn_settings = add_tb_btn("settings", "图层面板偏好设置", muted=True, prio=0)
        self.btn_settings.clicked.connect(self._open_settings_dialog)
        tb_layout.addWidget(self.btn_settings)

        parent_layout.addWidget(self.toolbar_frame)

    def _rebuild_toolbar_icons(self):
        """配置变化后刷新导航栏：图标颜色/大小/按钮尺寸跟随新配置"""
        t = get_theme()
        icon_sz = self._toolbar_icon_size()
        btn_sz = self._toolbar_btn_size()
        mapping = {
            self.btn_new_paint: ("plus", False),
            self.btn_new_group: ("folder", False),
            self.btn_new_more: ("chevron-down", False),
            self.btn_dup: ("copy", True),
            self.btn_del: ("trash-2", True),
            self.btn_up: ("arrow-up", True),
            self.btn_down: ("arrow-down", True),
            self.btn_color_label: ("tag", True),
            self.btn_layer_menu: ("more-horizontal", True),
            self.btn_search: ("search", True),
            self.btn_settings: ("settings", True),
        }
        for btn, (icon_name, muted) in mapping.items():
            btn.setFixedSize(btn_sz, btn_sz)
            icon_color = t.TEXT_MUTED if muted else t.TEXT_MAIN
            btn.setIcon(get_lucide_icon(icon_name, icon_color, icon_sz))
        # 按钮尺寸变化后刷新换行布局与高度
        lay = getattr(self.toolbar_frame, 'layout', None)
        if lay is not None and lay() is not None:
            lay().invalidate()
            self.toolbar_frame.updateGeometry()
        # 重建下拉菜单图标
        if hasattr(self, 'new_menu'):
            self.new_menu.clear()
            types = [
                ("vectorlayer", "矢量图层 (Vector Layer)", "type"),
                ("filterlayer", "滤镜图层 (Filter Layer)", "wand-2"),
                ("adjustmentlayer", "调整图层 (Adjustment Layer)", "sliders"),
                ("filllayer", "填充图层 (Fill Layer)", "palette"),
                ("clonelayer", "克隆图层 (Clone Layer)", "copy"),
                ("filelayer", "文件图层 (File Layer)", "layers"),
                ("SEP", "", ""),
                ("ACTION:add_new_transparency_mask", "透明度蒙版 (Transparency Mask)", "eye-off"),
                ("ACTION:add_new_filter_mask", "滤镜蒙版 (Filter Mask)", "wand-2"),
                ("ACTION:add_new_colorize_mask", "着色蒙版 (Colorize Mask)", "palette"),
                ("ACTION:add_new_transform_mask", "变换蒙版 (Transform Mask)", "move"),
            ]
            for t_code, t_name, t_icon in types:
                if t_code == "SEP":
                    self.new_menu.addSeparator()
                    continue
                act = QAction(get_lucide_icon(t_icon, t.TEXT_MAIN, icon_sz), t_name, self.new_menu)
                if t_code.startswith("ACTION:"):
                    action_name = t_code.split(":", 1)[1]
                    act.triggered.connect(lambda checked, a=action_name: self._trigger_action(a))
                else:
                    act.triggered.connect(lambda checked, c=t_code: self._create_layer(c))
                self.new_menu.addAction(act)

    def _build_property_bar(self, parent_layout):
        self.prop_card = QFrame()
        self.prop_card.setObjectName("PropCard")
        bar_h = max(24, self._toolbar_icon_size() + 10)
        self.prop_card.setFixedHeight(bar_h)

        p_layout = QHBoxLayout(self.prop_card)
        p_layout.setContentsMargins(2, 2, 2, 2)
        p_layout.setSpacing(4)

        # 多级分类混合模式选择按钮
        self.btn_blend = QToolButton()
        self.btn_blend.setObjectName("BlendModeBtn")
        from .qt_compat import QSizePolicy
        self.btn_blend.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_blend.setFixedHeight(bar_h - 4)
        self.btn_blend.setText("正常")
        ui_font = self._ui_font_size()
        self.btn_blend.setStyleSheet(f"font-size: {max(9, ui_font - 1)}px;")

        self.blend_menu = create_categorized_blending_menu(self.btn_blend, self._on_blend_selected)
        self.btn_blend.clicked.connect(lambda: self.blend_menu.exec(self.btn_blend.mapToGlobal(self.btn_blend.rect().bottomLeft())))
        p_layout.addWidget(self.btn_blend, 1)

        # 官方 KisSliderSpinBox 风格不透明度大滑块
        self.opacity_bar = OpacityBarWidget(self.prop_card)
        self.opacity_bar.setFixedHeight(bar_h - 4)
        self.opacity_bar.valueChanged.connect(self._on_opacity_bar_changed)
        p_layout.addWidget(self.opacity_bar, 2)

        parent_layout.addWidget(self.prop_card)

    def _rebuild_property_bar_theme(self):
        """配置变化后刷新属性栏高度与字号"""
        if not hasattr(self, 'prop_card'):
            return
        bar_h = max(24, self._toolbar_icon_size() + 10)
        self.prop_card.setFixedHeight(bar_h)
        self.btn_blend.setFixedHeight(bar_h - 4)
        self.opacity_bar.setFixedHeight(bar_h - 4)
        ui_font = self._ui_font_size()
        self.btn_blend.setStyleSheet(f"font-size: {max(9, ui_font - 1)}px;")
        self.opacity_bar.update()

    def _open_settings_dialog(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._hover_active = False
            self.hover_preview.hide()
            clear_theme_cache()
            # 重新应用主题 QSS + 重建图标/字号/尺寸（配置可能已变化）
            self.apply_theme_qss()
            self._rebuild_toolbar_icons()
            self._rebuild_property_bar_theme()
            self._apply_responsive_toolbar()
            self.refresh_tree()


    # ====== 悬停预览接口 ======
    def _is_cursor_in_widget(self, widget, global_pos):
        """判断全局鼠标位置是否在指定 QWidget 内"""
        if not widget or not widget.isVisible():
            return False
        return widget.rect().contains(widget.mapFromGlobal(global_pos))

    def _guard_hover_cursor(self):
        """取消鼠标已离开图层列表后的延迟弹出，避免悬停预览竞态"""
        tree = getattr(self, 'tree', None)
        if not tree:
            return
        pending = tree._hover_timer.isActive()
        visible = self.hover_preview.isVisible() or getattr(self, '_hover_active', False)
        if not pending and not visible:
            return

        global_pos = QCursor.pos()
        in_tree = self._is_cursor_in_widget(tree.viewport(), global_pos)
        in_preview = self._is_cursor_in_widget(self.hover_preview, global_pos)
        if in_tree or in_preview:
            return

        tree._hover_timer.stop()
        tree._hover_item = None
        self.reset_hover_state()

    def _on_row_mouse_move(self, row_widget, global_pos):
        # 滚动进行中或刚结束（250ms 内）：抑制 hover 预览触发，保证滚动流畅
        if time.monotonic() - getattr(self, '_last_scroll_ts', 0.0) < 0.25:
            self.tree._hover_timer.stop()
            return
        from .config import get_config
        cfg = get_config()
        if not cfg.enable_hover_preview or not row_widget or not row_widget.node:
            return

        if hasattr(self, '_leave_timer'):
            self._leave_timer.stop()

        item = getattr(row_widget, 'tree_item', None)
        node = getattr(row_widget, 'node', None)
        if not node:
            return

        node_uid = str(node.uniqueId()) if hasattr(node, 'uniqueId') else str(id(node))
        active_uid = getattr(self, '_active_hover_uid', None)

        if node_uid != active_uid:
            # 鼠标切换到了【新的图层项】
            self._active_hover_uid = node_uid
            self.tree._hover_item = item
            self._hover_node = node
            self._hover_global_pos = global_pos

            if getattr(self, '_hover_active', False) or self.hover_preview.isVisible():
                # 浮窗开启状态下：0ms 瞬间无缝切换新图层预览！
                self.show_hover_preview(node, global_pos)
            else:
                self.tree._hover_timer.start(1000)
        else:
            # 鼠标在【同一个图层项】上面移动 (无论经过 40x40 缩略图、图标、名字还是空白)
            if self.hover_preview.isVisible() or getattr(self, '_hover_active', False):
                # 浮窗已经在显示中：【绝对什么都不做！】
                # 不重新渲染！不重新加载！不更新 QSS！不平移位置！彻底静止！
                pass
            elif not self.tree._hover_timer.isActive():
                self.tree._hover_timer.start(1000)

    def _do_switch_layer_preview(self):
        if hasattr(self, '_hover_node') and self._hover_node:
            pos = getattr(self, '_hover_global_pos', QCursor.pos())
            self.show_hover_preview(self._hover_node, pos)

    def _on_row_mouse_leave(self, row_widget):
        if not hasattr(self, '_leave_timer'):
            self._leave_timer = QTimer(self)
            self._leave_timer.setSingleShot(True)
            self._leave_timer.timeout.connect(self._do_deferred_leave)
        self._leave_timer.start(1500)

    def _do_deferred_leave(self):
        global_pos = QCursor.pos()
        w = QApplication.widgetAt(global_pos)
        if w:
            if w == self or self.isAncestorOf(w):
                # 鼠标依然在图层面板内部任何子控件上 (包含列表, 行, 按钮, 滚动条, 空白)
                return
            if hasattr(self, 'hover_preview') and self.hover_preview:
                if w == self.hover_preview or self.hover_preview.isAncestorOf(w):
                    # 鼠标在悬停预览卡片上
                    return

        # 鼠标彻底离开了图层面板与预览卡片
        if hasattr(self, 'tree') and self.tree:
            self.tree._hover_timer.stop()
            self.tree._hover_item = None
        self.reset_hover_state()

    def show_hover_preview(self, node, global_pos):
        self._hover_active = True
        self.hover_preview.update_node(node, force=False, docker_widget=self)
        self.hover_preview.popup_at(global_pos, docker_widget=self)
        if not self.hover_preview.isVisible():
            self.hover_preview.show()
        self.hover_preview.raise_()
        self.hover_preview.update()

    def hide_hover_preview(self):
        self.hover_preview.hide()

    def reset_hover_state(self):
        """鼠标离开图层面板时重置悬停预览状态"""
        self._hover_active = False
        self._active_hover_uid = None
        self.hover_preview.hide()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.reset_hover_state()


    def refresh_canvas(self, delay=60):
        """延时刷新画布，多个连续操作时防抖"""
        if not IN_KRITA:
            return
        QTimer.singleShot(delay, self._do_refresh_canvas)

    def _do_refresh_canvas(self):
        if IN_KRITA:
            doc = Krita.instance().activeDocument()
            if doc:
                doc.refreshProjection()

    # ====== 树形刷新与同步 ======
    def request_tree_refresh(self, delay=60):
        if self._loading:
            return
        QTimer.singleShot(delay, self.refresh_tree)

    def refresh_tree(self):
        if not IN_KRITA or self._updating_ui or self._loading:
            return

        self._updating_ui = True
        self.tree.setUpdatesEnabled(False)

        doc = Krita.instance().activeDocument()
        if not doc:
            self.tree.clear()
            self.tree.setUpdatesEnabled(True)
            self._updating_ui = False
            return

        # 备份当前面板的多选状态，防止定时同步机制清空多选
        self._selected_uids = set()
        for item in self.tree.selectedItems():
            w = self.tree.itemWidget(item, 0)
            if w and w.node:
                self._selected_uids.add(str(w.node.uniqueId()))

        active_node = doc.activeNode()
        root = doc.rootNode()

        self._sync_node_tree(root, None, active_node)

        # 多选状态精准还原
        if len(self._selected_uids) > 1:
            self.tree.blockSignals(True)
            all_items = []
            def collect_all_items(parent_item):
                cnt = parent_item.childCount() if parent_item else self.tree.topLevelItemCount()
                for i in range(cnt):
                    it = parent_item.child(i) if parent_item else self.tree.topLevelItem(i)
                    all_items.append(it)
                    collect_all_items(it)
            collect_all_items(None)

            for item in all_items:
                w = self.tree.itemWidget(item, 0)
                if w and w.node and str(w.node.uniqueId()) in self._selected_uids:
                    item.setSelected(True)
            self.tree.blockSignals(False)

        if active_node:
            self._update_property_bar_for_node(active_node)

        self.tree.setUpdatesEnabled(True)
        self._updating_ui = False

    def _sync_node_tree(self, parent_node, parent_tree_item, active_node):
        from .layer_item import LayerRowWidget
        from .config import get_config
        cfg = get_config()
        children = parent_node.childNodes()
        if not cfg.show_selection_masks:
            children = [n for n in children if n.type() != "selectionmask"]
        target_nodes = list(reversed(children))
        
        current_items = []
        if parent_tree_item:
            for i in range(parent_tree_item.childCount()):
                current_items.append(parent_tree_item.child(i))
        else:
            for i in range(self.tree.topLevelItemCount()):
                current_items.append(self.tree.topLevelItem(i))
                
        item_map = {}
        for item in current_items:
            w = self.tree.itemWidget(item, 0)
            if w and w.node:
                item_map[str(w.node.uniqueId())] = item
                
        for i, node in enumerate(target_nodes):
            uid = str(node.uniqueId())
            if uid in item_map:
                item = item_map[uid]
                del item_map[uid]
                
                if parent_tree_item:
                    current_idx = parent_tree_item.indexOfChild(item)
                    if current_idx != i:
                        parent_tree_item.takeChild(current_idx)
                        parent_tree_item.insertChild(i, item)
                else:
                    current_idx = self.tree.indexOfTopLevelItem(item)
                    if current_idx != i:
                        self.tree.takeTopLevelItem(current_idx)
                        self.tree.insertTopLevelItem(i, item)
                        
                w = self.tree.itemWidget(item, 0)
                if not w:
                    w = LayerRowWidget(node, item, self)
                    self.tree.setItemWidget(item, 0, w)
                    
                needs_thumb = (active_node is None) or (active_node and node.uniqueId() == active_node.uniqueId())
                if hasattr(w, 'refresh_state_with_thumb'):
                    w.refresh_state_with_thumb(needs_thumb)
                else:
                    w.refresh_state()
            else:
                item = QTreeWidgetItem()
                if parent_tree_item:
                    parent_tree_item.insertChild(i, item)
                else:
                    self.tree.insertTopLevelItem(i, item)
                    
                w = LayerRowWidget(node, item, self)
                self.tree.setItemWidget(item, 0, w)
                
                if self._expanded_uids is None:
                    item.setExpanded(True)
                else:
                    item.setExpanded(str(node.uniqueId()) in self._expanded_uids)
                
            # 仅在非多选状态下设置 setCurrentItem
            has_multi = len(getattr(self, '_selected_uids', set())) > 1
            if active_node and node.uniqueId() == active_node.uniqueId() and not has_multi:
                self.tree.setCurrentItem(item)
                
            if len(node.childNodes()) > 0:
                self._sync_node_tree(node, item, active_node)
                
        for uid, item in item_map.items():
            if parent_tree_item:
                parent_tree_item.removeChild(item)
            else:
                idx = self.tree.indexOfTopLevelItem(item)
                if idx >= 0:
                    self.tree.takeTopLevelItem(idx)

    def _update_property_bar_for_node(self, node):
        if not node:
            return

        is_group = (node.type() == "grouplayer")
        if is_group and hasattr(node, "passThroughMode") and node.passThroughMode():
            mode_name = "穿透"
        else:
            b_mode = node.blendingMode()
            mode_name = get_blending_mode_name(b_mode)

        self.btn_blend.setText(mode_name)

        op_val = round(node.opacity() / 255.0 * 100)
        self.opacity_bar.blockSignals(True)
        self.opacity_bar.setValue(op_val)
        self.opacity_bar.blockSignals(False)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'sync_timer') and not self.sync_timer.isActive():
            self.sync_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, 'sync_timer') and self.sync_timer.isActive():
            self.sync_timer.stop()

    def _sync_with_krita(self):
        # Krita 主题切换偶尔不会向 pykrita dock 派发 PaletteChange，
        # 用已有同步定时器做轻量签名检查，最多延迟一个同步周期
        self._refresh_theme_if_needed()
        if not IN_KRITA or self._updating_ui or self._loading:
            return
        # 滚动进行中或刚结束：跳过轮询同步，避免周期性全量刷新打断滚动
        if time.monotonic() - getattr(self, '_last_scroll_ts', 0.0) < 0.5:
            return
        buttons = QApplication.mouseButtons()
        no_btn = getattr(Qt, 'NoButton', getattr(getattr(Qt, 'MouseButton', None), 'NoButton', 0))
        if buttons != no_btn:
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            return

        curr_node = doc.activeNode()
        if curr_node:
            self._update_property_bar_for_node(curr_node)

        self.refresh_tree()
        self._lazy_refresh_stale_thumbs()

    def _lazy_refresh_stale_thumbs(self):
        """周期兜底：可见项缩略图生成超过 1s 则重载（Krita 6 无内容修改信号，靠此保证更新）"""
        now = time.monotonic()
        stale = False
        def _check(item):
            nonlocal stale
            w = self.tree.itemWidget(item, 0)
            if w and w.node and w._is_tree_visible():
                if now - getattr(w, '_thumb_generated_ts', 0.0) > 1.0:
                    stale = True
                    w._thumb_timer.start()
            for i in range(item.childCount()):
                _check(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            _check(self.tree.topLevelItem(i))
        if stale:
            # 行缩略图更新时同步失效悬停大图缓存，保证悬停预览同样更新
            self.hover_preview.clear_cache()

    # ====== 属性事件 ======
    def _on_item_expanded(self, item):
        """组展开时懒加载子项缩略图（递归处理已展开的子组）"""
        for i in range(item.childCount()):
            child_item = item.child(i)
            w = self.tree.itemWidget(child_item, 0)
            if w:
                w._thumb_timer.start()
            if child_item.childCount() > 0 and child_item.isExpanded():
                self._on_item_expanded(child_item)

    # ====== 独显模式 (Solo Mode) ======
    def enable_solo(self, node):
        if not IN_KRITA or not node:
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            return

        target_uid = str(node.uniqueId())
        if getattr(self, '_solo_node_uid', None) == target_uid:
            self.disable_solo()
            return

        if getattr(self, '_solo_node_uid', None):
            self.disable_solo()

        # 1. 收集目标节点的所有祖先节点 UID (保证全路径父图层组 visible = True)
        ancestor_uids = set()
        curr = node
        while curr:
            ancestor_uids.add(str(curr.uniqueId()))
            curr = curr.parentNode()

        # 2. 收集目标节点的所有后代节点 UID (如果目标是图层组，子节点也保持 visible = True)
        descendant_uids = set()
        def collect_descendants(n):
            descendant_uids.add(str(n.uniqueId()))
            for c in list(n.childNodes()):
                collect_descendants(c)
        collect_descendants(node)

        keep_visible_uids = ancestor_uids.union(descendant_uids)

        self._solo_backup = {}
        self._solo_raw_mode = True

        def backup_and_solo(n):
            uid = str(n.uniqueId())
            vis = n.visible()
            op = n.opacity() if hasattr(n, 'opacity') else 255
            bm = n.blendingMode() if hasattr(n, 'blendingMode') else "normal"
            ialpha = n.inheritAlpha() if hasattr(n, 'inheritAlpha') else False
            self._solo_backup[uid] = (vis, op, bm, ialpha)

            if uid in keep_visible_uids:
                n.setVisible(True)
            else:
                n.setVisible(False)

            if uid == target_uid:
                # 独显默认启用纯净原色模式：100% 不透明度 + Normal 混合模式 + 关闭继承透明度
                if hasattr(n, 'setOpacity'):
                    n.setOpacity(255)
                if hasattr(n, 'setBlendingMode'):
                    n.setBlendingMode("normal")
                if hasattr(n, 'setInheritAlpha'):
                    n.setInheritAlpha(False)

            for child in list(n.childNodes()):
                backup_and_solo(child)

        backup_and_solo(doc.rootNode())
        self._solo_node_uid = target_uid
        doc.setActiveNode(node)
        self.refresh_canvas()
        self.refresh_tree()

    def toggle_solo_raw_mode(self):
        """独显模式下在 纯净原色模式 (100%不透明/Normal) 与 原图层效果 (原不透明度/混合模式) 之间一键切换"""
        if not IN_KRITA or not getattr(self, '_solo_node_uid', None):
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            return

        target_uid = self._solo_node_uid
        if target_uid not in getattr(self, '_solo_backup', {}):
            return

        target_node = None
        def find_node(n):
            nonlocal target_node
            if str(n.uniqueId()) == target_uid:
                target_node = n
                return
            for c in list(n.childNodes()):
                find_node(c)

        find_node(doc.rootNode())
        if not target_node:
            return

        self._solo_raw_mode = not getattr(self, '_solo_raw_mode', True)
        vis, orig_op, orig_bm, orig_ialpha = self._solo_backup[target_uid]

        if self._solo_raw_mode:
            # 切换为纯净原色
            if hasattr(target_node, 'setOpacity'): target_node.setOpacity(255)
            if hasattr(target_node, 'setBlendingMode'): target_node.setBlendingMode("normal")
            if hasattr(target_node, 'setInheritAlpha'): target_node.setInheritAlpha(False)
        else:
            # 切换为原图层效果
            if hasattr(target_node, 'setOpacity'): target_node.setOpacity(orig_op)
            if hasattr(target_node, 'setBlendingMode'): target_node.setBlendingMode(orig_bm)
            if hasattr(target_node, 'setInheritAlpha'): target_node.setInheritAlpha(orig_ialpha)

        self.refresh_canvas()
        self.refresh_tree()

    def disable_solo(self):
        if not IN_KRITA or not getattr(self, '_solo_node_uid', None):
            return
        doc = Krita.instance().activeDocument()
        if doc and getattr(self, '_solo_backup', None):
            def restore_node(n):
                uid = str(n.uniqueId())
                if uid in self._solo_backup:
                    vis, op, bm, ialpha = self._solo_backup[uid]
                    n.setVisible(vis)
                    if hasattr(n, 'setOpacity'):
                        n.setOpacity(op)
                    if hasattr(n, 'setBlendingMode'):
                        n.setBlendingMode(bm)
                    if hasattr(n, 'setInheritAlpha'):
                        n.setInheritAlpha(ialpha)
                for child in list(n.childNodes()):
                    restore_node(child)

            restore_node(doc.rootNode())

        self._solo_node_uid = None
        self._solo_raw_mode = True
        self._solo_backup = {}
        self.refresh_canvas()
        self.refresh_tree()

    def _on_tree_selection_changed(self):
        if self._updating_ui or not IN_KRITA:
            return
        selected_items = self.tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            row_widget = self.tree.itemWidget(item, 0)
            if row_widget and row_widget.node:
                # 处于独显模式时，选中其他图层自动取消独显
                solo_uid = getattr(self, '_solo_node_uid', None)
                if solo_uid and str(row_widget.node.uniqueId()) != solo_uid:
                    self.disable_solo()
                    return
                doc = Krita.instance().activeDocument()
                if doc and doc.activeNode() != row_widget.node:
                    doc.setActiveNode(row_widget.node)
                    self._update_property_bar_for_node(row_widget.node)

    def _on_blend_selected(self, mode_id):
        if self._updating_ui or not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        node = doc.activeNode() if doc else None
        if node:
            if mode_id == "pass_through" and node.type() == "grouplayer":
                if hasattr(node, "setPassThroughMode"):
                    node.setPassThroughMode(True)
            else:
                if node.type() == "grouplayer" and hasattr(node, "setPassThroughMode"):
                    node.setPassThroughMode(False)
                node.setBlendingMode(mode_id)

            mode_name = get_blending_mode_name(mode_id)
            self.btn_blend.setText(mode_name)
            self.refresh_canvas()
            self.update_tree_states()

    def _on_opacity_bar_changed(self, percent_val):
        if self._updating_ui or not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if doc and doc.activeNode():
            opacity_255 = round(percent_val / 100.0 * 255)
            doc.activeNode().setOpacity(opacity_255)
            self.update_tree_states()
            try:
                doc.refreshProjection()
            except Exception:
                self.refresh_canvas(delay=0)

    def _filter_layers(self, text):
        search_kw = text.strip().lower()
        def filter_item(item):
            row_widget = self.tree.itemWidget(item, 0)
            node_name = row_widget.node.name().lower() if row_widget and row_widget.node else ""
            match = (search_kw in node_name)
            child_match = False
            for i in range(item.childCount()):
                if filter_item(item.child(i)):
                    child_match = True

            show = match or child_match
            item.setHidden(not show)
            return show

        for i in range(self.tree.topLevelItemCount()):
            filter_item(self.tree.topLevelItem(i))

    # ====== 图层 CRUD 操作 (修复图层组插入) ======
    def _create_layer(self, layer_type):
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            return

        current_node = doc.activeNode() or doc.rootNode()

        if current_node.type() == "grouplayer":
            parent_node = current_node
            above_node = None
        else:
            parent_node = current_node.parentNode() or doc.rootNode()
            above_node = current_node

        # Krita 官方命名逻辑: 颜料图层 1, 图层组 2...
        base_name = "图层"
        if layer_type == "paintlayer":
            base_name = "颜料图层 "
        elif layer_type == "grouplayer":
            base_name = "图层组 "
        elif layer_type == "vectorlayer":
            base_name = "矢量图层 "

        def get_max_index(node, base):
            m = 0
            for child in node.childNodes():
                c_name = child.name()
                if c_name.startswith(base):
                    try:
                        num = int(c_name[len(base):].strip())
                        if num > m: m = num
                    except ValueError:
                        pass
                m = max(m, get_max_index(child, base))
            return m

        max_idx = get_max_index(doc.rootNode(), base_name)
        final_name = f"{base_name}{max_idx + 1}"

        # 特殊图层类型需要属性配置或生成器，必须触发 Krita 原生 Action 弹窗
        # 注意: Krita 并无独立的“滤镜图层”类型，其滤镜图层即调整图层
        # (KisAdjustmentLayer)，对应 action 为 add_new_adjustment_layer；
        # add_new_filter_layer 在 Krita 中不存在，触发会静默失败
        action_map = {
            "filllayer": "add_new_fill_layer",
            "filterlayer": "add_new_adjustment_layer",
            "filelayer": "add_new_file_layer",
            "clonelayer": "add_new_clone_layer",
            "adjustmentlayer": "add_new_adjustment_layer",
        }
        if layer_type in action_map:
            self._trigger_action(action_map[layer_type])
            # 延时轮询，确保用户在原生弹窗中点击确定后，图层面板能第一时间显示新图层
            QTimer.singleShot(500, self.refresh_tree)
            QTimer.singleShot(1500, self.refresh_tree)
            QTimer.singleShot(3000, self.refresh_tree)
            return

        if layer_type == "grouplayer":
            try:
                new_node = doc.createGroupLayer(final_name)
            except Exception:
                new_node = doc.createNode(final_name, "grouplayer")
        elif layer_type == "paintlayer":
            new_node = doc.createNode(final_name, "paintlayer")
        elif layer_type == "vectorlayer":
            new_node = doc.createVectorLayer(final_name)
        else:
            new_node = doc.createNode(final_name, layer_type)

        if new_node:
            # 确保新建图层无颜色标记
            try:
                new_node.setColorLabel(0)
            except Exception:
                pass
            parent_node.addChildNode(new_node, above_node)
            doc.setActiveNode(new_node)
            self.refresh_canvas()
            self.refresh_tree()

    def _duplicate_layer(self):
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if doc and doc.activeNode():
            node = doc.activeNode()
            dup = node.duplicate()
            try:
                dup.setName(f"{node.name()} - 副本")
            except Exception:
                pass
            parent = node.parentNode() or doc.rootNode()
            parent.addChildNode(dup, node)
            doc.setActiveNode(dup)
            self.refresh_canvas()
            self.refresh_tree()

    def _delete_layer(self):
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            return

        selected_items = self.tree.selectedItems()
        target_nodes = []
        if selected_items:
            for item in selected_items:
                w = self.tree.itemWidget(item, 0)
                if w and w.node and w.node != doc.rootNode():
                    target_nodes.append(w.node)

        if not target_nodes and doc.activeNode() and doc.activeNode() != doc.rootNode():
            target_nodes.append(doc.activeNode())

        if target_nodes:
            for node in target_nodes:
                try:
                    node.remove()
                except Exception:
                    pass
            self.refresh_canvas()
            self.refresh_tree()

    def _move_layer(self, direction):
        if not IN_KRITA:
            return
        action_name = "move_layer_up" if direction == "up" else "move_layer_down"
        try:
            Krita.instance().action(action_name).trigger()
        except Exception:
            pass
        self.refresh_canvas(delay=100)
        self.refresh_tree()

    def _merge_down(self):
        """合并到下层"""
        if not IN_KRITA: return
        doc = Krita.instance().activeDocument()
        if doc and doc.activeNode():
            try:
                doc.activeNode().mergeDown()
                self.refresh_canvas()
                self.refresh_tree()
            except:
                pass
                
    def _trigger_action(self, action_name):
        """触发官方内置 Action 宏"""
        if not IN_KRITA: return
        try:
            Krita.instance().action(action_name).trigger()
        except:
            pass

    def _group_selection(self):
        """将当前选中的图层归组包裹"""
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if not doc or not doc.activeNode():
            return

        node = doc.activeNode()
        parent = node.parentNode() or doc.rootNode()

        group_node = doc.createGroupLayer("图层组")
        if group_node:
            parent.addChildNode(group_node, node)
            node.remove()
            group_node.addChildNode(node)
            doc.setActiveNode(group_node)
            self.refresh_canvas()
            self.refresh_tree()

    def _isolate_layer(self, target_node):
        """独显/隔离当前图层"""
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            return

        root = doc.rootNode()
        def toggle_vis(n):
            for child in n.childNodes():
                if child.uniqueId() == target_node.uniqueId():
                    child.setVisible(True)
                else:
                    child.setVisible(False)
                if child.type() == "grouplayer":
                    toggle_vis(child)

        toggle_vis(root)
        self.refresh_canvas()
        self.update_tree_states()

    def _show_color_label_picker(self):
        """在导航栏颜色标记按钮下方弹出横向色块选择器"""
        selected = self.tree.selectedItems()
        if not selected:
            return
        row_widget = self.tree.itemWidget(selected[0], 0)
        if not row_widget or not row_widget.node:
            return
        node = row_widget.node

        def on_color_picked(idx):
            self._set_node_color_label(node, row_widget, idx)

        clm = build_color_label_menu(on_color_picked, self)
        clm.exec(self.btn_color_label.mapToGlobal(self.btn_color_label.rect().bottomLeft()))

    # ====== 右键菜单 ======
    def _show_active_layer_menu(self):
        """为当前选中的图层显示右键菜单 (由导航栏按钮触发)"""
        selected = self.tree.selectedItems()
        if selected:
            row_widget = self.tree.itemWidget(selected[0], 0)
            if row_widget and row_widget.node:
                self._build_and_show_context_menu(row_widget.node, row_widget, self.btn_layer_menu.mapToGlobal(self.btn_layer_menu.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        row_widget = self.tree.itemWidget(item, 0)
        if not row_widget or not row_widget.node:
            return
        self._build_and_show_context_menu(row_widget.node, row_widget, self.tree.viewport().mapToGlobal(pos))

    def _build_and_show_context_menu(self, node, row_widget, global_pos):
        t = get_theme()
        ui_font = self._ui_font_size()

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {t.BG_BASE};
                color: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                border-radius: {t.RADIUS_BTN};
                padding: 2px;
            }}
            QMenu::item {{
                padding: 4px 14px 4px 6px;
                border-radius: 2px;
                font-size: {ui_font}px;
            }}
            QMenu::item:selected {{
                background-color: {t.SELECTION_BG};
                color: {t.ACCENT_TEXT};
            }}
        """)

        # 官方右键菜单项补全
        act_cut = QAction(get_lucide_icon("scissors", t.TEXT_MAIN, 14), "剪切图层", menu)
        act_cut.triggered.connect(lambda: self._trigger_action("edit_cut"))
        menu.addAction(act_cut)

        act_copy = QAction(get_lucide_icon("copy", t.TEXT_MAIN, 14), "复制图层", menu)
        act_copy.triggered.connect(lambda: self._trigger_action("edit_copy"))
        menu.addAction(act_copy)

        act_paste = QAction(get_lucide_icon("clipboard", t.TEXT_MAIN, 14), "粘贴图层", menu)
        act_paste.triggered.connect(lambda: self._trigger_action("edit_paste"))
        menu.addAction(act_paste)

        menu.addSeparator()

        act_rename = QAction(get_lucide_icon("wand-2", t.TEXT_MAIN, 14), "重命名图层", menu)
        act_rename.triggered.connect(row_widget.start_rename)
        menu.addAction(act_rename)

        act_isolate = QAction(get_lucide_icon("eye", t.TEXT_MAIN, 14), "独显/隔离当前图层", menu)
        act_isolate.triggered.connect(lambda: self._isolate_layer(node))
        menu.addAction(act_isolate)

        act_group = QAction(get_lucide_icon("folder", t.TEXT_MAIN, 14), "将当前图层归组", menu)
        act_group.triggered.connect(self._group_selection)
        menu.addAction(act_group)

        act_clip = QAction(get_lucide_icon("scissors", t.TEXT_MAIN, 14), "快速创建剪切组 (Quick Clip)", menu)
        act_clip.triggered.connect(lambda: self._trigger_action("create_clipping_group"))
        menu.addAction(act_clip)

        # 图层组特有：穿透开关
        if node.type() == "grouplayer" and hasattr(node, "setPassThroughMode"):
            is_pt = node.passThroughMode()
            act_pt = QAction(get_lucide_icon("layers", t.TEXT_MAIN, 14), f"穿透模式 (Pass Through): {'开启' if is_pt else '关闭'}", menu)
            act_pt.triggered.connect(lambda: (node.setPassThroughMode(not is_pt), self.refresh_canvas(), self.update_tree_states()))
            menu.addAction(act_pt)

        menu.addSeparator()

        act_merge = QAction(get_lucide_icon("merge", t.TEXT_MAIN, 14), "合并到下层 (Merge Down)", menu)
        act_merge.triggered.connect(self._merge_down)
        menu.addAction(act_merge)

        act_flatten = QAction(get_lucide_icon("layers-2", t.TEXT_MAIN, 14), "拼合图层 (Flatten Layer)", menu)
        act_flatten.triggered.connect(lambda: self._trigger_action("flatten_layer"))
        menu.addAction(act_flatten)
        
        act_rasterize = QAction(get_lucide_icon("image", t.TEXT_MAIN, 14), "转换为颜料图层 / 栅格化 (Rasterize)", menu)
        act_rasterize.triggered.connect(lambda: self._trigger_action("convert_to_paint_layer"))
        menu.addAction(act_rasterize)

        act_sel_mask = QAction(get_lucide_icon("box", t.TEXT_MAIN, 14), "转换为选区蒙版 (Selection Mask)", menu)
        act_sel_mask.triggered.connect(lambda: self._trigger_action("convert_to_selection_mask"))
        menu.addAction(act_sel_mask)

        act_props = QAction(get_lucide_icon("sliders", t.TEXT_MAIN, 14), "图层属性 (Properties...)", menu)
        act_props.triggered.connect(lambda: self._trigger_action("layer_properties"))
        menu.addAction(act_props)

        menu.addSeparator()

        # 颜色标记——内嵌横向色块，不需二级子菜单
        color_act_label = QAction("颜色标记:", menu)
        color_act_label.setEnabled(False)
        menu.addAction(color_act_label)

        try:
            from PyQt6.QtWidgets import QWidgetAction
        except ImportError:
            from PyQt5.QtWidgets import QWidgetAction

        from .qt_compat import QWidget, QHBoxLayout
        from .color_label_popup import ColorSwatchButton

        swatch_container = QWidget()
        swatch_row = QHBoxLayout(swatch_container)
        swatch_row.setContentsMargins(8, 2, 8, 4)
        swatch_row.setSpacing(3)
        for idx, (c_name, c_hex) in COLOR_LABEL_MAP.items():
            btn = ColorSwatchButton(idx, c_hex)
            btn.clicked.connect(lambda checked=False, i=idx: (menu.close(), self._set_node_color_label(node, row_widget, i)))
            swatch_row.addWidget(btn)
        swatch_row.addStretch()

        wa = QWidgetAction(menu)
        wa.setDefaultWidget(swatch_container)
        menu.addAction(wa)

        menu.addSeparator()

        act_dup = QAction(get_lucide_icon("copy", t.TEXT_MAIN, 14), "复制图层 (Duplicate)", menu)
        act_dup.triggered.connect(self._duplicate_layer)
        menu.addAction(act_dup)

        act_del = QAction(get_lucide_icon("trash-2", t.TEXT_MUTED, 14), "删除图层", menu)
        act_del.triggered.connect(self._delete_layer)
        menu.addAction(act_del)

        menu.exec(global_pos)

    def _set_node_color_label(self, node, row_widget, color_idx):
        try:
            node.setColorLabel(color_idx)
            row_widget.refresh_state()
        except Exception:
            pass
