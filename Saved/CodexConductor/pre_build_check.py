import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
c = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
m = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.log("PREBUILD|world=%s|content=%d|map=%d" % (world.get_name(), len(c), len(m)))
for p in list(c) + list(m):
    unreal.log("PREBUILD_DIRTY|%s" % p.get_name())
unreal.log("PREBUILD_PIE|%s" % unreal.EditorLevelLibrary.is_playing_in_editor() if hasattr(unreal.EditorLevelLibrary,'is_playing_in_editor') else "PREBUILD_PIE|unknown")
