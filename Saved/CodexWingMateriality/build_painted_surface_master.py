"""Build (or rebuild in place) M_Wing_PaintedSurface_Master and M_Wing_CanvasEdge_Master.

New assets under /Game/Scenes/Wings/PaintedSurface. The old relief master and edge
material are not touched; they stay as the rollback.

Painted surface master:
  - parallax occlusion from the _H map, or from BaseColor luminance where a panel has
    no height map (static switch HasHeightMap);
  - clear-coat varnish with its own roughness, plus anisotropy for oil highlights;
  - height-driven grime (crevices) and rubbed wear (ridges), broken up by tiling grime;
  - close-range canvas weave and brush detail in panel-local centimetres, faded by
    distance so it never shimmers far away;
  - PerInstanceRandom tint, roughness, wear and detail offset (no C++ needed);
  - burn: BurnMask + BurnProgress behind static switch UseBurn (compiles out unused).
Parameter names BaseColor / Height / Normal / OpacityMask / Roughness / Specular match
the old relief master, so its MIs can be reparented without re-setting textures.

USAGE FLAGS ARE SET EXPLICITLY ON BOTH MASTERS (used_with_instanced_static_meshes,
used_with_nanite). Every wing is an ISM and 74 of 149 wing meshes are Nanite. The old
master had both False; the editor sets them silently at load, but a -game or packaged
run would render every wing with the default material. Do not "tidy" these away.
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL

FOLDER = "/Game/Scenes/Wings/PaintedSurface"
TEX = FOLDER + "/Textures"
MASTER = FOLDER + "/M_Wing_PaintedSurface_Master"
EDGE = FOLDER + "/M_Wing_CanvasEdge_Master"
POM_FN = "/Engine/Functions/Engine_MaterialFunctions01/Texturing/ParallaxOcclusionMapping"
DEF_BASE = "/Game/Scenes/Wings/StageOpeningV2/Textures/BambooScaffold_01_L"
DEF_H = "/Game/Scenes/Wings/StageOpeningV2/Textures/BambooScaffold_01_L_H"
DEF_N = "/Game/Scenes/Wings/StageOpeningV2/Textures/BambooScaffold_01_L_N"

LOG = []


def load(path):
    a = unreal.EditorAssetLibrary.load_asset(path)
    wm.require(a is not None, f"missing {path}")
    return a


def get_or_create(path):
    folder, name = path.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mat = load(path)
        # delete_all_material_expressions leaves nodes behind in 5.8; delete one by one and prove it.
        for e in list(MEL.get_material_expressions(mat)):
            MEL.delete_material_expression(mat, e)
        MEL.delete_all_material_expressions(mat)
        left = MEL.get_num_material_expressions(mat)
        wm.require(left == 0, f"{name}: {left} expressions survived the clear")
        LOG.append(f"rebuilt:{name}")
        return mat
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    wm.require(mat is not None, f"could not create {path}")
    LOG.append(f"created:{name}")
    return mat


class Graph:
    def __init__(self, mat):
        self.mat = mat
        self.col = {}

    def node(self, cls, x, y, **props):
        n = MEL.create_material_expression(self.mat, cls, x, y)
        wm.require(n is not None, f"create {cls}")
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    def scalar(self, name, value, group, x, y, prio=0):
        return self.node(unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name,
                         default_value=value, group=group, sort_priority=prio)

    def vector(self, name, rgb, group, x, y, prio=0):
        return self.node(unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name,
                         default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0), group=group, sort_priority=prio)

    def const3(self, rgb, x, y):
        return self.node(unreal.MaterialExpressionConstant3Vector, x, y,
                         constant=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))

    def const4(self, rgba, x, y):
        return self.node(unreal.MaterialExpressionConstant4Vector, x, y,
                         constant=unreal.LinearColor(*rgba))

    def const(self, v, x, y):
        return self.node(unreal.MaterialExpressionConstant, x, y, r=v)

    def link(self, a, a_out, b, b_in):
        ok = MEL.connect_material_expressions(a, a_out, b, b_in)
        if not ok and len(MEL.get_material_expression_input_names(b)) == 1:
            ok = MEL.connect_material_expressions(a, a_out, b, "")  # single-input nodes report 'None'
        if not ok:
            names = [str(n) for n in MEL.get_material_expression_input_names(b)]
            raise RuntimeError(f"connect {a.get_name()}.{a_out!r} -> {b.get_name()}.{b_in!r} failed; inputs={names}")

    def prop(self, a, a_out, prop):
        ok = MEL.connect_material_property(a, a_out, prop)
        wm.require(ok, f"connect {a.get_name()}.{a_out!r} -> {prop} failed")

    def custom(self, x, y, desc, code, inputs, out_type, extra_outputs=()):
        n = self.node(unreal.MaterialExpressionCustom, x, y, description=desc, code=code,
                      output_type=out_type)
        def struct(cls, **props):
            st = cls()
            for k, v in props.items():
                st.set_editor_property(k, v)
            return st
        n.set_editor_property("inputs", [struct(unreal.CustomInput, input_name=i) for i in inputs])
        if extra_outputs:
            n.set_editor_property("additional_outputs",
                                  [struct(unreal.CustomOutput, output_name=o, output_type=t) for o, t in extra_outputs])
        return n


F1, F2, F3 = (unreal.CustomMaterialOutputType.CMOT_FLOAT1, unreal.CustomMaterialOutputType.CMOT_FLOAT2,
              unreal.CustomMaterialOutputType.CMOT_FLOAT3)
SHARED = unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS

CODE_DETAIL_COORDS = r"""
float sy = max(length(AxisY), 1e-3);
float sz = max(length(AxisZ), 1e-3);
float2 cm = float2(LocalPos.y * sy, -LocalPos.z * sz);
float2 jitter = frac(Rand * float2(17.31, 5.13)) * 97.0;
BrushUV = cm / max(BrushTileCm, 1.0) + jitter;
GrimeUV = cm / max(GrimeTileCm, 1.0) + jitter.yx;
return cm / max(WeaveTileCm, 0.1);
"""

CODE_FADE = r"""
return 1.0 - saturate((Depth - FadeStartCm) / max(FadeEndCm - FadeStartCm, 1.0));
"""

CODE_PAINT = r"""
float r1 = Rand;
float r2 = frac(Rand * 7.1373 + 0.2311);
float r3 = frac(Rand * 13.719 + 0.5711);
float3 c = BC * lerp(float3(1, 1, 1), lerp(TintCool, TintWarm, r1), TintVar);
float wear = saturate(GrimeAmount * (1.0 + (r3 - 0.5) * WearJit));
float cavity = saturate((RefPlane - H) * 3.0);
float ridge = saturate((H - RefPlane) * 3.0);
float grime = saturate(cavity * wear * (0.5 + Grime) * 2.0 + (Grime - 0.7) * wear);
float lum = dot(c, float3(0.2126, 0.7152, 0.0722));
c = lerp(c, c * GrimeTint, grime * CreviceDarken);
float rub = saturate(ridge * wear * (0.5 + BrushH));
c = lerp(c, lerp(c, lum.xxx, 0.35) * (1.0 + RidgeLighten), rub);
c *= 1.0 + (BrushH - 0.5) * BrushTone * Fade;
float rough = Rough + (r2 - 0.5) * RoughJit + grime * 0.18 - rub * 0.12 + (BrushH - 0.5) * 0.08 * Fade;
float cc = VarnishAmt * lerp(0.75, 1.0, r2) * (1.0 - grime * 0.7);
float ccr = VarnishRough + Grime * 0.15 * wear + rub * 0.1;
// Burn. Progress = max(MI preview, per-instance custom data [0]); the front spreads
// in panel centimetres from the ignition UV ([1],[2]), roughened by BurnMask.
// BurnM < 0 means UseBurn is off for this MI.
float charAmt = 0.0, ember = 0.0, hole = 0.0, scorch = 0.0;
float p = max(BurnPreview, BurnProgressCD);
if (BurnM >= 0.0 && p > 1e-4)
{
    // UVSpan*Cm = centimetres covered by UV 0..1 on this mesh (measured, not the bounds:
    // the images carry transparent margins). Radius reaches the farthest UV corner plus
    // the noise and hole pad at progress 1, so 1 always means fully consumed.
    float2 span = float2(UVSpanUCm, UVSpanVCm);
    float2 ign = float2(IgnU, IgnV);
    float dist = length((UV - ign) * span);
    float dmax = length(max(ign, 1.0 - ign) * span);
    float pad = IrregularityCm * 0.5 + 1.25 * BurnEdgeCm;
    float front = p * (dmax + pad) - dist - (BurnM - 0.5) * IrregularityCm;
    float d = front / max(BurnEdgeCm, 1.0);
    scorch = saturate(1.0 + d * 0.5);
    charAmt = saturate(d * 1.4);
    ember = saturate(1.0 - abs(d - 0.12) * 5.0) * step(0.0, d);
    hole = step(1.25, d);
}
c = lerp(c, c * ScorchTint, scorch * 0.7);
c = lerp(c, CharColor, charAmt);
rough = lerp(rough, 0.95, charAmt);
cc *= 1.0 - max(charAmt, scorch * 0.5);
OutRoughness = saturate(rough);
OutClearCoat = saturate(cc);
OutClearCoatRoughness = saturate(ccr);
OutEmissive = EmberColor * EmberIntensity * ember;
OutOpacity = 1.0 - hole;
return max(c, 0.0);
"""

CODE_NORMAL = r"""
float3 b = normalize(lerp(float3(0, 0, 1), Base, BaseStrength));
float3 w = lerp(float3(0, 0, 1), Weave, WeaveStr * Fade);
float3 s = lerp(float3(0, 0, 1), Brush, BrushStr * Fade);
float3 d = float3(w.xy + s.xy, w.z * s.z);
return normalize(float3(b.xy + d.xy, b.z * d.z));
"""

CODE_EDGE = r"""
// Edge faces of a cut-out: across = local X through the thickness, along = the
// silhouette direction. Timber batten core, canvas turned over it at both faces,
// frayed where the canvas lip wanders.
float3 n = normalize(NormalLocal);
float3 t = normalize(cross(n, float3(1, 0, 0)) + 1e-5);
float along = dot(LocalPos, t);
float across = LocalPos.x / max(HalfThicknessCm, 0.1);   // -1..1 face to face
float fray = NoiseFine - 0.5;
float lipW = LipCm / max(HalfThicknessCm, 0.1) * (1.0 + fray * FrayAmount);
float lip = smoothstep(1.0 - lipW - 0.04, 1.0 - lipW, abs(across));
float grain = 0.5 + 0.5 * sin(across * 9.0 + NoiseCoarse * 6.0 + along * 0.015);
float3 timber = lerp(TimberDark, TimberLight, grain * (0.6 + 0.4 * NoiseFine));
float3 canvas = CanvasColor * (0.8 + 0.4 * NoiseFine);
OutRoughness = lerp(0.72 + 0.1 * grain, 0.9, lip);
return lerp(timber, canvas, lip);
"""


def build_master():
    mat = get_or_create(MASTER)
    g = Graph(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_CLEAR_COAT)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("use_material_attributes", True)
    mat.set_editor_property("opacity_mask_clip_value", 0.333)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    mat.set_editor_property("used_with_nanite", True)

    # --- 01 Image -------------------------------------------------------------
    uv = g.node(unreal.MaterialExpressionTextureCoordinate, -2600, 0)
    base_obj = g.node(unreal.MaterialExpressionTextureObjectParameter, -2600, 200, parameter_name="BaseColor",
                      texture=load(DEF_BASE), sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                      group="01 Image", sort_priority=0)
    height_obj = g.node(unreal.MaterialExpressionTextureObjectParameter, -2600, 400, parameter_name="Height",
                        texture=load(DEF_H), sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE,
                        group="01 Image", sort_priority=2)
    mask = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1200, 1400, parameter_name="OpacityMask",
                  texture=load(DEF_BASE), sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                  group="01 Image", sort_priority=1, sampler_source=SHARED)
    g.link(uv, "", mask, "UVs")

    # --- 02 Relief: POM from _H, or from BaseColor luminance ------------------
    h_ratio = g.scalar("HeightRatio", 0.006, "02 Relief", -2600, 600, 0)
    min_steps = g.scalar("POMMinSteps", 8.0, "02 Relief", -2600, 700, 1)
    max_steps = g.scalar("POMMaxSteps", 24.0, "02 Relief", -2600, 800, 2)
    ref_plane = g.scalar("ReferencePlane", 0.5, "02 Relief", -2600, 900, 3)
    pom_fn = load(POM_FN)
    poms = []
    for i, (tex_obj, channel) in enumerate(((height_obj, (1.0, 0.0, 0.0, 0.0)),
                                            (base_obj, (0.2126, 0.7152, 0.0722, 0.0)))):
        pom = g.node(unreal.MaterialExpressionMaterialFunctionCall, -2200, 300 + i * 500)
        pom.set_editor_property("material_function", pom_fn)
        chan = g.const4(channel, -2400, 500 + i * 500)
        g.link(tex_obj, "", pom, "Heightmap Texture")
        g.link(h_ratio, "", pom, "Height Ratio")
        g.link(min_steps, "", pom, "Min Steps")
        g.link(max_steps, "", pom, "Max Steps")
        g.link(uv, "", pom, "UVs")
        g.link(chan, "", pom, "Heightmap Channel")
        g.link(ref_plane, "", pom, "Reference Plane")
        poms.append(pom)
    uv_switch = g.node(unreal.MaterialExpressionStaticSwitchParameter, -1900, 400, parameter_name="HasHeightMap",
                       default_value=True, group="02 Relief", sort_priority=10)
    g.link(poms[0], "Parallax UVs", uv_switch, "True")
    g.link(poms[1], "Parallax UVs", uv_switch, "False")

    base_s = g.node(unreal.MaterialExpressionTextureSample, -1600, 200, sampler_source=SHARED)
    g.link(base_obj, "", base_s, "Tex")
    g.link(uv_switch, "", base_s, "UVs")
    height_s = g.node(unreal.MaterialExpressionTextureSample, -1600, 450, sampler_source=SHARED)
    g.link(height_obj, "", height_s, "Tex")
    g.link(uv_switch, "", height_s, "UVs")
    luma = g.node(unreal.MaterialExpressionDotProduct, -1400, 600)
    g.link(base_s, "RGB", luma, "A")
    g.link(g.const3((0.2126, 0.7152, 0.0722), -1600, 700), "", luma, "B")
    h_switch = g.node(unreal.MaterialExpressionStaticSwitchParameter, -1200, 450, parameter_name="HasHeightMap",
                      default_value=True, group="02 Relief", sort_priority=10)
    g.link(height_s, "R", h_switch, "True")
    g.link(luma, "", h_switch, "False")
    normal_s = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1600, 850, parameter_name="Normal",
                      texture=load(DEF_N), sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
                      group="01 Image", sort_priority=3, sampler_source=SHARED)
    g.link(uv_switch, "", normal_s, "UVs")

    # --- close-range detail coordinates, in panel-local centimetres ------------
    rand = g.node(unreal.MaterialExpressionPerInstanceRandom, -2600, 1100)
    # Per-instance custom data, agreed with Effects sources: [0] BurnProgress, [1] IgnitionU,
    # [2] IgnitionV (V-down), [3] VariationSeed. Defaults apply while the ISMs carry 0 floats.
    cd = [g.node(unreal.MaterialExpressionPerInstanceCustomData, -2600, 2600 + i * 100, data_index=i,
                 const_default_value=dv) for i, dv in enumerate((0.0, 0.5, 1.0, -1.0))]
    seed = g.custom(-2400, 1050, "Seed: custom data [3] if written, else PerInstanceRandom",
                    "return CD3 >= 0.0 ? frac(CD3) : PIR;", ["CD3", "PIR"], F1)
    g.link(cd[3], "", seed, "CD3")
    g.link(rand, "", seed, "PIR")
    wpos = g.node(unreal.MaterialExpressionWorldPosition, -2600, 1200,
                  world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    lpos = g.node(unreal.MaterialExpressionTransformPosition, -2400, 1200,
                  transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
                  transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    g.link(wpos, "", lpos, "Input")
    axes = []
    for i, v in enumerate(((0.0, 1.0, 0.0), (0.0, 0.0, 1.0))):
        t = g.node(unreal.MaterialExpressionTransform, -2400, 1350 + i * 120,
                   transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
                   transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        g.link(g.const3(v, -2600, 1350 + i * 120), "", t, "VectorInput")
        axes.append(t)
    weave_tile = g.scalar("WeaveTileCm", 4.0, "05 Close Detail", -2600, 1600, 0)
    brush_tile = g.scalar("BrushTileCm", 60.0, "05 Close Detail", -2600, 1700, 1)
    grime_tile = g.scalar("GrimeTileCm", 140.0, "05 Close Detail", -2600, 1800, 2)
    coords = g.custom(-2100, 1300, "Detail coords (panel-local cm)", CODE_DETAIL_COORDS,
                      ["LocalPos", "AxisY", "AxisZ", "Rand", "WeaveTileCm", "BrushTileCm", "GrimeTileCm"], F2,
                      [("BrushUV", F2), ("GrimeUV", F2)])
    for src, pin in ((lpos, "LocalPos"), (axes[0], "AxisY"), (axes[1], "AxisZ"), (seed, "Rand"),
                     (weave_tile, "WeaveTileCm"), (brush_tile, "BrushTileCm"), (grime_tile, "GrimeTileCm")):
        g.link(src, "", coords, pin)

    depth = g.node(unreal.MaterialExpressionPixelDepth, -2100, 1650)
    fade_start = g.scalar("DetailFadeStartCm", 150.0, "05 Close Detail", -2300, 1900, 10)
    fade_end = g.scalar("DetailFadeEndCm", 1500.0, "05 Close Detail", -2300, 2000, 11)
    fade = g.custom(-1900, 1700, "Detail distance fade", CODE_FADE, ["Depth", "FadeStartCm", "FadeEndCm"], F1)
    g.link(depth, "", fade, "Depth")
    g.link(fade_start, "", fade, "FadeStartCm")
    g.link(fade_end, "", fade, "FadeEndCm")

    def detail(name, path, sampler, x, y, uv_out):
        n = g.node(unreal.MaterialExpressionTextureSampleParameter2D, x, y, parameter_name=name, texture=load(path),
                   sampler_type=sampler, group="05 Close Detail", sort_priority=20, sampler_source=SHARED)
        g.link(coords, uv_out, n, "UVs")
        return n

    ST = unreal.MaterialSamplerType
    weave_n = detail("DetailWeaveNormal", TEX + "/T_WingDetail_WeaveN", ST.SAMPLERTYPE_NORMAL, -1600, 1250, "")
    brush_n = detail("DetailBrushNormal", TEX + "/T_WingDetail_BrushN", ST.SAMPLERTYPE_NORMAL, -1600, 1500, "BrushUV")
    brush_h = detail("DetailBrushHeight", TEX + "/T_WingDetail_BrushH", ST.SAMPLERTYPE_LINEAR_GRAYSCALE, -1600, 1750, "BrushUV")
    grime_t = detail("GrimeBreakup", TEX + "/T_WingDetail_Grime", ST.SAMPLERTYPE_LINEAR_GRAYSCALE, -1600, 2000, "GrimeUV")

    # --- 07 Burn (compiles out unless UseBurn) --------------------------------
    burn_s = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1600, 2300, parameter_name="BurnMask",
                    texture=load(TEX + "/T_WingDetail_Grime"), sampler_type=ST.SAMPLERTYPE_LINEAR_GRAYSCALE,
                    group="07 Burn", sort_priority=1, sampler_source=SHARED)
    g.link(uv, "", burn_s, "UVs")
    burn_sw = g.node(unreal.MaterialExpressionStaticSwitchParameter, -1300, 2300, parameter_name="UseBurn",
                     default_value=False, group="07 Burn", sort_priority=0)
    g.link(burn_s, "R", burn_sw, "True")
    g.link(g.const(-1.0, -1500, 2450), "", burn_sw, "False")

    # --- paint surface ---------------------------------------------------------
    paint_in = ["BC", "H", "Rand", "Grime", "BrushH", "Fade", "BurnM", "RefPlane", "CreviceDarken", "RidgeLighten",
                "GrimeAmount", "GrimeTint", "TintVar", "TintWarm", "TintCool", "Rough", "RoughJit", "VarnishAmt",
                "VarnishRough", "WearJit", "BrushTone", "BurnPreview", "BurnProgressCD", "IgnU", "IgnV", "UV",
                "UVSpanUCm", "UVSpanVCm", "IrregularityCm", "BurnEdgeCm", "ScorchTint",
                "CharColor", "EmberColor", "EmberIntensity"]
    paint = g.custom(-700, 600, "Painted surface: grime, wear, varnish, variation, burn", CODE_PAINT, paint_in, F3,
                     [("OutRoughness", F1), ("OutClearCoat", F1), ("OutClearCoatRoughness", F1),
                      ("OutEmissive", F3), ("OutOpacity", F1)])
    params = {
        "Rough": g.scalar("Roughness", 0.72, "03 Paint & Varnish", -1000, 900, 0),
        "VarnishAmt": g.scalar("VarnishAmount", 0.35, "03 Paint & Varnish", -1000, 1000, 1),
        "VarnishRough": g.scalar("VarnishRoughness", 0.22, "03 Paint & Varnish", -1000, 1100, 2),
        "BrushTone": g.scalar("BrushTone", 0.12, "05 Close Detail", -1000, 1200, 5),
        "CreviceDarken": g.scalar("CreviceDarken", 0.45, "04 Grime & Wear", -1000, 1300, 0),
        "RidgeLighten": g.scalar("RidgeLighten", 0.18, "04 Grime & Wear", -1000, 1400, 1),
        "GrimeAmount": g.scalar("GrimeAmount", 0.45, "04 Grime & Wear", -1000, 1500, 2),
        "GrimeTint": g.vector("GrimeTint", (0.42, 0.36, 0.28), "04 Grime & Wear", -1000, 1600, 3),
        "TintVar": g.scalar("TintVariation", 0.10, "06 Variation", -1000, 1700, 0),
        "TintWarm": g.vector("TintWarm", (1.06, 0.98, 0.86), "06 Variation", -1000, 1800, 1),
        "TintCool": g.vector("TintCool", (0.90, 0.96, 1.04), "06 Variation", -1000, 1900, 2),
        "RoughJit": g.scalar("RoughnessJitter", 0.10, "06 Variation", -1000, 2000, 3),
        "WearJit": g.scalar("WearJitter", 0.6, "06 Variation", -1000, 2100, 4),
        "BurnPreview": g.scalar("BurnPreview", 0.0, "07 Burn", -1000, 2400, 2),
        # BurnEdgeCm and BurnIrregularityCm are COUPLED to Effects sources' Wing Burn:
        # their front pad InfinityStageWingBurn::FrontPadCm = Irregularity/2 + 1.25*Edge = 130.
        # Change both sides together (and never override these per MI), or flames leave the char line.
        "BurnEdgeCm": g.scalar("BurnEdgeCm", 40.0, "07 Burn", -1000, 2500, 3),
        "IrregularityCm": g.scalar("BurnIrregularityCm", 160.0, "07 Burn", -1000, 2575, 8),
        "ScorchTint": g.vector("ScorchTint", (0.55, 0.36, 0.2), "07 Burn", -1000, 2590, 9),
        "UVSpanUCm": g.scalar("UVSpanUCm", 1000.0, "08 Panel", -1000, 2900, 0),
        "UVSpanVCm": g.scalar("UVSpanVCm", 1500.0, "08 Panel", -1000, 3000, 1),
        "CharColor": g.vector("CharColor", (0.018, 0.014, 0.012), "07 Burn", -1000, 2600, 4),
        "EmberColor": g.vector("EmberColor", (1.0, 0.32, 0.06), "07 Burn", -1000, 2700, 5),
        "EmberIntensity": g.scalar("EmberIntensity", 12.0, "07 Burn", -1000, 2800, 6),
    }
    wires = {"BC": (base_s, "RGB"), "H": (h_switch, ""), "Rand": (seed, ""), "Grime": (grime_t, "R"),
             "BurnProgressCD": (cd[0], ""), "IgnU": (cd[1], ""), "IgnV": (cd[2], ""), "UV": (uv, ""),
             "BrushH": (brush_h, "R"), "Fade": (fade, ""), "BurnM": (burn_sw, ""), "RefPlane": (ref_plane, "")}
    wires.update({k: (v, "") for k, v in params.items()})
    for pin in paint_in:
        src, out = wires[pin]
        g.link(src, out, paint, pin)

    normal_strength = g.scalar("NormalStrength", 1.0, "02 Relief", -1000, 300, 4)
    weave_str = g.scalar("WeaveStrength", 0.35, "05 Close Detail", -1000, 400, 3)
    brush_str = g.scalar("BrushStrength", 0.5, "05 Close Detail", -1000, 500, 4)
    nrm = g.custom(-700, 250, "Base + weave + brush normal (whiteout)", CODE_NORMAL,
                   ["Base", "Weave", "Brush", "BaseStrength", "WeaveStr", "BrushStr", "Fade"], F3)
    for src, out, pin in ((normal_s, "RGB", "Base"), (weave_n, "RGB", "Weave"), (brush_n, "RGB", "Brush"),
                          (normal_strength, "", "BaseStrength"), (weave_str, "", "WeaveStr"),
                          (brush_str, "", "BrushStr"), (fade, "", "Fade")):
        g.link(src, out, nrm, pin)

    opacity = g.node(unreal.MaterialExpressionMultiply, -400, 1400)
    g.link(mask, "A", opacity, "A")
    g.link(paint, "OutOpacity", opacity, "B")

    specular = g.scalar("Specular", 0.28, "03 Paint & Varnish", -400, 900, 3)
    aniso = g.scalar("Anisotropy", 0.25, "03 Paint & Varnish", -400, 1000, 4)
    # Clear-coat pins (CustomData0/1) aren't exposed as MaterialProperty in Python,
    # so the master outputs through Make Material Attributes.
    attrs = g.node(unreal.MaterialExpressionMakeMaterialAttributes, -100, 600)
    for src, out, pin in ((paint, "", "BaseColor"), (nrm, "", "Normal"), (paint, "OutRoughness", "Roughness"),
                          (specular, "", "Specular"), (paint, "OutClearCoat", "ClearCoat"),
                          (paint, "OutClearCoatRoughness", "ClearCoatRoughness"), (paint, "OutEmissive", "EmissiveColor"),
                          (opacity, "", "OpacityMask"), (aniso, "", "Anisotropy")):
        g.link(src, out, attrs, pin)
    g.prop(attrs, "", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
    return mat


def build_edge():
    mat = get_or_create(EDGE)
    g = Graph(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    mat.set_editor_property("used_with_nanite", True)

    wpos = g.node(unreal.MaterialExpressionWorldPosition, -1600, 0,
                  world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    lpos = g.node(unreal.MaterialExpressionTransformPosition, -1400, 0,
                  transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
                  transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    g.link(wpos, "", lpos, "Input")
    vn = g.node(unreal.MaterialExpressionVertexNormalWS, -1600, 200)
    nl = g.node(unreal.MaterialExpressionTransform, -1400, 200,
                transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD,
                transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_LOCAL)
    g.link(vn, "", nl, "VectorInput")
    # Noise in local cm: fine (fray, fibre) and coarse (grain wander).
    uv_fine = g.node(unreal.MaterialExpressionComponentMask, -1400, 400, r=False, g=True, b=True, a=False)
    g.link(lpos, "", uv_fine, "")
    fine_scale = g.node(unreal.MaterialExpressionMultiply, -1200, 400)
    g.link(uv_fine, "", fine_scale, "A")
    g.link(g.const(1.0 / 9.0, -1400, 520), "", fine_scale, "B")
    coarse_scale = g.node(unreal.MaterialExpressionMultiply, -1200, 600)
    g.link(uv_fine, "", coarse_scale, "A")
    g.link(g.const(1.0 / 120.0, -1400, 700), "", coarse_scale, "B")
    grime_tex = load(TEX + "/T_WingDetail_Grime")
    noise_fine = g.node(unreal.MaterialExpressionTextureSample, -1000, 400, texture=grime_tex,
                        sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, sampler_source=SHARED)
    g.link(fine_scale, "", noise_fine, "UVs")
    noise_coarse = g.node(unreal.MaterialExpressionTextureSample, -1000, 600, texture=grime_tex,
                          sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, sampler_source=SHARED)
    g.link(coarse_scale, "", noise_coarse, "UVs")

    ins = ["LocalPos", "NormalLocal", "NoiseFine", "NoiseCoarse", "HalfThicknessCm", "LipCm", "FrayAmount",
           "TimberDark", "TimberLight", "CanvasColor"]
    edge = g.custom(-600, 200, "Batten core, canvas lip, fray", CODE_EDGE, ins, F3, [("OutRoughness", F1)])
    wires = {
        "LocalPos": (lpos, ""), "NormalLocal": (nl, ""), "NoiseFine": (noise_fine, "R"),
        "NoiseCoarse": (noise_coarse, "R"),
        "HalfThicknessCm": (g.scalar("HalfThicknessCm", 5.0, "Edge", -900, 800, 0), ""),
        "LipCm": (g.scalar("CanvasLipCm", 0.6, "Edge", -900, 900, 1), ""),
        "FrayAmount": (g.scalar("FrayAmount", 0.8, "Edge", -900, 1000, 2), ""),
        "TimberDark": (g.vector("TimberDark", (0.045, 0.028, 0.016), "Edge", -900, 1100, 3), ""),
        "TimberLight": (g.vector("TimberLight", (0.16, 0.10, 0.055), "Edge", -900, 1200, 4), ""),
        "CanvasColor": (g.vector("CanvasColor", (0.30, 0.27, 0.22), "Edge", -900, 1300, 5), ""),
    }
    for pin in ins:
        src, out = wires[pin]
        g.link(src, out, edge, pin)
    MP = unreal.MaterialProperty
    g.prop(edge, "", MP.MP_BASE_COLOR)
    g.prop(edge, "OutRoughness", MP.MP_ROUGHNESS)
    g.prop(g.scalar("Specular", 0.3, "Edge", -300, 500, 6), "", MP.MP_SPECULAR)
    return mat


wm.editor_ready()
before = wm.dirty()
# Other streams may hold unsaved level work; targeted saves never persist it. The invariant
# is that this script adds nothing to the dirty set beyond its own two packages.
before_others = set(before) - {MASTER, EDGE}
results = {}
for path, builder in ((MASTER, build_master), (EDGE, build_edge)):
    mat = builder()
    MEL.layout_material_expressions(mat)
    MEL.recompile_material(mat)
    stats = MEL.get_statistics(mat)
    results[path] = {
        "expressions": MEL.get_num_material_expressions(mat),
        "used_with_ism": bool(mat.get_editor_property("used_with_instanced_static_meshes")),
        "used_with_nanite": bool(mat.get_editor_property("used_with_nanite")),
        "stats": {p: str(stats.get_editor_property(p)) for p in
                  ("num_pixel_shader_instructions", "num_vertex_shader_instructions", "num_samplers",
                   "num_vertex_texture_samples", "num_pixel_texture_samples")},
    }
    wm.require(results[path]["used_with_ism"] and results[path]["used_with_nanite"], f"usage flags not set on {path}")
    wm.require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), f"save failed {path}")
after = wm.dirty()
wm.require(set(after) <= before_others, f"Build left new dirty packages: {sorted(set(after) - before_others)}")
wm.write_json("build_masters_result.json", {"log": LOG, "results": results})
unreal.log("PUSS_WING_MASTERS_BUILD_SUCCESS|" + "|".join(
    f"{p.rsplit('/', 1)[-1]}:ps={r['stats']['num_pixel_shader_instructions']},samplers={r['stats']['num_samplers']}"
    for p, r in results.items()))
