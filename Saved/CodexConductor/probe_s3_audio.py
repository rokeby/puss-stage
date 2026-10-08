"""READ-ONLY: audio tracks (with sound assets, ranges) in LS_DevScene_03, LS_Clams and the Master. Marker PROBE_S3_AUDIO_OK."""
import json
def main():
    import unreal
    out = {}
    for sp in ("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03", "/Game/Scenes/LS_Clams",
               "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"):
        seq = unreal.load_asset(sp)
        rows = []
        tracks = list(seq.get_tracks()) + [t for b in seq.get_bindings() for t in b.get_tracks()]
        for t in tracks:
            if "Audio" not in t.get_class().get_name():
                continue
            for s in t.get_sections():
                snd = None
                try:
                    snd = s.get_editor_property("sound")
                except Exception:
                    pass
                rows.append({"track": str(t.get_display_name()), "range": [s.get_start_frame() if s.has_start_frame() else None,
                             s.get_end_frame() if s.has_end_frame() else None], "active": s.is_active(), "muted": s.is_muted() if hasattr(s, "is_muted") else None,
                             "sound": snd.get_path_name() if snd else None,
                             "dur": snd.get_editor_property("duration") if snd else None})
        dr = seq.get_display_rate()
        out[sp.split("/")[-1]] = {"fps": dr.numerator / dr.denominator, "audio": rows}
    unreal.log("PROBE_S3_AUDIO_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_S3_AUDIO_FAILED|%r" % (exc,))
