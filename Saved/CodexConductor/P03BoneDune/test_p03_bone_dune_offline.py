"""Offline harness with positive and negative controls for P17 P03 bone dune."""
from __future__ import annotations

import ast
import copy
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import p03_bone_dune_contract as C  # noqa: E402

RESULTS = []


def check(name, condition):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name)


def raises(function, token):
    try:
        function()
    except Exception as error:  # noqa: BLE001
        return token in str(error)
    return False


# Args: each gate has a positive or negative control.
A = C.check_args({})
check("args +: defaults are DRY and P03 Wing 013", A["mode"] == "DRY" and A["cue_label"] == "P03 Wing 013")
check("args +: default dune is 8 x 6 x 3.5 m", [A["dune"][k] for k in ("length_cm", "width_cm", "height_cm")]
      == [800.0, 600.0, 350.0])
check("args -: APPLY needs exact confirm", raises(lambda: C.check_args({"mode": "APPLY"}), "CONFIRM_MISSING"))
check("args +: APPLY exact confirm", C.check_args({"mode": "APPLY", "confirm": "APPLY P03 BONE DUNE"})["mode"] == "APPLY")
check("args -: REVERT wrong confirm", raises(lambda: C.check_args({"mode": "REVERT", "confirm": "yes"}), "CONFIRM_MISSING"))
check("args +: REVERT exact confirm", C.check_args({"mode": "REVERT", "confirm": "REVERT P03 BONE DUNE"})["mode"] == "REVERT")
check("args -: unknown top-level key", raises(lambda: C.check_args({"bay": 13}), "UNKNOWN_ARGS"))
check("args -: unknown dune key", raises(lambda: C.check_args({"dune": {"pretty": True}}), "UNKNOWN_DUNE_ARGS"))
check("args -: wrong stable cue identity", raises(lambda: C.check_args({"cue_guid": "0" * 32}), "CUE_GUID"))
check("args -: implausibly low dune", raises(lambda: C.check_args({"dune": {"height_cm": 100}}), "DUNE_HEIGHT_RANGE"))
check("args +: editable 4.2m dune", C.check_args({"dune": {"height_cm": 420}})["dune"]["height_cm"] == 420)
check("args -: route clearance below 1m", raises(
    lambda: C.check_args({"dune": {"station_offset_cm": [0, 350, 0], "width_cm": 600}}), "CAT_ROUTE_CLEARANCE"))
check("args +: default route clearance is 2m", C.placement_plan(A)["route_clearance_cm"] == 200.0)
check("args +: all creative bone placements are exposed", A["bone_layout"] == C.DEFAULT_BONE_LAYOUT)
bad_layout = copy.deepcopy(A); bad_layout["bone_layout"] = bad_layout["bone_layout"][:-1]
check("args -: incomplete creative bone layout", raises(lambda: C.check_args(bad_layout), "BONE_LAYOUT_COUNT"))

# Rodin contract.
check("bones +: six distinct requested kinds", len(C.BONE_SPECS) == 6 and len({s["name"] for s in C.BONE_SPECS}) == 6)
check("bones +: named coverage", {s["name"] for s in C.BONE_SPECS} == {
    "HominidCranium", "HominidPelvis", "HominidScapula", "HominidVertebraChain", "HominidFemurLong", "HominidHandBones"})
check("bones +: every prompt asks restrained sand-aged dry bone", all(
    "sand staining" in s["prompt"] and "calm matte" in s["prompt"] for s in C.BONE_SPECS))
check("bones +: every bbox is a believable nonzero integer triple", all(
    len(s["bbox_cm"]) == 3 and all(isinstance(v, int) and 4 <= v <= 50 for v in s["bbox_cm"]) for s in C.BONE_SPECS))
bad_specs = copy.deepcopy(C.BONE_SPECS)
bad_specs[0]["bbox_cm"] = [0, 20, 28]
check("bones -control: a zero bbox would fail the bbox predicate", not all(
    all(isinstance(v, int) and 4 <= v <= 50 for v in s["bbox_cm"]) for s in bad_specs))
check("bones +: unique deterministic seeds", len({s["seed"] for s in C.BONE_SPECS}) == 6)

# Dune field: shape, determinism, ripples and steep lee face.
h1 = C.dune_height_cm(-25, 0, A["dune"], A["seed"])
h2 = C.dune_height_cm(-25, 0, A["dune"], A["seed"])
check("field +: deterministic", h1 == h2)
check("field +: centre/crest is tall", h1 > 300.0)
check("field +: footprint edges close to zero", C.dune_height_cm(-400, 0, A["dune"], A["seed"]) < 1e-6
      and C.dune_height_cm(400, 0, A["dune"], A["seed"]) < 1e-6)
wind_slope = abs(C.dune_height_cm(-180, 0, A["dune"], A["seed"]) - C.dune_height_cm(-200, 0, A["dune"], A["seed"])) / 20
lee_slope = abs(C.dune_height_cm(80, 0, A["dune"], A["seed"]) - C.dune_height_cm(100, 0, A["dune"], A["seed"])) / 20
check("field +: lee face is steeper than windward ramp", lee_slope > wind_slope * 1.2)
flat = copy.deepcopy(A["dune"]); flat["ripple_height_cm"] = 0
check("field +: ripples materially change windward relief", abs(
    C.dune_height_cm(-210, 70, A["dune"], A["seed"]) - C.dune_height_cm(-210, 70, flat, A["seed"])) > 0.25)
check("field -control: zero-height profile is refused by args", raises(
    lambda: C.check_args({"dune": {"height_cm": 0}}), "DUNE_HEIGHT_RANGE"))

# Placement.
P = C.placement_plan(A)
check("plan +: one dune and six bone props", len(P["all"]) == 7 and len(P["bones"]) == 6)
check("plan +: target identity is the measured P03 B13 guid", P["target"]["guid"] == "622946E51046353D4D27EF8B20389CE3")
check("plan +: all are Station PROP attachments", all(r["kind"] == "PROP" and r["anchor"] == "STATION" for r in P["all"]))
check("plan +: labels are uniquely owned", len({r["label"] for r in P["all"]}) == 7 and all(
    r["label"].startswith("P03 BONE DUNE") for r in P["all"]))
check("plan +: every bone has a generated asset path", all("/P03Bones/" in r["mesh"] for r in P["bones"]))
placements = C.bone_placements(A)
check("plan +: every bone is buried below sampled surface", all(
    row["dune_local_transform"]["location_cm"][2] < row["sampled_surface_cm"] for row in placements))
check("plan +: every bone stays visibly above the dune base", all(
    row["dune_local_transform"]["location_cm"][2] > 20.0 for row in placements))
check("plan +: burial depths are bounded", all(5 <= row["burial_depth_cm"] <= 12 for row in placements))
check("plan +: bone xy positions remain inside footprint", all(
    abs(row["dune_local_transform"]["location_cm"][0]) < 400 and abs(row["dune_local_transform"]["location_cm"][1]) < 300
    for row in placements))
check("plan -control: moved location is detected", bool(C.drift_paths(
    P["all"], [dict(r, transform=dict(r["transform"], location_cm=[999, 0, 0])) if i == 0 else r
               for i, r in enumerate(P["all"])])))
check("plan +: float readback within 1e-4 is accepted", not C.drift_paths(1.0, 1.00005))
check("plan -: float readback outside 1e-4 is detected", C.drift_paths(1.0, 1.0002) == ["$type"] or bool(C.drift_paths(1.0, 1.0002)))

# Request and source guards.
request = json.loads((HERE / "p03_bone_dune_request.json").read_text(encoding="utf-8"))
check("request +: ships DRY", request["mode"] == "DRY")
ue_src = (HERE / "p03_bone_dune_ue.py").read_text(encoding="utf-8")
ue_tree = ast.parse(ue_src)
ue_calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            for n in ast.walk(ue_tree) if isinstance(n, ast.Call)}
check("UE guard +: no Save All or dirty-package save", not ({"save_all", "save_dirty_packages", "save_packages"} & ue_calls))
check("UE guard +: no asset delete, level load or PIE controls", not (
    {"delete_asset", "load_level", "load_map", "request_begin_play", "request_end_play"} & ue_calls))
check("UE guard +: narrow Show+level save used", "save_show_and_level" in ue_calls)
body = ue_src[ue_src.index('if args["mode"] == "APPLY":'):]
order = [body.index(token) for token in (
    'H.backup_packages(unreal, "PreP03BoneDune-"', 'H.write_json(RECORD, record, exclusive=True)',
    "mint_props(show, index, plan", "actor.materialize_passage()", '"APPLY_DIRTY_SCOPE', "H.save_show_and_level(unreal)",
    "actual = owned(unreal.load_asset")]
check("UE guard +: backup -> record -> change -> materialize -> census -> save -> readback", order == sorted(order))
check("UE guard +: explicit success markers carry run ids", all(token in ue_src for token in (
    "P03_BONE_DUNE_DRY_OK|run=", "P03_BONE_DUNE_APPLY_OK|run=", "P03_BONE_DUNE_REVERT_OK|run=")))
check("UE guard -control: script never claims it ran", "has not been run in Unreal" in ue_src)

bl_src = (HERE / "p03_assets_blender.py").read_text(encoding="utf-8")
check("Blender guard +: key source is add-on preferences", 'preferences.addons.get("blender_mcp_addon")' in bl_src)
check("Blender guard +: credential is never put in os.environ", "os.environ" not in bl_src)
check("Blender guard +: transient add-on enable never saves preferences", "addon_enable" in bl_src
      and "save_userpref" not in bl_src)
sanitize_body = bl_src[bl_src.index("def sanitize_generation"):bl_src.index("def download_url")]
check("Blender guard +: response sanitiser drops subscription key", '"subscription_key_serialized": False' in sanitize_body
      and '"subscription_key"' not in sanitize_body)
check("Blender guard +: Rodin submission is one explicit call", bl_src.count('api_json(key, "/rodin"') == 1)
apply_body = bl_src[bl_src.index("def apply(run):"):bl_src.index("def revert(run):")]
check("Blender guard +: APPLY backup and record precede get_key", apply_body.index('backup_outputs(run, "APPLY")') <
      apply_body.index('write_json(RECORD, record)') < apply_body.index("key = get_key()"))
check("Blender guard +: decimation hard gate <=150k", "MAX_TRIS = 150000" in bl_src and "DECIMATE_LIMIT" in bl_src)
check("Blender guard +: clean FBX reimport gate exists", "validate_fbx_clean" in bl_src and "FBX_REIMPORT_TRIS" in bl_src)
check("Blender guard +: bone and dune manifests both carry clean reimport", bl_src.count(
    '"validation_blender_clean_reimport": clean') == 2)
check("Blender guard +: REVERT preserves current outputs in a backup", 'backup_outputs(run, "REVERT")' in bl_src
      and "shutil.move(target, moved)" in bl_src)
check("Blender guard +: APPLY refuses an unresolved earlier record", "RECORD_EXISTS|status=" in bl_src)
check("Blender guard +: failed partial APPLY is recorded and reversible", '"status": "failed"' in bl_src
      and '("prepared", "failed", "applied")' in bl_src)

failed = [name for name, ok in RESULTS if not ok]
print("\n%d/%d passed" % (len(RESULTS) - len(failed), len(RESULTS)))
if failed:
    print("FAILED:", json.dumps(failed, indent=1))
sys.exit(1 if failed else 0)
