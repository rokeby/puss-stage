"""Offline +/- controls for scene_camera_owner_apply.py (stub ``unreal``).

Run:  python Saved/CodexConductor/test_scene_camera_owner_apply.py
Every positive has a negative that must stop for the stated reason, and the
guards themselves get a negative control (disable the guard -> tamper passes),
so a green run means the checks can fail.

What this proves is the tool's LOGIC against a stub whose copy semantics,
export_text format and enum spelling are modelled on the 30 Sep measured run;
it does NOT prove the real Unreal wrapper behaves the same (see the report).
"""
from __future__ import annotations

import copy
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "scene_camera_owner_apply_under_test", os.path.join(HERE, "scene_camera_owner_apply.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # unreal absent -> main() not run
    assert module.unreal is None
    return module


# ------------------------------------------------------------------ stub types
def camel(name):
    return "".join(part[:1].upper() + part[1:] for part in name.split("_"))


class EnumMember:
    def __init__(self, enum, name, ue_name, value):
        self.enum, self.name, self.ue_name, self.value = enum, name, ue_name, value

    def __repr__(self):
        return "<%s.%s: %d>" % (self.enum, self.name, self.value)

    def __deepcopy__(self, memo):
        return self  # enum members are singletons


def make_enum(enum_name, pairs):
    namespace = types.SimpleNamespace()
    for value, (name, ue_name) in enumerate(pairs):
        setattr(namespace, name, EnumMember(enum_name, name, ue_name, value))
    return namespace


class Guid:
    def __init__(self, text):
        self.text = text

    def export_text(self):
        return self.text


def export_value(value):
    if isinstance(value, EnumMember):
        return value.ue_name
    if hasattr(value, "export_text"):
        return value.export_text()
    if isinstance(value, list):
        return "(" + ",".join(export_value(v) for v in value) + ")"
    if isinstance(value, str):
        return '"%s"' % value
    return repr(value)


class Struct:
    """Copy-on-get / copy-on-set, like UE Python struct properties."""

    def __init__(self, type_name, **fields):
        self._type, self._fields = type_name, dict(fields)

    def get_editor_property(self, name):
        if name not in self._fields:
            raise AttributeError("no property " + name)
        return copy.deepcopy(self._fields[name])

    def set_editor_property(self, name, value):
        if name not in self._fields:
            raise AttributeError("no property " + name)
        self._fields[name] = copy.deepcopy(value)

    def export_text(self):
        return "(" + ",".join("%s=%s" % (camel(k), export_value(v)) for k, v in self._fields.items()) + ")"


class NoExportStruct(Struct):
    export_text = None


class LyingExportStruct(Struct):
    """Exports Timeline whatever the property holds (format-assumption fault)."""

    def export_text(self):
        return re.sub(r"CameraOwner=\w+", "CameraOwner=Timeline", Struct.export_text(self))


class Show:
    def __init__(self, env, **fields):
        self._env, self._fields, self.reads = env, dict(fields), []

    def get_editor_property(self, name):
        self.reads.append(name)
        if name not in self._fields:
            raise AttributeError("no property " + name)
        return copy.deepcopy(self._fields[name])

    def set_editor_property(self, name, value):
        self._fields[name] = copy.deepcopy(value)
        self._env.dirty_content.add(SHOW_PATH)
        for hook in self._env.on_set:
            hook(self, name)

    def get_path_name(self):
        return SHOW_PATH + ".DA_InfinityStage_V1Show"


def dump(value, path=""):
    """Flat {path: leaf} map of every stub field (for exact diffs)."""
    out = {}
    if isinstance(value, (Struct, Show)):
        for key, child in value._fields.items():
            out.update(dump(child, "%s.%s" % (path, key) if path else key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            out.update(dump(child, "%s[%d]" % (path, index)))
    elif isinstance(value, Guid):
        out[path] = value.text
    elif isinstance(value, EnumMember):
        out[path] = repr(value)
    else:
        out[path] = value
    return out


def diff(before, after):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


# ------------------------------------------------------------------ environment
TARGETS = [
    ("91030A272145EBEF25D33BA016458739", "Scene 1 — External Sound"),
    ("42D2F59416487AF7018DAEB62639C9BB", "Scene 2 — External Sound"),
    ("D8F61D9DF94F1E6080CC8D9028EE49D3", "Scene 3 — External Sound"),
    ("5C960C0C7A462BFEA4C86F93ADF5558D", "Scene 4 — External Sound"),
    ("730D67269F425DDC45C72A867BA04217", "Scene 5 — External Sound"),
    ("673B3535884DEBAE99723B8CC6BE877B", "Scene 6 — External Sound"),
]


class Env:
    def __init__(self, mod, struct_cls=Struct):
        self.mod = mod
        self.tmp = tempfile.mkdtemp(prefix="scene_owner_harness_")
        self.dirty_content, self.dirty_maps = set(), set()
        self.pie = False
        self.on_set = []
        self.logs, self.errors, self.saves, self.forbidden = [], [], [], []
        self.u = self._make_unreal()
        self.struct_cls = struct_cls
        self.show = self._make_show()
        os.makedirs(os.path.join(self.tmp, "Content", "InfinityStage", "Dev"))
        self._write_show_file()
        mod.unreal = self.u
        mod.EXPECTED_PROJECT = os.path.normcase(os.path.normpath(self.tmp))
        mod.REPORT_PATH = os.path.join(self.tmp, "Saved", "report.json")
        mod.RECORD_PATH = os.path.join(self.tmp, "Saved", "record.json")

    # -- show fixture
    def scene(self, owner):
        S = self.struct_cls
        return S("InfinitySceneCueData", sequence="/Game/Seq", use_sequence_length=False,
                 duration_frames=24000, external_sound=self.u.InfinityExternalSoundAuthority.NONE,
                 camera_owner=owner,
                 music=S("InfinitySectionMusicBinding", rail_offset_frames=0),
                 exit_handoff_hold_frames=24000, retain_previous_camera=False)

    def cue(self, guid, kind, label, owner=None):
        S = self.struct_cls
        owner = owner or self.u.InfinityCameraOwner.TIMELINE
        return S("InfinityShowCue", cue_guid=Guid(guid), type=kind, label=label, enabled=True, tags=[],
                 wing_pair=S("InfinityWingOccurrence", occurrence_offset=0.0), scene=self.scene(owner))

    def _make_show(self):
        T = self.u.InfinityCueType
        O = self.u.InfinityCameraOwner
        cues = [self.cue("A0" * 16, T.SEQUENCE, "Opening — Curtain")]
        n = 1
        for guid, label in TARGETS:
            cues.append(self.cue("%032X" % n, T.WING_PAIR, "Wing %d" % n)); n += 1
            cues.append(self.cue(guid, T.SCENE, label, O.DOG_FREE_LOOK))
            cues.append(self.cue("%032X" % (1000 + n), T.SEQUENCE, "Interaction %d" % n,
                                 O.TIMELINE)); n += 1
        passages = [Struct("InfinityPassageSettings", passage_guid=Guid("%032X" % (500 + i)),
                           camera_owner=O.DOG_GAZE_ONLY) for i in range(6)]
        return Show(self, show_guid=Guid("F" * 32), display_rate=Struct("FrameRate", numerator=30, denominator=1),
                    tick_resolution=Struct("FrameRate", numerator=24000, denominator=1), cues=cues,
                    passage_settings=passages, music_rails=[Struct("InfinityMusicRail", label="Rail")],
                    managed_master_sequence="MASTER_MUST_NOT_BE_READ", wing_library="LIB", schema_version=1)

    def show_file(self):
        return os.path.join(self.tmp, "Content", "InfinityStage", "Dev", "DA_InfinityStage_V1Show.uasset")

    def _write_show_file(self):
        with open(self.show_file(), "w", encoding="utf-8") as handle:
            handle.write(repr(sorted(dump(self.show).items())))

    # -- unreal stub
    def _make_unreal(self):
        env = self
        u = types.ModuleType("unreal")
        u.InfinityCameraOwner = make_enum("InfinityCameraOwner", [
            ("TIMELINE", "Timeline"), ("DOG_FREE_LOOK", "DogFreeLook"), ("DOG_GAZE_ONLY", "DogGazeOnly")])
        u.InfinityCueType = make_enum("InfinityCueType", [
            ("WING_PAIR", "WingPair"), ("SCENE", "Scene"), ("SEQUENCE", "Sequence")])
        u.InfinityExternalSoundAuthority = make_enum("InfinityExternalSoundAuthority", [("NONE", "None")])

        class Pkg:
            def __init__(self, path):
                self.path = path

            def get_path_name(self):
                return self.path

        class World:
            def get_path_name(self):
                return WORLD + "." + WORLD.rsplit("/", 1)[1]

        u.Paths = types.SimpleNamespace(
            project_dir=lambda: env.tmp + "/",
            project_content_dir=lambda: os.path.join(env.tmp, "Content") + "/",
            convert_relative_path_to_full=lambda p: p)
        editor = types.SimpleNamespace(
            get_game_world=lambda: object() if env.pie else None,
            get_editor_world=lambda: World())
        u.UnrealEditorSubsystem = "UnrealEditorSubsystem"
        u.LevelEditorSubsystem = "LevelEditorSubsystem"
        level_editor = types.SimpleNamespace(
            save_current_level=lambda: env.forbidden.append("save_current_level") or True,
            editor_request_end_play=lambda: env.forbidden.append("end_play"))
        u.get_editor_subsystem = lambda cls: editor if cls == "UnrealEditorSubsystem" else level_editor
        u.LevelSequenceEditorBlueprintLibrary = types.SimpleNamespace(get_current_level_sequence=lambda: None)
        u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
            get_dirty_content_packages=lambda: [Pkg(p) for p in env.dirty_content],
            get_dirty_map_packages=lambda: [Pkg(p) for p in env.dirty_maps],
            save_dirty_packages=lambda *a, **k: env.forbidden.append("save_all"),
            load_map=lambda *a, **k: env.forbidden.append("load_map"))

        def save_asset(path, only_if_is_dirty=True):
            env.saves.append(path)
            if path == SHOW_PATH:
                env._write_show_file()
                env.dirty_content.discard(SHOW_PATH)
            return True

        u.EditorAssetLibrary = types.SimpleNamespace(
            load_asset=lambda path: env.show if path == SHOW_PATH else None,
            save_asset=save_asset)
        u.SystemLibrary = types.SimpleNamespace(quit_editor=lambda: env.forbidden.append("quit"))
        u.GuidLibrary = types.SimpleNamespace(conv_guid_to_string=lambda g: g.text)
        u.log = env.logs.append
        u.log_error = env.errors.append
        return u

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ------------------------------------------------------------------ runner
RESULTS = []


def expect_stop(env, mode, reason):
    try:
        env.mod._run(mode)
    except env.mod.SceneCameraOwnerError as error:
        assert reason in str(error), "stopped for %r, wanted %r" % (str(error), reason)
        assert any("SCENE_CAMERA_OWNER_STOPPED|run=" in e for e in env.errors), env.errors
        return str(error)
    raise AssertionError("did not stop; wanted " + reason)


def assert_untouched(env, before):
    assert diff(before, dump(env.show)) == [], diff(before, dump(env.show))
    assert env.saves == [], env.saves
    assert not os.path.exists(os.path.join(env.tmp, "Backups")) or not os.listdir(os.path.join(env.tmp, "Backups"))


def assert_no_forbidden(env):
    assert env.forbidden == [], env.forbidden
    assert "managed_master_sequence" not in env.show.reads and "wing_library" not in env.show.reads


def case(name):
    def wrap(fn):
        def run():
            mod = load_tool()
            env = Env(mod, **getattr(fn, "env_kwargs", {}))
            try:
                fn(mod, env)
                assert_no_forbidden(env)
                RESULTS.append((name, "PASS", ""))
            except Exception as error:  # noqa: BLE001
                RESULTS.append((name, "FAIL", "%s: %s" % (type(error).__name__, error)))
            finally:
                env.cleanup()
        run.__name__ = name
        CASES.append(run)
        return fn
    return wrap


CASES = []
TARGET_OWNER_PATHS = None


def owner_paths(env):
    return sorted("cues[%d].scene.camera_owner" % i for i, c in enumerate(env.show._fields["cues"])
                  if c._fields["cue_guid"].text in {g for g, _ in TARGETS})


# ---- positives
@case("+ DRY reports what it found and mutates nothing")
def _(mod, env):
    before = dump(env.show)
    report = mod._run("DRY")
    assert report["ok"] and report["mutated"] is False
    assert len(report["would_change"]) == 6
    assert all(r["export_token"] == "DogFreeLook" and r["owner_before"] == "DOG_FREE_LOOK"
               for r in report["found"]["targets"])
    assert set(report["found"]["enum_members"]) == {"TIMELINE", "DOG_FREE_LOOK", "DOG_GAZE_ONLY"}
    assert any(l.startswith("SCENE_CAMERA_OWNER_DRY_OK|run=") for l in env.logs), env.logs
    assert_untouched(env, before)


@case("+ APPLY changes exactly the six Scene CameraOwner fields, saves only the Show")
def _(mod, env):
    before = dump(env.show)
    original_file = open(env.show_file(), encoding="utf-8").read()
    report = mod._run("APPLY")
    after = dump(env.show)
    changed = diff(before, after)
    assert changed == owner_paths(env), changed
    assert all(after[p] == "<InfinityCameraOwner.TIMELINE: 0>" for p in changed)
    assert all(before[p] == "<InfinityCameraOwner.DOG_FREE_LOOK: 1>" for p in changed)
    assert env.saves == [SHOW_PATH], env.saves
    assert env.dirty_content == set() and env.dirty_maps == set()
    assert open(env.show_file(), encoding="utf-8").read() != original_file
    root = report["backup"]["root"]
    assert re.search(r"PreSceneCameraOwner-\d{8}-\d{4}$", root), root
    assert open(report["backup"]["backup"], encoding="utf-8").read() == original_file
    assert any(l.startswith("SCENE_CAMERA_OWNER_APPLY_OK|run=%s|changed=6" % report["run"]) for l in env.logs)
    assert mod._read_json(mod.RECORD_PATH)["status"] == "saved_readback_verified"
    # passages (DOG_GAZE_ONLY) untouched
    assert all(after["passage_settings[%d].camera_owner" % i].endswith("DOG_GAZE_ONLY: 2>") for i in range(6))


@case("- diff checker can fail: a seventh changed field is visible")
def _(mod, env):
    before = dump(env.show)
    mod._run("APPLY")
    env.show._fields["cues"][0]._fields["label"] = "tampered"
    assert len(diff(before, dump(env.show))) == 7


@case("+ REVERT restores the pre-apply Show exactly (every field)")
def _(mod, env):
    before = dump(env.show)
    mod._run("APPLY")
    report = mod._run("REVERT")
    assert diff(before, dump(env.show)) == [], diff(before, dump(env.show))
    assert report["after"]["full_hash"] == mod._read_json(report["record_archived"])["before_full_hash"]
    assert env.saves == [SHOW_PATH, SHOW_PATH]
    assert not os.path.exists(mod.RECORD_PATH)
    assert any(l.startswith("SCENE_CAMERA_OWNER_REVERT_OK|run=") for l in env.logs)


@case("+ REVERT exact with a mixed before-state (S3 already Timeline, S6 Gaze)")
def _(mod, env):
    O = env.u.InfinityCameraOwner
    cues = env.show._fields["cues"]
    for c in cues:
        if c._fields["label"].startswith("Scene 3"):
            c._fields["scene"]._fields["camera_owner"] = O.TIMELINE
        if c._fields["label"].startswith("Scene 6"):
            c._fields["scene"]._fields["camera_owner"] = O.DOG_GAZE_ONLY
    before = dump(env.show)
    report = mod._run("APPLY")
    assert len(report["changed"]) == 5, report["changed"]
    mod._run("REVERT")
    assert diff(before, dump(env.show)) == []


@case("+ APPLY on an already-Timeline Show is a NOOP: no backup, no save")
def _(mod, env):
    for c in env.show._fields["cues"]:
        c._fields["scene"]._fields["camera_owner"] = env.u.InfinityCameraOwner.TIMELINE
    before = dump(env.show)
    report = mod._run("APPLY")
    assert report["noop"] is True
    assert any("APPLY_NOOP" in l for l in env.logs) and not any("APPLY_OK" in l for l in env.logs)
    assert_untouched(env, before)


# ---- negatives
@case("- wrong GUID refuses before any backup or write")
def _(mod, env):
    before = dump(env.show)
    targets = [dict(t) for t in mod.TARGETS]
    targets[2]["guid"] = "D8F61D9DF94F1E6080CC8D9028EE49D4"
    mod.TARGETS = tuple(targets)
    expect_stop(env, "APPLY", "TARGET_GUID_MISSING|guid=D8F61D9DF94F1E6080CC8D9028EE49D4")
    assert_untouched(env, before)
    assert not os.path.exists(mod.RECORD_PATH)


@case("- label drift on a correct GUID refuses")
def _(mod, env):
    before = dump(env.show)
    for c in env.show._fields["cues"]:
        if c._fields["label"].startswith("Scene 4"):
            c._fields["label"] = "Scene 4 — Renamed"
    before = dump(env.show)
    expect_stop(env, "APPLY", "TARGET_LABEL_DRIFT")
    assert_untouched(env, before)


@case("- a seventh Scene cue refuses (scene set drift)")
def _(mod, env):
    env.show._fields["cues"].append(env.cue("7" * 32, env.u.InfinityCueType.SCENE, "Scene 7"))
    before = dump(env.show)
    expect_stop(env, "DRY", "SCENE_SET_DRIFT")
    assert_untouched(env, before)


def _tamper_other_cue(show, name):
    if name == "cues":
        show._fields["cues"][0]._fields["label"] = "Opening — TAMPERED"


def _tamper_target_other_field(show, name):
    if name == "cues":
        for c in show._fields["cues"]:
            if c._fields["label"].startswith("Scene 2"):
                c._fields["scene"]._fields["duration_frames"] = 1


@case("- outside hash catches a tampered non-target cue; rolled back, nothing saved")
def _(mod, env):
    env.on_set.append(_tamper_other_cue)
    expect_stop(env, "APPLY", "APPLY_MEMORY_OUTSIDE_HASH_CHANGED")
    assert env.saves == []
    owners = [c._fields["scene"]._fields["camera_owner"].name for c in env.show._fields["cues"]
              if c._fields["cue_guid"].text in {g for g, _ in TARGETS}]
    assert owners == ["DOG_FREE_LOOK"] * 6, owners
    assert not os.path.exists(mod.RECORD_PATH)
    assert any(".failed-" in f for f in os.listdir(os.path.dirname(mod.RECORD_PATH)))


@case("- outside hash catches a non-owner field changed inside a TARGET cue")
def _(mod, env):
    env.on_set.append(_tamper_target_other_field)
    expect_stop(env, "APPLY", "APPLY_MEMORY_OUTSIDE_HASH_CHANGED")
    assert env.saves == []


@case("- guard control: with the outside check disabled the same tamper is SAVED")
def _(mod, env):
    env.on_set.append(_tamper_other_cue)
    mod._require_outside_unchanged = lambda expected, actual, phase: None
    mod._run("APPLY")
    assert env.saves == [SHOW_PATH]
    assert env.show._fields["cues"][0]._fields["label"].endswith("TAMPERED")


@case("- REVERT refuses when the Show changed after APPLY")
def _(mod, env):
    mod._run("APPLY")
    env.show._fields["cues"][0]._fields["label"] = "edited later"
    saves = list(env.saves)
    expect_stop(env, "REVERT", "REVERT_SHOW_CHANGED_SINCE_APPLY")
    assert env.saves == saves


@case("- second APPLY refuses while a revert record is active")
def _(mod, env):
    mod._run("APPLY")
    expect_stop(env, "APPLY", "ACTIVE_REVERT_RECORD_EXISTS")


@case("- wrong enum spelling stops DRY (ENUM_MEMBER_MISSING)")
def _(mod, env):
    delattr(env.u.InfinityCameraOwner, "DOG_FREE_LOOK")
    expect_stop(env, "DRY", "ENUM_MEMBER_MISSING|enum=InfinityCameraOwner|name=DOG_FREE_LOOK")


def _no_export(mod, env):
    before = dump(env.show)
    expect_stop(env, "DRY", "EXPORT_TEXT_MISSING")
    assert_untouched(env, before)


_no_export.env_kwargs = {"struct_cls": NoExportStruct}
case("- missing export_text stops DRY")(_no_export)


def _lying_export(mod, env):
    expect_stop(env, "DRY", "EXPORT_TOKEN_MISMATCH")


_lying_export.env_kwargs = {"struct_cls": LyingExportStruct}
case("- export token disagreeing with the property stops DRY")(_lying_export)


@case("- two CameraOwner tokens in one target cue stop DRY")
def _(mod, env):
    for c in env.show._fields["cues"]:
        if c._fields["label"].startswith("Scene 5"):
            c._fields["wing_pair"]._fields["camera_owner"] = env.u.InfinityCameraOwner.TIMELINE
    expect_stop(env, "DRY", "CAMERA_OWNER_TOKEN_COUNT|count=2")


@case("- PIE active: refused, never ended")
def _(mod, env):
    env.pie = True
    before = dump(env.show)
    expect_stop(env, "APPLY", "PIE_OR_SIE_ACTIVE")
    assert_untouched(env, before)


@case("- dirty package before start refuses")
def _(mod, env):
    env.dirty_content.add("/Game/Other/Asset")
    expect_stop(env, "APPLY", "DIRTY_BEFORE")


@case("- mutation that dirties the map: rolled back, Show not saved, level not saved")
def _(mod, env):
    env.on_set.append(lambda show, name: env.dirty_maps.add(WORLD))
    expect_stop(env, "APPLY", "APPLY_CENSUS_AFTER_MUTATION")
    assert env.saves == []
    owners = {c._fields["scene"]._fields["camera_owner"].name for c in env.show._fields["cues"]
              if c._fields["cue_guid"].text in {g for g, _ in TARGETS}}
    assert owners == {"DOG_FREE_LOOK"}, owners


@case("+ recorded GUIDs/labels match Saved/CodexStructure/arrivals_probe.json")
def _(mod, env):
    import json
    probe = json.load(open(os.path.join(HERE, "..", "CodexStructure", "arrivals_probe.json"), encoding="utf-8"))
    recorded = {(r["guid"], r["label"], r["cue_index"]) for r in probe}
    mine = {(t["guid"], t["label"], t["recorded_index"]) for t in mod.TARGETS}
    assert mine == recorded, mine ^ recorded


def main():
    for run in CASES:
        run()
    width = max(len(n) for n, _, _ in RESULTS)
    for name, status, detail in RESULTS:
        print("%-4s %s %s" % (status, name.ljust(width), detail))
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    print("SCENE_CAMERA_OWNER_HARNESS|pass=%d|fail=%d|total=%d" % (passed, len(RESULTS) - passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
