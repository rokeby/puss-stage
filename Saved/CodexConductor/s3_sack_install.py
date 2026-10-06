"""S3 sackcloth: import the six skinned sacks, build the hessian materials, and put the sacks on the placed shore
figures as LEVEL-INSTANCE components that follow the body (leader pose), hiding the live Chaos head drapes.
Written 6 Oct 2026, OFFLINE (Unreal not run, MCP not called). Plan: Docs/Conductor/S3_SACKCLOTH_PLAN_2026-10-06.md
sections 8.4 (UE plan) and 10 (finals).

Args Saved/CodexConductor/s3_sack_install_args.json:
  {"mode": "DRY"|"IMPORT"|"BUILD_MAT"|"APPLY"|"REVERT"|"VERIFY", "confirm": "<MODE> S3SACK",
   "figures": [...],                 # default all six; IMPORT/APPLY may pilot a subset (APPLY: one record per apply)
   "fbx_suffix": "_SK_root.fbx",     # the re-exported finals (Tools/S3Sackcloth/reexport_sk_root.py); see ROOT BONE
   "cloth_switch": "suspend+disable",# or "suspend" (the measured switch alone, ChaosClothCurtain.md:605-608)
   "bounds_scale": 1.25,             # SackSK bounds: the mesh's own ref-pose bounds, padded for the body's sway
   "pow2_mode": "STRETCH_TO_POWER_OF_TWO"}   # the hessian PNGs are 2048 x 2036 (NPOT)

Modes (write modes need the confirm string; every write mode refuses on a dirty editor and saves census-exact):
  DRY        read-only. Sources (JSON gates, FBX structure, sha256), live actors/components/skeleton/bone trees,
             cloth state, skin-pass overrides, target paths, API presence, what each write mode would save.
  IMPORT     the figures' sack FBXs -> /Game/Metahuman/ShoreCast_20260910/Sack/SKM_Sack_<id> as skeletal meshes ON
             THE EXISTING metahuman_base_skel (Interchange pipeline override: no skeleton, no physics asset, no
             materials/textures/animations/morphs, no skeleton ref-pose update). Refuses before importing if the FBX
             is not rooted at the skeleton's root bone; refuses before saving if the mesh's skeleton is not the body's,
             if ANY other asset appeared (a new skeleton/physics asset/material = stray), or if the skeleton package
             went dirty. Read back: LOD count, render vertex count, bone tree, slots Front/Back/Edge, bounds.
  BUILD_MAT  create-only: 6 textures (Sack/Textures), M_Sackcloth (opaque), M_Sackcloth_Masked (+ fringe opacity from
             UV1.x), MI_Sackcloth_OldGrey and MI_Sackcloth_OldGrey_Inner (both children of the MASKED master: the
             fringe is on every slot, plan 10.3). Every edge, parameter, flag and MI value is read back.
  APPLY      route 3 (see the APPLY / REVERT section header for why). Phase 1 reads EVERYTHING for every figure
             and asserts the census unchanged; then backup the umap; then (a) ShoreHeadCloth on every figure: visible
             false, hidden in game, suspend on, simulation off, one set_editor_property at a time on a freshly found
             component; (b) per figure spawn BP_S3SackFollower "<id> Sack" (tags S3.Sack, S3.Sack.<id>) at the Body's
             world transform, mesh / slot MIs / bounds scale by property, attach to Body (KEEP_WORLD), rerun its
             construction script (RelinkLeader: SetLeaderPoseComponent on the attach parent named "Body"). Body/Face
             (the skin pass's level overrides, S3SKIN-20261006-134520) must not change. Figure BPs are never edited.
  PIE_PROBE  read-only, only while Gary's PIE runs: every sack led by its figure's Body in the game world (the
             persistence proof: PIE is a fresh copy of the SAVED level), cloth hidden and suspended.
  REVERT     exact inverse from the record (refuses on drift, or if the sack actor is not the recorded one): lookups
             first, then destroy the tagged sack actors and restore the cloth flags; save the map. Assets stay.
  VERIFY     read-only: every record's end state (meshes, materials, attachment, leader pose resolving to the CURRENT
             Body, bone names, hidden cloth, skin overrides intact). Run it again after an editor RESTART: the leader
             pointer's persistence across reload/reconstruction is UNPROVEN (see PERSISTENCE).

ROOT BONE (measured 6 Oct, fbx_skeleton_summary below on the files): UE's own body export is Z-up with a "root"
  (FBX Root) node over "pelvis"; the Blender finals <id>_SK.fbx are Y-up with a Null "Armature" over "pelvis" and no
  "root". The figures' skeleton is rooted at "root", so the finals are expected to be refused by, or to fork, the
  skeleton [inferred; the compatibility .cpp is absent from the UE 5.8 install]. IMPORT therefore reads
  <id>_SK_root.fbx (same mesh/weights/bind, armature renamed "root", Root node, Z-up) and gates its structure.

PERSISTENCE (route 3): the sack is a BP_S3SackFollower whose construction script and BeginPlay re-link it
  (RelinkLeader). PIE_PROBE is the proof in a fresh world. Background: SkinnedMeshComponent.LeaderPoseComponent is a UPROPERTY(BlueprintReadOnly) TWeakObjectPtr
  (Engine/Classes/Components/SkinnedMeshComponent.h:313-314), so it is serialized with the level [decl]. Whether it
  survives the figure BP's construction-script rerun on load (ConfigureShoreDrape runs on construction and BeginPlay,
  Docs/ShoreCast-20260910.md:84), which may replace the Body component object, is [inferred, unproven]; the same holds
  for the actor attachment. VERIFY checks both resolve to the CURRENT Body. Fallbacks if a post-restart VERIFY fails:
  see the conductor report (re-link at construction/BeginPlay, not implemented).

Markers: S3SACK_START / S3SACK_PLAN / S3SACK_<MODE>_OK|run=.. / S3SACK_FAILED|run=..
Offline: importing this file without `unreal` defines only the pure helpers (harness test_s3_sack_install_offline.py).
Crash rules: no UE object at module level; all editor work inside functions.
"""
import datetime
import hashlib
import json
import math
import os
import shutil
import struct

try:
    import unreal
except ModuleNotFoundError:  # offline harness / Blender
    unreal = None

PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/"
ARGS = HERE + "s3_sack_install_args.json"
RECORDS = {"IMPORT": HERE + "s3_sack_install_import_record.json",
           "BUILD_MAT": HERE + "s3_sack_install_mat_record.json",
           "APPLY": HERE + "s3_sack_install_apply_record.json"}
DRY_OUT = HERE + "s3_sack_install_dry.json"
PIE_OUT = HERE + "s3_sack_install_pie_probe.json"
VERIFY_OUT = HERE + "s3_sack_install_verify.json"
BACKUP_ROOT = PROJECT + "Backups/PreS3Sack-"
CONTENT = PROJECT + "Content/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = CONTENT + "InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
ROOT = "/Game/Metahuman/ShoreCast_20260910"
SACK_DIR = ROOT + "/Sack"
TEX_DIR = SACK_DIR + "/Textures"
MAT_DIR = SACK_DIR + "/Materials"
FINALS = PROJECT + "DerivedAssets/S3Sackcloth/final_20261006/"
TEX_SRC = PROJECT + "DerivedAssets/S3Sackcloth/textures/hessian_230/"
EXPORT_MANIFEST = PROJECT + "DerivedAssets/S3Sackcloth/bodies/export_manifest.json"
SKIN_RECORD = HERE + "s3_shore_skin_record.json"
SKELETON = ROOT + "/Assembled/Common/Female/Medium/NormalWeight/Body/metahuman_base_skel"   # export manifest, all six
ROOT_BONE, FIRST_CHILD = "root", "pelvis"
CONFIRM_WORD = "S3SACK"
WRITE_MODES = ("IMPORT", "BUILD_MAT", "APPLY", "REVERT")
MODES = ("DRY", "VERIFY", "PIE_PROBE") + WRITE_MODES
SACK_COMPONENT, CLOTH_COMPONENT, BODY, FACE = "SackSK", "ShoreHeadCloth", "Body", "Face"   # SackSK: legacy route
SACK_TAG = "S3.Sack"
SACK_BP = SACK_DIR + "/BP_S3SackFollower"                 # authored by s3_sack_follower_bp_*.json (MCP generator)
SACK_BP_CLASS_NAME = "BP_S3SackFollower_C"
# cloth state key -> UPROPERTY python name: bVisible SceneComponent.h:182-183 (EditAnywhere), bHiddenInGame :225-226,
# bSuspendSimulation / bEnableSimulation ClothComponent.h:462-463 / 458-459 (Interp). Written AND read as properties.
CLOTH_PROPS = (("visible", "visible"), ("hidden_in_game", "hidden_in_game"), ("suspended", "suspend_simulation"),
               ("enabled", "enable_simulation"))
TOL = 1e-3

FIGURES = ("Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore05_M53", "Shore06_F25")
# Gary's decisions (plan 10.1 + conductor 6 Oct): upright four + Shore06 at 2.0 m pinned 20 cm forward; Shore02 at
# 2.0 m on the back pin (the "alt2p0" final). The source JSON's own args must agree, or the source is refused.
SOURCE_ID = {f: f + "_Sack" for f in FIGURES}
SOURCE_ID["Shore02_F52"] = "Shore02_F52_Sack_alt2p0"
DECISION = {f: {"size_x": 2.0, "size_y": 2.0, "crown": "head", "pin_forward": 0.2} for f in FIGURES}
DECISION["Shore02_F52"] = {"size_x": 2.0, "size_y": 2.0, "crown": "back", "pin_forward": 0.0}
DEFAULT_FBX_SUFFIX = "_SK_root.fbx"
SLOT_ROLES = ("Front", "Back", "Edge")

# ------------------------------------------------------------------------------------------------ textures
# key: (source map, asset name, compression, sRGB). Poly Haven hessian_230 2k (manifest.json sha256 checked).
# rough/ao/disp are 16-bit PNG (I;16, measured with PIL 6 Oct): TC_GRAYSCALE keeps G16 per TextureDefines.h:396
# ("Grayscale (G8/16) from source R") [decl]; whether the source really lands as G16 is read back only if the
# asset registry exposes it (UNCLEAR otherwise). NormalDX = UE convention: no green flip.
TEXTURES = {
    "BC": ("diff", "T_Sack_Hessian230_BC", "TC_DEFAULT", True),
    "N": ("nor_dx", "T_Sack_Hessian230_N", "TC_NORMALMAP", False),
    "R": ("rough", "T_Sack_Hessian230_R", "TC_GRAYSCALE", False),
    "AO": ("ao", "T_Sack_Hessian230_AO", "TC_GRAYSCALE", False),
    "H": ("disp", "T_Sack_Hessian230_H", "TC_GRAYSCALE", False),
    "Mask": ("mask", "T_Sack_Hessian230_Mask", "TC_GRAYSCALE", False),   # weave gaps; for a later see-through bench
}

# ------------------------------------------------------------------------------------------------ materials
M_OPAQUE, M_MASKED = MAT_DIR + "/M_Sackcloth", MAT_DIR + "/M_Sackcloth_Masked"
MI_OUTER, MI_INNER = MAT_DIR + "/MI_Sackcloth_OldGrey", MAT_DIR + "/MI_Sackcloth_OldGrey_Inner"
SLOT_MI = {"Front": MI_OUTER, "Back": MI_INNER, "Edge": MI_OUTER}   # plan 8.4 item 2 "Slots"
# name: (default, group). Defaults are the neutral hessian; the "old grey" look lives in the MIs.
SCALARS = {
    "TileM": (0.269, "01 Mapping"),             # hessian_230 real-world tile (268.75 x 267.2 mm); UV0 is metres
    "MottleScaleM": (0.5, "02 Colour"),
    "MottleAmount": (0.08, "02 Colour"),
    "Desaturate": (0.0, "02 Colour"),
    "InnerDarken": (1.0, "02 Colour"),
    "HemGrimeHeightM": (0.35, "03 Grime"),      # metres above the component origin (the figure's feet)
    "HemGrimeFalloffM": (0.25, "03 Grime"),
    "HemGrimeAmount": (1.0, "03 Grime"),
    "EdgeGrimeWidthM": (0.03, "03 Grime"),      # UV1.x = distance to the cut edge, metres (build_sackcloth.py:28)
    "EdgeGrimeAmount": (0.6, "03 Grime"),
    "RoughnessScale": (1.0, "04 Surface"),
    "NormalStrength": (1.0, "04 Surface"),
    "Specular": (0.3, "04 Surface"),
    "RimAmount": (0.06, "05 Rim"),
    "RimExponent": (4.0, "05 Rim"),
}
MASKED_SCALARS = {                               # plan 10.3: alpha = (UV1.x / 1.5 cm + 0.9 (noise - 0.5)) > 0.45
    "FringeWidthM": (0.015, "06 Fringe"),
    "FringeNoiseAmount": (0.9, "06 Fringe"),
    "FringeThreshold": (0.45, "06 Fringe"),
}
VECTORS = {
    "Tint": ((1.0, 1.0, 1.0), "02 Colour"),
    "GrimeColor": ((0.10, 0.09, 0.08), "03 Grime"),
    "RimColor": ((0.55, 0.50, 0.40), "05 Rim"),   # pale straw: loose-fibre glint at grazing light
}
TEX_PARAMS = {"BaseColorTexture": "BC", "NormalTexture": "N", "RoughnessTexture": "R", "AOTexture": "AO"}
MASKED_TEX_PARAMS = {"HeightTexture": "H"}       # the weave height drives the fringe "noise" (threads, few mm)
MASK_CLIP = 0.5
# "Old grey worn sack" (Gary 6 Oct; plan 8.4 item 3). Starting points [inf]; Gary judges stills.
MI_VALUES = {
    MI_OUTER: {"scalars": {"Desaturate": 0.75, "MottleAmount": 0.10, "HemGrimeHeightM": 0.35, "EdgeGrimeWidthM": 0.03,
                           "EdgeGrimeAmount": 0.6, "RoughnessScale": 1.0, "NormalStrength": 1.0, "RimAmount": 0.05},
               "vectors": {"Tint": (0.62, 0.60, 0.56), "GrimeColor": (0.10, 0.09, 0.08)}},
    MI_INNER: {"scalars": {"Desaturate": 0.75, "MottleAmount": 0.10, "HemGrimeHeightM": 0.35, "EdgeGrimeWidthM": 0.03,
                           "EdgeGrimeAmount": 0.6, "RoughnessScale": 1.0, "NormalStrength": 0.6, "RimAmount": 0.05,
                           "InnerDarken": 0.7},
               "vectors": {"Tint": (0.62, 0.60, 0.56), "GrimeColor": (0.10, 0.09, 0.08)}},
}
MI_PARENT = M_MASKED

CODE_TILE = "return UV / max(TileM, 1e-4);"
CODE_MOTTLE = """// Low-frequency value noise on the flat-fabric metres (UV0), offset per piece by UV1.y: it rides the cloth
// (a world-position mottle would swim as the body sways).
float2 p = UV0 / max(ScaleM, 1e-3) + UV1.y * 37.0;
float acc = 0.0;
float amp = 0.5;
float norm = 0.0;
for (int k = 0; k < 3; k++)
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
CODE_BASE = """// Hessian albedo: mottle, desaturate, tint, hem + torn-edge grime, inner-face darken, weak grazing rim.
float m = (Mottle - 0.5) * 2.0 * MottleAmt;
float3 col = BC * max(1.0 + m, 0.0);
float l = dot(col, float3(0.2126, 0.7152, 0.0722));
col = lerp(col, float3(l, l, l), saturate(Desat));
col *= Tint;
float zr = (WPc.z - OPc.z) * 0.01;                       // metres above the component origin (feet)
float hem = saturate((HemH - zr) / max(HemFall, 1e-3)) * HemAmt;
float edge = (1.0 - saturate(UV1.x / max(EdgeW, 1e-4))) * EdgeAmt;
col = lerp(col, GrimeCol, saturate(max(hem, edge)));
col *= Inner;
col += Fres * RimAmt * RimCol;
return max(col, 0.0);
"""
CODE_ROUGH = "return clamp(R * RScale, 0.75, 1.0);"
CODE_NORMAL = "return normalize(lerp(float3(0.0, 0.0, 1.0), N, Str));"
CODE_FRINGE = """// Fray fringe (plan 10.3): cut where the distance to the torn edge, broken by the weave height, is small.
return UV1.x / max(W, 1e-4) + Amt * (H - 0.5) - Thresh + 0.5;
"""
# key: (code, inputs, output type F1/F2/F3, masked-only)
CUSTOM = {
    "SK_TileUV": (CODE_TILE, ["UV", "TileM"], "F2", False),
    "SK_Mottle": (CODE_MOTTLE, ["UV0", "UV1", "ScaleM"], "F1", False),
    "SK_Base": (CODE_BASE, ["BC", "Mottle", "MottleAmt", "Desat", "Tint", "GrimeCol", "WPc", "OPc", "HemH", "HemFall",
                            "HemAmt", "UV1", "EdgeW", "EdgeAmt", "Fres", "RimAmt", "RimCol", "Inner"], "F3", False),
    "SK_Rough": (CODE_ROUGH, ["R", "RScale"], "F1", False),
    "SK_Normal": (CODE_NORMAL, ["N", "Str"], "F3", False),
    "SK_Fringe": (CODE_FRINGE, ["UV1", "W", "H", "Amt", "Thresh"], "F1", True),
}
# (source key, source output, target key, target pin, masked-only)
EDGES = [
    ("UV0", "", "SK_TileUV", "UV", False), ("TileM", "", "SK_TileUV", "TileM", False),
    ("SK_TileUV", "", "BaseColorTexture", "UVs", False), ("SK_TileUV", "", "NormalTexture", "UVs", False),
    ("SK_TileUV", "", "RoughnessTexture", "UVs", False), ("SK_TileUV", "", "AOTexture", "UVs", False),
    ("SK_TileUV", "", "HeightTexture", "UVs", True),
    ("UV0", "", "SK_Mottle", "UV0", False), ("UV1", "", "SK_Mottle", "UV1", False),
    ("MottleScaleM", "", "SK_Mottle", "ScaleM", False),
    ("RimExponent", "", "Fresnel", "ExponentIn", False),
    ("BaseColorTexture", "RGB", "SK_Base", "BC", False), ("SK_Mottle", "", "SK_Base", "Mottle", False),
    ("MottleAmount", "", "SK_Base", "MottleAmt", False), ("Desaturate", "", "SK_Base", "Desat", False),
    ("Tint", "", "SK_Base", "Tint", False), ("GrimeColor", "", "SK_Base", "GrimeCol", False),
    ("WPc", "", "SK_Base", "WPc", False), ("OPc", "", "SK_Base", "OPc", False),
    ("HemGrimeHeightM", "", "SK_Base", "HemH", False), ("HemGrimeFalloffM", "", "SK_Base", "HemFall", False),
    ("HemGrimeAmount", "", "SK_Base", "HemAmt", False), ("UV1", "", "SK_Base", "UV1", False),
    ("EdgeGrimeWidthM", "", "SK_Base", "EdgeW", False), ("EdgeGrimeAmount", "", "SK_Base", "EdgeAmt", False),
    ("Fresnel", "", "SK_Base", "Fres", False), ("RimAmount", "", "SK_Base", "RimAmt", False),
    ("RimColor", "", "SK_Base", "RimCol", False), ("InnerDarken", "", "SK_Base", "Inner", False),
    ("RoughnessTexture", "R", "SK_Rough", "R", False), ("RoughnessScale", "", "SK_Rough", "RScale", False),
    ("NormalTexture", "RGB", "SK_Normal", "N", False), ("NormalStrength", "", "SK_Normal", "Str", False),
    ("UV1", "", "SK_Fringe", "UV1", True), ("FringeWidthM", "", "SK_Fringe", "W", True),
    ("HeightTexture", "R", "SK_Fringe", "H", True), ("FringeNoiseAmount", "", "SK_Fringe", "Amt", True),
    ("FringeThreshold", "", "SK_Fringe", "Thresh", True),
]
# (source key, source output, MaterialProperty name, masked-only)
PROPS = [("SK_Base", "", "MP_BASE_COLOR", False), ("SK_Rough", "", "MP_ROUGHNESS", False),
         ("SK_Normal", "", "MP_NORMAL", False), ("Specular", "", "MP_SPECULAR", False),
         ("AOTexture", "R", "MP_AMBIENT_OCCLUSION", False), ("SK_Fringe", "", "MP_OPACITY_MASK", True)]
FIXED_NODES = {"UV0": ("MaterialExpressionTextureCoordinate", {"coordinate_index": 0}),
               "UV1": ("MaterialExpressionTextureCoordinate", {"coordinate_index": 1}),
               "Fresnel": ("MaterialExpressionFresnel", {}),
               "WPc": ("MaterialExpressionWorldPosition", {"world_position_shader_offset": "WPT_CAMERA_RELATIVE_NO_OFFSETS"}),
               "OPc": ("MaterialExpressionObjectPositionWS", {"origin_type": "CAMERA_RELATIVE"})}


class SackError(ValueError):
    pass


# ============================================================================================= pure helpers
def _require(cond, msg):
    if not cond:
        raise SackError(msg)


def _enum_name(v):
    s = str(v)
    if s.startswith("<") and ":" in s:
        s = s[1:].split(":", 1)[0]
    return s.rsplit(".", 1)[-1]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mesh_path(fig):
    return "%s/SKM_Sack_%s" % (SACK_DIR, fig)


def texture_path(key):
    return "%s/%s" % (TEX_DIR, TEXTURES[key][1])


def created_material_assets():
    return [M_OPAQUE, M_MASKED, MI_OUTER, MI_INNER]


def mat_stage_assets():
    return sorted([texture_path(k) for k in TEXTURES] + created_material_assets())


def source_files(fig, suffix=DEFAULT_FBX_SUFFIX):
    sid = SOURCE_ID[fig]
    return {"id": sid, "json": FINALS + sid + ".json", "fbx": FINALS + sid + suffix,
            "fbx_original": FINALS + sid + "_SK.fbx"}


# ------------------------------------------------------------------------------------------- FBX (binary) parser
def _fbx_nodes(data):
    """Top-level nodes of a binary FBX as (name, props, children). Arrays are summarised as ("arr", type, count)."""
    _require(data[:18] == b"Kaydara FBX Binary", "FBX_NOT_BINARY")
    ver = struct.unpack_from("<I", data, 23)[0]
    wide = ver >= 7500
    scalar = {"Y": "<h", "C": "<?", "I": "<i", "F": "<f", "D": "<d", "L": "<q"}

    def node(off):
        if wide:
            end, nprops, plen = struct.unpack_from("<QQQ", data, off)
            off += 24
        else:
            end, nprops, plen = struct.unpack_from("<III", data, off)
            off += 12
        nlen = data[off]
        off += 1
        name = data[off:off + nlen].decode("ascii", "replace")
        off += nlen
        if end == 0:
            return None, off
        props, p = [], off
        for _ in range(nprops):
            t = chr(data[p])
            p += 1
            if t in scalar:
                props.append(struct.unpack_from(scalar[t], data, p)[0])
                p += struct.calcsize(scalar[t])
            elif t in "SR":
                ln = struct.unpack_from("<I", data, p)[0]
                p += 4
                raw = data[p:p + ln]
                props.append(raw if t == "R" else raw.decode("utf-8", "replace"))
                p += ln
            else:
                ln, _enc, clen = struct.unpack_from("<III", data, p)
                p += 12 + clen
                props.append(("arr", t, ln))
        off += plen
        kids = []
        while off < end:
            ch, off2 = node(off)
            off = off2
            if ch is None:
                break
            kids.append(ch)
        return (name, props, kids), end

    out, off = [], 27
    while off < len(data) - 160:
        n, off2 = node(off)
        if n is None:
            break
        out.append(n)
        off = off2
    return ver, out


def fbx_skeleton_summary(path):
    """What a UE import will see, read straight from the binary FBX: axis/unit settings, the skeleton node tree
    (Root/LimbNode/Null models and their parents), meshes, materials, UV set names, vertex colour presence."""
    with open(path, "rb") as h:
        data = h.read()
    ver, nodes = _fbx_nodes(data)
    top = {n[0]: n for n in nodes}
    _require("Objects" in top and "Connections" in top, "FBX_NO_OBJECTS")
    settings = {}
    for n in top.get("GlobalSettings", ("", [], []))[2]:
        if n[0] == "Properties70":
            for q in n[2]:
                if q[1] and q[1][0] in ("UpAxis", "UpAxisSign", "FrontAxis", "FrontAxisSign", "UnitScaleFactor"):
                    settings[q[1][0]] = q[1][4] if len(q[1]) > 4 else None
    models, materials, uv_sets, colours, geo_verts = {}, [], set(), False, []
    for o in top["Objects"][2]:
        if o[0] == "Model":
            models[o[1][0]] = {"name": o[1][1].split("\x00")[0], "type": o[1][2]}
        elif o[0] == "Material":
            materials.append(o[1][1].split("\x00")[0])
        elif o[0] == "Geometry":
            for c in o[2]:
                if c[0] == "Vertices" and c[1] and isinstance(c[1][0], tuple):
                    geo_verts.append(c[1][0][2] // 3)
                elif c[0] == "LayerElementUV":
                    for d in c[2]:
                        if d[0] == "Name" and d[1]:
                            uv_sets.add(d[1][0])
                elif c[0] == "LayerElementColor":
                    colours = True
    parent = {}
    for c in top["Connections"][2]:
        if c[1] and c[1][0] == "OO" and c[1][1] in models and (c[1][2] in models or c[1][2] == 0):
            parent[c[1][1]] = c[1][2]          # model -> model (or scene) only; clusters/poses also link bones
    tree = {}
    for uid, m in models.items():
        if m["type"] in ("Root", "LimbNode", "Null"):
            p = parent.get(uid, 0)
            tree[m["name"]] = {"type": m["type"], "parent": models[p]["name"] if p in models else None,
                               "parent_type": models[p]["type"] if p in models else None}
    return {"file": path.replace("\\", "/"), "version": ver, "settings": settings, "tree": tree,
            "bones": sorted(n for n, r in tree.items() if r["type"] in ("Root", "LimbNode")),
            "meshes": sorted(m["name"] for m in models.values() if m["type"] == "Mesh"),
            "materials": sorted(materials), "uv_sets": sorted(uv_sets), "vertex_colours": colours,
            "geometry_vertices": geo_verts}


def fbx_structure_problems(summary, root_bone=ROOT_BONE, first_child=FIRST_CHILD, expected_bones=None):
    """Gate: the FBX skeleton must start at the skeleton's root bone (a Root/LimbNode named root_bone whose child is
    first_child), Z-up, centimetres; three sack slots; the fringe UV set; no other mesh."""
    probs = []
    tree = summary["tree"]
    r = tree.get(root_bone)
    if r is None or r["type"] not in ("Root", "LimbNode"):
        probs.append("ROOT_BONE_MISSING|%s|%s" % (root_bone, None if r is None else r["type"]))
    elif r["parent_type"] in ("Root", "LimbNode"):
        probs.append("ROOT_BONE_HAS_BONE_PARENT|%s" % r["parent"])
    c = tree.get(first_child)
    if c is None or c["parent"] != root_bone:
        probs.append("FIRST_CHILD_PARENT|%s|%s" % (first_child, None if c is None else c["parent"]))
    s = summary["settings"]
    if s.get("UpAxis") != 2:
        probs.append("NOT_Z_UP|UpAxis=%s" % s.get("UpAxis"))
    if s.get("UnitScaleFactor") is None or abs(float(s["UnitScaleFactor"]) - 1.0) > 1e-6:
        probs.append("NOT_CENTIMETRES|%s" % s.get("UnitScaleFactor"))
    if expected_bones is not None and len(summary["bones"]) != expected_bones:
        probs.append("BONE_COUNT|%d!=%d" % (len(summary["bones"]), expected_bones))
    return probs


def fbx_content_problems(summary):
    probs = []
    if len(summary["meshes"]) != 1:
        probs.append("MESH_COUNT|%s" % summary["meshes"])
    try:
        classify_slots(summary["materials"])
    except SackError as exc:
        probs.append(str(exc))
    if "FrayMask" not in summary["uv_sets"] or "UVMap" not in summary["uv_sets"]:
        probs.append("UV_SETS|%s" % summary["uv_sets"])
    return probs


# ------------------------------------------------------------------------------------------- sources
def source_problems(fig, src, summary=None):
    """src: the Blender JSON. Every Blender gate passed; the run matches Gary's decision; the skin export is whole."""
    probs = []
    checks = src.get("checks") or {}
    bad = sorted(k for k, v in checks.items() if v is not True)
    if not checks or bad:
        probs.append("BLENDER_CHECKS|%s" % (bad or "none"))
    a = src.get("args") or {}
    want = DECISION[fig]
    for k, v in want.items():
        got = a.get(k)
        if isinstance(v, float):
            if got is None or abs(float(got) - v) > 1e-6:
                probs.append("DECISION|%s|%s=%s want %s" % (fig, k, got, v))
        elif got != v:
            probs.append("DECISION|%s|%s=%s want %s" % (fig, k, got, v))
    if a.get("figure") != fig or a.get("mode") != "skin":
        probs.append("FIGURE_OR_MODE|%s|%s" % (a.get("figure"), a.get("mode")))
    skin = src.get("skin") or {}
    if not skin.get("fbx") or int(skin.get("unweighted_vertices", 10 ** 9)) > 0.01 * int(skin.get("vertices", 0)):
        probs.append("SKIN_WEIGHTS|%s" % skin.get("unweighted_vertices"))
    if int(skin.get("vertices", -1)) != int(src.get("exported_vertices", -2)):
        probs.append("SKIN_VERTS|%s|%s" % (skin.get("vertices"), src.get("exported_vertices")))
    if summary is not None and summary.get("geometry_vertices"):
        if summary["geometry_vertices"][0] != int(skin.get("vertices", -1)):
            probs.append("FBX_VERTS|%s|%s" % (summary["geometry_vertices"], skin.get("vertices")))
        n_fbx = len([b for b in summary["bones"] if b != ROOT_BONE])
        if n_fbx != int(skin.get("exported_bones", -1)):
            probs.append("FBX_BONES|%d|%s" % (n_fbx, skin.get("exported_bones")))
    return probs


def reexport_problems(rx, sf):
    probs = []
    if rx.get("ok") is not True or not rx.get("checks") or not all(rx["checks"].values()):
        probs.append("REEXPORT_NOT_OK|%s" % sorted(k for k, v in (rx.get("checks") or {}).items() if not v))
    if os.path.normcase(os.path.abspath(rx.get("src", ""))) != os.path.normcase(os.path.abspath(sf["fbx_original"])):
        probs.append("REEXPORT_SOURCE|%s" % rx.get("src"))
    if os.path.normcase(os.path.abspath(rx.get("dst", ""))) != os.path.normcase(os.path.abspath(sf["fbx"])):
        probs.append("REEXPORT_DST|%s" % rx.get("dst"))
    box = rx.get("bbox_world_m")
    if not (isinstance(box, list) and len(box) == 2 and all(len(v) == 3 for v in box)):
        probs.append("REEXPORT_NO_BOX")
    return probs


def classify_slots(names):
    """{"Front": index, "Back": index, "Edge": index}; exactly one slot name containing each role."""
    out, probs = {}, []
    for role in SLOT_ROLES:
        hits = [i for i, n in enumerate(names) if role in str(n)]
        if len(hits) != 1:
            probs.append("%s=%s" % (role, [names[i] for i in hits]))
        else:
            out[role] = hits[0]
    if probs or len(names) != 3:
        raise SackError("SLOTS|%s|%s" % (list(names), probs))
    return out


def expected_box_cm(bbox_world_m):
    """Blender world box (m) -> UE component-space box (cm): x, -y, z (the source JSON's head_bone_m vs
    record_head_m_ue_component shows exactly that mapping). Returns (origin, extent)."""
    (x0, y0, z0), (x1, y1, z1) = bbox_world_m
    lo, hi = (x0 * 100.0, -y1 * 100.0, z0 * 100.0), (x1 * 100.0, -y0 * 100.0, z1 * 100.0)
    return [(a + b) / 2.0 for a, b in zip(lo, hi)], [(b - a) / 2.0 for a, b in zip(lo, hi)]


def bounds_problems(src, origin, extent, tol_xy=5.0, tol_z=(10.0, 15.0), bbox_world_m=None, tol_box=1.0):
    """UE imported bounds (cm, mesh = body component space). With the re-export's exact Blender box: origin and
    extent each within tol_box cm (catches a mirrored or 180-degree-turned import). Without it: the Blender
    metrics (sheet footprint, crown) with loose tolerances."""
    probs = []
    if bbox_world_m is not None:
        eo, ee = expected_box_cm(bbox_world_m)
        for i, ax in enumerate("XYZ"):
            if abs(origin[i] - eo[i]) > tol_box:
                probs.append("BOX_ORIGIN_%s|%.1f!=%.1f cm" % (ax, origin[i], eo[i]))
            if abs(extent[i] - ee[i]) > tol_box:
                probs.append("BOX_EXTENT_%s|%.1f!=%.1f cm" % (ax, extent[i], ee[i]))
        return probs
    m, crown = src["metrics"], src["collider"]["crown"]
    bx, by = m["bbox_xy_m"]
    for axis, want, got in (("x", bx * 100.0, 2.0 * extent[0]), ("y", by * 100.0, 2.0 * extent[1])):
        if abs(want - got) > tol_xy:
            probs.append("BOUNDS_%s|%.1f!=%.1f cm" % (axis.upper(), got, want))
    top = origin[2] + extent[2]
    cz = crown[2] * 100.0
    if not (cz - tol_z[0] <= top <= cz + tol_z[1]):
        probs.append("BOUNDS_TOP|%.1f vs crown %.1f cm" % (top, cz))
    cx, cy = crown[0] * 100.0, -crown[1] * 100.0
    if not (origin[0] - extent[0] - 5 <= cx <= origin[0] + extent[0] + 5 and
            origin[1] - extent[1] - 5 <= cy <= origin[1] + extent[1] + 5):
        probs.append("BOUNDS_MISS_CROWN|crown (%.1f, %.1f) cm not inside" % (cx, cy))
    return probs


# ------------------------------------------------------------------------------------------- import settings
def interchange_wanted(asset_name):
    """Every pipeline value IMPORT sets, by (sub-object, property). Read back before importing."""
    return {
        ("pipeline", "asset_name"): asset_name,
        ("pipeline", "use_source_name_for_asset"): False,
        ("pipeline", "import_offset_uniform_scale"): 1.0,
        ("common_meshes", "import_lods"): False,
        ("common_meshes", "import_sockets"): False,
        ("common_skeletal", "skeleton"): SKELETON,
        ("common_skeletal", "use_t0_as_ref_pose"): False,        # keep the drape pose as the mesh's bind
        ("common_skeletal", "import_only_animations"): False,
        ("common_skeletal", "try_auto_select_skeleton"): False,
        ("common_skeletal", "add_curve_metadata_to_skeleton"): False,
        ("mesh", "import_skeletal_meshes"): True,
        ("mesh", "import_static_meshes"): False,
        ("mesh", "import_morph_targets"): False,
        ("mesh", "update_skeleton_reference_pose"): False,       # never touch the shared skeleton
        ("mesh", "create_physics_asset"): False,
        ("mesh", "import_vertex_attributes"): False,
        ("animation", "import_animations"): False,
        ("material", "import_materials"): False,
        ("texture", "import_textures"): False,
    }


def interchange_problems(wanted, got):
    probs = []
    for k, v in wanted.items():
        g = got.get(k, "<absent>")
        if isinstance(v, bool):
            ok = g is v
        elif isinstance(v, float):
            ok = isinstance(g, (int, float)) and not isinstance(g, bool) and abs(float(g) - v) < 1e-6
        else:
            ok = g == v
        if not ok:
            probs.append("PIPELINE|%s.%s=%r want %r" % (k[0], k[1], g, v))
    return probs


def sampler_for(compression, srgb):
    c = _enum_name(compression)
    if c == "TC_NORMALMAP":
        return "SAMPLERTYPE_NORMAL"
    if c == "TC_MASKS":
        return "SAMPLERTYPE_MASKS"
    if c in ("TC_GRAYSCALE", "TC_ALPHA", "TC_DISPLACEMENTMAP"):
        return "SAMPLERTYPE_GRAYSCALE" if srgb else "SAMPLERTYPE_LINEAR_GRAYSCALE"
    if c in ("TC_DEFAULT", "TC_BC7"):
        return "SAMPLERTYPE_COLOR" if srgb else "SAMPLERTYPE_LINEAR_COLOR"
    raise SackError("SAMPLER_UNMAPPED|%s|srgb=%s" % (compression, srgb))


def texture_settings_problems(key, got, pow2_mode, check_size=True):
    """check_size: the stretched 2048 x 2048 size is read from platform data, which a texture rebuild may not have
    refreshed inside the importing call [inf]; BUILD_MAT records it, VERIFY gates it."""
    _src, _name, comp, srgb = TEXTURES[key]
    probs = []
    if _enum_name(got.get("compression")) != comp:
        probs.append("COMPRESSION|%s|%s" % (key, got.get("compression")))
    if bool(got.get("srgb")) is not srgb:
        probs.append("SRGB|%s|%s" % (key, got.get("srgb")))
    if comp == "TC_NORMALMAP" and got.get("flip_green") is not False:
        probs.append("FLIP_GREEN|%s|%s" % (key, got.get("flip_green")))
    if _enum_name(got.get("pow2")) != pow2_mode:
        probs.append("POW2|%s|%s" % (key, got.get("pow2")))
    sx, sy = got.get("size_x"), got.get("size_y")
    if check_size and not (isinstance(sx, int) and isinstance(sy, int) and sx > 0 and sx & (sx - 1) == 0 and sy & (sy - 1) == 0):
        probs.append("NOT_POW2_AFTER|%s|%sx%s" % (key, sx, sy))
    if comp == "TC_GRAYSCALE" and sampler_for(comp, got.get("srgb")) != "SAMPLERTYPE_LINEAR_GRAYSCALE":
        probs.append("SAMPLER|%s" % key)
    return probs


# ------------------------------------------------------------------------------------------- material spec
def graph_spec(masked):
    """The logical graph one master gets: nodes {key: kind}, edges, property wires (pure; the harness checks it)."""
    nodes = {k: ("scalar", v) for k, v in SCALARS.items()}
    if masked:
        nodes.update({k: ("scalar", v) for k, v in MASKED_SCALARS.items()})
    nodes.update({k: ("vector", v) for k, v in VECTORS.items()})
    tp = dict(TEX_PARAMS)
    if masked:
        tp.update(MASKED_TEX_PARAMS)
    nodes.update({k: ("texture", t) for k, t in tp.items()})
    nodes.update({k: ("fixed", v) for k, v in FIXED_NODES.items()})
    nodes.update({k: ("custom", v) for k, v in CUSTOM.items() if masked or not v[3]})
    edges = [e[:4] for e in EDGES if masked or not e[4]]
    props = [p[:3] for p in PROPS if masked or not p[3]]
    return nodes, edges, props


def graph_problems(masked):
    nodes, edges, props = graph_spec(masked)
    probs = []
    for s, _o, d, pin in edges:
        if s not in nodes or d not in nodes:
            probs.append("EDGE_NODE|%s->%s" % (s, d))
    seen = {}
    for s, _o, d, pin in edges:
        seen.setdefault((d, pin), []).append(s)
    for k, (kind, v) in nodes.items():
        if kind == "custom":
            for pin in v[1]:
                if len(seen.get((k, pin), [])) != 1:
                    probs.append("CUSTOM_PIN|%s.%s|%s" % (k, pin, seen.get((k, pin))))
            for (d, pin) in seen:
                if d == k and pin not in v[1]:
                    probs.append("CUSTOM_UNKNOWN_PIN|%s.%s" % (k, pin))
    for d in {e[2] for e in edges}:
        srcs = [e[0] for e in edges if e[2] == d]
        if len(srcs) != len(set(srcs)):
            probs.append("SOURCE_FEEDS_TWO_PINS|%s|%s" % (d, srcs))
    used = {e[0] for e in edges} | {p[0] for p in props}
    for k, (kind, _v) in nodes.items():
        if k not in used:
            probs.append("UNUSED_NODE|%s" % k)
    want = {"MP_BASE_COLOR", "MP_ROUGHNESS", "MP_NORMAL", "MP_SPECULAR", "MP_AMBIENT_OCCLUSION"}
    if masked:
        want.add("MP_OPACITY_MASK")
    got = {p[2] for p in props}
    if got != want:
        probs.append("PROPS|%s" % sorted(got ^ want))
    return probs


def mi_problems(name, scalars, vectors, overridden, master_scalars):
    """Read-back gate of one MI: every planned value, and the override flag (a setter that did nothing would leave
    the master default, which equals some planned values)."""
    want = MI_VALUES[name]
    probs = []
    for k, v in want["scalars"].items():
        if k not in master_scalars:
            probs.append("MI_PARAM_NOT_ON_MASTER|%s" % k)
        g = scalars.get(k)
        if g is None or abs(float(g) - v) > TOL:
            probs.append("MI_SCALAR|%s|%s=%s want %s" % (name, k, g, v))
        if overridden.get(k) is not True:
            probs.append("MI_NOT_OVERRIDDEN|%s|%s" % (name, k))
    for k, v in want["vectors"].items():
        g = vectors.get(k)
        if g is None or any(abs(float(g[i]) - v[i]) > TOL for i in range(3)):
            probs.append("MI_VECTOR|%s|%s=%s want %s" % (name, k, g, v))
        if overridden.get(k) is not True:
            probs.append("MI_NOT_OVERRIDDEN|%s|%s" % (name, k))
    return probs


# ------------------------------------------------------------------------------------------- modes / census
def check_mode(args, records_exist):
    """records_exist: {"IMPORT": bool, "BUILD_MAT": bool, "APPLY": bool}. Returns (mode, figures, options)."""
    mode = str(args.get("mode", "DRY")).upper()
    _require(mode in MODES, "MODE|" + mode)
    if mode in WRITE_MODES:
        _require(args.get("confirm") == "%s %s" % (mode, CONFIRM_WORD),
                 "CONFIRM_MISSING|want '%s %s'" % (mode, CONFIRM_WORD))
    figs = list(args.get("figures") or FIGURES)
    bad = [f for f in figs if f not in FIGURES]
    _require(not bad and len(set(figs)) == len(figs) and figs, "FIGURES|%s" % figs)
    opts = {"fbx_suffix": str(args.get("fbx_suffix", DEFAULT_FBX_SUFFIX)),
            "cloth_switch": str(args.get("cloth_switch", "suspend+disable")),
            "bounds_scale": float(args.get("bounds_scale", 1.25)),
            "pow2_mode": str(args.get("pow2_mode", "STRETCH_TO_POWER_OF_TWO"))}
    _require(opts["fbx_suffix"].endswith(".fbx") and "_SK" in opts["fbx_suffix"], "FBX_SUFFIX|" + opts["fbx_suffix"])
    _require(opts["cloth_switch"] in ("suspend", "suspend+disable"), "CLOTH_SWITCH|" + opts["cloth_switch"])
    _require(1.0 <= opts["bounds_scale"] <= 2.0, "BOUNDS_SCALE|%s" % opts["bounds_scale"])
    _require(opts["pow2_mode"] in ("NONE", "STRETCH_TO_POWER_OF_TWO", "PAD_TO_POWER_OF_TWO"), "POW2|" + opts["pow2_mode"])
    if mode == "BUILD_MAT":
        _require(not records_exist["BUILD_MAT"], "ALREADY_BUILT|mat record exists")
    if mode == "APPLY":
        _require(records_exist["IMPORT"] and records_exist["BUILD_MAT"], "PREREQ|IMPORT and BUILD_MAT records needed")
        _require(not records_exist["APPLY"], "ALREADY_APPLIED|apply record exists (REVERT first)")
    if mode == "REVERT":
        _require(records_exist["APPLY"], "NO_APPLY_RECORD")
    if mode == "VERIFY":
        _require(any(records_exist.values()), "NOTHING_TO_VERIFY")
    if mode == "PIE_PROBE":
        _require(records_exist["APPLY"], "NO_APPLY_RECORD")
    return mode, figs, opts


def planned_packages(mode, figs):
    if mode == "IMPORT":
        return {"content": sorted(mesh_path(f) for f in figs), "maps": []}
    if mode == "BUILD_MAT":
        return {"content": mat_stage_assets(), "maps": []}
    if mode in ("APPLY", "REVERT"):
        return {"content": [], "maps": [WORLD]}
    return {"content": [], "maps": []}


def census_ok(dirty, planned):
    return sorted(dirty["maps"]) == sorted(planned["maps"]) and sorted(dirty["content"]) == sorted(planned["content"])


def cloth_target(before, switch):
    """The cloth state APPLY writes (and REVERT restores 'before')."""
    after = dict(before)
    after["visible"] = False
    after["hidden_in_game"] = True
    after["suspended"] = True
    if switch == "suspend+disable":
        after["enabled"] = False
    return after


def sack_label(fig):
    return fig + " Sack"


def relative_identity_problems(fig, s, tol_cm=0.1, tol_deg=0.01, tol_scale=1e-4):
    """The sack actor is spawned at the Body's world transform and attached KEEP_WORLD: relative = identity."""
    probs = []
    if any(abs(v) > tol_cm for v in s["relative_location"]):
        probs.append("SACK_OFFSET|%s|%s" % (fig, s["relative_location"]))
    if any(abs(((v + 180.0) % 360.0) - 180.0) > tol_deg for v in s["relative_rotation"]):
        probs.append("SACK_ROTATION|%s|%s" % (fig, s["relative_rotation"]))
    if any(abs(v - 1.0) > tol_scale for v in s["relative_scale"]):
        probs.append("SACK_SCALE|%s|%s" % (fig, s["relative_scale"]))
    return probs


def apply_expectation(fig, slots):
    """What VERIFY expects on a placed figure after APPLY (slots = classify_slots of the imported mesh)."""
    mats = [None, None, None]
    for role, idx in slots.items():
        mats[idx] = SLOT_MI[role]
    return {"component": SACK_COMPONENT, "mesh": mesh_path(fig), "materials": mats, "attach_parent": BODY,
            "leader": BODY}


def state_diff(want, got, keys=None):
    keys = keys or sorted(set(want) | set(got))
    return {k: (got.get(k), want.get(k)) for k in keys if got.get(k) != want.get(k)}


# ============================================================================================= unreal glue
def _path(obj):
    """Package path of an ASSET. Never use it to compare components or actors: every object in the level shares
the map's package, so their _path values are all equal."""
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def _full(obj):
    """Full object path (components, actors)."""
    return str(obj.get_path_name()) if obj is not None else None


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())


def _read(path):
    with open(path, encoding="utf-8") as h:
        return json.load(h)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def _temp_actor_guard(world):
    """GameplayStatics sees transient bench actors that get_all_level_actors misses (memory puss-benches)."""
    acts = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    bad = [str(a.get_actor_label()) for a in acts
           if str(a.get_actor_label()).startswith("ZZ_") or "TEMP" in str(a.get_actor_label()).upper()]
    _require(not bad, "TEMP_ACTORS_PRESENT|%s" % bad[:5])


def _save(ed, planned):
    world = ed.get_editor_world()
    _temp_actor_guard(world)
    dirty = _census()
    _require(census_ok(dirty, planned), "DIRTY_SCOPE|%s|planned=%s" % (json.dumps(dirty), json.dumps(planned)))
    for p in planned["content"]:
        _require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), "SAVE_ASSET_FAILED|" + p)
    if planned["maps"]:
        _require(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "SAVE_MAP_FAILED")
    after = _census()
    _require(after == {"content": [], "maps": []}, "POST_SAVE_DIRTY|" + json.dumps(after))
    return dirty


def _backup_umap(run, tag=""):
    d = BACKUP_ROOT.rstrip("-") + tag + "-" + run
    os.makedirs(d)
    dst = os.path.join(d, os.path.basename(UMAP))
    shutil.copy2(UMAP, dst)
    _require(sha256_file(UMAP) == sha256_file(dst), "BACKUP_HASH|" + UMAP)
    return d, [{"src": UMAP, "dst": dst, "bytes": os.path.getsize(dst)}]


def _figure_actors(figs):
    """{fig: actor}: label "<id> Clam" AND class BP_<id>_Draped_C, exactly one each (s3_shore_export_bodies.py:180)."""
    index = {}
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        index.setdefault(str(a.get_actor_label()), []).append(a)
    out, fails = {}, []
    for f in figs:
        hits = index.get(f + " Clam", [])
        if len(hits) != 1:
            fails.append("ACTOR_COUNT|%s|%d" % (f, len(hits)))
        elif str(hits[0].get_class().get_name()) != "BP_%s_Draped_C" % f:
            fails.append("ACTOR_CLASS|%s|%s" % (f, hits[0].get_class().get_name()))
        else:
            out[f] = hits[0]
    _require(not fails, ";".join(fails))
    return out


def _components(actor, name, cls_name=None):
    hits = [c for c in actor.get_components_by_class(unreal.ActorComponent) if str(c.get_name()) == name]
    if cls_name:
        hits = [c for c in hits if str(c.get_class().get_name()) == cls_name]
    return hits


def _one(actor, name, cls_name=None):
    hits = _components(actor, name, cls_name)
    _require(len(hits) == 1, "COMPONENT|%s|%s|%d" % (actor.get_actor_label(), name, len(hits)))
    return hits[0]


def _overrides(comp):
    return [_path(m) for m in (comp.get_editor_property("override_materials") or [])]


def _leader(comp):
    try:
        return comp.get_editor_property("leader_pose_component")
    except Exception as exc:  # noqa: BLE001 - property name unproven in Python: report, never treat as a pass
        raise SackError("LEADER_UNREADABLE|%s" % exc)


def _leader_path_safe(comp):
    """Full path of comp's leader, None, or "UNREADABLE" when Python cannot read the weak pointer (then compared
    before/after like any value, never treated as 'no leader' proof)."""
    try:
        return _full(_leader(comp))
    except SackError:
        return "UNREADABLE"


def _cloth_state(cloth):
    """Read through the SAME properties the writes use (CLOTH_PROPS). The function reads are informational only:
    IsSimulationEnabled/IsSimulationSuspended are virtual and may fold in more than the flag (ClothComponent.h:160,171)."""
    st = {k: bool(cloth.get_editor_property(prop)) for k, prop in CLOTH_PROPS}
    info = {}
    for name in ("is_visible", "is_simulation_enabled", "is_simulation_suspended"):
        try:
            info[name] = bool(getattr(cloth, name)())
        except Exception as exc:  # noqa: BLE001
            info[name] = "ERR %s" % exc
    st["functions_info"] = info
    return st


def _bone_children(mesh, name):
    cls = unreal.SkeletalMeshEditorSubsystem
    try:
        kids = cls.get_bone_children(mesh, name)            # static UFUNCTION (SkeletalMeshEditorSubsystem.h:242)
    except Exception:  # noqa: BLE001 - ScriptMethod spelling
        kids = mesh.get_bone_children(name)
    return [str(k) for k in kids]


def _bone_parent(mesh, name):
    cls = unreal.SkeletalMeshEditorSubsystem
    try:
        p = cls.get_bone_parent(mesh, name)                 # SkeletalMeshEditorSubsystem.h:234
    except Exception:  # noqa: BLE001
        p = mesh.get_bone_parent(name)
    p = str(p)
    return None if p in ("None", "") else p


def _bone_tree(mesh):
    """{bone: parent} by walking get_bone_children from ROOT_BONE (no ref-skeleton API in Python)."""
    _require(_bone_parent(mesh, ROOT_BONE) is None, "ROOT_HAS_PARENT|%s" % _path(mesh))
    tree, stack = {ROOT_BONE: None}, [ROOT_BONE]
    while stack:
        b = stack.pop()
        for k in _bone_children(mesh, b):
            _require(k not in tree, "BONE_CYCLE|%s" % k)
            tree[k] = b
            stack.append(k)
    _require(len(tree) > 1, "BONE_TREE_EMPTY|%s" % _path(mesh))
    return tree


def _body_mesh(actor):
    body = _one(actor, BODY, "SkeletalMeshComponent")
    m = body.get_skeletal_mesh_asset()
    _require(m is not None, "BODY_MESH_NONE|%s" % actor.get_actor_label())
    return body, m


def _mesh_slots(mesh):
    return [str(sm.get_editor_property("material_slot_name")) for sm in (mesh.get_editor_property("materials") or [])]


def _morph_names(mesh):
    for fn in ("k2_get_all_morph_target_names", "get_all_morph_target_names"):   # SkeletalMesh.h:2039 (K2_)
        if hasattr(mesh, fn):
            return [str(n) for n in getattr(mesh, fn)()]
    raise SackError("MORPH_API_ABSENT")


def _mesh_readback(fig, mesh, src, body_tree):
    eal = unreal.EditorAssetLibrary
    _require(isinstance(mesh, unreal.SkeletalMesh), "NOT_SKELETAL_MESH|%s" % fig)
    skel = mesh.get_editor_property("skeleton")
    rb = {"path": _path(mesh), "skeleton": _path(skel),
          "lods": int(unreal.SkeletalMeshEditorSubsystem.get_lod_count(mesh)),
          "render_vertices": int(unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem).get_num_verts(mesh, 0)),
          "slots": _mesh_slots(mesh),
          "physics_asset": _path(mesh.get_editor_property("physics_asset")),
          "morph_targets": _morph_names(mesh)}
    b = mesh.get_imported_bounds()
    o, e = b.get_editor_property("origin"), b.get_editor_property("box_extent")
    rb["bounds_origin_cm"] = [float(o.x), float(o.y), float(o.z)]
    rb["bounds_extent_cm"] = [float(e.x), float(e.y), float(e.z)]
    tree = _bone_tree(mesh)
    rb["bones"] = len(tree)
    probs = []
    if rb["skeleton"] != SKELETON:
        probs.append("SKELETON|%s" % rb["skeleton"])
    if rb["lods"] != 1:
        probs.append("LODS|%d" % rb["lods"])
    try:
        rb["slot_roles"] = classify_slots(rb["slots"])
    except SackError as exc:
        probs.append(str(exc))
    nv = int(src["skin"]["vertices"])
    if not nv <= rb["render_vertices"] <= 4 * nv:
        probs.append("RENDER_VERTS|%d vs blender %d" % (rb["render_vertices"], nv))
    if rb["physics_asset"] is not None:
        probs.append("PHYSICS_ASSET|%s" % rb["physics_asset"])
    if rb["morph_targets"]:
        probs.append("MORPHS|%s" % rb["morph_targets"][:4])
    if rb["bones"] != int(src["skin"]["exported_bones"]) + 1:
        probs.append("BONES|%d want %d (+root)" % (rb["bones"], int(src["skin"]["exported_bones"]) + 1))
    foreign = sorted(k for k in tree if k not in body_tree)
    wrong_parent = sorted(k for k, p in tree.items() if k in body_tree and body_tree[k] != p)
    if foreign or wrong_parent:
        probs.append("BONE_TREE_VS_BODY|foreign=%s|parent=%s" % (foreign[:5], wrong_parent[:5]))
    probs += bounds_problems(src, rb["bounds_origin_cm"], rb["bounds_extent_cm"],
                             bbox_world_m=(src.get("_reexport") or {}).get("bbox_world_m"))
    rb["exists"] = bool(eal.does_asset_exist(_path(mesh)))
    return rb, probs


def _pipeline(asset_name):
    """Interchange override (precedent s3_beach_v2.py:666-699, run 4 Oct). Every value read back."""
    skel = unreal.load_asset(SKELETON)
    _require(isinstance(skel, unreal.Skeleton), "SKELETON_MISSING|" + SKELETON)
    p = unreal.InterchangeGenericAssetsPipeline()
    subs = {"pipeline": p,
            "common_meshes": p.get_editor_property("common_meshes_properties"),
            "common_skeletal": p.get_editor_property("common_skeletal_meshes_and_animations_properties"),
            "mesh": p.get_editor_property("mesh_pipeline"),
            "animation": p.get_editor_property("animation_pipeline"),
            "material": p.get_editor_property("material_pipeline")}
    subs["texture"] = subs["material"].get_editor_property("texture_pipeline") if subs["material"] else None
    _require(all(v is not None for v in subs.values()), "PIPELINE_SUBOBJECTS|%s" % [k for k, v in subs.items() if v is None])
    wanted = interchange_wanted(asset_name)
    for (sub, prop), v in wanted.items():
        subs[sub].set_editor_property(prop, skel if prop == "skeleton" else v)
    got = {}
    for (sub, prop) in wanted:
        g = subs[sub].get_editor_property(prop)
        if prop == "skeleton":   # TSoftObjectPtr: Python may hand back the object or a soft-path wrapper [inf]
            text = _path(g) if g is not None and hasattr(g, "get_path_name") else (str(g) if g else "")
            g = SKELETON if text and (text == SKELETON or SKELETON + "." in text) else (text or None)
        elif isinstance(g, str):
            g = str(g)
        got[(sub, prop)] = g
    probs = interchange_problems(wanted, got)
    _require(not probs, "PIPELINE_READBACK|%s" % probs)
    override = unreal.InterchangePipelineStackOverride()
    override.add_pipeline(p)
    return override, {"%s.%s" % k: v for k, v in got.items()}


def _list_assets(folder):
    eal = unreal.EditorAssetLibrary
    if not eal.does_directory_exist(folder):
        return []
    return sorted(str(a).split(".", 1)[0] for a in eal.list_assets(folder, recursive=True, include_folder=False))


def _sources(figs, suffix):
    rows, probs = {}, []
    for f in figs:
        sf = source_files(f, suffix)
        if not os.path.isfile(sf["json"]) or not os.path.isfile(sf["fbx"]):
            probs.append("SOURCE_MISSING|%s|json=%s|fbx=%s" % (f, os.path.isfile(sf["json"]), os.path.isfile(sf["fbx"])))
            continue
        src = _read(sf["json"])
        summ = fbx_skeleton_summary(sf["fbx"])
        p = []
        if os.path.isfile(sf["fbx"] + ".json"):           # Tools/S3Sackcloth/reexport_sk_root.py report
            rx = _read(sf["fbx"] + ".json")
            p += reexport_problems(rx, sf)
            src["_reexport"] = rx
        elif sf["fbx"] != sf["fbx_original"]:
            p.append("REEXPORT_REPORT_MISSING|%s.json" % sf["fbx"])
        p += source_problems(f, src, summ) + fbx_structure_problems(summ, expected_bones=int(src["skin"]["exported_bones"]) + 1) \
            + fbx_content_problems(summ)
        rows[f] = {"files": sf, "src": src, "summary": summ, "sha256": sha256_file(sf["fbx"]), "problems": p}
        probs += ["%s|%s" % (f, x) for x in p]
    return rows, probs


# ------------------------------------------------------------------------------------------- IMPORT
def run_import(run, opts, figs, ed):
    eal = unreal.EditorAssetLibrary
    existing = _read(RECORDS["IMPORT"]) if os.path.exists(RECORDS["IMPORT"]) else {"figures": {}}
    already = [f for f in figs if f in existing.get("figures", {})]
    _require(not already, "ALREADY_IMPORTED|%s" % already)
    rows, probs = _sources(figs, opts["fbx_suffix"])
    _require(not probs, "SOURCE_PROBLEMS|%s" % probs[:8])
    actors = _figure_actors(figs)
    body_trees = {}
    for f, a in actors.items():
        _, bm = _body_mesh(a)
        _require(_path(bm.get_editor_property("skeleton")) == SKELETON, "BODY_SKELETON|%s" % f)
        body_trees[f] = _bone_tree(bm)
    taken = [mesh_path(f) for f in figs if eal.does_asset_exist(mesh_path(f))]
    _require(not taken, "TARGETS_EXIST|%s" % taken)
    before = _list_assets(SACK_DIR)
    record = dict(existing)
    record.setdefault("figures", {})
    record["last_run"] = run
    record["pending"] = {"run": run, "figures": figs, "saved": False}
    _write(RECORDS["IMPORT"], record)
    readbacks = {}
    for f in figs:
        override, settings = _pipeline("SKM_Sack_" + f)
        task = unreal.AssetImportTask()
        for k, v in (("filename", rows[f]["files"]["fbx"]), ("destination_path", SACK_DIR),
                     ("destination_name", "SKM_Sack_" + f), ("automated", True), ("replace_existing", False),
                     ("save", False)):
            task.set_editor_property(k, v)
        task.set_editor_property("options", override)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        mesh = unreal.load_asset(mesh_path(f))
        _require(mesh is not None, "IMPORT_FAILED|%s|objects=%s" % (f, [str(x) for x in task.imported_object_paths]))
        rb, p = _mesh_readback(f, mesh, rows[f]["src"], body_trees[f])
        rb["pipeline"] = settings
        _require(not p, "MESH_GATES|%s|%s" % (f, p))
        readbacks[f] = rb
    new = sorted(set(_list_assets(SACK_DIR)) - set(before))
    _require(new == sorted(mesh_path(f) for f in figs), "STRAY_ASSETS|%s" % new)
    planned = planned_packages("IMPORT", figs)
    _require(SKELETON not in _census()["content"], "SKELETON_DIRTIED|the import modified the shared skeleton")
    saved = _save(ed, planned)
    for f in figs:      # again from the saved state
        rb, p = _mesh_readback(f, unreal.load_asset(mesh_path(f)), rows[f]["src"], body_trees[f])
        _require(not p, "MESH_GATES_AFTER_SAVE|%s|%s" % (f, p))
        record["figures"][f] = {"run": run, "mesh": mesh_path(f), "source": rows[f]["files"], "sha256": rows[f]["sha256"],
                                "readback": readbacks[f], "saved": True}
    record.pop("pending", None)
    record["saved_packages"] = sorted(set(record.get("saved_packages", [])) | set(saved["content"]))
    _write(RECORDS["IMPORT"], record)
    return {"figures": figs, "saved": saved["content"]}


# ------------------------------------------------------------------------------------------- BUILD_MAT
def _texture_settings(tex):
    got = {"compression": str(tex.get_editor_property("compression_settings")),
           "srgb": bool(tex.get_editor_property("srgb")),
           "flip_green": bool(tex.get_editor_property("flip_green_channel")),
           "pow2": str(tex.get_editor_property("power_of_two_mode")),
           "size_x": int(tex.blueprint_get_size_x()), "size_y": int(tex.blueprint_get_size_y())}
    tags = {}
    try:   # G16 check: only if the asset registry exposes a format tag (UNCLEAR otherwise)
        data = unreal.EditorAssetLibrary.find_asset_data(_path(tex))
        for t in ("Format", "SourceFormat", "PixelFormat"):
            v = data.get_tag_value(t)
            if v:
                tags[t] = str(v)
    except Exception as exc:  # noqa: BLE001
        tags["error"] = str(exc)
    got["registry_tags"] = tags
    return got


def _import_texture(key, pow2_mode, manifest):
    src_key, name, comp, srgb = TEXTURES[key]
    row = manifest["files"][src_key]
    path = TEX_SRC + row["file"]
    _require(sha256_file(path) == row["sha256"], "TEXTURE_SHA|" + path)
    dest = texture_path(key)
    _require(not unreal.EditorAssetLibrary.does_asset_exist(dest), "TEXTURE_EXISTS|" + dest)
    task = unreal.AssetImportTask()       # pattern: s3_marble_tiling_material.py:741-764 (run 6 Oct)
    for k, v in (("filename", path), ("destination_path", TEX_DIR), ("destination_name", name), ("automated", True),
                 ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = unreal.load_asset(dest)
    _require(isinstance(tex, unreal.Texture2D), "TEXTURE_IMPORT_FAILED|" + dest)
    tex.modify()
    tex.set_editor_property("compression_settings", getattr(unreal.TextureCompressionSettings, comp))
    tex.set_editor_property("srgb", bool(srgb))
    tex.set_editor_property("power_of_two_mode", getattr(unreal.TexturePowerOfTwoSetting, pow2_mode))
    if comp == "TC_NORMALMAP":
        tex.set_editor_property("flip_green_channel", False)
    got = _texture_settings(tex)
    probs = texture_settings_problems(key, got, pow2_mode, check_size=False)
    _require(not probs, "TEXTURE_SETTINGS|%s" % probs)
    got["source"], got["sha256"] = path, row["sha256"]
    return tex, got


class _Graph:
    def __init__(self, mat):
        self.mat, self.mel, self.nodes = mat, unreal.MaterialEditingLibrary, {}

    def node(self, key, cls, x, y, **props):
        _require(key not in self.nodes, "DUP_NODE|" + key)
        n = self.mel.create_material_expression(self.mat, cls, x, y)
        _require(n is not None, "CREATE_NODE|%s" % key)
        for k, v in props.items():
            n.set_editor_property(k, v)
        self.nodes[key] = n
        return n

    def link(self, a, a_out, b, b_in):
        ok = self.mel.connect_material_expressions(self.nodes[a], a_out, self.nodes[b], b_in)
        _require(ok, "LINK|%s.%s->%s.%s|inputs=%s" % (a, a_out, b, b_in,
                                                     [str(x) for x in self.mel.get_material_expression_input_names(self.nodes[b])]))


def _build_master(path, masked, textures):
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    _require(not eal.does_asset_exist(path), "MASTER_EXISTS|" + path)
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(path.rsplit("/", 1)[1], MAT_DIR, unreal.Material,
                                                                  unreal.MaterialFactoryNew())
    _require(mat is not None, "MASTER_CREATE|" + path)
    flags = {"blend_mode": unreal.BlendMode.BLEND_MASKED if masked else unreal.BlendMode.BLEND_OPAQUE,
             "shading_model": unreal.MaterialShadingModel.MSM_DEFAULT_LIT, "two_sided": False,
             "used_with_skeletal_mesh": True, "used_with_nanite": True}
    if masked:
        flags["opacity_mask_clip_value"] = MASK_CLIP
    for k, v in flags.items():
        mat.modify()
        mat.set_editor_property(k, v)
    g = _Graph(mat)
    nodes, edges, props = graph_spec(masked)
    F = {"F1": unreal.CustomMaterialOutputType.CMOT_FLOAT1, "F2": unreal.CustomMaterialOutputType.CMOT_FLOAT2,
         "F3": unreal.CustomMaterialOutputType.CMOT_FLOAT3}
    y = {"scalar": -800, "vector": -800, "texture": -400, "fixed": 200, "custom": -600}
    for i, (key, (kind, v)) in enumerate(nodes.items()):
        if kind == "scalar":
            g.node(key, unreal.MaterialExpressionScalarParameter, -2400, y["scalar"] + 70 * i,
                   parameter_name=key, default_value=float(v[0]), group=v[1])
        elif kind == "vector":
            g.node(key, unreal.MaterialExpressionVectorParameter, -2400, y["vector"] - 150 * i,
                   parameter_name=key, default_value=unreal.LinearColor(v[0][0], v[0][1], v[0][2], 1.0), group=v[1])
        elif kind == "texture":
            tex = textures[v]
            st = getattr(unreal.MaterialSamplerType, sampler_for(str(tex.get_editor_property("compression_settings")),
                                                                 bool(tex.get_editor_property("srgb"))))
            g.node(key, unreal.MaterialExpressionTextureSampleParameter2D, -1500, y["texture"] + 260 * i,
                   parameter_name=key, texture=tex, sampler_type=st, group="00 Textures")
        elif kind == "fixed":
            cls_name, p = v
            pp = {}
            for k2, v2 in p.items():
                if k2 == "world_position_shader_offset":
                    v2 = getattr(unreal.WorldPositionIncludedOffsets, v2)
                elif k2 == "origin_type":
                    v2 = getattr(unreal.PositionOrigin, v2)
                pp[k2] = v2
            g.node(key, getattr(unreal, cls_name), -2000, y["fixed"] + 120 * i, **pp)
        else:
            code, inputs, otype, _m = v
            n = g.node(key, unreal.MaterialExpressionCustom, -900, y["custom"] + 200 * i,
                       description=key, code=code, output_type=F[otype])
            ins = []
            for name in inputs:
                ci = unreal.CustomInput()
                ci.set_editor_property("input_name", name)
                ins.append(ci)
            n.set_editor_property("inputs", ins)
            got = [str(c.get_editor_property("input_name")) for c in n.get_editor_property("inputs")]
            _require(got == list(inputs), "CUSTOM_INPUTS|%s|%s" % (key, got))
    for s, o, d, pin in edges:
        g.link(s, o, d, pin)
    MP = unreal.MaterialProperty
    for s, o, prop in props:
        _require(mel.connect_material_property(g.nodes[s], o, getattr(MP, prop)), "PROP|%s" % prop)
    _check_graph(mat, g.nodes, masked)
    errors = [str(e) for e in (mel.recompile_material(mat) or [])]
    _require(not errors, "RECOMPILE|%s|%s" % (path, errors))
    return mat, {"nodes": len(g.nodes), "edges": len(edges), "props": len(props)}


def _check_graph(mat, nodes, masked):
    """Edges and property wires read back through MEL read APIs (aligned input lists), flags and parameters."""
    mel = unreal.MaterialEditingLibrary
    spec_nodes, edges, props = graph_spec(masked)
    bad = []
    for d in sorted({e[2] for e in edges}):
        target = nodes[d]
        names = [str(x) for x in mel.get_material_expression_input_names(target)]
        ups = list(mel.get_inputs_for_material_expression(mat, target))
        rows = [e for e in edges if e[2] == d]
        live = [u for u in ups if u is not None]
        if len(live) != len(rows):
            bad.append("%s: %d live inputs, wired %d" % (d, len(live), len(rows)))
        for s, _o, _d, pin in rows:
            if pin not in names:
                bad.append("%s.%s not an input (%s)" % (d, pin, names))
            elif len(ups) == len(names):
                up = ups[names.index(pin)]
                if up is None or up.get_name() != nodes[s].get_name():
                    bad.append("%s->%s.%s reads %s" % (s, d, pin, None if up is None else up.get_name()))
            elif nodes[s].get_name() not in [u.get_name() for u in live]:
                bad.append("%s->%s.%s missing" % (s, d, pin))
    MP = unreal.MaterialProperty
    for s, _o, prop in props:
        n = mel.get_material_property_input_node(mat, getattr(MP, prop))
        if n is None or n.get_name() != nodes[s].get_name():
            bad.append("%s fed by %s" % (prop, None if n is None else n.get_name()))
    if int(mel.get_num_material_expressions(mat)) != len(nodes):
        bad.append("EXPRESSIONS|%s!=%d" % (mel.get_num_material_expressions(mat), len(nodes)))
    want_s = sorted(list(SCALARS) + (list(MASKED_SCALARS) if masked else []))
    got_s = sorted(str(n) for n in mel.get_scalar_parameter_names(mat))
    want_t = sorted(list(TEX_PARAMS) + (list(MASKED_TEX_PARAMS) if masked else []))
    got_t = sorted(str(n) for n in mel.get_texture_parameter_names(mat))
    got_v = sorted(str(n) for n in mel.get_vector_parameter_names(mat))
    if got_s != want_s or got_t != want_t or got_v != sorted(VECTORS):
        bad.append("PARAMS|s=%s|t=%s|v=%s" % (got_s, got_t, got_v))
    _require(not bad, "GRAPH_READBACK|%s" % bad[:8])


def _master_flags(mat, masked):
    rb = {"blend_mode": _enum_name(mat.get_editor_property("blend_mode")),
          "shading_model": _enum_name(mat.get_editor_property("shading_model")),
          "two_sided": bool(mat.get_editor_property("two_sided")),
          "used_with_skeletal_mesh": bool(mat.get_editor_property("used_with_skeletal_mesh")),
          "opacity_mask_clip_value": float(mat.get_editor_property("opacity_mask_clip_value"))}
    probs = []
    if rb["blend_mode"] != ("BLEND_MASKED" if masked else "BLEND_OPAQUE"):
        probs.append("BLEND|%s" % rb["blend_mode"])
    if rb["shading_model"] != "MSM_DEFAULT_LIT" or rb["two_sided"] or not rb["used_with_skeletal_mesh"]:
        probs.append("FLAGS|%s" % rb)
    if masked and abs(rb["opacity_mask_clip_value"] - MASK_CLIP) > 1e-4:
        probs.append("CLIP|%s" % rb["opacity_mask_clip_value"])
    return rb, probs


def _mi_readback(mi, name):
    mel = unreal.MaterialEditingLibrary
    _require(_path(mi.get_editor_property("parent")) == MI_PARENT, "MI_PARENT|%s|%s" % (name, mi.get_editor_property("parent")))
    master_scalars = [str(n) for n in mel.get_scalar_parameter_names(mi)]
    want = MI_VALUES[name]
    sc = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in want["scalars"]}
    vc = {}
    for k in want["vectors"]:
        c = mel.get_material_instance_vector_parameter_value(mi, k)
        vc[k] = [float(c.r), float(c.g), float(c.b)]
    ov = {k: bool(mel.is_material_instance_parameter_overridden(mi, k))
          for k in list(want["scalars"]) + list(want["vectors"])}
    return {"scalars": sc, "vectors": vc, "overridden": ov}, mi_problems(name, sc, vc, ov, master_scalars)


def _make_mi(name, parent):
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    _require(not eal.does_asset_exist(name), "MI_EXISTS|" + name)
    mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name.rsplit("/", 1)[1], MAT_DIR,
                                                                 unreal.MaterialInstanceConstant,
                                                                 unreal.MaterialInstanceConstantFactoryNew())
    _require(mi is not None, "MI_CREATE|" + name)
    mi.modify()
    mel.set_material_instance_parent(mi, parent)
    for k, v in MI_VALUES[name]["scalars"].items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))          # bool unreliable: read back
    for k, v in MI_VALUES[name]["vectors"].items():
        mel.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(v[0], v[1], v[2], 1.0))
    mel.update_material_instance(mi)
    rb, probs = _mi_readback(mi, name)
    _require(not probs, "MI_READBACK|%s" % probs)
    return mi, rb


def run_build_mat(run, opts, ed):
    eal = unreal.EditorAssetLibrary
    taken = [p for p in mat_stage_assets() if eal.does_asset_exist(p)]
    _require(not taken, "TARGETS_EXIST|%s" % taken)
    manifest = _read(TEX_SRC + "manifest.json")
    before_tex, before_mat = _list_assets(TEX_DIR), _list_assets(MAT_DIR)
    record = {"run": run, "saved": False, "created": [], "opts": opts}
    _write(RECORDS["BUILD_MAT"], record, exclusive=True)
    textures, rb = {}, {"textures": {}, "masters": {}, "mis": {}}
    for key in TEXTURES:
        textures[key], rb["textures"][key] = _import_texture(key, opts["pow2_mode"], manifest)
        record["created"].append(texture_path(key))
    for path, masked in ((M_OPAQUE, False), (M_MASKED, True)):
        _, info = _build_master(path, masked, textures)
        record["created"].append(path)
        rb["masters"][path] = info
    parent = unreal.load_asset(MI_PARENT)
    for name in (MI_OUTER, MI_INNER):
        _, rb["mis"][name] = _make_mi(name, parent)
        record["created"].append(name)
    new = sorted((set(_list_assets(TEX_DIR)) - set(before_tex)) | (set(_list_assets(MAT_DIR)) - set(before_mat)))
    _require(new == mat_stage_assets(), "STRAY_ASSETS|%s" % new)
    _write(RECORDS["BUILD_MAT"], record)
    saved = _save(ed, planned_packages("BUILD_MAT", []))
    for path, masked in ((M_OPAQUE, False), (M_MASKED, True)):
        flags, probs = _master_flags(unreal.load_asset(path), masked)
        _require(not probs, "MASTER_FLAGS|%s|%s" % (path, probs))
        rb["masters"][path]["flags"] = flags
    for name in (MI_OUTER, MI_INNER):
        _, probs = _mi_readback(unreal.load_asset(name), name)
        _require(not probs, "MI_AFTER_SAVE|%s" % probs)
    record.update({"saved": True, "saved_packages": saved["content"], "readback": rb})
    _write(RECORDS["BUILD_MAT"], record)
    unreal.log("S3SACK_COMPILE_CHECK|run=%s|grep Saved/Logs/PussStage.log for 'Failed to compile' + 'M_Sackcloth' in "
               "~20 s, then VERIFY (pixel-shader instructions > 0)" % run)
    return {"created": len(record["created"]), "saved": saved["content"]}


# ------------------------------------------------------------------------------------------- APPLY / REVERT
# Route 3 (conductor 6 Oct, after live APPLY S3SACK-20261006-161735 read back SACK_LEADER=None on all six and the
# cloth's visible/enabled unchanged). Reading of that failure [inf, consistent with every reported number]:
#   a set_editor_property on a component of a placed BP figure reruns the figure's construction script, which
#   REPLACES its components (Body, Face, ShoreHeadCloth). Edits made through the property system are carried to the
#   new components by the instance cache (suspend_simulation survived); a UFUNCTION edit (set_visibility) and any
#   edit made afterwards through the now-dead held reference (enable_simulation) are lost; a leader pointer set to
#   the old Body dangles (reads None).
# So: (1) every figure write goes through set_editor_property on a FRESHLY found component, one property at a time;
#     (2) all cloth writes happen BEFORE any sack exists; (3) the sack is a BP_S3SackFollower (child of
#     SkeletalMeshActor) whose construction script and BeginPlay call RelinkLeader (attach parent named "Body" ->
#     SetLeaderPoseComponent), so it re-links itself after reconstruction or in PIE; (4) every read-back re-finds
#     everything by name. Every lookup for every figure still runs before the first mutation.
def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _tags(actor):
    return [str(t) for t in (actor.get_editor_property("tags") or [])]


def _sack_actors(fig=None, world=None):
    """Every actor that is, or claims to be, a sack: tag S3.Sack, or a label ending " Sack". GameplayStatics sees
    transient actors too (memory puss-benches)."""
    out = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world or _world(), unreal.Actor):
        label = str(a.get_actor_label())
        if SACK_TAG in _tags(a) or label.endswith(" Sack"):
            if fig is None or label == sack_label(fig) or (SACK_TAG + "." + fig) in _tags(a):
                out.append(a)
    return out


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _rot(r):
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def _drape_head_cm(fig):
    """The head bone in the sack's bind (drape) pose, Body component space, cm (Blender JSON
    pose.record_head_m_ue_component). An UNLED sack draws its head here."""
    src = _read(source_files(fig)["json"])
    return [100.0 * float(v) for v in src["pose"]["record_head_m_ue_component"]]


def _leader_evidence(c, body, drape_head_cm):
    """Two independent reads of 'is the sack led by THIS Body':
      prop   leader_pose_component resolves to the current Body (None if Python cannot read the weak pointer);
      socket the sack's 'head' socket coincides with the Body's (a follower reads its bones from the leader [inf]),
             conclusive only when the Body's current head is > 2 cm from the drape-pose head (else an unled sack
             would coincide too)."""
    ev = {"prop": None, "socket_gap_cm": None, "socket_conclusive": False, "socket_led": False}
    try:
        lp = _leader(c)
        ev["prop_value"] = _full(lp)
        ev["prop"] = lp is not None and _full(lp) == _full(body)
    except SackError as exc:
        ev["prop_error"] = str(exc)
    try:
        sh, bh = c.get_socket_location("head"), body.get_socket_location("head")
        ev["socket_gap_cm"] = math.dist(_vec(sh), _vec(bh))
        cs = _vec(unreal.MathLibrary.inverse_transform_location(body.get_world_transform(), bh))
        ev["body_head_cs_cm"] = cs
        ev["body_vs_drape_head_cm"] = math.dist(cs, drape_head_cm)
        ev["socket_conclusive"] = ev["body_vs_drape_head_cm"] > 2.0
        ev["socket_led"] = ev["socket_conclusive"] and ev["socket_gap_cm"] < 0.5
    except Exception as exc:  # noqa: BLE001 - evidence, reported
        ev["socket_error"] = str(exc)
    ev["led"] = bool(ev["prop"]) or bool(ev["socket_led"])
    return ev


def _figure_state(actor, fig, world=None):
    """Everything APPLY touches or must not touch, for one placed figure (read-only, all found fresh by name)."""
    body, bm = _body_mesh(actor)
    face = _one(actor, FACE, "SkeletalMeshComponent")
    cloth = _one(actor, CLOTH_COMPONENT, "ChaosClothComponent")
    sacks = _sack_actors(fig, world)
    st = {"actor": actor.get_path_name(), "label": str(actor.get_actor_label()),
          "body_mesh": _path(bm), "body_skeleton": _path(bm.get_editor_property("skeleton")),
          "body_leader": _leader_path_safe(body), "body_overrides": _overrides(body),
          "face_overrides": _overrides(face),
          "cloth": _cloth_state(cloth), "sack": None, "sack_actors": sorted(_full(a) for a in sacks),
          # an instance component from the abandoned first route must never exist
          "legacy_sack_component": len(_components(actor, SACK_COMPONENT))}
    if len(sacks) == 1:
        sa = sacks[0]
        c = sa.get_editor_property("skeletal_mesh_component")      # SkeletalMeshActor.h:38-39
        root = sa.get_editor_property("root_component")
        n = int(c.get_num_materials())
        ap = root.get_attach_parent() if root is not None else None
        st["sack"] = {"actor": _full(sa), "label": str(sa.get_actor_label()), "class": str(sa.get_class().get_name()),
                      "tags": sorted(_tags(sa)), "root_is_mesh_component": _full(root) == _full(c),
                      "mesh": _path(c.get_skeletal_mesh_asset()),
                      "materials": [_path(c.get_material(i)) for i in range(n)],
                      "attach_parent": str(ap.get_name()) if ap is not None else None,
                      "attach_parent_is_body": ap is not None and _full(ap) == _full(body),
                      "attach_parent_actor_is_figure": _full(sa.get_attach_parent_actor()) == _full(actor),
                      "socket": str(root.get_attach_socket_name()) if root is not None else None,
                      "relative_location": _vec(root.get_editor_property("relative_location")),
                      "relative_rotation": _rot(root.get_editor_property("relative_rotation")),
                      "relative_scale": _vec(root.get_editor_property("relative_scale3d")),
                      "leader_evidence": _leader_evidence(c, body, _drape_head_cm(fig)),
                      "bounds_scale": float(c.get_editor_property("bounds_scale")),
                      "visible": bool(c.get_editor_property("visible")),
                      "num_bones": int(c.get_num_bones()),
                      "bone_names_missing_on_body": sorted(
                          {str(c.get_bone_name(i)) for i in range(int(c.get_num_bones()))}
                          - {str(body.get_bone_name(i)) for i in range(int(body.get_num_bones()))})[:8]}
    return st


def _sack_problems(fig, st, slots, opts):
    want = apply_expectation(fig, slots)
    s = st.get("sack")
    if s is None or len(st.get("sack_actors", [])) != 1:
        return ["SACK_ACTORS|%s|%s" % (fig, st.get("sack_actors"))]
    probs = []
    if s["label"] != sack_label(fig) or not {SACK_TAG, SACK_TAG + "." + fig} <= set(s["tags"]):
        probs.append("SACK_IDENTITY|%s|%s|%s" % (fig, s["label"], s["tags"]))
    if s["class"] != SACK_BP_CLASS_NAME or not s["root_is_mesh_component"]:
        probs.append("SACK_CLASS|%s|%s" % (fig, s["class"]))
    if s["mesh"] != want["mesh"]:
        probs.append("SACK_MESH|%s|%s" % (fig, s["mesh"]))
    if s["materials"] != want["materials"]:
        probs.append("SACK_MATERIALS|%s|%s" % (fig, s["materials"]))
    if not (s["attach_parent_is_body"] and s["attach_parent_actor_is_figure"]) or s["socket"] not in ("None", ""):
        probs.append("SACK_ATTACH|%s|%s|%s" % (fig, s["attach_parent"], s["socket"]))
    probs += relative_identity_problems(fig, s)
    if not s["leader_evidence"]["led"]:
        probs.append("SACK_LEADER|%s|%s" % (fig, json.dumps(s["leader_evidence"], default=str)))
    if abs(s["bounds_scale"] - opts["bounds_scale"]) > 1e-4:
        probs.append("SACK_BOUNDS_SCALE|%s|%s" % (fig, s["bounds_scale"]))
    if not s["visible"]:
        probs.append("SACK_HIDDEN|%s" % fig)
    if s["bone_names_missing_on_body"]:
        probs.append("SACK_BONES_NOT_ON_BODY|%s|%s" % (fig, s["bone_names_missing_on_body"]))
    if st.get("legacy_sack_component"):
        probs.append("LEGACY_SACKSK_COMPONENT|%s" % fig)
    return probs


def _slots_from_import(fig, mesh):
    rec = _read(RECORDS["IMPORT"])
    _require(fig in rec.get("figures", {}) and rec["figures"][fig].get("saved"), "NOT_IMPORTED|" + fig)
    return classify_slots(_mesh_slots(mesh))


def _sack_bp_class():
    """The follower BP (authored by the MCPBlueprintsGenerator specs, see s3_sack_follower_bp_*.json): exists, is a
    SkeletalMeshActor, has RelinkLeader. Returns the generated class."""
    eal = unreal.EditorAssetLibrary
    _require(eal.does_asset_exist(SACK_BP), "SACK_BP_MISSING|%s (apply the s3_sack_follower_bp specs first)" % SACK_BP)
    bp = unreal.load_asset(SACK_BP)
    _require(unreal.BlueprintEditorLibrary.find_graph(bp, "RelinkLeader") is not None, "SACK_BP_NO_RELINK|" + SACK_BP)
    cls = eal.load_blueprint_class(SACK_BP)
    _require(cls is not None and isinstance(unreal.get_default_object(cls), unreal.SkeletalMeshActor),
             "SACK_BP_PARENT|%s" % cls)
    return cls


def _apply_lookups(figs):
    """Phase 1 of APPLY: every read, for every figure, before anything is touched. Returns the plan."""
    mat_rec = _read(RECORDS["BUILD_MAT"])
    _require(mat_rec.get("saved"), "MAT_RECORD_UNSAVED")
    api = _api_presence()
    need = ["EditorActorSubsystem.spawn_actor_from_class", "EditorActorSubsystem.destroy_actor",
            "Actor.attach_to_component", "BlueprintEditorLibrary.find_graph", "EditorAssetLibrary.load_blueprint_class",
            "MathLibrary.inverse_transform_location"]
    _require(all(api.get(k) for k in need), "API_MISSING|%s" % [k for k in need if not api.get(k)])
    bp_class = _sack_bp_class()
    meshes = {f: unreal.load_asset(mesh_path(f)) for f in figs}
    mis = {r: unreal.load_asset(p) for r, p in SLOT_MI.items()}
    missing = [mesh_path(f) for f, m in meshes.items() if m is None] + [SLOT_MI[r] for r, m in mis.items() if m is None]
    _require(not missing, "ASSETS_MISSING|%s" % missing)
    _temp_actor_guard(_world())
    actors = _figure_actors(figs)
    plan, probs = {}, []
    for f in figs:
        a = actors[f]
        _one(a, CLOTH_COMPONENT, "ChaosClothComponent")
        st = _figure_state(a, f)
        if st["sack_actors"]:
            probs.append("SACK_EXISTS|%s|%s" % (f, st["sack_actors"]))
        if st["legacy_sack_component"]:
            probs.append("LEGACY_SACKSK_COMPONENT|%s" % f)
        if st["body_skeleton"] != SKELETON:
            probs.append("BODY_SKELETON|%s|%s" % (f, st["body_skeleton"]))
        if st["body_leader"] not in (None, "UNREADABLE"):
            probs.append("BODY_HAS_LEADER|%s|%s (a follower of a follower is unproven)" % (f, st["body_leader"]))
        plan[f] = {"actor": a, "mesh": meshes[f], "slots": _slots_from_import(f, meshes[f]), "before": st,
                   "folder": str(a.get_folder_path()), "drape_head_cm": _drape_head_cm(f)}
    stray = [_full(x) for x in _sack_actors() if not any(_full(x) in plan[f]["before"]["sack_actors"] for f in figs)]
    if stray:
        probs.append("STRAY_SACK_ACTORS|%s" % stray)
    _require(not probs, "PLAN_PROBLEMS|%s" % probs)
    return plan, mis, bp_class


def _set_cloth(actor, want):
    """One property per write, each on a FRESHLY found ShoreHeadCloth (a write may rebuild the figure's components),
    through the property system (the path the instance cache carries across a rebuild). Read back fresh."""
    for key, prop in CLOTH_PROPS:
        cloth = _one(actor, CLOTH_COMPONENT, "ChaosClothComponent")
        cloth.modify()
        cloth.set_editor_property(prop, bool(want[key]))
    got = _cloth_state(_one(actor, CLOTH_COMPONENT, "ChaosClothComponent"))
    bad = state_diff({k: want[k] for k, _p in CLOTH_PROPS}, got, [k for k, _p in CLOTH_PROPS])
    _require(not bad, "CLOTH_READBACK|%s|%s" % (actor.get_actor_label(), bad))
    return got


def _spawn_sack(f, p, mis, bp_class, opts):
    """Phase 3b, one figure, after every cloth write. Sack-actor writes go first (each may rebuild the sack BP; its
    mesh component is native, so it survives), then attach, then a deliberate construction rerun (re-set the tags)
    so the BP's own construction script does the linking. RelinkLeader via call_method is the fallback, recorded."""
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = p["actor"]
    body, _bm = _body_mesh(actor)                                       # fresh: after the cloth writes
    t = body.get_world_transform()
    sa = eas.spawn_actor_from_class(bp_class, t.translation, t.rotation.rotator())
    _require(sa is not None, "SPAWN_FAILED|%s" % f)
    sa.modify()
    sa.set_actor_label(sack_label(f))
    sa.set_actor_scale3d(t.scale3d)
    tags = [unreal.Name(SACK_TAG), unreal.Name(SACK_TAG + "." + f)]
    sa.set_editor_property("tags", tags)
    if p["folder"] not in ("", "None"):
        sa.set_folder_path(p["folder"])
    c = sa.get_editor_property("skeletal_mesh_component")
    _require(c is not None, "NO_MESH_COMPONENT|%s" % f)
    c.modify()
    try:
        c.set_editor_property("skeletal_mesh_asset", p["mesh"])       # SkeletalMeshComponent.h:360-361 (Setter=)
    except Exception:  # noqa: BLE001 - property path refused: the UFUNCTION (SkeletalMeshComponent.h:369); read back
        c.set_skeletal_mesh_asset(p["mesh"])
    mats = [None, None, None]
    for role, idx in p["slots"].items():
        mats[idx] = mis[role]
    c = sa.get_editor_property("skeletal_mesh_component")
    c.set_editor_property("override_materials", mats)
    c = sa.get_editor_property("skeletal_mesh_component")
    c.set_editor_property("bounds_scale", opts["bounds_scale"])
    body, _bm = _body_mesh(actor)
    keep = unreal.AttachmentRule.KEEP_WORLD
    sa.attach_to_component(body, unreal.Name(""), keep, keep, keep, False)   # AActor::K2_AttachToComponent
    sa.set_editor_property("tags", tags)                                # construction rerun -> RelinkLeader
    body, _bm = _body_mesh(actor)
    ev = _leader_evidence(sa.get_editor_property("skeletal_mesh_component"), body, p["drape_head_cm"])
    path = "construction"
    if not ev["led"]:
        sa.call_method("RelinkLeader")                                  # BP function (call_method: as ConfigureShoreDrape)
        ev = _leader_evidence(sa.get_editor_property("skeletal_mesh_component"), body, p["drape_head_cm"])
        path = "call_method" if ev["led"] else "none"
    return sa, path, ev


def run_apply(run, opts, figs, ed):
    c0 = _census()
    plan, mis, bp_class = _apply_lookups(figs)
    c1 = _census()
    _require(c1 == c0, "LOOKUP_DIRTIED|%s -> %s (a READ dirtied the editor; this tool mutated nothing)"
             % (json.dumps(c0), json.dumps(c1)))
    before = {f: p["before"] for f, p in plan.items()}
    slots = {f: p["slots"] for f, p in plan.items()}
    record = {"run": run, "world": WORLD, "route": "BP_S3SackFollower", "figures": figs, "opts": opts, "slots": slots,
              "before": before, "spawned": {}, "saved": False}
    _write(RECORDS["APPLY"], record, exclusive=True)
    record["backup"], record["backup_files"] = _backup_umap(run)
    _write(RECORDS["APPLY"], record)
    # ---------------- first mutation below this line
    for f in figs:                                     # 3a: every figure write first (each may rebuild that figure)
        _set_cloth(plan[f]["actor"], cloth_target(before[f]["cloth"], opts["cloth_switch"]))
    for f in figs:                                     # 3b: then the sacks, attached to the rebuilt Bodies
        sa, path, ev = _spawn_sack(f, plan[f], mis, bp_class, opts)
        record["spawned"][f] = {"path": _full(sa), "label": sack_label(f), "relink_path": path, "evidence": ev}
        _write(RECORDS["APPLY"], record)
    actors = _figure_actors(figs)                      # everything re-found by name
    after = {f: _figure_state(actors[f], f) for f in figs}
    record["after"] = after
    _write(RECORDS["APPLY"], record)
    bad = _apply_problems(figs, before, after, slots, opts)
    _require(not bad, "APPLY_READBACK|%s" % bad[:8])
    record["saved_packages"] = _save(ed, planned_packages("APPLY", figs))
    record["saved"] = True
    _write(RECORDS["APPLY"], record)
    again = {f: _figure_state(a, f) for f, a in _figure_actors(figs).items()}
    bad = _apply_problems(figs, before, again, slots, opts)
    _require(not bad, "APPLY_READBACK_AFTER_SAVE|%s" % bad[:8])
    return {"figures": figs, "backup": record["backup"], "saved": record["saved_packages"],
            "relink": {f: v["relink_path"] for f, v in record["spawned"].items()}}


def _apply_problems(figs, before, after, slots, opts):
    bad = []
    for f in figs:
        b, a = before[f], after[f]
        bad += _sack_problems(f, a, slots[f], opts)
        want_cloth = cloth_target(b["cloth"], opts["cloth_switch"])
        d = state_diff(want_cloth, a["cloth"], [k for k, _p in CLOTH_PROPS])
        if d:
            bad.append("CLOTH|%s|%s" % (f, d))
        for k in ("body_overrides", "face_overrides", "body_mesh", "body_leader"):
            if a[k] != b[k]:
                bad.append("UNTOUCHED_CHANGED|%s|%s|%s->%s" % (f, k, b[k], a[k]))
    return bad


def run_revert(run, opts, ed):
    record = _read(RECORDS["APPLY"])
    _require(record.get("world") == WORLD and record.get("saved"), "RECORD_INVALID")
    _require(record.get("route") == "BP_S3SackFollower", "RECORD_ROUTE|%s" % record.get("route"))
    figs, before, slots = record["figures"], record["before"], {f: dict(v) for f, v in record["slots"].items()}
    # ---------------- lookups (all figures) before any mutation
    c0 = _census()
    _temp_actor_guard(_world())
    actors = _figure_actors(figs)
    now = {f: _figure_state(a, f) for f, a in actors.items()}
    drift = _apply_problems(figs, before, now, slots, record["opts"])
    _require(not drift, "DRIFT_SINCE_APPLY|%s" % drift[:8])
    for f in figs:
        hits = _sack_actors(f)
        _require(len(hits) == 1 and _full(hits[0]) == record["spawned"][f]["path"],
                 "SACK_NOT_THE_RECORDED_ONE|%s|%s" % (f, [_full(h) for h in hits]))
        _one(actors[f], CLOTH_COMPONENT, "ChaosClothComponent")
    _require(_census() == c0, "LOOKUP_DIRTIED|%s" % json.dumps(_census()))
    backup, _ = _backup_umap(run, "Revert")
    # ---------------- first mutation below this line
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for f in figs:                                     # sacks first: nothing then points at the Bodies
        sa = _sack_actors(f)
        _require(len(sa) == 1, "SACK_GONE_MIDWAY|%s" % f)
        _require(bool(eas.destroy_actor(sa[0])), "DESTROY_FAILED|%s" % f)
    left = [_full(a) for a in _sack_actors()]
    _require(not left, "SACKS_REMAIN|%s" % left)
    for f in figs:
        _set_cloth(_figure_actors([f])[f], before[f]["cloth"])
    actors = _figure_actors(figs)
    back = {f: _figure_state(a, f) for f, a in actors.items()}
    bad = []
    for f in figs:
        for k in ("cloth", "body_overrides", "face_overrides", "body_mesh", "body_leader", "sack", "sack_actors",
                  "legacy_sack_component"):
            want, got = before[f][k], back[f][k]
            if k == "cloth":
                d = state_diff(want, got, [k2 for k2, _p in CLOTH_PROPS])
                if d:
                    bad.append("CLOTH|%s|%s" % (f, d))
            elif got != want:
                bad.append("%s|%s|%s!=%s" % (k, f, got, want))
    _require(not bad, "REVERT_READBACK|%s" % bad[:8])
    saved = _save(ed, planned_packages("REVERT", figs))
    os.replace(RECORDS["APPLY"], RECORDS["APPLY"] + ".reverted-" + run)
    return {"figures": figs, "backup": backup, "saved": saved, "assets_kept": True}


def run_pie_probe(run, figs, ed):
    """Read-only, ONLY while PIE runs (never starts or ends it): in the GAME world, every sack is led by its figure's
    Body (prop or socket evidence), the cloth is hidden and suspended. This is the persistence proof: the PIE world
    is a fresh copy of the saved level, constructed and BeginPlay'd."""
    gw = ed.get_game_world()
    _require(gw is not None, "PIE_NOT_RUNNING (Gary starts PIE; this probe never starts or ends it)")
    by_label = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(gw, unreal.Actor):
        by_label.setdefault(str(a.get_actor_label()), []).append(a)
    out, fails = {"run": run, "figures": {}}, []
    for f in figs:
        figs_hit, sacks = by_label.get(f + " Clam", []), by_label.get(sack_label(f), [])
        if len(figs_hit) != 1 or len(sacks) != 1:
            fails.append("PIE_ACTORS|%s|clam=%d|sack=%d" % (f, len(figs_hit), len(sacks)))
            continue
        body, _bm = _body_mesh(figs_hit[0])
        c = sacks[0].get_editor_property("skeletal_mesh_component")
        ev = _leader_evidence(c, body, _drape_head_cm(f))
        cl = _cloth_state(_one(figs_hit[0], CLOTH_COMPONENT, "ChaosClothComponent"))
        out["figures"][f] = {"evidence": ev, "cloth": cl}
        if not ev["led"]:
            fails.append("PIE_NOT_LED|%s|%s" % (f, json.dumps(ev, default=str)))
        if cl["visible"] or not cl["suspended"]:
            fails.append("PIE_CLOTH|%s|%s" % (f, cl))
    out["fails"] = fails
    _write(PIE_OUT, out)
    _require(not fails, "PIE_PROBE|%s|out=%s" % (fails[:6], PIE_OUT))
    return {"figures": len(figs), "out": PIE_OUT}


# ------------------------------------------------------------------------------------------- DRY / VERIFY
def _has(cls_name, attr=None):
    cls = getattr(unreal, cls_name, None)
    return cls is not None and (attr is None or hasattr(cls, attr))


def _api_presence():
    want = [("InterchangeGenericAssetsPipeline", None), ("InterchangePipelineStackOverride", None),
            ("EditorActorSubsystem", "spawn_actor_from_class"), ("EditorActorSubsystem", "destroy_actor"),
            ("SkeletalMeshActor", None), ("Actor", "attach_to_component"),
            ("BlueprintEditorLibrary", "find_graph"), ("EditorAssetLibrary", "load_blueprint_class"),
            ("MathLibrary", "inverse_transform_location"),
            ("SkinnedMeshComponent", "set_leader_pose_component"), ("SkeletalMeshComponent", "set_skeletal_mesh_asset"),
            ("SkeletalMeshEditorSubsystem", "get_bone_children"), ("SkeletalMeshEditorSubsystem", "get_lod_count"),
            ("SkeletalMeshEditorSubsystem", "get_num_verts"), ("ChaosClothComponent", None),
            ("TexturePowerOfTwoSetting", None), ("MaterialEditingLibrary", "is_material_instance_parameter_overridden")]
    return {(c if a is None else c + "." + a): _has(c, a) for c, a in want}


def run_dry(run, opts, figs):
    eal = unreal.EditorAssetLibrary
    c0 = _census()
    out = {"run": run, "figures": figs, "opts": opts, "census": c0, "problems": [], "api": _api_presence()}
    out["problems"] += ["API_MISSING|%s" % k for k, v in out["api"].items() if not v]
    rows, probs = _sources(figs, opts["fbx_suffix"])
    out["problems"] += probs
    out["sources"] = {f: {"files": r["files"], "sha256": r["sha256"], "fbx_tree_root": r["summary"]["tree"].get(ROOT_BONE),
                          "fbx_bones": len(r["summary"]["bones"]), "problems": r["problems"]} for f, r in rows.items()}
    for f in figs:   # the originals, for the record (expected to fail the root gate: why _SK_root exists)
        sf = source_files(f, "_SK.fbx")
        if os.path.isfile(sf["fbx"]):
            out.setdefault("original_sk_fbx_root_gate", {})[f] = fbx_structure_problems(fbx_skeleton_summary(sf["fbx"]))
    actors = _figure_actors(figs)
    out["figures_live"] = {}
    for f, a in actors.items():
        st = _figure_state(a, f)
        _, bm = _body_mesh(a)
        tree = _bone_tree(bm)
        st["body_bones"] = len(tree)
        st["body_root_child"] = sorted(_bone_children(bm, ROOT_BONE))
        if f in rows:
            names = set(rows[f]["summary"]["bones"])
            st["fbx_bones_not_on_body"] = sorted(names - set(tree))[:8]
            if st["fbx_bones_not_on_body"]:
                out["problems"].append("FBX_BONES_NOT_ON_BODY|%s|%s" % (f, st["fbx_bones_not_on_body"]))
        if st["body_skeleton"] != SKELETON:
            out["problems"].append("BODY_SKELETON|%s|%s" % (f, st["body_skeleton"]))
        if st["body_leader"] not in (None, "UNREADABLE"):
            out["problems"].append("BODY_HAS_LEADER|%s|%s" % (f, st["body_leader"]))
        if st["sack_actors"] or st["legacy_sack_component"]:
            out["problems"].append("SACK_ALREADY_PRESENT|%s|%s" % (f, st["sack_actors"]))
        out["figures_live"][f] = st
    if os.path.exists(SKIN_RECORD):
        skin = _read(SKIN_RECORD)
        out["skin_pass"] = {"run": skin.get("run"), "target": skin.get("target"), "saved": skin.get("saved")}
        for f in figs:
            plan = (skin.get("plan") or {}).get(f, {}).get("components", {})
            live = out["figures_live"].get(f, {})
            for comp, key in (("Body", "body_overrides"), ("Face", "face_overrides")):
                want = [x for x in plan.get(comp, {}).get("override_after", [])]
                got = live.get(key)
                if want and got != want:
                    out["problems"].append("SKIN_OVERRIDES_NOT_AS_RECORDED|%s|%s" % (f, comp))
    out["targets"] = {p: bool(eal.does_asset_exist(p)) for p in [mesh_path(f) for f in figs] + mat_stage_assets()}
    try:
        _sack_bp_class()
        out["sack_bp"] = "OK"
    except SackError as exc:
        out["sack_bp"] = str(exc)
        out["problems"].append(str(exc))
    out["would_save"] = {m: planned_packages(m, figs) for m in WRITE_MODES}
    out["apply_backs_up"] = [UMAP]
    _require(_census() == c0, "DRY_MUTATED|%s" % _census())
    _write(DRY_OUT, out)
    unreal.log("S3SACK_PLAN|run=%s|%s" % (run, json.dumps({"problems": out["problems"][:12], "api_missing":
                                                          [k for k, v in out["api"].items() if not v],
                                                          "targets_existing": [k for k, v in out["targets"].items() if v]},
                                                         default=str)))
    if out["problems"]:
        unreal.log_warning("S3SACK_DRY_PROBLEMS|run=%s|%d|%s" % (run, len(out["problems"]), out["problems"][:6]))
    return {"figures": len(figs), "problems": len(out["problems"]), "out": DRY_OUT}


def run_verify(run):
    c0 = _census()
    out = {"run": run, "fails": [], "stages": {}}
    if os.path.exists(RECORDS["IMPORT"]):
        rec = _read(RECORDS["IMPORT"])
        out["stages"]["IMPORT"] = sorted(rec.get("figures", {}))
        for f, row in rec.get("figures", {}).items():
            try:
                src = _read(row["source"]["json"])
                if os.path.isfile(row["source"]["fbx"] + ".json"):
                    src["_reexport"] = _read(row["source"]["fbx"] + ".json")
                actor = _figure_actors([f])[f]
                _, bm = _body_mesh(actor)
                _, p = _mesh_readback(f, unreal.load_asset(mesh_path(f)), src, _bone_tree(bm))
                out["fails"] += p
            except Exception as exc:  # noqa: BLE001 - a verifier reports, it never swallows
                out["fails"].append("IMPORT|%s|%s" % (f, exc))
    if os.path.exists(RECORDS["BUILD_MAT"]):
        out["stages"]["BUILD_MAT"] = True
        mel = unreal.MaterialEditingLibrary
        for path, masked in ((M_OPAQUE, False), (M_MASKED, True)):
            m = unreal.load_asset(path)
            if m is None:
                out["fails"].append("MASTER_MISSING|" + path)
                continue
            _, p = _master_flags(m, masked)
            out["fails"] += p
            ps = int(mel.get_statistics(m).get_editor_property("num_pixel_shader_instructions"))
            out.setdefault("ps_instructions", {})[path] = ps
            if ps <= 0:
                out["fails"].append("NOT_COMPILED|%s|ps=%d" % (path, ps))
        for name in (MI_OUTER, MI_INNER):
            mi = unreal.load_asset(name)
            if mi is None:
                out["fails"].append("MI_MISSING|" + name)
                continue
            _, p = _mi_readback(mi, name)
            out["fails"] += p
        for key in TEXTURES:
            t = unreal.load_asset(texture_path(key))
            if t is None:
                out["fails"].append("TEXTURE_MISSING|" + key)
                continue
            got = _texture_settings(t)
            out.setdefault("textures", {})[key] = got
            out["fails"] += texture_settings_problems(key, got, _read(RECORDS["BUILD_MAT"])["opts"]["pow2_mode"])
    if os.path.exists(RECORDS["APPLY"]):
        rec = _read(RECORDS["APPLY"])
        out["stages"]["APPLY"] = rec["figures"]
        actors = _figure_actors(rec["figures"])
        now = {f: _figure_state(a, f) for f, a in actors.items()}
        out["live"] = now
        out["fails"] += _apply_problems(rec["figures"], rec["before"], now, rec["slots"], rec["opts"])
        if os.path.exists(SKIN_RECORD):
            skin = _read(SKIN_RECORD)
            for f in rec["figures"]:
                plan = (skin.get("plan") or {}).get(f, {}).get("components", {})
                for comp, key in (("Body", "body_overrides"), ("Face", "face_overrides")):
                    want = plan.get(comp, {}).get("override_after")
                    if want and now[f][key] != want:
                        out["fails"].append("SKIN_OVERRIDES_CHANGED|%s|%s" % (f, comp))
    if _census() != c0:
        out["fails"].append("VERIFY_MUTATED|%s" % _census())
    _write(VERIFY_OUT, out)
    _require(not out["fails"], "VERIFY|%s|out=%s" % (out["fails"][:6], VERIFY_OUT))
    return {"stages": out["stages"], "out": VERIFY_OUT}


def main():
    run = datetime.datetime.now().strftime("S3SACK-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        args = _read(ARGS)
        mode, figs, opts = check_mode(args, {k: os.path.exists(v) for k, v in RECORDS.items()})
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = ed.get_editor_world()
        _require(world is not None and str(world.get_outermost().get_name()) == WORLD, "WRONG_WORLD")
        if mode != "PIE_PROBE":
            _require(ed.get_game_world() is None, "PIE_ACTIVE (never end PIE: refuse instead)")
        unreal.log("S3SACK_START|run=%s|mode=%s|figures=%s|opts=%s" % (run, mode, figs, json.dumps(opts)))
        if mode == "PIE_PROBE":
            result = run_pie_probe(run, figs, ed)
        elif mode == "DRY":
            result = run_dry(run, opts, figs)
        elif mode == "VERIFY":
            result = run_verify(run)
        else:
            c0 = _census()
            _require(c0 == {"content": [], "maps": []}, "DIRTY_BEFORE|" + json.dumps(c0))
            if mode == "IMPORT":
                result = run_import(run, opts, figs, ed)
            elif mode == "BUILD_MAT":
                try:
                    result = run_build_mat(run, opts, ed)
                except Exception:
                    if os.path.exists(RECORDS["BUILD_MAT"]) and not _read(RECORDS["BUILD_MAT"]).get("saved"):
                        os.replace(RECORDS["BUILD_MAT"], RECORDS["BUILD_MAT"] + ".failed-" + run)
                    raise
            elif mode == "APPLY":
                try:
                    result = run_apply(run, opts, figs, ed)
                except Exception:
                    if os.path.exists(RECORDS["APPLY"]) and not _read(RECORDS["APPLY"]).get("saved"):
                        os.replace(RECORDS["APPLY"], RECORDS["APPLY"] + ".failed-" + run)
                    raise
            else:
                result = run_revert(run, opts, ed)
        unreal.log("S3SACK_%s_OK|run=%s|%s" % (mode, run, json.dumps(result, default=str)))
    except Exception as exc:
        census = {}
        try:
            census = _census()
        except Exception:  # noqa: BLE001
            pass
        unreal.log_error("S3SACK_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            run, mode, str(exc).replace("\n", " "), json.dumps(census),
            "NOTHING SAVED unless an _OK marker printed; if anything is dirty: Don't-Save restart (never reload the "
            "open level)" if mode in WRITE_MODES else "read-only mode"))
        raise


if unreal is not None and os.environ.get("S3SACK_NO_AUTORUN") != "1":
    main()
