"""Undo part of S3FLAME-20261008-062908: remove the 'S3.Flame' tracks it added to the strike/daylight rect lights
(S3 Strike *, S3 Daylight *), which Gary has OFF via the rise keys; their editor intensity was nonzero, so the tool
treated them as static lights.  Keeps the flame tracks on Gary's Warm Side2/3/4.  Saves LS_DevScene_03.
S3FLAMEFIX_OK|removed=.. / S3FLAMEFIX_FAILED."""
def main():
    import unreal
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
    if dirty() not in ([], [SC]):      # [SC] = left dirty by this script's own refused first run (modify only, no change)
        raise RuntimeError("DIRTY|%s" % dirty())
    seq = unreal.load_asset(SC)
    seq.modify()
    removed = []
    for b in list(seq.get_bindings()):
        p = b.get_parent()
        own = str(p.get_display_name()) if p is not None and p.is_valid() else ""
        if not ("S3 Strike" in own or "S3 Daylight" in own):
            continue
        for t in list(b.get_tracks()):
            if str(t.get_display_name()) == "S3.Flame":
                b.remove_track(t)
                removed.append(own)
    left = [str(t.get_display_name()) for b in seq.get_bindings() for t in b.get_tracks()
            if str(t.get_display_name()) == "S3.Flame" and (lambda p: (str(p.get_display_name()) if p is not None and p.is_valid() else ""))(b.get_parent()).replace("S3 Hangar Float Hold: ", "").startswith(("S3 Strike", "S3 Daylight"))]
    if len(removed) != 8 or left or dirty() != [SC]:
        raise RuntimeError("READBACK|removed=%s|left=%s|%s|NOTHING SAVED; Don't-Save restart" % (removed, left, dirty()))
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3FLAMEFIX_OK|removed=%s" % sorted(removed))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3FLAMEFIX_FAILED|%r" % (exc,))
