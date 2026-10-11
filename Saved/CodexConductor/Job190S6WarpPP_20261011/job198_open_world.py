import unreal

EXPECTED = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
current = world.get_path_name().split(".", 1)[0] if world else None
if editor.get_game_world() is not None:
    raise RuntimeError("JOB198_OPEN_WORLD_REFUSED|PIE_ACTIVE")
dirty = {"maps": [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
         "content": [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
if dirty != {"maps": [], "content": []}:
    raise RuntimeError("JOB198_OPEN_WORLD_REFUSED|DIRTY|%r" % dirty)
if current != EXPECTED:
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(EXPECTED):
        raise RuntimeError("JOB198_OPEN_WORLD_FAILED|from=%r" % current)
world = editor.get_editor_world()
after = world.get_path_name().split(".", 1)[0] if world else None
if after != EXPECTED:
    raise RuntimeError("JOB198_OPEN_WORLD_READBACK|%r" % after)
unreal.log("JOB198_OPEN_WORLD_OK|from=%s|to=%s|pie=false|dirty_maps=0|dirty_content=0" % (current, after))
