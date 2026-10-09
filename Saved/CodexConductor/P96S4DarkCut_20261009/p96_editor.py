"""Guarded DRY/APPLY/REVERT editor tool for Codex job 96.

The conductor runs this later through ExecuteProjectPythonFile.  It never starts
Unreal/PIE, never saves a Klara level, never saves the show map, and never calls
Save All.  Its sole package write is LS_DevScene_04.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import sys

try:
    import unreal
except ModuleNotFoundError:  # Offline import for static tests.
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p96_core as core


ARGS = os.path.join(HERE, "p96_args.json")
RECORD = os.path.join(HERE, "p96_record.json")
MARK = "P96_S4_DARK_CUT"
APPLY_CONFIRM = "APPLY P96 S4 DARK CUT"
REVERT_CONFIRM = "REVERT P96 S4 DARK CUT"
HANGAR_TAG = "RigAtmos.Scene4Hangar"
KLARA_LEVEL = "/Game/L_KK_children"
ENV_CLASSES = {"DirectionalLight", "SkyLight", "SkyAtmosphere",
               "ExponentialHeightFog", "VolumetricCloud"}


def _json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, value, exclusive=False):
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, ensure_ascii=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _path(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def _guid(value):
    """FGuid wrappers stringify to changing addresses in UE 5.8."""
    try:
        return str(unreal.GuidLibrary.conv_guid_to_string(value))
    except Exception:
        return str(value.export_text())


def _enum(value):
    return core.enum_name(value)


def _sha(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def _asset_file(asset):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *asset[len("/Game/"):].split("/")) + ".uasset"


def _package(obj):
    return str(obj.get_outermost().get_name())


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
        "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages()),
    }


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _context(run, mutating=False):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or _package(world) != core.WORLD:
        _stop(run, "WRONG_WORLD|got=%s" % (_package(world) if world else None))
    if mutating:
        current = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        if current is not None:
            _stop(run, "SEQUENCER_OPEN|%s" % _path(current))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|%s" % core.canonical(_census()))
    return world


def _section_range(section):
    return [int(section.get_start_frame()) if section.has_start_frame() else None,
            int(section.get_end_frame()) if section.has_end_frame() else None]


def _binding_map(sequence):
    return {_guid(binding.get_id()): binding for binding in sequence.get_bindings()}


def _one_cut_track(sequence, run):
    rows = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(rows) != 1:
        _stop(run, "CAMERA_CUT_TRACK_COUNT|asset=%s|got=%d" % (_path(sequence), len(rows)))
    return rows[0]


def _camera_rows(sequence, track):
    names = {key: str(value.get_display_name()) for key, value in _binding_map(sequence).items()}
    rows = []
    for index, section in enumerate(track.get_sections()):
        bid = section.get_camera_binding_id().get_editor_property("guid")
        identity = _guid(bid)
        rows.append({"section_index": index, "range": _section_range(section),
                     "active": bool(section.is_active()), "binding_guid": identity,
                     "camera": names.get(identity)})
    return rows


def _nested_slots(sequence):
    rows = []
    for track_index, track in enumerate(sequence.get_tracks()):
        if track.get_class().get_name() not in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
            continue
        for section_index, section in enumerate(track.get_sections()):
            child = section.get_sequence()
            rows.append({"track_index": track_index, "section_index": section_index,
                         "track_class": track.get_class().get_name(), "range": _section_range(section),
                         "active": bool(section.is_active()), "sequence": _path(child) if child else None})
    return rows


def _resolved(binding, sequence, world):
    objects = list(sequence.locate_bound_objects(binding, world))
    return {"resolved_count": len(objects),
            "resolved": [{"path": item.get_path_name(), "level": _package(item),
                          "class": item.get_class().get_name()} for item in objects]}


def _cut_resolutions(scene, copy, world, args):
    root_track = _one_cut_track(scene, args["run_id"])
    root_rows = _camera_rows(scene, root_track)
    root_bindings = _binding_map(scene)
    out = []
    for role, label in (("root_entry", core.ENTRY), ("root_exit", core.EXIT)):
        rows = [row for row in root_rows if row["camera"] == label]
        if len(rows) != 1:
            out.append({"role": role, "resolved_count": 0, "error": "cut_count=%d" % len(rows)})
            continue
        row = dict(rows[0], role=role)
        row.update(_resolved(root_bindings.get(row["binding_guid"]), scene, world)
                   if root_bindings.get(row["binding_guid"]) else {"resolved_count": 0, "resolved": []})
        out.append(row)
    child_frame = int(args["expected_klara_frame_at_cut"])
    copy_track = _one_cut_track(copy, args["run_id"])
    candidates = [row for row in _camera_rows(copy, copy_track)
                  if row["active"] and row["range"][0] <= child_frame < row["range"][1]]
    if len(candidates) != 1:
        out.append({"role": "klara_at_cut", "resolved_count": 0,
                    "error": "active_cut_count=%d child_frame=%d" % (len(candidates), child_frame)})
    else:
        row = dict(candidates[0], role="klara_at_cut", child_frame=child_frame)
        binding = _binding_map(copy).get(row["binding_guid"])
        row.update(_resolved(binding, copy, world) if binding else {"resolved_count": 0, "resolved": []})
        out.append(row)
    return out


def _channel_row(channel):
    keys = []
    for key in channel.get_keys():
        when = key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE)
        keys.append([int(when.frame_number.value), bool(key.get_value())])
    return {"name": str(channel.channel_name), "base_name": core.channel_base(channel.channel_name),
            "has_default": bool(channel.has_default()),
            "default": bool(channel.get_default()) if channel.has_default() else None,
            "keys": keys}


def _visibility_rows(binding):
    rows = []
    if binding is None:
        return rows
    for index, track in enumerate(binding.get_tracks()):
        if track.get_class().get_name() != "MovieSceneVisibilityTrack":
            continue
        sections = []
        for section_index, section in enumerate(track.get_sections()):
            channels = list(section.get_all_channels())
            sections.append({"section_index": section_index, "range": _section_range(section),
                             "completion": _enum(section.get_completion_mode()),
                             "channels": [_channel_row(channel) for channel in channels],
                             "default": (bool(channels[0].get_default())
                                         if len(channels) == 1 and channels[0].has_default() else None),
                             "keys": (_channel_row(channels[0])["keys"] if len(channels) == 1 else None)})
        rows.append({"track_index": index, "class": "MovieSceneVisibilityTrack",
                     "name": str(track.get_display_name()),
                     "property": str(track.get_property_name()),
                     "property_path": str(track.get_property_path()), "sections": sections})
    return rows


def _actor_bindings(sequence, actor, world):
    path = actor.get_path_name()
    rows = []
    for binding in sequence.get_bindings():
        resolved = list(sequence.locate_bound_objects(binding, world))
        if any(obj.get_path_name() == path for obj in resolved):
            rows.append(binding)
    return rows


def _target(sequence, actor, world, group, rng):
    bindings = _actor_bindings(sequence, actor, world)
    if len(bindings) > 1:
        raise core.PlanError("ACTOR_BINDING_AMBIGUOUS|%s|%d" % (actor.get_path_name(), len(bindings)))
    binding = bindings[0] if bindings else None
    return {"group": group, "path": actor.get_path_name(), "label": str(actor.get_actor_label()),
            "class": actor.get_class().get_name(), "level": _package(actor), "range": list(rng),
            "binding_guid": _guid(binding.get_id()) if binding else None,
            "visibility_tracks": _visibility_rows(binding)}


def _has_light(actor):
    return bool(list(actor.get_components_by_class(unreal.LightComponent)))


def _targets(scene, world, args):
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    passages = [actor for actor in actors if actor.get_class().get_name() == "InfinityStagePassageActor"
                and str(actor.get_actor_label()).startswith("Passage 04")]
    if len(passages) != 1:
        raise core.PlanError("P04_PASSAGE_COUNT|%d" % len(passages))
    passage = passages[0]
    p04 = [actor for actor in actors if actor.get_attach_parent_actor() == passage and _has_light(actor)]
    hangar = []
    for actor in actors:
        tags = {str(value) for value in actor.tags}
        label = str(actor.get_actor_label())
        if HANGAR_TAG in tags and (_has_light(actor) or "Bulb" in label or "Glow" in label) \
                and "Stand" not in label:
            hangar.append(actor)
    klara = [actor for actor in actors if _package(actor) == KLARA_LEVEL
             and (_has_light(actor) or actor.get_class().get_name() in ENV_CLASSES)]
    curtain = [actor for actor in actors if str(actor.get_actor_label()) == core.CURTAIN]
    return {
        "p04_lights": [_target(scene, actor, world, "p04_lights", [0, core.EXPECTED_END])
                       for actor in sorted(p04, key=lambda item: item.get_path_name())],
        "hangar_lights_and_emissives": [
            _target(scene, actor, world, "hangar_lights_and_emissives", [0, core.EXPECTED_END])
            for actor in sorted(hangar, key=lambda item: item.get_path_name())],
        "klara_precut": [_target(scene, actor, world, "klara_precut", [0, core.EXPECTED_CUT])
                         for actor in sorted(klara, key=lambda item: item.get_path_name())],
        "curtain": [_target(scene, actor, world, "curtain", [core.EXPECTED_CUT, core.EXPECTED_END])
                    for actor in sorted(curtain, key=lambda item: item.get_path_name())],
    }


def gather(world, args):
    scene = unreal.load_asset(core.SCENE)
    copy = unreal.load_asset(core.COPY)
    if scene is None or copy is None:
        raise core.PlanError("ASSET_LOAD|scene=%s|copy=%s" % (scene is not None, copy is not None))
    state = {
        "world": _package(world), "scene": _path(scene), "scene_end": int(scene.get_playback_end()),
        "root_cuts": _camera_rows(scene, _one_cut_track(scene, args["run_id"])),
        "nested_slots": _nested_slots(scene), "cut_resolutions": _cut_resolutions(scene, copy, world, args),
        "target_groups": _targets(scene, world, args),
    }
    return state, scene


def _backup(run, dry_path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    root = os.path.join(project, "Backups", "PreP96S4DarkCut-" + run)
    if os.path.exists(root):
        _stop(run, "BACKUP_EXISTS|" + root)
    source = _asset_file(core.SCENE)
    destination = os.path.join(root, "Content", "InfinityStage", "Dev", "Sequences",
                               "LS_DevScene_04.uasset")
    os.makedirs(os.path.dirname(destination), exist_ok=False)
    shutil.copy2(source, destination)
    shutil.copy2(dry_path, root)
    if _sha(source) != _sha(destination):
        _stop(run, "BACKUP_HASH_MISMATCH")
    return {"root": root, "source": source, "copy": destination,
            "sha256": _sha(source), "bytes": os.path.getsize(source)}


def _binding_by_guid(sequence, guid):
    return _binding_map(sequence).get(guid)


def _actor_by_path(world, path):
    rows = [actor for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if actor.get_path_name() == path]
    if len(rows) != 1:
        raise RuntimeError("ACTOR_PATH_COUNT|%s|%d" % (path, len(rows)))
    return rows[0]


def _add_hidden(scene, world, row):
    actor = _actor_by_path(world, row["path"])
    binding = _binding_by_guid(scene, row.get("binding_guid")) if row.get("binding_guid") else None
    created_binding = False
    if binding is None:
        binding = scene.add_possessable(actor)
        created_binding = True
        binding.set_display_name("P96 S4 Dark: " + row["label"])
    resolved = list(scene.locate_bound_objects(binding, world))
    if [item.get_path_name() for item in resolved] != [row["path"]]:
        raise RuntimeError("BINDING_RESOLUTION|%s|%s" %
                           (row["path"], [item.get_path_name() for item in resolved]))
    before = len(binding.get_tracks())
    track = binding.add_track(unreal.MovieSceneVisibilityTrack)
    track.set_property_name_and_path("bHidden", "bHidden")
    if str(track.get_property_name()) != "bHidden" or str(track.get_property_path()) != "bHidden":
        raise RuntimeError("VISIBILITY_PROPERTY|%s|%s" %
                           (track.get_property_name(), track.get_property_path()))
    section = track.add_section()
    section.set_range(int(row["range"][0]), int(row["range"][1]))
    section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    channels = list(section.get_all_channels())
    if len(channels) != 1:
        raise RuntimeError("VISIBILITY_CHANNEL_COUNT|%s|%d" % (row["path"], len(channels)))
    channels[0].set_default(False)  # Visibility channel semantics: False = hidden.
    read = _visibility_rows(binding)[-1]
    section_read = read["sections"][0]
    if (read["property"] != "bHidden" or section_read["range"] != row["range"]
            or section_read["default"] is not False or section_read["keys"]
            or section_read["completion"] != "RESTORE_STATE"):
        raise RuntimeError("VISIBILITY_READBACK|%s|%s" % (row["path"], core.canonical(read)))
    return {"path": row["path"], "label": row["label"], "group": row["group"],
            "binding_guid": _guid(binding.get_id()), "created_binding": created_binding,
            "track_index": before, "range": list(row["range"]), "property": "bHidden",
            "channel_base": section_read["channels"][0]["base_name"], "default": False,
            "completion": "RESTORE_STATE"}


def _created_track(sequence, item):
    binding = _binding_by_guid(sequence, item["binding_guid"])
    if binding is None:
        return None, None
    matches = []
    for track in binding.get_tracks():
        if track.get_class().get_name() != "MovieSceneVisibilityTrack" \
                or str(track.get_property_name()) != "bHidden":
            continue
        sections = list(track.get_sections())
        if len(sections) != 1:
            continue
        channels = list(sections[0].get_all_channels())
        if (len(channels) == 1 and _section_range(sections[0]) == item["range"]
                and channels[0].has_default() and bool(channels[0].get_default()) is False
                and not channels[0].get_keys()
                and _enum(sections[0].get_completion_mode()) == "RESTORE_STATE"):
            matches.append(track)
    if len(matches) != 1:
        return binding, None
    return binding, matches[0]


def _camera_sections(scene, plan):
    sections = list(_one_cut_track(scene, "readback").get_sections())
    return sections[plan["camera"]["entry_section_index"]], sections[plan["camera"]["glide_section_index"]]


def _verify_applied(scene, record):
    entry, glide = _camera_sections(scene, record["plan"])
    errors = []
    if _section_range(entry) != record["plan"]["camera"]["entry_after_range"]:
        errors.append("ENTRY_RANGE")
    if bool(glide.is_active()):
        errors.append("GLIDE_ACTIVE")
    for item in record["created_tracks"]:
        _binding, track = _created_track(scene, item)
        if track is None:
            errors.append("TRACK|" + item["path"])
    return errors


def _save_scene(run):
    wanted = {"content": [core.SCENE], "maps": []}
    if _census() != wanted:
        _stop(run, "DIRTY_AFTER_MUTATION|got=%s|want=%s|NOTHING_SAVED_DONT_SAVE_RESTART" %
              (core.canonical(_census()), core.canonical(wanted)))
    if not unreal.EditorAssetLibrary.save_asset(core.SCENE, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|" + core.SCENE)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % core.canonical(_census()))


def dry(run, args, world):
    state, _scene = gather(world, args)
    report = {"schema": "p96_s4_dark_cut_dry/1", "run": run,
              "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "state": state, "state_digest": core.digest(state), "census": _census()}
    try:
        report["plan"] = core.plan_change(state)
        report["apply_ready"] = True
        report["refusals"] = []
    except core.PlanError as exc:
        report["apply_ready"] = False
        report["refusals"] = [str(exc)]
    path = os.path.join(HERE, "p96_dry_%s.json" % run)
    _write(path, report)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED_PACKAGES|%s" % core.canonical(_census()))
    marker = MARK + ("_DRY_OK" if report["apply_ready"] else "_DRY_REFUSED")
    counts = report.get("plan", {}).get("counts", {})
    unreal.log("%s|run=%s|apply_ready=%d|counts=%s|to_add=%s|already_dark=%s|report=%s" %
               (marker, run, int(report["apply_ready"]), core.canonical(counts),
                report.get("plan", {}).get("to_add"), report.get("plan", {}).get("already_dark"), path))


def apply(run, args, world):
    if args.get("confirm") != APPLY_CONFIRM or not str(args.get("decided_by") or "").strip():
        _stop(run, "CONFIRM_OR_DECIDED_BY|want=" + APPLY_CONFIRM)
    dry_run = str(args.get("dry_run") or "")
    dry_path = os.path.join(HERE, "p96_dry_%s.json" % dry_run)
    if not dry_run or not os.path.isfile(dry_path):
        _stop(run, "DRY_REPORT_MISSING|" + dry_run)
    report = _json(dry_path)
    if not report.get("apply_ready") or report.get("state", {}).get("scene") != core.SCENE:
        _stop(run, "DRY_NOT_APPLY_READY")
    if os.path.exists(RECORD):
        _stop(run, "RECORD_EXISTS|REVERT_FIRST")
    state, scene = gather(world, args)
    if core.digest(state) != report.get("state_digest"):
        _stop(run, "DRY_STATE_DRIFT|dry_run=" + dry_run)
    plan = core.plan_change(state)
    backup = _backup(run, dry_path)
    record = {"schema": "p96_s4_dark_cut_record/1", "status": "prepared", "run": run,
              "dry_run": dry_run, "decided_by": args["decided_by"], "world": core.WORLD,
              "scene": core.SCENE, "backup": backup, "before_state": state,
              "before_digest": core.digest(state), "plan": plan, "created_tracks": [],
              "written": datetime.datetime.now().isoformat(timespec="seconds")}
    _write(RECORD, record, exclusive=True)
    scene.modify()
    entry, glide = _camera_sections(scene, plan)
    entry.set_range(*plan["camera"]["entry_after_range"])
    glide.set_is_active(False)
    for row in plan["visibility"]:
        if row["action"] == "add":
            record["created_tracks"].append(_add_hidden(scene, world, row))
    _write(RECORD, record)
    errors = _verify_applied(scene, record)
    if errors:
        _stop(run, "PRE_SAVE_READBACK|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % errors)
    _save_scene(run)
    scene2 = unreal.load_asset(core.SCENE)
    errors = _verify_applied(scene2, record)
    if errors or _census() != {"content": [], "maps": []}:
        _stop(run, "POST_SAVE_READBACK|errors=%s|census=%s" % (errors, core.canonical(_census())))
    record.update(status="applied", saved_sha256=_sha(_asset_file(core.SCENE)),
                  post_save_census=_census(), applied=datetime.datetime.now().isoformat(timespec="seconds"))
    _write(RECORD, record)
    unreal.log("%s_APPLY_OK|run=%s|dry_run=%s|cut=%d|counts=%s|tracks_added=%d|saved=%s|backup=%s|dirty=0" %
               (MARK, run, dry_run, plan["cut_frame"], core.canonical(plan["counts"]),
                len(record["created_tracks"]), core.SCENE, backup["root"]))


def revert(run, args, world):
    if args.get("confirm") != REVERT_CONFIRM:
        _stop(run, "CONFIRM|want=" + REVERT_CONFIRM)
    if not os.path.isfile(RECORD):
        _stop(run, "RECORD_MISSING")
    record = _json(RECORD)
    if record.get("status") != "applied" or record.get("world") != core.WORLD \
            or record.get("scene") != core.SCENE:
        _stop(run, "RECORD_CONTEXT_OR_STATUS")
    scene = unreal.load_asset(core.SCENE)
    errors = _verify_applied(scene, record)
    if errors:
        _stop(run, "APPLIED_STATE_DRIFT|%s" % errors)
    backup = _backup(run + "-REVERT", os.path.join(record["backup"]["root"],
                                                    "p96_dry_%s.json" % record["dry_run"]))
    for item in record["created_tracks"]:
        binding, track = _created_track(scene, item)
        if binding is None or track is None:
            _stop(run, "TRACK_DRIFT|" + item["path"])
        binding.remove_track(track)
        if item.get("created_binding"):
            if list(binding.get_tracks()) or list(binding.get_child_possessables()):
                _stop(run, "CREATED_BINDING_NOT_EMPTY|" + item["path"])
            binding.remove()
    entry, glide = _camera_sections(scene, record["plan"])
    entry.set_range(*record["plan"]["camera"]["entry_before"]["range"])
    glide.set_is_active(bool(record["plan"]["camera"]["glide_before"]["active"]))
    if (_section_range(entry) != record["plan"]["camera"]["entry_before"]["range"]
            or bool(glide.is_active()) != bool(record["plan"]["camera"]["glide_before"]["active"])):
        _stop(run, "CAMERA_RESTORE_READBACK|NOTHING_SAVED_DONT_SAVE_RESTART")
    for item in record["created_tracks"]:
        _binding, track = _created_track(scene, item)
        if track is not None:
            _stop(run, "TRACK_STILL_PRESENT|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % item["path"])
    _save_scene(run)
    scene2 = unreal.load_asset(core.SCENE)
    entry2, glide2 = _camera_sections(scene2, record["plan"])
    if (_section_range(entry2) != record["plan"]["camera"]["entry_before"]["range"]
            or bool(glide2.is_active()) != bool(record["plan"]["camera"]["glide_before"]["active"])):
        _stop(run, "POST_SAVE_CAMERA_REVERT_READBACK")
    record.update(status="reverted", revert_run=run, revert_backup=backup,
                  reverted=datetime.datetime.now().isoformat(timespec="seconds"))
    _write(RECORD, record)
    archived = RECORD + ".reverted-" + run
    os.rename(RECORD, archived)
    unreal.log("%s_REVERT_OK|run=%s|tracks_removed=%d|camera_restored=1|saved=%s|backup=%s|record=%s|dirty=0" %
               (MARK, run, len(record["created_tracks"]), core.SCENE, backup["root"], archived))


def main():
    args = _json(ARGS)
    run = str(args.get("run_id") or "")
    mode = str(args.get("mode") or "").upper()
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]{5,100}$", run):
        raise RuntimeError("INVALID_RUN_ID")
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise RuntimeError("INVALID_MODE|" + mode)
    world = _context(run, mutating=mode in ("APPLY", "REVERT"))
    if mode == "DRY":
        dry(run, args, world)
    elif mode == "APPLY":
        apply(run, args, world)
    else:
        revert(run, args, world)


if unreal is not None and not getattr(unreal, "_PUSS_FAKE", False):
    try:
        main()
    except Exception as exc:
        unreal.log_error("%s_FAILED|%s: %s" % (MARK, type(exc).__name__, exc))
        raise
