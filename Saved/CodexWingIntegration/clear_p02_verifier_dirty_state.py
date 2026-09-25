import unreal


CONTENT_ROOT = "/Game/Wings/Passage02_AnimalsToShrineV2"
if not unreal.EditorAssetLibrary.save_directory(
    CONTENT_ROOT, only_if_is_dirty=True, recursive=True
):
    raise RuntimeError(f"Targeted save failed: {CONTENT_ROOT}")

dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
if dirty_content or dirty_maps:
    raise RuntimeError(
        f"Dirty state remains: content={len(dirty_content)} maps={len(dirty_maps)}"
    )

unreal.log("P02_VERIFIER_DIRTY_CLEAR_SUCCESS|scope=/Game/Wings/Passage02_AnimalsToShrineV2|dirty=0")
