import unreal
c = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
m = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.log("DIRTYCHECK|content=%d|map=%d" % (len(c), len(m)))
for p in list(c) + list(m):
    unreal.log("DIRTY|%s" % p.get_name())
exists = unreal.EditorAssetLibrary.does_asset_exist("/Game/Scenes/Wings/PaintedSurface/M_Wing_PaintedSurface_Master")
unreal.log("PAINTEDMASTER_EXISTS|%s" % exists)
