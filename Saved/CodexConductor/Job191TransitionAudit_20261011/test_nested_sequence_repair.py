"""Offline positive and negative controls for Job 191 nested repair."""

from __future__ import annotations

import pathlib
import json
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nested_repair_core as core


passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


def base(**updates):
    row = {
        "parent_path": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03",
        "parent_name": "LS_DevScene_03",
        "parent_playback": [0, 6240],
        "parent_display_fps": 24.0,
        "section_path": "LS_DevScene_03:Sub_0",
        "track_path": "LS_DevScene_03:Track_0",
        "track_index": 0,
        "section_index": 0,
        "section_range": [-1, 6313],
        "child_path": "/Game/Scenes/LS_Clams",
        "child_name": "LS_Clams",
        "child_playback": [0, 6313],
        "child_display_fps": 24.0,
        "child_tick_fps": 24000.0,
        "time_scale": 1.0,
        "start_offset_ticks": 21000,
        "end_offset_ticks": 0,
    }
    row.update(updates)
    return row


plan = core.build_plan([base()])
request = json.loads((HERE / "nested_sequence_request.json").read_text(encoding="utf-8"))
check("+ nested request uses call_tool envelope",
      request.get("name") == "call_tool" and
      request.get("arguments", {}).get("arguments", {}).get("relativeSavedPath") ==
      "CodexConductor/Job191TransitionAudit_20261011/nested_sequence_repair.py")
repair = plan["repairs"][0]
check("+ S3 overrun is found", plan["offender_count"] == 1)
check("+ only the end is trimmed 6313 -> 6240", repair["section_range"] == [-1, 6313] and repair["new_range"] == [-1, 6240])
check("+ trim is simulated green", core.simulated_test_passes(plan))
check("+ authored but parent-clipped tail is reported", "already clipped" in repair["visible_outside"])

clean = core.build_plan([base(section_range=[-1, 6240])])
check("- a clean section is not mutated", clean["offender_count"] == 0 and clean["repair_count"] == 0)

klara = core.build_plan([base(child_path="/Game/InfinityStage/KlaraHookin/LS_Animals")])
check("- Klara offender is skipped", klara["skipped_klara_count"] == 1 and klara["repair_count"] == 0)

retimed = core.build_plan([base(section_range=[0, 100], parent_playback=[0, 1000],
                                      child_playback=[0, 240], time_scale=0.5,
                                      start_offset_ticks=0)])
check("- retimed extension that would expose content is blocked", retimed["blocked_count"] == 1)

too_long = core.build_plan([base(section_range=[0, 100], parent_playback=[0, 150],
                                       child_playback=[0, 240], time_scale=0.5,
                                       start_offset_ticks=0)])
check("- retimed content beyond parent is blocked", too_long["blocked_count"] == 1)

try:
    core.validate_args({"mode": "APPLY", "run": "J191-NEST-A01", "confirm": "wrong", "plan_sha256": "x"})
    refused = False
except ValueError:
    refused = True
check("- wrong confirm is refused", refused)

check("+ plan digest is deterministic", plan["plan_sha256"] == core.build_plan([base()])["plan_sha256"])

print("NESTED_HARNESS_RESULT|passed=%d|failed=%d" % (passed, failed))
raise SystemExit(1 if failed else 0)
