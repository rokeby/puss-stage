"""BENCH (level activity, restored): cost the conductor's "release the box early, let the backcloth
mask the rise" option for the P04 -> Scene 4 transition, in pictures. Nothing is applied.

The option: the rise lasts RISE_S (Gary's 15 s) and is timed so the box is at CROSS_DEG when the
camera crosses the cloth line (x 10450, 0.874 s before Scene 4); the cloth still releases 2.7 s
before that crossing. For each camera moment (scene time t <= 0 along P04 at 2.5 m/s, plus a few
seconds into Scene 4 from the Entry camera) the root is posed at the option's pitch, a PROXY
backcloth stands at the line while it would still be hanging (a dark 10 m x 12.2 m slab, the
bake's size; conservative: no pleat gaps), and the frame is captured at the show's exposure (no
override; the hangar's pinned volume applies from x 10568.5 on).

Mutation: the root's relative rotation only, recorded as plain floats first and restored in a
finally, then checked; the level is never saved here (a verified save clears the no-net-change
flag). Transient capture and proxy actors. Writes Captures/EarlyRelease/. Lean: main()."""
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "EarlyRelease")
CAM_STOP_X, Y, Z, SPEED = 10668.47, 240000.0, 180.0, 250.0
CLOTH_X, CLOTH_W, CLOTH_H, LEAD_S, FALL_S = 10450.0, 1000.0, 1220.0, 2.7, 1.7
RISE_S, CROSS_DEG = globals().get("EARLY_RISE_S", 15.0), globals().get("EARLY_CROSS_DEG", -20.0)
MOMENTS = (-12.0, -10.0, -8.0, -6.0, -4.0, -3.0, -2.0, -0.874, 0.0, 2.0, 4.0)


def smooth(u):
    u = min(1.0, max(0.0, u))
    return 3 * u * u - 2 * u ** 3


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "dirty map"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    root = next(a for a in sub.get_all_level_actors() if a.get_actor_label() == "S4 Hangar Root")
    r0 = root.root_component.get_editor_property("relative_rotation")
    rest = (float(r0.roll), float(r0.pitch), float(r0.yaw))
    assert abs(rest[1] + 90.0) < 0.05, f"the root is not at rest: {rest}"
    # Solve the start so the smoothstep is at CROSS_DEG at the crossing.
    cross_t = -(CAM_STOP_X - CLOTH_X) / SPEED
    target = (CROSS_DEG + 90.0) / 90.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if smooth(mid) < target else (lo, mid)
    t0 = cross_t - lo * RISE_S
    release_t = cross_t - LEAD_S
    pitch_at = lambda t: -90.0 + 90.0 * smooth((t - t0) / RISE_S)
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    temps, rows = [], []
    try:
        cloth = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(CLOTH_X, Y, CLOTH_H / 2.0), unreal.Rotator(0.0, 0.0, 0.0), True)
        temps.append(cloth)
        smc = cloth.get_editor_property("static_mesh_component")
        smc.set_mobility(unreal.ComponentMobility.MOVABLE)
        smc.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube.Cube"))
        smc.set_material(0, unreal.load_asset("/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"))
        cloth.set_actor_scale3d(unreal.Vector(0.05, CLOTH_W / 100.0, CLOTH_H / 100.0))
        for t in MOMENTS:
            hanging = t < release_t + FALL_S
            smc.set_visibility(hanging)
            p = pitch_at(t)
            root.set_actor_relative_rotation(unreal.Rotator(roll=rest[0], pitch=p, yaw=rest[2]), False, True)
            x = CAM_STOP_X + SPEED * min(t, 0.0)
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(x, Y, Z), unreal.Rotator(0.0, 0.0, 0.0), True)
            temps.append(cap)
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", 37.5)
            for _ in range(2):
                comp.capture_scene()
            name = f"Early_{'m' if t < 0 else 'p'}{abs(t):05.2f}.png"
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)
            rows.append({"t": t, "camera_x": round(x, 1), "to_cloth_m": round((CLOTH_X - x) / 100.0, 2), "pitch": round(p, 2),
                         "cloth": "hanging" if hanging else "down", "file": name})
    finally:
        root.set_actor_relative_rotation(unreal.Rotator(roll=rest[0], pitch=rest[1], yaw=rest[2]), False, True)
        for a in temps:
            sub.destroy_actor(a)
    back = root.root_component.get_editor_property("relative_rotation")
    restored = abs(back.pitch - rest[1]) < 1e-4 and abs(back.yaw - rest[2]) < 1e-4 and abs(back.roll - rest[0]) < 1e-4
    json.dump({"rise_s": RISE_S, "cross_deg": CROSS_DEG, "start_t": t0, "land_t": t0 + RISE_S, "release_t": release_t, "cross_t": cross_t,
               "rows": rows}, open(os.path.join(HERE, "early_release.json"), "w"), indent=1)
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"EARLY_RELEASE_BENCH|start={t0:.2f}s|land={t0 + RISE_S:.2f}s|release={release_t:.2f}s|cross={cross_t:.3f}s"
               f"|restored={restored}|dirty_map_after={m1}")


main()
