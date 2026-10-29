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
  AUTOMDCONVERT_SKIP_OPEN, AUTOMDCONVERT_SKIP_QUICKACTION,
  AUTOMDCONVERT_ANSWERS (newline-joined for non-interactive runs).
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from shared.convert import core

REPO = Path(__file__).resolve().parent
HOME = Path.home()
MIN_PY = (3, 9)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

_C = {"b": "\033[1m", "g": "\033[32m", "y": "\033[33m", "r": "\033[31m", "0": "\033[0m"}


def say(msg: str, color: str = "0") -> None:
    print(f"{_C.get(color, '')}{msg}{_C['0']}")


def step(msg: str) -> None:
    print(f"\n{_C['b']}==>{_C['0']} {msg}")


def splash() -> None:
    """Print the startup banner + VK credit (shared, portable splash.py)."""
    if os.environ.get("SPLASH_OFF"):
        return
    try:
        sys.path.insert(0, str(REPO))
        from splash import render
        render()
    except ImportError as exc:
        say(f"   could not load startup banner: {exc}", "y")


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
    kw.setdefault("timeout", 600)
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def module_available(name: str, python: str | None = None) -> bool:
    """Check that a converter imports in the interpreter used by the watcher."""
    res = run([python or sys.executable, "-c",
               "import importlib, sys; importlib.import_module(sys.argv[1])", name])
    return res.returncode == 0


# --------------------------------------------------------------------------- #
# LaunchAgents
# --------------------------------------------------------------------------- #

def launchagents_dir() -> Path:
    return Path(os.environ.get("AUTOMDCONVERT_LAUNCHAGENTS_DIR", str(HOME / "Library" / "LaunchAgents")))


def write_launch_agent(label: str, program_args: list[str], log_path: Path) -> Path:
    d = launchagents_dir()
    d.mkdir(parents=True, exist_ok=True)
    target = d / f"{label}.plist"
    target.write_bytes(plistlib.dumps({
        "Label": label,
        "ProgramArguments": program_args,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }))
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
    if res.returncode:
        say(f"   launchctl failed: {res.stderr.strip() or res.stdout.strip()}", "r")
    return res.returncode == 0


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    try:
        return _main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        say(f"Setup failed: {exc}", "r")
        return 1


def _main() -> int:
    splash()
    say("Converts documents you drop into folders you choose into Markdown for your agent.\n")

    if sys.version_info < MIN_PY:
        have = f"{sys.version_info.major}.{sys.version_info.minor}"
        say(f"This needs Python {MIN_PY[0]}.{MIN_PY[1]} or newer, but setup is running on Python {have}.", "r")
        say("Install a newer Python, then run setup again:", "y")
        say("  https://www.python.org/downloads/   (or: brew install python)", "b")
        return 1

    # Preserve any folders already configured (safe to re-run setup, e.g. after a rename).
    existing = core.load_config(REPO / "config.json")
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
    config = {**existing, "watchFolders": watch_folders}
    core.save_config(config, REPO / "config.json")
    (REPO / "logs").mkdir(exist_ok=True)
    if watch_folders:
        say(f"   watching {watch_folders[0]}", "g")
    else:
        say("   no folders watched yet (add with dropzone/watch_folder.py add <path>)", "y")

    # 2. optional converters (markitdown adds PDF/PPTX/XLSX/XLS; textutil covers the rest)
    step("Installing optional converters (markitdown for PDF/Office, html2text)")
    python = sys.executable
    setup_ok = True
    if os.environ.get("AUTOMDCONVERT_SKIP_PIP"):
        say("   (skipped pip install)", "y")
    else:
        env = REPO / ".venv"
        env_python = env / "bin" / "python3"
        if env.is_symlink():
            raise ValueError("The project .venv must not be a symlink.")
        if not env_python.exists():
            result = run([sys.executable, "-m", "venv", str(env)])
            if result.returncode:
                say(f"   could not create converter environment: {result.stderr.strip()}", "r")
                return 1
        version_check = run([str(env_python), "-c",
                             "import sys; print('%s.%s' % sys.version_info[:2])"])
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        if version_check.returncode or version_check.stdout.strip() != version:
            say("   .venv uses a different or unavailable Python version.", "r")
            say(f"   Recreate it with this Python, then rerun setup:", "y")
            say(f'     "{sys.executable}" -m venv --clear "{env}"', "b")
            return 1
        python = str(env_python)
        pkgs = ["html2text", "ebooklib", "openpyxl"]
        if sys.version_info >= (3, 10):
            pkgs.append("markitdown[docx,pptx,xlsx,xls,pdf]")
        else:
            say("   markitdown requires Python 3.10+; basic formats will still work.", "y")
        r = run([python, "-m", "pip", "install", "--quiet", *pkgs])
        if r.returncode:
            setup_ok = False
            say(f"   converter installation failed: {r.stderr.strip() or r.stdout.strip()}", "r")
    # Report the real capability, regardless of how the install went.
    have_markitdown = module_available("markitdown", python)
    if have_markitdown:
        say("   markitdown is available (format support depends on installed extras).", "g")
    else:
        say("   Email, Word, RTF, HTML, and text/csv/json convert out of the box.", "y")
        say("   PDF, PowerPoint, legacy Excel, and EPUB need markitdown, which is not available yet.", "y")
        say("   XLSX uses openpyxl separately.", "y")
        say("   To enable them later, run:", "y")
        say("     rerun setup with Python 3.10 or newer", "b")

    # 3. drop-zone watcher LaunchAgent
    step("Installing the drop-zone watcher (auto-start at login)")
    watcher_plist = write_launch_agent(
        "com.automdconvert.watcher",
        [python, str(REPO / "dropzone" / "watch.py")],
        REPO / "logs" / "watcher.log",
    )
    ok = load_launch_agent(watcher_plist, "com.automdconvert.watcher")
    setup_ok = setup_ok and ok
    say("   watcher running" if ok else "   watcher installed (load it with: launchctl load -w " + str(watcher_plist) + ")",
        "g" if ok else "y")

    # 3b. Finder Quick Action (right-click any file > Convert to Markdown)
    step("Installing the Finder Quick Action (right-click > Convert to Markdown)")
    if os.environ.get("AUTOMDCONVERT_SKIP_QUICKACTION"):
        say("   (skipped Quick Action install)", "y")
    else:
        try:
            sys.path.insert(0, str(REPO / "dropzone"))
            import install_quick_action as qa
            if qa.install(python=python):
                say("   installed. Right-click a file in Finder > Quick Actions.", "g")
                say("   First time only: Quick Actions > Customize... and turn on 'Convert to Markdown'.", "y")
            else:
                setup_ok = False
                say("   Quick Action written, but plist validation flagged an issue (see above)", "y")
        except Exception as exc:
            setup_ok = False
            say(f"   could not install Quick Action: {exc}", "y")

    # 4. smoke test
    step("Smoke test: converting a sample document")
    smoke_test()

    # 5. open VS Code
    code = shutil.which("code")
    if code and not os.environ.get("AUTOMDCONVERT_SKIP_OPEN"):
        run([code, str(REPO)])

    if setup_ok:
        print_summary(config, have_markitdown)
    else:
        say("Setup incomplete; fix the errors above and rerun setup.", "r")
    return 0 if setup_ok else 1


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
    if not ok:
        raise ValueError("smoke test did not produce Markdown")
    say("   converter works", "g")


def print_summary(config: dict, have_markitdown: bool = True) -> None:
    print(f"\n{_C['g']}{_C['b']}Setup complete.{_C['0']}\n")
    folders = config.get("watchFolders", [])
    wf = REPO / "dropzone" / "watch_folder.py"
    if have_markitdown:
        say("Formats: email, Word, PowerPoint, Excel, PDF, HTML, RTF, CSV, and more.")
    else:
        say("Formats: email, Word, RTF, HTML, text/csv/json; optional formats depend on installed converters.", "y")
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
    say("  Or right-click a file in Finder > Quick Actions (first time: Quick Actions > Customize to enable).")
    say(f"\nManage folders: python3 {wf} list | add <path> | remove <path>")


if __name__ == "__main__":
    raise SystemExit(main())
