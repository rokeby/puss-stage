"""Offline +/- controls for the Job 100 pipeline gate."""
import swarm_pipeline as P


checks = []
checks.append(("no samples routes to read-only editor sampler",
               P.pipeline_state(False, False)["next_step"] == "EDITOR_READ_ONLY_HAND_SAMPLE"))
checks.append(("samples route to offline generator",
               P.pipeline_state(True, False)["next_step"] == "OFFLINE_CURVE_GENERATION"))
checks.append(("samples plus curves permit non-PIE DRY",
               P.pipeline_state(True, True)["ready_for_dry"]))
try:
    P.pipeline_state(False, True)
    checks.append(("orphan curves refuse", False))
except ValueError as exc:
    checks.append(("orphan curves refuse", "PROVENANCE" in str(exc)))

passed = sum(ok for _name, ok in checks)
for name, ok in checks:
    print(("PASS" if ok else "FAIL") + "|" + name)
print("S6_SWARM_PIPELINE_HARNESS|pass=%d|fail=%d|total=%d" %
      (passed, len(checks) - passed, len(checks)))
raise SystemExit(0 if passed == len(checks) else 1)

