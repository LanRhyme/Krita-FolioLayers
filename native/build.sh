#!/bin/bash
set -e

SRC_DIR="$(dirname "$(readlink -f "$0")")"
KRITA_SRC="$HOME/Projects/krita-source/libs"
COMPAT="$SRC_DIR/compat"
BUILD="$SRC_DIR/build"

QT_CFLAGS="$(pkg-config --cflags Qt6Core Qt6Gui)"
QT_LIBS="$(pkg-config --libs Qt6Core Qt6Gui)"

INCLUDES=(
    -I"$COMPAT"
    -I"$KRITA_SRC/libkis"
    -I"$KRITA_SRC/image"
    -I"$KRITA_SRC/global"
    -I"$KRITA_SRC/pigment"
    -I"$KRITA_SRC/brush"
    -I"$KRITA_SRC/flake"
    -I"$KRITA_SRC/widgetutils"
    -I/usr/include/KF6
    -I/usr/include/KF6/KI18n
    -I/usr/include/KF6/KCoreAddons
    -I/usr/include/KF6/KConfig
    -I/usr/include/KF6/KConfigCore
)

g++ -shared -fPIC -std=c++17 \
    "${INCLUDES[@]}" \
    $QT_CFLAGS \
    -o "$BUILD/libfolio_projthumb.so" \
    "$SRC_DIR/folio_projthumb.cpp" \
    -L/usr/lib \
    -lkritalibkis -lkritaimage -lkritapigment -lkritaglobal \
    $QT_LIBS

echo "Built: $BUILD/libfolio_projthumb.so"
ldd "$BUILD/libfolio_projthumb.so" | grep -i krita
