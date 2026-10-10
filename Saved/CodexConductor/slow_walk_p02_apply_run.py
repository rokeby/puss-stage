"""MCP wrapper: P02 slow-walk APPLY, one Passage and one run id."""
import os

import unreal

path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor", "passage_slow_walk.py",
)
with open(path, "r", encoding="utf-8") as handle:
    source = handle.read()
scope = {"__name__": "slow_walk_p02_apply_module", "__file__": path}
exec(compile(source, path, "exec"), scope)
scope["run_unreal"]("Passage 2", "APPLY", "SW-P02-APPLY-20261002-A")
