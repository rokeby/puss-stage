"""One-off (9 Oct): S2ARRIVAL-20261009-4 saved, then READBACK refused because add_possessable on Humo_Par4 returned
the existing strike binding and renamed it 'S2 Exit Hide: Humo_Par4'.  Restore the name 'S2 Arrival Strike: Humo_Par4'
(its two visibility tracks stay: hidden [0,376) and [3300, END)).  Saves LS_DevScene_02.  S2HUMO_OK / _FAILED."""
def main():
    import unreal
    seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_02")
    lib = unreal.EditorLoadingAndSavingUtils
    hits = [b for b in seq.get_bindings() if str(b.get_display_name()) == "S2 Exit Hide: Humo_Par4"]
    if len(hits) != 1: raise RuntimeError("HITS|%d" % len(hits))
    b = hits[0]
    tracks = [[int(s.get_start_frame()), int(s.get_end_frame())] for t in b.get_tracks() for s in t.get_sections()]
    b.set_display_name("S2 Arrival Strike: Humo_Par4")
    c = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if c != (["/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"], []): raise RuntimeError("CENSUS|%s" % (c,))
    if not unreal.EditorAssetLibrary.save_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_02", only_if_is_dirty=False): raise RuntimeError("SAVE")
    unreal.log("S2HUMO_OK|sections=%s" % tracks)
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S2HUMO_FAILED|%r" % (exc,))
