"""Build (or rebuild) M_Kit_Surface_Master and its two presets. Gary's choice, 2026-09-29:
"walnut planks, procedural steel for the grooves".

The structure kit is engine Cubes scaled to size, with per-instance custom data
[0] variation 0..1, [1] length, [2] width, [3] thickness (cm), local X = length.
Its UVs stretch with the scale, so this master ignores them and maps per member:
  - panel-local centimetres = local position x instance axis scale (rides with the
    member, so it's safe on anything that moves);
  - the face is picked from the local normal (box faces are axis-aligned), so each
    pixel samples one texture set, not triplanar's three;
  - normals are built in the member's own face frame and output in world space
    (tangent_space_normal False), because projected UVs don't match the cube's tangents.
Wood (IsMetal False): the walnut strip set from the 4K_WoodFlooring_Vol_02 pack, reused
not copied. One strip of the texture per board, chosen by the variation, grain along
the length, darker end grain.
Steel (IsMetal True): procedural brushed and worn steel, with no texture download.
It reuses our tiling detail maps, adds anisotropy along the length, and lightens and
smooths the edges where wear shows.
New assets in our own folder only. No level, no Show, no assignment: Rig assigns
Ground.BoardMaterial and the groove slot. ISM and Nanite usage are set explicitly.
"""
import importlib.util, os
import unreal
here = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(here, "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
bspec = importlib.util.spec_from_file_location("wm_builder", os.path.join(here, "build_painted_surface_master.py"))
B = importlib.util.module_from_spec(bspec)
B.WM_IMPORT_ONLY = True
bspec.loader.exec_module(B)
MEL = wm.MEL

KIT = B.FOLDER + "/Kit"
MASTER = KIT + "/M_Kit_Surface_Master"
MI_WOOD = KIT + "/MI_Kit_WalnutPlank"
MI_STEEL = KIT + "/MI_Kit_SteelGroove"
PACK = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Textures/Strip/T_Walnut_Strp_02_"
WOOD = {"D": PACK + "D", "N": PACK + "N", "R": PACK + "R", "AO": PACK + "AO"}
# Texture layout, read off T_Walnut_Strp_02_D and its strip mask T_Strp_01_M
# (exported 2026-09-29 to DerivedAssets/WingMateriality/SourceExports/KitWalnut).
# Strips run along U, 20 rows, and each plank is 0.5 U long; even rows joint at
# 0/0.5, odd rows at 0.25/0.75. A 960 cm tile gives one painted plank per 480 cm
# (Rig's MaxBoardLengthCm), so no painted joint lands mid-board. A 24 cm board maps
# to one strip, about 1.7x grain stretch. These are the master defaults; MIs can override.
LAYOUT = {"tile_length_cm": 960, "strips_across": 20, "strip_inset": 0.08, "swap_uv": 0,
          "plank_length_u": 0.5, "plank_offset_odd_u": 0.25, "joint_margin_u": 0.01}

CODE_COORDS = r"""
// Member-space centimetres and the face this pixel is on. Grain axis = local X
// (always, even when a board is shorter than it is wide).
float3 s = float3(max(length(AxisX), 1e-3), max(length(AxisY), 1e-3), max(length(AxisZ), 1e-3));
float3 p = LocalPos * s;
float3 n = abs(normalize(NormalLocal));
float L = LengthCm > 0.0 ? LengthCm : 100.0 * s.x;
float W = WidthCm > 0.0 ? WidthCm : 100.0 * s.y;
float T = ThickCm > 0.0 ? ThickCm : 100.0 * s.z;
float N = max(StripsAcrossTile, 1.0);
float strip = floor(frac(Seed * 7.31) * N);
// Each painted strip holds planks PlankLength long (in U). Odd rows are phase-shifted
// by PlankOffsetOdd. Put the whole board inside one painted plank, at a random slide,
// so no painted butt joint lands mid-board; the board's own ends are the real joints.
float plankStart = (fmod(strip, 2.0) > 0.5) ? PlankOffsetOdd : 0.0;
float Lu = L / max(TileLengthCm, 1.0);
float slack = max(PlankLength - Lu - 2.0 * JointMargin, 0.0);
float u0 = plankStart + JointMargin + slack * frac(Seed * 13.7);
float along = u0 + (p.x + 0.5 * L) / max(TileLengthCm, 1.0);
float across;
if (n.z >= n.x && n.z >= n.y) { across = p.y / W + 0.5; Face = 0.0; }
else if (n.y >= n.x)          { across = p.z / T + 0.5; Face = 1.0; }
else                          { across = p.y / W + 0.5; along = u0 + (p.z + 0.5 * T) / max(TileLengthCm, 1.0); Face = 2.0; }
float v = (strip + StripInset + (1.0 - 2.0 * StripInset) * saturate(across)) / N;
float2 uv = float2(along, v);
uv = lerp(uv, uv.yx, saturate(SwapUV));
// Distance to the nearest edge of this face, in cm (drives steel edge wear).
float3 hs = 0.5 * float3(L, W, T);
float3 d = hs - abs(p);
EdgeCm = (Face == 0.0) ? min(d.x, d.y) : ((Face == 1.0) ? min(d.x, d.z) : min(d.y, d.z));
MemberCm = p;
return uv;
"""

CODE_FRAME = r"""
// Build the world normal from a tangent-space sample in this face's own frame.
float3 ax = normalize(AxisX), ay = normalize(AxisY), az = normalize(AxisZ);
float3 nl = normalize(NormalLocal);
float3 Nw = normalize(nl.x * ax + nl.y * ay + nl.z * az);
float3 Tw, Bw;
if (Face < 0.5)      { Tw = ax; Bw = ay * sign(nl.z + 1e-4); }
else if (Face < 1.5) { Tw = ax; Bw = az * sign(nl.y + 1e-4); }
else                 { Tw = ay; Bw = az * sign(nl.x + 1e-4); }
float3 t = normalize(lerp(float3(0, 0, 1), Nts, Strength));
Tangent = Tw;
return normalize(t.x * Tw + t.y * Bw + t.z * Nw);
"""

CODE_WOOD = r"""
float r1 = frac(Seed * 3.17), r2 = frac(Seed * 5.71);
float3 c = D * lerp(float3(1, 1, 1), lerp(TintCool, TintWarm, r1), TintVar);
c *= (Face > 1.5) ? EndGrainDarken : 1.0;
c = lerp(c, c * GrimeTint, saturate((Grime - 0.55) * 2.0) * GrimeAmount);
OutRoughness = saturate(lerp(RoughLow, RoughHigh, R) + (r2 - 0.5) * RoughJit + Grime * 0.08 * GrimeAmount);
OutAO = lerp(1.0, AO, AOStrength);
return c;
"""

CODE_STEEL = r"""
// Procedural brushed, worn steel. Brush runs along the member (local X).
float wear = saturate(1.0 - EdgeCm / max(EdgeWearCm, 0.1)) * (0.5 + Grime);
float grime = saturate((Grime - 0.45) * 1.8) * GrimeAmount;
float3 c = lerp(SteelColor, SteelColor * 1.6, wear * 0.7);
c = lerp(c, RustTint, grime * 0.6);
c *= 0.92 + 0.16 * Brush;
OutMetallic = lerp(0.95, 0.35, grime);
OutRoughness = saturate(SteelRough + (Brush - 0.5) * 0.12 + grime * 0.35 - wear * 0.2);
OutAnisotropy = SteelAnisotropy * (1.0 - grime);
return c;
"""


def sampler_for(tex):
    comp = str(tex.get_editor_property("compression_settings"))
    srgb = bool(tex.get_editor_property("srgb"))
    ST = unreal.MaterialSamplerType
    if "NORMALMAP" in comp:
        return ST.SAMPLERTYPE_NORMAL
    if "GRAYSCALE" in comp:
        return ST.SAMPLERTYPE_GRAYSCALE if srgb else ST.SAMPLERTYPE_LINEAR_GRAYSCALE
    if "MASKS" in comp:
        return ST.SAMPLERTYPE_MASKS
    if "ALPHA" in comp:
        return ST.SAMPLERTYPE_ALPHA
    return ST.SAMPLERTYPE_COLOR if srgb else ST.SAMPLERTYPE_LINEAR_COLOR


def build_master():
    mat = B.get_or_create(MASTER)
    g = B.Graph(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("use_material_attributes", True)
    mat.set_editor_property("tangent_space_normal", False)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    mat.set_editor_property("used_with_nanite", True)
    F1, F2, F3 = B.F1, B.F2, B.F3

    wpos = g.node(unreal.MaterialExpressionWorldPosition, -3000, 0,
                  world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    lpos = g.node(unreal.MaterialExpressionTransformPosition, -2800, 0,
                  transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
                  transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    g.link(wpos, "", lpos, "Input")
    axes = []
    for i, v in enumerate(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))):
        t = g.node(unreal.MaterialExpressionTransform, -2800, 150 + i * 120,
                   transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
                   transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        g.link(g.const3(v, -3000, 150 + i * 120), "", t, "VectorInput")
        axes.append(t)
    vn = g.node(unreal.MaterialExpressionVertexNormalWS, -3000, 520)
    nl = g.node(unreal.MaterialExpressionTransform, -2800, 520,
                transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD,
                transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_LOCAL)
    g.link(vn, "", nl, "VectorInput")
    cd = [g.node(unreal.MaterialExpressionPerInstanceCustomData, -3000, 700 + i * 100, data_index=i,
                 const_default_value=dv) for i, dv in enumerate((-1.0, 0.0, 0.0, 0.0))]
    rand = g.node(unreal.MaterialExpressionPerInstanceRandom, -3000, 1100)
    seed = g.custom(-2700, 700, "Seed: kit variation [0], else PerInstanceRandom",
                    "return CD0 >= 0.0 ? frac(CD0) : PIR;", ["CD0", "PIR"], F1)
    g.link(cd[0], "", seed, "CD0")
    g.link(rand, "", seed, "PIR")

    p = {  # layout parameters, defaults from the exported texture
        "TileLengthCm": g.scalar("TileLengthCm", float(LAYOUT["tile_length_cm"]), "01 Layout", -2900, 1300, 0),
        "StripsAcrossTile": g.scalar("StripsAcrossTile", float(LAYOUT["strips_across"]), "01 Layout", -2900, 1400, 1),
        "StripInset": g.scalar("StripInset", float(LAYOUT["strip_inset"]), "01 Layout", -2900, 1500, 2),
        "SwapUV": g.scalar("SwapUV", float(LAYOUT["swap_uv"]), "01 Layout", -2900, 1600, 3),
        "PlankLength": g.scalar("PlankLengthU", float(LAYOUT["plank_length_u"]), "01 Layout", -2900, 1700, 4),
        "PlankOffsetOdd": g.scalar("PlankOffsetOddU", float(LAYOUT["plank_offset_odd_u"]), "01 Layout", -2900, 1800, 5),
        "JointMargin": g.scalar("JointMarginU", float(LAYOUT["joint_margin_u"]), "01 Layout", -2900, 1900, 6),
    }
    coords = g.custom(-2400, 300, "Kit coords: member cm, face, strip UV", CODE_COORDS,
                      ["LocalPos", "AxisX", "AxisY", "AxisZ", "NormalLocal", "Seed", "LengthCm", "WidthCm", "ThickCm",
                       "TileLengthCm", "StripsAcrossTile", "StripInset", "SwapUV", "PlankLength", "PlankOffsetOdd",
                       "JointMargin"], F2,
                      [("Face", F1), ("EdgeCm", F1), ("MemberCm", F3)])
    for src, pin in ((lpos, "LocalPos"), (axes[0], "AxisX"), (axes[1], "AxisY"), (axes[2], "AxisZ"),
                     (nl, "NormalLocal"), (seed, "Seed"), (cd[1], "LengthCm"), (cd[2], "WidthCm"), (cd[3], "ThickCm")):
        g.link(src, "", coords, pin)
    for k, node in p.items():
        g.link(node, "", coords, k)

    def tex_param(name, path, x, y, uv_src, uv_out, group):
        t = B.load(path)
        n = g.node(unreal.MaterialExpressionTextureSampleParameter2D, x, y, parameter_name=name, texture=t,
                   sampler_type=sampler_for(t), group=group, sort_priority=0, sampler_source=B.SHARED)
        g.link(uv_src, uv_out, n, "UVs")
        return n

    # --- wood ---------------------------------------------------------------
    d = tex_param("WoodColor", WOOD["D"], -2000, 0, coords, "", "02 Wood")
    nrm = tex_param("WoodNormal", WOOD["N"], -2000, 250, coords, "", "02 Wood")
    rgh = tex_param("WoodRoughness", WOOD["R"], -2000, 500, coords, "", "02 Wood")
    ao = tex_param("WoodAO", WOOD["AO"], -2000, 750, coords, "", "02 Wood")
    grime_uv = g.node(unreal.MaterialExpressionComponentMask, -2200, 1000, r=True, g=True, b=False, a=False)
    g.link(coords, "MemberCm", grime_uv, "")
    grime_scale = g.node(unreal.MaterialExpressionMultiply, -2100, 1000)
    g.link(grime_uv, "", grime_scale, "A")
    g.link(g.const(1.0 / 90.0, -2300, 1100), "", grime_scale, "B")
    grime = g.node(unreal.MaterialExpressionTextureSample, -1900, 1000, texture=B.load(B.TEX + "/T_WingDetail_Grime"),
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, sampler_source=B.SHARED)
    g.link(grime_scale, "", grime, "UVs")
    wood_in = ["D", "R", "AO", "Grime", "Seed", "Face", "TintVar", "TintWarm", "TintCool", "EndGrainDarken",
               "GrimeTint", "GrimeAmount", "RoughLow", "RoughHigh", "RoughJit", "AOStrength"]
    wood = g.custom(-1500, 200, "Walnut plank", CODE_WOOD, wood_in, F3, [("OutRoughness", F1), ("OutAO", F1)])
    wp = {
        "TintVar": g.scalar("TintVariation", 0.12, "02 Wood", -1800, 1200, 1),
        "TintWarm": g.vector("TintWarm", (1.06, 0.98, 0.9), "02 Wood", -1800, 1300, 2),
        "TintCool": g.vector("TintCool", (0.9, 0.93, 0.98), "02 Wood", -1800, 1400, 3),
        "EndGrainDarken": g.scalar("EndGrainDarken", 0.55, "02 Wood", -1800, 1500, 4),
        "GrimeTint": g.vector("GrimeTint", (0.45, 0.38, 0.3), "04 Wear", -1800, 1600, 0),
        "GrimeAmount": g.scalar("GrimeAmount", 0.35, "04 Wear", -1800, 1700, 1),
        "RoughLow": g.scalar("RoughnessLow", 0.45, "02 Wood", -1800, 1800, 5),
        "RoughHigh": g.scalar("RoughnessHigh", 0.8, "02 Wood", -1800, 1900, 6),
        "RoughJit": g.scalar("RoughnessJitter", 0.1, "02 Wood", -1800, 2000, 7),
        "AOStrength": g.scalar("AOStrength", 0.8, "02 Wood", -1800, 2100, 8),
    }
    wires = {"D": (d, "RGB"), "R": (rgh, "R"), "AO": (ao, "R"), "Grime": (grime, "R"), "Seed": (seed, ""),
             "Face": (coords, "Face")}
    wires.update({k: (v, "") for k, v in wp.items()})
    for pin in wood_in:
        g.link(wires[pin][0], wires[pin][1], wood, pin)

    # --- steel --------------------------------------------------------------
    brush_uv = g.custom(-2100, 1300, "Brush UV along the member",
                        "return float2(Cm.x / 60.0, (Face < 0.5 ? Cm.y : Cm.z) / 2.5);", ["Cm", "Face"], F2)
    g.link(coords, "MemberCm", brush_uv, "Cm")
    g.link(coords, "Face", brush_uv, "Face")
    brush = g.node(unreal.MaterialExpressionTextureSample, -1900, 1300, texture=B.load(B.TEX + "/T_WingDetail_BrushH"),
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, sampler_source=B.SHARED)
    g.link(brush_uv, "", brush, "UVs")
    brush_n = g.node(unreal.MaterialExpressionTextureSample, -1900, 1550, texture=B.load(B.TEX + "/T_WingDetail_BrushN"),
                     sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL, sampler_source=B.SHARED)
    g.link(brush_uv, "", brush_n, "UVs")
    steel_in = ["Brush", "Grime", "EdgeCm", "SteelColor", "RustTint", "SteelRough", "SteelAnisotropy",
                "EdgeWearCm", "GrimeAmount"]
    steel = g.custom(-1500, 1300, "Procedural worn steel", CODE_STEEL, steel_in, F3,
                     [("OutMetallic", F1), ("OutRoughness", F1), ("OutAnisotropy", F1)])
    sp = {
        "SteelColor": g.vector("SteelColor", (0.30, 0.30, 0.31), "03 Steel", -1800, 2300, 0),
        "RustTint": g.vector("RustTint", (0.22, 0.12, 0.06), "03 Steel", -1800, 2400, 1),
        "SteelRough": g.scalar("SteelRoughness", 0.42, "03 Steel", -1800, 2500, 2),
        "SteelAnisotropy": g.scalar("SteelAnisotropy", 0.5, "03 Steel", -1800, 2600, 3),
        "EdgeWearCm": g.scalar("EdgeWearCm", 1.2, "03 Steel", -1800, 2700, 4),
    }
    swires = {"Brush": (brush, "R"), "Grime": (grime, "R"), "EdgeCm": (coords, "EdgeCm"),
              "GrimeAmount": (wp["GrimeAmount"], "")}
    swires.update({k: (v, "") for k, v in sp.items()})
    for pin in steel_in:
        g.link(swires[pin][0], swires[pin][1], steel, pin)

    # --- normals in the face frame, one per branch --------------------------
    frames = []
    for i, (src, strength_name, default) in enumerate(((nrm, "WoodNormalStrength", 1.0),
                                                       (brush_n, "SteelBrushStrength", 0.35))):
        fr = g.custom(-1100, 600 + i * 400, "Face-frame normal", CODE_FRAME,
                      ["Nts", "NormalLocal", "AxisX", "AxisY", "AxisZ", "Face", "Strength"], F3, [("Tangent", F3)])
        g.link(src, "RGB", fr, "Nts")
        g.link(nl, "", fr, "NormalLocal")
        for a, pin in zip(axes, ("AxisX", "AxisY", "AxisZ")):
            g.link(a, "", fr, pin)
        g.link(coords, "Face", fr, "Face")
        g.link(g.scalar(strength_name, default, "02 Wood" if i == 0 else "03 Steel", -1300, 900 + i * 400, 9),
               "", fr, "Strength")
        frames.append(fr)

    # --- two attribute sets, one static switch -------------------------------
    spec_node = g.scalar("Specular", 0.4, "02 Wood", -900, 200, 10)
    wood_attr = g.node(unreal.MaterialExpressionMakeMaterialAttributes, -600, 300)
    for s_, o, pin in ((wood, "", "BaseColor"), (wood, "OutRoughness", "Roughness"), (wood, "OutAO", "AmbientOcclusion"),
                       (frames[0], "", "Normal"), (spec_node, "", "Specular")):
        g.link(s_, o, wood_attr, pin)
    steel_attr = g.node(unreal.MaterialExpressionMakeMaterialAttributes, -600, 1100)
    for s_, o, pin in ((steel, "", "BaseColor"), (steel, "OutMetallic", "Metallic"), (steel, "OutRoughness", "Roughness"),
                       (steel, "OutAnisotropy", "Anisotropy"), (frames[1], "", "Normal"),
                       (frames[1], "Tangent", "Tangent")):
        g.link(s_, o, steel_attr, pin)
    sw = g.node(unreal.MaterialExpressionStaticSwitchParameter, -300, 700, parameter_name="IsMetal",
                default_value=False, group="00 Kind", sort_priority=0)
    g.link(steel_attr, "", sw, "True")
    g.link(wood_attr, "", sw, "False")
    g.prop(sw, "", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
    return mat


def make_mi(path, metal):
    folder, name = path.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mi = B.load(path)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, B.load(MASTER))
    MEL.set_material_instance_static_switch_parameter_value(mi, "IsMetal", metal)
    wm.require(MEL.get_material_instance_static_switch_parameter_value(mi, "IsMetal") == metal, f"{name} switch")
    MEL.update_material_instance(mi)
    return mi


def main():
    wm.editor_ready()
    before = wm.dirty()
    mine = {MASTER, MI_WOOD, MI_STEEL}
    before_others = set(before) - mine
    mat = build_master()
    MEL.layout_material_expressions(mat)
    MEL.recompile_material(mat)
    wm.require(bool(mat.get_editor_property("used_with_instanced_static_meshes"))
               and bool(mat.get_editor_property("used_with_nanite")), "usage flags not set")
    wm.require(unreal.EditorAssetLibrary.save_asset(MASTER, only_if_is_dirty=False), "save master failed")
    for path, metal in ((MI_WOOD, False), (MI_STEEL, True)):
        make_mi(path, metal)
        wm.require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), f"save {path} failed")
    after = wm.dirty()
    wm.require(set(after) <= before_others, f"Build left new dirty packages: {sorted(set(after) - before_others)}")
    count = MEL.get_num_material_expressions(mat)
    wm.write_json("build_kit_result.json", {"expressions": count, "dirty_after": after,
                                            "assets": [MASTER, MI_WOOD, MI_STEEL]})
    unreal.log(f"PUSS_WING_KIT_MASTER_BUILD_SUCCESS|expressions={count}|dirty={len(after)}")


if not globals().get("WM_IMPORT_ONLY"):
    main()
