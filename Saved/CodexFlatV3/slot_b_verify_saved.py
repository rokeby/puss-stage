"""Read-only verification of a previously saved P04 swap under a fresh run id."""
import importlib
import json
import os
import sys
import traceback
import unreal

BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3"))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
import slot_b_common as c
c = importlib.reload(c)
import slot_b_verify as verifier
verifier = importlib.reload(verifier)

DEFAULT_SWAP_RUN = "FV3B-20261002-03"
DEFAULT_VERIFY_RUN = "FV3BV-20261002-01"


def main():
    swap_run = str(globals().get("FLATV3_SWAP_RUN", DEFAULT_SWAP_RUN))
    verify_run = str(globals().get("FLATV3_VERIFY_RUN", DEFAULT_VERIFY_RUN))
    try:
        if verify_run == swap_run:
            raise RuntimeError("VERIFY_RUN_MUST_DIFFER_FROM_SWAP_RUN")
        report = verifier.run_verify(swap_run, verify_run, emit_report=False)
        unreal.log("FLATV3_B_VERIFY_SAVED_OK run=%s source_run=%s rows=%d census=%s" %
                   (verify_run, swap_run, report["rows"],
                    json.dumps(report["dirty_after"], separators=(",", ":"), sort_keys=True)))
        c.log_release("OK", [], run=verify_run, artifact_run=swap_run)
    except Exception as exc:
        unreal.log_error("FLATV3_B_VERIFY_SAVED_FAIL run=%s source_run=%s reason=%s census=%s traceback=%s" %
                         (verify_run, swap_run, str(exc).replace("\n", "\\n"),
                          json.dumps(c.census(), separators=(",", ":"), sort_keys=True),
                          traceback.format_exc().replace("\n", "\\n")))
        c.log_release("FAIL", [], "verify_saved:" + str(exc),
                      run=verify_run, artifact_run=swap_run)


if __name__ == "__main__":
    main()
