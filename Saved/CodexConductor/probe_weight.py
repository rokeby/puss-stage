import unreal
seq = unreal.load_asset("/Game/Scenes/LS_Clams")
out = []
for b in seq.get_bindings():
    for t in b.get_tracks():
        if t.get_class().get_name() == "MovieSceneSkeletalAnimationTrack":
            s = t.get_sections()[0]
            out = [(c.get_name(), type(c).__name__, len(c.get_keys()), c.get_default() if hasattr(c, "get_default") else None) for c in s.get_all_channels()]
            out.append(("range_disp", s.get_start_frame(), s.get_end_frame()))
            break
    if out: break
unreal.log("PROBE_WEIGHT|%s" % out)
