"""Offline +/- harness for P40. No Unreal or Blender process is started."""
from __future__ import annotations

import copy
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p40_core as C  # noqa: E402

RESULTS = []


def case(name, control, fn):
    try:
        fn()
        RESULTS.append({"name": name, "control": control, "passed": True})
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"name": name, "control": control, "passed": False,
                        "error": repr(exc), "trace": traceback.format_exc()})


def raises(token, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        assert token in str(exc), (token, repr(exc))
        return
    raise AssertionError("expected " + token)


def args(**updates):
    value = {"mode": "DRY", "extra_count": 0, "seed": 4005,
             "cloth_reset": {"enabled": False}, "outfit": {"enabled": True, "asset_version": 1}}
    value.update(updates)
    return value


def cameras():
    return [
        {"label": "S3 Shot B02", "frame": 0, "xy": [12000.0, 158000.0], "yaw_deg": -90.0},
        {"label": "S3 Shot B06", "frame": 100, "xy": [16000.0, 162000.0], "yaw_deg": 90.0},
    ]


case("args_dry_valid", "POSITIVE", lambda: C.validate_args(args())["mode"] == "DRY" or (_ for _ in ()).throw(AssertionError()))
case("args_extra_five_valid", "POSITIVE", lambda: C.validate_args(args(extra_count=5))["extra_count"] == 5 or (_ for _ in ()).throw(AssertionError()))
case("args_apply_confirm_valid", "POSITIVE", lambda: C.validate_args(args(mode="APPLY", confirm="APPLY P40SHORE"))["mode"] == "APPLY" or (_ for _ in ()).throw(AssertionError()))
case("args_revert_record_valid", "POSITIVE", lambda: C.validate_args(args(mode="REVERT", confirm="REVERT P40SHORE"), True)["mode"] == "REVERT" or (_ for _ in ()).throw(AssertionError()))
case("args_bad_extra_refused", "NEGATIVE", lambda: raises("EXTRA_COUNT", lambda: C.validate_args(args(extra_count=6))))
case("args_bool_extra_refused", "NEGATIVE", lambda: raises("EXTRA_COUNT", lambda: C.validate_args(args(extra_count=True))))
case("args_apply_confirm_refused", "NEGATIVE", lambda: raises("CONFIRM", lambda: C.validate_args(args(mode="APPLY", confirm=""))))
case("args_duplicate_record_refused", "NEGATIVE", lambda: raises("RECORD_EXISTS", lambda: C.validate_args(args(mode="APPLY", confirm="APPLY P40SHORE"), True)))
case("args_revert_without_record_refused", "NEGATIVE", lambda: raises("NO_RECORD", lambda: C.validate_args(args(mode="REVERT", confirm="REVERT P40SHORE"), False)))
case("cloth_inferred_requires_ack", "NEGATIVE", lambda: raises("CLOTH_RESET_INFERRED", lambda: C.validate_args(
    args(mode="APPLY", confirm="APPLY P40SHORE", cloth_reset={"enabled": True}), False)))
case("cloth_inferred_ack_valid", "POSITIVE", lambda: C.validate_args(
    args(mode="APPLY", confirm="APPLY P40SHORE",
         cloth_reset={"enabled": True, "acknowledge_inferred_behavior": True}), False)["cloth_reset"]["enabled"] or (_ for _ in ()).throw(AssertionError()))


def deterministic_candidates():
    a, b = C.candidate_rows(4005, 20), C.candidate_rows(4005, 20)
    assert a == b and all(len(row["draws"]) == 5 for row in a)


case("candidate_seed_deterministic_five_draws", "POSITIVE", deterministic_candidates)
case("candidate_seed_changes", "NEGATIVE_CONTROL", lambda: C.candidate_rows(1, 4) != C.candidate_rows(2, 4) or (_ for _ in ()).throw(AssertionError()))
case("candidate_empty_refused", "NEGATIVE", lambda: raises("CANDIDATE_COUNT", lambda: C.candidate_rows(1, 0)))


def placement_zero_extra():
    cfg = C.validate_args(args())
    plan = C.build_placement_plan(cfg, [], cameras())
    assert len(plan["placements"]) == 1
    assert plan["placements"][0]["label"] == "Shore05_M53 Clam"
    assert plan["placements"][0]["source"] == "Shore05_M53"


def placement_five_extra():
    cfg = C.validate_args(args(extra_count=5))
    plan = C.build_placement_plan(cfg, [], cameras())
    assert len(plan["placements"]) == 6
    assert all(row["source"] in C.FIGURES for row in plan["placements"])
    for left, right in zip(plan["placements"], plan["placements"][1:]):
        assert left["label"] != right["label"]


case("placement_mandatory_shore05", "POSITIVE", placement_zero_extra)
case("placement_up_to_five_variants", "POSITIVE", placement_five_extra)
case("placement_requires_camera_reads", "NEGATIVE", lambda: raises("CAMERAS_UNREADABLE", lambda: C.build_placement_plan(C.validate_args(args()), [], [])))
case("placement_bounds_unordered_refused", "NEGATIVE", lambda: raises("PLACEMENT_BOUNDS", lambda: C.validate_args(args(placement_bounds_local_cm=[1, 0, -1, 1]))))


def sightline_control():
    cfg = C.validate_args(args())
    cam = [{"label": "B", "xy": [0.0, 0.0], "yaw_deg": 0.0}]
    row = {"local_xy_cm": [-C.DOCK_ORIGIN[0] + 500.0, -C.DOCK_ORIGIN[1]], "yaw_deg": 0.0}
    bad = C.placement_violations(row, [], cam, cfg)
    assert "sightline:B" in bad


case("sightline_tube_refuses_candidate", "NEGATIVE_CONTROL", sightline_control)


def spacing_control():
    cfg = C.validate_args(args())
    row = C.candidate_rows(cfg["seed"], 1)[0]
    world = (row["local_xy_cm"][0] + C.DOCK_ORIGIN[0], row["local_xy_cm"][1] + C.DOCK_ORIGIN[1])
    assert "figure_clearance" in C.placement_violations(row, [world], cameras(), cfg)


case("figure_spacing_refuses_candidate", "NEGATIVE_CONTROL", spacing_control)
case("dune_height_is_shared_authority", "POSITIVE", lambda: C.sand_height.__module__ == "s3_beach_v2" or (_ for _ in ()).throw(AssertionError(C.sand_height.__module__)))


def chains_positive():
    for figure in C.FIGURES:
        rows = C.forward_chain(figure, 0.37, 72)
        C.validate_chain(rows, 72)
        assert all(row["reverse"] is False for row in rows)


case("all_six_forward_only_chains_cover_scene", "POSITIVE", chains_positive)


def chain_reverse_mutation():
    rows = C.forward_chain("Shore05_M53", 0.2, 72)
    rows[len(rows) // 2]["reverse"] = True
    raises("MOTION_REVERSE", lambda: C.validate_chain(rows, 72))


def chain_overlap_mutation():
    rows = C.forward_chain("Shore05_M53", 0.2, 72)
    rows[1]["range"][0] += 1
    raises("MOTION_XFADE", lambda: C.validate_chain(rows, 72))


def chain_weight_mutation():
    rows = C.forward_chain("Shore05_M53", 0.2, 72)
    rows[1]["ease_in"] = 0
    raises("MOTION_WEIGHT_RAMP", lambda: C.validate_chain(rows, 72))


case("chain_reverse_mutation_caught", "NEGATIVE", chain_reverse_mutation)
case("chain_overlap_mutation_caught", "NEGATIVE", chain_overlap_mutation)
case("chain_weight_mutation_caught", "NEGATIVE", chain_weight_mutation)


def colour_product():
    got = C.cloth_colour([0.5, 0.75, 1.0, 1.0])
    want = [C.WEAVE_MEAN_LINEAR[0] * 0.5, C.WEAVE_MEAN_LINEAR[1] * 0.75,
            C.WEAVE_MEAN_LINEAR[2], 1.0]
    assert max(abs(got[i] - want[i]) for i in range(4)) < 1.0e-12


case("underwear_colour_is_weave_mean_times_tint", "POSITIVE", colour_product)
case("underwear_tint_short_refused", "NEGATIVE", lambda: raises("WEAVE_TINT", lambda: C.cloth_colour([1.0, 1.0])))
case("colour_parameter_unique", "POSITIVE", lambda: C.choose_colour_parameter(["Roughness", "Base Color Tint"], ["BaseColor Tint"]) == "Base Color Tint" or (_ for _ in ()).throw(AssertionError()))
case("colour_parameter_missing_refused", "NEGATIVE", lambda: raises("COLOUR_PARAMETER", lambda: C.choose_colour_parameter(["Roughness"], ["Tint"])))
case("colour_parameter_ambiguous_refused", "NEGATIVE", lambda: raises("COLOUR_PARAMETER", lambda: C.choose_colour_parameter(["Tint", "Color"], ["Tint", "Color"])))
case("stills_include_first_visible_boundary", "POSITIVE", lambda: any(abs(row["scene_seconds"] - 15.0) < 1e-6 for row in C.stills_plan()) or (_ for _ in ()).throw(AssertionError()))


def static_editor_guards():
    source = open(os.path.join(HERE, "p40_editor.py"), encoding="utf-8").read()
    assert "delete_asset" not in source
    assert "MaterialFactoryNew" not in source
    assert "save_all" not in source.lower()
    assert "set_material(index, child)" in source
    assert 'set_property_name_and_path("bHidden", "bHidden")' in source
    assert "sequence.get_spawnables()" in source
    assert "sequence.make_range(int(frame), 1)" in source
    apply_source = source[source.index("def apply("):source.index("def verify(")]
    assert apply_source.index("backup_row = backup") < apply_source.index("spawn_placements(")
    assert "DIRTY_CENSUS" in source and "POST_SAVE_DIRTY" in source
    assert "P40SHORE_APPLY_OK" in source and "P40SHORE_REVERT_OK" in source


case("editor_static_safety_guards", "POSITIVE", static_editor_guards)

passed = sum(1 for row in RESULTS if row["passed"])
positive = [row for row in RESULTS if row["control"] == "POSITIVE"]
negative = [row for row in RESULTS if row["control"] != "POSITIVE"]
report = {"schema": C.SCHEMA, "result": "PASS" if passed == len(RESULTS) else "FAIL",
          "passed": passed, "total": len(RESULTS),
          "positive_passed": sum(1 for row in positive if row["passed"]), "positive_total": len(positive),
          "negative_passed": sum(1 for row in negative if row["passed"]), "negative_total": len(negative),
          "unreal_started": False, "blender_started": False, "cases": RESULTS}
with open(os.path.join(HERE, "p40_harness_report.json"), "w", encoding="utf-8", newline="\n") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
print("P40_HARNESS_%s|passed=%d/%d|positive=%d/%d|negative=%d/%d|unreal=0|blender=0" %
      (report["result"], passed, len(RESULTS), report["positive_passed"], report["positive_total"],
       report["negative_passed"], report["negative_total"]))
if passed != len(RESULTS):
    for row in RESULTS:
        if not row["passed"]:
            print("FAILED|%s|%s" % (row["name"], row["error"]))
    raise SystemExit(1)
