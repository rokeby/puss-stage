"""Probe 2: is the NoiseVolume failure only an intermediate state (domain set while blend still OPAQUE)?
Unsaved materials under /Game/ZZ_Bench/BeamTexProbe2/. Markers BEAMTEX_BPROBE2|..."""
import unreal
mel = unreal.MaterialEditingLibrary
DIR = "/Game/ZZ_Bench/BeamTexProbe2"

def stats(mat):
    s = mel.get_statistics(mat)
    out = {}
    for k in ("num_vertex_shader_instructions", "num_pixel_shader_instructions", "num_samplers"):
        try:
            out[k] = s.get_editor_property(k)
        except Exception as e:
            out[k] = "?%s" % e
    return out

def build(name, order, shading):
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, DIR, unreal.Material, unreal.MaterialFactoryNew())
    unreal.log("BEAMTEX_BPROBE2_STEP|%s|created" % name)
    for step in order:
        if step == "blend":
            mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
        elif step == "shading":
            mat.set_editor_property("shading_model", shading)
        elif step == "domain":
            mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
        unreal.log("BEAMTEX_BPROBE2_STEP|%s|%s" % (name, step))
    c = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -600, 100)
    c.set_editor_property("r", 0.35)
    alb = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -600, -150)
    alb.set_editor_property("constant", unreal.LinearColor(0.8, 0.8, 0.8, 1.0))
    mel.connect_material_property(alb, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    unreal.log("BEAMTEX_BPROBE2_STEP|%s|wired" % name)
    mel.recompile_material(mat)
    unreal.log("BEAMTEX_BPROBE2_FINAL|%s|stats=%s" % (name, stats(mat)))

L, U = unreal.MaterialShadingModel.MSM_DEFAULT_LIT, unreal.MaterialShadingModel.MSM_UNLIT
build("Q1_BlendFirst_Lit", ["blend", "shading", "domain"], L)
build("Q2_DomainFirst_Lit", ["domain", "blend", "shading"], L)
build("Q3_BlendFirst_Unlit", ["blend", "shading", "domain"], U)
unreal.log("BEAMTEX_BPROBE2_DONE")
