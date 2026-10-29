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

import argparse
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


def _signature(src: Path) -> tuple[int, int, int, int]:
    stat = src.lstat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _convert(src: Path, cfg: dict) -> bool:
    target = None
    try:
        before = _signature(src)
        meta, body = core.convert_file(src)
        if src.is_symlink() or _signature(src) != before:
            raise OSError("source changed during conversion; will retry")
        archive = src.parent / ARCHIVE_DIRNAME
        if archive.is_symlink():
            raise OSError("archive directory must not be a symlink")
        archive.mkdir(exist_ok=True)
        target = core.write_markdown(src.parent, meta, body)
        if src.is_symlink() or _signature(src) != before:
            raise OSError("source changed before archiving; will retry")
        archived = core.publish_unique_file(src, archive / src.name)
        try:
            if src.is_symlink() or _signature(src) != before:
                raise OSError("source changed while archiving; will retry")
            src.unlink()
        except BaseException:
            archived.unlink()
            raise
    except Exception as exc:  # keep the watcher alive on a bad file
        if target is not None:
            try:
                target.unlink()
            except OSError as cleanup:
                _log(f"could not remove incomplete conversion {target}: {cleanup}")
        _log(f"retry ({src.suffix or 'file'}) {src.name}: {exc}")
        return False
    _log(f"captured {target}")
    return True


def _scan_once(cfg: dict, seen: set[Path]) -> bool:
    seen.clear()
    ok = True
    for directory in _candidate_dirs(cfg):
        try:
            entries = [
                p for p in directory.iterdir()
                if not p.is_symlink() and p.is_file() and
                not p.name.startswith(".") and core.is_supported(p)
            ]
        except OSError as exc:
            _log(f"cannot scan {directory}: {exc}")
            ok = False
            continue
        for src in entries:
            if ARCHIVE_DIRNAME in src.parts:
                continue
            # Wait until the file stops growing (apps write it progressively).
            try:
                before = _signature(src)
            except OSError:
                continue
            key = src.resolve()
            if key in seen:
                continue
            time.sleep(0.4)
            try:
                if src.is_symlink() or _signature(src) != before:
                    continue  # still being written; pick it up next pass
            except OSError:
                continue
            seen.add(key)
            if not _convert(src, cfg):
                ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="scan once, then exit")
    args = parser.parse_args()
    try:
        cfg = core.load_config()
    except ValueError as exc:
        _log(str(exc))
        return 1
    seen: set[Path] = set()
    if args.once:
        return 0 if _scan_once(cfg, seen) else 1
    folders = _candidate_dirs(cfg)
    if folders:
        _log(f"watching {len(folders)} folder(s): " + ", ".join(str(f) for f in folders))
    else:
        _log("no watchFolders configured; nothing is being watched (add one with watch_folder.py)")
    poll = cfg["pollSeconds"]
    while True:
        try:
            _scan_once(cfg, seen)
        except Exception as exc:  # never let a transient error kill the loop
            _log(f"scan error: {exc}")
        # Bound each sleep so large, valid JSON numbers cannot overflow time.sleep.
        remaining = poll
        while remaining > 0:
            interval = min(remaining, 3600)
            time.sleep(interval)
            remaining -= interval


if __name__ == "__main__":
    raise SystemExit(main())
