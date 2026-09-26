"""Import generated Group B _H/_N into /Game/Scenes/Wings/PaintedSurface/GeneratedRelief.

Source: DerivedAssets/WingMateriality/GroupBRelief/<stem>/Textures/<stem>_H.png, _N.png,
made by Tools/StageOpening/generate_relief_maps.py from the textures exported out of
Unreal (SourceExports/GroupB), so they are pixel-registered with what renders.
New packages only; nothing is assigned (the conductor's condition: generate now,
wire later, after the trial is accepted). Saves exactly the imported textures.
"""
import glob, importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)

DEST = "/Game/Scenes/Wings/PaintedSurface/GeneratedRelief"
SRC = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                   "DerivedAssets", "WingMateriality", "GroupBRelief")
wm.editor_ready()
before = wm.dirty()
tasks, expected = [], []
for folder in sorted(glob.glob(os.path.join(SRC, "*"))):
    stem = os.path.basename(folder)
    for suffix in ("_H", "_N"):
        fn = os.path.join(folder, "Textures", stem + suffix + ".png")
        wm.require(os.path.exists(fn), f"missing {fn}")
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", fn)
        t.set_editor_property("destination_path", DEST)
        t.set_editor_property("destination_name", f"T_{stem}{suffix}")
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", False)
        tasks.append(t)
        expected.append((f"{DEST}/T_{stem}{suffix}", suffix))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
rows = {}
for path, suffix in expected:
    tex = unreal.EditorAssetLibrary.load_asset(path)
    wm.require(isinstance(tex, unreal.Texture2D), f"{path} did not import")
    tex.set_editor_property("srgb", False)
    if suffix == "_N":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
    else:
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    wm.require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), f"save failed {path}")
    rows[path] = [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]
after = wm.dirty()
wm.require(set(after) <= set(before), f"Import left new dirty packages: {sorted(set(after) - set(before))}")
wm.write_json("import_generated_relief_result.json", rows)
unreal.log(f"PUSS_WING_GENERATED_RELIEF_IMPORT_SUCCESS|textures={len(rows)}")
