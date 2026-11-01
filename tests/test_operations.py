from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bootstrap
import splash
from dropzone import convert_path, install_quick_action as qa, watch, watch_folder
from shared.convert import core


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = io.StringIO()
        for context in (contextlib.redirect_stdout(self.output),
                        contextlib.redirect_stderr(self.output)):
            context.__enter__()
            self.addCleanup(context.__exit__, None, None, None)

    def setup_with_fake_services(self, *, pip_status=0, venv_status=0,
                                 version=None, quick_action=True):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            status = pip_status if "pip" in command else venv_status if "venv" in command else 0
            output = version if version is not None else f"{sys.version_info.major}.{sys.version_info.minor}"
            return subprocess.CompletedProcess(command, status, output, "simulated error" if status else "")

        fake_qa = mock.Mock()
        if isinstance(quick_action, Exception):
            fake_qa.install.side_effect = quick_action
        else:
            fake_qa.install.return_value = quick_action
        env = {
            "AUTOMDCONVERT_SKIP_PIP": "", "AUTOMDCONVERT_SKIP_QUICKACTION": "",
            "AUTOMDCONVERT_SKIP_OPEN": "1", "SPLASH_OFF": "1",
            "AUTOMDCONVERT_LAUNCHAGENTS_DIR": str(self.root / "agents"),
        }
        with mock.patch.dict(os.environ, env), mock.patch.dict(sys.modules, {"install_quick_action": fake_qa}), \
             mock.patch.object(bootstrap, "REPO", self.root), \
             mock.patch.object(bootstrap, "ask", return_value=str(self.root / "project")), \
             mock.patch.object(bootstrap, "run", side_effect=run), \
             mock.patch.object(bootstrap, "module_available", return_value=False), \
             mock.patch.object(bootstrap, "load_launch_agent", return_value=True) as load:
            status = bootstrap.main()
        return status, calls, fake_qa, load

    def test_setup_uses_isolated_environment_for_dependencies_and_services(self):
        status, calls, fake_qa, load = self.setup_with_fake_services()
        self.assertEqual(status, 0)
        env_python = str(self.root / ".venv/bin/python3")
        self.assertEqual(calls[0], [sys.executable, "-m", "venv", str(self.root / ".venv")])
        pip = next(c for c in calls if "pip" in c)
        self.assertEqual(pip[:4], [env_python, "-m", "pip", "install"])
        self.assertNotIn("--user", pip)
        self.assertNotIn("--break-system-packages", pip)
        self.assertEqual(any(c.startswith("markitdown") for c in pip), sys.version_info >= (3, 10))
        fake_qa.install.assert_called_once_with(python=env_python)
        load.assert_called_once()
        self.assertTrue((self.root / "project/agent-inbox").is_dir())
        self.assertIn("Setup complete.", self.output.getvalue())

    def test_setup_reports_pip_failure(self):
        status, _, _, _ = self.setup_with_fake_services(pip_status=1)
        self.assertEqual(status, 1)
        self.assertIn("converter installation failed: simulated error", self.output.getvalue())
        self.assertNotIn("Setup complete.", self.output.getvalue())

    def test_setup_stops_if_environment_creation_fails(self):
        status, calls, _, load = self.setup_with_fake_services(venv_status=1)
        self.assertEqual(status, 1)
        self.assertEqual(len(calls), 1)
        load.assert_not_called()

    def test_setup_rejects_incompatible_existing_interpreter(self):
        status, calls, _, load = self.setup_with_fake_services(version="3.8")
        self.assertEqual(status, 1)
        self.assertFalse(any("pip" in call for call in calls))
        load.assert_not_called()
        self.assertIn("different or unavailable Python", self.output.getvalue())

    def test_setup_reports_quick_action_failure(self):
        for result in (False, OSError("service unavailable")):
            with self.subTest(result=result):
                status, _, _, _ = self.setup_with_fake_services(quick_action=result)
                self.assertEqual(status, 1)

    def test_launchctl_fallback_and_failure_are_reported(self):
        for final_status in (0, 1):
            with self.subTest(final_status=final_status):
                responses = [subprocess.CompletedProcess([], code, "", "load failed")
                             for code in (1, 1, final_status)]
                with mock.patch.dict(os.environ, {"AUTOMDCONVERT_SKIP_LOAD": ""}), \
                     mock.patch.object(bootstrap, "run", side_effect=responses) as run:
                    result = bootstrap.load_launch_agent(self.root / "test.plist", "com.test")
                self.assertEqual(result, final_status == 0)
                self.assertEqual([c.args[0][1] for c in run.call_args_list], ["bootout", "bootstrap", "load"])

    def test_prompt_defaults_and_canned_answers(self):
        with mock.patch.dict(os.environ, {"AUTOMDCONVERT_ANSWERS": "chosen\n"}), \
             mock.patch.object(bootstrap, "_answers_iter", None), \
             mock.patch("builtins.input", side_effect=EOFError):
            self.assertEqual(bootstrap.ask("prompt", "default"), "chosen")
            self.assertEqual(bootstrap.ask("prompt", "default"), "default")
            self.assertEqual(bootstrap.ask("prompt", "default"), "default")

    def test_quick_action_cli_statuses(self):
        self.assertEqual(qa.main(["--help"]), 0)
        self.assertEqual(qa.main(["--typo"]), 1)
        for success in (True, False):
            with mock.patch.object(qa, "install", return_value=success), \
                 mock.patch.object(qa, "uninstall", return_value=success):
                self.assertEqual(qa.main([]), 0 if success else 1)
                self.assertEqual(qa.main(["--uninstall"]), 0 if success else 1)
        with mock.patch.object(qa, "install", side_effect=OSError("read only")):
            self.assertEqual(qa.main([]), 1)

    def test_quick_action_interpreter_detection(self):
        with mock.patch.object(qa, "REPO", self.root), \
             mock.patch.object(qa.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            self.assertEqual(qa.find_python(), sys.executable)
        with mock.patch.object(Path, "exists", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "No working Python"):
                qa.find_python()

    def test_quick_action_invalid_plist_does_not_refresh_services(self):
        with mock.patch.object(qa, "services_dir", return_value=self.root), \
             mock.patch.object(qa.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1, "invalid plist", "")), \
             mock.patch.object(qa, "_refresh_services") as refresh:
            self.assertFalse(qa.install(python=sys.executable))
        refresh.assert_not_called()
        self.assertIn("invalid plist", self.output.getvalue())

    def test_quick_action_refresh_failure_is_visible(self):
        for failure in (OSError("not available"), subprocess.CompletedProcess([], 1, "", "not available")):
            with self.subTest(failure=failure):
                kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
                with mock.patch.object(qa.subprocess, "run", **kwargs):
                    qa._refresh_services()
        self.assertIn("Could not refresh Quick Actions", self.output.getvalue())

    def test_uninstall_removes_only_service_symlink(self):
        outside = self.root / "actual"
        outside.mkdir()
        bundle = self.root / "Convert to Markdown.workflow"
        bundle.symlink_to(outside)
        with mock.patch.object(qa, "services_dir", return_value=self.root), \
             mock.patch.object(qa, "_refresh_services"):
            self.assertTrue(qa.uninstall())
        self.assertTrue(outside.is_dir())
        self.assertFalse(bundle.is_symlink())

    def test_folder_commands_are_idempotent(self):
        config = self.root / "config.json"
        with mock.patch.object(watch_folder, "CONFIG", config), \
             mock.patch.object(watch_folder, "restart_watcher") as restart:
            self.assertEqual(watch_folder.main(["--help"]), 0)
            self.assertEqual(watch_folder.main(["bad-command"]), 1)
            self.assertEqual(watch_folder.main(["list"]), 0)
            for _ in range(2):
                self.assertEqual(watch_folder.main(["add", str(self.root)]), 0)
            self.assertEqual(watch_folder.main(["list"]), 0)
            self.assertEqual(len(json.loads(config.read_text())["watchFolders"]), 1)
            for _ in range(2):
                self.assertEqual(watch_folder.main(["remove", str(self.root)]), 0)
        self.assertEqual(restart.call_count, 2)

    def test_restart_failure_keeps_saved_configuration_and_reports_it(self):
        for result in (subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1),
                       OSError("unavailable")):
            with self.subTest(result=result):
                kwargs = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
                with mock.patch.object(watch_folder.subprocess, "run", **kwargs):
                    watch_folder.restart_watcher()
        self.assertIn("Watcher restarted.", self.output.getvalue())
        self.assertIn("could not restart", self.output.getvalue())

    def test_conversion_cli_help_empty_unsupported_failure_and_success(self):
        good = self.root / "good.txt"
        other = self.root / "other.bin"
        good.write_text("content")
        other.write_bytes(b"\0")
        with mock.patch.object(convert_path, "_notify"), mock.patch.object(convert_path, "_reveal"):
            for args, expected in (
                ([], 1), (["--help"], 0), ([str(other)], 1),
                ([str(self.root / "missing.txt")], 1), ([str(good), str(other)], 0),
                ([str(good)], 0),
            ):
                with self.subTest(args=args):
                    self.assertEqual(convert_path.main(args), expected)
        self.assertEqual(len(list(self.root.glob("*.md"))), 2)

    def test_notification_errors_do_not_fail_a_conversion(self):
        with mock.patch.object(convert_path.subprocess, "run", side_effect=OSError("no GUI")):
            convert_path._notify("AutoMDConvert", "Converted 1 file")
            convert_path._reveal(self.root / "result.md")

    def test_watcher_daemon_recovers_from_scan_exception_and_preserves_fractional_poll(self):
        cfg = {"watchFolders": [str(self.root)], "pollSeconds": 1.5}
        with mock.patch.object(sys, "argv", ["watch.py"]), \
             mock.patch.object(core, "load_config", return_value=cfg), \
             mock.patch.object(watch, "_scan_once", side_effect=[OSError("temporary"), True]), \
             mock.patch.object(watch.time, "sleep", side_effect=[None, KeyboardInterrupt]) as sleep:
            with self.assertRaises(KeyboardInterrupt):
                watch.main()
        self.assertEqual(sleep.call_args_list, [mock.call(1.5), mock.call(1.5)])
        self.assertIn("scan error: temporary", self.output.getvalue())

    def test_splash_custom_title_plain_credit_and_opt_out(self):
        with mock.patch.dict(os.environ, {"SPLASH_OFF": "", "AUTOMDCONVERT_NO_SPLASH": "",
                                         "SPLASH_PLAIN_VK": "1"}):
            splash.render("Test", "Example tagline")
            splash.render("", credit=False)
        self.assertIn("Example tagline", self.output.getvalue())
        self.assertIn("VK", self.output.getvalue())
        self.output.seek(0)
        self.output.truncate()
        with mock.patch.dict(os.environ, {"SPLASH_OFF": "1"}):
            splash.render()
        self.assertEqual(self.output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
