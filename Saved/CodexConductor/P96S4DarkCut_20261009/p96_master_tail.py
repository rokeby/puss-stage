"""Guarded DRY/APPLY/REVERT for the exact 67-actor P04-tail/S4-cut darkness bridge."""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import sys

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p96_master_tail_core as C

ARGS = os.path.join(HERE, "p96_master_tail_args.json")
SOURCE = os.path.join(HERE, "p96_record.json")
RECORD = os.path.join(HERE, "p96_master_tail_record.json")
MARK = "P96_MASTER_TAIL"
CONFIRMS = {"APPLY": "APPLY P96 MASTER TAIL", "REVERT": "REVERT P96 MASTER TAIL"}


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())


def _pkg(value):
    text = value.get_name() if hasattr(value, "get_name") else str(value)
    return text.split(".", 1)[0]


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted({_pkg(x) for x in lib.get_dirty_content_packages()}),
            "maps": sorted({_pkg(x) for x in lib.get_dirty_map_packages()})}


def _guid(binding):
    return str(unreal.GuidLibrary.conv_guid_to_string(binding.get_id())).replace("-", "").upper()


def _range(section, sequence):
    return [int(section.get_start_frame() if section.has_start_frame() else sequence.get_playback_start()),
            int(section.get_end_frame() if section.has_end_frame() else sequence.get_playback_end())]


def _prop(track):
    try:
        return str(track.get_property_name()), str(track.get_property_path())
    except Exception:
        return "", ""


def _rate(value):
    return float(value.numerator) / float(value.denominator)


def _context(run, mutating=False):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != C.WORLD:
        raise RuntimeError("%s_FAILED|run=%s|WORLD" % (MARK, run))
    if editor.get_game_world() is not None:
        raise RuntimeError("%s_FAILED|run=%s|PIE_OR_SIE" % (MARK, run))
    if _census() != {"content": [], "maps": []}:
        raise RuntimeError("%s_FAILED|run=%s|DIRTY_AT_START|%s" % (MARK, run, _census()))
    if mutating and os.path.isfile(RECORD):
        raise RuntimeError("%s_FAILED|run=%s|ACTIVE_RECORD" % (MARK, run))
    return world


def _actor_map(world):
    return {actor.get_path_name(): actor for actor in
            unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if actor.get_outermost().get_name() == C.WORLD}


def _binding_for(master, world, actor):
    wanted = actor.get_path_name(); hits = []
    for binding in master.get_bindings():
        try:
            resolved = [obj.get_path_name() for obj in master.locate_bound_objects(binding, world)]
        except Exception:
            resolved = []
        if wanted in resolved:
            hits.append(binding)
    if len(hits) > 1:
        raise RuntimeError("BINDING_AMBIGUOUS|%s|%d" % (wanted, len(hits)))
    return hits[0] if hits else None


def _preflight(master, world, plan):
    actors = _actor_map(world); missing = [row["path"] for row in plan["inventory"] if row["path"] not in actors]
    if missing:
        raise RuntimeError("INVENTORY_ACTORS_MISSING|%s" % missing)
    wanted = plan["window"]["hidden_range"]
    bindings = []
    for row in plan["inventory"]:
        binding = _binding_for(master, world, actors[row["path"]])
        if binding is not None:
            for track in binding.get_tracks():
                if track.get_class().get_name() != "MovieSceneVisibilityTrack" or _prop(track) != ("bHidden", "bHidden"):
                    continue
                for section in track.get_sections():
                    rng = _range(section, master)
                    if rng[0] < wanted[1] and rng[1] > wanted[0]:
                        raise RuntimeError("MASTER_VISIBILITY_OVERLAP|%s|%s" % (row["path"], rng))
        bindings.append({"path": row["path"], "existing_binding": binding is not None,
                         "binding_guid": None if binding is None else _guid(binding)})
    for index, track in enumerate(master.get_tracks()):
        if track.get_class().get_name() != "MovieSceneFadeTrack":
            continue
        for section in track.get_sections():
            rng = _range(section, master)
            if rng[0] < plan["window"]["fade_section_range"][1] and rng[1] > plan["window"]["fade_section_range"][0]:
                raise RuntimeError("MASTER_FADE_OVERLAP|track=%d|range=%s" % (index, rng))
    return actors, bindings


def _backup(run, plan):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    root = os.path.join(project, "Backups", "PreP96MasterTail-" + run)
    os.makedirs(root, exist_ok=False)
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    src = os.path.join(content, *C.MASTER[len("/Game/"):].split("/")) + ".uasset"
    dst = os.path.join(root, os.path.basename(src)); shutil.copy2(src, dst)
    _write(os.path.join(root, "prestate.json"), {"run": run, "plan": plan, "census": _census()}, True)
    if not os.path.isfile(dst) or os.path.getsize(src) != os.path.getsize(dst):
        raise RuntimeError("BACKUP_READBACK")
    return root


def _find_binding(master, guid):
    rows = [binding for binding in master.get_bindings() if _guid(binding) == guid]
    return rows[0] if len(rows) == 1 else None


def _verify(master, record):
    errors = []
    for item in record["visibility"]:
        binding = _find_binding(master, item["binding_guid"])
        tracks = [] if binding is None else list(binding.get_tracks())
        track = tracks[item["track_index"]] if item["track_index"] < len(tracks) else None
        if track is None or track.get_class().get_name() != "MovieSceneVisibilityTrack" or _prop(track) != ("bHidden", "bHidden"):
            errors.append("VIS_TRACK|" + item["path"]); continue
        sections = list(track.get_sections()); channels = [] if len(sections) != 1 else list(sections[0].get_all_channels())
        if len(channels) != 1 or _range(sections[0], master) != record["plan"]["window"]["hidden_range"] \
                or bool(channels[0].get_default()) is not False:
            errors.append("VIS_SECTION|" + item["path"])
    tracks = list(master.get_tracks()); fi = record["fade"]["track_index"]
    fade = tracks[fi] if fi < len(tracks) else None
    if fade is None or fade.get_class().get_name() != "MovieSceneFadeTrack":
        errors.append("FADE_TRACK")
    else:
        sections = list(fade.get_sections()); channels = [] if len(sections) != 1 else list(sections[0].get_all_channels())
        got = [] if len(channels) != 1 else [[int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value),
                                             round(float(k.get_value()), 4)] for k in channels[0].get_keys()]
        if len(sections) != 1 or _range(sections[0], master) != record["plan"]["window"]["fade_section_range"] \
                or got != record["plan"]["window"]["fade_keys"]:
            errors.append("FADE_SECTION|%s" % got)
    return errors


def _verify_reverted(master, record):
    errors = []
    wanted_range = record["plan"]["window"]["hidden_range"]
    for item in record["visibility"]:
        binding = _find_binding(master, item["binding_guid"])
        if item["created_binding"]:
            if binding is not None:
                errors.append("CREATED_BINDING_REMAINS|" + item["path"])
            continue
        if binding is None:
            errors.append("REUSED_BINDING_MISSING|" + item["path"]); continue
        for track in binding.get_tracks():
            if track.get_class().get_name() == "MovieSceneVisibilityTrack" and _prop(track) == ("bHidden", "bHidden") \
                    and any(_range(section, master) == wanted_range for section in track.get_sections()):
                errors.append("OWNED_VISIBILITY_REMAINS|" + item["path"])
    wanted_fade = record["plan"]["window"]["fade_section_range"]
    for track in master.get_tracks():
        if track.get_class().get_name() == "MovieSceneFadeTrack" \
                and any(_range(section, master) == wanted_fade for section in track.get_sections()):
            errors.append("OWNED_FADE_REMAINS")
    return errors


def dry(run, args, world):
    if os.path.isfile(RECORD):
        raise RuntimeError("ACTIVE_RECORD")
    source = _read(SOURCE); master = unreal.load_asset(C.MASTER)
    plan = C.build_plan(source, _rate(master.get_tick_resolution()), _rate(master.get_display_rate()), args)
    _actors, bindings = _preflight(master, world, plan)
    plan["bindings"] = bindings; plan["plan_sha256"] = C.digest(plan)
    after = _census()
    if after != {"content": [], "maps": []}:
        raise RuntimeError("DRY_DIRTIED|%s" % after)
    report = os.path.join(HERE, "p96_master_tail_dry_%s.json" % run)
    _write(report, {"run": run, "mode": "DRY", "mutated": 0, "plan": plan, "census": after}, True)
    unreal.log("%s_DRY_OK|run=%s|mutated=0|actors=67|range=%s|fade=%s|plan_sha256=%s|report=%s|dirty=0" %
               (MARK, run, plan["window"]["hidden_range"], plan["window"]["fade_keys"], plan["plan_sha256"], report))


def apply(run, args, world):
    if args.get("confirm") != CONFIRMS["APPLY"] or not str(args.get("decided_by") or "").strip():
        raise RuntimeError("CONFIRM_OR_DECIDED_BY")
    source = _read(SOURCE); master = unreal.load_asset(C.MASTER)
    plan = C.build_plan(source, _rate(master.get_tick_resolution()), _rate(master.get_display_rate()), args)
    actors, bindings = _preflight(master, world, plan); plan["bindings"] = bindings; plan["plan_sha256"] = C.digest(plan)
    if args.get("plan_sha256") != plan["plan_sha256"]:
        raise RuntimeError("PLAN_DIGEST_MISMATCH|expected=" + plan["plan_sha256"])
    backup = _backup(run, plan)
    record = {"schema": 1, "run": run, "status": "applying", "plan": plan, "backup": backup,
              "visibility": [], "fade": None}
    _write(RECORD, record, True); master.modify()
    for row in plan["inventory"]:
        actor = actors[row["path"]]; binding = _binding_for(master, world, actor); created = binding is None
        if created:
            binding = master.add_possessable(actor)
        track = binding.add_track(unreal.MovieSceneVisibilityTrack)
        track.set_property_name_and_path("bHidden", "bHidden")
        section = track.add_section(); section.set_range(*plan["window"]["hidden_range"])
        section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
        channels = list(section.get_all_channels())
        if len(channels) != 1:
            raise RuntimeError("VIS_CHANNEL_COUNT|NOTHING_SAVED_DONT_SAVE_RESTART")
        channels[0].set_default(False)
        record["visibility"].append({"path": row["path"], "binding_guid": _guid(binding),
                                     "track_index": list(binding.get_tracks()).index(track), "created_binding": created})
        _write(RECORD, record)
    fade = master.add_track(unreal.MovieSceneFadeTrack)  # UE 5.8: add_master_track removed (live 10 Oct); add_track per SequenceExtensions.h
    section = fade.add_section(); section.set_range(*plan["window"]["fade_section_range"])
    section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    channel = list(section.get_all_channels())[0]
    for frame, value in plan["window"]["fade_keys"]:
        channel.add_key(unreal.FrameNumber(frame), value, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                        interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    record["fade"] = {"track_index": list(master.get_tracks()).index(fade)}; _write(RECORD, record)
    errors = _verify(master, record)
    if errors:
        raise RuntimeError("PRE_SAVE_READBACK|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % errors)
    if _census() != {"content": [C.MASTER], "maps": []}:
        raise RuntimeError("DIRTY_SCOPE|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % _census())
    if not unreal.EditorAssetLibrary.save_asset(C.MASTER, only_if_is_dirty=False):
        raise RuntimeError("SAVE")
    errors = _verify(unreal.load_asset(C.MASTER), record)
    if errors or _census() != {"content": [], "maps": []}:
        raise RuntimeError("POST_SAVE_READBACK|errors=%s|census=%s" % (errors, _census()))
    record.update(status="applied", applied=datetime.datetime.now().isoformat(timespec="seconds")); _write(RECORD, record)
    unreal.log("%s_APPLY_OK|run=%s|actors=67|tracks=67|fade=1|saved=%s|backup=%s|dirty=0|readback=1" %
               (MARK, run, C.MASTER, backup))


def revert(run, args, world):
    if args.get("confirm") != CONFIRMS["REVERT"]:
        raise RuntimeError("CONFIRM|want=" + CONFIRMS["REVERT"])
    record = _read(RECORD)
    if record.get("status") != "applied":
        raise RuntimeError("RECORD_STATUS")
    master = unreal.load_asset(C.MASTER); errors = _verify(master, record)
    if errors:
        raise RuntimeError("APPLIED_STATE_DRIFT|%s" % errors)
    backup = _backup(run + "-REVERT", record["plan"])
    for item in reversed(record["visibility"]):
        binding = _find_binding(master, item["binding_guid"]); tracks = list(binding.get_tracks())
        binding.remove_track(tracks[item["track_index"]])
        if item["created_binding"]:
            if list(binding.get_tracks()) or list(binding.get_child_possessables()):
                raise RuntimeError("CREATED_BINDING_NOT_EMPTY|NOTHING_SAVED_DONT_SAVE_RESTART")
            binding.remove()
    master.remove_track(list(master.get_tracks())[record["fade"]["track_index"]])
    errors = _verify_reverted(master, record)
    if errors:
        raise RuntimeError("REVERT_PRE_SAVE_READBACK|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % errors)
    if _census() != {"content": [C.MASTER], "maps": []}:
        raise RuntimeError("REVERT_DIRTY_SCOPE|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % _census())
    if not unreal.EditorAssetLibrary.save_asset(C.MASTER, only_if_is_dirty=False) or _census() != {"content": [], "maps": []}:
        raise RuntimeError("REVERT_SAVE")
    errors = _verify_reverted(unreal.load_asset(C.MASTER), record)
    if errors:
        raise RuntimeError("REVERT_POST_SAVE_READBACK|%s" % errors)
    archived = RECORD + ".reverted-" + run; record.update(status="reverted", revert_backup=backup); _write(RECORD, record)
    os.replace(RECORD, archived)
    unreal.log("%s_REVERT_OK|run=%s|tracks_removed=67|fade_removed=1|saved=%s|backup=%s|record=%s|dirty=0" %
               (MARK, run, C.MASTER, backup, archived))


def main():
    args = _read(ARGS); run = str(args.get("run_id") or ""); mode = str(args.get("mode") or "").upper()
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]{5,100}$", run) or mode not in ("DRY", "APPLY", "REVERT"):
        raise RuntimeError("ARGS")
    world = _context(run, mutating=mode == "APPLY")
    if mode == "DRY": dry(run, args, world)
    elif mode == "APPLY": apply(run, args, world)
    else: revert(run, args, world)


if unreal is not None and not getattr(unreal, "_PUSS_FAKE", False):
    try:
        main()
    except Exception as exc:
        unreal.log_error("%s_FAILED|%s: %s" % (MARK, type(exc).__name__, exc)); raise
