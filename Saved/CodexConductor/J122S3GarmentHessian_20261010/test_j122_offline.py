"""Positive and negative offline controls for Job 122. Never imports Unreal."""
from __future__ import annotations

import json
import os

import j122_core as C

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def case(name, control, fn):
    try:
        fn(); RESULTS.append({"name": name, "control": control, "passed": True})
    except Exception as exc:
        RESULTS.append({"name": name, "control": control, "passed": False, "error": repr(exc)})


def rejects(fn, token):
    try: fn()
    except Exception as exc:
        assert token in str(exc), (token, str(exc)); return
    raise AssertionError("expected rejection " + token)


BASE = {"mode": "PROBE", "weave_tiling": 8.0, "print_texture_kind": "tint",
        "print_color": [1, 1, 1, 1], "print_strength": 1.0, "confirm": ""}
NAMES = {"texture": ["DetailTex_Color", "detailTex_normal", "B_DetailTex_Color", "B_detailTex_normal",
                     "Print1Map", "Masks"],
         "scalar": ["DetailTex_UVTtiling", "B_DetailTex_UVTtiling", "Print1Tiling", "Print1Strength"],
         "vector": ["Print1ColorA", "Print1ColorB", "Print1ColorC"],
         "static_switch": ["DoDetailColor", "DoDetailNormal", "B_DoDetailColor", "B_DoDetailNormal",
                           "DoMaterialC", "MaterialB option", "bDoPrint1"]}
GRAPH = {"masks": {"parameter_found": True,
                   "channel_consumers": [{"class": "MaterialExpressionComponentMask", "channel": "R"}]},
         "parameter_consumers": {"DetailTex_Color": [{}], "detailTex_normal": [{}],
                                 "B_DetailTex_Color": [{}], "B_detailTex_normal": [{}], "Print1Map": [{}]}}

case("twelve_exact_targets", "POSITIVE", lambda: len(C.targets()) == 12 and len(set(C.targets())) == 12
     or (_ for _ in ()).throw(AssertionError()))
case("args_probe", "POSITIVE", lambda: C.validate_args(BASE, False))
case("args_apply", "POSITIVE", lambda: C.validate_args({**BASE, "mode": "APPLY", "confirm": "APPLY J122GARMENTS"}, False))
case("layer_a_ready", "POSITIVE", lambda: C.plan(NAMES, {"DoMaterialC": False, "MaterialB option": False}, GRAPH)["apply_ready"]
     or (_ for _ in ()).throw(AssertionError()))
case("layer_b_ready", "POSITIVE", lambda: C.plan(NAMES, {"DoMaterialC": False, "MaterialB option": True}, GRAPH)["apply_ready"]
     or (_ for _ in ()).throw(AssertionError()))
case("stains_are_one_to_one", "POSITIVE", lambda: sorted(C.STAIN_BY_FIGURE.values()) == list(range(3, 9))
     or (_ for _ in ()).throw(AssertionError()))
case("reject_apply_confirm", "NEGATIVE", lambda: rejects(
    lambda: C.validate_args({**BASE, "mode": "APPLY"}, False), "CONFIRM"))
case("reject_record_collision", "NEGATIVE", lambda: rejects(
    lambda: C.validate_args({**BASE, "mode": "APPLY", "confirm": "APPLY J122GARMENTS"}, True), "RECORD_EXISTS"))
case("reject_bad_tiling", "NEGATIVE", lambda: rejects(
    lambda: C.validate_args({**BASE, "weave_tiling": 0}, False), "WEAVE_TILING"))
case("reject_missing_switch_evidence", "NEGATIVE", lambda: rejects(
    lambda: C.plan(NAMES, {"DoMaterialC": False}, GRAPH), "ACTIVE_SWITCHES_MISSING"))
case("c_layer_refuses_missing_detail_path", "NEGATIVE", lambda: (
    (lambda p: (not p["apply_ready"] and "ACTIVE_LAYER_C_HAS_NO_EXPOSED_DETAIL_COLOR_NORMAL_PAIR" in p["problems"]) or
     (_ for _ in ()).throw(AssertionError()))(C.plan(NAMES, {"DoMaterialC": True, "MaterialB option": True}, GRAPH))))
case("missing_masks_channel_refuses", "NEGATIVE", lambda: (
    (lambda p: (not p["apply_ready"] and "MASKS_CHANNEL_USE_UNPROVED" in p["problems"]) or
     (_ for _ in ()).throw(AssertionError()))(C.plan(NAMES, {"DoMaterialC": False, "MaterialB option": False},
                                                      {**GRAPH, "masks": {"parameter_found": True,
                                                                          "channel_consumers": []}}))))


def static_guards():
    source = open(os.path.join(HERE, "j122_editor.py"), encoding="utf-8").read()
    assert "delete_asset" not in source and "delete_material_expression" not in source
    assert "get_material_expressions(container)" in source
    assert "get_material_function_expressions(container)" in source
    assert "get_inputs_for_material_expression" in source
    assert '"Backups", "PreJ122Garments-"' in source
    assert "save_exact(core.targets())" in source
    assert "DIRTY_SCOPE" in source and "READ_ONLY_PROBE_DIRTIED" in source
    assert "restore_touched_values" in source
    assert "clear_all_material_instance_parameters" not in source


case("editor_scope_and_readback_guards", "POSITIVE", static_guards)

passed = sum(row["passed"] for row in RESULTS)
positive = [row for row in RESULTS if row["control"] == "POSITIVE"]
negative = [row for row in RESULTS if row["control"] == "NEGATIVE"]
report = {"schema": C.SCHEMA, "result": "PASS" if passed == len(RESULTS) else "FAIL",
          "passed": passed, "total": len(RESULTS),
          "positive_passed": sum(row["passed"] for row in positive), "positive_total": len(positive),
          "negative_passed": sum(row["passed"] for row in negative), "negative_total": len(negative),
          "unreal_started": False, "blender_started": False, "cases": RESULTS}
with open(os.path.join(HERE, "j122_harness_report.json"), "w", encoding="utf-8", newline="\n") as handle:
    json.dump(report, handle, indent=2, sort_keys=True); handle.write("\n")
print("J122_HARNESS_%s|passed=%d/%d|positive=%d/%d|negative=%d/%d|unreal=0|blender=0" %
      (report["result"], passed, len(RESULTS), report["positive_passed"], report["positive_total"],
       report["negative_passed"], report["negative_total"]))
if passed != len(RESULTS):
    for row in RESULTS:
        if not row["passed"]: print("FAILED|%s|%s" % (row["name"], row.get("error")))
    raise SystemExit(1)
