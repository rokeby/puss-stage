"""Author or revert Scene 3's bright shore strike without opening Sequencer.

Dry run is the default.  S3STRIKE_APPLY creates six root-relative RectLights,
the world-fixed pinned exposure volume, their sequence bindings and one Arrival
pre-drive.  S3STRIKE_REVERT requires the recorded applied state, then removes
exactly those additions.  Both write modes read everything back before saving.

The geometry and key-planning helpers above the Unreal-specific code are kept
plain-Python for test_s3_strike_plan.py.
"""
import copy
import datetime
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Plain-Python planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
ROOT_LABEL = "S3 Hangar Root"
ARRIVAL_LABEL = "S3 Arrival"
EXPOSURE_LABEL = "S3 Hangar Pinned Exposure"
UPLIGHT_PREFIX = "S3 Uplight "
STRIKE_PREFIX = "S3 Strike"
FOLDER = "Infinity Stage/Scene 03 Hangar/Strike"
FPS_FALLBACK = 30.0
REVEAL_DELAY_S = 0.5
EXPECTED_STRIKE_AFTER_W1_S = 2.0
STRIKE_RAMP_S = 0.2
TRANSFORM_TOLERANCE_CM = 0.1
ROTATION_TOLERANCE_DEG = 0.1
KEY_VALUE_TOLERANCE = 1e-3
AIM_DOT_MIN = 0.999
HANGAR_LIGHT_MARGIN_CM = 500.0

# Every table value from SPEC_s3_strike.md is deliberately here at module scope.
CAST_CENTRE_ROOT_CM = (2000.0, -150.0, 120.0)
KEY_LOCATION_ROOT_CM = (700.0, 500.0, 1000.0)
FILL_L_LOCATION_ROOT_CM = (900.0, -900.0, 400.0)
FILL_R_LOCATION_ROOT_CM = (900.0, 900.0, 400.0)
CYC_1_LOCATION_ROOT_CM = (5000.0, -700.0, 1100.0)
CYC_2_LOCATION_ROOT_CM = (5000.0, 0.0, 1100.0)
CYC_3_LOCATION_ROOT_CM = (5000.0, 700.0, 1100.0)
CYC_1_TARGET_ROOT_CM = (6000.0, -700.0, 900.0)
CYC_2_TARGET_ROOT_CM = (6000.0, 0.0, 900.0)
CYC_3_TARGET_ROOT_CM = (6000.0, 700.0, 900.0)
KEY_RECT_CM = (400.0, 200.0)
FILL_RECT_CM = (600.0, 300.0)
CYC_RECT_CM = (400.0, 100.0)
KEY_INTENSITY_CD = 4000.0
FILL_INTENSITY_CD = 1000.0
CYC_INTENSITY_CD = 1500.0
KEY_TEMPERATURE_K = 5600.0
FILL_TEMPERATURE_K = 6500.0
CYC_TEMPERATURE_K = 7000.0

LIGHT_SPECS = (
    {"label": "S3 Strike Key", "location": KEY_LOCATION_ROOT_CM, "target": CAST_CENTRE_ROOT_CM,
     "rect": KEY_RECT_CM, "shadows": True, "intensity": KEY_INTENSITY_CD, "temperature": KEY_TEMPERATURE_K},
    {"label": "S3 Strike Fill L", "location": FILL_L_LOCATION_ROOT_CM, "target": CAST_CENTRE_ROOT_CM,
     "rect": FILL_RECT_CM, "shadows": False, "intensity": FILL_INTENSITY_CD, "temperature": FILL_TEMPERATURE_K},
    {"label": "S3 Strike Fill R", "location": FILL_R_LOCATION_ROOT_CM, "target": CAST_CENTRE_ROOT_CM,
     "rect": FILL_RECT_CM, "shadows": False, "intensity": FILL_INTENSITY_CD, "temperature": FILL_TEMPERATURE_K},
    {"label": "S3 Strike Cyc 1", "location": CYC_1_LOCATION_ROOT_CM, "target": CYC_1_TARGET_ROOT_CM,
     "rect": CYC_RECT_CM, "shadows": False, "intensity": CYC_INTENSITY_CD, "temperature": CYC_TEMPERATURE_K},
    {"label": "S3 Strike Cyc 2", "location": CYC_2_LOCATION_ROOT_CM, "target": CYC_2_TARGET_ROOT_CM,
     "rect": CYC_RECT_CM, "shadows": False, "intensity": CYC_INTENSITY_CD, "temperature": CYC_TEMPERATURE_K},
    {"label": "S3 Strike Cyc 3", "location": CYC_3_LOCATION_ROOT_CM, "target": CYC_3_TARGET_ROOT_CM,
     "rect": CYC_RECT_CM, "shadows": False, "intensity": CYC_INTENSITY_CD, "temperature": CYC_TEMPERATURE_K},
)

if unreal is not None:
    HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_RECORD = os.path.join(HERE, "hangar_s3_plan.json")
CAST_RECORD = os.path.join(HERE, "s3_cast_reveal_record.json")
RECORD = os.path.join(HERE, "s3_strike_record.json")


def _rotation_matrix(rotation_deg):
    """Unreal-style roll/pitch/yaw matrix (degrees), suitable for points/vectors."""
    roll, pitch, yaw = (math.radians(float(v)) for v in rotation_deg)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    roll_m = ((1.0, 0.0, 0.0), (0.0, cr, -sr), (0.0, sr, cr))
    pitch_m = ((cp, 0.0, -sp), (0.0, 1.0, 0.0), (sp, 0.0, cp))
    yaw_m = ((cy, -sy, 0.0), (sy, cy, 0.0), (0.0, 0.0, 1.0))

    def mul(a, b):
        return tuple(tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)) for r in range(3))

    return mul(yaw_m, mul(pitch_m, roll_m))


def rotate_vector(rotation_deg, vector):
    matrix = _rotation_matrix(rotation_deg)
    return tuple(sum(matrix[row][column] * float(vector[column]) for column in range(3)) for row in range(3))


def root_relative_to_world(root_location, root_rotation, relative_location):
    """Pure root-relative point -> world point transform."""
    turned = rotate_vector(root_rotation, relative_location)
    return tuple(float(root_location[i]) + turned[i] for i in range(3))


def look_at_rotation(location, target):
    """Pure root-space look-at rotation as (roll, pitch, yaw), with +X forward."""
    dx, dy, dz = (float(target[i]) - float(location[i]) for i in range(3))
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length <= 1e-9:
        raise ValueError("look-at location and target are coincident")
    return (0.0, math.degrees(math.atan2(dz, math.hypot(dx, dy))), math.degrees(math.atan2(dy, dx)))


def forward_vector(rotation_deg):
    return rotate_vector(rotation_deg, (1.0, 0.0, 0.0))


def normalized(vector):
    length = math.sqrt(sum(float(v) * float(v) for v in vector))
    if length <= 1e-9:
        raise ValueError("cannot normalize a zero vector")
    return tuple(float(v) / length for v in vector)


def dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def require_aim(forward, origin, target, minimum=AIM_DOT_MIN):
    value = dot(normalized(forward), normalized(tuple(float(target[i]) - float(origin[i]) for i in range(3))))
    if value <= float(minimum):
        raise ValueError(f"aim dot {value:.6f} is not > {minimum}")
    return value


def plan_intensity_keys(strike_s, reveal_s, intensity):
    """Pure three-key strike plan, rejecting a strike at/before the reveal."""
    strike_s, reveal_s, intensity = float(strike_s), float(reveal_s), float(intensity)
    if not reveal_s < strike_s:
        raise ValueError(f"required REVEAL_S < STRIKE_S, found {reveal_s} >= {strike_s}")
    if intensity <= 0.0:
        raise ValueError(f"intensity must be positive, found {intensity}")
    return [[0.0, 0.0], [strike_s, 0.0], [strike_s + STRIKE_RAMP_S, intensity]]


def validate_shadow_count(light_specs):
    count = sum(1 for spec in light_specs if bool(spec["shadows"]))
    if count != 1:
        raise ValueError(f"expected exactly one shadowed light, found {count}")
    return count


def fail(run, message):
    unreal.log_error(f"S3_STRIKE_STOPPED|run={run}|{message}")
    raise RuntimeError(message)


def package_census():
    return {
        "dirty_maps": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "dirty_content": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def all_level_actors(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def one_actor(actors, label, run):
    found = [actor for actor in actors if str(actor.get_actor_label()) == label]
    if len(found) != 1:
        fail(run, f"expected one level actor {label!r}, found {len(found)}")
    return found[0]


def guid_text(guid):
    return str(unreal.GuidLibrary.conv_guid_to_string(guid))


def object_path(value):
    if value is None:
        return "None"
    return str(value.get_path_name()) if hasattr(value, "get_path_name") else str(value)


def keys_of(channel, fps):
    return [[key.get_time().frame_number.value / fps, float(key.get_value())] for key in channel.get_keys()]


def keys_match(got, expected, fps):
    if len(got) != len(expected):
        return False
    return all(
        abs(float(gt) - float(wt)) <= 1.0 / fps + 1e-9 and abs(float(gv) - float(wv)) <= KEY_VALUE_TOLERANCE
        for (gt, gv), (wt, wv) in zip(got, expected)
    )


def interpolation_matches(channel, kind):
    wanted = {"LINEAR": "RCIM_LINEAR", "AUTO": "RCIM_CUBIC"}[kind]
    keys = list(channel.get_keys())
    return bool(keys) and all(
        hasattr(key, "get_interpolation_mode") and key.get_interpolation_mode().name == wanted for key in keys
    )


def one_binding(sequence, label, run):
    found = [binding for binding in sequence.get_bindings() if str(binding.get_display_name()) == label]
    if len(found) != 1:
        fail(run, f"expected one sequence binding {label!r}, found {len(found)}")
    return found[0]


def one_float_channel(binding, property_name, run):
    channels = []
    for track in binding.get_tracks():
        if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == property_name:
            for section in track.get_sections():
                channels.extend(section.get_all_channels())
    if len(channels) != 1:
        fail(run, f"expected one {property_name} channel on {binding.get_display_name()}, found {len(channels)}")
    return channels[0]


def root_window(sequence, fps, run):
    binding = one_binding(sequence, ROOT_LABEL, run)
    channels = []
    for track in binding.get_tracks():
        if isinstance(track, unreal.MovieScene3DTransformTrack):
            for section in track.get_sections():
                all_channels = section.get_all_channels()
                if len(all_channels) > 4:
                    channels.append(all_channels[4])
    if len(channels) != 1:
        fail(run, f"expected one root pitch channel, found {len(channels)}")
    channel = channels[0]
    keys = keys_of(channel, fps)
    if len(keys) != 2 or abs(keys[0][1] + 90.0) > KEY_VALUE_TOLERANCE or abs(keys[1][1]) > KEY_VALUE_TOLERANCE:
        fail(run, f"step 1 prerequisite absent; root keys are {keys}")
    if not keys[0][0] < 0.0 < keys[1][0] or not interpolation_matches(channel, "AUTO"):
        fail(run, f"step 1 root window/interpolation is invalid: {keys}")
    return float(keys[0][0]), float(keys[1][0]), keys


def intensity_bindings(sequence, prefix, run):
    found = {}
    for binding in sequence.get_bindings():
        parent = binding.get_parent()
        parent_name = str(parent.get_display_name()) if parent and parent.is_valid() else None
        own_name = str(binding.get_display_name())
        label = parent_name if parent_name and parent_name.startswith(prefix) else own_name if own_name.startswith(prefix) else None
        if label is None:
            continue
        channels = []
        for track in binding.get_tracks():
            if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == "Intensity":
                for section in track.get_sections():
                    channels.extend(section.get_all_channels())
        if len(channels) == 1:
            if label in found:
                fail(run, f"duplicate Intensity binding for {label}")
            found[label] = {"binding": binding, "channel": channels[0]}
    return found


def read_strike_s(sequence, fps, run):
    uplights = intensity_bindings(sequence, UPLIGHT_PREFIX, run)
    if not uplights:
        fail(run, "no S3 uplight Intensity channels found")
    starts = []
    evidence = {}
    for label, row in sorted(uplights.items()):
        keys = keys_of(row["channel"], fps)
        candidates = [keys[i][0] for i in range(len(keys) - 1)
                      if abs(keys[i][1]) <= KEY_VALUE_TOLERANCE and keys[i + 1][1] > KEY_VALUE_TOLERANCE]
        if len(candidates) != 1:
            fail(run, f"{label}: expected one zero-to-positive strike ramp, found {keys}")
        starts.append(candidates[0])
        evidence[label] = keys
    return min(starts), evidence


def _first_editor_property(obj, candidates, run, semantic):
    for name in candidates:
        try:
            obj.get_editor_property(name)
            return name
        except Exception:
            pass
    fail(run, f"could not discover {semantic}")


def discover_drive_api(arrival, run):
    probe = unreal.InfinityArrivalFloatDrive()
    fields = {
        "target": _first_editor_property(probe, ("target",), run, "float-drive Target"),
        "binding_guid": _first_editor_property(probe, ("binding_guid", "bindingguid"), run, "float-drive BindingGuid"),
        "property_name": _first_editor_property(probe, ("property_name", "propertyname"), run, "float-drive PropertyName"),
    }
    arrival_property = _first_editor_property(
        arrival, ("pre_scene_float_drives", "prescene_float_drives"), run, "Arrival PreSceneFloatDrives"
    )
    return {"struct_fields": fields, "arrival_property": arrival_property}


def plain_drive(drive, api):
    fields = api["struct_fields"]
    return {
        "target": object_path(drive.get_editor_property(fields["target"])),
        "binding_guid": guid_text(drive.get_editor_property(fields["binding_guid"])),
        "property_name": str(drive.get_editor_property(fields["property_name"])),
    }


def capture_drives(arrival, api):
    entries = [plain_drive(drive, api) for drive in list(arrival.get_editor_property(api["arrival_property"]))]
    return {"count": len(entries), "entries": entries}


def make_drive(target, binding_guid, property_name, api):
    fields = api["struct_fields"]
    drive = unreal.InfinityArrivalFloatDrive()
    drive.set_editor_property(fields["target"], target)
    drive.set_editor_property(fields["binding_guid"], binding_guid)
    drive.set_editor_property(fields["property_name"], property_name)
    return drive


def current_object_index(actors):
    out = {}
    for actor in actors:
        out[object_path(actor)] = actor
        for component in actor.get_components_by_class(unreal.ActorComponent):
            out[object_path(component)] = component
    return out


def restore_drive_structs(recorded, actors, sequence, api, run):
    objects = current_object_index(actors)
    guids = {guid_text(binding.get_id()): binding.get_id() for binding in sequence.get_bindings()}
    structs = []
    for index, row in enumerate(recorded["entries"]):
        target = None if row["target"] == "None" else objects.get(row["target"])
        binding_guid = guids.get(row["binding_guid"])
        if (target is None and row["target"] != "None") or binding_guid is None:
            fail(run, f"cannot restore prior drive {index}: {row}")
        structs.append(make_drive(target, binding_guid, row["property_name"], api))
    if len(structs) != int(recorded["count"]):
        fail(run, "recorded drive count does not match its entries")
    return structs


def drive_state_matches(got, wanted):
    return got.get("count") == wanted.get("count") and got.get("entries") == wanted.get("entries")


def read_json(path, run, purpose):
    if not os.path.exists(path):
        fail(run, f"missing {purpose}: {path}")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_hangar_plan(run):
    data = read_json(PLAN_RECORD, run, "S3 hangar plan")
    hangar, dock = data.get("hangar"), data.get("dock")
    if not isinstance(hangar, dict) or not isinstance(dock, dict):
        fail(run, "hangar_s3_plan.json is missing hangar or dock")
    required = ("apron", "depth", "half_w", "height", "pinned_ev100")
    if any(name not in hangar for name in required) or not isinstance(dock.get("loc"), list) or "yaw" not in dock:
        fail(run, "hangar_s3_plan.json lacks PPV geometry/exposure values")
    span = float(hangar["apron"]) + float(hangar["depth"]) + 200.0
    local = (span / 2.0 - 100.0, 0.0, float(hangar["height"]) / 2.0)
    dock_loc = (float(dock["loc"][0]), float(dock["loc"][1]), 0.0)
    dock_rot = (0.0, 0.0, float(dock["yaw"]))
    return {
        "pinned_ev100": float(hangar["pinned_ev100"]),
        "location": root_relative_to_world(dock_loc, dock_rot, local),
        "rotation": dock_rot,
        "scale": (span / 200.0, (2.0 * float(hangar["half_w"]) + 200.0) / 200.0,
                  (float(hangar["height"]) + 200.0) / 200.0),
        "light_attenuation_radius": float(hangar["height"]) + float(hangar["depth"]) + HANGAR_LIGHT_MARGIN_CM,
        "span": span,
    }


def assert_common_guards(editor, world, actors, run, revert):
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or editor.get_game_world() is not None:
        fail(run, "wrong world, or PIE")
    census = package_census()
    if census["dirty_maps"] or census["dirty_content"]:
        fail(run, f"packages already dirty: {census}")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail(run, "Sequencer is open")
    temps = sorted(str(a.get_actor_label()) for a in actors
                   if str(a.get_actor_label()).startswith(("ZZ_", "TEMP_"))
                   or str(a.get_name()).startswith(("ZZ_", "TEMP_")))
    if temps:
        fail(run, f"temporary actors present: {temps}")
    if revert and not os.path.exists(RECORD):
        fail(run, "revert record is absent")
    if not revert and os.path.exists(RECORD):
        fail(run, "record already exists; revert first")
    if not os.path.exists(CAST_RECORD):
        fail(run, f"cast reveal prerequisite record absent: {CAST_RECORD}")
    if not revert:
        conflicts = sorted(str(a.get_actor_label()) for a in actors
                           if str(a.get_actor_label()).startswith(STRIKE_PREFIX)
                           or str(a.get_actor_label()) == EXPOSURE_LABEL)
        if conflicts:
            fail(run, f"strike/exposure actors already exist: {conflicts}")


def write_record(record):
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def backup_files(stamp, project):
    backup = os.path.join(project, "Backups", "PreS3Strike-" + stamp.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=False)
    level_file = os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap"
    sequence_file = os.path.join(project, "Content", *SEQUENCE_PATH[len("/Game/"):].split("/")) + ".uasset"
    for path in (level_file, sequence_file, RECORD):
        if not os.path.isfile(path):
            fail(stamp.strftime("%H%M%S"), f"backup source missing: {path}")
        shutil.copy2(path, backup)
    return backup


def angular_error(a, b):
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def tuple3(value):
    return tuple(float(v) for v in value.to_tuple())


def actor_pose(actor):
    rotation = actor.get_actor_rotation()
    return {
        "location": tuple3(actor.get_actor_location()),
        "rotation": (float(rotation.roll), float(rotation.pitch), float(rotation.yaw)),
        "scale": tuple3(actor.get_actor_scale3d()),
    }


def component_mobility_name(component):
    value = component.get_editor_property("mobility")
    return value.name if hasattr(value, "name") else str(value).split(".")[-1]


def binding_map(sequence):
    return {guid_text(binding.get_id()): binding for binding in sequence.get_bindings()}


def verify_applied(record, sequence, actors, root, arrival, api, fps, world, run):
    by_label = {}
    for actor in actors:
        by_label.setdefault(str(actor.get_actor_label()), []).append(actor)
    bindings = binding_map(sequence)
    bad = []
    live_root_pose = actor_pose(root)
    expected_root_pose = record["root_pose"]
    if (math.dist(live_root_pose["location"], expected_root_pose["location"]) > TRANSFORM_TOLERANCE_CM
            or math.dist(live_root_pose["scale"], expected_root_pose["scale"]) > 1e-3
            or any(angular_error(live_root_pose["rotation"][i], expected_root_pose["rotation"][i])
                   > ROTATION_TOLERANCE_DEG for i in range(3))):
        bad.append(f"root-pose-changed:{live_root_pose}")
    root_loc = tuple3(root.get_actor_location())
    root_rot_live = root.get_actor_rotation()
    landed_root_rot = (float(root_rot_live.roll), 0.0, float(root_rot_live.yaw))
    for spec in record["light_specs"]:
        matches = by_label.get(spec["label"], [])
        if len(matches) != 1:
            bad.append(f"{spec['label']}:actors={len(matches)}")
            continue
        actor = matches[0]
        if object_path(actor) != spec["actor_path"] or actor.get_attach_parent_actor() != root:
            bad.append(f"{spec['label']}:path-or-parent")
        rel_loc = tuple3(actor.root_component.get_editor_property("relative_location"))
        rel_rot_obj = actor.root_component.get_editor_property("relative_rotation")
        rel_rot = (float(rel_rot_obj.roll), float(rel_rot_obj.pitch), float(rel_rot_obj.yaw))
        rel_scale = tuple3(actor.root_component.get_editor_property("relative_scale3d"))
        if math.dist(rel_loc, spec["location"]) > TRANSFORM_TOLERANCE_CM:
            bad.append(f"{spec['label']}:location={rel_loc}")
        if any(angular_error(rel_rot[i], spec["rotation"][i]) > ROTATION_TOLERANCE_DEG for i in range(3)):
            bad.append(f"{spec['label']}:rotation={rel_rot}")
        if math.dist(rel_scale, (1.0, 1.0, 1.0)) > 1e-3:
            bad.append(f"{spec['label']}:scale={rel_scale}")
        component = actor.get_component_by_class(unreal.RectLightComponent)
        if component is None:
            bad.append(f"{spec['label']}:no-rect-component")
            continue
        units = component.get_editor_property("intensity_units")
        units_name = units.name if hasattr(units, "name") else str(units).split(".")[-1]
        checks = (
            component_mobility_name(component) == "MOVABLE",
            abs(float(component.get_editor_property("source_width")) - spec["rect"][0]) <= 1e-3,
            abs(float(component.get_editor_property("source_height")) - spec["rect"][1]) <= 1e-3,
            abs(float(component.get_editor_property("intensity")) - spec["intensity"]) <= KEY_VALUE_TOLERANCE,
            abs(float(component.get_editor_property("attenuation_radius")) - spec["attenuation_radius"]) <= 1e-3,
            units_name == "CANDELAS",
            bool(component.get_editor_property("use_temperature")),
            abs(float(component.get_editor_property("temperature")) - spec["temperature"]) <= KEY_VALUE_TOLERANCE,
            bool(component.get_editor_property("cast_shadows")) == bool(spec["shadows"]),
        )
        if not all(checks):
            bad.append(f"{spec['label']}:light-properties")
        landed_origin = root_relative_to_world(root_loc, landed_root_rot, rel_loc)
        landed_target = root_relative_to_world(root_loc, landed_root_rot, spec["target"])
        landed_forward = rotate_vector(landed_root_rot, forward_vector(rel_rot))
        try:
            aim_dot = require_aim(landed_forward, landed_origin, landed_target)
        except ValueError as exc:
            bad.append(f"{spec['label']}:{exc}")
            aim_dot = -1.0
        spec["readback_aim_dot"] = aim_dot
        binding = bindings.get(spec["binding_guid"])
        if binding is None:
            bad.append(f"{spec['label']}:binding-missing")
        else:
            resolved = sorted(object_path(value) for value in sequence.locate_bound_objects(binding, world))
            if resolved != [spec["component_path"]]:
                bad.append(f"{spec['label']}:binding-resolves={resolved}")
            channel = one_float_channel(binding, "Intensity", run)
            if not keys_match(keys_of(channel, fps), spec["keys"], fps) or not interpolation_matches(channel, "LINEAR"):
                bad.append(f"{spec['label']}:keys")

    exposure_row = record["exposure"]
    exposure_matches = by_label.get(EXPOSURE_LABEL, [])
    if len(exposure_matches) != 1:
        bad.append(f"{EXPOSURE_LABEL}:actors={len(exposure_matches)}")
    else:
        exposure = exposure_matches[0]
        if object_path(exposure) != exposure_row["actor_path"] or exposure.get_attach_parent_actor() is not None:
            bad.append("exposure:path-or-parent")
        loc = tuple3(exposure.get_actor_location())
        rot_obj = exposure.get_actor_rotation()
        rot = (float(rot_obj.roll), float(rot_obj.pitch), float(rot_obj.yaw))
        scale = tuple3(exposure.get_actor_scale3d())
        if math.dist(loc, exposure_row["location"]) > TRANSFORM_TOLERANCE_CM:
            bad.append(f"exposure:location={loc}")
        if any(angular_error(rot[i], exposure_row["rotation"][i]) > ROTATION_TOLERANCE_DEG for i in range(3)):
            bad.append(f"exposure:rotation={rot}")
        if math.dist(scale, exposure_row["scale"]) > 1e-3:
            bad.append(f"exposure:scale={scale}")
        settings = exposure.get_editor_property("settings")
        ev = exposure_row["pinned_ev100"]
        exposure_ok = (
            not bool(exposure.get_editor_property("unbound"))
            and abs(float(exposure.get_editor_property("blend_weight"))) <= KEY_VALUE_TOLERANCE
            and bool(settings.get_editor_property("override_auto_exposure_min_brightness"))
            and bool(settings.get_editor_property("override_auto_exposure_max_brightness"))
            and abs(float(settings.get_editor_property("auto_exposure_min_brightness")) - ev) <= KEY_VALUE_TOLERANCE
            and abs(float(settings.get_editor_property("auto_exposure_max_brightness")) - ev) <= KEY_VALUE_TOLERANCE
            and bool(settings.get_editor_property("override_local_exposure_highlight_contrast_scale"))
            and bool(settings.get_editor_property("override_local_exposure_shadow_contrast_scale"))
            and abs(float(settings.get_editor_property("local_exposure_highlight_contrast_scale")) - 1.0)
            <= KEY_VALUE_TOLERANCE
            and abs(float(settings.get_editor_property("local_exposure_shadow_contrast_scale")) - 1.0)
            <= KEY_VALUE_TOLERANCE
        )
        if not exposure_ok:
            bad.append("exposure:settings")
        binding = bindings.get(exposure_row["binding_guid"])
        if binding is None:
            bad.append("exposure:binding-missing")
        else:
            resolved = sorted(object_path(value) for value in sequence.locate_bound_objects(binding, world))
            if resolved != [exposure_row["actor_path"]]:
                bad.append(f"exposure:binding-resolves={resolved}")
            channel = one_float_channel(binding, "BlendWeight", run)
            if not keys_match(keys_of(channel, fps), exposure_row["keys"], fps) or not interpolation_matches(channel, "AUTO"):
                bad.append("exposure:keys")

    got_drives = capture_drives(arrival, api)
    if not drive_state_matches(got_drives, record["after_drives"]):
        bad.append(f"drives:{got_drives}")
    before = record["before_drives"]
    after = record["after_drives"]
    if after["count"] != before["count"] + 1 or after["entries"][:-1] != before["entries"]:
        bad.append("drives:existing-entries-changed")
    if bad:
        fail(run, f"applied read-back failed; NOTHING saved: {bad[:12]}")
    return {spec["label"]: round(float(spec["readback_aim_dot"]), 6) for spec in record["light_specs"]}


def expected_dirty(run):
    census = package_census()
    if census["dirty_maps"] != [EXPECTED_WORLD] or census["dirty_content"] != [SEQUENCE_PATH]:
        fail(run, f"dirty set is not exactly the level and rise sequence; NOTHING saved: {census}")


def save_two(sequence, run):
    if not unreal.EditorAssetLibrary.save_asset(SEQUENCE_PATH, only_if_is_dirty=False):
        fail(run, "sequence save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail(run, "level save failed")
    census = package_census()
    if census["dirty_maps"] or census["dirty_content"]:
        fail(run, f"post-save packages are dirty: {census}")
    return census


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3STRIKE_APPLY"))
    revert = bool(globals().get("S3STRIKE_REVERT"))
    if apply and revert:
        fail(run, "apply and revert modes are mutually exclusive")

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    actors = all_level_actors(world) if world else []
    assert_common_guards(editor, world, actors, run, revert)
    sequence = unreal.load_asset(SEQUENCE_PATH)
    if sequence is None:
        fail(run, f"sequence missing: {SEQUENCE_PATH}")
    rate = sequence.get_display_rate()
    fps = float(rate.numerator) / float(rate.denominator)
    if fps <= 0.0:
        fail(run, f"invalid display rate: {rate}")
    W0, W1, root_keys = root_window(sequence, fps, run)
    reveal_s = W1 + REVEAL_DELAY_S
    strike_s, uplight_keys = read_strike_s(sequence, fps, run)
    if abs(strike_s - (W1 + EXPECTED_STRIKE_AFTER_W1_S)) > 1.0 / fps + 1e-9:
        fail(run, f"first uplight strike is not W1 + 2.0: W1={W1}, STRIKE_S={strike_s}")
    try:
        validate_shadow_count(LIGHT_SPECS)
        planned_lights = []
        for source in LIGHT_SPECS:
            row = copy.deepcopy(source)
            row["rotation"] = look_at_rotation(row["location"], row["target"])
            row["keys"] = plan_intensity_keys(strike_s, reveal_s, row["intensity"])
            planned_lights.append(row)
    except ValueError as exc:
        fail(run, f"planning failed: {exc}")
    exposure_plan = read_hangar_plan(run)
    exposure_plan["keys"] = [[W0, 0.0], [W1, 1.0]]
    for row in planned_lights:
        row["attenuation_radius"] = exposure_plan["light_attenuation_radius"]
    root = one_actor(actors, ROOT_LABEL, run)
    root_pose = actor_pose(root)
    if abs(float(root_pose["rotation"][1]) + 90.0) > ROTATION_TOLERANCE_DEG:
        fail(run, f"saved root pose is not hanging at pitch -90: {root_pose}")
    arrival = one_actor(actors, ARRIVAL_LABEL, run)
    if not isinstance(arrival, unreal.InfinityStageArrival):
        fail(run, f"{ARRIVAL_LABEL} is not an InfinityStageArrival")
    api = discover_drive_api(arrival, run)
    current_drives = capture_drives(arrival, api)

    plan_log = {
        "W0": W0, "W1": W1, "REVEAL_S": reveal_s, "STRIKE_S": strike_s,
        "root_keys": root_keys, "uplight_keys": uplight_keys,
        "root_pose": root_pose, "lights": planned_lights, "exposure": exposure_plan, "before_drives": current_drives,
    }
    unreal.log(f"S3_STRIKE_PLAN|run={run}|{json.dumps(plan_log, sort_keys=True)}")
    if not (apply or revert):
        unreal.log(f"S3_STRIKE_DRY_RUN_OK|run={run}|mutated=0|{json.dumps(package_census(), sort_keys=True)}")
        return

    if revert:
        with open(RECORD, encoding="utf-8") as handle:
            record = json.load(handle)
        if abs(float(record["W0"]) - W0) > 1.0 / fps or abs(float(record["W1"]) - W1) > 1.0 / fps:
            fail(run, "revert refused: root window drifted")
        verify_applied(record, sequence, actors, root, arrival, api, fps, world, run)
        restored = restore_drive_structs(record["before_drives"], actors, sequence, api, run)
        arrival.set_editor_property(api["arrival_property"], restored)
        wanted_guids = set(record["created_binding_guids"])
        current = [binding for binding in sequence.get_bindings() if guid_text(binding.get_id()) in wanted_guids]
        if len(current) != len(wanted_guids):
            fail(run, f"revert binding census mismatch: wanted={len(wanted_guids)}, found={len(current)}")
        current.sort(key=lambda binding: 0 if binding.get_parent() and binding.get_parent().is_valid() else 1)
        for binding in current:
            binding.remove()
        by_path = {object_path(actor): actor for actor in actors}
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for actor_path in record["created_actor_paths"]:
            actor = by_path.get(actor_path)
            if actor is None or not subsystem.destroy_actor(actor):
                fail(run, f"could not destroy recorded actor {actor_path}; NOTHING saved")
        remaining_paths = {object_path(actor) for actor in all_level_actors(world)}
        remaining_guids = set(binding_map(sequence))
        got_drives = capture_drives(arrival, api)
        if (remaining_paths.intersection(record["created_actor_paths"])
                or remaining_guids.intersection(wanted_guids)
                or not drive_state_matches(got_drives, record["before_drives"])):
            fail(run, "revert read-back failed; NOTHING saved")
        expected_dirty(run)
        census = save_two(sequence, run)
        os.rename(RECORD, RECORD + ".reverted-" + run)
        unreal.log(f"S3_STRIKE_DONE|run={run}|reverted|actors={len(record['created_actor_paths'])}|"
                   f"bindings={len(wanted_guids)}|census={json.dumps(census, sort_keys=True)}")
        return

    stamp = datetime.datetime.now()
    record = {
        "written": stamp.isoformat(timespec="seconds"), "run": run,
        "W0": W0, "W1": W1, "REVEAL_S": reveal_s, "STRIKE_S": strike_s, "fps": fps,
        "root_keys": root_keys, "uplight_keys": uplight_keys,
        "root_pose": root_pose,
        "light_specs": planned_lights, "exposure": exposure_plan,
        "before_drives": copy.deepcopy(current_drives), "after_drives": None,
        "created_actor_paths": [], "created_binding_guids": [],
    }
    write_record(record)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = backup_files(stamp, project)
    record["backup"] = backup
    write_record(record)

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    for spec in record["light_specs"]:
        actor = subsystem.spawn_actor_from_class(unreal.RectLight, root.get_actor_location(), root.get_actor_rotation())
        actor.set_actor_label(spec["label"])
        actor.set_folder_path(FOLDER)
        actor.set_editor_property("tags", [unreal.Name("RigAtmos.Scene3Strike"), unreal.Name("Light|role=strike")])
        actor.attach_to_actor(root, unreal.Name("None"), unreal.AttachmentRule.KEEP_RELATIVE,
                              unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE, False)
        actor.set_actor_relative_location(unreal.Vector(*spec["location"]), False, True)
        rotation = spec["rotation"]
        actor.set_actor_relative_rotation(
            unreal.Rotator(roll=rotation[0], pitch=rotation[1], yaw=rotation[2]), False, True
        )
        component = actor.get_component_by_class(unreal.RectLightComponent)
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_editor_property("source_width", spec["rect"][0])
        component.set_editor_property("source_height", spec["rect"][1])
        component.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        component.set_editor_property("intensity", spec["intensity"])
        component.set_editor_property("attenuation_radius", spec["attenuation_radius"])
        component.set_editor_property("use_temperature", True)
        component.set_editor_property("temperature", spec["temperature"])
        component.set_editor_property("cast_shadows", spec["shadows"])
        spec["actor_path"] = object_path(actor)
        spec["component_path"] = object_path(component)
        record["created_actor_paths"].append(spec["actor_path"])
        spawned.append((spec, actor, component))
        write_record(record)

    ppv_data = record["exposure"]
    ppv = subsystem.spawn_actor_from_class(
        unreal.PostProcessVolume, unreal.Vector(*ppv_data["location"]),
        unreal.Rotator(roll=ppv_data["rotation"][0], pitch=ppv_data["rotation"][1], yaw=ppv_data["rotation"][2])
    )
    ppv.set_actor_label(EXPOSURE_LABEL)
    ppv.set_folder_path(FOLDER)
    ppv.set_editor_property("tags", [unreal.Name("RigAtmos.Scene3Strike"), unreal.Name("PostProcess|exposure=pinned")])
    ppv.set_actor_scale3d(unreal.Vector(*ppv_data["scale"]))
    ppv.set_editor_property("unbound", False)
    ppv.set_editor_property("blend_weight", 0.0)
    settings = ppv.get_editor_property("settings")
    for name, value in (
        ("auto_exposure_min_brightness", ppv_data["pinned_ev100"]),
        ("auto_exposure_max_brightness", ppv_data["pinned_ev100"]),
        ("local_exposure_highlight_contrast_scale", 1.0),
        ("local_exposure_shadow_contrast_scale", 1.0),
    ):
        settings.set_editor_property("override_" + name, True)
        settings.set_editor_property(name, value)
    ppv.set_editor_property("settings", settings)
    ppv_data["actor_path"] = object_path(ppv)
    record["created_actor_paths"].append(ppv_data["actor_path"])
    write_record(record)

    before_binding_guids = set(binding_map(sequence))
    end_frame = int(round(sequence.get_playback_end_seconds() * fps))
    frame = lambda seconds: unreal.FrameNumber(int(round(float(seconds) * fps)))
    for spec, _actor, component in spawned:
        binding = sequence.add_possessable(component)
        track = binding.add_track(unreal.MovieSceneFloatTrack)
        track.set_property_name_and_path("Intensity", "Intensity")
        section = track.add_section()
        section.set_range(0, end_frame)
        channel = section.get_all_channels()[0]
        for time_s, value in spec["keys"]:
            channel.add_key(frame(time_s), float(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                            interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        spec["binding_guid"] = guid_text(binding.get_id())
    exposure_binding = sequence.add_possessable(ppv)
    exposure_track = exposure_binding.add_track(unreal.MovieSceneFloatTrack)
    exposure_track.set_property_name_and_path("BlendWeight", "BlendWeight")
    exposure_section = exposure_track.add_section()
    exposure_section.set_range(0, end_frame)
    exposure_channel = exposure_section.get_all_channels()[0]
    for time_s, value in ppv_data["keys"]:
        exposure_channel.add_key(frame(time_s), float(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                 interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
    ppv_data["binding_guid"] = guid_text(exposure_binding.get_id())
    record["created_binding_guids"] = sorted(set(binding_map(sequence)) - before_binding_guids)

    old_structs = list(arrival.get_editor_property(api["arrival_property"]))
    old_structs.append(make_drive(ppv, exposure_binding.get_id(), "BlendWeight", api))
    arrival.set_editor_property(api["arrival_property"], old_structs)
    record["after_drives"] = capture_drives(arrival, api)
    write_record(record)

    actors_after = all_level_actors(world)
    aim = verify_applied(record, sequence, actors_after, root, arrival, api, fps, world, run)
    expected_dirty(run)
    census = save_two(sequence, run)
    unreal.log(f"S3_STRIKE_DONE|run={run}|applied|actors={len(record['created_actor_paths'])}|"
               f"bindings={len(record['created_binding_guids'])}|aim={json.dumps(aim, sort_keys=True)}|"
               f"backup={backup}|census={json.dumps(census, sort_keys=True)}")


if unreal is not None:
    main()
