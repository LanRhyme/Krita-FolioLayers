# -*- coding: utf-8 -*-
"""Dynamic Krita Palette Theme Helper & Checkerboard Thumbnail Generator"""

from .qt_compat import (
    QApplication, QPalette, QColor, QPixmap, QPainter, QImage, Qt, QBrush, QSize
)

class DynamicKritaTheme:
    """Dynamically reads colors from Krita's active QApplication QPalette"""

    def _get_palette(self):
        app = QApplication.instance()
        return app.palette() if app else QPalette()

    @property
    def BG_DARK(self):
        return self._get_palette().color(QPalette.ColorRole.Window).name()

    @property
    def BG_BASE(self):
        return self._get_palette().color(QPalette.ColorRole.Base).name()

    @property
    def BG_ALT(self):
        pal = self._get_palette()
        c = pal.color(QPalette.ColorRole.AlternateBase)
        if c == pal.color(QPalette.ColorRole.Window):
            return pal.color(QPalette.ColorRole.Mid).name()
        return c.name()

    @property
    def TEXT_MAIN(self):
        return self._get_palette().color(QPalette.ColorRole.WindowText).name()

    @property
    def TEXT_MUTED(self):
        pal = self._get_palette()
        text = pal.color(QPalette.ColorRole.WindowText)
        bg = pal.color(QPalette.ColorRole.Window)
        r = (text.red() * 2 + bg.red()) // 3
        g = (text.green() * 2 + bg.green()) // 3
        b = (text.blue() * 2 + bg.blue()) // 3
        return QColor(r, g, b).name()

    @property
    def ACCENT(self):
        return self._get_palette().color(QPalette.ColorRole.Highlight).name()

    @property
    def ACCENT_RGB(self):
        c = self._get_palette().color(QPalette.ColorRole.Highlight)
        return f"{c.red()}, {c.green()}, {c.blue()}"

    @property
    def ACCENT_TEXT(self):
        return self._get_palette().color(QPalette.ColorRole.HighlightedText).name()

    @property
    def BORDER(self):
        pal = self._get_palette()
        return pal.color(QPalette.ColorRole.Mid).name()

    @property
    def HOVER_BG(self):
        pal = self._get_palette()
        base = pal.color(QPalette.ColorRole.Base)
        hl = pal.color(QPalette.ColorRole.Highlight)
        r = int(base.red() * 0.85 + hl.red() * 0.15)
        g = int(base.green() * 0.85 + hl.green() * 0.15)
        b = int(base.blue() * 0.85 + hl.blue() * 0.15)
        return QColor(r, g, b).name()

    @property
    def SELECTION_BG(self):
        return self._get_palette().color(QPalette.ColorRole.Highlight).name()

    RADIUS = "3px"
    RADIUS_BTN = "3px"

_theme_instance = DynamicKritaTheme()

def get_theme():
    return _theme_instance

_checkerboard_cache = {}

def create_checkerboard_pixmap(w, h, grid_size=4):
    """Generates a transparent checkerboard pattern pixmap (cached by size)"""
    cache_key = (w, h, grid_size)
    cached = _checkerboard_cache.get(cache_key)
    if cached is not None:
        return cached.copy()

    pix = QPixmap(w, h)
    painter = QPainter(pix)
    c1 = QColor(220, 220, 220)
    c2 = QColor(170, 170, 170)
    for x in range(0, w, grid_size):
        for y in range(0, h, grid_size):
            fill = c1 if ((x // grid_size) + (y // grid_size)) % 2 == 0 else c2
            painter.fillRect(x, y, grid_size, grid_size, fill)
    painter.end()

    _checkerboard_cache[cache_key] = pix
    return pix.copy()

def clear_theme_cache():
    """Clear all theme-related caches (call when theme/thumb_size changes)"""
    _checkerboard_cache.clear()

def draw_thumbnail_with_checkerboard(qimg, w, h, use_checkerboard=True):
    """Renders thumbnail QImage onto a checkerboard or flat background pixmap"""
    if use_checkerboard:
        base_pix = create_checkerboard_pixmap(w, h)
    else:
        t = get_theme()
        base_pix = QPixmap(w, h)
        base_pix.fill(QColor(t.BG_DARK))

    if qimg and not qimg.isNull():
        painter = QPainter(base_pix)
        scaled_img = qimg.scaled(
            QSize(w, h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        offset_x = (w - scaled_img.width()) // 2
        offset_y = (h - scaled_img.height()) // 2
        painter.drawImage(offset_x, offset_y, scaled_img)
        painter.end()
    return base_pix

def _aspect_ratio_dims(src_w, src_h, max_dim):
    """计算保持宽高比的目标尺寸（用于 node.thumbnail 调用，避免 IgnoreAspectRatio 拉伸）"""
    if src_w <= 0 or src_h <= 0:
        return max_dim, max_dim
    scale = max_dim / max(src_w, src_h)
    tw = max(1, int(src_w * scale))
    th = max(1, int(src_h * scale))
    return tw, th

def create_projection_thumbnail(node, thumb_size, use_checkerboard=True):
    """
    生成投影缩略图（含蒙版/效果/子图层）。
    优先使用 C++ 动态库（projection()->createThumbnail），
    失败时回退到 Python projectionPixelData 方案。
    返回与 draw_thumbnail_with_checkerboard 兼容的 QPixmap。
    """
    # 优先尝试原生 C++ 库
    try:
        from .projthumb import native_projection_thumbnail
        qimg = native_projection_thumbnail(node, thumb_size, thumb_size)
        if qimg is not None and not qimg.isNull():
            return draw_thumbnail_with_checkerboard(qimg, thumb_size, thumb_size, use_checkerboard)
    except Exception:
        pass

    # 回退：Python projectionPixelData 方案
    try:
        bounds = node.bounds()
    except Exception:
        bounds = None
    if not bounds or bounds.width() <= 0 or bounds.height() <= 0:
        return draw_thumbnail_with_checkerboard(None, thumb_size, thumb_size, use_checkerboard)

    bw, bh = bounds.width(), bounds.height()
    max_sample = 256
    scale = min(1.0, max_sample / max(bw, bh))
    sw, sh = max(1, int(bw * scale)), max(1, int(bh * scale))

    try:
        raw = node.projectionPixelData(bounds.x(), bounds.y(), sw, sh)
    except Exception:
        raw = b""

    if not raw:
        try:
            tw, th = _aspect_ratio_dims(bw, bh, thumb_size)
            qimg = node.thumbnail(tw, th)
            return draw_thumbnail_with_checkerboard(qimg, thumb_size, thumb_size, use_checkerboard)
        except Exception:
            return draw_thumbnail_with_checkerboard(None, thumb_size, thumb_size, use_checkerboard)

    expected_pixels = sw * sh
    bytes_per_pixel = len(raw) // expected_pixels if expected_pixels > 0 else 0
    if bytes_per_pixel == 0:
        return draw_thumbnail_with_checkerboard(None, thumb_size, thumb_size, use_checkerboard)

    img = None
    if bytes_per_pixel == 4:
        img = QImage(raw, sw, sh, sw * 4, QImage.Format.Format_ARGB32)
        img = img.copy()
    elif bytes_per_pixel == 3:
        rgb_data = bytearray(len(raw))
        for i in range(0, len(raw), 3):
            rgb_data[i] = raw[i + 2]
            rgb_data[i + 1] = raw[i + 1]
            rgb_data[i + 2] = raw[i]
        img = QImage(bytes(rgb_data), sw, sh, sw * 3, QImage.Format.Format_RGB888)
        img = img.copy()
    else:
        try:
            tw, th = _aspect_ratio_dims(bw, bh, thumb_size)
            qimg = node.thumbnail(tw, th)
            return draw_thumbnail_with_checkerboard(qimg, thumb_size, thumb_size, use_checkerboard)
        except Exception:
            pass

    if img is None or img.isNull():
        return draw_thumbnail_with_checkerboard(None, thumb_size, thumb_size, use_checkerboard)

    return draw_thumbnail_with_checkerboard(img, thumb_size, thumb_size, use_checkerboard)
