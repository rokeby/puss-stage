"""Shared guards for the P05 FLOAT pass.

This module intentionally contains no mutation or save calls.  The verifier can
import it without weakening the read-only boundary.
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
import hashlib
import json
import math
import os
import sys

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as shared


WORLD = shared.WORLD
SHOW = shared.SHOW
CLEAN = shared.CLEAN
SAVED_ROOTS = shared.SAVED_ROOTS
PROJECT = shared.PROJECT
BASE = HERE
SIDES = ("left", "right")


def project_path(value):
    value = str(value)
    return os.path.normpath(value if os.path.isabs(value) else os.path.join(PROJECT, value))


def load_config(explicit=None):
    path = explicit or globals().get("FLATV3_CONFIG") or os.environ.get("FLATV3_CONFIG")
    if not path and len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".json"):
        path = sys.argv[1]
    if not path:
        path = os.path.join(HERE, "run_p05float.json")
    path = project_path(path)
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    required = {
        "schema_version", "slot", "run_id", "saved_verify_run_id", "passage",
        "passage_label_prefix", "passage_actor_label_prefix", "expected_occurrence_count",
        "expected_row_index_start", "expected_row_index_end", "required_previous_markers",
        "target_bottom_min_cm", "target_bottom_span_cm", "max_world_top_cm",
        "bottom_tolerance_cm", "backup_path", "backup_files", "success_marker",
        "verify_token",
    }
    missing = sorted(required - set(config))
    if missing:
        raise RuntimeError("CONFIG_KEYS_MISSING|" + json.dumps(missing))
    if int(config["schema_version"]) != 1:
        raise RuntimeError("CONFIG_SCHEMA_FAIL|actual=" + str(config["schema_version"]))
    if (config["slot"] != "F" or config["passage"] != "P05" or
            config["passage_label_prefix"] != "P05 Wing " or
            int(config["expected_occurrence_count"]) != 93 or
            int(config["expected_row_index_start"]) != 122 or
            int(config["expected_row_index_end"]) != 214):
        raise RuntimeError("CONFIG_P05FLOAT_SCOPE_FAIL")
    if config["run_id"] != "FV3F-20261002-01" or config["saved_verify_run_id"] != "FV3FV-20261002-01":
        raise RuntimeError("CONFIG_RUN_ID_FAIL")
    if config["success_marker"] != "FLATV3_F_OK":
        raise RuntimeError("CONFIG_SUCCESS_MARKER_FAIL")
    if sorted(config["required_previous_markers"]) != ["FLATV3_C2_OK", "FLATV3_C_OK"]:
        raise RuntimeError("CONFIG_PRECONDITION_MARKERS_FAIL")
    numbers = ("target_bottom_min_cm", "target_bottom_span_cm", "max_world_top_cm",
               "bottom_tolerance_cm")
    for name in numbers:
        value = float(config[name])
        if not math.isfinite(value):
            raise RuntimeError("CONFIG_NONFINITE|field=" + name)
        config[name] = value
    if (config["target_bottom_min_cm"] != 150.0 or
            config["target_bottom_span_cm"] != 300.0 or
            config["max_world_top_cm"] != 1100.0 or
            config["bottom_tolerance_cm"] != 1.0):
        raise RuntimeError("CONFIG_HEIGHT_CONTRACT_FAIL")
    if config["backup_files"] != [
            "DA_InfinityStage_V1Show.uasset", "L_InfinityStage_V1VerticalSlice.umap"]:
        raise RuntimeError("CONFIG_BACKUP_FILES_FAIL")
    sources = config.get("backup_sources", {})
    if sorted(sources) != sorted(config["backup_files"]):
        raise RuntimeError("CONFIG_BACKUP_SOURCES_FAIL")
    config = dict(config)
    config["_path"] = path
    config["backup_path"] = project_path(config["backup_path"])
    config["backup_sources"] = {name: project_path(value) for name, value in sources.items()}
    return config


def marker(config, suffix):
    return "FLATV3_%s_%s" % (config["slot"], suffix)


def artifact(config, phase, run=None, failure=False):
    return os.path.join(BASE, "p05float_%s_%s%s.json" % (
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


def census():
    return shared.census()


def assert_context(config, clean=True):
    return shared.assert_context(config, clean=clean)


def log_has(text):
    return shared.log_has(text)


def asset_path(value):
    return shared.asset_path(value)


def frame_value(value):
    return shared.frame_value(value)


def transform_plain(value):
    return shared.transform_plain(value)


def close_transform(actual, expected, tolerance=0.001):
    return shared.close_transform(actual, expected, tolerance=tolerance)


def cue_guid(cue):
    return shared.cue_guid(cue)


def passage_actor(config, show):
    return shared.passage_actor(config, show)


def exported(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [exported(item) for item in value]
    if hasattr(value, "export_text"):
        return value.export_text()
    if hasattr(value, "to_string"):
        return value.to_string()
    if hasattr(value, "value") and isinstance(value.value, (bool, int, float, str)):
        return value.value
    if hasattr(value, "get_path_name"):
        return value.get_path_name()
    # The final branch is used by the offline Unreal stub only.  Real Unreal
    # structs expose export_text(), which is the saved/read-back fingerprint.
    if hasattr(value, "props"):
        return {str(key): exported(item) for key, item in sorted(value.props.items())}
    return str(value)


def panel_plain(panel):
    return {
        "mesh": asset_path(panel.get_editor_property("mesh")),
        "material_overrides": [asset_path(value) for value in panel.get_editor_property("material_overrides")],
        "local_transform": transform_plain(panel.get_editor_property("local_transform")),
        "facing_policy": str(panel.get_editor_property("facing_policy")),
        "flip_image_horizontally": bool(panel.get_editor_property("flip_image_horizontally")),
        "cast_shadow": bool(panel.get_editor_property("cast_shadow")),
        "visible_in_main_pass": bool(panel.get_editor_property("visible_in_main_pass")),
        "collision": exported(panel.get_editor_property("collision")),
    }


def pair_invariants(pair):
    return {
        "occurrence_guid": exported(pair.get_editor_property("occurrence_guid")),
        "has_top": bool(pair.get_editor_property("has_top")),
        "interval_to_next": frame_value(pair.get_editor_property("interval_to_next")),
        "gap_to_next_cm": float(pair.get_editor_property("gap_to_next_cm")),
        "occurrence_offset": transform_plain(pair.get_editor_property("occurrence_offset")),
        "mechanism": exported(pair.get_editor_property("mechanism")),
        "mute_mechanism_sound": bool(pair.get_editor_property("mute_mechanism_sound")),
        "attachments": exported(list(pair.get_editor_property("attachments"))),
        "local_override_mask": int(pair.get_editor_property("local_override_mask")),
    }


def cue_invariants(cue):
    return {
        "type": str(cue.get_editor_property("type")),
        "label": str(cue.get_editor_property("label")),
        "enabled": bool(cue.get_editor_property("enabled")),
        "tags": [str(value) for value in cue.get_editor_property("tags")],
        "scene": exported(cue.get_editor_property("scene")),
    }


def occurrence_row(index, cue):
    pair = cue.get_editor_property("wing_pair")
    return {
        "cue_index": int(index),
        "cue_guid": cue_guid(cue),
        "cue_label": str(cue.get_editor_property("label")),
        "left": panel_plain(pair.get_editor_property("left")),
        "right": panel_plain(pair.get_editor_property("right")),
        "top": panel_plain(pair.get_editor_property("top")),
        "pair_invariants": pair_invariants(pair),
        "cue_invariants": cue_invariants(cue),
    }


def assert_identity(cue, index, record, config, error="P05FLOAT_IDENTITY_FAIL"):
    actual_guid = cue_guid(cue)
    actual_label = str(cue.get_editor_property("label"))
    if (int(index) != int(record["cue_index"]) or actual_guid != record["cue_guid"] or
            actual_label != record["cue_label"] or
            not actual_label.startswith(config["passage_label_prefix"])):
        raise RuntimeError(
            "%s|expected_index=%s|actual_index=%s|expected_guid=%s|actual_guid=%s|"
            "expected_label=%s|actual_label=%s" %
            (error, record["cue_index"], index, record["cue_guid"], actual_guid,
             record["cue_label"], actual_label))


def panel_matches(actual, expected, tolerance=0.001):
    scalar_fields = ("mesh", "material_overrides", "facing_policy",
                     "flip_image_horizontally", "cast_shadow", "visible_in_main_pass", "collision")
    return (all(actual[name] == expected[name] for name in scalar_fields) and
            close_transform(actual["local_transform"], expected["local_transform"], tolerance))


def expected_panel(original, expected_z):
    result = json.loads(json.dumps(original))
    result["local_transform"]["location"][2] = float(expected_z)
    return result


def assert_row_state(cue, index, record, config, z_by_side, error="P05FLOAT_STATE_FAIL"):
    assert_identity(cue, index, record, config, error + "_IDENTITY")
    if cue_invariants(cue) != record["cue_invariants"]:
        raise RuntimeError(error + "_CUE_FIELDS|index=%d" % index)
    pair = cue.get_editor_property("wing_pair")
    if pair_invariants(pair) != record["pair_invariants"]:
        raise RuntimeError(error + "_PAIR_FIELDS|index=%d" % index)
    actual_top = panel_plain(pair.get_editor_property("top"))
    if not panel_matches(actual_top, record["top"]):
        raise RuntimeError(error + "_TOP_CHANGED|index=%d" % index)
    for side in SIDES:
        actual = panel_plain(pair.get_editor_property(side))
        expected = expected_panel(record[side], z_by_side[side])
        if not panel_matches(actual, expected):
            old_xy = record[side]["local_transform"]["location"][:2]
            actual_xy = actual["local_transform"]["location"][:2]
            suffix = "_LOCAL_XY_CHANGED" if actual_xy != old_xy else "_PANEL_FIELDS"
            raise RuntimeError("%s%s|index=%d|side=%s|actual=%s" %
                               (error, suffix, index, side, json.dumps(actual, sort_keys=True)))
    return pair


def assert_row_non_z_state(cue, index, record, config, error="P05FLOAT_NON_Z_STATE_FAIL"):
    """Accept any finite side-panel Z, but require every other field unchanged."""
    assert_identity(cue, index, record, config, error + "_IDENTITY")
    if cue_invariants(cue) != record["cue_invariants"]:
        raise RuntimeError(error + "_CUE_FIELDS|index=%d" % index)
    pair = cue.get_editor_property("wing_pair")
    if pair_invariants(pair) != record["pair_invariants"]:
        raise RuntimeError(error + "_PAIR_FIELDS|index=%d" % index)
    if not panel_matches(panel_plain(pair.get_editor_property("top")), record["top"]):
        raise RuntimeError(error + "_TOP_CHANGED|index=%d" % index)
    for side in SIDES:
        actual = panel_plain(pair.get_editor_property(side))
        actual_z = float(actual["local_transform"]["location"][2])
        if not math.isfinite(actual_z):
            raise RuntimeError(error + "_NONFINITE_Z|index=%d|side=%s" % (index, side))
        normalized = expected_panel(actual, record[side]["local_transform"]["location"][2])
        if not panel_matches(normalized, record[side]):
            old_xy = record[side]["local_transform"]["location"][:2]
            actual_xy = actual["local_transform"]["location"][:2]
            suffix = "_LOCAL_XY_CHANGED" if actual_xy != old_xy else "_PANEL_FIELDS"
            raise RuntimeError("%s%s|index=%d|side=%s|actual=%s" %
                               (error, suffix, index, side, json.dumps(actual, sort_keys=True)))
    return pair


def target_rows(config, show):
    cues = list(show.get_editor_property("cues"))
    rows = [(index, cue) for index, cue in enumerate(cues)
            if str(cue.get_editor_property("label")).startswith(config["passage_label_prefix"])]
    expected_indices = list(range(int(config["expected_row_index_start"]),
                                  int(config["expected_row_index_end"]) + 1))
    actual_indices = [index for index, _ in rows]
    if len(rows) != int(config["expected_occurrence_count"]):
        raise RuntimeError("P05FLOAT_OCCURRENCE_COUNT_FAIL|expected=%d|actual=%d" %
                           (config["expected_occurrence_count"], len(rows)))
    if actual_indices != expected_indices:
        raise RuntimeError("P05FLOAT_INDEX_RANGE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(expected_indices), json.dumps(actual_indices)))
    guids = [cue_guid(cue) for _, cue in rows]
    if any(not value for value in guids) or len(set(guids)) != len(guids):
        raise RuntimeError("P05FLOAT_GUID_IDENTITY_FAIL")
    return rows


def refs_for(actor, guid):
    result = {side: [] for side in SIDES}
    for ref in actor.get_editor_property("materialized_panels"):
        if ref.get_editor_property("cue_guid").to_string() != guid:
            continue
        side_text = str(ref.get_editor_property("side")).upper()
        if "LEFT" in side_text:
            result["left"].append(ref)
        elif "RIGHT" in side_text:
            result["right"].append(ref)
    if any(len(result[side]) != 1 for side in SIDES):
        raise RuntimeError("P05FLOAT_PLACED_REF_SCOPE_FAIL|guid=%s|counts=%s" %
                           (guid, json.dumps({side: len(result[side]) for side in SIDES})))
    return {side: result[side][0] for side in SIDES}


def box_points(box):
    return [unreal.Vector(x, y, z) for x in (box.min.x, box.max.x)
            for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]


def instance_transform(component, instance_index):
    value = component.get_instance_transform(int(instance_index), True)
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], bool):
        if not value[0]:
            raise RuntimeError("P05FLOAT_INSTANCE_TRANSFORM_FAIL|index=%s" % instance_index)
        value = value[1]
    return value


def world_bounds(ref):
    component = ref.get_editor_property("component")
    mesh = component.get_editor_property("static_mesh")
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("P05FLOAT_PLACED_MESH_FAIL")
    index = int(ref.get_editor_property("instance_index"))
    transform = instance_transform(component, index)
    points = [transform.transform_location(point) for point in box_points(mesh.get_bounding_box())]
    minimum = [min(getattr(point, axis) for point in points) for axis in "xyz"]
    maximum = [max(getattr(point, axis) for point in points) for axis in "xyz"]
    return {
        "mesh": asset_path(mesh), "instance_index": index,
        "world_min": [float(value) for value in minimum],
        "world_max": [float(value) for value in maximum],
    }


def stable_unit(cue_guid_value, side):
    side = str(side).lower()
    if side not in SIDES:
        raise RuntimeError("P05FLOAT_HASH_SIDE_FAIL|side=" + side)
    digest = hashlib.sha256((str(cue_guid_value) + side).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) / float(2 ** 64)


def target_height(config, cue_guid_value, side):
    return (config["target_bottom_min_cm"] +
            config["target_bottom_span_cm"] * stable_unit(cue_guid_value, side))


def planned_side(config, record, side, bounds):
    bottom = float(bounds["world_min"][2])
    top = float(bounds["world_max"][2])
    height = target_height(config, record["cue_guid"], side)
    lift = height - bottom
    new_top = top + lift
    if new_top > config["max_world_top_cm"] + 0.000001:
        raise RuntimeError(
            "P05FLOAT_WORLD_TOP_LIMIT_FAIL|index=%d|guid=%s|side=%s|new_top=%.9f|limit=%.9f" %
            (record["cue_index"], record["cue_guid"], side, new_top,
             config["max_world_top_cm"]))
    old_z = float(record[side]["local_transform"]["location"][2])
    return {
        "side": side, "hash_input": record["cue_guid"] + side,
        "u": stable_unit(record["cue_guid"], side),
        "old_local_z_cm": old_z, "measured_world_bottom_cm": bottom,
        "measured_world_top_cm": top, "target_world_bottom_cm": height,
        "lift_cm": lift, "new_local_z_cm": old_z + lift,
        "new_world_top_cm": new_top, "measured_world_min": bounds["world_min"],
        "measured_world_max": bounds["world_max"], "mesh": bounds["mesh"],
        "instance_index": bounds["instance_index"],
    }


def plan_from_measurements(config, preflight_rows, measurements):
    plan = []
    for record in preflight_rows:
        guid = record["cue_guid"]
        if guid not in measurements:
            raise RuntimeError("P05FLOAT_MEASUREMENT_MISSING|guid=" + guid)
        sides = {side: planned_side(config, record, side, measurements[guid][side])
                 for side in SIDES}
        plan.append({"cue_index": record["cue_index"], "cue_guid": guid,
                     "cue_label": record["cue_label"], "sides": sides})
    return plan


def saved_roots_for_run(config, run, current=None):
    roots = set(current or [])
    for phase in ("apply", "revert"):
        path = artifact(config, phase, run=run)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                roots.update(json.load(handle).get("saved_roots", []))
    return sorted(roots)


def log_release(config, status, saved_roots=None, reason=None, run=None, artifact_run=None):
    release_run = run or config["run_id"]
    roots = saved_roots_for_run(config, artifact_run or config["run_id"], saved_roots)
    current = census()
    if reason is not None:
        unreal.log_error("%s run=%s reason=%s census=%s" %
                         (marker(config, "FAIL"), release_run,
                          str(reason).replace("\n", "\\n"),
                          json.dumps(current, separators=(",", ":"), sort_keys=True)))
    unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s census=%s" %
               (release_run, status, len(roots),
                json.dumps(roots, separators=(",", ":")),
                json.dumps(current, separators=(",", ":"), sort_keys=True)))
    return roots
