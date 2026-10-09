"""Command-line Unreal runner for the MRQ fallback survey/build.

The unattended Saturday wrapper passes arguments in MRQFB_ARGS_JSON.  Keeping
them in the process environment avoids rewriting a shared args file.  This is
run only by UnrealEditor-Cmd after the interactive editor and Blender are shut.
"""
import json
import os
import runpy

import unreal


saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
here = os.path.join(saved, "CodexConductor", "MRQ")
raw = os.environ.get("MRQFB_ARGS_JSON", "")
if not raw:
    raise RuntimeError("MRQFB_ARGS_JSON is empty")
args = json.loads(raw)
runpy.run_path(os.path.join(saved, "CodexConductor", "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(here, "mrq_fallbacks.py"), init_globals={"MRQFB_ARGS": args})
