"""Read-only C3 clean census, P05 identity, donor and floated-bottom preflight."""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    # purge this folder's cached modules: the editor's Python keeps modules across
    # scripts, so a stale verify/common ran (P06, 2 Oct). Entry scripts only.
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
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
import p05float_support as f
f = importlib.reload(f)


def donor_evidence(config):
    with open(config["source_c_dry_plan"], encoding="utf-8") as handle:
        source = json.load(handle)
    candidates = [row for row in source.get("rows", [])
                  if int(row.get("cue_index", -1)) == int(config["donor"]["cue_index"]) and
                  str(row.get("cue_guid")) == config["donor"]["cue_guid"]]
    if len(candidates) != 1:
        raise RuntimeError("C3_DONOR_COUNT_FAIL|actual=%d" % len(candidates))
    row = candidates[0]
    left = row["left"]
    if (row["cue_label"] != config["donor"]["cue_label"] or
            left["mesh"] != config["donor"]["mesh"] or
            config["donor"]["facing_policy"] not in left["facing_policy"] or
            bool(left["flip_image_horizontally"]) !=
            bool(config["donor"]["flip_image_horizontally"])):
        raise RuntimeError("C3_DONOR_CONTRACT_FAIL|row=" + json.dumps(row, sort_keys=True))
    excluded = source.get("excluded_rows_kept_old", [])
    if len(excluded) != 12 or any(
            value.get("excluded_new_mesh") != config["asset_name"] or
            value.get("side") != "left" or value.get("old_mesh") != config["old_left_mesh"]
            for value in excluded):
        raise RuntimeError("C3_SOURCE_EXCLUSION_SCOPE_FAIL|actual=%d" % len(excluded))
    return {"source_plan": config["source_c_dry_plan"],
            "cue_index": row["cue_index"], "cue_guid": row["cue_guid"],
            "cue_label": row["cue_label"], "left": left,
            "excluded_rows_kept_old": len(excluded)}


def run(config_path=None):
    config = s.load_config(config_path)
    if s.log_has("FLATV3_SLOT_RELEASED run=" + config["run_id"]):
        raise RuntimeError("C3_RUN_ALREADY_RELEASED")
    s.assert_context(config, clean=True)
    missing_markers = [value for value in config["required_previous_markers"]
                       if not s.log_has(value)]
    if missing_markers:
        raise RuntimeError("C3_PREVIOUS_MARKER_NOT_FOUND|" + json.dumps(missing_markers))
    mesh = unreal.EditorAssetLibrary.load_asset(config["new_left_mesh"])
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("C3_IMPORTED_MESH_MISSING|" + config["new_left_mesh"])
    donor = donor_evidence(config)
    show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")
    actor = f.passage_actor(config, show)
    occurrence_rows = f.target_rows(config, show)
    rows = [f.occurrence_row(index, cue) for index, cue in occurrence_rows]
    old_mesh_rows = [row for row in rows if row["left"]["mesh"] == config["old_left_mesh"]]
    s.validate_target_rows(old_mesh_rows, config["targets"], config["target_count"])
    by_key = {s.target_key(row): row for row in rows}
    targets = []
    for target in config["targets"]:
        record = by_key.get(s.target_key(target))
        if record is None or record["cue_label"] != target["cue_label"]:
            raise RuntimeError("C3_TARGET_NOT_FOUND|" + json.dumps(target, sort_keys=True))
        refs = f.refs_for(actor, record["cue_guid"])
        placed = f.world_bounds(refs["left"])
        expected = s.target_height(config, record["cue_guid"], "left")
        s.assert_bottom(placed["world_min"][2], expected,
                        config["bottom_tolerance_cm"], record["cue_guid"])
        targets.append({
            "cue_index": record["cue_index"], "cue_guid": record["cue_guid"],
            "cue_label": record["cue_label"], "current_left": record["left"],
            "current_right": record["right"], "current_top": record["top"],
            "current_world_left": placed, "hash_input": record["cue_guid"] + "left",
            "u": s.stable_unit(record["cue_guid"], "left"),
            "expected_H_cm": expected,
        })
    end = s.census()
    if end != s.CLEAN:
        raise RuntimeError("C3_PREFLIGHT_DIRTIED_EDITOR|" + json.dumps(end, sort_keys=True))
    report = {
        "run": config["run_id"], "slot": "C3", "passage": "P05",
        "mode": "preflight", "status": "PASS", "world": s.WORLD, "show": s.SHOW,
        "row_count": len(rows), "index_range": [122, 214], "rows": rows,
        "target_count": len(targets), "targets": targets, "donor": donor,
        "required_previous_markers": config["required_previous_markers"],
        "dirty_at_start": s.CLEAN, "dirty_after": end,
    }
    path = s.write_json(config, "preflight", report)
    unreal.log("%s run=%s rows=93 targets=12 indices=122-214 donor_index=%d census=%s report=%s" %
               (s.marker("PREFLIGHT_OK"), config["run_id"], donor["cue_index"],
                json.dumps(end, separators=(",", ":"), sort_keys=True), path))
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
            s.log_release(config, "FAIL", [], "preflight:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
