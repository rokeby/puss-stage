"""Entrypoint for p01_rig_pattern.py with target_passage P04, via ExecuteProjectPythonFile.

Reads p04_rig_pattern_args.json (target P04, templates read LIVE from P01 Wing 003/004), e.g.
  {"mode": "DRY", "target_passage": "P04", "template_passage": "P01", ...}
  {"mode": "APPLY", "confirm": "APPLY P04RIGPATTERN", "target_passage": "P04", "expected_targets": <DRY rows>,
   "ack_records": ["<paths copied VERBATIM from the DRY report's unacknowledged_foreign_records>"], ...same jitter/roles}
  {"mode": "REVERT", "confirm": "REVERT P04RIGPATTERN", "target_passage": "P04"}
Optional "intensity_scale" (P04, Gary 7 Oct "even if the lights are dimmed for now") multiplies each moved light's
intensity; null leaves intensity untouched. Only "P04 SCORE B## <look> <ROLE>" rows move; the moonlight key, the strobe
and p04_strobe_halo*/opening rows are refused by label (FORBIDDEN_TARGET_LABEL) and guarded by the scope check.
Record p04_rig_pattern_record.json, reports p04_rig_pattern_report_<MODE>_<run>.json, markers
P04RIGPATTERN_*. The P01 record/args/runner are not touched. Refuses unless the args file names target P04,
and APPLY/REVERT unless "confirm" repeats "<MODE> P04RIGPATTERN" (the tool checks both again). Stale modules from
Saved/CodexConductor are purged first (ue58-python-stale-module-cache, 2 Oct).
"""
import json
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")

for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(os.path.normcase(os.path.abspath(HERE))):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "p04_rig_pattern_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if args.get("target_passage") != "P04":
    unreal.log_error("P04RIGPATTERN_STOPPED|run=none|mode=%s|TARGET_PASSAGE_NOT_P04|NOTHING SAVED" % mode)
    raise RuntimeError("P04RIGPATTERN_STOPPED|run=none|mode=%s|TARGET_PASSAGE_NOT_P04" % mode)
if mode != "DRY" and args.get("confirm") != "%s P04RIGPATTERN" % mode:
    unreal.log_error("P04RIGPATTERN_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("P04RIGPATTERN_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "p01_rig_pattern.py"), run_name="__p04_rig_pattern_runner__",
               init_globals={"P01RIGPATTERN_ARGS": args})
