from __future__ import annotations

import tempfile
import unittest
import contextlib
import io
import errno
import sys
from pathlib import Path
from unittest import mock

from dropzone import watch
from shared.convert import core


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = {"watchFolders": [str(self.root)], "pollSeconds": 1}
        self.seen = set()
        for patch in (mock.patch.object(watch.time, "sleep"),
                      mock.patch.object(core, "_markitdown", return_value=None),
                      mock.patch.object(watch, "_log")):
            patch.start()
            self.addCleanup(patch.stop)

    def scan(self):
        return watch._scan_once(self.cfg, self.seen)

    def test_reused_filename_is_converted_and_archive_is_not_overwritten(self):
        src = self.root / "report.txt"
        src.write_text("first version")
        self.scan()
        src.write_text("second version")
        self.scan()
        self.assertFalse(src.exists())
        archive = self.root / watch.ARCHIVE_DIRNAME
        self.assertEqual(sorted(p.read_text() for p in archive.iterdir()),
                         ["first version", "second version"])
        self.assertEqual(len(list(self.root.glob("*.md"))), 2)

    def test_preexisting_archive_is_preserved_after_restart(self):
        archive = self.root / watch.ARCHIVE_DIRNAME
        archive.mkdir()
        (archive / "report.txt").write_text("original")
        (self.root / "report.txt").write_text("replacement")
        self.scan()
        self.assertEqual((archive / "report.txt").read_text(), "original")
        self.assertEqual(len(list(archive.iterdir())), 2)

    def test_failed_conversion_is_retried(self):
        src = self.root / "report.txt"
        src.write_text("retry me")
        original = core.convert_file
        with mock.patch.object(core, "convert_file", side_effect=OSError("busy")):
            self.scan()
        with mock.patch.object(core, "convert_file", wraps=original) as convert:
            self.scan()
        convert.assert_called_once_with(src)
        self.assertFalse(src.exists())

    def test_output_error_does_not_prevent_other_conversions(self):
        for name in ("one.txt", "two.txt"):
            (self.root / name).write_text(name)
        original = core.write_markdown
        count = 0

        def write(*args):
            nonlocal count
            count += 1
            if count == 1:
                raise OSError("disk temporarily unavailable")
            return original(*args)

        with mock.patch.object(core, "write_markdown", side_effect=write):
            self.scan()
        self.assertEqual(count, 2)
        self.assertEqual(len(list(self.root.glob("*.md"))), 1)
        self.scan()
        self.assertEqual(len(list(self.root.glob("*.md"))), 2)

    def test_archive_failure_retains_source_and_rolls_back_output(self):
        src = self.root / "report.txt"
        src.write_text("keep me")
        (self.root / watch.ARCHIVE_DIRNAME).write_text("not a directory")
        self.scan()
        self.scan()
        self.assertEqual(src.read_text(), "keep me")
        self.assertEqual(list(self.root.glob("*.md")), [])

    def test_same_size_write_during_settling_is_not_converted(self):
        src = self.root / "report.txt"
        src.write_text("first")

        def modify(_):
            src.write_text("other")

        with mock.patch.object(watch.time, "sleep", side_effect=modify):
            self.scan()
        self.assertTrue(src.exists())
        self.assertEqual(list(self.root.glob("*.md")), [])

    def test_change_during_conversion_is_not_archived(self):
        src = self.root / "report.txt"
        src.write_text("before")
        original = core.convert_file

        def convert(path):
            result = original(path)
            path.write_text("changed during conversion")
            return result

        with mock.patch.object(core, "convert_file", side_effect=convert):
            self.scan()
        self.assertEqual(src.read_text(), "changed during conversion")
        self.assertEqual(list(self.root.glob("*.md")), [])

    def test_skips_symlinks_subfolders_hidden_and_unsupported_files(self):
        outside = self.root / "nested"
        outside.mkdir()
        real = outside / "real.txt"
        real.write_text("outside watch")
        (self.root / "link.txt").symlink_to(real)
        (self.root / ".hidden.txt").write_text("hidden")
        (self.root / "ignored.bin").write_bytes(b"\x00")
        self.scan()
        self.assertTrue((self.root / "link.txt").is_symlink())
        self.assertEqual(real.read_text(), "outside watch")
        self.assertEqual(list(self.root.glob("*.md")), [])

    def test_help_never_starts_watching_or_reads_config(self):
        with mock.patch.object(sys, "argv", ["watch.py", "--help"]), \
             mock.patch.object(core, "load_config", side_effect=AssertionError("read config")), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                watch.main()
        self.assertEqual(result.exception.code, 0)

    def test_unknown_options_are_rejected_before_reading_config(self):
        with mock.patch.object(sys, "argv", ["watch.py", "--typo"]), \
             mock.patch.object(core, "load_config", side_effect=AssertionError("read config")), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                watch.main()
        self.assertEqual(result.exception.code, 2)

    def test_once_exits_nonzero_for_conversion_failure(self):
        (self.root / "empty.txt").touch()
        with mock.patch.object(sys, "argv", ["watch.py", "--once"]), \
             mock.patch.object(core, "load_config", return_value=self.cfg):
            self.assertEqual(watch.main(), 1)

    def test_once_reports_invalid_config(self):
        with mock.patch.object(sys, "argv", ["watch.py", "--once"]), \
             mock.patch.object(core, "load_config", side_effect=ValueError("bad config")):
            self.assertEqual(watch.main(), 1)
        watch._log.assert_called_with("bad config")

    def test_failed_source_removal_rolls_back_archive_and_markdown(self):
        src = self.root / "report.txt"
        src.write_text("original")
        original = Path.unlink

        def unlink(path, *args, **kwargs):
            if path == src:
                raise PermissionError("cannot remove source")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", unlink):
            self.assertFalse(self.scan())
        self.assertEqual(src.read_text(), "original")
        self.assertEqual(list(self.root.glob("*.md")), [])
        self.assertEqual(list((self.root / ".originals").iterdir()), [])

    def test_archive_symlink_never_writes_outside_watched_folder(self):
        outside = self.root / "elsewhere"
        outside.mkdir()
        (self.root / ".originals").symlink_to(outside)
        src = self.root / "report.txt"
        src.write_text("original")
        self.assertFalse(self.scan())
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue(src.exists())

    def test_archives_on_filesystem_without_hard_links(self):
        src = self.root / "report.txt"
        src.write_text("original")
        with mock.patch.object(core.os, "link", side_effect=OSError(errno.ENOTSUP, "no hard links")):
            self.assertTrue(self.scan())
        self.assertFalse(src.exists())
        self.assertEqual((self.root / ".originals/report.txt").read_text(), "original")


if __name__ == "__main__":
    unittest.main()
