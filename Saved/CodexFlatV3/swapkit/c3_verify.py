"""Final READ-ONLY C3 Show and placed-instance verification; releases the slot."""
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
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
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
import c3_compare as compare
import common as c
c = importlib.reload(c)
import p05float_support as f
f = importlib.reload(f)
import verify as v
v = importlib.reload(v)


def library_entries(show):
    path = c.asset_path(show.get_editor_property("wing_library"))
    library = unreal.EditorAssetLibrary.load_asset(path) if path else None
    if library is None:
        raise RuntimeError("C3_WING_LIBRARY_LOAD_FAIL|path=" + str(path))
    result = {}
    for entry in library.get_editor_property("entries"):
        mesh = c.asset_path(entry.get_editor_property("mesh"))
        if mesh:
            result[mesh] = entry
    return result


def expected_rows(preflight, plan):
    result = {int(row["cue_index"]): row for row in preflight["rows"]}
    for row in plan["rows"]:
        updated = json.loads(json.dumps(result[int(row["cue_index"])]))
        updated["left"] = row["new_left"]
        result[int(row["cue_index"])] = updated
    return result


def run(config_path=None):
    config = s.load_config(config_path)
    s.assert_context(config, clean=True)
    preflight = s.read_json(config, "preflight")
    plan = s.read_json(config, "dry_run")
    apply = s.read_json(config, "apply")
    if (preflight.get("status") != "PASS" or plan.get("status") != "PASS" or
            apply.get("status") != "PASS" or apply.get("saved_roots") != s.SAVED_ROOTS):
        raise RuntimeError("C3_VERIFY_INPUT_NOT_PASS")
    if not s.log_has("FLATV3_V_TEST_QUEUED run=" + config["run_id"]):
        raise RuntimeError("C3_SAVED_MASTER_TEST_NOT_QUEUED")
    if not s.log_has(config["verify_token"]):
        raise RuntimeError("C3_VERIFY_TOKEN_NOT_FOUND|" + config["verify_token"])
    show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")
    cues = list(show.get_editor_property("cues"))
    f.target_rows(config, show)
    expected = expected_rows(preflight, plan)
    for index in range(122, 215):
        actual = f.occurrence_row(index, cues[index])
        if not compare.occurrence_matches(actual, expected[index]):
            raise RuntimeError("C3_VERIFY_SHOW_ROW_FAIL|index=%d|guid=%s" %
                               (index, expected[index]["cue_guid"]))
    actor = f.passage_actor(config, show)
    library_by_mesh = library_entries(show)
    placed = []
    gap_rows = []
    for row in plan["rows"]:
        index = int(row["cue_index"])
        cue = cues[index]
        pair = cue.get_editor_property("wing_pair")
        refs = f.refs_for(actor, row["cue_guid"])
        frame, frame_source = v.pair_frame(
            actor, cue, refs, pair,
            {"cue_label": row["cue_label"], "changed_sides": ["left"]},
            library_by_mesh)
        left_ref = refs["left"]
        left_component = left_ref.get_editor_property("component")
        left_mesh = left_component.get_editor_property("static_mesh")
        if c.asset_path(left_mesh) != config["new_left_mesh"]:
            raise RuntimeError("C3_PLACED_MESH_FAIL|index=%d|actual=%s" %
                               (index, c.asset_path(left_mesh)))
        left_transform = f.instance_transform(
            left_component, int(left_ref.get_editor_property("instance_index")))
        left_pair_bounds = v.bounds_in_frame(left_mesh, left_transform, frame)
        left_world = f.world_bounds(left_ref)
        actual_inner = float(left_pair_bounds["max"][1])
        expected_inner = float(row["placement"]["old_inner_edge_cm"])
        if (abs(actual_inner - expected_inner) > config["inner_edge_tolerance_cm"] or
                actual_inner > expected_inner + 0.000001):
            raise RuntimeError("C3_VERIFY_INNER_EDGE_FAIL|index=%d|expected=%.9f|actual=%.9f" %
                               (index, expected_inner, actual_inner))
        expected_height = s.target_height(config, row["cue_guid"], "left")
        actual_bottom = float(left_world["world_min"][2])
        s.assert_bottom(actual_bottom, expected_height,
                        config["bottom_tolerance_cm"], row["cue_guid"])
        s.assert_bottom(actual_bottom, row["height"]["current_world_bottom_cm"],
                        config["bottom_tolerance_cm"], row["cue_guid"] + ":preserved")

        right_ref = refs["right"]
        right_component = right_ref.get_editor_property("component")
        right_mesh = right_component.get_editor_property("static_mesh")
        if c.asset_path(right_mesh) != row["right_unchanged"]["mesh"]:
            raise RuntimeError("C3_VERIFY_RIGHT_MESH_CHANGED|index=%d" % index)
        right_transform = f.instance_transform(
            right_component, int(right_ref.get_editor_property("instance_index")))
        right_pair_bounds = v.bounds_in_frame(right_mesh, right_transform, frame)
        gap_old = float(row["centre_gap"]["gap_old_cm"])
        gap_new = s.centre_gap(actual_inner, float(right_pair_bounds["min"][1]))
        gap_rows.append({"cue_index": index, "cue_guid": row["cue_guid"],
                         "cue_label": row["cue_label"], "gap_old_cm": gap_old,
                         "gap_new_cm": gap_new})

        pair_minus_x = frame.rotation.rotate_vector(unreal.Vector(-1.0, 0.0, 0.0))
        placed_front = left_transform.rotation.rotate_vector(unreal.Vector(-1.0, 0.0, 0.0))
        front_dot = float(placed_front.dot(pair_minus_x))
        if front_dot < 0.99:
            raise RuntimeError("C3_VERIFY_FACING_FAIL|index=%d|dot=%.9f" %
                               (index, front_dot))
        placed.append({
            "cue_index": index, "cue_guid": row["cue_guid"],
            "cue_label": row["cue_label"], "mesh": c.asset_path(left_mesh),
            "instance_index": left_world["instance_index"],
            "inner_edge_pair_cm": actual_inner, "expected_inner_edge_cm": expected_inner,
            "world_bottom_cm": actual_bottom, "H_cm": expected_height,
            "world_min": left_world["world_min"], "world_max": left_world["world_max"],
            "front_dot_pair_minus_x": front_dot, "pair_frame_source": frame_source,
        })
    s.validate_target_rows(placed, config["targets"], config["target_count"])
    gap_gate = s.minimum_gap_gate(gap_rows, config["gap_tolerance_cm"])
    end = s.census()
    if end != s.CLEAN:
        raise RuntimeError("C3_VERIFY_DIRTIED_EDITOR|" + json.dumps(end, sort_keys=True))
    roots = s.saved_roots(config)
    if roots != s.SAVED_ROOTS:
        raise RuntimeError("C3_VERIFY_SAVED_ROOTS_FAIL|" + json.dumps(roots))
    report = {
        "run": config["run_id"], "mode": "verify", "status": "PASS",
        "rows": 12, "placed": placed, "centre_gap_gate": gap_gate,
        "narrower_cases": plan["narrower_cases"], "verify_token": config["verify_token"],
        "saved_roots": roots, "dirty_after": end,
    }
    path = s.write_json(config, "verify", report)
    unreal.log("%s run=%s rows=12 left=12 right=0 top=0 saved_count=%d saved_roots=%s narrower=%d census=%s report=%s" %
               (config["success_marker"], config["run_id"], len(roots),
                json.dumps(roots, separators=(",", ":")), len(plan["narrower_cases"]),
                json.dumps(end, separators=(",", ":"), sort_keys=True), path))
    s.log_release(config, "OK", roots)
    return report


def main(config_path=None):
    config = s.load_config(config_path)
    try:
        return run(config["_path"])
    except Exception as exc:
        reason = "verify:" + str(exc)
        s.write_json(config, "verify", {
            "run": config["run_id"], "mode": "verify", "status": "FAIL",
            "reason": reason, "traceback": traceback.format_exc(),
            "census": s.census()}, failure=True)
        s.log_release(config, "FAIL", reason=reason)
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
