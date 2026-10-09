"""READ-ONLY: per crowd figure in LS_Clams: visibility keys, animation sections (range, active, start/end offset in
seconds, rate, reverse), additive sections.  probe_crowd_tracks.json.  PROBE_CROWDTR_OK / _FAILED."""
import json


def main():
    import unreal as u
    clams = u.load_asset("/Game/Scenes/LS_Clams")
    tick = clams.get_tick_resolution(); tps = float(tick.numerator) / float(tick.denominator)
    out = {}
    binds = list(clams.get_bindings())
    for b in binds:
        n = str(b.get_display_name())
        par = b.get_parent()
        owner = str(par.get_display_name()) if par is not None else n
        if not (owner.startswith("S3 Crowd") or owner.startswith("Shore0")): continue
        row = out.setdefault(owner, {"vis": [], "anim": [], "xform": []})
        for t in b.get_tracks():
            if isinstance(t, u.MovieSceneVisibilityTrack):
                for s in t.get_sections():
                    ch = list(s.get_all_channels())[0]
                    row["vis"].append({"prop": str(t.get_property_name()), "range": [int(s.get_start_frame()) if s.has_start_frame() else None, int(s.get_end_frame()) if s.has_end_frame() else None],
                                       "default": ch.get_default() if ch.has_default() else None,
                                       "keys": [[int(k.get_time().frame_number.value), bool(k.get_value())] for k in ch.get_keys()]})
            elif isinstance(t, u.MovieSceneSkeletalAnimationTrack):
                for s in t.get_sections():
                    p = s.get_editor_property("params"); r = p.get_editor_property("play_rate")
                    rate = float(r.to_fixed_play_rate()) if hasattr(r, "to_fixed_play_rate") else float(r)
                    a = p.get_editor_property("animation")
                    row["anim"].append({"name": str(s.get_name()), "range": [int(s.get_start_frame()) if s.has_start_frame() else None, int(s.get_end_frame()) if s.has_end_frame() else None],
                                        "active": bool(s.is_active()), "in_s": round(p.get_editor_property("start_frame_offset").value / tps, 3),
                                        "end_off_s": round(p.get_editor_property("end_frame_offset").value / tps, 3), "rate": round(rate, 4),
                                        "reverse": bool(p.get_editor_property("reverse")), "len_s": round(float(a.get_play_length()), 2) if a else None,
                                        "row": int(s.get_row_index())})
            elif isinstance(t, u.MovieScene3DTransformTrack):
                for s in t.get_sections():
                    bt = s.get_blend_type()
                    row["xform"].append({"name": str(s.get_name()), "blend": str(bt.get_editor_property("blend_type")) if bt.get_editor_property("is_valid") else "UNSET",
                                         "range": [int(s.get_start_frame()) if s.has_start_frame() else None, int(s.get_end_frame()) if s.has_end_frame() else None]})
    json.dump(out, open("E:/PussStage/Saved/CodexConductor/probe_crowd_tracks.json", "w"), indent=1)
    u.log("PROBE_CROWDTR_OK|figures=%d" % len(out))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("PROBE_CROWDTR_FAILED|%r" % (exc,))
