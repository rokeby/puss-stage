import unreal
out = []
for p in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path("/Game", recursive=True).__iter__() if False else []:
    pass
reg = unreal.AssetRegistryHelpers.get_asset_registry()
f = unreal.ARFilter(class_paths=[unreal.TopLevelAssetPath("/Script/Engine", "MaterialInstanceConstant")], recursive_paths=True, package_paths=["/Game"])
for d in reg.get_assets(f):
    n = str(d.asset_name)
    if n in ("MI_PearlClam_Pearl_v3_GreenOrange", "MI_PearlClam_Pearl_Fade"):
        mi = d.get_asset(); chain = [str(d.package_name)]; m = mi
        while isinstance(m, unreal.MaterialInstance):
            m = m.get_editor_property("parent"); chain.append(m.get_path_name() if m else "None")
        out.append(chain)
unreal.log("PEARLPARENT_OK|%s" % out)
