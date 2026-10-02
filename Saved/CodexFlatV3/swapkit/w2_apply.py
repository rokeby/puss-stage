"""Swap only the six Scene 3 wave StaticMeshComponent meshes and save the level."""
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
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import w2_common as c


def _restore_in_memory(changed, rows_by_path):
    for actor, component in reversed(changed):
        old_path = rows_by_path[str(actor.get_path_name())]["old_mesh"]
        old_mesh = unreal.EditorAssetLibrary.load_asset(old_path)
        if old_mesh is None:
            raise RuntimeError("W2_ROLLBACK_OLD_MESH_LOAD_FAIL|path=" + str(old_path))
        c.set_component_mesh(component, old_mesh)


def main(config_path=None):
    config = c.load_config(config_path)
    saved_roots = []
    changed = []
    rows_by_path = {}
    try:
        c.assert_context(config, clean=True)
        plan = c.read_report(config, "preflight")
        if plan.get("status") != "PASS" or len(plan.get("rows", [])) != 6:
            raise RuntimeError("W2_PREFLIGHT_REPORT_FAIL")
        actors = c.wave_actors(config)
        rows_by_path = {str(row["actor_path"]): row for row in plan["rows"]}
        for row in plan["rows"]:
            actor = c.actor_by_path(actors, row["actor_path"])
            if str(actor.get_actor_label()) != row["label"]:
                raise RuntimeError("W2_ACTOR_LABEL_CHANGED|path=" + row["actor_path"])
            component = c.static_mesh_component(actor)
            if c.asset_path(c.component_mesh(component)) != row["old_mesh"]:
                raise RuntimeError("W2_OLD_MESH_CHANGED|actor=" + row["actor_path"])
            c.assert_transform_close(actor.get_actor_transform(), row["world_transform"])
            mesh = unreal.EditorAssetLibrary.load_asset(row["new_mesh"])
            if not isinstance(mesh, unreal.StaticMesh):
                raise RuntimeError("W2_NEW_MESH_LOAD_FAIL|path=" + row["new_mesh"])
            c.set_component_mesh(component, mesh)
            changed.append((actor, component))
            if c.asset_path(c.component_mesh(component)) != row["new_mesh"]:
                raise RuntimeError("W2_MESH_SET_READBACK_FAIL|actor=" + row["actor_path"])
            c.assert_transform_close(actor.get_actor_transform(), row["world_transform"])

        # Fresh-import packages were saved and read back by w2_import. Therefore the
        # only dirty package at this later level-save boundary must be the current map.
        new_dirty = sorted(set(c.census()["content"]) & set(c.all_destination_paths(config)))
        if new_dirty:
            raise RuntimeError("W2_SAVED_IMPORT_PACKAGE_DIRTY|paths=" + json.dumps(new_dirty))
        save = c.save_current_level(config)
        saved_roots = save["saved_roots"]
        actors = c.wave_actors(config)
        readback = []
        for row in plan["rows"]:
            actor = c.actor_by_path(actors, row["actor_path"])
            component = c.static_mesh_component(actor)
            if c.asset_path(c.component_mesh(component)) != row["new_mesh"]:
                raise RuntimeError("W2_SAVED_MESH_READBACK_FAIL|actor=" + row["actor_path"])
            c.assert_transform_close(actor.get_actor_transform(), row["world_transform"])
            readback.append(c.actor_record(row["key"], actor))
        report = {
            "run": config["run_id"], "mode": "w2_apply", "status": "PASS",
            "rows": plan["rows"], "readback": readback,
            "dirty_before_save": save["before"], "dirty_after_save": save["after"],
            "saved_roots": saved_roots,
            "ls_devscene_03_package": c.assert_ls_not_dirty(config),
        }
        path = c.write_report(config, "apply", report)
        unreal.log("FLATV3_W2_APPLY_SAVED run=%s actors=6 saved_count=1 saved_roots=%s report=%s" %
                   (config["run_id"], json.dumps(saved_roots, separators=(",", ":")), path))
        return report
    except Exception as exc:
        original = traceback.format_exc()
        if changed:
            _restore_in_memory(changed, rows_by_path)
            # Persist the restored old-mesh state ONLY if the map is actually dirty;
            # a clean map means nothing reached the package (and saving would raise).
            if c.census()["maps"]:
                try:
                    save = c.save_current_level(config)
                    saved_roots = save["saved_roots"]
                except Exception as save_exc:
                    original += " | RESTORE_SAVE_FAIL: " + str(save_exc)
        c.write_report(config, "apply", {
            "run": config["run_id"], "mode": "w2_apply", "status": "FAIL",
            "reason": str(exc), "traceback": original, "saved_roots": saved_roots,
            "census": c.census(),
        }, failure=True)
        c.log_release(config, "FAIL_RESTORED" if changed else "FAIL",
                      saved_roots, reason=exc)
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
