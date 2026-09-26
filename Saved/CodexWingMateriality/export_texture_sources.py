"""Read-only: export texture sources as PNG to DerivedAssets/WingMateriality/SourceExports.

Input: export_request.json {"textures": ["/Game/...", ...]}. Exports exactly the
pixels Unreal imported, which is what an upscale or relief pass must start from.
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
before = wm.dirty()
out_dir = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                       "DerivedAssets", "WingMateriality", "SourceExports", wm.read_json("export_request.json").get("subdir", ""))
os.makedirs(out_dir, exist_ok=True)
done = {}
for path in wm.read_json("export_request.json")["textures"]:
    tex = unreal.EditorAssetLibrary.load_asset(path)
    wm.require(isinstance(tex, unreal.Texture2D), f"not a texture: {path}")
    fn = os.path.join(out_dir, path.rsplit("/", 1)[-1] + ".png")
    task = unreal.AssetExportTask()
    task.set_editor_property("object", tex)
    task.set_editor_property("filename", fn)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("prompt", False)
    ok = unreal.Exporter.run_asset_export_task(task)
    done[path] = {"file": fn, "ok": bool(ok) and os.path.exists(fn)}
wm.require(wm.dirty() == before, f"dirty changed {wm.dirty()}")
wm.write_json("export_result.json", done)
unreal.log(f"PUSS_WING_EXPORT_SUCCESS|ok={sum(v['ok'] for v in done.values())}/{len(done)}")
