"""MCP wrapper: long Opening tool, APPLY. Run ALONE; read PUSS_OPENING_* in the Unreal log (and the report JSON)."""
import datetime
import os

import unreal

path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor", "opening_sequence_apply.py")
with open(path, "r", encoding="utf-8") as handle:
    source = handle.read()
scope = {
    "__name__": "opening_sequence_apply_module",
    "__file__": path,
    "OPENING_MODE": "DRY",
    "OPENING_RUN_ID": "OPENING-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
}
exec(compile(source, path, "exec"), scope)
