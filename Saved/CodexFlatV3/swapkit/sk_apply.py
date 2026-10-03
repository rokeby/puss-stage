"""SK apply: repoint Front/Flap MIs to the saved _o2 textures."""
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
import traceback

import unreal

import sk_common as c


def main(config_path=None):
    cfg = c.config(config_path)
    run = cfg["apply_run_id"]
    changed = []
    saved = []
    report = {"status": "RUNNING", "run": run, "phase": "apply"}
    final_status = "FAIL"
    try:
        c.assert_context(clean=True)
        log_checks = {
            "import_complete": c.require_marker("FLATV3_SK_IMPORT_OK", cfg["import_run_id"]),
            "apply_run_unused": c.require_run_unused(run),
        }
        for destination, (_source, kind) in sorted(c.planned_textures(cfg).items()):
            c.verify_texture(c.load_asset(destination, unreal.Texture2D), kind)
        for row in cfg["rows"]:
            instance = c.load_asset(row["mi"], unreal.MaterialInstanceConstant)
            c.assert_mi(instance, row["old_textures"], row["mi"] + ":before")
            c.set_mi_textures(instance, row["new_textures"])
            changed.append((row, instance))
            c.assert_mi(instance, row["new_textures"], row["mi"] + ":after")
        expected_dirty = sorted({row["mi"] for row in cfg["rows"]})
        actual_dirty = c.census()
        if actual_dirty["maps"] or actual_dirty["content"] != expected_dirty:
            raise RuntimeError(
                "SK_APPLY_DIRTY_SET_FAIL|expected=%s|actual=%s"
                % (json.dumps(expected_dirty), json.dumps(actual_dirty, sort_keys=True))
            )
        saved = c.save_exact(expected_dirty)
        if c.census() != c.CLEAN:
            raise RuntimeError("SK_APPLY_DIRTY_AFTER_SAVE|" + json.dumps(c.census()))
        c.reload_exact(saved)
        fresh = {}
        for row in cfg["rows"]:
            instance = c.load_asset(row["mi"], unreal.MaterialInstanceConstant)
            fresh[row["mi"]] = c.assert_mi(
                instance, row["new_textures"], row["mi"] + ":fresh"
            )
        if c.census() != c.CLEAN:
            raise RuntimeError("SK_APPLY_DIRTY_AFTER_FRESH_READBACK|" + json.dumps(c.census()))
        report.update({"status": "PASS", "log_checks": log_checks,
                       "mi_readback_fresh": fresh, "saved_roots": saved,
                       "census": c.census(), "next_required_stage": "verify",
                       "terminal": False})
        path = c.write_report("sk_apply_%s.json" % run, report)
        unreal.log(
            "FLATV3_SK_APPLY_OK run=%s mis=%d saved_count=%d report=%s next=verify terminal=false"
            % (run, len(fresh), len(saved), path)
        )
        final_status = "OK"
        return report
    except Exception as exc:
        reverted = []
        revert_failure = None
        try:
            for row, instance in reversed(changed):
                c.set_mi_textures(instance, row["old_textures"])
                c.assert_mi(instance, row["old_textures"], row["mi"] + ":failure_revert")
                if row["mi"] in c.census()["content"]:
                    c.save_exact([row["mi"]])
                reverted.append(row["mi"])
        except Exception as revert_exc:
            revert_failure = str(revert_exc)
        report.update({"status": "FAIL", "reason": str(exc),
                       "traceback": traceback.format_exc(),
                       "mi_reverted": sorted(set(reverted)),
                       "revert_failure": revert_failure,
                       "saved_roots": saved, "census": c.census()})
        c.write_report("sk_apply_%s_FAILURE.json" % run, report)
        final_status = "REVERT_FAIL" if revert_failure else "FAIL_REVERTED"
        raise
    finally:
        # Apply and verify are one FV3SK run.  A successful apply deliberately
        # does not release; sk_verify.py is the terminal stage and owns the one
        # success release marker.  Failure still releases after the revert.
        if final_status != "OK":
            c.release(run, final_status, saved, "apply", report)


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
