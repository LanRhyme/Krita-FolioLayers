# -*- coding: utf-8 -*-
"""Flexible Layer Row Widget with Opacity & Blending Text (Official Layout Style)"""

from .qt_compat import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QToolButton, QLineEdit,
    Qt, QSize, QPixmap, QColor, QFont, QTimer, QCursor, QMenu, QAction, QEvent
)
from .lucide_icons import get_lucide_icon, get_lucide_pixmap
from .hover_preview import get_layer_type_info, COLOR_LABEL_MAP
from .theme import get_theme, draw_thumbnail_with_checkerboard
from .config import (
    get_config, DETAIL_NONE, DETAIL_COMPACT, DETAIL_BALANCED, DETAIL_DETAILED
)
from .blending_modes import get_blending_mode_name

class LayerRowWidget(QWidget):
    """自适应图层列表项 Widget (与官方一致的两行/单行布局)"""

    def __init__(self, node, tree_item, docker, parent=None):
        super().__init__(parent)
        self.node = node
        self.tree_item = tree_item
        self.docker = docker
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(300)
        self.hover_timer.timeout.connect(self._on_hover_timeout)

        cfg = get_config()

        # 只要缩略图 >= 20px 且有显示必要，即可提供两行空间
        self.has_ample_space = (cfg.thumb_size >= 20)

        if cfg.detail_level == DETAIL_NONE:
            row_h = max(20, cfg.thumb_size + 2)
        elif cfg.detail_level == DETAIL_COMPACT:
            row_h = max(22, cfg.thumb_size + 4)
        elif cfg.detail_level == DETAIL_DETAILED:
            row_h = max(32 if self.has_ample_space else 28, cfg.thumb_size + 6)
        else: # BALANCED
            row_h = max(32 if self.has_ample_space else 24, cfg.thumb_size + 4)

        self.setFixedHeight(row_h)
        self.setMouseTracking(True)
        self.setObjectName("LayerRowWidget")
        # 必须透明以显示 QTreeWidget 选中的系统高亮背景色
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

        # 1.5 内部层级缩进，替代 QTreeWidget 的原生缩进，保证左侧对齐
        depth = self.get_depth()
        if depth > 0:
            self.indent_spacer = QWidget()
            self.indent_spacer.setFixedSize(14 * depth, 1)
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
        font_sz = max(9, min(12, (cfg.thumb_size // 2) - 1))
        if cfg.thumb_size < 24:
            font_sz = 10
        self.name_label.setStyleSheet(f"background: transparent; font-size: {font_sz}px;")
        
        sub_font_style = f"color: {t.TEXT_MUTED}; font-size: {max(9, font_sz - 1)}px; background: transparent;"
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

        self.name_label.setText(self.node.name())

        ntype = self.node.type()
        type_info = get_layer_type_info(ntype)
        is_group = (ntype == "grouplayer")

        # 获取可见性
        vis = self.node.visible()

        # 界面元素显隐
        show_type_icon = (level in (DETAIL_BALANCED, DETAIL_DETAILED))
        show_alpha_btns = (level in (DETAIL_BALANCED, DETAIL_DETAILED))
        show_lock_vis = (level in (DETAIL_COMPACT, DETAIL_BALANCED, DETAIL_DETAILED))
        show_meta_size = (level == DETAIL_DETAILED)

        self.type_icon.setVisible(show_type_icon)
        if show_type_icon:
            icon_color = t.TEXT_MAIN
            if is_group:
                icon_color = t.ACCENT
            self.type_icon.setPixmap(get_lucide_pixmap(type_info[2], icon_color, 14))

        self.expand_btn.setVisible(is_group)
        if is_group:
            expanded = self.tree_item.isExpanded()
            self.expand_btn.setIcon(get_lucide_icon("chevron-down" if expanded else "chevron-right", t.TEXT_MUTED, 12))

        # 颜色标记线
        try:
            c_idx = self.node.colorLabel()
            c_hex = COLOR_LABEL_MAP.get(c_idx, (None, "transparent"))[1]
            self.color_bar.setStyleSheet(f"background-color: {c_hex}; border-radius: 1px;")
        except Exception:
            self.color_bar.setStyleSheet("background-color: transparent;")

        # --- 不透明度与混合模式 (官方逻辑) ---
        op_pct = 100
        try:
            op_pct = int(self.node.opacity() / 255.0 * 100)
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

        # 缩略图（带网格棋盘格透明底）
        try:
            ts = cfg.thumb_size
            qimg = self.node.thumbnail(ts, ts)
            pix = draw_thumbnail_with_checkerboard(qimg, ts, ts, cfg.use_checkerboard)
            self.thumb_label.setPixmap(pix)
        except Exception:
            self.thumb_label.clear()

        # 隐藏图层时整体降低不透明度
        self.setDisabled(not vis)

    # ====== 事件交互 ======
    def _toggle_visibility(self):
        if self.node:
            new_vis = not self.node.visible()
            self.node.setVisible(new_vis)
            self.docker.refresh_canvas()
            self.refresh_state()

    def _toggle_lock(self):
        if self.node:
            new_lock = not self.node.locked()
            self.node.setLocked(new_lock)
            self.refresh_state()

    def _toggle_alpha_lock(self):
        if self.node and hasattr(self.node, 'setAlphaLocked'):
            new_alock = not self.node.alphaLocked()
            self.node.setAlphaLocked(new_alock)
            self.refresh_state()

    def _toggle_inherit_alpha(self):
        if self.node and hasattr(self.node, 'setInheritAlpha'):
            new_ainherit = not self.node.inheritAlpha()
            self.node.setInheritAlpha(new_ainherit)
            self.docker.refresh_canvas()
            self.refresh_state()

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

    def enterEvent(self, event):
        super().enterEvent(event)
        cfg = get_config()
        if not cfg.enable_hover_preview:
            return
        if getattr(self.docker, '_hover_active', False):
            # 浮窗已近期展示过，移动到新图层项时立即更新
            if self.node:
                self.docker.show_hover_preview(self.node, QCursor.pos())
        else:
            # 首次停留，延迟 300ms 后才弹出
            self.hover_timer.setInterval(300)
            self.hover_timer.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hover_timer.stop()
        # 移开图层项时隐藏浮窗，但不重置 _hover_active
        # (重置由图层面板的 leaveEvent 负责)
        self.docker.hover_preview.hide()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.docker.hover_preview.isVisible():
            self.docker.hover_preview.popup_at(QCursor.pos())

    def _on_hover_timeout(self):
        cfg = get_config()
        if cfg.enable_hover_preview and self.underMouse() and self.node:
            self.docker.show_hover_preview(self.node, QCursor.pos())
