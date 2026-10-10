"""Positive/negative offline harness. Imports neither Unreal nor Blender."""
from __future__ import annotations

import ast
import copy
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p02_lighting_lean as L  # noqa: E402

RESULTS = []


def check(name, value):
    ok = bool(value)
    RESULTS.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name)


def raises(fn, token):
    try:
        fn()
    except Exception as exc:
        return token in str(exc)
    return False


def row(number, ordinal, role, enabled=True, intensity=400.0, shadow=True, scatter=0.6, radius=2600.0):
    return {"guid": "%032X" % number, "label": "P02 P01STRUCT B%02d %s" % (ordinal, role),
            "kind": "LIGHT", "enabled": enabled,
            "lighting": {"intensity": intensity, "attenuation_radius_cm": radius,
                         "cast_shadows": shadow, "cast_volumetric_shadow": False,
                         "volumetric_scattering_intensity": scatter}}


roles = ("LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "TOP_L", "TOP_R", "BEAM_R", "ENTRY_TOP")
targets = []
counter = 1
for ordinal in range(1, 24):
    made = []
    for _ in range(18):
        r = roles[(counter - 1) % len(roles)]
        made.append(row(counter, ordinal, r, enabled=r != "ENTRY_TOP", intensity=1000.0 if r == "LOW_SIDE_L_KEY" else 400.0))
        counter += 1
    targets.append({"ordinal": ordinal, "cue_guid": "CUE-%02d" % ordinal, "show_index": ordinal,
                    "added": [{"guid": x["guid"]} for x in made], "after_rows": made})
origin = {"status": "saved_readback_verified", "run": "20261009-224343", "added_count": 414,
          "args": {"target_passage": "P02"}, "plan": {"targets": targets}}
car = {"mode": "APPLY", "mutated": True, "run": "P02CAR-TUNE-20261010-012009",
       "label": "P02 Car Light (trial, Gary to tune)", "actor_path": "/Game/Test.Car",
       "values": {"attenuation_radius_cm": 10000.0, "peak_intensity": 9000.0,
                  "outer_cone_degrees": 28.0}}

args = L.check_args({})
plan = L.build_plan(origin, car, args)
check("default is DRY", args["mode"] == "DRY")
check("negative APPLY confirmation", raises(lambda: L.check_args({"mode": "APPLY"}), "CONFIRM_MISSING"))
check("negative APPLY plan hash", raises(lambda: L.check_args(
    {"mode": "APPLY", "confirm": "APPLY P02LIGHTLEAN"}), "EXPECTED_PLAN_SHA256_REQUIRED"))
check("negative hero drift", raises(lambda: L.check_args({"hero_ordinals": [3, 7, 12]}), "HERO_ORDINALS"))
check("negative key scale", raises(lambda: L.check_args({"key_intensity_scale": 3.0}), "KEY_SCALE"))
check("negative car radius too wide", raises(lambda: L.check_args({"car_radius_cm": 10000.0}), "CAR_RADIUS"))
check("record scope is exactly 414", plan["counts"]["owned"] == 414)
check("plan is deterministic", plan["plan_sha256"] == L.build_plan(origin, car, args)["plan_sha256"])
check("lean disables owned lights", plan["counts"]["owned_enabled_after"] < plan["counts"]["owned_enabled_before"])
check("lean cuts shadow flags", plan["counts"]["owned_shadow_flags_after"] < plan["counts"]["owned_shadow_flags_before"])
expected_hero_scatter = sum(1 for ordinal, _cue, _index, item in L.origin_rows(origin)
                            if ordinal in L.HERO_ORDINALS and L.role(item["label"]) == "BEAM_R"
                            and item["enabled"] and item["lighting"]["volumetric_scattering_intensity"] > 0.0)
check("only recorded hero beams keep enabled scattering",
      plan["counts"]["owned_positive_scatter_enabled_after"] == expected_hero_scatter)
check("car radius returns to measured reach proposal", plan["car"]["after_radius_cm"] == 4600.0)
keys = [x for x in plan["changes"] if x["role"] == "LOW_SIDE_L_KEY"]
check("keys strengthen", all(x["after"]["lighting"].get("intensity", 0) >
                              x["before"]["lighting"].get("intensity", 0) for x in keys))
check("key radii cap", all(x["after"]["lighting"].get("attenuation_radius_cm", 0) <= 1800.0 for x in keys))
check("shadows only on hero keys", all(not x["after"]["lighting"].get("cast_shadows", False) or
                                        (x["role"] == "LOW_SIDE_L_KEY" and x["ordinal"] in L.HERO_ORDINALS)
                                        for x in plan["changes"]))
check("negative origin run drift", raises(lambda: L.build_plan(dict(origin, run="OTHER"), car, args),
                                           "ORIGIN_RUN_DRIFT"))
bad_car = copy.deepcopy(car)
bad_car["values"]["attenuation_radius_cm"] = 9000.0
check("negative car record drift", raises(lambda: L.build_plan(origin, bad_car, args),
                                           "CAR_RECORD_RADIUS_NOT_10000"))
for name in ("p02_lighting_lean.py", "p02_lighting_lean_run.py", "test_p02_lighting_lean_offline.py"):
    ast.parse((HERE / name).read_text(encoding="utf-8"))
check("all shipped Python parses", True)
check("negative syntax control", raises(lambda: ast.parse("def broken(:\n"), "invalid syntax"))
request = json.loads((HERE / "p02_lighting_lean_request.json").read_text(encoding="utf-8"))
check("request routes guarded runner", request["arguments"]["arguments"]["relativeSavedPath"].endswith(
    "p02_lighting_lean_run.py"))

failed = [name for name, ok in RESULTS if not ok]
summary = "P02LIGHTLEAN_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed))
print("\n" + summary)
(HERE / "P02_LIGHTING_LEAN_OFFLINE_HARNESS_RESULTS.md").write_text(
    "# P02 lighting lean offline harness\n\n- Command: `python Saved/CodexFlatV3/p02lighting/test_p02_lighting_lean_offline.py`\n"
    "- Result: **%d passed, %d failed**\n- Marker: `%s`\n\nNo Unreal, MCP, PIE or package mutation was used.\n" %
    (len(RESULTS) - len(failed), len(failed), summary), encoding="utf-8")
sys.exit(1 if failed else 0)
