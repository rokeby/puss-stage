import unreal
SHOW="/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"; WORLD="/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
def pk(p): return str(p).split("'")[1].split(".")[0] if "'" in str(p) else str(p)
c=[pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]; m=[pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
assert set(c) <= {SHOW} and set(m) <= {WORLD}, f"out-of-scope dirty: {c} {m}"
if c: assert unreal.EditorAssetLibrary.save_asset(SHOW, only_if_is_dirty=False)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
c2=len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()); m2=len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"TARGETED_SAVE_OK|show_saved={bool(c)}|level_saved=1|dirty_after={c2}+{m2}")
