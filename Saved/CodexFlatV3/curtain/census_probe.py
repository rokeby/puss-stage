import unreal
lib = unreal.EditorLoadingAndSavingUtils
c = sorted(p.get_path_name() for p in lib.get_dirty_content_packages()); m = sorted(p.get_path_name() for p in lib.get_dirty_map_packages())
pie = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None
unreal.log("CI_CENSUS run=CI-20261007-END content=%s maps=%s pie=%s" % (c, m, pie))
