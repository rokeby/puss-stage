"""Read-only: BugItGo viewpoints for judging the P01 trial at 1 m and 2 m (moves nothing)."""
import importlib.util, math, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
before = wm.dirty()
actor = wm.passage_actor(1)
near = wm.passage_camera(1).get_world_location()
views = {}
for tag, mesh, z_local in (("rococo_R_new", "/Game/Scenes/Wings/StaticMeshes/SM_R__1_roccoco", 170.0),
                           ("rococo_L_legacy", "/Game/Scenes/Wings/StaticMeshes/SM_L_1_roccoco", 170.0)):
    comp = wm.component_for_mesh(actor, mesh)
    box = comp.get_editor_property("static_mesh").get_bounding_box()
    local = unreal.Vector(0.0, (box.min.y + box.max.y) * 0.5, z_local)
    best = None
    for i in range(comp.get_instance_count()):
        xf = comp.get_instance_transform(i, True)
        p = unreal.MathLibrary.transform_location(xf, local)
        d = (p - near).length()
        if best is None or d < best[0]:
            best = (d, i, xf, p)
    _, idx, xf, target = best
    n = xf.rotation.rotate_vector(unreal.Vector(1, 0, 0)); n.normalize()
    # Wings are flats facing down the route; the travelling camera approaches from -X
    # (route start), so look at the face on that side for both members of the pair.
    if n.x > 0:
        n = n * -1.0
    # Swing the 30 degrees toward the corridor centre (y = 0) for both wings: a mirrored A/B.
    side = unreal.Vector(0.0, -1.0 if target.y > 0 else 1.0, 0.0)
    for dist in (100.0, 200.0):
        a = math.radians(30.0)
        cam = target + n * (math.cos(a) * dist) + side * (math.sin(a) * dist)
        rot = unreal.MathLibrary.find_look_at_rotation(cam, target)
        views[f"{tag}_{int(dist / 100)}m"] = (f"BugItGo {cam.x:.0f} {cam.y:.0f} {cam.z:.0f} "
                                               f"{rot.pitch:.1f} {rot.yaw:.1f} 0")
    views[f"{tag}_instance"] = idx
wm.require(wm.dirty() == before, "dirty changed")
wm.write_json("trial_viewpoints.json", views)
unreal.log("PUSS_WING_TRIAL_VIEWPOINTS_SUCCESS")
