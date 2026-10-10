"""Job 169 stage A: wrapper-owned S1 fire pan, fire, and warm practical.

Offline-authored only: importing this file outside Unreal is safe.  APPLY saves
only LS_DevScene_01.  Klara's sequence and L_Animals are hash-guarded and are
never save-eligible.

Camera precedence is deliberate.  A nested shot cut outranks a root cut, so the
Klara shot section is split at an exact 25->30 fps boundary.  Its tail continues
all animation with lower hierarchical bias, allowing the wrapper's spawnable
camera cut to win without editing Klara's sequence or her level.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:
    unreal = None


TOOL = "JOB169_S1_FIRE_ENDING"
VERSION = 1
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
KLARA = "/Game/InfinityStage/KlaraHookin/LS_Animals_1_S1Hangar"
KLARA_LEVEL = "/Game/KK_S1_Animals/L_Animals"
CAMERA_NAME = "JOB169 S1 Corner Fire Camera"
CAMERA_COMPONENT_NAME = CAMERA_NAME + "/CameraComponent"
FIRE_NAME = "JOB169 S1 Corner Wing Fire"
LIGHT_NAME = "JOB169 S1 Corner Wing Fire Light"
LIGHT_COMPONENT_NAME = LIGHT_NAME + "/LightComponent"
CUT_TRACK_NAME = "JOB169 Corner Fire Cut"
RECORD_NAME = "job169_camera_fire_record.json"
PLAN_NAME = "job169_camera_fire_apply_ready.json"
VALID_MODES = ("DRY", "APPLY", "REVERT")
LAYOUT_RELATIVE_EXPECTED = "CodexConductor/KlaraIngest/klara_reveal_record_S1.json"


class Refusal(RuntimeError):
    pass


def stable_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                 default=str).encode("utf-8")).hexdigest()


def timing_plan(args, fps=25.0):
    start = int(args["camera_start_frame"])
    pan_end = start + int(round(float(args["camera_pan_seconds"]) * fps))
    fire_start = int(args["fire_start_frame"])
    fire_ramp_end = fire_start + int(round(float(args["fire_ramp_seconds"]) * fps))
    lights_start = int(args["lights_out_start_frame"])
    lights_end = lights_start + int(round(float(args["lights_out_fade_seconds"]) * fps))
    return {"fps": fps, "camera_pan": [start, pan_end], "camera_hold": [pan_end, int(args["new_end_frame"])],
            "fire_window": [fire_start, int(args["new_end_frame"])],
            "fire_ramp": [fire_start, fire_ramp_end], "lights_out": [lights_start, lights_end],
            "new_end": int(args["new_end_frame"])}


def source_frame_for_scene(scene_frame, shot_start=594, start_offset_ticks=86400,
                           source_tick=24000, source_fps=30.0, scene_fps=25.0):
    offset_s = float(start_offset_ticks) / float(source_tick)
    return (offset_s + (float(scene_frame) - float(shot_start)) / float(scene_fps)) * float(source_fps)


def look_rotation(camera, target):
    dx, dy, dz = (float(target[i]) - float(camera[i]) for i in range(3))
    horizontal = math.hypot(dx, dy)
    return [0.0, math.degrees(math.atan2(dz, horizontal)), math.degrees(math.atan2(dy, dx))]


def target_focal_mm(distance_cm, object_height_cm, sensor_height_mm, fraction, limits):
    if distance_cm <= 0.0 or object_height_cm <= 0.0 or sensor_height_mm <= 0.0:
        raise ValueError("FRAMING_GEOMETRY")
    raw = float(fraction) * float(distance_cm) * float(sensor_height_mm) / float(object_height_cm)
    return max(float(limits[0]), min(float(limits[1]), raw))


def projected_fraction(distance_cm, object_height_cm, sensor_height_mm, focal_mm):
    return float(focal_mm) * float(object_height_cm) / (float(distance_cm) * float(sensor_height_mm))


def validate_args(args):
    errors = []
    mode = str(args.get("mode") or "").upper()
    if mode not in VALID_MODES:
        errors.append("MODE_INVALID")
    if args.get("confirm") != "%s JOB169" % mode:
        errors.append("CONFIRM_MISMATCH")
    if (args.get("scene_sequence"), args.get("klara_copy"), args.get("klara_level")) != (SCENE, KLARA, KLARA_LEVEL):
        errors.append("ASSET_AUTHORITY_MISMATCH")
    if args.get("wing_layout_record") != LAYOUT_RELATIVE_EXPECTED:
        errors.append("LAYOUT_RECORD_MISMATCH")
    if args.get("fire_system") != "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_1":
        errors.append("FIRE_SYSTEM_MISMATCH")
    try:
        plan = timing_plan(args)
        source = source_frame_for_scene(plan["camera_pan"][0])
        if abs(source - round(source)) > 1.0e-8:
            errors.append("CAMERA_START_NOT_EXACT_SOURCE_FRAME")
        if not (plan["camera_pan"][0] < plan["fire_window"][0] < plan["camera_pan"][1]):
            errors.append("FIRE_NOT_DURING_PAN")
        if not (plan["fire_ramp"][1] < plan["lights_out"][0] < plan["lights_out"][1] < plan["new_end"]):
            errors.append("ENDING_ORDER")
        if int(args["camera_hierarchical_bias"]) >= 0:
            errors.append("TAIL_BIAS_MUST_BE_NEGATIVE")
        lo, hi = [float(v) for v in args["camera_fraction_limits"]]
        if not (0.0 < lo <= float(args["camera_target_fraction"]) <= hi < 1.0):
            errors.append("FRAME_FRACTION")
        if float(args["fire_scale"]) <= 0.0 or float(args["fire_scale"]) > 0.5:
            errors.append("FIRE_NOT_SMALL")
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        errors.append("TIMING_OR_LOOK_INVALID")
    return errors


def review_digest(report):
    keys = ("plan", "layout_authority", "wing", "source_camera", "before_digest", "guards")
    return stable_digest({key: report[key] for key in keys})


def _here():
    if unreal is None:
        return os.path.dirname(os.path.abspath(__file__))
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexConductor", "Job169S1FireEnding_20261010")


def _project_root():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _json_read(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise Refusal("MISSING_JSON|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_file(asset_path, extension=".uasset"):
    return os.path.join(_project_root(), "Content", *asset_path[len("/Game/"):].split("/")) + extension


def _asset_path(value):
    return "" if value is None else value.get_path_name().split(".", 1)[0]


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(_asset_path(p) for p in lib.get_dirty_content_packages()),
            "maps": sorted(_asset_path(p) for p in lib.get_dirty_map_packages())}


def _guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def _rate(value):
    return float(value.numerator) / float(value.denominator)


def _channel_name(channel):
    try:
        text = str(channel.get_editor_property("channel_name"))
    except Exception:
        text = str(channel.get_name())
    bits = text.rsplit("_", 1)
    return bits[0] if len(bits) == 2 and bits[1].isdigit() else text


def _frame_value(value):
    return int(value.value) if hasattr(value, "value") else int(value)


def _section_range(section, seq):
    return [int(section.get_start_frame()) if section.has_start_frame() else int(seq.get_playback_start()),
            int(section.get_end_frame()) if section.has_end_frame() else int(seq.get_playback_end())]


def _section_bias(section):
    try:
        return int(section.get_editor_property("parameters").get_editor_property("hierarchical_bias"))
    except Exception:
        return None


def _section_offset(section):
    try:
        return _frame_value(section.get_editor_property("parameters").get_editor_property("start_frame_offset"))
    except Exception:
        return None


def _key_rows(section):
    rows = {}
    for channel in section.get_all_channels():
        rows[_channel_name(channel)] = [[int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                                             .frame_number.value), k.get_value()] for k in channel.get_keys()]
    return rows


def _timeline_state(seq):
    names = {_guid(b.get_id()): str(b.get_display_name()) for b in seq.get_bindings()}
    shots, cuts = [], []
    for ti, track in enumerate(seq.get_tracks()):
        cls = track.get_class().get_name()
        for si, section in enumerate(track.get_sections()):
            if hasattr(section, "get_sequence") and _asset_path(section.get_sequence()) == KLARA:
                shots.append({"track_index": ti, "section_index": si, "range": _section_range(section, seq),
                              "offset": _section_offset(section), "bias": _section_bias(section),
                              "active": bool(section.is_active()), "class": cls})
            if "CameraCut" in cls:
                bid = section.get_camera_binding_id()
                guid = _guid(bid.get_editor_property("guid"))
                cuts.append({"track_index": ti, "section_index": si, "range": _section_range(section, seq),
                             "camera_guid": guid, "camera": names.get(guid, "<unresolved>"),
                             "active": bool(section.is_active())})
    return {"shots": shots, "cuts": cuts, "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())]}


def _owned_state(seq):
    spawnables = {_guid(b.get_id()) for b in seq.get_spawnables()}
    rows = []
    for binding in seq.get_bindings():
        name = str(binding.get_display_name())
        if not name.startswith("JOB169 "):
            continue
        tracks = []
        for track in binding.get_tracks():
            prop = (str(track.get_property_name()), str(track.get_property_path())) \
                if hasattr(track, "get_property_name") else ("", "")
            tracks.append({"class": track.get_class().get_name(), "property": prop,
                           "sections": [{"range": _section_range(s, seq), "keys": _key_rows(s)}
                                        for s in track.get_sections()]})
        template = binding.get_object_template() if _guid(binding.get_id()) in spawnables else None
        rows.append({"guid": _guid(binding.get_id()), "name": name, "spawnable": _guid(binding.get_id()) in spawnables,
                     "template_class": None if template is None else template.get_class().get_name(), "tracks": tracks})
    return sorted(rows, key=lambda row: row["name"])


def _eval_channel(channel, sequence, frame):
    values = list(channel.evaluate_keys(sequence.make_range(int(frame), 1), sequence.get_display_rate()))
    if len(values) != 1:
        raise Refusal("CHANNEL_EVALUATE_COUNT|frame=%d|got=%d" % (frame, len(values)))
    return float(values[0])


def _camera_at_source_frame(klara, frame):
    cuts = []
    for track in klara.get_tracks():
        if "CameraCut" not in track.get_class().get_name():
            continue
        for section in track.get_sections():
            span = _section_range(section, klara)
            if section.is_active() and span[0] <= frame < span[1]:
                cuts.append(section)
    if len(cuts) != 1:
        raise Refusal("SOURCE_ACTIVE_CUT_COUNT|frame=%d|count=%d" % (frame, len(cuts)))
    guid = _guid(cuts[0].get_camera_binding_id().get_editor_property("guid"))
    bindings = {_guid(b.get_id()): b for b in klara.get_bindings()}
    binding = bindings.get(guid)
    if binding is None:
        raise Refusal("SOURCE_CAMERA_BINDING_MISSING|%s" % guid)
    parent = binding.get_parent()
    if parent is not None and hasattr(parent, "is_valid") and parent.is_valid():
        raise Refusal("SOURCE_CAMERA_HAS_PARENT|%s" % binding.get_display_name())
    sections = [s for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"
                for s in t.get_sections() if s.is_active() and _section_range(s, klara)[0] <= frame < _section_range(s, klara)[1]]
    if len(sections) != 1:
        raise Refusal("SOURCE_CAMERA_TRANSFORM_COUNT|%d" % len(sections))
    channels = {_channel_name(c): c for c in sections[0].get_all_channels()}
    required = (tuple("Location." + axis for axis in "XYZ") +
                tuple("Rotation." + axis for axis in "XYZ") +
                tuple("Scale." + axis for axis in "XYZ"))
    if not set(required).issubset(channels):
        raise Refusal("SOURCE_CAMERA_CHANNELS|%s" % sorted(channels))
    values = {name: _eval_channel(channels[name], klara, frame) for name in required}
    focal, focus = None, None
    for child in klara.get_bindings():
        p = child.get_parent()
        if p is None or not hasattr(p, "is_valid") or not p.is_valid() or _guid(p.get_id()) != guid:
            continue
        for track in child.get_tracks():
            prop = str(track.get_property_name()) if hasattr(track, "get_property_name") else ""
            for section in track.get_sections():
                if not section.is_active() or not (_section_range(section, klara)[0] <= frame < _section_range(section, klara)[1]):
                    continue
                channels1 = list(section.get_all_channels())
                if len(channels1) == 1 and prop == "CurrentFocalLength":
                    focal = _eval_channel(channels1[0], klara, frame)
                if len(channels1) == 1 and prop == "ManualFocusDistance":
                    focus = _eval_channel(channels1[0], klara, frame)
    if focal is None:
        raise Refusal("SOURCE_FOCAL_UNREADABLE")
    return {"frame": frame, "cut_range": _section_range(cuts[0], klara), "binding": str(binding.get_display_name()),
            "guid": guid, "location": [values["Location.X"], values["Location.Y"], values["Location.Z"]],
            "rotation": [values["Rotation.X"], values["Rotation.Y"], values["Rotation.Z"]],
            "scale": [values["Scale.X"], values["Scale.Y"], values["Scale.Z"]],
            "focal_mm": focal, "focus_cm": focus if focus is not None else 1000.0}


def _layout_wings(args):
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        *args["wing_layout_record"].split("/"))
    record = _json_read(path)
    rows = record.get("plan", {}).get("footprint", {}).get("kept", [])
    labels = [row.get("label") for row in rows if row.get("class") == "StaticMeshActor" and "Wing" in row.get("label", "")]
    if args["wing_label"] not in labels:
        raise Refusal("WING_NOT_IN_S1_LAYOUT_RECORD|%s" % args["wing_label"])
    return {"path": path, "sha256": _sha(path), "record_run": record.get("run"), "candidate_labels": labels}


def _one_actor(world, label):
    hits = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
            if str(a.get_actor_label()) == label]
    if len(hits) != 1:
        raise Refusal("ACTOR_COUNT|%s|%d" % (label, len(hits)))
    return hits[0]


def _preflight(args):
    errors = validate_args(args)
    if errors:
        raise Refusal("ARGS|%s" % errors)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise Refusal("PIE_RUNNING")
    world = editor.get_editor_world()
    if world is None or _asset_path(world) != EXPECTED_WORLD:
        raise Refusal("WORLD_MISMATCH|%s" % (None if world is None else _asset_path(world)))
    if _census() != {"content": [], "maps": []}:
        raise Refusal("DIRTY_AT_START|%s" % _census())
    seq, klara = unreal.load_asset(SCENE), unreal.load_asset(KLARA)
    if seq is None or klara is None:
        raise Refusal("SEQUENCE_LOAD_FAILED")
    if abs(_rate(seq.get_display_rate()) - 25.0) > 1.0e-6 or abs(_rate(klara.get_display_rate()) - 30.0) > 1.0e-6:
        raise Refusal("DISPLAY_RATE_MISMATCH")
    return world, seq, klara


def _report(args):
    world, seq, klara = _preflight(args)
    if _owned_state(seq):
        raise Refusal("OWNED_STATE_ALREADY_EXISTS|use REVERT or inspect drift")
    plan = timing_plan(args)
    timeline = _timeline_state(seq)
    if len(timeline["shots"]) != 1:
        raise Refusal("KLARA_SHOT_COUNT|%d" % len(timeline["shots"]))
    shot = timeline["shots"][0]
    start = plan["camera_pan"][0]
    if not (shot["range"][0] < start < shot["range"][1]):
        raise Refusal("CAMERA_START_OUTSIDE_SHOT")
    source_frame_exact = source_frame_for_scene(start, shot["range"][0], shot["offset"],
                                                _rate(klara.get_tick_resolution()),
                                                _rate(klara.get_display_rate()), _rate(seq.get_display_rate()))
    if abs(source_frame_exact - round(source_frame_exact)) > 1.0e-8:
        raise Refusal("SOURCE_FRAME_FRACTIONAL|%s" % source_frame_exact)
    source_camera = _camera_at_source_frame(klara, int(round(source_frame_exact)))
    layout = _layout_wings(args)
    wing = _one_actor(world, args["wing_label"])
    center, extent = wing.get_actor_bounds(False)
    base = [float(center.x), float(center.y), float(center.z - extent.z)]
    height = 2.0 * float(extent.z)
    target = [float(center.x), float(center.y), base[2] + height * float(args["fire_frame_height_fraction"])]
    camera_loc = source_camera["location"]
    distance = math.sqrt(sum((target[i] - camera_loc[i]) ** 2 for i in range(3)))
    sensor = [23.760000228881836, 13.364999771118164]
    focal_end = target_focal_mm(distance, height, sensor[1], float(args["camera_target_fraction"]),
                                args["camera_focal_limits_mm"])
    fraction = projected_fraction(distance, height, sensor[1], focal_end)
    lo, hi = [float(v) for v in args["camera_fraction_limits"]]
    if not (lo - 1.0e-6 <= fraction <= hi + 1.0e-6):
        raise Refusal("WING_FRAME_FRACTION|%.4f" % fraction)
    fire_loc = [base[i] + float(args["fire_offset_cm"][i]) for i in range(3)]
    light_loc = [fire_loc[0], fire_loc[1], fire_loc[2] + 70.0]
    plan.update({"source_frame": int(round(source_frame_exact)), "tail_bias": int(args["camera_hierarchical_bias"]),
                 "camera": {"start_location": camera_loc, "start_rotation": source_camera["rotation"],
                            "start_scale": source_camera["scale"],
                            "end_rotation": look_rotation(camera_loc, target),
                            "start_focal_mm": source_camera["focal_mm"], "end_focal_mm": focal_end,
                            "start_focus_cm": source_camera["focus_cm"], "end_focus_cm": distance,
                            "sensor_mm": sensor},
                 "fire": {"location": fire_loc, "light_location": light_loc,
                          "scale": float(args["fire_scale"]), "system": args["fire_system"]},
                 "framing": {"target": target, "distance_cm": distance, "wing_height_cm": height,
                             "projected_height_fraction": fraction, "requested_fraction": args["camera_target_fraction"]}})
    guards = {}
    for asset, ext in ((KLARA, ".uasset"), (KLARA_LEVEL, ".umap")):
        path = _asset_file(asset, ext)
        guards[asset] = {"file": path, "sha256": _sha(path)}
    before = {"timeline": timeline, "owned": _owned_state(seq)}
    report = {"schema": 1, "tool": TOOL, "version": VERSION, "run": args["run_id"], "mode": args["mode"],
              "decided_by": args["decided_by"], "plan": plan, "layout_authority": layout,
              "wing": {"label": args["wing_label"], "path": wing.get_path_name(),
                       "bounds_center": [center.x, center.y, center.z], "bounds_extent": [extent.x, extent.y, extent.z]},
              "source_camera": source_camera, "before": before, "before_digest": stable_digest(before),
              "guards": guards, "census": _census(),
              "choice": "Fire Niagara and warm point light remain through frame 3899 and are the last light after the rig fade.",
              "claims": {"measured_when_run": "live layout, source-camera channels, dry census, saved read-back",
                         "declaration_proven": "only LS_DevScene_01 is save-eligible",
                         "inferred": "30-50 percent analytical framing must be judged in PIE stills"}}
    return world, seq, klara, report


def _backup(run, suffix=""):
    base = os.path.join(_project_root(), "Backups", "PreJob169S1Fire%s-%s" % (suffix, run))
    folder = unique_artifact_path(base)
    os.makedirs(folder, exist_ok=False)
    source = _asset_file(SCENE)
    target = os.path.join(folder, os.path.basename(source))
    shutil.copy2(source, target)
    if _sha(source) != _sha(target):
        raise Refusal("BACKUP_VERIFY")
    return {"root": folder, "files": [{"asset": SCENE, "source": source, "backup": target,
                                        "sha256": _sha(target), "bytes": os.path.getsize(target)}]}


def unique_artifact_path(path):
    """Return a non-existing path without deleting evidence from failed attempts."""
    if not os.path.exists(path):
        return path
    attempt = 2
    while os.path.exists("%s-attempt%d" % (path, attempt)):
        attempt += 1
    return "%s-attempt%d" % (path, attempt)


def _spawn_track(binding, start, end):
    tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"]
    track = tracks[0] if tracks else binding.add_track(unreal.MovieSceneSpawnTrack)
    for extra in tracks[1:]:
        binding.remove_track(extra)
    for section in list(track.get_sections()):
        track.remove_section(section)
    section = track.add_section(); section.set_range(0, end + 1)
    channel = section.get_all_channels()[0]; channel.set_default(False)
    channel.add_key(unreal.FrameNumber(int(start)), True, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    channel.add_key(unreal.FrameNumber(int(end)), False, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)


def _visibility_track(binding, start, end):
    track = binding.add_track(unreal.MovieSceneVisibilityTrack)
    track.set_property_name_and_path("bHidden", "bHidden")
    section = track.add_section(); section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    section.set_range(0, end + 1)
    channel = section.get_all_channels()[0]; channel.set_default(False)
    # Visibility channel semantics: True means shown even though the bound property is AActor::bHidden.
    channel.add_key(unreal.FrameNumber(0), False, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    channel.add_key(unreal.FrameNumber(int(start)), True, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    channel.add_key(unreal.FrameNumber(int(end)), False, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    if (str(track.get_property_name()), str(track.get_property_path())) != ("bHidden", "bHidden"):
        raise Refusal("VISIBILITY_BINDING_READBACK")


def _transform_track(binding, span, keys, label):
    track = binding.add_track(unreal.MovieScene3DTransformTrack); track.set_display_name(label)
    section = track.add_section(); section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    section.set_range(int(span[0]), int(span[1]))
    channels = {_channel_name(c): c for c in section.get_all_channels()}
    # UE 5.8 exposes the smooth/default cubic tangent mode as AUTO.
    cubic, linear = unreal.MovieSceneKeyInterpolation.AUTO, unreal.MovieSceneKeyInterpolation.LINEAR
    for name, rows in keys.items():
        if name not in channels:
            raise Refusal("TRANSFORM_CHANNEL_MISSING|%s|%s" % (label, name))
        for frame, value, eased in rows:
            key = channels[name].add_key(unreal.FrameNumber(int(frame)), float(value),
                                         time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                         interpolation=cubic if eased else linear)
            if eased and key is not None:
                key.set_tangent_mode(unreal.RichCurveTangentMode.RCTM_AUTO)
    return track


def _float_track(binding, prop, path, span, rows, label, eased=True):
    track = binding.add_track(unreal.MovieSceneFloatTrack)
    if track is None:
        raise Refusal("FLOAT_TRACK_CREATE|%s|%s" % (label, prop))
    track.set_property_name_and_path(unreal.Name(prop), path); track.set_display_name(label)
    section = track.add_section(); section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    section.set_range(int(span[0]), int(span[1]))
    channel = section.get_all_channels()[0]
    for frame, value in rows:
        key = channel.add_key(unreal.FrameNumber(int(frame)), float(value),
                              time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                              interpolation=unreal.MovieSceneKeyInterpolation.AUTO if eased else unreal.MovieSceneKeyInterpolation.LINEAR)
        if eased and key is not None:
            key.set_tangent_mode(unreal.RichCurveTangentMode.RCTM_AUTO)
    return track


def _component_child_binding(seq, parent, component, display_name):
    """Reuse the child binding auto-created for a spawnable before adding one."""
    children = list(parent.get_child_possessables())
    if len(children) > 1:
        raise Refusal("COMPONENT_CHILD_AMBIGUOUS|%s|%d" % (display_name, len(children)))
    if children:
        child = children[0]
    else:
        child = seq.add_possessable(component)
        if child is None:
            raise Refusal("COMPONENT_CHILD_CREATE|%s" % display_name)
        child.set_parent(parent)
    child.set_display_name(display_name)
    return child


def _make_camera(seq, plan):
    binding = seq.add_spawnable_from_class(unreal.CineCameraActor); binding.set_display_name(CAMERA_NAME)
    template = binding.get_object_template(); component = template.get_editor_property("camera_component")
    filmback = component.get_editor_property("filmback")
    filmback.set_editor_property("sensor_width", plan["camera"]["sensor_mm"][0])
    filmback.set_editor_property("sensor_height", plan["camera"]["sensor_mm"][1])
    component.set_editor_property("filmback", filmback)
    _spawn_track(binding, plan["camera_pan"][0], plan["new_end"])
    start, pan_end, end = plan["camera_pan"][0], plan["camera_pan"][1], plan["new_end"]
    keys = {}
    for i, axis in enumerate("XYZ"):
        keys["Location." + axis] = [(start, plan["camera"]["start_location"][i], False),
                                     (end, plan["camera"]["start_location"][i], False)]
        keys["Rotation." + axis] = [(start, plan["camera"]["start_rotation"][i], True),
                                     (pan_end, plan["camera"]["end_rotation"][i], True),
                                     (end, plan["camera"]["end_rotation"][i], False)]
        keys["Scale." + axis] = [(start, plan["camera"]["start_scale"][i], False),
                                  (end, plan["camera"]["start_scale"][i], False)]
    _transform_track(binding, [start, end], keys, CAMERA_NAME + " Transform")
    child = _component_child_binding(seq, binding, component, CAMERA_COMPONENT_NAME)
    _float_track(child, "CurrentFocalLength", "CurrentFocalLength", [start, end],
                 [(start, plan["camera"]["start_focal_mm"]), (pan_end, plan["camera"]["end_focal_mm"]),
                  (end, plan["camera"]["end_focal_mm"])], CAMERA_NAME + " Focal")
    _float_track(child, "ManualFocusDistance", "FocusSettings.ManualFocusDistance", [start, end],
                 [(start, plan["camera"]["start_focus_cm"]), (pan_end, plan["camera"]["end_focus_cm"]),
                  (end, plan["camera"]["end_focus_cm"])], CAMERA_NAME + " Focus")
    return binding


def _make_fire(seq, args, plan):
    system = unreal.load_asset(args["fire_system"])
    if system is None or not isinstance(system, unreal.NiagaraSystem):
        raise Refusal("FIRE_SYSTEM_LOAD")
    fire = seq.add_spawnable_from_class(unreal.NiagaraActor); fire.set_display_name(FIRE_NAME)
    fire.get_object_template().get_editor_property("niagara_component").set_asset(system)
    _spawn_track(fire, plan["fire_window"][0], plan["new_end"]); _visibility_track(fire, plan["fire_window"][0], plan["new_end"])
    a, b, end = plan["fire_ramp"][0], plan["fire_ramp"][1], plan["new_end"]
    keys = {}
    for i, axis in enumerate("XYZ"):
        keys["Location." + axis] = [(a, plan["fire"]["location"][i], False), (end, plan["fire"]["location"][i], False)]
        keys["Rotation." + axis] = [(a, 0.0, False), (end, 0.0, False)]
        keys["Scale." + axis] = [(a, 0.01, True), (b, plan["fire"]["scale"], True),
                                  (end, plan["fire"]["scale"], False)]
    _transform_track(fire, [a, end], keys, FIRE_NAME + " Transform")

    light = seq.add_spawnable_from_class(unreal.PointLight); light.set_display_name(LIGHT_NAME)
    template = light.get_object_template(); component = template.get_editor_property("point_light_component")
    component.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    component.set_editor_property("use_temperature", True)
    component.set_editor_property("temperature", float(args["fire_light_temperature_k"]))
    component.set_editor_property("attenuation_radius", float(args["fire_light_radius_cm"]))
    component.set_editor_property("cast_shadows", False)
    _spawn_track(light, plan["fire_window"][0], plan["new_end"]); _visibility_track(light, plan["fire_window"][0], plan["new_end"])
    light_keys = {}
    for i, axis in enumerate("XYZ"):
        light_keys["Location." + axis] = [(a, plan["fire"]["light_location"][i], False),
                                          (end, plan["fire"]["light_location"][i], False)]
        light_keys["Rotation." + axis] = [(a, 0.0, False), (end, 0.0, False)]
        light_keys["Scale." + axis] = [(a, 1.0, False), (end, 1.0, False)]
    _transform_track(light, [a, end], light_keys, LIGHT_NAME + " Transform")
    child = _component_child_binding(seq, light, component, LIGHT_COMPONENT_NAME)
    _float_track(child, "Intensity", "Intensity", [a, end],
                 [(a, 0.0), (b, float(args["fire_light_intensity_lm"])),
                  (end, float(args["fire_light_intensity_lm"]))], LIGHT_NAME + " Intensity")
    return fire, light


def _split_shot_and_add_cut(seq, camera, plan):
    shot_tracks = [(t, s) for t in seq.get_tracks() for s in t.get_sections()
                   if hasattr(s, "get_sequence") and _asset_path(s.get_sequence()) == KLARA]
    if len(shot_tracks) != 1:
        raise Refusal("SHOT_DISCOVERY|%d" % len(shot_tracks))
    track, head = shot_tracks[0]
    original_end, original_offset = _section_range(head, seq)[1], _section_offset(head)
    start = plan["camera_pan"][0]
    delta_ticks = int(round((start - _section_range(head, seq)[0]) * _rate(seq.get_tick_resolution()) /
                            _rate(seq.get_display_rate())))
    head.set_end_frame(start)
    tail = track.add_section(); tail.set_sequence(unreal.load_asset(KLARA)); tail.set_range(start, original_end)
    params = head.get_editor_property("parameters")
    tail.set_editor_property("parameters", params)
    tail_params = tail.get_editor_property("parameters")
    tail_params.set_editor_property("start_frame_offset", unreal.FrameNumber(original_offset + delta_ticks))
    tail_params.set_editor_property("hierarchical_bias", int(plan["tail_bias"]))
    tail.set_editor_property("parameters", tail_params)
    tail.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)

    cut_tracks = [t for t in seq.get_tracks() if "CameraCut" in t.get_class().get_name()]
    if len(cut_tracks) != 1:
        raise Refusal("CUT_TRACK_COUNT|%d" % len(cut_tracks))
    cut_track = cut_tracks[0]
    containing = [s for s in cut_track.get_sections() if s.is_active() and
                  _section_range(s, seq)[0] < start < _section_range(s, seq)[1]]
    if len(containing) != 1:
        raise Refusal("PRIOR_CUT_AT_START|%d" % len(containing))
    containing[0].set_end_frame(start)
    owned_cut = cut_track.add_section(); owned_cut.set_camera_binding_id(seq.get_binding_id(camera))
    owned_cut.set_range(start, int(seq.get_playback_end()))
    return {"head": _section_range(head, seq), "tail": _section_range(tail, seq),
            "tail_offset": _section_offset(tail), "tail_bias": _section_bias(tail),
            "cut": _section_range(owned_cut, seq)}


def _guards_unchanged(guards):
    return all(_sha(row["file"]) == row["sha256"] for row in guards.values())


def run_dry(args):
    _world, _seq, _klara, report = _report(args)
    path = os.path.join(_here(), "job169_camera_fire_dry_%s.json" % args["run_id"])
    _json_write(path, report)
    _json_write(os.path.join(_here(), PLAN_NAME), {"run": args["run_id"], "digest": review_digest(report), "report": path})
    if _census() != {"content": [], "maps": []}:
        raise Refusal("DRY_DIRTIED_EDITOR")
    unreal.log("%s_DRY_OK|run=%s|mutated=0|wing=%s|pan=%s|fire=%s|fraction=%.3f|source_frame=%d|report=%s" %
               (TOOL, args["run_id"], report["wing"]["label"], report["plan"]["camera_pan"],
                report["plan"]["fire_window"], report["plan"]["framing"]["projected_height_fraction"],
                report["plan"]["source_frame"], path))
    return report


def run_apply(args):
    world, seq, _klara, report = _report(args)
    gate = _json_read(os.path.join(_here(), PLAN_NAME))
    if gate.get("digest") != review_digest(report):
        raise Refusal("CHANGED_SINCE_DRY")
    run = args["run_id"]; backup = _backup(run)
    transaction = unique_artifact_path(os.path.join(_here(), "job169_camera_fire_transaction_%s.json" % run))
    record = {"schema": 1, "tool": TOOL, "run": run, "applied": False, "written_before_mutation": True,
              "backup": backup, "report": report, "before": report["before"]}
    _json_write(transaction, record, exclusive=True)
    seq.modify()
    camera = _make_camera(seq, report["plan"])
    fire, light = _make_fire(seq, args, report["plan"])
    record["created_guids"] = [_guid(x.get_id()) for x in (camera, fire, light)]
    record["timeline_edit"] = _split_shot_and_add_cut(seq, camera, report["plan"])
    after = {"timeline": _timeline_state(seq), "owned": _owned_state(seq)}
    if len([r for r in after["owned"] if r["spawnable"]]) != 3:
        raise Refusal("OWNED_SPAWNABLE_COUNT|NOTHING SAVED")
    if len(after["timeline"]["shots"]) != 2 or after["timeline"]["shots"][1]["bias"] != int(args["camera_hierarchical_bias"]):
        raise Refusal("SHOT_SPLIT_READBACK|NOTHING SAVED")
    owned_cuts = [r for r in after["timeline"]["cuts"] if r["camera"] == CAMERA_NAME]
    if len(owned_cuts) != 1 or owned_cuts[0]["range"][0] != report["plan"]["camera_pan"][0]:
        raise Refusal("OWNED_CUT_READBACK|NOTHING SAVED")
    record.update({"after": after, "saved_readback_digest": stable_digest(after), "applied": True})
    _json_write(transaction, record)
    if _census() != {"content": [SCENE], "maps": []}:
        raise Refusal("DIRTY_SCOPE|%s|NOTHING SAVED" % _census())
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=True):
        raise Refusal("SAVE_FAILED|%s" % SCENE)
    if _census() != {"content": [], "maps": []}:
        raise Refusal("DIRTY_AFTER_SAVE|%s" % _census())
    saved_seq = unreal.load_asset(SCENE)
    saved = {"timeline": _timeline_state(saved_seq), "owned": _owned_state(saved_seq)}
    if saved != after:
        raise Refusal("SAVED_READBACK_MISMATCH|restore=%s" % backup["root"])
    if not _guards_unchanged(report["guards"]):
        raise Refusal("KLARA_ASSET_OR_LEVEL_CHANGED|restore=%s" % backup["root"])
    record.update({"saved_readback": saved, "saved_readback_digest": stable_digest(saved), "census_after": _census()})
    _json_write(os.path.join(_here(), RECORD_NAME), record, exclusive=True)
    _json_write(transaction, dict(record, transaction_complete=True))
    unreal.log("%s_APPLY_OK|run=%s|saved=%s|wing=%s|cut=%s|fire=%s|last_light=fire|klara_saved=0|levels_saved=0|backup=%s|record=%s" %
               (TOOL, run, SCENE, report["wing"]["label"], report["plan"]["camera_pan"],
                report["plan"]["fire_window"], backup["root"], os.path.join(_here(), RECORD_NAME)))
    return record


def _restore_timeline(seq, before):
    cut_tracks = [t for t in seq.get_tracks() if "CameraCut" in t.get_class().get_name()]
    if len(cut_tracks) != 1:
        raise Refusal("REVERT_CUT_TRACK_COUNT")
    cut_track = cut_tracks[0]
    names = {_guid(b.get_id()): str(b.get_display_name()) for b in seq.get_bindings()}
    for section in list(cut_track.get_sections()):
        guid = _guid(section.get_camera_binding_id().get_editor_property("guid"))
        if names.get(guid) == CAMERA_NAME:
            cut_track.remove_section(section)
    remaining = list(cut_track.get_sections())
    old = before["timeline"]["cuts"]
    if len(remaining) != len(old):
        raise Refusal("REVERT_CUT_COUNT|%d|%d" % (len(remaining), len(old)))
    for section, row in zip(remaining, old):
        section.set_range(*row["range"]); section.set_is_active(bool(row["active"]))

    shot_tracks = [(t, s) for t in seq.get_tracks() for s in t.get_sections()
                   if hasattr(s, "get_sequence") and _asset_path(s.get_sequence()) == KLARA]
    tails = [(t, s) for t, s in shot_tracks if _section_bias(s) is not None and _section_bias(s) < 0]
    if len(tails) != 1:
        raise Refusal("REVERT_TAIL_COUNT|%d" % len(tails))
    tails[0][0].remove_section(tails[0][1])
    heads = [(t, s) for t, s in shot_tracks if s is not tails[0][1]]
    if len(heads) != 1 or len(before["timeline"]["shots"]) != 1:
        raise Refusal("REVERT_HEAD_COUNT")
    row = before["timeline"]["shots"][0]; head = heads[0][1]
    head.set_range(*row["range"]); head.set_is_active(bool(row["active"]))
    params = head.get_editor_property("parameters")
    params.set_editor_property("start_frame_offset", unreal.FrameNumber(int(row["offset"])))
    if row["bias"] is not None:
        params.set_editor_property("hierarchical_bias", int(row["bias"]))
    head.set_editor_property("parameters", params)


def _remove_owned_bindings(seq):
    owned = [b for b in seq.get_bindings() if str(b.get_display_name()).startswith("JOB169 ")]
    spawnable_guids = {_guid(b.get_id()) for b in seq.get_spawnables()}
    for binding in [b for b in owned if _guid(b.get_id()) not in spawnable_guids]:
        seq.remove_possessable(binding.get_id())
    for binding in [b for b in owned if _guid(b.get_id()) in spawnable_guids]:
        seq.remove_spawnable(binding.get_id())


def run_revert(args):
    _world, seq, _klara = _preflight(args)
    record_path = os.path.join(_here(), RECORD_NAME); record = _json_read(record_path)
    if not record.get("applied"):
        raise Refusal("NO_APPLIED_RECORD")
    live = {"timeline": _timeline_state(seq), "owned": _owned_state(seq)}
    if stable_digest(live) != record["saved_readback_digest"]:
        raise Refusal("APPLIED_STATE_DRIFT|revert SHRINK and LIGHTS_OUT first")
    backup = _backup(args["run_id"], "Revert")
    txn = os.path.join(_here(), "job169_camera_fire_revert_%s.json" % args["run_id"])
    _json_write(txn, {"completed": False, "backup": backup, "source_record": record_path}, exclusive=True)
    seq.modify(); _restore_timeline(seq, record["before"]); _remove_owned_bindings(seq)
    restored = {"timeline": _timeline_state(seq), "owned": _owned_state(seq)}
    if restored != record["before"]:
        raise Refusal("REVERT_IN_MEMORY_MISMATCH|NOTHING SAVED")
    if _census() != {"content": [SCENE], "maps": []}:
        raise Refusal("REVERT_DIRTY_SCOPE|%s" % _census())
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=True):
        raise Refusal("REVERT_SAVE_FAILED")
    saved_seq = unreal.load_asset(SCENE)
    saved = {"timeline": _timeline_state(saved_seq), "owned": _owned_state(saved_seq)}
    if saved != record["before"] or _census() != {"content": [], "maps": []}:
        raise Refusal("REVERT_SAVED_READBACK")
    if not _guards_unchanged(record["report"]["guards"]):
        raise Refusal("KLARA_ASSET_OR_LEVEL_CHANGED")
    archived = record_path + ".reverted-" + args["run_id"]
    os.rename(record_path, archived)
    _json_write(txn, {"completed": True, "backup": backup, "source_record": archived, "saved_readback": saved})
    unreal.log("%s_REVERT_OK|run=%s|saved=%s|klara_saved=0|levels_saved=0|backup=%s|record=%s" %
               (TOOL, args["run_id"], SCENE, backup["root"], archived))
    return saved


def run(args):
    return {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[str(args["mode"]).upper()](args)
