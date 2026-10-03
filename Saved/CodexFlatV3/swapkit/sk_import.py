"""SK import: fresh-import and save only the 204 skin_v3 _o2 textures."""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
    if _fv3_here not in _fv3_sys.path:
        _fv3_sys.path.insert(0, _fv3_here)

import json
import os
import traceback

import unreal

import sk_common as c


def main(config_path=None):
    cfg = c.config(config_path)
    run = cfg["import_run_id"]
    saved = []
    tracker = None
    report = {"status": "RUNNING", "run": run, "phase": "import"}
    cleanup = {"status": "NOT_REQUIRED", "created": [], "deleted": []}
    final_status = "FAIL"
    try:
        c.assert_context(clean=True)
        log_checks = {
            "import_run_unused": c.require_run_unused(cfg["import_run_id"]),
            "apply_run_unused": c.require_run_unused(cfg["apply_run_id"]),
        }
        mapping = c.planned_textures(cfg)
        missing_sources = sorted(source for source, _kind in mapping.values()
                                 if not os.path.isfile(source))
        if missing_sources:
            raise RuntimeError("SK_SOURCE_MISSING|" + json.dumps(missing_sources))
        existing = sorted(path for path in mapping
                          if unreal.EditorAssetLibrary.does_asset_exist(path))
        if existing:
            raise RuntimeError("SK_FRESH_DESTINATION_EXISTS|" + json.dumps(existing))
        before = c.census()
        tracker = c.cleanup_mod.ImportRunTracker("SK", mapping.keys(), before, c.census)
        texture_readback = {}
        for destination, (source, kind) in sorted(mapping.items()):
            task = c.pilot.import_task(source, destination)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            tracker.observe_created()
            texture = c.load_asset(destination, unreal.Texture2D)
            texture_readback[destination] = c.texture_settings(texture, kind)
        actual_dirty = c.census()
        expected_dirty = sorted(mapping)
        if actual_dirty["maps"] or actual_dirty["content"] != expected_dirty:
            raise RuntimeError(
                "SK_IMPORT_DIRTY_SET_FAIL|expected=%s|actual=%s"
                % (json.dumps(expected_dirty), json.dumps(actual_dirty, sort_keys=True))
            )
        saved = c.save_exact(expected_dirty)
        if c.census() != c.CLEAN:
            raise RuntimeError("SK_IMPORT_DIRTY_AFTER_SAVE|" + json.dumps(c.census()))
        c.reload_exact(saved)
        fresh = {
            destination: c.verify_texture(c.load_asset(destination, unreal.Texture2D), kind)
            for destination, (_source, kind) in sorted(mapping.items())
        }
        if c.census() != c.CLEAN:
            raise RuntimeError("SK_IMPORT_DIRTY_AFTER_FRESH_READBACK|" + json.dumps(c.census()))
        report.update({
            "status": "PASS",
            "log_checks": log_checks,
            "cleanup_tracking": tracker.start_report(),
            "created_textures": sorted(tracker.created),
            "texture_readback_before_save": texture_readback,
            "texture_readback_fresh": fresh,
            "saved_roots": saved,
            "census": c.census(),
            "next_required_stage": "apply",
            "terminal": False,
        })
        path = c.write_report("sk_import_%s.json" % run, report)
        unreal.log(
            "FLATV3_SK_IMPORT_OK run=%s textures=%d saved_count=%d report=%s next=apply terminal=false"
            % (run, len(fresh), len(saved), path)
        )
        final_status = "OK"
        return report
    except Exception as exc:
        cleanup, cleanup_exc = c.cleanup_mod.cleanup_after_failure("SK", run, tracker, c.census)
        report.update({"status": "FAIL", "reason": str(exc),
                       "traceback": traceback.format_exc(), "cleanup": cleanup,
                       "saved_roots": saved, "census": c.census()})
        if cleanup_exc is not None:
            report["cleanup_failure"] = str(cleanup_exc)
            final_status = "CLEANUP_FAIL"
        else:
            final_status = "FAIL_CLEANED"
        c.write_report("sk_import_%s_FAILURE.json" % run, report)
        raise
    finally:
        c.release(run, final_status, saved, "import",
                  None if final_status == "OK" else report)


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))

