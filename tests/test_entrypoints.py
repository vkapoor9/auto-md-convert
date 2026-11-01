from __future__ import annotations

import contextlib
import io
import json
import os
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bootstrap
from dropzone import convert_path, install_quick_action, watch_folder


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_launch_agent_escapes_paths(self):
        args = ["/path with & and <angle>/python", "a\"b.py"]
        log = self.root / "log & <output>.log"
        with mock.patch.dict(os.environ, {"AUTOMDCONVERT_LAUNCHAGENTS_DIR": str(self.root)}):
            target = bootstrap.write_launch_agent("com.test.watcher", args, log)
        data = plistlib.loads(target.read_bytes())
        self.assertEqual(data["ProgramArguments"], args)
        self.assertEqual(data["StandardErrorPath"], str(log))

    def test_quick_action_uses_literal_shell_paths_without_killing_apps(self):
        fake_repo = self.root / 'repo $HOME & "quotes"'
        with mock.patch.object(install_quick_action, "REPO", fake_repo), \
             mock.patch.object(install_quick_action, "services_dir", return_value=self.root), \
             mock.patch.object(install_quick_action, "find_python", return_value="/bin/echo"), \
             mock.patch.object(install_quick_action.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(install_quick_action.install())
        data = plistlib.loads((self.root / "Convert to Markdown.workflow" /
                              "Contents" / "document.wflow").read_bytes())
        command = data["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
        import shlex
        self.assertEqual(shlex.split(command)[:2],
                         ["/bin/echo", str(fake_repo / "dropzone" / "convert_path.py")])
        self.assertNotIn("killall", [call.args[0][0] for call in run.call_args_list])
        result = subprocess.run(["/bin/zsh", "-c", command, "--", "selected file.txt"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         str(fake_repo / "dropzone/convert_path.py") + " selected file.txt")

    def test_uninstall_reports_permission_failure(self):
        bundle = self.root / "Convert to Markdown.workflow"
        bundle.mkdir()
        with mock.patch.object(install_quick_action, "bundle_path", return_value=bundle), \
             mock.patch.object(install_quick_action.shutil, "rmtree",
                               side_effect=PermissionError("denied")), \
             mock.patch.object(install_quick_action.subprocess, "run"), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(install_quick_action.uninstall())

    def test_mixed_cli_result_has_failure_exit_code(self):
        good = self.root / "good.txt"
        missing = self.root / "missing.txt"
        good.write_text("good")
        with mock.patch.object(convert_path, "_notify"), \
             mock.patch.object(convert_path, "_reveal"), \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            result = convert_path.main([str(good), str(missing)])
        self.assertEqual(result, 1)
        self.assertEqual(good.read_text(), "good")
        self.assertTrue(good.with_suffix(".md").exists())

    def test_finder_reveal_passes_filename_as_argument_not_script(self):
        path = self.root / 'a "quoted" \\ filename.md'
        with mock.patch.object(convert_path.subprocess, "run") as run:
            convert_path._reveal(path)
        args = run.call_args.args[0]
        self.assertEqual(args, ["open", "-R", str(path)])

    def test_malformed_config_cannot_be_overwritten_by_folder_command(self):
        config = self.root / "config.json"
        config.write_text("{broken")
        with mock.patch.object(watch_folder, "CONFIG", config), \
             mock.patch.object(watch_folder, "restart_watcher"), \
             contextlib.redirect_stderr(io.StringIO()):
            result = watch_folder.main(["add", str(self.root / "project")])
        self.assertEqual(result, 1)
        self.assertEqual(config.read_text(), "{broken")
        self.assertFalse((self.root / "project" / "agent-inbox").exists())

    def test_folder_commands_preserve_custom_config(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"watchFolders": [], "pollSeconds": 1.5,
                                      "custom": "keep"}))
        with mock.patch.object(watch_folder, "CONFIG", config), \
             mock.patch.object(watch_folder, "restart_watcher"), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(watch_folder.main(["add", str(self.root / "project")]), 0)
            self.assertEqual(watch_folder.main(["remove", str(self.root / "project")]), 0)
        self.assertEqual(json.loads(config.read_text()),
                         {"watchFolders": [], "pollSeconds": 1.5, "custom": "keep"})

    def test_folder_target_is_the_project_agent_inbox(self):
        project = self.root / "project"
        self.assertEqual(watch_folder.resolve_target(str(project)), (project / "agent-inbox").resolve())
        self.assertEqual(watch_folder.resolve_target(str(project / "agent-inbox")),
                         (project / "agent-inbox").resolve())

    def test_folder_command_rejects_extra_arguments(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(watch_folder.main(["list", "unexpected"]), 1)


if __name__ == "__main__":
    unittest.main()
