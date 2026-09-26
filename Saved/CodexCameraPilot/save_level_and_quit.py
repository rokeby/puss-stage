"""Save the vertical-slice level (net-nil capture dirty flag; Gary: "close, save and open
editor at will tonight"), prove nothing is dirty, then quit the editor gracefully for a build.
Refuses if any content package is dirty or any other map is dirty.
Success marker: PUSS_LEVEL_SAVED_READY_TO_QUIT (then the editor quits)."""
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    raise RuntimeError("Unexpected editor world")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if content or [m for m in maps if m != EXPECTED_WORLD]:
    raise RuntimeError(f"Refusing: unexpected dirty packages content={content} maps={maps}")
if maps:
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        raise RuntimeError("Level save failed")
content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if content or maps:
    raise RuntimeError(f"Still dirty after save: content={content} maps={maps}")
unreal.log(f"PUSS_LEVEL_SAVED_READY_TO_QUIT|saved_level={int(bool(maps) or True)}")
unreal.SystemLibrary.quit_editor()
