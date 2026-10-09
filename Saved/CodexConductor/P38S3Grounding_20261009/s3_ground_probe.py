"""Dedicated read-only P38 ground probe entry point requested by the brief.

The shared args file must name operation=ground_probe, mode=DRY and the exact
confirm string.  All implementation lives in p38_editor.py so safety and
diagnostic behavior cannot drift from the other P38 operations.
"""
import json
import os
import runpy

import unreal

root = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor", "P38S3Grounding_20261009")
with open(os.path.join(root, "p38_args.json"), "r", encoding="utf-8") as handle:
    args = json.load(handle)
if args.get("operation") != "ground_probe" or args.get("mode") != "DRY":
    raise RuntimeError("S3_GROUND_PROBE_WRAPPER_REQUIRES_GROUND_PROBE_DRY")
runpy.run_path(os.path.join(root, "p38_editor.py"), run_name="<run_path>")
