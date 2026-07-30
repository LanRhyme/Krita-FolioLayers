# -*- coding: utf-8 -*-
"""Plugin Settings Dialog for Folio Layer Docker"""

from .qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QSpinBox, Qt, QFont, QGroupBox
)
from .config import (
    get_config, DETAIL_NONE, DETAIL_COMPACT, DETAIL_BALANCED, DETAIL_DETAILED
)
from .theme import get_theme

class SettingsDialog(QDialog):
    """图层面板高级设置与偏好对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Folio Layers 图层面板设置")
        self.setFixedSize(360, 440)

        t = get_theme()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.BG_BASE};
                color: {t.TEXT_MAIN};
            }}
            QGroupBox {{
                color: {t.TEXT_MAIN};
                font-weight: bold;
                font-size: 11px;
                border: 1px solid {t.BORDER};
                border-radius: 5px;
                margin-top: 6px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                background-color: {t.BG_BASE};
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
        layout.setSpacing(10)

        cfg = get_config()

        # 分组 1: 外观与尺寸
        grp_visual = QGroupBox("外观与缩略图尺寸", self)
        l_visual = QVBoxLayout(grp_visual)
        l_visual.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("图层缩略图大小:"))
        self.combo_size = QComboBox()
        sizes = [
            ("20 x 20 px (极简小图)", 20),
            ("28 x 28 px (紧凑)", 28),
            ("32 x 32 px (中等)", 32),
            ("40 x 40 px (默认高清大图)", 40),
            ("48 x 48 px (大图)", 48),
            ("64 x 64 px (超大图)", 64),
        ]
        for label, val in sizes:
            self.combo_size.addItem(label, val)
            if val == cfg.thumb_size:
                self.combo_size.setCurrentIndex(self.combo_size.count() - 1)
        row1.addWidget(self.combo_size, 1)
        l_visual.addLayout(row1)

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
        l_visual.addLayout(row2)

        self.check_grid = QCheckBox("图层透明区域显示棋盘格网格背景")
        self.check_grid.setChecked(cfg.use_checkerboard)
        l_visual.addWidget(self.check_grid)

        self.check_group_count = QCheckBox("显示图层组内子图层数量标记 e.g. (3)")
        self.check_group_count.setChecked(cfg.show_group_count)
        l_visual.addWidget(self.check_group_count)

        self.check_selection_masks = QCheckBox("在图层列表中显示选区蒙版 (Selection Mask)")
        self.check_selection_masks.setChecked(cfg.show_selection_masks)
        l_visual.addWidget(self.check_selection_masks)

        layout.addWidget(grp_visual)

        # 分组 2: 交互与手势
        grp_interaction = QGroupBox("交互与手势偏好", self)
        l_inter = QVBoxLayout(grp_interaction)
        l_inter.setSpacing(8)

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
        l_inter.addLayout(row3)

        self.check_hover = QCheckBox("启用鼠标悬停大图浮窗预览")
        self.check_hover.setChecked(cfg.enable_hover_preview)
        l_inter.addWidget(self.check_hover)

        self.check_swipe = QCheckBox("启用向左滑动显露独显/删除功能快捷面板")
        self.check_swipe.setChecked(cfg.enable_swipe_gesture)
        l_inter.addWidget(self.check_swipe)

        layout.addWidget(grp_interaction)

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
        cfg.show_group_count = self.check_group_count.isChecked()
        cfg.enable_swipe_gesture = self.check_swipe.isChecked()
        cfg.show_selection_masks = self.check_selection_masks.isChecked()
        self.accept()
