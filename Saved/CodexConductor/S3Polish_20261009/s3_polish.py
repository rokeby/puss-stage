"""P28 S3 finishing-polish authoring tool (9 Oct 2026).

Offline-authored.  Import ``unreal`` only inside the functions used by the
conductor's later editor slot.

Modes and confirms:
  DRY     / ``DRY S3POLISH``
  APPLY   / ``APPLY S3POLISH``
  REVERT  / ``REVERT S3POLISH``

The four independently selectable parts are ``fires_together``, ``b11_dim``,
``dune_shadow`` and ``stylish_fire``.  ``stylish_fire`` remains a DRY look
report unless ``stylish_apply`` is explicitly true.  The only packages this
tool can save are LS_DevScene_03 and the vertical-slice map.

Evidence boundary:
  declaration-proven: the requested parts, defaults and save scope are in
    Docs/Conductor/codex_briefs/p28_s3_polish.md:1-29.
  measured upstream: that brief records B/C ignition at 260/290, B11 at
    [5181,6253], the named wave-light family and the tagged shore ground.
    DRY re-reads all of those states; this offline build does not re-measure UE.
  inferred: camera-space ``second_left`` is a deterministic interpretation of
    Gary's phrase, not rendered acceptance.  DRY reports the complete ranking
    and the args can override the selected labels.
"""

import datetime
import hashlib
import json
import math
import os
import shutil


TOOL = "S3_POLISH"
TOOL_VERSION = "2026-10-09a"
FOLDER = "S3Polish_20261009"
MAP_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
MAP_FILE = os.path.join("InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
SEQ_FILE = os.path.join("InfinityStage", "Dev", "Sequences", "LS_DevScene_03.uasset")
RECORD = "s3_polish_record.json"
PLAN = "s3_polish_plan.json"
PARTS = ("fires_together", "b11_dim", "dune_shadow", "stylish_fire")
CONFIRMS = {"DRY": "DRY S3POLISH", "APPLY": "APPLY S3POLISH", "REVERT": "REVERT S3POLISH"}

FIRE_LIGHTS = ("S3 Fire B Light", "S3 Fire C Light")
FIRE_EMITTERS = ("S3 Fire B", "S3 Fire C")
ALL_EMITTERS = ("S3 Ghost Light Flame", "S3 Fire A", "S3 Fire B", "S3 Fire C")
FIRE_TRACK = "S3.Fire.Light"
WAVE_TRACK = "S3.WavesV3.Light"
B11_CAMERA = "S3 Shot B11"
B11_RANGE = (5181, 6253)
WAVE_CANDIDATES = tuple("S3 WaveV3 Ground Row %d" % i for i in (2, 3, 4))
DUNE_TAG = "RigAtmos.S3ShoreGround"
STYLISH_TAG = "S3PolishStylishFire"
STYLISH_FOLDER = "RigAtmos/S3Fire/Stylish"
P_FIRE = "/Game/StarterContent/Particles/P_Fire"

SHADOW_READ_PROPS = (
    "cast_shadow", "cast_dynamic_shadow", "cast_static_shadow", "cast_contact_shadow",
    "cast_far_shadow", "cast_inset_shadow", "cast_hidden_shadow", "cast_cinematic_shadow",
    "shadow_cache_invalidation_behavior", "bounds_scale", "visible_in_ray_tracing",
    "affect_distance_field_lighting",
)

DEFAULTS = {
    "common_ignite_frame": 230,
    "fire_ramp_frames": 72,
    "b11_factor": 0.25,
    "b11_ramp_frames": 24,
    "b11_candidate_labels": list(WAVE_CANDIDATES),
    "b11_dim_labels": [],
    "b11_selection": "second_left",
    "stylish_apply": False,
    "stylish_systems": {
        "S3 Ghost Light Flame": "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_1",
        "S3 Fire A": "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_2",
        "S3 Fire B": "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_3",
        "S3 Fire C": "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_4",
    },
    "float_tolerance": 0.0001,
    "location_tolerance_cm": 0.01,
    "rotation_tolerance_deg": 0.001,
}

CLAIMS = [
    {"tier": "declaration-proven", "claim": "B and C share a configurable ignition and slow envelope; A and the ghost are untouched by fires_together.",
     "cite": "Docs/Conductor/codex_briefs/p28_s3_polish.md:20-23"},
    {"tier": "measured", "claim": "The live B11 cut, camera pose, candidate positions, dune flags and Niagara parameter stores are read by DRY.",
     "cite": "Docs/Conductor/codex_briefs/p28_s3_polish.md:12-19"},
    {"tier": "inferred", "claim": "second_left ranks camera-left candidates by forward depth and chooses the second; Gary may override b11_dim_labels.",
     "cite": "Docs/Conductor/codex_briefs/p28_s3_polish.md:14-16"},
]


class Stop(RuntimeError):
    pass


class PlanError(ValueError):
    pass


_MISSING = object()


def _ue():
    import unreal  # noqa: WPS433 - deliberately local for offline harnesses
    return unreal


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def merged_params(raw):
    p = dict(DEFAULTS)
    raw = dict(raw or {})
    stylish = dict(DEFAULTS["stylish_systems"])
    stylish.update(raw.pop("stylish_systems", {}) or {})
    p.update(raw)
    p["stylish_systems"] = stylish
    p["common_ignite_frame"] = int(p["common_ignite_frame"])
    p["fire_ramp_frames"] = int(p["fire_ramp_frames"])
    p["b11_factor"] = float(p["b11_factor"])
    p["b11_ramp_frames"] = int(p["b11_ramp_frames"])
    p["float_tolerance"] = float(p["float_tolerance"])
    p["location_tolerance_cm"] = float(p["location_tolerance_cm"])
    p["rotation_tolerance_deg"] = float(p["rotation_tolerance_deg"])
    p["b11_candidate_labels"] = [str(v) for v in p["b11_candidate_labels"]]
    p["b11_dim_labels"] = [str(v) for v in p["b11_dim_labels"]]
    p["b11_selection"] = str(p["b11_selection"])
    p["stylish_apply"] = bool(p["stylish_apply"])
    if p["common_ignite_frame"] < 0 or p["fire_ramp_frames"] <= 0:
        raise PlanError("FIRE_TIMING_RANGE")
    if not (0.0 <= p["b11_factor"] <= 1.0) or p["b11_ramp_frames"] <= 0:
        raise PlanError("B11_DIM_RANGE")
    if len(set(p["b11_candidate_labels"])) != len(p["b11_candidate_labels"]):
        raise PlanError("DUPLICATE_B11_CANDIDATE")
    if not set(p["b11_dim_labels"]).issubset(set(p["b11_candidate_labels"])):
        raise PlanError("B11_DIM_LABEL_NOT_CANDIDATE")
    if p["b11_selection"] not in ("second_left", "explicit"):
        raise PlanError("B11_SELECTION")
    if set(p["stylish_systems"]) != set(ALL_EMITTERS):
        raise PlanError("STYLISH_MAPPING_MUST_NAME_ALL_EMITTERS")
    return p


def selected_parts(raw):
    out = [str(v) for v in (raw or PARTS)]
    if not out or len(set(out)) != len(out) or any(v not in PARTS for v in out):
        raise PlanError("PARTS|%r" % out)
    return out


def _normalise_keys(keys, boolean=False):
    out = [[int(row[0]), bool(row[1]) if boolean else float(row[1])] for row in keys]
    out.sort(key=lambda row: row[0])
    if len({row[0] for row in out}) != len(out):
        raise PlanError("DUPLICATE_KEY_FRAME|%r" % out)
    return out


def fire_key_plan(keys, old_ignite, common_ignite, ramp_frames):
    """Shift the ignition-and-later curve, applying a 0->1 envelope.

    Returns the complete replacement curve and one audit row per moved key.
    The existing zero/baseline keys before ignition stay byte-for-byte logical.
    """
    before = _normalise_keys(keys)
    old_ignite, common_ignite, ramp_frames = int(old_ignite), int(common_ignite), int(ramp_frames)
    if ramp_frames <= 0 or not any(f == old_ignite and abs(v) <= 1.0e-4 for f, v in before):
        raise PlanError("FIRE_IGNITION_KEY_MISSING|%d" % old_ignite)
    delta = common_ignite - old_ignite
    after, moved = [], []
    for frame, value in before:
        if frame < old_ignite:
            after.append([frame, value])
            continue
        new_frame = frame + delta
        envelope = max(0.0, min(1.0, float(new_frame - common_ignite) / float(ramp_frames)))
        new_value = value * envelope
        after.append([new_frame, new_value])
        moved.append({"old_frame": frame, "new_frame": new_frame, "old_value": value,
                      "new_value": new_value, "envelope": envelope})
    after = _normalise_keys(after)
    if after[0][0] < 0:
        raise PlanError("FIRE_SHIFT_BEFORE_ZERO")
    return {"before": before, "after": after, "moved": moved, "delta": delta}


def visibility_key_plan(keys, old_ignite, common_ignite):
    before = _normalise_keys(keys, boolean=True)
    shown = [f for f, value in before if value]
    if shown != [int(old_ignite)]:
        raise PlanError("VISIBILITY_IGNITION_KEYS|got=%r|want=%r" % (shown, [int(old_ignite)]))
    after, moved = [], []
    for frame, value in before:
        new_frame = int(common_ignite) if value else frame
        after.append([new_frame, value])
        if new_frame != frame:
            moved.append({"old_frame": frame, "new_frame": new_frame, "value": value})
    return {"before": before, "after": _normalise_keys(after, boolean=True), "moved": moved}


def linear_value(keys, frame):
    rows = _normalise_keys(keys)
    frame = int(frame)
    if frame <= rows[0][0]:
        return rows[0][1]
    if frame >= rows[-1][0]:
        return rows[-1][1]
    for (fa, va), (fb, vb) in zip(rows, rows[1:]):
        if fa <= frame <= fb:
            if fb == fa:
                return vb
            alpha = float(frame - fa) / float(fb - fa)
            return va + (vb - va) * alpha
    raise PlanError("INTERPOLATION_RANGE")


def b11_dim_plan(keys, start, end, factor, ramp_frames):
    """Dim only [start,end), restoring the original curve at end."""
    before = _normalise_keys(keys)
    start, end, ramp_frames, factor = int(start), int(end), int(ramp_frames), float(factor)
    if not (start < start + ramp_frames < end):
        raise PlanError("B11_RAMP_OUTSIDE_CUT")
    by_frame = {f: v for f, v in before}
    for frame in (start, start + ramp_frames, end):
        by_frame.setdefault(frame, linear_value(before, frame))
    after, changed = [], []
    for frame in sorted(by_frame):
        old = by_frame[frame]
        if start <= frame < end:
            alpha = min(1.0, max(0.0, float(frame - start) / float(ramp_frames)))
            gain = 1.0 + (factor - 1.0) * alpha
        else:
            gain = 1.0
        value = old * gain
        after.append([frame, value])
        if frame not in {r[0] for r in before} or abs(value - old) > 1.0e-12:
            changed.append({"frame": frame, "old_value": old, "new_value": value,
                            "inserted": frame not in {r[0] for r in before}, "gain": gain})
    return {"before": before, "after": after, "changed": changed,
            "range": [start, end], "factor": factor, "ramp_frames": ramp_frames}


def rot_matrix(rpy):
    """UE FRotationMatrix rows (local forward/right/up axes in parent space)."""
    roll, pitch, yaw = [math.radians(float(v)) for v in rpy]
    sr, cr, sp, cp, sy, cy = (math.sin(roll), math.cos(roll), math.sin(pitch),
                              math.cos(pitch), math.sin(yaw), math.cos(yaw))
    return ((cp * cy, cp * sy, sp),
            (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp),
            (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp))


def transform_point(transform, point):
    matrix = rot_matrix(transform["rotation"])
    scaled = [float(point[i]) * float(transform.get("scale", [1, 1, 1])[i]) for i in range(3)]
    return [float(transform["location"][j]) + sum(scaled[i] * matrix[i][j] for i in range(3)) for j in range(3)]


def rank_candidates(camera_pose, positions):
    matrix = rot_matrix(camera_pose["rotation"])
    camera = camera_pose["location"]
    rows = []
    for label, position in positions.items():
        delta = [float(position[i]) - float(camera[i]) for i in range(3)]
        forward, right, up = [sum(delta[j] * matrix[axis][j] for j in range(3)) for axis in range(3)]
        rows.append({"label": label, "world_location": [float(v) for v in position],
                     "camera_forward_cm": forward, "camera_right_cm": right, "camera_up_cm": up,
                     "camera_side": "left" if right < 0 else "right"})
    left = sorted((row for row in rows if row["camera_side"] == "left" and row["camera_forward_cm"] > 0),
                  key=lambda row: row["camera_forward_cm"])
    for index, row in enumerate(left, 1):
        row["left_depth_rank"] = index
    rows.sort(key=lambda row: (row["camera_forward_cm"], row["label"]))
    return rows


def choose_b11_labels(ranking, params):
    if params["b11_dim_labels"]:
        return list(params["b11_dim_labels"]), "args.b11_dim_labels"
    if params["b11_selection"] == "explicit":
        raise PlanError("B11_EXPLICIT_SELECTION_EMPTY")
    left = sorted((row for row in ranking if row.get("left_depth_rank") is not None),
                  key=lambda row: row["left_depth_rank"])
    if len(left) < 2:
        raise PlanError("B11_SECOND_LEFT_UNRESOLVED|left=%r" % [row["label"] for row in left])
    return [left[1]["label"]], "inferred.second_left"


def numeric_diff(expected, actual, path="root", tolerance=1.0e-4):
    """Numeric read-back comparison; deliberately does not hash rounded floats."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return [] if expected is actual else ["%s|%r!=%r" % (path, expected, actual)]
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return [] if abs(float(expected) - float(actual)) <= tolerance else ["%s|%r!=%r" % (path, expected, actual)]
    if type(expected) is not type(actual):
        return ["%s|type %s!=%s" % (path, type(expected).__name__, type(actual).__name__)]
    if isinstance(expected, dict):
        if set(expected) != set(actual):
            return ["%s|keys %r!=%r" % (path, sorted(expected), sorted(actual))]
        out = []
        for key in sorted(expected):
            out += numeric_diff(expected[key], actual[key], "%s.%s" % (path, key), tolerance)
        return out
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return ["%s|len %d!=%d" % (path, len(expected), len(actual))]
        out = []
        for index, (left, right) in enumerate(zip(expected, actual)):
            out += numeric_diff(left, right, "%s[%d]" % (path, index), tolerance)
        return out
    return [] if expected == actual else ["%s|%r!=%r" % (path, expected, actual)]


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    for method in ("get_path_name", "export_text"):
        try:
            return str(getattr(value, method)())
        except Exception:  # noqa: BLE001
            pass
    return str(value)


def _prop(obj, name, default=_MISSING):
    try:
        return obj.get_editor_property(name)
    except Exception:  # noqa: BLE001
        if default is _MISSING:
            raise
        return default


def _guid(value):
    try:
        return str(value.export_text()).upper()
    except Exception:  # noqa: BLE001
        return str(value).upper()


def _track_prop(track):
    try:
        return str(track.get_property_name()), str(track.get_property_path())
    except Exception:  # noqa: BLE001
        return "", ""


def _track_class(track):
    return str(track.get_class().get_name())


def _section_range(section, seq):
    start = int(section.get_start_frame()) if section.has_start_frame() else int(seq.get_playback_start())
    end = int(section.get_end_frame()) if section.has_end_frame() else int(seq.get_playback_end())
    return [start, end]


def _channel_keys(channel, boolean=False):
    ue = _ue()
    out = []
    for key in channel.get_keys():
        time = key.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
        if abs(float(getattr(time, "sub_frame", 0.0) or 0.0)) > 1.0e-6:
            raise PlanError("SUBFRAME_KEY_UNSUPPORTED")
        value = key.get_value()
        out.append([int(time.frame_number.value), bool(value) if boolean else float(value)])
    return _normalise_keys(out, boolean=boolean)


def _replace_channel(channel, rows, boolean=False):
    ue = _ue()
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    for frame, value in rows:
        kwargs = {"time_unit": ue.MovieSceneTimeUnit.DISPLAY_RATE}
        if not boolean:
            kwargs["interpolation"] = ue.MovieSceneKeyInterpolation.LINEAR
        key = channel.add_key(ue.FrameNumber(int(frame)), bool(value) if boolean else float(value), **kwargs)
        if key is None:
            raise PlanError("ADD_KEY_FAILED|%d" % int(frame))


def _json_read(path, required=False):
    if not os.path.exists(path):
        if required:
            raise PlanError("MISSING_JSON|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_write(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, default=str)
        handle.write("\n")


def _saved_root():
    return os.path.normpath(_ue().Paths.convert_relative_path_to_full(_ue().Paths.project_saved_dir()))


def _project_root():
    return os.path.dirname(_saved_root())


def _here():
    return os.path.join(_saved_root(), "CodexConductor", FOLDER)


def _record_path():
    return os.path.join(_here(), RECORD)


def _plan_path():
    return os.path.join(_here(), PLAN)


def _log(message):
    _ue().log(message)


def _stop(run, reason):
    message = "%s_STOPPED|run=%s|reason=%s" % (TOOL, run, reason)
    _ue().log_error(message)
    raise Stop(message)


def _census():
    lib = _ue().EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _actors():
    ue = _ue()
    return list(ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors())


def _actor_tags(actor):
    return sorted(str(value) for value in (_prop(actor, "tags", []) or []))


def _actor_index():
    out = {}
    for actor in _actors():
        out.setdefault(str(actor.get_actor_label()), []).append(actor)
    return out


def _one_actor(index, label, run):
    rows = index.get(label, [])
    if len(rows) != 1:
        _stop(run, "ACTOR_COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def _world_path(world):
    try:
        return str(world.get_outermost().get_name())
    except Exception:  # noqa: BLE001
        return str(world.get_path_name()).split(".")[0]


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
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_CENSUS|%s" % json.dumps(_census(), sort_keys=True))
    if any(str(actor.get_actor_label()).startswith("ZZ_") for actor in _actors()):
        _stop(run, "ZZ_ACTORS_PRESENT")
    return world


def _load_sequence(run):
    seq = _ue().load_asset(SEQ_PATH)
    if seq is None:
        _stop(run, "SEQUENCE_MISSING")
    rate = seq.get_display_rate()
    fps = float(rate.numerator) / float(rate.denominator)
    if abs(fps - 24.0) > 1.0e-6:
        _stop(run, "DISPLAY_RATE|%.9f" % fps)
    return seq


def _binding_rows(seq):
    out = []
    for binding in seq.get_bindings():
        parent = binding.get_parent()
        out.append({"binding": binding, "guid": _guid(binding.get_id()),
                    "name": str(binding.get_display_name()),
                    "parent": str(parent.get_display_name()) if parent is not None and parent.is_valid() else ""})
    return out


def _tracks_for_owner(seq, owner_label, class_name, property_name=None):
    found = []
    for row in _binding_rows(seq):
        if owner_label not in (row["name"], row["parent"]):
            continue
        for track in row["binding"].get_tracks():
            prop, path = _track_prop(track)
            if _track_class(track) == class_name and (property_name is None or prop == property_name):
                found.append((row, track, prop, path))
    return found


def _one_channel(seq, owner_label, class_name, property_name, run):
    tracks = _tracks_for_owner(seq, owner_label, class_name, property_name)
    if len(tracks) != 1:
        _stop(run, "TRACK_COUNT|%s|%s|%s|%d" % (owner_label, class_name, property_name, len(tracks)))
    row, track, prop, path = tracks[0]
    sections = list(track.get_sections())
    if len(sections) != 1:
        _stop(run, "SECTION_COUNT|%s|%d" % (owner_label, len(sections)))
    channels = list(sections[0].get_all_channels())
    if len(channels) != 1:
        _stop(run, "CHANNEL_COUNT|%s|%d" % (owner_label, len(channels)))
    return {"binding": row, "track": track, "section": sections[0], "channel": channels[0],
            "class": class_name, "property": prop, "path": path,
            "display": str(track.get_display_name()), "range": _section_range(sections[0], seq)}


def _visibility_channel(seq, owner_label, run):
    rows = _tracks_for_owner(seq, owner_label, "MovieSceneVisibilityTrack", "bHidden")
    if len(rows) != 1:
        detail = [(str(track.get_display_name()), _track_prop(track)) for _row, track, _p, _q in
                  _tracks_for_owner(seq, owner_label, "MovieSceneVisibilityTrack", None)]
        _stop(run, "VISIBILITY_TRACK_BINDING|%s|want=(bHidden,bHidden)|got=%r" % (owner_label, detail))
    row, track, prop, path = rows[0]
    if path != "bHidden":
        _stop(run, "VISIBILITY_PATH|%s|%s" % (owner_label, path))
    sections = list(track.get_sections())
    if len(sections) != 1 or len(list(sections[0].get_all_channels())) != 1:
        _stop(run, "VISIBILITY_SECTION_CHANNEL|%s" % owner_label)
    return {"binding": row, "track": track, "section": sections[0],
            "channel": list(sections[0].get_all_channels())[0], "class": "MovieSceneVisibilityTrack",
            "property": prop, "path": path, "display": str(track.get_display_name()),
            "range": _section_range(sections[0], seq), "active": bool(sections[0].is_active())}


def _track_snapshot(row, seq, boolean=False):
    return {"owner": row["binding"]["name"], "parent": row["binding"]["parent"],
            "guid": row["binding"]["guid"], "class": row["class"], "property": row["property"],
            "path": row["path"], "display": row["display"], "range": row["range"],
            "active": bool(row["section"].is_active()), "keys": _channel_keys(row["channel"], boolean=boolean)}


def _eval_channel(seq, channel, frame, run, label):
    values = list(channel.evaluate_keys(seq.make_range(int(frame), 1), seq.get_display_rate()))
    if len(values) != 1:
        _stop(run, "EVALUATE_COUNT|%s|frame=%d|got=%d" % (label, frame, len(values)))
    return float(values[0])


def _canonical_transform_channel(channel):
    try:
        raw = str(channel.get_name())
    except Exception:  # noqa: BLE001
        raw = str(getattr(channel, "channel_name", ""))
    for candidate in ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
                      "Scale.X", "Scale.Y", "Scale.Z"):
        if raw == candidate or raw.startswith(candidate + "_"):
            return candidate
    return None


def _camera_cut(seq, run):
    names = {_guid(binding.get_id()): str(binding.get_display_name()) for binding in seq.get_bindings()}
    tracks = list(seq.find_tracks_by_type(_ue().MovieSceneCameraCutTrack))
    if len(tracks) != 1:
        _stop(run, "CAMERA_CUT_TRACK_COUNT|%d" % len(tracks))
    found = []
    for section in tracks[0].get_sections():
        binding_id = section.get_camera_binding_id()
        guid = _guid(_prop(binding_id, "guid", binding_id))
        row = {"range": _section_range(section, seq), "camera": names.get(guid, guid),
               "guid": guid, "active": bool(section.is_active())}
        if row["camera"] == B11_CAMERA:
            found.append(row)
    if len(found) != 1 or found[0]["range"] != list(B11_RANGE) or not found[0]["active"]:
        _stop(run, "B11_CUT|%r" % found)
    return found[0]


def _binding_transform_pose(seq, binding_name, frame, run):
    rows = [row for row in _binding_rows(seq) if row["name"] == binding_name]
    if len(rows) != 1:
        _stop(run, "BINDING_COUNT|%s|%d" % (binding_name, len(rows)))
    tracks = []
    for track in rows[0]["binding"].get_tracks():
        prop, path = _track_prop(track)
        if _track_class(track) == "MovieScene3DTransformTrack" and prop == "Transform":
            tracks.append((track, path))
    if len(tracks) != 1:
        _stop(run, "TRANSFORM_TRACK_COUNT|%s|%d" % (binding_name, len(tracks)))
    sections = list(tracks[0][0].get_sections())
    if len(sections) != 1:
        _stop(run, "TRANSFORM_SECTION_COUNT|%s|%d" % (binding_name, len(sections)))
    channels = {}
    for channel in sections[0].get_all_channels():
        name = _canonical_transform_channel(channel)
        if name is not None:
            if name in channels:
                _stop(run, "DUPLICATE_TRANSFORM_CHANNEL|%s|%s" % (binding_name, name))
            channels[name] = channel
    required = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z")
    if any(name not in channels for name in required):
        _stop(run, "TRANSFORM_CHANNELS|%s|%r" % (binding_name, sorted(channels)))
    values = {name: _eval_channel(seq, channels[name], frame, run, "%s.%s" % (binding_name, name)) for name in required}
    scale = [_eval_channel(seq, channels[name], frame, run, "%s.%s" % (binding_name, name))
             if name in channels else 1.0 for name in ("Scale.X", "Scale.Y", "Scale.Z")]
    return {"binding": binding_name, "frame": int(frame),
            "location": [values["Location.X"], values["Location.Y"], values["Location.Z"]],
            "rotation": [values["Rotation.X"], values["Rotation.Y"], values["Rotation.Z"]],
            "scale": scale, "source": "%s transform channels evaluated over make_range(frame,1)" % seq.get_path_name()}


def _actor_transform(actor, relative=False):
    if relative:
        root = actor.get_editor_property("root_component")
        loc = _prop(root, "relative_location")
        rot = _prop(root, "relative_rotation")
        scale = _prop(root, "relative_scale3d")
    else:
        loc, rot, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
    return {"location": [float(loc.x), float(loc.y), float(loc.z)],
            "rotation": [float(rot.roll), float(rot.pitch), float(rot.yaw)],
            "scale": [float(scale.x), float(scale.y), float(scale.z)]}


def _b11_light_positions(seq, index, labels, frame, run):
    out, detail = {}, {}
    for label in labels:
        actor = _one_actor(index, label, run)
        parent = actor.get_attach_parent_actor()
        relative = _actor_transform(actor, relative=True)
        if parent is not None:
            parent_label = str(parent.get_actor_label())
            parent_seq = seq
            direct = [row for row in _binding_rows(seq) if row["name"] == parent_label and
                      any(_track_class(track) == "MovieScene3DTransformTrack" and _track_prop(track)[0] == "Transform"
                          for track in row["binding"].get_tracks())]
            if not direct and parent_label == "S3 Hangar Root":
                parent_seq = _ue().load_asset(RISE_PATH)
                if parent_seq is None:
                    _stop(run, "RISE_SEQUENCE_MISSING|%s" % RISE_PATH)
            parent_pose = _binding_transform_pose(parent_seq, parent_label, frame, run)
            world = transform_point(parent_pose, relative["location"])
            source = "parent sequence pose + actor relative transform"
            detail[label] = {"parent": parent_label, "relative": relative, "parent_pose": parent_pose, "source": source}
        else:
            world = _actor_transform(actor)["location"]
            detail[label] = {"parent": None, "relative": relative, "source": "unattached actor world transform"}
        out[label] = world
    return out, detail


def _shadow_state(component):
    supported, unsupported = {}, []
    for name in SHADOW_READ_PROPS:
        try:
            value = component.get_editor_property(name)
        except Exception:  # noqa: BLE001 - capability census is the point
            unsupported.append(name)
            continue
        supported[name] = _plain(value)
    return {"supported": supported, "unsupported": unsupported}


def _dune_state(index, run):
    matches = [actor for rows in index.values() for actor in rows if DUNE_TAG in _actor_tags(actor)]
    if len(matches) != 1 or _track_class(matches[0]) != "StaticMeshActor":
        kinds = [str(actor.get_class().get_name()) for actor in matches]
        _stop(run, "DUNE_COUNT_OR_CLASS|count=%d|classes=%r" % (len(matches), kinds))
    actor = matches[0]
    comps = list(actor.get_components_by_class(_ue().StaticMeshComponent))
    if len(comps) != 1:
        _stop(run, "DUNE_MESH_COMPONENT_COUNT|%d" % len(comps))
    return actor, comps[0], {"label": str(actor.get_actor_label()), "path": str(actor.get_path_name()),
                             "class": str(actor.get_class().get_name()), "tag": DUNE_TAG,
                             "shadow": _shadow_state(comps[0])}


def _niagara_user_parameters(system):
    """Best-effort UE 5.8 inventory with explicit evidence about the API used."""
    report = {"method": None, "parameters": [], "raw": None, "errors": []}
    store = None
    for source, getter in (("get_exposed_parameters", lambda: system.get_exposed_parameters()),
                           ("editor_property.exposed_parameters", lambda: system.get_editor_property("exposed_parameters"))):
        try:
            store = getter()
            report["method"] = source
            break
        except Exception as exc:  # noqa: BLE001
            report["errors"].append("%s:%s" % (source, exc))
    if store is None:
        report["method"] = "unavailable"
        return report
    for method in ("get_user_parameters", "get_parameters", "get_parameter_names"):
        if not hasattr(store, method):
            continue
        try:
            values = list(getattr(store, method)())
            report["method"] += "." + method
            report["parameters"] = [_plain(value) for value in values]
            break
        except Exception as exc:  # noqa: BLE001
            report["errors"].append("%s:%s" % (method, exc))
    try:
        report["raw"] = str(store.export_text())
    except Exception as exc:  # noqa: BLE001
        report["errors"].append("export_text:%s" % exc)
        report["raw"] = str(store)
    return report


def _stylish_assets(params, run):
    ue = _ue()
    out = {}
    for emitter, path in params["stylish_systems"].items():
        asset = ue.load_asset(path)
        if asset is None or not isinstance(asset, ue.NiagaraSystem):
            _stop(run, "STYLISH_ASSET|%s|%s" % (emitter, path))
        out[emitter] = {"path": path, "class": str(asset.get_class().get_name()),
                        "user_parameters": _niagara_user_parameters(asset)}
    return out


def _stylish_actors():
    return [actor for actor in _actors() if STYLISH_TAG in _actor_tags(actor)]


def _bound_actor_bindings(seq, actor, world):
    found, has_api = {}, False
    if hasattr(seq, "find_binding_from_object"):
        has_api = True
        try:
            binding = seq.find_binding_from_object(actor, world)
            if binding is not None and binding.is_valid():
                found[_guid(binding.get_id())] = binding
        except Exception:  # noqa: BLE001
            pass
    if hasattr(seq, "locate_bound_objects"):
        has_api = True
        for binding in seq.get_bindings():
            try:
                if any(obj is actor or str(obj.get_path_name()) == str(actor.get_path_name())
                       for obj in seq.locate_bound_objects(binding, world)):
                    found[_guid(binding.get_id())] = binding
            except Exception:  # noqa: BLE001
                pass
    if not has_api:
        raise PlanError("BINDING_LOOKUP_API_UNAVAILABLE")
    return list(found.values())


def _protected_sequence(seq, target_labels):
    rows = []
    for binding in _binding_rows(seq):
        if binding["name"].endswith(" Stylish") or binding["parent"].endswith(" Stylish"):
            continue
        for track in binding["binding"].get_tracks():
            cls = _track_class(track)
            prop, path = _track_prop(track)
            owner = binding["parent"] or binding["name"]
            if owner in target_labels and ((cls == "MovieSceneFloatTrack" and prop == "Intensity") or
                                           (cls == "MovieSceneVisibilityTrack" and prop == "bHidden")):
                continue
            sections = []
            for section in track.get_sections():
                channels = []
                for channel in section.get_all_channels():
                    try:
                        channels.append(_channel_keys(channel, boolean=cls == "MovieSceneVisibilityTrack"))
                    except Exception:  # noqa: BLE001
                        channels.append({"count": int(channel.get_num_keys())})
                sections.append({"range": _section_range(section, seq), "active": bool(section.is_active()),
                                 "channels": channels})
            rows.append({"binding": binding["name"], "parent": binding["parent"], "guid": binding["guid"],
                         "class": cls, "property": prop, "path": path, "display": str(track.get_display_name()),
                         "sections": sections})
    master = []
    for track in seq.get_tracks():
        master.append({"class": _track_class(track), "display": str(track.get_display_name()),
                       "sections": [_section_range(section, seq) for section in track.get_sections()]})
    markers = []
    for marker in seq.get_marked_frames():
        markers.append([str(_prop(marker, "label", "")), int(_prop(marker, "frame_number").value)])
    return {"bindings_tracks": sorted(rows, key=lambda row: json.dumps(row, sort_keys=True)),
            "master": master, "markers": sorted(markers)}


def _target_state(seq, world, params, parts, run):
    index = _actor_index()
    state = {"parts": list(parts)}
    target_labels = set()
    if "fires_together" in parts:
        fires = {}
        for light, emitter in zip(FIRE_LIGHTS, FIRE_EMITTERS):
            intensity = _one_channel(seq, light, "MovieSceneFloatTrack", "Intensity", run)
            visibility = _visibility_channel(seq, emitter, run)
            fires[light] = {"emitter": emitter, "intensity": _track_snapshot(intensity, seq),
                            "visibility": _track_snapshot(visibility, seq, boolean=True)}
            target_labels.update((light, emitter))
        state["fires"] = fires
    if "b11_dim" in parts:
        cut = _camera_cut(seq, run)
        camera = _binding_transform_pose(seq, cut["camera"], cut["range"][0], run)
        positions, position_detail = _b11_light_positions(seq, index, params["b11_candidate_labels"], cut["range"][0], run)
        ranking = rank_candidates(camera, positions)
        chosen, source = choose_b11_labels(ranking, params)
        waves = {}
        for label in chosen:
            channel = _one_channel(seq, label, "MovieSceneFloatTrack", "Intensity", run)
            waves[label] = _track_snapshot(channel, seq)
            target_labels.add(label)
        state["b11"] = {"cut": cut, "camera_pose": camera, "candidate_positions": position_detail,
                        "ranking": ranking, "chosen": chosen, "choice_source": source, "waves": waves}
    if "dune_shadow" in parts:
        _actor, _component, dune = _dune_state(index, run)
        state["dune"] = dune
    if "stylish_fire" in parts:
        originals = {}
        for label in ALL_EMITTERS:
            actor = _one_actor(index, label, run)
            component = actor.get_component_by_class(_ue().ParticleSystemComponent)
            if component is None:
                _stop(run, "P_FIRE_COMPONENT|%s" % label)
            template = _prop(component, "template", None)
            template_path = str(template.get_path_name()).split(".")[0] if template else None
            if template_path != P_FIRE:
                _stop(run, "P_FIRE_TEMPLATE|%s|%s" % (label, template_path))
            visibility = _visibility_channel(seq, label, run)
            originals[label] = {"path": str(actor.get_path_name()), "transform": _actor_transform(actor),
                                "hidden": bool(_prop(actor, "hidden")),
                                "template": template_path,
                                "visibility": _track_snapshot(visibility, seq, boolean=True)}
            target_labels.add(label)
        styled = []
        for actor in _stylish_actors():
            component = actor.get_component_by_class(_ue().NiagaraComponent)
            asset = component.get_asset() if component is not None else None
            label = str(actor.get_actor_label())
            visibility = _track_snapshot(_visibility_channel(seq, label, run), seq, boolean=True)
            styled.append({"label": str(actor.get_actor_label()), "path": str(actor.get_path_name()),
                           "tags": _actor_tags(actor), "transform": _actor_transform(actor),
                           "hidden": bool(_prop(actor, "hidden")),
                           "asset": str(asset.get_path_name()).split(".")[0] if asset else None,
                           "visibility": visibility})
        state["stylish"] = {"apply_enabled": params["stylish_apply"], "originals": originals,
                            "assets": _stylish_assets(params, run), "created": sorted(styled, key=lambda row: row["label"])}
    state["protected_sequence"] = _protected_sequence(seq, target_labels)
    return state


def _build_plan(state, params, parts):
    plan = {"parts": list(parts), "params": params, "claims": CLAIMS, "mutating_parts": []}
    if "fires_together" in parts:
        rows = {}
        for light, item in state["fires"].items():
            old = [f for f, value in item["visibility"]["keys"] if value]
            if len(old) != 1:
                raise PlanError("FIRE_VIS_IGNITION|%s|%r" % (light, old))
            intensity = fire_key_plan(item["intensity"]["keys"], old[0], params["common_ignite_frame"],
                                      params["fire_ramp_frames"])
            visibility = visibility_key_plan(item["visibility"]["keys"], old[0], params["common_ignite_frame"])
            rows[light] = {"emitter": item["emitter"], "old_ignite": old[0], "intensity": intensity,
                           "visibility": visibility}
        plan["fires_together"] = rows
        plan["mutating_parts"].append("fires_together")
    if "b11_dim" in parts:
        waves = {}
        for label, item in state["b11"]["waves"].items():
            waves[label] = b11_dim_plan(item["keys"], state["b11"]["cut"]["range"][0],
                                        state["b11"]["cut"]["range"][1], params["b11_factor"],
                                        params["b11_ramp_frames"])
        plan["b11_dim"] = {"cut": state["b11"]["cut"], "camera_pose": state["b11"]["camera_pose"],
                           "ranking": state["b11"]["ranking"], "chosen": state["b11"]["chosen"],
                           "choice_source": state["b11"]["choice_source"], "waves": waves}
        plan["mutating_parts"].append("b11_dim")
    if "dune_shadow" in parts:
        supported = state["dune"]["shadow"]["supported"]
        before = {name: supported.get(name) for name in ("cast_shadow", "cast_dynamic_shadow")}
        if before["cast_shadow"] is None or before["cast_dynamic_shadow"] is None:
            raise PlanError("DUNE_REQUIRED_SHADOW_PROPERTY_UNSUPPORTED|%r" % before)
        plan["dune_shadow"] = {"before": before, "after": {"cast_shadow": True, "cast_dynamic_shadow": True},
                               "vsm_report": state["dune"]["shadow"]}
        if before != {"cast_shadow": True, "cast_dynamic_shadow": True}:
            plan["mutating_parts"].append("dune_shadow")
    if "stylish_fire" in parts:
        stylish = {"apply_enabled": params["stylish_apply"], "assets": state["stylish"]["assets"],
                   "swaps": []}
        for label in ALL_EMITTERS:
            stylish["swaps"].append({"old_label": label, "new_label": label + " Stylish",
                                     "system": params["stylish_systems"][label],
                                     "transform": state["stylish"]["originals"][label]["transform"],
                                     "old_hidden": state["stylish"]["originals"][label]["hidden"],
                                     "visibility": state["stylish"]["originals"][label]["visibility"],
                                     "old_kept_hidden": True})
        plan["stylish_fire"] = stylish
        if params["stylish_apply"]:
            if state["stylish"]["created"]:
                raise PlanError("STYLISH_ACTORS_ALREADY_EXIST")
            plan["mutating_parts"].append("stylish_fire")
    return plan


def build_report(seq, world, params, parts, run):
    state = _target_state(seq, world, params, parts, run)
    plan = _build_plan(state, params, parts)
    return {"schema_version": 1, "tool_version": TOOL_VERSION, "run": run, "mode": "DRY",
            "map": MAP_PATH, "sequence": SEQ_PATH, "parts": list(parts), "params": params,
            "state_before": state, "plan": plan,
            "input_digest": digest({"parts": parts, "params": params}), "claims": CLAIMS}


def _plan_state_problems(state, plan, params):
    """Compare live numeric read-back to the authored plan, not to a hash."""
    problems = []
    if "fires_together" in plan["mutating_parts"]:
        for light, wanted in plan["fires_together"].items():
            got = state["fires"][light]
            problems += ["FIRES.%s.%s" % (light, diff) for diff in
                         numeric_diff(wanted["intensity"]["after"], got["intensity"]["keys"],
                                      tolerance=params["float_tolerance"])]
            problems += ["FIRES.%s.VIS.%s" % (light, diff) for diff in
                         numeric_diff(wanted["visibility"]["after"], got["visibility"]["keys"],
                                      tolerance=params["float_tolerance"])]
    if "b11_dim" in plan["mutating_parts"]:
        for label, wanted in plan["b11_dim"]["waves"].items():
            problems += ["B11.%s.%s" % (label, diff) for diff in
                         numeric_diff(wanted["after"], state["b11"]["waves"][label]["keys"],
                                      tolerance=params["float_tolerance"])]
    if "dune_shadow" in plan["mutating_parts"]:
        got = state["dune"]["shadow"]["supported"]
        for name in ("cast_shadow", "cast_dynamic_shadow"):
            if got.get(name) is not True:
                problems.append("DUNE.%s|%r" % (name, got.get(name)))
    if "stylish_fire" in plan["mutating_parts"]:
        created = {row["label"]: row for row in state["stylish"]["created"]}
        if set(created) != {row["new_label"] for row in plan["stylish_fire"]["swaps"]}:
            problems.append("STYLISH_LABELS|%r" % sorted(created))
        for swap in plan["stylish_fire"]["swaps"]:
            old = state["stylish"]["originals"][swap["old_label"]]
            new = created.get(swap["new_label"])
            if old["hidden"] is not True:
                problems.append("STYLISH_OLD_NOT_HIDDEN|%s" % swap["old_label"])
            if old["visibility"]["active"] is not False:
                problems.append("STYLISH_OLD_VISIBILITY_ACTIVE|%s" % swap["old_label"])
            if new is None:
                continue
            if new["asset"] != swap["system"]:
                problems.append("STYLISH_ASSET|%s|%s" % (swap["new_label"], new["asset"]))
            for key, tolerance in (("location", params["location_tolerance_cm"]),
                                   ("rotation", params["rotation_tolerance_deg"]),
                                   ("scale", params["float_tolerance"])):
                problems += ["STYLISH_TRANSFORM.%s.%s.%s" % (swap["new_label"], key, diff) for diff in
                             numeric_diff(swap["transform"][key], new["transform"][key], tolerance=tolerance)]
            if new["hidden"] is not bool(swap["old_hidden"]):
                problems.append("STYLISH_NEW_HIDDEN|%s|%r" % (swap["new_label"], new["hidden"]))
            wanted_vis = swap["visibility"]
            got_vis = new["visibility"]
            for key in ("class", "property", "path", "range", "active", "keys"):
                problems += ["STYLISH_VIS.%s.%s.%s" % (swap["new_label"], key, diff) for diff in
                             numeric_diff(wanted_vis[key], got_vis[key], tolerance=params["float_tolerance"])]
    return problems


def _sha(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _backup(run, packages, suffix=""):
    label = "S3Polish" + suffix
    root = os.path.join(_project_root(), "Backups", "Pre%s-%s" % (label, run))
    os.makedirs(root, exist_ok=False)
    mapping = {MAP_PATH: (os.path.join(_project_root(), "Content", MAP_FILE), os.path.basename(MAP_FILE)),
               SEQ_PATH: (os.path.join(_project_root(), "Content", SEQ_FILE), os.path.basename(SEQ_FILE))}
    rows = []
    for package in packages:
        source, name = mapping[package]
        if not os.path.isfile(source):
            _stop(run, "BACKUP_SOURCE_MISSING|%s" % source)
        target = os.path.join(root, name)
        shutil.copy2(source, target)
        if _sha(source) != _sha(target):
            _stop(run, "BACKUP_VERIFY_FAILED|%s" % package)
        rows.append({"package": package, "source": source, "backup": target, "sha256": _sha(target)})
    return {"root": root, "files": rows}


def _packages_for_plan(plan):
    parts = set(plan["mutating_parts"])
    packages = []
    if parts & {"fires_together", "b11_dim", "stylish_fire"}:
        packages.append(SEQ_PATH)
    if parts & {"dune_shadow", "stylish_fire"}:
        packages.append(MAP_PATH)
    return packages


def _expected_census(packages):
    return {"content": [SEQ_PATH] if SEQ_PATH in packages else [],
            "maps": [MAP_PATH] if MAP_PATH in packages else []}


def _save_targets(world, packages, run):
    expected = _expected_census(packages)
    if _census() != expected:
        _stop(run, "UNEXPECTED_DIRTY_PACKAGES|live=%s|expected=%s|NOTHING SAVED; Don't-Save restart" %
              (json.dumps(_census(), sort_keys=True), json.dumps(expected, sort_keys=True)))
    saves = []
    if SEQ_PATH in packages:
        if not bool(_ue().EditorAssetLibrary.save_asset(SEQ_PATH, only_if_is_dirty=True)):
            _stop(run, "SAVE_FAILED|%s" % SEQ_PATH)
        saves.append(SEQ_PATH)
        remaining = {"content": [], "maps": [MAP_PATH] if MAP_PATH in packages else []}
        if _census() != remaining:
            _stop(run, "DIRTY_AFTER_SEQUENCE_SAVE|%s" % json.dumps(_census(), sort_keys=True))
    if MAP_PATH in packages:
        if not bool(_ue().EditorLoadingAndSavingUtils.save_map(world, MAP_PATH)):
            _stop(run, "SAVE_FAILED|%s" % MAP_PATH)
        saves.append(MAP_PATH)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census(), sort_keys=True))
    return saves


def _find_row_channel(seq, snapshot, run):
    owner = snapshot["parent"] or snapshot["owner"]
    if snapshot["class"] == "MovieSceneVisibilityTrack":
        return _visibility_channel(seq, owner, run)
    return _one_channel(seq, owner, snapshot["class"], snapshot["property"], run)


def _apply_fires(seq, plan, record, run):
    changes = []
    for light, item in plan.items():
        intensity = _one_channel(seq, light, "MovieSceneFloatTrack", "Intensity", run)
        visibility = _visibility_channel(seq, item["emitter"], run)
        _replace_channel(intensity["channel"], item["intensity"]["after"])
        _replace_channel(visibility["channel"], item["visibility"]["after"], boolean=True)
        changes.append({"light": light, "emitter": item["emitter"],
                        "intensity_moved": item["intensity"]["moved"],
                        "visibility_moved": item["visibility"]["moved"]})
    record["fires_changes"] = changes


def _apply_b11(seq, plan, record, run):
    changes = []
    for label, item in plan["waves"].items():
        channel = _one_channel(seq, label, "MovieSceneFloatTrack", "Intensity", run)
        _replace_channel(channel["channel"], item["after"])
        changes.append({"label": label, "changed": item["changed"]})
    record["b11_changes"] = changes


def _apply_dune(index, plan, record, run):
    actor, component, state = _dune_state(index, run)
    record["dune_before"] = state
    actor.modify()
    component.modify()
    component.set_cast_shadow(True)
    component.set_editor_property("cast_dynamic_shadow", True)


def _new_visibility_track(binding, source, seq, run):
    ue = _ue()
    track = binding.add_track(ue.MovieSceneVisibilityTrack)
    if track is None:
        _stop(run, "ADD_VISIBILITY_TRACK|NOTHING SAVED; Don't-Save restart")
    track.set_property_name_and_path("bHidden", "bHidden")
    prop, path = _track_prop(track)
    if (prop, path) != ("bHidden", "bHidden"):
        _stop(run, "NEW_VISIBILITY_BINDING|%r|NOTHING SAVED; Don't-Save restart" % ((prop, path),))
    section = track.add_section()
    section.set_range(int(source["range"][0]), int(source["range"][1]))
    section.set_is_active(bool(source["active"]))
    channels = list(section.get_all_channels())
    if len(channels) != 1:
        _stop(run, "NEW_VISIBILITY_CHANNELS|%d" % len(channels))
    _replace_channel(channels[0], source["keys"], boolean=True)
    return track, section


def _spawn_stylish(seq, world, index, params, record, run):
    ue = _ue()
    subsystem = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    created = []
    for old_label in ALL_EMITTERS:
        old = _one_actor(index, old_label, run)
        old_visibility = _visibility_channel(seq, old_label, run)
        source_vis = _track_snapshot(old_visibility, seq, boolean=True)
        system_path = params["stylish_systems"][old_label]
        system = ue.load_asset(system_path)
        before_guids = {_guid(binding.get_id()) for binding in seq.get_bindings()}
        actor = subsystem.spawn_actor_from_class(ue.NiagaraActor, old.get_actor_location(), old.get_actor_rotation(), False)
        if actor is None:
            _stop(run, "SPAWN_NIAGARA|%s|NOTHING SAVED; Don't-Save restart" % old_label)
        actor.set_actor_label(old_label + " Stylish")
        actor.set_editor_property("tags", [ue.Name(STYLISH_TAG), ue.Name("S3Fire")])
        actor.set_folder_path(STYLISH_FOLDER)
        actor.set_actor_scale3d(old.get_actor_scale3d())
        parent = old.get_attach_parent_actor()
        if parent is not None:
            actor.attach_to_actor(parent, "", ue.AttachmentRule.KEEP_WORLD, ue.AttachmentRule.KEEP_WORLD,
                                  ue.AttachmentRule.KEEP_WORLD, False)
        component = actor.get_component_by_class(ue.NiagaraComponent)
        if component is None:
            _stop(run, "NIAGARA_COMPONENT|%s|NOTHING SAVED; Don't-Save restart" % old_label)
        component.set_asset(system)
        # Rule 9: look up before add_possessable; never rename a returned-existing binding.
        matches = _bound_actor_bindings(seq, actor, world)
        if len(matches) > 1:
            _stop(run, "STYLISH_BINDING_COUNT|%s|%d" % (old_label, len(matches)))
        binding = matches[0] if matches else seq.add_possessable(actor)
        if binding is None or not binding.is_valid():
            _stop(run, "STYLISH_BINDING|%s" % old_label)
        guid = _guid(binding.get_id())
        binding_created = guid not in before_guids
        if binding_created:
            binding.set_display_name(old_label + " Stylish")
        _new_visibility_track(binding, source_vis, seq, run)
        old_hidden = bool(_prop(old, "hidden"))
        actor.set_actor_hidden_in_game(old_hidden)
        old.modify()
        old.set_actor_hidden_in_game(True)
        old_visibility["section"].set_is_active(False)
        created.append({"old_label": old_label, "old_hidden": old_hidden,
                        "old_visibility_active": source_vis["active"],
                        "new_label": old_label + " Stylish", "new_path": str(actor.get_path_name()),
                        "binding_guid": guid, "binding_created": binding_created, "system": system_path})
    record["stylish_created"] = created


def _restore_channel(seq, snapshot, run):
    row = _find_row_channel(seq, snapshot, run)
    _replace_channel(row["channel"], snapshot["keys"], boolean=snapshot["class"] == "MovieSceneVisibilityTrack")
    row["section"].set_is_active(bool(snapshot["active"]))


def _remove_stylish(seq, world, record, run):
    ue = _ue()
    bindings = {_guid(binding.get_id()): binding for binding in seq.get_bindings()}
    actors = {str(actor.get_actor_label()): actor for actor in _stylish_actors()}
    originals = _actor_index()
    subsystem = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    for row in record.get("stylish_created", []):
        binding = bindings.get(row["binding_guid"])
        if row["binding_created"]:
            if binding is None or str(binding.get_display_name()) != row["new_label"]:
                _stop(run, "REFUSE_REMOVE_STYLISH_BINDING|%s" % row["new_label"])
            binding.remove()
        actor = actors.get(row["new_label"])
        if actor is None or STYLISH_TAG not in _actor_tags(actor):
            _stop(run, "REFUSE_DESTROY_STYLISH|%s" % row["new_label"])
        if not bool(subsystem.destroy_actor(actor)):
            _stop(run, "DESTROY_STYLISH_FAILED|%s" % row["new_label"])
        old = _one_actor(originals, row["old_label"], run)
        old.modify()
        old.set_actor_hidden_in_game(bool(row["old_hidden"]))
        old_visibility = _visibility_channel(seq, row["old_label"], run)
        old_visibility["section"].set_is_active(bool(row["old_visibility_active"]))


def _restore_dune(index, record, run):
    actor, component, _state = _dune_state(index, run)
    old = record["dune_before"]["shadow"]["supported"]
    actor.modify()
    component.modify()
    component.set_cast_shadow(bool(old["cast_shadow"]))
    component.set_editor_property("cast_dynamic_shadow", bool(old["cast_dynamic_shadow"]))


def _post_state(params, parts, run, world):
    return _target_state(_load_sequence(run), world, params, parts, run)


def run_dry(run, params, parts, confirm):
    world = _preflight("DRY", run, confirm)
    report = build_report(_load_sequence(run), world, params, parts, run)
    report_path = os.path.join(_here(), "s3_polish_dry_%s.json" % run)
    _json_write(report_path, report)
    _json_write(_plan_path(), {"run": run, "parts": parts, "params": params,
                               "input_digest": report["input_digest"], "state_before": report["state_before"],
                               "plan": report["plan"], "report": report_path})
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % json.dumps(_census(), sort_keys=True))
    b11 = report["plan"].get("b11_dim", {})
    stylish = report["plan"].get("stylish_fire", {})
    _log("%s_DRY_OK|run=%s|mutated=0|parts=%s|mutating=%s|b11_choice=%s|choice_source=%s|"
         "stylish_apply=%d|report=%s" %
         (TOOL, run, ",".join(parts), ",".join(report["plan"]["mutating_parts"]),
          ",".join(b11.get("chosen", [])), b11.get("choice_source", "n/a"),
          int(bool(stylish.get("apply_enabled", False))), report_path))
    return report


def _require_dry(report, run):
    dry = _json_read(_plan_path(), required=True)
    if dry.get("input_digest") != report["input_digest"]:
        _stop(run, "ARGS_OR_PARTS_CHANGED_SINCE_DRY|rerun DRY")
    differences = numeric_diff(dry.get("state_before"), report["state_before"], tolerance=report["params"]["float_tolerance"])
    if differences:
        _stop(run, "STATE_CHANGED_SINCE_DRY|rerun DRY|%s" % json.dumps(differences[:20]))
    return dry


def run_apply(run, params, parts, confirm):
    world = _preflight("APPLY", run, confirm)
    if os.path.exists(_record_path()):
        _stop(run, "RECORD_EXISTS|REVERT first|%s" % _record_path())
    seq = _load_sequence(run)
    report = build_report(seq, world, params, parts, run)
    dry = _require_dry(report, run)
    packages = _packages_for_plan(report["plan"])
    if not packages:
        _stop(run, "NO_MUTATING_PARTS|stylish_fire is DRY-only unless stylish_apply=true")
    backup = _backup(run, packages)
    record = {"schema_version": 1, "tool_version": TOOL_VERSION, "run": run, "applied": False,
              "parts": parts, "params": params, "packages": packages, "backup": backup, "dry": dry,
              "state_before": report["state_before"], "plan": report["plan"]}
    try:
        _json_write(_record_path(), record, exclusive=True)
    except FileExistsError:
        _stop(run, "RECORD_EXISTS|nothing mutated")
    if SEQ_PATH in packages:
        seq.modify()
    if "fires_together" in report["plan"]["mutating_parts"]:
        _apply_fires(seq, report["plan"]["fires_together"], record, run)
    if "b11_dim" in report["plan"]["mutating_parts"]:
        _apply_b11(seq, report["plan"]["b11_dim"], record, run)
    if "dune_shadow" in report["plan"]["mutating_parts"]:
        _apply_dune(_actor_index(), report["plan"]["dune_shadow"], record, run)
    if "stylish_fire" in report["plan"]["mutating_parts"]:
        _spawn_stylish(seq, world, _actor_index(), params, record, run)
    _json_write(_record_path(), record)
    expected_state = _target_state(seq, world, params, parts, run)
    presave_problems = _plan_state_problems(expected_state, report["plan"], params)
    if expected_state["protected_sequence"] != report["state_before"]["protected_sequence"]:
        presave_problems.append("PROTECTED_SEQUENCE_CHANGED")
    if presave_problems:
        _stop(run, "PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
              (json.dumps(presave_problems[:20]), backup["root"]))
    saves = _save_targets(world, packages, run)
    readback = _post_state(params, parts, run, world)
    problems = _plan_state_problems(readback, report["plan"], params)
    problems += numeric_diff(expected_state, readback, tolerance=params["float_tolerance"])
    if problems or _census() != {"content": [], "maps": []}:
        _stop(run, "POSTSAVE_READBACK|%s|census=%s|restore=%s" %
              (json.dumps(problems[:20]), json.dumps(_census(), sort_keys=True), backup["root"]))
    record.update({"applied": True, "state_after": readback, "saves": saves, "census_after": _census()})
    _json_write(_record_path(), record)
    _log("%s_APPLY_OK|run=%s|parts=%s|saved=%s|backup=%s|record=%s" %
         (TOOL, run, ",".join(report["plan"]["mutating_parts"]), ",".join(saves), backup["root"], _record_path()))
    return record


def run_revert(run, params_unused, parts_unused, confirm):
    del params_unused, parts_unused
    world = _preflight("REVERT", run, confirm)
    record = _json_read(_record_path(), required=True)
    if not record.get("applied") or record.get("tool_version") != TOOL_VERSION:
        _stop(run, "REVERT_RECORD_CONTEXT")
    params, parts = merged_params(record["params"]), selected_parts(record["parts"])
    live = _post_state(params, parts, run, world)
    drift = numeric_diff(record["state_after"], live, tolerance=params["float_tolerance"])
    if drift:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%s|backup=%s" % (json.dumps(drift[:20]), record["backup"]["root"]))
    backup = _backup(run, record["packages"], suffix="Revert")
    txn = os.path.join(_here(), "s3_polish_revert_%s.json" % run)
    _json_write(txn, {"run": run, "completed": False, "backup": backup,
                      "source_record": _record_path(), "state_before_revert": live}, exclusive=True)
    seq = _load_sequence(run)
    if SEQ_PATH in record["packages"]:
        seq.modify()
    before = record["state_before"]
    if "fires_together" in record["plan"]["mutating_parts"]:
        for item in before["fires"].values():
            _restore_channel(seq, item["intensity"], run)
            _restore_channel(seq, item["visibility"], run)
    if "b11_dim" in record["plan"]["mutating_parts"]:
        for item in before["b11"]["waves"].values():
            _restore_channel(seq, item, run)
    if "stylish_fire" in record["plan"]["mutating_parts"]:
        _remove_stylish(seq, world, record, run)
    if "dune_shadow" in record["plan"]["mutating_parts"]:
        _restore_dune(_actor_index(), record, run)
    presave = _target_state(seq, world, params, parts, run)
    problems = numeric_diff(before, presave, tolerance=params["float_tolerance"])
    if problems:
        _stop(run, "REVERT_PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
              (json.dumps(problems[:20]), backup["root"]))
    saves = _save_targets(world, record["packages"], run)
    after = _post_state(params, parts, run, world)
    problems = numeric_diff(before, after, tolerance=params["float_tolerance"])
    if problems or _census() != {"content": [], "maps": []}:
        _stop(run, "REVERT_POSTSAVE_READBACK|%s|census=%s|restore=%s" %
              (json.dumps(problems[:20]), json.dumps(_census(), sort_keys=True), backup["root"]))
    archived = _record_path() + ".reverted-" + run
    os.rename(_record_path(), archived)
    _json_write(txn, {"run": run, "completed": True, "backup": backup,
                      "archived_record": archived, "saves": saves, "census_after": _census()})
    _log("%s_REVERT_OK|run=%s|parts=%s|saved=%s|backup=%s|record=%s" %
         (TOOL, run, ",".join(record["plan"]["mutating_parts"]), ",".join(saves), backup["root"], archived))
    return {"archived_record": archived, "backup": backup, "saves": saves}


def main(args):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or datetime.datetime.now().strftime("S3POLISH-%Y%m%d-%H%M%S"))
    try:
        params = merged_params(args.get("params") or {})
        parts = selected_parts(args.get("parts"))
        function = {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}.get(mode)
        if function is None:
            _stop(run, "MODE|%r" % mode)
        return function(run, params, parts, args.get("confirm"))
    except PlanError as error:
        _stop(run, "PLAN_REFUSED|%s" % error)
