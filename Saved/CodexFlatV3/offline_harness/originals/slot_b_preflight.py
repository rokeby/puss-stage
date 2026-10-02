"""Read-only Slot B preflight, independent outer-edge placement plan and gates."""
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import traceback
import unreal

BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3"))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
import slot_b_common as c
c = importlib.reload(c)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = {"run": c.RUN, "mode": "preflight"}
try:
    if c.log_has("FLATV3_SLOT_RELEASED run=" + c.RUN):
        raise RuntimeError("RUN_ALREADY_RELEASED")
    editor, world = c.assert_context(clean=True)
    if not c.log_has("FLATV3_A_OK"):
        raise RuntimeError("FLATV3_A_OK_NOT_FOUND")

    project = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    slot_a = load_module("flatv3_slot_a_reuse_b", os.path.join(BASE, "slot_a_import.py"))
    tools_dir = os.path.join(project, "Tools", "FlatV3")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import socket_contract

    source_rows, _ = slot_a.built_source_inventory()
    p04_rows = {row["owner"]: row for row in source_rows if row["passage"] == "P04"}
    contract_rows = {row["asset"]: row for row in socket_contract.discover_slot_a_rows(Path(project))
                     if row["passage"] == "P04"}
    expected_owners = [path.rsplit("SM_FlatV3_", 1)[1] for path in c.LEFT_POOL + c.RIGHT_POOL]
    if sorted(p04_rows) != sorted(expected_owners) or sorted(contract_rows) != sorted(expected_owners):
        raise RuntimeError("P04_POOL_CONTRACT_FAIL|source=%s|contract=%s|expected=%s" %
                           (sorted(p04_rows), sorted(contract_rows), sorted(expected_owners)))

    mesh_gates = {}
    for owner in expected_owners:
        row = p04_rows[owner]
        contract = contract_rows[owner]
        payload = socket_contract.load_json(contract["sidecar_path"])
        failures = socket_contract.validate_socket_payload(payload, contract["expected"])
        if failures:
            raise RuntimeError("SOCKET_CONTRACT_FAIL|owner=%s|failures=%s" %
                               (owner, json.dumps(failures)))
        by_name = {entry["name"]: entry for entry in contract["expected"]["sockets"]}
        mesh = unreal.EditorAssetLibrary.load_asset(row["destinations"]["mesh"])
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("P04_MESH_MISSING|" + row["destinations"]["mesh"])
        mesh_gates[owner] = slot_a.verify_geometry(mesh, row, by_name)

    show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")

    library_ref = show.get_editor_property("wing_library")
    library_path = c.asset_path(library_ref)
    library = unreal.EditorAssetLibrary.load_asset(library_path) if library_path else None
    if library is None:
        raise RuntimeError("WING_LIBRARY_LOAD_FAIL|path=" + str(library_path))
    library_by_mesh = {}
    for entry in library.get_editor_property("entries"):
        entry_mesh = c.asset_path(entry.get_editor_property("mesh"))
        if entry_mesh:
            library_by_mesh[entry_mesh] = entry

    def box_points(mesh):
        box = mesh.get_bounding_box()
        return [unreal.Vector(x, y, z) for x in (box.min.x, box.max.x)
                for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]

    def resolved_points(panel_record):
        mesh = unreal.EditorAssetLibrary.load_asset(panel_record["mesh"])
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("OLD_MESH_LOAD_FAIL|path=" + str(panel_record["mesh"]))
        points = box_points(mesh)
        if panel_record["flip_image_horizontally"]:
            points = [unreal.Vector(point.x, -point.y, point.z) for point in points]
        entry = library_by_mesh.get(panel_record["mesh"])
        rotate = "ROTATE180_AROUND_UP" in panel_record["facing_policy"]
        placement_applied = False
        front_axis = None
        if entry is not None:
            front_axis = str(entry.get_editor_property("front_axis"))
            if "AUTO_BY_ROLE" in panel_record["facing_policy"]:
                rotate = "NEGATIVE_X" in front_axis.upper()
            placement = entry.get_editor_property("placement_adjustment")
            placement_scale = placement.scale3d
            mirrored = float(placement_scale.x * placement_scale.y * placement_scale.z) < 0.0
            approved = bool(entry.get_editor_property("photographic_mirror_approved"))
            if not mirrored or approved:
                points = [placement.transform_location(point) for point in points]
                placement_applied = True
        if rotate:
            rotation = unreal.Transform(
                rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
            points = [rotation.transform_location(point) for point in points]
        local = c.transform_from_plain(panel_record["local_transform"])
        points = [local.transform_location(point) for point in points]
        return points, {"front_axis": front_axis, "rotate_180": rotate,
                        "placement_adjustment_applied": placement_applied}

    def side_bounds(panel_record):
        points, facing = resolved_points(panel_record)
        ys = [float(point.y) for point in points]
        return {"min_y_cm": min(ys), "max_y_cm": max(ys), "facing": facing}

    def planned_panel(mesh_path, y):
        return {"mesh": mesh_path, "material_overrides": [],
                "local_transform": {"location": [0.0, float(y), 0.0],
                                    "rotation": [0.0, 0.0, 0.0],
                                    "scale": [1.0, 1.0, 1.0]},
                "facing_policy": "PRESERVE_ASSET", "flip_image_horizontally": False}
    cues = list(show.get_editor_property("cues"))
    targets = [(index, cue) for index, cue in enumerate(cues)
               if str(cue.get_editor_property("label")).startswith("P04 Wing ")]
    if not targets:
        raise RuntimeError("NO_P04_WING_OCCURRENCES")
    if not any(str(cue.get_editor_property("label")) == "P04 Wing 011" for _, cue in targets):
        raise RuntimeError("P04_WING_011_MISSING")

    originals = []
    plan = []
    overreach_flags = []
    for ordinal, (index, cue) in enumerate(targets):
        label = str(cue.get_editor_property("label"))
        pair = cue.get_editor_property("wing_pair")
        left = c.panel_plain(pair.get_editor_property("left"))
        right = c.panel_plain(pair.get_editor_property("right"))
        left_y = float(left["local_transform"]["location"][1])
        right_y = float(right["local_transform"]["location"][1])
        old_left_bounds = side_bounds(left)
        old_right_bounds = side_bounds(right)
        left_outer = old_left_bounds["min_y_cm"]
        right_outer = old_right_bounds["max_y_cm"]
        left_mesh = c.LEFT_POOL[ordinal % len(c.LEFT_POOL)]
        right_mesh = c.RIGHT_POOL[ordinal % len(c.RIGHT_POOL)]
        planned_left = planned_panel(left_mesh, left_outer)
        planned_right = planned_panel(right_mesh, right_outer)
        new_left_bounds = side_bounds(planned_left)
        new_right_bounds = side_bounds(planned_right)
        left_inner = new_left_bounds["max_y_cm"]
        right_inner = new_right_bounds["min_y_cm"]
        left_old_inner = old_left_bounds["max_y_cm"]
        right_old_inner = old_right_bounds["min_y_cm"]
        left_overreach = max(0.0, left_inner) > max(0.0, left_old_inner) + 0.01
        right_overreach = max(0.0, -right_inner) > max(0.0, -right_old_inner) + 0.01
        for side, old_y, outer, new_y, inner, old_inner, flagged in (
                ("left", left_y, left_outer, left_outer, left_inner, left_old_inner, left_overreach),
                ("right", right_y, right_outer, right_outer, right_inner, right_old_inner, right_overreach)):
            unreal.log("FLATV3_B_LATERAL_DRY_RUN run=%s label=%s side=%s old_y=%.6f old_outer_edge=%.6f new_y=%.6f new_inner_edge=%.6f old_inner_edge=%.6f overreach_flag=%s" %
                       (c.RUN, label, side, old_y, outer, new_y, inner, old_inner,
                        str(flagged).lower()))
            if flagged:
                overreach_flags.append({"cue_label": label, "side": side,
                                        "old_inner_edge_cm": old_inner,
                                        "new_inner_edge_cm": inner})
        record = {
            "cue_index": index, "cue_label": label,
            "cue_guid": cue.get_editor_property("cue_guid").to_string(),
            "left": left, "right": right,
            "top": c.panel_plain(pair.get_editor_property("top")),
            "occurrence_offset": c.transform_plain(pair.get_editor_property("occurrence_offset")),
            "mechanism": c.mechanism_plain(pair.get_editor_property("mechanism")),
            "old_bounds": {"left": old_left_bounds, "right": old_right_bounds},
        }
        originals.append(record)
        plan.append({
            "cue_index": index, "cue_label": label, "cue_guid": record["cue_guid"],
            "left": planned_left, "right": planned_right,
            "placement": {
                "left": {"old_y_cm": left_y, "old_outer_edge_cm": left_outer,
                         "new_y_cm": left_outer, "old_inner_edge_cm": left_old_inner,
                         "new_inner_edge_cm": left_inner, "overreach_flag": left_overreach},
                "right": {"old_y_cm": right_y, "old_outer_edge_cm": right_outer,
                          "new_y_cm": right_outer, "old_inner_edge_cm": right_old_inner,
                          "new_inner_edge_cm": right_inner, "overreach_flag": right_overreach},
            },
            "top_unchanged": record["top"],
            "occurrence_offset_unchanged": record["occurrence_offset"],
            "mechanism_unchanged": record["mechanism"],
        })
    for side in ("left", "right"):
        sequence = [entry[side]["mesh"] for entry in plan]
        if any(a == b for a, b in zip(sequence, sequence[1:])):
            raise RuntimeError("POOL_CONSECUTIVE_REPEAT|side=" + side)

    originals_doc = {"run": c.RUN, "backup_path": c.BACKUP,
                     "world": c.WORLD, "show": c.SHOW, "rows": originals}
    dry_doc = {"run": c.RUN, "rotation_policy": "cue order modulo four per side",
               "lateral_derivation": "each side independently: new backbone Y equals the old transformed outer-edge Y; old mesh bounds, local scale/rotation/translation, image flip, facing rotation and allowed library placement adjustment are applied",
               "overreach_flags": overreach_flags,
               "materialize_calls": ["P04"], "rows": plan}
    originals_path = c.write_json("slot_b_originals_%s.json" % c.RUN, originals_doc)
    dry_path = c.write_json("slot_b_dry_run_%s.json" % c.RUN, dry_doc)
    report.update({"status": "PASS", "world": c.WORLD, "dirty": c.census(),
                   "p04_count": len(plan), "mesh_gates": mesh_gates,
                   "overreach_flags": overreach_flags,
                   "originals": originals_path, "dry_run": dry_path,
                   "pool_left": c.LEFT_POOL, "pool_right": c.RIGHT_POOL})
    report_path = c.write_json("slot_b_preflight_%s.json" % c.RUN, report)
    if c.census() != {"content": [], "maps": []}:
        raise RuntimeError("PREFLIGHT_DIRTIED_EDITOR|census=" + json.dumps(c.census(), sort_keys=True))
    unreal.log("FLATV3_B_DRY_RUN run=%s rows=%d materialize=[P04] overreach_flags=%d plan=%s" %
               (c.RUN, len(plan), len(overreach_flags), dry_path))
    unreal.log("FLATV3_B_PREFLIGHT_OK run=%s rows=%d pool_meshes=8 census=%s report=%s" %
               (c.RUN, len(plan), json.dumps(c.census(), separators=(",", ":"), sort_keys=True), report_path))
except Exception as exc:
    report.update({"status": "FAIL", "reason": str(exc), "traceback": traceback.format_exc(),
                   "census": c.census()})
    c.write_json("slot_b_preflight_%s_FAILURE.json" % c.RUN, report)
    c.log_release("FAIL", [], "preflight:" + str(exc))

