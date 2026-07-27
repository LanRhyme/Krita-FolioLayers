# -*- coding: utf-8 -*-
"""Native Krita Style Opacity Slider – matches the official layer docker appearance exactly"""

from .qt_compat import (
    QWidget, QSlider, QHBoxLayout, QLabel, pyqtSignal, Qt, QSizePolicy, QTimer
)
from .theme import get_theme

class OpacityBarWidget(QWidget):
    """Krita 官方风格不透明度滑块组合控件"""

    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 100
        self._pending = 0

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._apply_pending)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self._label = QLabel("不透明度:")
        self._label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(100)
        self._slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(1)
        self._slider.setTracking(True)
        self._slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self._slider, 1)

        self._val_label = QLabel("100%")
        self._val_label.setFixedWidth(32)
        self._val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._val_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self._val_label)

        self._update_style()

    def _update_style(self):
        t = get_theme()
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {t.BG_ALT};
                border: 1px solid {t.BORDER};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                height: 6px;
                background: {t.ACCENT};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 10px;
                height: 10px;
                margin: -3px 0;
                background: {t.TEXT_MAIN};
                border: 1px solid {t.BORDER};
                border-radius: 5px;
            }}
            QSlider::add-page:horizontal {{
                height: 6px;
            }}
        """)

    def value(self) -> int:
        return self._value

    def setValue(self, val: int):
        clamped = max(0, min(100, int(val)))
        if self._value != clamped:
            self._value = clamped
            self._pending = 0
            self._slider.blockSignals(True)
            self._slider.setValue(clamped)
            self._slider.blockSignals(False)
            self._val_label.setText(f"{clamped}%")

    def apply(self):
        if self._pending:
            self._value = self._pending
            self._pending = 0
            self.valueChanged.emit(self._value)

    def _apply_pending(self):
        self.apply()

    def _on_slider_changed(self, val: int):
        self._pending = val
        self._val_label.setText(f"{val}%")
        self._timer.start()

    def _on_slider_released(self):
        self._timer.stop()
        self.apply()

    def mousePressEvent(self, event):
        """Click on slider groove to jump to position immediately"""
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        slider_rect = self._slider.rect()
        slider_pos = self._slider.mapFromParent(event.pos())
        if slider_rect.contains(slider_pos) and slider_pos.x() >= 0:
            pct = int(slider_pos.x() / slider_rect.width() * 100)
            pct = max(0, min(100, pct))
            self._slider.setValue(pct)
            self._pending = pct
            self._val_label.setText(f"{pct}%")
            self.apply()
        super().mousePressEvent(event)
