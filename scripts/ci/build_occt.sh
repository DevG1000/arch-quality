#!/usr/bin/env bash
# build_occt.sh - Build OCCT V8.0.1 (pinned) for H3 runtime kernel checks (G0 / method C).
#
# Pinned to the sample ref in projects.yaml: V8.0.1 = b8f597c677811d1f9f4d8a97f5ae2825c0353a42.
# Installs into $OCCT_CACHE/install so CI can cache and reuse it (avoids per-run source build).
#
# Env:
#   OCCT_REPO   default https://github.com/Open-Cascade-SAS/OCCT.git
#   OCCT_REF    default b8f597c677811d1f9f4d8a97f5ae2825c0353a42  (V8.0.1)
#   OCCT_CACHE  default $PWD/.occt-cache
set -euo pipefail

OCCT_REPO="${OCCT_REPO:-https://github.com/Open-Cascade-SAS/OCCT.git}"
OCCT_REF="${OCCT_REF:-b8f597c677811d1f9f4d8a97f5ae2825c0353a42}"
OCCT_CACHE="${OCCT_CACHE:-$PWD/.occt-cache}"
SRC="$OCCT_CACHE/src"
BUILD="$OCCT_CACHE/build"
PREFIX="$OCCT_CACHE/install"

if [ -f "$PREFIX/lib/libTKernel.so" ] || [ -f "$PREFIX/lib/libTKernel.dylib" ]; then
  echo "[build_occt] already installed at $PREFIX"
  exit 0
fi

mkdir -p "$OCCT_CACHE"
if [ ! -d "$SRC/.git" ]; then
  echo "[build_occt] fetch $OCCT_REPO @ $OCCT_REF"
  git init -q "$SRC"
  git -C "$SRC" remote add origin "$OCCT_REPO"
  git -C "$SRC" fetch --depth 1 origin "$OCCT_REF"
  git -C "$SRC" checkout -q FETCH_HEAD
fi
echo "[build_occt] HEAD: $(git -C "$SRC" rev-parse HEAD)"

# Minimal modules: keep FoundationClasses/ModelingData/ModelingAlgorithms/DataExchange,
# drop Visualization/ApplicationFramework/Draw to cut build time and disk.
cmake -S "$SRC" -B "$BUILD" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DBUILD_MODULE_Visualization=OFF \
  -DBUILD_MODULE_ApplicationFramework=OFF \
  -DBUILD_MODULE_Draw=OFF \
  -DBUILD_DOC_Overview=OFF \
  -DBUILD_DOC_RefMan=OFF \
  -DUSE_TBB=OFF -DUSE_VTK=OFF -DUSE_FREEIMAGE=OFF -DUSE_RAPIDJSON=OFF -DUSE_Draco=OFF -DUSE_FREETYPE=OFF
cmake --build "$BUILD" --config Release --parallel "$(nproc)"
cmake --install "$BUILD" --config Release
echo "[build_occt] installed to $PREFIX"