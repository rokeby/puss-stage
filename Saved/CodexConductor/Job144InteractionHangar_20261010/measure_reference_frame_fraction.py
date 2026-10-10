"""Read-only I1/I4/I5 curtain framing measurement for Job 144."""
import json
import math
import os
import re

import unreal


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQS = {
    1: "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy",
    4: "/Game/InfinityStage/Interactions/LS_Interaction_04_GetsAName",
    5: "/Game/InfinityStage/Interactions/LS_Interaction_05_BecomesKing",
}
CURTAIN_WIDTH_CM = 1880.0
CURTAIN_HEIGHT_CM = 1000.0


def canonical(value):
    return re.sub(r"\s*(?:\(\d+\)|_\d+|\s+\d+)$", "", str(value).strip())


def cname(value):
    return re.sub(r"_\d+$", "", str(value))


def keys(channel):
    rows = []
    for key in channel.get_keys():
        frame = int(key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value)
        value = key.get_value()
        rows.append([frame, bool(value) if isinstance(value, bool) else float(value)])
    return sorted(rows)


def interp(rows, frame, default=0.0):
    if not rows:
        return float(default)
    if frame <= rows[0][0]:
        return float(rows[0][1])
    if frame >= rows[-1][0]:
        return float(rows[-1][1])
    for left, right in zip(rows, rows[1:]):
        if left[0] <= frame <= right[0]:
            if left[0] == right[0]:
                return float(right[1])
            alpha = (frame - left[0]) / float(right[0] - left[0])
            return float(left[1]) + (float(right[1]) - float(left[1])) * alpha
    return float(rows[-1][1])


def markers(seq):
    tick = seq.get_tick_resolution().numerator / float(seq.get_tick_resolution().denominator)
    fps = seq.get_display_rate().numerator / float(seq.get_display_rate().denominator)
    return {str(m.label): int(round(int(m.frame_number.value) / (tick / fps)))
            for m in unreal.MovieSceneSequenceExtensions.get_marked_frames(seq)}


def binding(seq, wanted):
    rows = [b for b in seq.get_bindings() if canonical(b.get_display_name()) == wanted]
    if len(rows) != 1:
        raise RuntimeError("BINDING_COUNT|%s|%d" % (wanted, len(rows)))
    return rows[0]


def pose(bound, frame):
    tracks = [t for t in bound.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        raise RuntimeError("POSE_TRACK_COUNT|%s|%d" % (bound.get_display_name(), len(tracks)))
    channels = {cname(ch.channel_name): keys(ch) for ch in tracks[0].get_sections()[0].get_all_channels()}
    names = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z")
    if any(name not in channels for name in names):
        raise RuntimeError("POSE_CHANNELS|%s|%s" % (bound.get_display_name(), sorted(channels)))
    values = {name: interp(channels[name], frame) for name in names}
    scale = [interp(channels.get("Scale.X", []), frame, 1.0),
             interp(channels.get("Scale.Y", []), frame, 1.0),
             interp(channels.get("Scale.Z", []), frame, 1.0)]
    return {
        "loc": [values["Location.X"], values["Location.Y"], values["Location.Z"]],
        "roll": values["Rotation.X"], "pitch": values["Rotation.Y"], "yaw": values["Rotation.Z"],
        "scale": scale,
    }


def active_camera(seq, frame):
    by_guid = {str(unreal.GuidLibrary.conv_guid_to_string(b.get_id())).replace("-", "").replace("{", "").replace("}", "").upper(): b
               for b in seq.get_bindings()}
    rows = []
    for track in seq.get_tracks():
        if track.get_class().get_name() != "MovieSceneCameraCutTrack":
            continue
        for section in track.get_sections():
            start = int(section.get_start_frame()) if section.has_start_frame() else int(seq.get_playback_start())
            end = int(section.get_end_frame()) if section.has_end_frame() else int(seq.get_playback_end())
            if section.is_active() and start <= frame < end:
                guid = str(unreal.GuidLibrary.conv_guid_to_string(section.get_camera_binding_id().get_editor_property("guid"))).replace("-", "").replace("{", "").replace("}", "").upper()
                rows.append(by_guid.get(guid))
    rows = [row for row in rows if row is not None]
    if len(rows) != 1:
        raise RuntimeError("ACTIVE_CAMERA_COUNT|frame=%d|count=%d" % (frame, len(rows)))
    return rows[0]


def shadow_frame(seq, marks):
    hung = [value for name, value in marks.items() if "curtain hung" in name.lower()]
    sleight = [value for name, value in marks.items() if "sleight" in name.lower()]
    if len(hung) != 1 or len(sleight) != 1:
        raise RuntimeError("BEAT_MARKERS|hung=%s|sleight=%s" % (hung, sleight))
    lo, hi = hung[0] + 1, sleight[0] - 1
    candidates = []
    for bound in seq.get_bindings():
        name = str(bound.get_display_name())
        if not re.search(r"shadow|spot|gobo|puppet", name, re.I):
            continue
        for track in bound.get_tracks():
            prop = str(track.get_property_name()) if hasattr(track, "get_property_name") else ""
            if track.get_class().get_name() != "MovieSceneFloatTrack" or prop != "Intensity":
                continue
            for section in track.get_sections():
                for channel in section.get_all_channels():
                    positive = [f for f, v in keys(channel) if lo <= f <= hi and float(v) > 1.0e-4]
                    if positive:
                        candidates.append({"binding": name, "frames": positive})
    if candidates:
        all_frames = sorted(f for row in candidates for f in row["frames"])
        return int(round((all_frames[0] + all_frames[-1]) * 0.5)), candidates
    return int(round((lo + hi) * 0.5)), []


def camera_lens(bound):
    template = bound.get_object_template()
    component = None
    if template is not None:
        try:
            component = template.get_component_by_class(unreal.CineCameraComponent)
        except Exception:
            component = None
    if component is None:
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        matches = [a for a in actors if canonical(a.get_actor_label()) == canonical(bound.get_display_name())]
        if len(matches) == 1:
            component = matches[0].get_component_by_class(unreal.CineCameraComponent)
    if component is None:
        raise RuntimeError("CINE_CAMERA_COMPONENT|%s" % bound.get_display_name())
    film = component.get_editor_property("filmback")
    return float(film.sensor_width), float(film.sensor_height), float(component.get_editor_property("current_focal_length"))


def curtain_template_inventory(bound):
    template = bound.get_object_template()
    row = {"template": str(template.get_path_name()) if template is not None else None,
           "class": template.get_class().get_name() if template is not None else None,
           "components": []}
    if template is None:
        return row
    try:
        direct = template.get_editor_property("geometry_cache_component")
        if direct is not None:
            components = [direct]
        else:
            components = []
    except Exception:
        components = []
    try:
        for component in template.get_components_by_class(unreal.ActorComponent):
            if component not in components:
                components.append(component)
    except Exception:
        pass
    for component in components:
        item = {"name": component.get_name(), "class": component.get_class().get_name()}
        for prop in ("static_mesh", "skeletal_mesh_asset", "skeletal_mesh", "geometry_cache"):
            try:
                asset = component.get_editor_property(prop)
            except Exception:
                continue
            if asset is None:
                continue
            item[prop] = str(asset.get_path_name())
            try:
                bounds = asset.get_bounds()
                extent = bounds.box_extent
                item[prop + "_box_extent_cm"] = [float(extent.x), float(extent.y), float(extent.z)]
            except Exception as exc:
                item[prop + "_bounds_error"] = repr(exc)
        row["components"].append(item)
    return row


def focal_at_frame(seq, camera, frame, fallback):
    camera_name = canonical(camera.get_display_name())
    values = []
    for bound in seq.get_bindings():
        name = canonical(bound.get_display_name())
        if camera_name not in name or "component" not in name.lower():
            continue
        for track in bound.get_tracks():
            prop = str(track.get_property_name()) if hasattr(track, "get_property_name") else ""
            if prop not in ("CurrentFocalLength", "current_focal_length"):
                continue
            for section in track.get_sections():
                channels = list(section.get_all_channels())
                if channels:
                    values.append(interp(keys(channels[0]), frame, fallback))
    if len(values) > 1:
        raise RuntimeError("FOCAL_TRACK_COUNT|%s|%d" % (camera.get_display_name(), len(values)))
    return float(values[0]) if values else float(fallback)


def measure(n):
    seq = unreal.load_asset(SEQS[n])
    if seq is None:
        raise RuntimeError("ASSET_LOAD|I%d" % n)
    marks = markers(seq)
    frame, shadow_sources = shadow_frame(seq, marks)
    camera = active_camera(seq, frame)
    curtain = binding(seq, "Sleight Hangar Drape")
    cp, dp = pose(camera, frame), pose(curtain, frame)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    roots = [a for a in actors if str(a.get_actor_label()) == "S%d Hangar Root" % n]
    if len(roots) != 1:
        raise RuntimeError("HANGAR_ROOT_COUNT|I%d|%d" % (n, len(roots)))
    camera_world = unreal.MathLibrary.transform_location(
        roots[0].get_actor_transform(), unreal.Vector(*cp["loc"]))
    camera_world_loc = [float(camera_world.x), float(camera_world.y), float(camera_world.z)]
    curtain_width = CURTAIN_WIDTH_CM * abs(dp["scale"][0])
    curtain_height = CURTAIN_HEIGHT_CM * abs(dp["scale"][2])
    curtain_centre = [dp["loc"][0], dp["loc"][1], dp["loc"][2] + curtain_height * 0.5]
    dx = curtain_centre[0] - camera_world_loc[0]
    dy = curtain_centre[1] - camera_world_loc[1]
    dz = curtain_centre[2] - camera_world_loc[2]
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    sensor_w, sensor_h, focal_fallback = camera_lens(camera)
    focal = focal_at_frame(seq, camera, frame, focal_fallback)
    hfov = 2.0 * math.atan(sensor_w / (2.0 * focal))
    vfov = 2.0 * math.atan(sensor_h / (2.0 * focal))
    width_fraction = curtain_width / (2.0 * distance * math.tan(hfov * 0.5))
    height_fraction = curtain_height / (2.0 * distance * math.tan(vfov * 0.5))
    return {
        "interaction": n, "sequence": SEQS[n], "shadow_frame": frame,
        "shadow_sources": shadow_sources, "markers": marks,
        "camera_binding": str(camera.get_display_name()), "curtain_binding": str(curtain.get_display_name()),
        "curtain_template": curtain_template_inventory(curtain),
        "camera_pose_relative": cp, "camera_world_loc": camera_world_loc,
        "curtain_pose_world": dp, "curtain_centre_world": curtain_centre,
        "camera_to_curtain_centre_cm": distance,
        "curtain_asset_bounds_cm": [CURTAIN_WIDTH_CM, CURTAIN_HEIGHT_CM],
        "curtain_scaled_bounds_cm": [curtain_width, curtain_height],
        "sensor_mm": [sensor_w, sensor_h], "focal_mm": focal,
        "projected_width_fraction": width_fraction, "projected_height_fraction": height_fraction,
        "occupied_width_fraction": min(1.0, width_fraction),
        "occupied_height_fraction": min(1.0, height_fraction),
    }


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or str(world.get_path_name()).split(".")[0] != WORLD:
    raise RuntimeError("WORLD|%s" % world)
if editor.get_game_world() is not None:
    raise RuntimeError("PIE_RUNNING")
lib = unreal.EditorLoadingAndSavingUtils
before = {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
          "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}
if before != {"content": [], "maps": []}:
    raise RuntimeError("DIRTY_AT_START|%s" % before)
rows = [measure(n) for n in (1, 4, 5)]
target_width_fraction = sum(row["occupied_width_fraction"] for row in rows) / len(rows)
sensor_w = rows[0]["sensor_mm"][0]
focal = rows[0]["focal_mm"]
target_distance_for_480_cm = 480.0 / (2.0 * target_width_fraction * math.tan(math.atan(sensor_w / (2.0 * focal))))
payload = {"proof": "measured live read-only", "rows": rows,
           "target_occupied_width_fraction_mean": target_width_fraction,
           "job144_camera_distance_for_480cm": target_distance_for_480_cm}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference_frame_fraction.json")
with open(out, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=1, sort_keys=True)
after = {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
         "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}
if after != before:
    raise RuntimeError("DIRTY_CHANGED|before=%s|after=%s" % (before, after))
unreal.log("JOB144_REFERENCE_FRACTION_OK|rows=%d|mean_width=%.9f|distance_480=%.3f|dirty=0|report=%s" %
           (len(rows), target_width_fraction, target_distance_for_480_cm, out))
