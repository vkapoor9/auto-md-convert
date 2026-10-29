from __future__ import annotations

import concurrent.futures
import errno
import json
import tempfile
import unittest
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

from shared.convert import core


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.json"
        self.patch = mock.patch.object(core, "CONFIG_PATH", self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_missing_config_has_independent_defaults(self):
        first = core.load_config()
        first["watchFolders"].append("/tmp/test")
        self.assertEqual(core.load_config()["watchFolders"], [])

    def test_invalid_config_is_not_silently_ignored(self):
        for content in ('{', '[]', '{"watchFolders": "abc"}',
                        '{"watchFolders": [null]}', '{"watchFolders": [""]}',
                        '{"pollSeconds": 0}', '{"pollSeconds": true}',
                        '{"pollSeconds": "two"}', '{"pollSeconds": NaN}',
                        '{"pollSeconds": ' + '9' * 400 + '}'):
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(ValueError):
                    core.load_config()
                self.assertEqual(self.path.read_text(), content)

    def test_paths_are_normalized_and_deduplicated_relative_to_config(self):
        self.path.write_text(json.dumps({"watchFolders": ["emails", "./emails"],
                                        "pollSeconds": 1.5, "custom": "keep"}))
        cfg = core.load_config()
        self.assertEqual(cfg["watchFolders"], [str((self.path.parent / "emails").resolve())])
        self.assertEqual(cfg["pollSeconds"], 1.5)
        self.assertEqual(cfg["custom"], "keep")


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_unsupported_binary_never_reaches_textutil(self):
        path = self.root / "data.bin"
        path.write_bytes(b"\x00binary")
        with mock.patch.object(core, "_textutil", return_value="garbage") as textutil:
            with self.assertRaises(ValueError):
                core.convert_file(path)
        textutil.assert_not_called()

    def test_missing_text_file_preserves_io_error(self):
        with mock.patch.object(core, "_markitdown", return_value=None):
            with self.assertRaises(FileNotFoundError):
                core.convert_file(self.root / "missing.csv")

    def test_empty_structured_text_is_not_success(self):
        for suffix in (".csv", ".json", ".xml"):
            with self.subTest(suffix=suffix):
                path = self.root / ("empty" + suffix)
                path.write_text("")
                with mock.patch.object(core, "_markitdown", return_value=None):
                    with self.assertRaises(ValueError):
                        core.convert_file(path)

    def test_utf_bom_text_is_decoded(self):
        for encoding in ("utf-8-sig", "utf-16", "utf-32"):
            with self.subTest(encoding=encoding):
                path = self.root / "text.txt"
                path.write_bytes("Hello café".encode(encoding))
                with mock.patch.object(core, "_markitdown", return_value=None):
                    _, body = core.convert_file(path)
                self.assertEqual(body, "Hello café")

    def test_embedded_fences_cannot_end_structured_text_block(self):
        path = self.root / "data.json"
        path.write_text('{"example": "```"}')
        with mock.patch.object(core, "_markitdown", return_value=None):
            _, body = core.convert_file(path)
        self.assertEqual(body, '````json\n{"example": "```"}\n````')

    def test_yaml_scalars_escape_control_characters(self):
        value = 'quoted " text\\path\x00\t\x1b\nnext'
        encoded = core._yaml_str(value)
        self.assertNotIn("\x00", encoded)
        self.assertNotIn("\x1b", encoded)
        self.assertEqual(json.loads(encoded), value)

    def test_write_does_not_follow_dangling_output_symlink(self):
        meta = {"title": "report", "date_prefix": "2026-01-01"}
        elsewhere = self.root / "unrelated"
        output = self.root / core.build_filename(meta)
        output.symlink_to(elsewhere)
        target = core.write_markdown(self.root, meta, "content")
        self.assertTrue(output.is_symlink())
        self.assertFalse(elsewhere.exists())
        self.assertNotEqual(output, target)
        self.assertIn("content", target.read_text())

    def test_concurrent_writes_preserve_every_document(self):
        meta = {"title": "report", "date_prefix": "2026-01-01"}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outputs = list(pool.map(
                lambda i: core.write_markdown(self.root, meta, f"document {i}"),
                range(24),
            ))
        self.assertEqual(len(set(outputs)), 24)
        for i, path in enumerate(outputs):
            self.assertTrue(path.read_text().endswith(f"document {i}\n"))

    def test_spreadsheet_is_closed_on_iteration_failure(self):
        workbook = mock.Mock()
        sheet = mock.Mock()
        sheet.iter_rows.side_effect = OSError("broken workbook")
        workbook.worksheets = [sheet]
        formulas = mock.MagicMock()
        loader = mock.Mock(side_effect=[workbook, formulas])
        with mock.patch.dict(sys.modules, {"openpyxl": SimpleNamespace(load_workbook=loader)}):
            with self.assertRaises(OSError):
                core._xlsx_to_markdown(self.root / "broken.xlsx")
        workbook.close.assert_called_once()
        formulas.close.assert_called_once()

    def test_failed_output_publication_leaves_no_temp_or_partial_file(self):
        with mock.patch.object(core.os, "link", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                core.write_markdown(self.root, {"title": "test"}, "body")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_failed_config_save_preserves_existing_file(self):
        path = self.root / "config.json"
        path.write_text('{"custom": "original"}')
        with mock.patch.object(core.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                core.save_config({"watchFolders": []}, path)
        self.assertEqual(path.read_text(), '{"custom": "original"}')
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_blank_email_is_rejected(self):
        path = self.root / "blank.eml"
        path.write_text("Subject: Empty\n\n")
        with self.assertRaisesRegex(ValueError, "no readable"):
            core.convert_file(path)

    def test_declared_html_encoding_is_honored(self):
        path = self.root / "page.html"
        path.write_bytes(b'<html><head><meta charset="windows-1252"></head>'
                         b'<body><p>caf\xe9</p></body></html>')
        _, body = core.convert_file(path)
        self.assertIn("café", body)

    def test_output_on_filesystem_without_hard_links(self):
        target = self.root / "report.md"
        target.write_text("existing")
        with mock.patch.object(core.os, "link", side_effect=OSError(errno.ENOTSUP, "no hard links")):
            result = core.write_unique_text(target, "new content")
        self.assertEqual(target.read_text(), "existing")
        self.assertEqual(result.read_text(), "new content")

    def test_fsync_failure_removes_temporary_output(self):
        with mock.patch.object(core.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                core.write_unique_text(self.root / "report.md", "new")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_fsync_failure_does_not_replace_config(self):
        path = self.root / "config.json"
        path.write_text("{}")
        with mock.patch.object(core.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                core.save_config({}, path)
        self.assertEqual(path.read_text(), "{}")
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_failed_fallback_copy_removes_partial_file(self):
        source = self.root / "source.txt"
        source.write_text("data")
        with mock.patch.object(core.os, "link", side_effect=OSError(errno.ENOTSUP, "no hard links")), \
             mock.patch.object(core.shutil, "copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                core.publish_unique_file(source, self.root / "output.txt")
        self.assertEqual(list(self.root.iterdir()), [source])
        self.assertEqual(source.read_text(), "data")


if __name__ == "__main__":
    unittest.main()
