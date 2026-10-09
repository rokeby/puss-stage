"""I2 hangar hold camera authoring tool (P27, 9 Oct 2026).

Offline-authored: do not import ``unreal`` at module scope.  The conductor runs
the runner later in the already-open PussStage editor.

Modes and confirms:
  DRY     / ``DRY I2HANGARCAM``
  APPLY   / ``APPLY I2HANGARCAM``
  REVERT  / ``REVERT I2HANGARCAM``

APPLY creates one unattached, tagged CineCameraActor in the current level and
re-points only the active hangar-side camera-cut section(s) covering [0, 1250).
REVERT restores those binding IDs, removes only a binding created by this tool,
and destroys only the tagged actor.  Both write a record and copy the map plus
I2 Level Sequence to Backups/ before mutating anything.

Evidence tiers used by this source:
  declaration-proven: paths, labels, expected rates/ranges, API contracts and
    Gary's framing defaults are in Docs/Conductor/codex_briefs/
    p27_i2_hangar_hold_camera.md:1-33.
  measured: the source evidence named by that brief reports I2 at 25 fps,
    playback [0,2226), a live cut at 1250, and the successful free-camera pose.
    Those evidence files are intentionally read again by DRY where available;
    this offline checkout does not claim to have re-measured Unreal.
  inferred: a free, unattached level camera removes the old camera's inherited
    attach-parent transform.  Rendered acceptance remains Gary's.
"""

import datetime
import hashlib
import json
import math
import os
import shutil


TOOL = "I2_HANGAR_CAM"
TOOL_VERSION = "2026-10-09a"
FOLDER = "I2HangarCam_20261009"
MAP_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ_PATH = "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips"
OLD_CAMERA = "S2 Sleight Hangar Camera"
MOUTH_CAMERA = "I2 Sleight Mouth Camera"
ACTOR_LABEL = "I2 Hangar Hold Camera"
ACTOR_TAG = "I2HangarHoldCamera"
EXPECTED_FPS = 25.0
EXPECTED_TICK = 24000.0
EXPECTED_PLAYBACK = [0, 2226]
EXPECTED_SLEIGHT = 1250
RECORD = "i2_hangar_cam_record.json"
PLAN = "i2_hangar_cam_plan.json"
CURTAIN_RECORD_REL = os.path.join("CodexConductor", "curtain_sleight_record_I2.json")
I2_ORDER_RECORD_REL = os.path.join("CodexConductor", "I2Order_20261008", "i2_order_record.json")
CONFIRMS = {
    "DRY": "DRY I2HANGARCAM",
    "APPLY": "APPLY I2HANGARCAM",
    "REVERT": "REVERT I2HANGARCAM",
}
ORDER_PREFIXES = ("I2 Order Dark:", "I2 Order Exposure:")
SPOT_LABELS = ("Shadow Play Spot (Hangar)", "Shadow Play Spot (Mouth)")
GOBO_PROPS = (
    "attenuation_radius", "cast_shadows", "disabled_brightness",
    "inner_cone_angle", "intensity", "intensity_units",
    "light_function_fade_distance", "light_function_material",
    "outer_cone_angle", "soft_source_radius", "source_length", "source_radius",
)

DEFAULTS = {
    "location_cm": [13393.0, 78777.0, 510.0],
    "rotation_deg": {"pitch": 0.0, "yaw": -43.57, "roll": 0.0},
    "horizontal_fov_deg": 50.0,
    "sensor_width_mm": 36.0,
    "sensor_height_mm": 20.25,
    "focus_distance_cm": 3000.0,
    "derive_focus_from_curtain_record": True,
    "fov_tolerance_deg": 0.001,
    "location_tolerance_cm": 0.01,
    "rotation_tolerance_deg": 0.001,
}

CLAIMS = [
    {
        "tier": "declaration-proven",
        "claim": "The only save targets are the vertical-slice map and LS_Interaction_02_Turnips.",
        "cite": "Docs/Conductor/codex_briefs/p27_i2_hangar_hold_camera.md:20-29",
    },
    {
        "tier": "measured",
        "claim": "The requested free-camera framing is (13393,78777,510), yaw -43.57, pitch 0, HFOV 50.",
        "cite": "Docs/Conductor/codex_briefs/p27_i2_hangar_hold_camera.md:17",
    },
    {
        "tier": "inferred",
        "claim": "An unattached camera avoids the inherited sunk/tipped S2 hangar-root transform.",
        "cite": "Docs/Conductor/codex_briefs/p27_i2_hangar_hold_camera.md:16-17",
    },
]


class Stop(RuntimeError):
    pass


class PlanError(ValueError):
    pass


def _ue():
    import unreal  # noqa: WPS433 - local by design; system-Python import stays offline
    return unreal


def merged_params(raw):
    p = dict(DEFAULTS)
    p.update(raw or {})
    p["location_cm"] = [float(v) for v in p["location_cm"]]
    if len(p["location_cm"]) != 3:
        raise PlanError("LOCATION_NEEDS_3_VALUES")
    rot = dict(DEFAULTS["rotation_deg"])
    rot.update(p.get("rotation_deg") or {})
    p["rotation_deg"] = {k: float(rot[k]) for k in ("pitch", "yaw", "roll")}
    for key in ("horizontal_fov_deg", "sensor_width_mm", "sensor_height_mm", "focus_distance_cm",
                "fov_tolerance_deg", "location_tolerance_cm", "rotation_tolerance_deg"):
        p[key] = float(p[key])
    if not (1.0 < p["horizontal_fov_deg"] < 170.0):
        raise PlanError("HFOV_RANGE")
    if p["sensor_width_mm"] <= 0 or p["sensor_height_mm"] <= 0 or p["focus_distance_cm"] <= 0:
        raise PlanError("LENS_VALUES_MUST_BE_POSITIVE")
    p["derive_focus_from_curtain_record"] = bool(p["derive_focus_from_curtain_record"])
    return p


def digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def focal_for_hfov(sensor_width_mm, hfov_deg):
    return float(sensor_width_mm) / (2.0 * math.tan(math.radians(float(hfov_deg)) / 2.0))


def hfov_for_focal(sensor_width_mm, focal_mm):
    return math.degrees(2.0 * math.atan(float(sensor_width_mm) / (2.0 * float(focal_mm))))


def _distance(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _world_from_yaw(frame, local):
    yaw = math.radians(float(frame.get("yaw", 0.0)))
    x, y, z = [float(v) for v in local]
    loc = [float(v) for v in frame["loc"]]
    return [loc[0] + x * math.cos(yaw) - y * math.sin(yaw),
            loc[1] + x * math.sin(yaw) + y * math.cos(yaw), loc[2] + z]


def focus_from_curtain_record(record, camera_location, default_cm):
    """Return (distance, source, point).  Uses only explicit record geometry.

    The Curtain Sleight record stores the drape world frame and the camera's
    eye-height relative to that drape.  That eye-height point is the authored
    look centre used by curtain_sleight diagnostics; it is preferable to the
    raw drape origin.  If those fields are absent, preserve Gary's args default.
    """
    try:
        plan = record["plan"]
        frame = plan["frames_of_reference"]["hangar_drape_world"]
        eye_z = float(plan["cam_rel_drape"]["loc"][2])
        point = _world_from_yaw(frame, [0.0, 0.0, eye_z])
        distance = _distance(camera_location, point)
        if distance > 1.0:
            return distance, "curtain_record:plan.frames_of_reference.hangar_drape_world+cam_rel_drape.eye_z", point
    except (KeyError, TypeError, ValueError, IndexError):
        pass
    return float(default_cm), "args.focus_distance_cm (curtain centre not derivable)", None


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return str(value)


def _enum_name(value):
    return str(getattr(value, "name", value)).split(".")[-1].split(":")[0].strip("<> ")


def _path(value):
    if value is None:
        return None
    try:
        return value.get_path_name().split(".")[0]
    except Exception:  # noqa: BLE001
        return str(value)


def _prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:  # noqa: BLE001
        return default


def _guid(value):
    return _ue().GuidLibrary.conv_guid_to_string(value)


def _rate(value):
    return float(value.numerator) / float(value.denominator)


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


def _asset_file(path):
    ext = ".umap" if path == MAP_PATH else ".uasset"
    return os.path.join(_project_root(), "Content", *path[len("/Game/"):].split("/")) + ext


def _json_read(path, required=False):
    if not os.path.isfile(path):
        if required:
            raise PlanError("MISSING_FILE|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_write(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False, default=str)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _log(message):
    _ue().log(message)


def _stop(run, reason):
    message = "%s_STOPPED|run=%s|reason=%s" % (TOOL, run, reason)
    _ue().log_error(message)
    raise Stop(message)


def _census():
    lib = _ue().EditorLoadingAndSavingUtils
    return {
        "content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
        "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages()),
    }


def _actors():
    ue = _ue()
    return list(ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors())


def _actor_tags(actor):
    return sorted(str(v) for v in (_prop(actor, "tags", []) or []))


def _ours_actors():
    return [a for a in _actors() if str(a.get_actor_label()) == ACTOR_LABEL or ACTOR_TAG in _actor_tags(a)]


def _world_path(world):
    try:
        return str(world.get_outermost().get_name())
    except Exception:  # noqa: BLE001
        return world.get_path_name().split(".")[0]


def _preflight(mode, run, confirm):
    ue = _ue()
    if CONFIRMS.get(mode) != str(confirm or "").strip():
        _stop(run, "CONFIRM_MISMATCH|want=%r|got=%r" % (CONFIRMS.get(mode), confirm))
    editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or _world_path(world) != MAP_PATH:
        _stop(run, "WRONG_WORLD|%s" % (_world_path(world) if world else None))
    if ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")
    census = _census()
    if census != {"content": [], "maps": []}:
        _stop(run, "DIRTY_CENSUS|%s" % json.dumps(census, sort_keys=True))
    if any(str(actor.get_actor_label()).startswith("ZZ_") for actor in _actors()):
        _stop(run, "ZZ_ACTORS_PRESENT")
    ours = _ours_actors()
    if mode in ("DRY", "APPLY") and ours:
        _stop(run, "EXISTING_I2_HANGAR_HOLD_CAMERA|count=%d" % len(ours))
    return world


def _channel_row(channel):
    ue = _ue()
    keys = []
    for key in channel.get_keys():
        time = key.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
        frame = int(time.frame_number.value)
        sub = float(getattr(time, "sub_frame", 0.0) or 0.0)
        keys.append([frame if abs(sub) < 1.0e-7 else frame + sub, _plain(key.get_value())])
    default = None
    try:
        if not hasattr(channel, "has_default") or channel.has_default():
            default = _plain(channel.get_default())
    except Exception:  # noqa: BLE001
        pass
    return {"name": str(getattr(channel, "channel_name", "")), "default": default, "keys": keys}


def _section_range(section, seq):
    start = int(section.get_start_frame()) if section.has_start_frame() else int(seq.get_playback_start())
    end = int(section.get_end_frame()) if section.has_end_frame() else int(seq.get_playback_end())
    return [start, end]


def _track_row(track, seq):
    cls = track.get_class().get_name()
    prop = path = ""
    try:
        prop, path = str(track.get_property_name()), str(track.get_property_path())
    except Exception:  # noqa: BLE001
        pass
    sections = []
    for section in track.get_sections():
        completion = None
        try:
            completion = _enum_name(section.get_completion_mode())
        except Exception:  # noqa: BLE001
            pass
        sections.append({
            "range": _section_range(section, seq),
            "active": bool(section.is_active()),
            "completion": completion,
            "channels": [_channel_row(c) for c in section.get_all_channels()],
        })
    row = {"class": cls, "property": prop, "path": path,
           "display_name": str(track.get_display_name()), "sections": sections}
    if cls == "MovieSceneMaterialParameterCollectionTrack":
        row["mpc"] = _path(_prop(track, "mpc"))
    return row


def _track_identity(row):
    """UE-generated display names are not identity; class + property/path are."""
    return (row["class"], row.get("property", ""), row.get("path", ""))


def _template_props(binding):
    template = binding.get_object_template()
    if template is None:
        return None
    component = _prop(template, "spot_light_component")
    if component is None:
        try:
            component = template.get_component_by_class(_ue().SpotLightComponent)
        except Exception:  # noqa: BLE001
            component = None
    if component is None:
        return None
    out = {}
    for name in GOBO_PROPS:
        value = _prop(component, name)
        out[name] = _path(value) if name == "light_function_material" else (
            _enum_name(value) if name == "intensity_units" else _plain(value))
    return out


def _snapshot(seq):
    ue = _ue()
    bindings = []
    for binding in seq.get_bindings():
        parent = binding.get_parent()
        name = str(binding.get_display_name())
        tracks = [_track_row(track, seq) for track in binding.get_tracks()]
        tracks.sort(key=lambda row: (_track_identity(row), row["display_name"], digest(row)))
        bindings.append({
            "guid": _guid(binding.get_id()), "name": name,
            "parent": _guid(parent.get_id()) if parent is not None and parent.is_valid() else "",
            "tracks": tracks,
            "template": _template_props(binding) if name in SPOT_LABELS else None,
        })
    bindings.sort(key=lambda row: (row["guid"], row["name"]))
    cut_tracks = list(seq.find_tracks_by_type(ue.MovieSceneCameraCutTrack))
    cuts = []
    for track_index, track in enumerate(cut_tracks):
        for section_index, section in enumerate(track.get_sections()):
            binding_id = section.get_camera_binding_id()
            completion = None
            try:
                completion = _enum_name(section.get_completion_mode())
            except Exception:  # noqa: BLE001
                pass
            cuts.append({
                "track_index": track_index, "section_index": section_index,
                "range": _section_range(section, seq), "active": bool(section.is_active()),
                "completion": completion,
                "binding_guid": _guid(binding_id.get_editor_property("guid")),
            })
    roots = [_track_row(t, seq) for t in seq.get_tracks()
             if t.get_class().get_name() != "MovieSceneCameraCutTrack"]
    roots.sort(key=lambda row: (_track_identity(row), row["display_name"], digest(row)))
    markers = sorted([
        [str(mark.get_editor_property("label")), int(mark.get_editor_property("frame_number").value)]
        for mark in seq.get_marked_frames_from_sequence(ue.MovieSceneTimeUnit.DISPLAY_RATE)
    ])
    return {
        "display_rate": _rate(seq.get_display_rate()), "tick_resolution": _rate(seq.get_tick_resolution()),
        "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
        "bindings": bindings, "cuts": cuts, "root_tracks": roots, "markers": markers,
        "cut_track_count": len(cut_tracks),
    }


def _level_actor_index():
    rows = [{"path": str(actor.get_path_name()), "label": str(actor.get_actor_label()), "tags": _actor_tags(actor)}
            for actor in _actors()]
    return sorted(rows, key=lambda row: row["path"])


def _binding_by_name(snapshot, name):
    rows = [row for row in snapshot["bindings"] if row["name"] == name]
    if len(rows) != 1:
        raise PlanError("BINDING_COUNT|%s|%d" % (name, len(rows)))
    return rows[0]


def plan_from_snapshot(snapshot):
    if abs(snapshot["display_rate"] - EXPECTED_FPS) > 1.0e-9:
        raise PlanError("DISPLAY_RATE|live=%s|expected=%s" % (snapshot["display_rate"], EXPECTED_FPS))
    if abs(snapshot["tick_resolution"] - EXPECTED_TICK) > 1.0e-9:
        raise PlanError("TICK_RESOLUTION|live=%s|expected=%s" % (snapshot["tick_resolution"], EXPECTED_TICK))
    if snapshot["playback"] != EXPECTED_PLAYBACK:
        raise PlanError("PLAYBACK|live=%r|expected=%r" % (snapshot["playback"], EXPECTED_PLAYBACK))
    if snapshot["cut_track_count"] != 1:
        raise PlanError("CUT_TRACK_COUNT|%d" % snapshot["cut_track_count"])
    old = _binding_by_name(snapshot, OLD_CAMERA)
    mouth = _binding_by_name(snapshot, MOUTH_CAMERA)
    active = [row for row in snapshot["cuts"] if row["active"]]
    mouth_starts = sorted({row["range"][0] for row in active if row["binding_guid"] == mouth["guid"]})
    live_cut = mouth_starts[0] if mouth_starts else None
    if live_cut != EXPECTED_SLEIGHT:
        raise PlanError("SLEIGHT_CUT_FRAME_MISMATCH|live=%r|expected=%d" % (live_cut, EXPECTED_SLEIGHT))
    targets = [row for row in active if row["binding_guid"] == old["guid"]
               and row["range"][0] >= EXPECTED_PLAYBACK[0]
               and row["range"][1] <= live_cut and row["range"][0] < live_cut]
    cursor = EXPECTED_PLAYBACK[0]
    for row in sorted(targets, key=lambda item: item["range"]):
        if row["range"][0] != cursor or row["range"][1] <= row["range"][0]:
            raise PlanError("HANGAR_CUT_COVERAGE|cursor=%d|row=%r" % (cursor, row))
        cursor = row["range"][1]
    if not targets or cursor != live_cut:
        raise PlanError("HANGAR_CUT_COVERAGE|covered_end=%d|expected=%d|sections=%r" %
                        (cursor, live_cut, [row["range"] for row in targets]))
    return {
        "live_sleight_cut_frame": live_cut, "expected_sleight_cut_frame": EXPECTED_SLEIGHT,
        "old_camera_guid": old["guid"], "mouth_camera_guid": mouth["guid"],
        "target_cut_sections": [{"track_index": r["track_index"], "section_index": r["section_index"],
                                 "range": r["range"], "original_binding_guid": r["binding_guid"]}
                                for r in targets],
    }


def _i2_order_guard_guids():
    record = _json_read(os.path.join(_saved_root(), I2_ORDER_RECORD_REL), required=False) or {}
    if not record.get("applied"):
        return []
    return sorted({str(row.get("guid")) for row in record.get("created", []) if row.get("guid")})


def guard_view(snapshot):
    mpc = [row for row in snapshot["root_tracks"]
           if row["class"] == "MovieSceneMaterialParameterCollectionTrack"
           and "ShadowGobo Frame" in row["display_name"]]
    if len(mpc) != 1:
        raise PlanError("SHADOW_GOBO_FRAME_TRACK_COUNT|%d" % len(mpc))
    spots = {}
    for label in SPOT_LABELS:
        binding = _binding_by_name(snapshot, label)
        if binding.get("template") is None:
            raise PlanError("GOBO_SPOT_TEMPLATE_UNREADABLE|%s" % label)
        spots[label] = binding["template"]
    order_guids = set(_i2_order_guard_guids())
    order = [row for row in snapshot["bindings"]
             if row["name"].startswith(ORDER_PREFIXES) or row["guid"] in order_guids]
    return {"shadow_gobo_frame_track": mpc[0], "gobo_spot_templates": spots,
            "i2_order_bindings": sorted(order, key=lambda row: (row["name"], row["guid"])),
            "i2_order_record_guids": sorted(order_guids)}


def guard_hashes(snapshot):
    view = guard_view(snapshot)
    return {key: digest(value) for key, value in view.items()}


def _load_curtain_record():
    record = _json_read(os.path.join(_saved_root(), CURTAIN_RECORD_REL), required=False)
    if not record or not record.get("applied") or int(record.get("interaction", 0)) != 2:
        return None
    return record


def build_report(seq, params, run):
    snapshot = _snapshot(seq)
    cut_plan = plan_from_snapshot(snapshot)
    curtain = _load_curtain_record()
    if params["derive_focus_from_curtain_record"] and curtain:
        focus, focus_source, focus_point = focus_from_curtain_record(
            curtain, params["location_cm"], params["focus_distance_cm"])
    else:
        focus, focus_source, focus_point = (params["focus_distance_cm"],
                                             "args.focus_distance_cm (derivation disabled or record absent)", None)
    focal = focal_for_hfov(params["sensor_width_mm"], params["horizontal_fov_deg"])
    plan = dict(cut_plan)
    plan.update({
        "actor": {"label": ACTOR_LABEL, "tag": ACTOR_TAG, "location_cm": params["location_cm"],
                  "rotation_deg": params["rotation_deg"], "sensor_width_mm": params["sensor_width_mm"],
                  "sensor_height_mm": params["sensor_height_mm"], "horizontal_fov_deg": params["horizontal_fov_deg"],
                  "focal_length_mm": focal, "focus_distance_cm": focus,
                  "focus_source": focus_source, "focus_point_world_cm": focus_point,
                  "mobility": "MOVABLE", "attached": False},
        "save_targets": {"content": [SEQ_PATH], "maps": [MAP_PATH]},
    })
    guards = guard_hashes(snapshot)
    inputs = {"snapshot": snapshot, "params": params, "focus_source": focus_source,
              "focus_point": focus_point}
    return {"schema_version": 1, "tool_version": TOOL_VERSION, "run": run, "mode": "DRY",
            "sequence": SEQ_PATH, "map": MAP_PATH, "plan": plan, "plan_digest": digest(plan),
            "inputs_digest": digest(inputs), "guards": guards, "guard_view": guard_view(snapshot),
            "snapshot": snapshot, "level_actors": _level_actor_index(), "claims": CLAIMS,
            "apply_ready": True}


def _load_sequence(run):
    seq = _ue().load_asset(SEQ_PATH)
    if seq is None:
        _stop(run, "SEQUENCE_LOAD_FAILED|%s" % SEQ_PATH)
    return seq


def _backup(run, suffix=""):
    label = "I2HangarCam%s" % suffix
    root = os.path.join(_project_root(), "Backups", "Pre%s-%s" % (label, run))
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in (MAP_PATH, SEQ_PATH):
        source = _asset_file(package)
        if not os.path.isfile(source):
            _stop(run, "BACKUP_SOURCE_MISSING|%s" % source)
        target = os.path.join(root, os.path.basename(source))
        shutil.copy2(source, target)
        if os.path.getsize(source) != os.path.getsize(target) or _sha(source) != _sha(target):
            _stop(run, "BACKUP_VERIFY_FAILED|%s" % package)
        rows.append({"package": package, "source": source, "backup": target, "sha256": _sha(target),
                     "bytes": os.path.getsize(target)})
    return {"root": root, "files": rows}


def _sha(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def _camera_component(actor, run):
    component = None
    try:
        component = actor.get_cine_camera_component()
    except Exception:  # noqa: BLE001
        pass
    if component is None:
        try:
            component = actor.get_component_by_class(_ue().CineCameraComponent)
        except Exception:  # noqa: BLE001
            pass
    if component is None:
        _stop(run, "CINE_CAMERA_COMPONENT_MISSING")
    return component


def _set_camera_lens(component, plan, run):
    ue = _ue()
    filmback = _prop(component, "filmback")
    if filmback is None:
        _stop(run, "FILMBACK_UNREADABLE")
    filmback.set_editor_property("sensor_width", float(plan["sensor_width_mm"]))
    filmback.set_editor_property("sensor_height", float(plan["sensor_height_mm"]))
    component.set_editor_property("filmback", filmback)
    component.set_editor_property("current_focal_length", float(plan["focal_length_mm"]))
    focus = _prop(component, "focus_settings")
    if focus is None:
        _stop(run, "FOCUS_SETTINGS_UNREADABLE")
    focus.set_editor_property("focus_method", ue.CameraFocusMethod.MANUAL)
    focus.set_editor_property("manual_focus_distance", float(plan["focus_distance_cm"]))
    component.set_editor_property("focus_settings", focus)


def _spawn_camera(world, plan, run):
    ue = _ue()
    p = plan["actor"]
    subsystem = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    location = ue.Vector(*p["location_cm"])
    rot = p["rotation_deg"]
    rotation = ue.Rotator(roll=rot["roll"], pitch=rot["pitch"], yaw=rot["yaw"])
    actor = subsystem.spawn_actor_from_class(ue.CineCameraActor, location, rotation, False)
    if actor is None:
        _stop(run, "SPAWN_CAMERA_FAILED|NOTHING SAVED; Don't-Save restart")
    actor.set_actor_label(ACTOR_LABEL)
    actor.set_editor_property("tags", list(_prop(actor, "tags", []) or []) + [ue.Name(ACTOR_TAG)])
    if actor.get_attach_parent_actor() is not None:
        _stop(run, "CAMERA_ATTACHED_AFTER_SPAWN|NOTHING SAVED; Don't-Save restart")
    root = _prop(actor, "root_component")
    if root is None:
        _stop(run, "CAMERA_ROOT_MISSING|NOTHING SAVED; Don't-Save restart")
    try:
        root.set_mobility(ue.ComponentMobility.MOVABLE)
    except Exception:  # noqa: BLE001
        root.set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
    moved = actor.set_actor_location_and_rotation(location, rotation, False, True)
    if moved is False:
        _stop(run, "SET_CAMERA_TRANSFORM_FAILED|NOTHING SAVED; Don't-Save restart")
    _set_camera_lens(_camera_component(actor, run), p, run)
    return actor


def _find_actor_bindings(seq, actor, world):
    found = {}
    lookup_api = False
    if hasattr(seq, "find_binding_from_object"):
        lookup_api = True
        try:
            binding = seq.find_binding_from_object(actor, world)
            if binding is not None and binding.is_valid():
                found[_guid(binding.get_id())] = binding
        except Exception:  # noqa: BLE001
            pass
    if hasattr(seq, "locate_bound_objects"):
        lookup_api = True
        for binding in seq.get_bindings():
            try:
                if any(obj is actor or str(obj.get_path_name()) == str(actor.get_path_name())
                       for obj in seq.locate_bound_objects(binding, world)):
                    found[_guid(binding.get_id())] = binding
            except Exception:  # noqa: BLE001
                pass
    if not lookup_api:
        raise PlanError("BINDING_LOOKUP_API_UNAVAILABLE")
    return list(found.values())


def _bind_camera(seq, actor, world, run):
    """Lookup first.  Never rename a pre-existing or returned-existing binding."""
    before = {_guid(binding.get_id()) for binding in seq.get_bindings()}
    matches = _find_actor_bindings(seq, actor, world)
    if len(matches) > 1:
        _stop(run, "CAMERA_EXISTING_BINDING_COUNT|%d|NOTHING SAVED; Don't-Save restart" % len(matches))
    if matches:
        binding, lookup_found = matches[0], True
    else:
        binding, lookup_found = seq.add_possessable(actor), False
        if binding is None or not binding.is_valid():
            _stop(run, "ADD_POSSESSABLE_FAILED|NOTHING SAVED; Don't-Save restart")
    guid = _guid(binding.get_id())
    created = guid not in before
    if created:
        binding.set_display_name(ACTOR_LABEL)
    return binding, {"guid": guid, "created": created, "lookup_found": lookup_found,
                     "display_name": str(binding.get_display_name()),
                     "add_possessable_returned_existing": (not lookup_found and not created)}


def _cut_sections(seq, run):
    tracks = list(seq.find_tracks_by_type(_ue().MovieSceneCameraCutTrack))
    if len(tracks) != 1:
        _stop(run, "CUT_TRACK_COUNT|%d" % len(tracks))
    return tracks[0], list(tracks[0].get_sections())


def _apply_cuts(seq, target_rows, binding, run):
    track, sections = _cut_sections(seq, run)
    del track
    binding_id = seq.get_binding_id(binding)
    changed = []
    for row in target_rows:
        index = int(row["section_index"])
        if index < 0 or index >= len(sections):
            _stop(run, "CUT_SECTION_INDEX|%d|NOTHING SAVED; Don't-Save restart" % index)
        section = sections[index]
        live_range = _section_range(section, seq)
        live_guid = _guid(section.get_camera_binding_id().get_editor_property("guid"))
        if live_range != row["range"] or live_guid != row["original_binding_guid"]:
            _stop(run, "CUT_SECTION_DRIFT|index=%d|range=%r|guid=%s|NOTHING SAVED; Don't-Save restart" %
                  (index, live_range, live_guid))
        section.set_camera_binding_id(binding_id)
        changed.append(dict(row, new_binding_guid=_guid(binding.get_id())))
    return changed


def _restore_cuts(seq, rows, run):
    bindings = {_guid(binding.get_id()): binding for binding in seq.get_bindings()}
    _track, sections = _cut_sections(seq, run)
    for row in rows:
        index = int(row["section_index"])
        if index < 0 or index >= len(sections):
            _stop(run, "REVERT_CUT_SECTION_INDEX|%d|NOTHING SAVED; Don't-Save restart" % index)
        section = sections[index]
        live_range = _section_range(section, seq)
        live_guid = _guid(section.get_camera_binding_id().get_editor_property("guid"))
        if live_range != row["range"] or live_guid != row["new_binding_guid"]:
            _stop(run, "REVERT_CUT_DRIFT|index=%d|range=%r|guid=%s|NOTHING SAVED; Don't-Save restart" %
                  (index, live_range, live_guid))
        old = bindings.get(row["original_binding_guid"])
        if old is None:
            _stop(run, "OLD_CAMERA_BINDING_MISSING|%s" % row["original_binding_guid"])
        section.set_camera_binding_id(seq.get_binding_id(old))


def _camera_hfov(component):
    try:
        return float(component.get_horizontal_field_of_view()), "get_horizontal_field_of_view"
    except Exception:  # noqa: BLE001
        value = _prop(component, "field_of_view")
        if value is None:
            filmback = _prop(component, "filmback")
            return hfov_for_focal(float(_prop(filmback, "sensor_width")),
                                  float(_prop(component, "current_focal_length"))), "filmback/focal readback"
        return float(value), "field_of_view"


def _actor_state(actor):
    loc, rot = actor.get_actor_location(), actor.get_actor_rotation()
    component = _camera_component(actor, "READBACK")
    filmback, focus = _prop(component, "filmback"), _prop(component, "focus_settings")
    hfov, hfov_source = _camera_hfov(component)
    root = _prop(actor, "root_component")
    parent = actor.get_attach_parent_actor()
    return {
        "path": str(actor.get_path_name()), "label": str(actor.get_actor_label()), "tags": _actor_tags(actor),
        "location_cm": [float(loc.x), float(loc.y), float(loc.z)],
        "rotation_deg": {"pitch": float(rot.pitch), "yaw": float(rot.yaw), "roll": float(rot.roll)},
        "parent": str(parent.get_path_name()) if parent is not None else None,
        "mobility": _enum_name(_prop(root, "mobility")),
        "sensor_width_mm": float(_prop(filmback, "sensor_width")),
        "sensor_height_mm": float(_prop(filmback, "sensor_height")),
        "focal_length_mm": float(_prop(component, "current_focal_length")),
        "horizontal_fov_deg": hfov, "horizontal_fov_source": hfov_source,
        "focus_method": _enum_name(_prop(focus, "focus_method")),
        "focus_distance_cm": float(_prop(focus, "manual_focus_distance")),
    }


def camera_state_problems(state, plan, params):
    want = plan["actor"]
    problems = []
    if state["label"] != want["label"] or want["tag"] not in state["tags"]:
        problems.append("CAMERA_IDENTITY|%r" % state)
    if state["parent"] is not None:
        problems.append("CAMERA_ATTACHED|%s" % state["parent"])
    if state["mobility"] != "MOVABLE":
        problems.append("CAMERA_NOT_MOVABLE|%s" % state["mobility"])
    for index, value in enumerate(want["location_cm"]):
        if abs(state["location_cm"][index] - value) > params["location_tolerance_cm"]:
            problems.append("CAMERA_LOCATION_%d|%s!=%s" % (index, state["location_cm"][index], value))
    for key, value in want["rotation_deg"].items():
        if abs(state["rotation_deg"][key] - value) > params["rotation_tolerance_deg"]:
            problems.append("CAMERA_ROTATION_%s|%s!=%s" % (key, state["rotation_deg"][key], value))
    for key in ("sensor_width_mm", "sensor_height_mm", "focal_length_mm", "focus_distance_cm"):
        tol = 1.0e-4 * max(1.0, abs(float(want[key])))
        if abs(state[key] - float(want[key])) > tol:
            problems.append("CAMERA_%s|%s!=%s" % (key, state[key], want[key]))
    if abs(state["horizontal_fov_deg"] - want["horizontal_fov_deg"]) > params["fov_tolerance_deg"]:
        problems.append("CAMERA_HFOV|%s!=%s" % (state["horizontal_fov_deg"], want["horizontal_fov_deg"]))
    if state["focus_method"] != "MANUAL":
        problems.append("CAMERA_FOCUS_NOT_MANUAL|%s" % state["focus_method"])
    return problems


def snapshot_apply_problems(before, after, created_guid, target_rows):
    problems = []
    for key in ("display_rate", "tick_resolution", "playback", "markers", "root_tracks", "cut_track_count"):
        if before[key] != after[key]:
            problems.append("UNTOUCHED_CHANGED|%s" % key)
    bmap = {row["guid"]: row for row in before["bindings"]}
    amap = {row["guid"]: row for row in after["bindings"]}
    extra = set(amap) - set(bmap)
    if extra != ({created_guid} if created_guid else set()):
        problems.append("BINDING_ADDITIONS|%r" % sorted(extra))
    if set(bmap) - set(amap):
        problems.append("BINDINGS_REMOVED|%r" % sorted(set(bmap) - set(amap)))
    for guid in sorted(set(bmap) & set(amap)):
        if bmap[guid] != amap[guid]:
            problems.append("UNTOUCHED_BINDING_CHANGED|%s|%s" % (guid, bmap[guid]["name"]))
    targets = {(int(row["track_index"]), int(row["section_index"])): row for row in target_rows}
    before_cuts = {(r["track_index"], r["section_index"]): r for r in before["cuts"]}
    after_cuts = {(r["track_index"], r["section_index"]): r for r in after["cuts"]}
    if set(before_cuts) != set(after_cuts):
        problems.append("CUT_SECTION_SET_CHANGED")
    for key in sorted(set(before_cuts) & set(after_cuts)):
        old, new = before_cuts[key], after_cuts[key]
        expected = dict(old)
        if key in targets:
            expected["binding_guid"] = targets[key]["new_binding_guid"]
        if new != expected:
            problems.append("CUT_CHANGED|%r|got=%r|want=%r" % (key, new, expected))
    return problems


def _save_targets(world, run):
    ue = _ue()
    expected = {"content": [SEQ_PATH], "maps": [MAP_PATH]}
    census = _census()
    if census != expected:
        _stop(run, "UNEXPECTED_DIRTY_PACKAGES|live=%s|expected=%s|NOTHING SAVED; Don't-Save restart" %
              (json.dumps(census, sort_keys=True), json.dumps(expected, sort_keys=True)))
    saves = []
    if not bool(ue.EditorAssetLibrary.save_asset(SEQ_PATH, only_if_is_dirty=True)):
        _stop(run, "SAVE_FAILED|%s" % SEQ_PATH)
    saves.append(SEQ_PATH)
    if _census() != {"content": [], "maps": [MAP_PATH]}:
        _stop(run, "DIRTY_AFTER_SEQUENCE_SAVE|%s" % json.dumps(_census(), sort_keys=True))
    if not bool(ue.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH)):
        _stop(run, "SAVE_FAILED|%s" % MAP_PATH)
    saves.append(MAP_PATH)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census(), sort_keys=True))
    return saves


def run_dry(run, params, confirm):
    _preflight("DRY", run, confirm)
    report = build_report(_load_sequence(run), params, run)
    report_path = os.path.join(_here(), "i2_hangar_cam_dry_%s.json" % run)
    _json_write(report_path, report)
    _json_write(_plan_path(), {"run": run, "plan_digest": report["plan_digest"],
                               "inputs_digest": report["inputs_digest"], "guards": report["guards"],
                               "params": params, "report": report_path})
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % json.dumps(_census(), sort_keys=True))
    _log("%s_DRY_OK|run=%s|mutated=0|apply_ready=1|live_cut=%d|targets=%d|focal_mm=%.6f|focus_cm=%.3f|"
         "guard=%s|report=%s" % (TOOL, run, report["plan"]["live_sleight_cut_frame"],
                                  len(report["plan"]["target_cut_sections"]),
                                  report["plan"]["actor"]["focal_length_mm"],
                                  report["plan"]["actor"]["focus_distance_cm"],
                                  digest(report["guards"])[:16], report_path))
    return report


def _require_dry(report, run):
    dry = _json_read(_plan_path(), required=True)
    if dry.get("guards") != report["guards"]:
        _stop(run, "GUARD_CHANGED_SINCE_DRY|rerun DRY|dry=%s|live=%s" %
              (json.dumps(dry.get("guards"), sort_keys=True), json.dumps(report["guards"], sort_keys=True)))
    if dry.get("plan_digest") != report["plan_digest"] or dry.get("inputs_digest") != report["inputs_digest"]:
        _stop(run, "PLAN_CHANGED_SINCE_DRY|rerun DRY")
    return dry


def run_apply(run, params, confirm):
    world = _preflight("APPLY", run, confirm)
    if os.path.exists(_record_path()):
        _stop(run, "RECORD_EXISTS|REVERT first|%s" % _record_path())
    seq = _load_sequence(run)
    report = build_report(seq, params, run)
    dry = _require_dry(report, run)
    backup = _backup(run)
    record = {
        "schema_version": 1, "tool_version": TOOL_VERSION, "run": run, "applied": False,
        "map": MAP_PATH, "sequence": SEQ_PATH, "backup": backup, "dry": dry,
        "params": params, "plan": report["plan"], "guards_dry": report["guards"],
        "snapshot_before": report["snapshot"], "level_actors_before": report["level_actors"],
    }
    try:
        _json_write(_record_path(), record, exclusive=True)
    except FileExistsError:
        _stop(run, "RECORD_EXISTS|nothing mutated")
    seq.modify()
    actor = _spawn_camera(world, report["plan"], run)
    binding, binding_record = _bind_camera(seq, actor, world, run)
    changed = _apply_cuts(seq, report["plan"]["target_cut_sections"], binding, run)
    record.update({"actor_path": str(actor.get_path_name()), "binding": binding_record,
                   "cut_sections": changed})
    _json_write(_record_path(), record)
    after = _snapshot(seq)
    state = _actor_state(actor)
    problems = camera_state_problems(state, report["plan"], params)
    created_guid = binding_record["guid"] if binding_record["created"] else None
    problems += snapshot_apply_problems(report["snapshot"], after, created_guid, changed)
    actor_after = _level_actor_index()
    added = [row for row in actor_after if row not in report["level_actors"]]
    if len(added) != 1 or added[0]["path"] != state["path"]:
        problems.append("LEVEL_ACTOR_DELTA|%r" % added)
    if guard_hashes(after) != report["guards"]:
        problems.append("GUARD_CHANGED_DURING_APPLY")
    if problems:
        _stop(run, "PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
              (json.dumps(problems), backup["root"]))
    saves = _save_targets(world, run)
    seq2 = _load_sequence(run)
    actors = _ours_actors()
    if len(actors) != 1:
        _stop(run, "POSTSAVE_CAMERA_COUNT|%d|restore=%s" % (len(actors), backup["root"]))
    after2, state2 = _snapshot(seq2), _actor_state(actors[0])
    problems = camera_state_problems(state2, report["plan"], params)
    problems += snapshot_apply_problems(report["snapshot"], after2, created_guid, changed)
    if after2 != after:
        problems.append("POSTSAVE_SEQUENCE_DIFFERS_FROM_PRESAVE")
    if guard_hashes(after2) != report["guards"]:
        problems.append("GUARD_CHANGED_AFTER_SAVE")
    if problems or _census() != {"content": [], "maps": []}:
        _stop(run, "POSTSAVE_READBACK|%s|census=%s|restore=%s" %
              (json.dumps(problems), json.dumps(_census()), backup["root"]))
    record.update({"applied": True, "snapshot_after": after2, "actor_after": state2,
                   "level_actors_after": _level_actor_index(), "guards_after": guard_hashes(after2),
                   "saves": saves, "census_after": _census()})
    _json_write(_record_path(), record)
    _log("%s_APPLY_OK|run=%s|actor=%s|binding=%s|created_binding=%d|cuts=%d|live_cut=%d|"
         "unattached=1|hfov=%.6f|saved=%s|backup=%s|record=%s" %
         (TOOL, run, state2["path"], binding_record["guid"], int(binding_record["created"]), len(changed),
          report["plan"]["live_sleight_cut_frame"], state2["horizontal_fov_deg"], ",".join(saves),
          backup["root"], _record_path()))
    return record


def _remove_binding(seq, record, run):
    binding_record = record["binding"]
    rows = [binding for binding in seq.get_bindings() if _guid(binding.get_id()) == binding_record["guid"]]
    if len(rows) != 1:
        _stop(run, "CAMERA_BINDING_COUNT|%d|NOTHING SAVED; Don't-Save restart" % len(rows))
    if binding_record["created"]:
        if str(rows[0].get_display_name()) != ACTOR_LABEL:
            _stop(run, "REFUSE_REMOVE_FOREIGN_BINDING|%s" % rows[0].get_display_name())
        rows[0].remove()


def run_revert(run, params, confirm):
    world = _preflight("REVERT", run, confirm)
    record = _json_read(_record_path(), required=True)
    if not record.get("applied") or record.get("sequence") != SEQ_PATH or record.get("map") != MAP_PATH:
        _stop(run, "REVERT_RECORD_CONTEXT")
    seq = _load_sequence(run)
    live = _snapshot(seq)
    live_guards = guard_hashes(live)
    if live_guards != record["guards_dry"]:
        _stop(run, "GUARD_CHANGED_SINCE_DRY|rerun DRY is not allowed over an applied record; coordinate first|dry=%s|live=%s" %
              (json.dumps(record["guards_dry"], sort_keys=True), json.dumps(live_guards, sort_keys=True)))
    actors = _ours_actors()
    if len(actors) != 1:
        _stop(run, "REVERT_CAMERA_COUNT|%d" % len(actors))
    drift = []
    if live != record["snapshot_after"]:
        drift.append("SEQUENCE")
    state = _actor_state(actors[0])
    if state != record["actor_after"]:
        drift.append("CAMERA")
    if _level_actor_index() != record["level_actors_after"]:
        drift.append("LEVEL_ACTORS")
    if drift:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%s|backup=%s" % (",".join(drift), record["backup"]["root"]))
    backup = _backup(run, "Revert")
    txn = os.path.join(_here(), "i2_hangar_cam_revert_%s.json" % run)
    _json_write(txn, {"schema_version": 1, "run": run, "completed": False, "backup": backup,
                      "source_record": _record_path(), "snapshot_before_revert": live,
                      "actor_before_revert": state}, exclusive=True)
    seq.modify()
    _restore_cuts(seq, record["cut_sections"], run)
    _remove_binding(seq, record, run)
    subsystem = _ue().get_editor_subsystem(_ue().EditorActorSubsystem)
    actor = actors[0]
    if str(actor.get_actor_label()) != ACTOR_LABEL or ACTOR_TAG not in _actor_tags(actor):
        _stop(run, "REFUSE_DESTROY_FOREIGN_ACTOR|NOTHING SAVED; Don't-Save restart")
    if not bool(subsystem.destroy_actor(actor)):
        _stop(run, "DESTROY_ACTOR_FAILED|NOTHING SAVED; Don't-Save restart")
    after = _snapshot(seq)
    problems = []
    if after != record["snapshot_before"]:
        problems.append("SEQUENCE_NOT_EXACT")
    if _level_actor_index() != record["level_actors_before"]:
        problems.append("LEVEL_ACTORS_NOT_EXACT")
    if _ours_actors():
        problems.append("TAGGED_ACTOR_SURVIVED")
    if guard_hashes(after) != record["guards_dry"]:
        problems.append("GUARD_CHANGED_DURING_REVERT")
    if problems:
        _stop(run, "REVERT_PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
              (json.dumps(problems), backup["root"]))
    saves = _save_targets(world, run)
    seq2 = _load_sequence(run)
    problems = []
    if _snapshot(seq2) != record["snapshot_before"]:
        problems.append("SEQUENCE_NOT_EXACT_AFTER_SAVE")
    if _level_actor_index() != record["level_actors_before"] or _ours_actors():
        problems.append("LEVEL_NOT_EXACT_AFTER_SAVE")
    if guard_hashes(_snapshot(seq2)) != record["guards_dry"]:
        problems.append("GUARD_CHANGED_AFTER_REVERT_SAVE")
    if problems or _census() != {"content": [], "maps": []}:
        _stop(run, "REVERT_POSTSAVE_READBACK|%s|census=%s|restore=%s" %
              (json.dumps(problems), json.dumps(_census()), backup["root"]))
    archived = _record_path() + ".reverted-" + run
    os.rename(_record_path(), archived)
    _json_write(txn, dict(_json_read(txn), completed=True, archived_record=archived, saves=saves,
                          census_after=_census()))
    _log("%s_REVERT_OK|run=%s|cuts=%d|binding_removed=%d|actor_destroyed=1|saved=%s|backup=%s|record=%s" %
         (TOOL, run, len(record["cut_sections"]), int(record["binding"]["created"]), ",".join(saves),
          backup["root"], archived))
    return {"archived_record": archived, "backup": backup, "saves": saves}


def main(args):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or datetime.datetime.now().strftime("I2HANGARCAM-%Y%m%d-%H%M%S"))
    try:
        params = merged_params(args.get("params") or {})
        function = {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}.get(mode)
        if function is None:
            _stop(run, "MODE|%r" % mode)
        return function(run, params, args.get("confirm"))
    except PlanError as error:
        _stop(run, "PLAN_REFUSED|%s" % error)
