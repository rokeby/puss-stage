"""Queue exactly the one Phase 2 acceptance automation test in the live editor."""
import unreal

RUN = "RZIMP2-TEST-SavedMasterMatchesShow"
TEST = "InfinityStage.Editor.SavedMasterMatchesShow"

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("FLATV3_AUTOMATION_REFUSED_PIE")
unreal.SystemLibrary.execute_console_command(
    editor.get_editor_world(), "Automation RunTests " + TEST)
unreal.log("FLATV3_AUTOMATION_QUEUED run=%s test=%s alone=true" % (RUN, TEST))
