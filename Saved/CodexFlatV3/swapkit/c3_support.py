"""Shared guards and pure gates for Flat V3 slot C3.

The pure functions deliberately import without Unreal so the offline harness can
exercise the exact target-count, height, offstage and gap rules.
"""
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
import glob
import hashlib
import json
import math
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
CLEAN = {"content": [], "maps": []}
SAVED_ROOTS = [SHOW, WORLD]


def project_path(value):
    value = str(value)
    return os.path.normpath(value if os.path.isabs(value) else os.path.join(PROJECT, value))


def load_config(explicit=None):
    path = explicit or globals().get("FLATV3_CONFIG") or os.environ.get("FLATV3_CONFIG")
    if not path and len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".json"):
        path = sys.argv[1]
    path = project_path(path or os.path.join(HERE, "run_c3.json"))
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    required = {
        "schema_version", "slot", "run_id", "import_run_id", "passage",
        "passage_label_prefix", "passage_actor_label_prefix",
        "expected_occurrence_count", "expected_row_index_start",
        "expected_row_index_end", "target_count", "source_c_dry_plan",
        "source_root", "destination_root", "asset_name", "asset_owner",
        "old_left_mesh", "new_left_mesh", "required_previous_markers",
        "import_success_marker", "success_marker", "target_bottom_min_cm",
        "target_bottom_span_cm", "bottom_tolerance_cm",
        "inner_edge_tolerance_cm", "gap_tolerance_cm",
        "expected_lod0_triangles", "expected_lod1_triangles", "backup_path",
        "backup_files", "backup_sources", "verify_token", "donor", "targets",
    }
    missing = sorted(required - set(config))
    if missing:
        raise RuntimeError("C3_CONFIG_KEYS_MISSING|" + json.dumps(missing))
    if (int(config["schema_version"]) != 1 or config["slot"] != "C3" or
            config["run_id"] != "FV3C3-20261002-01" or
            config["import_run_id"] != "FV3C3I-20261002-01" or
            config["passage"] != "P05" or config["passage_label_prefix"] != "P05 Wing " or
            int(config["expected_occurrence_count"]) != 93 or
            int(config["expected_row_index_start"]) != 122 or
            int(config["expected_row_index_end"]) != 214 or
            int(config["target_count"]) != 12):
        raise RuntimeError("C3_CONFIG_SCOPE_FAIL")
    if config["backup_files"] != [
            "DA_InfinityStage_V1Show.uasset", "L_InfinityStage_V1VerticalSlice.umap"]:
        raise RuntimeError("C3_CONFIG_BACKUP_FILES_FAIL")
    if sorted(config["backup_sources"]) != sorted(config["backup_files"]):
        raise RuntimeError("C3_CONFIG_BACKUP_SOURCES_FAIL")
    for name in ("target_bottom_min_cm", "target_bottom_span_cm",
                 "bottom_tolerance_cm", "inner_edge_tolerance_cm", "gap_tolerance_cm"):
        config[name] = float(config[name])
        if not math.isfinite(config[name]) or config[name] < 0.0:
            raise RuntimeError("C3_CONFIG_NUMBER_FAIL|field=" + name)
    if (config["target_bottom_min_cm"] != 150.0 or
            config["target_bottom_span_cm"] != 300.0 or
            config["bottom_tolerance_cm"] != 1.0 or
            config["gap_tolerance_cm"] != 2.0):
        raise RuntimeError("C3_CONFIG_GATE_VALUE_FAIL")
    config = dict(config)
    config["_path"] = path
    for name in ("source_c_dry_plan", "source_root", "backup_path"):
        config[name] = project_path(config[name])
    config["backup_sources"] = {
        name: project_path(value) for name, value in config["backup_sources"].items()}
    validate_target_rows(config["targets"], config["targets"], config["target_count"])
    return config


def target_key(row):
    return (int(row["cue_index"]), str(row["cue_guid"]))


def validate_target_rows(rows, targets, expected_count=12):
    """Require the complete exact index+GUID target set; labels are secondary."""
    if len(rows) != int(expected_count):
        raise RuntimeError("C3_TARGET_COUNT_FAIL|expected=%d|actual=%d" %
                           (int(expected_count), len(rows)))
    expected = {target_key(row): str(row["cue_label"]) for row in targets}
    actual = {target_key(row): str(row["cue_label"]) for row in rows}
    if len(expected) != int(expected_count) or len(actual) != int(expected_count):
        raise RuntimeError("C3_TARGET_IDENTITY_DUPLICATE")
    if actual != expected:
        raise RuntimeError("C3_TARGET_IDENTITY_FAIL|expected=%s|actual=%s" %
                           (json.dumps(sorted(expected)), json.dumps(sorted(actual))))
    return sorted(actual)


def stable_unit(cue_guid, side="left"):
    side = str(side).lower()
    if side not in ("left", "right"):
        raise RuntimeError("C3_HASH_SIDE_FAIL|side=" + side)
    digest = hashlib.sha256((str(cue_guid) + side).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False) / float(2 ** 64)


def target_height(config, cue_guid, side="left"):
    return (float(config["target_bottom_min_cm"]) +
            float(config["target_bottom_span_cm"]) * stable_unit(cue_guid, side))


def assert_bottom(actual_cm, expected_cm, tolerance_cm, identity=""):
    if (not math.isfinite(float(actual_cm)) or not math.isfinite(float(expected_cm)) or
            abs(float(actual_cm) - float(expected_cm)) > float(tolerance_cm)):
        raise RuntimeError("C3_BOTTOM_NOT_H|identity=%s|expected=%.9f|actual=%.9f|tolerance=%.9f" %
                           (identity, float(expected_cm), float(actual_cm),
                            float(tolerance_cm)))
    return float(actual_cm)


def validate_offstage_move(side, delta_cm, tolerance=0.000001):
    side = str(side).lower()
    delta = float(delta_cm)
    if side not in ("left", "right"):
        raise RuntimeError("C3_SIDE_FAIL|side=" + side)
    if (side == "left" and delta > tolerance) or (side == "right" and delta < -tolerance):
        raise RuntimeError("C3_ONSTAGE_INNER_MOVE|side=%s|delta_cm=%.9f" % (side, delta))
    return delta


def centre_gap(left_inner_cm, right_inner_cm):
    return float(right_inner_cm) - float(left_inner_cm)


def minimum_gap_gate(rows, tolerance_cm=2.0):
    if not rows:
        raise RuntimeError("C3_GAP_ROWS_EMPTY")
    failures = [row for row in rows
                if float(row["gap_new_cm"]) < float(row["gap_old_cm"]) - float(tolerance_cm)]
    if failures:
        worst = min(failures, key=lambda row: row["gap_new_cm"] - row["gap_old_cm"])
        raise RuntimeError("C3_ROW_GAP_FAIL|index=%d|guid=%s|old=%.6f|new=%.6f" %
                           (int(worst["cue_index"]), worst["cue_guid"],
                            float(worst["gap_old_cm"]), float(worst["gap_new_cm"])))
    minimum = min(rows, key=lambda row: float(row["gap_new_cm"]))
    return {
        "row_count": len(rows), "tolerance_cm": float(tolerance_cm),
        "min_gap_old_cm": min(float(row["gap_old_cm"]) for row in rows),
        "min_gap_new_cm": float(minimum["gap_new_cm"]),
        "minimum_cue_index": int(minimum["cue_index"]),
        "minimum_cue_guid": str(minimum["cue_guid"]),
        "minimum_cue_label": str(minimum["cue_label"]),
    }


def expected_left_panel(current, donor, mesh, y_cm, z_cm):
    """Complete the omitted C swap while preserving non-placement panel fields."""
    result = copy.deepcopy(current)
    result["mesh"] = str(mesh)
    result["material_overrides"] = list(donor["material_overrides"])
    result["local_transform"] = copy.deepcopy(donor["local_transform"])
    result["local_transform"]["location"][1] = float(y_cm)
    result["local_transform"]["location"][2] = float(z_cm)
    result["facing_policy"] = str(donor["facing_policy"])
    result["flip_image_horizontally"] = bool(donor["flip_image_horizontally"])
    return result


def artifact(config, phase, run=None, failure=False):
    suffix = "_FAILURE" if failure else ""
    return os.path.join(HERE, "c3_%s_%s%s.json" %
                        (phase, run or config["run_id"], suffix))


def write_json(config, phase, value, run=None, failure=False):
    path = artifact(config, phase, run=run, failure=failure)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_json(config, phase, run=None):
    with open(artifact(config, phase, run=run), encoding="utf-8") as handle:
        return json.load(handle)


def _unreal():
    import unreal
    return unreal


def census():
    unreal = _unreal()
    def names(packages):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in packages)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def assert_context(config, clean=True):
    unreal = _unreal()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    actual = world.get_outermost().get_name() if world else None
    if actual != WORLD:
        raise RuntimeError("WRONG_WORLD|expected=%s|actual=%s" % (WORLD, actual))
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_OR_SIE_ACTIVE")
    current = census()
    if clean and current != CLEAN:
        raise RuntimeError("DIRTY_AT_C3_START|census=" + json.dumps(current, sort_keys=True))
    return editor, world


def log_paths():
    unreal = _unreal()
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_log_dir())
    return sorted(glob.glob(os.path.join(root, "PussStage*.log")))


def log_has(text):
    for path in log_paths():
        with open(path, encoding="utf-8", errors="replace") as handle:
            if str(text) in handle.read():
                return True
    return False


def marker(suffix):
    return "FLATV3_C3_" + str(suffix)


def saved_roots(config, current=None):
    roots = set(current or [])
    path = artifact(config, "apply")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            roots.update(json.load(handle).get("saved_roots", []))
    return sorted(roots)


def log_release(config, status, roots=None, reason=None, run=None):
    unreal = _unreal()
    run = str(run or config["run_id"])
    roots = sorted(set(roots or ([] if run == config["import_run_id"]
                                  else saved_roots(config))))
    line = ("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s census=%s" %
            (run, status, len(roots), json.dumps(roots, separators=(",", ":")),
             json.dumps(census(), separators=(",", ":"), sort_keys=True)))
    if reason:
        line += " reason=" + str(reason).replace("\n", "\\n")
    unreal.log(line)
    return line
