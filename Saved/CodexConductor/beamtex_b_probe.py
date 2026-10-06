"""Bisect why M_ZZ_BeamTex_NoiseVolume fails to compile (6 Oct). Creates UNSAVED probe materials under
/Game/ZZ_Bench/BeamTexProbe/ (Don't-Save restart afterwards). No save call. Markers: BEAMTEX_BPROBE|..."""
import importlib.util, unreal
spec = importlib.util.spec_from_file_location("btb_src", "E:/PussStage/Saved/CodexConductor/beam_texture_bench.py")
src = open("E:/PussStage/Saved/CodexConductor/beam_texture_bench.py", encoding="utf-8").read()
ns = {}
code_noise = src.split('CODE_NOISE3 = r"""', 1)[1].split('"""', 1)[0]
mel = unreal.MaterialEditingLibrary
DIR = "/Game/ZZ_Bench/BeamTexProbe"
unreal.log("BEAMTEX_BPROBE_API|" + ",".join(n for n in dir(mel) if "rror" in n or "ompile" in n or "tat" in n))
INPUTS = ["WP", "T", "NoiseCm", "Contrast", "FloorFrac", "Peak", "Drift"]
VALS = {"NoiseCm": 120.0, "Contrast": 2.0, "FloorFrac": 0.2, "Peak": 0.35, "Drift": 20.0}

def build(name, domain_volume=True, shading="lit", exclude=True, trunc=True, use_custom=True, code=code_noise,
          ssc=True, blend="additive"):
    path = DIR + "/" + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, DIR, unreal.Material, unreal.MaterialFactoryNew())
    if domain_volume:
        mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE if blend == "additive" else unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT if shading == "lit"
                            else unreal.MaterialShadingModel.MSM_UNLIT)
    if use_custom:
        wp = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -1200, 0)
        if exclude:
            wp.set_editor_property("world_position_shader_offset", unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
        src_wp = wp
        if trunc:
            t = mel.create_material_expression(mat, unreal.MaterialExpressionTruncateLWC, -1000, 0)
            mel.connect_material_expressions(wp, "", t, "")
            src_wp = t
        tm = mel.create_material_expression(mat, unreal.MaterialExpressionTime, -1000, 120)
        c = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -600, 100)
        c.set_editor_property("code", code)
        c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        ins = []
        for n in INPUTS:
            ci = unreal.CustomInput(); ci.set_editor_property("input_name", n); ins.append(ci)
        c.set_editor_property("inputs", ins)
        ok = [mel.connect_material_expressions(src_wp, "", c, "WP"), mel.connect_material_expressions(tm, "", c, "T")]
        for k, (n, v) in enumerate(VALS.items()):
            s = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -1000, 250 + 100 * k)
            s.set_editor_property("parameter_name", n); s.set_editor_property("default_value", v)
            ok.append(mel.connect_material_expressions(s, "", c, n))
        out = c
    else:
        out = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -600, 100)
        out.set_editor_property("r", 0.35); ok = []
    alb = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -600, -150)
    alb.set_editor_property("constant", unreal.LinearColor(0.8, 0.8, 0.8, 1.0))
    ok.append(mel.connect_material_property(alb, "", unreal.MaterialProperty.MP_BASE_COLOR))
    ok.append(mel.connect_material_property(out, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR if ssc
                                            else unreal.MaterialProperty.MP_EMISSIVE_COLOR))
    unreal.log("BEAMTEX_BPROBE_BUILT|%s|links=%s" % (name, ok))
    mel.recompile_material(mat)
    unreal.log("BEAMTEX_BPROBE_RECOMPILED|%s" % name)

simple = "return Peak * saturate(frac(WP.x / NoiseCm + T * Drift * 0.0) * Contrast + FloorFrac);"
build("P1_Full")
build("P2_NoExclude", exclude=False)
build("P3_NoTrunc", trunc=False)
build("P4_NoTruncNoExclude", trunc=False, exclude=False)
build("P5_Const", use_custom=False)
build("P6_SimpleCode", code=simple)
build("P7_SurfaceDomain", domain_volume=False, blend="opaque", ssc=False)
unreal.log("BEAMTEX_BPROBE_DONE")
