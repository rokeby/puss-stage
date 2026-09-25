"""Read-only: facts needed to author the new master (cvars, texture formats, POM function pins)."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
editor = wm.editor_ready()
before = wm.dirty()
out = {"cvars": {}}
for cv in ("r.Substrate", "r.AnisotropicMaterials", "r.Nanite.AllowMaskedMaterials", "r.VirtualTextures",
           "r.ClearCoatNormal", "r.Shadow.Virtual.Enable", "r.Nanite.ProjectEnabled"):
    try:
        out["cvars"][cv] = unreal.SystemLibrary.get_console_variable_int_value(cv)
    except Exception as exc:
        out["cvars"][cv] = repr(exc)[:80]
tex_paths = [
    "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2/Textures/T_P02_SET01_L",
    "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2/Textures/T_P02_SET01_L_H",
    "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2/Textures/T_P02_SET01_L_N",
    "/Game/Scenes/Wings/Passage03_ShrineToForgetting/Textures/T_P03_GlassBlockClassroom_01_L_H",
    "/Game/Scenes/Wings/StageOpeningV2/Textures/BambooScaffold_01_L_H",
    "/Game/Scenes/Wings/StageOpeningV2/Textures/BambooScaffold_01_L",
    "/Game/Scenes/Wings/Textures/Beginning_stage",
    "/Game/Scenes/Wings/Passage05_BirdToMountain/Textures/T_CloudRef01_L_H",
]
for p in unreal.EditorAssetLibrary.list_assets("/Game/Scenes/Wings/FireSafetyCurtain", recursive=True):
    tex_paths.append(p.split(".", 1)[0])
out["textures"] = {}
for p in tex_paths:
    t = unreal.EditorAssetLibrary.load_asset(p)
    if not isinstance(t, unreal.Texture2D):
        out["textures"][p] = str(type(t).__name__)
        continue
    rec = {"size": [t.blueprint_get_size_x(), t.blueprint_get_size_y()]}
    for prop in ("compression_settings", "srgb", "lod_group", "virtual_texture_streaming", "address_x", "address_y",
                 "compression_no_alpha"):
        try:
            rec[prop] = str(t.get_editor_property(prop))
        except Exception as exc:
            rec[prop] = "ERR"
    out["textures"][p] = rec
out["functions"] = {}
for fp in ("/Engine/Functions/Engine_MaterialFunctions01/Texturing/ParallaxOcclusionMapping",
           "/Engine/Functions/Engine_MaterialFunctions03/Procedurals/NormalFromHeightmap",
           "/Engine/Functions/Engine_MaterialFunctions02/Utility/BlendAngleCorrectedNormals"):
    f = unreal.EditorAssetLibrary.load_asset(fp)
    if f is None:
        out["functions"][fp] = "missing"
        continue
    ins, outs = [], []
    for e in wm.MEL.get_material_function_expressions(f):
        cls = e.get_class().get_name()
        if cls == "MaterialExpressionFunctionInput":
            ins.append([str(e.get_editor_property("input_name")), str(e.get_editor_property("input_type")),
                        int(e.get_editor_property("sort_priority"))])
        elif cls == "MaterialExpressionFunctionOutput":
            outs.append([str(e.get_editor_property("output_name")), int(e.get_editor_property("sort_priority"))])
    out["functions"][fp] = {"inputs": sorted(ins, key=lambda x: x[2]), "outputs": sorted(outs, key=lambda x: x[1])}
wm.require(wm.dirty() == before, f"dirty changed {wm.dirty()}")
wm.write_json("build_facts.json", out)
unreal.log("PUSS_WING_BUILD_FACTS_SUCCESS")
