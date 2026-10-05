"""Red velvet v2: CREATE-ONLY builder for a new curtain master + one instance (NOT RUN; written 5 Oct 2026).

Why: Gary, 5 Oct - the curtain fabric "looks like a basic blender render still". The decided colour (plain oxblood B,
Docs/ChaosClothCurtain.md "Velvet") stays; what changes is how the cloth answers light.

Creates, under /Game/Scenes/Curtain/Chaos/Materials (the folder of M_CurtainVelvet), NEW assets only:
  M_CurtainVelvet_v2               master, Cloth shading model, two-sided, material attributes
  MI_CurtainVelvet_v2_DeepRed      instance; BaseColour/SheenColour = plain oxblood B; PatternWidthM/DropM copied
                                   (read-only) from /Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop
Nothing existing is edited: M_CurtainVelvet, MI_CurtainVelvet_DeepRed(_Drop) and every texture are only LOADED.
Swapping the curtain to v2 is a separate, later step, after Gary picks from bench stills.

Graph (every output goes through ONE MakeMaterialAttributes -> MP_MATERIAL_ATTRIBUTES):
  UV0 x (PatternWidthM, DropM)              = flat-fabric metres (same mapping as M_CurtainVelvet)
  PileNormal  (T_CurtainVelourScan_N)        tiled every PileScale m, strength PileNormalStrength
  CrushNormal (T_CurtainVelvetCrush_N)       tiled every CrushScale m, strength CrushNormalStrength
  VV2_Crush   procedural 4-octave value noise on metres / CrushScale (no texture, no lattice)
  Fresnel(ExponentIn = NapExponent)          face-on vs grazing (no curvature; the GeometryCache has no AO/colours)
  VV2_Base    BaseColour, crush on value+saturation, face-on darken (FoldDarken), grazing rim lift (RimLift)
  VV2_Fuzz    SheenColour, crush-modulated          -> SubsurfaceColor  (= Fuzz Color in the Cloth model)
  VV2_Cloth   SheenAmount, crush-modulated          -> ClearCoat pin of MakeMaterialAttributes (= CustomData0 = Cloth)
  VV2_Rough   Roughness, crush-modulated            -> Roughness
  Specular                                          -> Specular
  VV2_Normal  whiteout blend of the two normals     -> Normal

Traps honoured (memory ue58-python-material-authoring, puss-python-api-gotchas, puss-mcp-python-crashes-the-editor):
  * create-only: REFUSES if either target exists; never removes an expression from any material (no delete call);
  * no ClearCoat MATERIAL PROPERTY: MaterialProperty has no MP_CUSTOM_DATA0; the Cloth amount reaches CustomData0 only
    through MakeMaterialAttributes' ClearCoat pin, the route M_CurtainVelvet was built with
    (Scripts/build_curtain_chaos_asset.py:316-324; Docs/ChaosClothCurtain.md "Engine traps" 4);
  * every connect is asserted, then every edge is re-read through MaterialEditingLibrary read APIs;
  * MI setters may return False after success: the gate is the read-back, never the bool;
  * sampler types come from each texture's own compression/sRGB (LINEAR_GRAYSCALE for linear grayscale);
    both textures must be TC_NORMALMAP or the run refuses;
  * one source never feeds two pins of the same node (keeps output-name read-back unambiguous);
  * saves ONLY the two new packages, never Save All; dirty-scope gate before and after;
  * all unreal work inside main(); nothing UE-owned at module level.

Mode file Saved/CodexConductor/velvet_v2_build_mode.json {"mode": "DRY"|"APPLY"|"VERIFY"} (missing = DRY).
  DRY     loads inputs, checks targets are free and texture types, mutates nothing.
  APPLY   builds, verifies, saves the two packages, re-reads them.
  VERIFY  read-only: re-reads saved assets (parameters, flags, edges, shader statistics).
Markers (run id on every line): VV2_DRY_OK | VV2_OK | VV2_VERIFY_OK | VV2_FAILED | VV2_COMPILE_CHECK.
Report: Saved/CodexConductor/velvet_v2_build_<run>.json
"""
import datetime
import json
import os

FOLDER = "/Game/Scenes/Curtain/Chaos/Materials"
M_V2 = FOLDER + "/M_CurtainVelvet_v2"
MI_V2 = FOLDER + "/MI_CurtainVelvet_v2_DeepRed"
TARGETS = [M_V2, MI_V2]
DROP_MI = "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"   # read-only source of PatternWidthM/DropM
TEX = {
    "PileNormal": "/Game/Scenes/Curtain/Chaos/Textures/T_CurtainVelourScan_N",
    "CrushNormal": "/Game/Scenes/Curtain/Chaos/Textures/T_CurtainVelvetCrush_N",
}

# name: (default, group). PatternWidthM / DropM defaults are replaced at run time by the Drop MI's values.
SCALARS = {
    "SheenAmount": (1.0, "02 Sheen"),
    "RimLift": (0.35, "02 Sheen"),
    "NapExponent": (3.0, "02 Sheen"),
    "FoldDarken": (0.55, "02 Sheen"),
    "Roughness": (0.88, "01 Colour"),
    "Specular": (0.3, "01 Colour"),
    "PileNormalStrength": (0.6, "03 Pile"),
    "PileScale": (0.5, "03 Pile"),
    "CrushAmount": (0.35, "04 Crush"),
    "CrushScale": (0.6, "04 Crush"),
    "CrushNormalStrength": (0.25, "04 Crush"),
    "PatternWidthM": (37.629, "05 Mapping"),
    "DropM": (10.0, "05 Mapping"),
}
# Plain oxblood B (Docs/ChaosClothCurtain.md "Velvet": VelvetColor 0.07/0.004/0.012, SheenColor 0.32/0.03/0.07).
VECTORS = {
    "BaseColour": ((0.07, 0.004, 0.012), "01 Colour"),
    "SheenColour": ((0.32, 0.03, 0.07), "02 Sheen"),
}
MI_COPY_FROM_DROP = ("PatternWidthM", "DropM")
MI_VECTORS = {k: v[0] for k, v in VECTORS.items()}

# ---------------------------------------------------------------- HLSL (Custom nodes; inputs are the names listed)
CODE_CRUSH = """// Crushed-velvet mottle: 4-octave value noise on flat-fabric metres / CrushScale. Rotated octaves, no lattice.
float2 p = P;
float acc = 0.0;
float amp = 0.5;
float norm = 0.0;
for (int k = 0; k < 4; k++)
{
    float2 c0 = floor(p);
    float2 f = frac(p);
    float2 u = f * f * (3.0 - 2.0 * f);
    float h00 = frac(sin(dot(c0, float2(127.1, 311.7))) * 43758.5453);
    float h10 = frac(sin(dot(c0 + float2(1.0, 0.0), float2(127.1, 311.7))) * 43758.5453);
    float h01 = frac(sin(dot(c0 + float2(0.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
    float h11 = frac(sin(dot(c0 + float2(1.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
    acc += amp * lerp(lerp(h00, h10, u.x), lerp(h01, h11, u.x), u.y);
    norm += amp;
    amp *= 0.5;
    p = float2(1.6 * p.x + 1.2 * p.y, -1.2 * p.x + 1.6 * p.y) + 17.0;
}
return acc / norm;
"""

CODE_BASE = """// Albedo: crush on value and saturation, face-on darken (nap), grazing rim toward the sheen colour.
float c = (Crush - 0.5) * 2.0 * CrushAmt;
float3 col = Base * max(1.0 + 0.45 * c, 0.0);
float l = dot(col, float3(0.2126, 0.7152, 0.0722));
col = max(lerp(float3(l, l, l), col, 1.0 + 0.35 * c), 0.0);
col *= lerp(FoldDarken, 1.0, Fres);
return lerp(col, Sheen, saturate(Fres * RimLift));
"""

CODE_FUZZ = """// Fuzz colour: the pile sheen, stronger where the crush lifts the nap.
float c = (Crush - 0.5) * 2.0 * CrushAmt;
return Sheen * saturate(1.0 + 0.6 * c);
"""

CODE_CLOTH = """// Cloth amount (CustomData0): how much of the sheen lobe is used.
float c = (Crush - 0.5) * 2.0 * CrushAmt;
return saturate(SheenAmt * (1.0 + 0.3 * c));
"""

CODE_ROUGH = """// Roughness, slightly lower where the nap is crushed flat.
float c = (Crush - 0.5) * 2.0 * CrushAmt;
return clamp(Rough - 0.04 * c, 0.0, 1.0);
"""

CODE_NORMAL = """// Whiteout blend of the pile and crush normals, each eased from flat by its strength.
float3 a = lerp(float3(0.0, 0.0, 1.0), PileN, PileStr);
float3 b = lerp(float3(0.0, 0.0, 1.0), CrushN, CrushStr);
return normalize(float3(a.xy + b.xy, a.z * b.z));
"""

# (description, code, inputs, output type key)
CUSTOM = {
    "VV2_Crush": (CODE_CRUSH, ["P"], "F1"),
    "VV2_Base": (CODE_BASE, ["Base", "Sheen", "Crush", "CrushAmt", "Fres", "FoldDarken", "RimLift"], "F3"),
    "VV2_Fuzz": (CODE_FUZZ, ["Sheen", "Crush", "CrushAmt"], "F3"),
    "VV2_Cloth": (CODE_CLOTH, ["SheenAmt", "Crush", "CrushAmt"], "F1"),
    "VV2_Rough": (CODE_ROUGH, ["Rough", "Crush", "CrushAmt"], "F1"),
    "VV2_Normal": (CODE_NORMAL, ["PileN", "PileStr", "CrushN", "CrushStr"], "F3"),
}

# Edges by logical node key: (source, source output, target, target pin). The builder wires exactly these.
EDGES = [
    ("UV0", "", "UVMetres", "A"),
    ("PatternWidthM", "", "SizeM", "A"),
    ("DropM", "", "SizeM", "B"),
    ("SizeM", "", "UVMetres", "B"),
    ("UVMetres", "", "PileUV", "A"),
    ("PileScale", "", "PileUV", "B"),
    ("UVMetres", "", "CrushUV", "A"),
    ("CrushScale", "", "CrushUV", "B"),
    ("PileUV", "", "PileNormal", "UVs"),
    ("CrushUV", "", "CrushNormal", "UVs"),
    ("CrushUV", "", "VV2_Crush", "P"),
    ("NapExponent", "", "Fresnel", "ExponentIn"),
    ("BaseColour", "", "VV2_Base", "Base"),
    ("SheenColour", "", "VV2_Base", "Sheen"),
    ("VV2_Crush", "", "VV2_Base", "Crush"),
    ("CrushAmount", "", "VV2_Base", "CrushAmt"),
    ("Fresnel", "", "VV2_Base", "Fres"),
    ("FoldDarken", "", "VV2_Base", "FoldDarken"),
    ("RimLift", "", "VV2_Base", "RimLift"),
    ("SheenColour", "", "VV2_Fuzz", "Sheen"),
    ("VV2_Crush", "", "VV2_Fuzz", "Crush"),
    ("CrushAmount", "", "VV2_Fuzz", "CrushAmt"),
    ("SheenAmount", "", "VV2_Cloth", "SheenAmt"),
    ("VV2_Crush", "", "VV2_Cloth", "Crush"),
    ("CrushAmount", "", "VV2_Cloth", "CrushAmt"),
    ("Roughness", "", "VV2_Rough", "Rough"),
    ("VV2_Crush", "", "VV2_Rough", "Crush"),
    ("CrushAmount", "", "VV2_Rough", "CrushAmt"),
    ("PileNormal", "RGB", "VV2_Normal", "PileN"),
    ("PileNormalStrength", "", "VV2_Normal", "PileStr"),
    ("CrushNormal", "RGB", "VV2_Normal", "CrushN"),
    ("CrushNormalStrength", "", "VV2_Normal", "CrushStr"),
    ("VV2_Base", "", "Attrs", "BaseColor"),
    ("VV2_Fuzz", "", "Attrs", "SubsurfaceColor"),
    ("VV2_Cloth", "", "Attrs", "ClearCoat"),
    ("VV2_Rough", "", "Attrs", "Roughness"),
    ("Specular", "", "Attrs", "Specular"),
    ("VV2_Normal", "", "Attrs", "Normal"),
]


def main():
    import unreal  # inside main: nothing UE-owned survives the call

    mel = unreal.MaterialEditingLibrary
    eal = unreal.EditorAssetLibrary
    run = "VV2-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    mode_path = os.path.join(here, "velvet_v2_build_mode.json")
    mode = "DRY"
    if os.path.exists(mode_path):
        with open(mode_path, encoding="utf-8") as handle:
            mode = str(json.load(handle).get("mode", "DRY"))
    report_path = os.path.join(here, f"velvet_v2_build_{run}.json")
    report = {"run": run, "mode": mode, "targets": TARGETS, "textures": {}, "status": "STARTED"}

    class Stop(Exception):
        pass

    def write_report():
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, sort_keys=True)

    def fail(msg):
        report["status"] = "FAILED"
        report["error"] = msg
        write_report()
        unreal.log_error(f"VV2_FAILED|run={run}|{msg}")
        raise Stop(msg)

    def pk(p):
        s = str(p)
        return s.split("'")[1].split(".")[0] if "'" in s else s.split(".")[0]

    def dirty():
        return (sorted(pk(p.get_path_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
                sorted(pk(p.get_path_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))

    def out_name(value):
        # A bool UFUNCTION with one out-param returns only the out value in Python (puss-python-api-gotchas);
        # accept a (bool, str) tuple too, in case this binding differs.
        if isinstance(value, tuple):
            value = value[-1]
        return "" if value is None else str(value)

    def sampler_for(tex):
        comp = str(tex.get_editor_property("compression_settings"))
        srgb = bool(tex.get_editor_property("srgb"))
        st = unreal.MaterialSamplerType
        if "NORMALMAP" in comp:
            return st.SAMPLERTYPE_NORMAL
        if "GRAYSCALE" in comp:
            return st.SAMPLERTYPE_GRAYSCALE if srgb else st.SAMPLERTYPE_LINEAR_GRAYSCALE
        if "MASKS" in comp:
            return st.SAMPLERTYPE_MASKS
        if "ALPHA" in comp:
            return st.SAMPLERTYPE_ALPHA
        return st.SAMPLERTYPE_COLOR if srgb else st.SAMPLERTYPE_LINEAR_COLOR

    try:
        # ------------------------------------------------------------ guards (shared by every mode)
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if ed.get_game_world() is not None:
            fail("PIE active")
        content0, maps0 = dirty()
        report["dirty_at_start"] = {"content": content0, "maps": maps0}
        if mode in ("DRY", "APPLY") and content0:
            fail(f"dirty content packages at start (would blur the save scope): {content0}")

        textures = {}
        for key, path in TEX.items():
            tex = eal.load_asset(path)
            if tex is None or not isinstance(tex, unreal.Texture2D):
                fail(f"texture {key} {path} does not load as Texture2D")
            comp = str(tex.get_editor_property("compression_settings"))
            if "NORMALMAP" not in comp:
                fail(f"texture {key} {path} is {comp}, not TC_NORMALMAP; refusing (sampler/compile mismatch)")
            textures[key] = tex
            report["textures"][key] = {"path": path, "compression": comp, "srgb": bool(tex.get_editor_property("srgb")),
                                       "sampler": str(sampler_for(tex))}

        drop = eal.load_asset(DROP_MI)
        if drop is None:
            fail(f"could not load {DROP_MI}")
        mapping = {}
        for name in MI_COPY_FROM_DROP:
            value = float(mel.get_material_instance_scalar_parameter_value(drop, name))
            if not (value > 0.0):
                fail(f"{DROP_MI}.{name} read {value}; expected a positive length")
            mapping[name] = value
        report["mapping_from_drop_mi"] = mapping
        scalars = {k: (mapping.get(k, v[0]), v[1]) for k, v in SCALARS.items()}

        def check_param_readback(material, label):
            """Parameter names (exact sets) and defaults on the master, through MEL read APIs."""
            got_s = sorted(str(n) for n in mel.get_scalar_parameter_names(material))
            got_v = sorted(str(n) for n in mel.get_vector_parameter_names(material))
            got_t = sorted(str(n) for n in mel.get_texture_parameter_names(material))
            if got_s != sorted(scalars) or got_v != sorted(VECTORS) or got_t != sorted(TEX):
                fail(f"{label} parameter names: scalars={got_s} vectors={got_v} textures={got_t}")
            for name, (value, _) in scalars.items():
                got = float(mel.get_material_default_scalar_parameter_value(material, name))
                if abs(got - float(value)) > 1e-4:
                    fail(f"{label} default {name} read-back {got} != {value}")
            for name, (rgb, _) in VECTORS.items():
                got = mel.get_material_default_vector_parameter_value(material, name)
                if any(abs(a - b) > 1e-4 for a, b in zip((got.r, got.g, got.b), rgb)):
                    fail(f"{label} default {name} read-back {got} != {rgb}")
            for name, path in TEX.items():
                got = mel.get_material_default_texture_parameter_value(material, name)
                if got is None or pk(got.get_path_name()) != path:
                    fail(f"{label} default texture {name} read-back {got} != {path}")
            return {"scalars": len(got_s), "vectors": len(got_v), "textures": len(got_t)}

        def check_mi_readback(mi, master_path, label):
            par = mi.get_editor_property("parent")
            if par is None or pk(par.get_path_name()) != master_path:
                fail(f"{label} parent read-back {par}")
            for name, (value, _) in scalars.items():
                got = float(mel.get_material_instance_scalar_parameter_value(mi, name))
                if abs(got - float(value)) > 1e-4:
                    fail(f"{label}.{name} read-back {got} != {value}")
            for name, rgb in MI_VECTORS.items():
                got = mel.get_material_instance_vector_parameter_value(mi, name)
                if any(abs(a - b) > 1e-4 for a, b in zip((got.r, got.g, got.b), rgb)):
                    fail(f"{label}.{name} read-back {got} != {rgb}")
            for name, path in TEX.items():
                got = mel.get_material_instance_texture_parameter_value(mi, name)
                if got is None or pk(got.get_path_name()) != path:
                    fail(f"{label} texture {name} read-back {got} != {path}")
            # The master defaults equal these values, so a value read-back alone cannot see a setter that silently
            # did nothing (the MI would inherit the same number). The override flag can.
            missing = [n for n in list(MI_COPY_FROM_DROP) + list(MI_VECTORS)
                       if not mel.is_material_instance_parameter_overridden(mi, n)]
            if missing:
                fail(f"{label} parameters not overridden on the instance: {missing}")

        flags = {
            "shading_model": unreal.MaterialShadingModel.MSM_CLOTH,
            "two_sided": True,
            "use_material_attributes": True,
            "used_with_geometry_cache": True,
            "used_with_skeletal_mesh": True,
            "used_with_clothing": True,
        }

        def check_flags(material, label):
            for key, value in flags.items():
                if str(material.get_editor_property(key)) != str(value):
                    fail(f"{label}.{key} read-back {material.get_editor_property(key)} != {value}")

        # ------------------------------------------------------------ VERIFY (read-only)
        if mode == "VERIFY":
            for path in TARGETS:
                if not eal.does_asset_exist(path):
                    fail(f"VERIFY: {path} does not exist")
            master = eal.load_asset(M_V2)
            mi = eal.load_asset(MI_V2)
            check_flags(master, "M_CurtainVelvet_v2")
            report["params"] = check_param_readback(master, "M_CurtainVelvet_v2")
            check_mi_readback(mi, M_V2, "MI_CurtainVelvet_v2_DeepRed")
            term = mel.get_material_property_input_node(master, unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
            if term is None or "MakeMaterialAttributes" not in term.get_class().get_name():
                fail(f"VERIFY: MP_MATERIAL_ATTRIBUTES fed by {term}")
            n_expr = int(mel.get_num_material_expressions(master))
            report["expressions"] = n_expr
            stats = mel.get_statistics(master)
            ps = int(stats.get_editor_property("num_pixel_shader_instructions"))
            report["pixel_shader_instructions"] = ps
            if ps <= 0:
                fail(f"VERIFY: pixel shader instructions {ps} (not compiled, or compile failed)")
            if dirty() != (content0, maps0):
                fail(f"VERIFY dirtied packages: {dirty()}")
            report["status"] = "VERIFY_OK"
            write_report()
            unreal.log(f"VV2_VERIFY_OK|run={run}|expressions={n_expr}|ps_instructions={ps}|report={report_path}")
            return "verify"

        existing = [p for p in TARGETS if eal.does_asset_exist(p)]
        if existing:
            fail(f"targets already exist (create-only tool; never edits an existing material): {existing}")
        if dirty() != (content0, maps0):
            fail(f"loading inputs dirtied packages {dirty()}")
        if mode != "APPLY":
            report["status"] = "DRY_OK"
            write_report()
            unreal.log(f"VV2_DRY_OK|run={run}|textures={len(textures)}|targets_free={len(TARGETS)}|mapping={mapping}"
                       f"|mutated=0|report={report_path}")
            return "dry"

        # ------------------------------------------------------------ APPLY
        def new_asset(path, cls, factory):
            folder, name = path.rsplit("/", 1)
            if eal.does_asset_exist(path):
                fail(f"{path} appeared mid-run")
            asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)
            if asset is None or not isinstance(asset, cls):
                fail(f"create {path}")
            return asset

        master = new_asset(M_V2, unreal.Material, unreal.MaterialFactoryNew())
        for key, value in flags.items():
            master.modify()
            master.set_editor_property(key, value)
        check_flags(master, "M_CurtainVelvet_v2")

        nodes = {}
        edges = []
        out_types = {"F1": unreal.CustomMaterialOutputType.CMOT_FLOAT1,
                     "F3": unreal.CustomMaterialOutputType.CMOT_FLOAT3}

        def node(key, cls, x, y, **props):
            if key in nodes:
                fail(f"duplicate node key {key}")
            n = mel.create_material_expression(master, cls, x, y)
            if n is None:
                fail(f"create expression {key}")
            for prop, value in props.items():
                n.set_editor_property(prop, value)
            nodes[key] = n
            return n

        # parameters
        for i, (name, (value, group)) in enumerate(scalars.items()):
            node(name, unreal.MaterialExpressionScalarParameter, -2400, -400 + i * 90,
                 parameter_name=name, default_value=float(value), group=group)
        for i, (name, (rgb, group)) in enumerate(VECTORS.items()):
            node(name, unreal.MaterialExpressionVectorParameter, -2400, -700 - i * 160,
                 parameter_name=name, default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0), group=group)
        # mapping
        node("UV0", unreal.MaterialExpressionTextureCoordinate, -2100, 900, coordinate_index=0)
        node("SizeM", unreal.MaterialExpressionAppendVector, -2100, 1050)
        node("UVMetres", unreal.MaterialExpressionMultiply, -1900, 950)
        node("PileUV", unreal.MaterialExpressionDivide, -1700, 850)
        node("CrushUV", unreal.MaterialExpressionDivide, -1700, 1050)
        for i, (key, path) in enumerate(TEX.items()):
            tex = textures[key]
            node(key, unreal.MaterialExpressionTextureSampleParameter2D, -1450, 700 + i * 300,
                 parameter_name=key, texture=tex, sampler_type=sampler_for(tex), group="03 Pile" if i == 0 else "04 Crush")
        node("Fresnel", unreal.MaterialExpressionFresnel, -1450, -200)
        for i, (key, (code, inputs, otype)) in enumerate(CUSTOM.items()):
            n = node(key, unreal.MaterialExpressionCustom, -1000, -600 + i * 300,
                     description=key, code=code, output_type=out_types[otype])
            ins = []
            for name in inputs:
                ci = unreal.CustomInput()
                ci.set_editor_property("input_name", name)
                ins.append(ci)
            n.set_editor_property("inputs", ins)
            got = [str(c.get_editor_property("input_name")) for c in n.get_editor_property("inputs")]
            if got != list(inputs):
                fail(f"custom inputs read-back {key}: {got}")
        node("Attrs", unreal.MaterialExpressionMakeMaterialAttributes, -500, 0)

        # wiring (every connect asserted)
        for src, src_out, dst, pin in EDGES:
            a, b = nodes[src], nodes[dst]
            if not mel.connect_material_expressions(a, src_out, b, pin):
                fail(f"connect {src}.{src_out!r} -> {dst}.{pin!r}; inputs={[str(x) for x in mel.get_material_expression_input_names(b)]}")
            edges.append((src, src_out, dst, pin))
        if not mel.connect_material_property(nodes["Attrs"], "", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES):
            fail("connect Attrs -> MP_MATERIAL_ATTRIBUTES")

        # ------------------------------------------------------------ edge read-back (MEL read APIs)
        bad = []
        wired = {}
        for src, src_out, dst, pin in edges:
            wired.setdefault(dst, []).append((src, src_out, pin))
        for dst, rows in wired.items():
            target = nodes[dst]
            names = [str(x) for x in mel.get_material_expression_input_names(target)]
            ups = list(mel.get_inputs_for_material_expression(master, target))
            aligned = len(ups) == len(names)
            live = [u for u in ups if u is not None]
            if len(live) != len(rows):
                bad.append(f"{dst}: {len(live)} live inputs, wired {len(rows)}")
            for src, src_out, pin in rows:
                source = nodes[src]
                if pin not in names:
                    bad.append(f"{dst}.{pin} not an input ({names})")
                    continue
                if aligned:
                    up = ups[names.index(pin)]
                    if up is None or up.get_name() != source.get_name():
                        bad.append(f"{src}->{dst}.{pin} reads {None if up is None else up.get_name()}")
                elif source.get_name() not in [u.get_name() for u in live]:
                    bad.append(f"{src}->{dst}.{pin} missing (unaligned read)")
                if src_out:
                    got = out_name(mel.get_input_node_output_name_for_material_expression(target, source))
                    if got != src_out:
                        bad.append(f"{src}.{src_out}->{dst}.{pin} output reads {got!r}")
        term = mel.get_material_property_input_node(master, unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
        if term is None or term.get_name() != nodes["Attrs"].get_name():
            bad.append(f"MP_MATERIAL_ATTRIBUTES fed by {term}")
        if bad:
            fail(f"edge read-back: {bad}")
        n_expr = int(mel.get_num_material_expressions(master))
        if n_expr != len(nodes):
            fail(f"expression count {n_expr} != built {len(nodes)}")
        report["graph"] = {"nodes": len(nodes), "edges": len(edges), "terminal": "MP_MATERIAL_ATTRIBUTES"}

        errors = mel.recompile_material(master)
        errors = [str(e) for e in (errors or [])]
        report["recompile_errors"] = errors
        if errors:
            fail(f"recompile returned errors (nothing saved): {errors}")
        report["params"] = check_param_readback(master, "M_CurtainVelvet_v2")

        # ------------------------------------------------------------ MI (gate = read-back, not setter bools)
        mi = new_asset(MI_V2, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mi.modify()
        mel.set_material_instance_parent(mi, master)
        for name in MI_COPY_FROM_DROP:
            mi.modify()
            mel.set_material_instance_scalar_parameter_value(mi, name, float(mapping[name]))  # bool unreliable
        for name, rgb in MI_VECTORS.items():
            mi.modify()
            mel.set_material_instance_vector_parameter_value(mi, name, unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        mel.update_material_instance(mi)
        check_mi_readback(mi, M_V2, "MI_CurtainVelvet_v2_DeepRed")

        # ------------------------------------------------------------ save only the two new packages
        content1, maps1 = dirty()
        if maps1 != maps0 or not set(content1) <= set(TARGETS):
            fail(f"dirty scope before save: content={content1} maps={maps1} (maps at start {maps0}); nothing saved")
        for path in TARGETS:
            if not eal.save_asset(path, only_if_is_dirty=False):
                fail(f"save {path}")
        if dirty() != ([], maps0):
            fail(f"dirty after save {dirty()} (maps at start {maps0})")
        for path in TARGETS:
            if not eal.does_asset_exist(path):
                fail(f"{path} missing after save")
        master_back = eal.load_asset(M_V2)
        check_flags(master_back, "M_CurtainVelvet_v2 (saved)")
        check_param_readback(master_back, "M_CurtainVelvet_v2 (saved)")
        check_mi_readback(eal.load_asset(MI_V2), M_V2, "MI_CurtainVelvet_v2_DeepRed (saved)")
    except Stop:
        return "failed"
    except Exception as exc:  # noqa: BLE001
        try:
            fail(f"exception {exc!r} (any created assets are unsaved: Don't-Save restart, do NOT Save All)")
        except Stop:
            return "failed"
    report["status"] = "APPLIED"
    write_report()
    unreal.log(f"VV2_OK|run={run}|master=1|instances=1|nodes={report['graph']['nodes']}|edges={report['graph']['edges']}"
               f"|saved=2|maps_dirty_unchanged=1|report={report_path}")
    unreal.log(f"VV2_COMPILE_CHECK|run={run}|grep PussStage.log for 'Failed to compile' + 'M_CurtainVelvet_v2' in ~20 s,"
               f" then run mode VERIFY (pixel-shader instruction count > 0)")
    return "applied"


if os.environ.get("VV2_NO_AUTORUN") != "1":
    main()
