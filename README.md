# AutoMDConvert

Turn documents into clean Markdown automatically, so a coding agent working in a
project can read them for strategy, decisions, and task tracking. It handles most
common file types: email, Word, PowerPoint, Excel, PDF, HTML, RTF, CSV, and more.

You pick which folders to watch. Drag a file into a watched folder and a background
watcher turns it into a readable `.md` file. Drop a file anywhere else and it stays
untouched. That is the whole tool.

## Requirements

macOS (the watcher runs as a login LaunchAgent and uses `textutil`) and Python 3.

## Why it works this way

The unit of input is a file you drag out of any app. A single background watcher
converts each dropped file to Markdown in place, so the same gesture works for
email, Word, PDF, and everything else. No app scripting or plugins required.

## Quick start

Double-click `setup.command` (or run `python3 bootstrap.py`). It optionally enables
a first folder to watch, installs a background watcher that auto-starts at login,
and runs a smoke test. Nothing is watched until you choose a folder.

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

## Supported formats

- Email: `.eml`
- Word and rich text: `.docx`, `.doc`, `.rtf`, `.odt`
- PowerPoint: `.pptx`, `.ppt`
- Excel and data: `.xlsx`, `.xls`, `.csv`
- PDF: `.pdf`
- Web and markup: `.html`, `.htm`, `.xml`, `.json`
- Plain text and books: `.txt`, `.epub`

Word, RTF, ODT, HTML, email, and text/csv/json work out of the box (macOS
`textutil` plus built-ins). PDF, PowerPoint, and Excel need `markitdown`, which
setup tries to install. To add it later:

```
python3 -m pip install --user "markitdown[docx,pptx,xlsx,pdf]"
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
shared/convert/           File-to-Markdown core (email, Office, PDF, HTML, ...)
dropzone/watch.py         Background watcher for dropped files
dropzone/watch_folder.py  Enable/disable which folders are watched
shortcuts.zsh             Optional zsh shortcuts (add-folder/list-folder/remove-folder)
handoff-prompt.md         Prompt to hand another project's agent
```

## Uninstall

```
launchctl bootout gui/$(id -u)/com.automdconvert.watcher
rm ~/Library/LaunchAgents/com.automdconvert.watcher.plist
```

## Notes on security

The watcher runs locally and only reads files in the folders you enable. It writes
Markdown next to them and archives the originals into `.originals/`. Captured output
and the `.originals` archive are git-ignored by default.
