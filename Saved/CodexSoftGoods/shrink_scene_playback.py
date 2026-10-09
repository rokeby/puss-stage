"""Safely shorten one enabled Scene/Sequence cue and rebuild the managed Master.

Offline-authored for P24 (8 Oct 2026); this file has NOT been run in Unreal here.

Configuration: ``shrink_scene_playback_mode.json`` beside this file.

    {"mode": "DRY", "confirm": "DRY SHRINK",
     "cue_label": "Interaction 2 \u2014 Turnips", "new_end_frame": 1950}

Modes are DRY, APPLY, and REVERT.  Confirmation is always ``<MODE> SHRINK``.
DRY inventories every direct section/key/marker at or beyond the new end and
lists downstream absolute Master Passage channels.  APPLY creates a verified
backup and an exclusive record before changing anything, trims crossing
sections, deactivates later sections, requires gap-free camera-cut coverage,
rebuilds the managed Master, verifies key carry and exact segment shifts, and
saves only the cue sequence, Master, and (only when dirty) Show.  REVERT is
drift-guarded, creates its own backup/transaction record, restores the recorded
range/section state and recorded absolute Passage key times, then rebuilds and
reads everything back.

No level, actor, material, marker, key value, or cue-array mutation is made.
The conductor must run InfinityStage.Editor.SavedMasterMatchesShow afterwards.
Success markers include a run id:
  PUSS_SOFTGOODS_SCENE_SHRINK_<MODE>_OK|run=...

Reuse: extend_scene_playback.py cannot be imported normally because it ends in
an unconditional main().  At runtime _extend_helpers follows the established
curtain_sleight.py:1350-1363 precedent: verify that exact suffix, execute only
the definitions, and require the helper names used here.
"""

import datetime
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness imports the pure planning helpers.
    unreal = None


SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MODE_NAME = "shrink_scene_playback_mode.json"
RECORD_NAME = "shrink_scene_playback_record.json"
EXTEND_TOOL = "extend_scene_playback.py"
MARK = "PUSS_SOFTGOODS_SCENE_SHRINK"
VALID_MODES = ("DRY", "APPLY", "REVERT")


# ---------------------------------------------------------------------------
# Pure planning and verification helpers (covered by the offline harness).


def validate_args(args):
    problems = []
    mode = str(args.get("mode") or "").upper()
    if mode not in VALID_MODES:
        problems.append("MODE_INVALID: %r" % args.get("mode"))
    if args.get("confirm") != "%s SHRINK" % mode:
        problems.append("CONFIRM_MISMATCH: want %r" % ("%s SHRINK" % mode))
    if not isinstance(args.get("cue_label"), str) or not args.get("cue_label", "").strip():
        problems.append("CUE_LABEL_REQUIRED")
    new_end = args.get("new_end_frame")
    if isinstance(new_end, bool) or not isinstance(new_end, int):
        problems.append("NEW_END_FRAME_MUST_BE_INT")
    return problems


def plan_section_changes(rows, new_end):
    """Return all sections affected by a shorter end; never proposes deletion."""
    changes = []
    for row in rows:
        start, end = row.get("start"), row.get("end")
        effective_start = float("-inf") if start is None else int(start)
        effective_end = float("inf") if end is None else int(end)
        if effective_start >= new_end:
            after = dict(row, active=False)
            changes.append({"action": "deactivate", "before": dict(row), "after": after})
        elif effective_end > new_end:
            after = dict(row, end=int(new_end), has_end=True)
            changes.append({"action": "trim", "before": dict(row), "after": after})
    return changes


def cut_coverage_rows(playback_start, playback_end, rows):
    """Gap report for active camera-cut rows using display-frame half-open spans."""
    spans = []
    for row in rows:
        if not row.get("active", True):
            continue
        a = playback_start if row.get("start") is None else int(row["start"])
        b = playback_end if row.get("end") is None else int(row["end"])
        if b > playback_start and a < playback_end:
            spans.append((max(playback_start, a), min(playback_end, b)))
    spans.sort()
    gaps, cursor = [], int(playback_start)
    for a, b in spans:
        if a > cursor:
            gaps.append([cursor, a])
        cursor = max(cursor, b)
        if cursor >= playback_end:
            break
    if cursor < playback_end:
        gaps.append([cursor, playback_end])
    return {"range": [playback_start, playback_end], "cuts": [list(x) for x in spans], "gaps": gaps}


def planned_rows(rows, changes):
    by_id = {c["before"]["id"]: c["after"] for c in changes}
    return [dict(by_id.get(row["id"], row)) for row in rows]


def passage_key_delta_failures(before, after, downstream_guids, delta_ticks, tolerance_ticks=480):
    """Require downstream sections and every key to move by delta; earlier ones by zero."""
    downstream = set(downstream_guids)
    failures = []
    for guid, old in before.items():
        now = after.get(guid)
        if now is None:
            failures.append("%s vanished" % guid)
            continue
        expected = int(delta_ticks) if guid in downstream else 0
        if abs((now["section_start_tick"] - old["section_start_tick"]) - expected) > tolerance_ticks:
            failures.append("%s section delta %d != %d" %
                            (guid, now["section_start_tick"] - old["section_start_tick"], expected))
        if set(now["channels"]) != set(old["channels"]):
            failures.append("%s channel set changed" % guid)
            continue
        for name, old_keys in old["channels"].items():
            new_keys = now["channels"][name]
            if len(old_keys) != len(new_keys):
                failures.append("%s %s key count %d -> %d" % (guid, name, len(old_keys), len(new_keys)))
                continue
            for index, (a, b) in enumerate(zip(old_keys, new_keys)):
                moved = b["frame"] - a["frame"]
                if abs(moved - expected) > tolerance_ticks or abs(float(b["value"]) - float(a["value"])) > 1.0e-5:
                    failures.append("%s %s[%d] delta/value mismatch: %r -> %r, expected %d" %
                                    (guid, name, index, a, b, expected))
    extra = sorted(set(after) - set(before))
    if extra:
        failures.append("new Passage sections: %r" % extra)
    return failures


def segment_retime_failures(before, after, cue_label, delta_s, tolerance_s=0.05):
    """Earlier spans unchanged; cue end and both bounds of later spans shift by delta."""
    failures = []
    if len(before) != len(after):
        return ["segment count %d -> %d" % (len(before), len(after))]
    indices = [i for i, row in enumerate(before) if row["label"] == cue_label]
    if len(indices) != 1:
        return ["cue segment count %d" % len(indices)]
    target = indices[0]
    for index, (old, now) in enumerate(zip(before, after)):
        if old["label"] != now["label"]:
            failures.append("segment %d label %r -> %r" % (index, old["label"], now["label"]))
            continue
        want_start = 0.0 if index <= target else float(delta_s)
        want_end = 0.0 if index < target else float(delta_s)
        got_start = float(now["start"]) - float(old["start"])
        got_end = float(now["end"]) - float(old["end"])
        if abs(got_start - want_start) > tolerance_s or abs(got_end - want_end) > tolerance_s:
            failures.append("%s shifts start/end %.3f/%.3f != %.3f/%.3f" %
                            (old["label"], got_start, got_end, want_start, want_end))
    return failures


# ---------------------------------------------------------------------------
# Unreal-only discovery, mutation, persistence, and read-back.


def _here():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _rate(value):
    return float(value.numerator) / float(value.denominator)


def _write_json(path, value, exclusive=False):
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _load_json(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise RuntimeError("missing JSON: %s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _census():
    return {
        "content": sorted(p.get_path_name() for p in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(p.get_path_name() for p in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _content_file(path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _backup(run, label, paths):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "PreSceneShrink%s-%s" % (label, run))
    os.makedirs(folder, exist_ok=False)
    copied = []
    for path in paths:
        source = _content_file(path)
        if not os.path.isfile(source):
            raise RuntimeError("backup source missing: %s" % source)
        target = os.path.join(folder, os.path.basename(source))
        shutil.copy2(source, target)
        if os.path.getsize(source) != os.path.getsize(target):
            raise RuntimeError("backup size mismatch: %s" % source)
        copied.append(target)
    return folder, copied


def _extend_helpers(run):
    path = os.path.join(_here(), EXTEND_TOOL)
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    if not source.rstrip().endswith("\nmain()"):
        _stop(run, "EXTEND_TOOL_SHAPE: extend_scene_playback.py no longer ends with main()")
    namespace = {"__name__": "extend_scene_playback_helpers_for_shrink", "__file__": path}
    exec(compile(source.rstrip()[:-len("main()")], path, "exec"), namespace)  # reviewed project tool
    required = ("cut_coverage", "compiled_segments", "show_master_match", "segment_deltas",
                "passage_keys_section_relative", "key_carry_failures")
    missing = [name for name in required if name not in namespace]
    if missing:
        _stop(run, "EXTEND_HELPERS_MISSING|%r" % missing)
    return namespace


def _stop(run, reason, report=None):
    if report is not None:
        report["ok"] = False
        report["stop_reason"] = str(reason)
        _write_json(report["report_path"], report)
    unreal.log_error("%s_STOPPED|run=%s|%s" % (MARK, run, reason))
    raise RuntimeError(str(reason))


def _track_name(track):
    try:
        return str(track.get_display_name())
    except Exception:  # noqa: BLE001 - not every track exposes a display name.
        return str(track.get_name())


def _property_name(track):
    try:
        return str(track.get_property_name())
    except Exception:  # noqa: BLE001 - only property tracks expose it.
        return ""


def _owners(seq):
    yield {"kind": "root", "guid": "", "name": "<root>", "tracks": list(seq.get_tracks())}
    for binding in seq.get_bindings():
        yield {"kind": "binding", "guid": _guid(binding.get_id()),
               "name": str(binding.get_display_name()), "tracks": list(binding.get_tracks())}


def _section_rows(seq):
    rows = []
    for owner in _owners(seq):
        for track_index, track in enumerate(owner["tracks"]):
            track_class = track.get_class().get_name()
            for section_index, section in enumerate(track.get_sections()):
                locator = {"owner_kind": owner["kind"], "binding_guid": owner["guid"],
                           "track_index": track_index, "section_index": section_index,
                           "track_class": track_class, "track_name": _track_name(track),
                           "property_name": _property_name(track),
                           "section_class": section.get_class().get_name()}
                locator["id"] = "%s|%s|%d|%d|%s" % (
                    owner["kind"], owner["guid"], track_index, section_index, track_class)
                detail = {}
                if hasattr(section, "get_sequence"):
                    nested = section.get_sequence()
                    detail["sequence"] = nested.get_path_name().split(".")[0] if nested is not None else None
                try:
                    sound = section.get_editor_property("sound")
                    detail["sound"] = sound.get_path_name().split(".")[0] if sound is not None else None
                except Exception:  # noqa: BLE001 - only audio sections expose sound.
                    pass
                if "CameraCut" in track_class and hasattr(section, "get_camera_binding_id"):
                    detail["camera_binding_guid"] = _guid(
                        section.get_camera_binding_id().get_editor_property("guid"))
                rows.append(dict(locator, owner_name=owner["name"], detail=detail,
                                 start=int(section.get_start_frame()) if section.has_start_frame() else None,
                                 end=int(section.get_end_frame()) if section.has_end_frame() else None,
                                 has_start=bool(section.has_start_frame()), has_end=bool(section.has_end_frame()),
                                 active=bool(section.is_active())))
    return rows


def _locate_section(seq, locator):
    if locator["owner_kind"] == "root":
        tracks = list(seq.get_tracks())
    else:
        bindings = [b for b in seq.get_bindings() if _guid(b.get_id()) == locator["binding_guid"]]
        if len(bindings) != 1:
            raise RuntimeError("binding locator failed: %s" % locator["binding_guid"])
        tracks = list(bindings[0].get_tracks())
    index = int(locator["track_index"])
    if index >= len(tracks):
        raise RuntimeError("track locator out of range: %r" % locator)
    track = tracks[index]
    if track.get_class().get_name() != locator["track_class"] or _track_name(track) != locator["track_name"]:
        raise RuntimeError("track locator drift: %r" % locator)
    sections = list(track.get_sections())
    section_index = int(locator["section_index"])
    if section_index >= len(sections) or sections[section_index].get_class().get_name() != locator["section_class"]:
        raise RuntimeError("section locator drift: %r" % locator)
    return sections[section_index]


def _key_rows(seq, new_end):
    rows = []
    for owner in _owners(seq):
        for track_index, track in enumerate(owner["tracks"]):
            for section_index, section in enumerate(track.get_sections()):
                for channel_index, channel in enumerate(section.get_all_channels()):
                    try:
                        channel_name = str(channel.get_editor_property("channel_name"))
                    except Exception:  # noqa: BLE001
                        channel_name = "channel_%d" % channel_index
                    for key_index, key in enumerate(channel.get_keys()):
                        time = key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                        frame = int(time.frame_number.value)
                        if frame < new_end:
                            continue
                        try:
                            value = key.get_value()
                            value = float(value) if isinstance(value, (int, float)) else str(value)
                        except Exception as exc:  # noqa: BLE001 - event/object keys may not expose a simple value.
                            value = "<unreadable:%s>" % exc
                        rows.append({"owner": owner["name"], "binding_guid": owner["guid"],
                                     "track_index": track_index, "track_class": track.get_class().get_name(),
                                     "track_name": _track_name(track), "section_index": section_index,
                                     "channel_index": channel_index, "channel_name": channel_name,
                                     "key_index": key_index, "frame": frame,
                                     "sub_frame": float(getattr(time, "sub_frame", 0.0)), "value": value})
    return rows


def _markers(seq, new_end):
    values = seq.get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return [{"label": str(m.label), "frame": int(m.frame_number.value)} for m in values
            if int(m.frame_number.value) >= new_end]


def _inventory(seq, new_end):
    sections = _section_rows(seq)
    affected = plan_section_changes(sections, new_end)
    rows = [c["before"] for c in affected]
    specialized = {"camera_cuts": [], "audio": [], "sub_sequences": [], "events": []}
    for row in rows:
        cls = "%s %s" % (row["track_class"], row["section_class"])
        if "CameraCut" in cls:
            specialized["camera_cuts"].append(row)
        if "Audio" in cls:
            specialized["audio"].append(row)
        if "SubTrack" in cls or "SubSection" in cls:
            specialized["sub_sequences"].append(row)
        if "Event" in cls:
            specialized["events"].append(row)
    return dict({"sections": rows, "keys": _key_rows(seq, new_end), "markers": _markers(seq, new_end)},
                **specialized), sections, affected


def _cut_rows(section_rows):
    return [row for row in section_rows if "CameraCut" in "%s %s" %
            (row["track_class"], row["section_class"])]


def _passage_key_snapshot(master):
    tick_rate = _rate(master.get_tick_resolution())
    result = {}
    for track in master.get_tracks():
        if "InfinityPassage" not in track.get_class().get_name():
            continue
        for section in track.get_sections():
            guid = _guid(section.get_editor_property("passage_guid"))
            channels = {}
            for channel in section.get_all_channels():
                name = str(channel.get_editor_property("channel_name"))
                keys = []
                for key in channel.get_keys():
                    time = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
                    keys.append({"frame": int(time.frame_number.value),
                                 "sub_frame": float(getattr(time, "sub_frame", 0.0)),
                                 "value": round(float(key.get_value()), 6)})
                if keys:
                    channels[name] = keys
            result[guid] = {"section_start_tick": int(round(section.get_start_frame_seconds() * tick_rate)),
                            "section_start_s": round(section.get_start_frame_seconds(), 6),
                            "channels": channels}
    return result


def _downstream_multi_key_channels(snapshot, after_s):
    rows = []
    for guid, passage in snapshot.items():
        if passage["section_start_s"] < after_s - 1.0e-3:
            continue
        for name, keys in passage["channels"].items():
            if len(keys) >= 2:
                rows.append({"passage_guid": guid, "section_start_s": passage["section_start_s"],
                             "channel": name, "absolute_keys": keys})
    return rows


def _downstream_passage_guids(snapshot, after_s):
    return sorted(guid for guid, passage in snapshot.items()
                  if passage["section_start_s"] >= after_s - 1.0e-3)


def _restore_passage_keys(master, recorded):
    """Restore recorded absolute tick times; values/counts must still match."""
    touched = 0
    sections = {}
    for track in master.get_tracks():
        if "InfinityPassage" not in track.get_class().get_name():
            continue
        for section in track.get_sections():
            sections[_guid(section.get_editor_property("passage_guid"))] = section
    if set(sections) != set(recorded):
        raise RuntimeError("Passage GUID set changed while restoring keys")
    for guid, old in recorded.items():
        channels = {str(c.get_editor_property("channel_name")): c for c in sections[guid].get_all_channels()}
        if set(channels) != set(old["channels"]):
            raise RuntimeError("Passage channel set changed for %s" % guid)
        for name, rows in old["channels"].items():
            keys = list(channels[name].get_keys())
            if len(keys) != len(rows):
                raise RuntimeError("Passage key count changed for %s %s" % (guid, name))
            for key, row in zip(keys, rows):
                if abs(float(key.get_value()) - float(row["value"])) > 1.0e-5:
                    raise RuntimeError("Passage key value changed for %s %s" % (guid, name))
                now = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
                if int(now.frame_number.value) != int(row["frame"]) or \
                        abs(float(getattr(now, "sub_frame", 0.0)) - float(row["sub_frame"])) > 1.0e-6:
                    key.set_time(unreal.FrameNumber(value=int(row["frame"])), float(row["sub_frame"]),
                                 unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
                    touched += 1
    return touched


def _apply_section_changes(seq, changes, use_after):
    for change in changes:
        state = change["after"] if use_after else change["before"]
        section = _locate_section(seq, state)
        if state.get("has_end"):
            section.set_end_frame(int(state["end"]))
        else:
            section.set_end_frame_bounded(False)
        section.set_is_active(bool(state["active"]))


def _target_state_failures(seq, changes, use_after):
    failures = []
    for change in changes:
        want = change["after"] if use_after else change["before"]
        try:
            section = _locate_section(seq, want)
        except Exception as exc:  # noqa: BLE001
            failures.append(str(exc))
            continue
        got_end = int(section.get_end_frame()) if section.has_end_frame() else None
        if bool(section.has_end_frame()) != bool(want["has_end"]) or got_end != want["end"] or \
                bool(section.is_active()) != bool(want["active"]):
            failures.append("%s wanted end/active %r/%r got %r/%r" %
                            (want["id"], want["end"], want["active"], got_end, bool(section.is_active())))
    return failures


def _save_named(run, allowed):
    census = _census()
    unexpected = [p for p in census["content"] if p not in allowed] + list(census["maps"])
    if unexpected:
        _stop(run, "UNEXPECTED_DIRTY|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))
    saved = {}
    for path in (allowed[0], MASTER, SHOW):
        if path in census["content"]:
            saved[path] = bool(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=True))
    if allowed[0] not in saved or MASTER not in saved or not all(saved.values()):
        _stop(run, "REQUIRED_SAVE_MISSING_OR_FAILED|%r" % saved)
    final = _census()
    if final["content"] or final["maps"]:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(final))
    return saved, census, final


def _context(run, args):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_RUNNING")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    census = _census()
    if census["content"] or census["maps"]:
        _stop(run, "DIRTY_CENSUS|%s" % json.dumps(census))
    show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")) == args["cue_label"]]
    if len(cues) != 1 or not bool(cues[0].get_editor_property("enabled")):
        _stop(run, "CUE_NOT_EXACTLY_ONE_ENABLED|%r" % args["cue_label"])
    cue_type = str(cues[0].get_editor_property("type"))
    if cue_type not in (str(unreal.InfinityCueType.SCENE), str(unreal.InfinityCueType.SEQUENCE)):
        _stop(run, "CUE_NOT_SCENE_OR_SEQUENCE|%s" % cue_type)
    seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
    if seq is None:
        _stop(run, "CUE_HAS_NO_SEQUENCE")
    return show, master, cues[0], seq, census


def _report_base(run, mode, args, seq, census):
    path = os.path.join(_here(), "shrink_scene_playback_%s_%s.json" % (mode.lower(), run))
    return {"schema_version": 1, "tool": "shrink_scene_playback.py", "run": run, "mode": mode,
            "args": args, "sequence": seq.get_path_name().split(".")[0], "dirty_preflight": census,
            "report_path": path, "ok": False,
            "proof_note": "Unreal results are measured when this report is emitted; this source was authored offline."}


def _read_plan(show, master, seq, args, ext):
    new_end = int(args["new_end_frame"])
    start, old_end = int(seq.get_playback_start()), int(seq.get_playback_end())
    if not start < new_end < old_end:
        raise RuntimeError("new end must be strictly inside playback range: %d < %d < %d" %
                           (start, new_end, old_end))
    inventory, all_sections, changes = _inventory(seq, new_end)
    cut_rows = _cut_rows(all_sections)
    after_rows = planned_rows(cut_rows, changes)
    planned_coverage = cut_coverage_rows(start, new_end, after_rows)
    segments = ext["compiled_segments"](show)
    cue_segments = [row for row in segments if row["label"] == args["cue_label"]]
    if len(cue_segments) != 1:
        raise RuntimeError("cue compiled-segment count is %d" % len(cue_segments))
    passage_keys = _passage_key_snapshot(master)
    downstream = _downstream_multi_key_channels(passage_keys, cue_segments[0]["end"])
    rate = _rate(seq.get_display_rate())
    tick_rate = _rate(master.get_tick_resolution())
    delta_s = (new_end - old_end) / rate
    return {"playback_before": [start, old_end], "playback_after": [start, new_end],
            "fps": rate, "master_tick_rate": tick_rate, "delta_frames": new_end - old_end,
            "removed_frames": old_end - new_end,
            "delta_s": round(delta_s, 6), "delta_ticks": int(round(delta_s * tick_rate)),
            "inventory_past_new_end": inventory, "section_changes": changes,
            "coverage_before": ext["cut_coverage"](seq), "coverage_planned": planned_coverage,
            "segments_before": segments, "passage_keys_before": passage_keys,
            "extend_passage_keys_relative_before": ext["passage_keys_section_relative"](master),
            "downstream_passage_multi_key_channels": downstream,
            "downstream_passage_guids": _downstream_passage_guids(passage_keys, cue_segments[0]["end"])}


def run_dry(run, args):
    show, master, cue, seq, census = _context(run, args)
    report = _report_base(run, "DRY", args, seq, census)
    ext = _extend_helpers(run)
    try:
        report["plan"] = _read_plan(show, master, seq, args, ext)
    except Exception as exc:  # noqa: BLE001
        _stop(run, "PLAN_REFUSED|%s" % exc, report)
    report["apply_ready"] = not report["plan"]["coverage_planned"]["gaps"]
    report["ok"] = True
    _write_json(report["report_path"], report)
    unreal.log("%s_DRY_OK|run=%s|cue=%s|end=%d|sections=%d|keys=%d|markers=%d|cut_gaps=%s|report=%s" %
               (MARK, run, args["cue_label"], args["new_end_frame"],
                len(report["plan"]["inventory_past_new_end"]["sections"]),
                len(report["plan"]["inventory_past_new_end"]["keys"]),
                len(report["plan"]["inventory_past_new_end"]["markers"]),
                report["plan"]["coverage_planned"]["gaps"], report["report_path"]))
    return report


def run_apply(run, args):
    show, master, cue, seq, census = _context(run, args)
    report = _report_base(run, "APPLY", args, seq, census)
    ext = _extend_helpers(run)
    record_path = os.path.join(_here(), RECORD_NAME)
    if os.path.exists(record_path):
        old_record = _load_json(record_path)
        if old_record.get("applied"):
            _stop(run, "RECORD_EXISTS|%s|REVERT first" % record_path, report)
        old_plan = old_record.get("plan") or {}
        stale_failures = []
        if old_record.get("sequence") != report["sequence"] or \
                int(seq.get_playback_end()) != int((old_plan.get("playback_before") or [0, -1])[1]):
            stale_failures.append("sequence/range differs from unapplied record")
        if old_plan.get("section_changes"):
            stale_failures += _target_state_failures(seq, old_plan["section_changes"], False)
        if old_plan.get("segments_before"):
            stale_failures += segment_retime_failures(old_plan["segments_before"], ext["compiled_segments"](show),
                                                       old_record.get("cue_label"), 0.0)
        if old_plan.get("passage_keys_before"):
            stale_failures += passage_key_delta_failures(
                old_plan["passage_keys_before"], _passage_key_snapshot(master), [], 0)
        if stale_failures:
            _stop(run, "UNAPPLIED_RECORD_BUT_LIVE_STATE_DRIFTED|%r" % stale_failures[:8], report)
        os.rename(record_path, record_path + ".stopped-" + run)
    try:
        plan = _read_plan(show, master, seq, args, ext)
    except Exception as exc:  # noqa: BLE001
        _stop(run, "PLAN_REFUSED|%s" % exc, report)
    report["plan"] = plan
    if plan["coverage_planned"]["gaps"]:
        _stop(run, "CUT_GAP_REFUSED|%r|nothing mutated" % plan["coverage_planned"]["gaps"], report)
    seq_path = report["sequence"]
    try:
        backup, copied = _backup(run, "", (seq_path, MASTER, SHOW))
    except Exception as exc:  # noqa: BLE001
        _stop(run, "BACKUP_FAILED|%s" % exc, report)
    record = {"schema_version": 1, "tool": "shrink_scene_playback.py", "run": run, "applied": False,
              "cue_label": args["cue_label"], "new_end_frame": args["new_end_frame"], "sequence": seq_path,
              "backup": backup, "backup_files": copied, "plan": plan}
    try:
        _write_json(record_path, record, exclusive=True)
    except FileExistsError:
        _stop(run, "RECORD_RACE|%s" % record_path, report)

    seq.set_playback_end(int(args["new_end_frame"]))
    try:
        _apply_section_changes(seq, plan["section_changes"], True)
    except Exception as exc:  # noqa: BLE001
        _stop(run, "SECTION_MUTATION_FAILED|%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
              (exc, backup), report)
    coverage = ext["cut_coverage"](seq)
    if coverage["gaps"]:
        _stop(run, "CUT_GAPS_AFTER_WRITE|%r|NOTHING SAVED; Don't-Save restart" % coverage["gaps"], report)
    rebuild = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    if not rebuild:
        _stop(run, "REBUILD_FAILED|%r|NOTHING SAVED; Don't-Save restart" % rebuild, report)
    segments_after = ext["compiled_segments"](show)
    section_failures = _target_state_failures(seq, plan["section_changes"], True)
    segment_failures = segment_retime_failures(plan["segments_before"], segments_after, args["cue_label"],
                                               plan["delta_s"])
    passage_after = _passage_key_snapshot(master)
    key_failures = passage_key_delta_failures(plan["passage_keys_before"], passage_after,
                                              plan["downstream_passage_guids"], plan["delta_ticks"])
    helper_key_failures = ext["key_carry_failures"](
        plan["extend_passage_keys_relative_before"], ext["passage_keys_section_relative"](master))
    failures = section_failures + segment_failures + key_failures + helper_key_failures
    report.update({"coverage_after_write": coverage, "rebuild_result": str(rebuild),
                   "segments_after": segments_after, "segment_failures": segment_failures,
                   "passage_keys_after": passage_after, "key_carry_failures": key_failures,
                   "section_failures": section_failures})
    if failures:
        _stop(run, "PRESAVE_READBACK_FAILED|%r|NOTHING SAVED; Don't-Save restart" % failures[:8], report)
    allowed = (seq_path, MASTER, SHOW)
    try:
        saved, dirty_before_save, dirty_final = _save_named(run, allowed)
    except Exception as exc:  # _stop raises RuntimeError after logging.
        report["save_exception"] = str(exc)
        _write_json(report["report_path"], report)
        raise
    seq2, show2, master2 = unreal.load_asset(seq_path), unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    after2 = _passage_key_snapshot(master2)
    readback_failures = _target_state_failures(seq2, plan["section_changes"], True)
    if int(seq2.get_playback_end()) != int(args["new_end_frame"]):
        readback_failures.append("playback end did not persist")
    readback_failures += segment_retime_failures(plan["segments_before"], ext["compiled_segments"](show2),
                                                args["cue_label"], plan["delta_s"])
    readback_failures += passage_key_delta_failures(plan["passage_keys_before"], after2,
                                                    plan["downstream_passage_guids"], plan["delta_ticks"])
    master_match = ext["show_master_match"](show2, master2)
    if not master_match["match"]:
        readback_failures.append("show/master mismatch: %r" % master_match)
    report.update({"saved": saved, "dirty_before_save": dirty_before_save, "dirty_final": dirty_final,
                   "playback_readback": [int(seq2.get_playback_start()), int(seq2.get_playback_end())],
                   "show_master_readback": master_match,
                   "saved_master_matches_show_later": "Run InfinityStage.Editor.SavedMasterMatchesShow",
                   "readback_failures": readback_failures})
    if readback_failures:
        record["post_save_failure"] = readback_failures
        _write_json(record_path, record)
        _stop(run, "POSTSAVE_READBACK_FAILED|%r|record kept; REVERT or restore %s" %
              (readback_failures[:8], backup), report)
    record.update({"applied": True, "passage_keys_after": after2,
                   "segments_after": ext["compiled_segments"](show2), "saved": saved})
    _write_json(record_path, record)
    report["ok"] = True
    report["record"] = record_path
    _write_json(report["report_path"], report)
    unreal.log("%s_APPLY_OK|run=%s|cue=%s|end=%d|delta_frames=%d|saved=%s|backup=%s|record=%s|"
               "SavedMasterMatchesShow=later" %
               (MARK, run, args["cue_label"], args["new_end_frame"], plan["delta_frames"],
                sorted(saved), backup, record_path))
    return report


def run_revert(run, args):
    show, master, cue, seq, census = _context(run, args)
    report = _report_base(run, "REVERT", args, seq, census)
    ext = _extend_helpers(run)
    record_path = os.path.join(_here(), RECORD_NAME)
    record = _load_json(record_path, required=False)
    if not record or not record.get("applied"):
        _stop(run, "NO_APPLIED_RECORD|%s" % record_path, report)
    if record["cue_label"] != args["cue_label"] or int(record["new_end_frame"]) != int(args["new_end_frame"]):
        _stop(run, "ARGS_DO_NOT_MATCH_RECORD", report)
    seq_path, plan = record["sequence"], record["plan"]
    if seq.get_path_name().split(".")[0] != seq_path or int(seq.get_playback_end()) != int(record["new_end_frame"]):
        _stop(run, "LIVE_SEQUENCE_DRIFT", report)
    drift = _target_state_failures(seq, plan["section_changes"], True)
    drift += segment_retime_failures(plan["segments_before"], ext["compiled_segments"](show),
                                    record["cue_label"], plan["delta_s"])
    drift += passage_key_delta_failures(plan["passage_keys_before"], _passage_key_snapshot(master),
                                        plan["downstream_passage_guids"], plan["delta_ticks"])
    if drift:
        _stop(run, "APPLIED_STATE_DRIFT|%r" % drift[:8], report)
    try:
        backup, copied = _backup(run, "Revert", (seq_path, MASTER, SHOW))
    except Exception as exc:  # noqa: BLE001
        _stop(run, "REVERT_BACKUP_FAILED|%s" % exc, report)
    txn_path = os.path.join(_here(), "shrink_scene_playback_revert_%s.json" % run)
    txn = {"schema_version": 1, "run": run, "completed": False, "source_record": record_path,
           "backup": backup, "backup_files": copied, "live_segments_before": ext["compiled_segments"](show),
           "live_passage_keys_before": _passage_key_snapshot(master)}
    try:
        _write_json(txn_path, txn, exclusive=True)
    except FileExistsError:
        _stop(run, "REVERT_TRANSACTION_EXISTS|%s" % txn_path, report)

    seq.set_playback_end(int(plan["playback_before"][1]))
    try:
        _apply_section_changes(seq, plan["section_changes"], False)
    except Exception as exc:  # noqa: BLE001
        _stop(run, "REVERT_SECTION_FAILED|%s|NOTHING SAVED; Don't-Save restart" % exc, report)
    rebuild = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    if not rebuild:
        _stop(run, "REVERT_REBUILD_FAILED|NOTHING SAVED; Don't-Save restart", report)
    try:
        restored_keys = _restore_passage_keys(master, plan["passage_keys_before"])
    except Exception as exc:  # noqa: BLE001
        _stop(run, "REVERT_KEY_RESTORE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % exc, report)
    failures = _target_state_failures(seq, plan["section_changes"], False)
    if int(seq.get_playback_end()) != int(plan["playback_before"][1]):
        failures.append("playback range not restored")
    failures += segment_retime_failures(plan["segments_before"], ext["compiled_segments"](show),
                                       record["cue_label"], 0.0)
    failures += passage_key_delta_failures(plan["passage_keys_before"], _passage_key_snapshot(master), [], 0)
    failures += ext["key_carry_failures"](
        plan["extend_passage_keys_relative_before"], ext["passage_keys_section_relative"](master))
    coverage = ext["cut_coverage"](seq)
    master_match = ext["show_master_match"](show, master)
    if not master_match["match"]:
        failures.append("show/master mismatch: %r" % master_match)
    report.update({"backup": backup, "transaction": txn_path, "restored_key_times": restored_keys,
                   "coverage_restored": coverage, "show_master_presave": master_match,
                   "revert_failures": failures})
    if failures:
        _stop(run, "REVERT_PRESAVE_READBACK_FAILED|%r|NOTHING SAVED; Don't-Save restart" % failures[:8], report)
    try:
        saved, dirty_before_save, dirty_final = _save_named(run, (seq_path, MASTER, SHOW))
    except Exception as exc:
        report["save_exception"] = str(exc)
        _write_json(report["report_path"], report)
        raise
    seq2, show2, master2 = unreal.load_asset(seq_path), unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    final = _target_state_failures(seq2, plan["section_changes"], False)
    if int(seq2.get_playback_end()) != int(plan["playback_before"][1]):
        final.append("saved playback range not restored")
    final += segment_retime_failures(plan["segments_before"], ext["compiled_segments"](show2),
                                    record["cue_label"], 0.0)
    final += passage_key_delta_failures(plan["passage_keys_before"], _passage_key_snapshot(master2), [], 0)
    final_match = ext["show_master_match"](show2, master2)
    if not final_match["match"]:
        final.append("saved show/master mismatch: %r" % final_match)
    report.update({"saved": saved, "dirty_before_save": dirty_before_save, "dirty_final": dirty_final,
                   "show_master_readback": final_match,
                   "saved_master_matches_show_later": "Run InfinityStage.Editor.SavedMasterMatchesShow",
                   "readback_failures": final})
    if final:
        _stop(run, "REVERT_POSTSAVE_READBACK_FAILED|%r|restore %s" % (final[:8], backup), report)
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    txn.update({"completed": True, "archived_record": archived, "saved": saved})
    _write_json(txn_path, txn)
    report.update({"ok": True, "archived_record": archived})
    _write_json(report["report_path"], report)
    unreal.log("%s_REVERT_OK|run=%s|cue=%s|end=%d|restored_key_times=%d|saved=%s|backup=%s|record=%s|"
               "SavedMasterMatchesShow=later" %
               (MARK, run, args["cue_label"], plan["playback_before"][1], restored_keys,
                sorted(saved), backup, archived))
    return report


def main():
    args = _load_json(os.path.join(_here(), MODE_NAME))
    mode = str(args.get("mode") or "").upper()
    run = str(args.get("run_id") or ("SHRINK-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    problems = validate_args(args)
    if problems:
        _stop(run, "ARGS|%r" % problems)
    functions = {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}
    return functions[mode](run, args)


if unreal is not None:
    main()
