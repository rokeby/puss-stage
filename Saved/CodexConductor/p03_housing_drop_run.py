"""Entrypoint for p03_housing_drop.py via ExecuteProjectPythonFile.

Reads p03_housing_drop_args.json, e.g.
  {"mode": "DRY"}
  {"mode": "APPLY", "confirm": "APPLY P03", "ack_records": [], "extra_light_guids": [], "top_convention": "BOX"}
  {"mode": "REVERT", "confirm": "REVERT P03"}
APPLY and REVERT refuse unless "confirm" repeats "<MODE> P03" exactly, so a
stale args file cannot turn a dry run into a write. The tool checks it again.
"""
import json
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/"
with open(HERE + "p03_housing_drop_args.json", encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P03" % mode:
    raise RuntimeError("P03_HOUSING_DROP_FAILED|run=none|reason=CONFIRM_MISSING|mode=%s" % mode)
runpy.run_path(HERE + "p03_housing_drop.py", init_globals={
    "P03_HOUSING_DROP_MODE": mode,
    "P03_HOUSING_DROP_CONFIRM": args.get("confirm"),
    "P03_HOUSING_DROP_ACK_RECORDS": list(args.get("ack_records", [])),
    "P03_HOUSING_DROP_EXTRA_LIGHT_GUIDS": list(args.get("extra_light_guids", [])),
    "P03_HOUSING_DROP_TOP_CONVENTION": args.get("top_convention", "BOX"),
})
