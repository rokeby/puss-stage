"""READ-ONLY asset read (safe during PIE): LS_DevScene_01 sub-sections (range, start offset, time scale text) and
LS_S1_HangarRise root/roof/lattice transform key times+values (rotation channels). Marker PROBE_S1_FOLD_OK."""
import json
def main():
    import unreal
    out = {"subs": [], "rise": {}}
    seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_01")
    for mt in seq.get_tracks():
        for s in mt.get_sections():
            if not hasattr(s, "get_sequence"):
                continue
            sub = s.get_sequence()
            p = s.get_editor_property("parameters")
            out["subs"].append({"track": str(mt.get_display_name()), "sub": sub.get_name() if sub else None,
                                "range": [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None],
                                "start_offset": int(p.get_editor_property("start_frame_offset").value),
                                "timescale": str(p.get_editor_property("time_scale"))[:120], "active": s.is_active()})
    rise = unreal.load_asset("/Game/InfinityStage/RigAtmos/LS_S1_HangarRise")
    out["rise_fps"] = rise.get_display_rate().numerator
    for b in rise.get_bindings():
        nm = str(b.get_display_name())
        if not any(w in nm for w in ("Root", "Roof", "Lattice", "Hinge")):
            continue
        for t in b.get_tracks():
            if t.get_class().get_name() != "MovieScene3DTransformTrack":
                continue
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    ks = [(int(k.get_time().frame_number.value), round(float(k.get_value()), 3)) for k in ch.get_keys()]
                    if ks and len(set(v for _, v in ks)) > 1:
                        out["rise"]["%s|%s" % (nm, ch.get_name())] = ks
    unreal.log("PROBE_S1_FOLD_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_S1_FOLD_FAILED|%r" % (exc,))
