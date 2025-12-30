#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PY="${PYTHON:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PY" ]]; then
  echo "[build_desktop_app] ERROR: Python not found at $PY" >&2
  echo "[build_desktop_app] Tip: create venv at .venv and install deps." >&2
  exit 2
fi

"$PY" -m pip install -r requirements.txt -r requirements_desktop.txt -r requirements_packaging.txt

# Build a double-clickable macOS app bundle.
"$PY" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name AutoBlogDesktop \
  run_desktop.py

APP_DIR="$ROOT_DIR/dist/AutoBlogDesktop.app"

# Produce a standard DMG for easiest end-user install flow.
DMG_OUT="$ROOT_DIR/dist/AutoBlogDesktop-macos.dmg"
rm -f "$DMG_OUT"
if command -v hdiutil >/dev/null 2>&1; then
  hdiutil create \
    -volname "AutoBlogDesktop" \
    -srcfolder "$APP_DIR" \
    -ov \
    -format UDZO \
    "$DMG_OUT" >/dev/null
  echo "[build_desktop_app] OK: dist/AutoBlogDesktop-macos.dmg"
else
  echo "[build_desktop_app] WARN: hdiutil not found; DMG not created" >&2
fi

echo "[build_desktop_app] OK: dist/AutoBlogDesktop.app"
