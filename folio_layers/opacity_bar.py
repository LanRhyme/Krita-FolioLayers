# -*- coding: utf-8 -*-
"""Native Krita Style Opacity Slider – matches official KisSliderSpinBox appearance and interaction"""

from .qt_compat import (
    QWidget, QLineEdit, QPainter, QColor, QFont, QPen, QBrush, pyqtSignal, Qt,
    QSizePolicy, QRect, QTimer
)
from .theme import get_theme


class OpacityBarWidget(QWidget):
    """
    Krita 官方风格大不透明度滑块组合控件 (KisSliderSpinBox 风格)：
    1. 整体大滑块呈现当前不透明度进度条背景与“不透明度: XX%”文本
    2. 拖拽滑块时 UI 文本与进度条 0ms 瞬间实时更新，画布以 0.2s 频率刷新
    3. 支持双击进入内嵌 QLineEdit 文本直接输入数字 (0-100)
    4. 右侧提供精致扁平的 ▲ / ▼ 步进微调按钮 (精确单击一次更新一次，绝对不跳变)
    5. 支持滚轮调节
    """

    valueChanged = pyqtSignal(int)

    STEP_BTN_WIDTH = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 100
        self._is_dragging = False
        self._is_editing = False
        self._hover_btn = None  # 'up', 'down', or None

        # 拖拽 0.2s (200ms) 节流刷新定时器
        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(200)
        self._emit_timer.timeout.connect(self._emit_throttled_value)
        self._last_emitted_val = 100

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(24)

        # 内嵌编辑框 (双击时显示)
        self._edit = QLineEdit(self)
        self._edit.hide()
        self._edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._edit.returnPressed.connect(self._finish_edit)
        self._edit.editingFinished.connect(self._finish_edit)

    def value(self) -> int:
        return self._value

    def setValue(self, val: int):
        # 拖拽或编辑期间禁止外部同步覆盖
        if self._is_dragging or self._is_editing:
            return
        clamped = max(0, min(100, int(val)))
        if self._value != clamped:
            self._value = clamped
            self._last_emitted_val = clamped
            self.update()

    def _emit_throttled_value(self):
        if self._last_emitted_val != self._value:
            self._last_emitted_val = self._value
            self.valueChanged.emit(self._value)
        if self._is_dragging:
            self._emit_timer.start(200)

    # ====== 尺寸与区域计算 ======
    def _step_up_rect(self) -> QRect:
        w = self.width()
        h = self.height()
        btn_w = self.STEP_BTN_WIDTH
        btn_h = (h - 2) // 2
        return QRect(w - btn_w - 1, 1, btn_w, btn_h)

    def _step_down_rect(self) -> QRect:
        w = self.width()
        h = self.height()
        btn_w = self.STEP_BTN_WIDTH
        btn_h = (h - 2) // 2
        return QRect(w - btn_w - 1, 1 + btn_h, btn_w, h - 2 - btn_h)

    def _slider_bar_rect(self) -> QRect:
        w = self.width()
        h = self.height()
        return QRect(0, 0, max(10, w - self.STEP_BTN_WIDTH - 2), h)

    # ====== 绘图事件 ======
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        t = get_theme()
        w = self.width()
        h = self.height()
        bar_rect = self._slider_bar_rect()
        up_rect = self._step_up_rect()
        down_rect = self._step_down_rect()

        # 1. 绘制滑块底框
        painter.setPen(QPen(QColor(t.BORDER), 1))
        painter.setBrush(QBrush(QColor(t.BG_ALT)))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        # 2. 绘制滑块填充条
        fill_w = int(bar_rect.width() * (self._value / 100.0))
        if fill_w > 0:
            accent_color = QColor(t.ACCENT)
            accent_color.setAlpha(180)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent_color))
            painter.drawRoundedRect(1, 1, fill_w, h - 2, 3, 3)

        # 3. 绘制文本 ("不透明度: XX%")
        if not self._is_editing:
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.setPen(QPen(QColor(t.TEXT_MAIN)))
            text = f"不透明度: {self._value}%"
            painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, text)

        # 4. 绘制右侧微调按钮分隔线与矢量微型箭头
        border_color = QColor(t.BORDER)
        border_color.setAlpha(120)
        painter.setPen(QPen(border_color, 1))
        painter.drawLine(bar_rect.right() + 1, 3, bar_rect.right() + 1, h - 4)

        # 悬停背景 (圆角气泡)
        if self._hover_btn == 'up':
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(t.HOVER_BG)))
            painter.drawRoundedRect(up_rect.adjusted(1, 1, -1, -1), 3, 3)
        elif self._hover_btn == 'down':
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(t.HOVER_BG)))
            painter.drawRoundedRect(down_rect.adjusted(1, 0, -1, -1), 3, 3)

        # 抗锯齿矢量箭头
        painter.setPen(QPen(QColor(t.TEXT_MUTED), 1.2))

        # 上箭头 (▲)
        cx_up = up_rect.center().x()
        cy_up = up_rect.center().y() + 1
        painter.drawLine(cx_up - 3, cy_up + 1, cx_up, cy_up - 2)
        painter.drawLine(cx_up, cy_up - 2, cx_up + 3, cy_up + 1)

        # 下箭头 (▼)
        cx_down = down_rect.center().x()
        cy_down = down_rect.center().y() - 1
        painter.drawLine(cx_down - 3, cy_down - 1, cx_down, cy_down + 2)
        painter.drawLine(cx_down, cy_down + 2, cx_down + 3, cy_down - 1)

    # ====== 鼠标事件 ======
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        pos = event.pos()
        up_rect = self._step_up_rect()
        down_rect = self._step_down_rect()

        shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        step = 5 if shift_held else 1

        if up_rect.contains(pos):
            self._is_dragging = False
            new_val = max(0, min(100, self._value + step))
            if self._value != new_val:
                self._value = new_val
                self._last_emitted_val = new_val
                self.update()
                self.valueChanged.emit(new_val)
            return
        elif down_rect.contains(pos):
            self._is_dragging = False
            new_val = max(0, min(100, self._value - step))
            if self._value != new_val:
                self._value = new_val
                self._last_emitted_val = new_val
                self.update()
                self.valueChanged.emit(new_val)
            return

        # 拖拽滑块区域
        self._is_dragging = True
        self._update_val_from_mouse_x(pos.x())

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self._is_dragging:
            self._update_val_from_mouse_x(pos.x())
            return

        # 悬停检测
        old_hover = self._hover_btn
        if self._step_up_rect().contains(pos):
            self._hover_btn = 'up'
        elif self._step_down_rect().contains(pos):
            self._hover_btn = 'down'
        else:
            self._hover_btn = None

        if old_hover != self._hover_btn:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self._emit_timer.stop()
            if self._last_emitted_val != self._value:
                self._last_emitted_val = self._value
                self.valueChanged.emit(self._value)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            bar_rect = self._slider_bar_rect()
            if bar_rect.contains(event.pos()):
                self._start_edit()

    def leaveEvent(self, event):
        if self._hover_btn is not None:
            self._hover_btn = None
            self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y() if hasattr(event, 'angleDelta') else getattr(event, 'delta', lambda: 0)()
        shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        step = 5 if shift_held else 1
        new_val = self._value
        if delta > 0:
            new_val = max(0, min(100, self._value + step))
        elif delta < 0:
            new_val = max(0, min(100, self._value - step))

        if new_val != self._value:
            self._value = new_val
            self._last_emitted_val = new_val
            self.update()
            self.valueChanged.emit(new_val)

    def _update_val_from_mouse_x(self, mouse_x: int):
        bar_w = max(1, self._slider_bar_rect().width())
        pct = max(0, min(100, int(mouse_x / bar_w * 100)))
        if self._value != pct:
            self._value = pct
            self.update()  # 0ms 瞬间更新 UI 文本和进度条

        if not self._emit_timer.isActive():
            self._emit_timer.start(200)  # 0.2s 频率刷新画布

    # ====== 双击内嵌编辑模式 ======
    def _start_edit(self):
        t = get_theme()
        self._is_editing = True
        bar_rect = self._slider_bar_rect()
        self._edit.setStyleSheet(
            f"background: {t.BG_DARK}; color: {t.TEXT_MAIN}; "
            f"border: 1px solid {t.ACCENT}; border-radius: 3px; font-size: 11px;"
        )
        self._edit.setGeometry(bar_rect.adjusted(2, 2, -2, -2))
        self._edit.setText(str(self._value))
        self._edit.selectAll()
        self._edit.show()
        self._edit.setFocus()
        self.update()

    def _finish_edit(self):
        if not self._is_editing:
            return
        text = self._edit.text().strip().rstrip('%')
        try:
            val = max(0, min(100, int(text)))
            if self._value != val:
                self._value = val
                self._last_emitted_val = val
                self.update()
                self.valueChanged.emit(val)
        except ValueError:
            pass
        self._is_editing = False
        self._edit.hide()
        self.update()

    def keyPressEvent(self, event):
        if self._is_editing and event.key() == Qt.Key.Key_Escape:
            self._is_editing = False
            self._edit.hide()
            self.update()
            return
        super().keyPressEvent(event)
