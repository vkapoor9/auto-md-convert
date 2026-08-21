"""Convert dropped files into clean Markdown a coding agent can read.

Dispatch by extension:
  - .eml            parsed here into email Markdown (headers + full thread).
  - everything else Microsoft markitdown when installed (best output, adds PDF /
                    PPTX / XLSX), else macOS `textutil` for Word / RTF / ODT / HTML,
                    else a plain-text wrapper for txt / csv / json / xml.

Baseline is standard library plus macOS `textutil`; markitdown and html2text are
optional upgrades. Used by dropzone/watch.py.
"""

from __future__ import annotations

import json
import re
import html as _html
import subprocess
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config.json"

_DEFAULT_CONFIG = {
    "watchFolders": [],
    "pollSeconds": 2,
}

# Files the watcher will try to convert. Markdown output (.md) is intentionally
# excluded so the tool never reprocesses its own output.
SUPPORTED_EXTS = {
    ".eml",
    ".doc", ".docx", ".rtf", ".odt",
    ".pptx",
    ".xls", ".xlsx", ".csv",
    ".pdf",
    ".html", ".htm",
    ".epub",
    ".json", ".xml",
    ".txt",
}

# Formats macOS `textutil` can read, used when markitdown is unavailable.
_TEXTUTIL_EXTS = {".doc", ".docx", ".rtf", ".odt", ".html", ".htm", ".wordml", ".webarchive"}

# Formats markitdown handles poorly (returns raw markup); prefer textutil for these.
_TEXTUTIL_FIRST = {".rtf", ".doc", ".odt", ".wordml", ".webarchive"}

# Spreadsheets we convert with openpyxl first: cleaner tables, blanks instead of
# markitdown's pandas "NaN", and no dependency on markitdown's optional xlsx extra.
_XLSX_FIRST = {".xlsx", ".xlsm"}


def load_config() -> dict:
    """Read config.json from the repo root, filling in defaults for missing keys."""
    cfg = dict(_DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError):
        pass
    cfg["watchFolders"] = [str(Path(p).expanduser()) for p in cfg.get("watchFolders", [])]
    return cfg


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTS


# --------------------------------------------------------------------------- #
# HTML -> text
# --------------------------------------------------------------------------- #

def html_to_text(html: str) -> str:
    """Best-effort HTML to plain text. Uses html2text if installed."""
    if not html:
        return ""
    try:
        import html2text  # type: ignore

        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_images = True
        return h.handle(html).strip()
    except Exception:
        return _basic_html_to_text(html)


def _basic_html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?i)</tr\s*>", "\n", text)
    text = re.sub(r"(?i)</h[1-6]\s*>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = _html.unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# Filenames and Markdown rendering
# --------------------------------------------------------------------------- #

def slugify(text: str) -> str:
    slug = (text or "").strip().lower()
    slug = re.sub(r"^(re|fwd?|fw)\s*:\s*", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    slug = slug[:60].strip("-")
    return slug or "untitled"


def _email_date_prefix(date_header: str | None, captured_iso: str) -> str:
    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)
            if dt is not None:
                return dt.strftime("%Y-%m-%d")
        except (TypeError, ValueError, IndexError):
            pass
    return captured_iso[:10]


def build_filename(meta: dict) -> str:
    prefix = meta.get("date_prefix") or (meta.get("captured", "") or "")[:10] \
        or datetime.now().strftime("%Y-%m-%d")
    title = meta.get("subject") or meta.get("title") or "untitled"
    return f"{prefix}--{slugify(title)}.md"


def _yaml_str(value) -> str:
    if value is None:
        return '""'
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\r", "").replace("\n", " ").strip()
    return f'"{s}"'


def _human_size(num) -> str:
    try:
        num = float(num)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def render_markdown(meta: dict, body: str) -> str:
    if meta.get("kind") == "email":
        return _render_email(meta, body)
    return _render_file(meta, body)


def _render_email(meta: dict, body_text: str) -> str:
    attachments = meta.get("attachments") or []
    att_names = [a.get("name", "attachment") for a in attachments]

    lines = ["---"]
    lines.append(f"subject: {_yaml_str(meta.get('subject'))}")
    lines.append(f"from: {_yaml_str(meta.get('from'))}")
    lines.append(f"to: {_yaml_str(meta.get('to'))}")
    if meta.get("cc"):
        lines.append(f"cc: {_yaml_str(meta.get('cc'))}")
    lines.append(f"date: {_yaml_str(meta.get('date'))}")
    if meta.get("message_id"):
        lines.append(f"message_id: {_yaml_str(meta.get('message_id'))}")
    if att_names:
        lines.append("attachments: [" + ", ".join(_yaml_str(n) for n in att_names) + "]")
    lines.append(f"captured: {_yaml_str(meta.get('captured'))}")
    lines.append(f"source: {_yaml_str(meta.get('source'))}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {(meta.get('subject') or '(no subject)').strip()}")
    lines.append("")
    lines.append(f"**From:** {meta.get('from') or ''}  ")
    lines.append(f"**To:** {meta.get('to') or ''}  ")
    if meta.get("cc"):
        lines.append(f"**Cc:** {meta.get('cc')}  ")
    lines.append(f"**Date:** {meta.get('date') or ''}")
    lines.append("")
    lines.append((body_text or "").strip())
    if attachments:
        lines.append("")
        lines.append("## Attachments")
        for a in attachments:
            size = a.get("size")
            size_str = f" ({_human_size(size)})" if size else ""
            lines.append(f"- {a.get('name', 'attachment')}{size_str}")
    lines.append("")
    return "\n".join(lines)


def _render_file(meta: dict, body: str) -> str:
    lines = ["---"]
    lines.append(f"title: {_yaml_str(meta.get('title'))}")
    lines.append(f"source_file: {_yaml_str(meta.get('source_file'))}")
    lines.append(f"type: {_yaml_str(meta.get('type'))}")
    lines.append(f"captured: {_yaml_str(meta.get('captured'))}")
    lines.append(f"source: {_yaml_str(meta.get('source'))}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {(meta.get('title') or 'Untitled').strip()}")
    lines.append("")
    lines.append((body or "").strip())
    lines.append("")
    return "\n".join(lines)


def write_markdown(dest_dir: Path, meta: dict, body: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(meta)
    target = dest_dir / filename
    counter = 2
    stem = target.stem
    while target.exists():
        target = dest_dir / f"{stem}-{counter}.md"
        counter += 1
    target.write_text(render_markdown(meta, body), encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Conversion dispatch
# --------------------------------------------------------------------------- #

def convert_file(path: Path) -> tuple[dict, str]:
    """Turn a supported file into (meta, markdown_body). Raises on failure."""
    ext = path.suffix.lower()
    captured = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if ext == ".eml":
        meta, body = _eml_to_meta_body(path)
        meta["kind"] = "email"
        meta["date_prefix"] = _email_date_prefix(meta.get("date"), captured)
        return meta, body

    body = _convert_other(path)
    if not body or not body.strip():
        raise ValueError(f"no converter produced output for '{ext or path.name}'")

    try:
        date_prefix = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        date_prefix = captured[:10]

    meta = {
        "kind": "file",
        "title": path.stem,
        "source_file": path.name,
        "type": ext.lstrip(".") or "file",
        "captured": captured,
        "date_prefix": date_prefix,
        "source": "drag-file",
    }
    return meta, body


def _convert_other(path: Path) -> str | None:
    ext = path.suffix.lower()

    # RTF/DOC/ODT: markitdown returns raw markup, so use textutil first.
    if ext in _TEXTUTIL_FIRST:
        t = _textutil(path)
        if t and t.strip():
            return t

    # XLSX/XLSM: openpyxl gives cleaner tables than markitdown (no "NaN" blanks).
    if ext in _XLSX_FIRST:
        x = _xlsx_to_markdown(path)
        if x and x.strip():
            return x

    md = _markitdown(path)
    if md and md.strip():
        return md

    if ext in _TEXTUTIL_EXTS:
        t = _textutil(path)
        if t and t.strip():
            return t

    if ext == ".txt":
        return _read_text(path)
    if ext in {".csv", ".json", ".xml"}:
        return f"```{ext.lstrip('.')}\n{_read_text(path).rstrip()}\n```"
    if ext in {".html", ".htm"}:
        return html_to_text(_read_text(path))

    return _textutil(path)


def _markitdown(path: Path) -> str | None:
    try:
        from markitdown import MarkItDown  # type: ignore
    except Exception:
        return None
    try:
        return MarkItDown().convert(str(path)).text_content
    except Exception:
        return None


def _xlsx_to_markdown(path: Path) -> str | None:
    """Render an .xlsx/.xlsm workbook as one Markdown table per non-empty sheet."""
    try:
        from openpyxl import load_workbook  # type: ignore
    except Exception:
        return None
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return None

    def cell(value) -> str:
        if value is None:
            return ""
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()

    out: list[str] = []
    for ws in wb.worksheets:
        rows = [r for r in ws.iter_rows(values_only=True)
                if any(c is not None and str(c).strip() != "" for c in r)]
        if not rows:
            continue
        width = max(len(r) for r in rows)
        out.append(f"## {ws.title}")
        header = list(rows[0]) + [None] * (width - len(rows[0]))
        out.append("| " + " | ".join(cell(c) for c in header) + " |")
        out.append("| " + " | ".join(["---"] * width) + " |")
        for r in rows[1:]:
            padded = list(r) + [None] * (width - len(r))
            out.append("| " + " | ".join(cell(c) for c in padded) + " |")
        out.append("")
    try:
        wb.close()
    except Exception:
        pass
    return "\n".join(out).strip() or None


def _textutil(path: Path) -> str | None:
    try:
        res = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# --------------------------------------------------------------------------- #
# .eml parsing
# --------------------------------------------------------------------------- #

def _eml_to_meta_body(eml_path: Path) -> tuple[dict, str]:
    with open(eml_path, "rb") as fh:
        msg = BytesParser(policy=policy.default).parse(fh)

    def hdr(name: str) -> str:
        value = msg[name]
        return "" if value is None else str(value).strip()

    try:
        body_part = msg.get_body(preferencelist=("plain", "html"))
    except Exception:
        body_part = None

    body_text = ""
    if body_part is not None:
        ctype = body_part.get_content_type()
        try:
            content = body_part.get_content()
        except Exception:
            content = ""
        if ctype == "text/html":
            body_text = html_to_text(content)
        else:
            body_text = content if isinstance(content, str) else str(content)

    attachments = []
    try:
        for part in msg.iter_attachments():
            name = part.get_filename() or "attachment"
            try:
                size = len(part.get_content()) if part.get_content_maintype() != "text" \
                    else len(part.get_content().encode("utf-8", "ignore"))
            except Exception:
                size = None
            attachments.append({"name": name, "size": size})
    except Exception:
        pass

    meta = {
        "subject": hdr("subject"),
        "from": hdr("from"),
        "to": hdr("to"),
        "cc": hdr("cc"),
        "date": hdr("date"),
        "message_id": hdr("message-id"),
        "attachments": attachments,
        "captured": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "drag-eml",
    }
    return meta, body_text
