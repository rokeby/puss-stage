"""Pure gates and shared helpers for PF, the P05 long-pole mesh-only swap."""
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
SIDES = ("left", "right")
SKIP_REASON = "kept_old_non_v3"


def project_path(value):
    value = str(value)
    return os.path.normpath(value if os.path.isabs(value) else os.path.join(PROJECT, value))


def load_config(explicit=None):
    path = explicit or globals().get("FLATV3_CONFIG") or os.environ.get("FLATV3_CONFIG")
    if not path and len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".json"):
        path = sys.argv[1]
    path = project_path(path or os.path.join(HERE, "run_pf.json"))
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    required = {
        "schema_version", "slot", "run_id", "import_run_id", "passage",
        "passage_label_prefix", "passage_actor_label_prefix", "expected_occurrence_count",
        "expected_asset_count", "source_root", "build_report", "destination_root",
        "required_previous_marker", "import_success_marker", "success_marker",
        "pole_extension_cm", "floor_z_cm", "panel_bottom_tolerance_cm",
        "pole_floor_tolerance_cm", "inner_edge_tolerance_cm", "gap_tolerance_cm",
        "backup_path", "backup_files", "backup_sources", "verify_token",
    }
    missing = sorted(required - set(config))
    if missing:
        raise RuntimeError("PF_CONFIG_KEYS_MISSING|" + json.dumps(missing))
    if (int(config["schema_version"]) != 1 or config["slot"] != "PF" or
            config["passage"] != "P05" or config["passage_label_prefix"] != "P05 Wing " or
            int(config["expected_occurrence_count"]) != 93 or
            int(config["expected_asset_count"]) != 16 or
            config["success_marker"] != "FLATV3_PF_OK"):
        raise RuntimeError("PF_CONFIG_SCOPE_FAIL")
    for name in ("pole_extension_cm", "floor_z_cm", "panel_bottom_tolerance_cm",
                 "pole_floor_tolerance_cm", "inner_edge_tolerance_cm", "gap_tolerance_cm"):
        config[name] = float(config[name])
        if not math.isfinite(config[name]):
            raise RuntimeError("PF_CONFIG_NONFINITE|field=" + name)
    if (config["pole_extension_cm"] != 460.0 or config["floor_z_cm"] != 0.0 or
            config["panel_bottom_tolerance_cm"] != 1.0 or
            config["pole_floor_tolerance_cm"] != 1.0):
        raise RuntimeError("PF_CONFIG_GEOMETRY_GATE_FAIL")
    if config["backup_files"] != [
            "DA_InfinityStage_V1Show.uasset", "L_InfinityStage_V1VerticalSlice.umap"]:
        raise RuntimeError("PF_BACKUP_FILES_FAIL")
    if sorted(config["backup_sources"]) != sorted(config["backup_files"]):
        raise RuntimeError("PF_BACKUP_SOURCES_FAIL")
    config = dict(config)
    config["_path"] = path
    for name in ("source_root", "build_report", "backup_path"):
        config[name] = project_path(config[name])
    config["backup_sources"] = {
        name: project_path(value) for name, value in config["backup_sources"].items()}
    return config


def artifact(config, phase, run=None, failure=False):
    return os.path.join(HERE, "pf_%s_%s%s.json" % (
        phase, run or config["run_id"], "_FAILURE" if failure else ""))


def write_json(config, phase, value, run=None, failure=False):
    path = artifact(config, phase, run=run, failure=failure)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_json(config, phase, run=None):
    with open(artifact(config, phase, run=run), encoding="utf-8") as handle:
        return json.load(handle)


def target_mesh_path(source_mesh, destination_root):
    source_mesh = str(source_mesh)
    prefix = str(destination_root).rstrip("/") + "/StaticMeshes/"
    if not source_mesh.startswith(prefix):
        raise RuntimeError("PF_SOURCE_MESH_ROOT_FAIL|mesh=" + source_mesh)
    name = source_mesh.rsplit("/", 1)[-1]
    if not name.startswith("SM_FlatV3_P05_CloudRef") or name.endswith("_poles"):
        raise RuntimeError("PF_SOURCE_MESH_NAME_FAIL|mesh=" + source_mesh)
    return prefix + name + "_poles"


def mesh_name(mesh_path):
    return str(mesh_path).split(".", 1)[0].rsplit("/", 1)[-1]


def is_flat_v3_mesh(mesh_path):
    return mesh_name(mesh_path).startswith("SM_FlatV3_")


def source_policy(panel, by_source, destination_root):
    """Classify one current side; only kept-old non-V3 sides may bypass the build gate."""
    mesh = str(panel["mesh"])
    if not is_flat_v3_mesh(mesh):
        return {"action": "skip", "reason": SKIP_REASON, "mesh": mesh}
    source = mesh_name(mesh)
    if source not in by_source:
        raise RuntimeError("PF_SOURCE_NOT_BUILT|mesh=" + mesh)
    return {"action": "replace", "source": source,
            "target_mesh": target_mesh_path(mesh, destination_root)}


def side_is_skipped(record, side):
    return record[side].get("pf_action") == "skip"


def skipped_entry(record, side):
    return {"cue_index": int(record["cue_index"]), "cue_guid": record["cue_guid"],
            "cue_label": record["cue_label"], "side": side,
            "mesh": record[side]["mesh"], "reason": record[side]["skip_reason"]}


def skipped_entries(rows):
    return [skipped_entry(record, side) for record in rows for side in SIDES
            if side_is_skipped(record, side)]


def _numbers_close(left, right, tolerance=0.001):
    return (len(left) == len(right) and
            all(abs(float(a) - float(b)) <= float(tolerance)
                for a, b in zip(left, right)))


def _transforms_close(left, right, tolerance=0.001):
    return all(_numbers_close(left[name], right[name], tolerance)
               for name in ("location", "rotation", "scale"))


def validate_skipped_unchanged(before, after, identity="", tolerance=0.001):
    """Prove a kept-old side retained its mesh, transforms, and placed world bounds."""
    failures = []
    if before.get("mesh") != after.get("mesh"):
        failures.append("MESH_CHANGED")
    for name in ("panel_local_transform", "base_world_transform", "instance_world_transform"):
        if not _transforms_close(before[name], after[name], tolerance):
            failures.append(name.upper() + "_CHANGED")
    for name in ("world_min", "world_max"):
        if not _numbers_close(before["world_bounds"][name], after["world_bounds"][name], tolerance):
            failures.append(name.upper() + "_CHANGED")
    if failures:
        raise RuntimeError("PF_SKIPPED_SIDE_CHANGED|identity=%s|failures=%s|before=%s|after=%s" %
                           (identity, json.dumps(failures), json.dumps(before, sort_keys=True),
                            json.dumps(after, sort_keys=True)))
    return {"status": "UNCHANGED", "reason": SKIP_REASON,
            "assertions": ["mesh", "panel_local_transform", "base_world_transform",
                           "instance_world_transform", "world_bounds"]}


def ensure_fresh_import(existing_paths):
    existing = sorted(set(str(value) for value in existing_paths))
    if existing:
        raise RuntimeError("PF_REIMPORT_REFUSED|existing=" + json.dumps(existing))
    return True


def validate_measurement(before, after, config, identity=""):
    failures = []
    bottom_delta = float(after["panel_world_bottom_cm"]) - float(before["panel_world_bottom_cm"])
    if abs(bottom_delta) > float(config["panel_bottom_tolerance_cm"]):
        failures.append("PANEL_BOTTOM_CHANGED")
    if float(after["pole_world_bottom_cm"]) > (
            float(config["floor_z_cm"]) + float(config["pole_floor_tolerance_cm"])):
        failures.append("POLE_BOTTOM_ABOVE_FLOOR")
    inner_delta = float(after["inner_edge_cm"]) - float(before["inner_edge_cm"])
    if abs(inner_delta) > float(config["inner_edge_tolerance_cm"]):
        failures.append("INNER_EDGE_CHANGED")
    if failures:
        raise RuntimeError("PF_GEOMETRY_GATE_FAIL|identity=%s|failures=%s|before=%s|after=%s" %
                           (identity, json.dumps(failures), json.dumps(before, sort_keys=True),
                            json.dumps(after, sort_keys=True)))
    return {"panel_bottom_delta_cm": bottom_delta, "inner_edge_delta_cm": inner_delta,
            "pole_clearance_to_floor_cm": float(after["pole_world_bottom_cm"]) -
            float(config["floor_z_cm"])}


def validate_gap(before_gap, after_gap, config, identity=""):
    delta = float(after_gap) - float(before_gap)
    if abs(delta) > float(config["gap_tolerance_cm"]):
        raise RuntimeError("PF_GAP_CHANGED|identity=%s|before=%.9f|after=%.9f|tolerance=%.9f" %
                           (identity, float(before_gap), float(after_gap),
                            float(config["gap_tolerance_cm"])))
    return delta


def _unreal():
    import unreal
    return unreal


def census():
    unreal = _unreal()
    def names(packages):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in packages)
    return {"content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


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
        raise RuntimeError("DIRTY_AT_PF_START|census=" + json.dumps(current, sort_keys=True))
    return editor, world


def log_has(text):
    unreal = _unreal()
    import glob
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_log_dir())
    for path in sorted(glob.glob(os.path.join(root, "PussStage*.log"))):
        with open(path, encoding="utf-8", errors="replace") as handle:
            if str(text) in handle.read():
                return True
    return False


def marker(suffix):
    return "FLATV3_PF_" + str(suffix)


def saved_roots(config, current=None):
    roots = set(current or [])
    path = artifact(config, "apply")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            roots.update(json.load(handle).get("saved_roots", []))
    return sorted(roots)


def log_release(config, status, roots=None, reason=None, run=None, skipped=None):
    unreal = _unreal()
    release_run = str(run or config["run_id"])
    if skipped is None and release_run == str(config["run_id"]):
        preflight_path = artifact(config, "preflight")
        if os.path.isfile(preflight_path):
            with open(preflight_path, encoding="utf-8") as handle:
                skipped = json.load(handle).get("skipped_sides", [])
    roots = sorted(set(roots or ([] if release_run == config["import_run_id"]
                                  else saved_roots(config))))
    if reason:
        unreal.log_error("%s run=%s reason=%s census=%s" %
                         (marker("FAIL"), release_run, str(reason).replace("\n", "\\n"),
                          json.dumps(census(), separators=(",", ":"), sort_keys=True)))
    unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s skipped=%s census=%s" %
                (release_run, status, len(roots),
                 json.dumps(roots, separators=(",", ":")),
                 json.dumps(skipped or [], separators=(",", ":"), sort_keys=True),
                 json.dumps(census(), separators=(",", ":"), sort_keys=True)))
    return roots
