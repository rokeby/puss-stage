"""Entrypoint for lighting_scores_apply.py via ExecuteProjectPythonFile.

Reads lighting_scores_run_args.json, e.g.
  {"mode": "DRY", "passage": "P05"}
  {"mode": "APPLY", "passage": "P05", "confirm": "APPLY P05", "ack_records": []}
APPLY and REVERT refuse unless "confirm" repeats "<MODE> <PASSAGE>" exactly, so a
stale args file cannot turn a dry-run request into a write.
"""
import json
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/"
with open(HERE + "lighting_scores_run_args.json", encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
passage = str(args.get("passage", "")).upper()
if mode != "DRY" and args.get("confirm") != "%s %s" % (mode, passage):
    raise RuntimeError("LIGHTING_SCORES_STOPPED|reason=CONFIRM_MISSING|mode=%s|passage=%s" % (mode, passage))
runpy.run_path(HERE + "lighting_scores_apply.py", init_globals={
    "LIGHTING_SCORES_MODE": mode,
    "LIGHTING_SCORES_PASSAGE": passage,
    "LIGHTING_SCORES_ACK_RECORDS": list(args.get("ack_records", [])),
    "LIGHTING_SCORES_PROTOTYPE_ABSENT": args.get("prototype_absent"),
})
