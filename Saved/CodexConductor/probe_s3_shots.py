"""READ-ONLY: S3 shot map for lining shots/keys up with the audio. For LS_DevScene_03 and every nested (non-rise)
sequence: camera-cut sections (camera binding name, range), sub/shot sections (range, start offset), marked frames,
and per-binding key-time summaries for transform / animation / geometry-cache / skeletal tracks.
Writes probe_s3_shots.json; marker PROBE_S3_SHOTS_OK|run=.. / PROBE_S3_SHOTS_FAILED. No modify, no save."""
import json
import time

OUT = "E:/PussStage/Saved/CodexConductor/probe_s3_shots.json"


def main():
    import unreal
    run = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    lib = unreal.EditorLoadingAndSavingUtils
    c0 = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    ext = unreal.MovieSceneSequenceExtensions
    out = {"run": run, "seqs": {}}

    def fr(s, which):
        try:
            return (s.get_start_frame() if s.has_start_frame() else None) if which == 0 else (s.get_end_frame() if s.has_end_frame() else None)
        except Exception:
            return None

    def walk(seq, depth):
        if seq is None or depth > 3 or seq.get_path_name() in out["seqs"]:
            return
        dr = seq.get_display_rate()
        d = {"fps": dr.numerator / float(dr.denominator), "playback": [seq.get_playback_start(), seq.get_playback_end()],
             "markers": sorted((int(m.frame_number.value), str(m.label)) for m in ext.get_marked_frames(seq)),
             "cuts": [], "subs": [], "keyed": []}
        tpf = seq.get_tick_resolution().numerator / float(seq.get_tick_resolution().denominator) / d["fps"]
        d["markers"] = [(int(round(f / tpf)), l) for f, l in d["markers"]]
        bind_names = {}
        for b in seq.get_bindings():
            bind_names[str(b.get_id())] = str(b.get_display_name())
        subs_to_walk = []
        for mt in seq.get_tracks():
            cls = mt.get_class().get_name()
            for s in mt.get_sections():
                if cls == "MovieSceneCameraCutTrack":
                    cam = None
                    try:
                        cb = s.get_camera_binding_id()
                        g = cb.get_editor_property("guid")
                        gt = g.export_text()
                        cam = next((str(b.get_display_name()) for b in seq.get_bindings() if b.get_id().export_text() == gt), None)
                        if cam is None:
                            cam = "GUID_NOT_IN_THIS_SEQ(%s)" % gt
                    except Exception as e:
                        cam = "?%r" % e
                    d["cuts"].append({"track": str(mt.get_display_name()), "range": [fr(s, 0), fr(s, 1)], "camera": cam,
                                      "active": s.is_active()})
                elif cls in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
                    sub = s.get_sequence()
                    off = None
                    try:
                        off = int(s.get_editor_property("parameters").get_editor_property("start_frame_offset").value)
                    except Exception:
                        pass
                    d["subs"].append({"track": str(mt.get_display_name()), "range": [fr(s, 0), fr(s, 1)],
                                      "sub": sub.get_path_name() if sub else None, "start_offset_ticks": off,
                                      "active": s.is_active()})
                    if sub is not None and "HangarRise" not in sub.get_path_name():
                        subs_to_walk.append(sub)
        for b in seq.get_bindings():
            for t in b.get_tracks():
                cls = t.get_class().get_name()
                if cls not in ("MovieScene3DTransformTrack", "MovieSceneSkeletalAnimationTrack", "MovieSceneGeometryCacheTrack",
                               "MovieSceneSpawnTrack", "MovieSceneFloatTrack"):
                    continue
                if cls == "MovieSceneFloatTrack" and "Focal" not in str(t.get_display_name()):
                    continue
                for s in t.get_sections():
                    times = set()
                    for ch in s.get_all_channels():
                        try:
                            for k in ch.get_keys():
                                times.add(int(k.get_time().frame_number.value))
                        except Exception:
                            pass
                    row = {"b": str(b.get_display_name()), "track": str(t.get_display_name())[:40], "cls": cls,
                           "range": [fr(s, 0), fr(s, 1)], "n": len(times)}
                    if times:
                        ts = sorted(times)
                        row["first"], row["last"] = ts[0], ts[-1]
                        row["times"] = ts if len(ts) <= 24 else ts[:12] + ts[-12:]
                    if cls == "MovieSceneSkeletalAnimationTrack":
                        try:
                            p = s.get_editor_property("params")
                            row["anim"] = p.get_editor_property("animation").get_name() if p.get_editor_property("animation") else None
                            row["play_rate"] = p.get_editor_property("play_rate")
                        except Exception as e:
                            row["anim_err"] = repr(e)
                    d["keyed"].append(row)
        out["seqs"][seq.get_path_name()] = d
        for sub in subs_to_walk:
            walk(sub, depth + 1)

    walk(unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"), 0)
    c1 = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    out["census"] = [c0, c1]
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    unreal.log("PROBE_S3_SHOTS_OK|run=%s|seqs=%d|census_unchanged=%s" % (run, len(out["seqs"]), c0 == c1))


try:
    main()
except Exception as exc:
    import unreal, traceback
    unreal.log_error("PROBE_S3_SHOTS_FAILED|%r|%s" % (exc, traceback.format_exc()[-600:].replace("\n", " / ")))
