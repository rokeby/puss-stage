"""Set every Location.Z key of S3 Shot B07's S3.VampOrbit track to a value (Gary 8 Oct: "make the Z height 195").
Args s3_orbit_z_args.json {"run":..,"z":195.0}.  Record + backup; saves LS_DevScene_03 only.  S3ORBITZ_OK / S3ORBITZ_FAILED."""
import json
import os
import shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UA = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
def main():
    import unreal
    a = json.load(open(HERE + "s3_orbit_z_args.json"))
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("DIRTY|%s" % dirty())
    seq = unreal.load_asset(SC)
    ch = None
    for b in seq.get_bindings():
        if str(b.get_display_name()) == "S3 Shot B07":
            for t in b.get_tracks():
                if str(t.get_display_name()) == "S3.VampOrbit":
                    for c in t.get_sections()[0].get_all_channels():
                        if str(c.get_name()).startswith("Location.Z"):
                            ch = c
    if ch is None or ch.get_num_keys() < 721:      # Gary added 2 keys by hand (723 on 8 Oct)
        raise RuntimeError("CHANNEL")
    before = sorted(set(round(k.get_value(), 3) for k in ch.get_keys()))
    json.dump({"run": a["run"], "z_before": before}, open(HERE + "s3_orbit_z_record_%s.json" % a["run"], "w"))
    bd = "E:/PussStage/Backups/PreS3OrbitZ-%s" % a["run"]
    os.makedirs(bd)
    shutil.copy2(UA, bd)
    seq.modify()
    for k in ch.get_keys():
        k.set_value(float(a["z"]))
    if sorted(set(round(k.get_value(), 3) for k in ch.get_keys())) != [round(float(a["z"]), 3)] or dirty() != [SC]:
        raise RuntimeError("READBACK_OR_CENSUS|NOTHING SAVED; Don't-Save restart")
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3ORBITZ_OK|run=%s|z %s -> %s" % (a["run"], before, a["z"]))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3ORBITZ_FAILED|%r" % (exc,))
