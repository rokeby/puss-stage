"""READ-ONLY fresh-run verification of the saved P05 FLOAT result."""
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
import importlib
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p05float_support as f
f = importlib.reload(f)
import p05float_verify as verifier
verifier = importlib.reload(verifier)


def main(config_path=None):
    config = f.load_config(config_path)
    source_run = str(globals().get("FLATV3_SWAP_RUN", config["run_id"]))
    verify_run = str(globals().get("FLATV3_VERIFY_RUN", config["saved_verify_run_id"]))
    try:
        if verify_run == source_run:
            raise RuntimeError("VERIFY_RUN_MUST_DIFFER_FROM_SOURCE_RUN")
        report = verifier.run_verify(config["_path"], source_run, verify_run, True, True)
        unreal.log("%s run=%s source_run=%s rows=%d placed_panels=%d census=%s report=%s" %
                   (f.marker(config, "VERIFY_SAVED_OK"), verify_run, source_run, report["rows"],
                    report["placed_panels"],
                    json.dumps(report["dirty_after"], separators=(",", ":"), sort_keys=True),
                    report["report_path"]))
        f.log_release(config, "OK", run=verify_run, artifact_run=source_run)
        return report
    except Exception as exc:
        reason = "verify_saved:" + str(exc)
        unreal.log_error("%s run=%s source_run=%s reason=%s census=%s traceback=%s" %
                         (f.marker(config, "VERIFY_SAVED_FAIL"), verify_run, source_run,
                          str(exc).replace("\n", "\\n"),
                          json.dumps(f.census(), separators=(",", ":"), sort_keys=True),
                          traceback.format_exc().replace("\n", "\\n")))
        f.log_release(config, "FAIL", reason=reason, run=verify_run, artifact_run=source_run)
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
