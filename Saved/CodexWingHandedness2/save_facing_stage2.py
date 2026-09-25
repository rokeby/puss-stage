"""STAGE 2: targeted save of the Show asset and the current level only. Asserts the dirty scope
before saving and zero dirty packages afterwards. Never Save All."""
import os
import sys

import unreal  # noqa: E402

sys.path.insert(0, os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexWingHandedness2"))
from _common import EXPECTED_WORLD, SHOW_PATH, dirty, editor_ready, require, write_json  # noqa: E402

editor_ready()
d0 = dirty()
require(set(d0["content"]) <= {SHOW_PATH} and set(d0["maps"]) <= {EXPECTED_WORLD},
        f"Out-of-scope dirty packages: {d0}")
require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False), "Show save failed")
require(bool(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()), "Level save failed")
d1 = dirty()
require(not d1["content"] and not d1["maps"], f"Dirty after targeted save: {d1}")
write_json("save_stage2_result.json", {"status": "ok", "dirty_before": d0, "dirty_after": d1})
unreal.log("WING_FACING_STAGE2_SUCCESS|show_saved=1|level_saved=1|dirty=0")
