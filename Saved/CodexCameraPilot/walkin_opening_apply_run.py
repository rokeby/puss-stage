"""MCP wrapper: generalized walk-in keyer, OPENING APPLY."""
import os
import unreal
path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexCameraPilot", "key_walkin_i1_p02.py")
with open(path, "r", encoding="utf-8") as handle:
    source = handle.read()
scope = {
    "__name__": "walkin_opening_apply_module",
    "__file__": path,
    "WALKIN_DRY_RUN": False,
    "WALKIN_TRANSITION_ID": "OPENING",
    "WALKIN_RUN_ID": "WALKIN-OPENING-APPLY-20261002-A",
}
exec(compile(source, path, "exec"), scope)
