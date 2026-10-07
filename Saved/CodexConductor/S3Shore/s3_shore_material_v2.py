"""S3 shore ground material v2 -- create-only anti-tiling sand master + MI.  BUILD_MAT_V2 / DRY_V2.

DRAFT, written 7 Oct 2026 OFFLINE.  NEVER RUN IN UNREAL.  Plan + candidate search:
Docs/Conductor/S3_SAND_TEXTURE_2026-10-07.md.

Gary 7 Oct: "the S3 shore sand looks low-res" -> hi-res search + a 2K fallback.  This file is the fallback:
  * sand sampled at TWO scales (A: SandTileM 1.5 m; B: SandTileM2 4.7 m, rotated SandRot2Deg 37 deg, offset),
    blended by a low-frequency value noise (period BlendNoiseM ~9 m), so the 1.5 m repeat stops reading;
  * macro albedo + roughness variation from a second noise (period MacroNoiseM ~14 m);
  * a detail normal: the sand normal again at DetailTileM 0.35 m, strength DetailNormalStrength (whiteout blend);
  * every texture is a TextureSampleParameter2D, so a hi-res scan is swapped per MI later (v1 parameter names kept);
  * the vertex-colour logic of v1 (R = mud, G = wet + puddle, B = moss) is ported VERBATIM: CODE_TILE / CODE_MUDW /
    CODE_BASE / CODE_ROUGH / CODE_NORMAL are character-identical to s3_shore_ground_ue.py:104-117 (the harness
    asserts it against v1's source, parsed with ast, never imported into the editor).

v1 (M_S3_ShoreGround / MI_S3_ShoreGround) is NEVER touched: new names only, create-only, refuses if either v2 name
exists, refuses on a dirty editor, saves exactly the two v2 packages, and hashes the two v1 .uasset files on disk
before and after (must be identical).

Args Saved/CodexConductor/S3Shore/s3_shore_material_v2_args.json:
  {"mode": "DRY_V2" | "BUILD_MAT_V2", "confirm": "BUILD_MAT_V2 S3SHOREMAT2", "run": "<id>",
   "mi_texture_set": "2K" | "PJUUZ_4K",            # optional; MI overrides from MI_TEXTURE_SETS (default "2K" = none)
   "mi_textures": {"SandAlbedo": "/Game/...", ...}}  # optional; explicit per-parameter MI overrides (win over the set)
  DRY_V2        read-only: loads every texture (master defaults + MI overrides), reports dims/samplers, asset
                existence and census.  Writes s3_shore_material_v2_dry.json.  No confirm needed.
  BUILD_MAT_V2  create-only master + MI, MI texture overrides with sampler-compatibility gate and read-back.

Markers: S3SHOREMAT2_START|run= / S3SHOREMAT2_OK|run=|mode=... / S3SHOREMAT2_FAILED|run=|mode=|reason.
The OK line is logged only after the mode function returned, i.e. after every asserted read-back.
Crash rules (memory puss-mcp-python-crashes-the-editor): no UE object at module level, no deletes at all (memory
ue58-python-material-authoring: never delete nodes; a failed build leaves UNSAVED packages -> Don't-Save restart,
tell the conductor), one build per call + collect_garbage (memory ue58-bulk-import-oom-crash).

Tiers used in comments: [decl] declaration-proven, [bin] binary-proven, [meas] measured, [inf] inferred.
"""
import datetime
import hashlib
import json
import os

try:
    import unreal
except ModuleNotFoundError:  # offline
    unreal = None

PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/S3Shore/"
ARGS = HERE + "s3_shore_material_v2_args.json"
RECORD = HERE + "s3_shore_material_v2_record.json"
DRY_OUT = HERE + "s3_shore_material_v2_dry.json"
ASSET_DIR = "/Game/InfinityStage/Dev/Generated/S3Shore"
MASTER2 = ASSET_DIR + "/M_S3_ShoreGround_v2"
MI2 = ASSET_DIR + "/MI_S3_ShoreGround_v2"
V1_ASSETS = (ASSET_DIR + "/M_S3_ShoreGround", ASSET_DIR + "/MI_S3_ShoreGround")
V1_FILES = tuple(PROJECT + "Content/InfinityStage/Dev/Generated/S3Shore/%s.uasset" % p.rsplit("/", 1)[1]
                 for p in V1_ASSETS)
CONFIRM = "BUILD_MAT_V2 S3SHOREMAT2"

# Master defaults = the 2K textures v1 uses (s3_shore_ground_ue.py:82-91; v1 BUILD_MAT ran and saved 7 Oct [meas:
# s3_shore_ground_record.json.build_mat run S3SHORE-20261007-193358-MAT]).
TEX = {
    "SandAlbedo": "/Game/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/pjuuz_2K_Albedo",
    "SandNormal": "/Game/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/pjuuz_2K_Normal",
    "SandRough": "/Game/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/pjuuz_2K_Roughness",
    "MudAlbedo": "/Game/EnvironmentPacks/Megascans_2K/Surface/09_Soil_Mud_pkbc30/pkbc3_2K_Albedo",
    "MudNormal": "/Game/EnvironmentPacks/Megascans_2K/Surface/09_Soil_Mud_pkbc30/pkbc3_2K_Normal",
    "MudRough": "/Game/EnvironmentPacks/Megascans_2K/Surface/09_Soil_Mud_pkbc30/pkbc3_2K_Roughness",
    "MossAlbedo": "/Game/EnvironmentPacks/MWMeadowWetlands/Textures/Grounds/TEX_MWL_GroundMoss_col",
}
# Texture PARAMETER name -> TEX key.  Same parameter names as v1 (s3_shore_ground_ue.py:102-103) so an MI recipe
# written for one fits the other.
PARAM_TEX = {"SandAlbedo": "SandAlbedo", "SandNormalT": "SandNormal", "SandRoughT": "SandRough",
             "MudAlbedo": "MudAlbedo", "MudNormalT": "MudNormal", "MudRoughT": "MudRough", "MossAlbedo": "MossAlbedo"}

# MI override sets.  PJUUZ_4K = the SAME scans at 4096^2, already in Content [bin: asset-registry tag
# "Dimensions" = 4096x4096 read from each .uasset 7 Oct; compression names TC_Default / TC_Normalmap / TC_Grayscale
# match the 2K maps, so the master's sampler types fit -- the build re-checks live with _sampler_for()].
_P4 = "/Game/EnvironmentPacks/Megascans_4K/Surface/"
MI_TEXTURE_SETS = {
    "2K": {},
    "PJUUZ_4K": {"SandAlbedo": _P4 + "02_Soil_Sand_pjuuz0/pjuuz_4K_Albedo",
                 "SandNormalT": _P4 + "02_Soil_Sand_pjuuz0/pjuuz_4K_Normal",
                 "SandRoughT": _P4 + "02_Soil_Sand_pjuuz0/pjuuz_4K_Roughness",
                 "MudAlbedo": _P4 + "12_Soil_Mud_pkbc30/pkbc3_4K_Albedo",
                 "MudNormalT": _P4 + "12_Soil_Mud_pkbc30/pkbc3_4K_Normal",
                 "MudRoughT": _P4 + "12_Soil_Mud_pkbc30/pkbc3_4K_Roughness"},
}

# Scalar parameters (look values are Gary's; first-pass defaults).  v1's eleven are kept with v1's defaults.
SCALARS = {
    "SandTileM": (1.5, "10 Tiling"), "MudTileM": (2.0, "10 Tiling"), "MossTileM": (1.2, "10 Tiling"),
    "MudBlendContrast": (4.0, "20 Blend"), "MossStrength": (1.0, "20 Blend"),
    "WetDarken": (0.55, "30 Wet"), "WetRoughness": (0.12, "30 Wet"), "PuddleRoughness": (0.04, "30 Wet"),
    "PuddleFromG": (0.85, "30 Wet"), "NormalStrength": (1.0, "40 Normal"), "Specular": (0.5, "40 Normal"),
    # v2 anti-tiling
    "SandTileM2": (4.7, "11 AntiTile"), "SandRot2Deg": (37.0, "11 AntiTile"),
    "SandOffX2": (0.37, "11 AntiTile"), "SandOffY2": (0.61, "11 AntiTile"),
    "BlendNoiseM": (9.0, "11 AntiTile"), "BlendContrast": (2.0, "11 AntiTile"),
    "MacroNoiseM": (14.0, "12 Macro"), "MacroAlbedoAmp": (0.10, "12 Macro"), "MacroRoughAmp": (0.08, "12 Macro"),
    "DetailTileM": (0.35, "13 Detail"), "DetailNormalStrength": (0.4, "13 Detail"),
}

# ---- v1 code, VERBATIM (harness: equals s3_shore_ground_ue.py CODE_* via ast) ----
CODE_TILE = "return UV / max(TileM, 0.01);"
CODE_MUDW = "return saturate((VC.r - 0.5) * C + 0.5);"
CODE_BASE = ("float3 c = lerp(SandC, MudC, M);\n"
             "c = lerp(c, MossC, saturate(VC.b * MossS));\n"
             "return c * lerp(1.0, WetD, saturate(VC.g));")
CODE_ROUGH = ("float r = lerp(SandR, MudR, M);\n"
              "r = lerp(r, 0.85, saturate(VC.b));\n"
              "r = lerp(r, WetR, saturate(VC.g));\n"
              "float p = saturate((VC.g - PF) / max(1.0 - PF, 0.001));\n"
              "return lerp(r, PudR, p);")
CODE_NORMAL = ("float3 n = lerp(SandN, MudN, M);\n"
               "n.xy *= Str;\n"
               "float p = saturate((VC.g - PF) / max(1.0 - PF, 0.001));\n"
               "return normalize(lerp(n, float3(0, 0, 1), p));")

# ---- v2 code (HLSL; [inf] compiles -- not compiled anywhere yet; the build's RECOMPILE gate is the check) ----
# UV B: rotate by +Rot, scale, offset.  The tangent-space normal sampled at UV B must be rotated by -Rot back into
# the surface frame (SH_SandNormal does it); without that, B's lighting direction is off by 37 deg [inf: standard
# derivation, see the doc; verify on a raking-light still].
CODE_TILE_ROT = ("float a = radians(Rot);\n"
                 "float s = sin(a);\n"
                 "float c = cos(a);\n"
                 "float2 r = float2(c * UV.x - s * UV.y, s * UV.x + c * UV.y);\n"
                 "return r / max(TileM, 0.01) + float2(OffX, OffY);")
# Two value-noise fields from UV (metres): x = scale-blend noise (period BlendM), y = macro noise (period MacroM).
# 3 octaves each, sin-hash, smoothstep interpolation; range 0..1.  UV-based (not world) so it rides with the
# rising hangar box exactly like v1's tiling.
CODE_NOISE = ("float2 res = float2(0.5, 0.5);\n"
              "for (int k = 0; k < 2; k++) {\n"
              "  float per = (k == 0) ? max(BlendM, 0.01) : max(MacroM, 0.01);\n"
              "  float2 p = UV / per + float2(17.3, 5.1) * k;\n"
              "  float acc = 0.0;\n"
              "  float amp = 0.5;\n"
              "  float nrm = 0.0;\n"
              "  for (int o = 0; o < 3; o++) {\n"
              "    float2 i = floor(p);\n"
              "    float2 f = frac(p);\n"
              "    float2 u = f * f * (3.0 - 2.0 * f);\n"
              "    float h00 = frac(sin(dot(i, float2(127.1, 311.7))) * 43758.5453);\n"
              "    float h10 = frac(sin(dot(i + float2(1, 0), float2(127.1, 311.7))) * 43758.5453);\n"
              "    float h01 = frac(sin(dot(i + float2(0, 1), float2(127.1, 311.7))) * 43758.5453);\n"
              "    float h11 = frac(sin(dot(i + float2(1, 1), float2(127.1, 311.7))) * 43758.5453);\n"
              "    acc += amp * lerp(lerp(h00, h10, u.x), lerp(h01, h11, u.x), u.y);\n"
              "    nrm += amp;\n"
              "    amp *= 0.5;\n"
              "    p = p * 2.03 + float2(3.7, 1.9);\n"
              "  }\n"
              "  if (k == 0) { res.x = acc / nrm; } else { res.y = acc / nrm; }\n"
              "}\n"
              "return res;")
CODE_SAND_ALBEDO = ("float w = saturate((N.x - 0.5) * BC + 0.5);\n"
                    "float3 c = lerp(CA, CB, w);\n"
                    "return c * (1.0 + MAmp * (N.y - 0.5) * 2.0);")
CODE_SAND_ROUGH = ("float w = saturate((N.x - 0.5) * BC + 0.5);\n"
                   "return saturate(lerp(RA, RB, w) + RAmp * (N.y - 0.5) * 2.0);")
CODE_SAND_NORMAL = ("float w = saturate((N.x - 0.5) * BC + 0.5);\n"
                    "float a = radians(Rot);\n"
                    "float s = sin(a);\n"
                    "float c = cos(a);\n"
                    "float2 b = float2(c * NB.x + s * NB.y, -s * NB.x + c * NB.y);\n"
                    "float3 n = normalize(lerp(NA, float3(b, NB.z), w));\n"
                    "float3 d = ND;\n"
                    "d.xy *= DStr;\n"
                    "return normalize(float3(n.xy + d.xy, n.z * d.z));")

CUSTOM = {   # key: (code, inputs, output type)
    "TileSandA": (CODE_TILE, ["UV", "TileM"], "F2"),
    "TileSandB": (CODE_TILE_ROT, ["UV", "TileM", "Rot", "OffX", "OffY"], "F2"),
    "TileSandD": (CODE_TILE, ["UV", "TileM"], "F2"),
    "TileMud": (CODE_TILE, ["UV", "TileM"], "F2"),
    "TileMoss": (CODE_TILE, ["UV", "TileM"], "F2"),
    "Noise": (CODE_NOISE, ["UV", "BlendM", "MacroM"], "F2"),
    "SH_SandAlbedo": (CODE_SAND_ALBEDO, ["CA", "CB", "N", "BC", "MAmp"], "F3"),
    "SH_SandRough": (CODE_SAND_ROUGH, ["RA", "RB", "N", "BC", "RAmp"], "F1"),
    "SH_SandNormal": (CODE_SAND_NORMAL, ["NA", "NB", "ND", "N", "BC", "Rot", "DStr"], "F3"),
    "MudW": (CODE_MUDW, ["VC", "C"], "F1"),
    "SH_Base": (CODE_BASE, ["SandC", "MudC", "MossC", "M", "VC", "MossS", "WetD"], "F3"),
    "SH_Rough": (CODE_ROUGH, ["SandR", "MudR", "M", "VC", "WetR", "PF", "PudR"], "F1"),
    "SH_Normal": (CODE_NORMAL, ["SandN", "MudN", "M", "Str", "VC", "PF"], "F3"),
}
# Texture sample NODES -> parameter name.  Several nodes share one parameter (SandAlbedo x2, SandNormalT x3,
# SandRoughT x2): UE keeps same-named parameter nodes as ONE parameter when their defaults agree [inf: standard
# material-editor behaviour, not declaration-proven here; the build asserts each name appears once in the MI's
# texture parameter list and that the MI override reads back].
TEX_NODES = {"SandAlbedoA": "SandAlbedo", "SandAlbedoB": "SandAlbedo",
             "SandNormalA": "SandNormalT", "SandNormalB": "SandNormalT", "SandNormalD": "SandNormalT",
             "SandRoughA": "SandRoughT", "SandRoughB": "SandRoughT",
             "MudAlbedo": "MudAlbedo", "MudNormalT": "MudNormalT", "MudRoughT": "MudRoughT", "MossAlbedo": "MossAlbedo"}
FIXED_NODES = {"UV0": ("MaterialExpressionTextureCoordinate", {"coordinate_index": 0}),
               "VC": ("MaterialExpressionVertexColor", {})}
EDGES = [
    # tiling
    ("UV0", "", "TileSandA", "UV"), ("SandTileM", "", "TileSandA", "TileM"),
    ("UV0", "", "TileSandB", "UV"), ("SandTileM2", "", "TileSandB", "TileM"), ("SandRot2Deg", "", "TileSandB", "Rot"),
    ("SandOffX2", "", "TileSandB", "OffX"), ("SandOffY2", "", "TileSandB", "OffY"),
    ("UV0", "", "TileSandD", "UV"), ("DetailTileM", "", "TileSandD", "TileM"),
    ("UV0", "", "TileMud", "UV"), ("MudTileM", "", "TileMud", "TileM"),
    ("UV0", "", "TileMoss", "UV"), ("MossTileM", "", "TileMoss", "TileM"),
    ("UV0", "", "Noise", "UV"), ("BlendNoiseM", "", "Noise", "BlendM"), ("MacroNoiseM", "", "Noise", "MacroM"),
    # samples
    ("TileSandA", "", "SandAlbedoA", "UVs"), ("TileSandB", "", "SandAlbedoB", "UVs"),
    ("TileSandA", "", "SandNormalA", "UVs"), ("TileSandB", "", "SandNormalB", "UVs"), ("TileSandD", "", "SandNormalD", "UVs"),
    ("TileSandA", "", "SandRoughA", "UVs"), ("TileSandB", "", "SandRoughB", "UVs"),
    ("TileMud", "", "MudAlbedo", "UVs"), ("TileMud", "", "MudNormalT", "UVs"), ("TileMud", "", "MudRoughT", "UVs"),
    ("TileMoss", "", "MossAlbedo", "UVs"),
    # sand mixes
    ("SandAlbedoA", "RGB", "SH_SandAlbedo", "CA"), ("SandAlbedoB", "RGB", "SH_SandAlbedo", "CB"),
    ("Noise", "", "SH_SandAlbedo", "N"), ("BlendContrast", "", "SH_SandAlbedo", "BC"),
    ("MacroAlbedoAmp", "", "SH_SandAlbedo", "MAmp"),
    ("SandRoughA", "R", "SH_SandRough", "RA"), ("SandRoughB", "R", "SH_SandRough", "RB"),
    ("Noise", "", "SH_SandRough", "N"), ("BlendContrast", "", "SH_SandRough", "BC"),
    ("MacroRoughAmp", "", "SH_SandRough", "RAmp"),
    ("SandNormalA", "RGB", "SH_SandNormal", "NA"), ("SandNormalB", "RGB", "SH_SandNormal", "NB"),
    ("SandNormalD", "RGB", "SH_SandNormal", "ND"), ("Noise", "", "SH_SandNormal", "N"),
    ("BlendContrast", "", "SH_SandNormal", "BC"), ("SandRot2Deg", "", "SH_SandNormal", "Rot"),
    ("DetailNormalStrength", "", "SH_SandNormal", "DStr"),
    # v1 vertex-colour logic (same pins as s3_shore_ground_ue.py:138-147; sand inputs now come from the mixes)
    ("VC", "", "MudW", "VC"), ("MudBlendContrast", "", "MudW", "C"),
    ("SH_SandAlbedo", "", "SH_Base", "SandC"), ("MudAlbedo", "RGB", "SH_Base", "MudC"),
    ("MossAlbedo", "RGB", "SH_Base", "MossC"), ("MudW", "", "SH_Base", "M"), ("VC", "", "SH_Base", "VC"),
    ("MossStrength", "", "SH_Base", "MossS"), ("WetDarken", "", "SH_Base", "WetD"),
    ("SH_SandRough", "", "SH_Rough", "SandR"), ("MudRoughT", "R", "SH_Rough", "MudR"), ("MudW", "", "SH_Rough", "M"),
    ("VC", "", "SH_Rough", "VC"), ("WetRoughness", "", "SH_Rough", "WetR"), ("PuddleFromG", "", "SH_Rough", "PF"),
    ("PuddleRoughness", "", "SH_Rough", "PudR"),
    ("SH_SandNormal", "", "SH_Normal", "SandN"), ("MudNormalT", "RGB", "SH_Normal", "MudN"),
    ("MudW", "", "SH_Normal", "M"), ("NormalStrength", "", "SH_Normal", "Str"), ("VC", "", "SH_Normal", "VC"),
    ("PuddleFromG", "", "SH_Normal", "PF"),
]
PROPS = [("SH_Base", "", "MP_BASE_COLOR"), ("SH_Rough", "", "MP_ROUGHNESS"), ("SH_Normal", "", "MP_NORMAL"),
         ("Specular", "", "MP_SPECULAR")]


def graph_spec():
    """Logical graph of M_S3_ShoreGround_v2 (pure data; checked by graph_problems())."""
    nodes = {k: ("scalar", v) for k, v in SCALARS.items()}
    nodes.update({k: ("texture", p) for k, p in TEX_NODES.items()})
    nodes.update({k: ("fixed", v) for k, v in FIXED_NODES.items()})
    nodes.update({k: ("custom", v) for k, v in CUSTOM.items()})
    return nodes, list(EDGES), list(PROPS)


def _code_problems(key, code, ins):
    probs = []
    if code.count("{") != code.count("}") or code.count("(") != code.count(")"):
        probs.append("CUSTOM_UNBALANCED|%s" % key)
    if "return" not in code:
        probs.append("CUSTOM_NO_RETURN|%s" % key)
    import re
    for pin in ins:
        if not re.search(r"\b%s\b" % re.escape(pin), code):
            probs.append("CUSTOM_PIN_UNUSED_IN_CODE|%s.%s" % (key, pin))
    return probs


def graph_problems(spec=None):
    nodes, edges, props = spec if spec is not None else graph_spec()
    probs = []
    for s, _o, d, _pin in edges:
        if s not in nodes or d not in nodes:
            probs.append("EDGE_NODE|%s->%s" % (s, d))
    seen = {}
    for s, _o, d, pin in edges:
        seen.setdefault((d, pin), []).append(s)
    for (d, pin), srcs in seen.items():
        if len(srcs) != 1:
            probs.append("PIN_FED_TWICE|%s.%s|%s" % (d, pin, srcs))
        kind = nodes.get(d, ("?",))[0]
        if kind == "custom" and pin not in nodes[d][1][1]:
            probs.append("CUSTOM_PIN_UNKNOWN|%s.%s" % (d, pin))
        if kind == "texture" and pin != "UVs":
            probs.append("TEXTURE_PIN|%s.%s" % (d, pin))
        if kind in ("scalar", "fixed"):
            probs.append("INPUT_INTO_LEAF|%s.%s" % (d, pin))
    for k, (kind, v) in nodes.items():
        if kind == "custom":
            code, ins, _t = v
            for pin in ins:
                if (k, pin) not in seen:
                    probs.append("CUSTOM_PIN_UNFED|%s.%s" % (k, pin))
            probs.extend(_code_problems(k, code, ins))
        if kind == "texture":
            if (k, "UVs") not in seen:
                probs.append("TEXTURE_UV_UNFED|%s" % k)
            if v not in PARAM_TEX:
                probs.append("TEXTURE_PARAM_UNKNOWN|%s|%s" % (k, v))
    used = {e[0] for e in edges} | {p[0] for p in props}
    for k in nodes:
        if k not in used:
            probs.append("UNUSED_NODE|%s" % k)
    if sorted(p[2] for p in props) != sorted(["MP_BASE_COLOR", "MP_ROUGHNESS", "MP_NORMAL", "MP_SPECULAR"]):
        probs.append("PROPS")
    # cycle check (Custom chains must be a DAG)
    adj = {}
    for s, _o, d, _p in edges:
        adj.setdefault(s, set()).add(d)
    state = {}

    def visit(n):
        if state.get(n) == 1:
            return True
        if state.get(n) == 2:
            return False
        state[n] = 1
        cyc = any(visit(m) for m in adj.get(n, ()))
        state[n] = 2
        return cyc
    if any(visit(n) for n in list(nodes)):
        probs.append("CYCLE")
    # every parameter used by a texture node needs a default texture
    for p in set(TEX_NODES.values()):
        if PARAM_TEX.get(p) not in TEX:
            probs.append("PARAM_NO_DEFAULT|%s" % p)
    # name clash between scalar and texture parameter names would make one parameter of two types
    clash = set(SCALARS) & set(PARAM_TEX)
    if clash:
        probs.append("PARAM_NAME_CLASH|%s" % sorted(clash))
    return probs


def mi_overrides(args):
    """Resolve MI texture overrides: the named set, then explicit per-parameter paths on top."""
    name = args.get("mi_texture_set", "2K")
    if name not in MI_TEXTURE_SETS:
        raise RuntimeError("MI_TEXTURE_SET_UNKNOWN|%s" % name)
    out = dict(MI_TEXTURE_SETS[name])
    out.update(args.get("mi_textures") or {})
    bad = sorted(k for k in out if k not in PARAM_TEX)
    if bad:
        raise RuntimeError("MI_TEXTURE_PARAM_UNKNOWN|%s" % bad)
    return out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def v1_hashes():
    return {p: (sha256_file(p) if os.path.isfile(p) else None) for p in V1_FILES}


# ----------------------------------------------------------------------------- editor helpers
def _require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def _write(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as h:
        json.dump(value, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def _enum_name(v):
    s = str(v)
    return s.split(".")[-1].split(":")[0].strip("<> ").upper()


def _sampler_for(tex):
    """Same mapping as v1 (s3_shore_ground_ue.py:414-425); LINEAR_GRAYSCALE for non-sRGB grayscale (memory)."""
    comp = _enum_name(tex.get_editor_property("compression_settings"))
    srgb = bool(tex.get_editor_property("srgb"))
    if comp == "TC_NORMALMAP":
        return "SAMPLERTYPE_NORMAL"
    if comp == "TC_MASKS":
        return "SAMPLERTYPE_MASKS"
    if comp in ("TC_GRAYSCALE", "TC_ALPHA", "TC_DISPLACEMENTMAP"):
        return "SAMPLERTYPE_GRAYSCALE" if srgb else "SAMPLERTYPE_LINEAR_GRAYSCALE"
    if comp in ("TC_DEFAULT", "TC_BC7"):
        return "SAMPLERTYPE_COLOR" if srgb else "SAMPLERTYPE_LINEAR_COLOR"
    raise RuntimeError("SAMPLER_UNMAPPED|%s|srgb=%s" % (comp, srgb))


def _load_tex(path):
    t = unreal.load_asset(path)
    _require(isinstance(t, unreal.Texture2D), "TEXTURE_MISSING|" + path)
    return t


def _tex_info(t):
    # Texture2D.h:361 Blueprint_GetSizeX [decl]; reported only, never gated (platform data may be unloaded [inf])
    return {"path": str(t.get_path_name()), "size": [int(t.blueprint_get_size_x()), int(t.blueprint_get_size_y())],
            "sampler": _sampler_for(t)}


def _texture_plan(args):
    """Load master defaults + MI overrides; refuse an override whose sampler type differs from the default's
    (the master node's sampler type is fixed at build; a mismatch fails compile -- memory LINEAR_GRAYSCALE)."""
    defaults = {p: _load_tex(TEX[k]) for p, k in PARAM_TEX.items()}
    over = {}
    for p, path in mi_overrides(args).items():
        t = _load_tex(path)
        want, got = _sampler_for(defaults[p]), _sampler_for(t)
        _require(want == got, "MI_OVERRIDE_SAMPLER|%s|default=%s|override=%s|%s" % (p, want, got, path))
        over[p] = t
    return defaults, over


def run_dry(run, args):
    eal = unreal.EditorAssetLibrary
    defaults, over = _texture_plan(args)
    out = {"run": run, "utc": datetime.datetime.utcnow().isoformat() + "Z", "census": _census(),
           "graph_problems": graph_problems(),
           "exists": {p: bool(eal.does_asset_exist(p)) for p in (MASTER2, MI2) + V1_ASSETS},
           "defaults": {p: _tex_info(t) for p, t in defaults.items()},
           "mi_overrides": {p: _tex_info(t) for p, t in over.items()},
           "v1_sha256": v1_hashes()}
    _write(DRY_OUT, out)
    return out


def run_build_mat_v2(run, args):
    """Create-only master + MI.  Pattern = v1 run_build_mat (s3_shore_ground_ue.py:428-520), which ran and saved.
    No delete call anywhere in this file."""
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    _require(_census() == {"content": [], "maps": []}, "DIRTY_EDITOR|%s" % _census())
    gp = graph_problems()
    _require(not gp, "GRAPH_SPEC|%s" % gp)
    for p in (MASTER2, MI2):
        _require(not eal.does_asset_exist(p), "EXISTS|" + p)
    _require(MASTER2 not in V1_ASSETS and MI2 not in V1_ASSETS, "NAME_IS_V1")
    v1_before = v1_hashes()
    folder_before = set(str(n).split(".")[0] for n in eal.list_assets(ASSET_DIR, recursive=True)) \
        if eal.does_directory_exist(ASSET_DIR) else set()
    defaults, over = _texture_plan(args)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(MASTER2.rsplit("/", 1)[1], ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())
    _require(mat is not None, "MASTER_CREATE")
    mat.modify()
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("used_with_nanite", True)                              # Material.h:863 bUsedWithNanite
    nodes, edges, props = graph_spec()
    made = {}
    otypes = {"F1": unreal.CustomMaterialOutputType.CMOT_FLOAT1, "F2": unreal.CustomMaterialOutputType.CMOT_FLOAT2,
              "F3": unreal.CustomMaterialOutputType.CMOT_FLOAT3}
    for i, (key, (kind, v)) in enumerate(nodes.items()):
        if kind == "scalar":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -2600, -1200 + 70 * i)
            _require(n is not None, "CREATE_NODE|" + key)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("default_value", float(v[0]))
            n.set_editor_property("group", v[1])
        elif kind == "texture":
            tex = defaults[v]
            n = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D,
                                               -1500, -1200 + 260 * i)
            _require(n is not None, "CREATE_NODE|" + key)
            n.set_editor_property("parameter_name", v)                    # shared names: see TEX_NODES note
            n.set_editor_property("texture", tex)
            n.set_editor_property("sampler_type", getattr(unreal.MaterialSamplerType, _sampler_for(tex)))
            n.set_editor_property("group", "00 Textures")
            n.set_editor_property("desc", key)                            # MaterialExpression.h:195 Desc [decl]
        elif kind == "fixed":
            cls_name, pp = v
            n = mel.create_material_expression(mat, getattr(unreal, cls_name), -2200, 200 + 120 * i)
            _require(n is not None, "CREATE_NODE|" + key)
            for k2, v2 in pp.items():
                n.set_editor_property(k2, v2)
        else:
            code, ins, otype = v
            n = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -900, -1200 + 200 * i)
            _require(n is not None, "CREATE_NODE|" + key)
            n.set_editor_property("description", key)
            n.set_editor_property("code", code)
            n.set_editor_property("output_type", otypes[otype])
            cis = []
            for name in ins:
                ci = unreal.CustomInput()
                ci.set_editor_property("input_name", name)
                cis.append(ci)
            n.set_editor_property("inputs", cis)
            got = [str(c.get_editor_property("input_name")) for c in n.get_editor_property("inputs")]
            _require(got == list(ins), "CUSTOM_INPUTS|%s|%s" % (key, got))
            _require(str(n.get_editor_property("code")) == code, "CUSTOM_CODE_READBACK|" + key)
        made[key] = n
    for s, o, d, pin in edges:
        ok = mel.connect_material_expressions(made[s], o, made[d], pin)
        _require(ok, "LINK|%s.%s->%s.%s|inputs=%s" % (s, o, d, pin,
                                                     [str(x) for x in mel.get_material_expression_input_names(made[d])]))
    for s, o, prop in props:
        _require(mel.connect_material_property(made[s], o, getattr(unreal.MaterialProperty, prop)), "PROP|" + prop)
    errors = [str(e) for e in (mel.recompile_material(mat) or [])]
    _require(not errors, "RECOMPILE|%s" % errors)
    _require(bool(mat.get_editor_property("used_with_nanite")), "NANITE_USAGE_READBACK")
    n_expr = len(mel.get_material_expressions(mat)) if hasattr(mel, "get_material_expressions") else None  # :141
    _require(n_expr in (None, len(made)), "EXPRESSION_COUNT|%s!=%d" % (n_expr, len(made)))
    mi = tools.create_asset(MI2.rsplit("/", 1)[1], ASSET_DIR, unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    _require(mi is not None, "MI_CREATE")
    mi.modify()
    mel.set_material_instance_parent(mi, mat)
    _require(mi.get_editor_property("parent") == mat, "MI_PARENT")
    tex_names = [str(x) for x in mel.get_texture_parameter_names(mat)]   # MaterialEditingLibrary.h:510, out-param [decl]
    _require(sorted(tex_names) == sorted(PARAM_TEX), "TEXTURE_PARAMS|%s" % tex_names)  # shared names collapsed once
    for p, t in over.items():
        mel.set_material_instance_texture_parameter_value(mi, p, t)   # bool LIES (memory): read back below
    mel.update_material_instance(mi)
    tex_read = {}
    for p in PARAM_TEX:                                     # MaterialEditingLibrary.h:426 [decl]
        t = mel.get_material_instance_texture_parameter_value(mi, p)
        tex_read[p] = str(t.get_path_name()) if t is not None else None
    for p in PARAM_TEX:
        want = over[p] if p in over else defaults[p]
        _require(tex_read[p] == str(want.get_path_name()), "MI_TEXTURE_READBACK|%s|%s" % (p, tex_read[p]))
    scal = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in SCALARS}
    bad = {k: v for k, v in scal.items() if abs(v - SCALARS[k][0]) > 1e-4}
    _require(not bad, "MI_DEFAULTS|%s" % bad)
    planned = sorted([MASTER2, MI2])
    _require(_census() == {"content": planned, "maps": []}, "DIRTY_SCOPE|%s" % _census())
    folder_after = set(str(n).split(".")[0] for n in eal.list_assets(ASSET_DIR, recursive=True))
    _require(sorted(folder_after - folder_before) == planned, "STRAY_ASSETS|%s" % sorted(folder_after - folder_before))
    for p in planned:
        _require(eal.save_asset(p, only_if_is_dirty=False), "SAVE|" + p)
    _require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    v1_after = v1_hashes()
    _require(v1_after == v1_before, "V1_CHANGED|%s" % v1_after)
    unreal.SystemLibrary.collect_garbage()                       # memory ue58-bulk-import-oom-crash
    rec = {"run": run, "master": MASTER2, "mi": MI2, "nodes": len(made), "edges": len(edges), "scalars": scal,
           "mi_texture_set": args.get("mi_texture_set", "2K"), "mi_textures": tex_read,
           "samplers": {p: _sampler_for(t) for p, t in defaults.items()},
           "v1_sha256": v1_after, "saved": True}
    _write(RECORD, rec)
    return rec


def main():
    """Entry for ExecuteProjectPythonFile.  Everything inside functions (crash rule 4)."""
    mode, run = "", "S3SHOREMAT2-unknown"
    try:
        args = json.load(open(ARGS, encoding="utf-8"))
        mode = str(args.get("mode") or "")
        run = args.get("run") or "S3SHOREMAT2-" + datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        unreal.log("S3SHOREMAT2_START|run=%s|mode=%s" % (run, mode))
        if mode == "DRY_V2":
            out = run_dry(run, args)
            unreal.log("S3SHOREMAT2_OK|run=%s|mode=DRY_V2|exists=%s|graph_problems=%d|census=%s|out=%s" % (
                run, json.dumps(out["exists"]), len(out["graph_problems"]), json.dumps(out["census"]), DRY_OUT))
        elif mode == "BUILD_MAT_V2":
            _require(args.get("confirm") == CONFIRM, "CONFIRM_MISSING|needs confirm=%r" % CONFIRM)
            out = run_build_mat_v2(run, args)
            unreal.log("S3SHOREMAT2_OK|run=%s|mode=BUILD_MAT_V2|nodes=%d|edges=%d|set=%s|record=%s" % (
                run, out["nodes"], out["edges"], out["mi_texture_set"], RECORD))
        else:
            raise RuntimeError("MODE_NOT_ENABLED|%s" % mode)
    except Exception as exc:  # noqa: BLE001
        unreal.log_error("S3SHOREMAT2_FAILED|run=%s|mode=%s|%r" % (run, mode, exc))


if unreal is not None and not getattr(unreal, "_S3SHOREMAT2_FAKE", False):
    main()
