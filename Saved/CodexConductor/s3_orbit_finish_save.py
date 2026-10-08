"""One-off finish for S3SHOTS-20261008-034435APPLY (orbit-only): the orbit keys were written and read back in memory, the run
refused at CENSUS because rise.modify() dirtied LS_S3_HangarRise with no data change.  Verify the orbit centre is the new
clam, census is exactly {scene, rise}, then save both and read back.  Marker S3ORBITSAVE_OK / S3ORBITSAVE_FAILED."""
def main():
    import unreal
    lib = unreal.EditorLoadingAndSavingUtils
    SC, RI = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03", "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
    d = sorted(p.get_name() for p in lib.get_dirty_content_packages())
    m = [p.get_name() for p in lib.get_dirty_map_packages()]
    if d != sorted([SC, RI]) or m:
        raise RuntimeError("CENSUS|%s|%s" % (d, m))
    seq = unreal.load_asset(SC)
    xs = ys = None
    for b in seq.get_bindings():
        if str(b.get_display_name()) == "S3 Shot B07":
            for t in b.get_tracks():
                if str(t.get_display_name()) == "S3.VampOrbit":
                    for ch in t.get_sections()[0].get_all_channels():
                        n = str(ch.get_name())
                        if n.startswith("Location.X"):
                            xs = [k.get_value() for k in ch.get_keys()]
                        if n.startswith("Location.Y"):
                            ys = [k.get_value() for k in ch.get_keys()]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    if abs(cx - 15484.4) > 1 or abs(cy - 160169.5) > 1:
        raise RuntimeError("CENTRE|%.2f,%.2f" % (cx, cy))
    for p in (SC, RI):
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            raise RuntimeError("SAVE|%s" % p)
    if list(lib.get_dirty_content_packages()):
        raise RuntimeError("DIRTY_AFTER")
    unreal.log("S3ORBITSAVE_OK|centre=%.2f,%.2f|saved=scene+rise(unchanged data)" % (cx, cy))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3ORBITSAVE_FAILED|%r" % (exc,))
