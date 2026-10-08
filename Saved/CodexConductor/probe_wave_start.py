import json
def main():
    import unreal
    seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03")
    out = {}
    for b in seq.get_bindings():
        for t in b.get_tracks():
            tn = str(t.get_display_name())
            if tn not in ("S3.WavesV3.Motion", "S3.WaveSlide", "S3.WaveSplit"):
                continue
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    ks = ch.get_keys()
                    if len(ks) < 5:
                        continue
                    vals = [(int(k.get_time().frame_number.value), round(k.get_value(), 2)) for k in ks[:6]]
                    if len(set(v for _, v in vals)) > 1:
                        out.setdefault(tn, {})[str(b.get_display_name())[:30] + "|" + str(ch.get_name())[:12]] = vals
    unreal.log("PROBE_WSTART_OK|" + json.dumps({k: dict(list(v.items())[:6]) for k, v in out.items()}))
main()
