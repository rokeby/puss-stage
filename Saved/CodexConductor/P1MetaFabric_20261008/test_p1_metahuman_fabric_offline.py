"""Offline POSITIVE/NEGATIVE harness for P1 cloth, texture, and outfit tooling."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REPORT = HERE / "p1_metahuman_fabric_harness_report.json"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


os.environ["S3LIVESACK_NO_AUTORUN"] = "1"
os.environ["P1OUTFIT_NO_AUTORUN"] = "1"
live = load("p1_livecloth", ROOT / "Saved" / "CodexConductor" / "s3_sack_livecloth.py")
outfit = load("p1_outfit", HERE / "p1_metahuman_outfit.py")
textures = load("p1_textures", ROOT / "Tools" / "S3Sackcloth" / "generate_filthy_shroud_textures.py")


tests = []


def test(name, control, fn):
    try:
        detail = fn()
        tests.append({"name": name, "control": control, "passed": True, "detail": detail})
    except Exception as exc:  # noqa: BLE001 - harness records all failures
        tests.append({"name": name, "control": control, "passed": False, "detail": str(exc),
                      "traceback": traceback.format_exc()})


def expect_raises(fn, contains):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - expected negative
        if contains not in str(exc):
            raise AssertionError("wrong refusal: %s" % exc)
        return str(exc)
    raise AssertionError("expected refusal containing " + contains)


def p1_args():
    return json.loads((HERE / "p1_metahuman_fabric_args.json").read_text(encoding="utf-8"))


def cloth_profile_positive():
    parsed = live.check_mode(p1_args(), {"BUILD": False, "APPLY": False})
    assert parsed[0] == "DRY" and parsed[2] == 3 and parsed[3]["size_m"] == 1.8
    assert parsed[4]["back_pin_figures"] == sorted(live.FIGURES)
    assert parsed[3]["head_pin_back_cm"] == 6.0
    assert parsed[3]["bending_stiffness"] < live.PARAMS["bending_stiffness"]
    assert parsed[3]["density_kg_m2"] == live.PARAMS["density_kg_m2"]
    return {"mode": parsed[0], "version": parsed[2], "size_m": parsed[3]["size_m"],
            "back_pin_figures": parsed[4]["back_pin_figures"]}


test("cloth_v3_profile_accepts_1p8_all_back_pins", "POSITIVE", cloth_profile_positive)

test("cloth_shore02_v3_is_crown_plus_back", "POSITIVE",
     lambda: live.pin_layout("Shore02_F52", 3, list(live.FIGURES)))


def rear_head_pin_positive():
    params = live.check_mode(p1_args(), {"BUILD": False, "APPLY": False})[3]
    frame = {"up_local": [0.0, 0.0, 1.0], "fwd_local": [0.0, 1.0, 0.0], "pin_local_cm": [0.0, 0.0, 0.0],
             "back": {"back_local_cm": [0.0, -30.0, -25.0], "down_back_local": [0.0, 0.0, -1.0]}}
    _sheet, placed, _metrics, problems = live.plan_geometry("Shore01_M56", frame, params, "crown+back")
    assert not problems, problems
    assert placed["pins"][0] == [0.0, -6.0, 0.0]
    assert placed["pins"][1] == [0.0, -30.0, -25.0]
    return {"rear_head_pin_cm": placed["pins"][0], "upper_back_pin_cm": placed["pins"][1]}


test("cloth_v3_rear_head_and_upper_back_pin_centres", "POSITIVE", rear_head_pin_positive)

test("cloth_v2_rejects_shore02_dual_pin", "NEGATIVE",
     lambda: expect_raises(lambda: live.check_mode({**p1_args(), "version": 2}, {"BUILD": False, "APPLY": False}),
                           "BACK_PIN_FIGURES"))

test("cloth_rejects_undersize", "NEGATIVE",
     lambda: (lambda a: expect_raises(lambda: live.check_mode(a, {"BUILD": False, "APPLY": False}), "PARAMS"))
     ({**p1_args(), "params": {**p1_args()["params"], "size_m": 1.0}}))

def cloth_dataflow_positive():
    params = live.check_mode(p1_args(), {"BUILD": False, "APPLY": False})[3]
    spec = live.dataflow_spec("/Game/Test/SM", [0.0, 0.0, 0.0], params, [0.0, -30.0, -20.0])
    problems = live.dataflow_problems(spec[0], spec[1], spec[2], params)
    assert not problems, problems
    return {"nodes": len(spec[0]), "links": len(spec[1]), "problems": problems}


test("cloth_dual_pin_dataflow_connected", "POSITIVE", cloth_dataflow_positive)


OUTFIT_BASE = {"mode": "DRY", "figures": list(outfit.FIGURES), "asset_version": 1,
               "loincloth_color": [0.16, 0.095, 0.055, 1.0], "roughness": 0.86,
               "hide_shirt": False, "accept_missing_torso": False}
SHORT = "/Game/Test/MI_WI_DefaultGarment_M_DG_bodyShapeA_Short"
SHIRT = "/Game/Test/MI_WI_DefaultGarment_M_DG_bodyShapeA_Shirt"

test("outfit_safe_colour_config", "POSITIVE", lambda: outfit.validate_args(OUTFIT_BASE, False))
def outfit_plan_positive():
    result = outfit.plan_overrides([SHORT, SHIRT, SHORT, SHIRT], "/Game/New/Loin", "/Game/New/Hidden", False)
    assert result["roles"] == ["short", "shirt", "short", "shirt"]
    assert result["target"] == ["/Game/New/Loin", SHIRT, "/Game/New/Loin", SHIRT]
    return result


test("outfit_short_recolour_shirt_preserved", "POSITIVE", outfit_plan_positive)
test("outfit_hide_refuses_missing_torso", "NEGATIVE",
     lambda: expect_raises(lambda: outfit.validate_args({**OUTFIT_BASE, "hide_shirt": True}, False), "MISSING_TORSO"))
test("outfit_unknown_slot_refused", "NEGATIVE",
     lambda: expect_raises(lambda: outfit.plan_overrides([SHORT, SHIRT, "/Game/Other/Shoes"],
                                                         "/Game/New/Loin", "/Game/New/Hidden", False),
                           "OUTFIT_SLOT_UNKNOWN"))


def texture_positive():
    a = textures.build_variant(128, textures.VARIANTS["A_ash_grey"])
    b = textures.build_variant(128, textures.VARIANTS["A_ash_grey"])
    assert all(a[k].shape == ((128, 128, 3) if k != "R" else (128, 128)) for k in a)
    assert all((a[k] == b[k]).all() for k in a)
    seams = {k: textures.seam_metrics(v) for k, v in a.items()}
    assert all(v["ratio"] < 4.0 for v in seams.values()), seams
    return seams


test("texture_deterministic_tileable_maps", "POSITIVE", texture_positive)
test("texture_rejects_non_power_of_two", "NEGATIVE",
     lambda: expect_raises(lambda: textures.validate_args("DRY", 1000, textures.DEFAULT_OUT), "SIZE"))


passed = sum(1 for row in tests if row["passed"])
controls = {kind: {"passed": sum(1 for r in tests if r["control"] == kind and r["passed"]),
                   "total": sum(1 for r in tests if r["control"] == kind)} for kind in ("POSITIVE", "NEGATIVE")}
report = {"passed": passed, "total": len(tests), "controls": controls, "tests": tests,
          "unreal_run": False, "blender_run": False}
REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("P1_META_FABRIC_HARNESS|%d/%d|positive=%d/%d|negative=%d/%d|report=%s" %
      (passed, len(tests), controls["POSITIVE"]["passed"], controls["POSITIVE"]["total"],
       controls["NEGATIVE"]["passed"], controls["NEGATIVE"]["total"], REPORT))
if passed != len(tests):
    for row in tests:
        if not row["passed"]:
            print("FAIL|%s|%s" % (row["name"], row["detail"]))
    raise SystemExit(1)
