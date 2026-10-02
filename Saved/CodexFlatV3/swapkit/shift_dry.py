"""Read-only per-occurrence Y-shift plan restoring old inner edges."""
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


def edge_values(side, bounds):
    if side == "left":
        return float(bounds["min_y_cm"]), float(bounds["max_y_cm"])
    return float(bounds["max_y_cm"]), float(bounds["min_y_cm"])


def run(config_path=None):
    config = s.load_config(config_path)
    s.assert_context(config, clean=True)
    preflight = s.read_json(config, "preflight")
    if preflight.get("status") != "PASS":
        raise RuntimeError("SHIFT_PREFLIGHT_NOT_PASS")
    if s.sha256_file(config["source_plan"]) != preflight["source_plan_sha256"]:
        raise RuntimeError("SHIFT_SOURCE_PLAN_CHANGED_AFTER_PREFLIGHT")
    source = s.read_source_plan(config)
    source_by_key = s.rows_by_identity(source["rows"])
    show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
    cues = list(show.get_editor_property("cues"))
    live_rows = s.occurrence_rows(config, show)
    if live_rows != preflight["rows"]:
        raise RuntimeError("SHIFT_PREFLIGHT_STATE_DRIFT")

    library_ref = show.get_editor_property("wing_library")
    library_path = s.shared.asset_path(library_ref)
    library = unreal.EditorAssetLibrary.load_asset(library_path) if library_path else None
    if library is None:
        raise RuntimeError("SHIFT_WING_LIBRARY_LOAD_FAIL|path=" + str(library_path))
    library_by_mesh = {}
    for entry in library.get_editor_property("entries"):
        mesh_path = s.shared.asset_path(entry.get_editor_property("mesh"))
        if mesh_path:
            library_by_mesh[mesh_path] = entry

    target_by_key = s.rows_by_identity(preflight["targets"])
    plan_rows = []
    planned_by_key = {}
    nonzero_count = 0
    for target in preflight["targets"]:
        key = (int(target["cue_index"]), str(target["cue_guid"]))
        source_row = source_by_key[key]
        live = next(row for row in live_rows
                    if (row["cue_index"], row["cue_guid"]) == key)
        s.assert_occurrence(cues[key[0]], live, config)
        override = s.row_override(config, source_row)
        plan = {"cue_index": key[0], "cue_guid": key[1],
                "cue_label": live["cue_label"], "candidate_sides": target["candidate_sides"],
                "shifted_sides": [], "placement": {},
                "row_override": override}
        for side in target["candidate_sides"]:
            current = live["pair"][side]
            bounds = s.shared.side_bounds(s.panel_basic(current), library_by_mesh)
            current_outer, current_inner = edge_values(side, bounds)
            placement = source_row["placement"].get(side)
            if placement is None:
                raise RuntimeError("SHIFT_SOURCE_PLACEMENT_MISSING|label=%s|side=%s" %
                                   (live["cue_label"], side))
            source_current_inner = float(placement["new_inner_edge_cm"])
            source_old_inner = float(placement["old_inner_edge_cm"])
            old_inner, target_source = s.target_inner_edge(
                config, source_row, side, source_old_inner)
            if abs(current_inner - source_current_inner) > 0.1:
                raise RuntimeError("SHIFT_CURRENT_INNER_DRIFT|label=%s|side=%s|source=%g|actual=%g" %
                                   (live["cue_label"], side, source_current_inner, current_inner))
            delta = s.target_delta(
                side, current_inner, old_inner, exact_offstage=override is not None)
            after = s.shifted_panel(current, side, delta)
            after_bounds = s.shared.side_bounds(s.panel_basic(after), library_by_mesh)
            after_outer, after_inner = edge_values(side, after_bounds)
            moved = abs(delta) > 0.000001
            if override is not None and not moved:
                raise RuntimeError("SHIFT_ROW_OVERRIDE_NOT_OFFSTAGE_MOVE|label=%s|side=%s" %
                                   (live["cue_label"], side))
            if moved and abs(after_inner - old_inner) > config["inner_tolerance_cm"]:
                raise RuntimeError(
                    "SHIFT_PLANNED_OLD_INNER_FAIL|label=%s|side=%s|old=%g|actual=%g|"
                    "tolerance_cm=%g" %
                    (live["cue_label"], side, old_inner, after_inner,
                     config["inner_tolerance_cm"]))
            if moved:
                plan["shifted_sides"].append(side)
                nonzero_count += 1
            rule = ("equals_row_override_target_inner" if override is not None else
                    ("equals_old_inner" if moved else "already_offstage_unchanged"))
            plan[side] = after
            plan["placement"][side] = {
                "current_y_cm": float(current["local_transform"]["location"][1]),
                "delta_y_cm": delta,
                "new_y_cm": float(after["local_transform"]["location"][1]),
                "current_inner_edge_cm": current_inner,
                "old_inner_edge_cm": old_inner,
                "source_plan_old_inner_edge_cm": source_old_inner,
                "inner_target_source": target_source,
                "new_inner_edge_cm": after_inner,
                "current_outer_edge_cm": current_outer,
                "new_outer_edge_cm": after_outer,
                "overreach_cm": s.overreach_cm(side, current_inner, old_inner),
                "verification_rule": rule,
            }
            unreal.log("%s run=%s index=%d guid=%s label=%s side=%s current_y=%.6f delta_y=%.6f new_y=%.6f current_inner=%.6f old_inner=%.6f new_inner=%.6f current_outer=%.6f new_outer=%.6f rule=%s" %
                       (s.marker(config, "SHIFT_ROW"), config["run_id"], key[0], key[1],
                        live["cue_label"], side,
                        plan["placement"][side]["current_y_cm"], delta,
                        plan["placement"][side]["new_y_cm"], current_inner, old_inner,
                        after_inner, current_outer, after_outer, rule))
        plan_rows.append(plan)
        planned_by_key[key] = plan
    if nonzero_count != int(config["expected_nonzero_delta_count"]):
        raise RuntimeError("SHIFT_NONZERO_DELTA_COUNT_FAIL|expected=%d|actual=%d" %
                           (int(config["expected_nonzero_delta_count"]), nonzero_count))

    edge_rows = []
    max_before = 0.0
    max_after = 0.0
    beyond = []
    for live in live_rows:
        key = (int(live["cue_index"]), str(live["cue_guid"]))
        planned = planned_by_key.get(key)
        row_edges = {"cue_index": key[0], "cue_guid": key[1],
                     "cue_label": live["cue_label"],
                     "shifted_sides": list(planned["shifted_sides"]) if planned else [],
                     "sides": {}}
        source_row = source_by_key.get(key)
        override = s.row_override(config, source_row) if source_row is not None else None
        for side in s.SIDES:
            before_panel = live["pair"][side]
            after_panel = planned.get(side, before_panel) if planned else before_panel
            before_outer, before_inner = edge_values(
                side, s.shared.side_bounds(s.panel_basic(before_panel), library_by_mesh))
            after_outer, after_inner = edge_values(
                side, s.shared.side_bounds(s.panel_basic(after_panel), library_by_mesh))
            source_placement = ((source_row or {}).get("placement") or {}).get(side)
            source_old_inner = (float(source_placement["old_inner_edge_cm"])
                                if source_placement is not None else before_inner)
            old_inner, target_source = s.target_inner_edge(
                config, source_row, side, source_old_inner) if source_row is not None else \
                (source_old_inner, "live_before")
            row_edges["sides"][side] = {
                "old_inner_edge_cm": old_inner,
                "source_plan_old_inner_edge_cm": source_old_inner,
                "inner_target_source": target_source,
                "before_inner_edge_cm": before_inner, "after_inner_edge_cm": after_inner,
                "before_outer_edge_cm": before_outer, "after_outer_edge_cm": after_outer,
            }
            max_before = max(max_before, abs(before_outer))
            max_after = max(max_after, abs(after_outer))
            if abs(after_outer) > config["outer_report_limit_cm"]:
                beyond.append({"cue_index": key[0], "cue_guid": key[1],
                               "cue_label": live["cue_label"], "side": side,
                               "outer_edge_cm": after_outer})
        row_edges["gap_old_cm"] = s.centre_gap_cm(
            row_edges["sides"]["left"]["old_inner_edge_cm"],
            row_edges["sides"]["right"]["old_inner_edge_cm"])
        row_edges["gap_before_cm"] = s.centre_gap_cm(
            row_edges["sides"]["left"]["before_inner_edge_cm"],
            row_edges["sides"]["right"]["before_inner_edge_cm"])
        row_edges["gap_after_cm"] = s.centre_gap_cm(
            row_edges["sides"]["left"]["after_inner_edge_cm"],
            row_edges["sides"]["right"]["after_inner_edge_cm"])
        row_edges["gap_new_cm"] = row_edges["gap_after_cm"]
        row_edges["gap_baseline_source"] = \
            "row_override" if override is not None else "source_plan_old_inner"
        row_edges["row_override"] = override
        edge_rows.append(row_edges)
    gap_gate = s.minimum_gap_gate(
        edge_rows, config["inner_tolerance_cm"], config["passage"])
    gap_line = s.emit_gap_line(config, gap_gate)
    if s.census() != s.CLEAN:
        raise RuntimeError("SHIFT_DRY_DIRTIED_EDITOR|census=" + json.dumps(s.census(), sort_keys=True))
    report = {
        "run": config["run_id"], "mode": "dry", "status": "PASS",
        "passage": config["passage"], "source_run": config["source_run_id"],
        "rows": plan_rows, "row_count": len(plan_rows),
        "candidate_side_count": sum(len(row["candidate_sides"]) for row in plan_rows),
        "nonzero_delta_count": nonzero_count,
        "row_overrides": config["row_overrides"],
        "override_source_evidence": preflight.get("override_source_evidence", []),
        "edge_rows": edge_rows,
        "max_abs_outer_before_cm": max_before,
        "max_abs_outer_after_cm": max_after,
        "outer_report_limit_cm": config["outer_report_limit_cm"],
        "outer_beyond_limit": beyond,
        "min_gap_old_cm": gap_gate["min_gap_old_cm"],
        "min_gap_new_cm": gap_gate["min_gap_new_cm"],
        "gap_row_count": gap_gate["row_count"],
        "gap_gate": gap_gate, "gap_log_line": gap_line,
        "materialize_calls": [config["passage"]], "dirty_after": s.census(),
    }
    path = s.write_json(config, "dry_run", report)
    unreal.log("%s run=%s passage=%s rows=%d candidate_sides=%d shifted_sides=%d max_outer_before=%.3f max_outer_after=%.3f beyond_%gcm=%d census=%s plan=%s" %
               (s.marker(config, "DRY_RUN"), config["run_id"], config["passage"],
                len(plan_rows), report["candidate_side_count"], nonzero_count,
                max_before, max_after, config["outer_report_limit_cm"], len(beyond),
                json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
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
            s.log_release(config, "FAIL", reason="dry:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
