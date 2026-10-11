"""Read-only diagnostic for the most recent Job 191 seam-audit state."""
import builtins
import json

import unreal


state = getattr(builtins, "PUSS_JOB191_SEAM_AUDIT_STATE", None)
if state is None:
    raise RuntimeError("JOB191_SEAM_STATE_MISSING")
summary = {
    "run": state.get("run"),
    "status": state.get("status"),
    "phase": state.get("phase"),
    "errors": state.get("errors", []),
    "captured_frames": state.get("captured_frames", 0),
    "plan_counts": state.get("plan", {}).get("counts"),
}
unreal.log("JOB191_SEAM_STATE|" + json.dumps(summary, sort_keys=True))
