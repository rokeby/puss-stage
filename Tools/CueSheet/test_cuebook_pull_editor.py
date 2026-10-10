"""Offline +/- harness for Job 142's Unreal editor Cue Book launcher."""

import importlib.util
import os
import pathlib
import sys
import tempfile
import textwrap
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "Saved" / "CueBook" / "cuebook_pull_editor.py"
SPEC = importlib.util.spec_from_file_location("cuebook_pull_editor_tested", MODULE_PATH)
EDITOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EDITOR
SPEC.loader.exec_module(EDITOR)

SYNC_SPEC = importlib.util.spec_from_file_location("cue_sync_job142_tested", ROOT / "Tools" / "CueSheet" / "cue_sync.py")
SYNC = importlib.util.module_from_spec(SYNC_SPEC)
sys.modules[SYNC_SPEC.name] = SYNC
SYNC_SPEC.loader.exec_module(SYNC)


class _Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeUnreal:
    class Paths:
        @staticmethod
        def project_dir():
            raise AssertionError("the harness passes project_dir explicitly")

    class UnrealEditorSubsystem:
        pass

    class SystemLibrary:
        calls = []

        @classmethod
        def execute_console_command(cls, world, command):
            cls.calls.append((world, command))

    class AppMsgType:
        OK = "OK"

    class AppReturnType:
        OK = "OK"

    class EditorDialog:
        messages = []

        @classmethod
        def show_message(cls, title, message, message_type, default):
            cls.messages.append((title, message, message_type, default))

    logs = []

    @classmethod
    def log(cls, message):
        cls.logs.append(message)

    @staticmethod
    def get_editor_subsystem(_kind):
        class _Subsystem:
            @staticmethod
            def get_game_world():
                return "FAKE_PIE_WORLD"

        return _Subsystem()


FAKE_SYNC = r'''
import csv
import os
import sys

root = os.getcwd()
working = os.path.join(root, "Docs", "CueSheet", "working.csv")
os.makedirs(os.path.dirname(working), exist_ok=True)
with open(working, "w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["Key", "Name"])
    writer.writerow(["R1", "new"])
    writer.writerow(["R2", "added"])
print("CUE_SYNC_WEBPULL_OK docs=2 applied=2 conflicts=1")
if sys.argv[1] == "cuebook":
    print("hostile child echoed secret=" + os.environ["CUEBOOK_PASS"])
print('CUE_SYNC_EXPORT_OK|cues=2|surtitles=1|changed_files=["Docs/CueSheet/working.csv"]')
'''


class CueBookEditorHarness(unittest.TestCase):
    def setUp(self):
        FakeUnreal.SystemLibrary.calls.clear()
        FakeUnreal.EditorDialog.messages.clear()
        FakeUnreal.logs.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "Tools" / "CueSheet").mkdir(parents=True)
        (self.root / "Saved" / "CueBook").mkdir(parents=True)
        (self.root / "Docs" / "CueSheet").mkdir(parents=True)
        (self.root / "Tools" / "CueSheet" / "cue_sync.py").write_text(
            textwrap.dedent(FAKE_SYNC), encoding="utf-8"
        )
        (self.root / "Docs" / "CueSheet" / "working.csv").write_text(
            "Key,Name\nR1,old\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_negative_missing_pass_file_refuses_without_subprocess(self):
        called = []

        def forbidden(*_args, **_kwargs):
            called.append(True)
            return _Completed()

        result = EDITOR.run_sync(
            "cuebook",
            project_dir=str(self.root),
            unreal_module=FakeUnreal,
            runner=forbidden,
            python_executable=sys.executable,
        )
        self.assertFalse(result.ok)
        self.assertFalse(called)
        self.assertIn("Saved", result.message)
        self.assertIn("cuebook_pass.txt", result.message)

    def test_positive_pull_reports_conflict_reloads_and_never_exposes_passcode(self):
        secret = "NEVER-SHOW-142"
        (self.root / "Saved" / "CueBook" / "cuebook_pass.txt").write_text(secret, encoding="utf-8")
        result = EDITOR.run_sync(
            "cuebook",
            project_dir=str(self.root),
            unreal_module=FakeUnreal,
            python_executable=sys.executable,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.rows_changed, 2)
        self.assertEqual(result.conflicts, 1)
        self.assertNotIn(secret, result.message)
        self.assertNotIn(secret, "\n".join(FakeUnreal.logs))
        self.assertNotIn(secret, "\n".join(message for _, message, _, _ in FakeUnreal.EditorDialog.messages))
        self.assertEqual(
            FakeUnreal.SystemLibrary.calls,
            [("FAKE_PIE_WORLD", "InfinityStage.Surtitles.Reload")],
        )

    def test_positive_export_uses_selected_json_without_passcode(self):
        backup = self.root / "downloaded cue book.json"
        backup.write_text("{}", encoding="utf-8")
        result = EDITOR.run_sync(
            "export",
            str(backup),
            project_dir=str(self.root),
            unreal_module=FakeUnreal,
            python_executable=sys.executable,
            show_dialog=False,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.conflicts, 1)

    def test_online_download_routes_through_full_export(self):
        site = self.root / "Tools" / "CueBook" / "site"
        site.mkdir(parents=True)
        (site / "config.js").write_text('const CUEBOOK_API = "https://invalid.test/api";\n', encoding="utf-8")
        captured = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def read():
                return b'{"ok":true,"cues":[{"key":"R1"}],"surtitles":[{"key":"T1"}]}'

        old_root, old_dir = SYNC.ROOT, SYNC.DIR
        SYNC.ROOT = str(self.root)
        SYNC.DIR = str(self.root / "Docs" / "CueSheet")
        try:
            with mock.patch.dict(os.environ, {"CUEBOOK_PASS": "FAKE-PASS"}, clear=False), mock.patch(
                "urllib.request.urlopen", return_value=FakeResponse()
            ), mock.patch.object(SYNC, "cuebook_export", side_effect=lambda path: captured.append(path)):
                SYNC.cuebook_pull()
        finally:
            SYNC.ROOT, SYNC.DIR = old_root, old_dir
        self.assertEqual(len(captured), 1)
        self.assertTrue(pathlib.Path(captured[0]).is_file())

    def test_startup_script_registers_both_menu_entries(self):
        entries = []

        class FakeEntry:
            def __init__(self, name, type):
                self.name, self.type = name, type

            def set_label(self, value):
                self.label = value

            def set_tool_tip(self, value):
                self.tip = value

            def set_string_command(self, kind, custom, command):
                self.command = (kind, custom, command)

        class FakeMenu:
            @staticmethod
            def get_name():
                return "LevelEditor.MainMenu"

            def add_sub_menu(self, *_args):
                return self

            def add_menu_entry(self, section, entry):
                entries.append((section, entry))

        class FakeMenus:
            menu = FakeMenu()

            @classmethod
            def get(cls):
                return cls()

            def find_menu(self, _name):
                return self.menu

            def refresh_all_widgets(self):
                pass

        class MenuUnreal:
            ToolMenus = FakeMenus
            ToolMenuEntry = FakeEntry

            class Paths:
                @staticmethod
                def project_saved_dir():
                    return str(self.root / "Saved")

            class MultiBlockType:
                MENU_ENTRY = "entry"

            class ToolMenuStringCommandType:
                PYTHON = "python"

            @staticmethod
            def log(_message):
                pass

            @staticmethod
            def log_warning(_message):
                pass

        startup_path = ROOT / "Plugins" / "InfinityStage" / "Content" / "Python" / "init_unreal.py"
        startup_spec = importlib.util.spec_from_file_location("init_unreal_job142_tested", startup_path)
        startup = importlib.util.module_from_spec(startup_spec)
        with mock.patch.dict(sys.modules, {"unreal": MenuUnreal}):
            startup_spec.loader.exec_module(startup)
        self.assertEqual([entry.label for _, entry in entries], [
            "Pull Cue Book", "Export from Cue Book backup...", "Rebuild Passage Fixtures"
        ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
