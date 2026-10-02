"""Read-only saved and WORLD-instance verification for an inner-edge shift."""
import importlib
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import shift_common as s
s = importlib.reload(s)
import verify as world_verify
world_verify = importlib.reload(world_verify)


def edge_values(side, bounds):
    if side == "left":
        return float(bounds["min"][1]), float(bounds["max"][1])
    return float(bounds["max"][1]), float(bounds["min"][1])


def instance_transform(ref):
    component = ref.get_editor_property("component")
    index = int(ref.get_editor_property("instance_index"))
    value = component.get_instance_transform(index, True)
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], bool):
        if not value[0]:
            raise RuntimeError("SHIFT_INSTANCE_TRANSFORM_FAIL|index=%d" % index)
        value = value[1]
    if value is None:
        raise RuntimeError("SHIFT_INSTANCE_TRANSFORM_FAIL|index=%d" % index)
    return component, value


def run_verify(config_path=None, source_run=None, verification_run=None,
               require_token=True, emit_report=True):
    config = s.load_config(config_path)
    source_run = source_run or config["run_id"]
    verification_run = verification_run or source_run
    s.assert_context(config, clean=True)
    preflight = s.read_json(config, "preflight", source_run)
    dry = s.read_json(config, "dry_run", source_run)
    apply = s.read_json(config, "apply", source_run)
    if any(doc.get("status") != "PASS" for doc in (preflight, dry, apply)):
        raise RuntimeError("SHIFT_VERIFY_PREREQUISITE_NOT_PASS")
    show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
    actual_rows = s.occurrence_rows(config, show)
    expected_rows = s.expected_shifted_rows(preflight, dry)
    if actual_rows != expected_rows:
        raise RuntimeError("SHIFT_VERIFY_AUTHORING_FIELD_CHANGED")
    cues = list(show.get_editor_property("cues"))
    actor = s.passage_actor(config, show)
    library_ref = show.get_editor_property("wing_library")
    library_path = s.shared.asset_path(library_ref)
    library = unreal.EditorAssetLibrary.load_asset(library_path) if library_path else None
    if library is None:
        raise RuntimeError("SHIFT_VERIFY_LIBRARY_LOAD_FAIL")
    library_by_mesh = {}
    for entry in library.get_editor_property("entries"):
        mesh_path = s.shared.asset_path(entry.get_editor_property("mesh"))
        if mesh_path:
            library_by_mesh[mesh_path] = entry

    placed = []
    world_gap_rows = []
    outer_beyond = []
    max_world_outer = 0.0
    tolerance = config["inner_tolerance_cm"]
    expected_by_key = s.rows_by_identity(expected_rows)
    dry_edges_by_key = s.rows_by_identity(dry["edge_rows"])
    for plan in dry["rows"]:
        key = (int(plan["cue_index"]), str(plan["cue_guid"]))
        cue = cues[int(plan["cue_index"])]
        s.assert_occurrence(cue, plan, config, "SHIFT_VERIFY_IDENTITY_FAIL")
        pair = cue.get_editor_property("wing_pair")
        refs = world_verify.refs_for(actor, plan["cue_guid"])
        frame_row = {"changed_sides": plan["candidate_sides"],
                     "cue_label": plan["cue_label"]}
        frame, frame_source = world_verify.pair_frame(
            actor, cue, refs, pair, frame_row, library_by_mesh)
        world_sides = {}
        expected_row = expected_by_key[key]
        for side in s.SIDES:
            ref = refs[side]
            component, placed_transform = instance_transform(ref)
            mesh = component.get_editor_property("static_mesh")
            expected_mesh = expected_row["pair"][side]["mesh"]
            if s.shared.asset_path(mesh) != expected_mesh:
                raise RuntimeError("SHIFT_PLACED_MESH_FAIL|label=%s|side=%s" %
                                   (plan["cue_label"], side))
            bounds = world_verify.bounds_in_frame(mesh, placed_transform, frame)
            outer, inner = edge_values(side, bounds)
            world_sides[side] = {"outer_edge_cm": outer, "inner_edge_cm": inner,
                                 "bounds_pair_cm": bounds}
            max_world_outer = max(max_world_outer, abs(outer))
            if side not in plan["candidate_sides"]:
                continue
            placement = plan["placement"][side]
            expected_inner = float(placement["new_inner_edge_cm"])
            old_inner = float(placement["old_inner_edge_cm"])
            if abs(inner - expected_inner) > tolerance:
                raise RuntimeError("SHIFT_INNER_EDGE_READBACK_FAIL|label=%s|side=%s|expected=%g|actual=%g" %
                                   (plan["cue_label"], side, expected_inner, inner))
            if placement["verification_rule"] in (
                    "equals_old_inner", "equals_row_override_target_inner"):
                if abs(inner - old_inner) > tolerance:
                    raise RuntimeError("SHIFT_OLD_INNER_NOT_RESTORED|label=%s|side=%s|old=%g|actual=%g" %
                                       (plan["cue_label"], side, old_inner, inner))
            elif ((side == "left" and inner > old_inner + tolerance) or
                  (side == "right" and inner < old_inner - tolerance)):
                raise RuntimeError("SHIFT_ALREADY_OFFSTAGE_REGRESSED|label=%s|side=%s|old=%g|actual=%g" %
                                   (plan["cue_label"], side, old_inner, inner))
            record = {"cue_index": plan["cue_index"], "cue_guid": plan["cue_guid"],
                      "cue_label": plan["cue_label"], "side": side,
                      "mesh": expected_mesh, "bounds_pair_cm": bounds,
                      "inner_edge_cm": inner, "old_inner_edge_cm": old_inner,
                      "outer_edge_cm": outer, "verification_rule":
                      placement["verification_rule"], "pair_frame_source": frame_source}
            placed.append(record)
            if abs(outer) > config["outer_report_limit_cm"]:
                outer_beyond.append(record)
        if plan["shifted_sides"]:
            dry_edge = dry_edges_by_key[key]
            world_gap_rows.append({
                "cue_index": key[0], "cue_guid": key[1],
                "cue_label": plan["cue_label"],
                "shifted_sides": list(plan["shifted_sides"]),
                "gap_old_cm": float(dry_edge["gap_old_cm"]),
                "gap_new_cm": s.centre_gap_cm(
                    world_sides["left"]["inner_edge_cm"],
                    world_sides["right"]["inner_edge_cm"]),
                "sides": world_sides,
                "pair_frame_source": frame_source,
            })
    gap_gate = s.minimum_gap_gate(world_gap_rows, tolerance, config["passage"])
    gap_line = s.emit_gap_line(config, gap_gate)
    verify_order = s.assert_fresh_verify_token(config) if require_token else None
    if s.census() != s.CLEAN:
        raise RuntimeError("SHIFT_VERIFY_DIRTIED_EDITOR|" + json.dumps(s.census(), sort_keys=True))
    report = {
        "run": verification_run, "source_shift_run": source_run,
        "mode": "verify", "status": "PASS", "passage": config["passage"],
        "rows": len(dry["rows"]), "placed_panels": placed,
        "max_abs_outer_before_cm": dry["max_abs_outer_before_cm"],
        "max_abs_outer_after_planned_cm": dry["max_abs_outer_after_cm"],
        "max_abs_outer_after_world_cm": max_world_outer,
        "outer_report_limit_cm": config["outer_report_limit_cm"],
        "outer_beyond_limit_world": outer_beyond,
        "world_gap_rows": world_gap_rows,
        "min_gap_old_cm": gap_gate["min_gap_old_cm"],
        "min_gap_new_cm": gap_gate["min_gap_new_cm"],
        "gap_row_count": gap_gate["row_count"],
        "gap_gate": gap_gate, "gap_log_line": gap_line,
        "verify_token": config["verify_token"], "verify_order": verify_order,
        "dirty_after": s.census(),
    }
    if emit_report:
        report["report_path"] = s.write_json(config, "verify", report, run=verification_run)
    return report


def main(config_path=None):
    config = s.load_config(config_path)
    try:
        report = run_verify(config["_path"], config["run_id"], config["run_id"], True, True)
        unreal.log("%s run=%s passage=%s rows=%d placed_panels=%d max_outer_before=%.3f max_outer_after_plan=%.3f max_outer_after_world=%.3f beyond_%gcm=%d census=%s report=%s" %
                   (s.marker(config, "READBACK_OK"), config["run_id"], config["passage"],
                    report["rows"], len(report["placed_panels"]),
                    report["max_abs_outer_before_cm"],
                    report["max_abs_outer_after_planned_cm"],
                    report["max_abs_outer_after_world_cm"], config["outer_report_limit_cm"],
                    len(report["outer_beyond_limit_world"]),
                    json.dumps(s.census(), separators=(",", ":"), sort_keys=True),
                    report["report_path"]))
        unreal.log(config["success_marker"] + " run=" + config["run_id"])
        s.log_release(config, "OK", artifact_run=config["run_id"])
        return report
    except Exception as exc:
        reason = "verify:" + str(exc)
        s.write_json(config, "verify", {
            "run": config["run_id"], "mode": "verify", "status": "FAIL",
            "reason": reason, "traceback": traceback.format_exc(),
            "census": s.census()}, failure=True)
        s.log_release(config, "FAIL", reason=reason, artifact_run=config["run_id"])
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
