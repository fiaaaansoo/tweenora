#!/bin/bash
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
WASM_DIR="$HERE/rive-wasm/wasm"
JS_DIR="$HERE/rive-wasm/js"
PKG_DIR="$JS_DIR/npm/webgl2"
DEPS="$ROOT/runtime/build/dependencies"
EMSDK_VERSION=4.0.23
JOBS="${TWEENORA_JOBS:-4}"
BUILD_WASM=1

case "${1:-}" in
"") ;;
--no-wasm) BUILD_WASM=0 ;;
*)
    echo "usage: $0 [--no-wasm]" >&2
    exit 2
    ;;
esac

for needed in "$DEPS/emsdk_$EMSDK_VERSION" "$DEPS/premake-core" "$DEPS/premake-ninja"; do
    if [ ! -d "$needed" ]; then
        echo "missing $needed: run runtime/build/build_rive.sh ninja release wasm first" >&2
        exit 1
    fi
done

PREMAKE_BIN=$(find "$DEPS/premake-core/bin" -name 'premake5*' -type f | head -1)
if [ -z "$PREMAKE_BIN" ]; then
    echo "no premake5 under $DEPS/premake-core/bin" >&2
    exit 1
fi
export PATH="$(dirname "$PREMAKE_BIN"):$PATH"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.longpaths GIT_CONFIG_VALUE_0=true
export RIVE_WASM_BUILD_SYSTEM=ninja

if ! command -v getconf >/dev/null 2>&1; then
    SHIM=$(mktemp -d)
    trap 'rm -rf "$SHIM"' EXIT
    printf '#!/bin/sh\necho %s\n' "$JOBS" >"$SHIM/getconf"
    chmod +x "$SHIM/getconf"
    export PATH="$SHIM:$PATH"
fi

if [ "$BUILD_WASM" = 1 ]; then
    cd "$WASM_DIR"
    mkdir -p bin ../js/npm/webgl2 ../js/npm/webgl2_advanced
    if [ ! -e "bin/emsdk_$EMSDK_VERSION" ]; then
        case "$(uname -s)" in
        MINGW* | MSYS* | CYGWIN*)
            cmd //c mklink //J "$(cygpath -w "$PWD/bin/emsdk_$EMSDK_VERSION")" "$(cygpath -w "$DEPS/emsdk_$EMSDK_VERSION")" >/dev/null
            ;;
        *) ln -s "$DEPS/emsdk_$EMSDK_VERSION" "bin/emsdk_$EMSDK_VERSION" ;;
        esac
    fi

    echo "::::: webgl2 fallback (no SIMD)"
    OUT_DIR=build/webgl2_advanced_fallback/bin/release ./build_wasm.sh -w -c -r webgl2 release
    cp build/webgl2_advanced_fallback/bin/release/webgl2_advanced.wasm ../js/npm/webgl2_advanced/rive_fallback.wasm
    cp build/webgl2_advanced_fallback/bin/release/webgl2_advanced.wasm ../js/npm/webgl2/rive_fallback.wasm

    echo "::::: webgl2"
    OUT_DIR=build/webgl2_advanced/bin/release ./build_wasm.sh -w -r webgl2 release
    cp build/webgl2_advanced/bin/release/webgl2_advanced.mjs ../js/npm/webgl2_advanced/webgl2_advanced.mjs
    cp build/webgl2_advanced/bin/release/webgl2_advanced.wasm ../js/npm/webgl2_advanced/rive.wasm
    cp build/webgl2_advanced/bin/release/webgl2_advanced.wasm ../js/npm/webgl2/rive.wasm
    cp ../js/src/rive_advanced.mjs.d.ts ../js/npm/webgl2_advanced/rive_advanced.mjs.d.ts
fi

for wasm in rive.wasm rive_fallback.wasm; do
    if [ ! -f "$PKG_DIR/$wasm" ]; then
        echo "missing $PKG_DIR/$wasm: run without --no-wasm first" >&2
        exit 1
    fi
done
python3 "$WASM_DIR/verify_fallback_abi.py" "$PKG_DIR/rive.wasm" "$PKG_DIR/rive_fallback.wasm"

cd "$JS_DIR"
[ -d node_modules ] || npm ci --no-audit --no-fund
npm run build -- --env targets=webgl2
mkdir -p build/pack
cd "$PKG_DIR"
npm pack --pack-destination "$(cd "$JS_DIR/build/pack" && pwd -W 2>/dev/null || pwd)"
