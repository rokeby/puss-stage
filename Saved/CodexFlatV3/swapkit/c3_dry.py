"""Read-only per-row C3 plan: exact inner edge, preserved H and 2 cm gap gate."""
import copy
import importlib
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import c3_support as s
import common as c
c = importlib.reload(c)
import p05float_support as f
f = importlib.reload(f)
import verify as v
v = importlib.reload(v)


def library_entries(show):
    path = c.asset_path(show.get_editor_property("wing_library"))
    library = unreal.EditorAssetLibrary.load_asset(path) if path else None
    if library is None:
        raise RuntimeError("C3_WING_LIBRARY_LOAD_FAIL|path=" + str(path))
    result = {}
    for entry in library.get_editor_property("entries"):
        mesh = c.asset_path(entry.get_editor_property("mesh"))
        if mesh:
            result[mesh] = entry
    return result


def transform_point(parts, point):
    scaled = tuple(float(point[axis]) * parts["scale"][axis] for axis in range(3))
    rotated = v.quat_rotate(parts["rotation"], scaled)
    return tuple(parts["location"][axis] + rotated[axis] for axis in range(3))


def predicted_world_bounds(mesh, panel_record, pair_frame, library_by_mesh):
    prefix = v.resolved_panel_prefix(panel_record, library_by_mesh)
    full = v.compose_parts(prefix, v.transform_parts(pair_frame))
    box = mesh.get_bounding_box()
    points = [transform_point(full, point) for point in
              ((x, y, z) for x in (box.min.x, box.max.x)
               for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z))]
    return {"world_min": [min(point[axis] for point in points) for axis in range(3)],
            "world_max": [max(point[axis] for point in points) for axis in range(3)]}


def assert_live_matches_preflight(config, preflight, show):
    cues = list(show.get_editor_property("cues"))
    f.target_rows(config, show)
    for record in preflight["rows"]:
        actual = f.occurrence_row(record["cue_index"], cues[record["cue_index"]])
        if actual != record:
            raise RuntimeError("C3_PREFLIGHT_DRIFT|index=%d|guid=%s" %
                               (record["cue_index"], record["cue_guid"]))
    return cues


def run(config_path=None):
    config = s.load_config(config_path)
    s.assert_context(config, clean=True)
    preflight = s.read_json(config, "preflight")
    if (preflight.get("status") != "PASS" or preflight.get("row_count") != 93 or
            preflight.get("target_count") != 12):
        raise RuntimeError("C3_PREFLIGHT_NOT_PASS")
    show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")
    cues = assert_live_matches_preflight(config, preflight, show)
    actor = f.passage_actor(config, show)
    library_by_mesh = library_entries(show)
    mesh = unreal.EditorAssetLibrary.load_asset(config["new_left_mesh"])
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("C3_NEW_MESH_LOAD_FAIL|" + config["new_left_mesh"])
    donor = preflight["donor"]["left"]
    target_by_key = {s.target_key(row): row for row in preflight["targets"]}
    plan = []
    gap_rows = []
    narrower = []
    for target in config["targets"]:
        original = target_by_key[s.target_key(target)]
        cue = cues[target["cue_index"]]
        pair = cue.get_editor_property("wing_pair")
        refs = f.refs_for(actor, target["cue_guid"])
        frame, frame_source = v.pair_frame(
            actor, cue, refs, pair,
            {"cue_label": target["cue_label"], "changed_sides": ["left"]},
            library_by_mesh)
        old_left_pair = v.bounds_in_frame(
            refs["left"].get_editor_property("component").get_editor_property("static_mesh"),
            refs["left"].get_editor_property("base_world_transform"), frame)
        old_right_pair = v.bounds_in_frame(
            refs["right"].get_editor_property("component").get_editor_property("static_mesh"),
            refs["right"].get_editor_property("base_world_transform"), frame)
        old_inner = float(old_left_pair["max"][1])
        old_outer = float(old_left_pair["min"][1])
        old_right_inner = float(old_right_pair["min"][1])

        base = copy.deepcopy(donor)
        base["mesh"] = config["new_left_mesh"]
        base["local_transform"]["location"][1] = 0.0
        base["local_transform"]["location"][2] = 0.0
        zero_bounds = c.side_bounds(base, library_by_mesh)
        new_y = old_inner - float(zero_bounds["max_y_cm"])
        current_y = float(original["current_left"]["local_transform"]["location"][1])
        inner_move = new_y - current_y
        s.validate_offstage_move("left", inner_move)
        base["local_transform"]["location"][1] = new_y
        new_pair = c.side_bounds(base, library_by_mesh)
        new_inner = float(new_pair["max_y_cm"])
        new_outer = float(new_pair["min_y_cm"])
        if abs(new_inner - old_inner) > 0.01 or new_inner > old_inner + 0.000001:
            raise RuntimeError("C3_INNER_EDGE_PLAN_FAIL|index=%d|old=%.9f|new=%.9f" %
                               (target["cue_index"], old_inner, new_inner))
        is_narrower = new_outer > old_outer + 0.01
        if is_narrower:
            narrower.append({"cue_index": target["cue_index"],
                             "cue_guid": target["cue_guid"],
                             "cue_label": target["cue_label"],
                             "old_outer_edge_cm": old_outer,
                             "new_outer_edge_cm": new_outer,
                             "backbone_onstage_cm": new_outer - old_outer})

        current_world = f.world_bounds(refs["left"])
        height = s.target_height(config, target["cue_guid"], "left")
        current_bottom = float(current_world["world_min"][2])
        s.assert_bottom(current_bottom, height, config["bottom_tolerance_cm"],
                        target["cue_guid"])
        bottom_zero = predicted_world_bounds(mesh, base, frame, library_by_mesh)["world_min"][2]
        plus_one = copy.deepcopy(base)
        plus_one["local_transform"]["location"][2] = 1.0
        bottom_one = predicted_world_bounds(mesh, plus_one, frame, library_by_mesh)["world_min"][2]
        slope = float(bottom_one) - float(bottom_zero)
        if slope <= 0.000001:
            raise RuntimeError("C3_WORLD_Z_SLOPE_FAIL|index=%d|slope=%.9f" %
                               (target["cue_index"], slope))
        new_z = (current_bottom - float(bottom_zero)) / slope
        expected_left = s.expected_left_panel(
            original["current_left"], donor, config["new_left_mesh"], new_y, new_z)
        predicted = predicted_world_bounds(mesh, expected_left, frame, library_by_mesh)
        s.assert_bottom(predicted["world_min"][2], current_bottom, 0.01,
                        target["cue_guid"] + ":predicted")

        gap_old = s.centre_gap(old_inner, old_right_inner)
        gap_new = s.centre_gap(new_inner, old_right_inner)
        gap_row = {"cue_index": target["cue_index"], "cue_guid": target["cue_guid"],
                   "cue_label": target["cue_label"], "shifted_sides": ["left"],
                   "gap_old_cm": gap_old, "gap_new_cm": gap_new}
        gap_rows.append(gap_row)
        row = {
            "cue_index": target["cue_index"], "cue_guid": target["cue_guid"],
            "cue_label": target["cue_label"], "changed_sides": ["left"],
            "old_left": original["current_left"], "new_left": expected_left,
            "right_unchanged": original["current_right"],
            "top_unchanged": original["current_top"],
            "pair_frame_source": frame_source,
            "placement": {
                "old_y_cm": current_y, "new_y_cm": new_y,
                "inner_move_cm": inner_move, "old_inner_edge_cm": old_inner,
                "new_inner_edge_cm": new_inner, "old_outer_edge_cm": old_outer,
                "new_outer_edge_cm": new_outer, "narrower_than_old": is_narrower,
            },
            "height": {
                "hash_input": target["cue_guid"] + "left",
                "u": s.stable_unit(target["cue_guid"], "left"),
                "H_cm": height, "current_world_bottom_cm": current_bottom,
                "predicted_new_world_bottom_cm": predicted["world_min"][2],
                "new_local_z_cm": new_z, "predicted_world_min": predicted["world_min"],
                "predicted_world_max": predicted["world_max"],
            },
            "centre_gap": gap_row,
        }
        plan.append(row)
        unreal.log("FLATV3_C3_ROW run=%s index=%d guid=%s old_inner=%.6f new_inner=%.6f old_y=%.6f new_y=%.6f inner_move=%.6f H=%.6f old_bottom=%.6f new_bottom=%.6f gap_old=%.6f gap_new=%.6f narrower=%s" %
                   (config["run_id"], target["cue_index"], target["cue_guid"],
                    old_inner, new_inner, current_y, new_y, inner_move, height,
                    current_bottom, predicted["world_min"][2], gap_old, gap_new,
                    str(is_narrower).lower()))
    s.validate_target_rows(plan, config["targets"], config["target_count"])
    gap_gate = s.minimum_gap_gate(gap_rows, config["gap_tolerance_cm"])
    end = s.census()
    if end != s.CLEAN:
        raise RuntimeError("C3_DRY_DIRTIED_EDITOR|" + json.dumps(end, sort_keys=True))
    box = mesh.get_bounding_box()
    report = {
        "run": config["run_id"], "slot": "C3", "passage": "P05",
        "mode": "dry", "status": "PASS", "row_count": len(plan), "rows": plan,
        "formula": "H(guid,side) = 150 + 300*u; u = sha256(guid+side) first 8 bytes big-endian / 2**64",
        "lateral_rule": "new left inner edge equals current kept-old left inner edge; move from current Y must be offstage",
        "facing_donor": preflight["donor"], "narrower_cases": narrower,
        "centre_gap_gate": gap_gate, "materialize_calls": ["P05"],
        "mesh_gate": {"path": config["new_left_mesh"], "static_mesh": True,
                      "bounds_cm": {"min": [box.min.x, box.min.y, box.min.z],
                                    "max": [box.max.x, box.max.y, box.max.z]}},
        "dirty_after": end,
    }
    path = s.write_json(config, "dry_run", report)
    unreal.log("%s run=%s rows=12 side=left gap_min_old=%.6f gap_min_new=%.6f narrower=%d materialize=[P05] census=%s report=%s" %
               (s.marker("DRY_RUN_OK"), config["run_id"],
                gap_gate["min_gap_old_cm"], gap_gate["min_gap_new_cm"], len(narrower),
                json.dumps(end, separators=(",", ":"), sort_keys=True), path))
    return report


def main(config_path=None):
    config = None
    try:
        config = s.load_config(config_path)
        return run(config["_path"])
    except Exception as exc:
        if config is not None:
            s.write_json(config, "dry_run", {
                "run": config["run_id"], "mode": "dry", "status": "FAIL",
                "reason": str(exc), "traceback": traceback.format_exc(),
                "census": s.census()}, failure=True)
            s.log_release(config, "FAIL", [], "dry:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
