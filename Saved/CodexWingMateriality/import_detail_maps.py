"""Import the generated detail maps into /Game/Scenes/Wings/PaintedSurface/Textures.

New packages only; touches no existing asset. Saves exactly the imported textures.
"""
import importlib.util, json, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)

DEST = "/Game/Scenes/Wings/PaintedSurface/Textures"
SRC = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                   "DerivedAssets", "WingMateriality", "DetailMaps")
wm.editor_ready()
wm.require(wm.dirty() == [], f"Refusing to write with dirty packages present: {wm.dirty()}")
manifest = json.load(open(os.path.join(SRC, "manifest.json"), encoding="utf-8"))
tasks = []
for name in manifest["import"]:
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", os.path.join(SRC, name + ".png"))
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("destination_name", name)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", False)
    tasks.append(t)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
saved = []
for name, cfg in manifest["import"].items():
    path = f"{DEST}/{name}"
    tex = unreal.EditorAssetLibrary.load_asset(path)
    wm.require(isinstance(tex, unreal.Texture2D), f"{path} did not import")
    tex.set_editor_property("srgb", bool(cfg["srgb"]))
    tex.set_editor_property("compression_settings", getattr(unreal.TextureCompressionSettings, cfg["compression"]))
    if cfg["compression"] == "TC_NORMALMAP":
        tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
    tex.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
    tex.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
    wm.require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), f"save failed {path}")
    saved.append(path)
after = wm.dirty()
wm.require(after == [], f"Dirty after import: {after}")
rows = {}
for path in saved:
    tex = unreal.EditorAssetLibrary.load_asset(path)
    rows[path] = {"size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()],
                  "compression": str(tex.get_editor_property("compression_settings")),
                  "srgb": bool(tex.get_editor_property("srgb"))}
wm.write_json("import_detail_maps_result.json", rows)
unreal.log(f"PUSS_WING_DETAIL_IMPORT_SUCCESS|textures={len(saved)}|dirty=0")
