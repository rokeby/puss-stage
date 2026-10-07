"""S3 marker set (Gary 7 Oct: keep ONE set, the section markers 'S3 1-7'; restore VampStart). LS_DevScene_03 only.
Args s3_markers_fix_args.json {"mode": "DRY"|"APPLY", "confirm": "APPLY S3MARKERS", "run": "..."}.
APPLY: record (before list) first, .uasset backup, delete every marker whose label starts 'S3 B', add the three missing
markers, save ONLY LS_DevScene_03, read back. Markers S3MARKERS_<MODE>_OK|run= / S3MARKERS_FAILED|run=|reason."""
import json
import os
import shutil

SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UASSET = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
HERE = "E:/PussStage/Saved/CodexConductor/"
ADD = [(2880, "S3 5 Chorus / Puss takes the song (narration)"), (3480, "InfinityStage.VampStart"),
       (5520, "S3 7 Finish / out")]                      # display frames; labels exactly as in the 14:58 snapshot


def main():
    import unreal
    a = json.load(open(HERE + "s3_markers_fix_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = [p.get_name() for p in lib.get_dirty_content_packages()] + [p.get_name() for p in lib.get_dirty_map_packages()]
    if dirty:
        raise RuntimeError("DIRTY_AT_START|%s" % dirty)
    seq = unreal.load_asset(SEQ)
    ext = unreal.MovieSceneSequenceExtensions
    tpf = int(round(seq.get_tick_resolution().numerator / float(seq.get_display_rate().numerator)))

    def marks():
        return [(int(m.frame_number.value), str(m.label)) for m in ext.get_marked_frames(seq)]

    before = marks()
    dele = [m for m in before if m[1].startswith("S3 B")]
    have = {l for _f, l in before}
    add = [(f * tpf, l) for f, l in ADD if l not in have]
    plan = {"run": run, "tpf": tpf, "before": before, "delete": dele, "add": add}
    if mode == "DRY":
        json.dump(plan, open(HERE + "s3_markers_fix_dry.json", "w", encoding="utf-8"), indent=1)
        unreal.log("S3MARKERS_DRY_OK|run=%s|before=%d|delete=%d|add=%d" % (run, len(before), len(dele), len(add)))
        return
    if a.get("confirm") != "APPLY S3MARKERS":
        raise RuntimeError("CONFIRM")
    rec = HERE + "s3_markers_fix_record.json"
    if os.path.exists(rec):
        raise RuntimeError("RECORD_EXISTS")
    json.dump(plan, open(rec, "w", encoding="utf-8"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3Markers-%s" % run
    os.makedirs(bdir)
    shutil.copy2(UASSET, bdir)
    seq.modify()
    # get_marked_frames returns a SORTED copy; delete_marked_frame takes the INTERNAL index [meas 7 Oct: deleting by the
    # sorted index removed 'S3 1 Arrival' instead of 'S3 B01' at the same frame]. find_marked_frame_by_label gives the
    # internal index.
    for _f, lab in dele:
        idx = ext.find_marked_frame_by_label(seq, lab)
        if idx < 0:
            raise RuntimeError("NOT_FOUND|%s|NOTHING SAVED; Don't-Save restart" % lab)
        ext.delete_marked_frame(seq, idx)
    for f, l in add:
        m = unreal.MovieSceneMarkedFrame()
        m.set_editor_property("frame_number", unreal.FrameNumber(f))
        m.set_editor_property("label", l)
        ext.add_marked_frame(seq, m)
    after = marks()
    want = sorted([m for m in before if not m[1].startswith("S3 B")] + add)
    if sorted(after) != want:
        raise RuntimeError("READBACK|got=%s|want=%s|NOTHING SAVED; Don't-Save restart" % (sorted(after), want))
    dirty = [p.get_name() for p in lib.get_dirty_content_packages()] + [p.get_name() for p in lib.get_dirty_map_packages()]
    if dirty != [SEQ]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % dirty)
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        raise RuntimeError("SAVE_FAILED")
    seq2 = unreal.load_asset(SEQ)
    saved = sorted((int(m.frame_number.value), str(m.label)) for m in ext.get_marked_frames(seq2))
    if saved != want:
        raise RuntimeError("SAVED_READBACK|%s" % saved)
    plan.update(state="applied", after=saved, backup=bdir)
    json.dump(plan, open(rec, "w", encoding="utf-8"), indent=1)
    unreal.log("S3MARKERS_APPLY_OK|run=%s|deleted=%d|added=%d|now=%d|backup=%s" % (run, len(dele), len(add), len(saved), bdir))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3MARKERS_FAILED|%r" % (exc,))
