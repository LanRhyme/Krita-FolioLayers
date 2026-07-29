# -*- coding: utf-8 -*-
"""PyQt5 and PyQt6 compatibility layer for Krita"""

try:
    from PyQt6.QtCore import (
        Qt, pyqtSignal, pyqtSlot, QSize, QPoint, QRect, QEvent, QTimer, QByteArray,
        QMimeData, QSettings, QPropertyAnimation, QEasingCurve
    )
    from PyQt6.QtGui import (
        QPainter, QColor, QFont, QPen, QBrush, QIcon, QPixmap, QImage, QCursor, QDrag,
        QAction, QPalette
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton,
        QScrollArea, QSizePolicy, QApplication, QFrame, QInputDialog, QMenu,
        QTreeWidget, QTreeWidgetItem, QSlider, QComboBox, QSpinBox, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
        QHeaderView, QLineEdit, QAbstractItemView, QDialog, QCheckBox
    )
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
        _fix_qt_enum(Qt.WindowType, ['ToolTip', 'FramelessWindowHint', 'WindowStaysOnTopHint', 'Popup'])
    if hasattr(Qt, 'FocusPolicy'):
        _fix_qt_enum(Qt.FocusPolicy, ['StrongFocus', 'NoFocus', 'TabFocus', 'ClickFocus'])
    if hasattr(Qt, 'DockWidgetArea'):
        _fix_qt_enum(Qt.DockWidgetArea, ['LeftDockWidgetArea', 'RightDockWidgetArea', 'TopDockWidgetArea', 'BottomDockWidgetArea', 'AllDockWidgetAreas'])
    if hasattr(QPainter, 'RenderHint'):
        for name in ['TextAntialiasing', 'Antialiasing', 'SmoothPixmapTransform', 'LosslessImageRendering']:
            if hasattr(QPainter.RenderHint, name):
                setattr(QPainter, name, getattr(QPainter.RenderHint, name))

except ImportError:
    from PyQt5.QtCore import (
        Qt, pyqtSignal, pyqtSlot, QSize, QPoint, QRect, QEvent, QTimer, QByteArray,
        QMimeData, QSettings, QPropertyAnimation, QEasingCurve
    )
    from PyQt5.QtGui import (
        QPainter, QColor, QFont, QPen, QBrush, QIcon, QPixmap, QImage, QCursor, QDrag,
        QPalette
    )
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton,
        QScrollArea, QSizePolicy, QApplication, QFrame, QInputDialog, QMenu,
        QTreeWidget, QTreeWidgetItem, QSlider, QComboBox, QSpinBox, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
        QHeaderView, QLineEdit, QAction, QAbstractItemView, QDialog, QCheckBox
    )
    from PyQt5.QtSvg import QSvgRenderer
