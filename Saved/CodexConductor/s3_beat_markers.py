"""Gary 5 Oct ~19:25: lay the seven S3 beats into LS_DevScene_03 as named marked frames for him to key against
("Yes, with these times"; no audio placeholders). Markers only: nothing else in the sequence is touched.

Args s3_beat_markers_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S3BEATS"}.
APPLY: guards (no PIE, LS_DevScene_03 not already dirty, no existing "S3 <n> " marker) -> record of every existing
marker (fsync) + .uasset backup -> add 7 markers at playback start + t -> read back (all old markers unchanged, 7 new at
the planned ticks) -> the sequence must be the ONLY newly dirtied package -> save only it. Other packages that were
already dirty (Gary's own unsaved work) are left alone and never saved. REVERT deletes exactly the recorded new markers.
Marker S3_BEATS_<MODE>_OK|run=..
"""
import datetime
import json
import os
import re
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UASSET = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
REC = HERE + "s3_beat_markers_record.json"
BEATS = [(0.0, "S3 1 Arrival to shore"), (15.0, "S3 2 Swaying shore people"),
         (40.0, "S3 3 They whimper (narration)"), (70.0, "S3 4 Cello soothes / clam opens"),
         (120.0, "S3 5 Chorus / Puss takes the song (narration)"), (180.0, "S3 6 Anguished crying"),
         (230.0, "S3 7 Finish / out")]
OURS = re.compile(r"^S3 [1-7] ")
RUN = datetime.datetime.now().strftime("S3BEATS-%Y%m%d-%H%M%S")


def stop(msg):
    unreal.log_error("S3_BEATS_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def dirty():
    lib = unreal.EditorLoadingAndSavingUtils
    return sorted(p.get_name() for p in lib.get_dirty_content_packages()) + \
        sorted(p.get_name() for p in lib.get_dirty_map_packages())


def markers(seq):
    try:
        raw = seq.get_marked_frames()
    except Exception:  # noqa: BLE001
        raw = unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(
            seq, unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
    return [{"frame": int(m.get_editor_property("frame_number").value), "label": str(m.get_editor_property("label"))}
            for m in raw]


def main():
    a = json.load(open(HERE + "s3_beat_markers_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    if mode != "DRY" and a.get("confirm") != "%s S3BEATS" % mode:
        stop("CONFIRM_MISSING")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        stop("PIE_ACTIVE")
    seq = unreal.load_asset(SEQ)
    if seq is None:
        stop("SEQ_MISSING")
    tick = seq.get_tick_resolution()
    tps = float(tick.numerator) / float(tick.denominator)
    start_s = float(seq.get_playback_start_seconds())
    end_s = float(seq.get_playback_end_seconds())
    plan = [{"frame": int(round((start_s + t) * tps)), "label": lab, "t": t} for t, lab in BEATS]
    before = markers(seq)
    pre_dirty = dirty()
    unreal.log("S3_BEATS_PLAN|run=%s|%s" % (RUN, json.dumps({"tps": tps, "start_s": start_s, "end_s": end_s,
                                                              "existing": len(before), "plan": plan,
                                                              "dirty_before": pre_dirty})))
    if any(t > end_s - start_s for t, _ in BEATS):
        stop("BEAT_PAST_END|scene %.2f s" % (end_s - start_s))
    seq_pkg = SEQ
    if mode == "DRY":
        unreal.log("S3_BEATS_DRY_OK|run=%s|existing=%d|ours_present=%d|seq_dirty=%d"
                   % (RUN, len(before), sum(1 for m in before if OURS.match(m["label"])), int(seq_pkg in pre_dirty)))
        return
    if seq_pkg in pre_dirty:
        stop("SEQ_ALREADY_DIRTY|save or discard your own S3 edits first; this tool never saves them for you")
    if mode == "APPLY":
        if os.path.exists(REC) or any(OURS.match(m["label"]) for m in before):
            stop("ALREADY_APPLIED")
        backup = "E:/PussStage/Backups/PreS3BeatMarkers-" + RUN
        os.makedirs(backup)
        shutil.copy2(UASSET, backup)
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "before": before, "added": plan, "backup": backup}, h, indent=1)
            h.flush()
            os.fsync(h.fileno())
        for p in plan:
            mf = unreal.MovieSceneMarkedFrame()
            mf.set_editor_property("frame_number", unreal.FrameNumber(p["frame"]))
            mf.set_editor_property("label", p["label"])
            seq.add_marked_frame(mf)
        after = markers(seq)
        want = sorted([(m["frame"], m["label"]) for m in before] + [(p["frame"], p["label"]) for p in plan])
        if sorted((m["frame"], m["label"]) for m in after) != want:
            stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(after))
    else:
        if not os.path.exists(REC):
            stop("NO_RECORD")
        rec = json.load(open(REC, encoding="utf-8"))
        added = {(p["frame"], p["label"]) for p in rec["added"]}
        for i in sorted((i for i, m in enumerate(before) if (m["frame"], m["label"]) in added), reverse=True):
            seq.delete_marked_frame(i)
        after = markers(seq)
        if sorted((m["frame"], m["label"]) for m in after) != sorted((m["frame"], m["label"]) for m in rec["before"]):
            stop("REVERT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(after))
    new_dirty = sorted(set(dirty()) - set(pre_dirty))
    if new_dirty != [seq_pkg]:
        stop("DIRTY_SCOPE|new=%s|NOTHING SAVED; Don't-Save restart" % json.dumps(new_dirty))
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        stop("SAVE_FAILED")
    if seq_pkg in dirty():
        stop("POST_SAVE_DIRTY")
    if sorted(markers(unreal.load_asset(SEQ)), key=lambda m: (m["frame"], m["label"])) != \
            sorted(after, key=lambda m: (m["frame"], m["label"])):
        stop("POST_SAVE_READBACK")
    if mode == "REVERT":
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("S3_BEATS_%s_OK|run=%s|markers=%d|saved=LS_DevScene_03|others_left_dirty=%d"
               % (mode, RUN, len(after), len(pre_dirty)))


main()
