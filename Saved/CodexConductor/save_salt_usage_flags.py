import unreal
L = unreal.EditorLoadingAndSavingUtils
dirty = [p.get_name() for p in L.get_dirty_content_packages()]
want = [p for p in dirty if p.startswith("/Game/Scenes/Wings/StageOpeningV2/Materials/M_SaltFormation_")]
if sorted(dirty) != sorted(want) or not want:
    raise RuntimeError("SALT_FLAGS_REFUSED|dirty=%s" % dirty)
ok = [unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True) for p in want]
unreal.log("SALT_FLAGS_SAVED|%s|%s|after=%s" % (want, ok, [p.get_name() for p in L.get_dirty_content_packages()]))
