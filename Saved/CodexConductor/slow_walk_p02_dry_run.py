"""MCP wrapper: P02 slow-walk DRY, one Passage and one run id."""
import os

import unreal

path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor", "passage_slow_walk.py",
)
with open(path, "r", encoding="utf-8") as handle:
    source = handle.read()
scope = {"__name__": "slow_walk_p02_dry_module", "__file__": path}
exec(compile(source, path, "exec"), scope)
scope["run_unreal"]("Passage 2", "DRY", "SW-P02-DRY-20261002-A")
