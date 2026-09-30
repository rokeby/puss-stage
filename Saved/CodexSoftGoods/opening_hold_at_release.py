"""The Opening's HOLD at the RELEASE (30 Sep, conductor-approved on Gary's delegation): LS_Opening_Curtain_Baked freezes the
cache sample ONE FRAME BEFORE the release instead of its first sample, so nothing moves on screen before the fall.
This folds in the one-tick fix. APPLY ONLY WITH A SETTLED CACHE: the frozen frame must read as a curtain at rest.
final2's release-minus-one frame is arrested mid-sway (check_frozen_frames_at_rest_NOT_SHOW_FRAME.png).

Today: HOLD 0-25 loops a window at the first sample, FALL 25-300 plays the whole 11 s cache (release 1.0 s in, so on
frame 50 at 25 fps), and PILE 300-375 holds the end. After (the release stays on frame 50, as the old rig's lift did):
  HOLD  0 .. 49    a one-TICK window at cache time R - 1/30 s (R = release in cache, read from the cache's import chain)
  FALL  49 .. 299  starts at offset R - 1/30 s. It is 250 frames (10.0 s), so offset + length stays inside the 11.0 s
                   cache and it cannot LOOP (the guard refuses otherwise)
  PILE  299 .. 375 a one-tick window at the last sample
The camera cut and the spawn range are untouched.
Mode file opening_hold_at_release_mode.json: {"dry_run": true}. Guards: no PIE; no dirty content (a dirty map is
tolerated and never saved); exactly one drape binding with three GC sections. Backs up the .uasset first, saves ONLY
this sequence, and reads it back. Logs PUSS_SOFTGOODS_OPENING_HOLD_AT_RELEASE|ok=...
"""
import datetime
import json
import os
import shutil

import unreal

SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked"
DRAPE = "Opening Drape (baked)"
GC = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
CACHE_FPS = 30.0
RELEASE_DISPLAY_FRAME = 50       # where the release has always landed in this sequence (25 fps)


def release_in_cache_s(cache, bake_dir):
    """As fit_transition_drapes.py: trace the cache to its bake JSON through its import source; never assume."""
    src = os.path.basename(cache.get_editor_property("asset_import_data").get_first_filename())
    stem = GC.split("/")[-1] + "_"
    if src.startswith(stem) and src.endswith(".abc"):
        bake_id = src[len(stem):-4]
    elif src == "CurtainDrop_Opening_final2.abc":
        bake_id = "final2_stage_v2"
    else:
        raise RuntimeError(f"cannot trace {GC} to a bake: source {src}")
    with open(os.path.join(bake_dir, f"{bake_id}.json"), encoding="utf-8") as h:
        bake = json.load(h)
    return (bake["release_frame"] - bake["show_start"]) / CACHE_FPS, bake_id


def main():
    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
    with open(os.path.join(here, "opening_hold_at_release_mode.json"), encoding="utf-8") as h:
        dry = bool(json.load(h).get("dry_run", True))
    report = {"ok": False, "dry_run": dry}

    def finish(msg):
        report["message"] = msg
        with open(os.path.join(here, "opening_hold_at_release.json"), "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(f"PUSS_SOFTGOODS_OPENING_HOLD_AT_RELEASE|ok={report['ok']}|{msg}")

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        return finish("PIE is running")
    world = editor.get_editor_world().get_outermost().get_name()
    if world != "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice":                                   # two projects serve MCP here
        return finish(f"refusing: open world is {world}")
    content = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if content:
        return finish(f"refusing: dirty content {content}")
    seq = unreal.load_asset(SEQ)
    cache = unreal.load_asset(GC)
    try:
        release_s, bake_id = release_in_cache_s(cache, os.path.join(here, "DropBake"))
    except Exception as exc:  # noqa: BLE001
        return finish(f"refusing: {exc}")
    rate = seq.get_display_rate()
    fps = rate.numerator / rate.denominator
    tick = seq.get_tick_resolution()
    tps = tick.numerator / tick.denominator
    dur_ticks = int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / CACHE_FPS * tps))
    hold_off = int(round((release_s - 1.0 / CACHE_FPS) * tps))
    fall_start = RELEASE_DISPLAY_FRAME - 1
    fall_end = fall_start + int((dur_ticks - hold_off) / tps * fps)          # whole display frames that fit
    fall_end = min(fall_end, 300)
    if hold_off + int(round((fall_end - fall_start) / fps * tps)) > dur_ticks:
        return finish(f"refusing: FALL {fall_start}-{fall_end} from offset {hold_off} would overrun the cache and LOOP")
    drapes = [b for b in seq.get_bindings() if str(b.get_display_name()) == DRAPE]
    if len(drapes) != 1:
        return finish(f"expected one '{DRAPE}' binding, found {len(drapes)}")
    tracks = [t for t in drapes[0].get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"]
    secs = sorted(tracks[0].get_sections(), key=lambda s: s.get_start_frame()) if len(tracks) == 1 else []
    if len(secs) != 3:
        return finish(f"expected one GC track with 3 sections, found {len(tracks)} / {len(secs)}")
    end = secs[2].get_end_frame()

    def state():
        out = []
        for s in secs:
            p = s.get_editor_property("params")
            out.append([s.get_start_frame(), s.get_end_frame(), p.get_editor_property("start_frame_offset").value,
                        p.get_editor_property("end_frame_offset").value])
        return out

    plan = [[0, fall_start, hold_off, dur_ticks - hold_off - 1], [fall_start, fall_end, hold_off, 0],
            [fall_end, end, dur_ticks - 1, 0]]
    report.update({"cache_bake": bake_id, "release_in_cache_s": release_s, "dur_ticks": dur_ticks, "before": state(),
                   "plan": plan, "release_display_frame": RELEASE_DISPLAY_FRAME})
    if dry:
        report["ok"] = True
        return finish(f"DRY RUN|bake={bake_id}|release_in_cache={release_s}|before={report['before']}|plan={plan}")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreOpeningHoldAtRelease-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", "InfinityStage", "Interactions", "LS_Opening_Curtain_Baked.uasset"), backup)
    report["backup"] = backup
    for s, (a, b, so, eo) in zip(secs, plan):
        s.set_range(a, b)
        p = s.get_editor_property("params")
        p.set_editor_property("start_frame_offset", unreal.FrameNumber(so))
        p.set_editor_property("end_frame_offset", unreal.FrameNumber(eo))
        s.set_editor_property("params", p)
    now = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if now != [SEQ]:
        return finish(f"unexpected dirty content {now}; NOTHING saved (backup {backup})")
    report["saved"] = unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False)
    report["after"] = state()
    report["ok"] = bool(report["saved"]) and report["after"] == plan and not [
        q.get_path_name() for q in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    del seq, cache, drapes, tracks, secs
    finish(f"bake={bake_id}|before={report['before']}|after={report['after']}|backup={backup}")


main()
