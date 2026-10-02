"""Finalize Slot B exactly once after the exact test result is present in the log."""
import json
import importlib
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
import slot_b_revert

TEST = "InfinityStage.Editor.SavedMasterMatchesShow"
report = {"run": c.RUN, "mode": "finalize"}
try:
    c.assert_context(clean=True)
    verify = c.read_json("slot_b_verify_%s.json" % c.RUN)
    captures = c.read_json("slot_b_captures_%s.json" % c.RUN)
    apply = c.read_json("slot_b_apply_%s.json" % c.RUN)
    if any(value.get("status") != "PASS" for value in (verify, captures, apply)):
        raise RuntimeError("PRIOR_REPORT_NOT_PASS")
    log_path = os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_log_dir()), "PussStage.log")
    with open(log_path, encoding="utf-8", errors="replace") as handle:
        log_text = handle.read()
    queued = "FLATV3_B_AUTOMATION_QUEUED run=%s test=%s alone=true" % (c.RUN, TEST)
    success = "Test Completed. Result={Success} Name={SavedMasterMatchesShow} Path={%s}" % TEST
    failure = "Test Completed. Result={Fail} Name={SavedMasterMatchesShow} Path={%s}" % TEST
    queued_at = log_text.rfind(queued)
    success_at = log_text.find(success, queued_at) if queued_at >= 0 else -1
    failure_at = log_text.find(failure, queued_at) if queued_at >= 0 else -1
    if queued_at < 0:
        raise RuntimeError("AUTOMATION_QUEUE_MARKER_MISSING")
    if failure_at >= 0 and (success_at < 0 or failure_at < success_at):
        raise RuntimeError("SAVED_MASTER_TEST_FAILED")
    if success_at < 0:
        raise RuntimeError("SAVED_MASTER_TEST_RESULT_MISSING")
    if c.census() != {"content": [], "maps": []}:
        raise RuntimeError("FINAL_DIRTY|" + json.dumps(c.census(), sort_keys=True))

    final = {"run": c.RUN, "status": "PASS", "p04_occurrences": verify["rows"],
             "placed_panels": len(verify["placed_panels"]),
             "movement_sample_occurrences": verify["movement_sample_count"],
             "movement_phases_each": verify["movement_phases_each"],
             "captures": captures["files"], "automation_test": TEST,
             "automation_result": "Success", "saved_roots": c.SAVED_ROOTS,
             "final_census": c.census(), "backup": c.BACKUP}
    final_path = c.write_json("slot_b_final_%s.json" % c.RUN, final)
    report_path = os.path.join(BASE, "REPORT_%s.md" % c.RUN)
    lines = [
        "# Flat V3 Slot B Report - %s" % c.RUN,
        "",
        "Final status: **PASS**.",
        "",
        "- **measured:** Starting editor world was `%s`, PIE/SIE was absent, and the starting census was clean." % c.WORLD,
        "- **declaration-proven + measured:** `FLATV3_A_OK` was present; all eight pool meshes passed the corrected Slot A geometry/UV/LOD gates and the live socket read-back generated from `Tools/FlatV3/socket_contract.py`.",
        "- **measured:** %d P04 wing occurrences were changed in deterministic cue order; neither side repeats the same mesh consecutively." % verify["rows"],
        "- **measured:** Every Left/Right placement read back with identity facing policy, flip off, zero rotation, unit scale, empty MaterialOverrides, and each side's backbone Y derived independently from that old panel's transformed outer edge. Top panels and mechanisms read back unchanged.",
        "- **measured:** Only P04 was materialized. The dirty set before save was exactly the Show and vertical-slice level; only those two packages were saved, then the census returned clean.",
        "- **measured:** All %d placed Left/Right panels passed side bounds and Front -X gates." % len(verify["placed_panels"]),
        "- **measured:** Three distinct occurrences were evaluated at phases 0.25, 0.50 and 0.75; their transforms and movement are in `slot_b_verify_%s.json`." % c.RUN,
        "- **measured:** Three viewport poses were captured in both lit and unlit modes (six PNGs), without an exposure override and without spawning actors.",
        "- **measured:** `%s` ran alone and completed with `Success`." % TEST,
        "- **measured:** Final census is `content=[]`, `maps=[]`.",
        "- **inferred, bounded:** Visual/artistic acceptance is not claimed; the captures prove rendered output was produced, not that Gary has approved the look.",
        "",
        "Backup: `%s`" % c.BACKUP,
        "",
        "Evidence: `slot_b_originals_%s.json`, `slot_b_dry_run_%s.json`, `slot_b_apply_%s.json`, `slot_b_verify_%s.json`, `slot_b_captures_%s.json`, `slot_b_final_%s.json`, and `Saved/Logs/PussStage.log`." %
        (c.RUN, c.RUN, c.RUN, c.RUN, c.RUN, c.RUN),
    ]
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    unreal.log("FLATV3_B_OK run=%s rows=%d movement_occurrences=3 captures=6 test=%s result=Success saved_count=2 saved_roots=%s census=%s report=%s" %
               (c.RUN, verify["rows"], TEST, json.dumps(c.SAVED_ROOTS, separators=(",", ":")),
                json.dumps(c.census(), separators=(",", ":"), sort_keys=True), report_path))
    c.log_release("OK", c.SAVED_ROOTS)
except Exception as exc:
    reason = "finalize:" + str(exc)
    report.update({"status": "FAIL", "reason": reason, "traceback": traceback.format_exc(),
                   "census": c.census()})
    c.write_json("slot_b_final_%s_FAILURE.json" % c.RUN, report)
    saved = []
    try:
        saved = slot_b_revert.revert(reason)
    except Exception as revert_exc:
        reason += "|REVERT_FAIL:" + str(revert_exc)
    c.log_release("FAIL", saved, reason)
