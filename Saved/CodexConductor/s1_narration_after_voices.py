"""Gary 6 Oct (relayed by Directing, then his own answer here: "Lengthen S1 by ~33 s"): in Scene 1 the pre-existing
clip (Animal_Voices_1, in LS_Animals_1, scene 12.29-208.63 s, s1_audio_probe.json) plays FIRST, then the stand-in
narration. This moves ONLY the "Narration (stand-in)" section of LS_DevScene_01 to start on the first display frame at
or after the voices end, keeping its length. Run AFTER S1 is extended (Saved/CodexSoftGoods/extend_scene_playback.py,
new_end_s 245.0): APPLY refuses if the narration would run past S1's playback end.

Args s1_narration_after_voices_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S1NARR"}.
Guards: no PIE, LS_DevScene_01 not already dirty. Record (fsync) + .uasset backup; read back; the sequence must be the ONLY
newly dirtied package; save only it (others' unsaved work is left alone). Marker S1_NARR_<MODE>_OK|run=..
"""
import datetime
import json
import math
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
UASSET = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_01.uasset"
REC = HERE + "s1_narration_after_voices_record.json"
TRACK = "Narration (stand-in)"
VOICES = "/Game/Scenes/Animal_Voices_1.Animal_Voices_1"
RUN = datetime.datetime.now().strftime("S1NARR-%Y%m%d-%H%M%S")


def stop(msg):
    unreal.log_error("S1_NARR_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def dirty():
    lib = unreal.EditorLoadingAndSavingUtils
    return sorted(p.get_name() for p in lib.get_dirty_content_packages()) + \
        sorted(p.get_name() for p in lib.get_dirty_map_packages())


def voices_end_s(seq):
    """Scene-time end of the Animal_Voices_1 section inside the S1 sub/shot sequences (depth 1), measured live."""
    r = seq.get_display_rate()
    fps = float(r.numerator) / r.denominator
    ends = []
    for t in seq.get_tracks():
        for s in t.get_sections():
            if not isinstance(s, unreal.MovieSceneSubSection) or s.get_sequence() is None:
                continue
            sub = s.get_sequence()
            sr = sub.get_display_rate()
            sfps = float(sr.numerator) / sr.denominator
            outer = s.get_start_frame() / fps
            inner0 = sub.get_playback_start_seconds()
            for st in sub.get_tracks():
                for a in st.get_sections():
                    if isinstance(a, unreal.MovieSceneAudioSection) and a.get_sound() and \
                            a.get_sound().get_path_name() == VOICES:
                        ends.append(outer + a.get_end_frame() / sfps - inner0)
    if len(ends) != 1:
        stop("VOICES_COUNT|%d" % len(ends))
    return ends[0], fps


def main():
    a = json.load(open(HERE + "s1_narration_after_voices_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    if mode != "DRY" and a.get("confirm") != "%s S1NARR" % mode:
        stop("CONFIRM_MISSING")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        stop("PIE_ACTIVE")
    seq = unreal.load_asset(SEQ)
    tracks = [t for t in seq.get_tracks() if str(t.get_display_name()) == TRACK]
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        stop("NARRATION_TRACK_SHAPE")
    sec = tracks[0].get_sections()[0]
    old = [int(sec.get_start_frame()), int(sec.get_end_frame())]
    v_end, fps = voices_end_s(seq)
    start = int(math.ceil(v_end * fps - 1e-6))
    new = [start, start + (old[1] - old[0])]
    end_s = float(seq.get_playback_end_seconds())
    plan = {"fps": fps, "voices_end_s": v_end, "old_frames": old, "new_frames": new,
            "new_s": [new[0] / fps, new[1] / fps], "scene_end_s": end_s,
            "overrun_s": max(0.0, new[1] / fps - end_s)}
    pre = dirty()
    unreal.log("S1_NARR_PLAN|run=%s|%s|dirty_before=%s" % (RUN, json.dumps(plan), json.dumps(pre)))
    if mode == "DRY":
        unreal.log("S1_NARR_DRY_OK|run=%s|overrun_s=%.3f|apply_ready=%d"
                   % (RUN, plan["overrun_s"], int(plan["overrun_s"] == 0 and SEQ not in pre)))
        return
    if SEQ in pre:
        stop("SEQ_ALREADY_DIRTY")
    if mode == "APPLY":
        if os.path.exists(REC):
            stop("RECORD_EXISTS")
        if plan["overrun_s"] > 0:
            stop("OVERRUN|%.3f s past S1's end: extend S1 first (extend_scene_playback new_end_s 245.0)" % plan["overrun_s"])
        backup = "E:/PussStage/Backups/PreS1NarrationAfterVoices-" + RUN
        os.makedirs(backup)
        shutil.copy2(UASSET, backup)
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "plan": plan, "backup": backup}, h, indent=1)
            h.flush()
            os.fsync(h.fileno())
        want = new
    else:
        if not os.path.exists(REC):
            stop("NO_RECORD")
        want = json.load(open(REC, encoding="utf-8"))["plan"]["old_frames"]
    sec.set_range(want[0], want[1])
    got = [int(sec.get_start_frame()), int(sec.get_end_frame())]
    if got != want:
        stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % got)
    newly = sorted(set(dirty()) - set(pre))
    if newly != [SEQ]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(newly))
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        stop("SAVE_FAILED")
    if SEQ in dirty():
        stop("POST_SAVE_DIRTY")
    if mode == "REVERT":
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("S1_NARR_%s_OK|run=%s|frames=%s|s=%.3f-%.3f|saved=LS_DevScene_01"
               % (mode, RUN, got, got[0] / fps, got[1] / fps))


main()
