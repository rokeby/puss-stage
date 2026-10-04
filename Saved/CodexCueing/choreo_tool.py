"""Cueing T1: create one Choreography sequence per Passage and nest it in the Master.

Run inside the editor through the guarded MCP route (ExecuteProjectPythonFile,
relativeSavedPath "CodexCueing/choreo_tool.py"). It reads its request from
Saved/CodexCueing/choreo_request.json:

    {"mode": "INSPECT" | "DRY" | "APPLY", "run": "<id>", "passages": ["all"] or [labels]}

INSPECT and DRY write nothing. APPLY:
  1. refuses unless build A is in (MovieSceneInfinityChoreoTrack exists), the editor
     is not in PIE, and no package is dirty;
  2. snapshots the Show and Master to Backups/PreChoreo-<stamp>;
  3. creates /Game/InfinityStage/Choreo/LS_Choreo_<Passage> for each requested
     Passage without one: Show tick/display rate, 0:00 = Passage start (Gary, 4 Oct),
     playback = Passage length + 30 s, and the song's bars and section changes as
     marked frames placed at song time minus the rail offset;
  4. sets PassageSettings.Choreography, rebuilds the Master, saves ONLY the new
     Choreos, the Show and the Master;
  5. reads back and logs CHOREO_APPLY_OK|run=... only after every assertion passes.

Never: Save All, reload the level, end PIE, or hold unreal objects in module globals.
"""
import datetime
import json
import os
import re
import shutil

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
CHOREO_DIR = "/Game/InfinityStage/Choreo"
TAIL_SECONDS = 30.0
BEATS_PER_BAR = 4


def _request(project_dir):
    path = os.path.join(project_dir, "Saved", "CodexCueing", "choreo_request.json")
    with open(path, "r", encoding="utf-8") as handle:
        request = json.load(handle)
    mode = str(request.get("mode", "INSPECT")).upper()
    if mode not in ("INSPECT", "DRY", "APPLY"):
        raise RuntimeError("bad mode %r" % mode)
    run = str(request.get("run", "")).strip()
    if not run:
        raise RuntimeError("request needs a run id")
    return mode, run, request.get("passages", ["all"])


def _asset_file(project_dir, asset_path, ext=".uasset"):
    return os.path.join(project_dir, "Content", asset_path[len("/Game/"):].replace("/", os.sep) + ext)


def _census(unreal):
    content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    return {"content": sorted(content), "maps": sorted(maps)}


def _safe_name(label):
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")
    return cleaned or "Passage"


def _passage_sections(unreal, master):
    """PassageGuid -> (start_s, end_s) from the Master's managed Passage track."""
    out = {}
    for track in master.find_tracks_by_exact_type(unreal.MovieSceneInfinityPassageTrack):
        for section in track.get_sections():
            guid = str(section.get_editor_property("block_guid"))
            out[guid] = (section.get_start_frame_seconds(), section.get_end_frame_seconds())
    return out


def _song_markers(unreal, show, settings, tick_rate):
    """Bars and section changes of this Passage's song, as (choreo_seconds, label)."""
    music = settings.get_editor_property("music")
    rail_guid = str(music.get_editor_property("primary_rail_guid"))
    rail = None
    for candidate in show.get_editor_property("music_rails"):
        if str(candidate.get_editor_property("rail_guid")) == rail_guid:
            rail = candidate
            break
    if rail is None:
        return [], "no_rail"
    analysis = rail.get_editor_property("analysis_map").load_synchronous() if rail.get_editor_property("analysis_map") else None
    if analysis is None:
        return [], "no_music_map"
    source_in = rail.get_editor_property("source_in_frame").value
    offset_frames = music.get_editor_property("rail_offset_frames").value
    # The managed music section starts at the Passage start, playing the song from
    # SourceIn + RailOffset (SequenceBuilderLibrary: SetStartOffset), so
    # choreo_time = song_time - that offset.
    offset_s = (source_in + offset_frames) / tick_rate
    rejected = str(unreal.InfinityMusicProposalState.REJECTED)
    markers = []
    beats = [m for m in analysis.get_editor_property("beat_proposals")
             if str(m.get_editor_property("state")) != rejected]
    beats.sort(key=lambda m: m.get_editor_property("time_seconds"))
    for index, beat in enumerate(beats):
        if index % BEATS_PER_BAR == 0:
            markers.append((beat.get_editor_property("time_seconds") - offset_s, "bar %d" % (index // BEATS_PER_BAR + 1)))
    for change in analysis.get_editor_property("major_change_proposals"):
        if str(change.get_editor_property("state")) == rejected:
            continue
        label = str(change.get_editor_property("label")) or "change"
        markers.append((change.get_editor_property("time_seconds") - offset_s, "§ " + label))
    return markers, "ok offset_s=%.3f beats=%d" % (offset_s, len(beats))


def _plan(unreal, show, master, wanted):
    tick = show.get_editor_property("tick_resolution")
    tick_rate = float(tick.numerator) / float(tick.denominator)
    sections = _passage_sections(unreal, master)
    rows = []
    for settings in show.get_editor_property("passage_settings"):
        guid = str(settings.get_editor_property("passage_guid"))
        label = str(settings.get_editor_property("label"))
        if wanted != ["all"] and label not in wanted:
            continue
        try:
            existing = settings.get_editor_property("choreography")
            has = bool(existing)
        except Exception:
            has = None  # field missing: build A has not landed (INSPECT/DRY still report the plan)
        span = sections.get(guid)
        if span is None:
            raise RuntimeError("Passage %s (%s) has no managed section in the Master; rebuild first" % (label, guid))
        length = span[1] - span[0]
        markers, music_note = _song_markers(unreal, show, settings, tick_rate)
        kept = [(t, l) for (t, l) in markers if 0.0 <= t <= length + TAIL_SECONDS]
        rows.append({
            "passage_guid": guid, "label": label, "start_s": span[0], "length_s": length,
            "has_choreo": has, "asset": "%s/LS_Choreo_%s" % (CHOREO_DIR, _safe_name(label)),
            "markers": kept, "music": music_note,
        })
    return rows, tick_rate


def _backup(project_dir, stamp):
    backup_dir = os.path.join(project_dir, "Backups", "PreChoreo-%s" % stamp)
    os.makedirs(backup_dir, exist_ok=False)
    for asset in (SHOW_PATH, MASTER_PATH):
        source = _asset_file(project_dir, asset)
        destination = os.path.join(backup_dir, os.path.basename(source))
        shutil.copy2(source, destination)
        if os.path.getsize(destination) != os.path.getsize(source):
            raise RuntimeError("backup verification failed: %s" % destination)
    return backup_dir


def _create_choreo(unreal, row, master):
    folder, name = row["asset"].rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(row["asset"]):
        raise RuntimeError("asset already exists, refusing to overwrite: %s" % row["asset"])
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    sequence = tools.create_asset(name, folder, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    if sequence is None:
        raise RuntimeError("create_asset returned None for %s" % row["asset"])
    sequence.set_tick_resolution(master.get_tick_resolution())
    sequence.set_display_rate(master.get_display_rate())
    sequence.set_playback_start_seconds(0.0)
    sequence.set_playback_end_seconds(row["length_s"] + TAIL_SECONDS)
    display = master.get_display_rate()
    fps = float(display.numerator) / float(display.denominator)
    tick = master.get_tick_resolution()
    ticks_per_second = float(tick.numerator) / float(tick.denominator)
    for seconds, label in row["markers"]:
        frame = unreal.FrameNumber(int(round(seconds * ticks_per_second)))
        marked = unreal.MovieSceneMarkedFrame()
        marked.set_editor_property("frame_number", frame)
        marked.set_editor_property("label", label)
        sequence.add_marked_frame(marked)
    return sequence, fps


def run():
    import unreal

    project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    mode, run_id, wanted = _request(project_dir)
    report = {"run": run_id, "mode": mode, "ok": False}
    report_path = os.path.join(project_dir, "Saved", "CodexCueing", "choreo_report_%s.json" % re.sub(r"[^A-Za-z0-9_-]", "_", run_id))
    try:
        show = unreal.load_asset(SHOW_PATH)
        master = unreal.load_asset(MASTER_PATH)
        if show is None or master is None:
            raise RuntimeError("Show or Master failed to load")
        rows, tick_rate = _plan(unreal, show, master, wanted)
        report["plan"] = [{k: v for k, v in row.items() if k != "markers"} | {"marker_count": len(row["markers"])} for row in rows]
        report["census_before"] = _census(unreal)
        if mode in ("INSPECT", "DRY"):
            report["ok"] = True
            unreal.log("CHOREO_%s_OK|run=%s|passages=%d|to_create=%d|report=%s"
                       % (mode, run_id, len(rows), sum(1 for r in rows if not r["has_choreo"]), report_path))
            return report

        # ---------------- APPLY
        if not hasattr(unreal, "MovieSceneInfinityChoreoTrack"):
            raise RuntimeError("NOT_BUILT: MovieSceneInfinityChoreoTrack is missing; build A has not landed")
        level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if level_editor.is_in_play_in_editor():
            raise RuntimeError("PIE is running; this tool never touches a running PIE")
        if report["census_before"]["content"] or report["census_before"]["maps"]:
            raise RuntimeError("dirty packages before APPLY: %s" % report["census_before"])
        todo = [row for row in rows if row["has_choreo"] is False]
        if not todo:
            raise RuntimeError("NOOP: every requested Passage already has a Choreo (NOOP is not success)")

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        report["backup"] = _backup(project_dir, stamp)

        created = {}
        for row in todo:
            sequence, _ = _create_choreo(unreal, row, master)
            created[row["passage_guid"]] = sequence

        show.modify()
        settings_list = show.get_editor_property("passage_settings")
        for settings in settings_list:
            guid = str(settings.get_editor_property("passage_guid"))
            if guid in created:
                settings.set_editor_property("choreography", created[guid])
        show.set_editor_property("passage_settings", settings_list)

        rebuild = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
        ok = rebuild[0] if isinstance(rebuild, tuple) else bool(rebuild)
        if not ok:
            raise RuntimeError("rebuild_managed_master failed: %r" % (rebuild,))

        allowed = {SHOW_PATH, MASTER_PATH} | {row["asset"] for row in todo}
        census = _census(unreal)
        stray = set(census["content"]) - allowed
        if stray or census["maps"]:
            raise RuntimeError("out-of-scope dirty packages before save: %s" % census)
        for asset in sorted(allowed):
            if not unreal.EditorAssetLibrary.save_asset(asset, only_if_is_dirty=False):
                raise RuntimeError("save failed: %s" % asset)

        # Read back from the saved objects.
        nested = {}
        for track in master.find_tracks_by_exact_type(unreal.MovieSceneInfinityChoreoTrack):
            for section in track.get_sections():
                nested[str(section.get_editor_property("block_guid"))] = (
                    section.get_sequence().get_path_name() if section.get_sequence() else None,
                    section.get_start_frame_seconds())
        for row in todo:
            got = nested.get(row["passage_guid"])
            if got is None:
                raise RuntimeError("read-back: no Choreo section for %s" % row["label"])
            if not got[0] or not got[0].startswith(row["asset"]):
                raise RuntimeError("read-back: %s nests %r, expected %s" % (row["label"], got[0], row["asset"]))
            if abs(got[1] - row["start_s"]) > 1.0 / 60.0:
                raise RuntimeError("read-back: %s Choreo starts at %.3f s, Passage at %.3f s" % (row["label"], got[1], row["start_s"]))
        for settings in show.get_editor_property("passage_settings"):
            guid = str(settings.get_editor_property("passage_guid"))
            if guid in created and not settings.get_editor_property("choreography"):
                raise RuntimeError("read-back: Show lost the Choreography field for %s" % guid)
        report["census_after"] = _census(unreal)
        if report["census_after"]["content"] or report["census_after"]["maps"]:
            raise RuntimeError("dirty after save: %s" % report["census_after"])
        report["created"] = [row["asset"] for row in todo]
        report["ok"] = True
        unreal.log("CHOREO_APPLY_OK|run=%s|created=%d|nested=%d|backup=%s|report=%s"
                   % (run_id, len(todo), len(nested), report["backup"], report_path))
        unreal.log("CHOREO_NEXT|run=%s|run InfinityStage.Editor.SavedMasterMatchesShow and SceneCutBindingsResolve singly" % run_id)
        return report
    except Exception as error:
        report["error"] = str(error)
        unreal.log_error("CHOREO_STOPPED|run=%s|mode=%s|reason=%s|report=%s" % (run_id, mode, error, report_path))
        raise
    finally:
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)


run()
