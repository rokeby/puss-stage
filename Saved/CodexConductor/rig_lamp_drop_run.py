"""Entrypoint for rig_lamp_drop.py via ExecuteProjectPythonFile.

Reads rig_lamp_drop_args.json, e.g.
  {"mode": "DRY", "passage": "P02", "label_regex": "TOP_[LR]$", "top_convention": "BOX"}
  {"mode": "APPLY", "passage": "P02", "confirm": "APPLY P02", "label_regex": "TOP_[LR]$",
   "ack_records": ["<paths copied VERBATIM from the DRY report's unacknowledged_foreign_records>"],
   "top_convention": "BOX", "expected_targets": <DRY targets>, "expected_drop_cm": <DRY drop_cm>}
  {"mode": "REVERT", "passage": "P02", "confirm": "REVERT P02"}
APPLY and REVERT refuse unless "confirm" repeats "<MODE> <passage>" exactly, so a
stale args file cannot turn a dry run into a write, or aim a write at another
passage. The tool checks it again (check_args). Cached modules from Saved/CodexConductor
are purged first so edited helpers never run stale (editor module cache, 2 Oct).
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

with open(os.path.join(HERE, "rig_lamp_drop_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
passage = str(args.get("passage", "")).upper()
if mode != "DRY" and args.get("confirm") != "%s %s" % (mode, passage):
    raise RuntimeError("RIG_LAMP_DROP_FAILED|run=none|passage=%s|mode=%s|reason=CONFIRM_MISSING" % (passage, mode))
runpy.run_path(os.path.join(HERE, "rig_lamp_drop.py"), init_globals={
    "RIG_LAMP_DROP_MODE": mode,
    "RIG_LAMP_DROP_PASSAGE": passage,
    "RIG_LAMP_DROP_CONFIRM": args.get("confirm"),
    "RIG_LAMP_DROP_LABEL_REGEX": args.get("label_regex", "TOP_[LR]$"),
    "RIG_LAMP_DROP_ACK_RECORDS": list(args.get("ack_records", []) or []),
    "RIG_LAMP_DROP_TOP_CONVENTION": args.get("top_convention", "BOX"),
    "RIG_LAMP_DROP_EXPECTED_TARGETS": args.get("expected_targets"),
    "RIG_LAMP_DROP_EXPECTED_DROP_CM": args.get("expected_drop_cm"),
    "RIG_LAMP_DROP_RECORD_TAG": args.get("record_tag", ""),
    "RIG_LAMP_DROP_ALLOW_NON_SCORE_BECAUSE": args.get("allow_non_score_because", ""),
})
