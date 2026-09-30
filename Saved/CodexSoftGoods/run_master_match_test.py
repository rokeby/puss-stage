"""Queue ONE read-only automation test in the open editor: InfinityStage.Editor.SavedMasterMatchesShow (30 Sep, the
Conductor: the verification after any Master rebuild; "the instrument that just told us the truth").

The filter names that single test; never broaden it (never the unfiltered suite). The test loads the Show and the Master,
compiles the transport and compares each Master sub-section against the Show-compiled segment to 0.05 s. It rebuilds and
saves nothing. The test runs on later editor ticks, so this call only queues it: read the result from the editor log,
"Test Completed. Result={...} Name={SavedMasterMatchesShow}", and read every assertion line, not just a green summary
(the test only logs failures). Refuses during PIE. Crash rules: everything inside main().
"""
import unreal

TEST = "InfinityStage.Editor.SavedMasterMatchesShow"


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        unreal.log("PUSS_SOFTGOODS_MASTER_TEST|refused: PIE is running")
        return
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), f"Automation RunTests {TEST}")
    unreal.log(f"PUSS_SOFTGOODS_MASTER_TEST|queued|{TEST}")


main()
