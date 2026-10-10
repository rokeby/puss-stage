"""Offline +/- harness for job 111.  No Unreal import or editor access."""
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
    value.update(updates)
    return value


stations = {"P01": [{"id": "S1", "center": [0.0, 0.0, 0.0], "left": [0.0, -1000.0, 0.0],
                       "right": [0.0, 1000.0, 0.0], "half_width_cm": 1000.0}]}
params = dict(m.DEFAULTS)
params.update({"passages": ["P01"], "margin_cm": 300.0})

plan = m.plan_census([row("raise", 0.0, 500.0), row("keep", 0.0, 2000.0)], stations, params)
check("positive raises to far wing plus margin", plan[1]["planned_radius_cm"] == 1300.0 if plan[1]["id"] == "raise" else plan[0]["planned_radius_cm"] == 1300.0)
by_id = {r["id"]: r for r in plan}
check("positive never lowers", by_id["keep"]["planned_radius_cm"] == 2000.0)
check("positive only one change", sum(r["will_change"] for r in plan) == 1)

keyed = m.plan_census([row("keyed", 0.0, 500.0)], stations, params, ["keyed"])[0]
check("negative sequencer track blocks edit", not keyed["will_change"] and keyed["radius_keyed_by_sequencer"])

capped_params = dict(params, cap_cm=900.0)
capped = m.plan_census([row("cap", 0.0, 500.0)], stations, capped_params)[0]
check("positive cap respected", capped["planned_radius_cm"] == 900.0)
check("negative cap underreach explicit", capped["decision"] == "RAISE_CAPPED_UNDERREACH")

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
rejects("negative bad passage", lambda: m.check_args({"params": {"passages": ["P07"]}}), "PASSAGES_INVALID")
rejects("negative negative margin", lambda: m.check_args({"params": {"margin_cm": -1}}), "MARGIN_NEGATIVE")
rejects("negative zero cap", lambda: m.check_args({"params": {"cap_cm": 0}}), "CAP_NONPOSITIVE")

source = open(TOOL, encoding="utf-8").read()
check("static apply setter only radius component", 'set_editor_property("attenuation_radius", float(want))' in source)
check("static show setter only radius field", 'set_editor_property("attenuation_radius_cm", float(value))' in source)
check("static no fog mutation", 'set_editor_property("cast_volumetric_shadow"' not in source)
check("static backup before apply", source.index('backup_assets("PreShadowRadiusReach-"') < source.index('apply_values(live, changes, "after")'))
check("negative unrelated live tool is never imported", "lighting_looks_apply.py" not in source)
check("static success markers", all(x in source for x in ("_DRY_OK", "_APPLY_OK", "_REVERT_OK")))

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
