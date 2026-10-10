"""Offline +/- harness for Jobs 111/159/163/179. No Unreal/editor access."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "shadow_radius_reach.py")
spec = importlib.util.spec_from_file_location("shadow_radius_reach", TOOL)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


def rejects(name, fn, needle):
    try:
        fn()
    except Exception as error:
        check(name, needle in str(error))
    else:
        check(name, False)


def row(identity, x, radius, **updates):
    value = {"id": identity, "passage": "P01", "label": identity, "class": "SpotLightComponent",
             "source": "LEVEL_ACTOR", "location": [x, 0.0, 0.0], "intensity": 1000.0,
             "attenuation_radius_cm": radius, "volumetric_scattering_intensity": 1.0,
             "cast_shadows": True, "cast_volumetric_shadow": True,
             "use_inverse_squared_falloff": True, "source_radius_cm": 0.0, "light_function": None}
    value.update({"level_package": m.EXPECTED_WORLD, "passage_owned": True,
                  "source": "SHOW_ATTACHMENT"})
    value.update(updates)
    return value


stations = {"P01": [
    {"id": "S1", "ordinal": 1, "center": [0.0, 0.0, 0.0], "left": [0.0, -1000.0, 0.0],
     "right": [0.0, 1000.0, 0.0], "half_width_cm": 1000.0},
    {"id": "S2", "ordinal": 2, "center": [800.0, 0.0, 0.0], "left": [800.0, -1000.0, 0.0],
     "right": [800.0, 1000.0, 0.0], "half_width_cm": 1000.0},
    {"id": "S3", "ordinal": 3, "center": [1600.0, 0.0, 0.0], "left": [1600.0, -1000.0, 0.0],
     "right": [1600.0, 1000.0, 0.0], "half_width_cm": 1000.0}]}
params = dict(m.DEFAULTS)
params.update({"passages": ["P01"]})

geometry = m.passage_geometry(stations, params)["P01"]
check("positive pitch measured", geometry["wing_pitch_cm"] == 800.0)
check("positive across gap measured", geometry["across_gap_cm"] == 2000.0)
check("positive larger reach plus margin chosen", geometry["chosen_radius_cm"] == 2100.0)
plan = m.plan_census([row("raise", 0.0, 500.0), row("keep", 0.0, 2500.0)], stations, params)
check("positive raises to per-passage middle point", plan[1]["planned_radius_cm"] == 2100.0 if plan[1]["id"] == "raise" else plan[0]["planned_radius_cm"] == 2100.0)
by_id = {r["id"]: r for r in plan}
check("positive never lowers", by_id["keep"]["planned_radius_cm"] == 2500.0)
check("positive only one change", sum(r["will_change"] for r in plan) == 1)

keyed = m.plan_census([row("keyed", 0.0, 500.0)], stations, params, ["keyed"])[0]
check("negative sequencer track blocks edit", not keyed["will_change"] and keyed["radius_keyed_by_sequencer"])

capped_params = dict(params, cap_cm=900.0)
capped = m.plan_census([row("cap", 0.0, 500.0)], stations, capped_params)[0]
check("positive cap respected", capped["planned_radius_cm"] == 900.0)
check("positive clamped geometry reported", m.passage_geometry(stations, capped_params)["P01"]["clamped"])

fog = m.plan_census([row("fog", 0.0, 2000.0, cast_volumetric_shadow=False)], stations, params)[0]
check("positive fog flag separate", fog["likely_milky_fog_contributor"])
check("positive no volumetric shadow reason", "SCATTERS_WITHOUT_VOLUMETRIC_SHADOW" in fog["milky_fog_reasons"])
large = m.plan_census([row("large", 0.0, 2000.0, source_radius_cm=20.0)], stations, params)[0]
check("positive large source reason", "LARGE_SOURCE_RADIUS" in large["milky_fog_reasons"])
dark = m.plan_census([row("dark", 0.0, 2000.0, volumetric_scattering_intensity=0.0,
                               cast_volumetric_shadow=False, source_radius_cm=100.0)], stations, params)[0]
check("negative zero scatter not fog suspect", not dark["likely_milky_fog_contributor"])

overlap = m.overlap_prediction(plan, stations)[0]
check("positive overlap predicted", overlap["shadow_lights_after"] >= overlap["shadow_lights_before"])
report = m.tiered_report(plan + [fog], stations, [])
check("positive tiered counts", report["tier_0_verdict"]["likely_milky_fog_contributors"] == 1)
check("positive per-light fog column", "likely_milky_fog_contributor" in report["tier_2_per_light"][0])

check("positive dry accepts no confirm", m.check_args({"mode": "DRY"})["mode"] == "DRY")
rejects("negative apply needs confirm", lambda: m.check_args({"mode": "APPLY", "expected_changes": 1}), "CONFIRM_MISSING")
rejects("negative apply needs expected count", lambda: m.check_args({"mode": "APPLY", "confirm": m.CONFIRM["APPLY"]}), "EXPECTED_CHANGES_REQUIRED")
rejects("negative apply needs plan hash", lambda: m.check_args({"mode": "APPLY", "confirm": m.CONFIRM["APPLY"],
                                                                 "expected_changes": 1}), "EXPECTED_PLAN_SHA256")
rejects("negative bad passage", lambda: m.check_args({"params": {"passages": ["P07"]}}), "PASSAGES_INVALID")
rejects("negative negative margin", lambda: m.check_args({"params": {"margin_cm": -1}}), "MARGIN_NEGATIVE")
rejects("negative zero cap", lambda: m.check_args({"params": {"cap_cm": 0}}), "CAP_MUST_BE_BELOW_100M")
rejects("negative 100m cap", lambda: m.check_args({"params": {"cap_cm": 10000}}), "CAP_MUST_BE_BELOW_100M")

inventory = [
    {"level_package": m.EXPECTED_WORLD, "passage_owned": True, "included": True},
    {"level_package": m.EXPECTED_WORLD, "passage_owned": False, "included": False},
    {"level_package": "/Game/Klara/L_Animals", "passage_owned": False, "included": False},
]
scoped_plan = m.plan_census([row("owned", 0.0, 500.0)], stations, params)
m.assert_planned_scope(scoped_plan)
counts = m.level_scope_counts(inventory, scoped_plan)
check("positive persistent Passage-owned change accepted",
      counts[m.EXPECTED_WORLD]["planned_changes"] == 1)
check("positive DRY counts every scanned level",
      set(counts) == {m.EXPECTED_WORLD, "/Game/Klara/L_Animals"})
check("positive unowned persistent light excluded",
      counts[m.EXPECTED_WORLD]["excluded_unowned"] == 1)
streamed = m.plan_census([row("klara", 0.0, 500.0,
                              level_package="/Game/Klara/L_Animals")], stations, params)
rejects("negative streamed-level light refused",
        lambda: m.assert_planned_scope(streamed),
        "PLANNED_CHANGE_OUTSIDE_PERSISTENT_PASSAGE_SCOPE")
unowned = m.plan_census([row("foreign", 0.0, 500.0,
                             passage_owned=False, source="LEVEL_ACTOR")], stations, params)
rejects("negative unowned persistent light refused",
        lambda: m.assert_planned_scope(unowned),
        "PLANNED_CHANGE_OUTSIDE_PERSISTENT_PASSAGE_SCOPE")

source = open(TOOL, encoding="utf-8").read()
apply_source = source[source.index("def apply_values("):source.index("def save_narrow(")]
check("positive persistent component mirror uses supported setter",
      'setter = getattr(component, "set_attenuation_radius", None)' in apply_source and
      "setter(float(want))" in apply_source)
check("static show setter only radius field", 'set_editor_property("attenuation_radius_cm", float(value))' in source)
check("negative persistent-only apply never rematerializes whole passages",
      "materialize_passage" not in apply_source)
check("positive Show authority is written before component mirror",
      apply_source.index("set_show_radius(show, target, want, expected, strict)") <
      apply_source.index("setter(float(want))"))
check("static no fog mutation", 'set_editor_property("cast_volumetric_shadow"' not in source)
check("static backup before apply", source.index('backup_assets("PreShadowRadiusReach-"') < source.index('apply_values(live, changes, "after")'))
check("negative unrelated live tool is never imported", "lighting_looks_apply.py" not in source)
check("static success markers", all(x in source for x in ("_DRY_OK", "_APPLY_OK", "_REVERT_OK")))
check("static proximity membership removed", 'source, "LEVEL_ACTOR"' not in source and
      'nearest_distance > args["params"]["membership_radius_cm"]' not in source)

before = {"P01:a": 40.0, "P01:b": 41.0, "P01:c": 42.0}
gate_ok = m.evaluate_perf(before, {"P01:a": 42.0, "P01:b": 43.0, "P01:c": 44.0}, ["P01"])
check("positive three-spot perf pass", gate_ok["pass"] and not gate_ok["auto_revert"])
gate_bad = m.evaluate_perf(before, {"P01:a": 45.0, "P01:b": 43.0, "P01:c": 44.0}, ["P01"])
check("negative over-ten-percent auto reverts", not gate_bad["pass"] and gate_bad["auto_revert"])
rejects("negative perf needs three spots", lambda: m.evaluate_perf({"P01:a": 1}, {"P01:a": 1}, ["P01"]),
        "PERF_NEEDS_THREE_SPOTS")

with tempfile.TemporaryDirectory() as temp:
    content = os.path.join(temp, "Content")
    packages = ("/Game/Test/Show", "/Game/Test/Map")
    paths = (os.path.join(content, "Test", "Show.uasset"),
             os.path.join(content, "Test", "Map.umap"))
    for index, path in enumerate(paths):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(("package-%d" % index).encode("ascii"))
    copied = m.backup_assets("PreHarness-", "ONE", temp, content, packages)
    check("positive pure backup copies both packages", len(copied["packages"]) == 2 and
          all(os.path.isfile(row["backup"]) for row in copied["packages"]))
    check("positive pure backup hashes match", all(len(row["sha256"]) == 64 for row in copied["packages"]))
    rejects("negative duplicate backup refused", lambda: m.backup_assets(
        "PreHarness-", "ONE", temp, content, packages), "WinError 183")

print("SHADOW_RADIUS_REACH_HARNESS|passed=%d|failed=%d" % (passed, failed))
raise SystemExit(1 if failed else 0)
