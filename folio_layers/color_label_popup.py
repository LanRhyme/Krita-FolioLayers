# -*- coding: utf-8 -*-
"""Color Label Swatch Popup - horizontal color picker matching Krita official style"""

from .qt_compat import (
    QWidget, QHBoxLayout, QToolButton, Qt, QSize, QColor, QPainter, QPen, QMenu
)
from .hover_preview import COLOR_LABEL_MAP
from .theme import get_theme


class ColorSwatchButton(QToolButton):
    """单个圆形/方形色块按钮"""

    def __init__(self, idx, hex_color, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.hex_color = hex_color
        self.setFixedSize(18, 18)
        self.setToolTip(COLOR_LABEL_MAP[idx][0])
        self._update_style()

    def _update_style(self):
        t = get_theme()
        if self.hex_color == "transparent":
            # 无标记：显示一个带斜线的空方块
            self.setStyleSheet(f"""
                QToolButton {{
                    background: transparent;
                    border: 1px solid {t.BORDER};
                    border-radius: 3px;
                    font-size: 9px;
                    color: {t.TEXT_MUTED};
                }}
                QToolButton:hover {{
                    border: 2px solid {t.ACCENT};
                }}
            """)
            self.setText("✕")
        else:
            self.setStyleSheet(f"""
                QToolButton {{
                    background-color: {self.hex_color};
                    border: 1px solid rgba(0,0,0,0.25);
                    border-radius: 3px;
                }}
                QToolButton:hover {{
                    border: 2px solid {t.TEXT_MAIN};
                }}
            """)
            self.setText("")


def build_color_label_menu(callback, parent=None):
    """构建横向内嵌色块的颜色标记菜单（与官方 Krita 一级菜单对齐）"""
    t = get_theme()
    menu = QMenu(parent)

    # 用 QWidgetAction 内嵌一行色块
    from .qt_compat import QAction, QSizePolicy
    try:
        from PyQt6.QtWidgets import QWidgetAction
    except ImportError:
        from PyQt5.QtWidgets import QWidgetAction

    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(4, 4, 4, 4)
    row.setSpacing(3)

    for idx, (c_name, c_hex) in COLOR_LABEL_MAP.items():
        btn = ColorSwatchButton(idx, c_hex)
        btn.clicked.connect(lambda checked=False, i=idx: (menu.close(), callback(i)))
        row.addWidget(btn)

    row.addStretch()

    wa = QWidgetAction(menu)
    wa.setDefaultWidget(container)
    menu.addAction(wa)

    return menu
