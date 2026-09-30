"""BENCH (30 Sep): did this morning's plane trim make the INERT (unnested) S1/S5/S6 hangars visible from their
stops at REST? Unnested, a hangar hangs at -90 in its pit with its lattice bulb meshes emissive; before the
trim a floor plane covered the pit. For each scene, at the level's rest state (nothing posed), capture the
Scene's Entry Handoff Camera view (its own lens, level) and a 15 deg look-down: (a) as the level is now,
(b) with a TRANSIENT proxy re-covering only the trimmed strip (hinge -> the plane's old far end, the
plane's own mesh and material, from plane_trim_record.json). The proxy is transient and destroyed in a
finally; nothing is saved; dirty must stay 0+0. Writes Captures/TrimRestAB/. Lean: main()."""
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "TrimRestAB")


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() and not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    rec = {r["scene"]: r for r in json.load(open(os.path.join(HERE, "plane_trim_record.json"), encoding="utf-8"))["planes"]}
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    rows = []
    for n in (1, 5, 6):
        r = rec[n]
        plane = by[r["label"]]
        cam = next(a for a in actors if a.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in a.get_actor_label())
        cc = cam.get_cine_camera_component()
        fov = math.degrees(2.0 * math.atan(cc.get_editor_property("filmback").sensor_width / (2.0 * cc.get_editor_property("current_focal_length"))))
        root_pitch = by[f"S{n} Hangar Root"].root_component.get_editor_property("relative_rotation").pitch
        views = (("level", 0.0, fov), ("down15", -15.0, fov))
        proxy = None
        try:
            for state in ("now", "proxy"):
                if state == "proxy":
                    # Only the removed strip: from the hinge to the old far end, same y/z/thickness.
                    x0, x1 = r["hinge_x"], r["far_x"]
                    proxy = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector((x0 + x1) / 2.0, r["loc"][1], r["loc"][2]),
                                                       unreal.Rotator(0.0, 0.0, 0.0), True)
                    smc = proxy.get_editor_property("static_mesh_component")
                    src = plane.get_component_by_class(unreal.StaticMeshComponent)
                    smc.set_static_mesh(src.get_editor_property("static_mesh"))
                    smc.set_material(0, src.get_material(0))
                    proxy.set_actor_scale3d(unreal.Vector((x1 - x0) / 100.0, r["scale"][1], r["scale"][2]))
                for name, pitch, f in views:
                    cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, cam.get_actor_location(),
                                                     unreal.Rotator(roll=0.0, pitch=pitch, yaw=cam.get_actor_rotation().yaw), True)
                    try:
                        comp = cap.capture_component2d
                        comp.set_editor_property("texture_target", rt)
                        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                        comp.set_editor_property("fov_angle", f)
                        for _ in range(2):
                            comp.capture_scene()
                        unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"S{n}_{name}_{state}.png")
                    finally:
                        sub.destroy_actor(cap)
        finally:
            if proxy:
                sub.destroy_actor(proxy)
        rows.append(f"S{n}:root_pitch={root_pitch:.1f}:fov={fov:.1f}")
    d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"TRIM_REST_AB_OK|{' '.join(rows)}|dirty_after={d[0]}+{d[1]}")


main()
