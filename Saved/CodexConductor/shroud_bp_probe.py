import unreal as u
bp = u.load_asset("/Game/Metahuman/ShoreCast_20260910/SceneCharacters/BP_Shore01_M56_Draped")
sds = u.get_engine_subsystem(u.SubobjectDataSubsystem)
out = []
for h in sds.k2_gather_subobject_data_for_blueprint(bp):
    o = u.SubobjectDataBlueprintFunctionLibrary.get_object(u.SubobjectDataBlueprintFunctionLibrary.get_data(h))
    out.append((o.get_name() if o else None, o.get_class().get_name() if o else None))
u.log("SHROUDBP_OK|%s" % out)
