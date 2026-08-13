# -*- coding: utf-8 -*-
"""PyQt5 and PyQt6 compatibility layer for Krita"""

try:
    from PyQt6.QtCore import (
        Qt, pyqtSignal, pyqtSlot, QSize, QPoint, QPointF, QRect, QEvent, QTimer, QByteArray,
        QMimeData, QSettings, QPropertyAnimation, QEasingCurve, QAbstractListModel, QModelIndex, QVariant, QUrl
    )
    from PyQt6.QtGui import (
        QPainter, QColor, QFont, QPen, QBrush, QIcon, QPixmap, QImage, QCursor, QDrag,
        QAction, QPalette, QMouseEvent
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton,
        QScrollArea, QSizePolicy, QApplication, QFrame, QInputDialog, QMenu,
        QTreeWidget, QTreeWidgetItem, QSlider, QComboBox, QSpinBox, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
        QHeaderView, QLineEdit, QAbstractItemView, QDialog, QCheckBox, QGroupBox, QLayout, QFileDialog
    )
    from PyQt6.QtQuickWidgets import QQuickWidget
    from PyQt6.QtSvg import QSvgRenderer

    def _fix_qt_enum(enum_cls, names):
        for name in names:
            if hasattr(enum_cls, name):
                setattr(Qt, name, getattr(enum_cls, name))

    if hasattr(Qt, 'TimerType'):
        _fix_qt_enum(Qt.TimerType, ['PreciseTimer', 'CoarseTimer', 'VeryCoarseTimer'])
    if hasattr(Qt, 'MouseButton'):
        _fix_qt_enum(Qt.MouseButton, ['LeftButton', 'RightButton', 'MiddleButton', 'NoButton'])
    if hasattr(Qt, 'AspectRatioMode'):
        _fix_qt_enum(Qt.AspectRatioMode, ['KeepAspectRatio', 'IgnoreAspectRatio', 'KeepAspectRatioByExpanding'])
    if hasattr(Qt, 'TransformationMode'):
        _fix_qt_enum(Qt.TransformationMode, ['FastTransformation', 'SmoothTransformation'])
    if hasattr(Qt, 'Orientation'):
        _fix_qt_enum(Qt.Orientation, ['Horizontal', 'Vertical'])
    if hasattr(Qt, 'AlignmentFlag'):
        _fix_qt_enum(Qt.AlignmentFlag, ['AlignCenter', 'AlignLeft', 'AlignRight', 'AlignTop', 'AlignBottom', 'AlignVCenter', 'AlignHCenter'])
    if hasattr(Qt, 'WindowType'):
        _fix_qt_enum(Qt.WindowType, ['ToolTip', 'Tool', 'SubWindow', 'FramelessWindowHint', 'WindowStaysOnTopHint', 'Popup'])
    if hasattr(Qt, 'FocusPolicy'):
        _fix_qt_enum(Qt.FocusPolicy, ['StrongFocus', 'NoFocus', 'TabFocus', 'ClickFocus'])
    if hasattr(Qt, 'DockWidgetArea'):
        _fix_qt_enum(Qt.DockWidgetArea, ['LeftDockWidgetArea', 'RightDockWidgetArea', 'TopDockWidgetArea', 'BottomDockWidgetArea', 'AllDockWidgetAreas'])
    if hasattr(QPainter, 'RenderHint'):
        for name in ['TextAntialiasing', 'Antialiasing', 'SmoothPixmapTransform', 'LosslessImageRendering']:
            if hasattr(QPainter.RenderHint, name):
                setattr(QPainter, name, getattr(QPainter.RenderHint, name))

except ImportError:
    # PyQt5 仅在 Krita 5.x 自带 Python 环境存在，开发机/静态分析器不可见
    from PyQt5.QtCore import (  # type: ignore[import-not-found]
        Qt, pyqtSignal, pyqtSlot, QSize, QPoint, QPointF, QRect, QEvent, QTimer, QByteArray,
        QMimeData, QSettings, QPropertyAnimation, QEasingCurve, QAbstractListModel, QModelIndex, QVariant, QUrl
    )
    from PyQt5.QtGui import (  # type: ignore[import-not-found]
        QPainter, QColor, QFont, QPen, QBrush, QIcon, QPixmap, QImage, QCursor, QDrag,
        QPalette, QMouseEvent
    )
    from PyQt5.QtWidgets import (  # type: ignore[import-not-found]
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton,
        QScrollArea, QSizePolicy, QApplication, QFrame, QInputDialog, QMenu,
        QTreeWidget, QTreeWidgetItem, QSlider, QComboBox, QSpinBox, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
        QHeaderView, QLineEdit, QAction, QAbstractItemView, QDialog, QCheckBox, QGroupBox, QLayout, QFileDialog
    )
    from PyQt5.QtQuickWidgets import QQuickWidget  # type: ignore[import-not-found]
    from PyQt5.QtSvg import QSvgRenderer  # type: ignore[import-not-found]


def mouse_x(event):
    """鼠标事件 x 坐标，兼容 Qt5（pos）与 Qt6（position）"""
    if hasattr(event, 'position'):
        return event.position().x()
    return event.pos().x()


def mouse_point(event):
    """鼠标事件整数坐标 QPoint，兼容 Qt5（pos）与 Qt6（position.toPoint）"""
    if hasattr(event, 'position'):
        return event.position().toPoint()
    return event.pos()


def mouse_global_point(event):
    """鼠标事件全局整数坐标 QPoint，兼容 Qt5（globalPos 返回 QPoint）与 Qt6（globalPosition 返回 QPointF）"""
    if hasattr(event, 'globalPosition'):
        return event.globalPosition().toPoint()
    return event.globalPos()
