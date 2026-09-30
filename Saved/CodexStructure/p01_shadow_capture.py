"""Read-only before/after capture for P01's shadow pass, at the show's own exposure (no override).
Four views along P01's route (straight, +X from the origin), eye height unless stated:
  entry  - 6 m in, looking 20 m down the floor;
  rhythm - raised 4.5 m, looking down over several stations;
  mid    - halfway down the passage, looking ahead;
  w041   - 12 m before Wing 041, looking at the blinking spot's pool (Gary's shadow).
Files suffixed P01_SHADOW_SUFFIX ("_before"/"_after"). Transient captures, destroyed in a
finally; dirty must not change. Writes Captures/P01Shadow/. Lean: all work in main()."""
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "Captures", "P01Shadow")
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SUFFIX = globals().get("P01_SHADOW_SUFFIX", "")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    p01 = next(a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
    route = p01.get_editor_property("route")
    length = route.get_spline_length()
    show = unreal.load_asset(SHOW)
    w41 = next(c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == "P01 Wing 041")
    g41 = w41.get_editor_property("cue_guid").to_string()
    x41 = next(r.get_editor_property("base_world_transform").translation.x for r in p01.get_editor_property("materialized_panels")
               if r.get_editor_property("cue_guid").to_string() == g41)

    def at(d, z):
        return route.get_location_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD) + unreal.Vector(0.0, 0.0, z)

    views = (("entry", at(600.0, 160.0), at(2600.0, 0.0), 70.0),
             ("rhythm", at(300.0, 450.0), at(3600.0, 0.0), 55.0),
             ("mid", at(length / 2.0, 160.0), at(length / 2.0 + 2500.0, 60.0), 60.0),
             ("w041", unreal.Vector(x41 - 1200.0, 0.0, 160.0), unreal.Vector(x41 + 600.0, 0.0, 40.0), 60.0))
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1600, 900, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    for name, loc, look, fov in views:
        cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, unreal.MathLibrary.find_look_at_rotation(loc, look), True)
        try:
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", fov)
            for _ in range(3):
                comp.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"P01_{name}{SUFFIX}.png")
        finally:
            sub.destroy_actor(cap)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"P01_SHADOW_CAPTURE_OK|suffix={SUFFIX}|wing041_x={x41:.0f}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
