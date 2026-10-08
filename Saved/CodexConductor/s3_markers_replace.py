"""Gary 8 Oct: the audio markers (SCENEAUDIO-20261007-214457, 'S3 score in 0:00' ... 'S3 Puss takes clam 3:10') replace
the old section markers 'S3 1 ..' - 'S3 7 ..'.  InfinityStage.VampStart is KEPT: it is read by the transport
(InfinityStageTransportController.cpp).  LS_DevScene_03 only; record + backup first; deletes by find_marked_frame_by_label.
Args s3_markers_replace_args.json {"mode":"DRY"|"APPLY","run":..}.  Markers S3MREPL_<MODE>_OK / S3MREPL_FAILED."""
import json
import os
import re
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UASSET = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
OLD = re.compile(r"^S3 [1-7] ")


def main():
    import unreal
    a = json.load(open(HERE + "s3_markers_replace_args.json"))
    run, mode = a["run"], a["mode"]
    lib = unreal.EditorLoadingAndSavingUtils

    def dirty():
        return [p.get_name() for p in lib.get_dirty_content_packages()] + [p.get_name() for p in lib.get_dirty_map_packages()]
    if dirty():
        raise RuntimeError("DIRTY_AT_START|%s" % dirty())
    seq = unreal.load_asset(SEQ)
    ext = unreal.MovieSceneSequenceExtensions
    marks = lambda s: sorted((int(m.frame_number.value), str(m.label)) for m in ext.get_marked_frames(s))
    before = marks(seq)
    dele = [m for m in before if OLD.match(m[1])]
    if mode == "DRY":
        unreal.log("S3MREPL_DRY_OK|run=%s|delete=%s|keep=%s" % (run, [m[1] for m in dele], [m[1] for m in before if m not in dele]))
        return
    rec = HERE + "s3_markers_replace_record_%s.json" % run
    json.dump({"run": run, "before": before, "delete": dele}, open(rec, "w"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3MarkersReplace-%s" % run
    os.makedirs(bdir)
    shutil.copy2(UASSET, bdir)
    seq.modify()
    for _f, lab in dele:
        idx = ext.find_marked_frame_by_label(seq, lab)
        if idx < 0:
            raise RuntimeError("NOT_FOUND|%s|NOTHING SAVED; Don't-Save restart" % lab)
        ext.delete_marked_frame(seq, idx)
    want = sorted(m for m in before if m not in dele)
    if marks(seq) != want:
        raise RuntimeError("READBACK|NOTHING SAVED; Don't-Save restart")
    if dirty() != [SEQ]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % dirty())
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        raise RuntimeError("SAVE_FAILED")
    if marks(unreal.load_asset(SEQ)) != want or dirty():
        raise RuntimeError("SAVED_READBACK")
    unreal.log("S3MREPL_APPLY_OK|run=%s|deleted=%d|now=%s" % (run, len(dele), [m[1] for m in want]))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3MREPL_FAILED|%r" % (exc,))
