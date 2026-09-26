"""Offscreen capture that does not depend on the level viewport rendering.

HighResShot returns a stale or black frame whenever the editor's level viewport
is not the visible, focused window. A SceneCapture2D renders through its own
pipeline, so it works while the editor is behind another window or minimized.
Transient actor + transient render target: nothing is added to the level and no
package is dirtied.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("CAPTURE_WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

before_c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
before_m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())

# Derive shot positions from Passage 1's actual route rather than guessing.
passages = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p1 = None
for p in passages:
    if "1" in p.get_actor_label() and p1 is None:
        p1 = p
if p1 is None and passages:
    p1 = passages[0]
unreal.log("CAPTURE_PASSAGE|%s|of %d" % (p1.get_actor_label() if p1 else "NONE", len(passages)))

route = None
for comp in p1.get_components_by_class(unreal.SplineComponent):
    route = comp
    break

shots = []
if route:
    length = route.get_spline_length()
    unreal.log("CAPTURE_ROUTE|length=%.0f" % length)
    PLAN = (
        (0.30, "P01_eye",        0.0,   -3.0, 80.0),
        (0.30, "P01_eye_bright", 0.0,    1.0, 80.0),
        (0.30, "P01_up",        38.0,    1.0, 90.0),
        (0.30, "P01_down",     -35.0,    1.0, 90.0),
        (0.55, "P01_far_bright", 0.0,    1.0, 80.0),
    )
    for frac, name, pitch, ev, fov in PLAN:
        d = length * frac
        loc = route.get_location_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)
        rot = route.get_rotation_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)
        shots.append((name, unreal.Vector(loc.x, loc.y, loc.z + 170.0),
                      unreal.Rotator(roll=0.0, pitch=pitch, yaw=rot.yaw), fov, ev))
else:
    unreal.log_error("CAPTURE_NO_ROUTE")
    raise SystemExit

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

for name, loc, rot, fov, ev in shots:
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot)
    try:
        cap.set_actor_label("ZZ_TransientCapture")
        comp = cap.capture_component2d
        comp.set_editor_property("texture_target", rt)
        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        comp.set_editor_property("fov_angle", fov)
        comp.set_editor_property("capture_every_frame", False)
        comp.set_editor_property("capture_on_movement", False)
        pp = comp.get_editor_property("post_process_settings")
        pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        pp.set_editor_property("override_auto_exposure_method", True)
        pp.set_editor_property("auto_exposure_bias", ev)
        pp.set_editor_property("override_auto_exposure_bias", True)
        comp.set_editor_property("post_process_settings", pp)
        comp.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
        path = OUT + name + ".png"
        size = os.path.getsize(path) if os.path.exists(path) else 0
        unreal.log("CAPTURE|%s|loc=%.0f,%.0f,%.0f|bytes=%d" % (name, loc.x, loc.y, loc.z, size))
    finally:
        unreal.EditorLevelLibrary.destroy_actor(cap)

# Spawning and destroying a transient actor marks the map dirty even though the
# net change is nil, and UE 5.8's Python exposes NO way to clear that flag --
# checked on Package, EditorLoadingAndSavingUtils, SystemLibrary and
# EditorAssetLibrary. Do not add a set_dirty_flag call here: Package has no such
# method, and an earlier version of this script threw on it every run, which
# silently suppressed the two log lines below.
#
# So a capture run leaves dirty_maps=1 with no content change. Report it to the
# conductor; do not save the level to tidy it away.

after_c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
after_m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log("CAPTURE_DIRTY|before=%d+%d|after=%d+%d" % (before_c, before_m, after_c, after_m))
unreal.log("CAPTURE_DONE|%d|%s" % (len(shots), OUT))
