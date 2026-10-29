#!/usr/bin/env python3
"""Install a Finder "Convert to Markdown" Quick Action (macOS Service).

Right-click any supported file in Finder and choose Quick Actions > Convert to
Markdown. Selected files are converted to Markdown next to the originals by
dropzone/convert_path.py, so it works anywhere, not just in watched folders.

Usage:
    python3 dropzone/install_quick_action.py            # install / update
    python3 dropzone/install_quick_action.py --uninstall
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

REPO = Path(__file__).resolve().parents[1]
SERVICE_NAME = "Convert to Markdown"
MIN_PY = (3, 9)


def services_dir() -> Path:
    # Overridable for tests; defaults to the real Services folder.
    return Path(os.environ.get("AUTOMDCONVERT_SERVICES_DIR",
                               str(Path.home() / "Library" / "Services")))


def find_python() -> str:
    """Pick a Python 3.9+ interpreter to bake into the action."""
    for cand in (str(REPO / ".venv" / "bin" / "python3"), sys.executable,
                 "python3", "python3.14", "python3.13",
                 "python3.12", "python3.11", "python3.10", "python3.9"):
        exe = shutil.which(cand) if not cand.startswith("/") else cand
        if not exe or not Path(exe).exists():
            continue
        try:
            r = subprocess.run(
                [exe, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"],
                capture_output=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0:
            return exe
    raise RuntimeError("No working Python 3.9+ interpreter found.")


def _info_plist() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>NSServices</key>
	<array>
		<dict>
			<key>NSBackgroundColorName</key>
			<string>background</string>
			<key>NSIconName</key>
			<string>NSActionTemplate</string>
			<key>NSMenuItem</key>
			<dict>
				<key>default</key>
				<string>{SERVICE_NAME}</string>
			</dict>
			<key>NSMessage</key>
			<string>runWorkflowAsService</string>
			<key>NSRequiredContext</key>
			<dict>
				<key>NSApplicationIdentifier</key>
				<string>com.apple.finder</string>
			</dict>
			<key>NSSendFileTypes</key>
			<array>
				<string>public.item</string>
			</array>
		</dict>
	</array>
</dict>
</plist>
"""


def _wflow(command: str) -> str:
    cmd = _xml_escape(command)
    u1, u2, u3 = (str(uuid.uuid4()).upper() for _ in range(3))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>AMApplicationBuild</key>
	<string>521</string>
	<key>AMApplicationVersion</key>
	<string>2.10</string>
	<key>AMDocumentVersion</key>
	<string>2</string>
	<key>actions</key>
	<array>
		<dict>
			<key>action</key>
			<dict>
				<key>AMAccepts</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Optional</key>
					<false/>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.path</string>
					</array>
				</dict>
				<key>AMActionVersion</key>
				<string>2.0.3</string>
				<key>AMApplication</key>
				<array>
					<string>Automator</string>
				</array>
				<key>AMParameterProperties</key>
				<dict>
					<key>COMMAND_STRING</key>
					<dict/>
					<key>CheckedForUserDefaultShell</key>
					<dict/>
					<key>inputMethod</key>
					<dict/>
					<key>shell</key>
					<dict/>
					<key>source</key>
					<dict/>
				</dict>
				<key>AMProvides</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.path</string>
					</array>
				</dict>
				<key>ActionBundlePath</key>
				<string>/System/Library/Automator/Run Shell Script.action</string>
				<key>ActionName</key>
				<string>Run Shell Script</string>
				<key>ActionParameters</key>
				<dict>
					<key>COMMAND_STRING</key>
					<string>{cmd}</string>
					<key>CheckedForUserDefaultShell</key>
					<true/>
					<key>inputMethod</key>
					<integer>1</integer>
					<key>shell</key>
					<string>/bin/zsh</string>
					<key>source</key>
					<string></string>
				</dict>
				<key>BundleIdentifier</key>
				<string>com.apple.RunShellScript</string>
				<key>CFBundleVersion</key>
				<string>2.0.3</string>
				<key>CanShowSelectedItemsWhenRun</key>
				<false/>
				<key>CanShowWhenRun</key>
				<true/>
				<key>Category</key>
				<array>
					<string>AMCategoryUtilities</string>
				</array>
				<key>Class Name</key>
				<string>RunShellScriptAction</string>
				<key>InputUUID</key>
				<string>{u1}</string>
				<key>Keywords</key>
				<array>
					<string>Shell</string>
					<string>Script</string>
					<string>Command</string>
					<string>Run</string>
					<string>Unix</string>
				</array>
				<key>OutputUUID</key>
				<string>{u2}</string>
				<key>UUID</key>
				<string>{u3}</string>
				<key>UnlocalizedApplications</key>
				<array>
					<string>Automator</string>
				</array>
				<key>arguments</key>
				<dict>
					<key>0</key>
					<dict>
						<key>default value</key>
						<integer>0</integer>
						<key>name</key>
						<string>inputMethod</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>0</string>
					</dict>
					<key>1</key>
					<dict>
						<key>default value</key>
						<false/>
						<key>name</key>
						<string>CheckedForUserDefaultShell</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>1</string>
					</dict>
					<key>2</key>
					<dict>
						<key>default value</key>
						<string></string>
						<key>name</key>
						<string>source</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>2</string>
					</dict>
					<key>3</key>
					<dict>
						<key>default value</key>
						<string></string>
						<key>name</key>
						<string>COMMAND_STRING</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>3</string>
					</dict>
					<key>4</key>
					<dict>
						<key>default value</key>
						<string>/bin/sh</string>
						<key>name</key>
						<string>shell</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>4</string>
					</dict>
				</dict>
				<key>isViewVisible</key>
				<integer>1</integer>
				<key>location</key>
				<string>309.000000:253.000000</string>
				<key>nibPath</key>
				<string>/System/Library/Automator/Run Shell Script.action/Contents/Resources/main.nib</string>
			</dict>
			<key>isViewVisible</key>
			<integer>1</integer>
		</dict>
	</array>
	<key>connectors</key>
	<dict/>
	<key>workflowMetaData</key>
	<dict>
		<key>serviceApplicationBundleID</key>
		<string>com.apple.finder</string>
		<key>serviceApplicationPath</key>
		<string>/System/Library/CoreServices/Finder.app</string>
		<key>serviceInputTypeIdentifier</key>
		<string>com.apple.Automator.fileSystemObject</string>
		<key>serviceOutputTypeIdentifier</key>
		<string>com.apple.Automator.nothing</string>
		<key>serviceProcessesInput</key>
		<integer>0</integer>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
"""


def bundle_path() -> Path:
    return services_dir() / f"{SERVICE_NAME}.workflow"


def _refresh_services() -> None:
    try:
        result = subprocess.run(["/System/Library/CoreServices/pbs", "-flush"],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            print(f"Could not refresh Quick Actions: {result.stderr.strip()}", file=sys.stderr)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Could not refresh Quick Actions: {exc}", file=sys.stderr)


def install(python: str | None = None) -> bool:
    py = python or find_python()
    command = shlex.join([py, str(REPO / "dropzone" / "convert_path.py")]) + ' "$@"'

    bundle = bundle_path()
    contents = bundle / "Contents"
    contents.mkdir(parents=True, exist_ok=True)
    info = contents / "Info.plist"
    wflow = contents / "document.wflow"
    info.write_text(_info_plist(), encoding="utf-8")
    wflow.write_text(_wflow(command), encoding="utf-8")

    ok = True
    for p in (info, wflow):
        r = subprocess.run(["plutil", "-lint", str(p)], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"plist lint failed for {p.name}: {r.stdout.strip() or r.stderr.strip()}",
                  file=sys.stderr)
            ok = False

    if ok:
        _refresh_services()
    return ok


def uninstall() -> bool:
    bundle = bundle_path()
    try:
        if bundle.is_symlink():
            bundle.unlink()
        elif bundle.exists():
            shutil.rmtree(bundle)
    except OSError as exc:
        print(f"Could not remove Quick Action: {exc}", file=sys.stderr)
        return False
    _refresh_services()
    return True


def main(argv: list[str]) -> int:
    if argv in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    if argv and argv != ["--uninstall"]:
        print("Usage: install_quick_action.py [--uninstall]", file=sys.stderr)
        return 1
    if argv == ["--uninstall"]:
        if uninstall():
            print(f"Removed the '{SERVICE_NAME}' Quick Action.")
            return 0
        return 1
    try:
        ok = install()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Could not install Quick Action: {exc}", file=sys.stderr)
        return 1
    if ok:
        print(f"Installed the '{SERVICE_NAME}' Quick Action.")
        print("To use it: right-click a supported file in Finder, open the Quick Actions submenu.")
        print("If you do not see it, click Quick Actions > Customize... and turn on")
        print("'Convert to Markdown' (recent macOS hides new Quick Actions until you enable them).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
