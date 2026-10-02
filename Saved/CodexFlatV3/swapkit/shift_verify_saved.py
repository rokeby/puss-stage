"""Read-only verification of a saved inner shift under a fresh run id."""
import importlib
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import shift_common as s
s = importlib.reload(s)
import shift_verify as verifier
verifier = importlib.reload(verifier)


def main(config_path=None):
    config = s.load_config(config_path)
    source_run = str(globals().get("FLATV3_SHIFT_RUN", config["run_id"]))
    verify_run = str(globals().get("FLATV3_VERIFY_RUN", config["saved_verify_run_id"]))
    try:
        if verify_run == source_run:
            raise RuntimeError("SHIFT_VERIFY_RUN_MUST_DIFFER")
        report = verifier.run_verify(
            config["_path"], source_run, verify_run, require_token=True, emit_report=True)
        unreal.log("%s run=%s source_run=%s passage=%s rows=%d census=%s report=%s" %
                   (s.marker(config, "VERIFY_SAVED_OK"), verify_run, source_run,
                    config["passage"], report["rows"],
                    json.dumps(s.census(), separators=(",", ":"), sort_keys=True),
                    report["report_path"]))
        s.log_release(config, "OK", run=verify_run, artifact_run=source_run)
        return report
    except Exception as exc:
        reason = "verify_saved:" + str(exc)
        s.log_release(config, "FAIL", reason=reason, run=verify_run,
                      artifact_run=source_run)
        unreal.log_error("%s run=%s source_run=%s reason=%s traceback=%s" %
                         (s.marker(config, "VERIFY_SAVED_FAIL"), verify_run, source_run,
                          str(exc).replace("\n", "\\n"),
                          traceback.format_exc().replace("\n", "\\n")))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
