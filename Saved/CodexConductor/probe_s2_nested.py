import unreal
seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_02")
out = {"playback": [seq.get_playback_start(), seq.get_playback_end()], "subs": [], "root_tracks": []}
for t in seq.get_tracks():
    out["root_tracks"].append((t.get_class().get_name(), str(t.get_display_name())))
    if t.get_class().get_name() in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
        for s in t.get_sections():
            sq = s.get_sequence()
            out["subs"].append((str(t.get_display_name()), sq.get_path_name() if sq else None, s.get_start_frame(), s.get_end_frame(), s.is_active()))
unreal.log("PROBE_S2NEST|%s" % out)
