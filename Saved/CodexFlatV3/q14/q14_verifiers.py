"""Q14: queue SavedMasterMatchesShow + SceneCutBindingsResolve (read-only automation tests) after a run-id marker."""
import datetime
import unreal

RUN = datetime.datetime.now().strftime("Q14V-%Y%m%d-%H%M%S")
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.log("Q14_VERIFIERS_QUEUED|run=%s" % RUN)
unreal.SystemLibrary.execute_console_command(
    world, "Automation RunTests InfinityStage.Editor.SavedMasterMatchesShow+InfinityStage.Editor.SceneCutBindingsResolve")
