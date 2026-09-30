"""Read-only: after the hide, what does each landscape's COMPONENTS still do? Collision-enabled state per primitive
component class, and whether the landscape still renders (a capture at P03's approach with the landscape hidden
from the capture vs not: identical frames = it no longer renders). Mutates nothing (transient capture, destroyed)."""
import unreal


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    rows = []
    for label in ("Passage 1 - ForestedLandscape", "Passage 3 - Wet Ground"):
        L = by[label]
        counts = {}
        for c in L.get_components_by_class(unreal.PrimitiveComponent):
            key = f"{c.get_class().get_name()}:{c.get_collision_enabled()}:vis={c.is_visible()}"
            counts[key] = counts.get(key, 0) + 1
        rows.append(f"{label}: actor hidden={L.get_editor_property('hidden')} actor_collision={L.get_actor_enable_collision()} components={counts}")
    rt = unreal.RenderingLibrary.create_render_target2d(world, 640, 360, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    wet = by["Passage 3 - Wet Ground"]
    means = []
    for hide in (False, True):
        cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(-1500.0, 160000.0, 180.0), unreal.Rotator(roll=0.0, pitch=-10.0, yaw=0.0), True)
        try:
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            if hide:
                comp.hide_actor_components(wet, False)
            comp.capture_scene()
            comp.capture_scene()
            unreal.RenderingLibrary.export_render_target(world, rt, unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + "CodexStructure/Captures/LandscapeHideProbe", f"p03_approach_{'hidden_in_capture' if hide else 'as_is'}.png")
        finally:
            sub.destroy_actor(cap)
    unreal.log("LS_HIDE_PROBE|" + " || ".join(rows))


main()
