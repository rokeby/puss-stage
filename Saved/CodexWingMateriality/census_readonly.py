"""Read-only census: dirty map packages and dirty content packages, reported separately."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
maps = sorted({wm.pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()})
content = sorted({wm.pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()})
wm.write_json("census.json", {"maps": maps, "content": content})
unreal.log(f"PUSS_WING_CENSUS|maps={len(maps)}|content={len(content)}|{maps}|{content}")
