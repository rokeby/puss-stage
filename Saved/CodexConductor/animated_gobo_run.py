"""Fresh runner for animated_gobo.py through ExecuteProjectPythonFile.

Reads Saved/CodexConductor/animated_gobo_args.json.  The args file is deliberately
not tracked: the conductor writes exact sequence/label/range and an explicit
confirm string for each run.  See Docs/Conductor/P6_ANIMATED_GOBO_FINDINGS_2026-10-08.md.
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

with open(os.path.join(HERE, "animated_gobo_args.json"), encoding="utf-8") as handle:
    ARGS = json.load(handle)

runpy.run_path(os.path.join(HERE, "animated_gobo.py"), run_name="__animated_gobo_runner__",
               init_globals={"ANIMATED_GOBO_ARGS": ARGS})
