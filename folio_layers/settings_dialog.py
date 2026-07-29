# -*- coding: utf-8 -*-
"""Plugin Settings Dialog for Folio Layer Docker"""

from .qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QSpinBox, Qt, QFont
)
from .config import (
    get_config, DETAIL_NONE, DETAIL_COMPACT, DETAIL_BALANCED, DETAIL_DETAILED
)
from .theme import get_theme

class SettingsDialog(QDialog):
    """图层面板设置与偏好对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Folio Layers 设置")
        self.setFixedSize(320, 310)

        t = get_theme()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.BG_BASE};
                color: {t.TEXT_MAIN};
            }}
            QLabel {{
                color: {t.TEXT_MAIN};
                font-size: 11px;
            }}
            QComboBox, QSpinBox {{
                background: {t.BG_DARK};
                color: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
            }}
            QCheckBox {{
                color: {t.TEXT_MAIN};
                font-size: 11px;
            }}
            QPushButton {{
                background-color: {t.BG_ALT};
                color: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {t.HOVER_BG};
            }}
            QPushButton#PrimaryBtn {{
                background-color: {t.ACCENT};
                color: {t.ACCENT_TEXT};
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        cfg = get_config()

        # 1. 缩略图尺寸
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("图层预览图大小:"))
        self.combo_size = QComboBox()
        sizes = [("16 x 16 px", 16), ("20 x 20 px (默认)", 20), ("24 x 24 px", 24), ("32 x 32 px", 32), ("40 x 40 px", 40)]
        for label, val in sizes:
            self.combo_size.addItem(label, val)
            if val == cfg.thumb_size:
                self.combo_size.setCurrentIndex(self.combo_size.count() - 1)
        row1.addWidget(self.combo_size, 1)
        layout.addLayout(row1)

        # 2. 图层项详细信息级别 (无、简洁、平衡、完整)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("图层信息显示级别:"))
        self.combo_detail = QComboBox()
        details = [
            ("无 (仅缩略图+名称)", DETAIL_NONE),
            ("简洁 (名称+可见性+锁定)", DETAIL_COMPACT),
            ("平衡 (默认全操控图标)", DETAIL_BALANCED),
            ("完整 (显示尺寸+不透明度%)", DETAIL_DETAILED),
        ]
        for label, val in details:
            self.combo_detail.addItem(label, val)
            if val == cfg.detail_level:
                self.combo_detail.setCurrentIndex(self.combo_detail.count() - 1)
        row2.addWidget(self.combo_detail, 1)
        layout.addLayout(row2)

        # 3. 独显触发快捷键
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("独显眼睛按钮快捷键:"))
        self.combo_solo = QComboBox()
        shortcuts = [
            ("Ctrl + Click (默认)", "Ctrl+Click"),
            ("Alt + Click", "Alt+Click"),
            ("Shift + Click", "Shift+Click"),
        ]
        for label, val in shortcuts:
            self.combo_solo.addItem(label, val)
            if val == cfg.solo_shortcut:
                self.combo_solo.setCurrentIndex(self.combo_solo.count() - 1)
        row3.addWidget(self.combo_solo, 1)
        layout.addLayout(row3)

        # 4. 网格图棋盘格透明显示
        self.check_grid = QCheckBox("图层透明区域显示网格图(棋盘格)")
        self.check_grid.setChecked(cfg.use_checkerboard)
        layout.addWidget(self.check_grid)

        # 5. 启用悬停浮窗预览
        self.check_hover = QCheckBox("启用鼠标悬停大图浮窗预览")
        self.check_hover.setChecked(cfg.enable_hover_preview)
        layout.addWidget(self.check_hover)

        layout.addStretch()

        # 底部按钮
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("保存设置")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _save_settings(self):
        cfg = get_config()
        cfg.thumb_size = self.combo_size.currentData()
        cfg.detail_level = self.combo_detail.currentData()
        cfg.solo_shortcut = self.combo_solo.currentData()
        cfg.use_checkerboard = self.check_grid.isChecked()
        cfg.enable_hover_preview = self.check_hover.isChecked()
        self.accept()
