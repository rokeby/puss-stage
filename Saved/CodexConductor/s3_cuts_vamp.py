"""Gary 8 Oct questionnaire: vamp follows the B07 orbit to the cello (VampStart 1440, VampEnd 2880; the transport reads
these labels, InfinityStageTransportController.cpp:32-33,201-202); B08 cut extended to 3:23 (4200-4872), B09 starts at
4872.  LS_DevScene_03 only; record + backup first; read back; saves the sequence only.
Args s3_cuts_vamp_args.json {"mode":"DRY"|"APPLY","run":..}.  Markers S3CV_<MODE>_OK / S3CV_FAILED."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UASSET = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
VAMP = {"InfinityStage.VampStart": (3480, 1440), "InfinityStage.VampEnd": (4200, 2880)}
CUTS = {"S3 Shot B08": ((4200, 4680), (4200, 4872)), "S3 Shot B09": ((4680, 5040), (4872, 5040))}


def main():
    import unreal
    a = json.load(open(HERE + "s3_cuts_vamp_args.json"))
    run, mode = a["run"], a["mode"]
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: [p.get_name() for p in lib.get_dirty_content_packages()]
    if dirty():
        raise RuntimeError("CONTENT_DIRTY|%s" % dirty())
    seq = unreal.load_asset(SEQ)
    ext = unreal.MovieSceneSequenceExtensions
    tpf = int(round(seq.get_tick_resolution().numerator / float(seq.get_display_rate().numerator)))
    marks = {str(m.label): int(m.frame_number.value) // tpf for m in ext.get_marked_frames(seq)}
    for l, (f, _t) in VAMP.items():
        if marks.get(l) != f:
            raise RuntimeError("VAMP_UNEXPECTED|%s|%s" % (l, marks.get(l)))
    binds = list(seq.get_bindings())
    cuts = {}
    for mt in seq.get_tracks():
        if mt.get_class().get_name() != "MovieSceneCameraCutTrack":
            continue
        for s in mt.get_sections():
            g = s.get_camera_binding_id().get_editor_property("guid").export_text()
            cam = next((str(b.get_display_name()) for b in binds if b.get_id().export_text() == g), None)
            if cam in CUTS and (s.get_start_frame(), s.get_end_frame()) == CUTS[cam][0]:
                cuts[cam] = s
    if sorted(cuts) != sorted(CUTS):
        raise RuntimeError("CUTS_NOT_FOUND|%s" % sorted(cuts))
    if mode == "DRY":
        unreal.log("S3CV_DRY_OK|run=%s|vamp=%s|cuts=%s" % (run, {l: marks[l] for l in VAMP}, {c: CUTS[c] for c in cuts}))
        return
    json.dump({"run": run, "vamp_before": {l: marks[l] for l in VAMP}, "cuts_before": {c: CUTS[c][0] for c in CUTS}},
              open(HERE + "s3_cuts_vamp_record_%s.json" % run, "w"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3CutsVamp-%s" % run
    os.makedirs(bdir)
    shutil.copy2(UASSET, bdir)
    seq.modify()
    for l, (_f, t) in VAMP.items():
        idx = ext.find_marked_frame_by_label(seq, l)
        if idx < 0:
            raise RuntimeError("NOT_FOUND|%s|NOTHING SAVED; Don't-Save restart" % l)
        ext.delete_marked_frame(seq, idx)
        m = unreal.MovieSceneMarkedFrame()
        m.set_editor_property("frame_number", unreal.FrameNumber(t * tpf))
        m.set_editor_property("label", l)
        ext.add_marked_frame(seq, m)
    # B09 start first (shrink), then B08 end (grow)
    cuts["S3 Shot B09"].set_range(*CUTS["S3 Shot B09"][1])
    cuts["S3 Shot B08"].set_range(*CUTS["S3 Shot B08"][1])
    marks2 = {str(m.label): int(m.frame_number.value) // tpf for m in ext.get_marked_frames(seq)}
    bad = [l for l, (_f, t) in VAMP.items() if marks2.get(l) != t] + \
          [c for c in CUTS if (cuts[c].get_start_frame(), cuts[c].get_end_frame()) != CUTS[c][1]]
    if bad or dirty() != [SEQ]:
        raise RuntimeError("READBACK_OR_CENSUS|%s|%s|NOTHING SAVED; Don't-Save restart" % (bad, dirty()))
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False) or dirty():
        raise RuntimeError("SAVE")
    unreal.log("S3CV_APPLY_OK|run=%s|vamp=1440-2880|B08=4200-4872|B09=4872-5040" % run)


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3CV_FAILED|%r" % (exc,))
