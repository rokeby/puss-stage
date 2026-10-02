"""Read-only deterministic plan using the configured mapping and Slot B lateral rule."""
import importlib
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as c
c = importlib.reload(c)


def run(config_path=None):
    config = c.load_config(config_path)
    c.assert_context(config, clean=True)
    preflight = c.read_json(config, "preflight")
    if preflight.get("status") != "PASS":
        raise RuntimeError("PREFLIGHT_NOT_PASS")
    mapping = c.load_mapping(config)
    show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    cues = list(show.get_editor_property("cues"))
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

    plan = []
    overreach_flags = []
    excluded_hits = []
    planned_meshes = set()
    for ordinal, original in enumerate(preflight["rows"]):
        cue = cues[original["cue_index"]]
        _, label = c.assert_occurrence(
            cue, original["cue_index"], original, config["passage_label_prefix"])
        pair = cue.get_editor_property("wing_pair")
        for side in ("left", "right", "top"):
            if c.panel_plain(pair.get_editor_property(side)) != original[side]:
                raise RuntimeError("PREFLIGHT_DRIFT|label=%s|side=%s" % (label, side))
        desired, requested, row_excluded = c.desired_meshes(
            config, mapping, label, ordinal, original)
        excluded_hits.extend(row_excluded)
        row = {"cue_index": original["cue_index"], "cue_label": label,
               "cue_guid": original["cue_guid"], "changed_sides": [],
               "placement": {}, "top_unchanged": original["top"],
               "occurrence_offset_unchanged": original["occurrence_offset"],
               "mechanism_unchanged": original["mechanism"]}
        for side in ("left", "right"):
            if side not in requested:
                row[side] = original[side]
                continue
            old_bounds = c.side_bounds(original[side], library_by_mesh)
            outer = old_bounds["min_y_cm"] if side == "left" else old_bounds["max_y_cm"]
            planned = c.planned_panel(desired[side], outer)
            new_bounds = c.side_bounds(planned, library_by_mesh)
            old_inner = old_bounds["max_y_cm"] if side == "left" else old_bounds["min_y_cm"]
            new_inner = new_bounds["max_y_cm"] if side == "left" else new_bounds["min_y_cm"]
            flagged = (max(0.0, new_inner) > max(0.0, old_inner) + 0.01 if side == "left"
                       else max(0.0, -new_inner) > max(0.0, -old_inner) + 0.01)
            row[side] = planned
            row["changed_sides"].append(side)
            row["placement"][side] = {
                "old_y_cm": float(original[side]["local_transform"]["location"][1]),
                "old_outer_edge_cm": outer, "new_y_cm": outer,
                "old_inner_edge_cm": old_inner, "new_inner_edge_cm": new_inner,
                "overreach_flag": flagged,
            }
            unreal.log("%s run=%s label=%s side=%s old_y=%.6f old_outer_edge=%.6f new_y=%.6f new_inner_edge=%.6f old_inner_edge=%.6f overreach_flag=%s" %
                       (c.marker(config, "LATERAL_DRY_RUN"), config["run_id"], label, side,
                        row["placement"][side]["old_y_cm"], outer, outer, new_inner,
                        old_inner, str(flagged).lower()))
            if flagged:
                overreach_flags.append({"cue_guid": original["cue_guid"],
                                        "cue_index": original["cue_index"],
                                        "cue_label": label, "side": side,
                                        "old_inner_edge_cm": old_inner,
                                        "new_inner_edge_cm": new_inner})
            planned_meshes.add(desired[side])
        if "top" in requested:
            top = dict(original["top"])
            top["mesh"] = desired["top"]
            top["material_overrides"] = []
            row["top"] = top
            row["changed_sides"].append("top")
            if desired["top"]:
                planned_meshes.add(desired["top"])
        else:
            row["top"] = original["top"]
        if row["changed_sides"]:
            plan.append(row)

    required_hits = int(config.get("required_exclusion_hits", 0))
    if len(excluded_hits) < required_hits:
        raise RuntimeError("REQUIRED_EXCLUSION_NOT_OBSERVED|expected_at_least=%d|actual=%d" %
                           (required_hits, len(excluded_hits)))
    forbidden_paths = {c.destination_mesh(config, name)
                       for name in config.get("excluded_new_meshes", [])}
    leaked = sorted(planned_meshes & forbidden_paths)
    if leaked:
        raise RuntimeError("EXCLUDED_ASSET_PLANNED|" + json.dumps(leaked))
    mesh_gates = {}
    for path in sorted(planned_meshes):
        mesh = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("MESH_GATE_FAIL|path=" + path)
        box = mesh.get_bounding_box()
        mesh_gates[path] = {"loaded_static_mesh": True,
                            "bounds_cm": {"min": [box.min.x, box.min.y, box.min.z],
                                          "max": [box.max.x, box.max.y, box.max.z]}}
    if not plan:
        raise RuntimeError("EMPTY_SWAP_PLAN")
    if c.census() != c.CLEAN:
        raise RuntimeError("DRY_RUN_DIRTIED_EDITOR|census=" + json.dumps(c.census(), sort_keys=True))
    doc = {
        "run": config["run_id"], "slot": config["slot"], "passage": config["passage"],
        "mode": "dry", "status": "PASS", "rows": plan,
        "row_count": len(plan), "mesh_gates": mesh_gates,
        "excluded_rows_kept_old": excluded_hits,
        "overreach_flags": overreach_flags,
        "lateral_derivation": "each side independently: new backbone Y equals the old transformed offstage edge Y; never symmetrise; print and flag overreach",
        "materialize_calls": [config["passage"]], "dirty_after": c.census(),
    }
    path = c.write_json(config, "dry_run", doc)
    unreal.log("%s run=%s rows=%d materialize=[%s] overreach_flags=%d excluded_kept=%d plan=%s" %
               (c.marker(config, "DRY_RUN"), config["run_id"], len(plan), config["passage"],
                len(overreach_flags), len(excluded_hits), path))
    return doc


def main(config_path=None):
    config = None
    try:
        config = c.load_config(config_path)
        return run(config["_path"])
    except Exception as exc:
        if config is not None:
            c.write_json(config, "dry_run", {"run": config["run_id"], "mode": "dry",
                         "status": "FAIL", "reason": str(exc),
                         "traceback": traceback.format_exc(), "census": c.census()}, failure=True)
            c.log_release(config, "FAIL", [], "dry:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
