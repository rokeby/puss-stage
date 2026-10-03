"""Queue exactly InfinityStage.Editor.SceneCutBindingsResolve in the live editor."""
import datetime
import json

import unreal

TEST = "InfinityStage.Editor.SceneCutBindingsResolve"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
run = datetime.datetime.now().strftime("%H%M%S")
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("TEST_QUEUE_STOPPED|run=%s|reason=PIE_OR_SIE_ACTIVE" % run)
world = editor.get_editor_world()
if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
    raise RuntimeError("TEST_QUEUE_STOPPED|run=%s|reason=WRONG_WORLD" % run)
census = {
    "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
}
if census["content"] or census["maps"]:
    raise RuntimeError("TEST_QUEUE_STOPPED|run=%s|reason=DIRTY_BEFORE|census=%s" %
                       (run, json.dumps(census, separators=(",", ":"), sort_keys=True)))
unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + TEST)
unreal.log("CONDUCTOR_AUTOMATION_QUEUED|run=%s|test=%s|alone=true" % (run, TEST))
