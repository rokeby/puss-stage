"""Read-only: what of Scene 4 is visible WHILE APPROACHING down Passage 4, at fold
frame 0 (the level's rest pose, everything packed)? Gary: "we don't see the Scene
at the end of the Tunnel, instead it folds into view once we arrive".

The camera sits on P04's route at 20/40/60/80/90/100% of its length, at the
show camera's height (180 cm) and lens (35 mm Super 35, hfov 37.5 deg), looking
along the route. Each view is captured twice: normally, and with every Scene 4
hangar actor hidden (tag RigAtmos.Scene4Hangar: flats, lattice, bulbs, ghost
light, practicals, uplights). The difference, computed afterwards, is exactly
what the hangar contributes to the frame, geometry and light alike. Manual EV
1.0, as the other P0x captures. The capture actors are transient, destroyed in a
finally. Mutates nothing. Lean: all work in main().
"""
import json
import math
import os

import unreal

TAG = "RigAtmos.Scene4Hangar"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "Captures", "Approach")
FRACTIONS = (0.2, 0.4, 0.6, 0.8, 0.9, 1.0)


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open (the level must rest at frame 0)"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    hangar = [a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]]
    p04 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 04"))
    route = p04.get_editor_property("route")
    length = route.get_spline_length()
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    rows = []
    for f in FRACTIONS:
        d = length * f
        loc = route.get_location_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD) + unreal.Vector(0.0, 0.0, 180.0)
        fwd = route.get_direction_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)
        rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=math.degrees(math.atan2(fwd.y, fwd.x)))
        for variant, hidden in (("with", []), ("without", hangar)):
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
            try:
                cap.set_actor_label(f"ZZ_Approach_{int(f * 100)}_{variant}")
                comp = cap.capture_component2d
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                comp.set_editor_property("fov_angle", 37.5)
                for h in hidden:     # hidden_actors isn't settable in 5.8; the function is
                    comp.hide_actor_components(h, True)
                pp = comp.post_process_settings
                pp.set_editor_property("override_auto_exposure_method", True)
                pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
                pp.set_editor_property("override_auto_exposure_bias", True)
                pp.set_editor_property("auto_exposure_bias", 1.0)
                comp.set_editor_property("post_process_settings", pp)
                comp.capture_scene()
                unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"Approach_{int(f * 100):03d}_{variant}.png")
            finally:
                sub.destroy_actor(cap)
        rows.append({"fraction": f, "loc": [round(v) for v in loc.to_tuple()], "distance_to_mouth_m": round((length - d) / 100.0, 1)})
    json.dump({"route_length_cm": length, "hangar_actors": len(hangar), "views": rows},
              open(os.path.join(OUT, "approach.json"), "w"), indent=1)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"S4_APPROACH_OK|views={len(rows)}|hangar_actors={len(hangar)}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
