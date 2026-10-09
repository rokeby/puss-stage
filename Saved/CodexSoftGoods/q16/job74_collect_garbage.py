import unreal

RUN_ID = "Q16-J74-20261009-1223"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world().get_outermost().get_name()
pie = editor.get_game_world() is not None
if world != EXPECTED_WORLD or pie:
    raise RuntimeError("Q16_GC_REFUSED|run=%s|world=%s|pie=%s" % (RUN_ID, world, pie))

unreal.SystemLibrary.collect_garbage()
content = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
maps = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
pie_after = editor.get_game_world() is not None
if content or maps or pie_after:
    raise RuntimeError("Q16_GC_FAILED|run=%s|content=%s|maps=%s|pie=%s" %
                       (RUN_ID, content, maps, pie_after))
unreal.log("Q16_GC_SUCCESS|run=%s|content=%s|maps=%s|pie=%s" %
           (RUN_ID, content, maps, pie_after))
