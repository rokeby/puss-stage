"""Offline positive/negative harness for p166_scripted_safe_startup.py."""
from __future__ import annotations

import importlib.util
import pathlib
import types


HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "p166_scripted_safe_startup.py"
spec = importlib.util.spec_from_file_location("p166_scripted_safe_startup", TARGET)
M = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(M)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL|" + name)


class Delegate:
    def __init__(self):
        self.calls = []

    def add_callable_unique(self, callback):
        if callback not in self.calls:
            self.calls.append(callback)


class LevelEditor:
    def __init__(self):
        self.realtime = True

    def editor_set_viewport_realtime(self, value):
        self.realtime = bool(value)


class SystemLibrary:
    values = {name: 7 + index for index, name in enumerate(M.SAFE_VALUES)}
    reject = None

    @classmethod
    def get_console_variable_int_value(cls, name):
        return cls.values[name]

    @classmethod
    def execute_console_command(cls, _world, command, _player):
        name, raw = command.rsplit(" ", 1)
        if name != cls.reject:
            cls.values[name] = int(raw)


level_editor = LevelEditor()
editor = types.SimpleNamespace(get_game_world=lambda: None, get_editor_world=lambda: object())
FAKE = types.SimpleNamespace(
    UnrealEditorSubsystem=type("UnrealEditorSubsystem", (), {}),
    LevelEditorSubsystem=type("LevelEditorSubsystem", (), {}),
    SystemLibrary=SystemLibrary,
    EditorDelegates=types.SimpleNamespace(pre_begin_pie=Delegate(), end_pie=Delegate()),
    logs=[], errors=[],
)
FAKE.get_editor_subsystem = lambda cls: level_editor if cls is FAKE.LevelEditorSubsystem else editor
FAKE.log = FAKE.logs.append
FAKE.log_error = FAKE.errors.append
M.unreal = FAKE

originals = dict(SystemLibrary.values)
M._INSTALLED = False
check("install positive", M.install())
check("all safe values applied", SystemLibrary.values == M.SAFE_VALUES)
check("realtime disabled", not level_editor.realtime)
check("pre-begin PIE delegate bound", len(FAKE.EditorDelegates.pre_begin_pie.calls) == 1)
check("end PIE delegate bound", len(FAKE.EditorDelegates.end_pie.calls) == 1)
check("idempotent install negative", not M.install())

M._pre_begin_pie(False)
check("PIE restores all originals", SystemLibrary.values == originals)
M._end_pie(False)
check("end PIE reapplies safe values", SystemLibrary.values == M.SAFE_VALUES)
check("end PIE disables realtime again", not level_editor.realtime)

# Negative control: a rejected cvar write must fail its exact read-back.
SystemLibrary.reject = "r.Lumen.Reflections.Allow"
SystemLibrary.values[SystemLibrary.reject] = 1
caught = False
try:
    M.apply_safe_settings("negative")
except RuntimeError as exc:
    caught = "CVAR_READBACK_FAILED" in str(exc)
check("readback mismatch caught", caught)
SystemLibrary.reject = None

# Negative control: show restoration cannot guess values before capture.
saved = dict(M._ORIGINAL_VALUES)
M._ORIGINAL_VALUES.clear()
caught = False
try:
    M.restore_show_settings("negative")
except RuntimeError as exc:
    caught = "ORIGINAL_VALUES_NOT_CAPTURED" in str(exc)
check("missing originals caught", caught)
M._ORIGINAL_VALUES.update(saved)

print("P166_SCRIPTED_SAFE_TESTS|pass=%d|fail=%d" % (passed, failed))
raise SystemExit(1 if failed else 0)
