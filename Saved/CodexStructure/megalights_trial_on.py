"""MegaLights trial, switch on. Console variable only: nothing is saved to config,
the Show or the level, and it resets when the editor restarts. Judge the 136 beam
fixtures by eye - if the shafts thin out or lose volumetric shadows, it fails."""
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
before = unreal.SystemLibrary.get_console_variable_int_value("r.MegaLights.EnableForProject")
unreal.SystemLibrary.execute_console_command(world, "r.MegaLights.EnableForProject 1")
after = unreal.SystemLibrary.get_console_variable_int_value("r.MegaLights.EnableForProject")
assert after == 1, f"cvar did not take: {after}"
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"MEGALIGHTS_TRIAL_ON_OK|before={before}|after={after}|dirty={dirty}|persisted=0")
