# -*- coding: utf-8 -*-
"""Native Krita Style Opacity Slider – matches the official layer docker appearance exactly"""

from .qt_compat import (
    QWidget, QSlider, QHBoxLayout, QLabel, pyqtSignal, Qt, QSizePolicy
)

class OpacityBarWidget(QWidget):
    """与 Krita 官方图层面板完全相同的不透明度滑块组合控件"""

    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 100

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        # 标签
        self._label = QLabel("不透明度:")
        self._label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._label)

        # 原生 Qt 水平滑块 (0-100)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(100)
        self._slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self._slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self._slider, 1)

        # 数字显示
        self._val_label = QLabel("100%")
        self._val_label.setFixedWidth(32)
        self._val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._val_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._val_label)

    def value(self) -> int:
        return self._value

    def setValue(self, val: int):
        clamped = max(0, min(100, int(val)))
        if self._value != clamped:
            self._value = clamped
            self._slider.blockSignals(True)
            self._slider.setValue(clamped)
            self._slider.blockSignals(False)
            self._val_label.setText(f"{clamped}%")

    def _on_slider_changed(self, val: int):
        self._value = val
        self._val_label.setText(f"{val}%")
        self.valueChanged.emit(val)
