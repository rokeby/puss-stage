"""Slow one existing Passage to exactly 180 seconds without changing its wings.

The pure planning and invariant helpers at the top are exercised by
test_passage_slow_walk.py without Unreal.  ``run_unreal`` is the live entry
point; small Saved/ wrappers inject one Passage, mode and run id per MCP call.

This is deliberately not the ResizePassageToDuration tool.  It never appends,
removes or reorders a cue.  The only Show fields it writes are LeadInFrames,
TailFrames and each existing WingPair's IntervalToNext.
"""

import copy
import datetime
import json
import math
import os
import shutil


TARGET_SECONDS = 180.0
EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage")).rstrip("\\/")
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
VALID_PASSAGES = {"Passage 2": "P02", "Passage 3": "P03", "Passage 4": "P04"}


def _round_positive(value):
    """UE-style nearest-integer rounding for the non-negative timing domain."""
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError("timing value must be finite and non-negative: %r" % value)
    return int(math.floor(number + 0.5))


def plan_scaled_timing(lead_frames, intervals, tail_frames, target_ticks):
    """Scale all timing fields, then absorb the aggregate rounding residual in Tail."""
    lead = int(lead_frames)
    rows = [int(value) for value in intervals]
    tail = int(tail_frames)
    target = int(target_ticks)
    if not rows:
        raise ValueError("at least one WingPair interval is required")
    if lead < 0 or tail < 0 or target <= 0 or any(value <= 0 for value in rows):
        raise ValueError("invalid timing inputs")
    old_ticks = lead + sum(rows[:-1]) + tail
    if old_ticks <= 0:
        raise ValueError("compiled duration must be positive")
    scale = target / float(old_ticks)
    new_lead = _round_positive(lead * scale)
    new_intervals = [_round_positive(value * scale) for value in rows]
    rounded_tail = _round_positive(tail * scale)
    rounded_total = new_lead + sum(new_intervals[:-1]) + rounded_tail
    residual = target - rounded_total
    new_tail = rounded_tail + residual
    if new_tail < 0:
        raise ValueError("rounding residual made TailFrames negative")
    exact_total = new_lead + sum(new_intervals[:-1]) + new_tail
    if exact_total != target:
        raise AssertionError("planned duration is not exact")
    return {
        "old_ticks": old_ticks,
        "target_ticks": target,
        "k": scale,
        "lead_frames": new_lead,
        "intervals": new_intervals,
        "rounded_tail_frames": rounded_tail,
        "rounding_residual_ticks": residual,
        "tail_frames": new_tail,
        "new_ticks": exact_total,
    }


def assert_protected_unchanged(before, after):
    """Reject any change to the non-timing identity/layout contract."""
    protected = (
        "cue_count",
        "cue_indices",
        "cue_guids",
        "occurrence_guids",
        "meshes",
        "override_masks",
        "lead_in_distance_cm",
        "gap_to_next_cm",
        "tail_distance_cm",
    )
    problems = []
    for field in protected:
        if before.get(field) != after.get(field):
            problems.append({"field": field, "before": before.get(field), "after": after.get(field)})
    if problems:
        raise AssertionError("protected Passage state changed: %s" % json.dumps(problems, sort_keys=True))
    return True


def _asset_id(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


def _frame(value):
    if hasattr(value, "value"):
        return int(value.value)
    try:
        return int(value.get_editor_property("value"))
    except Exception:
        return int(value)


def _guid(unreal, value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def _prop(value, *names):
    failures = []
    for name in names:
        try:
            return value.get_editor_property(name)
        except Exception as error:
            failures.append("%s:%s" % (name, error))
    raise RuntimeError("property lookup failed: " + " | ".join(failures))


def _object_path(value):
    if value is None:
        return None
    text = value.get_path_name() if hasattr(value, "get_path_name") else str(value)
    return text.split(".", 1)[0]


def _census(unreal):
    return {
        "content": sorted(_asset_id(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(_asset_id(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _sequence_file(project_dir, asset_path, extension=".uasset"):
    return os.path.join(project_dir, "Content", *asset_path[len("/Game/"):].split("/")) + extension


def _wing_snapshot(unreal, cue, cue_index):
    wing = _prop(cue, "wing_pair")
    left = _prop(wing, "left")
    right = _prop(wing, "right")
    has_top = bool(_prop(wing, "has_top", "b_has_top"))
    top = _prop(wing, "top")
    return {
        "cue_index": int(cue_index),
        "cue_guid": _guid(unreal, _prop(cue, "cue_guid")),
        "occurrence_guid": _guid(unreal, _prop(wing, "occurrence_guid")),
        "label": str(_prop(cue, "label")),
        "interval_to_next": _frame(_prop(wing, "interval_to_next")),
        "gap_to_next_cm": float(_prop(wing, "gap_to_next_cm")),
        "override_mask": int(_prop(wing, "local_override_mask")),
        "left_mesh": _object_path(_prop(left, "mesh")),
        "right_mesh": _object_path(_prop(right, "mesh")),
        "has_top": has_top,
        "top_mesh": _object_path(_prop(top, "mesh")) if has_top else None,
    }


def _protected_snapshot(settings, wing_rows):
    return {
        "cue_count": len(wing_rows),
        "cue_indices": [row["cue_index"] for row in wing_rows],
        "cue_guids": [row["cue_guid"] for row in wing_rows],
        "occurrence_guids": [row["occurrence_guid"] for row in wing_rows],
        "meshes": [
            [row["left_mesh"], row["right_mesh"], row["has_top"], row["top_mesh"]]
            for row in wing_rows
        ],
        "override_masks": [row["override_mask"] for row in wing_rows],
        "lead_in_distance_cm": float(_prop(settings, "lead_in_distance_cm")),
        "gap_to_next_cm": [row["gap_to_next_cm"] for row in wing_rows],
        "tail_distance_cm": float(_prop(settings, "tail_distance_cm")),
    }


def _passage_state(unreal, show, passage_label):
    settings_rows = [
        (index, row) for index, row in enumerate(list(_prop(show, "passage_settings")))
        if str(_prop(row, "label")) == passage_label
    ]
    if len(settings_rows) != 1:
        raise RuntimeError("expected one %s settings row, found %d" % (passage_label, len(settings_rows)))
    settings_index, settings = settings_rows[0]
    cues = list(_prop(show, "cues"))
    first_guid = _guid(unreal, _prop(settings, "first_cue_guid"))
    last_guid = _guid(unreal, _prop(settings, "last_cue_guid"))
    index_by_guid = {_guid(unreal, _prop(cue, "cue_guid")): index for index, cue in enumerate(cues)}
    if first_guid not in index_by_guid or last_guid not in index_by_guid:
        raise RuntimeError("Passage range GUIDs do not resolve")
    first_index, last_index = index_by_guid[first_guid], index_by_guid[last_guid]
    if last_index < first_index:
        raise RuntimeError("Passage range is reversed")
    rows = []
    for cue_index in range(first_index, last_index + 1):
        cue = cues[cue_index]
        cue_type = str(_prop(cue, "type"))
        if "WING_PAIR" not in cue_type.upper() or not bool(_prop(cue, "enabled")):
            raise RuntimeError("%s cue %d is not an enabled WingPair: %s" % (passage_label, cue_index, cue_type))
        rows.append(_wing_snapshot(unreal, cue, cue_index))
    lead = _frame(_prop(settings, "lead_in_frames"))
    tail = _frame(_prop(settings, "tail_frames"))
    intervals = [row["interval_to_next"] for row in rows]
    duration_ticks = lead + sum(intervals[:-1]) + tail
    route_cm = (
        float(_prop(settings, "lead_in_distance_cm"))
        + sum(row["gap_to_next_cm"] for row in rows[:-1])
        + float(_prop(settings, "tail_distance_cm"))
    )
    return {
        "settings_index": settings_index,
        "settings": settings,
        "first_index": first_index,
        "last_index": last_index,
        "rows": rows,
        "lead_frames": lead,
        "tail_frames": tail,
        "intervals": intervals,
        "duration_ticks": duration_ticks,
        "route_cm": route_cm,
        "passage_guid": _guid(unreal, _prop(settings, "passage_guid")),
        "protected": _protected_snapshot(settings, rows),
    }


def _compiled_segments(unreal, show):
    transport = unreal.new_object(unreal.InfinityStageTransportController)
    transport.build_segments(show)
    output = []
    for index, segment in enumerate(list(_prop(transport, "segments"))):
        output.append({
            "index": index,
            "label": str(_prop(segment, "label")),
            "start_tick": _frame(_prop(segment, "start_frame")),
            "end_tick": _frame(_prop(segment, "end_frame")),
            "cue_index": int(_prop(segment, "cue_index")),
        })
    del transport
    return output


def _predicted_segment_shifts(segments, passage_label, delta_ticks):
    matches = [row["index"] for row in segments if row["label"] == passage_label]
    if len(matches) != 1:
        raise RuntimeError("compiled segment lookup for %s returned %d rows" % (passage_label, len(matches)))
    target_index = matches[0]
    rows = []
    for row in segments[target_index:]:
        predicted = copy.deepcopy(row)
        if row["index"] == target_index:
            predicted["new_start_tick"] = row["start_tick"]
            predicted["new_end_tick"] = row["end_tick"] + delta_ticks
            predicted["shift_tick"] = 0
            predicted["end_delta_tick"] = delta_ticks
        else:
            predicted["new_start_tick"] = row["start_tick"] + delta_ticks
            predicted["new_end_tick"] = row["end_tick"] + delta_ticks
            predicted["shift_tick"] = delta_ticks
            predicted["end_delta_tick"] = delta_ticks
        rows.append(predicted)
    following = segments[target_index + 1] if target_index + 1 < len(segments) else None
    return rows, following


def _master_sections(master, passage_guid, passage_start_s, passage_end_s, delta_s):
    rows = []
    for track_index, track in enumerate(master.get_tracks()):
        track_name = str(track.get_display_name())
        track_class = track.get_class().get_name()
        for section_index, section in enumerate(track.get_sections()):
            start_s = float(section.get_start_frame_seconds())
            end_s = float(section.get_end_frame_seconds())
            section_guid = None
            try:
                section_guid = str(section.get_editor_property("passage_guid"))
            except Exception:
                pass
            is_target = section_guid == passage_guid or (
                "InfinityPassage" in track_class
                and abs(start_s - passage_start_s) <= 0.05
                and abs(end_s - passage_end_s) <= 0.05
            )
            downstream = start_s >= passage_end_s - 0.05 and not is_target
            if is_target or downstream:
                rows.append({
                    "track_index": track_index,
                    "section_index": section_index,
                    "track": track_name,
                    "track_class": track_class,
                    "old_range_s": [start_s, end_s],
                    "new_range_s": [
                        start_s + (delta_s if downstream else 0.0),
                        end_s + delta_s,
                    ],
                    "shift_s": delta_s if downstream else 0.0,
                    "target_passage_section": is_target,
                })
    return rows


def _backup(unreal, project_dir, short, prefix="PreSlowWalk"):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = os.path.join(project_dir, "Backups", "%s-%s-%s" % (prefix, short, stamp))
    os.makedirs(backup_dir, exist_ok=False)
    sources = [
        _sequence_file(project_dir, SHOW_PATH),
        _sequence_file(project_dir, MASTER_PATH),
        _sequence_file(project_dir, EXPECTED_WORLD, ".umap"),
    ]
    copied = []
    for source in sources:
        if not os.path.isfile(source):
            raise RuntimeError("backup source is missing: %s" % source)
        destination = os.path.join(backup_dir, os.path.basename(source))
        shutil.copy2(source, destination)
        if not os.path.isfile(destination) or os.path.getsize(destination) != os.path.getsize(source):
            raise RuntimeError("backup verification failed: %s" % destination)
        copied.append(destination)
    return backup_dir, copied


def _following_scene(unreal, show, following_segment):
    if following_segment is None:
        raise RuntimeError("target Passage has no following segment")
    cues = list(_prop(show, "cues"))
    cue_index = following_segment["cue_index"]
    if cue_index < 0 or cue_index >= len(cues):
        raise RuntimeError("following segment cue index is invalid")
    cue = cues[cue_index]
    cue_type = str(_prop(cue, "type"))
    if cue_type != str(unreal.InfinityCueType.SCENE):
        raise RuntimeError("following segment is not a Scene: %s (%s)" % (following_segment["label"], cue_type))
    label = str(_prop(cue, "label"))
    if label != following_segment["label"]:
        raise RuntimeError("following Scene label mismatch")
    return label


def _run_rematch_only(unreal, scene_label, run_id):
    saved_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    soft_dir = os.path.join(saved_dir, "CodexSoftGoods")
    mode_path = os.path.join(soft_dir, "extend_scene_playback_mode.json")
    script_path = os.path.join(soft_dir, "extend_scene_playback.py")
    report_path = os.path.join(soft_dir, "extend_scene_playback.json")
    if not os.path.isfile(script_path):
        raise RuntimeError("rematch script is missing: %s" % script_path)
    previous = None
    if os.path.isfile(mode_path):
        with open(mode_path, "rb") as handle:
            previous = handle.read()
    mode = {"scene_label": scene_label, "rematch_only": True, "dry_run": False, "run_id": run_id}
    try:
        with open(mode_path, "w", encoding="utf-8") as handle:
            json.dump(mode, handle, separators=(",", ":"), sort_keys=True)
        with open(script_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        scope = {"__name__": "slow_walk_rematch_%s" % run_id, "__file__": script_path}
        exec(compile(source, script_path, "exec"), scope)
        if not os.path.isfile(report_path):
            raise RuntimeError("rematch did not write its report")
        with open(report_path, "r", encoding="utf-8") as handle:
            report = json.load(handle)
        if not report.get("ok"):
            raise RuntimeError("rematch_only failed: %s" % report.get("message"))
        return report
    finally:
        if previous is None:
            # The normal project already has this mode file.  If it did not,
            # leave the run's explicit configuration as evidence rather than
            # permanently deleting a newly created file.
            pass
        else:
            with open(mode_path, "wb") as handle:
                handle.write(previous)


def _write_report(unreal, short, mode, run_id, report):
    directory = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor"
    )
    safe_run = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run_id)
    path = os.path.join(directory, "passage_slow_walk_%s_%s_%s.json" % (short, mode.lower(), safe_run))
    latest = os.path.join(directory, "passage_slow_walk_%s_latest.json" % short)
    for output in (path, latest):
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
    return path


def _set_timings(unreal, show, state, plan):
    show.modify()
    settings_rows = list(_prop(show, "passage_settings"))
    settings = settings_rows[state["settings_index"]]
    settings.set_editor_property("lead_in_frames", unreal.FrameNumber(plan["lead_frames"]))
    settings.set_editor_property("tail_frames", unreal.FrameNumber(plan["tail_frames"]))
    settings_rows[state["settings_index"]] = settings
    show.set_editor_property("passage_settings", settings_rows)

    cues = list(_prop(show, "cues"))
    for row, new_interval in zip(state["rows"], plan["intervals"]):
        cue = cues[row["cue_index"]]
        wing = _prop(cue, "wing_pair")
        wing.set_editor_property("interval_to_next", unreal.FrameNumber(int(new_interval)))
        cue.set_editor_property("wing_pair", wing)
        cues[row["cue_index"]] = cue
    show.set_editor_property("cues", cues)


def _passage_actor(unreal, show, passage_guid):
    actors = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if not isinstance(actor, unreal.InfinityStagePassageActor):
            continue
        if _asset_id(_prop(actor, "show_asset")) != SHOW_PATH:
            continue
        if _guid(unreal, _prop(actor, "passage_guid")) == passage_guid:
            actors.append(actor)
    if len(actors) != 1:
        raise RuntimeError("expected one Passage Actor, found %d" % len(actors))
    return actors[0]


def _save_scoped(unreal, world):
    saved = {
        SHOW_PATH: bool(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False)),
        MASTER_PATH: bool(unreal.EditorAssetLibrary.save_asset(MASTER_PATH, only_if_is_dirty=False)),
        EXPECTED_WORLD: bool(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()),
    }
    if not all(saved.values()):
        raise RuntimeError("targeted save failed: %s" % saved)
    census = _census(unreal)
    if census != {"content": [], "maps": []}:
        raise RuntimeError("dirty packages remain after targeted saves: %s" % census)
    return saved, census


def run_unreal(passage_label, mode, run_id):
    """Execute one DRY/APPLY/REVERT run in the already-open editor."""
    import unreal

    passage_label = str(passage_label).strip()
    mode = str(mode).strip().upper()
    run_id = str(run_id).strip()
    if passage_label not in VALID_PASSAGES:
        raise RuntimeError("SLOW_WALK_STOPPED|run=%s|reason=INVALID_PASSAGE|label=%s" % (run_id, passage_label))
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise RuntimeError("SLOW_WALK_STOPPED|run=%s|reason=INVALID_MODE|mode=%s" % (run_id, mode))
    if not run_id:
        raise RuntimeError("SLOW_WALK_STOPPED|reason=EMPTY_RUN_ID")
    short = VALID_PASSAGES[passage_label]
    report = {"ok": False, "run": run_id, "mode": mode, "passage_label": passage_label, "passage_short": short}

    try:
        project_dir = os.path.normcase(os.path.normpath(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        )).rstrip("\\/")
        if project_dir != EXPECTED_PROJECT:
            raise RuntimeError("wrong project directory %s" % project_dir)
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            raise RuntimeError("PIE_OR_SIE_ACTIVE")
        world = editor.get_editor_world()
        if world is None or _asset_id(world) != EXPECTED_WORLD:
            raise RuntimeError("WRONG_WORLD|world=%s" % _asset_id(world))
        if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
            raise RuntimeError("SEQUENCER_IS_OPEN")
        before_census = _census(unreal)
        report["census_before"] = before_census
        if before_census != {"content": [], "maps": []}:
            raise RuntimeError("DIRTY_BEFORE|census=%s" % json.dumps(before_census, sort_keys=True))

        show = unreal.load_asset(SHOW_PATH)
        master = unreal.load_asset(MASTER_PATH)
        if show is None or master is None:
            raise RuntimeError("Show or Master did not load")
        tick_rate_value = _prop(show, "tick_resolution")
        tick_rate = float(tick_rate_value.numerator) / float(tick_rate_value.denominator)
        if abs(tick_rate - 24000.0) > 1.0e-6:
            raise RuntimeError("unexpected Show tick resolution %.9f" % tick_rate)
        target_ticks = _round_positive(TARGET_SECONDS * tick_rate)
        before = _passage_state(unreal, show, passage_label)
        plan = plan_scaled_timing(before["lead_frames"], before["intervals"], before["tail_frames"], target_ticks)
        if plan["old_ticks"] != before["duration_ticks"]:
            raise RuntimeError("planner/current duration mismatch")
        old_seconds = before["duration_ticks"] / tick_rate
        new_seconds = plan["new_ticks"] / tick_rate
        old_speed = before["route_cm"] / old_seconds
        new_speed = before["route_cm"] / new_seconds
        segments_before = _compiled_segments(unreal, show)
        segment_match = [row for row in segments_before if row["label"] == passage_label]
        if len(segment_match) != 1:
            raise RuntimeError("compiled Passage segment count is %d" % len(segment_match))
        compiled_duration = segment_match[0]["end_tick"] - segment_match[0]["start_tick"]
        if compiled_duration != before["duration_ticks"]:
            raise RuntimeError("compiled duration %d != authored duration %d" % (compiled_duration, before["duration_ticks"]))
        delta_ticks = plan["new_ticks"] - before["duration_ticks"]
        delta_s = delta_ticks / tick_rate
        predicted, following_segment = _predicted_segment_shifts(segments_before, passage_label, delta_ticks)
        following_scene = _following_scene(unreal, show, following_segment)
        master_sections = _master_sections(
            master,
            before["passage_guid"],
            segment_match[0]["start_tick"] / tick_rate,
            segment_match[0]["end_tick"] / tick_rate,
            delta_s,
        )
        if not master_sections:
            raise RuntimeError("no managed Master sections were available for shift reporting")
        report.update({
            "tick_rate": tick_rate,
            "target_seconds": TARGET_SECONDS,
            "target_ticks": target_ticks,
            "old_seconds": old_seconds,
            "new_seconds": new_seconds,
            "k": plan["k"],
            "route_cm": before["route_cm"],
            "old_speed_cm_s": old_speed,
            "new_speed_cm_s": new_speed,
            "master_range_delta_ticks": delta_ticks,
            "master_range_delta_seconds": delta_s,
            "following_scene": following_scene,
            "plan": plan,
            "protected_before": before["protected"],
            "wing_rows_before": before["rows"],
            "downstream_segment_shifts": predicted,
            "managed_master_section_shifts": master_sections,
        })

        if mode == "DRY":
            after_census = _census(unreal)
            report["census_after"] = after_census
            report["ok"] = after_census == before_census
            if not report["ok"]:
                raise RuntimeError("DRY dirtied packages: %s" % after_census)
            report_path = _write_report(unreal, short, mode, run_id, report)
            unreal.log(
                "SLOW_WALK_DRY_OK|run=%s|passage=%s|old_s=%.6f|new_s=%.3f|k=%.9f|speed_cm_s=%.6f->%.6f|pairs=%d|master_delta_ticks=%d|downstream=%d|following_scene=%s|census=%s|report=%s"
                % (run_id, short, old_seconds, new_seconds, plan["k"], old_speed, new_speed,
                   len(before["rows"]), delta_ticks, len(predicted) - 1, following_scene,
                   json.dumps(after_census, separators=(",", ":"), sort_keys=True), report_path)
            )
            return report

        record_path = os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
            "CodexConductor", "passage_slow_walk_record_%s.json" % short,
        )
        if mode == "APPLY":
            if abs(new_seconds - TARGET_SECONDS) > 1.0e-9:
                raise RuntimeError("planned duration is not exactly 180 seconds")
            backup_dir, backup_files = _backup(unreal, project_dir, short)
            record = {
                "version": 1,
                "run": run_id,
                "passage_label": passage_label,
                "passage_short": short,
                "backup": backup_dir,
                "backup_files": backup_files,
                "before": {
                    "lead_frames": before["lead_frames"],
                    "intervals": before["intervals"],
                    "tail_frames": before["tail_frames"],
                    "duration_ticks": before["duration_ticks"],
                    "protected": before["protected"],
                },
                "after": {
                    "lead_frames": plan["lead_frames"],
                    "intervals": plan["intervals"],
                    "tail_frames": plan["tail_frames"],
                    "duration_ticks": plan["new_ticks"],
                    "protected": before["protected"],
                },
                "following_scene": following_scene,
            }
            with open(record_path, "w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2, sort_keys=True)
            desired_plan = plan
            expected_protected = before["protected"]
        else:
            if not os.path.isfile(record_path):
                raise RuntimeError("revert record is missing: %s" % record_path)
            with open(record_path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
            if record.get("passage_label") != passage_label:
                raise RuntimeError("revert record Passage mismatch")
            assert_protected_unchanged(record["after"]["protected"], before["protected"])
            current_timing = [before["lead_frames"], before["intervals"], before["tail_frames"]]
            applied_timing = [record["after"]["lead_frames"], record["after"]["intervals"], record["after"]["tail_frames"]]
            if current_timing != applied_timing:
                raise RuntimeError("current timing does not match the recorded applied state")
            backup_dir, backup_files = _backup(unreal, project_dir, short, "PreSlowWalkRevert")
            desired_plan = {
                "lead_frames": int(record["before"]["lead_frames"]),
                "intervals": [int(value) for value in record["before"]["intervals"]],
                "tail_frames": int(record["before"]["tail_frames"]),
            }
            expected_protected = record["before"]["protected"]
            following_scene = record["following_scene"]

        _set_timings(unreal, show, before, desired_plan)
        changed = _passage_state(unreal, show, passage_label)
        assert_protected_unchanged(expected_protected, changed["protected"])
        expected_ticks = (
            desired_plan["lead_frames"] + sum(desired_plan["intervals"][:-1]) + desired_plan["tail_frames"]
        )
        if changed["duration_ticks"] != expected_ticks:
            raise RuntimeError("in-memory duration read-back failed")
        actor = _passage_actor(unreal, show, before["passage_guid"])
        if not actor.materialize_passage():
            raise RuntimeError("materialize_passage returned false")
        rebuild = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
        if not rebuild:
            raise RuntimeError("rebuild_managed_master returned %r" % (rebuild,))
        dirty_before_save = _census(unreal)
        allowed_content = {SHOW_PATH, MASTER_PATH}
        if set(dirty_before_save["content"]) - allowed_content or set(dirty_before_save["maps"]) - {EXPECTED_WORLD}:
            raise RuntimeError("out-of-scope dirty packages before save: %s" % dirty_before_save)
        saved, census_after_save = _save_scoped(unreal, world)
        rematch_report = _run_rematch_only(unreal, following_scene, run_id)
        census_after_rematch = _census(unreal)
        if census_after_rematch != {"content": [], "maps": []}:
            raise RuntimeError("rematch left dirty packages: %s" % census_after_rematch)

        show_readback = unreal.load_asset(SHOW_PATH)
        readback = _passage_state(unreal, show_readback, passage_label)
        assert_protected_unchanged(expected_protected, readback["protected"])
        if readback["duration_ticks"] != expected_ticks:
            raise RuntimeError("saved duration read-back failed: %d != %d" % (readback["duration_ticks"], expected_ticks))
        if readback["lead_frames"] != desired_plan["lead_frames"] or readback["intervals"] != desired_plan["intervals"] or readback["tail_frames"] != desired_plan["tail_frames"]:
            raise RuntimeError("saved timing field read-back failed")
        report.update({
            "backup": backup_dir,
            "backup_files": backup_files,
            "record": record_path,
            "dirty_before_save": dirty_before_save,
            "saved": saved,
            "census_after_save": census_after_save,
            "rematch": rematch_report,
            "census_after": census_after_rematch,
            "readback_duration_ticks": readback["duration_ticks"],
            "readback_duration_seconds": readback["duration_ticks"] / tick_rate,
            "protected_after": readback["protected"],
            "ok": True,
        })
        report_path = _write_report(unreal, short, mode, run_id, report)
        marker = "SLOW_WALK_APPLY_OK" if mode == "APPLY" else "SLOW_WALK_REVERT_OK"
        rematch_backup = rematch_report.get("backup")
        unreal.log(
            "%s|run=%s|passage=%s|duration_s=%.6f|pairs=%d|materialized=1|rebuild=1|following_scene=%s|backup=%s|rematch_backup=%s|record=%s|census=%s|report=%s"
            % (marker, run_id, short, readback["duration_ticks"] / tick_rate, len(readback["rows"]),
               following_scene, backup_dir, rematch_backup, record_path,
               json.dumps(census_after_rematch, separators=(",", ":"), sort_keys=True), report_path)
        )
        return report
    except Exception as error:
        report["error"] = str(error)
        report["census_on_failure"] = _census(unreal)
        try:
            report_path = _write_report(unreal, short, mode, run_id, report)
        except Exception:
            report_path = "unwritten"
        unreal.log_error(
            "SLOW_WALK_STOPPED|run=%s|passage=%s|mode=%s|reason=%s|census=%s|report=%s"
            % (run_id, short, mode, error,
               json.dumps(report["census_on_failure"], separators=(",", ":"), sort_keys=True), report_path)
        )
        raise
