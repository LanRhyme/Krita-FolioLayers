# -*- coding: utf-8 -*-
"""Full Comprehensive Krita Blending Modes Registry according to Krita CompositeOp Specs"""

from .qt_compat import QMenu, QAction
from .theme import get_theme

# Krita 官方完整混合模式分类列表
FULL_KRITA_BLENDING_MODES = [
    ("常用 (Favorites)", [
        ("正常", "normal"),
        ("正片叠底", "multiply"),
        ("滤色", "screen"),
        ("叠加", "overlay"),
        ("柔光", "soft_light"),
        ("强光", "hard_light"),
        ("颜色", "color"),
        ("明度", "luminosity"),
        ("穿透 (图层组)", "pass_through"),
        ("溶解", "dissolve"),
    ]),
    ("变暗 (Darken)", [
        ("变暗", "darken"),
        ("正片叠底", "multiply"),
        ("颜色加深", "color-burn"),
        ("线性加深", "linear_burn"),
        ("深色", "darker-color"),
        ("伽马变暗", "gamma_dark"),
        ("雾化变暗", "fog_darken"),
        ("阴影", "shades_very_easy"),
    ]),
    ("变亮 (Lighten)", [
        ("变亮", "lighten"),
        ("滤色", "screen"),
        ("颜色减淡", "color_dodge"),
        ("线性减淡 (加)", "add"),
        ("浅色", "lighter-color"),
        ("伽马变亮", "gamma_light"),
        ("雾化变亮", "fog_lighten"),
    ]),
    ("对比 (Contrast)", [
        ("叠加", "overlay"),
        ("柔光", "soft_light"),
        ("强光", "hard_light"),
        ("亮光", "vivid_light"),
        ("线性光", "linear_light"),
        ("点光", "pin_light"),
        ("实色混合", "hard_mix"),
        ("实色混合 (柔和)", "hard_mix_softer"),
        ("实色混合 (Photoshop)", "hard_mix_photoshop"),
    ]),
    ("减淡/加深 (Dodge/Burn)", [
        ("颜色减淡", "color_dodge"),
        ("线性减淡", "add"),
        ("颜色加深", "color-burn"),
        ("线性加深", "linear_burn"),
        ("易减淡", "easy_dodge"),
        ("易加深", "easy_burn"),
        ("柔减淡", "soft_dodge"),
        ("柔加深", "soft_burn"),
    ]),
    ("比较/反差 (Comparison)", [
        ("差值", "difference"),
        ("排除", "exclusion"),
        ("相当", "equivalence"),
        ("减去", "subtract"),
        ("划分", "divide"),
        ("否定", "negation"),
        ("绝对差值", "abs_difference"),
    ]),
    ("色彩/颜色 (HSI/HSV/HSL)", [
        ("色相", "hue"),
        ("饱和度", "saturation"),
        ("颜色", "color"),
        ("明度", "luminosity"),
        ("纯度 (Chroma)", "chroma"),
        ("灰度 (Luma)", "luma"),
        ("强光度 (Intensity)", "intensity"),
        ("价值 (Value)", "value"),
    ]),
    ("算术/数学 (Arithmetic)", [
        ("加", "add"),
        ("减", "subtract"),
        ("乘", "multiply"),
        ("除", "divide"),
        ("模 (Modulo)", "modulo"),
        ("连续模", "modulo_continuous"),
        ("连续乘", "multiply_continuous"),
    ]),
    ("负片 (Negative)", [
        ("反转", "invert"),
        ("反转 Alpha", "invert_alpha"),
        ("反转明度", "invert_lightness"),
    ]),
    ("杂项 (Misc)", [
        ("纹理提取 (Grain Extract)", "grain_extract"),
        ("纹理合并 (Grain Merge)", "grain_merge"),
        ("平行 (Parallel)", "parallel"),
        ("凹凸贴图 (Bumpmap)", "bumpmap"),
        ("法线贴图 (Normal Map)", "normal_map"),
    ]),
]

_ID_TO_NAME = {}
for _cat, _modes in FULL_KRITA_BLENDING_MODES:
    for _name, _id in _modes:
        _ID_TO_NAME[_id] = _name

def get_blending_mode_name(mode_id: str) -> str:
    if mode_id == "pass_through":
        return "穿透"
    return _ID_TO_NAME.get(mode_id, mode_id)

def create_categorized_blending_menu(parent_widget, callback):
    """Builds a multi-level nested QMenu for all Krita blending mode categories"""
    t = get_theme()
    menu = QMenu(parent_widget)
    menu.setStyleSheet(f"""
        QMenu {{
            background-color: {t.BG_BASE};
            color: {t.TEXT_MAIN};
            border: 1px solid {t.BORDER};
            border-radius: {t.RADIUS_BTN};
            padding: 2px;
        }}
        QMenu::item {{
            padding: 4px 14px 4px 8px;
            border-radius: 2px;
            font-size: 11px;
        }}
        QMenu::item:selected {{
            background-color: {t.SELECTION_BG};
            color: {t.ACCENT_TEXT};
        }}
    """)

    for cat_name, modes in FULL_KRITA_BLENDING_MODES:
        sub_menu = menu.addMenu(cat_name)
        sub_menu.setStyleSheet(menu.styleSheet())
        for mode_label, mode_id in modes:
            act = QAction(mode_label, sub_menu)
            act.triggered.connect(lambda checked, m_id=mode_id: callback(m_id))
            sub_menu.addAction(act)

    return menu
