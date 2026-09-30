"""READ-ONLY (30 Sep): do the Passage camera keys still sit inside their Passage sections on the Master?

Why: MovieSceneInfinityPassageTrack.cpp evaluates every camera channel (speed, offsets, rotation, look-ahead, focal,
focus) and both wing channels at ABSOLUTE Master time, and KeyPassageCameraPose keys at the absolute Master frame. The
Master rebuild (InfinityStageSequenceBuilderLibrary.cpp:298) moves a Passage section with SetRange, which does not move
keys; only the pinned frames are relative. So lengthening a Scene moves every later Passage section by the change and
leaves its keys where they were. The 29 Sep Scene 1 extension moved P02 onward by +195.8 s. This probe measures, for each
Passage section: its range, and per channel the key count, first and last key, and keys outside the section. Nothing is
modified or saved. Writes probe_passage_key_alignment.json and logs PUSS_SOFTGOODS_KEY_ALIGNMENT|...
Crash rules: everything inside main().
"""
import json
import os

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def main():
    out = os.path.join(HERE, "probe_passage_key_alignment.json")
    before_dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    tick = master.get_tick_resolution()
    rate = tick.numerator / tick.denominator
    labels = {str(c.get_editor_property("cue_guid")): str(c.get_editor_property("label"))
              for c in show.get_editor_property("cues")}
    rows = []
    for track in master.get_tracks():
        if "InfinityPassage" not in track.get_class().get_name():
            continue
        for sec in track.get_sections():
            guid = str(sec.get_editor_property("passage_guid"))
            start, end = sec.get_start_frame_seconds(), sec.get_end_frame_seconds()
            chans = []
            for ch in sec.get_all_channels():
                try:
                    keys = ch.get_keys()
                except Exception as e:  # noqa: BLE001
                    chans.append({"channel": str(ch.get_editor_property("channel_name")), "error": str(e)})
                    continue
                times = sorted(k.get_time(unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value / rate
                               for k in keys)
                vals = [round(float(k.get_value()), 3) for k in keys][:6]
                chans.append({"channel": str(ch.get_editor_property("channel_name")), "n": len(times),
                              "first_s": round(times[0], 3) if times else None,
                              "last_s": round(times[-1], 3) if times else None,
                              "before_start": sum(1 for t in times if t < start - 1e-3),
                              "after_end": sum(1 for t in times if t > end + 1e-3),
                              "first_minus_start_s": round(times[0] - start, 3) if times else None,
                              "values_head": vals})
            multi = [c for c in chans if c.get("n", 0) >= 2]
            rows.append({"passage": labels.get(guid, guid), "range_s": [round(start, 3), round(end, 3)],
                         "channels_with_keys": sum(1 for c in chans if c.get("n")),
                         "multi_key_channels": len(multi),
                         "keys_outside": sum(c.get("before_start", 0) + c.get("after_end", 0) for c in chans),
                         "pinned_relative_frames": [f.value for f in sec.get_editor_property("pinned_passage_frames")],
                         "channels": chans})
    rows.sort(key=lambda r: r["range_s"][0])
    after_dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    report = {"tick_rate": rate, "rows": rows, "dirty_before": before_dirty, "dirty_after": after_dirty}
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    summary = ";".join(f"{r['passage'][:12]}@{r['range_s']}:keyed={r['channels_with_keys']},multi={r['multi_key_channels']},"
                       f"outside={r['keys_outside']}" for r in rows)
    del show, master
    unreal.log(f"PUSS_SOFTGOODS_KEY_ALIGNMENT|{summary}|dirty_changed={before_dirty != after_dirty}")


main()
