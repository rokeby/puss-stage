"""Shaft trial state 'B_nofog': console variables only. Nothing is saved to config,
the Show or the level; everything resets on editor restart. Pair each state
with an offscreen capture at the same beam bay and compare."""
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SETTINGS = [("r.VolumetricFog", 0), ("r.VolumetricFog.UseLightFunctionAtlas", 0), ("r.MegaLights.EnableForProject", 1)]
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
report = []
for name, value in SETTINGS:
    before = unreal.SystemLibrary.get_console_variable_float_value(name)
    unreal.SystemLibrary.execute_console_command(world, f"{name} {value}")
    after = unreal.SystemLibrary.get_console_variable_float_value(name)
    assert abs(after - value) < 1e-6, f"{name} did not take: {after}"
    report.append(f"{name}:{before:g}->{after:g}")
unreal.log("SHAFT_TRIAL_B_nofog_OK|" + "|".join(report) + "|persisted=0")
