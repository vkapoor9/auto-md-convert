#!/usr/bin/env python3
"""Choose which folders the watcher converts. Nothing is watched by default.

Usage (run from anywhere):
  python3 dropzone/watch_folder.py add [PATH]     enable a folder (default: ./emails)
  python3 dropzone/watch_folder.py remove [PATH]  disable a folder
  python3 dropzone/watch_folder.py list           show watched folders

PATH resolves to an "emails" folder: a bare project path gets "/emails" appended,
a path already ending in "emails" is used as-is. Only that exact folder is watched;
subfolders and other locations keep their .eml files raw (no conversion).

After a change it restarts the watcher so it takes effect immediately.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "config.json"
LABEL = "com.automdconvert.watcher"


def load() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"watchFolders": [], "pollSeconds": 2}


def save(cfg: dict) -> None:
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def resolve_target(arg: str | None) -> Path:
    base = Path(arg).expanduser() if arg else Path.cwd()
    base = base.resolve()
    return base if base.name == "emails" else base / "emails"


def restart_watcher() -> None:
    uid = os.getuid()
    res = subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        print("Watcher restarted.")
    else:
        print("Note: could not restart the watcher automatically. It picks up the")
        print("change on next login, or run: launchctl kickstart -k gui/$(id -u)/" + LABEL)


def cmd_list() -> int:
    folders = load().get("watchFolders", [])
    if not folders:
        print("No folders are being watched. Enable one with: watch_folder.py add <path>")
        return 0
    print("Watched folders:")
    for f in folders:
        print(f"  {f}")
    return 0


def cmd_add(arg: str | None) -> int:
    target = resolve_target(arg)
    target.mkdir(parents=True, exist_ok=True)
    cfg = load()
    folders = cfg.setdefault("watchFolders", [])
    entry = str(target)
    if entry in folders:
        print(f"Already watching: {entry}")
        return 0
    folders.append(entry)
    save(cfg)
    print(f"Now watching: {entry}")
    print("Drag emails into that exact folder to auto-convert them to Markdown.")
    restart_watcher()
    return 0


def cmd_remove(arg: str | None) -> int:
    target = str(resolve_target(arg))
    cfg = load()
    folders = cfg.get("watchFolders", [])
    if target not in folders:
        print(f"Not in the watch list: {target}")
        return 0
    folders.remove(target)
    save(cfg)
    print(f"Stopped watching: {target}")
    restart_watcher()
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    action = argv[0]
    arg = argv[1] if len(argv) > 1 else None
    if action == "list":
        return cmd_list()
    if action == "add":
        return cmd_add(arg)
    if action == "remove":
        return cmd_remove(arg)
    print(f"Unknown command: {action}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
