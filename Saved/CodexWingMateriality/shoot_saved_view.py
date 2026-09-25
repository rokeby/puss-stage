"""Read-only capture at a view stored in shoot_request.json: {"views_file","view","name"}."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
req = wm.read_json("shoot_request.json")
v = wm.read_json(req["views_file"])[req["view"]]
wm.shoot(req["name"], unreal.Vector(*v["loc"]), unreal.Rotator(roll=v["rot"][0], pitch=v["rot"][1], yaw=v["rot"][2]))
unreal.log(f"PUSS_WING_CAPTURE_REQUESTED|{req['name']}")
