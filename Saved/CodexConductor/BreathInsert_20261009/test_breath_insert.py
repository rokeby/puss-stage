"""Offline fake-Unreal controls for P45 breath_insert.py."""

import copy
import importlib.util
import json
import os
import tempfile
import traceback


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("breath_insert", os.path.join(HERE, "breath_insert.py"))
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

TICK = 24000
PASSAGE_GUID = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
PACKAGES = [
    "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show",
    "/Game/InfinityStage/Dev/LS_InfinityStage_Master",
    "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice",
    "/Game/InfinityStage/Choreo/LS_Passage_01_Choreo",
    "/Game/InfinityStage/Music/DA_BreathRenderedAnalysis",
    "/Game/InfinityStage/Render/LS_RenderWrapper",
]


def channel(keys=None):
    return copy.deepcopy(keys or [])


def section(start, end, cls="MovieSceneFloatTrack", keys=None, index=0):
    return {"class": cls, "range": [start, end], "channels": [
        {"name": "Value", "keys": copy.deepcopy(keys or [])}],
        "locator": {"track": 0, "section": index}}


def fixture_snapshot():
    duration = 90 * TICK
    f = int(duration * 0.4)
    channels = {name: channel([[f - 1000, 1.0], [f + 1000, 1.0]]) for name in TOOL.CHANNELS}
    channels["Camera.YawDegrees"] = [[f - 1000, 0.0], [f + 1000, 2.0]]
    channels["Camera.PitchDegrees"] = [[f - 1000, 0.0], [f + 1000, -1.0]]
    return {
        "tick_resolution": TICK,
        "display_rate": 25,
        "passages": [
            {"guid": PASSAGE_GUID, "label": "Passage 01", "start": 0, "end": duration,
             "linear_spans": [
                 {"kind": "lead_in", "index": 0, "start": 0, "end": 10*TICK, "duration": 10*TICK,
                  "wing_before_guid": "START", "wing_after_guid": "W1"},
                 {"kind": "interval", "index": 0, "start": 10*TICK, "end": 30*TICK, "duration": 20*TICK,
                  "wing_before_guid": "W1", "wing_after_guid": "W2"},
                 {"kind": "interval", "index": 1, "start": 30*TICK, "end": 50*TICK, "duration": 20*TICK,
                  "wing_before_guid": "W2", "wing_after_guid": "W3"},
                 {"kind": "interval", "index": 2, "start": 50*TICK, "end": 70*TICK, "duration": 20*TICK,
                  "wing_before_guid": "W3", "wing_after_guid": "W4"},
                 {"kind": "tail", "index": 0, "start": 70*TICK, "end": duration, "duration": 20*TICK,
                  "wing_before_guid": "W4", "wing_after_guid": "END"},
             ]},
            {"guid": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", "label": "Passage 02",
             "start": duration + TICK, "end": duration + 61*TICK, "linear_spans": []},
        ],
        "passage_sections": {
            PASSAGE_GUID: {"range": [0, duration], "channels": channels,
                           "pinned_passage_frames": [5*TICK, 45*TICK],
                           "pinned_wing_cue_guids": ["W1"]}
        },
        "master": {
            "playback": [0, duration + 61*TICK],
            "root_tracks": [
                {"classification": "master_managed", "class": "MovieSceneInfinityPassageTrack",
                 "sections": []},
                {"classification": "master_artist_root", "class": "MovieSceneFloatTrack",
                 "sections": [section(f - 2000, f + 2000, keys=[[f - 100, 0.2], [f + 100, 0.8]])]},
            ],
            "binding_tracks": [
                {"classification": "master_artist_binding", "class": "MovieSceneBoolTrack",
                 "sections": [section(f + 5000, f + 10000, keys=[[f + 6000, 1.0]])]},
            ],
            "camera_cuts": [dict(section(f + 20000, f + 40000, "MovieSceneCameraCutTrack"),
                                 classification="master_camera_cut")],
            "markers": [{"classification": "master_marker", "label": "after", "frame": f + 100, "locked": False}],
            "managed_sections": [
                {"classification": "master_managed", "passage_guid": PASSAGE_GUID, "range": [0, duration]},
                {"classification": "later_passage_managed", "passage_guid": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
                 "range": [duration + TICK, duration + 61*TICK]},
            ],
        },
        "changed_choreo": {
            "package": PACKAGES[3], "playback": [0, duration],
            "tracks": [{"classification": "changed_choreo_track", "class": "MovieSceneFloatTrack",
                        "sections": [section(f - 500, f + 500, keys=[[f - 50, 1.0], [f + 50, 2.0]])]}],
            "markers": [{"classification": "changed_choreo_marker", "label": "GO look", "frame": f + 200,
                         "locked": False}],
        },
        "mechanism_origins": [
            {"classification": "mechanism_origin", "cue_guid": "W3", "explicit": True, "frame": f + 300}],
        "cue_rows": [
            {"classification": "cue_at_go", "row_id": "P01-LOOK", "passage_guid": PASSAGE_GUID,
             "at_frame": f + 400, "go_frame": f + 450},
            {"classification": "cue_at_go", "row_id": "P02-LOCAL", "passage_guid": "BBBB", "at_frame": 20,
             "go_frame": 25},
        ],
        "managed_music": {"classification": "managed_music", "sound": "/Game/OldSound",
                          "analysis": "/Game/OldAnalysis", "sections": [[0, duration]],
                          "import_validation": {"sound": "/Game/InfinityStage/Music/SW_BreathRendered",
                          "analysis": "/Game/InfinityStage/Music/DA_BreathRenderedAnalysis",
                          "audio_record_run": "AUDIO-SYNTH-6S", "rendered_wav_sha256": "a" * 64,
                          "analysis_source_wav_sha256": "a" * 64, "stale": False}},
        "render_wrapper": {"package": "/Game/InfinityStage/Render/LS_RenderWrapper",
                           "playback": [0, duration + 61*TICK],
                           "source_sections": [{"range": [0, duration + 61*TICK],
                                                "locator": {"package": PACKAGES[5], "host": "root",
                                                            "binding_guid": "", "track_index": 0,
                                                            "section_index": 0}}],
                           "cuts": [dict(section(f + 1000, f + 2000, "MovieSceneCameraCutTrack"),
                                         classification="render_wrapper_cut")]},
        "existing_breaths": [],
        "holders": [{"classification": name} for name in sorted(TOOL.KNOWN_HOLDERS)],
    }


def audio_record(delta_s=6.0):
    samples = int(round(delta_s * 48000))
    return {"schema_version": 1, "tool": "breath_audio", "mode": "APPLY", "status": "passed",
            "run_id": "AUDIO-SYNTH-6S", "timing": {"sample_rate_hz": 48000,
            "output_length_delta_samples": samples, "output_length_delta_seconds": delta_s},
            "target_after": {"C:/synthetic/rendered.wav": {"sha256": "a" * 64}}}


def write_audio(root, delta_s=6.0):
    path = os.path.join(root, "audio_apply_record.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(audio_record(delta_s), handle)
    return path


def params(root, **updates):
    value = {
        "passage_guid": PASSAGE_GUID,
        "passage_offset_frame": int(90 * TICK * 0.4),
        "insert_frames": 6 * TICK,
        "audio_apply_record": write_audio(root),
        "look_yaw_degrees": 12.0,
        "look_pitch_degrees": -4.0,
        "ease_frames": TICK,
        "changed_choreo_policy": "RIPPLE_CLASSIFIED",
        "show_package": PACKAGES[0], "master_package": PACKAGES[1], "level_package": PACKAGES[2],
        "choreo_package": PACKAGES[3], "music_package": PACKAGES[4],
        "render_wrapper_package": PACKAGES[5],
        "rendered_sound_path": "/Game/InfinityStage/Music/SW_BreathRendered",
        "analysis_map_path": "/Game/InfinityStage/Music/DA_BreathRenderedAnalysis",
    }
    value.update(updates)
    return value


def f32_tree(value):
    if isinstance(value, dict):
        return {key: f32_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [f32_tree(item) for item in value]
    return TOOL.f32(value) if isinstance(value, float) else value


class FakeBackend(object):
    def __init__(self, snapshot=None):
        self.state = copy.deepcopy(snapshot or fixture_snapshot())
        self.pie = False
        self.dirty = {"content": [], "maps": []}
        self.logs = []
        self.events = []

    def log(self, text):
        self.logs.append(text)

    def stop(self, text):
        self.logs.append(text)

    def census(self):
        return copy.deepcopy(self.dirty)

    def preflight(self, args, mode):
        if self.pie:
            raise TOOL.PlanError("PIE_OR_SIE_ACTIVE")
        if self.dirty != {"content": [], "maps": []}:
            raise TOOL.PlanError("DIRTY_CENSUS|%s" % self.dirty)

    def inspect(self, args):
        return copy.deepcopy(self.state)

    def backup(self, run, packages, prefix="PreBreathInsert"):
        self.events.append("backup")
        return {"root": "FAKE/Backups/%s-%s" % (prefix, run),
                "files": [{"package": p, "sha256": "fake", "bytes": 1} for p in packages]}

    def apply(self, plan, args):
        if self.events != ["backup"]:
            raise AssertionError("mutation must follow backup")
        self.events.append("apply")
        self.state = f32_tree(plan["after_snapshot"])
        self.dirty = {"content": list(PACKAGES[:-1]), "maps": [PACKAGES[-1]]}
        return {"edits": len(plan["edits"])}

    def save(self, packages):
        if sorted(set(self.dirty["content"] + self.dirty["maps"])) != sorted(packages):
            raise TOOL.PlanError("FAKE_SAVE_SCOPE")
        self.events.append("save")
        self.dirty = {"content": [], "maps": []}
        return list(packages)

    def revert(self, record, args):
        if not self.events or self.events[-1] != "backup":
            raise AssertionError("revert must follow backup")
        self.events.append("revert")
        self.state = copy.deepcopy(record["snapshot_before"])
        self.dirty = {"content": list(PACKAGES[:-1]), "maps": [PACKAGES[-1]]}


def call_args(mode, run, p, source=None):
    confirm = ("REVERT BREATH %s" % source) if mode == "REVERT" else ("%s BREATH %s" % (mode, run))
    value = {"mode": mode, "run_id": run, "confirm": confirm, "params": p}
    if source:
        value["source_run_id"] = source
    return value


def expect_stop(function, text):
    try:
        function()
    except TOOL.Stop as error:
        if text not in str(error):
            raise AssertionError("wanted %r in %s" % (text, error))
        return
    except TOOL.PlanError as error:
        if text not in str(error):
            raise AssertionError("wanted %r in %s" % (text, error))
        return
    raise AssertionError("expected refusal containing %r" % text)


def positive_synthetic_plan():
    root = tempfile.mkdtemp(prefix="breath-plan-")
    plan = TOOL.build_plan(fixture_snapshot(), audio_record(), params(root))
    assert plan["F"] == int(90 * TICK * 0.4)
    assert plan["D"] == 6 * TICK
    assert plan["containing_span"]["wing_before_guid"] == "W2"
    assert plan["bounding_wing_pins"] == ["W2", "W3"]
    assert plan["later_passage_carry"] == "MANAGED_REBUILD_ONLY_NO_DOUBLE_SHIFT"
    speed = plan["after_snapshot"]["passage_sections"][PASSAGE_GUID]["channels"]["Camera.SpeedMultiplier"]
    for row in [[plan["F"], 0.0], [plan["F"] + plan["D"], 0.0]]:
        assert row in speed
    preview = TOOL.write_preview(plan, HERE, "synthetic_90s_40pct_6s")
    assert os.path.getsize(preview) > 500


def positive_round_trip():
    root = tempfile.mkdtemp(prefix="breath-roundtrip-")
    env, p = FakeBackend(), params(root)
    original = copy.deepcopy(env.state)
    report = TOOL.main(call_args("DRY", "SYNTH-DRY", p), backend=env, tool_root=root)
    assert os.path.getsize(report["preview"]) > 500
    TOOL.main(call_args("APPLY", "SYNTH-APPLY", p), backend=env, tool_root=root)
    assert env.events == ["backup", "apply", "save"]
    assert env.state != original
    env.events = []
    TOOL.main(call_args("REVERT", "SYNTH-REVERT", p, "SYNTH-APPLY"), backend=env, tool_root=root)
    assert env.state == original
    assert env.events == ["backup", "revert", "save"]
    assert any("P36_BREATH_REVERT_OK" in text for text in env.logs)


def negative_pie():
    root = tempfile.mkdtemp(); env = FakeBackend(); env.pie = True; p = params(root)
    expect_stop(lambda: TOOL.main(call_args("DRY", "NEG-PIE", p), backend=env, tool_root=root), "PIE_OR_SIE_ACTIVE")


def negative_dirty():
    root = tempfile.mkdtemp(); env = FakeBackend(); env.dirty = {"content": ["/Game/Foreign"], "maps": []}; p = params(root)
    expect_stop(lambda: TOOL.main(call_args("DRY", "NEG-DIRTY", p), backend=env, tool_root=root), "DIRTY_CENSUS")


def negative_f_outside():
    root = tempfile.mkdtemp(); p = params(root, passage_offset_frame=90*TICK)
    expect_stop(lambda: TOOL.build_plan(fixture_snapshot(), audio_record(), p), "F_OUTSIDE_PASSAGE")


def negative_d_mismatch():
    root = tempfile.mkdtemp(); p = params(root, insert_frames=5*TICK)
    expect_stop(lambda: TOOL.build_plan(fixture_snapshot(), audio_record(), p), "D_MISMATCH")


def negative_straddling_subsection():
    root = tempfile.mkdtemp(); snap = fixture_snapshot(); f = int(90*TICK*0.4)
    snap["changed_choreo"]["tracks"][0]["sections"][0]["class"] = "MovieSceneSubTrack"
    expect_stop(lambda: TOOL.build_plan(snap, audio_record(), params(root)), "STRADDLING_SUB_SECTION")


def negative_existing_breath():
    root = tempfile.mkdtemp(); snap = fixture_snapshot(); f = int(90*TICK*0.4)
    snap["existing_breaths"] = [{"start": f - 1, "end": f + 20}]
    expect_stop(lambda: TOOL.build_plan(snap, audio_record(), params(root)), "EXISTING_BREATH_OVERLAP")


def negative_unknown_holder():
    root = tempfile.mkdtemp(); snap = fixture_snapshot(); snap["holders"].append({"classification": "mystery"})
    expect_stop(lambda: TOOL.build_plan(snap, audio_record(), params(root)), "UNKNOWN_HOLDER")


def negative_locked_marker():
    root = tempfile.mkdtemp(); snap = fixture_snapshot(); snap["master"]["markers"][0]["locked"] = True
    expect_stop(lambda: TOOL.build_plan(snap, audio_record(), params(root)), "LOCKED_MARKER")


def negative_confirm():
    root = tempfile.mkdtemp(); env = FakeBackend(); p = params(root)
    raw = call_args("DRY", "NEG-CONFIRM", p); raw["confirm"] = "yes"
    expect_stop(lambda: TOOL.main(raw, backend=env, tool_root=root), "CONFIRM_MISMATCH")


CASES = [
    ("+ synthetic 90s Passage, F=40%, D=6s plans exactly", positive_synthetic_plan),
    ("+ DRY -> APPLY -> REVERT fake round trip is exact", positive_round_trip),
    ("- PIE running refuses", negative_pie),
    ("- dirty census refuses", negative_dirty),
    ("- F outside Passage refuses", negative_f_outside),
    ("- D mismatch refuses", negative_d_mismatch),
    ("- straddling sub-section refuses", negative_straddling_subsection),
    ("- existing breath overlap refuses", negative_existing_breath),
    ("- unknown holder refuses", negative_unknown_holder),
    ("- locked marker refuses", negative_locked_marker),
    ("- wrong confirm refuses", negative_confirm),
]


def main():
    rows = []
    for name, function in CASES:
        try:
            function()
            rows.append({"name": name, "status": "PASS"})
            print("PASS|" + name)
        except Exception as error:  # noqa: BLE001
            rows.append({"name": name, "status": "FAIL", "error": repr(error), "trace": traceback.format_exc()})
            print("FAIL|%s|%s" % (name, error))
    positive = [r for r in rows if r["name"].startswith("+")]
    negative = [r for r in rows if r["name"].startswith("-")]
    result = {"schema_version": 1, "tool": TOOL.TOOL, "results": rows,
              "positive": {"passed": sum(r["status"] == "PASS" for r in positive), "total": len(positive)},
              "negative": {"passed": sum(r["status"] == "PASS" for r in negative), "total": len(negative)},
              "proof": "measured-offline fake backend; no Unreal/editor/rendered acceptance"}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    marker = "BREATH_INSERT_HARNESS_%s|positive=%d/%d|negative=%d/%d" % (
        "OK" if all(r["status"] == "PASS" for r in rows) else "FAILED",
        result["positive"]["passed"], result["positive"]["total"],
        result["negative"]["passed"], result["negative"]["total"])
    print(marker)
    return 0 if all(r["status"] == "PASS" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
