# -*- coding: utf-8 -*-
"""Krita Blending Modes Registry

Composite op IDs and display names sourced from Krita's KoCompositeOpRegistry
and zh_CN translation (krita.po)
"""

from .qt_compat import QMenu, QAction
from .theme import get_theme

# Krita 官方混合模式分类列表
# 中文名称来自 Krita 官方翻译 (krita.po)
# 菜单分类按 Krita 官方分类组织，方便快速查找
FULL_KRITA_BLENDING_MODES = [
    ("常用 (Favorites)", [
        ("正常", "normal"),
        ("溶解", "dissolve"),
        ("变暗", "darken"),
        ("正片叠底", "multiply"),
        ("颜色加深", "burn"),
        ("线性加深", "linear_burn"),
        ("变亮", "lighten"),
        ("滤色", "screen"),
        ("颜色减淡", "dodge"),
        ("线性减淡", "linear_dodge"),
        ("叠加", "overlay"),
        ("柔光", "soft_light"),
        ("强光", "hard_light"),
        ("亮光", "vivid_light"),
        ("线性光", "linear light"),
        ("点光", "pin_light"),
        ("实色混合", "hard mix"),
        ("差值", "diff"),
        ("排除", "exclusion"),
        ("色相", "hue"),
        ("饱和度", "saturation"),
        ("颜色", "color"),
        ("明度", "luminize"),
        ("穿透 (图层组)", "pass through"),
    ]),
    ("变暗 (Darken)", [
        ("变暗", "darken"),
        ("正片叠底", "multiply"),
        ("颜色加深", "burn"),
        ("线性加深", "linear_burn"),
        ("深色", "darker color"),
        ("伽马变暗", "gamma_dark"),
        ("阴影 (IFS Illusions)", "shade_ifs_illusions"),
        ("雾状变暗 (IFS Illusions)", "fog_darken_ifs_illusions"),
        ("平缓加深", "easy burn"),
    ]),
    ("变亮 (Lighten)", [
        ("变亮", "lighten"),
        ("滤色", "screen"),
        ("颜色减淡", "dodge"),
        ("线性减淡", "linear_dodge"),
        ("浅色", "lighter color"),
        ("伽马变亮", "gamma_light"),
        ("雾状变亮 (IFS Illusions)", "fog_lighten_ifs_illusions"),
        ("平缓减淡", "easy dodge"),
    ]),
    ("颜色混合 (Mix)", [
        ("叠加", "overlay"),
        ("柔光 (Photoshop)", "soft_light"),
        ("强光", "hard_light"),
        ("亮光", "vivid_light"),
        ("线性光", "linear light"),
        ("点光", "pin_light"),
        ("实色混合", "hard mix"),
        ("实色混合 (Photoshop)", "hard_mix_photoshop"),
        ("实色混合柔和 (Photoshop)", "hard_mix_softer_photoshop"),
        ("强光叠加", "hard overlay"),
        ("背后", "behind"),
        ("擦除", "erase"),
        ("透明度变暗", "alphadarken"),
        ("马克笔", "marker"),
    ]),
    ("减淡/加深 (Dodge/Burn)", [
        ("颜色减淡", "dodge"),
        ("线性减淡", "linear_dodge"),
        ("颜色加深", "burn"),
        ("线性加深", "linear_burn"),
        ("平缓减淡", "easy dodge"),
        ("平缓加深", "easy burn"),
    ]),
    ("比较/反差 (Comparison)", [
        ("差值", "diff"),
        ("排除", "exclusion"),
        ("等效值", "equivalence"),
        ("减去", "subtract"),
        ("划分", "divide"),
        ("取反", "negation"),
        ("减去反相值", "inverse_subtract"),
    ]),
    ("HSY 颜色调整 (HSY)", [
        ("色相", "hue"),
        ("饱和度", "saturation"),
        ("颜色", "color"),
        ("明度", "luminize"),
        ("着色", "tint"),
        ("提高饱和度", "inc_saturation"),
        ("降低饱和度", "dec_saturation"),
        ("提高明度", "inc_luminosity"),
        ("降低明度", "dec_luminosity"),
    ]),
    ("数学运算 (Arithmetic)", [
        ("相加", "add"),
        ("减去", "subtract"),
        ("正片叠底", "multiply"),
        ("划分", "divide"),
        ("减去反相值", "inverse_subtract"),
        ("反正切值", "arc_tangent"),
        ("几何平均", "geometric_mean"),
        ("减去平方根", "additive_subtractive"),
    ]),
    ("取模运算 (Modulo)", [
        ("取模运算", "modulo"),
        ("取模运算 - 连续", "modulo_continuous"),
        ("取余运算", "divisive_modulo"),
        ("取余运算 - 连续", "divisive_modulo_continuous"),
        ("取模运算偏移", "modulo_shift"),
        ("取模运算偏移 - 连续", "modulo_shift_continuous"),
    ]),
    ("负片 (Negative)", [
        ("差值", "diff"),
        ("排除", "exclusion"),
        ("取反", "negation"),
        ("减去", "subtract"),
    ]),
    ("杂项 (Misc)", [
        ("颗粒合并", "grain_merge"),
        ("颗粒抽取", "grain_extract"),
        ("平行", "parallel"),
        ("凹凸贴图", "bumpmap"),
        ("切线空间法线贴图", "tangent_normalmap"),
        ("合并法线贴图", "combine_normal"),
        ("颜色化", "colorize"),
        ("复制", "copy"),
        ("Lambert 光照 (线性)", "lambert_lighting"),
    ]),
]

_ID_TO_NAME = {}
_SEEN_IDS = set()
for _cat, _modes in FULL_KRITA_BLENDING_MODES:
    for _name, _id in _modes:
        if _id not in _SEEN_IDS:
            _ID_TO_NAME[_id] = _name
            _SEEN_IDS.add(_id)


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