"""EDITOR BENCH, NO PIE, NO SAVES (30 Sep; conductor: mock and capture before any apply). What the upstage portal border
looks like: six transient ZZ_ black slabs, 5 cm x 19.8 m x 80 cm, x +45..+50 cm upstage of each portal plane, z 10.20-11.00
m (Soft goods' ray test on final13 f479: 0 rays through; the lowered header leaked 324). Stalls views WITHOUT and WITH, at
the Opening (its baked drape at the HOLD) and at the five Interaction stalls cameras (no drape there outside their
sequences, so those show the border against the open mouth).

One mode per MCP call (BENCH_MODE from the runners):
  open     writes the pre-state (dirty set, Sequencer, ZZ_ census) to portal_border_mock_prestate.json FIRST, then opens
           LS_Opening_Curtain_Baked (its spawnable drape appears, transient) and sets the HOLD frame
  capture  re-sets the HOLD frame (the cache was decoded in the earlier call: the GeometryCache rule), captures every view
           WITHOUT, spawns the six ZZ_ slabs (transient), captures every view WITH, and destroys the slabs by reference in a
           finally. Writes Captures/PortalBorderMock/
  close    closes the sequence; the dirty set must equal the pre-state's and no ZZ_ actor may remain (GameplayStatics census)
Captures use SceneCapture2D at each camera's own transform and horizontal FOV, FINAL_TONE_CURVE_HDR, no exposure override.
Everything inside main(). Markers PORTAL_BORDER_MOCK|<mode>|run=<id>."""
import datetime
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked"
HOLD_FRAME = 25                  # display frame inside the HOLD (0..49, frozen one tick before the release)
CUBE = "/Engine/BasicShapes/Cube.Cube"
BLACK = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"   # the pit liners' black
BORDER = {"x": (45.0, 50.0), "half_y": 990.0, "z": (1020.0, 1100.0)}
CAMERAS = ["Opening — Stalls Camera"] + [f"Interaction {i} — Stalls Camera" for i in range(1, 6)]
# Material candidates (BENCH_MATS): the first run's black steel read as a LIT TAN band in the notches (metal takes the
# Opening's warm light), so matte candidates are compared at the Opening. "velvet_black" is a TRANSIENT dynamic instance
# of the curtain's own velvet with its colour parameters set to black: no asset is created or changed.
MATERIALS = {"steel": BLACK,
             "basic_black": "/Game/EnvironmentPacks/MWMeadowWetlands/Materials/MASTER/Basic/MTL_MW_Basic_Black",
             "crow_black": "/Game/EnvironmentPacks/Birds/Crow/Materials/M_Black",
             "velvet_black": "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"}


def dirty():
    return sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def main():
    mode = globals().get("BENCH_MODE", "open")
    run = datetime.datetime.now().strftime("%H%M%S")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    lib = unreal.LevelSequenceEditorBlueprintLibrary
    if ed.get_game_world() is not None:
        unreal.log_error(f"PORTAL_BORDER_MOCK|refused|run={run}|PIE is running")
        return
    world = ed.get_editor_world()
    pre_path = os.path.join(HERE, "portal_border_mock_prestate.json")
    zz = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a.get_actor_label().startswith("ZZ_")]

    if mode == "open":
        cur = lib.get_current_level_sequence()
        pre = {"run": run, "dirty": dirty(), "sequencer_open": cur.get_path_name() if cur else None, "zz_actors": zz}
        with open(pre_path, "w", encoding="utf-8") as fh:
            json.dump(pre, fh, indent=1)
        unreal.log(f"PORTAL_BORDER_MOCK|prestate|run={run}|{pre_path}")
        if cur or zz:
            unreal.log_error(f"PORTAL_BORDER_MOCK|refused|run={run}|Sequencer open ({pre['sequencer_open']}) or ZZ_ actors {zz}")
            return
        lib.open_level_sequence(unreal.load_asset(SEQ))
        lib.set_current_time(HOLD_FRAME)
        unreal.log(f"PORTAL_BORDER_MOCK|open|run={run}|hold_frame={HOLD_FRAME}|dirty={dirty()}")
        return

    if mode == "close":
        pre = json.load(open(pre_path, encoding="utf-8"))
        cur = lib.get_current_level_sequence()
        if cur and cur.get_path_name().split(".")[0] == SEQ:
            lib.close_level_sequence()
        after = dirty()
        unreal.log(f"PORTAL_BORDER_MOCK|close|run={run}|dirty_after={after}|dirty_matches_prestate={after == pre['dirty']}|zz_left={zz}")
        return

    # capture
    cur = lib.get_current_level_sequence()
    if not cur or cur.get_path_name().split(".")[0] != SEQ:
        unreal.log_error(f"PORTAL_BORDER_MOCK|refused|run={run}|the Opening sequence is not open (run 'open' first)")
        return
    lib.set_current_time(HOLD_FRAME)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    mouths = json.load(open(os.path.join(HERE, "mouth_survey.json"), encoding="utf-8"))["mouths"]
    out = os.path.join(HERE, "Captures", "PortalBorderMock")
    os.makedirs(out, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1600, 900, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    drapes = len(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.GeometryCacheActor))
    shots = []

    def shoot(tag):
        for label in CAMERAS:
            cam = by.get(label)
            if cam is None:
                continue
            cc = cam.get_cine_camera_component()
            fov = math.degrees(2.0 * math.atan(cc.get_editor_property("filmback").sensor_width / (2.0 * cc.get_editor_property("current_focal_length"))))
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, cam.get_actor_location(), cam.get_actor_rotation(), True)
            try:
                comp = cap.capture_component2d
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                comp.set_editor_property("fov_angle", fov)
                comp.set_editor_property("capture_every_frame", False)
                for _ in range(2):
                    comp.capture_scene()
                name = ("Opening" if label.startswith("Opening") else "Interaction" + label.split()[1]) + f"_{tag}.png"
                unreal.RenderingLibrary.export_render_target(world, rt, out, name)
                shots.append(name)
            finally:
                sub.destroy_actor(cap)

    mats = list(globals().get("BENCH_MATS", ["steel"]))
    only_opening = bool(globals().get("OPENING_ONLY", False))
    if only_opening:
        CAMERAS[:] = CAMERAS[:1]
    shoot("without")
    mesh = unreal.load_asset(CUBE)
    notes = {}
    slabs = []
    for tag in mats:
        parent = unreal.load_asset(MATERIALS[tag])
        try:
            for key, m in mouths.items():
                sx, sy, sz = m["route_start"]
                yaw = m["route_start_rot"][2]
                frame = unreal.Transform(location=unreal.Vector(sx, sy, sz), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
                centre = frame.transform_location(unreal.Vector(sum(BORDER["x"]) / 2.0, 0.0, sum(BORDER["z"]) / 2.0))
                a = sub.spawn_actor_from_class(unreal.StaticMeshActor, centre, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), True)
                slabs.append(a)
                a.set_actor_label(f"ZZ_PortalBorderMock_P{key}")
                c = a.static_mesh_component
                c.set_static_mesh(mesh)
                if tag == "velvet_black":
                    mid = c.create_dynamic_material_instance(0, parent)
                    names = [str(n) for n in unreal.MaterialEditingLibrary.get_vector_parameter_names(parent)]
                    hit = [n for n in names if any(k in n.lower() for k in ("color", "colour", "tint", "albedo", "sheen", "base"))]
                    for n in hit:
                        mid.set_vector_parameter_value(n, unreal.LinearColor(0.01, 0.01, 0.01, 1.0))
                    notes["velvet_black"] = {"vector_params": names, "set_black": hit}
                else:
                    c.set_material(0, parent)
                a.set_actor_scale3d(unreal.Vector((BORDER["x"][1] - BORDER["x"][0]) / 100.0, 2.0 * BORDER["half_y"] / 100.0, (BORDER["z"][1] - BORDER["z"][0]) / 100.0))
            shoot(f"with_{tag}")
        finally:
            for a in slabs:
                sub.destroy_actor(a)
            slabs = []
    unreal.log(f"PORTAL_BORDER_MOCK|materials|run={run}|{json.dumps(notes)}")
    left = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a.get_actor_label().startswith("ZZ_")]
    unreal.log(f"PORTAL_BORDER_MOCK|capture|run={run}|drapes_spawned={drapes}|mats={mats}|shots={len(shots)}|zz_left={left}|dirty={dirty()}|out={out}")


main()
