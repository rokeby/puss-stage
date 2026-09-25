"""Read-only capture test: an unmistakable top-down view, to prove whether captures follow the camera."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
editor = wm.editor_ready()
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
les.editor_set_game_view(False)
wm.shoot("WingMat_Test_TopDown2", unreal.Vector(4400.0, 0.0, 6000.0), unreal.Rotator(roll=0.0, pitch=-89.0, yaw=0.0))
info = editor.get_level_viewport_camera_info()
unreal.log(f"PUSS_WING_SHOOT_TEST2|cam={info[-2]}|rot={info[-1]}")
