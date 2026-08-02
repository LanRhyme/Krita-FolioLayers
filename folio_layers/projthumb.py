# -*- coding: utf-8 -*-
"""
Native C++ projection-thumbnail bridge via ctypes + sip
Includes cross-platform DLL/SO discovery and graceful pure-Python fallback mechanism
"""

import ctypes
import os

from .qt_compat import QImage

try:
    from PyQt6 import sip as _sip
except ImportError:
    try:
        import sip as _sip
    except ImportError:
        _sip = None

_LIB = None
_LIB_TRIED = False


def _qt_major():
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        return 6
    except ImportError:
        return 5


def _find_lib():
    candidates = []
    here = os.path.dirname(os.path.abspath(__file__))
    qt = _qt_major()
    lib_names = [
        "libfolio_projthumb_qt%d.so" % qt,
        "libfolio_projthumb_qt%d.dll" % qt,
        "libfolio_projthumb.so",
        "libfolio_projthumb.dll",
        "folio_projthumb.dll",
    ]

    for name in lib_names:
        candidates.append(os.path.join(here, name))
        candidates.append(os.path.expanduser(f"~/.local/share/krita/pykrita/folio_layers/{name}"))
        candidates.append(os.path.expandvars(f"%APPDATA%/krita/pykrita/folio_layers/{name}"))

    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _load_lib():
    global _LIB, _LIB_TRIED
    if _LIB_TRIED:
        return _LIB
    _LIB_TRIED = True

    path = _find_lib()
    if path is None:
        return None

    try:
        lib = ctypes.CDLL(path)
        if hasattr(lib, 'folio_projection_thumbnail'):
            lib.folio_projection_thumbnail.argtypes = [
                ctypes.c_uint64,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
            ]
            lib.folio_projection_thumbnail.restype = ctypes.c_int
            lib.folio_free.argtypes = [ctypes.c_void_p]
            lib.folio_free.restype = None
            _LIB = lib
            return _LIB
    except Exception:
        return None
    return None


def native_projection_thumbnail(node, req_w, req_h):
    """Call the native C++ library to generate high-performance projection thumbnails.
    If native library is unavailable (e.g. Windows without DLL), gracefully falls back to node.thumbnail().

    Returns a QImage or None.
    """
    lib = _load_lib()
    if lib is not None and _sip is not None:
        try:
            ptr = _sip.unwrapinstance(node)
            if ptr:
                out = ctypes.c_void_p()
                outw = ctypes.c_int()
                outh = ctypes.c_int()
                outstride = ctypes.c_int()

                ret = lib.folio_projection_thumbnail(
                    ctypes.c_uint64(ptr),
                    ctypes.c_int(req_w),
                    ctypes.c_int(req_h),
                    ctypes.byref(out),
                    ctypes.byref(outw),
                    ctypes.byref(outh),
                    ctypes.byref(outstride),
                )
                if ret and outw.value > 0 and outh.value > 0 and out.value:
                    w, h, stride = outw.value, outh.value, outstride.value
                    buf_size = stride * h
                    raw = ctypes.string_at(out.value, buf_size)
                    img = QImage(raw, w, h, stride, QImage.Format.Format_RGBA8888)
                    result = img.copy()
                    lib.folio_free(out)
                    return result
        except Exception:
            pass

    # 纯 Python 无缝降级回退机制（如 Windows 未编译 dll 或动态库缺失）
    if node and hasattr(node, 'thumbnail'):
        try:
            pix = node.thumbnail(req_w, req_h)
            if pix and not pix.isNull():
                return pix.toImage() if hasattr(pix, 'toImage') else pix
        except Exception:
            pass

    return None
