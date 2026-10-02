"""Restore the recorded old wave meshes, save the level only, keep _v2 assets."""
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import import_failure_cleanup as ifc
import w2_common as c


def main(config_path=None):
    config = c.load_config(config_path)
    saved_roots = []
    try:
        c.assert_context(config, clean=True)
        marker = "%s run=%s" % (config["success_marker"], config["run_id"])
        if not c.log_has(marker):
            raise RuntimeError("W2_VERIFY_MARKER_MISSING|marker=" + marker)
        applied = c.read_report(config, "apply")
        verified = c.read_report(config, "verify")
        if (applied.get("status") != "PASS" or verified.get("status") != "PASS" or
                len(applied.get("rows", [])) != 6):
            raise RuntimeError("W2_REVERT_INPUT_REPORT_FAIL")
        actors = c.wave_actors(config)
        restored = []
        for row in applied["rows"]:
            actor = c.actor_by_path(actors, row["actor_path"])
            component = c.static_mesh_component(actor)
            if c.asset_path(c.component_mesh(component)) != row["new_mesh"]:
                raise RuntimeError("W2_REVERT_EXPECTED_NEW_MESH_FAIL|actor=" + row["actor_path"])
            c.assert_transform_close(actor.get_actor_transform(), row["world_transform"])
            old_mesh = unreal.EditorAssetLibrary.load_asset(row["old_mesh"])
            if not isinstance(old_mesh, unreal.StaticMesh):
                raise RuntimeError("W2_REVERT_OLD_MESH_LOAD_FAIL|path=" + str(row["old_mesh"]))
            c.set_component_mesh(component, old_mesh)
            c.assert_transform_close(actor.get_actor_transform(), row["world_transform"])
            restored.append(row["actor_path"])
        save = c.save_current_level(config)
        saved_roots = save["saved_roots"]
        actors = c.wave_actors(config)
        readback = []
        for row in applied["rows"]:
            actor = c.actor_by_path(actors, row["actor_path"])
            component = c.static_mesh_component(actor)
            actual = c.asset_path(c.component_mesh(component))
            if actual != row["old_mesh"]:
                raise RuntimeError("W2_REVERT_READBACK_FAIL|actor=%s|expected=%s|actual=%s" %
                                   (row["actor_path"], row["old_mesh"], actual))
            c.assert_transform_close(actor.get_actor_transform(), row["world_transform"])
            readback.append(c.actor_record(row["key"], actor))
        missing = [path for path in c.all_destination_paths(config)
                   if not ifc.package_exists_on_disk(path) or
                   not unreal.EditorAssetLibrary.does_asset_exist(path)]
        if missing:
            raise RuntimeError("W2_REVERT_NEW_ASSET_MISSING|paths=" + json.dumps(missing))
        references = {}
        for key in c.PAIR_KEYS:
            path = c.mesh_path(config, key)
            refs = sorted(str(value).split(".", 1)[0] for value in
                          unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False))
            if refs:
                references[path] = refs
        if references:
            raise RuntimeError("W2_REVERT_NEW_MESH_REFERENCED|refs=" +
                               json.dumps(references, sort_keys=True))
        report = {
            "run": config["run_id"], "mode": "w2_revert", "status": "PASS",
            "restored_actor_paths": restored, "readback": readback,
            "dirty_before_save": save["before"], "dirty_after_save": save["after"],
            "saved_roots": saved_roots, "new_assets_retained": c.all_destination_paths(config),
            "new_mesh_referencers": references,
            "ls_devscene_03_package": c.assert_ls_not_dirty(config),
        }
        path = c.write_report(config, "revert", report)
        unreal.log("FLATV3_W2_REVERT_OK run=%s actors=6 saved_count=1 saved_roots=%s report=%s" %
                   (config["run_id"], json.dumps(saved_roots, separators=(",", ":")), path))
        c.log_release(config, "REVERTED", saved_roots)
        return report
    except Exception as exc:
        c.write_report(config, "revert", {
            "run": config["run_id"], "mode": "w2_revert", "status": "FAIL",
            "reason": str(exc), "traceback": traceback.format_exc(),
            "saved_roots": saved_roots, "census": c.census(),
        }, failure=True)
        c.log_release(config, "REVERT_FAIL", saved_roots, reason=exc)
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
