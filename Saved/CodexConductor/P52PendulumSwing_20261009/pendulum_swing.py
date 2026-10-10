"""P52 guarded Unreal tool: DRY/APPLY/REVERT/REBUILD/CHECK pendulum keys.

The simulation is imported from :mod:`pendulum_core`, which has no Unreal dependency.
This file is loaded by ``pendulum_swing_run.py`` through ExecuteProjectPythonFile.
It never opens Sequencer or PIE.  APPLY owns exactly one named transform track;
REBUILD refuses if those owned keys drifted after APPLY.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import shutil


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p52_pendulum_core", os.path.join(HERE, "pendulum_core.py"))
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)

MARK = "P52_PENDULUM"
MODES = ("DRY", "APPLY", "REVERT", "REBUILD", "CHECK")
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OWNED_TRACK = "P52 Pendulum Swing [OWNED]"
ACTIVE_RECORD = os.path.join(HERE, "pendulum_swing_ACTIVE.json")
SPEED_CHANNEL = "Camera.SpeedMultiplier"


def require(condition, message):
    if not condition:
        raise C.PendulumError(message)


def _u():
    import unreal
    return unreal


def _guid(value):
    return _u().GuidLibrary.conv_guid_to_string(value)


def _path(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


def _project():
    return _u().Paths.convert_relative_path_to_full(_u().Paths.project_dir())


def _census():
    u = _u()
    return {
        "content": sorted(p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_file(package):
    base = os.path.join(_project(), "Content", *package[len("/Game/"):].split("/"))
    for suffix in (".uasset", ".umap"):
        if os.path.isfile(base + suffix):
            return base + suffix
    raise C.PendulumError("PACKAGE_FILE_MISSING|" + package)


def _backup(run, purpose):
    root = os.path.join(_project(), "Backups", "PrePendulumSwing-%s" % run)
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in (MASTER_PATH, EXPECTED_WORLD):
        source = _package_file(package)
        target = os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(source)[1])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)
        require(_sha(source) == _sha(target), "BACKUP_HASH|" + package)
        rows.append({"package": package, "source": source, "backup": target, "sha256": _sha(target)})
    manifest = {"run": run, "purpose": purpose, "packages": rows}
    _write(os.path.join(root, "manifest.json"), manifest, exclusive=True)
    return {"root": root, "packages": rows}


def check_args(raw):
    raw = dict(raw or {})
    mode = str(raw.get("mode", "DRY")).upper()
    require(mode in MODES, "MODE_INVALID|" + mode)
    if mode not in ("DRY", "CHECK"):
        require(raw.get("confirm") == "%s %s" % (mode, MARK),
                "CONFIRM_MISMATCH|want='%s %s'" % (mode, MARK))
    config = C.check_config(raw)
    return dict(config, mode=mode, confirm=raw.get("confirm"),
                passage_label=str(raw.get("passage_label", "Passage 1")),
                target_actor_label=str(raw.get("target_actor_label", "Swinging Candle Chandelier")),
                allow_dirty=sorted(str(x) for x in (raw.get("allow_dirty") or [])))


def _context(args):
    u = _u()
    project = os.path.normcase(os.path.normpath(_project())).rstrip("\\/")
    require(os.path.basename(project).lower() == "pussstage", "WRONG_PROJECT|" + project)
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_ACTIVE")
    world = editor.get_editor_world()
    require(world is not None and _path(world) == EXPECTED_WORLD, "WRONG_WORLD|%r" % _path(world))
    census = _census()
    dirty = set(census["content"] + census["maps"])
    require(dirty <= set(args["allow_dirty"]), "DIRTY_BEFORE|" + json.dumps(census, sort_keys=True))
    require(u.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is None, "SEQUENCER_OPEN")
    return world, census


def _unwrap(result, count):
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    return result if isinstance(result, tuple) and len(result) == count else None


def _channel(section, name):
    hits = [channel for channel in section.get_all_channels()
            if str(channel.get_editor_property("channel_name")) == name
            or str(channel.get_editor_property("channel_name")).startswith(name + "_")]
    require(len(hits) == 1, "CHANNEL_COUNT|%s|%d" % (name, len(hits)))
    return hits[0]


def _channel_rows(channel):
    u = _u()
    rows = []
    for key in channel.get_keys():
        time = key.get_time(time_unit=u.MovieSceneTimeUnit.TICK_RESOLUTION)
        rows.append([int(time.frame_number.value), float(key.get_value())])
    return {"default": float(channel.get_default()) if channel.has_default() else None, "keys": sorted(rows)}


def _load(args, world):
    u = _u()
    show, master = u.load_asset(SHOW_PATH), u.load_asset(MASTER_PATH)
    require(show is not None and master is not None, "ASSET_LOAD")
    passages = [row for row in show.get_editor_property("passage_settings")
                if str(row.get_editor_property("label")) == args["passage_label"]]
    require(len(passages) == 1, "PASSAGE_COUNT|%d" % len(passages))
    guid = passages[0].get_editor_property("passage_guid")
    sections = []
    for track in master.get_tracks():
        if track.get_class().get_name() == "MovieSceneInfinityPassageTrack":
            sections += [section for section in track.get_sections()
                         if _guid(section.get_editor_property("passage_guid")) == _guid(guid)]
    require(len(sections) == 1, "PASSAGE_SECTION_COUNT|%d" % len(sections))
    actors = [actor for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
              if str(actor.get_actor_label()) == args["target_actor_label"]]
    require(len(actors) == 1, "TARGET_ACTOR_COUNT|%d" % len(actors))
    frame_range = _unwrap(u.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, guid), 2)
    require(frame_range is not None, "PASSAGE_FRAME_RANGE")
    tick = master.get_tick_resolution()
    tick_rate = tick.numerator / float(tick.denominator)
    return {"show": show, "master": master, "section": sections[0], "guid": guid, "actor": actors[0],
            "world": world, "tick_rate": tick_rate, "range": [int(frame_range[0]), int(frame_range[1])]}


def _input_facts(ctx):
    speed = _channel_rows(_channel(ctx["section"], SPEED_CHANNEL))
    facts = {"passage_guid": _guid(ctx["guid"]), "section_range": ctx["range"],
             "tick_rate": ctx["tick_rate"], "speed_multiplier": speed}
    return facts, C.canonical_fingerprint(facts)


def _pose(ctx, tick):
    result = _unwrap(_u().InfinityStageCameraPilotLibrary.get_passage_camera_pose(
        ctx["show"], ctx["guid"], int(tick)), 3)
    require(result is not None, "POSE_READ|%d" % tick)
    location = result[0].translation
    return [float(location.x), float(location.y), float(location.z)]


def _plan(args, ctx):
    start, end = ctx["range"]
    step_ticks = max(1, int(round(ctx["tick_rate"] / args["fixed_step_hz"])))
    ticks = list(range(start, end + 1, step_ticks))
    if ticks[-1] != end:
        # Fixed step integration needs a uniform grid; the final partial interval is deliberately excluded.
        end = ticks[-1]
    positions = []
    for tick in ticks:
        xyz = _pose(ctx, tick)
        positions.append([(tick - start) / ctx["tick_rate"], xyz[0], xyz[1]])
    simulation = C.simulate(positions, args)
    keys = [[start + int(round(row[0] * ctx["tick_rate"])), row[1], row[2]] for row in simulation["keys"]]
    cue_rows = _cue_times(ctx, start)
    for peak in simulation["peak_times_seconds"]:
        absolute = start + int(round(peak["time_seconds"] * ctx["tick_rate"]))
        nearest = min(cue_rows, key=lambda row: abs(row["tick"] - absolute)) if cue_rows else None
        peak["master_tick"] = absolute
        peak["nearest_cue"] = nearest
    return {"start_tick": start, "end_tick": end, "step_ticks": step_ticks, "sample_count": len(positions),
            "keys": keys, "simulation": {key: value for key, value in simulation.items() if key != "dense"},
            "max_reconstruction_error_degrees": C.max_reconstruction_error(simulation["dense"], simulation["keys"]),
            "cue_times": cue_rows}


def _cue_times(ctx, start):
    """Wing cue pass times from Show order + Passage lead-in; all values are absolute Master ticks."""
    show = ctx["show"]
    settings = [row for row in show.get_editor_property("passage_settings")
                if _guid(row.get_editor_property("passage_guid")) == _guid(ctx["guid"])]
    if len(settings) != 1:
        return []
    first = _guid(settings[0].get_editor_property("first_cue_guid"))
    last = _guid(settings[0].get_editor_property("last_cue_guid"))
    cues = list(show.get_editor_property("cues"))
    indexes = { _guid(cue.get_editor_property("cue_guid")): index for index, cue in enumerate(cues) }
    if first not in indexes or last not in indexes or indexes[first] > indexes[last]:
        return []
    tick = start + int(settings[0].get_editor_property("lead_in_frames").value)
    rows = []
    for cue in cues[indexes[first]:indexes[last] + 1]:
        guid = _guid(cue.get_editor_property("cue_guid"))
        rows.append({"cue_id": guid, "tick": tick})
        wing = cue.get_editor_property("wing_pair")
        tick += int(wing.get_editor_property("interval_to_next").value)
    return rows


def _bindings(ctx):
    # Actor object paths must retain the PersistentLevel object suffix.  Using
    # _path() here collapsed every level actor to the map package and made all
    # unrelated bindings appear to target the chandelier.
    target = str(ctx["actor"].get_path_name())
    found = []
    for binding in ctx["master"].get_bindings():
        try:
            if any(str(obj.get_path_name()) == target
                   for obj in ctx["master"].locate_bound_objects(binding.get_id(), ctx["world"])):
                found.append(binding)
        except Exception:
            pass
    return found


def _owned(binding):
    return [track for track in binding.get_tracks()
            if track.get_class().get_name() == "MovieScene3DTransformTrack"
            and str(track.get_display_name()) == OWNED_TRACK]


def _track_snapshot(binding):
    tracks = _owned(binding)
    if not tracks:
        return None
    require(len(tracks) == 1, "OWNED_TRACK_COUNT|%d" % len(tracks))
    sections = list(tracks[0].get_sections())
    require(len(sections) == 1, "OWNED_SECTION_COUNT|%d" % len(sections))
    channels = list(sections[0].get_all_channels())
    require(len(channels) >= 9, "TRANSFORM_CHANNEL_COUNT|%d" % len(channels))
    pitch = _channel_rows(channels[4])["keys"]
    yaw = _channel_rows(channels[5])["keys"]
    require([row[0] for row in pitch] == [row[0] for row in yaw], "OWNED_TIME_MISMATCH")
    return [[p[0], p[1], y[1]] for p, y in zip(pitch, yaw)]


def _base_transform(actor):
    # StaticMeshActor does not expose get_root_component() in UE 5.8's
    # generated Python API; the reflected root_component property is stable.
    root = actor.get_editor_property("root_component")
    require(root is not None, "TARGET_ROOT_MISSING")
    # Actor transform tracks drive the root's relative transform. World values
    # would double an attached chandelier's support transform.
    loc = root.get_editor_property("relative_location")
    rot = root.get_editor_property("relative_rotation")
    scale = root.get_editor_property("relative_scale3d")
    return {"location": [float(loc.x), float(loc.y), float(loc.z)],
            "rotation": [float(rot.roll), float(rot.pitch), float(rot.yaw)],
            "scale": [float(scale.x), float(scale.y), float(scale.z)]}


def _write_track(ctx, plan, before):
    u = _u()
    bindings = _bindings(ctx)
    require(len(bindings) <= 1, "TARGET_BINDING_COUNT|%d" % len(bindings))
    created = not bindings
    binding = bindings[0] if bindings else ctx["master"].add_possessable(ctx["actor"])
    if created:
        binding.set_display_name(ctx["actor"].get_actor_label())
    require(not _owned(binding), "OWNED_TRACK_EXISTS")
    other_transforms = [track for track in binding.get_tracks()
                        if track.get_class().get_name() == "MovieScene3DTransformTrack"]
    require(not other_transforms, "NON_OWNED_TRANSFORM_TRACK|%d" % len(other_transforms))
    track = binding.add_track(u.MovieScene3DTransformTrack)
    track.set_display_name(OWNED_TRACK)
    section = track.add_section()
    section.set_range(ctx["master"].get_playback_start(), ctx["master"].get_playback_end())
    channels = list(section.get_all_channels())
    require(len(channels) >= 9, "TRANSFORM_CHANNEL_COUNT|%d" % len(channels))
    defaults = before["location"] + before["rotation"] + before["scale"]
    for channel, value in zip(channels[:9], defaults):
        channel.set_default(float(value))
    applied = []
    for tick, pitch_delta, yaw_delta in plan["keys"]:
        pitch = before["rotation"][1] + pitch_delta
        yaw = before["rotation"][2] + yaw_delta
        channels[4].add_key(u.FrameNumber(int(tick)), pitch, 0.0, u.MovieSceneTimeUnit.TICK_RESOLUTION,
                            u.MovieSceneKeyInterpolation.LINEAR)
        channels[5].add_key(u.FrameNumber(int(tick)), yaw, 0.0, u.MovieSceneTimeUnit.TICK_RESOLUTION,
                            u.MovieSceneKeyInterpolation.LINEAR)
        applied.append([int(tick), pitch, yaw])
    require(C.drift_matches(applied, _track_snapshot(binding)), "WRITE_READBACK")
    return binding, created, applied


def _remove_owned(ctx, record):
    bindings = _bindings(ctx)
    require(len(bindings) == 1, "REVERT_BINDING_COUNT|%d" % len(bindings))
    binding = bindings[0]
    live = _track_snapshot(binding)
    require(live is not None and C.drift_matches(record["applied_keys"], live), "OWNED_KEYS_DRIFT")
    track = _owned(binding)[0]
    binding.remove_track(track)
    if record["binding_created"]:
        require(not list(binding.get_tracks()), "CREATED_BINDING_NOT_EMPTY")
        binding.remove()
    return live


def _save_narrow():
    u = _u()
    census = _census()
    require(set(census["content"]) <= {MASTER_PATH} and set(census["maps"]) <= {EXPECTED_WORLD},
            "DIRTY_SCOPE|" + json.dumps(census, sort_keys=True))
    if MASTER_PATH in census["content"]:
        require(u.EditorAssetLibrary.save_asset(MASTER_PATH, only_if_is_dirty=False), "MASTER_SAVE")
    if EXPECTED_WORLD in census["maps"]:
        require(u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE")
    require(_census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|" + json.dumps(_census()))


def _report_path(mode, run):
    return os.path.join(HERE, "pendulum_%s_%s.json" % (mode.lower(), run))


def run(raw):
    run_id = datetime.datetime.now().strftime("P52-%Y%m%d-%H%M%S")
    try:
        args = check_args(raw)
        world, before_census = _context(args)
        ctx = _load(args, world)
        facts, fingerprint = _input_facts(ctx)
        mode = args["mode"]
        if mode == "CHECK":
            require(os.path.isfile(ACTIVE_RECORD), "NO_ACTIVE_RECORD")
            record = json.load(open(ACTIVE_RECORD, encoding="utf-8"))
            stale = record["input_fingerprint"] != fingerprint
            report = {"run": run_id, "mode": mode, "stale": stale, "recorded": record["input_fingerprint"],
                      "current": fingerprint, "input": facts, "census": before_census}
            path = _report_path(mode, run_id)
            _write(path, report)
            _u().log("%s_CHECK_OK|run=%s|stale=%d|recorded=%s|current=%s|report=%s" %
                     (MARK, run_id, int(stale), record["input_fingerprint"], fingerprint, path))
            return
        if mode == "DRY":
            plan = _plan(args, ctx)
            require(_census() == before_census, "DRY_CENSUS_CHANGED")
            report = {"run": run_id, "mode": mode, "args": args, "input": facts,
                      "input_fingerprint": fingerprint, "plan": plan, "apply_ready": not os.path.exists(ACTIVE_RECORD),
                      "active_record_exists": os.path.exists(ACTIVE_RECORD), "census": before_census}
            path = _report_path(mode, run_id)
            _write(path, report)
            _u().log("%s_DRY_OK|run=%s|samples=%d|keys=%d|max_pitch=%.3f|max_yaw=%.3f|error=%.4f|fingerprint=%s|report=%s" %
                     (MARK, run_id, plan["sample_count"], len(plan["keys"]),
                      plan["simulation"]["max_abs_pitch_degrees"], plan["simulation"]["max_abs_yaw_degrees"],
                      plan["max_reconstruction_error_degrees"], fingerprint, path))
            return
        if mode == "APPLY":
            require(not os.path.exists(ACTIVE_RECORD), "ACTIVE_RECORD_EXISTS|revert or rebuild")
            plan = _plan(args, ctx)
            backup = _backup(run_id, "APPLY owned pendulum transform track")
            before = _base_transform(ctx["actor"])
            record = {"version": 1, "status": "WRITING", "apply_run": run_id, "args": args,
                      "target_actor_path": _path(ctx["actor"]), "input": facts, "input_fingerprint": fingerprint,
                      "plan": plan, "before_transform": before, "backup": backup}
            _write(ACTIVE_RECORD, record, exclusive=True)
            binding, created, applied = _write_track(ctx, plan, before)
            _save_narrow()
            record.update(status="APPLIED", binding_created=created, binding_guid=_guid(binding.get_id()),
                          applied_keys=applied)
            _write(ACTIVE_RECORD, record)
            _u().log("%s_APPLY_OK|run=%s|keys=%d|fingerprint=%s|backup=%s|record=%s|census=clean" %
                     (MARK, run_id, len(applied), fingerprint, backup["root"], ACTIVE_RECORD))
            return
        require(os.path.isfile(ACTIVE_RECORD), "NO_ACTIVE_RECORD")
        record = json.load(open(ACTIVE_RECORD, encoding="utf-8"))
        require(record.get("status") == "APPLIED", "RECORD_STATUS|%r" % record.get("status"))
        require(_path(ctx["actor"]) == record["target_actor_path"], "TARGET_CHANGED")
        backup = _backup(run_id, mode + " owned pendulum transform track")
        _remove_owned(ctx, record)
        if mode == "REVERT":
            _save_narrow()
            archive = ACTIVE_RECORD.replace(".json", ".reverted-%s.json" % run_id)
            record.update(status="REVERTED", revert_run=run_id, revert_backup=backup)
            os.replace(ACTIVE_RECORD, archive)
            _write(archive, record)
            _u().log("%s_REVERT_OK|run=%s|apply=%s|backup=%s|record=%s|census=clean" %
                     (MARK, run_id, record["apply_run"], backup["root"], archive))
            return
        # REBUILD is an exact owned-track revert followed by a fresh sample/sim/apply.
        plan = _plan(args, ctx)
        before = record["before_transform"]
        binding, created, applied = _write_track(ctx, plan, before)
        _save_narrow()
        history = list(record.get("rebuild_history", []))
        history.append({"run": run_id, "from_fingerprint": record["input_fingerprint"],
                        "to_fingerprint": fingerprint, "backup": backup})
        record.update(args=args, input=facts, input_fingerprint=fingerprint, plan=plan,
                      binding_created=created, binding_guid=_guid(binding.get_id()), applied_keys=applied,
                      rebuild_history=history, last_rebuild_run=run_id)
        _write(ACTIVE_RECORD, record)
        _u().log("%s_REBUILD_OK|run=%s|keys=%d|fingerprint=%s|backup=%s|record=%s|census=clean" %
                 (MARK, run_id, len(applied), fingerprint, backup["root"], ACTIVE_RECORD))
    except Exception as error:
        _u().log_error("%s_STOPPED|run=%s|%s" % (MARK, run_id, error))
        raise


if __name__ == "__p52_pendulum_runner__":
    run(globals().get("P52_PENDULUM_ARGS") or {})
