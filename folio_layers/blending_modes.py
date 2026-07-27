# -*- coding: utf-8 -*-
"""Full Comprehensive Krita Blending Modes Registry

Composite op IDs sourced from KoCompositeOpRegistry.h (Krita 6.x)
"""

from .qt_compat import QMenu, QAction
from .theme import get_theme

# Krita 官方完整混合模式分类列表
# IDs correspond to KoCompositeOpRegistry::getCompositeOps()
FULL_KRITA_BLENDING_MODES = [
    ("常用 (Favorites)", [
        ("正常", "normal"),
        ("正片叠底", "multiply"),
        ("滤色", "screen"),
        ("叠加", "overlay"),
        ("柔光", "soft_light"),
        ("强光", "hard_light"),
        ("颜色", "color"),
        ("明度", "luminize"),
        ("穿透 (图层组)", "pass through"),
        ("溶解", "dissolve"),
    ]),
    ("变暗 (Darken)", [
        ("变暗", "darken"),
        ("正片叠底", "multiply"),
        ("颜色加深", "burn"),
        ("线性加深", "linear_burn"),
        ("深色", "darker color"),
        ("伽马变暗", "gamma_dark"),
        ("雾化变暗", "fog_darken_ifs_illusions"),
        ("阴影", "shade_ifs_illusions"),
        ("易加深", "easy burn"),
    ]),
    ("变亮 (Lighten)", [
        ("变亮", "lighten"),
        ("滤色", "screen"),
        ("颜色减淡", "dodge"),
        ("线性减淡", "linear_dodge"),
        ("浅色", "lighter color"),
        ("伽马变亮", "gamma_light"),
        ("雾化变亮", "fog_lighten_ifs_illusions"),
        ("易减淡", "easy dodge"),
    ]),
    ("对比 (Contrast)", [
        ("叠加", "overlay"),
        ("柔光", "soft_light"),
        ("强光", "hard_light"),
        ("亮光", "vivid_light"),
        ("线性光", "linear light"),
        ("点光", "pin_light"),
        ("实色混合", "hard mix"),
        ("实色混合 (柔和)", "hard_mix_softer_photoshop"),
        ("实色混合 (Photoshop)", "hard_mix_photoshop"),
        ("强对比", "hard overlay"),
    ]),
    ("减淡/加深 (Dodge/Burn)", [
        ("颜色减淡", "dodge"),
        ("线性减淡", "linear_dodge"),
        ("颜色加深", "burn"),
        ("线性加深", "linear_burn"),
        ("易减淡", "easy dodge"),
        ("易加深", "easy burn"),
        ("柔减淡", "soft_light_svg"),
        ("柔加深", "soft_light_ifs_illusions"),
    ]),
    ("比较/反差 (Comparison)", [
        ("差值", "diff"),
        ("排除", "exclusion"),
        ("相当", "equivalence"),
        ("减去", "subtract"),
        ("划分", "divide"),
        ("否定", "negation"),
        ("绝对差值", "negation"),
    ]),
    ("色彩/颜色 (HSI/HSV/HSL)", [
        ("色相", "hue"),
        ("饱和度", "saturation"),
        ("颜色", "color"),
        ("明度", "luminize"),
        ("强光度 (Intensity)", "intensity"),
        ("价值 (Value)", "value"),
        ("色相 (HSV)", "hue_hsv"),
        ("颜色 (HSV)", "color_hsv"),
        ("饱和度 (HSV)", "saturation_hsv"),
        ("色相 (HSL)", "hue_hsl"),
        ("颜色 (HSL)", "color_hsl"),
        ("饱和度 (HSL)", "saturation_hsl"),
        ("明度 (HSL)", "lightness"),
        ("色相 (HSI)", "hue_hsi"),
        ("颜色 (HSI)", "color_hsi"),
        ("饱和度 (HSI)", "saturation_hsi"),
    ]),
    ("算术/数学 (Arithmetic)", [
        ("加", "add"),
        ("减", "subtract"),
        ("乘", "multiply"),
        ("除", "divide"),
        ("模 (Modulo)", "modulo"),
        ("连续模", "modulo_continuous"),
        ("除模 (Divisive Mod)", "divisive_modulo"),
        ("连续除模", "divisive_modulo_continuous"),
        ("模位移 (Modulo Shift)", "modulo_shift"),
        ("连续模位移", "modulo_shift_continuous"),
        ("反正切 (Arc Tangent)", "arc_tangent"),
        ("几何平均 (Geometric Mean)", "geometric_mean"),
        ("加减混合", "additive_subtractive"),
    ]),
    ("负片 (Negative)", [
        ("反转", "minus"),
        ("反转", "diff"),
        ("排除", "exclusion"),
        ("否定", "negation"),
    ]),
    ("杂项 (Misc)", [
        ("纹理提取 (Grain Extract)", "grain_extract"),
        ("纹理合并 (Grain Merge)", "grain_merge"),
        ("平行 (Parallel)", "parallel"),
        ("凹凸贴图 (Bumpmap)", "bumpmap"),
        ("法线贴图 (Normal Map)", "tangent_normalmap"),
        ("颜色化 (Colorize)", "colorize"),
        ("合并法线 (Combine Normal)", "combine_normal"),
        ("Lambert 光照", "lambert_lighting"),
    ]),
]

_ID_TO_NAME = {}
for _cat, _modes in FULL_KRITA_BLENDING_MODES:
    for _name, _id in _modes:
        _ID_TO_NAME[_id] = _name

def get_blending_mode_name(mode_id: str) -> str:
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