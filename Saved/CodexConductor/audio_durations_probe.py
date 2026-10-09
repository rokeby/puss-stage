import unreal
paths = ["/Game/InfinityStage/Audio/Passages/" + n for n in ["SW_P01_IntroWalking","SW_P02_Walking","SW_P03_Walking","SW_P04_Walking","SW_P05_TennisBall","SW_P06_IntoVoid"]]
paths += ["/Game/InfinityStage/Audio/PassageMusic/Cameron_20261005/" + n for n in ["SW_P01_Walking1_Cameron","SW_P02_Walking2_Cameron","SW_P03_Walking3_Cameron","SW_P04_Walking4_pad10_Cameron","SW_P05_Walking5_Cameron"]]
out = []
for p in paths:
    a = unreal.EditorAssetLibrary.load_asset(p)
    d = a.get_editor_property("duration") if a else None
    out.append("%s=%s" % (p.split("/")[-1], ("%.3f" % d) if d is not None else "MISSING"))
unreal.log("AUDIO_DUR_PROBE_OK|" + ";".join(out))
