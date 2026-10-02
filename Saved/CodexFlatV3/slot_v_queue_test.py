"""Read-only: queue InfinityStage.Editor.SavedMasterMatchesShow once. No save, no revert, no edits."""
import json
import unreal

RUN = str(globals().get("FLATV3_V_RUN", "FV3V-20261002-02"))
TEST = "InfinityStage.Editor.SavedMasterMatchesShow"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def census():
    def names(packages):
        return sorted(str(p.get_name()).split(".", 1)[0] for p in packages)
    return {"content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or world.get_outermost().get_name() != WORLD:
    raise RuntimeError("WRONG_WORLD")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE_OR_SIE_ACTIVE")
if census() != {"content": [], "maps": []}:
    raise RuntimeError("DIRTY_BEFORE_TEST|" + json.dumps(census(), sort_keys=True))
unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + TEST)
unreal.log("FLATV3_V_TEST_QUEUED run=%s test=%s" % (RUN, TEST))
