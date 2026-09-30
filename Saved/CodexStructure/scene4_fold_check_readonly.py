"""Read-only, one line: is the Scene 4 fold CLIPPED by its speed dial?

Gary's dial is the "Hangar Fold" section's Time Scale in LS_DevScene_04. Dragging
it without re-running scene4_fold_nest.py leaves the section and the Scene at
their old lengths, so a slower fold is cut off silently. This reads the live Time
Scale and reports:
- OK: the whole fold, including its hold, fits the section and the Scene.
- HOLD CUT: the motion (lattice landed at 22.5 s) still fits, but part of the
  final hold is lost.
- CLIPPED: the motion itself is cut.
It ends with the exact fix: run scene4_fold_nest.py, which keeps whichever
sequence Scene 4 plays (v1 fold or v2 rise) and re-derives everything from the dial.
Mutates nothing. Lean: all work in main().
"""
import unreal

SCENE4 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
MOTION_END_S = {"LS_S4_HangarFold": 22.5, "LS_S4_HangarRise": 28.5}   # the last moving key, per sequence


def main():
    scene = unreal.load_asset(SCENE4)
    tracks = [t for t in scene.find_tracks_by_type(unreal.MovieSceneSubTrack) if str(t.get_display_name()) == "Hangar Fold"]
    if not tracks or not tracks[0].get_sections():
        unreal.log("S4_FOLD_CHECK|NOT NESTED|run scene4_fold_nest.py")
        return
    sec = tracks[0].get_sections()[0]
    fold = sec.get_sequence()
    scale = float(unreal.MovieSceneTimeWarpExtensions.conv_time_warp_variant_to_play_rate(
        sec.get_editor_property("parameters").get_editor_property("time_scale")))
    fold_len = fold.get_playback_end_seconds() - fold.get_playback_start_seconds()
    need_all, need_motion = fold_len / scale, MOTION_END_S.get(fold.get_name(), fold_len) / scale
    have = min(sec.get_end_frame_seconds(), scene.get_playback_end_seconds())
    state = "OK" if have >= need_all - 0.02 else ("HOLD CUT" if have >= need_motion - 0.02 else "CLIPPED")
    fix = "" if state == "OK" else "|FIX: run scene4_fold_nest.py (it resizes the section, the Scene and its cuts, then rebuilds the Master)"
    unreal.log(f"S4_FOLD_CHECK|{state}|sequence={fold.get_name()}|time_scale={scale:.3f}|needs={need_all:.2f}s (motion {need_motion:.2f}s)"
               f"|section_end={sec.get_end_frame_seconds():.2f}s|scene_end={scene.get_playback_end_seconds():.2f}s{fix}")


main()
