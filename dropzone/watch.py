#!/usr/bin/env python3
"""Watch an opt-in list of folders for documents dropped from any app.

Only the exact folders in config.json "watchFolders" are watched. Drop a supported
file (email .eml, Word, PowerPoint, Excel, PDF, HTML, RTF, CSV, and more) into
one of them and it is converted to a clean Markdown file in the same folder, then
the original is moved into an .originals/ subfolder. Anything dropped elsewhere
(including subfolders of a watched folder) is left untouched.

Manage the list with dropzone/watch_folder.py. Runs as a login LaunchAgent installed
by bootstrap.py, or manually: python3 dropzone/watch.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.convert import core  # noqa: E402

ARCHIVE_DIRNAME = ".originals"


def _log(msg: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def _candidate_dirs(cfg: dict) -> list[Path]:
    dirs: list[Path] = []
    for entry in cfg.get("watchFolders", []):
        d = Path(entry).expanduser()
        if d.is_dir():
            dirs.append(d)
    return dirs


def _convert(src: Path, cfg: dict) -> None:
    try:
        meta, body = core.convert_file(src)
    except Exception as exc:  # keep the watcher alive on a bad file
        _log(f"skip ({src.suffix or 'file'}) {src.name}: {exc}")
        return
    target = core.write_markdown(src.parent, meta, body)
    archive = src.parent / ARCHIVE_DIRNAME
    archive.mkdir(exist_ok=True)
    try:
        src.replace(archive / src.name)
    except OSError:
        pass
    _log(f"captured {target}")


def _scan_once(cfg: dict, seen: set[Path]) -> None:
    for directory in _candidate_dirs(cfg):
        try:
            entries = [
                p for p in directory.iterdir()
                if p.is_file() and not p.name.startswith(".") and core.is_supported(p)
            ]
        except OSError:
            continue
        for src in entries:
            if ARCHIVE_DIRNAME in src.parts:
                continue
            # Wait until the file stops growing (apps write it progressively).
            try:
                size = src.stat().st_size
            except OSError:
                continue
            key = src.resolve()
            if key in seen:
                continue
            time.sleep(0.4)
            try:
                if src.stat().st_size != size:
                    continue  # still being written; pick it up next pass
            except OSError:
                continue
            seen.add(key)
            _convert(src, cfg)


def main() -> int:
    cfg = core.load_config()
    run_once = "--once" in sys.argv[1:]
    seen: set[Path] = set()
    if run_once:
        _scan_once(cfg, seen)
        return 0
    folders = _candidate_dirs(cfg)
    if folders:
        _log(f"watching {len(folders)} folder(s): " + ", ".join(str(f) for f in folders))
    else:
        _log("no watchFolders configured; nothing is being watched (add one with watch_folder.py)")
    poll = max(1, int(cfg.get("pollSeconds", 2)))
    while True:
        try:
            _scan_once(cfg, seen)
        except Exception as exc:  # never let a transient error kill the loop
            _log(f"scan error: {exc}")
        time.sleep(poll)


if __name__ == "__main__":
    raise SystemExit(main())
