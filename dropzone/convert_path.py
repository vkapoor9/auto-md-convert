#!/usr/bin/env python3
"""Convert one or more files to Markdown in place, next to each original.

Used by the Finder "Convert to Markdown" Quick Action, and handy on its own:

    python3 dropzone/convert_path.py ~/Desktop/report.pdf notes.docx

For each supported file it writes `<name>.md` in the same folder and leaves the
original untouched (unlike the watcher, which archives originals). Unsupported files
are skipped. A macOS notification summarizes the result.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.convert import core  # noqa: E402


def _notify(title: str, message: str) -> None:
    # Best effort; keep to controlled text (no filenames) so quoting stays safe.
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _reveal(path: Path) -> None:
    try:
        subprocess.run(
            ["open", "-R", str(path)],
            capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def convert_one(src: Path) -> Path | None:
    """Convert a single file to Markdown beside it. Returns the .md path or None."""
    if not src.exists():
        raise FileNotFoundError(f"file does not exist: {src}")
    if not src.is_file() or not core.is_supported(src):
        return None
    meta, body = core.convert_file(src)
    meta["source"] = "quick-action"
    return core.write_unique_text(src.with_suffix(".md"), core.render_markdown(meta, body))


def main(argv: list[str]) -> int:
    if not argv or argv == ["--help"] or argv == ["-h"]:
        print(__doc__)
        return 0 if argv else 1
    paths = [Path(a).expanduser() for a in argv]
    converted: list[Path] = []
    skipped = 0
    errors = 0

    for src in paths:
        try:
            out = convert_one(src)
        except Exception as exc:
            errors += 1
            print(f"error: {src.name}: {exc}", file=sys.stderr)
            continue
        if out is None:
            skipped += 1
            print(f"skip (unsupported): {src.name}", file=sys.stderr)
        else:
            converted.append(out)
            print(f"converted: {out}")

    n = len(converted)
    if n:
        parts = [f"Converted {n} file{'s' if n != 1 else ''} to Markdown"]
        extra = []
        if skipped:
            extra.append(f"{skipped} skipped")
        if errors:
            extra.append(f"{errors} failed")
        if extra:
            parts.append("(" + ", ".join(extra) + ")")
        _notify("AutoMDConvert", " ".join(parts))
        if n == 1:
            _reveal(converted[0])
        return 1 if errors else 0

    if errors:
        _notify("AutoMDConvert", f"Could not convert {errors} file{'s' if errors != 1 else ''}")
        return 1
    _notify("AutoMDConvert", "Nothing to convert (unsupported file type)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
