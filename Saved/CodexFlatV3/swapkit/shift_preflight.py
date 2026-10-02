"""Read-only census and applied-plan identity gate for one inner-edge shift."""
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
import shift_common as s
s = importlib.reload(s)


def run(config_path=None):
    config = s.load_config(config_path)
    s.assert_context(config, clean=True)
    if s.log_has("FLATV3_SLOT_RELEASED run=" + config["run_id"]):
        raise RuntimeError("SHIFT_RUN_ALREADY_RELEASED")
    prior_marker = s.previous_marker(config)
    s.validate_source_exclusions(config)
    source = s.read_source_plan(config)
    source_hash = s.sha256_file(config["source_plan"])
    override_sources = s.override_source_evidence(config)
    show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
    if show is None:
        raise RuntimeError("SHIFT_SHOW_LOAD_FAIL")
    rows = s.occurrence_rows(config, show)
    live = s.rows_by_identity(rows)
    cues = list(show.get_editor_property("cues"))
    targets = []
    matched_overrides = set()
    for source_row in source["rows"]:
        sides = s.candidate_sides(config, source_row)
        if not sides:
            continue
        override = s.row_override(config, source_row)
        if override is not None:
            if set(sides) != set(s.SIDES):
                raise RuntimeError("SHIFT_ROW_OVERRIDE_CANDIDATE_SIDES_FAIL|label=%s|sides=%s" %
                                   (source_row["cue_label"], json.dumps(sides)))
            matched_overrides.add((int(source_row["cue_index"]), str(source_row["cue_guid"])))
        key = (int(source_row["cue_index"]), str(source_row["cue_guid"]))
        current = live.get(key)
        if current is None:
            raise RuntimeError("SHIFT_SOURCE_OCCURRENCE_MISSING|index=%s|guid=%s" % key)
        cue = cues[key[0]]
        s.assert_occurrence(cue, current, config)
        for side in sides:
            actual = s.panel_basic(current["pair"][side])
            if not s.shared.panel_matches(actual, source_row[side]):
                raise RuntimeError("SHIFT_APPLIED_PLAN_DRIFT|label=%s|index=%d|guid=%s|side=%s" %
                                   (current["cue_label"], key[0], key[1], side))
        targets.append({"cue_index": key[0], "cue_guid": key[1],
                        "cue_label": current["cue_label"], "candidate_sides": sides,
                        "row_override": copy.deepcopy(override) if override else None})
    configured_overrides = {(int(row["cue_index"]), str(row["cue_guid"]))
                            for row in config["row_overrides"]}
    if matched_overrides != configured_overrides:
        raise RuntimeError("SHIFT_ROW_OVERRIDE_UNMATCHED|configured=%s|matched=%s" %
                           (json.dumps(sorted(configured_overrides)),
                            json.dumps(sorted(matched_overrides))))
    if len(targets) != int(config["expected_target_row_count"]):
        raise RuntimeError("SHIFT_TARGET_ROW_COUNT_FAIL|expected=%d|actual=%d" %
                           (int(config["expected_target_row_count"]), len(targets)))
    candidate_count = sum(len(row["candidate_sides"]) for row in targets)
    if candidate_count != int(config["expected_candidate_side_count"]):
        raise RuntimeError("SHIFT_CANDIDATE_SIDE_COUNT_FAIL|expected=%d|actual=%d" %
                           (int(config["expected_candidate_side_count"]), candidate_count))
    if s.census() != s.CLEAN:
        raise RuntimeError("SHIFT_PREFLIGHT_DIRTIED_EDITOR|census=" +
                           json.dumps(s.census(), sort_keys=True))
    report = {
        "run": config["run_id"], "mode": "preflight", "status": "PASS",
        "passage": config["passage"], "prior_marker": prior_marker,
        "source_run": config["source_run_id"], "source_plan": config["source_plan"],
        "source_plan_sha256": source_hash, "rows": rows, "targets": targets,
        "occurrence_count": len(rows), "target_row_count": len(targets),
        "candidate_side_count": candidate_count,
        "row_overrides": config["row_overrides"],
        "override_source_evidence": override_sources,
        "keep_old_sides": config["keep_old_sides"],
        "excluded_new_meshes": config["excluded_new_meshes"],
        "dirty_after": s.census(),
    }
    path = s.write_json(config, "preflight", report)
    unreal.log("%s run=%s passage=%s occurrences=%d target_rows=%d candidate_sides=%d previous=%s census=%s report=%s" %
               (s.marker(config, "PREFLIGHT_OK"), config["run_id"], config["passage"],
                len(rows), len(targets), candidate_count, prior_marker,
                json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
    return report


def main(config_path=None):
    config = None
    try:
        config = s.load_config(config_path)
        return run(config["_path"])
    except Exception as exc:
        if config is not None:
            s.write_json(config, "preflight", {
                "run": config["run_id"], "mode": "preflight", "status": "FAIL",
                "reason": str(exc), "traceback": traceback.format_exc(),
                "census": s.census()}, failure=True)
            s.log_release(config, "FAIL", reason="preflight:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
