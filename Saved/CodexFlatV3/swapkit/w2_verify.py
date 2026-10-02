"""Read-only verification of the six applied W2 wave actor mesh swaps."""
import json
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import w2_common as c


def main(config_path=None):
    config = c.load_config(config_path)
    c.assert_context(config, clean=False)
    applied = c.read_report(config, "apply")
    if applied.get("status") != "PASS" or len(applied.get("rows", [])) != 6:
        raise RuntimeError("W2_APPLY_REPORT_FAIL")
    actors = c.wave_actors(config)
    widths = c.load_probe_widths(config)
    verified = []
    for row in applied["rows"]:
        actor = c.actor_by_path(actors, row["actor_path"])
        component = c.static_mesh_component(actor)
        actual_mesh = c.asset_path(c.component_mesh(component))
        if actual_mesh != row["new_mesh"]:
            raise RuntimeError("W2_VERIFY_MESH_FAIL|actor=%s|expected=%s|actual=%s" %
                               (row["actor_path"], row["new_mesh"], actual_mesh))
        c.assert_transform_close(actor.get_actor_transform(), row["world_transform"],
                                 tolerance=0.01, marker="W2_VERIFY_TRANSFORM_FAIL")
        actual_width = c.actor_bounds_width_cm(actor)
        expected_width = widths[row["key"]]
        if abs(actual_width - expected_width) > 1.0:
            raise RuntimeError("W2_WORLD_BOUNDS_WIDTH_FAIL|actor=%s|expected=%g|actual=%g|tolerance=1" %
                               (row["actor_path"], expected_width, actual_width))
        verified.append({
            "key": row["key"], "label": row["label"],
            "actor_path": row["actor_path"], "mesh": actual_mesh,
            "world_transform": c.transform_plain(actor.get_actor_transform()),
            "world_bounds_width_cm": actual_width,
            "expected_world_bounds_width_cm": expected_width,
            "width_error_cm": actual_width - expected_width,
        })
    current = c.census()
    ls_package = c.assert_ls_not_dirty(config, current)
    if current != c.CLEAN:
        raise RuntimeError("W2_VERIFY_CENSUS_FAIL|census=" + json.dumps(current, sort_keys=True))
    saved_roots = sorted(set(applied.get("saved_roots", [])))
    if saved_roots != [config["world"]]:
        raise RuntimeError("W2_APPLY_SAVED_ROOTS_FAIL|actual=" + json.dumps(saved_roots))
    report = {
        "run": config["run_id"], "mode": "w2_verify", "status": "PASS",
        "actor_count": len(verified), "rows": verified, "census": current,
        "ls_devscene_03_package": ls_package, "saved_roots": saved_roots,
    }
    path = c.write_report(config, "verify", report)
    unreal.log("%s run=%s actors=6 saved_count=%d saved_roots=%s census=%s report=%s" %
               (config["success_marker"], config["run_id"], len(saved_roots),
                json.dumps(saved_roots, separators=(",", ":")),
                json.dumps(current, separators=(",", ":"), sort_keys=True), path))
    return report


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
