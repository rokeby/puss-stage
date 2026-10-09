"""Offline positive and negative controls for P33 passages_to_music.py.

Run from the repository root, optionally naming the args file whose contract
must also be checked:
  python -X utf8 Saved/CodexConductor/test_passages_to_music.py [args.json]

No Unreal, MCP, Blender, GPU, source audio, or Content asset is opened.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))


def load_tool():
    path = os.path.join(HERE, "passages_to_music.py")
    spec = importlib.util.spec_from_file_location("passages_to_music_offline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()
assert tool.unreal is None, "offline harness must not load Unreal"

if len(sys.argv) > 2:
    raise SystemExit("usage: test_passages_to_music.py [args.json]")
ARGS_PATH = (os.path.abspath(sys.argv[1]) if len(sys.argv) == 2
             else os.path.join(HERE, "passages_to_music_args.json"))
with open(ARGS_PATH, "r", encoding="utf-8") as handle:
    LIVE_ARGS = json.load(handle)


def isolated_dry_fixture():
    """Own all test inputs; never inherit mutable state from the operator args file."""
    seconds = {"1": 73.516032, "2": 45.51424, "3": 40.217914,
               "4": 48.397664, "5": 42.022472}
    per_passage = {
        key: {"guid": "fixture-guid-" + key, "music_s": value,
              "sound": "/Game/Fixture/SW_P%s" % key, "expected": None}
        for key, value in seconds.items()
    }
    per_passage["6"] = {
        "guid": "fixture-guid-6", "music_s": None, "sound": tool.P06_LIVE_SOUND,
        "duration_source": "LIVE_SOUNDWAVE", "expected": None}
    return {
        "mode": "DRY", "confirm": "DRY PASSAGES TO MUSIC", "run_id": None,
        "passages": list(tool.VALID_KEYS),
        "tail_overrides_s": {key: 0.0 for key in tool.VALID_KEYS},
        "review": {"inventory_sha256": None, "past_end_actions": {}},
        "per_passage": per_passage,
        "decided_by": "offline fixture",
    }


FIXTURE = isolated_dry_fixture()
with open(os.path.join(HERE, "..", "..", "Tools", "MusicAnalysis", "p11_timing_snapshot.json"),
          "r", encoding="utf-8") as handle:
    SNAPSHOT = json.load(handle)

TICK = int(SNAPSHOT["tickRate"])
FPS = (int(SNAPSHOT["displayRate"]), 1)
PASS = 0
FAIL = []
TESTS = []


def check(condition, label):
    global PASS
    if condition:
        PASS += 1
    else:
        FAIL.append(label)


def test(function):
    TESTS.append(function)
    return function


def args(**updates):
    value = copy.deepcopy(FIXTURE)
    value.update(updates)
    return value


def passage_segment(key):
    label = tool.label_of(key)
    label_, start, end = [row for row in SNAPSHOT["segments"] if row[0] == label][0]
    return {"label": label_, "start": int(start), "end": int(end)}


@test
def shipped_args_and_negative_controls():
    check(tool.validate_args(LIVE_ARGS) == [], "selected live args valid in its own mode")
    check(tool.validate_args(FIXTURE) == [], "isolated DRY fixture valid")
    check(any("MODE" in x for x in tool.validate_args(args(mode="GO"))), "negative invalid mode")
    check(any("ALL_SIX" in x for x in tool.validate_args(args(passages=["1"]))), "negative partial set")
    bad = args()
    bad["tail_overrides_s"]["5"] = -1
    check(any("TAIL_OVERRIDE" in x for x in tool.validate_args(bad)), "negative tail override")
    bad = args(mode="APPLY", confirm="APPLY PASSAGES TO MUSIC")
    errors = tool.validate_args(bad)
    missing = [row for row in errors if row.startswith("EXPECTED_")]
    check(len(missing) == len(tool.VALID_KEYS) * 3 and "REVIEW_HASH_MISSING" in errors,
          "negative APPLY without DRY numbers")
    apply = args(mode="APPLY", confirm="APPLY PASSAGES TO MUSIC")
    apply["review"]["inventory_sha256"] = "abc"
    for key in tool.VALID_KEYS:
        apply["per_passage"][key]["expected"] = {"old_len_ticks": 1, "new_len_ticks": 2, "music_ticks": 3}
    check(tool.validate_args(apply) == [], "positive APPLY args contract")
    apply["decided_by"] = ""
    check(any("DECIDED_BY" in x for x in tool.validate_args(apply)), "negative missing decision owner")


@test
def music_targets_are_exact_display_frames():
    expected = {"1": 1764480, "2": 1092480, "3": 965760, "4": 1161600, "5": 1008960, "6": 2654400}
    for key, want in expected.items():
        live_duration = 110.561125 if key == "6" else None
        seconds = tool.selected_music_seconds(key, FIXTURE["per_passage"][key], live_duration)
        got = tool.target_ticks(seconds, 0.0, TICK, *FPS)
        check(got == want, "P%s selected music target %d == %d" % (key, got, want))
        check(got % 960 == 0, "P%s target on 25 fps frame" % key)
    check(tool.target_ticks(42.022472, 1.0, TICK, *FPS) == 1032960, "positive explicit one-second override")


@test
def proportional_plan_and_residual():
    plan = tool.plan_scaled_timing(100, [200, 300, 400], 150, 1000)
    check(plan["new_ticks"] == 1000, "scaled plan exact")
    check(tool.compiled_length(plan["lead_frames"], plan["intervals"], plan["tail_frames"]) == 1000,
          "compiled length exact")
    check(plan["k"] == 1000 / 750.0, "one proportional scale factor")
    try:
        tool.plan_scaled_timing(1, [], 1, 10)
    except tool.PlanError:
        check(True, "negative no pairs refused")
    else:
        check(False, "negative no pairs refused")


def synthetic_inventory(new_len=1000):
    segment = {"label": "Passage 5", "start": 10000, "end": 13000}
    section = {"start": 10000,
               "channels": {"Camera.HeightOffsetCm": [[10000, 0.0], [10999, 20.0], [11000, 5.0], [12500, 0.0]],
                            "Camera.YawDegrees": [[10010, 0.0]]},
               "pins_rel": [10, 1000], "wing_pins": []}
    choreo = {"start_offset": 0, "keys": [["binding/Transform/X", 999], ["binding/Transform/X", 1000]],
              "sections": [{"where": "root/A", "start": 0, "end": 1200, "keyed": True},
                           {"where": "root/B", "start": 1500, "end": 1700, "keyed": False}],
              "markers": [["bar 1", 0], ["GO late", 1001]], "camera_cut": False}
    artist = [{"owner": "root", "class": "ArtistTrack", "track": "Absolute", "keys": [10950, 11000, 14000],
               "sections": [[0, 20000], [11500, 12000]]}]
    markers = [["before", 10999], ["at end", 11000], ["later segment", 14000]]
    managed = {"Playback:master": [0, 50000], "Passage:g": [10000, 13000], "Scene:next": [13000, 15000]}
    return tool.build_inventory("P05", segment, section, choreo, artist, markers, managed, new_len)


@test
def complete_past_end_inventory():
    inv = synthetic_inventory()
    check(len(inv["absolutePassageKeys"]) == 5, "all absolute Passage keys listed, not only late keys")
    check([r["sectionLocalTick"] for r in inv["pastNewEnd"]["passageChannelKeys"]] == [1000, 2500],
          "keys at and after new end listed")
    check([r["localTick"] for r in inv["pastNewEnd"]["relativePins"]] == [1000],
          "relative pin at end listed")
    check(len(inv["pastNewEnd"]["choreoKeys"]) == 1, "Choreo key at end listed")
    check(len(inv["pastNewEnd"]["choreoSections"]) == 2, "crossing and late Choreo sections listed")
    check(len(inv["pastNewEnd"]["choreoMarkers"]) == 1, "late Choreo marker listed")
    check(len(inv["pastNewEnd"]["masterArtistKeys"]) == 1, "absolute artist key in truncated tail listed")
    check(len(inv["pastNewEnd"]["masterMarkers"]) == 1, "Master marker at new end listed")
    check(any(not row["managed"] for row in inv["pastNewEnd"]["masterSections"]),
          "absolute artist section crossing tail listed")
    check(any(row["managed"] for row in inv["pastNewEnd"]["masterSections"]),
          "managed section crossing tail listed with expected rebuild")


@test
def review_actions_are_explicit():
    inv = synthetic_inventory()
    groups = tool.review_groups("P05", inv)
    refusals, notes = tool.review_refusals(groups, {})
    check(refusals and not notes, "negative unresolved items refuse")
    actions = {group: ("KEEP_ABSOLUTE" if any(group.endswith(":" + suffix) for suffix in (
        "masterMarkers", "masterArtistKeys", "masterArtistSections")) else "KEEP_UNPLAYED")
        for group in groups if not group.endswith(":relative_pins")}
    refusals, notes = tool.review_refusals(groups, actions)
    check(any("RELATIVE_PINS" in row for row in refusals), "negative pin cannot be silently lost")
    inv["pastNewEnd"]["relativePins"] = []
    groups = tool.review_groups("P05", inv)
    actions = {group: ("KEEP_ABSOLUTE" if any(group.endswith(":" + suffix) for suffix in (
        "masterMarkers", "masterArtistKeys", "masterArtistSections")) else "KEEP_UNPLAYED") for group in groups}
    refusals, notes = tool.review_refusals(groups, actions)
    check(refusals == [] and len(notes) == len(groups), "positive every remaining group explicitly reviewed")
    bad_actions = {group: "PROPORTIONAL_SCALE" for group in groups}
    check(tool.review_refusals(groups, bad_actions)[0], "negative unsupported silent scaling refused")
    move_actions = {group: ("KEEP_ABSOLUTE" if any(group.endswith(":" + suffix) for suffix in (
        "masterMarkers", "masterArtistKeys", "masterArtistSections")) else "MOVE_INSIDE") for group in groups}
    check(tool.review_refusals(groups, move_actions)[0] == [], "positive MOVE_INSIDE requires explicit action")
    check(tool.review_refusals(groups, {})[0], "negative past-end item left unresolved still refuses")


@test
def p05_resolution_options_are_complete():
    options = tool.p05_height_options(synthetic_inventory(), TICK, 42.022472)
    names = [row["name"] for row in options["options"]]
    check(options["status"] == "hazard" and len(options["lateKeys"]) == 2, "P05 hazard detected")
    check(names == ["MOVE_RETURN_TO_NEW_END", "MOVE_INSIDE", "DELETE_LATE_KEYS", "TAIL_OVERRIDE",
                     "KEEP_UNPLAYED"], "P05 options listed in review order")
    supported = {row["name"]: row["supportedByThisTool"] for row in options["options"]}
    check(supported["TAIL_OVERRIDE"] and supported["KEEP_UNPLAYED"], "non-destructive in-tool options supported")
    check(supported["MOVE_INSIDE"] and not supported["DELETE_LATE_KEYS"],
          "reviewed MOVE_INSIDE supported and deletion never implicit")


@test
def move_inside_lands_inside_and_revert_values_are_exact():
    old_len, new_len = 4472727, 1008960
    key_id = "P05|passage-key|Camera.HeightOffsetCm|4472726|3"
    section_id = "P06|choreo-section|root/MovieSceneSubTrack/P06 Bee Glints (Effects)|0|0"
    per = {
        "5": {"guid": "g5", "plan": {"old_ticks": old_len, "new_ticks": new_len},
              "inventory": {"pastNewEnd": {"passageChannelKeys": [{"id": key_id,
                  "channel": "Camera.HeightOffsetCm", "sectionLocalTick": 4472726, "value": 0.0}],
                  "choreoSections": []}},
              "reviewGroups": {"P05:passage_channel:Camera.HeightOffsetCm": [key_id]}, "choreo": None},
        "6": {"guid": "g6", "plan": {"old_ticks": 3024027, "new_ticks": 2654400},
              "inventory": {"pastNewEnd": {"passageChannelKeys": [], "choreoSections": [{"id": section_id,
                  "where": "root/MovieSceneSubTrack/P06 Bee Glints (Effects)", "start": 0, "end": 3024000}]}},
              "reviewGroups": {"P06:choreoSections": [section_id]},
              "choreo": {"path": "/Game/InfinityStage/Choreo/LS_Choreo_Passage_6"}}}
    actions = {"P05:passage_channel:Camera.HeightOffsetCm": "MOVE_INSIDE", "P06:choreoSections": "MOVE_INSIDE"}
    plan = tool.build_move_inside_plan(per, actions)
    moved_key = plan["passageKeys"][0]
    moved_section = plan["choreoSections"][0]
    check(moved_key["newLocal"] < new_len, "MOVE_INSIDE point lands strictly inside")
    check((moved_key["oldLocal"], moved_section["oldStart"], moved_section["oldEnd"]) ==
          (4472726, 0, 3024000), "REVERT originals recorded exactly")
    check(moved_section["newEnd"] <= 2654400 and moved_section["newEnd"] > moved_section["newStart"],
          "MOVE_INSIDE section lands within shortened Passage")
    keep = tool.build_move_inside_plan(per, {group: "KEEP_UNPLAYED" for group in actions})
    check(keep["passageKeys"] == [] and keep["choreoSections"] == [], "KEEP_UNPLAYED is never chosen implicitly")


def key_state(start, height=10.0, yaw=1.0):
    return {"g": {"start": start,
                  "channels": {"Camera.HeightOffsetCm": [[start + 10, height]],
                               "Camera.YawDegrees": [[start + 20, yaw]]},
                  "pins_rel": [30], "wing_pins": ["w"]}}


@test
def relative_key_carry_and_float_tolerances():
    before = key_state(1000)
    spans = [(100, 500, -50)]
    after = key_state(950, height=10.005, yaw=1.0005)
    check(tool.relative_key_carry_gate(before, after, spans) == [], "positive local ticks and float values carried")
    moved = key_state(950)
    moved["g"]["channels"]["Camera.HeightOffsetCm"][0][0] += 1
    check(any("LOCAL_TICK" in x for x in tool.relative_key_carry_gate(before, moved, spans)),
          "negative one-tick local drift")
    height = key_state(950, height=10.02)
    check(any("VALUE_CHANGED" in x for x in tool.relative_key_carry_gate(before, height, spans)),
          "negative height exceeds 0.01 cm tolerance")
    yaw = key_state(950, yaw=1.002)
    check(any("VALUE_CHANGED" in x for x in tool.relative_key_carry_gate(before, yaw, spans)),
          "negative angle exceeds 0.001 degree tolerance")
    pin = key_state(950)
    pin["g"]["pins_rel"] = []
    check(any("PINS_CHANGED" in x for x in tool.relative_key_carry_gate(before, pin, spans)),
          "negative relative pin loss")


@test
def logged_p05_p06_rebuild_rounding_regression():
    """P33-20261009-092149: old raw-boundary control fails; corrected gates accept only logged round-off."""
    spans = [
        (2312640, 4624705, -547585), (12649345, 13789825, -48000),
        (19662145, 20675905, -48000), (29064385, 30273985, -48000),
        (36731905, 41204632, -3463767), (44144152, 47168179, -369627),
    ]
    p05 = "3B27C331B54325A469AE8A818B9049F9"
    p06 = "9BFC29C45D47911FF7836BB8537230D2"
    before = {
        p05: {"start": 36731906, "channels": {"Camera.HeightOffsetCm": [
            [36731905, 0.0], [36767905, -90.0], [41168632, -90.0], [41204632, 0.0]]},
              "pins_rel": [], "wing_pins": []},
        p06: {"start": 44144153, "channels": {"Camera.SpeedMultiplier": [[35087952, 1.0]]},
              "pins_rel": [], "wing_pins": []},
    }
    after = {
        p05: {"start": 36040321, "channels": {"Camera.HeightOffsetCm": [
            [36040320, 0.0], [36076320, -90.0], [37041160, -90.0], [37049280, 0.0]]},
              "pins_rel": [], "wing_pins": []},
        p06: {"start": 39988799, "channels": {"Camera.SpeedMultiplier": [[30932600, 1.0]]},
              "pins_rel": [], "wing_pins": []},
    }
    # Reproduce the old code's unsnapped shift decision: both +1 starts look
    # strictly inside their shortened Passages, so shift_at returns None.
    old_control = [guid for guid in (p05, p06) if tool.base.shift_at(before[guid]["start"], spans) is None]
    check(old_control == [p05, p06], "negative old control reproduces both PASSAGE_SECTION_START_WRONG failures")
    move_plan = {"passageKeys": [
        {"guid": p05, "channel": "Camera.HeightOffsetCm", "ordinal": 2},
        {"guid": p05, "channel": "Camera.HeightOffsetCm", "ordinal": 3}], "choreoSections": []}
    check(tool._relative_gate_with_moves(before, after, spans, move_plan) == [],
          "positive logged P05/P06 section starts and local keys pass after boundary snap")
    bad_start = copy.deepcopy(after)
    bad_start[p06]["start"] = 39988800 + tool.SECTION_READ_TOL_TICKS + 1
    check(any("PASSAGE_SECTION_START_WRONG" in row for row in
              tool._relative_gate_with_moves(before, bad_start, spans, move_plan)),
          "negative Master section start beyond tolerance still refuses")

    expected = {"passageKeys": [
        {"group": "P05:passage_channel:Camera.HeightOffsetCm", "local": 1000839, "value": -90.0},
        {"group": "P05:passage_channel:Camera.HeightOffsetCm", "local": 1008959, "value": 0.0}],
        "choreoSections": [{"group": "P06:choreoSections", "start": 0, "end": 2654376}]}
    logged = copy.deepcopy(expected)
    logged["choreoSections"][0]["end"] = 2654377
    check(logged != expected, "negative old raw-equality control reproduces MOVE_INSIDE_READBACK_FAILED")
    check(tool.move_state_gate(logged, expected) == [],
          "positive logged one-tick Choreo seconds round-trip passes established section tolerance")
    key_drift = copy.deepcopy(logged)
    key_drift["passageKeys"][0]["local"] += 1
    check(tool.move_state_gate(key_drift, expected), "negative MOVE_INSIDE key tick drift remains exact and refuses")
    too_far = copy.deepcopy(logged)
    too_far["choreoSections"][0]["end"] = 2654376 + tool.SECTION_READ_TOL_TICKS + 1
    check(tool.move_state_gate(too_far, expected), "negative Choreo drift beyond tolerance still refuses")


@test
def downstream_shift_is_proven():
    segments = [{"label": row[0], "start": row[1], "end": row[2]} for row in SNAPSHOT["segments"]]
    deltas = {}
    for key in tool.VALID_KEYS:
        seg = passage_segment(key)
        duration = 110.561125 if key == "6" else None
        selected = tool.selected_music_seconds(key, FIXTURE["per_passage"][key], duration)
        target = tool.target_ticks(selected, 0.0, TICK, *FPS)
        deltas[tool.label_of(key)] = target - (seg["end"] - seg["start"])
    predicted = tool.base.predict_segments(segments, deltas)
    after = [{"label": row["label"], "start": row["new_start"], "end": row["new_end"]} for row in predicted]
    check(tool.base.segment_shift_gate(segments, after, deltas) == [], "positive downstream segment movement")
    broken = copy.deepcopy(after)
    broken[-1]["start"] += 1
    check(tool.base.segment_shift_gate(segments, broken, deltas), "negative downstream one-tick error")
    check(abs(sum(deltas.values()) / TICK - (-188.54079166666667)) < 1e-9, "P11 net shrink reproduced")


@test
def p06_live_sound_is_the_default_source():
    row = FIXTURE["per_passage"]["6"]
    selected = tool.selected_music_seconds("6", row, 110.561125)
    music = {"mode": "START", "sound": row["sound"], "source_in": 0, "source_out": int(selected * TICK),
             "offset": 0, "fade_in": 0, "fade_out": TICK, "tick_rate": TICK}
    refusals, notes, report = tool.source_policy("6", music, selected, row, {"past_end_actions": {}})
    check(refusals == [] and not notes and report["sound"] == tool.P06_LIVE_SOUND,
          "positive live P06 sound has no SOUND_CHANGED refusal")
    changed = dict(music, sound="/Game/Old/Cameron")
    check(any("SOUND_CHANGED" in x for x in tool.source_policy("6", changed, selected, row, {})[0]),
          "negative non-live P06 sound still refuses")
    short = dict(music, source_out=100 * TICK)
    check(any("EXCEEDS_LIVE_RAIL" in x for x in tool.source_policy("6", short, selected, row, {})[0]),
          "negative selection longer than rail")
    offset = dict(music, offset=1)
    check(any("RAIL_OFFSET" in x for x in tool.source_policy("6", offset, selected, row, {})[0]),
          "negative nonzero rail offset")


@test
def review_hash_and_expected_numbers_gate_drift():
    row = {"old": {"lenTicks": 200}, "plan": {"old_ticks": 200, "new_ticks": 100},
           "music": {"selectedTicks": 100}, "inventory": synthetic_inventory(),
           "p05HeightOffset": tool.p05_height_options(synthetic_inventory(), TICK, 1.0)}
    first = tool.inventory_sha256({"5": row})
    check(len(first) == 64 and first == tool.inventory_sha256({"5": copy.deepcopy(row)}), "stable review hash")
    changed = copy.deepcopy(row)
    changed["inventory"]["absolutePassageKeys"][0]["value"] = 99.0
    check(first != tool.inventory_sha256({"5": changed}), "negative value drift changes review hash")
    expected = {"old_len_ticks": 200, "new_len_ticks": 100, "music_ticks": 100}
    check(tool.expected_refusals("5", row, expected, "APPLY") == [], "positive expected numbers")
    expected["old_len_ticks"] = 201
    check(tool.expected_refusals("5", row, expected, "APPLY"), "negative state drift since DRY")


@test
def exact_dirty_census_and_live_gates():
    wanted = [tool.SHOW_PATH, tool.MASTER_PATH]
    check(tool.exact_census_gate({"content": sorted(wanted), "maps": []}, wanted) == [], "positive exact dirty set")
    check(tool.exact_census_gate({"content": [tool.SHOW_PATH], "maps": []}, wanted), "negative missing dirty Master")
    check(tool.exact_census_gate({"content": wanted + ["/Game/X"], "maps": []}, wanted),
          "negative extra dirty package")
    clean = {"mode": "DRY", "confirm": "DRY PASSAGES TO MUSIC", "census": {"content": [], "maps": []}}
    check(tool.live_gates(clean) == [], "positive clean DRY gate")
    for field, value, word in (("confirm", "DRY RETIME", "CONFIRM"), ("pie", True, "PIE"),
                               ("sequencer_open", True, "SEQUENCER"),
                               ("census", {"content": ["/Game/X"], "maps": []}, "DIRTY")):
        state = dict(clean)
        state[field] = value
        check(any(word in x for x in tool.live_gates(state)), "negative live gate %s" % field)
    apply = {"mode": "APPLY", "confirm": "APPLY PASSAGES TO MUSIC", "census": {"content": [], "maps": []},
             "record_exists": True}
    check(any("RECORD_EXISTS" in x for x in tool.live_gates(apply)), "negative APPLY record collision")
    revert = {"mode": "REVERT", "confirm": "REVERT PASSAGES TO MUSIC", "census": {"content": [], "maps": []}}
    check(any("NO_APPLIED_RECORD" in x for x in tool.live_gates(revert)), "negative REVERT without record")


@test
def record_is_create_only():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "record.json")
        tool.base.write_record_exclusive(path, {"run": "A"})
        check(json.load(open(path, encoding="utf-8"))["run"] == "A", "positive record written")
        try:
            tool.base.write_record_exclusive(path, {"run": "B"})
        except OSError:
            check(True, "negative record overwrite refused")
        else:
            check(False, "negative record overwrite refused")


def main():
    for function in TESTS:
        try:
            function()
        except Exception as exc:  # noqa: BLE001 - harness counts and reports every failure
            FAIL.append("%s raised %r" % (function.__name__, exc))
    for failure in FAIL:
        print("FAIL", failure)
    print("PASSAGES_TO_MUSIC_HARNESS|tests=%d|passed=%d|failed=%d" % (len(TESTS), PASS, len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
