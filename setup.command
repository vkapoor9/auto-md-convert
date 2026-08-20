#!/bin/bash
# Double-click this file in Finder to set up AutoMDConvert.
cd "$(dirname "$0")" || exit 1
echo "Starting AutoMDConvert setup..."
python3 bootstrap.py
echo ""
echo "Press Return to close."
read -r _
