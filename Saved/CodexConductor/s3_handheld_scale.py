"""Scale the B06 additive handheld section by a factor (Gary 8 Oct: "a bit too jittery, could be 40% less" -> 0.6).
Saves LS_DevScene_03.  S3HANDSCALE_OK / _FAILED."""
import shutil, os, time
def main():
    import unreal
    k_ = 0.6
    lib = unreal.EditorLoadingAndSavingUtils
    SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
    if [p.get_name() for p in lib.get_dirty_content_packages()]:
        raise RuntimeError("DIRTY")
    seq = unreal.load_asset(SC)
    secs = [s for b in seq.get_bindings() if str(b.get_display_name()) == "S3 Shot B06" for t in b.get_tracks()
            if t.get_class().get_name() == "MovieScene3DTransformTrack" for s in t.get_sections()
            if s.get_blend_type().get_editor_property("is_valid") and str(s.get_blend_type().get_editor_property("blend_type")).upper().find("ADDITIVE") >= 0]
    if len(secs) != 1:
        raise RuntimeError("SECTIONS|%d" % len(secs))
    bd = "E:/PussStage/Backups/PreS3HandScale-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    os.makedirs(bd)
    shutil.copy2("E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset", bd)
    seq.modify()
    n = 0
    for ch in secs[0].get_all_channels():
        for k in ch.get_keys():
            k.set_value(k.get_value() * k_)
            n += 1
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False):
        raise RuntimeError("SAVE")
    unreal.log("S3HANDSCALE_OK|x%s|keys=%d" % (k_, n))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3HANDSCALE_FAILED|%r" % (exc,))
