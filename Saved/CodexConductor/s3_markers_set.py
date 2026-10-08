"""Remove/add named marked frames in LS_DevScene_03 (display frames @24).  Args s3_markers_set_args.json
{"mode":"DRY"|"APPLY","run":..,"remove":[labels],"add":[[frame,label],..],"why":..}.  Never touches InfinityStage.* markers.
Record + backup first; deletes by find_marked_frame_by_label; saves LS_DevScene_03 only.  S3MSET_<MODE>_OK / S3MSET_FAILED."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UASSET = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"


def main():
    import unreal
    a = json.load(open(HERE + "s3_markers_set_args.json"))
    run, mode = a["run"], a["mode"]
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("CONTENT_DIRTY|%s" % dirty())
    seq = unreal.load_asset(SEQ)
    ext = unreal.MovieSceneSequenceExtensions
    tpf = int(round(seq.get_tick_resolution().numerator / float(seq.get_display_rate().numerator)))
    marks = lambda s: sorted((int(m.frame_number.value) // tpf, str(m.label)) for m in ext.get_marked_frames(s))
    before = marks(seq)
    labels = [l for _, l in before]
    rem = a.get("remove", [])
    if (any(l.startswith("InfinityStage.") for l in rem) and not a.get("allow_infinitystage")) or any(l not in labels for l in rem):
        raise RuntimeError("REMOVE_INVALID|%s|have=%s" % (rem, labels))
    add = [(int(f), str(l)) for f, l in a.get("add", [])]
    if any(l in labels and l not in rem for _, l in add) or any(l.startswith("GO ") for _, l in add):
        raise RuntimeError("ADD_INVALID|%s" % add)
    want = sorted([m for m in before if m[1] not in rem] + add)
    if mode == "DRY":
        unreal.log("S3MSET_DRY_OK|run=%s|want=%s" % (run, want))
        return
    json.dump({"run": run, "args": a, "before": before}, open(HERE + "s3_markers_set_record_%s.json" % run, "w"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3MarkersSet-%s" % run
    os.makedirs(bdir)
    shutil.copy2(UASSET, bdir)
    seq.modify()
    for lab in rem:
        idx = ext.find_marked_frame_by_label(seq, lab)
        if idx < 0:
            raise RuntimeError("NOT_FOUND|%s|NOTHING SAVED; Don't-Save restart" % lab)
        ext.delete_marked_frame(seq, idx)
    for f, l in add:
        m = unreal.MovieSceneMarkedFrame()
        m.set_editor_property("frame_number", unreal.FrameNumber(f * tpf))
        m.set_editor_property("label", l)
        ext.add_marked_frame(seq, m)
    if marks(seq) != want or dirty() != [SEQ]:
        raise RuntimeError("READBACK_OR_CENSUS|%s|%s|NOTHING SAVED; Don't-Save restart" % (marks(seq), dirty()))
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3MSET_APPLY_OK|run=%s|now=%s" % (run, marks(unreal.load_asset(SEQ))))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3MSET_FAILED|%r" % (exc,))
