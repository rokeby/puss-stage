"""Read-only verification of a configured saved swap under a fresh run id."""
import importlib
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as c
c = importlib.reload(c)
import verify as verifier
verifier = importlib.reload(verifier)


def main(config_path=None):
    config = c.load_config(config_path)
    swap_run = str(globals().get("FLATV3_SWAP_RUN", config["run_id"]))
    verify_run = str(globals().get("FLATV3_VERIFY_RUN", config["saved_verify_run_id"]))
    try:
        if verify_run == swap_run:
            raise RuntimeError("VERIFY_RUN_MUST_DIFFER_FROM_SWAP_RUN")
        report = verifier.run_verify(config["_path"], swap_run, verify_run, False, True)
        unreal.log("%s run=%s source_run=%s rows=%d census=%s" %
                   (c.marker(config, "VERIFY_SAVED_OK"), verify_run, swap_run, report["rows"],
                    json.dumps(report["dirty_after"], separators=(",", ":"), sort_keys=True)))
        c.log_release(config, "OK", [], run=verify_run, artifact_run=swap_run)
        return report
    except Exception as exc:
        unreal.log_error("%s run=%s source_run=%s reason=%s census=%s traceback=%s" %
                         (c.marker(config, "VERIFY_SAVED_FAIL"), verify_run, swap_run,
                          str(exc).replace("\n", "\\n"),
                          json.dumps(c.census(), separators=(",", ":"), sort_keys=True),
                          traceback.format_exc().replace("\n", "\\n")))
        c.log_release(config, "FAIL", [], "verify_saved:" + str(exc),
                      run=verify_run, artifact_run=swap_run)
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
