"""Offline positive/negative harness for interaction_shadow_transition.py. No Unreal import or project mutation."""
import copy
import hashlib
import importlib.util
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "interaction_shadow_transition.py")
spec = importlib.util.spec_from_file_location("interaction_shadow_transition_offline", PATH)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

RESULTS = []


def check(name, condition, detail=None):
    RESULTS.append((name, bool(condition), detail))


def has(rows, text):
    return any(text in str(row) for row in rows)


FRAME_H = {"loc": [16768.0, 0.0, 0.0], "pitch": 0.0, "yaw": 0.0}
FRAME_M = {"loc": [1000.0, 2500.0, 20.0], "pitch": 0.0, "yaw": 90.0}
TARGET = {
    "interaction": 1,
    "sequence": "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy",
    "cue_guid": "11112222333344445555666677778888",
    "fps": 25.0,
    "start": 0,
    "end": 2183,
    "beats": {"play0": 175, "sleight": 1250, "strike": 1300, "release": 1675},
    "drapes": {"hangar": FRAME_H, "mouth": FRAME_M},
}
REFERENCE = {
    "interaction": 4,
    "relative": {"loc": [-2819.077862, 0.0, 1026.06043],
                 "direction": [0.9396926208, 0.0, -0.3420201433]},
    "light": {
        "intensity": 7483.0,
        "intensity_units": "CANDELAS",
        "use_temperature": True,
        "temperature": 3200.0,
        "outer_cone_angle": 3.433630362,
        "inner_cone_angle": 2.060178217,
        "attenuation_radius": 4500.0,
        "source_radius": 2.0,
        "soft_source_radius": 0.0,
        "cast_shadows": True,
        "light_function_material": None,
    },
}
PLAN = tool.plan_transition(TARGET, REFERENCE, {})

# A. positive planner controls
check("A1 default reference is I4", PLAN["reference_interaction"] == 4)
check("A2 default fade is 4 seconds / 100 frames", PLAN["fade_up"] == [175, 275], PLAN["fade_up"])
check("A3 fade begins dark", all(tool._interp_rows(PLAN["spots"][s]["intensity_keys"], 175) == 0.0 for s in tool.SIDES))
check("A4 fade reaches 7483 cd", all(abs(tool._interp_rows(PLAN["spots"][s]["intensity_keys"], 275)-7483.0) < 1e-6 for s in tool.SIDES))
check("A5 default fade-out is 25 frames", PLAN["fade_out"] == [1675, 1700], PLAN["fade_out"])
check("A6 cast shadows copied", PLAN["light"]["cast_shadows"] is True)
check("A7 light-function slot exposed and empty", "light_function_material" in PLAN["light"] and PLAN["light"]["light_function_material"] is None)
check("A8 cards are disabled-if-present", set(PLAN["cards"]) == set(tool.CARD_NAMES) and set(PLAN["cards"].values()) == {"disable_if_present"})
check("A9 target range unchanged", (PLAN["start"], PLAN["end"]) == (0, 2183))
check("A10 positive plan has no failures", tool.check_plan(PLAN) == [], tool.check_plan(PLAN))
check("A11 two spots have identical relative profile", PLAN["relative"] == REFERENCE["relative"])
check("A12 plan deterministic", PLAN["digest"] == tool.plan_transition(TARGET, REFERENCE, {})["digest"])
check("A13 drape is ready before first nonzero spot frame", PLAN["drape_ready_frame"] <= PLAN["fade_up"][0])

# B. parameter controls and negative planner controls
p = tool.plan_transition(TARGET, REFERENCE, {"fade_seconds": 2.0, "fade_out_seconds": 0.0,
                                             "light_function_material": "/Game/FX/M_Gobo"})
check("B1 args override fade", p["fade_up"] == [175, 225])
check("B2 zero fade-out becomes one frame", p["fade_out"] == [1675, 1676])
check("B3 gobo material path reaches plan", p["light"]["light_function_material"] == "/Game/FX/M_Gobo")
for name, params, code in (
    ("unknown arg", {"bogus": 1}, "UNKNOWN_PARAMS"),
    ("bad reference", {"reference_interaction": 6}, "REFERENCE_INTERACTION"),
    ("zero fade", {"fade_seconds": 0}, "FADE_SECONDS"),
    ("bad gobo", {"light_function_material": "Engine/X"}, "LIGHT_FUNCTION_MATERIAL"),
):
    try:
        tool.plan_transition(TARGET, REFERENCE, params)
        check("B -control " + name, False)
    except tool.PlanError as exc:
        check("B -control " + name, code in str(exc), str(exc))
late = copy.deepcopy(TARGET); late["beats"]["sleight"] = 250
try:
    tool.plan_transition(late, REFERENCE, {})
    check("B -control fade overlaps sleight", False)
except tool.PlanError as exc:
    check("B -control fade overlaps sleight", "FADE_OVERLAPS_SLEIGHT" in str(exc), str(exc))
short = copy.deepcopy(TARGET); short["end"] = 1680
try:
    tool.plan_transition(short, REFERENCE, {})
    check("B -control fade outside range", False)
except tool.PlanError as exc:
    check("B -control fade outside range", "FADE_OUTSIDE_RANGE" in str(exc), str(exc))
dim = copy.deepcopy(PLAN); dim["light"]["intensity"] = 100.0
check("B -control intensity mismatch", has(tool.check_plan(dim), "REFERENCE_INTENSITY_NOT_7483"))
shadowless = copy.deepcopy(PLAN); shadowless["light"]["cast_shadows"] = False
check("B -control cast shadows off", has(tool.check_plan(shadowless), "CAST_SHADOWS_OFF"))
late_drape = copy.deepcopy(PLAN); late_drape["drape_ready_frame"] = PLAN["fade_up"][0] + 1
check("B -control drape not ready before fade", has(tool.check_plan(late_drape), "DRAPE_NOT_READY_BEFORE_FADE"))
offset = copy.deepcopy(PLAN); offset["spots"]["mouth"]["pose"]["loc"][0] += 5.0
check("B -control 5 cm spot mismatch", has(tool.check_plan(offset), "SPOT_RELATIVE_MOUTH"), tool.check_plan(offset))

# C. gates, including positive and negative state controls
CLEAN = {"pie": False, "world_ok": True, "sequencer_open": False,
         "census": {"content": [], "maps": []}, "zz": False, "record": None,
         "confirm": "APPLY I1"}
check("C1 clean APPLY gate passes", tool.preflight_refusals("APPLY", 1, CLEAN) == [])
for name, delta, code in (
    ("PIE", {"pie": True}, "PIE_OR_SIE_ACTIVE"),
    ("wrong world", {"world_ok": False}, "WRONG_WORLD"),
    ("Sequencer", {"sequencer_open": True}, "SEQUENCER_IS_OPEN"),
    ("dirty content", {"census": {"content": ["/Game/X"], "maps": []}}, "DIRTY_CENSUS"),
    ("dirty map", {"census": {"content": [], "maps": ["/Game/M"]}}, "DIRTY_CENSUS"),
    ("ZZ actor", {"zz": True}, "ZZ_ACTORS_PRESENT"),
    ("existing record", {"record": {"applied": True}}, "RECORD_EXISTS"),
    ("confirm", {"confirm": "APPLY I2"}, "CONFIRM_MISMATCH"),
):
    state = dict(CLEAN); state.update(delta)
    check("C -control " + name, has(tool.preflight_refusals("APPLY", 1, state), code), tool.preflight_refusals("APPLY", 1, state))
rev = dict(CLEAN, confirm="REVERT I1", record={"applied": True, "interaction": 1})
check("C2 valid REVERT gate passes", tool.preflight_refusals("REVERT", 1, rev) == [])
check("C3 -control REVERT no record", has(tool.preflight_refusals("REVERT", 1, dict(CLEAN, confirm="REVERT I1")), "NOTHING_TO_REVERT"))
check("C4 exact confirm strings", tool.confirm_ok("DRY", 5, "DRY I5") and not tool.confirm_ok("DRY", 5, "DRY I4"))

# D. structural model: present spots unchanged, absent spots added, exact revert model
base = {"playback": [0, 2183], "markers": [], "cuts": [], "root_tracks": [], "level_labels": [], "bindings": [
    {"name": tool.CARD_NAMES[0], "guid": "C1", "parent": "", "tracks": [{"class": "MovieSceneSpawnTrack", "name": "", "sections": [[0, 2184]]}]},
    {"name": tool.CARD_NAMES[1], "guid": "C2", "parent": "", "tracks": [{"class": "MovieSceneSpawnTrack", "name": "", "sections": [[0, 2184]]}]},
]}
created = {tool.SPOT_NAMES["hangar"]: "S1", tool.SPOT_NAMES["mouth"]: "S2"}
applied = tool.structural_apply_model(base, PLAN, {}, created)
check("D1 absent spot pair adds exactly two bindings", len(applied["bindings"]) == 4)
check("D2 each created spot has spawn/transform/float", all(len(b["tracks"]) == 3 for b in applied["bindings"] if b["guid"] in created.values()))
reverted = tool.structural_revert_model(applied, created)
check("D3 structural revert is exact", tool.CS["snapshot_diff"](reverted, tool.CS["normalize_snapshot"](base)) == [])
existing_base = copy.deepcopy(applied)
again = tool.structural_apply_model(existing_base, PLAN, created, {})
check("D4 existing spots are not duplicated", len(again["bindings"]) == len(existing_base["bindings"]))
check("D5 -control structural drift is detected", tool.CS["snapshot_diff"](dict(applied, playback=[0, 2184]), applied) != [])

# E. preview image positive/negative checks
preview = os.path.join(os.environ.get("TEMP", HERE), "ist_harness_preview.png")
meta = tool.write_preview_png(preview, PLAN, width=320, height=180)
with open(preview, "rb") as handle:
    data = handle.read()
check("E1 preview is PNG", data.startswith(b"\x89PNG\r\n\x1a\n"))
check("E2 preview dimensions are exact", struct.unpack(">II", data[16:24]) == (320, 180))
check("E3 preview metadata checksum", hashlib.sha256(data).hexdigest() == meta["sha256"])
check("E4 preview nontrivial", len(data) > 500, len(data))
os.remove(preview)

# F. report claim discipline and per-Interaction args
check("F1 every claim has tier/cite", all(set(row) == {"tier", "claim", "cite"} and row["tier"] in
      {"declaration-proven", "binary-proven", "measured", "inferred"} for row in tool.CLAIMS))
check("F2 every API row has accepted tier", all(row[1] in {"declaration-proven", "binary-proven", "measured", "inferred"} for row in tool.API_TABLE))
with open(os.path.join(HERE, "interaction_shadow_transition_args.json"), "r", encoding="utf-8") as handle:
    args = json.load(handle)
check("F3 args contain exactly I1..I5", set(args["interactions"]) == {"I1", "I2", "I3", "I4", "I5"})
check("F4 P44 args use applied I2 pattern as reference", args["reference_interaction"] == 2)
check("F5 P44 stand-ins name the current BoyPussRub gobo", all(
    args["interactions"][key]["light_function_material"] ==
    "/Game/InfinityStage/Lighting/Gobo/MI_ShadowGobo_BoyPussRub" for key in ("I1", "I3", "I4", "I5")))
check("F6 args put Gary's fade in each Interaction", all(row["fade_seconds"] == 4.0 for row in args["interactions"].values()))
check("F7 source imports without Unreal", tool.unreal is None)

passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = [(name, detail) for name, ok, detail in RESULTS if not ok]
for name, detail in failed:
    print("FAIL", name, str(detail)[:500])
print("INTERACTION_SHADOW_TRANSITION_TESTS|pass=%d|fail=%d" % (passed, len(failed)))
sys.exit(1 if failed else 0)
