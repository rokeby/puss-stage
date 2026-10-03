"""SK revert: repoint the 136 MIs to old textures; retain all _o2 textures."""
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

import unreal

import sk_common as c


def main(config_path=None):
    cfg = c.config(config_path)
    run = cfg.get("revert_run_id", "FV3SKR-20261003-01")
    c.assert_context(clean=True)
    c.require_marker("FLATV3_SK_APPLY_OK", cfg["apply_run_id"])
    c.require_run_unused(run)
    changed = []
    for row in cfg["rows"]:
        instance = c.load_asset(row["mi"], unreal.MaterialInstanceConstant)
        c.assert_mi(instance, row["new_textures"], row["mi"] + ":revert_before")
        c.set_mi_textures(instance, row["old_textures"])
        c.assert_mi(instance, row["old_textures"], row["mi"] + ":revert_after")
        changed.append(row["mi"])
    expected = sorted(set(changed))
    if c.census() != {"content": expected, "maps": []}:
        raise RuntimeError("SK_REVERT_DIRTY_SET_FAIL|" + json.dumps(c.census()))
    saved = c.save_exact(expected)
    # NO reload: the MIs are referenced by placed meshes in the open level (W-04 failure class).
    for row in cfg["rows"]:
        c.assert_mi(c.load_asset(row["mi"], unreal.MaterialInstanceConstant),
                    row["old_textures"], row["mi"] + ":revert_fresh")
    if c.census() != c.CLEAN:
        raise RuntimeError("SK_REVERT_DIRTY_AFTER")
    report = {"status": "PASS", "run": run, "phase": "revert",
              "saved_roots": saved, "o2_textures_retained": True,
              "census": c.census()}
    path = c.write_report("sk_revert_%s.json" % run, report)
    unreal.log("FLATV3_SK_REVERT_OK run=%s mis=%d o2_textures_retained=true report=%s"
               % (run, len(saved), path))
    c.release(run, "OK", saved, "revert")
    return report


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))

