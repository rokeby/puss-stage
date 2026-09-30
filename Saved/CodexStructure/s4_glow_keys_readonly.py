"""READ-ONLY: the in-memory keys (and interpolation) of two glow and two practical Intensity channels in LS_S4_HangarRise.
Marker S4_GLOW_KEYS. Saves nothing."""
import unreal


def main():
    seq = unreal.load_asset("/Game/InfinityStage/RigAtmos/LS_S4_HangarRise")
    rate = seq.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    rows = []
    for b in seq.get_bindings():
        p = b.get_parent()
        pn = str(p.get_display_name()) if p and p.is_valid() else ""
        if pn not in ("S4 Lattice Glow 1-1", "S4 Lattice Glow 2-5", "S4 Practical L1", "S4 Practical R4"):
            continue
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieSceneFloatTrack):
                for s in t.get_sections():
                    for ch in s.get_all_channels():
                        ks = ch.get_keys()
                        rows.append(f"{pn}: " + ", ".join(f"({k.get_time().frame_number.value / fps:.4f},{k.get_value():.3f},{k.get_interpolation_mode()})" for k in ks))
    unreal.log("S4_GLOW_KEYS|" + " || ".join(rows))


main()
