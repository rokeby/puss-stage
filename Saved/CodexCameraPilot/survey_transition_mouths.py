"""Read-only placement study: stalls cameras for the five transition curtains.

Gary, 29 Sep: the Interaction's shadow play runs ON the curtain at the next
Passage's mouth for 60 s or more; then the curtain falls into that Passage. So
each transition needs a stalls camera holding one framing for a minute.

The pattern is the Opening's stalls camera (Gary's 28 Sep view), expressed in
Passage 1's route-start frame and carried to Passages 2-6. This script:
  - reads every Passage's route start (world position and heading) and every
    structure's portal settings;
  - reads the Opening stalls camera and its lens;
  - computes a candidate seat per mouth (nothing is placed);
  - captures the Opening's own view plus each candidate: one TRUE still
    (EV100 0.5, as the hangar volume) and one GEOMETRY still (unlit base colour,
    framing only), because board collision is off and traces can't see boards.

LEVEL ACTIVITY (announce it): one ZZ_TransientCapture actor per still, destroyed
at once; spawn/destroy dirties the map with no net change. Refuses unless only
the map is dirty (this stream's earlier benches) and no ZZ_ actor exists.
Everything is inside main().

Success marker: PUSS_TRANSITION_MOUTHS_SURVEY
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OPENING_CAMERA_LABEL = "Opening — Stalls Camera"
PASSES = (("true", "SCS_FINAL_TONE_CURVE_HDR"), ("geometry", "SCS_BASE_COLOR"))


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def show_flags():
    flags = []
    for name, on in (("VolumetricFog", True), ("Editor", False), ("BillboardSprites", False)):
        setting = unreal.EngineShowFlagsSetting()
        setting.set_editor_property("show_flag_name", name)
        setting.set_editor_property("enabled", on)
        flags.append(setting)
    return flags


def capture(world, target, location, rotation, fov, source, hidden_actors, out_dir, name):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation)
    try:
        actor.set_actor_label("ZZ_TransientCapture")
        component = actor.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", getattr(unreal.SceneCaptureSource, source))
        component.set_editor_property("fov_angle", fov)
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        component.set_editor_property("show_flag_settings", show_flags())
        post = component.get_editor_property("post_process_settings")
        for key, value in (("auto_exposure_min_brightness", 0.5), ("auto_exposure_max_brightness", 0.5),
                           ("local_exposure_highlight_contrast_scale", 1.0),
                           ("local_exposure_shadow_contrast_scale", 1.0)):
            post.set_editor_property("override_" + key, True)
            post.set_editor_property(key, value)
        component.set_editor_property("post_process_settings", post)
        for hidden in hidden_actors:
            component.hide_actor_components(hidden, True)
        component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)
    path = os.path.join(out_dir, name + ".png")
    return os.path.getsize(path) if os.path.exists(path) else 0


def route_frame(passage):
    route = passage.get_editor_property("route")
    start = route.get_location_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD)
    direction = route.get_direction_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD)
    yaw = math.degrees(math.atan2(direction.y, direction.x))
    return start, yaw, route.get_spline_length()


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    others = [p for p in dirty() if p != EXPECTED_WORLD]
    if others:
        raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    strays = [a.get_actor_label() for a in actors if a.get_actor_label().startswith("ZZ_")]
    if strays:
        raise RuntimeError(f"Refusing: ZZ_ actors present {strays}")

    show = unreal.load_asset(SHOW_PATH)
    guid_to_label = {unreal.GuidLibrary.conv_guid_to_string(p.get_editor_property("passage_guid")):
                     str(p.get_editor_property("label")) for p in show.get_editor_property("passage_settings")}

    passages = {}
    for actor in actors:
        if actor.get_class().get_name() != "InfinityStagePassageActor":
            continue
        guid = unreal.GuidLibrary.conv_guid_to_string(actor.get_editor_property("passage_guid"))
        label = guid_to_label.get(guid)
        if not label:
            continue
        start, yaw, length = route_frame(actor)
        passages[label] = {"actor": actor.get_actor_label(), "route_start": vec(start), "yaw": round(yaw, 3),
                           "route_length_cm": round(length, 1), "_start": start}

    structures = {}
    for actor in actors:
        if actor.get_class().get_name() != "InfinityStageStructureActor":
            continue
        portal = actor.get_editor_property("portal")
        row = {"location": vec(actor.get_actor_location())}
        for key in ("enabled", "offset_from_first_station_cm", "opening_half_width_cm", "opening_height_cm",
                    "forestage_depth_cm", "extend_gridiron", "stage_front"):
            try:
                value = portal.get_editor_property(key)
                row[key] = value if isinstance(value, (bool, int, float)) else str(value)
            except Exception as error:
                row[key] = f"error: {error}"
        passage_actor = actor.get_editor_property("passage")
        row["passage_actor"] = passage_actor.get_actor_label() if passage_actor else None
        structures[actor.get_actor_label()] = row

    openings = [a for a in actors if isinstance(a, unreal.CineCameraActor) and a.get_actor_label() == OPENING_CAMERA_LABEL]
    if len(openings) != 1 or "Passage 1" not in passages:
        raise RuntimeError(f"Need exactly one '{OPENING_CAMERA_LABEL}' and Passage 1 (found {len(openings)})")
    opening = openings[0]
    lens = opening.get_cine_camera_component()
    sensor_width = lens.get_editor_property("filmback").get_editor_property("sensor_width")
    sensor_height = lens.get_editor_property("filmback").get_editor_property("sensor_height")
    focal = lens.get_editor_property("current_focal_length")
    fov = math.degrees(2.0 * math.atan(sensor_width / (2.0 * focal)))
    opening_location = opening.get_actor_location()
    opening_rotation = opening.get_actor_rotation()

    # The Opening seat in Passage 1's route-start frame (heading only; routes are level).
    p1 = passages["Passage 1"]
    yaw1 = math.radians(p1["yaw"])
    d = opening_location - p1["_start"]
    along = d.x * math.cos(yaw1) + d.y * math.sin(yaw1)
    across = -d.x * math.sin(yaw1) + d.y * math.cos(yaw1)
    rise = d.z
    pattern = {"along_cm": round(along, 1), "across_cm": round(across, 1), "rise_cm": round(rise, 1),
               "pitch": round(opening_rotation.pitch, 3), "yaw_offset": round(opening_rotation.yaw - p1["yaw"], 3),
               "focal_mm": focal, "filmback_mm": [sensor_width, sensor_height], "hfov_deg": round(fov, 2)}

    seats = [("Opening_P01_actual", opening_location, opening_rotation)]
    for n in (2, 3, 4, 5, 6):
        label = f"Passage {n}"
        if label not in passages:
            continue
        row = passages[label]
        yaw = math.radians(row["yaw"])
        start = row["_start"]
        location = unreal.Vector(start.x + along * math.cos(yaw) - across * math.sin(yaw),
                                 start.y + along * math.sin(yaw) + across * math.cos(yaw),
                                 start.z + rise)
        rotation = unreal.Rotator(roll=0.0, pitch=opening_rotation.pitch, yaw=row["yaw"] + pattern["yaw_offset"])
        row["candidate_seat"] = {"location": vec(location), "pitch": round(rotation.pitch, 3), "yaw": round(rotation.yaw, 3)}
        seats.append((f"Transition_P{n:02d}_candidate", location, rotation))

    hidden = [a for a in actors if "Camera + Shadow Figures" in a.get_actor_label()
              or a.get_class().get_name() == "InfinityStageShadowCatActor"]
    del actors, openings

    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "Transitions")
    os.makedirs(out_dir, exist_ok=True)
    target = unreal.RenderingLibrary.create_render_target2d(
        world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    stills = []
    for name, location, rotation in seats:
        for pass_name, source in PASSES:
            still = f"{name}_{pass_name}"
            size = capture(world, target, location, rotation, fov, source, hidden, out_dir, still)
            stills.append({"name": still, "bytes": size})

    for row in passages.values():
        row.pop("_start", None)
    report = {"pattern_from_opening": pattern, "passages": passages, "structures": structures,
              "stills": stills, "dirty_after": dirty()}
    with open(os.path.join(saved, "CodexCameraPilot", "survey_transition_mouths.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    unreal.log("PUSS_TRANSITION_MOUTHS_SURVEY|passages=%d|structures=%d|stills=%d|empty=%d|pattern=%s"
               % (len(passages), len(structures), len(stills), sum(1 for s in stills if s["bytes"] == 0), pattern))


main()
