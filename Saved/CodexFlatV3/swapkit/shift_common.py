"""Shared guards and pure geometry rules for Flat V3 inner-edge shifts."""
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
import copy
import hashlib
import importlib
import json
import math
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as shared
shared = importlib.reload(shared)

WORLD = shared.WORLD
SHOW = shared.SHOW
CLEAN = shared.CLEAN
SAVED_ROOTS = shared.SAVED_ROOTS
BASE = HERE
SIDES = ("left", "right")


def project_path(value):
    value = str(value)
    return os.path.normpath(value if os.path.isabs(value)
                            else os.path.join(shared.PROJECT, value))


def load_config(explicit=None):
    path = explicit or globals().get("FLATV3_CONFIG") or os.environ.get("FLATV3_CONFIG")
    if not path and len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".json"):
        path = sys.argv[1]
    if not path:
        raise RuntimeError("SHIFT_CONFIG_REQUIRED")
    path = project_path(path)
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    required = {
        "schema_version", "slot", "run_id", "saved_verify_run_id", "passage",
        "passage_label_prefix", "passage_actor_label_prefix", "expected_occurrence_count",
        "expected_target_row_count", "expected_candidate_side_count",
        "expected_nonzero_delta_count", "source_kind", "source_plan",
        "source_run_id", "required_previous_markers_any", "keep_old_sides",
        "excluded_new_meshes", "backup_path", "backup_files", "backup_sources",
        "verify_token", "verify_queue_marker", "success_marker",
        "inner_tolerance_cm", "outer_report_limit_cm",
    }
    missing = sorted(required - set(config))
    if missing:
        raise RuntimeError("SHIFT_CONFIG_KEYS_MISSING|" + json.dumps(missing))
    if int(config["schema_version"]) != 1:
        raise RuntimeError("SHIFT_CONFIG_SCHEMA_FAIL|actual=" + str(config["schema_version"]))
    if config["slot"] not in ("S2", "S3", "S4"):
        raise RuntimeError("SHIFT_CONFIG_SLOT_FAIL|actual=" + str(config["slot"]))
    if config["source_kind"] not in ("swapkit", "slot_b"):
        raise RuntimeError("SHIFT_SOURCE_KIND_FAIL|actual=" + str(config["source_kind"]))
    if not str(config["passage_label_prefix"]).startswith(config["passage"] + " Wing "):
        raise RuntimeError("SHIFT_PASSAGE_PREFIX_FAIL")
    if not isinstance(config["required_previous_markers_any"], list) or \
            not config["required_previous_markers_any"]:
        raise RuntimeError("SHIFT_PREVIOUS_MARKERS_FAIL")
    if not isinstance(config["keep_old_sides"], list) or \
            not isinstance(config["excluded_new_meshes"], list):
        raise RuntimeError("SHIFT_EXCLUSIONS_FAIL")
    overrides = config.get("row_overrides", [])
    if not isinstance(overrides, list):
        raise RuntimeError("SHIFT_ROW_OVERRIDES_FAIL")
    override_keys = set()
    for override in overrides:
        required_override = {
            "cue_index", "cue_guid", "cue_label", "reason", "movement_policy",
            "target_inner_edges_cm", "gap_baseline_cm", "source_files",
        }
        if not isinstance(override, dict) or required_override - set(override):
            raise RuntimeError("SHIFT_ROW_OVERRIDE_KEYS_FAIL")
        key = (int(override["cue_index"]), str(override["cue_guid"]))
        if key in override_keys:
            raise RuntimeError("SHIFT_ROW_OVERRIDE_DUPLICATE|index=%d|guid=%s" % key)
        override_keys.add(key)
        if not str(override["cue_label"]).startswith(config["passage_label_prefix"]):
            raise RuntimeError("SHIFT_ROW_OVERRIDE_LABEL_FAIL|index=%d|guid=%s" % key)
        if override["movement_policy"] != "offstage_only_exact_target":
            raise RuntimeError("SHIFT_ROW_OVERRIDE_POLICY_FAIL|index=%d|guid=%s" % key)
        targets = override["target_inner_edges_cm"]
        if not isinstance(targets, dict) or set(targets) != set(SIDES):
            raise RuntimeError("SHIFT_ROW_OVERRIDE_TARGETS_FAIL|index=%d|guid=%s" % key)
        left = float(targets["left"])
        right = float(targets["right"])
        baseline = float(override["gap_baseline_cm"])
        if not all(math.isfinite(value) for value in (left, right, baseline)):
            raise RuntimeError("SHIFT_ROW_OVERRIDE_NOT_FINITE|index=%d|guid=%s" % key)
        if abs(centre_gap_cm(left, right) - baseline) > 0.001:
            raise RuntimeError("SHIFT_ROW_OVERRIDE_GAP_FAIL|index=%d|guid=%s" % key)
        if not isinstance(override["source_files"], list) or not override["source_files"] or \
                any(not isinstance(value, str) or not value for value in override["source_files"]):
            raise RuntimeError("SHIFT_ROW_OVERRIDE_SOURCES_FAIL|index=%d|guid=%s" % key)
    if config["backup_files"] != [
            "DA_InfinityStage_V1Show.uasset", "L_InfinityStage_V1VerticalSlice.umap"]:
        raise RuntimeError("SHIFT_BACKUP_FILES_FAIL")
    if sorted(config["backup_sources"]) != sorted(config["backup_files"]):
        raise RuntimeError("SHIFT_BACKUP_SOURCES_FAIL")
    tolerance = float(config["inner_tolerance_cm"])
    report_limit = float(config["outer_report_limit_cm"])
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise RuntimeError("SHIFT_INNER_TOLERANCE_FAIL")
    if not math.isfinite(report_limit) or report_limit <= 0.0:
        raise RuntimeError("SHIFT_OUTER_REPORT_LIMIT_FAIL")
    config = copy.deepcopy(config)
    config["_path"] = path
    config["source_plan"] = project_path(config["source_plan"])
    source_config = config.get("source_config")
    config["source_config"] = project_path(source_config) if source_config else None
    config["backup_path"] = project_path(config["backup_path"])
    config["backup_sources"] = {
        name: project_path(value) for name, value in config["backup_sources"].items()}
    config["row_overrides"] = overrides
    for override in config["row_overrides"]:
        override["cue_index"] = int(override["cue_index"])
        override["cue_guid"] = str(override["cue_guid"])
        override["target_inner_edges_cm"] = {
            side: float(override["target_inner_edges_cm"][side]) for side in SIDES}
        override["gap_baseline_cm"] = float(override["gap_baseline_cm"])
        override["source_files"] = [project_path(value) for value in override["source_files"]]
    config["inner_tolerance_cm"] = tolerance
    config["outer_report_limit_cm"] = report_limit
    return config


def marker(config, suffix):
    return "FLATV3_%s_%s" % (config["slot"], suffix)


def artifact(config, phase, run=None, failure=False):
    return os.path.join(BASE, "shift_%s_%s%s.json" % (
        phase, run or config["run_id"], "_FAILURE" if failure else ""))


def write_json(config, phase, value, run=None, failure=False):
    path = artifact(config, phase, run, failure)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_json(config, phase, run=None):
    with open(artifact(config, phase, run), encoding="utf-8") as handle:
        return json.load(handle)


def read_source_plan(config):
    with open(config["source_plan"], encoding="utf-8") as handle:
        plan = json.load(handle)
    if str(plan.get("run")) != str(config["source_run_id"]):
        raise RuntimeError("SHIFT_SOURCE_RUN_MISMATCH|expected=%s|actual=%s" %
                           (config["source_run_id"], plan.get("run")))
    if not plan.get("rows"):
        raise RuntimeError("SHIFT_SOURCE_PLAN_EMPTY")
    return plan


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def census():
    return shared.census()


def assert_context(config, clean=True):
    return shared.assert_context(config, clean=clean)


def log_has(value):
    return shared.log_has(value)


def assert_fresh_verify_token(config):
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_log_dir()), "PussStage.log")
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    queued = text.rfind(config["verify_queue_marker"])
    completed = text.rfind(config["verify_token"])
    if queued < 0:
        raise RuntimeError("SHIFT_VERIFY_QUEUE_MARKER_NOT_FOUND|" +
                           config["verify_queue_marker"])
    if completed < queued:
        raise RuntimeError("SHIFT_VERIFY_TOKEN_NOT_AFTER_QUEUE|" + config["verify_token"])
    return {"queue_offset": queued, "completion_offset": completed}


def previous_marker(config):
    hits = [value for value in config["required_previous_markers_any"] if log_has(value)]
    if not hits:
        raise RuntimeError("SHIFT_PREVIOUS_MARKER_MISSING|accepted=" +
                           json.dumps(config["required_previous_markers_any"]))
    return hits[0]


def validate_source_exclusions(config):
    if not config.get("source_config"):
        return
    with open(config["source_config"], encoding="utf-8") as handle:
        source = json.load(handle)
    if source.get("keep_old_sides", []) != config["keep_old_sides"]:
        raise RuntimeError("SHIFT_KEEP_OLD_SOURCE_MISMATCH")
    if source.get("excluded_new_meshes", []) != config["excluded_new_meshes"]:
        raise RuntimeError("SHIFT_EXCLUDED_MESH_SOURCE_MISMATCH")


def keep_keys(config):
    return {(str(row["cue_guid"]), str(row["side"]).lower())
            for row in config["keep_old_sides"]}


def excluded_mesh(config, mesh_path):
    name = "" if mesh_path is None else str(mesh_path).rsplit("/", 1)[-1]
    return mesh_path in config["excluded_new_meshes"] or name in config["excluded_new_meshes"]


def candidate_sides(config, source_row):
    requested = set(SIDES if config["source_kind"] == "slot_b" else
                    (side for side in source_row.get("changed_sides", []) if side in SIDES))
    kept = keep_keys(config)
    return [side for side in SIDES if side in requested and
            (str(source_row["cue_guid"]), side) not in kept and
            not excluded_mesh(config, source_row[side]["mesh"])]


def row_override(config, row):
    key = (int(row["cue_index"]), str(row["cue_guid"]))
    matches = [override for override in config.get("row_overrides", [])
               if (int(override["cue_index"]), str(override["cue_guid"])) == key]
    if len(matches) > 1:
        raise RuntimeError("SHIFT_ROW_OVERRIDE_DUPLICATE|index=%d|guid=%s" % key)
    if not matches:
        return None
    override = matches[0]
    if str(row.get("cue_label")) != str(override["cue_label"]):
        raise RuntimeError("SHIFT_ROW_OVERRIDE_IDENTITY_FAIL|index=%d|guid=%s|expected=%s|actual=%s" %
                           (key[0], key[1], override["cue_label"], row.get("cue_label")))
    return override


def target_inner_edge(config, source_row, side, source_old_inner_cm):
    override = row_override(config, source_row)
    if override is None:
        return float(source_old_inner_cm), "source_plan_old_inner"
    return float(override["target_inner_edges_cm"][side]), "row_override"


def target_delta(side, current_inner_cm, target_inner_cm, exact_offstage=False):
    if exact_offstage:
        return validate_offstage_delta(
            side, float(target_inner_cm) - float(current_inner_cm))
    return offstage_delta(side, current_inner_cm, target_inner_cm)


def override_source_evidence(config):
    evidence = []
    for override in config.get("row_overrides", []):
        for path in override["source_files"]:
            if not os.path.isfile(path):
                raise RuntimeError("SHIFT_ROW_OVERRIDE_SOURCE_MISSING|" + path)
            evidence.append({
                "cue_index": int(override["cue_index"]),
                "cue_guid": str(override["cue_guid"]),
                "path": path,
                "sha256": sha256_file(path),
            })
    return evidence


def old_centreline_flag(side, new_inner_cm, old_inner_cm):
    if side == "left":
        return max(0.0, float(new_inner_cm)) > max(0.0, float(old_inner_cm)) + 0.01
    if side == "right":
        return max(0.0, -float(new_inner_cm)) > max(0.0, -float(old_inner_cm)) + 0.01
    raise RuntimeError("SHIFT_SIDE_FAIL|" + str(side))


def overreach_cm(side, current_inner_cm, old_inner_cm):
    if side == "left":
        return max(0.0, float(current_inner_cm) - float(old_inner_cm))
    if side == "right":
        return max(0.0, float(old_inner_cm) - float(current_inner_cm))
    raise RuntimeError("SHIFT_SIDE_FAIL|" + str(side))


def new_overreach_flag(side, current_inner_cm, old_inner_cm, tolerance_cm):
    return overreach_cm(side, current_inner_cm, old_inner_cm) > float(tolerance_cm)


def centre_gap_cm(left_inner_cm, right_inner_cm):
    """Return the clear centre gap in the pair frame (right inner - left inner)."""
    return float(right_inner_cm) - float(left_inner_cm)


def minimum_gap_gate(rows, tolerance_cm, passage):
    """Gate the minimum shifted occurrence against that occurrence's old gap."""
    tolerance = float(tolerance_cm)
    eligible = [row for row in rows if row.get("shifted_sides")]
    if not eligible:
        raise RuntimeError("SHIFT_GAP_ROWS_EMPTY|passage=" + str(passage))
    for row in eligible:
        for key in ("gap_old_cm", "gap_new_cm"):
            if not math.isfinite(float(row[key])):
                raise RuntimeError("SHIFT_GAP_NOT_FINITE|passage=%s|label=%s|field=%s" %
                                   (passage, row.get("cue_label"), key))
    # Every shifted row must keep its own old gap (Gary: "the old gap restored");
    # checking only the narrowest new row let a mislabelled table through review.
    narrowed = [row for row in eligible
                if float(row["gap_new_cm"]) < float(row["gap_old_cm"]) - tolerance]
    if narrowed:
        worst = min(narrowed, key=lambda row: float(row["gap_new_cm"]) - float(row["gap_old_cm"]))
        raise RuntimeError(
            "SHIFT_ROW_GAP_FAIL|passage=%s|rows=%d|worst_label=%s|old=%.6f|new=%.6f" %
            (passage, len(narrowed), worst.get("cue_label"),
             float(worst["gap_old_cm"]), float(worst["gap_new_cm"])))
    minimum = min(eligible, key=lambda row: float(row["gap_new_cm"]))
    old_gap = float(minimum["gap_old_cm"])
    new_gap = float(minimum["gap_new_cm"])
    if new_gap < old_gap - tolerance:
        raise RuntimeError(
            "SHIFT_MIN_GAP_FAIL|passage=%s|label=%s|min_old=%.6f|min_new=%.6f|"
            "tolerance_cm=%.6f|rows=%d" %
            (passage, minimum.get("cue_label"), old_gap, new_gap,
             tolerance, len(eligible)))
    return {
        "passage": str(passage),
        "min_gap_old_cm": old_gap,
        "min_gap_new_cm": new_gap,
        "minimum_cue_index": int(minimum["cue_index"]),
        "minimum_cue_guid": str(minimum["cue_guid"]),
        "minimum_cue_label": str(minimum["cue_label"]),
        "row_count": len(eligible),
        "passage_min_gap_old_cm": min(float(row["gap_old_cm"]) for row in eligible),
        "passage_min_gap_new_cm": min(float(row["gap_new_cm"]) for row in eligible),
        "tolerance_cm": tolerance,
    }


def emit_gap_line(config, summary):
    line = ("FLATV3_%s_GAPS passage=%s min_old=%.3f min_new=%.3f rows=%d" %
            (config["slot"], config["passage"], summary["min_gap_old_cm"],
             summary["min_gap_new_cm"], summary["row_count"]))
    print(line)
    unreal.log(line)
    return line


def validate_offstage_delta(side, delta_cm, tolerance=0.000001):
    delta = float(delta_cm)
    if (side == "left" and delta > tolerance) or (side == "right" and delta < -tolerance):
        raise RuntimeError("SHIFT_ONSTAGE_DELTA_FAIL|side=%s|delta_cm=%.9f" % (side, delta))
    if side not in SIDES:
        raise RuntimeError("SHIFT_SIDE_FAIL|" + str(side))
    return delta


def offstage_delta(side, current_inner_cm, old_inner_cm):
    amount = overreach_cm(side, current_inner_cm, old_inner_cm)
    return validate_offstage_delta(side, -amount if side == "left" else amount)


def shifted_panel(panel_record, side, delta_cm):
    delta = validate_offstage_delta(side, delta_cm)
    result = copy.deepcopy(panel_record)
    result["local_transform"]["location"][1] = \
        float(result["local_transform"]["location"][1]) + delta
    assert_y_only(panel_record, result)
    return result


def assert_y_only(before, after, tolerance=0.000001):
    check = copy.deepcopy(after)
    check["local_transform"]["location"][1] = before["local_transform"]["location"][1]
    if check != before:
        raise RuntimeError("SHIFT_NON_Y_FIELD_CHANGED")
    if not math.isfinite(float(after["local_transform"]["location"][1])):
        raise RuntimeError("SHIFT_Y_NOT_FINITE")
    return abs(float(after["local_transform"]["location"][1]) -
               float(before["local_transform"]["location"][1])) > tolerance


def panel_plain_full(panel):
    value = shared.panel_plain(panel)
    value.update({
        "cast_shadow": bool(panel.get_editor_property("cast_shadow")),
        "visible_in_main_pass": bool(panel.get_editor_property("visible_in_main_pass")),
        "collision": str(panel.get_editor_property("collision")),
    })
    return value


def panel_basic(value):
    return {key: copy.deepcopy(value[key]) for key in (
        "mesh", "material_overrides", "local_transform", "facing_policy",
        "flip_image_horizontally")}


def pair_plain(pair):
    mechanism = shared.mechanism_plain(pair.get_editor_property("mechanism"))
    mechanism_value = pair.get_editor_property("mechanism")
    mechanism.update({
        "max_angle_deg": float(mechanism_value.get_editor_property("max_angle_deg")),
        "top_follows_mechanism": bool(
            mechanism_value.get_editor_property("top_follows_mechanism")),
    })
    return {
        "left": panel_plain_full(pair.get_editor_property("left")),
        "right": panel_plain_full(pair.get_editor_property("right")),
        "top": panel_plain_full(pair.get_editor_property("top")),
        "has_top": bool(pair.get_editor_property("has_top")),
        "interval_to_next": shared.frame_value(pair.get_editor_property("interval_to_next")),
        "gap_to_next_cm": float(pair.get_editor_property("gap_to_next_cm")),
        "occurrence_offset": shared.transform_plain(pair.get_editor_property("occurrence_offset")),
        "mechanism": mechanism,
        "mute_mechanism_sound": bool(pair.get_editor_property("mute_mechanism_sound")),
        "local_override_mask": int(pair.get_editor_property("local_override_mask")),
    }


def occurrence_rows(config, show):
    rows = []
    for cue_index, cue in enumerate(show.get_editor_property("cues")):
        label = str(cue.get_editor_property("label"))
        if not label.startswith(config["passage_label_prefix"]):
            continue
        rows.append({"cue_index": cue_index, "cue_guid": shared.cue_guid(cue),
                     "cue_label": label, "pair": pair_plain(
                         cue.get_editor_property("wing_pair"))})
    if len(rows) != int(config["expected_occurrence_count"]):
        raise RuntimeError("SHIFT_OCCURRENCE_COUNT_FAIL|expected=%d|actual=%d" %
                           (int(config["expected_occurrence_count"]), len(rows)))
    keys = [(row["cue_index"], row["cue_guid"]) for row in rows]
    if len(keys) != len(set(keys)) or len({row["cue_guid"] for row in rows}) != len(rows):
        raise RuntimeError("SHIFT_OCCURRENCE_IDENTITY_DUPLICATE")
    return rows


def assert_occurrence(cue, row, config, error="SHIFT_CUE_IDENTITY_FAIL"):
    return shared.assert_occurrence(cue, row["cue_index"], row,
                                    config["passage_label_prefix"], error)


def passage_actor(config, show):
    return shared.passage_actor(config, show)


def set_panel_y(panel, expected_before, expected_after):
    actual = panel_plain_full(panel)
    if actual != expected_before:
        raise RuntimeError("SHIFT_PANEL_DRIFT_BEFORE")
    assert_y_only(expected_before, expected_after)
    panel.set_editor_property(
        "local_transform", shared.transform_from_plain(expected_after["local_transform"]))
    return panel


def rows_by_identity(rows):
    return {(int(row["cue_index"]), str(row["cue_guid"])): row for row in rows}


def expected_shifted_rows(preflight, dry):
    rows = copy.deepcopy(preflight["rows"])
    by_key = rows_by_identity(rows)
    for plan in dry["rows"]:
        row = by_key[(int(plan["cue_index"]), str(plan["cue_guid"]))]
        for side in plan["shifted_sides"]:
            row["pair"][side] = copy.deepcopy(plan[side])
    return rows


def saved_roots_for_run(config, run=None, current=None):
    roots = set(current or [])
    for phase in ("apply", "revert"):
        path = artifact(config, phase, run or config["run_id"])
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                roots.update(json.load(handle).get("saved_roots", []))
    return sorted(roots)


def log_release(config, status, saved_roots=None, reason=None, run=None, artifact_run=None):
    release_run = run or config["run_id"]
    roots = saved_roots_for_run(config, artifact_run or config["run_id"], saved_roots)
    if reason:
        unreal.log_error("%s run=%s reason=%s census=%s" %
                         (marker(config, "FAIL"), release_run,
                          str(reason).replace("\n", "\\n"),
                          json.dumps(census(), separators=(",", ":"), sort_keys=True)))
    unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s census=%s" %
               (release_run, status, len(roots), json.dumps(roots, separators=(",", ":")),
                json.dumps(census(), separators=(",", ":"), sort_keys=True)))
