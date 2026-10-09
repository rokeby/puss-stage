"""S1 rig-light fade authoring tool (P29, offline-authored 9 Oct 2026).

Modes and confirmations:
  DRY / ``DRY S1RIGFADE``
  APPLY / ``APPLY S1RIGFADE``
  REVERT / ``REVERT S1RIGFADE``

The tool audits LS_DevScene_01 around its local frames 269/282.  Visibility-off
steps receive a linear property ramp ending at the existing switch frame, so
the existing visibility section hides only after light output reaches zero.
Existing one-frame Intensity/FogDensity drops are retimed into the same ramp.

Evidence boundary:
  declaration-proven: the target and safety contract are in
    Docs/Conductor/codex_briefs/p29_s1_rig_fade.md:1-8 and _house_rules.md:1-17.
  measured (upstream record): klara_reveal_record_S1.json records Ours Off at
    frame 269 and rig_bulbs_hidden [282,6001), at 25 fps.
  declaration-proven: Saved/CodexStructure/hangar_build.py:132-140 creates
    emissive Lattice Bulb meshes and paired Lattice Glow light actors.
  inferred: fading the paired glow before hiding an emissive bulb mesh removes
    the lighting jolt; only the requested rendered review can prove the look.
"""

import datetime
import hashlib
import json
import os
import shutil


TOOL = "S1_RIG_FADE"
TOOL_VERSION = "2026-10-09a"
FOLDER = "S1RigFade_20261009"
SEQ_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
EXPECTED_FPS = 25.0
EXPECTED_TICK = 24000.0
RECORD = "s1_rig_fade_record.json"
PLAN = "s1_rig_fade_plan.json"
CONFIRMS = {
    "DRY": "DRY S1RIGFADE",
    "APPLY": "APPLY S1RIGFADE",
    "REVERT": "REVERT S1RIGFADE",
}
DEFAULTS = {
    "review_time_seconds": 224.0,
    "scene_local_switch_frame": 282,
    "search_radius_frames": 20,
    "fade_seconds": 1.52,
    "min_fade_seconds": 1.0,
    "max_fade_seconds": 2.0,
    "value_tolerance": 0.0001,
    "bulb_prefix": "S1 Lattice Bulb ",
    "glow_prefix": "S1 Lattice Glow ",
}
CLAIMS = [
    {"tier": "declaration-proven", "claim": "Only LS_DevScene_01 is saved.",
     "cite": "Docs/Conductor/codex_briefs/p29_s1_rig_fade.md:1-8"},
    {"tier": "measured", "claim": "The upstream S1 record places Ours Off at 269 and bulb hiding at 282.",
     "cite": "Saved/CodexConductor/KlaraIngest/klara_reveal_record_S1.json:10760-10790,10906-10910"},
    {"tier": "declaration-proven", "claim": "Lattice Bulbs are emissive meshes with paired Lattice Glow lights.",
     "cite": "Saved/CodexStructure/hangar_build.py:132-140"},
    {"tier": "inferred", "claim": "The paired-light ramp removes the perceived snap of the emissive bulb mesh.",
     "cite": "Docs/Conductor/codex_briefs/p29_s1_rig_fade.md:1-8"},
]


class Stop(RuntimeError):
    pass


class PlanError(ValueError):
    pass


def _ue():
    import unreal  # noqa: WPS433 - local so the module imports under system Python
    return unreal


def merged_params(raw):
    p = dict(DEFAULTS)
    p.update(raw or {})
    for key in ("review_time_seconds", "fade_seconds", "min_fade_seconds", "max_fade_seconds",
                "value_tolerance"):
        p[key] = float(p[key])
    for key in ("scene_local_switch_frame", "search_radius_frames"):
        p[key] = int(p[key])
    if p["search_radius_frames"] < 0:
        raise PlanError("SEARCH_RADIUS_NEGATIVE")
    if not p["min_fade_seconds"] <= p["fade_seconds"] <= p["max_fade_seconds"]:
        raise PlanError("FADE_SECONDS_OUTSIDE_CREATIVE_BOUNDS|%.3f not in [%.3f,%.3f]" %
                        (p["fade_seconds"], p["min_fade_seconds"], p["max_fade_seconds"]))
    if p["value_tolerance"] <= 0:
        raise PlanError("VALUE_TOLERANCE_MUST_BE_POSITIVE")
    p["fade_frames"] = int(round(p["fade_seconds"] * EXPECTED_FPS))
    if p["fade_frames"] < 1:
        raise PlanError("FADE_FRAMES_ZERO")
    return p


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def pair_glow_label(label, params):
    prefix = params["bulb_prefix"]
    if not str(label).startswith(prefix):
        return None
    return params["glow_prefix"] + str(label)[len(prefix):]


def make_plan(candidates, params):
    """Pure planner used by live discovery and the offline +/- harness."""
    lo = params["scene_local_switch_frame"] - params["search_radius_frames"]
    hi = params["scene_local_switch_frame"] + params["search_radius_frames"]
    targets, unsupported = [], []
    seen = set()
    for row in candidates:
        switch = int(row["switch_frame"])
        if not lo <= switch <= hi:
            continue
        identity = (row["mechanism"], row.get("visibility_binding_guid"), row.get("target_object_path"),
                    row.get("property"), switch)
        if identity in seen:
            raise PlanError("DUPLICATE_TARGET|%r" % (identity,))
        seen.add(identity)
        if row.get("unsupported"):
            unsupported.append(dict(row))
            continue
        out = dict(row)
        out["fade_frames"] = params["fade_frames"]
        out["fade_start_frame"] = switch - params["fade_frames"]
        if out["fade_start_frame"] < 0:
            raise PlanError("FADE_BEFORE_PLAYBACK|%s" % row.get("light_label"))
        targets.append(out)
    targets.sort(key=lambda r: (r["switch_frame"], r.get("light_label", ""), r["mechanism"]))
    unsupported.sort(key=lambda r: (r["switch_frame"], r.get("light_label", "")))
    if unsupported:
        raise PlanError("UNSUPPORTED_VISIBILITY_TARGETS|%s" %
                        ",".join(r.get("light_label", "?") for r in unsupported))
    if not targets:
        raise PlanError("NO_RIG_LIGHT_SWITCHES_IN_WINDOW|%d..%d" % (lo, hi))
    return {"search_window": [lo, hi], "fade_seconds": params["fade_seconds"],
            "fade_frames": params["fade_frames"], "targets": targets, "unsupported": unsupported}


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return str(value)


def _enum(value):
    return str(getattr(value, "name", value)).split(".")[-1].split(":")[0].strip("<> ")


def _guid(value):
    return _ue().GuidLibrary.conv_guid_to_string(value)


def _rate(value):
    return float(value.numerator) / float(value.denominator)


def _prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:  # noqa: BLE001
        return default


def _stop(run, reason):
    message = "%s_STOP|run=%s|%s" % (TOOL, run, reason)
    try:
        _ue().log_error(message)
    except Exception:  # noqa: BLE001
        pass
    raise Stop(message)


def _log(message):
    try:
        _ue().log(message)
    except Exception:  # noqa: BLE001
        print(message)


def _saved_root():
    ue = _ue()
    return ue.Paths.convert_relative_path_to_full(ue.Paths.project_saved_dir())


def _project_root():
    ue = _ue()
    return ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())


def _here():
    return os.path.join(_saved_root(), "CodexConductor", FOLDER)


def _record_path():
    return os.path.join(_here(), RECORD)


def _plan_path():
    return os.path.join(_here(), PLAN)


def _json_read(path, required=False):
    if not os.path.isfile(path):
        if required:
            raise PlanError("MISSING_FILE|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_write(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    os.replace(temporary, path)


def _asset_file():
    return os.path.join(_project_root(), "Content", *SEQ_PATH[len("/Game/"):].split("/")) + ".uasset"


def _sha(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def _census():
    lib = _ue().EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _preflight(mode, run, confirm):
    ue = _ue()
    if CONFIRMS.get(mode) != str(confirm or "").strip():
        _stop(run, "CONFIRM_MISMATCH|want=%r|got=%r" % (CONFIRMS.get(mode), confirm))
    editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    if ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_CENSUS|%s" % json.dumps(_census(), sort_keys=True))
    if mode in ("DRY", "APPLY") and os.path.isfile(_record_path()):
        _stop(run, "APPLIED_RECORD_EXISTS|%s" % _record_path())
    return editor.get_editor_world()


def _load_sequence(run):
    seq = _ue().load_asset(SEQ_PATH)
    if seq is None:
        _stop(run, "SEQUENCE_LOAD_FAILED|%s" % SEQ_PATH)
    if abs(_rate(seq.get_display_rate()) - EXPECTED_FPS) > 1e-9:
        _stop(run, "DISPLAY_RATE|live=%s|expected=%s" % (_rate(seq.get_display_rate()), EXPECTED_FPS))
    if abs(_rate(seq.get_tick_resolution()) - EXPECTED_TICK) > 1e-9:
        _stop(run, "TICK_RESOLUTION|live=%s|expected=%s" % (_rate(seq.get_tick_resolution()), EXPECTED_TICK))
    return seq


def _section_range(section, seq):
    start = int(section.get_start_frame()) if section.has_start_frame() else int(seq.get_playback_start())
    end = int(section.get_end_frame()) if section.has_end_frame() else int(seq.get_playback_end())
    return [start, end]


def _key_row(key):
    ue = _ue()
    time = key.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
    row = {"frame": int(time.frame_number.value), "sub_frame": float(getattr(time, "sub_frame", 0.0) or 0.0),
           "value": _plain(key.get_value())}
    for field, method in (("interp", "get_interpolation_mode"), ("tangent_mode", "get_tangent_mode"),
                          ("weight_mode", "get_tangent_weight_mode"), ("arrive", "get_arrive_tangent"),
                          ("leave", "get_leave_tangent"), ("arrive_weight", "get_arrive_tangent_weight"),
                          ("leave_weight", "get_leave_tangent_weight")):
        try:
            value = getattr(key, method)()
            row[field] = _enum(value) if "mode" in field or field == "interp" else float(value)
        except Exception:  # noqa: BLE001
            pass
    return row


def _channel_row(channel):
    default = None
    try:
        if not hasattr(channel, "has_default") or channel.has_default():
            default = _plain(channel.get_default())
    except Exception:  # noqa: BLE001
        pass
    return {"name": str(getattr(channel, "channel_name", "")), "default": default,
            "keys": [_key_row(key) for key in channel.get_keys()]}


def _track_row(track, seq):
    prop = path = ""
    try:
        prop, path = str(track.get_property_name()), str(track.get_property_path())
    except Exception:  # noqa: BLE001
        pass
    return {"class": track.get_class().get_name(), "property": prop, "path": path,
            "display_name": str(track.get_display_name()),
            "sections": [{"range": _section_range(section, seq), "active": bool(section.is_active()),
                          "channels": [_channel_row(c) for c in section.get_all_channels()]}
                         for section in track.get_sections()]}


def _snapshot(seq):
    bindings = []
    for binding in seq.get_bindings():
        parent = binding.get_parent()
        rows = [_track_row(track, seq) for track in binding.get_tracks()]
        rows.sort(key=lambda row: (row["class"], row["property"], row["path"], digest(row)))
        bindings.append({"guid": _guid(binding.get_id()), "name": str(binding.get_display_name()),
                         "parent": _guid(parent.get_id()) if parent is not None and parent.is_valid() else "",
                         "tracks": rows})
    bindings.sort(key=lambda row: row["guid"])
    roots = [_track_row(track, seq) for track in seq.get_tracks()]
    roots.sort(key=lambda row: (row["class"], row["property"], row["path"], digest(row)))
    markers = sorted([[str(mark.get_editor_property("label")),
                       int(mark.get_editor_property("frame_number").value)]
                      for mark in seq.get_marked_frames_from_sequence(_ue().MovieSceneTimeUnit.DISPLAY_RATE)])
    return {"display_rate": _rate(seq.get_display_rate()), "tick_resolution": _rate(seq.get_tick_resolution()),
            "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
            "bindings": bindings, "root_tracks": roots, "markers": markers}


def _binding_map(seq):
    return {_guid(binding.get_id()): binding for binding in seq.get_bindings()}


def _actors_by_label():
    ue = _ue()
    rows = {}
    for actor in ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors():
        rows.setdefault(str(actor.get_actor_label()), []).append(actor)
    return rows


def _object_path(obj):
    try:
        return str(obj.get_path_name())
    except Exception:  # noqa: BLE001
        return str(obj)


def _bound_objects(seq, binding, world):
    try:
        return list(seq.locate_bound_objects(binding, world))
    except Exception:  # noqa: BLE001
        return []


def _actor_for_binding(seq, binding, world, actors, run):
    objects = [obj for obj in _bound_objects(seq, binding, world) if hasattr(obj, "get_actor_label")]
    if len(objects) == 1:
        return objects[0]
    name = str(binding.get_display_name())
    labels = [name]
    for prefix in ("Klara Hookin - Ours Off: ", "Klara Reveal - Hide: "):
        if name.startswith(prefix):
            labels.append(name[len(prefix):])
    matches = []
    for label in labels:
        matches.extend(actors.get(label, []))
    unique = {_object_path(actor): actor for actor in matches}
    if len(unique) != 1:
        _stop(run, "ACTOR_RESOLVE|binding=%s|matches=%d" % (name, len(unique)))
    return list(unique.values())[0]


def _light_or_fog(actor):
    ue = _ue()
    component = actor.get_component_by_class(ue.LightComponentBase)
    if component is not None:
        return component, "Intensity", "intensity", "light"
    component = actor.get_component_by_class(ue.ExponentialHeightFogComponent)
    if component is not None:
        return component, "FogDensity", "fog_density", "fog"
    return None


def _find_binding_for_object(seq, obj, world):
    path = _object_path(obj)
    found = []
    for binding in seq.get_bindings():
        if any(_object_path(bound) == path for bound in _bound_objects(seq, binding, world)):
            found.append(binding)
    if len(found) > 1:
        raise PlanError("OBJECT_MULTIBOUND|%s|%d" % (path, len(found)))
    return found[0] if found else None


def _track_property(track):
    try:
        return str(track.get_property_name()), str(track.get_property_path())
    except Exception:  # noqa: BLE001
        return "", ""


def _evaluate(seq, channel, frame, run, label):
    values = list(channel.evaluate_keys(seq.make_range(int(frame), 1), seq.get_display_rate()))
    if len(values) != 1:
        _stop(run, "EVALUATE_COUNT|%s|frame=%d|got=%d" % (label, frame, len(values)))
    return float(values[0])


def _candidate_from_actor(seq, visibility_binding, actor, switch, world, actors, params, run):
    label = str(actor.get_actor_label())
    pair = pair_glow_label(label, params)
    target_actor = actor
    mechanism = "visibility"
    proxy = None
    if pair is not None:
        matches = actors.get(pair, [])
        if len(matches) != 1:
            return {"mechanism": "visibility", "switch_frame": switch, "light_label": label,
                    "visibility_binding_guid": _guid(visibility_binding.get_id()), "unsupported": True,
                    "reason": "PAIRED_GLOW_COUNT_%d|%s" % (len(matches), pair)}
        target_actor, mechanism, proxy = matches[0], "visibility_paired_glow", pair
    found = _light_or_fog(target_actor)
    if found is None:
        return {"mechanism": "visibility", "switch_frame": switch, "light_label": label,
                "visibility_binding_guid": _guid(visibility_binding.get_id()), "unsupported": True,
                "reason": "NO_INTENSITY_OR_FOG_PROPERTY"}
    component, prop_name, editor_prop, kind = found
    target_actor_binding = _find_binding_for_object(seq, target_actor, world)
    if target_actor_binding is None:
        return {"mechanism": mechanism, "switch_frame": switch, "light_label": label,
                "visibility_binding_guid": _guid(visibility_binding.get_id()), "unsupported": True,
                "reason": "TARGET_ACTOR_NOT_BOUND|%s" % target_actor.get_actor_label()}
    target_binding = _find_binding_for_object(seq, component, world)
    if target_binding is not None:
        conflicts = [track for track in target_binding.get_tracks()
                     if track.get_class().get_name() == "MovieSceneFloatTrack" and _track_property(track)[0] == prop_name]
        if conflicts:
            return {"mechanism": mechanism, "switch_frame": switch, "light_label": label,
                    "visibility_binding_guid": _guid(visibility_binding.get_id()), "unsupported": True,
                    "reason": "EXISTING_PROPERTY_TRACK|%s|count=%d" % (prop_name, len(conflicts))}
    base = float(_prop(component, editor_prop))
    return {"mechanism": mechanism, "switch_frame": switch, "light_label": label,
            "proxy_light_label": proxy, "kind": kind, "property": prop_name,
            "editor_property": editor_prop, "base_value": base,
            "visibility_binding_guid": _guid(visibility_binding.get_id()),
            "target_object_path": _object_path(component),
            "target_actor_label": str(target_actor.get_actor_label()),
            "target_actor_binding_guid": _guid(target_actor_binding.get_id()),
            "target_binding_guid": _guid(target_binding.get_id()) if target_binding is not None else None,
            "unsupported": False}


def _discover(seq, world, params, run):
    actors = _actors_by_label()
    candidates = []
    lo = params["scene_local_switch_frame"] - params["search_radius_frames"]
    hi = params["scene_local_switch_frame"] + params["search_radius_frames"]
    for binding in seq.get_bindings():
        for track in binding.get_tracks():
            if track.get_class().get_name() != "MovieSceneVisibilityTrack":
                continue
            prop, path = _track_property(track)
            if (prop, path) != ("bHidden", "bHidden"):
                _stop(run, "VISIBILITY_TRACK_BINDING|%s|want=(bHidden,bHidden)|got=(%s,%s)" %
                      (binding.get_display_name(), prop, path))
            for section in track.get_sections():
                channels = list(section.get_all_channels())
                if not section.is_active() or len(channels) != 1:
                    continue
                switch = _section_range(section, seq)[0]
                if not lo <= switch <= hi:
                    continue
                visible = bool(_evaluate(seq, channels[0], switch, run, str(binding.get_display_name())))
                if visible:  # This is a show step, not an off step.
                    continue
                actor = _actor_for_binding(seq, binding, world, actors, run)
                candidates.append(_candidate_from_actor(seq, binding, actor, switch, world, actors, params, run))
    # Existing one-frame intensity/fog drops are supported too.  Long authored
    # curves are not silently rewritten.
    used_paths = {row.get("target_object_path") for row in candidates if not row.get("unsupported")}
    for binding in seq.get_bindings():
        objects = _bound_objects(seq, binding, world)
        object_path = _object_path(objects[0]) if len(objects) == 1 else None
        if object_path in used_paths:
            continue
        for track in binding.get_tracks():
            prop, _path_value = _track_property(track)
            if track.get_class().get_name() != "MovieSceneFloatTrack" or prop not in ("Intensity", "FogDensity"):
                continue
            sections = list(track.get_sections())
            if len(sections) != 1 or len(list(sections[0].get_all_channels())) != 1:
                continue
            keys = list(list(sections[0].get_all_channels())[0].get_keys())
            rows = [_key_row(key) for key in keys]
            for index in range(1, len(rows)):
                prev, current = rows[index - 1], rows[index]
                if (lo <= current["frame"] <= hi and abs(float(current["value"])) <= params["value_tolerance"]
                        and abs(float(prev["value"])) > params["value_tolerance"]
                        and current["frame"] - prev["frame"] <= 1):
                    candidates.append({"mechanism": "intensity_step", "switch_frame": current["frame"],
                                       "light_label": str(binding.get_display_name()), "kind": "property",
                                       "property": prop, "base_value": float(prev["value"]),
                                       "target_object_path": object_path, "target_actor_label": "",
                                       "target_binding_guid": _guid(binding.get_id()),
                                       "key_index": index - 1, "original_key": prev, "unsupported": False})
    return make_plan(candidates, params)


def _backup(run, suffix=""):
    source = _asset_file()
    if not os.path.isfile(source):
        _stop(run, "BACKUP_SOURCE_MISSING|%s" % source)
    root = os.path.join(_project_root(), "Backups", "PreS1RigFade%s-%s" % (suffix, run))
    os.makedirs(root, exist_ok=False)
    target = os.path.join(root, os.path.basename(source))
    shutil.copy2(source, target)
    if os.path.getsize(source) != os.path.getsize(target) or _sha(source) != _sha(target):
        _stop(run, "BACKUP_VERIFY_FAILED|%s" % SEQ_PATH)
    return {"root": root, "files": [{"package": SEQ_PATH, "source": source, "backup": target,
                                       "bytes": os.path.getsize(target), "sha256": _sha(target)}]}


def _component_for_plan(plan, actors, run):
    matches = actors.get(plan["target_actor_label"], [])
    if len(matches) != 1:
        _stop(run, "TARGET_ACTOR_COUNT|%s|%d" % (plan["target_actor_label"], len(matches)))
    found = _light_or_fog(matches[0])
    if found is None or found[1] != plan["property"]:
        _stop(run, "TARGET_PROPERTY_GONE|%s|%s" % (plan["target_actor_label"], plan["property"]))
    if _object_path(found[0]) != plan["target_object_path"]:
        _stop(run, "TARGET_OBJECT_CHANGED|%s" % plan["light_label"])
    return found[0]


def _bind_component(seq, component, actor_binding_guid, world, run):
    existing = _find_binding_for_object(seq, component, world)
    if existing is not None:
        return existing, False, False
    before = {_guid(binding.get_id()) for binding in seq.get_bindings()}
    binding = seq.add_possessable(component)
    guid = _guid(binding.get_id())
    returned_existing = guid in before
    if returned_existing:  # Rule 9: do not rename or reparent an existing binding.
        return binding, False, True
    parents = [row for row in seq.get_bindings() if _guid(row.get_id()) == actor_binding_guid]
    if len(parents) == 1:
        binding.set_parent(parents[0])
    binding.set_display_name("S1 Rig Fade: " + str(component.get_name()))
    return binding, True, False


def _write_ramp(seq, binding, plan, run):
    ue = _ue()
    conflicts = [track for track in binding.get_tracks()
                 if track.get_class().get_name() == "MovieSceneFloatTrack"
                 and _track_property(track)[0] == plan["property"]]
    if conflicts:
        _stop(run, "PROPERTY_TRACK_ALREADY_EXISTS|%s|%s|%d" %
              (plan["light_label"], plan["property"], len(conflicts)))
    track = binding.add_track(ue.MovieSceneFloatTrack)
    track.set_property_name_and_path(plan["property"], plan["property"])
    track.set_display_name("S1 Rig Fade - " + plan["property"])
    section = track.add_section()
    section.set_range(int(plan["fade_start_frame"]), int(plan["switch_frame"]) + 1)
    section.set_completion_mode(ue.MovieSceneCompletionMode.RESTORE_STATE)
    channels = list(section.get_all_channels())
    if len(channels) != 1:
        _stop(run, "RAMP_CHANNEL_COUNT|%s|%d" % (plan["light_label"], len(channels)))
    channel = channels[0]
    linear = ue.MovieSceneKeyInterpolation.LINEAR
    channel.add_key(ue.FrameNumber(int(plan["fade_start_frame"])), float(plan["base_value"]),
                    time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=linear)
    channel.add_key(ue.FrameNumber(int(plan["switch_frame"])), 0.0,
                    time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=linear)
    start = _evaluate(seq, channel, plan["fade_start_frame"], run, plan["light_label"])
    end = _evaluate(seq, channel, plan["switch_frame"], run, plan["light_label"])
    if abs(start - float(plan["base_value"])) > 0.0001 or abs(end) > 0.0001:
        _stop(run, "RAMP_READBACK|%s|start=%s|end=%s" % (plan["light_label"], start, end))
    return track


def _retime_step(seq, binding, plan, run):
    ue = _ue()
    tracks = [track for track in binding.get_tracks() if track.get_class().get_name() == "MovieSceneFloatTrack"
              and _track_property(track)[0] == plan["property"]]
    if len(tracks) != 1:
        _stop(run, "STEP_TRACK_COUNT|%s|%d" % (plan["light_label"], len(tracks)))
    sections = list(tracks[0].get_sections())
    if len(sections) != 1 or len(list(sections[0].get_all_channels())) != 1:
        _stop(run, "STEP_SECTION_CHANNEL|%s" % plan["light_label"])
    channel = list(sections[0].get_all_channels())[0]
    keys = list(channel.get_keys())
    index = int(plan["key_index"])
    if index >= len(keys) or _key_row(keys[index]) != plan["original_key"]:
        _stop(run, "STEP_KEY_DRIFT|%s" % plan["light_label"])
    keys[index].set_time(ue.FrameNumber(int(plan["fade_start_frame"])), 0.0,
                         ue.MovieSceneTimeUnit.DISPLAY_RATE)
    keys[index].set_interpolation_mode(ue.RichCurveInterpMode.RCIM_LINEAR)
    start = _evaluate(seq, channel, plan["fade_start_frame"], run, plan["light_label"])
    end = _evaluate(seq, channel, plan["switch_frame"], run, plan["light_label"])
    if abs(start - float(plan["base_value"])) > 0.0001 or abs(end) > 0.0001:
        _stop(run, "STEP_RAMP_READBACK|%s|start=%s|end=%s" % (plan["light_label"], start, end))
    return tracks[0]


def _save(run):
    expected = {"content": [SEQ_PATH], "maps": []}
    if _census() != expected:
        _stop(run, "UNEXPECTED_DIRTY_PACKAGES|live=%s|expected=%s|NOTHING SAVED; Don't-Save restart" %
              (json.dumps(_census(), sort_keys=True), json.dumps(expected, sort_keys=True)))
    if not bool(_ue().EditorAssetLibrary.save_asset(SEQ_PATH, only_if_is_dirty=True)):
        _stop(run, "SAVE_FAILED|%s" % SEQ_PATH)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census(), sort_keys=True))
    return [SEQ_PATH]


def _print_targets(run, plan):
    for row in plan["targets"]:
        _log("%s_TARGET|run=%s|light=%s|switch_frame=%d|mechanism=%s|property=%s|fade=%d..%d|proxy=%s" %
             (TOOL, run, row["light_label"], row["switch_frame"], row["mechanism"], row["property"],
              row["fade_start_frame"], row["switch_frame"], row.get("proxy_light_label") or "-"))


def _assert_scoped_change(before, after, operations):
    """Require the post-edit snapshot to equal before plus only recorded ops."""
    for key in ("display_rate", "tick_resolution", "playback", "root_tracks", "markers"):
        if before[key] != after[key]:
            raise PlanError("UNTOUCHED_CHANGED|%s" % key)
    before_map = {row["guid"]: row for row in before["bindings"]}
    after_map = {row["guid"]: row for row in after["bindings"]}
    created = {op["binding_guid"] for op in operations if op.get("binding_created")}
    if set(after_map) - set(before_map) != created or set(before_map) - set(after_map):
        raise PlanError("BINDING_SET_CHANGED|added=%r|removed=%r|expected_added=%r" %
                        (sorted(set(after_map) - set(before_map)), sorted(set(before_map) - set(after_map)),
                         sorted(created)))
    by_guid = {}
    for op in operations:
        by_guid.setdefault(op["binding_guid"], []).append(op)
    for guid, old in before_map.items():
        new = after_map[guid]
        if (old["name"], old["parent"]) != (new["name"], new["parent"]):
            raise PlanError("BINDING_METADATA_CHANGED|%s" % guid)
        expected = list(old["tracks"])
        for op in by_guid.get(guid, []):
            if op["kind"] == "new_track":
                expected.append(op["track_after"])
            else:
                try:
                    expected.remove(op["track_before"])
                except ValueError as error:
                    raise PlanError("RETIMED_TRACK_NOT_IN_BEFORE|%s" % guid) from error
                expected.append(op["track_after"])
        expected.sort(key=lambda row: (row["class"], row["property"], row["path"], digest(row)))
        if expected != new["tracks"]:
            raise PlanError("UNSCOPED_TRACK_CHANGE|%s|%s" % (guid, new["name"]))
    for guid in created:
        new = after_map[guid]
        ops = by_guid.get(guid, [])
        expected = [op["track_after"] for op in ops]
        expected.sort(key=lambda row: (row["class"], row["property"], row["path"], digest(row)))
        if new["tracks"] != expected:
            raise PlanError("CREATED_BINDING_TRACKS|%s" % guid)


def _report(seq, world, params, run):
    before = _snapshot(seq)
    plan = _discover(seq, world, params, run)
    return {"schema_version": 1, "tool_version": TOOL_VERSION, "tool": TOOL, "run": run, "mode": "DRY",
            "sequence": SEQ_PATH, "params": params, "plan": plan, "plan_digest": digest(plan),
            "snapshot": before, "snapshot_digest": digest(before), "census": _census(), "claims": CLAIMS,
            "apply_ready": True}


def run_dry(run, params, confirm):
    world = _preflight("DRY", run, confirm)
    report = _report(_load_sequence(run), world, params, run)
    path = os.path.join(_here(), "s1_rig_fade_dry_%s.json" % run)
    _json_write(path, report)
    _json_write(_plan_path(), {"run": run, "report": path, "plan_digest": report["plan_digest"],
                               "snapshot_digest": report["snapshot_digest"], "params": params})
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % json.dumps(_census(), sort_keys=True))
    _print_targets(run, report["plan"])
    _log("%s_DRY_OK|run=%s|mutated=0|apply_ready=1|targets=%d|frames=%s|fade_frames=%d|report=%s" %
         (TOOL, run, len(report["plan"]["targets"]), report["plan"]["search_window"],
          report["plan"]["fade_frames"], path))
    return report


def _require_dry(report, run):
    state = _json_read(_plan_path(), required=True)
    if state.get("plan_digest") != report["plan_digest"] or state.get("snapshot_digest") != report["snapshot_digest"]:
        _stop(run, "CHANGED_SINCE_DRY|rerun DRY")


def run_apply(run, params, confirm):
    world = _preflight("APPLY", run, confirm)
    seq = _load_sequence(run)
    report = _report(seq, world, params, run)
    _require_dry(report, run)
    backup = _backup(run)
    transaction = os.path.join(_here(), "s1_rig_fade_transaction_%s.json" % run)
    record = {"schema_version": 1, "tool_version": TOOL_VERSION, "tool": TOOL, "run": run,
              "applied": False, "written_before_mutation": True, "sequence": SEQ_PATH,
              "params": params, "plan": report["plan"], "snapshot_before": report["snapshot"],
              "snapshot_before_digest": report["snapshot_digest"], "backup": backup, "operations": []}
    _json_write(transaction, record)
    bindings = _binding_map(seq)
    actors = _actors_by_label()
    for row in report["plan"]["targets"]:
        if row["mechanism"] == "intensity_step":
            binding = bindings.get(row["target_binding_guid"])
            if binding is None:
                _stop(run, "TARGET_BINDING_GONE|%s" % row["light_label"])
            before_tracks = [track for track in binding.get_tracks()
                             if track.get_class().get_name() == "MovieSceneFloatTrack"
                             and _track_property(track)[0] == row["property"]]
            if len(before_tracks) != 1:
                _stop(run, "STEP_TRACK_COUNT|%s|%d" % (row["light_label"], len(before_tracks)))
            track_before = _track_row(before_tracks[0], seq)
            track = _retime_step(seq, binding, row, run)
            record["operations"].append({"kind": "retime", "binding_guid": row["target_binding_guid"],
                                         "property": row["property"], "track_before": track_before,
                                         "track_after": _track_row(track, seq),
                                         "original_key": row["original_key"], "key_index": row["key_index"]})
            _json_write(transaction, record)
            continue
        component = _component_for_plan(row, actors, run)
        binding, created, returned_existing = _bind_component(
            seq, component, row["target_actor_binding_guid"], world, run)
        track = _write_ramp(seq, binding, row, run)
        record["operations"].append({"kind": "new_track", "binding_guid": _guid(binding.get_id()),
                                     "binding_created": created, "add_returned_existing": returned_existing,
                                     "property": row["property"], "track_after": _track_row(track, seq),
                                     "target_object_path": row["target_object_path"]})
        _json_write(transaction, record)
    after = _snapshot(seq)
    _assert_scoped_change(report["snapshot"], after, record["operations"])
    record["snapshot_after"] = after
    record["snapshot_after_digest"] = digest(after)
    record["applied"] = True
    _json_write(transaction, record)
    saves = _save(run)
    readback = _snapshot(_load_sequence(run))
    if readback != after:
        _stop(run, "POSTSAVE_READBACK_MISMATCH|restore=%s" % backup["root"])
    record.update({"saves": saves, "census_after": _census(), "saved_readback": readback,
                   "saved_readback_digest": digest(readback)})
    _json_write(_record_path(), record)
    _json_write(transaction, dict(record, transaction_complete=True))
    _print_targets(run, report["plan"])
    _log("%s_APPLY_OK|run=%s|targets=%d|saved=%s|backup=%s|record=%s|readback=%s" %
         (TOOL, run, len(report["plan"]["targets"]), ",".join(saves), backup["root"], _record_path(),
          record["saved_readback_digest"][:16]))
    return record


def _find_track(binding, spec, seq, run):
    rows = [track for track in binding.get_tracks() if _track_row(track, seq) == spec]
    if len(rows) != 1:
        _stop(run, "RECORDED_TRACK_COUNT|binding=%s|property=%s|count=%d" %
              (binding.get_display_name(), spec.get("property"), len(rows)))
    return rows[0]


def _restore_key(track, op, run):
    ue = _ue()
    sections = list(track.get_sections())
    channel = list(sections[0].get_all_channels())[0]
    keys = list(channel.get_keys())
    index = int(op["key_index"])
    original = op["original_key"]
    if index >= len(keys):
        _stop(run, "REVERT_KEY_INDEX|%s" % op["property"])
    keys[index].set_time(ue.FrameNumber(int(original["frame"])), float(original.get("sub_frame", 0.0)),
                         ue.MovieSceneTimeUnit.DISPLAY_RATE)
    if original.get("interp"):
        keys[index].set_interpolation_mode(getattr(ue.RichCurveInterpMode, original["interp"]))


def run_revert(run, params, confirm):
    del params
    _preflight("REVERT", run, confirm)
    record = _json_read(_record_path(), required=True)
    if not record.get("applied") or record.get("sequence") != SEQ_PATH:
        _stop(run, "REVERT_RECORD_CONTEXT")
    seq = _load_sequence(run)
    live = _snapshot(seq)
    if digest(live) != record.get("snapshot_after_digest"):
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|live=%s|recorded=%s" %
              (digest(live), record.get("snapshot_after_digest")))
    backup = _backup(run, "Revert")
    transaction = os.path.join(_here(), "s1_rig_fade_revert_transaction_%s.json" % run)
    _json_write(transaction, {"tool": TOOL, "run": run, "written_before_mutation": True,
                              "backup": backup, "record": _record_path(), "snapshot_before": live})
    for op in reversed(record["operations"]):
        bindings = _binding_map(seq)
        binding = bindings.get(op["binding_guid"])
        if binding is None:
            _stop(run, "REVERT_BINDING_GONE|%s" % op["binding_guid"])
        track = _find_track(binding, op["track_after"], seq, run)
        if op["kind"] == "retime":
            _restore_key(track, op, run)
        else:
            binding.remove_track(track)  # return is unreliable; exact snapshot below is authority
            if op["binding_created"]:
                if list(binding.get_tracks()):
                    _stop(run, "REFUSE_REMOVE_NONEMPTY_BINDING|%s" % op["binding_guid"])
                binding.remove()
    restored = _snapshot(seq)
    if restored != record["snapshot_before"]:
        _stop(run, "REVERT_PRESAVE_NOT_EXACT|restore=%s" % backup["root"])
    saves = _save(run)
    readback = _snapshot(_load_sequence(run))
    if readback != record["snapshot_before"] or _census() != {"content": [], "maps": []}:
        _stop(run, "REVERT_POSTSAVE_READBACK|restore=%s" % backup["root"])
    archived = _record_path() + ".reverted-" + run
    os.replace(_record_path(), archived)
    _json_write(transaction, {"tool": TOOL, "run": run, "transaction_complete": True, "backup": backup,
                              "archived_record": archived, "saves": saves, "readback_digest": digest(readback)})
    _log("%s_REVERT_OK|run=%s|targets=%d|saved=%s|backup=%s|record=%s|readback=%s" %
         (TOOL, run, len(record["operations"]), ",".join(saves), backup["root"], archived,
          digest(readback)[:16]))
    return {"backup": backup, "archived_record": archived, "saves": saves}


def main(args):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or datetime.datetime.now().strftime("S1RIGFADE-%Y%m%d-%H%M%S"))
    try:
        params = merged_params(args.get("params") or {})
        function = {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}.get(mode)
        if function is None:
            _stop(run, "MODE|%r" % mode)
        return function(run, params, args.get("confirm"))
    except PlanError as error:
        _stop(run, "PLAN_REFUSED|%s" % error)
