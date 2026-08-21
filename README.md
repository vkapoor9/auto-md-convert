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
| Python 3.9 or newer | Running setup and the watcher | Installer at https://www.python.org/downloads/, or `xcode-select --install`, or `brew install python` |

Check what you have with `python3 --version`. If it prints 3.9 or higher, you are
ready. If Python is missing or too old, `setup.command` detects it and tells you
exactly what to install before it does anything else.

Everything else is installed for you by setup: the `markitdown` and `html2text`
converters (via `pip`) and the background watcher service. The only thing setup ever
asks you is which folder to watch, and even that is optional.

## Why it works this way

The unit of input is a file you drag out of any app. A single background watcher
converts each dropped file to Markdown in place, so the same gesture works for
email, Word, PDF, and everything else. No app scripting or plugins required.

## Quick start

1. Confirm Python 3.9+ is installed (`python3 --version`). See Requirements above if not.
2. Double-click `setup.command` (or run `python3 bootstrap.py`).
3. When asked, type a folder to watch, or press Return to skip and add one later.

That is it. Setup installs the converters, installs a background watcher that
auto-starts at login, runs a smoke test, and opens VS Code. Nothing is watched
until you choose a folder.

If Python is missing, `setup.command` stops with clear install instructions instead
of failing part way. Email, Word, RTF, HTML, and text/csv/json convert with zero
extra installs; PDF, PowerPoint, and Excel light up once `markitdown` installs (setup
does this automatically and tells you if it could not).

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
the original into `.originals/`.

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
python3 dropzone/convert_path.py ~/Desktop/report.pdf notes.docx
```

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
python3 -m pip install --user "markitdown[docx,pptx,xlsx,xls,pdf]" ebooklib openpyxl html2text
```

## How your agent uses it

Point your agent at the watched folder. Each `.md` file has YAML front matter (for
emails: subject, from, to, date; for other files: title, source_file, type)
followed by the converted content. Ask things like "read emails/ and summarize open
decisions" or "pull the action items from the latest spec I dropped in."

## Configuration

`config.json` (created by setup; see `config.example.json`):

| Key | Meaning |
|---|---|
| `watchFolders` | List of exact folders to watch. Managed by `watch_folder.py`, or edit by hand. |
| `pollSeconds` | How often the watcher checks for new files. |

After editing, restart the watcher:
`launchctl kickstart -k gui/$(id -u)/com.automdconvert.watcher`

## Layout

```
bootstrap.py              One-shot installer
setup.command             Double-click launcher for bootstrap
splash.py                 Reusable startup banner + VK credit (drop into any repo)
shared/convert/           File-to-Markdown core (email, Office, PDF, HTML, ...)
dropzone/watch.py         Background watcher for dropped files
dropzone/watch_folder.py  Enable/disable which folders are watched
dropzone/convert_path.py  Convert specific files to Markdown in place (CLI)
dropzone/install_quick_action.py  Install/remove the Finder "Convert to Markdown" Quick Action
shortcuts.zsh             Optional zsh shortcuts (add-folder/list-folder/remove-folder)
handoff-prompt.md         Prompt to hand another project's agent
```

Reuse the splash on any repo: copy `splash.py` and run `python3 splash.py "YOUR TITLE"`
(or `from splash import render`). `SPLASH_OFF=1` skips it; `SPLASH_PLAIN_VK=1` uses a
plain `VK` for terminals without the styled glyph.

## Uninstall

```
launchctl bootout gui/$(id -u)/com.automdconvert.watcher
rm ~/Library/LaunchAgents/com.automdconvert.watcher.plist
python3 dropzone/install_quick_action.py --uninstall
```

## Notes on security

The watcher runs locally and only reads files in the folders you enable. It writes
Markdown next to them and archives the originals into `.originals/`. Captured output
and the `.originals` archive are git-ignored by default.

---

Crafted by VK.
