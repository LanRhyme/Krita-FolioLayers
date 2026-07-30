# -*- coding: utf-8 -*-
"""Configuration manager for Folio Layer Docker"""

import json
import os
from .qt_compat import QSettings

DETAIL_NONE = "none"         # 无: 仅缩略图+名称
DETAIL_COMPACT = "compact"   # 简洁: 缩略图+名称+可见性+锁定
DETAIL_BALANCED = "balanced" # 平衡(默认): 缩略图+名称+类型图标+可见性+锁定+Alpha锁+继承Alpha
DETAIL_DETAILED = "detailed" # 完整: 缩略图+名称+类型图标+尺寸+不透明度%+全控制按钮

class LayerDockerConfig:
    """Persistent plugin settings stored via QSettings"""

    def __init__(self):
        self.settings = QSettings("Krita", "FolioLayers")

    @property
    def thumb_size(self) -> int:
        return int(self.settings.value("thumb_size", 40))  # 默认 40x40 px

    @thumb_size.setter
    def thumb_size(self, val: int):
        self.settings.setValue("thumb_size", int(val))

    @property
    def detail_level(self) -> str:
        return str(self.settings.value("detail_level", DETAIL_BALANCED))

    @detail_level.setter
    def detail_level(self, val: str):
        self.settings.setValue("detail_level", str(val))

    @property
    def use_checkerboard(self) -> bool:
        v = self.settings.value("use_checkerboard", True)
        return str(v).lower() in ("true", "1")

    @use_checkerboard.setter
    def use_checkerboard(self, val: bool):
        self.settings.setValue("use_checkerboard", bool(val))

    @property
    def enable_hover_preview(self) -> bool:
        v = self.settings.value("enable_hover_preview", True)
        return str(v).lower() in ("true", "1")

    @enable_hover_preview.setter
    def enable_hover_preview(self, val: bool):
        self.settings.setValue("enable_hover_preview", bool(val))

    @property
    def show_group_count(self) -> bool:
        v = self.settings.value("show_group_count", True)
        return str(v).lower() in ("true", "1")

    @show_group_count.setter
    def show_group_count(self, val: bool):
        self.settings.setValue("show_group_count", bool(val))

    @property
    def enable_swipe_gesture(self) -> bool:
        v = self.settings.value("enable_swipe_gesture", True)
        return str(v).lower() in ("true", "1")

    @enable_swipe_gesture.setter
    def enable_swipe_gesture(self, val: bool):
        self.settings.setValue("enable_swipe_gesture", bool(val))

    @property
    def show_selection_masks(self) -> bool:
        v = self.settings.value("show_selection_masks", False)  # 默认不显示选区蒙版
        return str(v).lower() in ("true", "1")

    @show_selection_masks.setter
    def show_selection_masks(self, val: bool):
        self.settings.setValue("show_selection_masks", bool(val))

    @property
    def solo_shortcut(self) -> str:
        return str(self.settings.value("solo_shortcut", "Ctrl+Click"))

    @solo_shortcut.setter
    def solo_shortcut(self, val: str):
        self.settings.setValue("solo_shortcut", str(val))

config_instance = LayerDockerConfig()

def get_config():
    return config_instance
