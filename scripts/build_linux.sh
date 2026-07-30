#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
BUILD_ROOT="$PROJECT_ROOT/.build/linux"
VENV_DIR="$BUILD_ROOT/venv"
PYINSTALLER_WORK="$BUILD_ROOT/pyinstaller"
DIST_DIR="$PROJECT_ROOT/dist/linux"
PYTHON_COMMAND="${PYTHON_COMMAND:-python3}"

test -f "$PROJECT_ROOT/release/banhelper-bridge-2.0.0.jar"
test -f "$PROJECT_ROOT/assets/banhelper.png"
test -f "$PROJECT_ROOT/assets/banhelper.svg"

rm -rf -- "$BUILD_ROOT" "$DIST_DIR"
mkdir -p -- "$BUILD_ROOT" "$DIST_DIR"
"$PYTHON_COMMAND" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check --requirement "$PROJECT_ROOT/requirements-build.txt"

export BANHELPER_OUTPUT_NAME="BanHelper.grxt"
export PYINSTALLER_CONFIG_DIR="$BUILD_ROOT/pyinstaller-config"
"$VENV_DIR/bin/python" -m PyInstaller \
  --noconfirm \
  --workpath "$PYINSTALLER_WORK" \
  --distpath "$DIST_DIR" \
  "$PROJECT_ROOT/packaging/banhelper.spec"

chmod +x "$DIST_DIR/BanHelper.grxt"
cp -- "$PROJECT_ROOT/packaging/banhelper.desktop" "$DIST_DIR/banhelper.desktop"
cp -- "$PROJECT_ROOT/assets/banhelper.png" "$DIST_DIR/banhelper.png"
cp -- "$PROJECT_ROOT/assets/banhelper.svg" "$DIST_DIR/banhelper.svg"

SMOKE_ROOT="$BUILD_ROOT/smoke path кириллица"
MOVED_DIR="$BUILD_ROOT/moved artifact"
mkdir -p -- "$SMOKE_ROOT/config" "$SMOKE_ROOT/data" "$SMOKE_ROOT/cache" "$MOVED_DIR"
cp -- "$DIST_DIR/BanHelper.grxt" "$MOVED_DIR/BanHelper.grxt"
chmod +x "$MOVED_DIR/BanHelper.grxt"
env -i \
  HOME="$SMOKE_ROOT" \
  XDG_CONFIG_HOME="$SMOKE_ROOT/config" \
  XDG_DATA_HOME="$SMOKE_ROOT/data" \
  XDG_CACHE_HOME="$SMOKE_ROOT/cache" \
  QT_QPA_PLATFORM=offscreen \
  "$MOVED_DIR/BanHelper.grxt" --packaging-smoke

test -f "$SMOKE_ROOT/data/banhelper/banhelper.sqlite3"
test ! -e "$MOVED_DIR/banhelper.sqlite3"
test ! -e "$MOVED_DIR/BanHelper"
sha256sum "$DIST_DIR/BanHelper.grxt" > "$DIST_DIR/SHA256SUMS.txt"
echo "Linux release created: $DIST_DIR/BanHelper.grxt"
