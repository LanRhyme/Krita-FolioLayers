# -*- coding: utf-8 -*-
"""Hover Floating Window Preview Component - Dynamic Krita Palette"""

from .qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, Qt, QPixmap, QColor,
    QFont, QGraphicsDropShadowEffect, QSize, QRect, QApplication
)
from .lucide_icons import get_lucide_pixmap
from .theme import get_theme

def get_layer_type_info(ntype):
    t = get_theme()
    mapping = {
        "paintlayer": ("绘画图层", t.ACCENT, "image"),
        "grouplayer": ("图层组", t.TEXT_MAIN, "folder"),
        "vectorlayer": ("矢量图层", t.TEXT_MUTED, "type"),
        "filterlayer": ("滤镜图层", t.ACCENT, "wand-2"),
        "adjustmentlayer": ("调整图层", t.ACCENT, "sliders"),
        "filllayer": ("填充图层", t.ACCENT, "palette"),
        "clonelayer": ("克隆图层", t.TEXT_MUTED, "copy"),
        "filelayer": ("文件图层", t.TEXT_MUTED, "layers"),
    }
    return mapping.get(ntype, ("图层", t.TEXT_MUTED, "layers"))

COLOR_LABEL_MAP = {
    0: ("无标签", "transparent"),
    1: ("蓝色",  "#7f9bb0"),
    2: ("绿色",  "#8fa382"),
    3: ("黄色",  "#bda572"),
    4: ("橙色",  "#c79685"),
    5: ("褐色",  "#b08a70"),
    6: ("红色",  "#be7a6b"),
    7: ("紫色",  "#8c7fa5"),
    8: ("灰色",  "#8c8c8c"),
}

class HoverPreviewPopup(QFrame):
    """动态主题浮动预览弹窗，鼠标悬停图层项时弹出大图和详细参数"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setFixedSize(260, 300)

        # 内部主容器
        self.card = QFrame(self)
        self.card.setObjectName("MainCard")
        self.card.setFixedSize(260, 300)

        # 软阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 4)
        self.card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 顶部：图层名 + 图层类型 Pill 标签
        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        self.type_icon_label = QLabel()
        self.type_icon_label.setFixedSize(16, 16)
        top_row.addWidget(self.type_icon_label)

        self.name_label = QLabel("图层名称")
        font_name = QFont()
        font_name.setBold(True)
        font_name.setPointSize(9)
        self.name_label.setFont(font_name)
        top_row.addWidget(self.name_label, 1)

        self.type_badge = QLabel("绘画图层")
        top_row.addWidget(self.type_badge)

        layout.addLayout(top_row)

        # 中间：大图缩略图预览
        self.preview_box = QFrame()
        self.preview_box.setFixedHeight(180)
        preview_layout = QVBoxLayout(self.preview_box)
        preview_layout.setContentsMargins(2, 2, 2, 2)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.image_label)

        layout.addWidget(self.preview_box)

        # 底部信息网格：分辨率, 不透明度, 混合模式, 状态徽章
        info_row1 = QHBoxLayout()

        self.bounds_label = QLabel("尺寸: 0 x 0")
        info_row1.addWidget(self.bounds_label)

        info_row1.addStretch()

        self.opacity_label = QLabel("不透明度: 100%")
        info_row1.addWidget(self.opacity_label)

        layout.addLayout(info_row1)

        info_row2 = QHBoxLayout()

        self.blend_label = QLabel("混合: Normal")
        info_row2.addWidget(self.blend_label)

        info_row2.addStretch()

        self.status_badges_box = QHBoxLayout()
        self.status_badges_box.setSpacing(4)

        self.vis_badge = QLabel()
        self.lock_badge = QLabel()
        self.alpha_lock_badge = QLabel()
        self.inherit_alpha_badge = QLabel()

        for badge in (self.vis_badge, self.lock_badge, self.alpha_lock_badge, self.inherit_alpha_badge):
            badge.setFixedSize(16, 16)
            self.status_badges_box.addWidget(badge)

        info_row2.addLayout(self.status_badges_box)
        layout.addLayout(info_row2)

        self.refresh_theme_styles()

    def refresh_theme_styles(self):
        t = get_theme()
        self.setStyleSheet(f"""
            QFrame#MainCard {{
                background-color: {t.BG_BASE};
                border: 1px solid {t.BORDER};
                border-radius: {t.RADIUS};
            }}
            QLabel {{
                color: {t.TEXT_MAIN};
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
        """)
        self.name_label.setStyleSheet(f"color: {t.TEXT_MAIN};")
        self.preview_box.setStyleSheet(f"""
            QFrame {{
                background-color: {t.BG_DARK};
                border: 1px solid {t.BORDER};
                border-radius: {t.RADIUS};
            }}
        """)
        self.bounds_label.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 10px;")
        self.opacity_label.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 10px;")
        self.blend_label.setStyleSheet(f"color: {t.ACCENT}; font-size: 10px; font-weight: 500;")

    def update_node(self, node):
        """用 Krita Node 更新浮窗数据"""
        if not node:
            return

        self.refresh_theme_styles()
        t = get_theme()

        name = node.name()
        self.name_label.setText(name)

        ntype = node.type()
        type_info = get_layer_type_info(ntype)
        self.type_badge.setText(type_info[0])
        self.type_badge.setStyleSheet(f"""
            background-color: {t.BG_ALT};
            color: {t.TEXT_MAIN};
            border: 1px solid {t.BORDER};
            border-radius: 3px;
            padding: 1px 4px;
            font-size: 9px;
            font-weight: bold;
        """)
        self.type_icon_label.setPixmap(get_lucide_pixmap(type_info[2], type_info[1], 16))

        # 获取缩略图
        try:
            qimg = node.thumbnail(220, 170)
            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg)
                scaled_pix = pix.scaled(
                    QSize(220, 170),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pix)
            else:
                self.image_label.setText("无图像预览")
        except Exception:
            self.image_label.setText("预览加载失败")

        # 尺寸范围
        try:
            b = node.bounds()
            self.bounds_label.setText(f"范围: {b.width()} × {b.height()} px")
        except Exception:
            self.bounds_label.setText("范围: 未知")

        # 不透明度与混合模式
        op = int(node.opacity() / 255.0 * 100)
        self.opacity_label.setText(f"不透明度: {op}%")
        self.blend_label.setText(f"混合: {node.blendingMode()}")

        # 状态徽章图标
        vis = node.visible()
        self.vis_badge.setPixmap(get_lucide_pixmap("eye" if vis else "eye-off", t.ACCENT if vis else t.TEXT_MUTED, 14))

        locked = node.locked()
        self.lock_badge.setPixmap(get_lucide_pixmap("lock" if locked else "unlock", t.ACCENT if locked else t.TEXT_MUTED, 14))

        try:
            alock = node.alphaLocked()
            self.alpha_lock_badge.setPixmap(get_lucide_pixmap("alpha-lock", t.ACCENT if alock else t.TEXT_MUTED, 14))
        except Exception:
            self.alpha_lock_badge.clear()

        try:
            ainherit = node.inheritAlpha()
            self.inherit_alpha_badge.setPixmap(get_lucide_pixmap("alpha-inherit", t.ACCENT if ainherit else t.TEXT_MUTED, 14))
        except Exception:
            self.inherit_alpha_badge.clear()

    def popup_at(self, global_pos):
        """在指定全局坐标位置安全显示（避开屏幕边缘）"""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = global_pos.x() + 12
            y = global_pos.y() - 40

            if x + self.width() > geo.right():
                x = global_pos.x() - self.width() - 12
            if y + self.height() > geo.bottom():
                y = geo.bottom() - self.height() - 8
            if y < geo.top():
                y = geo.top() + 8

            self.move(x, y)
        else:
            self.move(global_pos.x() + 12, global_pos.y())

        self.show()
        self.raise_()
