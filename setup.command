#!/bin/bash
# Double-click this file in Finder to set up AutoMDConvert.
cd "$(dirname "$0")" || exit 1

echo "Starting AutoMDConvert setup..."
echo ""

# --- Prerequisite check: a working Python 3.9+ interpreter -------------------
PY=""
for cand in python3 python3.14 python3.13 python3.12 python3.11 python3.10 python3.9; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
      PY="$cand"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "AutoMDConvert needs Python 3.9 or newer, and it was not found on this Mac."
  echo ""
  echo "Install Python once, then double-click this file again. Any one of these works:"
  echo "  A) Download the macOS installer from https://www.python.org/downloads/"
  echo "  B) In Terminal run:  xcode-select --install   (installs Apple's python3)"
  echo "  C) With Homebrew run:  brew install python"
  echo ""
  echo "Press Return to close."
  read -r _
  exit 1
fi

echo "Using $("$PY" --version 2>&1) at $(command -v "$PY")"
echo ""
"$PY" bootstrap.py
echo ""
echo "Press Return to close."
read -r _
