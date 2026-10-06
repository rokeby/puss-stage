"""S3 tiling marble: CREATE-ONLY master M_S3_MarbleTiling + MI_S3_Marble_Tiling_Daylight (+ optional per-actor children).

Why (Gary 6 Oct, "just marble for now"): the S3 liners use MI_S3_Marble_Heavy_Daylight, whose textures are the 8K
Megascans Roman_Marble_Plinth 3D-asset UV ATLAS stretched once over a 6000 x 605 cm cube face (~10:1 anisotropic),
so the hand prints sit on giant horizontal streaks (Saved/CodexFlatV3/handprints/hp_marble_probe.json).

The master samples a TILEABLE marble in planar coordinates (cm) at RepeatCm (default 150), blends a second
rotated/rescaled sample by a two-octave value noise (macro breakup), and copies the old MI's look parameters
(Brightness, Saturation, Min/Max Roughness, Specular; names kept, spaces included).

Two coordinate frames, chosen PER MI by the scalar ObjectRelative (0 = world, 1 = object):
  world  (ObjectRelative 0, the MI_S3_Marble_Tiling_Daylight default, as briefed): absolute world position on the
         dominant-normal plane. Base liners and upper tiles are continuous for free. BUT the S3 box RISES AND ROTATES
         ("rises from below the horizon, hinged at the mouth", Docs/InfinityStageSessionHandover.md:130,211; level is
         saved LANDED, sunk + pitched at BeginPlay, memory puss-level-saved-landed-frame-trap): during the rise the
         texture would swim across the walls and under the attached hand-print decals. Correct only once landed.
  object (ObjectRelative 1, per-actor child MIs MI_S3_Marble_Tiling_Daylight_<L|R><k>): coordinates = (WorldPos -
         ObjectPos) projected on the actor's own local X / Z axes, times USign/VSign, plus UOffsetCm/VOffsetCm that the
         apply tool computes from the live transforms so all five actors per side share ONE frame anchored on that
         side's base liner. Rigid with the box through the rise; still continuous at the liner/tile seams; immune to
         the mirrored (negative-Z) upper tiles.

Pure helpers at the top run offline (test_s3_marble_tiling_offline.py); the Unreal builder is below them.
Rules followed (memory ue58-python-material-authoring): create-only, NEVER delete expressions, never trust setter
return values (read everything back), sampler type derived from each default texture's compression + sRGB.
"""
import math

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None

MATDIR = "/Game/InfinityStage/Dev/Materials"
MASTER = MATDIR + "/M_S3_MarbleTiling"
MI = MATDIR + "/MI_S3_Marble_Tiling_Daylight"
CHILD_PREFIX = MATDIR + "/MI_S3_Marble_Tiling_Daylight_"
OLD_MI = MATDIR + "/MI_S3_Marble_Heavy_Daylight"

# Look parameters copied from the live OLD_MI at build time; these are the fallbacks = the probe values
# (hp_marble_probe.json, 6 Oct). Names match M_MS_Base exactly (spaces included).
LOOK_FALLBACK = {"Brightness": 1.15, "Min Roughness": 0.05, "Max Roughness": 0.12, "Specular": 0.7,
                 "Saturation": 0.8}
SCALARS = {  # name: (default, group, sort)
    "Brightness": (1.15, "01 Look", 0),
    "Saturation": (0.8, "01 Look", 1),
    "Min Roughness": (0.05, "01 Look", 2),
    "Max Roughness": (0.12, "01 Look", 3),
    "Specular": (0.7, "01 Look", 4),
    "Normal Intensity": (0.5, "01 Look", 5),
    "RoughnessTextureWeight": (0.0, "01 Look", 6),
    "RepeatCm": (150.0, "02 Tiling", 0),
    "BackFaceShiftCm": (317.0, "02 Tiling", 1),
    "BreakupScale": (2.37, "03 Breakup", 0),
    "BreakupRotationDeg": (37.0, "03 Breakup", 1),
    "BreakupNoiseCm": (420.0, "03 Breakup", 2),
    "BreakupContrast": (2.2, "03 Breakup", 3),
    "BreakupAmount": (1.0, "03 Breakup", 4),
    "ObjectRelative": (0.0, "04 Frame", 0),
    "USign": (1.0, "04 Frame", 1),
    "VSign": (1.0, "04 Frame", 2),
    "UOffsetCm": (0.0, "04 Frame", 3),
    "VOffsetCm": (0.0, "04 Frame", 4),
}
FRAME_PARAMS = ("ObjectRelative", "USign", "VSign", "UOffsetCm", "VOffsetCm")
TEXTURE_PARAMS = ("BaseColorTexture", "NormalTexture", "RoughnessTexture")
# Default source = the only tileable marble already in Content (searched 6 Oct; see the report). Diffuse only:
# normal is flat and roughness comes from vein luminance until a CC0 set is imported (args "textures").
SOURCES = {
    "starter": {"BaseColorTexture": "/Game/KK_S2_Shrine/StarterContent/Textures/T_Rock_Marble_Polished_D",
                "NormalTexture": "/Engine/EngineMaterials/FlatNormal",
                "RoughnessTexture": "/Game/KK_S2_Shrine/StarterContent/Textures/T_Rock_Marble_Polished_D"},
}
SIDE_U_SHIFT_CM = {"L": 0.0, "R": 317.0}   # object frame: keep the facing walls from being mirror twins
TOL_AXIS = 0.999
TOL_PLANE_CM = 0.5


class MarbleError(ValueError):
    pass


# --------------------------------------------------------------------------------------------- pure helpers
def sampler_for(compression, srgb):
    """Sampler type NAME that matches a texture (mismatch fails compile and cascades). compression is the
    TextureCompressionSettings name, e.g. 'TC_DEFAULT', 'TextureCompressionSettings.TC_NORMALMAP'."""
    c = str(compression).upper().rsplit(".", 1)[-1]
    if c == "TC_NORMALMAP":
        return "SAMPLERTYPE_NORMAL"
    if c == "TC_MASKS":
        return "SAMPLERTYPE_MASKS"
    if c in ("TC_GRAYSCALE", "TC_ALPHA", "TC_DISPLACEMENTMAP"):
        return "SAMPLERTYPE_GRAYSCALE" if srgb else "SAMPLERTYPE_LINEAR_GRAYSCALE"
    if c in ("TC_DEFAULT", "TC_BC7", "TC_EDITOR_ICON", "TC_LQ"):
        return "SAMPLERTYPE_COLOR" if srgb else "SAMPLERTYPE_LINEAR_COLOR"
    raise MarbleError("SAMPLER_UNMAPPED|%s|srgb=%s" % (compression, srgb))


def rotator_axes(rotation):
    """UE FRotationMatrix axes for [roll, pitch, yaw] in degrees: (X forward, Y right, Z up)."""
    r, p, y = (math.radians(float(v)) for v in rotation)
    sr, cr, sp, cp, sy, cy = math.sin(r), math.cos(r), math.sin(p), math.cos(p), math.sin(y), math.cos(y)
    x = (cp * cy, cp * sy, sp)
    yy = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp)
    z = (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp)
    return x, yy, z


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _sub(a, b):
    return [float(a[i]) - float(b[i]) for i in range(3)]


def _scale(v, s):
    return [float(x) * s for x in v]


def _norm(v):
    n = math.sqrt(_dot(v, v))
    if n < 1e-12:
        raise MarbleError("ZERO_AXIS")
    return [x / n for x in v]


def local_axes_world(world):
    """What the material's Transform(Local->World) of (1,0,0) and (0,0,1) give, normalised: the columns of the
    actor matrix, which do not depend on how UE decomposed a mirrored scale (memory ue58-ism-readback)."""
    x, _, z = rotator_axes(world["rotation"])
    s = world["scale"]
    return _norm(_scale(x, s[0])), _norm(_scale(z, s[2]))


def object_frame_params(rows):
    """rows: [{label, side 'L'|'R', role 'base'|'upper', world {location, rotation, scale}}].
    Returns {label: {ObjectRelative, USign, VSign, UOffsetCm, VOffsetCm}} so that for every actor
    u = USign*dot(P - pivot, AU) + UOffsetCm == dot(P - base_pivot, base_AU) + side shift (same for v):
    one rigid frame per side, anchored on that side's base liner."""
    out, fails = {}, []
    for side in "LR":
        bases = [r for r in rows if r["side"] == side and r["role"] == "base"]
        if len(bases) != 1:
            raise MarbleError("BASE_COUNT|%s|%d" % (side, len(bases)))
        b = bases[0]
        bu, bv = local_axes_world(b["world"])
        bn = _norm([bu[1] * bv[2] - bu[2] * bv[1], bu[2] * bv[0] - bu[0] * bv[2], bu[0] * bv[1] - bu[1] * bv[0]])
        for r in (x for x in rows if x["side"] == side):
            au, av = local_axes_world(r["world"])
            du, dv = _dot(au, bu), _dot(av, bv)
            if abs(du) < TOL_AXIS or abs(dv) < TOL_AXIS:
                fails.append("AXES_NOT_PARALLEL|%s|%.4f|%.4f" % (r["label"], du, dv))
                continue
            off = _sub(r["world"]["location"], b["world"]["location"])
            if abs(_dot(off, bn)) > TOL_PLANE_CM:
                fails.append("NOT_COPLANAR|%s|%.3f" % (r["label"], _dot(off, bn)))
                continue
            out[r["label"]] = {"ObjectRelative": 1.0, "USign": 1.0 if du > 0 else -1.0,
                               "VSign": 1.0 if dv > 0 else -1.0,
                               "UOffsetCm": round(_dot(off, bu) + SIDE_U_SHIFT_CM[side], 3),
                               "VOffsetCm": round(_dot(off, bv), 3)}
    if fails:
        raise MarbleError(";".join(fails))
    return out


def child_suffix(row):
    return "%s%d" % (row["side"], 0 if row["role"] == "base" else int(row["index"]))


def _hash(ix, iy):
    return (math.sin(ix * 127.1 + iy * 311.7) * 43758.5453) % 1.0


def coords_reference(wp_abs, normal, wp_minus_op, au, av, p):
    """Python mirror of CODE_COORDS (same order of operations). Returns (uvA, uvB, blend)."""
    an = [abs(float(c)) for c in normal]
    if an[1] >= an[0] and an[1] >= an[2]:
        pw, back = [wp_abs[0], wp_abs[2]], normal[1] < 0.0
    elif an[0] >= an[2]:
        pw, back = [wp_abs[1], wp_abs[2]], normal[0] < 0.0
    else:
        pw, back = [wp_abs[0], wp_abs[1]], normal[2] < 0.0
    pw[0] += p["BackFaceShiftCm"] if back else 0.0
    po = [p["USign"] * _dot(wp_minus_op, _norm(au)) + p["UOffsetCm"],
          p["VSign"] * _dot(wp_minus_op, _norm(av)) + p["VOffsetCm"]]
    k = min(max(p["ObjectRelative"], 0.0), 1.0)
    pp = [pw[i] + (po[i] - pw[i]) * k for i in range(2)]
    r = 1.0 / max(p["RepeatCm"], 1.0)
    t = [pp[0], -pp[1]]
    ang = p["BreakupRotationDeg"] * 0.0174532925
    cs, sn = math.cos(ang), math.sin(ang)
    tb = [cs * t[0] - sn * t[1], sn * t[0] + cs * t[1]]
    rb = r / max(p["BreakupScale"], 0.01)
    uvb = [tb[0] * rb + 0.37, tb[1] * rb + 0.61]
    q = [pp[0] / max(p["BreakupNoiseCm"], 1.0), pp[1] / max(p["BreakupNoiseCm"], 1.0)]
    n, amp = 0.0, 0.65
    for _ in range(2):
        i0 = [math.floor(q[0]), math.floor(q[1])]
        i1 = [i0[0] + 1.0, i0[1] + 1.0]
        i0 = [v - 289.0 * math.floor(v / 289.0) for v in i0]   # wrap EACH corner (wrapping before +1 tore
        i1 = [v - 289.0 * math.floor(v / 289.0) for v in i1]   # the noise at cell 0; harness, 6 Oct)
        f = [q[0] - math.floor(q[0]), q[1] - math.floor(q[1])]
        u = [f[0] * f[0] * (3.0 - 2.0 * f[0]), f[1] * f[1] * (3.0 - 2.0 * f[1])]
        a, b = _hash(i0[0], i0[1]), _hash(i1[0], i0[1])
        c, e = _hash(i0[0], i1[1]), _hash(i1[0], i1[1])
        n += amp * ((a + (b - a) * u[0]) + ((c + (e - c) * u[0]) - (a + (b - a) * u[0])) * u[1])
        q = [q[0] * 2.03 + 17.1, q[1] * 2.03 + 5.3]
        amp = 0.35
    blend = min(max((n - 0.5) * p["BreakupContrast"] + 0.5, 0.0), 1.0) * min(max(p["BreakupAmount"], 0.0), 1.0)
    return [t[0] * r, t[1] * r], uvb, blend


def compile_errors_since(log_text, marker):
    """Lines after the LAST line matching `marker` that report a compile error for the master.
    marker: a substring, or a list of alternatives where each alternative is a tuple of substrings that must
    ALL be on the line."""
    alts = [(marker,)] if isinstance(marker, str) else [tuple(a) if not isinstance(a, str) else (a,) for a in marker]
    lines = log_text.splitlines()
    start = max((i for i, ln in enumerate(lines) if any(all(s in ln for s in alt) for alt in alts)), default=-1)
    if start < 0:
        return None   # marker not found: cannot judge
    name = MASTER.rsplit("/", 1)[-1]
    return [ln for ln in lines[start + 1:]
            if name in ln and ("failed to compile" in ln.lower() or "error" in ln.lower())]


# HLSL. Keep in step with coords_reference() above (the harness checks the shared constants).
CODE_COORDS = r"""
float3 an = abs(N);
float2 pw;
float back;
if (an.y >= an.x && an.y >= an.z) { pw = float2(WPAbs.x, WPAbs.z); back = N.y < 0.0 ? 1.0 : 0.0; }
else if (an.x >= an.z)            { pw = float2(WPAbs.y, WPAbs.z); back = N.x < 0.0 ? 1.0 : 0.0; }
else                              { pw = float2(WPAbs.x, WPAbs.y); back = N.z < 0.0 ? 1.0 : 0.0; }
pw.x += back * BackShift;
float3 d = WPc - OPc;
float2 po = float2(USign * dot(d, normalize(AU)) + UOff, VSign * dot(d, normalize(AV)) + VOff);
float2 p = lerp(pw, po, saturate(ObjRel));
float r = 1.0 / max(RepeatCm, 1.0);
float2 t = float2(p.x, -p.y);
float ang = BRotDeg * 0.0174532925;
float cs = cos(ang);
float sn = sin(ang);
float2 tb = float2(cs * t.x - sn * t.y, sn * t.x + cs * t.y);
UVB = tb * (r / max(BScale, 0.01)) + float2(0.37, 0.61);
float2 q = p / max(NoiseCm, 1.0);
float n = 0.0;
float amp = 0.65;
for (int o = 0; o < 2; o++)
{
    float2 i0 = floor(q);
    float2 i1 = i0 + 1.0;
    i0 = i0 - 289.0 * floor(i0 / 289.0);
    i1 = i1 - 289.0 * floor(i1 / 289.0);
    float2 f = frac(q);
    float2 u = f * f * (3.0 - 2.0 * f);
    float a = frac(sin(dot(float2(i0.x, i0.y), float2(127.1, 311.7))) * 43758.5453);
    float b = frac(sin(dot(float2(i1.x, i0.y), float2(127.1, 311.7))) * 43758.5453);
    float c = frac(sin(dot(float2(i0.x, i1.y), float2(127.1, 311.7))) * 43758.5453);
    float e = frac(sin(dot(float2(i1.x, i1.y), float2(127.1, 311.7))) * 43758.5453);
    n += amp * lerp(lerp(a, b, u.x), lerp(c, e, u.x), u.y);
    q = q * 2.03 + float2(17.1, 5.3);
    amp = 0.35;
}
Blend = saturate((n - 0.5) * Contrast + 0.5) * saturate(Amount);
return t * r;
"""
COORD_INPUTS = ["WPAbs", "WPc", "OPc", "N", "AU", "AV", "ObjRel", "USign", "VSign", "UOff", "VOff", "BackShift",
                "RepeatCm", "BScale", "BRotDeg", "NoiseCm", "Contrast", "Amount"]
COORD_PARAM_PINS = {"ObjRel": "ObjectRelative", "USign": "USign", "VSign": "VSign", "UOff": "UOffsetCm",
                    "VOff": "VOffsetCm", "BackShift": "BackFaceShiftCm", "RepeatCm": "RepeatCm",
                    "BScale": "BreakupScale", "BRotDeg": "BreakupRotationDeg", "NoiseCm": "BreakupNoiseCm",
                    "Contrast": "BreakupContrast", "Amount": "BreakupAmount"}

CODE_SHADE = r"""
float3 bc = lerp(BCA, BCB, Blend);
float3 nn = normalize(lerp(NA, NB, Blend));
float rt = lerp(RA, RB, Blend);
float lum = dot(bc, float3(0.2126, 0.7152, 0.0722));
float3 c = lerp(lum.xxx, bc, Saturation) * Brightness;
float vein = saturate(1.0 - lum);
OutRoughness = lerp(MinR, MaxR, lerp(vein, rt, saturate(RoughW)));
OutNormal = normalize(lerp(float3(0.0, 0.0, 1.0), nn, NormalIntensity));
return saturate(c);
"""
SHADE_INPUTS = ["BCA", "BCB", "NA", "NB", "RA", "RB", "Blend", "Brightness", "Saturation", "MinR", "MaxR",
                "RoughW", "NormalIntensity"]
SHADE_PARAM_PINS = {"Brightness": "Brightness", "Saturation": "Saturation", "MinR": "Min Roughness",
                    "MaxR": "Max Roughness", "RoughW": "RoughnessTextureWeight", "NormalIntensity": "Normal Intensity"}


def graph_spec_problems():
    """Static consistency of the graph description (offline): every HLSL input is declared and wired."""
    import re
    probs = []
    for code, ins in ((CODE_COORDS, COORD_INPUTS), (CODE_SHADE, SHADE_INPUTS)):
        for name in ins:
            if not re.search(r"\b%s\b" % re.escape(name), code):
                probs.append("INPUT_UNUSED|" + name)
    for pin, param in list(COORD_PARAM_PINS.items()) + list(SHADE_PARAM_PINS.items()):
        if param not in SCALARS:
            probs.append("PARAM_UNDECLARED|" + param)
    for pin in COORD_PARAM_PINS:
        if pin not in COORD_INPUTS:
            probs.append("COORD_PIN_UNKNOWN|" + pin)
    for pin in SHADE_PARAM_PINS:
        if pin not in SHADE_INPUTS:
            probs.append("SHADE_PIN_UNKNOWN|" + pin)
    for k in LOOK_FALLBACK:
        if k not in SCALARS:
            probs.append("LOOK_NOT_A_PARAM|" + k)
    for tok in ("127.1", "311.7", "43758.5453", "289.0", "2.03", "17.1", "5.3", "0.65", "0.35", "0.37", "0.61",
                "0.0174532925"):
        if tok not in CODE_COORDS:
            probs.append("HLSL_CONST_DRIFT|" + tok)
    return probs


# --------------------------------------------------------------------------------------------- unreal builder
def _require(cond, msg):
    if not cond:
        raise MarbleError(msg)


def _path(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def texture_sampler(path):
    tex = unreal.load_asset(path)
    _require(tex is not None, "TEXTURE_MISSING|" + path)
    return tex, sampler_for(str(tex.get_editor_property("compression_settings")), bool(tex.get_editor_property("srgb")))


def live_look():
    """Current look scalars of the OLD MI (copy the look, never edit it)."""
    mel = unreal.MaterialEditingLibrary
    old = unreal.load_asset(OLD_MI)
    if old is None:
        return dict(LOOK_FALLBACK), "fallback(OLD_MI missing)"
    names = [str(n) for n in mel.get_scalar_parameter_names(old)]
    out = {}
    for k, v in LOOK_FALLBACK.items():
        out[k] = float(mel.get_material_instance_scalar_parameter_value(old, k)) if k in names else v
    return out, "live"


class _Graph:
    def __init__(self, mat):
        self.mat, self.mel = mat, unreal.MaterialEditingLibrary

    def node(self, cls, x, y, **props):
        n = self.mel.create_material_expression(self.mat, cls, x, y)
        _require(n is not None, "CREATE_NODE|%s" % cls)
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    def link(self, a, a_out, b, b_in):
        ok = self.mel.connect_material_expressions(a, a_out, b, b_in)
        if not ok and len(self.mel.get_material_expression_input_names(b)) == 1:
            ok = self.mel.connect_material_expressions(a, a_out, b, "")
        _require(ok, "LINK|%s.%s->%s.%s" % (a.get_name(), a_out, b.get_name(), b_in))

    def custom(self, x, y, desc, code, inputs, out_type, extra=()):
        n = self.node(unreal.MaterialExpressionCustom, x, y, description=desc, code=code, output_type=out_type)
        ins = []
        for name in inputs:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", name)
            ins.append(ci)
        n.set_editor_property("inputs", ins)
        if extra:
            outs = []
            for name, t in extra:
                co = unreal.CustomOutput()
                co.set_editor_property("output_name", name)
                co.set_editor_property("output_type", t)
                outs.append(co)
            n.set_editor_property("additional_outputs", outs)
        return n


def build_master(look, textures):
    """CREATE-ONLY: refuses if MASTER exists. Returns (material, readback dict)."""
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    _require(not eal.does_asset_exist(MASTER), "MASTER_EXISTS")
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        MASTER.rsplit("/", 1)[-1], MATDIR, unreal.Material, unreal.MaterialFactoryNew())
    _require(mat is not None, "MASTER_CREATE_FAILED")
    g = _Graph(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    F1, F2, F3 = (unreal.CustomMaterialOutputType.CMOT_FLOAT1, unreal.CustomMaterialOutputType.CMOT_FLOAT2,
                  unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    shared = unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS
    params = {}
    for i, (name, (dflt, group, prio)) in enumerate(SCALARS.items()):
        v = look.get(name, dflt)
        params[name] = g.node(unreal.MaterialExpressionScalarParameter, -2200, -400 + 90 * i,
                              parameter_name=name, default_value=float(v), group=group, sort_priority=prio)
    # coordinates
    wabs = g.node(unreal.MaterialExpressionWorldPosition, -2600, 0,
                  world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    wabs_f = g.node(unreal.MaterialExpressionTruncateLWC, -2400, 0)
    g.link(wabs, "", wabs_f, "")
    wcam = g.node(unreal.MaterialExpressionWorldPosition, -2600, 120,
                  world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_CAMERA_RELATIVE_NO_OFFSETS)
    ocam = g.node(unreal.MaterialExpressionObjectPositionWS, -2600, 240,
                  origin_type=unreal.PositionOrigin.CAMERA_RELATIVE)
    vn = g.node(unreal.MaterialExpressionVertexNormalWS, -2600, 360)
    axes = []
    for k, v in enumerate(((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))):
        c = g.node(unreal.MaterialExpressionConstant3Vector, -2800, 480 + 120 * k,
                   constant=unreal.LinearColor(v[0], v[1], v[2], 1.0))
        t = g.node(unreal.MaterialExpressionTransform, -2600, 480 + 120 * k,
                   transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
                   transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        g.link(c, "", t, "VectorInput")
        axes.append(t)
    coords = g.custom(-1900, 200, "S3 marble planar coords + macro breakup", CODE_COORDS, COORD_INPUTS, F2,
                      [("UVB", F2), ("Blend", F1)])
    wires = {"WPAbs": wabs_f, "WPc": wcam, "OPc": ocam, "N": vn, "AU": axes[0], "AV": axes[1]}
    wires.update({pin: params[name] for pin, name in COORD_PARAM_PINS.items()})
    for pin in COORD_INPUTS:
        g.link(wires[pin], "", coords, pin)
    # textures: parameter objects + A/B samples
    ST = unreal.MaterialSamplerType
    samples, samplers = {}, {}
    for k, name in enumerate(TEXTURE_PARAMS):
        tex, st_name = texture_sampler(textures[name])
        samplers[name] = st_name
        st = getattr(ST, st_name)
        obj = g.node(unreal.MaterialExpressionTextureObjectParameter, -1600, -200 + 300 * k, parameter_name=name,
                     texture=tex, sampler_type=st, group="00 Textures", sort_priority=k)
        pair = []
        for j, uv_out in enumerate(("", "UVB")):
            s = g.node(unreal.MaterialExpressionTextureSample, -1300, -200 + 300 * k + 140 * j,
                       sampler_type=st, sampler_source=shared)
            g.link(obj, "", s, "Tex")
            g.link(coords, uv_out, s, "UVs")
            pair.append(s)
        samples[name] = pair
    shade = g.custom(-900, 200, "S3 marble look (copied MI params)", CODE_SHADE, SHADE_INPUTS, F3,
                     [("OutRoughness", F1), ("OutNormal", F3)])
    sw = {"BCA": (samples["BaseColorTexture"][0], "RGB"), "BCB": (samples["BaseColorTexture"][1], "RGB"),
          "NA": (samples["NormalTexture"][0], "RGB"), "NB": (samples["NormalTexture"][1], "RGB"),
          "RA": (samples["RoughnessTexture"][0], "R"), "RB": (samples["RoughnessTexture"][1], "R"),
          "Blend": (coords, "Blend")}
    sw.update({pin: (params[name], "") for pin, name in SHADE_PARAM_PINS.items()})
    for pin in SHADE_INPUTS:
        src, out = sw[pin]
        g.link(src, out, shade, pin)
    MP = unreal.MaterialProperty
    for src, out, prop in ((shade, "", MP.MP_BASE_COLOR), (shade, "OutRoughness", MP.MP_ROUGHNESS),
                           (shade, "OutNormal", MP.MP_NORMAL), (params["Specular"], "", MP.MP_SPECULAR)):
        _require(mel.connect_material_property(src, out, prop), "PROP|%s" % prop)
    mel.layout_material_expressions(mat)
    mel.recompile_material(mat)
    return mat, readback_master(mat, shade, params["Specular"], look, samplers)


def readback_master(mat, shade=None, spec=None, look=None, samplers=None):
    """Judge by the graph and the parameter tables, never by setter return values."""
    mel = unreal.MaterialEditingLibrary
    MP = unreal.MaterialProperty
    rb = {"blend_mode": str(mat.get_editor_property("blend_mode")),
          "shading_model": str(mat.get_editor_property("shading_model")),
          "decal_response": str(mat.get_editor_property("material_decal_response")),
          "tangent_space_normal": bool(mat.get_editor_property("tangent_space_normal")),
          "expressions": int(mel.get_num_material_expressions(mat)),
          "scalars": sorted(str(n) for n in mel.get_scalar_parameter_names(mat)),
          "textures": sorted(str(n) for n in mel.get_texture_parameter_names(mat)),
          "samplers": samplers, "inputs": {}}
    for key, prop in (("base", MP.MP_BASE_COLOR), ("rough", MP.MP_ROUGHNESS), ("normal", MP.MP_NORMAL),
                      ("spec", MP.MP_SPECULAR)):
        n = mel.get_material_property_input_node(mat, prop)
        rb["inputs"][key] = n.get_name() if n is not None else None
    missing = sorted(set(SCALARS) - set(rb["scalars"])) + sorted(set(TEXTURE_PARAMS) - set(rb["textures"]))
    _require(not missing, "MASTER_PARAMS_MISSING|%s" % missing)
    _require("OPAQUE" in rb["blend_mode"] and "DEFAULT_LIT" in rb["shading_model"], "MASTER_MODE|%s" % rb)
    _require("COLOR_NORMAL_ROUGHNESS" in rb["decal_response"], "DECAL_RESPONSE|%s" % rb["decal_response"])
    _require(all(rb["inputs"].values()), "MASTER_UNWIRED|%s" % rb["inputs"])
    if shade is not None:
        for k in ("base", "rough", "normal"):
            _require(rb["inputs"][k] == shade.get_name(), "MASTER_WIRE|%s|%s" % (k, rb["inputs"][k]))
        _require(rb["inputs"]["spec"] == spec.get_name(), "MASTER_WIRE|spec")
    return rb


def _mi_scalars(mi, names):
    mel = unreal.MaterialEditingLibrary
    return {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in names}


def create_mi(path, parent, values):
    """CREATE-ONLY instance. Read back parent and every value; refuses if it exists."""
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    _require(not eal.does_asset_exist(path), "MI_EXISTS|" + path)
    mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        path.rsplit("/", 1)[-1], MATDIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    _require(mi is not None, "MI_CREATE_FAILED|" + path)
    mel.set_material_instance_parent(mi, parent)
    for k, v in values.items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    mel.update_material_instance(mi)
    check_mi(mi, parent, values)
    return mi


def check_mi(mi, parent, values):
    _require(_path(mi.get_editor_property("parent")) == _path(parent), "MI_PARENT|%s" % _path(mi))
    got = _mi_scalars(mi, values)
    bad = {k: (got[k], v) for k, v in values.items() if abs(got[k] - float(v)) > 1e-3}
    _require(not bad, "MI_READBACK|%s|%s" % (_path(mi), bad))
    return got


def ensure(look, textures, children=None):
    """Create whatever is missing (never edits an existing asset; existing ones are only CHECKED).
    children: {suffix: {param: value}} for the object frame. Returns (assets, created_paths, readback)."""
    eal = unreal.EditorAssetLibrary
    created, rb = [], {}
    if eal.does_asset_exist(MASTER):
        master = unreal.load_asset(MASTER)
        rb["master"] = readback_master(master)
    else:
        master, rb["master"] = build_master(look, textures)
        created.append(MASTER)
    mi_values = dict(look)
    mi_values.update({"RepeatCm": SCALARS["RepeatCm"][0], "ObjectRelative": 0.0})
    if eal.does_asset_exist(MI):
        mi = unreal.load_asset(MI)
        _require(_path(mi.get_editor_property("parent")) == MASTER, "MI_PARENT_FOREIGN")
        rb["mi"] = _mi_scalars(mi, mi_values)   # existing: report, do not edit
    else:
        mi = create_mi(MI, master, mi_values)
        rb["mi"] = _mi_scalars(mi, mi_values)
        created.append(MI)
    assets = {"master": master, "mi": mi, "children": {}}
    for suffix, vals in sorted((children or {}).items()):
        path = CHILD_PREFIX + suffix
        if eal.does_asset_exist(path):
            child = unreal.load_asset(path)
            check_mi(child, mi, vals)       # stale offsets -> refuse; never edit
        else:
            child = create_mi(path, mi, vals)
            created.append(path)
        assets["children"][suffix] = child
    return assets, created, rb
