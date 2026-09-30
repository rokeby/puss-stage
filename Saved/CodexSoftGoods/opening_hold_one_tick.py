"""The Opening's HOLD and PILE on a ONE-TICK window (30 Sep). The fix belongs with the re-import of a passing bake.

LS_Opening_Curtain_Baked holds the drape with two looping GeometryCache sections:
  - HOLD (0-25), end offset = duration - one DISPLAY frame (960 ticks at 25 fps);
  - PILE (300-375), start offset the same.
A one-display-frame window lets the evaluated time wander up to 0.04 s between cache samples. The bench logged
0.03999 at frame 10, and on a cloth still moving it flickers: part of Gary's "weirdly bouncy". A ONE-TICK window
shows exactly one sample: the first for HOLD, the last for PILE. That is the rule fit_transition_drapes.py already
uses. FALL is not touched.

Guards: no PIE; no dirty CONTENT (a dirty map is tolerated and never saved); exactly one drape binding with exactly
the three sections. Backs up the .uasset to Backups/PreOpeningOneTick-<ts>/. Saves ONLY this sequence, and reads it
back. Logs PUSS_SOFTGOODS_OPENING_ONE_TICK|ok=...
"""
import datetime
import json
import os
import shutil

import unreal

SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked"
DRAPE = "Opening Drape (baked)"
GC = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"


def main():
    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
    report = {"ok": False}

    def finish(msg):
        report["message"] = msg
        with open(os.path.join(here, "opening_hold_one_tick.json"), "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(f"PUSS_SOFTGOODS_OPENING_ONE_TICK|ok={report['ok']}|{msg}")

    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        return finish("PIE is running")
    content = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if content:
        return finish(f"refusing: dirty content {content}")
    seq = unreal.load_asset(SEQ)
    cache = unreal.load_asset(GC)
    tick = seq.get_tick_resolution()
    dur_ticks = int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / 30.0
                          * tick.numerator / tick.denominator))
    drapes = [b for b in seq.get_bindings() if str(b.get_display_name()) == DRAPE]
    if len(drapes) != 1:
        return finish(f"expected one '{DRAPE}' binding, found {len(drapes)}")
    tracks = [t for t in drapes[0].get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"]
    secs = sorted(tracks[0].get_sections(), key=lambda s: s.get_start_frame()) if len(tracks) == 1 else []
    if len(secs) != 3:
        return finish(f"expected one GC track with 3 sections, found {len(tracks)} tracks / {len(secs)} sections")

    def offs(s):
        p = s.get_editor_property("params")
        return [p.get_editor_property("start_frame_offset").value, p.get_editor_property("end_frame_offset").value]

    report["before"] = [[s.get_start_frame(), s.get_end_frame()] + offs(s) for s in secs]
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreOpeningOneTick-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", "InfinityStage", "Interactions", "LS_Opening_Curtain_Baked.uasset"), backup)
    report["backup"] = backup
    hold, fall, pile = secs
    for s, start_off, end_off in ((hold, 0, dur_ticks - 1), (pile, dur_ticks - 1, 0)):
        p = s.get_editor_property("params")
        p.set_editor_property("start_frame_offset", unreal.FrameNumber(start_off))
        p.set_editor_property("end_frame_offset", unreal.FrameNumber(end_off))
        s.set_editor_property("params", p)
    now = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if now != [SEQ]:
        return finish(f"unexpected dirty content {now}; NOTHING saved (backup {backup})")
    report["saved"] = unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False)
    report["after"] = [[s.get_start_frame(), s.get_end_frame()] + offs(s) for s in secs]
    want = [[report["before"][0][0], report["before"][0][1], 0, dur_ticks - 1], report["before"][1],
            [report["before"][2][0], report["before"][2][1], dur_ticks - 1, 0]]
    report["dur_ticks"] = dur_ticks
    report["ok"] = bool(report["saved"]) and report["after"] == want and not [
        p for p in (q.get_path_name() for q in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
    del seq, cache, drapes, tracks, secs, hold, fall, pile
    finish(f"before={report['before']}|after={report['after']}|backup={backup}")


main()
