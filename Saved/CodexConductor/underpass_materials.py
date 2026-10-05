"""Underpass rig kit, Step 2: two NEW master materials + three MIs (NOT RUN; written 5 Oct 2026).

Blueprint: Docs/Conductor/UNDERPASS_RIG_KIT_PLAN_2026-10-05.md section 3 "Materials".

Creates, under /Game/InfinityStage/RigAtmos/Underpass/Materials, NEW assets only:
  M_UP_PaintedSteel   green paint, procedural rivet row in the UV0 rivet band (V 0-0.1),
                      black band below world Z (PassageFloorZ + BandHeightCm = 150),
                      paint chips revealing rust, rust streaks below the rivet band.
  M_UP_GrimyConcrete  poured concrete + grime overlay, wet/dark foot band.
  MI_UP_Steel_Green, MI_UP_Steel_Black (deck underside), MI_UP_Concrete.

Textures are EXISTING project textures, loaded read-only (their settings are never touched):
  /Game/KK_S2_Shrine/StarterContent/Textures/T_Metal_Rust_D, T_Metal_Rust_N,
  T_Concrete_Poured_D, T_Concrete_Poured_N, T_Concrete_Grime_D
  /Game/EnvironmentPacks/OceanFloor/Textures/T_Rust_BC   (chip-noise source)
Sampler types are chosen from each texture's own compression/sRGB (LINEAR_GRAYSCALE for
linear grayscale), because a mismatch fails compile.

Mapping (kit meshes from Tools/UnderpassKit/build_underpass_kit.py):
  UV0 U = 1 per 100 cm of AUTHORED length; the instance custom data [1] = true length (cm),
  so true metres along = U * Length / AuthoredLengthCm * (AuthoredLengthCm / 100)
                       = U * Length / 100 * (100 / AuthoredLengthCm) ... computed in UP_TrueUV.
  Not an ISM (hand-placed mock): PerInstanceCustomData returns 0 -> authored length is used.

Traps honoured (memory ue58-python-material-authoring / puss-python-api-gotchas):
  * create-only: REFUSES if any target exists; never deletes an expression anywhere;
  * every connect asserted, then every edge re-read through MEL's read APIs;
  * MI setters can return False after success: the gate is the read-back;
  * single-input pins connect with "" (fallback, as the Wing materiality builder does);
  * compile is async: the run prints UP_MATERIALS_COMPILE_CHECK; read Saved/Logs/PussStage.log
    ~20 s later for "Failed to compile" naming M_UP_ (none = pass);
  * saves ONLY the five new packages (never Save All), then asserts 0+0 dirty.

Mode file: Saved/CodexConductor/underpass_materials_mode.json {"mode": "DRY"|"APPLY"}
(missing file = DRY). DRY loads every texture, checks targets are free, mutates nothing.
Markers (run id in every line): UP_MATERIALS_DRY_OK | UP_MATERIALS_OK | UP_MATERIALS_FAILED.
All work in main(); no unreal objects at module level (memory puss-mcp-python-crashes-the-editor).
"""
import datetime
import json
import os

FOLDER = "/Game/InfinityStage/RigAtmos/Underpass/Materials"
M_STEEL = FOLDER + "/M_UP_PaintedSteel"
M_CONCRETE = FOLDER + "/M_UP_GrimyConcrete"
MI_GREEN = FOLDER + "/MI_UP_Steel_Green"
MI_BLACK = FOLDER + "/MI_UP_Steel_Black"
MI_CONCRETE = FOLDER + "/MI_UP_Concrete"
TARGETS = [M_STEEL, M_CONCRETE, MI_GREEN, MI_BLACK, MI_CONCRETE]
SC = "/Game/KK_S2_Shrine/StarterContent/Textures/"
TEX = {
    "RustD": SC + "T_Metal_Rust_D",
    "RustN": SC + "T_Metal_Rust_N",
    "ChipNoise": "/Game/EnvironmentPacks/OceanFloor/Textures/T_Rust_BC",
    "ConcreteD": SC + "T_Concrete_Poured_D",
    "ConcreteN": SC + "T_Concrete_Poured_N",
    "GrimeD": SC + "T_Concrete_Grime_D",
}
# Paint: Cypress Hills el green (ref_03/04), linear. Black band per the brief (~1.5 m).
STEEL_SCALARS = {
    "AuthoredLengthCm": 100.0, "RivetPitchCm": 10.0, "RivetRadiusCm": 1.1, "RivetBandCm": 10.0,
    "RivetHeight": 0.6, "PassageFloorZ": 0.0, "BandHeightCm": 150.0, "BandSoftnessCm": 4.0,
    "RustTileM": 1.5, "ChipTileM": 2.3, "ChipThreshold": 0.62, "ChipAmount": 0.8,
    "StreakAmount": 0.35, "PaintRoughness": 0.62, "RustRoughness": 0.88, "GrimeAmount": 0.35,
    "RustNormalStrength": 0.6,
}
STEEL_VECTORS = {
    "PaintColor": (0.045, 0.085, 0.05), "BandColor": (0.012, 0.012, 0.012), "RustColor": (0.16, 0.07, 0.03),
}
CONCRETE_SCALARS = {
    "AuthoredLengthCm": 140.0, "ConcreteTileM": 1.4, "GrimeTileM": 2.7, "GrimeAmount": 0.55,
    "PassageFloorZ": 0.0, "WetHeightCm": 35.0, "WetDarken": 0.55, "Roughness": 0.9, "WetRoughness": 0.35,
    "NormalStrength": 0.8,
}
CONCRETE_VECTORS = {"Tint": (0.62, 0.6, 0.56)}
MI_OVERRIDES = {
    MI_GREEN: {"parent": M_STEEL, "scalars": {}, "vectors": {}},
    MI_BLACK: {"parent": M_STEEL, "scalars": {"ChipAmount": 0.35, "StreakAmount": 0.15},
               "vectors": {"PaintColor": (0.014, 0.015, 0.014)}},
    MI_CONCRETE: {"parent": M_CONCRETE, "scalars": {}, "vectors": {}},
}

CODE_TRUE_UV = r"""
// UV0.x = 1 per 100 cm of authored length. Length = custom data [1] (cm), 0 off-ISM.
float L = LengthCm > 0.0 ? LengthCm : AuthoredLengthCm;
float k = L / max(AuthoredLengthCm, 1.0);
TrueCm = UV.x * 100.0 * k;          // centimetres along the member
return float2(UV.x * k, UV.y);       // metres along, raw V
"""

CODE_RIVET = r"""
// Rivet band = V 0..0.1 (Unreal V). One row of domes on the band centre line, RivetPitchCm apart.
float inBand = (UV.y >= 0.0 && UV.y <= 0.1) ? 1.0 : 0.0;
float t = saturate(UV.y / 0.1);
float dx = (frac(TrueCm / max(PitchCm, 0.5)) - 0.5) * PitchCm;
float dy = (t - 0.5) * BandCm;
float r = length(float2(dx, dy));
float m = inBand * (1.0 - smoothstep(RadiusCm * 0.8, RadiusCm, r));
float2 slope = (r > 1e-3 ? float2(dx, dy) / max(RadiusCm, 0.1) : float2(0, 0)) * Height * m;
RivetNormal = normalize(float3(slope.x, -slope.y, 1.0));
return m;
"""

CODE_STEEL_CHIP = r"""
// Paint chips: high values of a rust noise reveal bare rust; more near the rivet band edges.
float c = smoothstep(Threshold, Threshold + 0.06, Noise.g * 0.6 + Noise.r * 0.4 + RivetMask * 0.15);
return saturate(c * Amount);
"""

CODE_STEEL_BASE = r"""
float band = 1.0 - smoothstep(FloorZ + BandH - BandSoft, FloorZ + BandH + BandSoft, WorldPos.z);
float3 paint = lerp(PaintColor, BandColor, band);
paint *= lerp(1.0, 0.75 + 0.5 * Grime, GrimeAmount);
// streaks: rust bleeding down from the rivet band (V just past 0.1, fading over 0.5 V)
float streak = (UV.y > 0.1) ? saturate(1.0 - (UV.y - 0.1) / 0.5) * smoothstep(0.55, 0.8, Noise.r) : 0.0;
paint = lerp(paint, RustColor * 0.8, saturate(streak * StreakAmount));
float3 rust = RustD * RustColor * 3.0;
float3 c = lerp(paint, rust, Chip);
c *= 1.0 - RivetMask * 0.15;            // rivet heads read slightly darker (dirt ring)
OutRough = lerp(PaintRough, RustRough, saturate(Chip + streak * StreakAmount * 0.5));
OutMetal = Chip * 0.3;
return c;
"""

CODE_STEEL_NORMAL = r"""
float3 rn = lerp(float3(0, 0, 1), RustN, saturate(Chip * Strength));
// add the rivet dome on top (whiteout-style blend)
return normalize(float3(rn.xy + RivetN.xy, rn.z * RivetN.z));
"""

CODE_CONCRETE = r"""
float wet = 1.0 - smoothstep(FloorZ + WetH - 6.0, FloorZ + WetH + 6.0, WorldPos.z);
float3 c = D * Tint;
c *= lerp(1.0, 0.6 + 0.6 * Grime, GrimeAmount);
c *= lerp(1.0, WetDarken, wet);
OutRough = lerp(Rough, WetRough, wet);
return c;
"""


def main():
    import unreal  # inside main: nothing UE-owned survives the call

    mel = unreal.MaterialEditingLibrary
    run = "UPMAT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    mode_path = os.path.join(here, "underpass_materials_mode.json")
    mode = "DRY"
    if os.path.exists(mode_path):
        mode = json.load(open(mode_path, encoding="utf-8")).get("mode", "DRY")
    report_path = os.path.join(here, f"underpass_materials_{run}.json")
    report = {"run": run, "mode": mode, "targets": TARGETS, "textures": {}, "status": "STARTED"}
    F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    F2 = unreal.CustomMaterialOutputType.CMOT_FLOAT2
    F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3

    def fail(msg):
        report["status"] = "FAILED"
        report["error"] = msg
        json.dump(report, open(report_path, "w", encoding="utf-8"), indent=1)
        unreal.log_error(f"UP_MATERIALS_FAILED|run={run}|{msg}")
        raise RuntimeError(f"UP_MATERIALS_FAILED|run={run}|{msg}")

    def pk(p):
        s = str(p)
        return s.split("'")[1].split(".")[0] if "'" in s else s.split(".")[0]

    def dirty():
        return (sorted(pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
                sorted(pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))

    # ---------------------------------------------------------------- guards
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        fail("PIE active")
    if dirty() != ([], []):
        fail(f"editor dirty at start {dirty()}")
    existing = [p for p in TARGETS if unreal.EditorAssetLibrary.does_asset_exist(p)]
    if existing:
        fail(f"targets already exist (create-only tool; never edits an existing material): {existing}")

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

    textures = {}
    for key, path in TEX.items():
        tex = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(tex, unreal.Texture2D):
            fail(f"texture {key} {path} does not load as Texture2D")
        textures[key] = tex
        report["textures"][key] = {"path": path, "sampler": str(sampler_for(tex)),
                                   "compression": str(tex.get_editor_property("compression_settings")),
                                   "srgb": bool(tex.get_editor_property("srgb"))}
    if dirty() != ([], []):
        fail(f"loading textures dirtied packages {dirty()}")
    if mode != "APPLY":
        report["status"] = "DRY_OK"
        json.dump(report, open(report_path, "w", encoding="utf-8"), indent=1)
        unreal.log(f"UP_MATERIALS_DRY_OK|run={run}|textures={len(textures)}|targets_free={len(TARGETS)}|mutated=0"
                   f"|report={report_path}")
        return "dry"

    # ---------------------------------------------------------------- graph helper (new assets only)
    class Graph:
        def __init__(self, material):
            self.m = material
            self.edges = []      # (target node, pin, source node, output)
            self.terminals = []  # (property, source node, output)

        def node(self, cls, x, y, **props):
            n = mel.create_material_expression(self.m, cls, x, y)
            if n is None:
                fail(f"create {cls}")
            for k, v in props.items():
                n.set_editor_property(k, v)
            return n

        def scalar(self, name, value, group, x, y):
            return self.node(unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name,
                             default_value=float(value), group=group)

        def vector(self, name, rgb, group, x, y):
            return self.node(unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name,
                             default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0), group=group)

        def custom(self, x, y, desc, code, inputs, out_type, extra=()):
            n = self.node(unreal.MaterialExpressionCustom, x, y, description=desc, code=code, output_type=out_type)
            ins = []
            for name in inputs:
                ci = unreal.CustomInput()
                ci.set_editor_property("input_name", name)
                ins.append(ci)
            n.set_editor_property("inputs", ins)
            got = [str(i.get_editor_property("input_name")) for i in n.get_editor_property("inputs")]
            if got != list(inputs):
                fail(f"custom inputs read-back {desc}: {got}")
            if extra:
                outs = []
                for name, t in extra:
                    co = unreal.CustomOutput()
                    co.set_editor_property("output_name", name)
                    co.set_editor_property("output_type", t)
                    outs.append(co)
                n.set_editor_property("additional_outputs", outs)
            return n

        def tex(self, key, x, y, uv_src, uv_out=""):
            t = textures[key]
            n = self.node(unreal.MaterialExpressionTextureSample, x, y, texture=t, sampler_type=sampler_for(t))
            self.link(uv_src, uv_out, n, "UVs")
            return n

        def link(self, a, a_out, b, b_in):
            ok = mel.connect_material_expressions(a, a_out, b, b_in)
            if not ok and len(mel.get_material_expression_input_names(b)) == 1:
                ok = mel.connect_material_expressions(a, a_out, b, "")  # single-input pins report 'None'
                b_in = "" if ok else b_in
            if not ok:
                fail(f"connect {a.get_name()}.{a_out!r} -> {b.get_name()}.{b_in!r}; "
                     f"inputs={[str(x) for x in mel.get_material_expression_input_names(b)]}")
            self.edges.append((b, b_in, a, a_out))

        def out(self, a, a_out, prop):
            if not mel.connect_material_property(a, a_out, prop):
                fail(f"connect {a.get_name()}.{a_out!r} -> {prop}")
            self.terminals.append((prop, a, a_out))

        def verify(self):
            """Re-read every edge: the upstream node on each target must be the one we wired."""
            bad = []
            for target, pin, source, _ in self.edges:
                ups = list(mel.get_inputs_for_material_expression(self.m, target))
                names = [str(x) for x in mel.get_material_expression_input_names(target)]
                idx = names.index(pin) if pin in names else (0 if pin == "" else -1)
                if idx < 0 or idx >= len(ups) or ups[idx] is None or ups[idx].get_name() != source.get_name():
                    bad.append(f"{source.get_name()}->{target.get_name()}.{pin}")
            for prop, source, _ in self.terminals:
                n = mel.get_material_property_input_node(self.m, prop)
                if n is None or n.get_name() != source.get_name():
                    bad.append(f"{source.get_name()}->{prop}")
            if bad:
                fail(f"{self.m.get_name()} edge read-back: {bad}")
            return {"edges": len(self.edges), "terminals": len(self.terminals)}

    def new_asset(path, cls, factory):
        folder, name = path.rsplit("/", 1)
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"{path} appeared mid-run")
        a = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)
        if not isinstance(a, cls):
            fail(f"create {path}")
        return a

    def set_props(m):
        for k, v in (("blend_mode", unreal.BlendMode.BLEND_OPAQUE),
                     ("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT),
                     ("two_sided", False), ("tangent_space_normal", True),
                     ("used_with_instanced_static_meshes", True), ("used_with_nanite", True)):
            m.modify()
            m.set_editor_property(k, v)
            if str(m.get_editor_property(k)) != str(v):
                fail(f"{m.get_name()}.{k} read-back {m.get_editor_property(k)} != {v}")

    def true_uv(g):
        uv = g.node(unreal.MaterialExpressionTextureCoordinate, -2600, 0, coordinate_index=0)
        cd1 = g.node(unreal.MaterialExpressionPerInstanceCustomData, -2600, 150, data_index=1, const_default_value=0.0)
        auth = g.scalar("AuthoredLengthCm", g_scalars["AuthoredLengthCm"], "01 Mapping", -2600, 250)
        n = g.custom(-2300, 100, "UP_TrueUV: metres along the member", CODE_TRUE_UV,
                     ["UV", "LengthCm", "AuthoredLengthCm"], F2, [("TrueCm", F1)])
        g.link(uv, "", n, "UV")
        g.link(cd1, "", n, "LengthCm")
        g.link(auth, "", n, "AuthoredLengthCm")
        return n

    def scaled(g, src, param, x, y):
        mul = g.node(unreal.MaterialExpressionMultiply, x, y)
        g.link(src, "", mul, "A")
        inv = g.node(unreal.MaterialExpressionDivide, x - 150, y + 60)
        g.link(g.node(unreal.MaterialExpressionConstant, x - 300, y + 60, r=1.0), "", inv, "A")
        g.link(param, "", inv, "B")
        g.link(inv, "", mul, "B")
        return mul

    made = {}
    try:
        # ------------------------------------------------------------ M_UP_PaintedSteel
        steel = new_asset(M_STEEL, unreal.Material, unreal.MaterialFactoryNew())
        set_props(steel)
        g = Graph(steel)
        g_scalars = STEEL_SCALARS
        s = {k: g.scalar(k, v, "02 Steel", -2000, 600 + i * 70) for i, (k, v) in enumerate(STEEL_SCALARS.items())
             if k != "AuthoredLengthCm"}
        v = {k: g.vector(k, c, "02 Steel", -2000, 1900 + i * 90) for i, (k, c) in enumerate(STEEL_VECTORS.items())}
        tuv = true_uv(g)
        rivet = g.custom(-1700, -200, "UP_Rivet: dome row in the V 0-0.1 band", CODE_RIVET,
                         ["UV", "TrueCm", "PitchCm", "RadiusCm", "BandCm", "Height"], F1, [("RivetNormal", F3)])
        g.link(tuv, "", rivet, "UV")
        g.link(tuv, "TrueCm", rivet, "TrueCm")
        for pin, key in (("PitchCm", "RivetPitchCm"), ("RadiusCm", "RivetRadiusCm"), ("BandCm", "RivetBandCm"),
                         ("Height", "RivetHeight")):
            g.link(s[key], "", rivet, pin)
        rust_uv = scaled(g, tuv, s["RustTileM"], -1700, 100)
        chip_uv = scaled(g, tuv, s["ChipTileM"], -1700, 300)
        rust_d = g.tex("RustD", -1400, 0, rust_uv)
        rust_n = g.tex("RustN", -1400, 250, rust_uv)
        noise = g.tex("ChipNoise", -1400, 500, chip_uv)
        grime = g.tex("RustD", -1400, 750, chip_uv)  # rust luminance doubles as a paint-grime mask
        chip = g.custom(-1100, 400, "UP_Chip", CODE_STEEL_CHIP, ["Noise", "RivetMask", "Threshold", "Amount"], F1)
        g.link(noise, "RGB", chip, "Noise")
        g.link(rivet, "", chip, "RivetMask")
        g.link(s["ChipThreshold"], "", chip, "Threshold")
        g.link(s["ChipAmount"], "", chip, "Amount")
        wpos = g.node(unreal.MaterialExpressionWorldPosition, -1400, 1000,
                      world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
        base_in = ["WorldPos", "UV", "FloorZ", "BandH", "BandSoft", "PaintColor", "BandColor", "RustColor", "RustD",
                   "Noise", "Grime", "GrimeAmount", "Chip", "RivetMask", "StreakAmount", "PaintRough", "RustRough"]
        base = g.custom(-700, 0, "UP_SteelBase", CODE_STEEL_BASE, base_in, F3, [("OutRough", F1), ("OutMetal", F1)])
        wires = {"WorldPos": (wpos, ""), "UV": (tuv, ""), "FloorZ": (s["PassageFloorZ"], ""),
                 "BandH": (s["BandHeightCm"], ""), "BandSoft": (s["BandSoftnessCm"], ""),
                 "PaintColor": (v["PaintColor"], "RGB"), "BandColor": (v["BandColor"], "RGB"),
                 "RustColor": (v["RustColor"], "RGB"), "RustD": (rust_d, "RGB"), "Noise": (noise, "RGB"),
                 "Grime": (grime, "R"), "GrimeAmount": (s["GrimeAmount"], ""), "Chip": (chip, ""),
                 "RivetMask": (rivet, ""), "StreakAmount": (s["StreakAmount"], ""),
                 "PaintRough": (s["PaintRoughness"], ""), "RustRough": (s["RustRoughness"], "")}
        for pin in base_in:
            g.link(wires[pin][0], wires[pin][1], base, pin)
        normal = g.custom(-700, 500, "UP_SteelNormal", CODE_STEEL_NORMAL, ["RustN", "RivetN", "Chip", "Strength"], F3)
        g.link(rust_n, "RGB", normal, "RustN")
        g.link(rivet, "RivetNormal", normal, "RivetN")
        g.link(chip, "", normal, "Chip")
        g.link(s["RustNormalStrength"], "", normal, "Strength")
        g.out(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(base, "OutRough", unreal.MaterialProperty.MP_ROUGHNESS)
        g.out(base, "OutMetal", unreal.MaterialProperty.MP_METALLIC)
        g.out(normal, "", unreal.MaterialProperty.MP_NORMAL)
        made[M_STEEL] = g.verify()
        mel.recompile_material(steel)

        # ------------------------------------------------------------ M_UP_GrimyConcrete
        conc = new_asset(M_CONCRETE, unreal.Material, unreal.MaterialFactoryNew())
        set_props(conc)
        g = Graph(conc)
        g_scalars = CONCRETE_SCALARS
        s = {k: g.scalar(k, val, "02 Concrete", -2000, 600 + i * 70)
             for i, (k, val) in enumerate(CONCRETE_SCALARS.items()) if k != "AuthoredLengthCm"}
        tint = g.vector("Tint", CONCRETE_VECTORS["Tint"], "02 Concrete", -2000, 1500)
        tuv = true_uv(g)
        c_uv = scaled(g, tuv, s["ConcreteTileM"], -1700, 100)
        gr_uv = scaled(g, tuv, s["GrimeTileM"], -1700, 300)
        cd = g.tex("ConcreteD", -1400, 0, c_uv)
        cn = g.tex("ConcreteN", -1400, 250, c_uv)
        gr = g.tex("GrimeD", -1400, 500, gr_uv)
        wpos = g.node(unreal.MaterialExpressionWorldPosition, -1400, 800,
                      world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
        c_in = ["D", "Tint", "Grime", "GrimeAmount", "WorldPos", "FloorZ", "WetH", "WetDarken", "Rough", "WetRough"]
        cbase = g.custom(-800, 0, "UP_Concrete", CODE_CONCRETE, c_in, F3, [("OutRough", F1)])
        cw = {"D": (cd, "RGB"), "Tint": (tint, "RGB"), "Grime": (gr, "R"), "GrimeAmount": (s["GrimeAmount"], ""),
              "WorldPos": (wpos, ""), "FloorZ": (s["PassageFloorZ"], ""), "WetH": (s["WetHeightCm"], ""),
              "WetDarken": (s["WetDarken"], ""), "Rough": (s["Roughness"], ""), "WetRough": (s["WetRoughness"], "")}
        for pin in c_in:
            g.link(cw[pin][0], cw[pin][1], cbase, pin)
        flat = g.node(unreal.MaterialExpressionConstant3Vector, -1100, 400, constant=unreal.LinearColor(0, 0, 1, 1))
        nlerp = g.node(unreal.MaterialExpressionLinearInterpolate, -800, 400)
        g.link(flat, "", nlerp, "A")
        g.link(cn, "RGB", nlerp, "B")
        g.link(s["NormalStrength"], "", nlerp, "Alpha")
        g.out(cbase, "", unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(cbase, "OutRough", unreal.MaterialProperty.MP_ROUGHNESS)
        g.out(nlerp, "", unreal.MaterialProperty.MP_NORMAL)
        made[M_CONCRETE] = g.verify()
        mel.recompile_material(conc)

        # ------------------------------------------------------------ MIs (gate = read-back, not setter bools)
        parents = {M_STEEL: steel, M_CONCRETE: conc}
        for path, row in MI_OVERRIDES.items():
            mi = new_asset(path, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
            mi.modify()
            mel.set_material_instance_parent(mi, parents[row["parent"]])
            par = mi.get_editor_property("parent")
            if par is None or pk(par.get_path_name()) != row["parent"]:
                fail(f"{path} parent read-back {par}")
            for name, val in row["scalars"].items():
                mi.modify()
                mel.set_material_instance_scalar_parameter_value(mi, name, float(val))  # bool unreliable
                got = float(mel.get_material_instance_scalar_parameter_value(mi, name))
                if abs(got - float(val)) > 1e-5:
                    fail(f"{path}.{name} read-back {got} != {val}")
            for name, rgb in row["vectors"].items():
                mi.modify()
                mel.set_material_instance_vector_parameter_value(mi, name, unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
                got = mel.get_material_instance_vector_parameter_value(mi, name)
                if any(abs(a - b) > 1e-4 for a, b in zip((got.r, got.g, got.b), rgb)):
                    fail(f"{path}.{name} read-back {got} != {rgb}")
            mel.update_material_instance(mi)
            made[path] = {"parent": row["parent"], "scalars": row["scalars"], "vectors": row["vectors"]}

        # ------------------------------------------------------------ save only the five new packages
        c1, m1 = dirty()
        if m1 or not set(c1) <= set(TARGETS):
            fail(f"dirty scope before save: content={c1} maps={m1}")
        for path in TARGETS:
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                fail(f"save {path}")
        if dirty() != ([], []):
            fail(f"dirty after save {dirty()}")
        # read-back from the saved assets
        for path in TARGETS:
            if not unreal.EditorAssetLibrary.does_asset_exist(path):
                fail(f"{path} missing after save")
        back = unreal.EditorAssetLibrary.load_asset(MI_BLACK)
        got = mel.get_material_instance_vector_parameter_value(back, "PaintColor")
        if abs(got.r - MI_OVERRIDES[MI_BLACK]["vectors"]["PaintColor"][0]) > 1e-4:
            fail("MI_UP_Steel_Black PaintColor read-back after save")
    except Exception as exc:  # noqa: BLE001
        if report.get("status") != "FAILED":
            fail(f"exception {exc!r} (created assets are unsaved: Don't-Save restart, do NOT Save All)")
        raise
    report["status"] = "APPLIED"
    report["made"] = made
    json.dump(report, open(report_path, "w", encoding="utf-8"), indent=1)
    unreal.log(f"UP_MATERIALS_OK|run={run}|masters=2|instances=3|saved=5|dirty_after=0+0|report={report_path}")
    unreal.log(f"UP_MATERIALS_COMPILE_CHECK|run={run}|grep PussStage.log for 'Failed to compile' + 'M_UP_' in ~20 s")
    return "applied"


main()
