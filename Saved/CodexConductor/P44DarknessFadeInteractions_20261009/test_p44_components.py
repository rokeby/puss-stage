"""Offline positive/negative controls for the P44 probe and dispatcher."""
import importlib.util
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(name):
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location("p44_test_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load("p44_probe")
action = load("p44_action")
RESULTS = []


def check(name, condition, detail=None):
    RESULTS.append((name, bool(condition), detail))


def rejects(name, function, text):
    try:
        function()
    except Exception as error:  # noqa: BLE001
        check(name, text in str(error), str(error))
        return
    check(name, False, "did not reject")


mapped = probe.map_master_time(224.0, 4624705.0 / 24000.0, 10553665.0 / 24000.0, 25.0)
check("P clock maps 3:44 to frame 783", mapped["scene_frame"] == 783 and
      abs(mapped["scene_frame_exact"] - 782.5989583333334) < 1e-9, mapped)
rejects("N clock rejects pre-S1 time", lambda: probe.map_master_time(190, 192, 300, 25), "OUTSIDE")
rejects("N clock rejects zero rate", lambda: probe.map_master_time(224, 192, 300, 0), "NONPOSITIVE")

summary = probe.visibility_summary([{"property": "bHiddenInGame"}, {"property": "bHidden"},
                                    {"property": None}, {"property": "Odd"}])
check("P visibility census separates inert/working/None/other", summary == {
    "bHidden": 1, "bHiddenInGame": 1, "None": 1, "other": 1,
    "needs_f4_apply": True, "f4_already_fixed": False}, summary)
fixed = probe.visibility_summary([{"property": "bHidden"}])
check("P fixed visibility is idempotent", fixed["f4_already_fixed"] and not fixed["needs_f4_apply"], fixed)

inventory = probe.inventory_labels(["Sleight Mouth Shadow Card", "Shadow Play Spot (Mouth)"])
check("P inventory names present and missing per interaction",
      inventory["Sleight Mouth Shadow Card"]["state"] == "present" and
      inventory["Sleight Hangar Shadow Card"]["state"] == "missing" and
      inventory["Shadow Play Spot (Mouth)"]["count"] == 1, inventory)

for item in action.ITEMS:
    normalized = action.normalize_action({"item": item, "mode": "DRY", "confirm": "DRY P44 " + item,
                                          "run_id": "P44-%s-001" % item})
    check("P dispatcher accepts " + item, normalized["item"] == item)
rejects("N dispatcher rejects I2 (already patterned)", lambda: action.normalize_action(
    {"item": "I2", "mode": "DRY", "confirm": "DRY P44 I2", "run_id": "P44-I2-001"}), "ITEM")
rejects("N dispatcher rejects confirmation typo", lambda: action.normalize_action(
    {"item": "F4", "mode": "APPLY", "confirm": "DRY P44 F4", "run_id": "P44-F4-001"}), "CONFIRM")
rejects("N dispatcher rejects placeholder run id", lambda: action.normalize_action(
    {"item": "F4", "mode": "DRY", "confirm": "DRY P44 F4", "run_id": "P44-F4-SET-UNIQUE-ID"}), "RUN_ID")

f4 = action.dispatch_spec(action.normalize_action(
    {"item": "F4", "mode": "DRY", "confirm": "DRY P44 F4", "run_id": "P44-F4-001"}), ROOT)
f5 = action.dispatch_spec(action.normalize_action(
    {"item": "F5", "mode": "APPLY", "confirm": "APPLY P44 F5", "run_id": "P44-F5-001"}), ROOT)
i3 = action.dispatch_spec(action.normalize_action(
    {"item": "I3", "mode": "REVERT", "confirm": "REVERT P44 I3", "run_id": "P44-I3-001"}), ROOT)
check("P F4 dispatch owns vis_fix", f4["owner"].endswith(os.path.join("KlaraIngest", "vis_fix.py")) and
      f4["owner_confirm"] == "DRY VISFIX", f4)
check("P F5 dispatch owns retargeted fade tool", f5["owner"].endswith(os.path.join("S1RigFade_20261009", "s1_rig_fade.py")) and
      f5["owner_confirm"] == "APPLY S1RIGFADE", f5)
check("P interaction dispatch preserves per-item revert", i3["interaction"] == 3 and i3["owner_confirm"] == "REVERT I3", i3)

with open(os.path.join(ROOT, "interaction_shadow_transition_args.json"), "r", encoding="utf-8") as handle:
    interaction_args = json.load(handle)
check("P interactions use I2 pattern reference", interaction_args["reference_interaction"] == 2)
check("P four requested interactions use current gobo stand-in", all(
    interaction_args["interactions"][key]["light_function_material"] ==
    "/Game/InfinityStage/Lighting/Gobo/MI_ShadowGobo_BoyRub" for key in ("I1", "I3", "I4", "I5")))

source = open(os.path.join(HERE, "p44_probe.py"), "r", encoding="utf-8").read()
check("P probe contains no save call", "save_asset(" not in source and "save_loaded_asset(" not in source)
check("P probe asserts unchanged dirty census", "PROBE_DIRTIED" in source and "dirty_before" in source and "dirty_after" in source)

for name, ok, detail in RESULTS:
    if not ok:
        print("FAIL", name, str(detail)[:500])
passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = len(RESULTS) - passed
print("P44_COMPONENT_HARNESS|pass=%d|fail=%d|total=%d" % (passed, failed, len(RESULTS)))
sys.exit(1 if failed else 0)
