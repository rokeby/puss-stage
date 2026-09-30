"""Re-key the practicals' strike in LS_S4_HangarFold (Gary, 29 Sep: "light the fold").
Three beats:
1. Arrive in near-dark, ghost light only.
2. The practicals strike: a wave from WAVE_START, one pair every 0.3 s, each
   ramping 0 -> 400 cd over 0.2 s.
3. The lit rig lifts itself: the walls rise from 4 s carrying their lamps, so
   the beams sweep.

Only the 14 practical intensity tracks change; the hinge keys are untouched.
Each lamp's current keys are recorded first, so FOLD_RELIGHT_REVERT restores
them exactly. Dry run: FOLD_RELIGHT_DRY_RUN. Saves the sequence only.
Refuses on PIE, dirty state, or the sequence open in Sequencer. Lean: all work
in main().
"""
import json
import os

import unreal

SEQ = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "scene4_fold_relight_record.json")
FPS = 30
WAVE_START, WAVE_STEP, RAMP, CD = 2.0, 0.3, 0.2, 400.0


def fail(message):
    raise RuntimeError(f"FOLD_RELIGHT_FAILED|{message}")


def lamp_channels(seq):
    """{actor label: intensity channel} for the practical lamps, via their actor bindings."""
    out = {}
    for b in seq.get_bindings():
        name = str(b.get_display_name())
        if not name.startswith("S4 Practical ") or name.endswith("Body"):
            continue
        for child in b.get_child_possessables():
            for track in child.get_tracks():
                if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == "Intensity":
                    out[name] = track.get_sections()[0].get_all_channels()[0]
    return out


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("editor already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("a sequence is open in Sequencer; close it first")
    seq = unreal.EditorAssetLibrary.load_asset(SEQ)
    if not seq:
        fail("fold sequence missing")
    chans = lamp_channels(seq)
    if len(chans) != 14:
        fail(f"found {len(chans)} practical intensity tracks, expected 14")
    def seconds(key):
        # Explicit display-rate frames (30 fps): the default unit is display rate,
        # and dividing it by the tick rate read 9.0 s as 0.0112 s (29 Sep dry run).
        return key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value / FPS

    current = {n: [[round(seconds(k), 4), k.get_value()] for k in ch.get_keys()] for n, ch in chans.items()}
    if globals().get("FOLD_RELIGHT_REVERT"):
        want = json.load(open(RECORD, encoding="utf-8"))["before"]
    else:
        lamps = sorted(chans, key=lambda n: (int(n.split()[2][1:]), n))   # L1,R1,L2,R2...: one pair per step
        want = {}
        for i, n in enumerate(lamps):
            t = WAVE_START + (i // 2) * WAVE_STEP
            want[n] = [[0.0, 0.0], [t, 0.0], [round(t + RAMP, 4), CD]]
        # The record keeps the ORIGINAL keys: written once, never overwritten by a
        # later run (which would otherwise record the relit keys as "before").
        if not os.path.exists(RECORD):
            with open(RECORD, "w", encoding="utf-8") as fh:
                json.dump({"before": current, "after": want}, fh, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
    unreal.log(f"FOLD_RELIGHT_PLAN|lamps={len(want)}|first={sorted(want.items())[0]}")
    if globals().get("FOLD_RELIGHT_DRY_RUN"):
        unreal.log(f"FOLD_RELIGHT_DRY_RUN_OK|current={sorted(current.items())[0]}|mutated=0")
        return "dry"
    seq.modify()
    for n, ch in chans.items():
        for k in list(ch.get_keys()):
            ch.remove_key(k)
        for t, v in want[n]:
            ch.add_key(unreal.FrameNumber(int(round(t * FPS))), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                       interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    got = {n: [[round(seconds(k), 4), k.get_value()] for k in ch.get_keys()] for n, ch in lamp_channels(seq).items()}
    bad = [n for n in want if [[round(a, 2), round(b, 1)] for a, b in got[n]] != [[round(a, 2), round(b, 1)] for a, b in want[n]]]
    if bad:
        fail(f"keys did not land as planned, NOT saved: {bad[:3]} {got[bad[0]]}")
    dirty = {str(p).split("'")[1].split(".")[0] if "'" in str(p) else str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    if dirty - {SEQ} or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail(f"out-of-scope dirty: {dirty}")
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        fail("sequence save failed")
    unreal.log(f"FOLD_RELIGHT_OK|mode={'revert' if globals().get('FOLD_RELIGHT_REVERT') else 'relight'}|lamps={len(want)}|saved=sequence")
    return "applied"


result = main()
