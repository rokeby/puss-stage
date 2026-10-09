"""Offline positive/negative harness for all P43 lighting deliverables."""
from __future__ import annotations

import ast
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p03_lighting_as_p01 as RELIGHT  # noqa: E402
import opening_lighting_p13 as OPENING  # noqa: E402
import s2_lighting_seam as SEAM  # noqa: E402

RESULTS = []


def check(name, condition):
    ok = bool(condition); RESULTS.append((name, ok)); print(("PASS " if ok else "FAIL ") + name)


def raises(fn, token):
    try:
        fn()
    except Exception as exc:  # deliberate negative controls
        return token in str(exc)
    return False


def light(label, shadow=False, volumetric=False, cached=False, function=None):
    return {"guid": label, "label": label, "kind": "LIGHT", "enabled": True,
            "relative_transform": {}, "effect": {},
            "lighting": {"color": [1, .5, .25, 1], "cast_shadows": shadow,
                         "cast_volumetric_shadow": volumetric,
                         "force_cached_shadows_for_movable_primitives": cached,
                         "light_function_material": function,
                         "drama": {"after_pass": "HOLD"}}}


def cue(prefix, ordinal, rows):
    return {"show_index": ordinal, "guid": "%s-%02d" % (prefix, ordinal),
            "label": "%s Wing %03d" % (prefix, ordinal), "attachments": rows,
            "wing_y": [-900, 900], "tags": []}


# P02 generalisation + exact confirm.
p02 = RELIGHT.check_args({"target_passage_number": 2})
check("relight + target context P02", RELIGHT.target_context(2)["mark"] == "P02ASP01")
check("relight + P02 APPLY confirm", RELIGHT.check_args({"target_passage_number": 2, "mode": "APPLY",
      "confirm": "APPLY P02ASP01", "expected_plan_sha256": "a" * 64})["mode"] == "APPLY")
check("relight - P03 confirm cannot authorize P02", raises(lambda: RELIGHT.check_args({
      "target_passage_number": 2, "mode": "APPLY", "confirm": "APPLY P03ASP01",
      "expected_plan_sha256": "a" * 64}), "CONFIRM_MISSING"))
check("relight - P01 cannot be target", raises(lambda: RELIGHT.check_args({"target_passage_number": 1}),
                                                "TARGET_PASSAGE_NUMBER"))

source = [cue("P01", 1, [light("P01 Wing 001 KEY", True, True), light("P01 Wing 001 FILL")])]
target = [cue("P02", 1, [light("P02 Wing 001 OLD")])]
plan = RELIGHT.build_plan(source, target, p02)
cvars = {"r.Shadow.Virtual.Enable": 1, "r.Shadow.Virtual.OnePassProjection.MaxLightsPerPixel": 16,
         "r.VolumetricFog.InjectShadowedLightsSeparately": 1}
gate = RELIGHT.evaluate_performance_gate(plan, cvars, p02["performance_gate"])
check("relight + perf gate counts lights/shadows/VSM", gate["ok"] and gate["metrics"]["total_lights"] == 2 and
      gate["metrics"]["shadow_casting_lights"] == 1 and gate["metrics"]["volumetric_shadow_lights"] == 1)
tight = json.loads(json.dumps(p02["performance_gate"])); tight["max_shadow_casting_lights"] = 0
check("relight - perf gate refuses shadow excess", not RELIGHT.evaluate_performance_gate(plan, cvars, tight)["ok"])
bad_cvars = dict(cvars, **{"r.Shadow.Virtual.Enable": 0})
check("relight - perf gate refuses VSM mismatch", not RELIGHT.evaluate_performance_gate(plan, bad_cvars,
                                                                                         p02["performance_gate"])["ok"])

# S2 seam: every row remains in output; aggregate delta and exact adjustment planning.
p02_rows = [{"label": "P02 A", "kind": "light", "visible": True, "intensity": 100,
             "cast_shadows": True},
            {"label": "P02 B", "kind": "light", "visible": True, "intensity": 50,
             "cast_shadows": False}]
samples = [{"frame": 0, "shot": "boundary", "shot_sample": False,
            "rows": [{"label": "S2 A", "kind": "light", "visible": True, "intensity": 25,
                      "cast_shadows": True},
                     {"label": "PP", "kind": "post_process", "visible": True, "exposure_bias": -1.0},
                     {"label": "Fog", "kind": "height_fog", "visible": True, "fog_density": .02}]},
           {"frame": 100, "shot": "Shot 1", "shot_sample": True,
            "rows": [{"label": "S2 A", "kind": "light", "visible": False, "intensity": 25,
                      "cast_shadows": True}]}]
probe = SEAM.analyse_probe(p02_rows, samples, [-2, -1])
check("seam + preserves every evaluated row", len(probe["s2_samples"][0]["rows"]) == 3)
check("seam + represents negative boundary window without claiming runtime evaluation",
      len(probe["p02_window"]) == 2 and "not evaluated" in probe["p02_window"][0]["source"])
check("seam + reports intensity and visible-count deltas", probe["seam_delta"]["visible_intensity_sum"] == -125 and
      probe["seam_delta"]["visible_light_count"] == -1)
check("seam + reports every shot sample", probe["shot_summaries"][0]["shot"] == "Shot 1")
args = SEAM.validate_args({"mode": "DRY", "confirm": "DRY P43S2LIGHT", "adjustments": [{
    "binding": "S2 A", "property": "Intensity", "factor": 1.5, "offset": 0,
    "start_frame": 100, "end_frame": 200}]})
adj = SEAM.build_adjustment_plan(probe, args, {("S2 A", "Intensity"): 25})
check("seam + args factor makes exact scoped plan", adj["count"] == 1 and adj["adjustments"][0]["target"] == 37.5)
check("seam - refuses wildcard/missing target", raises(lambda: SEAM.build_adjustment_plan(
      probe, args, {("Other", "Intensity"): 25}), "ADJUSTMENT_TARGET_MISSING"))
check("seam - APPLY needs probe digest", raises(lambda: SEAM.validate_args({
      "mode": "APPLY", "confirm": "APPLY P43S2LIGHT"}), "EXPECTED_PROBE_DIGEST"))

# P30: exact six-slot subset, bay 1 refused, one mesh, other models reported.
opening = OPENING.build_plan({})
facade = [row for row in opening["fixtures"] if row["role"] == "facade_par"]
check("P30 + exact six non-bay-1 facade slots", [row["facade_slot"] for row in facade] == [2, 3, 4, 5, 6, 7])
check("P30 + bay-1 practical subset empty", opening["p01_lights"] == [])
audit = OPENING.parcan_mesh_audit(opening["fixtures"], opening["params"]["parcan_mesh_path"], [
    {"actor": "Other can", "mesh": "/Game/Other/SM_ParCan_Old"}])
check("P30 + one planned parcan model", audit["ok"] and len({row["mesh"] for row in audit["planned"]}) == 1)
check("P30 + reports other show model", len(audit["other_parcan_models_in_show"]) == 1)
check("P30 - bay 1 selection refused", raises(lambda: OPENING.build_plan({"facade_par_indices": [1, 2, 3]}),
                                                   "BAY1_PRACTICAL_REFUSED"))
broken = json.loads(json.dumps(opening["fixtures"])); next(r for r in broken if r["role"] == "facade_par")["housing_mesh"] = "/Game/Bad"
check("P30 - mixed planned models fail audit", not OPENING.parcan_mesh_audit(
      broken, opening["params"]["parcan_mesh_path"])["ok"])

# Shipped artifacts parse and route only project-Saved runners.
names = ["p03_lighting_as_p01.py", "passage_lighting_as_p01_run.py", "s2_lighting_seam.py",
         "s2_lighting_seam_run.py", "opening_lighting_p13.py", "test_p43_lighting_offline.py"]
for name in names:
    ast.parse((HERE / name).read_text(encoding="utf-8"))
check("shipping + all P43 Python parses", True)
for name in ("p02_lighting_as_p01_request.json", "s2_lighting_seam_request.json"):
    request = json.loads((HERE / name).read_text(encoding="utf-8"))
    check("shipping + guarded runner " + name, request["arguments"]["arguments"]["relativeSavedPath"].startswith("CodexConductor/"))
check("shipping - AST catches syntax error", raises(lambda: ast.parse("def bad(:\n"), "invalid syntax"))

failed = [name for name, ok in RESULTS if not ok]
print("\nP43_LIGHTING_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
