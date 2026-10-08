def main():
    import unreal
    seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03")
    out = []
    for b in seq.get_bindings():
        if str(b.get_display_name()) != "S3 Shot B06":
            continue
        for t in b.get_tracks():
            for s in t.get_sections():
                bt = s.get_blend_type()
                out.append([t.get_class().get_name(), str(bt), [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None],
                            [c.get_num_keys() for c in s.get_all_channels()][:3]])
    unreal.log("PROBE_B06S_OK|%s" % out)
main()
