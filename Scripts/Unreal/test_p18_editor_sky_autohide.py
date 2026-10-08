"""Offline harness for p18_editor_sky_autohide.py; no Unreal import required."""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import types


HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "p18_editor_sky_autohide.py"
spec = importlib.util.spec_from_file_location("p18_editor_sky_autohide", TARGET)
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


def eq(name, got, want):
    check(name + "|got=%r|want=%r" % (got, want), got == want)


class Delegate:
    def __init__(self):
        self.calls = []

    def add_callable_unique(self, callback):
        if callback not in self.calls:
            self.calls.append(callback)


class Obj:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class Actor:
    def __init__(self, label, cls, package, dirties=False):
        self.label, self.cls, self.package = label, cls, package
        self.hidden, self.dirties = False, dirties

    def get_actor_label(self):
        return self.label

    def get_class(self):
        return Obj(self.cls)

    def get_outermost(self):
        return Obj(self.package)

    def set_is_temporarily_hidden_in_editor(self, value):
        self.hidden = bool(value)
        if self.dirties:
            FAKE.dirty_content.append(Obj("/Game/Bad"))

    def is_temporarily_hidden_in_editor(self):
        return self.hidden


class Editor:
    def __init__(self, world):
        self.world, self.game = world, None

    def get_editor_world(self):
        return self.world

    def get_game_world(self):
        return self.game


class World:
    def __init__(self, package):
        self.package = package

    def get_outermost(self):
        return Obj(self.package)


class Level:
    def __init__(self, package):
        self.package = package

    def get_outer(self):
        return Obj(self.package)

    def get_name(self):
        return self.package.rsplit("/", 1)[-1]


class FakeUnreal(types.SimpleNamespace):
    pass


root = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
world = World(root)
editor = Editor(world)
level_editor = types.SimpleNamespace(on_map_opened=Delegate(), on_map_changed=Delegate())
actors = [
    Actor("Sky", "SkyLight", root),
    Actor("Atmosphere", "SkyAtmosphere", root),
    Actor("Cloud", "VolumetricCloud", root),
    Actor("Sphere", "BP_Sky_Sphere_C", root),
    Actor("Klara Sun", "DirectionalLight", "/Game/L_KK_children"),
    Actor("P06 Sun", "DirectionalLight", root),
    Actor("Chair", "StaticMeshActor", root),
]

FAKE = FakeUnreal()
FAKE.UnrealEditorSubsystem = type("UnrealEditorSubsystem", (), {})
FAKE.LevelEditorSubsystem = type("LevelEditorSubsystem", (), {})
FAKE.Actor = Actor
FAKE.Paths = types.SimpleNamespace(project_dir=lambda: str(HERE.parent.parent) + os.sep,
                                   convert_relative_path_to_full=lambda value: value)
FAKE.dirty_content, FAKE.dirty_maps = [], []
FAKE.EditorLoadingAndSavingUtils = types.SimpleNamespace(
    get_dirty_content_packages=lambda: list(FAKE.dirty_content),
    get_dirty_map_packages=lambda: list(FAKE.dirty_maps),
)
FAKE.GameplayStatics = types.SimpleNamespace(get_all_actors_of_class=lambda _w, _c: list(actors))
levels = [Level(root)]
FAKE.EditorLevelUtils = types.SimpleNamespace(get_levels=lambda _w: list(levels))
FAKE.get_editor_subsystem = lambda cls: level_editor if cls is FAKE.LevelEditorSubsystem else editor
FAKE.logs, FAKE.errors, FAKE.ticks = [], [], {}
FAKE.log = FAKE.logs.append
FAKE.log_error = FAKE.errors.append


def register_tick(callback):
    handle = "H%d" % (len(FAKE.ticks) + 1)
    FAKE.ticks[handle] = callback
    return handle


FAKE.register_slate_post_tick_callback = register_tick
FAKE.unregister_slate_post_tick_callback = lambda handle: FAKE.ticks.pop(handle, None)


# Pure positive controls.
eq("skylight", M.classify_actor("SkyLight", root, root), "skylight")
eq("atmosphere", M.classify_actor("SkyAtmosphere", root, root), "atmosphere")
eq("cloud", M.classify_actor("VolumetricCloud", root, root), "cloud")
eq("sphere", M.classify_actor("BP_Sky_Sphere_C", root, root), "sky-sphere")
eq("streamed sun", M.classify_actor("DirectionalLight", "/Game/Klara", root), "streamed-sun")

# Negative controls: persistent sun and unrelated actors survive.
eq("persistent sun kept", M.classify_actor("DirectionalLight", root, root), None)
eq("mesh kept", M.classify_actor("StaticMeshActor", root, root), None)
check("default enabled", M.switch_enabled({}))
for value in ("0", "false", "OFF", "disabled"):
    check("env disables " + value, not M.switch_enabled({M.ENV_SWITCH: value}))
check("flag disables", not M.switch_enabled({}, flag_exists=True))

# Live-shaped positive control: exact targets, transient read-back, unchanged census.
M.unreal = FAKE
report = M.hide_now("harness")
eq("hidden count", len(report["hidden"]), 5)
check("target actors hidden", all(a.hidden for a in actors[:5]))
check("persistent sun visible", not actors[5].hidden)
check("chair visible", not actors[6].hidden)
eq("census unchanged", report["census_before"], report["census_after"])

# Delegate/install positive control and idempotence negative control.
M._INSTALLED = False
M._TICK_HANDLE = None
M._WATCH_HANDLE = None
M._LAST_LEVELS = None
M._PENDING_REASONS.clear()
check("install", M.install())
eq("map opened delegate", len(level_editor.on_map_opened.calls), 1)
eq("map changed delegate", len(level_editor.on_map_changed.calls), 1)
check("startup queued", "editor-start" in M._PENDING_REASONS)
check("one shot tick", M._TICK_HANDLE in FAKE.ticks)
check("level watcher tick", M._WATCH_HANDLE in FAKE.ticks)
check("idempotent install refuses", not M.install())

# Streamed-level fallback control: a changed level set queues a deferred pass.
M._PENDING_REASONS.clear()
levels.append(Level("/Game/L_KK_children"))
M._watch_levels(0.5)
check("stream level watcher queues", "streamed-level-set-changed" in M._PENDING_REASONS)

# PIE negative control.
editor.game = object()
pie = M.hide_now("pie")
check("pie ignored", pie.get("pie_ignored") is True)
editor.game = None

# Dirty-package negative control catches a hypothetical non-transient implementation.
bad = Actor("Bad Sky", "SkyLight", root, dirties=True)
actors.append(bad)
caught = False
try:
    M.hide_now("dirty-negative")
except RuntimeError as exc:
    caught = "DIRTIED" in str(exc)
check("dirty mutation caught", caught)
actors.pop()
FAKE.dirty_content.clear()

print("P18_EDITOR_SKY_AUTOHIDE_TESTS|pass=%d|fail=%d" % (passed, failed))
raise SystemExit(1 if failed else 0)
