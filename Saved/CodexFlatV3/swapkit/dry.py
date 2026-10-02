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
    within_tolerance = []
    unexplained_overreach = []
    kept_old_sides = []
    excluded_hits = []
    planned_meshes = set()
    tolerance_cm = float(config["overreach_tolerance_cm"])
    keep_by_key = c.keep_old_by_key(config)
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
               "kept_old_sides": [], "placement": {},
               "top_unchanged": original["top"],
               "occurrence_offset_unchanged": original["occurrence_offset"],
               "mechanism_unchanged": original["mechanism"]}
        for side in ("left", "right"):
            keep_entry = keep_by_key.get((original["cue_guid"], side))
            if side not in requested:
                row[side] = original[side]
                if keep_entry is not None:
                    kept = {"cue_guid": original["cue_guid"],
                            "cue_index": original["cue_index"], "cue_label": label,
                            "side": side, "reason": keep_entry["reason"],
                            "old_panel": original[side], "proposal_present": False}
                    row["kept_old_sides"].append(kept)
                    kept_old_sides.append(kept)
                continue
            old_bounds = c.side_bounds(original[side], library_by_mesh)
            outer = old_bounds["min_y_cm"] if side == "left" else old_bounds["max_y_cm"]
            planned = c.planned_panel(desired[side], outer)
            new_bounds = c.side_bounds(planned, library_by_mesh)
            old_inner = old_bounds["max_y_cm"] if side == "left" else old_bounds["min_y_cm"]
            new_inner = new_bounds["max_y_cm"] if side == "left" else new_bounds["min_y_cm"]
            overreach_cm = max(0.0, (new_inner - old_inner) if side == "left"
                               else (old_inner - new_inner))
            flagged = overreach_cm > tolerance_cm
            adjudication = ("kept_old" if keep_entry is not None else
                            "within_tolerance" if 0.0 < overreach_cm <= tolerance_cm else
                            "unexplained" if flagged else "none")
            row["placement"][side] = {
                "old_y_cm": float(original[side]["local_transform"]["location"][1]),
                "old_outer_edge_cm": outer, "new_y_cm": outer,
                "old_inner_edge_cm": old_inner, "new_inner_edge_cm": new_inner,
                "overreach_cm": overreach_cm, "overreach_flag": flagged,
                "overreach_adjudication": adjudication,
            }
            unreal.log("%s run=%s label=%s side=%s old_y=%.6f old_outer_edge=%.6f new_y=%.6f new_inner_edge=%.6f old_inner_edge=%.6f overreach_cm=%.6f overreach_flag=%s adjudication=%s" %
                       (c.marker(config, "LATERAL_DRY_RUN"), config["run_id"], label, side,
                        row["placement"][side]["old_y_cm"], outer, outer, new_inner,
                        old_inner, overreach_cm, str(flagged).lower(), adjudication))
            flag = {"cue_guid": original["cue_guid"],
                    "cue_index": original["cue_index"],
                    "cue_label": label, "side": side,
                    "old_inner_edge_cm": old_inner,
                    "new_inner_edge_cm": new_inner,
                    "overreach_cm": overreach_cm,
                    "adjudication": adjudication}
            if keep_entry is not None:
                row[side] = original[side]
                kept = {"cue_guid": original["cue_guid"],
                        "cue_index": original["cue_index"], "cue_label": label,
                        "side": side, "reason": keep_entry["reason"],
                        "old_panel": original[side], "proposal_present": True,
                        "proposed_mesh": desired[side],
                        "proposed_old_outer_edge_cm": outer,
                        "proposed_old_inner_edge_cm": old_inner,
                        "proposed_new_inner_edge_cm": new_inner,
                        "proposed_overreach_cm": overreach_cm,
                        "proposed_overreach_flag": flagged}
                row["kept_old_sides"].append(kept)
                kept_old_sides.append(kept)
                if flagged:
                    overreach_flags.append(flag)
                continue
            row[side] = planned
            row["changed_sides"].append(side)
            if flagged:
                overreach_flags.append(flag)
                unexplained_overreach.append(flag)
            elif adjudication == "within_tolerance":
                within_tolerance.append(flag)
            planned_meshes.add(desired[side])
        top_keep = keep_by_key.get((original["cue_guid"], "top"))
        if top_keep is not None:
            row["top"] = original["top"]
            kept = {"cue_guid": original["cue_guid"],
                    "cue_index": original["cue_index"], "cue_label": label,
                    "side": "top", "reason": top_keep["reason"],
                    "old_panel": original["top"],
                    "proposal_present": "top" in requested,
                    "proposed_mesh": desired["top"] if "top" in requested else original["top"]["mesh"]}
            row["kept_old_sides"].append(kept)
            kept_old_sides.append(kept)
        elif "top" in requested:
            top = dict(original["top"])
            top["mesh"] = desired["top"]
            top["material_overrides"] = []
            row["top"] = top
            row["changed_sides"].append("top")
            if desired["top"]:
                planned_meshes.add(desired["top"])
        else:
            row["top"] = original["top"]
        if row["changed_sides"] or row["kept_old_sides"]:
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
    if unexplained_overreach:
        raise RuntimeError("UNEXPLAINED_OVERREACH_FLAGS|count=%d" %
                           len(unexplained_overreach))
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
        "overreach_tolerance_cm": tolerance_cm,
        "within_tolerance_overreach_flags": within_tolerance,
        "unexplained_overreach_flags": unexplained_overreach,
        "kept_old_sides": kept_old_sides,
        "lateral_derivation": "each side independently: new backbone Y equals the old transformed offstage edge Y; never symmetrise; print and flag overreach",
        "materialize_calls": [config["passage"]], "dirty_after": c.census(),
    }
    path = c.write_json(config, "dry_run", doc)
    unreal.log("%s run=%s rows=%d materialize=[%s] overreach_flags=%d within_tolerance=%d unexplained=%d kept_old_sides=%d excluded_kept=%d plan=%s" %
               (c.marker(config, "DRY_RUN"), config["run_id"], len(plan), config["passage"],
                len(overreach_flags), len(within_tolerance), len(unexplained_overreach),
                len(kept_old_sides), len(excluded_hits), path))
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
