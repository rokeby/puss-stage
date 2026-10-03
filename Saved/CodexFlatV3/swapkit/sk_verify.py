"""SK verify END: read back all 204 textures and 136 MIs, with no writes."""
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

import unreal
import traceback

import sk_common as c


def main(config_path=None):
    cfg = c.config(config_path)
    run = cfg["apply_run_id"]
    report = {"status": "RUNNING", "run": run, "phase": "verify"}
    status = "FAIL"
    try:
        c.assert_context(clean=True)
        log_checks = {
            "import_complete": c.require_marker("FLATV3_SK_IMPORT_OK", cfg["import_run_id"]),
            "apply_complete": c.require_marker("FLATV3_SK_APPLY_OK", run),
        }
        textures = {
            destination: c.verify_texture(c.load_asset(destination, unreal.Texture2D), kind)
            for destination, (_source, kind) in sorted(c.planned_textures(cfg).items())
        }
        instances = {}
        for row in cfg["rows"]:
            instance = c.load_asset(row["mi"], unreal.MaterialInstanceConstant)
            instances[row["mi"]] = c.assert_mi(
                instance, row["new_textures"], row["mi"] + ":verify"
            )
        if c.census() != c.CLEAN:
            raise RuntimeError("SK_VERIFY_DIRTY_AFTER_READBACK")
        report.update({"status": "PASS", "log_checks": log_checks,
                       "textures": textures, "mi_readback": instances,
                       "saved_roots": [], "census": c.census(), "terminal": True})
        path = c.write_report("sk_verify_%s.json" % run, report)
        unreal.log(
            "FLATV3_SK_OK run=%s textures=%d mis=%d report=%s terminal=true"
            % (run, len(textures), len(instances), path)
        )
        status = "OK"
        return report
    except Exception as exc:
        report.update({"status": "FAIL", "reason": str(exc),
                       "traceback": traceback.format_exc(), "census": c.census()})
        c.write_report("sk_verify_%s_FAILURE.json" % run, report)
        raise
    finally:
        c.release(run, status, [], "verify", None if status == "OK" else report)


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
