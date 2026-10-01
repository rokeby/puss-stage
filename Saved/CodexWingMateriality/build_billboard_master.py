"""Build the Flat V3 billboard master, its Front/Flap MIs, and placeholder textures.

Draft-only authoring script. It creates assets only under
/Game/Scenes/Wings/PaintedSurface/Billboard and never touches the Show or level.
Run generate_billboard_placeholders.py before running this inside Unreal.
"""
import importlib.util
import os

import unreal


here = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(here, "_wm_common.py"))
wm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wm)
bspec = importlib.util.spec_from_file_location(
    "wm_builder", os.path.join(here, "build_painted_surface_master.py")
)
B = importlib.util.module_from_spec(bspec)
B.WM_IMPORT_ONLY = True
bspec.loader.exec_module(B)
MEL = wm.MEL


BILLBOARD = "/Game/Scenes/Wings/PaintedSurface/Billboard"
MASTER = "/Game/Scenes/Wings/PaintedSurface/Billboard/M_Wing_Billboard_Master"
MI_FRONT = BILLBOARD + "/MI_Billboard_Front"
MI_FLAP = BILLBOARD + "/MI_Billboard_Flap"
TEXTURES = BILLBOARD + "/Textures"
PLACEHOLDER_SOURCE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
    "DerivedAssets",
    "WingMateriality",
    "BillboardPlaceholders",
)
PLACEHOLDERS = {
    "T_BB_Colour": {
        "file": "T_BB_Colour.png",
        "compression": unreal.TextureCompressionSettings.TC_DEFAULT,
        "srgb": True,
    },
    "T_BB_Mask": {
        "file": "T_BB_Mask.png",
        "compression": unreal.TextureCompressionSettings.TC_MASKS,
        "srgb": False,
    },
    "T_BB_Normal": {
        "file": "T_BB_Normal.png",
        "compression": unreal.TextureCompressionSettings.TC_NORMALMAP,
        "srgb": False,
    },
}
FLUTTER_MAX_CM = 6.0


CODE_SHEET = r"""
float row = floor(UV1.y / max(SheetHeightM, 1e-4));
float cell = floor((UV1.x + RowOffset * row * SheetWidthM) / max(SheetWidthM, 1e-4));
SheetHash = frac(sin(dot(float2(cell, row), float2(12.9898, 78.233))) * 43758.5453);
float xCell = (UV1.x + RowOffset * row * SheetWidthM) / max(SheetWidthM, 1e-4);
float yCell = UV1.y / max(SheetHeightM, 1e-4);
float xBorder = min(frac(xCell), 1.0 - frac(xCell)) * SheetWidthM;
float yBorder = min(frac(yCell), 1.0 - frac(yCell)) * SheetHeightM;
Seam = 1.0 - smoothstep(0.0, max(SheetOverlapM, 1e-4), min(xBorder, yBorder));
return UV0 + float2(SheetHash * 0.37, SheetHash * 0.61);
"""


CODE_UNDER = r"""
float oldLum = dot(Older, float3(0.2126, 0.7152, 0.0722));
float3 oldPoster = lerp(Older, oldLum.xxx, 0.5);
oldPoster = lerp(oldPoster, float3(1.0, 1.0, 1.0), 0.3);
if (SheetHash < PBacking)
    return BackingColor;
if (SheetHash < PBacking + POlder)
    return oldPoster;
return PrimerColor;
"""


# This is the painted master's CODE_PAINT burn block verbatim. It is the shared
# contract with Effects sources; keep both copies in lock-step.
CODE_BURN = r"""
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
    // Once the ISMs carry 4 floats the slots read 0, not the node defaults, so (0,0) means
    // "no ignition written": use bottom centre, where fire climbs from. Effects always
    // writes a real ignition when it burns; this only governs BurnPreview in the editor.
    float2 ign = (IgnU == 0.0 && IgnV == 0.0) ? float2(0.5, 1.0) : float2(IgnU, IgnV);
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


CODE_SURFACE = r"""
float peelT = smoothstep(PeelLo, PeelHi, PeelMask);
float3 c = lerp(Skin, Under, peelT);
// Darken a band around the peel threshold, measured in TEXTURE space. Screen-space
// derivatives (ddx/ddy) grow with distance and flicker per 2x2 quad under TSR (review fix).
float peelEdge = (1.0 - abs(2.0 * peelT - 1.0)) * saturate(PeelEdgeDark * 0.5);
c *= 1.0 - 0.35 * peelEdge;
c *= 1.0 - Seam * SeamDark;

float2 panelCm = UV1 * 100.0;
float pitchCm = max(HalftonePitchMm * 0.1, 1e-4);
float sn = 0.2588190451;
float cs = 0.9659258263;
float2 dotUv = float2(cs * panelCm.x - sn * panelCm.y,
                      sn * panelCm.x + cs * panelCm.y) / pitchCm;
float2 dotCell = frac(dotUv) - 0.5;
float skinLum = dot(Skin, float3(0.2126, 0.7152, 0.0722));
float dotRadius = lerp(0.42, 0.16, saturate(skinLum));
float dotAA = max(length(fwidth(dotUv)), 1e-4);
float dotInk = 1.0 - smoothstep(dotRadius - dotAA, dotRadius + dotAA, length(dotCell));
float fw = length(fwidth(panelCm)) / pitchCm;
float halftoneFade = 1.0 - smoothstep(0.25, 0.5, fw);
c *= 1.0 - dotInk * HalftoneStrength * halftoneFade;

// About 2 mm fibres, stretched 3:1 along panel X.
float2 fibreUv = float2(panelCm.x / 0.6, panelCm.y / 0.2);
float2 fibreBase = floor(fibreUv);
float2 fibreFrac = frac(fibreUv);
float2 fibreSmooth = fibreFrac * fibreFrac * (3.0 - 2.0 * fibreFrac);
float f00 = frac(sin(dot(fibreBase, float2(127.1, 311.7))) * 43758.5453);
float f10 = frac(sin(dot(fibreBase + float2(1, 0), float2(127.1, 311.7))) * 43758.5453);
float f01 = frac(sin(dot(fibreBase + float2(0, 1), float2(127.1, 311.7))) * 43758.5453);
float f11 = frac(sin(dot(fibreBase + float2(1, 1), float2(127.1, 311.7))) * 43758.5453);
float fibreValue = lerp(lerp(f00, f10, fibreSmooth.x), lerp(f01, f11, fibreSmooth.x), fibreSmooth.y);
float fibreFade = 1.0 - smoothstep(0.25, 0.5, length(fwidth(fibreUv)));
float fibreSigned = (fibreValue - 0.5) * 2.0 * fibreFade;
c *= 1.0 + fibreSigned * 0.03;

float tintPick = frac(Seed * 5.713 + 0.173);
c *= lerp(float3(1.0, 1.0, 1.0), lerp(TintCool, TintWarm, tintPick), TintVar);
float agePick = (frac(Seed * 13.719 + 0.5711) - 0.5) * 2.0 * FadeVar;
float variedLum = dot(c, float3(0.2126, 0.7152, 0.0722));
float3 faded = lerp(variedLum.xxx, float3(1.0, 1.0, 1.0), 0.25);
c = lerp(c, faded, agePick);

float rough = saturate(lerp(RoughMin, RoughMax, MaskRough) - PasteSoak * PasteGloss + fibreSigned * 0.05);
float3 baseN = normalize(lerp(float3(0, 0, 1), SkinN, NormalStrength));
// Analytic gradient of the value noise, per cm: stable at any distance (review fix; the
// ddx/ddy version varied with pixel footprint and flickered in motion).
float2 dS = 6.0 * fibreFrac * (1.0 - fibreFrac);
float dVdx = lerp(f10 - f00, f11 - f01, fibreSmooth.y) * dS.x / 0.6;
float dVdy = lerp(f01 - f00, f11 - f10, fibreSmooth.x) * dS.y / 0.2;
float fibreK = FibreNormal * 0.2 * fibreFade;
float3 fibreN = normalize(float3(-dVdx * fibreK, -dVdy * fibreK, 1.0));
OutNormal = normalize(float3(baseN.xy + fibreN.xy, baseN.z * fibreN.z));
float cc = 0.0;
float ccr = 0.0;
""" + CODE_BURN


CODE_FLUTTER = r"""
float phase = Seed * 6.28 + dot(LocalPos, float3(0.013, 0.021, 0.017));
float wave = sin(GameTime * FlutterHz * 6.28318530718 + phase);
float gust = 0.5 * (sin(GameTime * 0.13 * 6.28318530718 + Seed * 3.11)
                  + sin(GameTime * 0.31 * 6.28318530718 + Seed * 7.73));
float displacement = VertexWeight * FlutterAmpCm * (wave * 0.7 + gust * 0.3);
displacement = clamp(displacement, -FlutterMaxCm, FlutterMaxCm);
return float3(-displacement, 0.0, 0.0);
"""


def sampler_for(tex):
    """Match the texture's compression/sRGB settings, as the kit builder does."""
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


def import_placeholders():
    tasks = []
    for name, cfg in PLACEHOLDERS.items():
        filename = os.path.join(PLACEHOLDER_SOURCE, cfg["file"])
        wm.require(os.path.isfile(filename), f"missing placeholder {filename}")
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", filename)
        task.set_editor_property("destination_path", TEXTURES)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", False)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

    imported = {}
    for name, cfg in PLACEHOLDERS.items():
        path = f"{TEXTURES}/{name}"
        tex = B.load(path)
        wm.require(isinstance(tex, unreal.Texture2D), f"{path} did not import as Texture2D")
        tex.set_editor_property("srgb", cfg["srgb"])
        tex.set_editor_property("compression_settings", cfg["compression"])
        tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
        tex.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
        tex.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
        if name == "T_BB_Normal":
            tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
        wm.require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), f"save failed {path}")
        imported[name] = tex

    for name, tex in imported.items():
        cfg = PLACEHOLDERS[name]
        wm.require(bool(tex.get_editor_property("srgb")) == cfg["srgb"], f"{name}: sRGB read-back")
        wm.require(tex.get_editor_property("compression_settings") == cfg["compression"],
                   f"{name}: compression read-back")
        wm.require(tex.get_editor_property("mip_gen_settings") ==
                   unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP, f"{name}: mip read-back")
    return imported


def build_master(textures):
    mat = B.get_or_create(MASTER)
    g = B.Graph(mat)
    F1, F2, F3 = B.F1, B.F2, B.F3
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("use_material_attributes", True)
    mat.set_editor_property("tangent_space_normal", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    mat.set_editor_property("used_with_nanite", True)
    wpo_property = {"set": False, "error": None}
    try:
        mat.set_editor_property("max_world_position_offset_displacement", FLUTTER_MAX_CM)
        wpo_property["set"] = True
    except Exception as exc:
        wpo_property["error"] = str(exc)

    uv0 = g.node(unreal.MaterialExpressionTextureCoordinate, -3200, 0, coordinate_index=0)
    uv1 = g.node(unreal.MaterialExpressionTextureCoordinate, -3200, 120, coordinate_index=1)

    def texture_object(name, tex, y, priority):
        return g.node(
            unreal.MaterialExpressionTextureObjectParameter,
            -3200,
            y,
            parameter_name=name,
            texture=tex,
            sampler_type=sampler_for(tex),
            group="01 Skin",
            sort_priority=priority,
        )

    color_obj = texture_object("SkinColor", textures["T_BB_Colour"], 300, 0)
    mask_obj = texture_object("SkinMask", textures["T_BB_Mask"], 440, 1)
    normal_obj = texture_object("SkinNormal", textures["T_BB_Normal"], 580, 2)

    def sample(tex_obj, tex, x, y, uv_source, uv_output=""):
        node = g.node(
            unreal.MaterialExpressionTextureSample,
            x,
            y,
            sampler_type=sampler_for(tex),
            sampler_source=B.SHARED,
        )
        g.link(tex_obj, "", node, "Tex")
        g.link(uv_source, uv_output, node, "UVs")
        return node

    skin = sample(color_obj, textures["T_BB_Colour"], -2300, 0, uv0)
    mask = sample(mask_obj, textures["T_BB_Mask"], -2300, 250, uv0)
    normal = sample(normal_obj, textures["T_BB_Normal"], -2300, 500, uv0)

    sheet_params = {
        "SheetWidthM": g.scalar("SheetWidthM", 1.0, "02 Sheets", -3000, 800, 0),
        "SheetHeightM": g.scalar("SheetHeightM", 1.5, "02 Sheets", -3000, 900, 1),
        "SheetOverlapM": g.scalar("SheetOverlapM", 0.025, "02 Sheets", -3000, 1000, 2),
        "RowOffset": g.scalar("RowOffset", 0.5, "02 Sheets", -3000, 1100, 3),
    }
    sheet = g.custom(
        -2700,
        750,
        "UV1 sheet cells, hash, seams, and older-poster UV",
        CODE_SHEET,
        ["UV0", "UV1", "SheetWidthM", "SheetHeightM", "SheetOverlapM", "RowOffset"],
        F2,
        [("SheetHash", F1), ("Seam", F1)],
    )
    g.link(uv0, "", sheet, "UV0")
    g.link(uv1, "", sheet, "UV1")
    for name, node in sheet_params.items():
        g.link(node, "", sheet, name)
    older = sample(color_obj, textures["T_BB_Colour"], -2300, 750, sheet)

    under = g.custom(
        -1800,
        700,
        "Per-sheet backing, older poster, or primer",
        CODE_UNDER,
        ["Older", "SheetHash", "PBacking", "POlder", "BackingColor", "PrimerColor"],
        F3,
    )
    under_params = {
        "PBacking": g.scalar("PBacking", 0.45, "02 Sheets", -2200, 1000, 4),
        "POlder": g.scalar("POlder", 0.35, "02 Sheets", -2200, 1100, 5),
        "BackingColor": g.vector("BackingColor", (0.80, 0.78, 0.72), "02 Sheets", -2200, 1200, 6),
        "PrimerColor": g.vector("PrimerColor", (0.42, 0.42, 0.40), "02 Sheets", -2200, 1300, 7),
    }
    g.link(older, "RGB", under, "Older")
    g.link(sheet, "SheetHash", under, "SheetHash")
    for name, node in under_params.items():
        g.link(node, "", under, name)

    rand = g.node(unreal.MaterialExpressionPerInstanceRandom, -3000, 1400)
    cd = [
        g.node(
            unreal.MaterialExpressionPerInstanceCustomData,
            -3000,
            1550 + i * 110,
            data_index=i,
            const_default_value=default,
        )
        for i, default in enumerate((0.0, 0.5, 1.0, -1.0))
    ]
    seed = g.custom(
        -2700,
        1400,
        "Seed: custom data [3] if written, else PerInstanceRandom",
        "return CD3 >= 0.0 ? frac(CD3) : PIR;",
        ["CD3", "PIR"],
        F1,
    )
    g.link(cd[3], "", seed, "CD3")
    g.link(rand, "", seed, "PIR")

    burn_sample = g.node(
        unreal.MaterialExpressionTextureSampleParameter2D,
        -2200,
        1800,
        parameter_name="BurnMask",
        texture=B.load(B.TEX + "/T_WingDetail_Grime"),
        sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE,
        group="07 Burn",
        sort_priority=1,
        sampler_source=B.SHARED,
    )
    g.link(uv0, "", burn_sample, "UVs")
    burn_switch = g.node(
        unreal.MaterialExpressionStaticSwitchParameter,
        -1900,
        1800,
        parameter_name="UseBurn",
        default_value=False,
        group="07 Burn",
        sort_priority=0,
    )
    g.link(burn_sample, "R", burn_switch, "True")
    g.link(g.const(-1.0, -2100, 1950), "", burn_switch, "False")

    params = {
        "PeelLo": g.scalar("PeelLo", 0.35, "03 Peel", -1700, 1100, 0),
        "PeelHi": g.scalar("PeelHi", 0.65, "03 Peel", -1700, 1200, 1),
        "PeelEdgeDark": g.scalar("PeelEdgeDark", 2.0, "03 Peel", -1700, 1300, 2),
        "SeamDark": g.scalar("SeamDark", 0.12, "02 Sheets", -1700, 1400, 8),
        "HalftonePitchMm": g.scalar("HalftonePitchMm", 4.5, "04 Print & Fibre", -1700, 1500, 0),
        "HalftoneStrength": g.scalar("HalftoneStrength", 0.12, "04 Print & Fibre", -1700, 1600, 1),
        "RoughMin": g.scalar("RoughMin", 0.40, "05 Surface", -1700, 1700, 0),
        "RoughMax": g.scalar("RoughMax", 0.55, "05 Surface", -1700, 1800, 1),
        "PasteGloss": g.scalar("PasteGloss", 0.15, "05 Surface", -1700, 1900, 2),
        "NormalStrength": g.scalar("NormalStrength", 1.0, "05 Surface", -1700, 2000, 3),
        "FibreNormal": g.scalar("FibreNormal", 0.15, "04 Print & Fibre", -1700, 2100, 2),
        "TintVar": g.scalar("TintVar", 0.04, "06 Variation", -1700, 2200, 0),
        "TintWarm": g.vector("TintWarm", (1.04, 0.99, 0.95), "06 Variation", -1700, 2300, 1),
        "TintCool": g.vector("TintCool", (0.96, 1.00, 1.04), "06 Variation", -1700, 2400, 2),
        "FadeVar": g.scalar("FadeVar", 0.06, "06 Variation", -1700, 2500, 3),
        "BurnPreview": g.scalar("BurnPreview", 0.0, "07 Burn", -1700, 2700, 2),
        "BurnEdgeCm": g.scalar("BurnEdgeCm", 40.0, "07 Burn", -1700, 2800, 3),
        "IrregularityCm": g.scalar("BurnIrregularityCm", 160.0, "07 Burn", -1700, 2900, 8),
        "ScorchTint": g.vector("ScorchTint", (0.55, 0.36, 0.2), "07 Burn", -1700, 3000, 9),
        "CharColor": g.vector("CharColor", (0.018, 0.014, 0.012), "07 Burn", -1700, 3100, 4),
        "EmberColor": g.vector("EmberColor", (1.0, 0.32, 0.06), "07 Burn", -1700, 3200, 5),
        "EmberIntensity": g.scalar("EmberIntensity", 12.0, "07 Burn", -1700, 3300, 6),
        "UVSpanUCm": g.scalar("UVSpanUCm", 1000.0, "08 Panel", -1700, 3400, 0),
        "UVSpanVCm": g.scalar("UVSpanVCm", 1500.0, "08 Panel", -1700, 3500, 1),
    }
    surface_inputs = [
        "Skin", "Under", "PeelMask", "MaskRough", "PasteSoak", "SkinN", "UV", "UV1", "Seam", "Seed",
        "PeelLo", "PeelHi",
        "PeelEdgeDark", "SeamDark", "HalftonePitchMm", "HalftoneStrength", "RoughMin", "RoughMax",
        "PasteGloss", "NormalStrength", "FibreNormal", "TintVar", "TintWarm", "TintCool", "FadeVar",
        "BurnM", "BurnPreview", "BurnProgressCD", "IgnU", "IgnV", "UVSpanUCm", "UVSpanVCm",
        "IrregularityCm", "BurnEdgeCm", "ScorchTint", "CharColor", "EmberColor", "EmberIntensity",
    ]
    surface = g.custom(
        -1100,
        700,
        "Billboard skin, procedural print/fibre, variation, and burn",
        CODE_SURFACE,
        surface_inputs,
        F3,
        [
            ("OutRoughness", F1),
            ("OutNormal", F3),
            ("OutClearCoat", F1),
            ("OutClearCoatRoughness", F1),
            ("OutEmissive", F3),
            ("OutOpacity", F1),
        ],
    )
    wires = {
        "Skin": (skin, "RGB"),
        "Under": (under, ""),
        "PeelMask": (mask, "R"),
        "MaskRough": (mask, "B"),
        "PasteSoak": (mask, "A"),
        "SkinN": (normal, "RGB"),
        "UV": (uv0, ""),
        "UV1": (uv1, ""),
        "Seam": (sheet, "Seam"),
        "Seed": (seed, ""),
        "BurnM": (burn_switch, ""),
        "BurnProgressCD": (cd[0], ""),
        "IgnU": (cd[1], ""),
        "IgnV": (cd[2], ""),
    }
    wires.update({name: (node, "") for name, node in params.items()})
    for pin in surface_inputs:
        source, output = wires[pin]
        g.link(source, output, surface, pin)

    attribute_inputs = (
        (surface, "", "BaseColor"),
        (surface, "OutRoughness", "Roughness"),
        (surface, "OutNormal", "Normal"),
        (surface, "OutEmissive", "EmissiveColor"),
        (surface, "OutOpacity", "OpacityMask"),
        (g.scalar("Specular", 0.3, "05 Surface", -600, 1200, 4), "", "Specular"),
    )
    front_attrs = g.node(unreal.MaterialExpressionMakeMaterialAttributes, -300, 700)
    for source, output, pin in attribute_inputs:
        g.link(source, output, front_attrs, pin)

    world_pos = g.node(
        unreal.MaterialExpressionWorldPosition,
        -1100,
        3800,
        world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS,
    )
    local_pos = g.node(
        unreal.MaterialExpressionTransformPosition,
        -900,
        3800,
        transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
        transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL,
    )
    g.link(world_pos, "", local_pos, "")
    vertex_color = g.node(unreal.MaterialExpressionVertexColor, -1100, 4000)
    game_time = g.node(unreal.MaterialExpressionTime, -1100, 4150)
    flutter_params = {
        "FlutterAmpCm": g.scalar("FlutterAmpCm", 3.0, "09 Flutter", -1100, 4300, 0),
        "FlutterHz": g.scalar("FlutterHz", 0.7, "09 Flutter", -1100, 4400, 1),
        "FlutterMaxCm": g.scalar("FlutterMaxCm", FLUTTER_MAX_CM, "09 Flutter", -1100, 4500, 2),
    }
    flutter = g.custom(
        -650,
        3850,
        "Flap VC.R displacement along local -X",
        CODE_FLUTTER,
        ["LocalPos", "VertexWeight", "GameTime", "Seed", "FlutterAmpCm", "FlutterHz", "FlutterMaxCm"],
        F3,
    )
    for source, output, pin in (
        (local_pos, "", "LocalPos"),
        (vertex_color, "R", "VertexWeight"),
        (game_time, "", "GameTime"),
        (seed, "", "Seed"),
    ):
        g.link(source, output, flutter, pin)
    for name, node in flutter_params.items():
        g.link(node, "", flutter, name)
    flutter_world = g.node(
        unreal.MaterialExpressionTransform,
        -400,
        3850,
        transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
        transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD,
    )
    g.link(flutter, "", flutter_world, "")
    flap_attrs = g.node(unreal.MaterialExpressionMakeMaterialAttributes, -50, 1500)
    for source, output, pin in attribute_inputs:
        g.link(source, output, flap_attrs, pin)
    g.link(flutter_world, "", flap_attrs, "WorldPositionOffset")
    flutter_switch = g.node(
        unreal.MaterialExpressionStaticSwitchParameter,
        250,
        1050,
        parameter_name="Flutter",
        default_value=False,
        group="09 Flutter",
        sort_priority=0,
    )
    g.link(flap_attrs, "", flutter_switch, "True")
    # front_attrs has no WorldPositionOffset connection at all.
    g.link(front_attrs, "", flutter_switch, "False")
    g.prop(flutter_switch, "", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
    return mat, wpo_property


def make_mi(path, flutter, two_sided, textures):
    folder, name = path.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mi = B.load(path)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()
        )
    MEL.set_material_instance_parent(mi, B.load(MASTER))
    MEL.set_material_instance_static_switch_parameter_value(mi, "Flutter", flutter)
    wm.require(MEL.get_material_instance_static_switch_parameter_value(mi, "Flutter") == flutter,
               f"{name}: Flutter read-back")
    for parameter, tex_name in (
        ("SkinColor", "T_BB_Colour"),
        ("SkinMask", "T_BB_Mask"),
        ("SkinNormal", "T_BB_Normal"),
    ):
        # The setter can report False even when it succeeds in UE 5.8; read back instead.
        MEL.set_material_instance_texture_parameter_value(mi, parameter, textures[tex_name])
        actual = wm.pkg(MEL.get_material_instance_texture_parameter_value(mi, parameter))
        expected = wm.pkg(textures[tex_name])
        wm.require(actual == expected, f"{name}: {parameter} read-back {actual}, expected {expected}")
    overrides = mi.get_editor_property("base_property_overrides")
    overrides.set_editor_property("override_two_sided", two_sided)
    overrides.set_editor_property("two_sided", two_sided)
    mi.set_editor_property("base_property_overrides", overrides)
    readback = mi.get_editor_property("base_property_overrides")
    wm.require(bool(readback.get_editor_property("override_two_sided")) == two_sided,
               f"{name}: override_two_sided read-back")
    if two_sided:
        wm.require(bool(readback.get_editor_property("two_sided")), f"{name}: two_sided read-back")
    MEL.update_material_instance(mi)
    return mi


def main():
    wm.editor_ready()
    texture_paths = {f"{TEXTURES}/{name}" for name in PLACEHOLDERS}
    mine = {MASTER, MI_FRONT, MI_FLAP} | texture_paths
    before = wm.dirty()
    before_others = set(before) - mine
    textures = import_placeholders()
    mat, wpo_property = build_master(textures)
    MEL.layout_material_expressions(mat)
    MEL.recompile_material(mat)
    wm.require(bool(mat.get_editor_property("used_with_instanced_static_meshes")) and
               bool(mat.get_editor_property("used_with_nanite")), "usage flags not set")
    wm.require(mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_OPAQUE,
               "master is not opaque")
    wm.require(unreal.EditorAssetLibrary.save_asset(MASTER, only_if_is_dirty=False), "save master failed")
    for path, flutter, two_sided in (
        (MI_FRONT, False, False),
        (MI_FLAP, True, True),
    ):
        make_mi(path, flutter, two_sided, textures)
        wm.require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), f"save {path} failed")
    after = wm.dirty()
    wm.require(set(after) <= before_others,
               f"Build left new dirty packages: {sorted(set(after) - before_others)}")
    count = MEL.get_num_material_expressions(mat)
    wm.write_json(
        "build_billboard_result.json",
        {
            "assets": [MASTER, MI_FRONT, MI_FLAP] + sorted(texture_paths),
            "dirty_after": after,
            "expressions": count,
            "max_wpo_property": wpo_property,
        },
    )
    unreal.log(
        f"PUSS_WING_BILLBOARD_MASTER_BUILD_SUCCESS|expressions={count}|"
        f"max_wpo_set={wpo_property['set']}|dirty={len(after)}"
    )


if not globals().get("WM_IMPORT_ONLY"):
    main()
