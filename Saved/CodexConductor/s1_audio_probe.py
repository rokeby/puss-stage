"""READ-ONLY (6 Oct): list every audio section in LS_DevScene_01 and its nested sub/shot sequences (depth <= 3), with
the outer-time placement, so the clip that pre-existed the S1 narration can be identified. Writes nothing, saves nothing.
Marker S1_AUDIO_PROBE_OK|run=..|n=..  -> s1_audio_probe.json"""
import datetime
import json

import unreal

SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
OUT = "E:/PussStage/Saved/CodexConductor/s1_audio_probe.json"
RUN = datetime.datetime.now().strftime("S1AP-%Y%m%d-%H%M%S")


def secs(seq, frame_display):
    r = seq.get_display_rate()
    return float(frame_display) * r.denominator / r.numerator


def walk(seq, offset_s, depth, path, rows):
    tracks = list(seq.get_tracks())
    for b in seq.get_bindings():
        tracks += [(t, str(b.get_display_name())) for t in b.get_tracks()]
    for item in tracks:
        t, owner = item if isinstance(item, tuple) else (item, "")
        cls = t.get_class().get_name()
        for s in t.get_sections():
            try:
                st = secs(seq, s.get_start_frame()) if s.has_start_frame() else None
                en = secs(seq, s.get_end_frame()) if s.has_end_frame() else None
            except Exception as e:  # noqa: BLE001
                st, en = "ERR %s" % e, None
            if isinstance(s, unreal.MovieSceneAudioSection):
                snd = s.get_sound()
                rows.append({"path": path, "track": str(t.get_display_name()), "owner": owner, "cls": cls,
                             "sound": snd.get_path_name() if snd else None,
                             "sound_s": float(snd.get_editor_property("duration")) if snd else None,
                             "start_s_local": st, "end_s_local": en,
                             "start_s_scene": (offset_s + st) if isinstance(st, float) else None,
                             "end_s_scene": (offset_s + en) if isinstance(en, float) else None,
                             "active": bool(s.is_active()), "muted": bool(t.is_eval_disabled()) if hasattr(t, "is_eval_disabled") else None})
            elif isinstance(s, unreal.MovieSceneSubSection) and depth < 3:
                sub = s.get_sequence()
                if sub is None or not isinstance(st, float):
                    continue
                try:
                    so = float(s.get_editor_property("parameters").get_editor_property("start_frame_offset").value)
                except Exception:  # noqa: BLE001
                    so = 0.0
                walk(sub, offset_s + st, depth + 1, path + " > " + sub.get_name(), rows)


def main():
    seq = unreal.load_asset(SEQ)
    rows = []
    walk(seq, 0.0, 0, seq.get_name(), rows)
    out = {"run": RUN, "scene_end_s": float(seq.get_playback_end_seconds()),
           "scene_start_s": float(seq.get_playback_start_seconds()), "audio": rows}
    with open(OUT, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str)
    unreal.log("S1_AUDIO_PROBE_OK|run=%s|n=%d|out=%s" % (RUN, len(rows), OUT))


main()
