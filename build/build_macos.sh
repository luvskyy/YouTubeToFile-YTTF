#!/usr/bin/env bash
set -e
set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

section() { printf '\n== %s ==\n' "$1"; }

cd "$ROOT"

# --- venv ---
section "Setting up venv"
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
python3 -m pip install -U pip -q

# --- dependencies ---
section "Installing dependencies"
python3 -m pip install -r requirements.txt -q

# --- FFmpeg check ---
section "Checking for FFmpeg"
FFMPEG_DIR="$ROOT/assets/ffmpeg"
if [ -x "$FFMPEG_DIR/ffmpeg" ] && [ -x "$FFMPEG_DIR/ffprobe" ]; then
    echo "Bundled FFmpeg found in assets/ffmpeg"
else
    echo "WARNING: FFmpeg not found in assets/ffmpeg."
    echo "The app will fall back to system-installed FFmpeg (e.g. Homebrew)."
    echo "For a fully self-contained build, place macOS ffmpeg and ffprobe in assets/ffmpeg/"
fi

# --- PyInstaller ---
section "Building .app (PyInstaller)"
SPEC="$SCRIPT_DIR/yt_to_file_macos.spec"
pyinstaller "$SPEC" --noconfirm

if [ ! -d "$ROOT/dist/YTTF.app" ]; then
    echo "ERROR: dist/YTTF.app was not created."
    exit 1
fi
echo "Built: dist/YTTF.app"

# --- DMG ---
section "Creating .dmg"
DMG_STAGING="$ROOT/dist/dmg_staging"
DMG_OUTPUT="$ROOT/dist/YTTF.dmg"

rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "$ROOT/dist/YTTF.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

rm -f "$DMG_OUTPUT"
hdiutil create "$DMG_OUTPUT" \
    -volname "YTTF" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO

rm -rf "$DMG_STAGING"

if [ -f "$DMG_OUTPUT" ]; then
    echo "Created: dist/YTTF.dmg"
else
    echo "ERROR: DMG creation failed."
    exit 1
fi

section "Done"
echo "Output: dist/YTTF.app"
echo "Output: dist/YTTF.dmg"
