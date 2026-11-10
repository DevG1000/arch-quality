#!/usr/bin/env bash
# run_kernel_smoke.sh - Compile & run the OCCT kernel smoke probe (G0 substrate check).
set -euo pipefail
OCCT_CACHE="${OCCT_CACHE:-$PWD/.occt-cache}"
PREFIX="$OCCT_CACHE/install"
CXX="${CXX:-g++}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$CXX" -std=c++17 "$HERE/kernel_smoke.cpp" \
  -I"$PREFIX/include/opencascade" \
  -L"$PREFIX/lib" \
  -lTKernel -lTKMath -lTKBRep -lTKTopAlgo -lTKPrim -lTKShHealing \
  -o "$OCCT_CACHE/kernel_smoke"

LD_LIBRARY_PATH="$PREFIX/lib:${LD_LIBRARY_PATH:-}" "$OCCT_CACHE/kernel_smoke"