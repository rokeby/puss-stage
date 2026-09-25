"""Read-only capture: P01 ceiling panel SM_CloudCeilingSmall_02_C before the OpacityMask fix.

Moves only the editor viewport camera (saved first for restore_viewport.py).
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)

MESH = "/Game/Scenes/Wings/Passage05_BirdToMountain/StaticMeshes/SM_CloudCeilingSmall_02_C"
wm.editor_ready()
before = wm.dirty()
if not os.path.exists(os.path.join(wm.OUT_DIR, "viewport_restore.json")):
    wm.save_viewport()
comp = wm.component_for_mesh(wm.passage_actor(1), MESH)
near = wm.passage_camera(1).get_world_location()
views = {}
for tag, dist, lift in (("2m", 200.0, -40.0), ("6m", 600.0, -80.0)):
    v = wm.panel_view(comp, near, dist, lateral_deg=0.0, lift_cm=lift)
    views[tag] = {k: str(val) for k, val in v.items()}
    views[tag]["loc"] = [v["location"].x, v["location"].y, v["location"].z]
    views[tag]["rot"] = [v["rotation"].roll, v["rotation"].pitch, v["rotation"].yaw]
wm.write_json("ceiling_mask_views.json", views)
v = views["6m"]
wm.shoot("WingMat_CeilingMask_Before_6m", unreal.Vector(*v["loc"]),
         unreal.Rotator(roll=v["rot"][0], pitch=v["rot"][1], yaw=v["rot"][2]))
wm.require(wm.dirty() == before, "dirty set changed")
unreal.log(f"PUSS_WING_CEILING_BEFORE_CAPTURE_REQUESTED|instances={comp.get_instance_count()}|index={v['index']}")
