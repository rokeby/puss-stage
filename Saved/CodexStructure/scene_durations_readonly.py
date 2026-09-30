"""Read-only: each Scene cue's Show duration (the Master's timing authority) vs its Scene sequence's playback
range, and the compiled segment length. Mutates nothing."""
import unreal


def main():
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = {str(s.get_editor_property("label")): s for s in tr.get_editor_property("segments")}
    rows = []
    for c in show.get_editor_property("cues"):
        if c.get_editor_property("type") != unreal.InfinityCueType.SCENE:
            continue
        sc = c.get_editor_property("scene")
        seq = sc.get_editor_property("sequence")
        dur = sc.get_editor_property("duration_frames").value / rate
        label = str(c.get_editor_property("label"))
        seg = segs.get(label)
        seg_len = (seg.get_editor_property("end_frame").value - seg.get_editor_property("start_frame").value) / rate if seg else None
        rows.append(f"{label[:7]}: show_duration={dur:.3f}s segment={seg_len if seg_len is None else round(seg_len, 3)}s sequence={seq.get_name() if seq else None} "
                    f"playback={seq.get_playback_end_seconds() if seq else None}s")
    del tr
    unreal.log("SCENE_DURATIONS|" + " || ".join(rows))


main()
