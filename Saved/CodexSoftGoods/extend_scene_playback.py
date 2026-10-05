"""Change a Scene or Sequence cue's playback length SAFELY (30 Sep): end, coverage, Master rebuild, exact saves.

Why: Scene 1 was lengthened (0-375 -> 0-5270) on 29 Sep without re-running the scene-handoff match. Its Exit Handoff cut
stayed at 350-375 and 375-5270 had NO camera cut, so a transport jump into the tail left the player controller at the
origin (the dev grid). Scenes 2, 5 and 6 are about to be lengthened for the hangar rises. This script makes the
omission impossible: the rematch and a coverage check are part of the change, not a separate step.

Mode file extend_scene_playback_mode.json:
  {"scene_label": "Scene 2 — External Sound", "new_end_s": 31.0, "dry_run": true}
  {"scene_label": "Scene 1 — External Sound", "rematch_only": true, "dry_run": true}   # fix an existing gap, range unchanged
  {"cue_label": "Interaction 1 — Washing the Boy", "new_end_frame": 638, "dry_run": true}
Steps (apply):
  1. Guards: no PIE, the show level open, nothing dirty; the cue must be an enabled Scene or Sequence cue with a sequence.
  2. Backups of the Show, the Master, the cue sequence and the level, to Backups/PreSceneExtend-<sequence>-<ts>/.
  3. set_playback_end (unless rematch_only).
  4. Scenes run InfinityStageCameraPilotLibrary.match_named_scene_handoffs(show, [cue guid], 1). Sequence cues instead
     extend active camera cuts ending at the old playback end, changing section ends only.
  5. CUT COVERAGE: the cue's camera cut track must cover [playback start, playback end) with no gap, or NOTHING is saved.
  6. Rebuild the managed Master (the library call, never PussStageBootstrap.RebuildCurrentMaster). NOT in rematch_only:
     the range is unchanged, so the Master's section for the scene is unchanged and the Master is not touched at all.
     rematch_only REFUSES if the Master or the Show goes dirty. (The Master is NOT stale: SavedMasterMatchesShow passed
     at 11:06 on 30 Sep with zero failed assertions, and Look & camera measured Scene 3's section 1:1 with the transport.
     The care is to PRESERVE a correct Master.)
  7. Save exactly: the cue sequence, the Master, the Show if the rebuild dirtied it, and for Scenes only the level when
     the rematch writes handoff cameras. Read back the coverage and the Show/Master match.
Downstream (full mode only):
  - KEY GATE. Passage camera and wing channels are evaluated and keyed at ABSOLUTE Master time
    (MovieSceneInfinityPassageTrack.cpp, CameraPilotLibrary KeyPassageCameraPose), and the rebuild moves a Passage section
    with SetRange, which does not move keys. So a later Passage carrying a channel with 2+ keys would be left with its
    score displaced by the change. The script REFUSES then, and lists them. Carrying keys is a camera-key write
    (Look & camera's), never done here.
  - SEGMENT DELTAS. Every compiled segment before and after, with its shift: segments ending at or before the scene's
    start must not move, and later ones must move by exactly the change. A mismatch fails ok.
  - Verify with InfinityStage.Editor.SavedMasterMatchesShow afterwards (run_master_match_test.py).
Logs PUSS_SOFTGOODS_SCENE_EXTENDED|... or _STOPPED|... Crash rules: everything inside main().
"""
import datetime
import json
import os
import shutil

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def content_file(path, ext=".uasset"):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ext


def cut_coverage(seq):
    """Stretches of [playback start, playback end) with NO camera cut section, in display frames. [] = fully covered."""
    start, end = seq.get_playback_start(), seq.get_playback_end()
    spans = []
    for t in seq.get_tracks():
        if t.get_class().get_name() == "MovieSceneCameraCutTrack":
            for s in t.get_sections():
                if s.is_active():
                    spans.append((s.get_start_frame() if s.has_start_frame() else start,
                                  s.get_end_frame() if s.has_end_frame() else end))
    spans.sort()
    gaps, cursor = [], start
    for a, b in spans:
        if a > cursor:
            gaps.append([cursor, min(a, end)])
        cursor = max(cursor, b)
        if cursor >= end:
            break
    if cursor < end:
        gaps.append([cursor, end])
    return {"range": [start, end], "cuts": [list(x) for x in spans], "gaps": [g for g in gaps if g[1] > g[0]]}


def tail_cut_extensions(seq, old_end, new_end, apply=False):
    """Camera-cut tail changes for a Sequence cue. Dry runs only predict them; apply changes section ends only."""
    changes = []
    for track in seq.get_tracks():
        if track.get_class().get_name() != "MovieSceneCameraCutTrack":
            continue
        for section in track.get_sections():
            if not section.is_active() or not section.has_end_frame() or section.get_end_frame() != old_end:
                continue
            start = section.get_start_frame() if section.has_start_frame() else seq.get_playback_start()
            changes.append([[start, old_end], [start, new_end]])
            if apply:
                section.set_end_frame(new_end)
    return changes


def handoff_cameras(scene_label):
    """The scene's Entry and Exit handoff cameras: transform, focal length and focus. The match RE-COPIES them from the
    neighbouring Passages (Look & camera, 30 Sep), so a rematch can MOVE them even when the range is unchanged. They are
    recorded before and after, and a move is stated, not discovered."""
    out = {}
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label = a.get_actor_label()
        for kind in ("Entry", "Exit"):
            if label == f"{scene_label} — {kind} Handoff Camera":
                cc = a.get_editor_property("camera_component")
                loc, rot = a.get_actor_location(), a.get_actor_rotation()
                fs = cc.get_editor_property("focus_settings")
                out[kind] = {"loc": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)],
                             "rot": [round(rot.pitch, 3), round(rot.yaw, 3), round(rot.roll, 3)],
                             "focal_mm": round(cc.get_editor_property("current_focal_length"), 3),
                             "focus_cm": round(fs.get_editor_property("manual_focus_distance"), 2)}
    return out


def camera_deltas(before, after):
    rows = {}
    for kind in set(before) | set(after):
        b, a = before.get(kind), after.get(kind)
        if not b or not a:
            rows[kind] = {"before": b, "after": a}
            continue
        rows[kind] = {"moved_cm": round(sum((x - y) ** 2 for x, y in zip(a["loc"], b["loc"])) ** 0.5, 2),
                      "turned_deg": round(max(abs(x - y) for x, y in zip(a["rot"], b["rot"])), 3),
                      "focal_delta_mm": round(a["focal_mm"] - b["focal_mm"], 3),
                      "focus_delta_cm": round(a["focus_cm"] - b["focus_cm"], 2)}
    return rows


def neighbour_rule(show, scene_label):
    """Predicts whether the match will REFUSE, the way the builder decides (InfinityStageSceneHandoffBuilder.cpp:176-206,
    via Look & camera): it reads the COMPILED segments, not the cue list. It refuses if the segment BEFORE the scene is
    not a WingPair (Passage), or if the segment AFTER is neither a WingPair nor a cue whose scene.retain_previous_camera
    is true."""
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = list(tr.get_editor_property("segments"))
    cues = list(show.get_editor_property("cues"))
    labels = [str(sg.get_editor_property("label")) for sg in segs]
    if scene_label not in labels:
        del tr
        return {"error": f"'{scene_label}' is not a compiled segment", "match_would_refuse": True}
    i = labels.index(scene_label)

    def describe(j):
        if j < 0 or j >= len(segs):
            return None
        cue = cues[segs[j].get_editor_property("cue_index")]
        kind = str(cue.get_editor_property("type"))
        retain = None
        try:
            retain = bool(cue.get_editor_property("scene").get_editor_property("retain_previous_camera"))
        except Exception:  # noqa: BLE001
            pass
        return {"segment": j, "label": labels[j], "type": kind, "wing_pair": "WING_PAIR" in kind.upper(),
                "retain_previous_camera": retain}

    before, after = describe(i - 1), describe(i + 1)
    del tr
    refuse = (not before or not before["wing_pair"]) or (not after or not (after["wing_pair"] or after["retain_previous_camera"]))
    return {"scene_segment": i, "before": before, "after": after, "match_would_refuse": refuse}


def show_master_match(show, master):
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [(str(s.get_editor_property("label")), s.get_editor_property("start_frame").value / rate,
             s.get_editor_property("end_frame").value / rate) for s in tr.get_editor_property("segments")]
    del tr
    secs = sorted((sec.get_start_frame_seconds(), sec.get_end_frame_seconds())
                  for track in master.find_tracks_by_type(unreal.MovieSceneSubTrack)
                  # Passage Choreography tracks (cueing A2) nest per Passage, not per Scene/Sequence cue:
                  # skip them as SavedMasterMatchesShow does (patch A2d). Measured 4 Oct: counting them gave 640 s.
                  if "InfinityChoreo" not in track.get_class().get_name()
                  for sec in track.get_sections())
    seq_segs = [s for s in segs if not s[0].startswith("Passage")]
    worst = max((max(abs(s[1] - m[0]), abs(s[2] - m[1])) for s, m in zip(seq_segs, secs)), default=0.0)
    return {"worst_err_s": round(worst, 3), "match": len(seq_segs) == len(secs) and worst <= 0.05}


def compiled_segments(show):
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [{"label": str(s.get_editor_property("label")),
             "start": round(s.get_editor_property("start_frame").value / rate, 3),
             "end": round(s.get_editor_property("end_frame").value / rate, 3)} for s in tr.get_editor_property("segments")]
    del tr
    return segs


def downstream_keyed_passages(master, after_s):
    """Passage sections starting at or after after_s (Master seconds) that carry a VARYING channel (2+ distinct key
    values). A single key, or several with one value, is a constant and survives any shift; a varying channel is a score
    tied to absolute Master frames. Measured 30 Sep (probe_passage_key_alignment): every keyed channel on the Master sits
    BEFORE its section, P02's exactly 195.8 s behind (the 29 Sep Scene 1 extension); only P01's wing channels vary."""
    found = []
    for track in master.get_tracks():
        if "InfinityPassage" not in track.get_class().get_name():
            continue
        for sec in track.get_sections():
            start = sec.get_start_frame_seconds()
            if start < after_s - 1e-3:
                continue
            multi = []
            for ch in sec.get_all_channels():
                values = {round(float(k.get_value()), 6) for k in ch.get_keys()}
                if len(values) >= 2:       # 2+ keys with EQUAL values are a constant (P03's 50/50 mm focal, 30 Sep)
                    multi.append(f"{ch.get_editor_property('channel_name')}={sorted(values)}")
            if multi:
                found.append({"section_start_s": round(start, 3), "passage_guid": str(sec.get_editor_property("passage_guid")),
                              "multi_key_channels": multi})
    return found


def passage_keys_section_relative(master):
    """Every Passage section's keys as (tick offset from its own section start, value), by passage GUID.
    Patch K (InfinityStageSequenceBuilderLibrary.cpp, PassageKeysFollowSection) moves a Passage's keys with its
    section, so these must be identical before and after any retime. Conductor 4 Oct: replaces the pre-K key gate."""
    unit = unreal.MovieSceneTimeUnit
    out = {}
    for track in master.get_tracks():
        if "InfinityPassage" not in track.get_class().get_name():
            continue
        for sec in track.get_sections():
            start_tick = int(round(sec.get_start_frame_seconds() * 24000.0))
            rows = {}
            for ch in sec.get_all_channels():
                keys = [[int(k.get_time(time_unit=unit.TICK_RESOLUTION).frame_number.value) - start_tick,
                         round(float(k.get_value()), 6)] for k in ch.get_keys()]
                if keys:
                    rows[str(ch.get_editor_property("channel_name"))] = keys
            out[unreal.GuidLibrary.conv_guid_to_string(sec.get_editor_property("passage_guid"))] = rows
    return out


def key_carry_failures(before, after):
    bad = []
    for guid, chans in before.items():
        now = after.get(guid)
        if now is None:
            bad.append("%s vanished" % guid)
            continue
        for ch, kb in chans.items():
            ka = now.get(ch)
            # Tolerance: half a 25 fps display frame (480 ticks). The section start is derived from float
            # seconds, so a correct carry shows +/-2 ticks (measured 4 Oct S2); a failed carry is off by the
            # whole retime (71.6 s = 1.7M ticks).
            if ka is None or len(ka) != len(kb) or any(abs(x[0] - y[0]) > 480 or abs(x[1] - y[1]) > 1e-5
                                                       for x, y in zip(ka, kb)):
                bad.append("%s %s: %r -> %r" % (guid, ch, kb[:3], (ka or [])[:3]))
    return bad


def segment_deltas(before, after, scene_label, delta_s):
    """Every segment's shift; the scene itself may only grow at its end, earlier ones stay, later ones move by delta_s."""
    rows, bad = [], []
    idx = next((i for i, s in enumerate(before) if s["label"] == scene_label), None)
    for i, (b, a) in enumerate(zip(before, after)):
        expect = 0.0 if idx is None or i <= idx else delta_s
        shift = round(a["start"] - b["start"], 3)
        row = {"label": b["label"], "before": [b["start"], b["end"]], "after": [a["start"], a["end"]], "shift_s": shift,
               "expected_shift_s": round(expect, 3)}
        rows.append(row)
        if b["label"] != a["label"] or abs(shift - expect) > 0.05:
            bad.append(row)
    if len(before) != len(after):
        bad.append({"error": f"segment count {len(before)} -> {len(after)}"})
    return rows, bad


def main():
    with open(os.path.join(HERE, "extend_scene_playback_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    dry = bool(cfg.get("dry_run", True))
    rematch_only = bool(cfg.get("rematch_only", False))
    report = {"ok": False, "cfg": cfg}
    out = os.path.join(HERE, "extend_scene_playback.json")

    def finish(msg):
        msg = f"cue_type={report.get('cue_type', 'unknown')}|{msg}"
        report["message"] = msg
        with open(out, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(("PUSS_SOFTGOODS_SCENE_EXTENDED|" if report["ok"] else "PUSS_SOFTGOODS_SCENE_EXTEND_STOPPED|") + msg)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:                 # PIE first: in play mode get_editor_world() is None
        return finish("PIE is running")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        return finish("unsafe editor state (wrong or no world)")
    if dirty():
        return finish(f"refusing: dirty packages {dirty()}")
    show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    cue_label = cfg.get("cue_label", cfg.get("scene_label"))
    if not cue_label:
        return finish("refusing: mode file needs cue_label (scene_label remains an alias)")
    all_cues = list(show.get_editor_property("cues"))
    cues = [c for c in all_cues if str(c.get_editor_property("label")) == cue_label]
    if len(cues) != 1 or not cues[0].get_editor_property("enabled"):
        return finish(f"refusing: '{cue_label}' is not exactly one enabled cue")
    raw_cue_type = str(cues[0].get_editor_property("type"))
    is_scene = raw_cue_type == str(unreal.InfinityCueType.SCENE)
    is_sequence = raw_cue_type == str(unreal.InfinityCueType.SEQUENCE)
    if not is_scene and not is_sequence:
        return finish(f"refusing: '{cue_label}' is neither a Scene nor a Sequence cue")
    cue_type = "SCENE" if is_scene else "SEQUENCE"
    report["cue_type"] = cue_type
    report["note"] = ("n/a (Scene cue)" if is_scene else
                      "drape sections are re-fitted by fit_transition_drapes.py")
    if is_sequence and rematch_only:
        return finish("refusing: rematch_only is Scene-only")
    cue_guid = cues[0].get_editor_property("cue_guid")
    seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
    if seq is None:
        return finish(f"refusing: the {cue_type.title()} cue has no sequence")
    seq_path = seq.get_path_name().split(".")[0]
    rate = seq.get_display_rate()
    fps = rate.numerator / rate.denominator
    old_end = seq.get_playback_end()
    if rematch_only:
        new_end = old_end
    elif "new_end_frame" in cfg:
        if isinstance(cfg["new_end_frame"], bool) or not isinstance(cfg["new_end_frame"], int):
            return finish("refusing: new_end_frame must be an int in display frames")
        new_end = cfg["new_end_frame"]
    elif "new_end_s" in cfg:
        new_end = int(round(float(cfg["new_end_s"]) * fps))
    else:
        return finish("refusing: mode file needs new_end_frame or new_end_s")
    report.update({"sequence": seq_path, "fps": fps, "playback_before": [seq.get_playback_start(), seq.get_playback_end()],
                   "new_end": new_end, "coverage_before": cut_coverage(seq),
                   "next_segment": neighbour_rule(show, cue_label) if is_scene else "n/a (Sequence cue)",
                   "cameras_before": handoff_cameras(cue_label) if is_scene else "n/a (Sequence cue)"})
    if is_sequence:
        report["cut_extended"] = tail_cut_extensions(seq, old_end, new_end)
    if not rematch_only and new_end <= seq.get_playback_start():
        return finish(f"refusing: new end {new_end} is not after the start")
    if is_sequence and new_end <= old_end:
        return finish(f"refusing: Sequence cues can only be lengthened ({old_end} -> {new_end})")
    report["segments_before"] = compiled_segments(show)
    cue_seg = next((s for s in report["segments_before"] if s["label"] == cue_label), None)
    report["delta_s"] = round((new_end - old_end) / fps, 3)
    if not rematch_only:
        # Pre-patch-K this refused; patch K now carries Passage keys with their sections, so record what is
        # downstream (informational) and VERIFY the carry after the rebuild instead (see key_carry_failures).
        report["key_gate_info"] = downstream_keyed_passages(master, cue_seg["end"] if cue_seg else 0.0)
        report["passage_keys_before"] = passage_keys_section_relative(master)
    if dry:
        report["ok"] = True
        return finish(f"DRY RUN|{seq_path}|{report['playback_before']} -> end {new_end}|gaps before "
                      f"{report['coverage_before']['gaps']}|next={report['next_segment']}"
                      f"|cameras={list(report['cameras_before']) if is_scene else report['cameras_before']}"
                      f"|delta_s={report['delta_s']}|cut_extended={report.get('cut_extended', 'n/a (Scene cue)')}"
                      f"|key_gate={report.get('key_gate', 'n/a (rematch_only)')}")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", f"PreSceneExtend-{seq_path.split('/')[-1]}-{stamp}")
    os.makedirs(backup, exist_ok=True)
    for p in (SHOW, MASTER, seq_path):
        shutil.copy2(content_file(p), backup)
    shutil.copy2(content_file(EXPECTED_WORLD, ".umap"), backup)
    report["backup"] = backup
    if not rematch_only:
        seq.set_playback_end(new_end)
    if is_scene:
        res = unreal.InfinityStageCameraPilotLibrary.match_named_scene_handoffs(show, [cue_guid], 1)
        matched, match_report = (res if isinstance(res, tuple) else (res, ""))
        report["match"] = {"ok": bool(matched), "report": str(match_report)}
        report["camera_deltas"] = camera_deltas(report["cameras_before"], handoff_cameras(cue_label))
    else:
        report["cut_extended"] = tail_cut_extensions(seq, old_end, new_end, apply=True)
        matched = True
        report["match"] = {"ok": True, "report": "n/a (Sequence cue)"}
        report["camera_deltas"] = "n/a (Sequence cue)"
    report["coverage_after_match"] = cut_coverage(seq)
    if not matched or report["coverage_after_match"]["gaps"]:
        return finish(f"STOPPED: match={matched} gaps={report['coverage_after_match']['gaps']}; NOTHING saved "
                      f"(relaunch to discard; backup {backup})")
    if rematch_only:
        result = "skipped (rematch_only: range unchanged, the Master is not touched)"
        expected = {seq_path, EXPECTED_WORLD}
    else:
        result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
        expected = {seq_path, MASTER, SHOW} | ({EXPECTED_WORLD} if is_scene else set())
    report["rebuild_result"] = result
    if not rematch_only:
        report["key_carry_failures"] = key_carry_failures(report["passage_keys_before"],
                                                          passage_keys_section_relative(master))
        if report["key_carry_failures"]:
            return finish(f"STOPPED: Passage keys did not travel with their sections (patch K): "
                          f"{report['key_carry_failures'][:5]}; NOTHING saved (relaunch to discard; backup {backup})")
    now = dirty()
    report["dirty_before_save"] = now
    if not result or [p for p in now if p not in expected]:
        return finish(f"STOPPED: rebuild={result!r} unexpected dirty {[p for p in now if p not in expected]}; NOTHING "
                      f"saved (backup {backup})")
    saved = {p: unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True) for p in (seq_path, MASTER, SHOW) if p in now}
    if is_scene and EXPECTED_WORLD in now:
        saved[EXPECTED_WORLD] = unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)
    report["saved"] = saved
    seq = unreal.load_asset(seq_path)
    report["coverage_after"] = cut_coverage(seq)
    report["playback_after"] = [seq.get_playback_start(), seq.get_playback_end()]
    report["show_master"] = ({"match": True, "note": "not checked: the Master was not rebuilt (rematch_only)"}
                             if rematch_only else show_master_match(unreal.load_asset(SHOW), unreal.load_asset(MASTER)))
    report["segments"], report["segment_errors"] = segment_deltas(
        report["segments_before"], compiled_segments(unreal.load_asset(SHOW)), cue_label, report["delta_s"])
    report["dirty_final"] = dirty()
    report["ok"] = (all(saved.values()) and not report["coverage_after"]["gaps"] and report["show_master"]["match"]
                    and not report["dirty_final"] and report["playback_after"][1] == new_end
                    and not report["segment_errors"])
    del show, master, seq, cues, world
    finish(f"{seq_path}|end={new_end}|gaps={report['coverage_after']['gaps']}|cameras_moved={report['camera_deltas']}"
           f"|master_match={report['show_master']}|segment_errors={report['segment_errors']}"
           f"|saved={saved}|backup={backup}")


main()
