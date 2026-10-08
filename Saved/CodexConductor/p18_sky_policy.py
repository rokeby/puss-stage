"""P18 show-side no-external-sky policy for Klara Scene levels.

Modes are DRY / APPLY / REVERT with exact confirmation strings.  The tool adds
one RESTORE_STATE visibility section to an *existing* Klara actor binding in our
LS_DevScene_0N sequence.  It never creates a possessable and refuses if any map
package becomes dirty, so Klara's streamed levels are never saved.

Defaults from Gary's 8 Oct direction:
  S1: SkyLight OFF, DirectionalLight kept (Gary to decide the sun).
  S4: SkyLight OFF, DirectionalLight OFF.

Nothing in this file auto-runs outside Unreal; the offline harness imports its
pure validation, planning and diff functions.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness.
    unreal = None


MARK = "P18_SKY_POLICY"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ARGS_NAME = "p18_sky_policy_args.json"
TRACK_NAME = "P18 Sky Policy - Hidden In Game"
MODES = ("DRY", "APPLY", "REVERT")

# Binding ids are measured records from the already-applied Klara reveal.  APPLY
# additionally checks each current binding's display name before touching it.
SCENES = {
    "1": {
        "sequence": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01",
        "klara_level": "/Game/KK_S1_Animals/L_Animals",
        "defaults": {"skylight_off": True, "sun_off": False},
        "bindings": {
            "skylight": {"guid": "AEA1E44F405DFF48BF8BE1ADA5D7656B",
                         "name": "Klara Hookin - Hers Dark: SkyLight"},
            "sun": {"guid": "3FB7BB1849CFDB5B4E3CCB94EB3E417D",
                    "name": "Klara Hookin - Hers Dark: DirectionalLight"},
        },
    },
    "4": {
        "sequence": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04",
        "klara_level": "/Game/L_KK_children",
        "defaults": {"skylight_off": True, "sun_off": True},
        "bindings": {
            "skylight": {"guid": "11E354EC45E6A26428C4DD98254D50D8",
                         "name": "Klara Hookin - Hers Dark: SkyLight"},
            "sun": {"guid": "6DA2FFE1405A0A3D3A8CD3BDB9038375",
                    "name": "Klara Hookin - Hers Dark: DirectionalLight"},
        },
    },
}


class PlanError(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def confirm_text(mode):
    return "%s P18 SKY POLICY" % str(mode).upper()


def normalize_args(raw):
    allowed = {"mode", "confirm", "run_id", "scene", "skylight_off", "sun_off", "decided_by"}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise PlanError("UNKNOWN_ARGS|%s" % unknown)
    mode = str(raw.get("mode", "DRY")).upper()
    if mode not in MODES:
        raise PlanError("MODE|%s" % mode)
    scene = str(raw.get("scene", "4"))
    if scene not in SCENES:
        raise PlanError("SCENE|supported S1/S4, got %s" % scene)
    defaults = SCENES[scene]["defaults"]
    sky = raw.get("skylight_off", defaults["skylight_off"])
    sun = raw.get("sun_off", defaults["sun_off"])
    if type(sky) is not bool or type(sun) is not bool:
        raise PlanError("POLICY_FLAGS|skylight_off and sun_off must be bool")
    if not sky and not sun:
        raise PlanError("EMPTY_POLICY|nothing would be forced off")
    return {
        "mode": mode,
        "confirm": raw.get("confirm"),
        "run_id": raw.get("run_id"),
        "scene": scene,
        "skylight_off": sky,
        "sun_off": sun,
        "decided_by": str(raw.get("decided_by") or "Gary, 8 Oct 2026; S1 sun remains Gary to decide"),
    }


def plan_from_args(args):
    row = SCENES[args["scene"]]
    targets = []
    if args["skylight_off"]:
        targets.append(dict(kind="skylight", **row["bindings"]["skylight"]))
    if args["sun_off"]:
        targets.append(dict(kind="sun", **row["bindings"]["sun"]))
    plan = {
        "schema": 1,
        "scene": args["scene"],
        "sequence": row["sequence"],
        "klara_level_read_only": row["klara_level"],
        "targets": targets,
        "save_only": [row["sequence"]],
        "never_save": [row["klara_level"], EXPECTED_WORLD],
        "track": TRACK_NAME,
        "completion_mode": "RESTORE_STATE",
        "gary_to_decide": "S1 DirectionalLight" if args["scene"] == "1" and not args["sun_off"] else None,
        "decided_by": args["decided_by"],
    }
    plan["digest"] = _digest(plan)
    return plan


def exact_dirty(census, allowed_content):
    problems = []
    content = sorted(census.get("content") or [])
    maps = sorted(census.get("maps") or [])
    if content != sorted(allowed_content):
        problems.append("DIRTY_CONTENT|got=%s|want=%s" % (content, sorted(allowed_content)))
    if maps:
        problems.append("DIRTY_MAPS_FORBIDDEN|%s" % maps)
    return problems


def state_diff(got, want):
    return [] if got == want else ["STATE_DIFF|got=%s|want=%s" % (got, want)]


def _here():
    return os.path.dirname(os.path.abspath(__file__))


def _load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    fd = os.open(path, flags)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _record_path(scene):
    return os.path.join(_here(), "p18_sky_policy_record_S%s.json" % scene)


def _plan_path(scene):
    return os.path.join(_here(), "p18_sky_policy_dry_S%s.json" % scene)


def _stop(run, text):
    unreal.log_error("%s_FAILED|run=%s|%s" % (MARK, run, text))
    raise RuntimeError(text)


def _asset_path(value):
    return str(value).split(".", 1)[0]


def _guid(binding):
    return str(unreal.GuidLibrary.conv_guid_to_string(binding.get_id())).replace("-", "").upper()


def _bindings_by_guid(sequence):
    return {_guid(binding): binding for binding in sequence.get_bindings()}


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
        "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages()),
    }


def _world_and_gates(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_RUNNING|nothing changed")
    world = editor.get_editor_world()
    name = _asset_path(world.get_outermost().get_name()) if world is not None else None
    if name != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD|%s|want=%s|nothing changed" % (name, EXPECTED_WORLD))
    census = _census()
    if census != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|%s|nothing changed" % census)
    return world


def _track_snapshot(track):
    sections = []
    for section in track.get_sections():
        channels = list(section.get_all_channels())
        sections.append({
            "range": [int(section.get_start_frame()), int(section.get_end_frame())],
            "defaults": [bool(channel.get_default()) for channel in channels],
            "channels": len(channels),
            "completion": str(section.get_completion_mode()).split(".")[-1],
        })
    return {
        "class": str(track.get_class().get_name()),
        "display": str(track.get_display_name()),
        "property": str(track.get_property_name()),
        "sections": sections,
    }


def _snapshot(sequence, plan, run):
    bindings = _bindings_by_guid(sequence)
    targets = []
    for target in plan["targets"]:
        binding = bindings.get(target["guid"])
        if binding is None:
            _stop(run, "BINDING_GUID_MISSING|%s|%s" % (target["kind"], target["guid"]))
        name = str(binding.get_display_name())
        if name != target["name"]:
            _stop(run, "BINDING_NAME_DRIFT|%s|got=%r|want=%r" % (target["guid"], name, target["name"]))
        owned = [_track_snapshot(track) for track in binding.get_tracks()
                 if str(track.get_display_name()) == TRACK_NAME]
        targets.append({"kind": target["kind"], "guid": target["guid"], "name": name, "owned": owned})
    return {
        "sequence": _asset_path(sequence.get_path_name()),
        "playback": [int(sequence.get_playback_start()), int(sequence.get_playback_end())],
        "targets": targets,
    }


def _validate_live_plan(plan, sequence, run, require_owned):
    snap = _snapshot(sequence, plan, run)
    if snap["sequence"] != plan["sequence"]:
        _stop(run, "SEQUENCE_PATH|%s|want=%s" % (snap["sequence"], plan["sequence"]))
    for row in snap["targets"]:
        count = len(row["owned"])
        if require_owned and count != 1:
            _stop(run, "OWNED_TRACK_COUNT|%s|%d|want=1" % (row["kind"], count))
        if not require_owned and count:
            _stop(run, "ALREADY_PRESENT|%s|%d|nothing changed" % (row["kind"], count))
    return snap


def _content_file(asset_path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


def _backup(sequence_path, label, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "%s-%s" % (label, run))
    os.makedirs(folder, exist_ok=False)
    source = _content_file(sequence_path)
    if not os.path.isfile(source):
        _stop(run, "SOURCE_FILE_MISSING|%s" % source)
    destination = os.path.join(folder, os.path.basename(source))
    shutil.copy2(source, destination)
    source_hash = hashlib.sha256(open(source, "rb").read()).hexdigest()
    backup_hash = hashlib.sha256(open(destination, "rb").read()).hexdigest()
    if source_hash != backup_hash:
        _stop(run, "BACKUP_HASH|%s" % source)
    return {"folder": folder, "source": source, "copy": destination, "sha256": source_hash}


def _add_owned_track(binding, frame_range, run):
    track = binding.add_track(unreal.MovieSceneVisibilityTrack)
    if str(track.get_property_name()) in ("None", ""):
        track.set_property_name_and_path("bHiddenInGame", "bHiddenInGame")
    if str(track.get_property_name()) != "bHiddenInGame":
        _stop(run, "VISIBILITY_PROPERTY|%r" % str(track.get_property_name()))
    track.set_display_name(TRACK_NAME)
    section = track.add_section()
    section.set_range(int(frame_range[0]), int(frame_range[1]))
    section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    channels = list(section.get_all_channels())
    if len(channels) != 1:
        _stop(run, "VISIBILITY_CHANNELS|%d" % len(channels))
    channels[0].set_default(True)
    return track


def _expected_after(before):
    out = copy.deepcopy(before)
    start, end = out["playback"]
    expected = {
        "class": "MovieSceneVisibilityTrack",
        "display": TRACK_NAME,
        "property": "bHiddenInGame",
        "sections": [{"range": [start, end], "defaults": [True], "channels": 1,
                      "completion": "RESTORE_STATE"}],
    }
    for row in out["targets"]:
        row["owned"] = [expected]
    return out


def _remove_owned_tracks(sequence, plan, run):
    bindings = _bindings_by_guid(sequence)
    removed = 0
    for target in plan["targets"]:
        binding = bindings[target["guid"]]
        tracks = [track for track in binding.get_tracks() if str(track.get_display_name()) == TRACK_NAME]
        if len(tracks) != 1:
            _stop(run, "OWNED_TRACK_COUNT|%s|%d|NOTHING SAVED; Don't-Save restart" % (target["kind"], len(tracks)))
        binding.remove_track(tracks[0])
        removed += 1
    return removed


def run_dry(args, plan, run):
    _world_and_gates(run)
    if os.path.exists(_record_path(args["scene"])):
        _stop(run, "RECORD_EXISTS|%s|revert first" % _record_path(args["scene"]))
    sequence = unreal.load_asset(plan["sequence"])
    if sequence is None:
        _stop(run, "SEQUENCE_MISSING|%s" % plan["sequence"])
    snapshot = _validate_live_plan(plan, sequence, run, require_owned=False)
    result = {"tool": MARK, "mode": "DRY", "run": run, "apply_ready": True, "plan": plan,
              "snapshot": snapshot, "dirty": _census(), "note": "No package was changed or saved."}
    _write_json(_plan_path(args["scene"]), result)
    unreal.log("%s_DRY_OK|run=%s|scene=S%s|targets=%s|dirty=0|plan=%s" %
               (MARK, run, args["scene"], ",".join(t["kind"] for t in plan["targets"]),
                _plan_path(args["scene"])))


def run_apply(args, plan, run):
    _world_and_gates(run)
    record_path = _record_path(args["scene"])
    if os.path.exists(record_path):
        _stop(run, "RECORD_EXISTS|%s|revert first" % record_path)
    dry = _load_json(_plan_path(args["scene"]))
    if not dry or not dry.get("apply_ready") or dry.get("plan", {}).get("digest") != plan["digest"]:
        _stop(run, "MATCHING_DRY_REQUIRED|run DRY with these exact args first")
    sequence = unreal.load_asset(plan["sequence"])
    before = _validate_live_plan(plan, sequence, run, require_owned=False)
    if before != dry.get("snapshot"):
        _stop(run, "STATE_DRIFTED_SINCE_DRY|nothing changed")

    backup = _backup(plan["sequence"], "PreP18SkyPolicy-S%s" % args["scene"], run)
    expected_after = _expected_after(before)
    record = {
        "schema": 1, "tool": MARK, "run": run, "scene": args["scene"], "applied": False,
        "written": datetime.datetime.now().isoformat(timespec="seconds"), "plan": plan,
        "backup": backup, "snapshot_before": before, "snapshot_after_expected": expected_after,
    }
    _write_json(record_path, record, exclusive=True)  # Record exists before the first UObject mutation.

    sequence.modify()
    bindings = _bindings_by_guid(sequence)
    for target in plan["targets"]:
        _add_owned_track(bindings[target["guid"]], before["playback"], run)
    after = _snapshot(sequence, plan, run)
    problems = state_diff(after, expected_after) + exact_dirty(_census(), [plan["sequence"]])
    if problems:
        _stop(run, "PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup=%s" % (problems, backup["folder"]))
    if not unreal.EditorAssetLibrary.save_asset(plan["sequence"], only_if_is_dirty=True):
        _stop(run, "SAVE_FAILED|%s|backup=%s" % (plan["sequence"], backup["folder"]))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s|backup=%s" % (_census(), backup["folder"]))

    # Saved-state read-back through Unreal.  No Klara map is ever in save_only.
    reloaded = unreal.load_asset(plan["sequence"])
    saved = _snapshot(reloaded, plan, run)
    problems = state_diff(saved, expected_after)
    if problems:
        _stop(run, "SAVED_READBACK|%s|recover=%s" % (problems, backup["folder"]))
    record.update({"applied": True, "snapshot_after": saved, "dirty_after": _census()})
    _write_json(record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|scene=S%s|targets=%s|saved_only=%s|maps_saved=0|dirty=0|backup=%s" %
               (MARK, run, args["scene"], ",".join(t["kind"] for t in plan["targets"]),
                plan["sequence"], backup["folder"]))


def run_revert(args, run):
    _world_and_gates(run)
    record_path = _record_path(args["scene"])
    record = _load_json(record_path)
    if not record or not record.get("applied"):
        _stop(run, "NOTHING_TO_REVERT|%s" % record_path)
    plan = record["plan"]
    # REVERT is tied to the recorded policy, not mutable current args.
    sequence = unreal.load_asset(plan["sequence"])
    current = _validate_live_plan(plan, sequence, run, require_owned=True)
    if current != record["snapshot_after"]:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|nothing changed")

    backup = _backup(plan["sequence"], "PreP18SkyPolicyRevert-S%s" % args["scene"], run)
    revert_record = os.path.join(_here(), "p18_sky_policy_revert_record_S%s_%s.json" % (args["scene"], run))
    _write_json(revert_record, {"tool": MARK, "mode": "REVERT", "run": run, "apply_record": record_path,
                                "backup": backup, "before": current}, exclusive=True)

    sequence.modify()
    removed = _remove_owned_tracks(sequence, plan, run)
    restored = _snapshot(sequence, plan, run)
    problems = state_diff(restored, record["snapshot_before"]) + exact_dirty(_census(), [plan["sequence"]])
    if problems:
        _stop(run, "REVERT_PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
              (problems, backup["folder"]))
    if not unreal.EditorAssetLibrary.save_asset(plan["sequence"], only_if_is_dirty=True):
        _stop(run, "REVERT_SAVE_FAILED|%s" % plan["sequence"])
    if _census() != {"content": [], "maps": []}:
        _stop(run, "REVERT_DIRTY_AFTER_SAVE|%s" % _census())
    saved = _snapshot(unreal.load_asset(plan["sequence"]), plan, run)
    if saved != record["snapshot_before"]:
        _stop(run, "REVERT_SAVED_READBACK|got=%s|want=%s|recover=%s" %
              (saved, record["snapshot_before"], backup["folder"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    _write_json(revert_record, {"tool": MARK, "mode": "REVERT", "run": run, "applied": True,
                                "backup": backup, "removed": removed, "saved_readback": saved,
                                "archived_apply_record": archived})
    unreal.log("%s_REVERT_OK|run=%s|scene=S%s|removed=%d|saved_only=%s|maps_saved=0|dirty=0|backup=%s" %
               (MARK, run, args["scene"], removed, plan["sequence"], backup["folder"]))


def main(raw=None):
    raw = dict(raw if raw is not None else globals().get("P18_SKY_POLICY_ARGS") or {})
    run = str(raw.get("run_id") or datetime.datetime.now().strftime("P18SKY-%Y%m%d-%H%M%S"))
    try:
        args = normalize_args(raw)
        if str(args.get("confirm") or "") != confirm_text(args["mode"]):
            _stop(run, "CONFIRM_MISMATCH|want=%r|got=%r" % (confirm_text(args["mode"]), args.get("confirm")))
        if args["mode"] == "REVERT":
            run_revert(args, run)
            return
        plan = plan_from_args(args)
        if args["mode"] == "DRY":
            run_dry(args, plan, run)
        else:
            run_apply(args, plan, run)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|%s" % exc)


if unreal is not None:
    main()

