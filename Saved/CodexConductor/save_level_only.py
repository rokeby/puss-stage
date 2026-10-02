"""Save only the current vertical-slice level under an exact dirty-state guard."""
import datetime
import json

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def census():
    return {
        "content": sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        ),
        "maps": sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        ),
    }


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = world.get_outermost().get_name() if world is not None else None
assert world_path == EXPECTED_WORLD, "unexpected editor world: %s" % world_path
assert editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE"

before = census()
expected_before = {"content": [], "maps": [EXPECTED_WORLD]}
assert before == expected_before, "unexpected dirty census: %s" % json.dumps(
    before, sort_keys=True, separators=(",", ":")
)

saved = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
assert saved is True, "save_current_level returned: %r" % saved

after = census()
assert after == {"content": [], "maps": []}, "post-save dirty census: %s" % json.dumps(
    after, sort_keys=True, separators=(",", ":")
)

run = datetime.datetime.now().strftime("%H%M%S")
unreal.log(
    "CONDUCTOR_LEVEL_RESAVED|run=%s|census=%s"
    % (run, json.dumps(after, sort_keys=True, separators=(",", ":")))
)
