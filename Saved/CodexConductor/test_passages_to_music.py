"""Offline positive and negative controls for P33 passages_to_music.py.

Run from the repository root:
  python -X utf8 Saved/CodexConductor/test_passages_to_music.py

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

with open(os.path.join(HERE, "passages_to_music_args.json"), "r", encoding="utf-8") as handle:
    SHIPPED = json.load(handle)
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
    value = copy.deepcopy(SHIPPED)
    value.update(updates)
    return value


def passage_segment(key):
    label = tool.label_of(key)
    label_, start, end = [row for row in SNAPSHOT["segments"] if row[0] == label][0]
    return {"label": label_, "start": int(start), "end": int(end)}


@test
def shipped_args_and_negative_controls():
    check(tool.validate_args(SHIPPED) == [], "shipped DRY args valid")
    check(any("MODE" in x for x in tool.validate_args(args(mode="GO"))), "negative invalid mode")
    check(any("ALL_SIX" in x for x in tool.validate_args(args(passages=["1"]))), "negative partial set")
    bad = args()
    bad["tail_overrides_s"]["5"] = -1
    check(any("TAIL_OVERRIDE" in x for x in tool.validate_args(bad)), "negative tail override")
    bad = args(mode="APPLY", confirm="APPLY PASSAGES TO MUSIC")
    check(any("EXPECTED" in x for x in tool.validate_args(bad)), "negative APPLY without DRY numbers")
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
        got = tool.target_ticks(SHIPPED["per_passage"][key]["music_s"], 0.0, TICK, *FPS)
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


@test
def p05_resolution_options_are_complete():
    options = tool.p05_height_options(synthetic_inventory(), TICK, 42.022472)
    names = [row["name"] for row in options["options"]]
    check(options["status"] == "hazard" and len(options["lateKeys"]) == 2, "P05 hazard detected")
    check(names == ["MOVE_RETURN_TO_NEW_END", "PROPORTIONAL_RETIME", "DELETE_LATE_KEYS", "TAIL_OVERRIDE",
                    "KEEP_UNPLAYED"], "P05 options listed in review order")
    supported = {row["name"]: row["supportedByThisTool"] for row in options["options"]}
    check(supported["TAIL_OVERRIDE"] and supported["KEEP_UNPLAYED"], "non-destructive in-tool options supported")
    check(not supported["PROPORTIONAL_RETIME"] and not supported["DELETE_LATE_KEYS"],
          "absolute key scaling/deletion never implicit")


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
def downstream_shift_is_proven():
    segments = [{"label": row[0], "start": row[1], "end": row[2]} for row in SNAPSHOT["segments"]]
    deltas = {}
    for key in tool.VALID_KEYS:
        seg = passage_segment(key)
        target = tool.target_ticks(SHIPPED["per_passage"][key]["music_s"], 0.0, TICK, *FPS)
        deltas[tool.label_of(key)] = target - (seg["end"] - seg["start"])
    predicted = tool.base.predict_segments(segments, deltas)
    after = [{"label": row["label"], "start": row["new_start"], "end": row["new_end"]} for row in predicted]
    check(tool.base.segment_shift_gate(segments, after, deltas) == [], "positive downstream segment movement")
    broken = copy.deepcopy(after)
    broken[-1]["start"] += 1
    check(tool.base.segment_shift_gate(segments, broken, deltas), "negative downstream one-tick error")
    check(abs(sum(deltas.values()) / TICK - (-188.54079166666667)) < 1e-9, "P11 net shrink reproduced")


@test
def source_tail_requires_a_decision():
    row = SHIPPED["per_passage"]["6"]
    music = {"mode": "START", "sound": row["sound"], "source_in": 0, "source_out": 125 * TICK,
             "offset": 0, "fade_in": 0, "fade_out": TICK, "tick_rate": TICK}
    refusals, notes, report = tool.source_policy("6", music, row["music_s"], row, {"past_end_actions": {}})
    check(any("SOURCE_TAIL_UNDECIDED" in x for x in refusals), "negative P06 source tail undecided")
    review = {"past_end_actions": {"P06:source_tail": "KEEP_UNUSED"}}
    refusals, notes, report = tool.source_policy("6", music, row["music_s"], row, review)
    check(refusals == [] and notes and abs(report["unusedSourceTailSeconds"] - 14.438875) < 1e-6,
          "positive P06 explicit unused tail")
    short = dict(music, source_out=100 * TICK)
    check(any("EXCEEDS_LIVE_RAIL" in x for x in tool.source_policy("6", short, row["music_s"], row, review)[0]),
          "negative selection longer than rail")
    offset = dict(music, offset=1)
    check(any("RAIL_OFFSET" in x for x in tool.source_policy("6", offset, row["music_s"], row, review)[0]),
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
