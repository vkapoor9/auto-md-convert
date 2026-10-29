# AutoMDConvert

Turn documents into clean Markdown automatically, so a coding agent working in a
project can read them for strategy, decisions, and task tracking. It handles most
common file types: email, Word, PowerPoint, Excel, PDF, HTML, RTF, CSV, and more.

You pick which folders to watch. Drag a file into a watched folder and a background
watcher turns it into a readable `.md` file. Drop a file anywhere else and it stays
untouched. That is the whole tool.

## Requirements

You only need two things before you start. Setup handles everything else.

| Prerequisite | Needed for | How to get it |
|---|---|---|
| macOS | The watcher runs as a login LaunchAgent and uses `textutil` | Already on your Mac |
| Python 3.9 or newer; 3.10+ for all formats | Running setup and the watcher; `markitdown` requires 3.10+ | Installer at https://www.python.org/downloads/, or `xcode-select --install`, or `brew install python` |

Check what you have with `python3 --version`. If it prints 3.9 or higher, you are
ready. If Python is missing or too old, `setup.command` detects it and tells you
exactly what to install before it does anything else.

Setup installs optional converters in a project-local `.venv`, without modifying
system Python or bypassing Homebrew's package protections. The watcher and Finder
Quick Action use that environment. On Python 3.9, setup installs the basic
converters but skips `markitdown`. The only thing setup asks you is which folder to
watch, and even that is optional. Installation failures are reported with a nonzero
exit code; rerunning setup preserves your configuration.

## Why it works this way

The unit of input is a file you drag out of any app. A single background watcher
converts each dropped file to Markdown in place, so the same gesture works for
email, Word, PDF, and everything else. No app scripting or plugins required.

## Quick start

1. Confirm Python 3.9+ is installed (`python3 --version`); use 3.10+ for all formats.
2. Double-click `setup.command` (or run `python3 bootstrap.py`).
3. When asked, type a folder to watch, or press Return to skip and add one later.

That is it. Setup installs the converters, installs a background watcher that
auto-starts at login, runs a smoke test, and opens VS Code. Nothing is watched
until you choose a folder.

If Python is missing, `setup.command` stops with clear install instructions instead
of failing part way. Email, Word, RTF, HTML, and text/csv/json convert with zero
extra installs; XLSX uses `openpyxl`, while PDF, PowerPoint, legacy Excel, and EPUB
need optional converters (setup installs them and reports failures).

## Install on another Mac

Double-click `package.command` (or run `./package.command`). It writes
`~/Desktop/auto-md-convert-YYYY-MM-DD.zip` containing just the tool — your
`config.json`, logs, virtual environments, and notes stay on this Mac. Packaging
uses an explicit list of runtime files, so unrelated files in the repository are
never included. It also runs non-interactively.

On the other Mac:

1. Copy the zip over (AirDrop, iCloud Drive, USB) and unzip it.
2. Move the `auto-md-convert` folder where you want it to live, e.g. `~/ai/auto-md-convert`.
3. Right-click `setup.command` and choose **Open** (first launch only, so Gatekeeper
   allows a downloaded script), then confirm.
4. When asked, type a folder to watch, or press Return to skip.

Setup is per-machine: it installs the converters, the login watcher, and the Finder
Quick Action there, and writes a fresh `config.json`. Watched folder paths are
absolute, so add the folders that exist on that Mac with
`python3 dropzone/watch_folder.py add <path>`.

## Choosing which folders to watch

The watcher only converts files in folders you explicitly enable. Manage the list
with `dropzone/watch_folder.py`:

```
python3 dropzone/watch_folder.py add ~/ai/my-project   # watch my-project/emails
python3 dropzone/watch_folder.py list                  # show watched folders
python3 dropzone/watch_folder.py remove ~/ai/my-project
```

`add` appends `/emails` to a project path (or takes an exact `.../emails` path),
creates the folder, and restarts the watcher so it takes effect right away.

### Shell shortcuts

Add this line to your `~/.zshrc` (use your clone path) to get short commands from
any directory:

```
source /path/to/auto-md-convert/shortcuts.zsh
```

Then use:

```
add-folder ~/ai/my-project     # enable a folder
list-folder                    # show watched folders
remove-folder ~/ai/my-project  # disable a folder
```

## How to capture a file

Drag one or more files onto a watched folder, or into it via the VS Code Explorer.
The watcher converts each one into `YYYY-MM-DD--name.md` in that folder and moves
the original into `.originals/`. Existing Markdown and archived originals are never
overwritten: name collisions get a `-2`, `-3`, etc. suffix, including repeated drops
of the same filename.

Files that change while being read are left for a later scan. Failed conversions
retain the source and are retried on subsequent scans; errors appear in
`logs/watcher.log`. Hidden files, file symlinks, and subfolders are not processed.
The archive directory must not be a symlink. Where the filesystem supports hard
links, complete output is published atomically; otherwise, exclusive file creation
still prevents overwriting existing files, with partial copies removed on failure.

For an `.eml` email, the same Markdown file contains the email body followed by a
clearly separated **Attachments** section. Each attachment is converted with the
same converter used when that file type is dropped on its own. Attached `.eml`
messages and their attachments are handled recursively. If an attachment format
cannot be converted, its name and size still appear with a **Conversion unavailable**
notice; conversion of the rest of the email continues. Nested email conversion is
limited to ten levels, with a visible notice when that limit is reached.

To keep a file as-is instead, drop it into a folder that is not watched, or into a
subfolder of a watched folder (the watcher looks only at the exact watched folders,
not their subfolders).

## Convert any file from Finder (Quick Action)

Setup also installs a Finder Quick Action so you can convert files anywhere, not just
in watched folders. Right-click one or more files in Finder and choose
**Quick Actions > Convert to Markdown**. Each supported file becomes a `.md` next to
the original, and the original is left in place (unlike the watcher, which archives it).
Unsupported selections are skipped, and a notification summarizes the result.

Manage it yourself anytime:

```
python3 dropzone/install_quick_action.py             # install or update
python3 dropzone/install_quick_action.py --uninstall # remove
```

You can also convert from the command line without Finder:

```
.venv/bin/python3 dropzone/convert_path.py ~/Desktop/report.pdf notes.docx
```

Use the `.venv` interpreter for optional formats installed by setup. System
`python3` still works for built-in formats or when converters are installed there.
The CLI returns a nonzero exit code if any selected file fails, even when other
files convert successfully. Unsupported existing files are skipped.

If the menu item does not appear right after install, right-click a file, open the
Quick Actions submenu, click **Customize...**, and turn on **Convert to Markdown**.
Recent macOS hides newly installed Quick Actions until you enable them there once.
(You can also toggle it under System Settings > Keyboard > Keyboard Shortcuts >
Services > Files and Folders.)

## Supported formats

- Email: `.eml`
- Word and rich text: `.docx`, `.doc`, `.rtf`, `.odt`
- PowerPoint: `.pptx` (legacy `.ppt` is not supported; re-save it as `.pptx`)
- Excel and data: `.xlsx`, `.xls`, `.csv`
- PDF: `.pdf`
- Web and markup: `.html`, `.htm`, `.xml`, `.json`
- Plain text and books: `.txt`, `.epub`

Email, Word, RTF, ODT, HTML, and text/csv/json/xml convert out of the box (macOS
`textutil` plus built-ins), and `.xlsx` uses `openpyxl`. PDF, PowerPoint (`.pptx`),
legacy Excel (`.xls`), and EPUB rely on `markitdown` and a couple of helper libraries,
which setup installs for you (`markitdown` extras, `ebooklib`, `openpyxl`). To add them
later:

```
python3 -m venv .venv
.venv/bin/python3 -m pip install "markitdown[docx,pptx,xlsx,xls,pdf]" ebooklib openpyxl html2text
```

Use Python 3.10+ when creating that environment. If you change Python major/minor
versions, setup reports an incompatible existing `.venv` rather than silently
installing into the old interpreter; recreate the environment as directed.

TXT, CSV, JSON, and XML use built-in readers regardless of optional converters.
CSV, JSON, and XML are preserved in fenced code blocks; UTF BOMs and HTML/XML
encoding declarations are honored. XLSX uses saved cell values when available;
formulas without saved results are shown as formulas, not silently omitted. The
converter does not calculate formulas.

## How your agent uses it

Point your agent at the watched folder. Each `.md` file has YAML front matter (for
emails: subject, from, to, date; for other files: title, source_file, type)
followed by the converted content. Email attachment names are recorded in the front
matter, and their converted contents are appended after the email body in the same
file. Ask things like "read emails/ and summarize open decisions" or "pull the
action items from the latest spec I dropped in."

## Configuration

`config.json` (created by setup; see `config.example.json`):

| Key | Meaning |
|---|---|
| `watchFolders` | List of non-empty paths to exact folders. `~` is expanded; relative paths resolve from the configuration directory. Duplicates are removed. |
| `pollSeconds` | Seconds between scans: a finite number of at least 1 (default 2). Fractions are supported. |

A missing configuration watches nothing. Malformed JSON or invalid values produce
an error rather than silently disabling the watcher or overwriting the file.
Setup and folder commands preserve unknown configuration keys and save atomically.

After editing, restart the watcher:
`launchctl kickstart -k gui/$(id -u)/com.automdconvert.watcher`

## Layout

```
bootstrap.py              One-shot installer
setup.command             Double-click launcher for bootstrap
package.command           Build a distributable zip for another Mac
splash.py                 Reusable startup banner + VK credit (drop into any repo)
shared/convert/           File-to-Markdown core (email, Office, PDF, HTML, ...)
dropzone/watch.py         Background watcher for dropped files
dropzone/watch_folder.py  Enable/disable which folders are watched
dropzone/convert_path.py  Convert specific files to Markdown in place (CLI)
dropzone/install_quick_action.py  Install/remove the Finder "Convert to Markdown" Quick Action
shortcuts.zsh             Optional zsh shortcuts (add-folder/list-folder/remove-folder)
handoff-prompt.md         Prompt to hand another project's agent
tests/                   Regression and isolated integration tests (source checkout)
```

Reuse the splash on any repo: copy `splash.py` and run `python3 splash.py "YOUR TITLE"`
(or `from splash import render`). `SPLASH_OFF=1` skips it; `SPLASH_PLAIN_VK=1` uses a
plain `VK` for terminals without the styled glyph.

## Validation

From a source checkout:

```
python3 -m unittest discover -s tests -v
bash -n setup.command package.command
zsh -n shortcuts.zsh
```

The tests use temporary folders and do not load LaunchAgents, install real Finder
services, or modify your configuration. Format integration tests generate their
own documents; optional-format tests explicitly skip when dependencies are absent.
Run the suite with `.venv/bin/python3` after setup to include those formats.
macOS-specific integration tests require `textutil`, `plutil`, and `ditto`.

## Uninstall

```
launchctl bootout gui/$(id -u)/com.automdconvert.watcher
rm ~/Library/LaunchAgents/com.automdconvert.watcher.plist
python3 dropzone/install_quick_action.py --uninstall
```

## Notes on security

The watcher runs locally and only reads files in the folders you enable. It writes
Markdown next to them and archives the originals into `.originals/`. This
repository ignores its `emails/` folder and `.originals/` archives. Other watched
projects need their own ignore rules; the watcher does not change their
`.gitignore`. Treat document contents as untrusted input when an agent reads them.

---

Crafted by VK.
