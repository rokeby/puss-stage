"""Positive and negative offline harness for opening_lighting_p13.py."""
import copy
import hashlib
import importlib.util
import json
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "opening_lighting_p13.py")
spec = importlib.util.spec_from_file_location("opening_lighting_p13_offline", PATH)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

RESULTS = []


def check(name, condition, detail=None):
    RESULTS.append((name, bool(condition), detail))


def raises(name, args, token, inventory=None):
    try:
        tool.build_plan(args, inventory)
        check(name, False, "did not raise")
    except tool.P13Error as exc:
        check(name, token in str(exc), str(exc))


P01_INVENTORY = [
    {"label": "P01 SCORE B01 VOID PRACTICAL_DEAD",
     "guid": "0123456789ABCDEF0123456789ABCDEF", "cue_index": 1,
     "cue_guid": "11111111111111111111111111111111", "cue_label": "P01 Wing 001",
     "base_intensity": 300.0, "intensity_units": "LUMENS", "light_type": "POINT"},
]
plan = tool.build_plan({}, P01_INVENTORY)
p = plan["params"]

# A. positive creative-plan controls
check("A01 four moving spots", len([x for x in plan["fixtures"] if x["role"] == "moving_spot"]) == 4)
check("A02 two corner fixtures", len([x for x in plan["fixtures"] if x["role"] == "corner_pulse"]) == 2)
check("A03 no wash fixture", all("wash" not in x["label"].lower() for x in plan["fixtures"]))
check("A04 tight cones", all(x["outer_cone_deg"] <= 12 for x in plan["fixtures"]))
check("A05 soft penumbra", all(x["outer_cone_deg"] - x["inner_cone_deg"] >= 5 for x in plan["fixtures"]))
check("A06 high falloff exponent", all(x["falloff_exponent"] >= 8 for x in plan["fixtures"]))
check("A07 aims end near centre", all(abs(x["end_target_cm"][1]) <= p["centre_aim_half_width_cm"] for x in plan["fixtures"] if x["role"] == "moving_spot"))
check("A08 default curtain on flurry 1", plan["cue_frames"]["curtain_drop"] == plan["flurries"][0]["frame"])
check("A09 default lights on flurry 2", plan["cue_frames"]["lights_on"] == plan["flurries"][1]["frame"])
check("A10 perspective on flurry 3", plan["cue_frames"]["perspective"] == plan["flurries"][2]["frame"])
check("A11 focal pull 15 to 25", plan["perspective_keys"][1][1] == 15 and plan["perspective_keys"][2][1] == 25)
check("A12 curtain has hold fall pile", len(plan["curtain_sections"]) == 3)
check("A13 curtain sections contiguous", plan["curtain_sections"][0][1] == plan["curtain_sections"][1][0] and plan["curtain_sections"][1][1] == plan["curtain_sections"][2][0])
check("A14 old rig disabled not deleted", plan["disable_existing_bindings_prefix"] == "Opening Rig - ")
check("A15 deterministic digest", plan["digest"] == tool.build_plan({}, P01_INVENTORY)["digest"])
check("A16 every flurry has two corner peaks", all(sum(1 for x in plan["fixtures"] if x["role"] == "corner_pulse" and [f["frame"], p["corner_intensity_cd"]] in x["intensity_keys"]) == 2 for f in plan["flurries"]))
check("A17 spots remain lit after movement", all(x["intensity_keys"][-2][1] > 0 for x in plan["fixtures"] if x["role"] == "moving_spot"))
check("A18 end is dark", all(x["intensity_keys"][-1][1] == 0 for x in plan["fixtures"]))
facade = [x for x in plan["fixtures"] if x["role"] == "facade_par"]
check("A19 seven facade PARs", len(facade) == 7)
check("A20 facade row spans args", facade[0]["world_location_cm"][1] == p["facade_par_y_min_cm"] and facade[-1]["world_location_cm"][1] == p["facade_par_y_max_cm"])
check("A21 facade placed audience-side", all(x["world_location_cm"][0] < -75 for x in facade))
check("A22 facade aims at valance plane", all(x["end_target_cm"][0] == -60 and x["end_target_cm"][2] == 1120 for x in facade))
check("A23 facade warm and tight", all(x["temperature_kelvin"] == 2700 and x["outer_cone_deg"] == 9 for x in facade))
check("A24 facade strikes at flurry 2", all([plan["flurries"][1]["frame"], 0.0] in x["intensity_keys"] for x in facade))
check("A25 P01 exact subset", [x["label"] for x in plan["p01_lights"]] == p["p01_opening_light_labels"])
check("A26 P01 partial target", plan["p01_lights"][0]["target_intensity"] == 105.0)
check("A27 P01 partial then full at P01 start", all(row["intensity_keys"][-2][1] == row["target_intensity"] and row["intensity_keys"][-1] == [plan["opening_end_frame"], row["base_intensity"]] for row in plan["p01_lights"]))
check("A28 P01 base identity preserved", plan["p01_lights"][0]["guid"] == P01_INVENTORY[0]["guid"])
check("A29 pass-2 markers", {"P13 facade PARs on", "P13 P01 subset on"} <= {row[0] for row in plan["markers"]})

# B. args and negative controls
alt = tool.build_plan({"spot_count": 6, "curtain_flurry_index": 3, "spot_intensity_cd": 975,
                       "spot_outer_cone_deg": 14, "spot_inner_cone_deg": 8}, P01_INVENTORY)
check("B01 spot count arg", len([x for x in alt["fixtures"] if x["role"] == "moving_spot"]) == 6)
check("B02 curtain index arg", alt["cue_frames"]["curtain_drop"] == alt["flurries"][2]["frame"])
check("B03 intensity arg", all(x["intensity_cd"] == 975 for x in alt["fixtures"] if x["role"] == "moving_spot"))
check("B04 cone args", all((x["inner_cone_deg"], x["outer_cone_deg"]) == (8, 14) for x in alt["fixtures"] if x["role"] == "moving_spot"))
raises("B05 -control unknown arg", {"bogus": 1}, "UNKNOWN_ARGS")
raises("B06 -control too few spots", {"spot_count": 1}, "SPOT_COUNT")
raises("B07 -control unordered flurries", {"flurry_times_s": [4, 3, 5]}, "FLURRIES")
raises("B08 -control duplicate flurry", {"flurry_times_s": [3, 3, 5]}, "FLURRIES")
raises("B09 -control bad index", {"curtain_flurry_index": 4}, "FLURRY_INDEX")
raises("B10 -control hard/no penumbra", {"spot_inner_cone_deg": 12, "spot_outer_cone_deg": 12}, "CONE")
raises("B11 -control low falloff", {"spot_falloff_exponent": 4}, "FALLOFF")
raises("B12 -control unsupported perspective", {"perspective_mode": "walkin"}, "PERSPECTIVE_MODE")
raises("B13 -control opening too short", {"opening_end_s": 50}, "OPENING_END")
raises("B14 -control too few facade PARs", {"facade_par_count": 2}, "FACADE_PAR_COUNT")
raises("B15 -control facade hard edge", {"facade_par_inner_cone_deg": 9}, "CONE")
raises("B16 -control facade y inverted", {"facade_par_y_min_cm": 10, "facade_par_y_max_cm": -10}, "FACADE_PAR_Y_RANGE")
raises("B17 -control P01 labels not list", {"p01_opening_light_labels": "P01 X"}, "P01_LIGHT_LABELS")
raises("B18 -control duplicate P01 label", {"p01_opening_light_labels": ["P01 X", "P01 X"]}, "P01_LIGHT_LABELS")
raises("B19 -control full P01 intensity", {"p01_opening_intensity_scale": 1.0}, "P01_OPENING_INTENSITY_SCALE")
raises("B20 -control missing live label", {}, "P01_LIGHT_INVENTORY", [])
zero_inventory = [dict(row) for row in P01_INVENTORY]
zero_inventory[0]["base_intensity"] = 0.0
raises("B21 -control zero live P01 intensity", {}, "P01_LIGHT_NOT_LIT_IN_P01", zero_inventory)
two_labels = {"p01_opening_light_labels": [P01_INVENTORY[0]["label"], "P01 OTHER"]}
raises("B22 -control incomplete live inventory", two_labels, "P01_LIGHT_INVENTORY", P01_INVENTORY[:1])

# C. preflight gates, positive and negative
clean = {"confirm": "APPLY P13", "pie": False, "world_ok": True, "sequencer_open": False,
         "census": {"content": [], "maps": []}, "zz": False, "record": None}
check("C01 clean APPLY passes", tool.preflight_refusals("APPLY", clean) == [])
for name, delta, token in (
    ("PIE", {"pie": True}, "PIE_OR_SIE_ACTIVE"),
    ("world", {"world_ok": False}, "WRONG_WORLD"),
    ("Sequencer", {"sequencer_open": True}, "SEQUENCER_IS_OPEN"),
    ("dirty content", {"census": {"content": ["/Game/X"], "maps": []}}, "DIRTY_CENSUS"),
    ("dirty map", {"census": {"content": [], "maps": ["/Game/M"]}}, "DIRTY_CENSUS"),
    ("ZZ", {"zz": True}, "ZZ_ACTORS_PRESENT"),
    ("confirm", {"confirm": "APPLY P12"}, "CONFIRM_MISMATCH"),
    ("record", {"record": {"status": "saved_readback_verified"}}, "RECORD_EXISTS"),
):
    state = dict(clean); state.update(delta)
    check("C -control " + name, any(token in x for x in tool.preflight_refusals("APPLY", state)))
rev = dict(clean, confirm="REVERT P13", record={"status": "saved_readback_verified"})
check("C02 valid REVERT passes", tool.preflight_refusals("REVERT", rev) == [])
rev_bad = dict(clean, confirm="REVERT P13")
check("C03 -control REVERT no record", any("NOTHING_TO_REVERT" in x for x in tool.preflight_refusals("REVERT", rev_bad)))

# D. geometry/timing math controls
check("D01 aim rotation finite", all(math == math for x in plan["fixtures"] for math in x["start_rotation_rpy_deg"]))
check("D02 relative X accounts for station", all(abs(x["relative_location_cm"][0] - (x["world_location_cm"][0] - 250)) < 1e-9 for x in plan["fixtures"]))
check("D03 moving aim actually changes", all(x["start_rotation_rpy_deg"] != x["end_rotation_rpy_deg"] for x in plan["fixtures"] if x["role"] == "moving_spot"))
check("D04 corner aim static", all(x["start_rotation_rpy_deg"] == x["end_rotation_rpy_deg"] for x in plan["fixtures"] if x["role"] == "corner_pulse"))
check("D05 perspective completes before end", plan["cue_frames"]["perspective_end"] < plan["opening_end_frame"])
check("D06 float32 tolerance positive", tool._keys_close([[1, 100.00005]], [[1, 100.0]], tool.FLOAT_TOLERANCE))
check("D07 -control float32 tolerance negative", not tool._keys_close([[1, 100.001]], [[1, 100.0]], tool.FLOAT_TOLERANCE))
check("D08 -control frame drift", not tool._keys_close([[2, 100.0]], [[1, 100.0]], tool.FLOAT_TOLERANCE))

# E. preview positive/negative controls
tmp = tempfile.mkdtemp(prefix="p13_opening_")
try:
    rig_path = os.path.join(tmp, "rig.png"); time_path = os.path.join(tmp, "timeline.png")
    rig = tool.write_rig_diagram(rig_path, plan, size=(700, 400))
    env = {"source": "synthetic-positive-control", "rate_hz": 2.0, "duration_s": 96.36,
           "values": [0.5 + 0.4 * ((i % 20) / 20.0) for i in range(193)]}
    timeline = tool.write_timeline(time_path, plan, env, size=(800, 620))
    for token, path, meta in (("rig", rig_path, rig), ("timeline", time_path, timeline)):
        data = open(path, "rb").read()
        check("E %s PNG signature" % token, data.startswith(b"\x89PNG\r\n\x1a\n"))
        check("E %s dimensions" % token, list(struct.unpack(">II", data[16:24])) == meta["size"])
        check("E %s checksum" % token, hashlib.sha256(data).hexdigest() == meta["sha256"])
        check("E %s nontrivial" % token, len(data) > 1500, len(data))
finally:
    for name in os.listdir(tmp): os.remove(os.path.join(tmp, name))
    os.rmdir(tmp)

# F. delivery/claim discipline
with open(os.path.join(HERE, "opening_lighting_p13_args.json"), encoding="utf-8") as handle:
    args_file = json.load(handle)
check("F01 args defaults DRY", args_file["mode"] == "DRY" and args_file["confirm"] == "DRY P13")
check("F02 every claim tiered", all(row["tier"] in {"declaration-proven", "binary-proven", "measured", "inferred"} and row.get("cite") for row in tool.CLAIMS))
check("F03 offline import has no Unreal", tool.unreal is None)
check("F04 Show authority declared", plan["authority"]["show"] == tool.SHOW_PATH)
check("F05 apply mutates no material graph", "Material" not in open(PATH, encoding="utf-8").read())
check("F06 exact confirm tokens", not tool.preflight_refusals("DRY", dict(clean, confirm="DRY P13")) and any("CONFIRM" in x for x in tool.preflight_refusals("DRY", dict(clean, confirm="dry p13"))))
check("F07 delivered args expose every default", set(args_file["args"]) == set(tool.DEFAULTS), sorted(set(tool.DEFAULTS) - set(args_file["args"])))

passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = [(name, detail) for name, ok, detail in RESULTS if not ok]
for name, detail in failed:
    print("FAIL", name, str(detail)[:500])
print("P13_OPENING_LIGHTING_TESTS|pass=%d|fail=%d" % (passed, len(failed)))
sys.exit(1 if failed else 0)
