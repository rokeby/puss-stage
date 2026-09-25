"""Put the editor viewport camera back where it was before the Wing materiality captures."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
wm.restore_viewport()
unreal.log("PUSS_WING_VIEWPORT_RESTORED")
