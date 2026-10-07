"""READ-ONLY: for LS_DevScene_01..06 (and their sub-sequences), list every track on a binding whose name contains
'Exposure' with section ranges and float keys, plus the Scene playback range. No writes, no save, no level open.
Writes Saved/CodexConductor/scene_exposure_weight_read.json; marker SCENE_EXPW_READ_OK|n=..."""
import json


def main():
    import unreal
    out = {}

    def rng(sec):
        r = {}
        try:
            r["start"] = sec.get_start_frame() if sec.has_start_frame() else None
            r["end"] = sec.get_end_frame() if sec.has_end_frame() else None
        except Exception as exc:
            r["err"] = repr(exc)
        return r

    def walk(seq, depth, offset_note, rows):
        for b in seq.get_bindings():
            name = str(b.get_display_name())
            if "exposure" not in name.lower():
                continue
            for t in b.get_tracks():
                tr = {"seq": seq.get_name(), "depth": depth, "via": offset_note, "binding": name,
                      "track": t.get_class().get_name(), "track_name": str(t.get_display_name()), "sections": []}
                for s in t.get_sections():
                    sd = rng(s)
                    sd["active"] = bool(s.is_active())
                    keys = []
                    for ch in s.get_all_channels():
                        try:
                            for k in ch.get_keys():
                                keys.append([k.get_time().frame_number.value, round(float(k.get_value()), 4)])
                        except Exception:
                            pass
                        try:
                            if ch.has_default():
                                sd["default"] = ch.get_default()
                        except Exception:
                            pass
                    sd["keys"] = keys
                    tr["sections"].append(sd)
                rows.append(tr)
        if depth > 2:
            return
        for t in seq.get_tracks():
            if isinstance(t, unreal.MovieSceneSubTrack) or t.get_class().get_name().endswith("SubTrack"):
                for s in t.get_sections():
                    sub = s.get_sequence() if hasattr(s, "get_sequence") else None
                    if sub:
                        r = rng(s)
                        walk(sub, depth + 1, "%s[%s,%s)" % (seq.get_name(), r.get("start"), r.get("end")), rows)

    for n in range(1, 7):
        path = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_%02d" % n
        seq = unreal.load_asset(path)
        rows = []
        walk(seq, 0, "root", rows)
        fr = seq.get_display_rate()
        out["S%d" % n] = {"playback": [seq.get_playback_start(), seq.get_playback_end()],
                          "display_rate": [fr.numerator, fr.denominator],
                          "tick_rate": seq.get_tick_rate().numerator if hasattr(seq, "get_tick_rate") else None,
                          "tracks": rows}
    p = "E:/PussStage/Saved/CodexConductor/scene_exposure_weight_read.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    unreal.log("SCENE_EXPW_READ_OK|n=%d|path=%s" % (sum(len(v["tracks"]) for v in out.values()), p))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("SCENE_EXPW_READ_FAILED|%r" % (exc,))
