"""Job 184: extend S1 LIGHTS_OUT to the light rig missed by Job 169.

The selection is intentionally closed: every non-zero P01 SCORE light plus the
single S1 Ghost Light.  Counts and label digests come from the Job 184 owned-PIE
measurement at frame 3880.  Existing bindings/tracks are never rewritten.
"""
import datetime
import hashlib
import json
import os
import re

try:
    import unreal
except ImportError:  # offline harness
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.normpath(os.path.join(HERE, "..", "S1RigFade_20261009", "s1_rig_fade.py"))
SEQ_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
PREFIX = "Job184 Lights Out: "
P01_RE = re.compile(r"^P01 SCORE B\d{2} \S+ \S+$")
EXPECTED_ALL_P01_COUNT = 236
EXPECTED_ALL_P01_DIGEST = "4e4b73e7882f8927376bb6f3989781ba1f07a8c5ef25b459312a8ebb508c3870"
EXPECTED_NONZERO_P01_COUNT = 212
EXPECTED_NONZERO_P01_DIGEST = "7e5e553ed13111f1aee6dc4937a26e57c0a32b16a75b345911455e10885201a3"
EXPECTED_SELECTED_COUNT = 213
EXPECTED_SELECTED_DIGEST = "1205e92b70b82a6948178ec5fe207971444664a47cf64a8781b63ebcc4b9c77c"
FADE_START = 3800
FADE_END = 3838
EPSILON = 0.0001
CONFIRMS = {
    "DRY": "DRY JOB184 S1 MISSED LIGHTS",
    "APPLY": "APPLY JOB184 S1 MISSED LIGHTS",
    "READBACK": "READBACK JOB184 S1 MISSED LIGHTS",
    "REVERT": "REVERT JOB184 S1 MISSED LIGHTS",
}


class Stop(RuntimeError):
    pass


def label_digest(labels):
    payload = json.dumps(sorted(labels), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def choose_labels(rows):
    """Pure closed-set selector used by the live tool and offline harness."""
    all_p01 = sorted(row["label"] for row in rows if P01_RE.match(row["label"]))
    nonzero = sorted(row["label"] for row in rows
                     if P01_RE.match(row["label"]) and float(row["intensity"]) > EPSILON)
    ghost = [row for row in rows if row["label"] == "S1 Ghost Light"]
    if len(set(all_p01)) != len(all_p01):
        raise Stop("DUPLICATE_P01_LABEL")
    if len(all_p01) != EXPECTED_ALL_P01_COUNT or label_digest(all_p01) != EXPECTED_ALL_P01_DIGEST:
        raise Stop("ALL_P01_MANIFEST_DRIFT|count=%d|digest=%s" % (len(all_p01), label_digest(all_p01)))
    if len(nonzero) != EXPECTED_NONZERO_P01_COUNT or label_digest(nonzero) != EXPECTED_NONZERO_P01_DIGEST:
        raise Stop("NONZERO_P01_MANIFEST_DRIFT|count=%d|digest=%s" % (len(nonzero), label_digest(nonzero)))
    if len(ghost) != 1 or abs(float(ghost[0]["intensity"]) - 60.0) > EPSILON:
        raise Stop("S1_GHOST_LIGHT_DRIFT|count=%d|intensity=%s" %
                   (len(ghost), None if not ghost else ghost[0]["intensity"]))
    selected = sorted(nonzero + ["S1 Ghost Light"])
    if len(selected) != EXPECTED_SELECTED_COUNT or label_digest(selected) != EXPECTED_SELECTED_DIGEST:
        raise Stop("SELECTED_MANIFEST_DRIFT|count=%d|digest=%s" % (len(selected), label_digest(selected)))
    return selected


def _legacy():
    with open(LEGACY, "r", encoding="utf-8") as handle:
        source = handle.read()
    namespace = {"__name__": "job184_s1_rig_fade_definitions", "__file__": LEGACY}
    exec(compile(source, LEGACY, "exec"), namespace)
    required = ("_snapshot", "_track_row", "_binding_map", "_census", "_load_sequence",
                "_backup", "_save", "_guid", "_object_path", "_bound_objects")
    if any(name not in namespace for name in required):
        raise Stop("LEGACY_HELPERS_MISSING")
    namespace["_here"] = lambda: HERE
    return namespace


def _log(message, error=False):
    if unreal is None:
        print(message)
    elif error:
        unreal.log_error(message)
    else:
        unreal.log(message)


def _stop(run, reason):
    message = "JOB184_S1_MISSED_LIGHTS_STOP|run=%s|%s" % (run, reason)
    _log(message, error=True)
    raise Stop(message)


def _write(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    os.replace(temporary, path)


def _read(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise Stop("MISSING_FILE|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _plan_path():
    return os.path.join(HERE, "job184_s1_missed_lights_plan.json")


def _record_path():
    return os.path.join(HERE, "job184_s1_missed_lights_ACTIVE.json")


def _census(namespace):
    return namespace["_census"]()


def _preflight(namespace, mode, run, confirm):
    if CONFIRMS.get(mode) != str(confirm or "").strip():
        _stop(run, "CONFIRM_MISMATCH|want=%r|got=%r" % (CONFIRMS.get(mode), confirm))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")
    if _census(namespace) != {"content": [], "maps": []}:
        _stop(run, "DIRTY_CENSUS|%s" % json.dumps(_census(namespace), sort_keys=True))
    if mode in ("DRY", "APPLY") and os.path.isfile(_record_path()):
        _stop(run, "APPLIED_RECORD_EXISTS|%s" % _record_path())
    return editor.get_editor_world()


def _object_binding_map(namespace, seq, world):
    rows = {}
    for binding in seq.get_bindings():
        objects = list(namespace["_bound_objects"](seq, binding, world))
        if len(objects) == 1:
            path = namespace["_object_path"](objects[0])
            if path in rows:
                raise Stop("OBJECT_BOUND_MORE_THAN_ONCE|%s" % path)
            rows[path] = binding
    return rows


def _discover(namespace, seq, world, run):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_label = {}
    rows = []
    for actor in actors:
        label = str(actor.get_actor_label())
        component = actor.get_component_by_class(unreal.LightComponentBase)
        if component is None:
            continue
        intensity = float(component.get_editor_property("intensity"))
        rows.append({"label": label, "intensity": intensity})
        by_label.setdefault(label, []).append((actor, component, intensity))
    selected = choose_labels(rows)
    object_bindings = _object_binding_map(namespace, seq, world)
    targets = []
    for label in selected:
        matches = by_label.get(label, [])
        if len(matches) != 1:
            _stop(run, "TARGET_ACTOR_COUNT|label=%s|count=%d" % (label, len(matches)))
        actor, component, intensity = matches[0]
        actor_path = namespace["_object_path"](actor)
        component_path = namespace["_object_path"](component)
        actor_binding = object_bindings.get(actor_path)
        component_binding = object_bindings.get(component_path)
        if component_binding is not None:
            conflicts = [track for track in component_binding.get_tracks()
                         if track.get_class().get_name() == "MovieSceneFloatTrack"
                         and namespace["_track_property"](track)[0] == "Intensity"]
            if conflicts:
                _stop(run, "EXISTING_INTENSITY_TRACK|label=%s|count=%d" % (label, len(conflicts)))
        targets.append({
            "label": label,
            "base_intensity": intensity,
            "actor_path": actor_path,
            "component_path": component_path,
            "actor_binding_guid": None if actor_binding is None else namespace["_guid"](actor_binding.get_id()),
            "component_binding_guid": None if component_binding is None else namespace["_guid"](component_binding.get_id()),
        })
    return targets


def _report(namespace, seq, world, run):
    snapshot = namespace["_snapshot"](seq)
    targets = _discover(namespace, seq, world, run)
    plan = {"sequence": SEQ_PATH, "fade": [FADE_START, FADE_END], "targets": targets,
            "selection_count": len(targets), "selection_digest": label_digest([x["label"] for x in targets])}
    return {"schema_version": 1, "tool": "JOB184_S1_MISSED_LIGHTS", "run": run,
            "plan": plan, "plan_digest": namespace["digest"](plan),
            "snapshot_digest": namespace["digest"](snapshot), "snapshot": snapshot,
            "census": _census(namespace), "apply_ready": True}


def _run_dry(namespace, run, args):
    world = _preflight(namespace, "DRY", run, args.get("confirm"))
    seq = namespace["_load_sequence"](run)
    report = _report(namespace, seq, world, run)
    if _census(namespace) != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED")
    _write(os.path.join(HERE, "job184_s1_missed_lights_dry_%s.json" % run), report)
    _write(_plan_path(), {"run": run, "plan_digest": report["plan_digest"],
                         "snapshot_digest": report["snapshot_digest"]})
    _log("JOB184_S1_MISSED_LIGHTS_DRY_OK|run=%s|targets=%d|p01=212|ghost=1|fade=%d:%d|mutated=0|dirty=0+0" %
         (run, len(report["plan"]["targets"]), FADE_START, FADE_END))
    return report


def _add_binding(namespace, seq, obj, display_name, parent=None):
    before = {namespace["_guid"](binding.get_id()) for binding in seq.get_bindings()}
    binding = seq.add_possessable(obj)
    guid = namespace["_guid"](binding.get_id())
    if guid in before:
        raise Stop("ADD_POSSESSABLE_RETURNED_EXISTING|%s" % display_name)
    if parent is not None:
        binding.set_parent(parent)
    binding.set_display_name(display_name)
    return binding


def _write_ramp(namespace, seq, binding, label, base, run):
    conflicts = [track for track in binding.get_tracks()
                 if track.get_class().get_name() == "MovieSceneFloatTrack"
                 and namespace["_track_property"](track)[0] == "Intensity"]
    if conflicts:
        _stop(run, "PROPERTY_TRACK_ALREADY_EXISTS|%s|count=%d" % (label, len(conflicts)))
    track = binding.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path("Intensity", "Intensity")
    track.set_display_name(PREFIX + "Intensity")
    section = track.add_section()
    section.set_range(FADE_START, FADE_END + 1)
    section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    channels = list(section.get_all_channels())
    if len(channels) != 1:
        _stop(run, "RAMP_CHANNEL_COUNT|%s|%d" % (label, len(channels)))
    channel = channels[0]
    channel.add_key(unreal.FrameNumber(FADE_START), float(base),
                    time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                    interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    channel.add_key(unreal.FrameNumber(FADE_END), 0.0,
                    time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                    interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    return track


def _assert_scoped(namespace, before, after, operations):
    for key in ("display_rate", "tick_resolution", "playback", "root_tracks", "markers"):
        if before[key] != after[key]:
            raise Stop("UNSCOPED_SEQUENCE_CHANGE|%s" % key)
    old = {row["guid"]: row for row in before["bindings"]}
    new = {row["guid"]: row for row in after["bindings"]}
    created = {op["binding_guid"] for op in operations if op["binding_created"]}
    if set(new) - set(old) != created or set(old) - set(new):
        raise Stop("BINDING_SET_CHANGED")
    tracks_by_guid = {}
    for op in operations:
        if op.get("track_after") is not None:
            tracks_by_guid.setdefault(op["binding_guid"], []).append(op["track_after"])
    for guid, old_row in old.items():
        new_row = new[guid]
        if (old_row["name"], old_row["parent"]) != (new_row["name"], new_row["parent"]):
            raise Stop("EXISTING_BINDING_METADATA_CHANGED|%s" % guid)
        expected_tracks = list(old_row["tracks"]) + tracks_by_guid.get(guid, [])
        expected_tracks.sort(key=lambda row: (row["class"], row["property"], row["path"], namespace["digest"](row)))
        if expected_tracks != new_row["tracks"]:
            raise Stop("EXISTING_BINDING_TRACKS_CHANGED|%s" % guid)
    for guid in created:
        row = new[guid]
        expected_tracks = tracks_by_guid.get(guid, [])
        expected_tracks.sort(key=lambda item: (item["class"], item["property"], item["path"], namespace["digest"](item)))
        if row["tracks"] != expected_tracks:
            raise Stop("CREATED_BINDING_TRACKS_CHANGED|%s" % guid)


def _run_apply(namespace, run, args):
    world = _preflight(namespace, "APPLY", run, args.get("confirm"))
    seq = namespace["_load_sequence"](run)
    report = _report(namespace, seq, world, run)
    dry = _read(_plan_path())
    if (dry.get("plan_digest") != report["plan_digest"] or
            dry.get("snapshot_digest") != report["snapshot_digest"]):
        _stop(run, "CHANGED_SINCE_DRY|rerun DRY")
    backup = namespace["_backup"](run, "Job184MissedLights")
    transaction = os.path.join(HERE, "job184_s1_missed_lights_transaction_%s.json" % run)
    record = {"schema_version": 1, "tool": "JOB184_S1_MISSED_LIGHTS", "run": run,
              "applied": False, "written_before_mutation": True, "sequence": SEQ_PATH,
              "plan": report["plan"], "snapshot_before": report["snapshot"],
              "snapshot_before_digest": report["snapshot_digest"], "backup": backup, "operations": []}
    _write(transaction, record)

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_path = {namespace["_object_path"](actor): actor for actor in actors}
    for actor in actors:
        component = actor.get_component_by_class(unreal.LightComponentBase)
        if component is not None:
            by_path[namespace["_object_path"](component)] = component
    bindings = namespace["_binding_map"](seq)
    for target in report["plan"]["targets"]:
        actor = by_path.get(target["actor_path"])
        component = by_path.get(target["component_path"])
        if actor is None or component is None:
            _stop(run, "TARGET_OBJECT_GONE|%s" % target["label"])
        if abs(float(component.get_editor_property("intensity")) - float(target["base_intensity"])) > EPSILON:
            _stop(run, "TARGET_INTENSITY_CHANGED|%s" % target["label"])
        actor_binding = bindings.get(target["actor_binding_guid"])
        if actor_binding is None:
            actor_binding = _add_binding(namespace, seq, actor, PREFIX + target["label"])
            actor_guid = namespace["_guid"](actor_binding.get_id())
            bindings[actor_guid] = actor_binding
            record["operations"].append({"kind": "new_actor_binding", "binding_guid": actor_guid,
                                         "binding_created": True, "track_after": None})
        component_binding = bindings.get(target["component_binding_guid"])
        if component_binding is None:
            component_binding = _add_binding(namespace, seq, component, PREFIX + target["label"] + " Component",
                                             parent=actor_binding)
            component_guid = namespace["_guid"](component_binding.get_id())
            bindings[component_guid] = component_binding
            component_created = True
        else:
            component_guid = namespace["_guid"](component_binding.get_id())
            component_created = False
        track = _write_ramp(namespace, seq, component_binding, target["label"], target["base_intensity"], run)
        record["operations"].append({"kind": "new_intensity_track", "label": target["label"],
                                     "binding_guid": component_guid, "binding_created": component_created,
                                     "track_after": namespace["_track_row"](track, seq),
                                     "base_intensity": target["base_intensity"]})
        _write(transaction, record)
    after = namespace["_snapshot"](seq)
    _assert_scoped(namespace, report["snapshot"], after, record["operations"])
    record.update({"applied": True, "snapshot_after": after,
                   "snapshot_after_digest": namespace["digest"](after)})
    _write(transaction, record)
    saves = namespace["_save"](run)
    readback = namespace["_snapshot"](namespace["_load_sequence"](run))
    if readback != after or _census(namespace) != {"content": [], "maps": []}:
        _stop(run, "POSTSAVE_READBACK_MISMATCH|restore=%s" % backup["root"])
    record.update({"saves": saves, "saved_readback": readback,
                   "saved_readback_digest": namespace["digest"](readback),
                   "census_after": _census(namespace)})
    _write(_record_path(), record)
    _write(transaction, dict(record, transaction_complete=True))
    _log("JOB184_S1_MISSED_LIGHTS_APPLY_OK|run=%s|targets=%d|p01=212|ghost=1|fade=%d:%d|saved=1|readback=1|dirty=0+0|backup=%s" %
         (run, len(report["plan"]["targets"]), FADE_START, FADE_END, backup["root"]))
    return record


def _run_readback(namespace, run, args):
    _preflight(namespace, "READBACK", run, args.get("confirm"))
    record = _read(_record_path())
    if not record.get("applied") or len(record.get("operations", [])) < EXPECTED_SELECTED_COUNT:
        _stop(run, "RECORD_SHAPE")
    snapshot = namespace["_snapshot"](namespace["_load_sequence"](run))
    if snapshot != record.get("saved_readback"):
        _stop(run, "SAVED_STATE_DRIFT")
    _log("JOB184_S1_MISSED_LIGHTS_READBACK_OK|run=%s|targets=%d|readback=1|dirty=0+0" %
         (run, EXPECTED_SELECTED_COUNT))
    return record


def run(args):
    if unreal is None:
        raise Stop("UNREAL_REQUIRED")
    namespace = _legacy()
    mode = str(args.get("mode", "DRY")).upper()
    run_id = str(args.get("run_id") or datetime.datetime.now().strftime("J184-S1-%Y%m%d-%H%M%S"))
    function = {"DRY": _run_dry, "APPLY": _run_apply, "READBACK": _run_readback}.get(mode)
    if function is None:
        _stop(run_id, "MODE|%s" % mode)
    return function(namespace, run_id, args)

