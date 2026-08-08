# -*- coding: utf-8 -*-
"""QML 图层列表原型：QAbstractListModel 数据桥接 + QQuickWidget 嵌入

验证目标（Krita 实测前 offscreen 只能验证加载/布局/模型）：
1. QQuickWidget 在 Krita 的 Wayland/OpenGL 环境下能否正常渲染
2. 数位笔事件能否被 QML 的 DragHandler（acceptedDevices 含 Tablet）接收
3. 拖拽让位动画与落点回调是否流畅

原型开关：环境变量 FOLIO_QML_TREE=1 时 docker 用本模块替换 QTreeWidget
"""

import os

from .qt_compat import (
    Qt, pyqtSignal, pyqtSlot, QAbstractListModel, QModelIndex, QVariant,
    QColor, QQuickWidget, QUrl, QByteArray
)

QML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml", "FolioLayerList.qml")


class LayerListModel(QAbstractListModel):
    """扁平图层列表模型（缩进用 depth 表示）"""

    ROLE_NAME = Qt.ItemDataRole.UserRole + 1
    ROLE_COLOR = Qt.ItemDataRole.UserRole + 2
    ROLE_VISIBLE = Qt.ItemDataRole.UserRole + 3
    ROLE_LOCKED = Qt.ItemDataRole.UserRole + 4
    ROLE_DEPTH = Qt.ItemDataRole.UserRole + 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []  # dict: name, color, visible, locked, depth

    # ---- 模型接口 ----
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return QVariant()
        row = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole or role == self.ROLE_NAME:
            return row["name"]
        if role == self.ROLE_COLOR:
            return row["color"]
        if role == self.ROLE_VISIBLE:
            return row["visible"]
        if role == self.ROLE_LOCKED:
            return row["locked"]
        if role == self.ROLE_DEPTH:
            return row["depth"]
        return QVariant()

    def roleNames(self):
        return {
            self.ROLE_NAME: QByteArray(b"name"),
            self.ROLE_COLOR: QByteArray(b"color"),
            self.ROLE_VISIBLE: QByteArray(b"visible"),
            self.ROLE_LOCKED: QByteArray(b"locked"),
            self.ROLE_DEPTH: QByteArray(b"depth"),
        }

    # ---- 数据操作 ----
    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def move(self, from_row, to_row):
        if from_row == to_row or from_row < 0 or to_row < 0:
            return
        if from_row >= len(self._rows) or to_row >= len(self._rows):
            return
        if not self.beginMoveRows(QModelIndex(), from_row, from_row, QModelIndex(), to_row + (1 if to_row > from_row else 0)):
            return
        item = self._rows.pop(from_row)
        self._rows.insert(to_row, item)
        self.endMoveRows()

    def toggle_visible(self, row):
        if 0 <= row < len(self._rows):
            self._rows[row]["visible"] = not self._rows[row]["visible"]
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [self.ROLE_VISIBLE])

    def row_at(self, row):
        return self._rows[row] if 0 <= row < len(self._rows) else None


class QmlLayerList(QQuickWidget):
    """嵌入的 QML 图层列表控件"""

    reorderRequested = pyqtSignal(int, int)   # (from, to) 拖拽落点
    toggleVisible = pyqtSignal(int)           # 眼睛按钮点击
    rowClicked = pyqtSignal(int)              # 行点击

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = LayerListModel(self)
        size_mode = getattr(QQuickWidget, 'SizeRootObjectToView',
                            getattr(getattr(QQuickWidget, 'ResizeMode', None), 'SizeRootObjectToView', 0))
        self.setResizeMode(size_mode)
        self.setClearColor(QColor(0, 0, 0, 0))
        self.engine().rootContext().setContextProperty("layerModel", self.model)
        self.setSource(QUrl.fromLocalFile(QML_FILE))
        # QML 异步加载：就绪后再连接信号
        self.statusChanged.connect(self._on_status_changed)

    def _on_status_changed(self, status):
        if status != self.status().Ready:
            return
        root = self.rootObject()
        if root is None:
            return
        root.reorderRequested.connect(self.reorderRequested)
        root.toggleVisible.connect(self.toggleVisible)
        root.rowClicked.connect(self.rowClicked)

    def set_layers(self, rows):
        self.model.set_rows(rows)
