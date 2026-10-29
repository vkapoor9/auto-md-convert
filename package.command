#!/bin/bash
# Double-click this file in Finder to build a zip of AutoMDConvert for another Mac.
# Output: ~/Desktop/auto-md-convert-YYYY-MM-DD.zip
set -euo pipefail
cd "$(dirname "$0")" || exit 1

NAME="auto-md-convert"
STAMP="$(date +%Y-%m-%d)"
OUT="$HOME/Desktop/${NAME}-${STAMP}.zip"
TEMP="$(mktemp -d)"
STAGE="${TEMP}/${NAME}"
cleanup() {
  rm -r -- "$TEMP"
}
trap cleanup EXIT

echo "Building ${NAME} package..."

# Everything the other Mac needs; local state and personal notes are left behind.
mkdir -p "$STAGE/shared/convert" "$STAGE/dropzone"
cp README.md bootstrap.py config.example.json handoff-prompt.md \
  setup.command package.command shortcuts.zsh splash.py "$STAGE/"
cp shared/convert/__init__.py shared/convert/core.py "$STAGE/shared/convert/"
cp dropzone/convert_path.py dropzone/install_quick_action.py \
  dropzone/watch.py dropzone/watch_folder.py "$STAGE/dropzone/"
cp .gitignore "$STAGE/"

chmod +x "$STAGE/setup.command" "$STAGE/package.command"

mkdir -p "$HOME/Desktop"
ditto -c -k --sequesterRsrc --keepParent "$STAGE" "$TEMP/package.zip"
mv -f "$TEMP/package.zip" "$OUT"

echo ""
echo "Package ready: $OUT"
echo ""
echo "On the other Mac:"
echo "  1. Copy the zip over (AirDrop, iCloud Drive, USB) and unzip it."
echo "  2. Move the ${NAME} folder where you want it to live, e.g. ~/ai/${NAME}."
echo "  3. Right-click setup.command > Open (first launch only, to clear Gatekeeper)."
echo "  4. When asked, type a folder to watch, or press Return to skip."
echo ""
if [ -t 0 ]; then
  echo "Press Return to close."
  read -r _
fi
