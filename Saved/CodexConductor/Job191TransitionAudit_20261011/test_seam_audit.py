"""Offline positive and negative controls for Job 191 seam audit."""

from __future__ import annotations

import pathlib
import json
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seam_audit_core as core


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


segments = [{"label": "Opening - Curtain", "start": 0, "end": 100}]
request = json.loads((HERE / "seam_audit_request.json").read_text(encoding="utf-8"))
check("+ seam request uses call_tool envelope",
      request.get("name") == "call_tool" and
      request.get("arguments", {}).get("arguments", {}).get("relativeSavedPath") ==
      "CodexConductor/Job191TransitionAudit_20261011/seam_audit_runner.py")
cursor = 100
for number in range(1, 7):
    segments.append({"label": "Passage %d" % number, "start": cursor, "end": cursor + 100})
    cursor += 100
    segments.append({"label": "Scene %d - External Sound" % number, "start": cursor, "end": cursor + 100})
    cursor += 100
    if number < 6:
        segments.append({"label": "Interaction %d - Test" % number, "start": cursor, "end": cursor + 100})
        cursor += 100
segments.append({"label": "Closing - Sweeping Up", "start": cursor, "end": cursor + 100})

plan = core.plan_seams(segments, ticks_per_second=24, display_fps=24)
check("+ exact 16-seam census", len(plan["seams"]) == 16 and plan["counts"] == {
      "passage_to_scene": 6, "interaction_start": 5, "interaction_end": 5})
check("+ seams stay in Master order", [s["boundary"] for s in plan["seams"]] == sorted(s["boundary"] for s in plan["seams"]))
check("+ four requested sample offsets", [s["target_frame"] - plan["seams"][0]["boundary"] for s in plan["seams"][0]["samples"]] == [-24, -1, 1, 24])

with_interlude = [dict(row) for row in segments]
i4 = next(i for i, row in enumerate(with_interlude) if row["label"].startswith("Interaction 4"))
interlude_start = with_interlude[i4]["end"]
for row in with_interlude[i4 + 1:]:
    row["start"] += 100
    row["end"] += 100
with_interlude.insert(i4 + 1, {"label": "Interlude: Puss Sleep/Wet Tennis Ball/Battery",
                               "start": interlude_start, "end": interlude_start + 100})
interlude_plan = core.plan_seams(with_interlude, ticks_per_second=24, display_fps=24)
i4_end = next(row for row in interlude_plan["seams"]
              if row.get("interaction", "").startswith("Interaction 4") and row["kind"].endswith("interaction_end"))
check("+ Interlude between I4 and P5 preserves the logical transition",
      len(interlude_plan["seams"]) == 16 and i4_end["to"].startswith("Interlude") and
      i4_end["logical_to"] == "Passage 5")

runner_source = (HERE / "seam_audit_runner.py").read_text(encoding="utf-8")
check("+ failed audit always rewrites its result evidence",
      'if "plan" in state and "captured_frames" not in state' in runner_source and
      'errors=%d' in runner_source)

seam = plan["seams"][0]
for index, sample in enumerate(seam["samples"]):
    sample.update(path="%s.png" % sample["key"], actual_frame=sample["target_frame"],
                  camera={"location": [0.0 if index < 2 else 100.0, 0.0, 0.0],
                          "rotation": {"pitch": 0.0, "yaw": 0.0 if index < 2 else 10.0, "roll": 0.0},
                          "fov_deg": 60.0},
                  view_target={"path": "A" if index < 2 else "B", "label": "A" if index < 2 else "B"},
                  mean_luminance=2.0 if index == 1 else (100.0 if index < 2 else 220.0))
thresholds = {"position_cm": 25.0, "rotation_deg": 2.0, "luma_abs": 32.0,
              "luma_ratio": 0.4, "black": 5.0, "white": 250.0}
analysis = core.analyze_seam(seam, thresholds)
check("+ camera position jump flagged", "camera_position_jump" in analysis["flags"])
check("+ camera rotation jump flagged", "camera_rotation_jump" in analysis["flags"])
check("+ luminance pop flagged", "luminance_pop" in analysis["flags"])
check("+ black frame flagged", "black_frame:minus_1f" in analysis["flags"])
seam["analysis"] = analysis
html = core.contact_sheet_html(seam)
check("+ contact sheet contains four images and metrics", html.count("<img ") == 4 and "mean luma" in html and "Flags:" in html)

broken = [dict(row) for row in segments]
broken[1]["end"] -= 1
try:
    core.plan_seams(broken, ticks_per_second=24, display_fps=24)
    refused_gap = False
except ValueError:
    refused_gap = True
check("- non-contiguous Master is refused", refused_gap)

try:
    core.validate_args({"run": "bad", "confirm": "CONFIRM_JOB191_SEAM_AUDIT"})
    refused_run = False
except ValueError:
    refused_run = True
check("- malformed run id is refused", refused_run)

try:
    core.analyze_seam({"id": "x", "samples": seam["samples"][:3]}, thresholds)
    refused_partial = False
except ValueError:
    refused_partial = True
check("- incomplete contact sheet is refused", refused_partial)

print("SEAM_HARNESS_RESULT|passed=%d|failed=%d" % (passed, failed))
raise SystemExit(1 if failed else 0)
