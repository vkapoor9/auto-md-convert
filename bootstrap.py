#!/usr/bin/env python3
"""One-shot setup for AutoMDConvert.

Run this once (double-click setup.command, or `python3 bootstrap.py`). It:
  1. optionally enables a first folder to watch,
  2. writes config.json,
  3. installs the background drop-zone watcher (a login LaunchAgent),
  4. runs a smoke test and opens VS Code.

The watcher only converts files dropped into folders you pick (see
dropzone/watch_folder.py). It handles email (.eml), Word, PowerPoint, Excel, PDF,
HTML, RTF, CSV, and more. Drop a file anywhere else to leave it untouched.

Environment overrides used only for testing (leave unset for a normal install):
  AUTOMDCONVERT_LAUNCHAGENTS_DIR, AUTOMDCONVERT_SKIP_LOAD, AUTOMDCONVERT_SKIP_PIP,
  AUTOMDCONVERT_SKIP_OPEN, AUTOMDCONVERT_ANSWERS (newline-joined for non-interactive runs).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
HOME = Path.home()


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

_C = {"b": "\033[1m", "g": "\033[32m", "y": "\033[33m", "r": "\033[31m", "0": "\033[0m"}


def say(msg: str, color: str = "0") -> None:
    print(f"{_C.get(color, '')}{msg}{_C['0']}")


def step(msg: str) -> None:
    print(f"\n{_C['b']}==>{_C['0']} {msg}")


_answers_iter = None


def ask(prompt: str, default: str) -> str:
    """Prompt with a default. Supports AUTOMDCONVERT_ANSWERS for non-interactive runs."""
    global _answers_iter
    if _answers_iter is None:
        preset = os.environ.get("AUTOMDCONVERT_ANSWERS")
        _answers_iter = iter(preset.split("\n")) if preset is not None else iter(())
    canned = next(_answers_iter, None)
    if canned is not None:
        value = canned.strip() or default
        say(f"{prompt} [{default}]: {value}", "y")
        return value
    try:
        entered = input(f"{prompt} [{default}]: ").strip()
    except EOFError:
        entered = ""
    return entered or default


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# --------------------------------------------------------------------------- #
# LaunchAgents
# --------------------------------------------------------------------------- #

def launchagents_dir() -> Path:
    return Path(os.environ.get("AUTOMDCONVERT_LAUNCHAGENTS_DIR", str(HOME / "Library" / "LaunchAgents")))


def write_launch_agent(label: str, program_args: list[str], log_path: Path) -> Path:
    d = launchagents_dir()
    d.mkdir(parents=True, exist_ok=True)
    args_xml = "".join(f"      <string>{a}</string>\n" for a in program_args)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{args_xml}    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>{log_path}</string>
    <key>StandardErrorPath</key><string>{log_path}</string>
</dict>
</plist>
"""
    target = d / f"{label}.plist"
    target.write_text(plist, encoding="utf-8")
    return target


def load_launch_agent(plist: Path, label: str) -> bool:
    if os.environ.get("AUTOMDCONVERT_SKIP_LOAD"):
        say(f"   (skipped launchctl load for {label})", "y")
        return True
    uid = os.getuid()
    run(["launchctl", "bootout", f"gui/{uid}/{label}"])  # ignore result
    res = run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)])
    if res.returncode != 0:
        res = run(["launchctl", "load", "-w", str(plist)])
    return res.returncode == 0


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    say(f"\n{_C['b']}AutoMDConvert setup{_C['0']}")
    say("Converts documents you drop into folders you choose into Markdown for your agent.\n")

    # Preserve any folders already configured (safe to re-run setup, e.g. after a rename).
    existing: dict = {}
    try:
        existing = json.loads((REPO / "config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing = {}
    watch_folders: list[str] = list(existing.get("watchFolders", []))

    step("Choosing a first folder to watch (optional)")
    if watch_folders:
        say(f"Keeping {len(watch_folders)} folder(s) already configured.", "g")
    say("Enter a project (its emails/ folder is watched), or leave blank to add later.")
    first = ask("Project or emails folder to watch (blank to skip)", "")
    if first.strip():
        target = Path(first).expanduser().resolve()
        if target.name != "emails":
            target = target / "emails"
        target.mkdir(parents=True, exist_ok=True)
        if str(target) not in watch_folders:
            watch_folders.append(str(target))

    # 1. config.json
    step("Writing config.json")
    config = {
        "watchFolders": watch_folders,
        "pollSeconds": existing.get("pollSeconds", 2),
    }
    (REPO / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (REPO / "logs").mkdir(exist_ok=True)
    if watch_folders:
        say(f"   watching {watch_folders[0]}", "g")
    else:
        say("   no folders watched yet (add with dropzone/watch_folder.py add <path>)", "y")

    # 2. optional converters (markitdown adds PDF/PPTX/XLSX; textutil covers the rest)
    step("Installing optional converters (markitdown for PDF/Office, html2text)")
    if os.environ.get("AUTOMDCONVERT_SKIP_PIP"):
        say("   (skipped pip install)", "y")
    else:
        res = run([sys.executable, "-m", "pip", "install", "--user", "--quiet",
                   "markitdown[docx,pptx,xlsx,pdf]", "html2text"])
        if res.returncode == 0:
            say("   installed markitdown + html2text (full format support)", "g")
        else:
            say("   markitdown not installed; Word/RTF/HTML/eml/txt/csv still work via built-ins", "y")
            say("   for PDF/PPTX/XLSX, install markitdown (see README)", "y")

    # 3. drop-zone watcher LaunchAgent
    step("Installing the drop-zone watcher (auto-start at login)")
    watcher_plist = write_launch_agent(
        "com.automdconvert.watcher",
        [sys.executable, str(REPO / "dropzone" / "watch.py")],
        REPO / "logs" / "watcher.log",
    )
    ok = load_launch_agent(watcher_plist, "com.automdconvert.watcher")
    say("   watcher running" if ok else "   watcher installed (load it with: launchctl load -w " + str(watcher_plist) + ")",
        "g" if ok else "y")

    # 4. smoke test
    step("Smoke test: converting a sample email")
    smoke_test()

    # 5. open VS Code
    code = shutil.which("code")
    if code and not os.environ.get("AUTOMDCONVERT_SKIP_OPEN"):
        run([code, str(REPO)])

    print_summary(config)
    return 0


def smoke_test() -> None:
    import tempfile

    sys.path.insert(0, str(REPO))
    from shared.convert import core

    with tempfile.TemporaryDirectory() as td:
        sample = Path(td) / "welcome.txt"
        sample.write_text(
            "Drop a document into a watched folder and it becomes Markdown like this.\n",
            encoding="utf-8",
        )
        meta, body = core.convert_file(sample)
        target = core.write_markdown(Path(td), meta, body)
        ok = target.exists()
    say("   converter works" if ok else "   smoke test failed", "g" if ok else "r")


def print_summary(config: dict) -> None:
    print(f"\n{_C['g']}{_C['b']}Setup complete.{_C['0']}\n")
    folders = config.get("watchFolders", [])
    wf = REPO / "dropzone" / "watch_folder.py"
    if folders:
        say("Watching (emails dropped here auto-convert to Markdown):")
        for f in folders:
            say(f"  {f}")
    else:
        say("No folders are watched yet. Enable one when ready:")
        say(f"  python3 {wf} add <project-path>", "b")
    say("\nHow it works:")
    say("  Drag an email into a watched folder and it becomes a clean Markdown file.")
    say("  Drop a .eml anywhere else, or in a subfolder, to keep it as a raw .eml.")
    say(f"\nManage folders: python3 {wf} list | add <path> | remove <path>")


if __name__ == "__main__":
    raise SystemExit(main())
