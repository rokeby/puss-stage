"""Queues ONE automation test by its full name (read from run_single_test.json). Results land in the log."""
import json
import os


def run():
    import unreal
    project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    with open(os.path.join(project_dir, "Saved", "CodexCueing", "run_single_test.json"), encoding="utf-8") as handle:
        test = json.load(handle)["test"]
    if not test.startswith("InfinityStage.") or "PussStage" in test:
        raise RuntimeError("refusing test filter %r" % test)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + test)
    unreal.log("CUEING_TEST_QUEUED|test=%s" % test)


run()
