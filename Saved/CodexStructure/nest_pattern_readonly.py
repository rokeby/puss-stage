"""Read-only: how LS_S4_HangarRise is nested in LS_DevScene_04 (track class, section range, parameters),
plus every Scene sequence's playback range and existing sub-tracks, and each rise sequence's playback range.
Mutates nothing."""
import json

import unreal


def secs(seq, frame):
    tick = seq.get_tick_resolution()
    return frame / (tick.numerator / tick.denominator)


def main():
    out = {}
    for n in range(1, 7):
        scene = unreal.load_asset(f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_0{n}")
        rise = unreal.load_asset(f"/Game/InfinityStage/RigAtmos/LS_S{n}_HangarRise")
        row = {"scene_playback_s": [round(scene.get_playback_start_seconds(), 3), round(scene.get_playback_end_seconds(), 3)],
               "scene_tick": str(scene.get_tick_resolution().numerator), "scene_display": str(scene.get_display_rate().numerator),
               "rise_playback_s": [round(rise.get_playback_start_seconds(), 3), round(rise.get_playback_end_seconds(), 3)] if rise else None,
               "subtracks": []}
        for tr in scene.get_tracks():
            if isinstance(tr, unreal.MovieSceneSubTrack):
                for sec in tr.get_sections():
                    s = sec.get_sequence()
                    p = sec.get_editor_property("parameters")
                    info = {"track": tr.get_class().get_name(), "track_name": str(tr.get_display_name()), "seq": s.get_name() if s else None,
                            "start_s": round(sec.get_start_frame_seconds(), 4), "end_s": round(sec.get_end_frame_seconds(), 4),
                            "row": sec.get_row_index()}
                    for k in ("start_frame_offset", "end_frame_offset", "time_scale", "hierarchical_bias", "flags", "can_loop"):
                        try:
                            v = p.get_editor_property(k)
                            info[k] = v.value if hasattr(v, "value") else str(v)
                        except Exception as exc:  # noqa: BLE001
                            info[k] = f"n/a"
                    try:
                        ev = sec.get_editor_property("eval_options")
                        info["completion"] = str(ev.get_editor_property("completion_mode"))
                    except Exception:  # noqa: BLE001
                        pass
                    row["subtracks"].append(info)
        out[n] = row
    unreal.log("NEST_PATTERN|" + json.dumps(out))


main()
