"""Positive and negative offline controls for job 115. Never imports Unreal."""
from __future__ import annotations

import json
import os
import tempfile

from PIL import Image

import j115_core as C

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def case(name, control, fn):
    try:
        fn()
        RESULTS.append({"name": name, "control": control, "passed": True})
    except Exception as exc:
        RESULTS.append({"name": name, "control": control, "passed": False, "error": repr(exc)})


def rejects(fn, token):
    try:
        fn()
    except Exception as exc:
        assert token in str(exc), (token, str(exc))
        return
    raise AssertionError("expected rejection " + token)


BASE = {
    "mode": "DRY", "asset_version": 1, "fallback_roughness": 0.84, "fallback_specular": 0.18,
    "parameter_candidates": {"base_color_texture": ["BC"], "normal_texture": ["N"],
                             "tint_vector": ["Tint"], "roughness_scalar": ["Roughness"],
                             "specular_scalar": ["Specular"]},
    "texture_mode_static_switches": {"Use Fabric Maps": True},
}


case("args_dry", "POSITIVE", lambda: C.validate_args(BASE, False))
case("args_apply_confirm", "POSITIVE", lambda: C.validate_args({**BASE, "mode": "APPLY", "confirm": "APPLY J115SHIRTS"}, False))
case("texture_strategy", "POSITIVE", lambda: (
    C.plan_parameter_strategy({"texture": ["BC", "N"], "vector": [], "scalar": []}, BASE["parameter_candidates"])["mode"] == "textures"
    or (_ for _ in ()).throw(AssertionError())))
case("fallback_strategy", "POSITIVE", lambda: (
    C.plan_parameter_strategy({"texture": [], "vector": ["Tint"], "scalar": ["Roughness", "Specular"]},
                              BASE["parameter_candidates"])["mode"] == "tint_roughness"
    or (_ for _ in ()).throw(AssertionError())))


def scope_positive():
    rows = [{"figure": f, "label": C.BASE_LABELS[f], "path": "/Actor/" + f, "tags": []} for f in C.FIGURES]
    rows.append({"figure": "Shore05_M53", "label": "S3 Crowd 01 Shore05_M53",
                 "path": "/Actor/Variant", "tags": [C.P40_TAG]})
    assert len(C.expected_actor_scope(rows)) == 7


case("six_plus_p40_variant_scope", "POSITIVE", scope_positive)


def mean_positive():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "source.png")
        Image.new("RGB", (4, 2), (128, 64, 32)).save(path)
        got = C.texture_mean(path)
        assert got["size"] == [4, 2] and got["sampled_pixels"] == 8
        assert max(abs(a - b) for a, b in zip(got["mean_srgb"], [128/255, 64/255, 32/255])) < 1e-9
        expected_linear = [C.srgb_to_linear(x) for x in [128/255, 64/255, 32/255]]
        assert max(abs(a - b) for a, b in zip(got["mean_linear"], expected_linear)) < 1e-9


case("source_png_mean", "POSITIVE", mean_positive)
case("diagnostic_matrix_complete", "POSITIVE", lambda: (
    {row["candidate"] for row in C.diagnostic_fix_matrix()} == set(C.DIAG_CANDIDATES)
    or (_ for _ in ()).throw(AssertionError())))
case("reject_apply_without_confirm", "NEGATIVE", lambda: rejects(
    lambda: C.validate_args({**BASE, "mode": "APPLY"}, False), "CONFIRM"))
case("reject_record_collision", "NEGATIVE", lambda: rejects(
    lambda: C.validate_args({**BASE, "mode": "APPLY", "confirm": "APPLY J115SHIRTS"}, True), "RECORD_EXISTS"))
case("reject_revert_without_record", "NEGATIVE", lambda: rejects(
    lambda: C.validate_args({**BASE, "mode": "REVERT", "confirm": "REVERT J115SHIRTS"}, False), "NO_RECORD"))
case("reject_nonboolean_switch", "NEGATIVE", lambda: rejects(
    lambda: C.validate_args({**BASE, "texture_mode_static_switches": {"Use": 1}}, False), "STATIC_SWITCHES"))
case("reject_incomplete_texture_pair", "NEGATIVE", lambda: rejects(
    lambda: C.plan_parameter_strategy({"texture": ["BC"], "vector": ["Tint"], "scalar": ["Roughness"]},
                                      BASE["parameter_candidates"]), "TEXTURE_PAIR_INCOMPLETE"))
case("reject_missing_fallback_tint", "NEGATIVE", lambda: rejects(
    lambda: C.plan_parameter_strategy({"texture": [], "vector": [], "scalar": ["Roughness"]},
                                      BASE["parameter_candidates"]), "TINT_VECTOR_MISSING"))


def scope_missing_base():
    rows = [{"figure": f, "label": C.BASE_LABELS[f], "path": "/Actor/" + f, "tags": []}
            for f in C.FIGURES[:-1]]
    rejects(lambda: C.expected_actor_scope(rows), "BASE_ACTOR_COUNTS")


case("reject_missing_base_actor", "NEGATIVE", scope_missing_base)


def static_editor_guards():
    source = open(os.path.join(HERE, "j115_editor.py"), encoding="utf-8").read()
    assert "delete_asset" not in source and "delete_material_expression" not in source
    assert "set_material_instance_static_switch_parameter_value" in source
    assert "get_material_instance_static_switch_parameter_value" in source
    assert "component.set_material(slot, child)" in source
    assert "resolved_after" in source and "parameter_readback" in source
    assert "Backups\", \"PreJ115S3Shirts-" in source
    assert "save_exact(packages, world, True)" in source


case("editor_create_only_readback_guards", "POSITIVE", static_editor_guards)

passed = sum(1 for row in RESULTS if row["passed"])
positive = [row for row in RESULTS if row["control"] == "POSITIVE"]
negative = [row for row in RESULTS if row["control"] == "NEGATIVE"]
report = {"schema": C.SCHEMA, "result": "PASS" if passed == len(RESULTS) else "FAIL",
          "passed": passed, "total": len(RESULTS),
          "positive_passed": sum(row["passed"] for row in positive), "positive_total": len(positive),
          "negative_passed": sum(row["passed"] for row in negative), "negative_total": len(negative),
          "unreal_started": False, "blender_started": False, "cases": RESULTS}
with open(os.path.join(HERE, "j115_harness_report.json"), "w", encoding="utf-8", newline="\n") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
print("J115_HARNESS_%s|passed=%d/%d|positive=%d/%d|negative=%d/%d|unreal=0|blender=0" %
      (report["result"], passed, len(RESULTS), report["positive_passed"], report["positive_total"],
       report["negative_passed"], report["negative_total"]))
if passed != len(RESULTS):
    for row in RESULTS:
        if not row["passed"]:
            print("FAILED|%s|%s" % (row["name"], row.get("error")))
    raise SystemExit(1)
