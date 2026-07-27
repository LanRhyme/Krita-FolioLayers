# -*- coding: utf-8 -*-
"""Folio Layer Docker - Native Qt Integration, Clean Dropdowns & Full Blending Modes"""

import sys
from .qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QFrame, QMenu, QAction, QTimer,
    Qt, QSize, QCursor, QApplication, QHeaderView, QAbstractItemView
)
from .lucide_icons import get_lucide_icon, get_lucide_pixmap
from .hover_preview import HoverPreviewPopup, COLOR_LABEL_MAP
from .layer_item import LayerRowWidget
from .theme import get_theme
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

class LayerTreeWidget(QTreeWidget):
    """支持将拖拽事件转发给 Krita 原生 API 的图层树"""
    def __init__(self, docker):
        super().__init__()
        self.docker = docker
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def mousePressEvent(self, event):
        """点击空白区域时不取消选中，始终保持至少选择一个图层"""
        item = self.itemAt(event.pos())
        if item is None:
            # 点到空白处：吃掉事件，不传递给父类（防止取消选中）
            return
        super().mousePressEvent(event)

    def dropEvent(self, event):
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

        def reorder(drag_node, new_parent, above_sibling):
            """将 drag_node 从原来位置移除并插入到 new_parent 下 above_sibling 节点上方"""
            drag_node.remove()
            new_parent.addChildNode(drag_node, above_sibling)

        if drop_ind == QAbstractItemView.DropIndicatorPosition.OnItem:
            # 拖入图层组内部 (放到组内第一个位置)
            if target_node.type() == "grouplayer":
                children = target_node.childNodes()
                first_child = children[-1] if children else None
                reorder(drag_node, target_node, first_child)
            else:
                event.ignore()
                return
        elif drop_ind == QAbstractItemView.DropIndicatorPosition.AboveItem:
            # 放在 target 上方 (在父节点内 target 之后, 因 Krita 列表是倒序)
            parent = target_node.parentNode()
            if not parent:
                event.ignore()
                return
            reorder(drag_node, parent, target_node)
        elif drop_ind == QAbstractItemView.DropIndicatorPosition.BelowItem:
            # 放在 target 下方 (在父节点内 target 之前)
            parent = target_node.parentNode()
            if not parent:
                event.ignore()
                return
            siblings = parent.childNodes()  # childNodes() 返回从下到上顺序
            idx = next((i for i, n in enumerate(siblings) if n.uniqueId() == target_node.uniqueId()), -1)
            above = siblings[idx - 1] if idx > 0 else None
            reorder(drag_node, parent, above)

        doc.refreshProjection()
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        QTimer.singleShot(50, self.docker.refresh_tree)

class FolioLayerDocker(DockWidget if IN_KRITA else QWidget):
    """精简优雅、包含全套原生功能与全类混合模式菜单的 Krita 图层面板"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folio Layers")
        self.canvas = None

        self.hover_preview = HoverPreviewPopup(self)
        self.hover_preview.hide()
        # 悬停预览状态跟踪：首次停留需要延迟，之后移动到其它项就立即显示
        self._hover_active = False  # True 表示浮窗已在展示过

        self._updating_ui = False

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
        self.tree = LayerTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(0) # 缩进由 LayerRowWidget 内部接管，保证左侧对齐
        self.tree.setAnimated(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

        main_layout.addWidget(self.tree, 1)

        # 5. 定时刷新与 Krita 事件挂载
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(600)
        self.sync_timer.timeout.connect(self._sync_with_krita)
        self.sync_timer.start()

        if IN_KRITA:
            try:
                notifier = Krita.instance().notifier()
                # 使用局部状态更新，避免重构树导致闪烁
                notifier.imageUpdated.connect(self.update_tree_states)
                notifier.activeViewChanged.connect(self.request_tree_refresh)
            except Exception:
                pass

        self.apply_theme_qss()
        self.refresh_tree()

    def update_tree_states(self, *args):
        """轻量级刷新：仅更新现有树节点的状态、缩略图和徽章，不重建整个树"""
        if self._updating_ui or not IN_KRITA:
            return
        def _update(item):
            w = self.tree.itemWidget(item, 0)
            if w: w.refresh_state()
            for i in range(item.childCount()):
                _update(item.child(i))
        
        for i in range(self.tree.topLevelItemCount()):
            _update(self.tree.topLevelItem(i))

    def canvasChanged(self, canvas):
        """Krita 画布切换回调（DockWidget 抽象方法重写）"""
        self.canvas = canvas
        if canvas:
            self.refresh_tree()

    def apply_theme_qss(self):
        """仅重写悬停与选中状态，以及修复系统 Tooltip 颜色使其在暗色主题下可见"""
        t = get_theme()

        # 系统 QToolTip 颜色修复（防止暗色主题下黑字贴近深背景导致不可见）
        QApplication.instance().setStyleSheet(f"""
            QToolTip {{
                background-color: {t.BG_BASE};
                color: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                padding: 3px 6px;
                font-size: 11px;
            }}
        """)

        self.tree.setStyleSheet(f"""
            QTreeWidget::branch {{
                border-image: none;
                image: none;
                width: 0px;
            }}
            QTreeWidget::item {{
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 0px;
                margin-bottom: 1px;
            }}
            QTreeWidget::item:hover {{
                border: 1px solid {t.ACCENT};
                background-color: transparent;
            }}
            QTreeWidget::item:selected {{
                border: 1px solid {t.ACCENT};
                background-color: rgba({t.ACCENT_RGB}, 0.15);
            }}
        """)

    # ====== UI 结构构建 ======
    def _build_toolbar(self, parent_layout):
        self.toolbar_frame = QFrame()
        self.toolbar_frame.setFixedHeight(24)

        tb_layout = QHBoxLayout(self.toolbar_frame)
        tb_layout.setContentsMargins(2, 1, 2, 1)
        tb_layout.setSpacing(2)

        t = get_theme()

        # 1. 新建颜料图层 (单独按钮)
        self.btn_new_paint = QToolButton()
        self.btn_new_paint.setFixedSize(20, 20)
        self.btn_new_paint.setIcon(get_lucide_icon("plus", t.TEXT_MAIN, 14))
        self.btn_new_paint.setToolTip("新建颜料图层 (Paint Layer)")
        self.btn_new_paint.clicked.connect(lambda: self._create_layer("paintlayer"))
        tb_layout.addWidget(self.btn_new_paint)

        # 2. 新建图层组 (文件夹图标)
        self.btn_new_group = QToolButton()
        self.btn_new_group.setFixedSize(20, 20)
        self.btn_new_group.setIcon(get_lucide_icon("folder", t.TEXT_MAIN, 14))
        self.btn_new_group.setToolTip("新建图层组 (Group Layer)")
        self.btn_new_group.clicked.connect(lambda: self._create_layer("grouplayer"))
        tb_layout.addWidget(self.btn_new_group)

        # 3. 更多图层类型 (纯下拉菜单)
        self.btn_new_more = QToolButton()
        self.btn_new_more.setFixedSize(20, 20)
        self.btn_new_more.setIcon(get_lucide_icon("chevron-down", t.TEXT_MAIN, 14))
        self.btn_new_more.setToolTip("更多图层类型...")
        
        self.new_menu = QMenu(self)
        types = [
            ("vectorlayer", "矢量图层 (Vector Layer)", "type"),
            ("filterlayer", "滤镜图层 (Filter Layer)", "wand-2"),
            ("adjustmentlayer", "调整图层 (Adjustment Layer)", "sliders"),
            ("filllayer", "填充图层 (Fill Layer)", "palette"),
            ("clonelayer", "克隆图层 (Clone Layer)", "copy"),
            ("filelayer", "文件图层 (File Layer)", "layers"),
        ]
        for t_code, t_name, t_icon in types:
            act = QAction(get_lucide_icon(t_icon, t.TEXT_MAIN, 14), t_name, self.new_menu)
            act.triggered.connect(lambda checked, c=t_code: self._create_layer(c))
            self.new_menu.addAction(act)

        # 不使用 PopupMode 以避免原生绘制额外的箭头，直接监听点击弹出
        self.btn_new_more.clicked.connect(lambda: self.new_menu.exec(self.btn_new_more.mapToGlobal(self.btn_new_more.rect().bottomLeft())))
        tb_layout.addWidget(self.btn_new_more)

        tb_layout.addSpacing(2)

        # 2. 复制图层
        self.btn_dup = QToolButton()
        self.btn_dup.setFixedSize(20, 20)
        self.btn_dup.setIcon(get_lucide_icon("copy", t.TEXT_MUTED, 14))
        self.btn_dup.setToolTip("复制当前图层")
        self.btn_dup.clicked.connect(self._duplicate_layer)
        tb_layout.addWidget(self.btn_dup)

        # 3. 删除图层
        self.btn_del = QToolButton()
        self.btn_del.setFixedSize(20, 20)
        self.btn_del.setIcon(get_lucide_icon("trash-2", t.TEXT_MUTED, 14))
        self.btn_del.setToolTip("删除当前图层")
        self.btn_del.clicked.connect(self._delete_layer)
        tb_layout.addWidget(self.btn_del)

        tb_layout.addSpacing(2)

        # 4. 上移 / 下移图层
        self.btn_up = QToolButton()
        self.btn_up.setFixedSize(20, 20)
        self.btn_up.setIcon(get_lucide_icon("arrow-up", t.TEXT_MUTED, 14))
        self.btn_up.setToolTip("向上移动图层")
        self.btn_up.clicked.connect(lambda: self._move_layer("up"))
        tb_layout.addWidget(self.btn_up)

        self.btn_down = QToolButton()
        self.btn_down.setFixedSize(20, 20)
        self.btn_down.setIcon(get_lucide_icon("arrow-down", t.TEXT_MUTED, 14))
        self.btn_down.setToolTip("向下移动图层")
        self.btn_down.clicked.connect(lambda: self._move_layer("down"))
        tb_layout.addWidget(self.btn_down)

        tb_layout.addStretch()

        # 颜色标记快捷按钮
        self.btn_color_label = QToolButton()
        self.btn_color_label.setFixedSize(20, 20)
        self.btn_color_label.setIcon(get_lucide_icon("tag", t.TEXT_MUTED, 14))
        self.btn_color_label.setToolTip("设置当前图层颜色标记")
        self.btn_color_label.clicked.connect(self._show_color_label_picker)
        tb_layout.addWidget(self.btn_color_label)

        # 图层属性/操作菜单按钮 (对应右键菜单)
        self.btn_layer_menu = QToolButton()
        self.btn_layer_menu.setFixedSize(20, 20)
        self.btn_layer_menu.setIcon(get_lucide_icon("more-horizontal", t.TEXT_MUTED, 14))
        self.btn_layer_menu.setToolTip("当前图层操作菜单")
        self.btn_layer_menu.clicked.connect(self._show_active_layer_menu)
        tb_layout.addWidget(self.btn_layer_menu)

        # 5. 搜索按钮
        self.btn_search = QToolButton()
        self.btn_search.setFixedSize(20, 20)
        self.btn_search.setIcon(get_lucide_icon("search", t.TEXT_MUTED, 14))
        self.btn_search.setToolTip("搜索图层名称")
        self.btn_search.clicked.connect(lambda: self.search_input.setVisible(not self.search_input.isVisible()))
        tb_layout.addWidget(self.btn_search)

        # 6. 偏好设置按钮 ⚙️
        self.btn_settings = QToolButton()
        self.btn_settings.setFixedSize(20, 20)
        self.btn_settings.setIcon(get_lucide_icon("settings", t.TEXT_MUTED, 14))
        self.btn_settings.setToolTip("图层面板偏好设置")
        self.btn_settings.clicked.connect(self._open_settings_dialog)
        tb_layout.addWidget(self.btn_settings)

        parent_layout.addWidget(self.toolbar_frame)

    def _build_property_bar(self, parent_layout):
        self.prop_card = QFrame()
        self.prop_card.setFixedHeight(24)

        p_layout = QHBoxLayout(self.prop_card)
        p_layout.setContentsMargins(2, 2, 2, 2)
        p_layout.setSpacing(4)

        # 多级分类混合模式选择按钮
        self.btn_blend = QToolButton()
        self.btn_blend.setObjectName("BlendModeBtn")
        from .qt_compat import QSizePolicy
        self.btn_blend.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_blend.setFixedHeight(20)
        self.btn_blend.setText("正常")
        self.btn_blend.setStyleSheet("font-size: 10px;")

        self.blend_menu = create_categorized_blending_menu(self.btn_blend, self._on_blend_selected)
        self.btn_blend.clicked.connect(lambda: self.blend_menu.exec(self.btn_blend.mapToGlobal(self.btn_blend.rect().bottomLeft())))
        p_layout.addWidget(self.btn_blend, 1)

        # 原生 QSlider 风格不透明度条
        self.opacity_bar = OpacityBarWidget(self.prop_card)
        self.opacity_bar.setFixedHeight(20)
        self.opacity_bar.valueChanged.connect(self._on_opacity_bar_changed)
        p_layout.addWidget(self.opacity_bar, 2)

        parent_layout.addWidget(self.prop_card)

    def _open_settings_dialog(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._hover_active = False
            self.hover_preview.hide()
            self.refresh_tree()


    # ====== 悬停预览接口 ======
    def show_hover_preview(self, node, global_pos):
        self.hover_preview.update_node(node)
        self.hover_preview.popup_at(global_pos)
        self._hover_active = True

    def hide_hover_preview(self):
        self.hover_preview.hide()

    def reset_hover_state(self):
        """鼠标离开图层面板时重置悬停预览状态"""
        self._hover_active = False
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
        QTimer.singleShot(delay, self.refresh_tree)

    def refresh_tree(self):
        if not IN_KRITA or self._updating_ui:
            return

        self._updating_ui = True
        self.tree.clear()

        doc = Krita.instance().activeDocument()
        if not doc:
            self._updating_ui = False
            return

        active_node = doc.activeNode()
        root = doc.rootNode()

        self._populate_node_tree(root, None, active_node)

        if active_node:
            self._update_property_bar_for_node(active_node)

        self._updating_ui = False

    def _populate_node_tree(self, parent_node, parent_tree_item, active_node):
        children = parent_node.childNodes()
        for child in reversed(children):
            if child.type() == "selectionmask":
                continue

            item = QTreeWidgetItem()
            if parent_tree_item:
                parent_tree_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

            row_widget = LayerRowWidget(child, item, self)
            self.tree.setItemWidget(item, 0, row_widget)

            if active_node and child.uniqueId() == active_node.uniqueId():
                self.tree.setCurrentItem(item)

            if child.type() == "grouplayer":
                item.setExpanded(True)
                self._populate_node_tree(child, item, active_node)

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

        op_val = int(node.opacity() / 255.0 * 100)
        self.opacity_bar.blockSignals(True)
        self.opacity_bar.setValue(op_val)
        self.opacity_bar.blockSignals(False)

    def _sync_with_krita(self):
        if not IN_KRITA or self._updating_ui:
            return
        doc = Krita.instance().activeDocument()
        if not doc:
            return

        curr_node = doc.activeNode()
        if curr_node:
            self._update_property_bar_for_node(curr_node)

        # 定时器周期性调用更新：让不透明度和缩略图实时跟进改变
        self.update_tree_states()

    # ====== 属性事件 ======
    def _on_tree_selection_changed(self):
        if self._updating_ui or not IN_KRITA:
            return
        selected_items = self.tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            row_widget = self.tree.itemWidget(item, 0)
            if row_widget and row_widget.node:
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
            self.refresh_tree()

    def _on_opacity_bar_changed(self, percent_val):
        if self._updating_ui or not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if doc and doc.activeNode():
            opacity_255 = int(percent_val / 100.0 * 255)
            doc.activeNode().setOpacity(opacity_255)
            self.refresh_canvas()

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
            parent = node.parentNode() or doc.rootNode()
            parent.addChildNode(dup, node)
            doc.setActiveNode(dup)
            self.refresh_canvas()
            self.refresh_tree()

    def _delete_layer(self):
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if doc and doc.activeNode():
            node = doc.activeNode()
            if node != doc.rootNode():
                node.remove()
                self.refresh_canvas()
                self.refresh_tree()

    def _move_layer(self, direction):
        if not IN_KRITA:
            return
        doc = Krita.instance().activeDocument()
        if not doc or not doc.activeNode():
            return
        node = doc.activeNode()
        parent = node.parentNode()
        if not parent:
            return

        siblings = parent.childNodes()
        idx = siblings.index(node) if node in siblings else -1
        if idx < 0:
            return

        if direction == "up" and idx < len(siblings) - 1:
            target_above = siblings[idx + 1]
            parent.removeChildNode(node)
            parent.addChildNode(node, target_above)
        elif direction == "down" and idx > 0:
            target_below = siblings[idx - 1]
            parent.removeChildNode(node)
            parent.addChildNode(node, target_below)

        self.refresh_canvas()
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
            parent.removeChildNode(node)
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
        self.refresh_tree()

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
                font-size: 11px;
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

        # 图层组特有：穿透开关
        if node.type() == "grouplayer" and hasattr(node, "setPassThroughMode"):
            is_pt = node.passThroughMode()
            act_pt = QAction(get_lucide_icon("layers", t.TEXT_MAIN, 14), f"穿透模式 (Pass Through): {'开启' if is_pt else '关闭'}", menu)
            act_pt.triggered.connect(lambda: (node.setPassThroughMode(not is_pt), self.refresh_canvas(), self.refresh_tree()))
            menu.addAction(act_pt)

        menu.addSeparator()

        act_merge = QAction(get_lucide_icon("merge", t.TEXT_MAIN, 14), "合并到下层 (Merge Down)", menu)
        act_merge.triggered.connect(self._merge_down)
        menu.addAction(act_merge)

        act_flatten = QAction(get_lucide_icon("layers-2", t.TEXT_MAIN, 14), "拼合图层 (Flatten Layer)", menu)
        act_flatten.triggered.connect(lambda: self._trigger_action("flatten_layer"))
        menu.addAction(act_flatten)
        
        act_rasterize = QAction(get_lucide_icon("image", t.TEXT_MAIN, 14), "栅格化图层 (Rasterize)", menu)
        act_rasterize.triggered.connect(lambda: self._trigger_action("rasterize_layer"))
        menu.addAction(act_rasterize)

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
