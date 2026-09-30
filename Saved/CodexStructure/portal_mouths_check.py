"""After portal_mouths_apply.py:
1. For each passage start (02-06): which stage-front, forestage or portal
   instance lies under the route line at 0, -7 and -14 m (the stalls seat), and
   its top z. This tests Look & camera's P04 void directly, by instance
   footprint (the boards carry no visibility collision, so traces pass through
   them).
2. A capture of P05's mouth from 14 m back at eye height, showing the ±950
   portal against its ±250 corridor, plus a frame at each other mouth. The
   capture actors are transient and destroyed in a finally.

Manual exposure EV 1.0, as the other P0x captures. Dirty logged before and
after. Mutates nothing. Lean: all work in main().
"""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    passages = {a.get_actor_label()[8:10]: a for a in actors if isinstance(a, unreal.InfinityStagePassageActor)}
    structures = {a.get_actor_label()[-2:]: a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)}
    report = {}
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    os.makedirs(OUT, exist_ok=True)
    for k in ("02", "03", "04", "05", "06"):
        route = passages[k].get_editor_property("route")
        start = route.get_location_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD)
        fwd = route.get_direction_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD)
        comps = [c for c in structures[k].get_editor_property("managed_components")
                 if c and "InfinityStage.Structure.Portal" in [str(t) for t in c.get_editor_property("component_tags")]]
        rows = []
        for back in (0.0, 700.0, 1400.0):
            p = start - fwd * back
            under = []
            for c in comps:
                o, e, _ = unreal.SystemLibrary.get_component_bounds(c)
                if abs(p.x - o.x) > e.x or abs(p.y - o.y) > e.y:
                    continue
                for i in range(c.get_instance_count()):
                    tf = c.get_instance_transform(i, True)
                    loc = unreal.MathLibrary.inverse_transform_location(tf, p)
                    if abs(loc.x) <= 50.0 and abs(loc.y) <= 50.0:
                        top = unreal.MathLibrary.transform_location(tf, unreal.Vector(loc.x, loc.y, 50.0)).z
                        under.append({"component": c.get_name(), "top_z": round(top, 1)})
                        break
            rows.append({"back_m": back / 100.0, "point": [round(v) for v in p.to_tuple()], "under": under[:3]})
        report[f"P{k}"] = {"route_start": [round(v, 1) for v in start.to_tuple()], "dir": [round(v, 3) for v in fwd.to_tuple()],
                           "portal_pieces": int(structures[k].get_editor_property("portal_piece_count")), "ground_under": rows}
        cam = start - fwd * 1400.0 + unreal.Vector(0.0, 0.0, 170.0)
        rot = unreal.MathLibrary.find_look_at_rotation(cam, start + fwd * 1500.0 + unreal.Vector(0.0, 0.0, 300.0))
        cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, cam, rot, True)
        try:
            cap.set_actor_label(f"ZZ_PortalMouth_{k}")
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", 70.0)
            pp = comp.post_process_settings
            pp.set_editor_property("override_auto_exposure_method", True)
            pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
            pp.set_editor_property("override_auto_exposure_bias", True)
            pp.set_editor_property("auto_exposure_bias", 1.0)
            comp.set_editor_property("post_process_settings", pp)
            comp.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"PortalMouth_P{k}.png")
        finally:
            sub.destroy_actor(cap)
    json.dump(report, open(os.path.join(HERE, "portal_mouths_check.json"), "w"), indent=1)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"PORTAL_MOUTHS_CHECK_OK|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}|mutated=0")


main()
