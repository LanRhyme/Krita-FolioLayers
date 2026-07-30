# -*- coding: utf-8 -*-
"""Flexible Layer Row Widget with Opacity & Blending Text (Official Layout Style)"""

from .qt_compat import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QToolButton, QPushButton, QLineEdit,
    Qt, QSize, QPixmap, QColor, QFont, QTimer, QCursor, QMenu, QAction, QEvent,
    QPainter, QApplication, QPen, QPropertyAnimation, QRect, QPoint, QSizePolicy
)
from .lucide_icons import get_lucide_icon, get_lucide_pixmap
from .hover_preview import get_layer_type_info, COLOR_LABEL_MAP
from .theme import get_theme, draw_thumbnail_with_checkerboard, create_projection_thumbnail
from .config import (
    get_config, DETAIL_NONE, DETAIL_COMPACT, DETAIL_BALANCED, DETAIL_DETAILED
)
from .blending_modes import get_blending_mode_name

class IndentGuideWidget(QWidget):
    """绘制层级缩进参考线的极简组件"""

    def __init__(self, depth, step=16, parent=None):
        super().__init__(parent)
        self.depth = depth
        self.step = step
        self.setFixedWidth(depth * step)

    def paintEvent(self, event):
        t = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 使用自适应亮度的 TEXT_MUTED 颜色，确保在深色模式与浅色模式下缩进线清晰可见
        line_color = QColor(t.TEXT_MUTED)
        line_color.setAlpha(140)
        pen = QPen(line_color, 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        for i in range(self.depth):
            x = i * self.step + self.step // 2
            painter.drawLine(x, 0, x, self.height())
        painter.end()


class LayerRowWidget(QWidget):
    """Procreate / iOS 风格原生图层滑动显露面板 Widget"""

    def __init__(self, node, tree_item=None, docker=None):
        super().__init__()
        self.node = node
        self.tree_item = tree_item
        self.docker = docker
        self.setObjectName("LayerRowWidget")

        # 缩略图懒加载：避免建树时同步阻塞，延迟到事件循环空闲时加载
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.setInterval(80)
        self._thumb_timer.timeout.connect(self._load_thumbnail)

        cfg = get_config()
        t = get_theme()
        self.has_ample_space = (cfg.thumb_size >= 20)

        # 根据配置详情级别确定控件标准行高
        if cfg.detail_level == DETAIL_NONE:
            row_h = max(20, cfg.thumb_size + 2)
        elif cfg.detail_level == DETAIL_COMPACT:
            row_h = max(22, cfg.thumb_size + 4)
        elif cfg.detail_level == DETAIL_DETAILED:
            row_h = max(32 if self.has_ample_space else 28, cfg.thumb_size + 6)
        else: # BALANCED
            row_h = max(32 if self.has_ample_space else 24, cfg.thumb_size + 4)

        self.setFixedHeight(row_h)
        self.tree_item.setSizeHint(0, QSize(0, row_h))
        self.setMouseTracking(True)
        self.setStyleSheet("QWidget#LayerRowWidget { background: transparent; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 2, 1) # Left margin 0 to accommodate select button
        layout.setSpacing(4)

        # 0. 快速多选按钮 (左侧空白区域)
        self.select_btn = QToolButton()
        self.select_btn.setFixedSize(14, row_h - 2)
        self.select_btn.setToolTip("切换多选 (Ctrl+Click 效果)")
        self.select_btn.clicked.connect(self._toggle_multi_select)
        layout.addWidget(self.select_btn)

        # 1. 颜色标记线 (3px 宽)
        self.color_bar = QLabel()
        self.color_bar.setFixedWidth(3)
        self.color_bar.setFixedHeight(max(12, row_h - 6))
        layout.addWidget(self.color_bar)

        # 1.5 内部层级缩进导轨线，极简直观的深层连线效果
        depth = self.get_depth()
        if depth > 0:
            self.indent_spacer = IndentGuideWidget(depth, step=16)
            layout.addWidget(self.indent_spacer)

        # 2. 折叠/展开按钮（图层组专用）
        self.expand_btn = QToolButton()
        self.expand_btn.setFixedSize(14, 14)
        self.expand_btn.clicked.connect(self._toggle_expand)
        layout.addWidget(self.expand_btn)

        # 3. 动态大小缩略图
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(cfg.thumb_size, cfg.thumb_size)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumb_label)

        # 4. 图层类型图标 (14x14 px)
        self.type_icon = QLabel()
        self.type_icon.setFixedSize(14, 14)
        layout.addWidget(self.type_icon)

        # 5. 图层信息区 (中段，自适应单行/双行，垂直居中)
        self.text_vbox = QVBoxLayout()
        self.text_vbox.setContentsMargins(0, 0, 0, 0)
        self.text_vbox.setSpacing(0)
        self.text_vbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # 顶行：名字 + 重命名框
        self.name_label = QLabel(node.name() if node else "")
        self.text_vbox.addWidget(self.name_label)
        
        self.name_edit = QLineEdit(node.name() if node else "")
        self.name_edit.hide()
        self.name_edit.returnPressed.connect(self._finish_rename)
        self.name_edit.editingFinished.connect(self._finish_rename)
        self.text_vbox.addWidget(self.name_edit)

        # 底行：混合模式 + 不透明度 + 分辨率 (当空间充足且有内容时显示)
        self.sub_info_widget = QWidget()
        sub_layout = QHBoxLayout(self.sub_info_widget)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(6)
        
        self.blend_label = QLabel()
        self.opacity_label = QLabel()
        self.size_label = QLabel()
        
        sub_layout.addWidget(self.blend_label)
        sub_layout.addWidget(self.opacity_label)
        sub_layout.addWidget(self.size_label)
        sub_layout.addStretch()
        
        self.text_vbox.addWidget(self.sub_info_widget)

        layout.addLayout(self.text_vbox, 1)

        # 6. 右侧工具按钮组
        self.inherit_alpha_btn = QToolButton()
        self.inherit_alpha_btn.setFixedSize(18, 18)
        self.inherit_alpha_btn.setToolTip("继承透明度 (Inherit Alpha)")
        self.inherit_alpha_btn.clicked.connect(self._toggle_inherit_alpha)
        layout.addWidget(self.inherit_alpha_btn)

        self.alpha_lock_btn = QToolButton()
        self.alpha_lock_btn.setFixedSize(18, 18)
        self.alpha_lock_btn.setToolTip("锁定Alpha透明度 (Lock Alpha)")
        self.alpha_lock_btn.clicked.connect(self._toggle_alpha_lock)
        layout.addWidget(self.alpha_lock_btn)

        self.lock_btn = QToolButton()
        self.lock_btn.setFixedSize(18, 18)
        self.lock_btn.setToolTip("锁定图层 (Lock Layer)")
        self.lock_btn.clicked.connect(self._toggle_lock)
        layout.addWidget(self.lock_btn)

        self.vis_btn = QToolButton()
        self.vis_btn.setFixedSize(18, 18)
        self.vis_btn.setToolTip("显示/隐藏图层 (Toggle Visibility)")
        self.vis_btn.clicked.connect(self._toggle_visibility)
        layout.addWidget(self.vis_btn)

        self.pt_btn = QToolButton()
        self.pt_btn.setFixedSize(18, 18)
        self.pt_btn.setToolTip("穿透模式 (Pass Through)")
        self.pt_btn.clicked.connect(self._toggle_pass_through)
        layout.addWidget(self.pt_btn)

        # 开启所有子控件鼠标跟踪，并挂载事件过滤器，精准捕获 40x40 缩略图、图标和名称上的移动事件
        self.setMouseTracking(True)
        self.installEventFilter(self)
        for sub in (self.select_btn, self.color_bar, self.expand_btn, self.thumb_label,
                    self.type_icon, self.name_label, self.sub_info_widget,
                    self.blend_label, self.opacity_label, self.size_label):
            sub.setMouseTracking(True)
            sub.installEventFilter(self)
        if hasattr(self, 'indent_spacer') and self.indent_spacer:
            self.indent_spacer.setMouseTracking(True)
            self.indent_spacer.installEventFilter(self)

        # ====== 建立悬浮滑动操作面板 (极简 Morandi 无边缝滑动层) ======
        self.swipe_container = QWidget(self)
        self.swipe_container.setObjectName("SwipeContainer")
        self.swipe_container.setStyleSheet(f"""
            QWidget#SwipeContainer {{
                background-color: {t.BG_BASE};
                border: 1px solid {t.BORDER};
                border-radius: 4px;
            }}
        """)
        s_layout = QHBoxLayout(self.swipe_container)
        s_layout.setContentsMargins(1, 1, 1, 1)
        s_layout.setSpacing(2)

        btn_base_qss = f"""
            QToolButton {{
                background-color: transparent;
                color: {t.TEXT_MAIN};
                border: none;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 500;
                padding: 0px 2px;
            }}
        """

        # 1. 选区按钮
        self.btn_swipe_select = QToolButton(self.swipe_container)
        self.btn_swipe_select.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_swipe_select.setIcon(get_lucide_icon("box-select", t.TEXT_MAIN, 12))
        self.btn_swipe_select.setText(" 选区")
        self.btn_swipe_select.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.btn_swipe_select.setToolTip("从当前图层不透明像素提取选区")
        self.btn_swipe_select.setStyleSheet(btn_base_qss + f"""
            QToolButton:hover {{
                background-color: rgba(66, 153, 225, 0.2);
                color: #4299e1;
            }}
            QToolButton:pressed {{
                background-color: rgba(66, 153, 225, 0.35);
            }}
        """)
        self.btn_swipe_select.clicked.connect(self._on_swipe_select_clicked)

        # 2. 独显按钮
        self.btn_swipe_solo = QToolButton(self.swipe_container)
        self.btn_swipe_solo.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_swipe_solo.setIcon(get_lucide_icon("sparkles", t.TEXT_MAIN, 12))
        self.btn_swipe_solo.setText(" 独显")
        self.btn_swipe_solo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.btn_swipe_solo.setToolTip("独显当前图层 (纯净原色模式)")
        self.btn_swipe_solo.setStyleSheet(btn_base_qss + f"""
            QToolButton:hover {{
                background-color: rgba({t.ACCENT_RGB}, 0.22);
                color: {t.ACCENT};
            }}
            QToolButton:pressed {{
                background-color: rgba({t.ACCENT_RGB}, 0.4);
            }}
        """)
        self.btn_swipe_solo.clicked.connect(self._on_swipe_solo_clicked)

        # 3. 删除按钮
        self.btn_swipe_del = QToolButton(self.swipe_container)
        self.btn_swipe_del.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_swipe_del.setIcon(get_lucide_icon("trash-2", t.TEXT_MAIN, 12))
        self.btn_swipe_del.setText(" 删除")
        self.btn_swipe_del.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.btn_swipe_del.setToolTip("删除当前图层")
        self.btn_swipe_del.setStyleSheet(btn_base_qss + f"""
            QToolButton:hover {{
                background-color: rgba(229, 80, 70, 0.2);
                color: #e55046;
            }}
            QToolButton:pressed {{
                background-color: rgba(229, 80, 70, 0.35);
            }}
        """)
        self.btn_swipe_del.clicked.connect(self._on_swipe_del_clicked)

        s_layout.addWidget(self.btn_swipe_select)
        s_layout.addWidget(self.btn_swipe_solo)
        s_layout.addWidget(self.btn_swipe_del)
        self.swipe_container.hide()

        self._init_native_styles()
        self.refresh_state()

    def _init_native_styles(self):
        """尽量移除硬编码的 QSS 背景与圆角，使用纯净透明或原生组件样式"""
        t = get_theme()
        # 让工具按钮保持原生状态，不强制写死 hover 颜色
        btn_style = "QToolButton { background: transparent; border: none; padding: 1px; }"
        self.expand_btn.setStyleSheet(btn_style)
        self.inherit_alpha_btn.setStyleSheet(btn_style)
        self.alpha_lock_btn.setStyleSheet(btn_style)
        self.lock_btn.setStyleSheet(btn_style)
        self.vis_btn.setStyleSheet(btn_style)
        self.pt_btn.setStyleSheet(btn_style)
        self.select_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: none;
                border-right: 1px solid transparent;
            }}
            QToolButton:hover {{
                background: rgba({t.ACCENT_RGB}, 0.1);
                border-right: 1px solid {t.ACCENT};
            }}
        """)

        # 字体大小自适应调整 (默认稍小一些)
        cfg = get_config()
        self._font_sz = max(9, min(12, (cfg.thumb_size // 2) - 1))
        if cfg.thumb_size < 24:
            self._font_sz = 10
        self.name_label.setStyleSheet(f"color: {t.TEXT_MAIN}; background: transparent; font-size: {self._font_sz}px;")
        
        sub_font_style = f"color: {t.TEXT_MUTED}; font-size: {max(9, self._font_sz - 1)}px; background: transparent;"
        self.blend_label.setStyleSheet(sub_font_style)
        self.opacity_label.setStyleSheet(sub_font_style)
        self.size_label.setStyleSheet(sub_font_style)
        self.sub_info_widget.setStyleSheet("background: transparent;")

        self.name_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {t.BG_BASE};
                color: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                font-size: 11px;
                padding: 0px;
            }}
        """)
        self.thumb_label.setStyleSheet(f"background: transparent; border: 1px solid {t.BORDER}; border-radius: 1px;")

    def get_depth(self):
        d = 0
        p = self.tree_item.parent()
        while p:
            d += 1
            p = p.parent()
        return d

    def refresh_state(self):
        """完全遵循 Krita 官方平衡与完整模式下的文字显示逻辑"""
        if not self.node:
            return

        t = get_theme()
        cfg = get_config()
        level = cfg.detail_level

        ntype = self.node.type()
        type_info = get_layer_type_info(ntype)
        is_group = (ntype == "grouplayer")

        # 获取可见性
        vis = self.node.visible()

        # 检查是否有子节点（包含图层组及挂载了蒙版的图层）
        try:
            cfg = get_config()
            cnodes = self.node.childNodes()
            if not cfg.show_selection_masks:
                cnodes = [n for n in cnodes if n.type() != "selectionmask"]
            has_children = (is_group or len(cnodes) > 0)
            child_cnt = len(cnodes)
        except Exception:
            has_children = is_group
            child_cnt = 0

        expanded = self.tree_item.isExpanded() if has_children else False

        solo_uid = getattr(self.docker, '_solo_node_uid', None)
        is_soloed = (solo_uid and str(self.node.uniqueId()) == solo_uid)
        is_suppressed = (solo_uid and not is_soloed)
        raw_mode = getattr(self.docker, '_solo_raw_mode', True)

        if is_suppressed:
            self.setStyleSheet(f"QWidget#LayerRowWidget {{ background: transparent; opacity: 0.35; color: {t.TEXT_MUTED}; }}")
        elif is_soloed:
            self.setStyleSheet(f"QWidget#LayerRowWidget {{ background: rgba({t.ACCENT_RGB}, 0.22); border: 1px solid {t.ACCENT}; border-radius: 3px; }}")
        else:
            self.setStyleSheet("QWidget#LayerRowWidget { background: transparent; border: none; }")

        solo_tag = (" [独显-纯净原色]" if raw_mode else " [独显-原效果]") if is_soloed else ""

        # 图层组视觉强化: 加粗标题 + 显示子图层数量
        if is_group:
            self.name_label.setText(f"{self.node.name()} ({child_cnt}){solo_tag}")
            self.name_label.setStyleSheet(f"color: {t.ACCENT if is_soloed else (t.TEXT_MAIN if vis else t.TEXT_MUTED)}; font-weight: 600;")
        else:
            self.name_label.setText(f"{self.node.name()}{solo_tag}")
            self.name_label.setStyleSheet(f"color: {t.ACCENT if is_soloed else (t.TEXT_MAIN if vis else t.TEXT_MUTED)}; font-weight: {'bold' if is_soloed else 'normal'};")

        # 界面元素显隐
        show_type_icon = (level in (DETAIL_BALANCED, DETAIL_DETAILED))
        show_alpha_btns = (level in (DETAIL_BALANCED, DETAIL_DETAILED))
        show_lock_vis = (level in (DETAIL_COMPACT, DETAIL_BALANCED, DETAIL_DETAILED))
        show_meta_size = (level == DETAIL_DETAILED)

        self.type_icon.setVisible(show_type_icon)
        if show_type_icon:
            icon_color = t.ACCENT if is_soloed else (t.TEXT_MAIN if vis else t.TEXT_MUTED)
            self.type_icon.setPixmap(get_lucide_pixmap(type_info[2], icon_color, 14))

        self.expand_btn.setVisible(has_children)
        if has_children:
            self.expand_btn.setIcon(get_lucide_icon("chevron-down" if expanded else "chevron-right", t.TEXT_MAIN if vis else t.TEXT_MUTED, 12))

        # 颜色标记线
        try:
            c_idx = self.node.colorLabel()
            c_hex = COLOR_LABEL_MAP.get(c_idx, (None, "transparent"))[1]
            if c_hex != "transparent" and not vis:
                c = QColor(c_hex)
                bg = QColor(t.BG_DARK)
                dimmed = QColor(
                    (c.red() + bg.red() * 2) // 3,
                    (c.green() + bg.green() * 2) // 3,
                    (c.blue() + bg.blue() * 2) // 3
                )
                c_hex = dimmed.name()
            self.color_bar.setStyleSheet(f"background-color: {c_hex}; border-radius: 1px;")
        except Exception:
            self.color_bar.setStyleSheet("background-color: transparent;")

        # --- 不透明度与混合模式 (官方逻辑) ---
        op_pct = 100
        try:
            op_pct = round(self.node.opacity() / 255.0 * 100)
        except Exception:
            pass

        b_mode = "normal"
        try:
            if is_group and hasattr(self.node, 'passThroughMode') and self.node.passThroughMode():
                b_mode = "pass_through"
            else:
                b_mode = self.node.blendingMode()
        except Exception:
            pass

        b_name = get_blending_mode_name(b_mode)

        is_modified = (op_pct < 100 or b_mode != "normal")
        should_show_info = (level == DETAIL_DETAILED) or (level == DETAIL_BALANCED and is_modified)

        if should_show_info and level != DETAIL_NONE:
            self.sub_info_widget.show()
            self.opacity_label.setText(f"{op_pct}%" if op_pct < 100 or level == DETAIL_DETAILED else "")
            self.blend_label.setText(b_name if b_mode != "normal" or level == DETAIL_DETAILED else "")
            self.opacity_label.setVisible(bool(self.opacity_label.text()))
            self.blend_label.setVisible(bool(self.blend_label.text()))
        else:
            self.sub_info_widget.hide()

        if show_meta_size and self.has_ample_space:
            try:
                b = self.node.bounds()
                self.size_label.setText(f"{b.width()}x{b.height()}")
                self.size_label.show()
            except Exception:
                self.size_label.hide()
        else:
            self.size_label.hide()

        # 独显模式专用右侧操作控制
        if is_soloed:
            self.inherit_alpha_btn.hide()
            self.alpha_lock_btn.hide()
            self.lock_btn.hide()
            self.pt_btn.hide()
            self.vis_btn.show()
            raw_tip = "[纯净原色模式] 点击切换为原图层效果" if raw_mode else "[原图层效果模式] 点击切换为纯净原色模式"
            self.vis_btn.setIcon(get_lucide_icon("sparkles" if raw_mode else "eye", t.ACCENT, 14))
            self.vis_btn.setToolTip(raw_tip)
            return

        # 可见性与锁定
        self.vis_btn.setVisible(show_lock_vis)
        self.vis_btn.setIcon(get_lucide_icon("eye" if vis else "eye-off", t.TEXT_MAIN if vis else t.TEXT_MUTED, 14))

        locked = self.node.locked()
        self.lock_btn.setVisible(show_lock_vis)
        self.lock_btn.setIcon(get_lucide_icon("lock" if locked else "unlock", t.ACCENT if locked else t.TEXT_MUTED, 14))

        # 穿透模式（仅图层组）
        if is_group and hasattr(self.node, 'passThroughMode'):
            pt = self.node.passThroughMode()
            self.pt_btn.setVisible(show_lock_vis)
            self.pt_btn.setIcon(get_lucide_icon("layers" if pt else "aperture", t.ACCENT if pt else t.TEXT_MUTED, 14))
        else:
            self.pt_btn.hide()

        # 锁定 Alpha 与 继承 Alpha
        try:
            alock = self.node.alphaLocked()
            self.alpha_lock_btn.setVisible(show_alpha_btns and not is_group)
            self.alpha_lock_btn.setIcon(get_lucide_icon("alpha-lock", t.TEXT_MAIN if alock else t.TEXT_MUTED, 14))
        except Exception:
            self.alpha_lock_btn.hide()

        try:
            ainherit = self.node.inheritAlpha()
            self.inherit_alpha_btn.setVisible(show_alpha_btns and not is_group)
            self.inherit_alpha_btn.setIcon(get_lucide_icon("alpha-inherit", t.TEXT_MAIN if ainherit else t.TEXT_MUTED, 14))
        except Exception:
            self.inherit_alpha_btn.hide()

# 尝试从缓存中立即加载旧的缩略图以消除闪烁
        uid = str(self.node.uniqueId())
        if hasattr(self.docker, 'thumbnail_cache') and uid in self.docker.thumbnail_cache:
            self.thumb_label.setPixmap(self.docker.thumbnail_cache[uid])

        # 启动定时器以后台更新最新缩略图
        self._thumb_timer.start()

        # 隐藏图层时整体降低不透明度（文本调色 + 缩略图叠加半透明遮罩）
        if not vis:
            self.name_label.setStyleSheet(
                f"color: {t.TEXT_MUTED}; background: transparent; font-size: {self._font_sz}px;")
            dimmed_sub = f"color: {t.TEXT_MUTED}; font-size: {max(9, self._font_sz - 1)}px; background: transparent;"
            self.blend_label.setStyleSheet(dimmed_sub)
            self.opacity_label.setStyleSheet(dimmed_sub)
            self.size_label.setStyleSheet(dimmed_sub)
        else:
            self.name_label.setStyleSheet(
                f"color: {t.TEXT_MAIN}; background: transparent; font-size: {self._font_sz}px;")
            restored_sub = f"color: {t.TEXT_MUTED}; font-size: {max(9, self._font_sz - 1)}px; background: transparent;"
            self.blend_label.setStyleSheet(restored_sub)
            self.opacity_label.setStyleSheet(restored_sub)
            self.size_label.setStyleSheet(restored_sub)

    def _is_tree_visible(self):
        """检查此项是否在树中可见（所有父组都已展开）"""
        item = self.tree_item
        parent = item.parent()
        while parent:
            if not parent.isExpanded():
                return False
            parent = parent.parent()
        return True

    def _load_thumbnail(self):
        """实际加载缩略图（由 _thumb_timer 延迟触发，避免建树/刷新时同步阻塞）"""
        if not self.node:
            return
        # 折叠组内的子项不加载缩略图，等展开时再加载
        if not self._is_tree_visible():
            return
        buttons = QApplication.mouseButtons()
        no_btn = getattr(Qt, 'NoButton', getattr(getattr(Qt, 'MouseButton', None), 'NoButton', 0))
        if buttons != no_btn:
            self._thumb_timer.start(500)
            return
        try:
            cfg = get_config()
            ts = cfg.thumb_size
            pix = create_projection_thumbnail(self.node, ts, cfg.use_checkerboard)
            # 隐藏图层：叠加半透明遮罩
            if not self.node.visible():
                dimmed = QPixmap(pix.size())
                dimmed.fill(Qt.GlobalColor.transparent)
                dp = QPainter(dimmed)
                dp.setOpacity(0.35)
                dp.drawPixmap(0, 0, pix)
                dp.end()
                self.thumb_label.setPixmap(dimmed)
            else:
                self.thumb_label.setPixmap(pix)
        except Exception:
            self.thumb_label.clear()

    # ====== 拖拽插入指示条 ======
    def set_drop_indicator(self, pos_str):
        t = get_theme()
        if not pos_str:
            self.setStyleSheet("QWidget#LayerRowWidget { background: transparent; border: none; }")
            return
        if pos_str == "above":
            self.setStyleSheet(f"QWidget#LayerRowWidget {{ background: transparent; border-top: 8px solid {t.ACCENT}; }}")
        elif pos_str == "below":
            self.setStyleSheet(f"QWidget#LayerRowWidget {{ background: transparent; border-bottom: 8px solid {t.ACCENT}; }}")
        elif pos_str == "on":
            self.setStyleSheet(f"QWidget#LayerRowWidget {{ background: rgba({t.ACCENT_RGB}, 0.35); border: 3px solid {t.ACCENT}; }}")
        else:
            self.setStyleSheet("QWidget#LayerRowWidget { background: transparent; border: none; }")

    def _get_target_nodes(self):
        if not self.docker or not hasattr(self.docker, 'tree'):
            return [self.node]
        selected_items = self.docker.tree.selectedItems()
        nodes = []
        if selected_items and len(selected_items) > 1:
            for item in selected_items:
                w = self.docker.tree.itemWidget(item, 0)
                if w and w.node:
                    nodes.append(w.node)
        if self.node and self.node not in nodes:
            nodes.append(self.node)
        return nodes if nodes else ([self.node] if self.node else [])

    def _toggle_visibility(self):
        if self.node:
            cfg = get_config()
            shortcut = cfg.solo_shortcut
            modifiers = QApplication.keyboardModifiers()
            is_shortcut = False
            if shortcut == "Ctrl+Click" and (modifiers & Qt.KeyboardModifier.ControlModifier):
                is_shortcut = True
            elif shortcut == "Alt+Click" and (modifiers & Qt.KeyboardModifier.AltModifier):
                is_shortcut = True
            elif shortcut == "Shift+Click" and (modifiers & Qt.KeyboardModifier.ShiftModifier):
                is_shortcut = True

            if is_shortcut:
                if self.docker and hasattr(self.docker, 'enable_solo'):
                    self.docker.enable_solo(self.node)
                    return

            solo_uid = getattr(self.docker, '_solo_node_uid', None)
            if solo_uid and str(self.node.uniqueId()) == solo_uid:
                # 独显状态下再点击眼睛按钮：切换 纯净原色模式 与 原图层效果
                if self.docker and hasattr(self.docker, 'toggle_solo_raw_mode'):
                    self.docker.toggle_solo_raw_mode()
                    return

            targets = self._get_target_nodes()
            new_vis = not self.node.visible()
            for n in targets:
                try:
                    n.setVisible(new_vis)
                except Exception:
                    pass
            self.docker.refresh_canvas()
            self.docker.refresh_tree()

    def _toggle_lock(self):
        if self.node:
            targets = self._get_target_nodes()
            new_lock = not self.node.locked()
            for n in targets:
                try:
                    n.setLocked(new_lock)
                except Exception:
                    pass
            self.docker.refresh_tree()

    def _toggle_alpha_lock(self):
        if self.node:
            targets = self._get_target_nodes()
            new_alock = not self.node.alphaLocked() if hasattr(self.node, 'alphaLocked') else False
            for n in targets:
                if hasattr(n, 'setAlphaLocked'):
                    try:
                        n.setAlphaLocked(new_alock)
                    except Exception:
                        pass
            self.docker.refresh_tree()

    def _toggle_inherit_alpha(self):
        if self.node:
            targets = self._get_target_nodes()
            new_ainherit = not self.node.inheritAlpha() if hasattr(self.node, 'inheritAlpha') else False
            for n in targets:
                if hasattr(n, 'setInheritAlpha'):
                    try:
                        n.setInheritAlpha(new_ainherit)
                    except Exception:
                        pass
            self.docker.refresh_canvas()
            self.docker.refresh_tree()

    def _toggle_pass_through(self):
        if self.node and hasattr(self.node, 'setPassThroughMode'):
            new_pt = not self.node.passThroughMode()
            self.node.setPassThroughMode(new_pt)
            self.docker.refresh_canvas()
            self.refresh_state()

    def _toggle_expand(self):
        if self.tree_item:
            self.tree_item.setExpanded(not self.tree_item.isExpanded())
            self.refresh_state()

    def _toggle_multi_select(self):
        if self.tree_item and self.docker:
            # 切换该项的选择状态而不影响其他选中项
            is_selected = self.tree_item.isSelected()
            self.tree_item.setSelected(not is_selected)
            
    def start_rename(self):
        self.name_label.hide()
        self.name_edit.setText(self.node.name())
        self.name_edit.show()
        self.name_edit.selectAll()
        self.name_edit.setFocus()

    def _finish_rename(self):
        if self.name_edit.isVisible():
            new_name = self.name_edit.text().strip()
            if new_name and self.node:
                self.node.setName(new_name)
            self.name_edit.hide()
            self.name_label.show()
            self.refresh_state()

    # ====== 滑动手势与独显交互 ======
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_drag_start_pos', None) and (event.buttons() & Qt.MouseButton.LeftButton):
            dx = event.pos().x() - self._drag_start_pos.x()
            dy = event.pos().y() - self._drag_start_pos.y()
            if dx < -30 and abs(dy) < 20:
                self.open_swipe()
            elif dx > 30 and abs(dy) < 20:
                self.close_swipe()
        super().mouseMoveEvent(event)

    def eventFilter(self, obj, event):
        ev_type = event.type()
        ev_mouse_move = getattr(QEvent, 'MouseMove', getattr(getattr(QEvent, 'Type', None), 'MouseMove', None))
        ev_enter = getattr(QEvent, 'Enter', getattr(getattr(QEvent, 'Type', None), 'Enter', None))
        ev_leave = getattr(QEvent, 'Leave', getattr(getattr(QEvent, 'Type', None), 'Leave', None))

        if ev_type in (ev_mouse_move, ev_enter):
            if self.docker and hasattr(self.docker, '_on_row_mouse_move'):
                self.docker._on_row_mouse_move(self, QCursor.pos())
        elif ev_type == ev_leave:
            if self.docker and hasattr(self.docker, '_on_row_mouse_leave'):
                self.docker._on_row_mouse_leave(self)

        return super().eventFilter(obj, event)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'swipe_container') and self.swipe_container.isVisible():
            start_x, end_x, y, w, h = self._get_swipe_geometry()
            self.swipe_container.setGeometry(end_x, y, w, h)

    def _get_swipe_geometry(self):
        w = 165
        row_h = self.height()
        # 向上微调 -2px，精确消除 QTreeWidget 单元格的 2px 顶部偏移
        y = -2
        h = max(20, row_h)
        end_x = max(0, self.width() - w)
        start_x = self.width()
        return start_x, end_x, y, w, h

    def open_swipe(self):
        cfg = get_config()
        if not cfg.enable_swipe_gesture:
            return
        start_x, end_x, y, w, h = self._get_swipe_geometry()
        if not hasattr(self, '_open_anim'):
            self._open_anim = QPropertyAnimation(self.swipe_container, b"geometry")
            self._open_anim.setDuration(160)

        self.swipe_container.show()
        self.swipe_container.raise_()
        self._open_anim.stop()
        self._open_anim.setStartValue(QRect(start_x, y, w, h))
        self._open_anim.setEndValue(QRect(end_x, y, w, h))
        self._open_anim.start()

    def close_swipe(self):
        if not hasattr(self, 'swipe_container') or not self.swipe_container.isVisible():
            return
        start_x, end_x, y, w, h = self._get_swipe_geometry()
        if not hasattr(self, '_close_anim'):
            self._close_anim = QPropertyAnimation(self.swipe_container, b"geometry")
            self._close_anim.setDuration(120)
            self._close_anim.finished.connect(self._on_close_anim_finished)

        self._close_anim.stop()
        self._close_anim.setStartValue(QRect(end_x, y, w, h))
        self._close_anim.setEndValue(QRect(start_x, y, w, h))
        self._close_anim.start()

    def _on_close_anim_finished(self):
        if hasattr(self, 'swipe_container'):
            self.swipe_container.hide()

    def _on_swipe_select_clicked(self):
        self.close_swipe()
        if not self.node:
            return

        from krita import Krita
        doc = Krita.instance().activeDocument() if hasattr(Krita, 'instance') else None
        if not doc:
            return

        doc.setActiveNode(self.node)
        sel = doc.selection()
        has_selection = (sel is not None and sel.width() > 0 and sel.height() > 0)

        if not has_selection:
            self._execute_selection_action("replace")
        else:
            self._show_selection_mode_menu()

    def _show_selection_mode_menu(self):
        t = get_theme()
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {t.BG_BASE};
                color: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                border-radius: 4px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 3px;
                font-size: 11px;
                color: {t.TEXT_MAIN};
            }}
            QMenu::item:selected {{
                background-color: rgba({t.ACCENT_RGB}, 0.22);
                color: {t.ACCENT};
            }}
        """)

        act_replace = QAction(get_lucide_icon("box-select", t.TEXT_MAIN, 12), "替换选区 (Replace)", menu)
        act_add = QAction(get_lucide_icon("plus", t.TEXT_MAIN, 12), "添加选区 (Add)", menu)
        act_sub = QAction(get_lucide_icon("minus", t.TEXT_MAIN, 12), "减去选区 (Subtract)", menu)
        act_intersect = QAction(get_lucide_icon("intersect", t.TEXT_MAIN, 12), "交集选区 (Intersect)", menu)

        act_replace.triggered.connect(lambda: self._execute_selection_action("replace"))
        act_add.triggered.connect(lambda: self._execute_selection_action("add"))
        act_sub.triggered.connect(lambda: self._execute_selection_action("subtract"))
        act_intersect.triggered.connect(lambda: self._execute_selection_action("intersect"))

        menu.addAction(act_replace)
        menu.addAction(act_add)
        menu.addAction(act_sub)
        menu.addAction(act_intersect)

        pos = QCursor.pos()
        if hasattr(self, 'btn_swipe_select') and self.btn_swipe_select.isVisible():
            pos = self.btn_swipe_select.mapToGlobal(QPoint(0, self.btn_swipe_select.height()))
        menu.exec(pos)

    def _execute_selection_action(self, mode="replace"):
        if not self.node:
            return
        from krita import Krita
        doc = Krita.instance().activeDocument() if hasattr(Krita, 'instance') else None
        if not doc:
            return

        doc.setActiveNode(self.node)

        action_map = {
            "replace": ["selectopaque", "select_opaque"],
            "add": ["selectopaque_add"],
            "subtract": ["selectopaque_subtract"],
            "intersect": ["selectopaque_intersect"],
        }

        names = action_map.get(mode, ["selectopaque", "select_opaque"])
        executed = False
        for name in names:
            act = Krita.instance().action(name)
            if act:
                act.trigger()
                executed = True
                break

        if executed and self.docker:
            if hasattr(self.docker, 'refresh_canvas'):
                self.docker.refresh_canvas(delay=0)

    def _on_swipe_solo_clicked(self):
        self.close_swipe()
        if self.docker and hasattr(self.docker, 'enable_solo'):
            self.docker.enable_solo(self.node)

    def _on_swipe_del_clicked(self):
        self.close_swipe()
        if self.docker and hasattr(self.docker, '_delete_layer'):
            self.docker._delete_layer()
