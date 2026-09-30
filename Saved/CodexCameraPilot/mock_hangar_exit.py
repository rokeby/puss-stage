"""Mock-ups for Gary's exit question (nothing built, nothing saved), STEPWISE.

1. HOUSE: from a stalls seat inside Hangar 4 at the Scene's end (the Opening's
   seat pattern: 14 m back from the portal line, eye 1.5 m, +14 deg, 15 mm),
   with the far wall HIDDEN FOR THE CAPTURE ONLY (hide_actor_components; the
   level is untouched), a PROXY portal frame (transient cubes) and the real
   drape bake hanging where the far wall would open.
2. FALLBACK A: the same seat, far wall visible, the drape "flown in" in front of
   it, the frame just before a match cut.
3. FALLBACK B: the real Interaction 4 stalls camera at Passage 5's mouth, with
   Interaction 4's own drape (LS_Interaction_04 scrubbed into its hold), the
   frame just after the match cut.

The drape is a GeometryCache, so per the capture rule: pose, tick, RE-POSE THE
SAME TIME, then capture. Every pose change is captured in a later call.
Transient actors are labelled ZZ_ and destroyed; captures use no exposure
override (the show's own volumes). Run the same request until
PUSS_HANGAR_EXIT_MOCK_DONE. Writes Captures/HangarExit/.
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
DRAPE_CACHE = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
CUBE = "/Engine/BasicShapes/Cube.Cube"
PORTAL_MATERIAL = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"
STOP_X, Y = 10668.5, 240000.0
FAR_WALL_X = STOP_X + 6000.0          # inner face of Hangar 4's far wall (Rig's v2 numbers)
SEAT = unreal.Vector(FAR_WALL_X - 1400.0, Y, 150.0)
SEAT_ROT = unreal.Rotator(roll=0.0, pitch=14.0, yaw=0.0)
S4_TIME = 29.0                         # Scene 4 end state: roof closed, lattice down, lights on
I4_TIME = 4.0                          # Interaction 4: drape hanging
HALF_OPEN, OPEN_H, POST, HEADER = 950.0, 1050.0, 40.0, 45.0
STATE_VERSION = 1


def cue_sequence(show, prefix):
    for cue in show.get_editor_property("cues"):
        if str(cue.get_editor_property("label")).startswith(prefix):
            return cue.get_editor_property("scene").get_editor_property("sequence")
    raise RuntimeError(f"No cue starting '{prefix}'")


def frame_at(sequence, seconds):
    rate = sequence.get_display_rate()
    return sequence.get_playback_start() + int(round(seconds * rate.numerator / float(rate.denominator)))


def zz(subsystem, cls, location, label):
    actor = subsystem.spawn_actor_from_class(cls, location, unreal.Rotator(0.0, 0.0, 0.0), True)
    actor.set_actor_label(label)
    return actor


def cube(subsystem, center, size_cm, label):
    actor = zz(subsystem, unreal.StaticMeshActor, center, label)
    mesh = actor.get_editor_property("static_mesh_component")
    mesh.set_mobility(unreal.ComponentMobility.MOVABLE)
    mesh.set_static_mesh(unreal.load_asset(CUBE))
    mesh.set_material(0, unreal.load_asset(PORTAL_MATERIAL))
    actor.set_actor_scale3d(unreal.Vector(size_cm[0] / 100.0, size_cm[1] / 100.0, size_cm[2] / 100.0))
    return actor


def capture(world, location, rotation, fov, hidden, out_dir, name):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    target = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    actor = subsystem.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation, True)
    try:
        actor.set_actor_label("ZZ_TransientCapture")
        component = actor.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        component.set_editor_property("fov_angle", fov)
        for h in hidden:
            component.hide_actor_components(h, True)
        for _ in range(2):
            component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
    finally:
        subsystem.destroy_actor(actor)


def pose_drape(actor):
    gcc = actor.get_component_by_class(unreal.GeometryCacheComponent)
    gcc.set_editor_property("running", False)
    gcc.tick_at_this_time(0.0, False, False, False)


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world (or PIE is running)")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sequencer = unreal.LevelSequenceEditorBlueprintLibrary
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "HangarExit")
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(out_dir, "state.json")
    state = json.load(open(state_path, encoding="utf-8")) if os.path.exists(state_path) else None
    show = unreal.load_asset(SHOW_PATH)
    s4 = cue_sequence(show, "Scene 4")
    i4 = cue_sequence(show, "Interaction 4")

    def mine():
        # Spawned TRANSIENT, so get_all_level_actors() does not list them (found the hard
        # way on the first run); GameplayStatics iterates every actor in the world.
        return [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_actor_label().startswith("ZZ_HangarExit")]

    if state is None or state.get("version") != STATE_VERSION:
        if [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
            raise RuntimeError("Refusing: content dirty")
        if [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_actor_label().startswith("ZZ_")]:
            raise RuntimeError("Refusing: ZZ_ actors present")
        sequencer.open_level_sequence(s4)
        sequencer.set_current_time(frame_at(s4, S4_TIME))
        drape = zz(subsystem, unreal.GeometryCacheActor, unreal.Vector(FAR_WALL_X - 50.0, Y, 0.0), "ZZ_HangarExit_Drape")
        drape.get_component_by_class(unreal.GeometryCacheComponent).set_editor_property(
            "geometry_cache", unreal.load_asset(DRAPE_CACHE))
        pose_drape(drape)
        x = FAR_WALL_X
        cube(subsystem, unreal.Vector(x, Y - HALF_OPEN - POST / 2, OPEN_H / 2), (HEADER, POST, OPEN_H), "ZZ_HangarExit_PostL")
        cube(subsystem, unreal.Vector(x, Y + HALF_OPEN + POST / 2, OPEN_H / 2), (HEADER, POST, OPEN_H), "ZZ_HangarExit_PostR")
        cube(subsystem, unreal.Vector(x, Y, OPEN_H + HEADER / 2), (HEADER, 2 * (HALF_OPEN + POST), HEADER), "ZZ_HangarExit_Header")
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"version": STATE_VERSION, "step": 1}, handle)
        unreal.log("PUSS_HANGAR_EXIT_STEP|0|scene4 at %.1f s, proxies spawned, drape posed" % S4_TIME)
        return

    step = state["step"]
    actors = subsystem.get_all_level_actors()
    hidden_base = [a for a in actors if "Camera + Shadow Figures" in a.get_actor_label()
                   or a.get_class().get_name() == "InfinityStageShadowCatActor"]
    fov_seat = math.degrees(2.0 * math.atan(23.76 / (2.0 * 15.0)))

    if step == 1:
        drapes = [a for a in mine() if a.get_actor_label() == "ZZ_HangarExit_Drape"]
        pose_drape(drapes[0])                                  # re-pose the same time, then capture
        far_walls = [a for a in actors if a.get_actor_label().startswith("S4") and "Far Wall" in a.get_actor_label()]
        capture(world, SEAT, SEAT_ROT, fov_seat, hidden_base + far_walls, out_dir, "House_seat_in_hangar4")
        portal = [a for a in mine() if "Post" in a.get_actor_label() or "Header" in a.get_actor_label()]
        capture(world, SEAT, SEAT_ROT, fov_seat, hidden_base + portal, out_dir, "Fallback_A_drape_flown_in")
        for a in mine():
            subsystem.destroy_actor(a)
        sequencer.close_level_sequence()
        sequencer.open_level_sequence(i4)
        sequencer.set_current_time(frame_at(i4, I4_TIME))
        state.update({"step": 2, "far_walls_hidden": [a.get_actor_label() for a in far_walls]})
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        unreal.log("PUSS_HANGAR_EXIT_STEP|1|house and fallback A captured; far walls hidden=%s" % state["far_walls_hidden"])
        return

    # step 2: re-pose Interaction 4 at the same time (its drape is a GeometryCache), then capture.
    sequencer.set_current_time(frame_at(i4, I4_TIME))
    stalls = [a for a in actors if a.get_actor_label().startswith("Interaction 4") and "Stalls Camera" in a.get_actor_label()]
    component = stalls[0].get_cine_camera_component()
    width = component.get_editor_property("filmback").get_editor_property("sensor_width")
    fov = math.degrees(2.0 * math.atan(width / (2.0 * component.get_editor_property("current_focal_length"))))
    capture(world, component.get_world_location(), component.get_world_rotation(), fov, hidden_base, out_dir,
            "Fallback_B_P05_stalls_after_cut")
    sequencer.close_level_sequence()
    os.remove(state_path)
    left = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
            if a.get_actor_label().startswith("ZZ_")]
    unreal.log("PUSS_HANGAR_EXIT_MOCK_DONE|zz_left=%s" % left)


main()
