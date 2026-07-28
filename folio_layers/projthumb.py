# -*- coding: utf-8 -*-
"""Native C++ projection-thumbnail bridge via ctypes + sip"""

import ctypes
import os
import sys

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


def _find_lib():
    candidates = []
    # Same directory as this module
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "libfolio_projthumb.so"))
    # native/build relative to repo root
    repo_root = os.path.dirname(here)
    candidates.append(os.path.join(repo_root, "native", "build", "libfolio_projthumb.so"))
    # Krita plugin directory
    candidates.append(os.path.expanduser(
        "~/.local/share/krita/pykrita/lucide_layer_docker/libfolio_projthumb.so"))

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
        lib.folio_projection_thumbnail.argtypes = [
            ctypes.c_uint64,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
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


def native_projection_thumbnail(node, req_w, req_h):
    """Call the C++ lib to get a projection-based thumbnail.

    Returns a QImage (Format_RGBA8888) or None on failure.
    """
    lib = _load_lib()
    if lib is None or _sip is None:
        return None

    try:
        ptr = _sip.unwrapinstance(node)
    except Exception:
        return None
    if not ptr:
        return None

    out = ctypes.pointer(ctypes.c_ubyte())
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
    if not ret:
        return None

    w = outw.value
    h = outh.value
    stride = outstride.value
    if w <= 0 or h <= 0:
        lib.folio_free(out)
        return None

    img = QImage(out, w, h, stride, QImage.Format.Format_RGBA8888)
    result = img.copy()
    lib.folio_free(out)
    return result
