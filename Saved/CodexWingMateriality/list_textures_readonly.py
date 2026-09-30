"""Read-only: run the engine's ListTextures so built sizes and mip counts land in the log."""
import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.log("PUSS_WING_LISTTEXTURES_BEGIN")
unreal.SystemLibrary.execute_console_command(world, "ListTextures")
unreal.log("PUSS_WING_LISTTEXTURES_END")
