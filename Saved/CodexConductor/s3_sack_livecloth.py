"""S3 LIVE sackcloth: make each shore figure's existing LIVE Chaos head drape (ShoreHeadCloth) a 2.0 x 2.0 m heavy
hessian sack. Written 6 Oct 2026 OFFLINE (Unreal not run, MCP not called). Gary's choice, 6 Oct 17:00: "Live cloth with
the new sack" (after the skinned follower sacks, S3SACK-20261006-163706, floated / did not collide / rendered white and
were reverted).

WHAT IT DOES (per figure <id>, all names versioned: _v<version>):
  BUILD  (create-only content; never touches a BP or the level)
    - M_Sackcloth_Masked_Cloth (+ M_Sackcloth_Cloth if material_variant=opaque): DUPLICATES of today's masters with
      two_sided=True (Chaos simulates ONE surface: the back must render) and used_with_clothing=True (else saving the
      cloth asset re-dirties the MI, ChaosClothCurtain.md "Engine traps" 5). No node is added or deleted.
    - MI_Sackcloth_OldGrey_Cloth: a duplicate of MI_Sackcloth_OldGrey re-parented to the cloth master; every
      overridden scalar/vector/texture value is read back equal to the source MI.
    - SM_ShoreSack_<id>_v<N>: a FLAT torn-edged 2.0 m sheet built in-editor with GeometryScript (no importer: no
      axis/unit/V-flip traps), positioned in the cloth COMPONENT frame of that figure: perpendicular to world-up,
      its pin point over the crown (upright, sheet centre 20 cm FORWARD of the pin) or over the mid-back (Shore02).
      UV0 = flat-pattern METRES (the 2D sim pattern = UV0 x 100 cm, isometric to the 3D sheet: rest = start, no
      pre-stress), UV1 = (distance to the torn edge m, per-figure random) for the material's fray fringe and grime.
    - DF_ShoreSack_<id>_v<N>: Dataflow graph built node by node (Scripts/build_curtain_chaos_asset.py pattern):
      StaticMeshImport_v2 -> BindToRootBone -> spatial crown weight (sphere distance -> smoothstep -> attribute, the
      SAME mechanism as Saved/CodexMocap/fix_spatial_crown_attachment.py) -> Mass -> Stretch -> Bending -> Damping
      -> Aerodynamics -> Collision [-> SelfCollision] -> Solver -> MaxDistance(weight map) -> LongRangeAttachment
      -> ClothAssetTerminal_v2.  Rest = FLAT 2D pattern (bStretchUse3dRestLengths False, RestAngleType
      FlatnessRatio 1): the rest-shape trap (ChaosClothCurtain.md "Read this first").
    - CA_ShoreSack_<id>_v<N>: Chaos Cloth Asset linked to that graph, evaluated; its material slot 0 must read back
      as the MI (the evaluation fills slots from the render mesh, whose slot 0 carries the MI).
  APPLY  (the six figure BPs; Gary chose this: the BP template is the persistent place)
    - In BP_<id>_Draped, template ShoreHeadCloth (class must be EXACTLY ChaosClothComponent: never a pose component,
      memory puss-chaos-cloth-teleport-floor): set_asset(CA_ShoreSack_<id>_v<N>), set_material(0, MI), relative
      scale 1.0 (the old 1.641315 scaled a 1 m sheet; the new sheet is authored at true size). Location, rotation,
      absolute-rotation (Shore02) are KEPT. ConfigureShoreDrape (construction + BeginPlay: attach to Body "head",
      ResetCollisionSources, AddCollisionSource(Body, PHYS_<id>_Drape)) is NOT touched; it sets no material and no
      asset (binary strings of the BP: no SetMaterial/SetAsset symbol), so the template values reach PIE.
    - Refuses if a level instance of the figure overrides the cloth's asset / materials / scale (the template change
      would not reach it).
    - Backup Backups/PreS3LiveSack-<run>/ (the six BP .uasset + the umap) BEFORE the first write.
    - Then sets the INSTANCE asset on each placed figure (fresh lookup; see VERSION 2) and saves exactly the BP
      packages + the level (required) in one scope, after every read-back passed.
  REVERT the exact inverse of the APPLY record (old asset, old override material, old scale on the templates; the old
         instance assets from instance_asset_override), drift-checked first (templates AND instance assets), all
         read back before ONE save (BPs + level).
         The created assets stay (create-only; unreferenced after REVERT).
  VERIFY read-only: assets, graph link, CA slot material, BP templates, level instances (asset, material,
         attach parent = the CURRENT Body / socket head).
  SIM_START / SIM_READ / SIM_STOP  editor-world probe (never PIE; Gary owns PIE): Simulate-In-Editor on the chosen
         figures' level instances (bSimulateInEditor is Transient and per instance, ClothComponent.h:489-490: it must
         not dirty anything; the census is asserted unchanged), read component bounds (indicative only: cloth bounds
         may be padded, ChaosClothCurtain.md "State and proof"), optional high-res still from a named camera, stop.
  PIE_PROBE read-only while Gary's PIE runs (never starts or ends PIE): in the GAME world every figure's
         ShoreHeadCloth plays CA_ShoreSack_<id>_v<N>, material 0 = the MI, parent = that actor's Body at socket
         "head", scale 1, simulation enabled; interactor config values (density, bending, collision thickness,
         iterations, substeps) reported against the asset's.

Args Saved/CodexConductor/s3_sack_livecloth_args.json:
  {"mode": "DRY"|"BUILD"|"APPLY"|"REVERT"|"VERIFY"|"SIM_START"|"SIM_READ"|"SIM_STOP"|"PIE_PROBE",
   "confirm": "<MODE> S3LIVESACK"          (write modes only: BUILD, APPLY, REVERT),
   "figures": [...]                         (default all six; BUILD/APPLY may pilot a subset),
   "version": 1, "params": {...}            (overrides of PARAMS below, validated),
   "forward_local_override": {"<id>": [x,y,z]}   (only if a face has no eye bones),
   "camera_label": "..."                    (SIM_READ still, optional),
   "back_pin_figures": [...]                (v2+: override the measured leaning set),
   "accept_editor_pose": [...]              (v2+: figures whose atypical editor pose is accepted for the back pin),
   "mi_look": {"scalars": {..}, "vectors": {..}}   (v2+: override MI_LOOK[2] values, keys limited to MI_LOOK_KEYS)}

VERSION 2 (written 6 Oct OFFLINE after Gary's PIE note ~17:50: "the guy on the left is always losing his piece because
it's not pinned to his back. And the material reads much too dark"):
  - Pins. v2 builds ALL six figures (same names, _v2) so APPLY/REVERT stay per version. Figures in BACK_PIN_FIGURES
    (default leaning_figures(LEAN_SCAN) = Shore03_M59, Shore05_M53; measured from the exported anims, see LEAN_SCAN)
    get layout "crown+back": the crown disc is KEPT and a second MaxDistance-0 disc sits on the upper back
    (spine_05 + back normal x (back_pin_depth_cm + back_lift_cm)); the two distances are joined by a Min sampler
    (FDataflowMinSamplerNode, DataflowMinSamplerNode.h) before the one smoothstep -> one weight map. The rear of the
    sheet starts on a smooth arc-length (isometric) curve from the crown over the back of the head to that point, so
    both discs lie ON the sheet. Gate pin_coverage(): kinematic particles at the crown AND at the back point, spanning
    the crown->back arc. Shore02 keeps her v1 back pin; the other upright figures keep the v1 crown pin.
    Rear path (6 Oct evening, after the live DRY failed both back-pin figures with the cubic Bezier): params
    back_path "arc" (default; back_geometry_arc: arc R1 down from the crown, tangent segment to the back point,
    arc R2 onto the spine, straight; heading "behind" or "hook" when the head is thrown back and the back point
    lies AHEAD of the crown) or "bezier" (the original back_geometry_bezier). Gates for "arc": BACK_TOO_CLOSE,
    BACK_PIN_NOT_BELOW (replaces BACK_PIN_NOT_BEHIND), BEND_TIGHT, BACK_FACING; isometry unchanged.
  - Material. v2 makes MI_Sackcloth_OldGrey_Cloth_v2 (create-only; v1 MI untouched, so REVERT v1 / APPLY v1 still
    work). MI_LOOK[2]: HemGrimeAmount 0 (the hem grime is referenced to ObjectPositionWS = the cloth's BOUNDS centre,
    PrimitiveUniformShaderParametersBuilder.h:194, which for a head-attached cloth sits above most of the sack: the
    v1 sack rendered as GrimeColor 0.10/0.09/0.08 [inferred, see report]), Tint x2.0 (0.62,0.60,0.56 ->
    1.24,1.20,1.12), Desaturate 0.75 -> 0.60, InnerDarken 1.0 explicitly (v1 already 1.0 by default: the master has
    NO back-face term, InnerDarken multiplies both faces). UV/tiling, NormalStrength, roughness unchanged (Gary:
    "weave actually looks quite ok"). UV0 is METRES (build_sheet: uv0 = x + s/2), TileM 0.269 m: real scale.
  - APPLY now also sets the INSTANCE asset on each placed figure (fresh lookup after the BP compile; the placed
    figures carry their own asset value, S3LSFIX-20261006-172813) and saves BPs + the level in ONE save scope (the
    level is REQUIRED dirty). The instance before-values are in the record (before.<fig>.instance and
    instance_asset_override) for REVERT, which restores templates + instance assets and saves once.

LIVE ORDER for v2 (each step: args file, run, read the marker; stop on any _FAILED):
  1. REVERT  {"mode":"REVERT","confirm":"REVERT S3LIVESACK"}  -> restores v1's six templates AND the six instance
     assets (record instance_asset_override), one save (6 BPs + level). Record -> .reverted-<run>.
  2. DRY     {"mode":"DRY","version":2}                       -> geometry + coverage + editor-pose gates, no writes.
  3. BUILD   {"mode":"BUILD","confirm":"BUILD S3LIVESACK","version":2,"figures":["Shore05_M53"]}  (pilot: the Min
     sampler pin names are the one unproven link; a DF_LINK failure leaves only new unsaved assets: Don't-Save
     restart), then the remaining five with the same args minus "figures".
  4. APPLY   {"mode":"APPLY","confirm":"APPLY S3LIVESACK","version":2}  -> templates + instance assets, one save.
  5. VERIFY  {"mode":"VERIFY"} ; Gary's PIE ; PIE_PROBE while it runs (reports back_pin_track_cm per leaning figure).

Markers: S3LIVESACK_START / S3LIVESACK_<MODE>_OK|run=.. / S3LIVESACK_FAILED|run=..|reason
Crash rules: no UE object at module level; editor work only inside functions; no node deletion; no level reload;
never end PIE. Offline: importing without `unreal` defines only the pure helpers (harness
test_s3_sack_livecloth_offline.py).
"""
import datetime
import hashlib
import json
import math
import os
import random
import shutil

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None

PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/"
ARGS = HERE + "s3_sack_livecloth_args.json"
RECORDS = {"BUILD": HERE + "s3_sack_livecloth_build_record.json",
           "APPLY": HERE + "s3_sack_livecloth_apply_record.json"}
OUT = {"DRY": HERE + "s3_sack_livecloth_dry.json", "VERIFY": HERE + "s3_sack_livecloth_verify.json",
       "SIM": HERE + "s3_sack_livecloth_sim_probe.json", "PIE_PROBE": HERE + "s3_sack_livecloth_pie_probe.json"}
BACKUP_ROOT = PROJECT + "Backups/PreS3LiveSack-"
CONTENT = PROJECT + "Content/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = CONTENT + "InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
ROOT = "/Game/Metahuman/ShoreCast_20260910"
LIVE_DIR = ROOT + "/Cloth/LiveSack"
MAT_DIR = ROOT + "/Sack/Materials"
SRC_MASTER = {"masked": MAT_DIR + "/M_Sackcloth_Masked", "opaque": MAT_DIR + "/M_Sackcloth"}
SRC_MI = MAT_DIR + "/MI_Sackcloth_OldGrey"
FINALS = PROJECT + "DerivedAssets/S3Sackcloth/final_20261006/"
CONFIRM_WORD = "S3LIVESACK"
WRITE_MODES = ("BUILD", "APPLY", "REVERT")
SIM_MODES = ("SIM_START", "SIM_READ", "SIM_STOP")
MODES = ("DRY", "VERIFY", "PIE_PROBE") + SIM_MODES + WRITE_MODES
CLOTH, BODY, FACE = "ShoreHeadCloth", "Body", "Face"
CLOTH_CLASS = "ChaosClothComponent"
FIGURES = ("Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore05_M53", "Shore06_F25")
OLD_SCALE = 1.641315                      # create_shore_drape_pilot.py:35, all six (shore_draped_cast_components.json)
OLD_ASSET = {f: ROOT + "/Cloth/CA_ShoreHeadDrape" for f in FIGURES}
OLD_ASSET["Shore02_F52"] = ROOT + "/Cloth/CA_ShoreHeadDrape_Bowed"   # fix_bowed_shore_drape.py:8
OLD_MATERIAL = ROOT + "/Cloth/M_ShoreLinen"                          # create_pinned_shore_drape.py:37,62
# Gary 6 Oct (plan 10.1 + conductor): 2.0 m all six; upright pinned at the crown with the sheet 20 cm FORWARD
# (build_sackcloth.py:117-118,981: the pin point sits pin_forward BEHIND the sheet centre); Shore02 pinned on the
# mid-back ("crown back", the alt2p0 final).
DECISION = {f: {"size_m": 2.0, "pin": "crown", "pin_forward_m": 0.20} for f in FIGURES}
DECISION["Shore02_F52"] = {"size_m": 2.0, "pin": "back", "pin_forward_m": 0.0}
SHORE02_RECORD = FINALS + "Shore02_F52_Sack_alt2p0.json"
TOL = 1e-3

# v2 back pin. MEASURED 6 Oct offline: Tools/S3Sackcloth/lean_scan.py (Blender 4.4 -b) over each figure's exported
# anim FBX (export_manifest.json), every 6th frame; head-z at the pose frame matched the record to <=1.1 mm for all six.
# "window" = the manifest's section [section_start_s, +section_source_duration_s] (what the scene plays [inferred from
# the manifest field names]); lean = |head - pelvis| horizontal (m); tilt = pelvis->neck_01 from vertical (deg).
# Summary: DerivedAssets/S3Sackcloth/bodies/lean_scan_summary.json.
LEAN_SCAN = {
    "Shore01_M56": {"lean_p50_m": 0.101, "lean_p90_m": 0.168, "tilt_p50_deg": 8.8, "tilt_p90_deg": 16.7, "tilt_max_deg": 20.1, "lean_max_m": 0.202},
    "Shore02_F52": {"lean_p50_m": 0.493, "lean_p90_m": 0.500, "tilt_p50_deg": 70.7, "tilt_p90_deg": 74.1, "tilt_max_deg": 75.8, "lean_max_m": 0.504},
    "Shore03_M59": {"lean_p50_m": 0.121, "lean_p90_m": 0.236, "tilt_p50_deg": 11.1, "tilt_p90_deg": 20.0, "tilt_max_deg": 24.9, "lean_max_m": 0.286},
    "Shore04_F55": {"lean_p50_m": 0.048, "lean_p90_m": 0.110, "tilt_p50_deg": 4.1, "tilt_p90_deg": 9.6, "tilt_max_deg": 13.5, "lean_max_m": 0.136},
    "Shore05_M53": {"lean_p50_m": 0.305, "lean_p90_m": 0.378, "tilt_p50_deg": 23.8, "tilt_p90_deg": 31.7, "tilt_max_deg": 38.0, "lean_max_m": 0.436},
    "Shore06_F25": {"lean_p50_m": 0.055, "lean_p90_m": 0.090, "tilt_p50_deg": 6.8, "tilt_p90_deg": 11.0, "tilt_max_deg": 14.8, "lean_max_m": 0.119},
}
LEAN_P90_M, TILT_P90_DEG = 0.20, 19.0      # a crown disc alone lets the sheet slide off a back beyond these [inferred]
MI_LOOK_KEYS = {"scalars": ("HemGrimeAmount", "Desaturate", "InnerDarken", "MottleAmount", "NormalStrength",
                            "RoughnessScale", "RimAmount", "EdgeGrimeAmount"), "vectors": ("Tint", "GrimeColor")}
# v1 = the source MI's values (MI_Sackcloth_OldGrey). v2: Gary 6 Oct "still a bit dark" (weave and tiling OK).
MI_LOOK = {1: {"scalars": {}, "vectors": {}},
           2: {"scalars": {"HemGrimeAmount": 0.0, "Desaturate": 0.60, "InnerDarken": 1.0},
               "vectors": {"Tint": [1.24, 1.20, 1.12, 1.0]}}}
# MEASURED 6 Oct from DerivedAssets/S3Sackcloth/textures/hessian_230/hessian_230_diff_2k.png (sRGB -> linear mean)
HESSIAN_DIFF_LINEAR = {"mean_rgb": [0.2824, 0.1991, 0.1070], "lum_mean": 0.2102, "lum_p10": 0.0874, "lum_p90": 0.3263}
SRC_MI_LOOK = {"Desaturate": 0.75, "Tint": [0.62, 0.60, 0.56], "GrimeColor": [0.10, 0.09, 0.08], "InnerDarken": 1.0,
               "HemGrimeAmount": 1.0}   # build record v1 material_readback + master defaults (s3_sack_install.py:142,145)

# Starting point, not a tune (judge from Gary's PIE stills). Chaos PBD units; relationships carried from the
# approved curtain (ChaosClothCurtain.md "Physics" + build_curtain_chaos_asset.py:52-71), made heavier and stiffer.
PARAMS = {
    "quad_cm": 5.0,             # sim edge. 2.0 m -> 41 x 41 = 1681 particles (the old drape: 441)
    "fray_depth_cm": 3.5,       # torn outline inset (build_sackcloth.py --fray-depth 0.035)
    "seed": 20261006,
    "lift_cm": 2.0,             # pin point above the component origin (upright) / above the back point (Shore02)
    "back_lift_cm": 2.0,        # Shore02: above the recorded mid-back crown (Blender --lift 0.02)
    "pin_inner_cm": 7.0,        # MaxDistance 0 inside (kinematic disc); old: 3 cm x 1.64 = 4.9 cm
    "pin_outer_cm": 20.0,       # smooth falloff to free;               old: 14 cm x 1.64 = 23 cm
    "max_distance_cm": 250.0,   # free particles' allowance (gate: >= sqrt(2) x farthest geodesic reach)
    "density_kg_m2": 0.50,      # heavy jute sacking ~0.4-0.5 kg/m2 [inferred]; old drape 0.08-0.28, curtain 0.8
    "stretch_stiffness": 1.0,   # PBD max: hessian does not stretch; no area constraint (curtain: area -> plate)
    "bending_stiffness": 0.90,  # stiffer than the velvet's 0.8: broad, angular sacking folds
    "buckling_ratio": 0.0,      # no buckle-softening (folds keep their body)
    "buckling_stiffness": 0.05, # an order below bending, so it still folds rather than tenting
    "damping": 0.12,            # heavy: kills flutter as the bodies sway (curtain 0.05, old drape 0.01)
    "drag": 0.02, "lift": 0.02, # heavy cloth barely feels air
    "collision_thickness_cm": 2.0,   # old 1.0: keeps the hessian off the capsules' facets
    "friction": 0.8,            # hessian grips the shoulders
    "self_collision": False,    # single sheet; enable only if PIE shows the hem passing through itself (costly)
    "self_thickness_cm": 0.5,
    "iterations": 2, "max_iterations": 6, "substeps": 4,   # old runtime: 2/4 iterations, 6 substeps
    "tether_stiffness": 1.0, "tether_scale": 1.0,
    "skinned_triangle_mesh_collisions": True,   # unchanged from today's measured asset; a perf lever to bench
    "material_variant": "masked",              # "masked" (fray fringe from UV1.x) or "opaque"
    # v2 back pin (crown+back layout only)
    "back_pin_depth_cm": 12.0,  # spine_05 joint -> back skin: the finals' torso proxy half-depth 0.115 / 0.10 m
    "back_handle": 0.40,        # Bezier handles crown->back, x |crown - back| (back_path "bezier" only)
    # v2 rear path (6 Oct, after the DRY failed both back-pin figures with the Bezier: Shore05 min radius 8.4 cm,
    # Shore03 head thrown back -> back point AHEAD of the crown): "arc" = arc R1 down from the crown, tangent line to
    # the back point B, arc R2 onto the spine, straight. "bezier" = the original cubic (kept selectable).
    "back_path": "arc",
    "back_arc_radius_cm": 15.0,     # R1: chord ratio at quad 5 cm = 2R sin(q/2R)/q = 0.9954 (>= 0.99)
    "back_arc2_radius_cm": 15.0,    # R2: segment -> spine direction at B
}
PARAM_RANGES = {"quad_cm": (2.0, 10.0), "fray_depth_cm": (0.0, 8.0), "lift_cm": (0.0, 10.0),
                "back_lift_cm": (0.0, 10.0), "pin_inner_cm": (2.0, 20.0), "pin_outer_cm": (5.0, 60.0),
                "max_distance_cm": (50.0, 1000.0), "density_kg_m2": (0.05, 3.0), "stretch_stiffness": (0.1, 1.0),
                "bending_stiffness": (0.0, 1.0), "buckling_ratio": (0.0, 1.0), "buckling_stiffness": (0.0, 1.0),
                "damping": (0.0, 1.0), "drag": (0.0, 1.0), "lift": (0.0, 1.0),
                "collision_thickness_cm": (0.1, 10.0), "friction": (0.0, 2.0), "self_thickness_cm": (0.05, 5.0),
                "iterations": (1, 20), "max_iterations": (1, 40), "substeps": (1, 12),
                "tether_stiffness": (0.0, 1.0), "tether_scale": (0.9, 1.2),
                "back_pin_depth_cm": (0.0, 25.0), "back_handle": (0.1, 0.7),
                "back_arc_radius_cm": (4.0, 60.0), "back_arc2_radius_cm": (4.0, 60.0)}
BACK_PATHS = ("arc", "bezier")
BEND_MIN_RADIUS_CM = 12.0     # a sanity floor; the binding gate is PATTERN_NOT_ISOMETRIC on EVERY triangle (0.99-1.01)
BACK_TARGET_TOL_CM = 6.0      # the back disc centre (on the sheet) vs the measured back point
BACK_MIN_SPAN_CM = 20.0       # crown -> back disc distance: below this it is one disc, not a back pin
BACK_FACING_MAX_DEG = 60.0    # sheet "forward" (away from the back) vs the eyes
BACK_BELOW_MIN_CM = 20.0      # arc path: the back point must sit at least this far below the crown
BACK_HEADING_MIN_CM = 3.0     # arc path: below this horizontal crown->back distance the heading is the eyes'
ARC2_MIN_TURN_DEG = 2.0       # arc path: a smaller turn onto the spine is skipped


class LiveSackError(RuntimeError):
    pass


def _require(cond, msg):
    if not cond:
        raise LiveSackError(msg)


# ============================================================================================== pure: names / args
def names(fig, version, variant="masked"):
    v = "_v%d" % int(version)
    mi_v = "" if int(version) == 1 else v          # v1 MI kept its unversioned name (built 6 Oct, S3LIVESACK-20261006-172635)
    return {"mesh": "%s/SM_ShoreSack_%s%s" % (LIVE_DIR, fig, v), "dataflow": "%s/DF_ShoreSack_%s%s" % (LIVE_DIR, fig, v),
            "cloth": "%s/CA_ShoreSack_%s%s" % (LIVE_DIR, fig, v),
            "master": MAT_DIR + ("/M_Sackcloth_Masked_Cloth" if variant == "masked" else "/M_Sackcloth_Cloth"),
            "mi": MAT_DIR + ("/MI_Sackcloth_OldGrey_Cloth" if variant == "masked" else "/MI_Sackcloth_OldGrey_ClothOpaque") + mi_v,
            "bp": "%s/SceneCharacters/BP_%s_Draped" % (ROOT, fig)}


def leaning_figures(scan=None, lean_p90_m=LEAN_P90_M, tilt_p90_deg=TILT_P90_DEG):
    """Figures whose measured lean needs a back pin. Shore02 is excluded: her v1 layout already pins the back."""
    scan = LEAN_SCAN if scan is None else scan
    return sorted(f for f, r in scan.items() if DECISION[f]["pin"] != "back" and
                  (r["lean_p90_m"] >= lean_p90_m or r["tilt_p90_deg"] >= tilt_p90_deg))


BACK_PIN_FIGURES = tuple(leaning_figures())


def pin_layout(fig, version, back_figs=BACK_PIN_FIGURES):
    """v1: DECISION ("crown" / "back"). v2+: "crown+back" for the leaning figures, else the v1 layout."""
    if int(version) >= 2 and fig in back_figs:
        _require(DECISION[fig]["pin"] == "crown", "LAYOUT|%s: crown+back needs a crown-pinned figure" % fig)
        return "crown+back"
    return DECISION[fig]["pin"]


def mi_look(version, override=None):
    """The MI values this version writes over the source MI's (v1: none). override = args "mi_look" (v2+)."""
    base = MI_LOOK.get(int(version), MI_LOOK[max(MI_LOOK)]) if int(version) > 1 else MI_LOOK[1]
    look = {"scalars": dict(base["scalars"]), "vectors": {k: list(v) for k, v in base["vectors"].items()}}
    for kind in ("scalars", "vectors"):
        for k, v in ((override or {}).get(kind) or {}).items():
            look[kind][k] = list(v) if kind == "vectors" else v
    return look


def look_problems(look):
    probs = []
    for kind in ("scalars", "vectors"):
        for k, v in look.get(kind, {}).items():
            if k not in MI_LOOK_KEYS[kind]:
                probs.append("LOOK_KEY|%s.%s" % (kind, k))
            elif kind == "scalars" and (not isinstance(v, (int, float)) or isinstance(v, bool) or not 0.0 <= v <= 4.0):
                probs.append("LOOK_RANGE|%s=%r" % (k, v))
            elif kind == "vectors" and (not isinstance(v, list) or len(v) != 4 or
                                        not all(isinstance(x, (int, float)) and 0.0 <= x <= 4.0 for x in v)):
                probs.append("LOOK_VECTOR|%s=%r" % (k, v))
    return probs


def predicted_albedo(look, tex=HESSIAN_DIFF_LINEAR, src=SRC_MI_LOOK, hem=1.0):
    """Mean linear albedo of the master's SK_Base (s3_sack_install.py:202-215) with mottle at its mean (0) and no edge
    grime: desaturate -> tint -> hem-grime lerp (hem = the hem weight; 1.0 = fully inside the grime band) -> InnerDarken.
    Rim excluded (view-dependent)."""
    s = dict(src)
    s.update(look.get("scalars", {}))
    s.update({k: v[:3] for k, v in look.get("vectors", {}).items()})
    d = max(0.0, min(1.0, s["Desaturate"]))
    lum = tex["lum_mean"]
    col = [c * (1 - d) + lum * d for c in tex["mean_rgb"]]
    col = [c * t for c, t in zip(col, s["Tint"])]
    w = max(0.0, min(1.0, hem * s["HemGrimeAmount"]))
    col = [c * (1 - w) + g * w for c, g in zip(col, s["GrimeColor"])]
    col = [c * s["InnerDarken"] for c in col]
    return {"rgb": [round(c, 4) for c in col], "lum": round(0.2126 * col[0] + 0.7152 * col[1] + 0.0722 * col[2], 4)}


def hem_weight(z_above_bounds_centre_m, hem_h=0.35, hem_fall=0.25):
    """SK_Base's hem term (s3_sack_install.py:208-209) before HemGrimeAmount: saturate((HemH - zr) / HemFall)."""
    return max(0.0, min(1.0, (hem_h - z_above_bounds_centre_m) / hem_fall))


def material_problems(version, look):
    """v2+ gates: no hem grime on a head-attached cloth; brighter than v1 by 1.8-2.2x (Gary: moderate); not white."""
    probs = look_problems(look)
    if int(version) < 2:
        return probs
    v1 = predicted_albedo(MI_LOOK[1], hem=0.0)
    v2 = predicted_albedo(look, hem=1.0)          # worst case: every pixel inside the (broken) hem band
    if look.get("scalars", {}).get("HemGrimeAmount", SRC_MI_LOOK["HemGrimeAmount"]) != 0.0:
        probs.append("HEM_GRIME_ON|the hem band is referenced to the cloth's bounds centre (head-attached): it blackens the sack")
    ratio = v2["lum"] / max(v1["lum"], 1e-6)
    if not 1.8 <= ratio <= 2.2:
        probs.append("ALBEDO_STEP|v2/v1 textured albedo %.2fx (want 1.8-2.2x)" % ratio)
    if v2["lum"] > 0.5:
        probs.append("ALBEDO_HIGH|%.3f" % v2["lum"])
    return probs


def validate_params(p):
    probs = []
    unknown = sorted(set(p) - set(PARAMS))
    if unknown:
        probs.append("PARAM_UNKNOWN|%s" % unknown)
    for k, (lo, hi) in PARAM_RANGES.items():
        v = p.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not (lo <= v <= hi):
            probs.append("PARAM_RANGE|%s=%r not in [%s, %s]" % (k, v, lo, hi))
    if p.get("material_variant") not in ("masked", "opaque"):
        probs.append("PARAM_VARIANT|%r" % p.get("material_variant"))
    if p.get("back_path", "arc") not in BACK_PATHS:
        probs.append("PARAM_BACK_PATH|%r not in %s" % (p.get("back_path"), BACK_PATHS))
    if not probs:
        if p["pin_outer_cm"] <= p["pin_inner_cm"] + 2.0:
            probs.append("PIN_FALLOFF|outer must exceed inner by > 2 cm")
        if p["max_iterations"] < p["iterations"]:
            probs.append("ITERATIONS|max < iterations")
        if p["pin_inner_cm"] < 1.2 * p["quad_cm"]:
            probs.append("PIN_DISC|inner radius %.1f < 1.2 x quad %.1f: too few kinematic particles (hinge)"
                         % (p["pin_inner_cm"], p["quad_cm"]))
    return probs


def check_mode(args, records_exist):
    """records_exist: {"BUILD": bool, "APPLY": bool}. Returns (mode, figures, version, params, extra)."""
    mode = str(args.get("mode", "DRY")).upper()
    _require(mode in MODES, "MODE|" + mode)
    if mode in WRITE_MODES:
        _require(args.get("confirm") == "%s %s" % (mode, CONFIRM_WORD),
                 "CONFIRM_MISSING|want '%s %s'" % (mode, CONFIRM_WORD))
    figs = list(args.get("figures") or FIGURES)
    bad = [f for f in figs if f not in FIGURES]
    _require(figs and not bad and len(set(figs)) == len(figs), "FIGURES|%s" % figs)
    version = args.get("version", 1)
    _require(isinstance(version, int) and not isinstance(version, bool) and 1 <= version <= 99, "VERSION|%r" % version)
    params = dict(PARAMS)
    params.update(args.get("params") or {})
    probs = validate_params(params)
    _require(not probs, "PARAMS|%s" % probs)
    over = args.get("forward_local_override") or {}
    _require(isinstance(over, dict) and all(k in FIGURES and isinstance(v, list) and len(v) == 3
                                            for k, v in over.items()), "FORWARD_OVERRIDE|%r" % over)
    if mode == "APPLY":
        _require(records_exist["BUILD"], "PREREQ|BUILD record needed")
        _require(not records_exist["APPLY"], "ALREADY_APPLIED|apply record exists (REVERT first)")
    if mode in ("REVERT", "PIE_PROBE"):
        _require(records_exist["APPLY"], "NO_APPLY_RECORD")
    if mode == "VERIFY":
        _require(any(records_exist.values()), "NOTHING_TO_VERIFY")
    if mode in ("SIM_READ", "SIM_STOP"):
        _require(os.path.exists(OUT["SIM"]), "NO_SIM_START|run SIM_START first")
    back = args.get("back_pin_figures")
    back = list(BACK_PIN_FIGURES) if back is None else back
    _require(isinstance(back, list) and all(f in FIGURES and DECISION[f]["pin"] == "crown" for f in back),
             "BACK_PIN_FIGURES|%r (crown-pinned figure ids only)" % back)
    accept = args.get("accept_editor_pose") or []
    _require(isinstance(accept, list) and all(f in FIGURES for f in accept), "ACCEPT_EDITOR_POSE|%r" % accept)
    look = mi_look(version, args.get("mi_look"))
    _require(version >= 2 or not args.get("mi_look"), "MI_LOOK|v1 is the source look (bump version)")
    probs = material_problems(version, look)
    _require(not probs, "MATERIAL|%s" % probs)
    extra = {"forward_local_override": over, "camera_label": str(args.get("camera_label") or ""),
             "back_pin_figures": sorted(back), "accept_editor_pose": accept, "mi_look": look}
    return mode, figs, version, params, extra


def planned_packages(mode, figs, version, variant, existing=(), instances=True):
    """Content packages each write mode may dirty and save. Maps: APPLY/REVERT save WORLD; with instances=True (APPLY
    from v2's tool on; REVERT of a record with instance writes) the level is REQUIRED dirty (the instance asset
    writes), else only allowed (the BP compile re-instancing may dirty it)."""
    if mode == "BUILD":
        n0 = names(figs[0], version, variant)
        shared = [p for p in (n0["master"], n0["mi"]) if p not in existing]
        per = [names(f, version, variant)[k] for f in figs for k in ("mesh", "dataflow", "cloth")]
        # exact=False: a factory may save its own new package (GeometryScript's CreateNew... is UNVERIFIED on this);
        # BUILD then proves existence of every planned asset after the save instead.
        return {"content": sorted(shared + per), "maps_allowed": [], "exact": False}
    if mode in ("APPLY", "REVERT"):
        return {"content": sorted(names(f, version, variant)["bp"] for f in figs), "maps_allowed": [WORLD],
                "maps_required": [WORLD] if instances else [], "exact": True}
    return {"content": [], "maps_allowed": [], "exact": True}


def census_ok(dirty, planned):
    """exact: content dirty == planned (a missing one = a write that did not happen; an extra one = a side effect).
    Not exact (BUILD, create-only): dirty must be a SUBSET of planned. Maps dirty must be within maps_allowed and
    include maps_required (a required map that is clean = the instance writes did not happen)."""
    if planned.get("exact", True):
        content_ok = sorted(dirty["content"]) == sorted(planned["content"])
    else:
        content_ok = set(dirty["content"]) <= set(planned["content"])
    return (content_ok and set(dirty["maps"]) <= set(planned["maps_allowed"]) and
            set(planned.get("maps_required", [])) <= set(dirty["maps"]))


# ============================================================================================== pure: vectors
def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _mul(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a, what="vector"):
    n = _norm(a)
    _require(n > 1e-6, "ZERO_VECTOR|" + what)
    return _mul(a, 1.0 / n)


def to_local(p_world, origin, axes):
    """axes = (X, Y, Z) unit world vectors of a frame with no scale (SceneComponent Get{Forward,Right,Up}Vector)."""
    d = _sub(p_world, origin)
    return [_dot(d, axes[0]), _dot(d, axes[1]), _dot(d, axes[2])]


def dir_to_local(v_world, axes):
    return [_dot(v_world, axes[0]), _dot(v_world, axes[1]), _dot(v_world, axes[2])]


def dir_to_world(v_local, axes):
    return _add(_add(_mul(axes[0], v_local[0]), _mul(axes[1], v_local[1])), _mul(axes[2], v_local[2]))


def axes_problems(axes):
    probs = []
    for i, a in enumerate(axes):
        if abs(_norm(a) - 1.0) > 1e-3:
            probs.append("AXIS_NOT_UNIT|%d|%s" % (i, a))
    for i, j in ((0, 1), (0, 2), (1, 2)):
        if abs(_dot(axes[i], axes[j])) > 1e-3:
            probs.append("AXES_NOT_ORTHOGONAL|%d%d" % (i, j))
    return probs


def blender_to_ue(v):
    """Blender skin-mode frame -> UE Body component frame: Y flips. PROVEN by the record itself:
    Shore02_F52_Sack_alt2p0.json pose.head_bone_m [0.1118,-0.4534,0.9403] vs pose.record_head_m_ue_component
    [0.1118,+0.4534,0.9403] (same for every final; also memory tk-lateral-shift-frame-mirrored)."""
    return [v[0], -v[1], v[2]]


def facing_from_feet(thigh_l, thigh_r, ball_l, foot_l, ball_r, foot_r):
    """World facing (horizontal) as build_sackcloth.py:965-979: perpendicular to the hip line, signed by the toes."""
    lat = _sub(thigh_l, thigh_r)
    fwd = [-lat[1], lat[0], 0.0]
    toes = _add(_sub(ball_l, foot_l), _sub(ball_r, foot_r))
    toes[2] = 0.0
    fwd = _unit(fwd, "hip line")
    if _norm(toes) > 1.0 and _dot(fwd, toes) < 0:
        fwd = _mul(fwd, -1.0)
    return fwd, _norm(toes)


def upright_frame(comp_origin, comp_axes, eye_mid_world, world_up, feet_facing_world, params, fwd_override=None):
    """Pin geometry in the cloth COMPONENT frame for an upright figure (crown pin, sheet 20 cm forward).
    up_local  = world up seen from the component (editor pose) -> the sheet starts horizontal;
    fwd_local = component origin -> eye midpoint, projected off up_local (rigid on the head: pose-invariant);
    pin_local = component origin + lift along up (the old drape pinned at the origin, shore_spatial_crown_attachment.json)."""
    probs = axes_problems(comp_axes)
    up = _unit(dir_to_local(world_up, comp_axes), "up")
    if fwd_override is not None:
        f = list(fwd_override)
        src = "override"
    else:
        _require(eye_mid_world is not None, "NO_EYES|face eye bones not found; pass forward_local_override")
        f = to_local(eye_mid_world, comp_origin, comp_axes)
        src = "eyes"
    f = _sub(f, _mul(up, _dot(f, up)))
    fwd = _unit(f, "forward")
    out = {"up_local": up, "fwd_local": fwd, "pin_local_cm": _mul(up, params["lift_cm"]), "fwd_source": src,
           "comp_z_vs_up_deg": math.degrees(math.acos(max(-1.0, min(1.0, up[2]))))}
    if feet_facing_world is not None:
        fw = dir_to_world(fwd, comp_axes)
        fw = [fw[0], fw[1], 0.0]
        if _norm(fw) > 1e-3:
            ang = math.degrees(math.acos(max(-1.0, min(1.0, _dot(_unit(fw), _unit(feet_facing_world))))))
            out["face_vs_feet_deg"] = ang
            if ang > 75.0:
                probs.append("FACING_DISAGREES|face vs feet %.0f deg" % ang)
    return out, probs


def shore02_frame(record, body_to_world, comp_origin_editor, head_world_editor, comp_axes, world_up, params):
    """Shore02 back pin, from her RECORDED drape pose (alt2p0, pose 57.5 s), not the editor pose:
    crown_back and head bone are in Blender frame -> UE Body component (blender_to_ue) -> world (body_to_world, a
    function cm->cm incl. the actor placement). Her component is world-aligned (absolute rotation, fix_bowed_shore_
    drape.py:28-29), so only the component ORIGIN in that pose is estimated: recorded head + the editor's
    (component - head socket) offset (|offset| ~6.3 cm = the skull-centre anchor 6.18,0.95,0: error <= that)."""
    probs = axes_problems(comp_axes)
    _require(record["args"]["crown"] == "back" and abs(record["args"]["size_x"] - 2.0) < 1e-6,
             "SHORE02_RECORD|not the 2.0 m back-pin final")
    crown_cm = body_to_world(_mul(blender_to_ue(record["collider"]["crown"]), 100.0))
    head_cm = body_to_world(_mul(record["pose"]["record_head_m_ue_component"], 100.0))
    origin_est = _add(head_cm, _sub(comp_origin_editor, head_world_editor))
    pin_world = _add(crown_cm, _mul(world_up, params["back_lift_cm"]))
    up = _unit(dir_to_local(world_up, comp_axes), "up")
    fwd_b = record["facing"]["forward_xy"]
    fwd_world = _sub(body_to_world(_mul(blender_to_ue([fwd_b[0], fwd_b[1], 0.0]), 100.0)), body_to_world([0.0, 0.0, 0.0]))
    f = dir_to_local(fwd_world, comp_axes)
    f = _sub(f, _mul(up, _dot(f, up)))
    out = {"up_local": up, "fwd_local": _unit(f, "shore02 forward"), "pin_local_cm": to_local(pin_world, origin_est, comp_axes),
           "fwd_source": "record", "origin_offset_cm": _norm(_sub(comp_origin_editor, head_world_editor)),
           "back_from_head_cm": _norm(_sub(crown_cm, head_cm))}
    if out["origin_offset_cm"] > 12.0:
        probs.append("SHORE02_ORIGIN_OFFSET|%.1f cm (expected ~6.3)" % out["origin_offset_cm"])
    if not (15.0 <= out["back_from_head_cm"] <= 80.0):
        probs.append("SHORE02_BACK_DISTANCE|%.1f cm" % out["back_from_head_cm"])
    return out, probs


# ============================================================================================== pure: the sheet
def build_sheet(size_m, quad_cm, fray_depth_cm, seed):
    """Flat torn sheet as build_sackcloth.py make_piece (:766-809): the whole grid is WARPED so its boundary lies on a
    smooth aperiodic cut (4 random-frequency sines per side), no deleted quads (no sawtooth). Returns flat metres
    (x, y; y = forward), UV0 (metres from the corner), UV1 (edge distance m, per-sheet random), triangles."""
    rnd = random.Random(seed)
    piece_rand = rnd.random()
    q = quad_cm / 100.0
    depth = fray_depth_cm / 100.0
    n = max(2, int(round(size_m / q)))
    waves = [[(rnd.uniform(4.0, 40.0), rnd.uniform(0, 6.283), rnd.uniform(0.3, 1.0)) for _ in range(4)] for _ in range(4)]

    def inset(t, side):
        w = waves[side]
        val = sum(a * math.sin(f * t + ph) for f, ph, a in w) / sum(a for _, _, a in w)
        return depth * 0.5 * (1.0 + val)

    s = size_m
    xy, uv0, uv1 = [], [], []
    for j in range(n + 1):
        for i in range(n + 1):
            u, v = i / n, j / n
            y0 = -s / 2 + s * v
            left, right = -s / 2 + inset(y0, 0), s / 2 - inset(y0, 1)
            x = left + u * (right - left)
            bottom, top = -s / 2 + inset(x, 2), s / 2 - inset(x, 3)
            y = bottom + v * (top - bottom)
            d = max(0.0, min(x - left, right - x, y - bottom, top - y))
            xy.append((x, y))
            uv0.append((x + s / 2, y + s / 2))
            uv1.append((d, piece_rand))
    tris = []
    for j in range(n):
        for i in range(n):
            a, b = j * (n + 1) + i, j * (n + 1) + i + 1
            c, d = (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i
            tris += [(a, b, c), (a, c, d)]           # CCW seen from +n in the (x, y, n) right-handed sheet frame
    return {"n": n, "xy": xy, "uv0": uv0, "uv1": uv1, "tris": tris, "piece_rand": piece_rand, "size_m": size_m}


def place_sheet(sheet, frame, pin_forward_m):
    """Sheet -> component-frame cm. Sheet +y = fwd_local, +x = fwd x up (right), normal = up. The sheet point
    (0, -pin_forward) sits on pin_local, so the sheet centre is pin_forward AHEAD of the pin."""
    up, fwd = frame["up_local"], frame["fwd_local"]
    side = _unit(_cross(fwd, up), "side")
    pin = frame["pin_local_cm"]
    pos = []
    for x, y in sheet["xy"]:
        yy = y + pin_forward_m
        pos.append(_add(pin, _add(_mul(side, 100.0 * x), _mul(fwd, 100.0 * yy))))
    return {"positions_cm": pos, "normal": up, "side": side, "pin_local_cm": pin}


# ---------------------------------------------------------------------------------------------- v2: crown + back pin
def back_target_world(spine05, spine03, neck01, facing_world, params):
    """The upper-back pin point (world cm): spine_05 + the back normal x (depth + lift). Back normal = minus the feet
    facing, made perpendicular to the spine (spine_03 -> neck_01). down_back = along the back, away from the head."""
    up_sp = _unit(_sub(neck01, spine03), "spine")
    back = _mul(_unit([facing_world[0], facing_world[1], 0.0], "facing"), -1.0)
    nb = _unit(_sub(back, _mul(up_sp, _dot(back, up_sp))), "back normal")
    target = _add(spine05, _mul(nb, params["back_pin_depth_cm"] + params["back_lift_cm"]))
    return target, {"back_normal_world": nb, "down_back_world": _mul(up_sp, -1.0)}


def torso_pose(pelvis, neck01, head):
    """Frame-invariant pose numbers, comparable with LEAN_SCAN: torso tilt (deg) and head-pelvis horizontal lean (m)."""
    t = _unit(_sub(neck01, pelvis), "torso")
    return {"tilt_deg": math.degrees(math.acos(max(-1.0, min(1.0, t[2])))),
            "lean_m": math.hypot(head[0] - pelvis[0], head[1] - pelvis[1]) / 100.0}


def editor_pose_problems(fig, pose, accept=()):
    """The back disc rides the HEAD (BindToRootBone: the whole sheet follows the component), so it is placed from the
    editor pose: refuse an editor pose whose torso tilt is outside [0.5 x window p50, window max + 5 deg] of the
    measured scene motion (then the head->back relation would be atypical) unless the figure is in accept_editor_pose."""
    r = LEAN_SCAN[fig]
    lo, hi = 0.5 * r["tilt_p50_deg"], r["tilt_max_deg"] + 5.0
    if not lo <= pose["tilt_deg"] <= hi and fig not in accept:
        return ["EDITOR_POSE_ATYPICAL|%s|editor torso tilt %.1f deg not in [%.1f, %.1f] (scene motion); pass "
                "accept_editor_pose to override" % (fig, pose["tilt_deg"], lo, hi)]
    return []


def _bezier(p, t):
    m = 1.0 - t
    return [m * m * m * p[0][i] + 3 * m * m * t * p[1][i] + 3 * m * t * t * p[2][i] + t * t * t * p[3][i] for i in (0, 1)]


def _bezier_d(p, t):
    m = 1.0 - t
    d1 = [3 * m * m * (p[1][i] - p[0][i]) + 6 * m * t * (p[2][i] - p[1][i]) + 3 * t * t * (p[3][i] - p[2][i]) for i in (0, 1)]
    d2 = [6 * m * (p[2][i] - 2 * p[1][i] + p[0][i]) + 6 * t * (p[3][i] - 2 * p[2][i] + p[1][i]) for i in (0, 1)]
    return d1, d2


def back_geometry(frame, back_local_cm, down_back_local, params, samples=4000):
    """Dispatch on params["back_path"]: "arc" (default since 6 Oct) or the original "bezier"."""
    if params.get("back_path", "arc") == "bezier":
        return back_geometry_bezier(frame, back_local_cm, down_back_local, params, samples)
    return back_geometry_arc(frame, back_local_cm, down_back_local, params)


def back_geometry_bezier(frame, back_local_cm, down_back_local, params, samples=4000):
    """back_path "bezier" (the original v2 path). The rear profile of a crown+back sheet in the plane through the crown pin C spanned by world-up and the
    horizontal C->back direction (so the back point lies IN the plane: no lateral error). 2D coords (a, b) cm:
    a along fwd2 (= away from the back), b along up. Rear path: cubic Bezier C -> B leaving C horizontally backwards
    (continuous with the flat front panel: no fold at the crown) and arriving at B along the back (down_back); beyond
    B a straight run along that tangent. Arc-length table -> isometric placement."""
    up, C = frame["up_local"], frame["pin_local_cm"]
    d = _sub(back_local_cm, C)
    horiz = _sub(d, _mul(up, _dot(d, up)))
    fwd2 = _mul(_unit(horiz, "crown->back horizontal"), -1.0)
    side = _unit(_cross(fwd2, up), "side")
    aB, bB = _dot(d, fwd2), _dot(d, up)
    L = math.hypot(aB, bB)
    ta, tb = _dot(down_back_local, fwd2), _dot(down_back_local, up)
    tn = math.hypot(ta, tb)
    tangent_src = "spine"
    if tn < 1e-3 or (ta * aB + tb * bB) <= 0.0:       # degenerate, or pointing back toward the crown: use the chord
        ta, tb, tangent_src = aB, bB, "chord"
        tn = math.hypot(ta, tb)
    ta, tb = ta / tn, tb / tn
    h = params["back_handle"] * L
    P = [[0.0, 0.0], [-h, 0.0], [aB - ta * h, bB - tb * h], [aB, bB]]
    pts, arc, rmin = [], [0.0], float("inf")
    for i in range(samples + 1):
        t = i / samples
        pts.append(_bezier(P, t))
        d1, d2 = _bezier_d(P, t)
        sp = math.hypot(d1[0], d1[1])
        cr = abs(d1[0] * d2[1] - d1[1] * d2[0])
        if sp > 1e-9 and cr > 1e-12:
            rmin = min(rmin, sp ** 3 / cr)
        if i:
            arc.append(arc[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    eye = frame.get("fwd_local")
    eye_deg, along_eyes = None, aB
    if eye is not None:
        e = _sub(eye, _mul(up, _dot(eye, up)))
        if _norm(e) > 1e-6:
            eye_deg = math.degrees(math.acos(max(-1.0, min(1.0, _dot(_unit(e), fwd2)))))
            along_eyes = _dot(d, _unit(e))
    return {"path": "bezier", "fwd2_local": fwd2, "side_local": side, "up_local": up, "pin_local_cm": C,
            "back_local_cm": back_local_cm,
            "b2_cm": [aB, bB], "chord_cm": L, "tangent_b": [ta, tb], "tangent_source": tangent_src, "ctrl_cm": P,
            "pts": pts, "arc": arc, "rear_len_cm": arc[-1], "min_radius_cm": rmin, "fwd2_vs_eyes_deg": eye_deg,
            "back_along_eyes_cm": along_eyes}


def _arc_piece(pos0, psi0, sign, radius, length, step):
    """Points of a circular arc (2D) leaving pos0 at heading psi0, turning CCW (sign +1) or CW (-1), first point
    excluded. pos(s) = pos0 + sign R (sin psi(s) - sin psi0, cos psi0 - cos psi(s)), psi(s) = psi0 + sign s / R."""
    n = max(1, int(math.ceil(length / step)))
    out = []
    for i in range(1, n + 1):
        psi = psi0 + sign * (length * i / n) / radius
        out.append([pos0[0] + sign * radius * (math.sin(psi) - math.sin(psi0)),
                    pos0[1] + sign * radius * (math.cos(psi0) - math.cos(psi))])
    return out


def back_geometry_arc(frame, back_local_cm, down_back_local, params, step_cm=0.05):
    """back_path "arc". Heading h (sheet forward, the front panel's direction) from the horizontal crown->back vector
    Bh: h = -unit(Bh) if B is behind the crown w.r.t. the eyes ("behind"), +unit(Bh) if ahead (head thrown back:
    "hook"), the eyes' forward if |Bh| < BACK_HEADING_MIN_CM. B therefore lies in the plane (up, h): no lateral error.
    Rear path in 2D (A along -h = backwards, b up), from the crown C=(0,0) heading +A (continuous with the flat front
    panel): arc R1 turning DOWN (centre (0,-R1)) through theta1, until its tangent line passes through B; the straight
    tangent segment to B (s = s_B); at B an arc R2 turning onto the in-plane spine direction (theta2, skipped when the
    projection is degenerate or the turn < ARC2_MIN_TURN_DEG); then straight. Stored in the Bezier path's (a, b)
    convention (a along fwd2 = h, so a = -A) and arc-length table, so _rear_point / place_sheet_back are shared."""
    up, C = frame["up_local"], frame["pin_local_cm"]
    R1, R2 = float(params["back_arc_radius_cm"]), float(params["back_arc2_radius_cm"])
    d = _sub(back_local_cm, C)
    horiz = _sub(d, _mul(up, _dot(d, up)))
    eye = frame.get("fwd_local")
    e = None
    if eye is not None:
        e0 = _sub(eye, _mul(up, _dot(eye, up)))
        e = _unit(e0, "eyes horizontal") if _norm(e0) > 1e-6 else None
    along_eyes = _dot(d, e) if e is not None else None
    if _norm(horiz) < BACK_HEADING_MIN_CM:
        _require(e is not None, "BACK_HEADING|crown->back nearly vertical and no eyes' forward")
        h, heading_src = e, "eyes"
    else:
        hb = _unit(horiz, "crown->back horizontal")
        behind = along_eyes is None or along_eyes < 0.0
        h, heading_src = (_mul(hb, -1.0) if behind else hb), "back"
    mode = "behind" if (along_eyes is None or along_eyes < 0.0) else "hook"
    side = _unit(_cross(h, up), "side")
    lateral = _dot(d, side)
    BA, Bb = -_dot(d, h), _dot(d, up)                     # spec coords: A backwards, b up
    eye_deg = None if e is None else math.degrees(math.acos(max(-1.0, min(1.0, _dot(e, h)))))
    # arc 1 + tangent segment
    DA, Db = BA, Bb + R1                                   # B relative to the arc-1 centre (0, -R1)
    Dn = math.hypot(DA, Db)
    too_close = Dn <= R1 * (1.0 + 1e-9)
    pts = [[0.0, 0.0]]
    if too_close:                                          # reported (BACK_TOO_CLOSE); fallback = the chord (a fold)
        theta1, seg_len, rmin = 0.0, math.hypot(BA, Bb), 0.0
        psi_seg = math.atan2(Bb, BA)
        pts.append([BA, Bb])
    else:
        theta1 = (math.atan2(DA, Db) - math.acos(R1 / Dn)) % (2.0 * math.pi)
        if theta1 > 2.0 * math.pi - 1e-9:
            theta1 = 0.0
        if theta1 > 0.0:
            pts += _arc_piece([0.0, 0.0], 0.0, -1.0, R1, R1 * theta1, step_cm)
        psi_seg = -theta1
        seg_len = math.sqrt(max(0.0, Dn * Dn - R1 * R1))
        p1 = pts[-1]
        pts.append([p1[0] + seg_len * math.cos(psi_seg), p1[1] + seg_len * math.sin(psi_seg)])
        rmin = R1
    i_B = len(pts) - 1
    end_err = math.hypot(pts[i_B][0] - BA, pts[i_B][1] - Bb)
    # arc 2 onto the spine direction
    sA, sb = -_dot(down_back_local, h), _dot(down_back_local, up)
    sn = math.hypot(sA, sb)
    theta2, arc2 = 0.0, "skipped_degenerate"
    psi_end = psi_seg
    if sn >= 1e-3:
        turn = math.atan2(sb, sA) - psi_seg
        turn = (turn + math.pi) % (2.0 * math.pi) - math.pi
        theta2 = math.degrees(turn)
        if abs(theta2) < ARC2_MIN_TURN_DEG:
            arc2 = "skipped_small"
        else:
            sign = 1.0 if turn > 0 else -1.0
            pts += _arc_piece(pts[i_B], psi_seg, sign, R2, R2 * abs(turn), step_cm)
            psi_end = psi_seg + turn
            rmin = min(rmin, R2)
            arc2 = "used"
    tail = [pts[-1][0] + 5.0 * math.cos(psi_end), pts[-1][1] + 5.0 * math.sin(psi_end)]
    pts.append(tail)                                       # a short table tail; _rear_point extrapolates beyond
    pts = [[-p[0], p[1]] for p in pts]                     # -> (a along fwd2 = h, b up)
    arc = [0.0]
    for i in range(1, len(pts)):
        arc.append(arc[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    tb = [-math.cos(psi_end), math.sin(psi_end)]
    return {"path": "arc", "fwd2_local": h, "side_local": side, "up_local": up, "pin_local_cm": C,
            "back_local_cm": back_local_cm, "b2_cm": list(pts[i_B]), "chord_cm": math.hypot(BA, Bb),
            "tangent_b": tb, "tangent_source": "spine" if arc2 != "skipped_degenerate" else "segment",
            "pts": pts, "arc": arc, "rear_len_cm": arc[i_B], "s_B_cm": arc[i_B], "path_len_cm": arc[-1],
            "min_radius_cm": rmin, "fwd2_vs_eyes_deg": eye_deg, "back_along_eyes_cm": along_eyes,
            "heading_mode": mode, "heading_source": heading_src, "theta1_deg": math.degrees(theta1),
            "theta2_deg": theta2, "arc2": arc2, "segment_cm": seg_len, "lateral_error_cm": lateral,
            "back_end_error_cm": end_err, "back_below_crown_cm": -Bb, "too_close": too_close,
            "arc_radii_cm": [R1, R2]}


def _rear_point(bg, s):
    """(a, b) and the unit tangent d/ds at arc length s >= 0 along the rear path."""
    arc, pts = bg["arc"], bg["pts"]
    if s >= arc[-1]:
        ta, tb = bg["tangent_b"]
        e = s - arc[-1]
        return [pts[-1][0] + ta * e, pts[-1][1] + tb * e], [ta, tb]
    lo, hi = 0, len(arc) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if arc[mid] <= s:
            lo = mid
        else:
            hi = mid
    seg = arc[hi] - arc[lo]
    f = (s - arc[lo]) / seg if seg > 0 else 0.0
    p = [pts[lo][i] + f * (pts[hi][i] - pts[lo][i]) for i in (0, 1)]
    t = [(pts[hi][i] - pts[lo][i]) / seg if seg > 0 else 0.0 for i in (0, 1)]
    return p, t


def place_sheet_back(sheet, bg, pin_forward_m):
    """Crown+back placement. Sheet +y = fwd2 on the front panel (flat, as v1, sheet centre pin_forward AHEAD of the
    crown); behind the crown pin the sheet follows the rear path by arc length, so the 2D pattern is unchanged
    (isometric: a generalised cylinder with rulings along the side axis). Per-vertex normals = side x dP/du."""
    C, f2, up, side = bg["pin_local_cm"], bg["fwd2_local"], bg["up_local"], bg["side_local"]
    pos, nrm, us = [], [], []
    for x, y in sheet["xy"]:
        u = 100.0 * (y + pin_forward_m)                 # signed arc length from the crown pin, + = forward
        if u >= 0.0:
            a, b, T = u, 0.0, [1.0, 0.0]
        else:
            (a, b), t = _rear_point(bg, -u)
            T = [-t[0], -t[1]]
        pos.append(_add(C, _add(_mul(side, 100.0 * x), _add(_mul(f2, a), _mul(up, b)))))
        T3 = _add(_mul(f2, T[0]), _mul(up, T[1]))
        nrm.append(_unit(_cross(side, T3), "normal"))
        us.append(u)
    back_on_sheet = _add(C, _add(_mul(f2, bg["b2_cm"][0]), _mul(up, bg["b2_cm"][1])))
    return {"positions_cm": pos, "normals": nrm, "normal": up, "side": side, "pin_local_cm": C,
            "pins": [C, back_on_sheet], "u_cm": us, "rear_len_cm": bg["rear_len_cm"]}


def pin_coverage(sheet, placed, params, back_target_cm=None):
    """The MaxDistance-0 region (smoothstep(min distance to the pin centres) == 0) and whether it spans crown -> upper
    back. Returns (metrics, problems). For a single-pin layout it only reports."""
    pins = placed.get("pins") or [placed["pin_local_cm"]]
    pos = placed["positions_cm"]
    inner = params["pin_inner_cm"]
    dist = [min(_norm(_sub(p, c)) for c in pins) for p in pos]
    kin = [i for i, d in enumerate(dist) if smoothstep_weight(d, inner, params["pin_outer_cm"]) <= 0.0]
    near = [sum(1 for i in kin if _norm(_sub(pos[i], c)) <= inner + 1e-9) for c in pins]
    m = {"kinematic": len(kin), "per_pin": near, "pins_cm": pins}
    probs = []
    if len(pins) < 2:
        return m, probs
    us = placed["u_cm"]
    rear = [-us[i] for i in kin]
    m.update({"rear_arc_min_cm": min(rear) if rear else None, "rear_arc_max_cm": max(rear) if rear else None,
              "rear_len_cm": placed["rear_len_cm"], "span_cm": _norm(_sub(pins[1], pins[0]))})
    if min(near) < 3:
        probs.append("BACK_PIN_COVERAGE|kinematic particles per disc %s (< 3)" % near)
    if not rear or m["rear_arc_min_cm"] > inner or m["rear_arc_max_cm"] < placed["rear_len_cm"] - inner:
        probs.append("BACK_PIN_COVERAGE|kinematic rear arc %s..%s does not span 0..%.1f cm (crown -> back)"
                     % (m["rear_arc_min_cm"], m["rear_arc_max_cm"], placed["rear_len_cm"]))
    if m["span_cm"] < BACK_MIN_SPAN_CM:
        probs.append("BACK_PIN_SPAN|crown -> back disc %.1f cm (< %.0f)" % (m["span_cm"], BACK_MIN_SPAN_CM))
    if back_target_cm is not None:
        m["back_vs_target_cm"] = _norm(_sub(pins[1], back_target_cm))
        if m["back_vs_target_cm"] > BACK_TARGET_TOL_CM:
            probs.append("BACK_PIN_OFF_TARGET|%.1f cm" % m["back_vs_target_cm"])
    return m, probs


def back_geometry_problems(bg):
    probs = []
    if bg.get("path") == "arc":
        # BACK_PIN_NOT_BEHIND does not apply: the hook path reaches a back point AHEAD of the crown (head thrown back)
        if bg["too_close"]:
            probs.append("BACK_TOO_CLOSE|back point inside the R1 %.1f cm arc circle" % bg["arc_radii_cm"][0])
        if bg["back_below_crown_cm"] < BACK_BELOW_MIN_CM:
            probs.append("BACK_PIN_NOT_BELOW|back point %.1f cm below the crown (< %.0f)"
                         % (bg["back_below_crown_cm"], BACK_BELOW_MIN_CM))
        if bg["min_radius_cm"] < BEND_MIN_RADIUS_CM:
            probs.append("BEND_TIGHT|min radius %.1f cm < %.0f" % (bg["min_radius_cm"], BEND_MIN_RADIUS_CM))
        if bg["fwd2_vs_eyes_deg"] is not None and bg["fwd2_vs_eyes_deg"] > BACK_FACING_MAX_DEG:
            probs.append("BACK_FACING|sheet forward (heading %s) vs eyes %.0f deg"
                         % (bg["heading_mode"], bg["fwd2_vs_eyes_deg"]))
        return probs
    if bg["back_along_eyes_cm"] > -5.0:     # fwd2 is built FROM the back point: test against the eyes instead
        probs.append("BACK_PIN_NOT_BEHIND|back point %.1f cm along the eyes' forward (must be behind the crown)"
                     % bg["back_along_eyes_cm"])
    if bg["min_radius_cm"] < BEND_MIN_RADIUS_CM:
        probs.append("BEND_TIGHT|min radius %.1f cm < %.0f" % (bg["min_radius_cm"], BEND_MIN_RADIUS_CM))
    if bg["fwd2_vs_eyes_deg"] is not None and bg["fwd2_vs_eyes_deg"] > BACK_FACING_MAX_DEG:
        probs.append("BACK_FACING|sheet forward vs eyes %.0f deg" % bg["fwd2_vs_eyes_deg"])
    return probs


def plan_geometry(fig, frame, params, layout, seed_offset=None):
    """Pure: the sheet, its placement, metrics and every geometry problem for one figure (DRY and BUILD share it)."""
    seed = params["seed"] + (FIGURES.index(fig) if seed_offset is None else seed_offset)
    sheet = build_sheet(DECISION[fig]["size_m"], params["quad_cm"], params["fray_depth_cm"], seed)
    probs = []
    if layout == "crown+back":
        b = frame["back"]
        bg = back_geometry(frame, b["back_local_cm"], b["down_back_local"], params)
        placed = place_sheet_back(sheet, bg, DECISION[fig]["pin_forward_m"])
        probs += back_geometry_problems(bg)
        frame["back"]["geometry"] = {k: v for k, v in bg.items() if k not in ("pts", "arc")}
    else:
        placed = place_sheet(sheet, frame, DECISION[fig]["pin_forward_m"])
    m = sheet_metrics(sheet, placed, params)
    cov, cprobs = pin_coverage(sheet, placed, params,
                               frame["back"]["back_local_cm"] if layout == "crown+back" else None)
    m["coverage"] = cov
    probs += sheet_problems(m, params) + cprobs
    return sheet, placed, m, probs


def smoothstep_weight(dist_cm, inner, outer):
    """FDataflowSmoothStepFloatSampler (MinValue=inner, MaxValue=outer, ValueA 0 -> ValueB 1) [inferred: Hermite]."""
    t = max(0.0, min(1.0, (dist_cm - inner) / (outer - inner)))
    return t * t * (3.0 - 2.0 * t)


def sheet_metrics(sheet, placed, params):
    """Offline gates on what BUILD will author (the same buffers go to GeometryScript)."""
    pos, uv0, tris = placed["positions_cm"], sheet["uv0"], sheet["tris"]
    pin = placed["pin_local_cm"]
    pins = placed.get("pins") or [pin]
    vn = placed.get("normals")                       # crown+back: per-vertex normals (curved rear)
    curved = vn is not None
    # curved sheets: EVERY triangle (the bends are local); flat: a 400-triangle stride as v1
    ratios, wind = [], 0
    for a, b, c in (tris if curved else tris[:: max(1, len(tris) // 400)]):
        for i, j in ((a, b), (b, c), (c, a)):
            l3 = _norm(_sub(pos[i], pos[j]))
            l2 = 100.0 * math.hypot(uv0[i][0] - uv0[j][0], uv0[i][1] - uv0[j][1])
            ratios.append(l3 / l2 if l2 > 1e-9 else float("inf"))
        nrm = _cross(_sub(pos[b], pos[a]), _sub(pos[c], pos[a]))
        wind += 1 if _dot(nrm, vn[a] if curved else placed["normal"]) > 0 else -1
    dist = [min(_norm(_sub(p, c)) for c in pins) for p in pos]
    w = [smoothstep_weight(d, params["pin_inner_cm"], params["pin_outer_cm"]) for d in dist]
    kin = sum(1 for x in w if x <= 0.0)
    if curved:   # flatness of the FRONT panel only (the rear is curved by design; isometry is the gate there)
        plane = max(abs(_dot(_sub(p, pin), placed["normal"])) for p, u in zip(pos, placed["u_cm"]) if u >= 0.0)
    else:
        plane = max(abs(_dot(_sub(p, pin), placed["normal"])) for p in pos)
    dist = [_norm(_sub(p, pin)) for p in pos]       # farthest reach is measured from the crown pin (conservative)
    edge_d = [u[0] for u in sheet["uv1"]]
    return {"vertices": len(pos), "triangles": len(tris), "edge_ratio_min": min(ratios), "edge_ratio_max": max(ratios),
            "winding_sign": wind, "kinematic": kin, "partially_pinned": sum(1 for x in w if 0.0 < x < 1.0),
            "farthest_from_pin_cm": max(dist), "plane_dev_cm": plane, "edge_dist_max_m": max(edge_d),
            "edge_dist_min_m": min(edge_d), "boundary_on_edge": _boundary_on_edge(sheet)}


def _boundary_on_edge(sheet):
    n = sheet["n"]
    idx = [i for i in range((n + 1) ** 2) if i % (n + 1) in (0, n) or i // (n + 1) in (0, n)]
    return max(sheet["uv1"][i][0] for i in idx)


def sheet_problems(m, params):
    probs = []
    if not (0.99 <= m["edge_ratio_min"] and m["edge_ratio_max"] <= 1.01):
        probs.append("PATTERN_NOT_ISOMETRIC|%s..%s (2D pattern = UV0 x 100 must equal 3D)" %
                     (m["edge_ratio_min"], m["edge_ratio_max"]))
    if m["winding_sign"] <= 0:
        probs.append("WINDING|normal not along up")
    if m["kinematic"] < 5:
        probs.append("PIN_TOO_FEW|%d kinematic particles" % m["kinematic"])
    if m["kinematic"] > 0.05 * m["vertices"]:
        probs.append("PIN_TOO_MANY|%d" % m["kinematic"])
    if params["max_distance_cm"] < math.sqrt(2.0) * m["farthest_from_pin_cm"]:
        probs.append("MAX_DISTANCE_LOW|%.0f < sqrt2 x %.0f" % (params["max_distance_cm"], m["farthest_from_pin_cm"]))
    if m["plane_dev_cm"] > 0.01:
        probs.append("NOT_FLAT|%.3f cm" % m["plane_dev_cm"])
    if m["boundary_on_edge"] > 1e-9:
        probs.append("BOUNDARY_UV1|%s" % m["boundary_on_edge"])
    return probs


def buffers_sha(sheet, placed):
    h = hashlib.sha256()
    for p in placed["positions_cm"]:
        h.update(("%.4f,%.4f,%.4f;" % tuple(p)).encode())
    for a, b in zip(sheet["uv0"], sheet["uv1"]):
        h.update(("%.6f,%.6f,%.6f,%.6f;" % (a[0], a[1], b[0], b[1])).encode())
    for t in sheet["tris"]:
        h.update(("%d,%d,%d;" % t).encode())
    return h.hexdigest()


# ============================================================================================== pure: Dataflow spec
def weighted(value, animatable=True, weight_map=None):
    s = "(%sLow=%s,High=%s%s)" % ("bIsAnimatable=True," if animatable else "", _num(value), _num(value),
                                  (',WeightMap="%s"' % weight_map) if weight_map else "")
    return s


def _num(v):
    return ("%.6f" % float(v)).rstrip("0").rstrip(".") if float(v) != int(float(v)) else str(int(float(v)))


def _b(v):
    return "True" if v else "False"


WEIGHT_ATTR = "ShoreSackMaxDistance"


SAMPLER_KEYS = ("CrownDistance", "BackDistance", "PinUnion", "CrownFalloff")
MIN_SAMPLER_INPUTS = ("InputSamplers[%d]", "InputSamplers_%d")   # array pin naming: "CollectionLods[0]" ran in v1 BUILD


def _sphere(c):
    return "(Sphere=(Center=(X=%s,Y=%s,Z=%s),W=0))" % (_num(c[0]), _num(c[1]), _num(c[2]))


def dataflow_spec(mesh_path, pin_local_cm, p, back_local_cm=None):
    """[(key, type, {prop: ImportText})], [(from, out, to, in)], terminal key. Property names: the 5.8 headers
    (ChaosClothAssetDataflowNodes/Public/ChaosClothAsset/*.h) and the curtain build that ran
    (build_curtain_chaos_asset.py:413-483); sampler nodes as fix_spatial_crown_attachment.py:20-33.
    back_local_cm (v2 crown+back): a second sphere distance and FDataflowMinSamplerNode (DataflowMinSamplerNode.h,
    multi-input InputSamplers) -> min distance -> the same smoothstep -> one weight map = union of the two discs."""
    nodes = [
        ("Import", "FChaosClothAssetStaticMeshImportNode_v2", {
            "StaticMesh": mesh_path, "bImportSimMesh": "True", "bImportRenderMesh": "True",
            "UVChannel": "0", "UVScale": "(X=100,Y=100)"}),                 # UV0 metres -> pattern cm
        ("BindToRoot", "FChaosClothAssetBindToRootBoneNode", {"bBindSimMesh": "True", "bBindRenderMesh": "True"}),
        ("CrownDistance", "FDataflowDistanceFromSphereFloatSamplerNode", {"DistanceFromSphereSampler": _sphere(pin_local_cm)}),
    ]
    if back_local_cm is not None:
        nodes += [("BackDistance", "FDataflowDistanceFromSphereFloatSamplerNode", {"DistanceFromSphereSampler": _sphere(back_local_cm)}),
                  ("PinUnion", "FDataflowMinSamplerNode", {})]
    nodes += [
        ("CrownFalloff", "FDataflowSmoothStepFloatSamplerNode", {
            "SmoothStepSampler": "(MinValue=%s,MaxValue=%s,ValueA=0,ValueB=1)" % (_num(p["pin_inner_cm"]), _num(p["pin_outer_cm"]))}),
        ("CrownWeights", "FDataflowSamplerToAttributeNode", {
            "AttributeName": WEIGHT_ATTR, "VertexGroup": '(Name="SimVertices3D")'}),
        ("Mass", "FChaosClothAssetSimulationMassConfigNode", {
            "MassMode": "Density", "DensityWeighted": weighted(p["density_kg_m2"], animatable=False)}),
        ("Stretch", "FChaosClothAssetSimulationStretchConfigNode", {
            "bStretchUse3dRestLengths": "False", "SolverType": "PBD", "DistributionType": "Isotropic",
            "bAddAreaConstraint": "False", "StretchStiffness": weighted(p["stretch_stiffness"])}),
        ("Bending", "FChaosClothAssetSimulationBendingConfigNode", {
            "RestAngleType": "FlatnessRatio", "FlatnessRatio": weighted(1.0, animatable=False), "SolverType": "PBD",
            "DistributionType": "Isotropic", "BendingStiffness": weighted(p["bending_stiffness"]),
            "BucklingRatioWeighted": weighted(p["buckling_ratio"]), "BucklingStiffness": weighted(p["buckling_stiffness"])}),
        ("Damping", "FChaosClothAssetSimulationDampingConfigNode", {"DampingCoefficientWeighted": weighted(p["damping"])}),
        ("Aero", "FChaosClothAssetSimulationAerodynamicsConfigNode", {
            "Drag": weighted(p["drag"]), "Lift": weighted(p["lift"]), "WindVelocitySpace": "WorldSpace",
            "WindVelocity": "(X=0,Y=0,Z=0)"}),
        ("Collision", "FChaosClothAssetSimulationCollisionConfigNode", {
            "CollisionThicknessImported": "(ImportedValue=%s,bUseImportedValue=False)" % _num(p["collision_thickness_cm"]),
            "FrictionCoefficientImported": "(ImportedValue=%s,bUseImportedValue=False)" % _num(p["friction"]),
            "bEnableSkinnedTriangleMeshCollisions": _b(p["skinned_triangle_mesh_collisions"])}),
    ]
    if p["self_collision"]:
        nodes.append(("SelfCollision", "FChaosClothAssetSimulationSelfCollisionConfigNode_v2", {
            "bUseSelfCollisions": "True", "SelfCollisionThickness": weighted(p["self_thickness_cm"]),
            "SelfCollisionFriction": "(ImportedValue=%s,bUseImportedValue=False)" % _num(p["friction"])}))
    nodes += [
        ("Solver", "FChaosClothAssetSimulationSolverConfigNode", {
            "NumIterations": str(int(p["iterations"])), "MaxNumIterations": str(int(p["max_iterations"])),
            "NumSubstepsImported": "(ImportedValue=%d,bUseImportedValue=False)" % int(p["substeps"])}),
        ("MaxDistance", "FChaosClothAssetSimulationMaxDistanceConfigNode", {
            "MaxDistance": "(bIsAnimatable=True,Low=0,High=%s,WeightMap=\"%s\")" % (_num(p["max_distance_cm"]), WEIGHT_ATTR),
            "InKinematic": '(StringValue="")'}),
        ("Tethers", "FChaosClothAssetSimulationLongRangeAttachmentConfigNode_v2", {
            "TetherStiffness": weighted(p["tether_stiffness"]), "TetherScale": weighted(p["tether_scale"])}),
        ("Terminal", "FChaosClothAssetTerminalNode_v2", {}),
    ]
    chain = [k for k, _t, _p in nodes if k not in SAMPLER_KEYS + ("Terminal",)]
    links = [(a, "Collection", b, "Collection") for a, b in zip(chain, chain[1:])]
    if back_local_cm is None:
        links += [("CrownDistance", "Sampler", "CrownFalloff", "Sampler")]
    else:
        links += [("CrownDistance", "Sampler", "PinUnion", MIN_SAMPLER_INPUTS[0] % 0),
                  ("BackDistance", "Sampler", "PinUnion", MIN_SAMPLER_INPUTS[0] % 1),
                  ("PinUnion", "Sampler", "CrownFalloff", "Sampler")]
    links += [("CrownFalloff", "Sampler", "CrownWeights", "Sampler"),
              ("CrownWeights", "AttributeName", "MaxDistance", "MaxDistance.WeightMap")]
    return nodes, links, "Terminal"


def dataflow_problems(nodes, links, terminal, p):
    probs = []
    by = {k: (t, props) for k, t, props in nodes}
    for k, t, props in nodes:
        if list(by).count(k) != 1:
            probs.append("DUP_NODE|" + k)
    if by.get("Stretch", (None, {}))[1].get("bStretchUse3dRestLengths") != "False":
        probs.append("REST_TRAP|stretch rest lengths from 3D (must be the flat 2D pattern)")
    bend = by.get("Bending", (None, {}))[1]
    if bend.get("RestAngleType") != "FlatnessRatio" or "Low=1," not in bend.get("FlatnessRatio", ""):
        probs.append("REST_TRAP|bending rest angles not flat")
    md = by.get("MaxDistance", (None, {}))[1].get("MaxDistance", "")
    if WEIGHT_ATTR not in md or "High=0" in md.replace("High=0.", "x"):
        probs.append("MAX_DISTANCE|no weight map or High=0 freezes the cloth (Engine trap 1)")
    if ("CrownWeights", "AttributeName", "MaxDistance", "MaxDistance.WeightMap") not in links:
        probs.append("WEIGHT_MAP_UNLINKED")
    imp = by.get("Import", (None, {}))[1]
    if imp.get("UVScale") != "(X=100,Y=100)" or imp.get("UVChannel") != "0":
        probs.append("PATTERN_SCALE|UV0 is metres: UVScale must be 100 on channel 0")
    if by.get(terminal, (None,))[0] != "FChaosClothAssetTerminalNode_v2":
        probs.append("TERMINAL")
    coll_in = {b for _a, pa, b, pb in links if pb == "Collection"}
    coll_out = {a for a, pa, _b, pb in links if pa == "Collection"}
    heads = [k for k, t, _ in nodes if k not in coll_in and k not in SAMPLER_KEYS + (terminal,)]
    tails = [k for k, t, _ in nodes if k not in coll_out and k not in SAMPLER_KEYS + (terminal,)]
    if heads != ["Import"] or len(tails) != 1:
        probs.append("CHAIN|heads=%s tails=%s" % (heads, tails))
    if "BackDistance" in by:     # v2 crown+back: both distances must reach the falloff through the Min sampler
        want = {("CrownDistance", "Sampler", "PinUnion", MIN_SAMPLER_INPUTS[0] % 0),
                ("BackDistance", "Sampler", "PinUnion", MIN_SAMPLER_INPUTS[0] % 1),
                ("PinUnion", "Sampler", "CrownFalloff", "Sampler")}
        if by.get("PinUnion", (None,))[0] != "FDataflowMinSamplerNode" or not want <= set(links):
            probs.append("BACK_PIN_UNLINKED|the back sphere does not reach the weight map through a Min sampler")
        if ("CrownDistance", "Sampler", "CrownFalloff", "Sampler") in links:
            probs.append("BACK_PIN_BYPASSED|crown distance wired straight to the falloff")
    elif ("CrownDistance", "Sampler", "CrownFalloff", "Sampler") not in links:
        probs.append("CROWN_UNLINKED")
    order = [k for k, _t, _p in nodes]
    if order.index("CrownWeights") > order.index("MaxDistance") or order.index("MaxDistance") > order.index("Tethers"):
        probs.append("ORDER|weights before MaxDistance before Tethers")
    return probs


# ============================================================================================== pure: BP / PIE
def template_target(before, cloth_path, mi_path):
    after = dict(before)
    after.update({"asset": cloth_path, "override_materials": [mi_path], "relative_scale": [1.0, 1.0, 1.0]})
    return after


TEMPLATE_KEYS = ("class", "asset", "override_materials", "relative_location", "relative_rotation", "relative_scale",
                 "absolute_rotation", "attach_socket")


def template_diff(want, got, keys=TEMPLATE_KEYS):
    out = {}
    for k in keys:
        a, b = want.get(k), got.get(k)
        if isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(isinstance(x, (int, float)) for x in a + b):
            if any(abs(x - y) > TOL for x, y in zip(a, b)):
                out[k] = (b, a)
        elif a != b:
            out[k] = (b, a)
    return out


def before_problems(fig, tpl, inst):
    """The state APPLY expects to replace: today's drape on the template, and a level instance that does not
    override what APPLY writes (else the template change cannot reach the level / PIE)."""
    probs = []
    if tpl.get("class") != CLOTH_CLASS:
        probs.append("TEMPLATE_CLASS|%s|%s (never give a cloth asset to another component class)" % (fig, tpl.get("class")))
    if tpl.get("asset") != OLD_ASSET[fig]:
        probs.append("TEMPLATE_ASSET|%s|%s" % (fig, tpl.get("asset")))
    if any(abs(s - OLD_SCALE) > 1e-4 for s in tpl.get("relative_scale") or [0, 0, 0]):
        probs.append("TEMPLATE_SCALE|%s|%s" % (fig, tpl.get("relative_scale")))
    if inst is not None:
        for k in ("asset", "override_materials", "relative_scale"):
            if template_diff({k: tpl.get(k)}, {k: inst.get(k)}, (k,)):
                probs.append("INSTANCE_OVERRIDE|%s|%s|template=%s instance=%s" % (fig, k, tpl.get(k), inst.get(k)))
        if inst.get("attach_parent") != BODY or inst.get("attach_socket") != "head":
            probs.append("INSTANCE_ATTACH|%s|%s/%s" % (fig, inst.get("attach_parent"), inst.get("attach_socket")))
    return probs


def pie_problems(fig, r, cloth_path, mi_path):
    probs = []
    if r.get("asset") != cloth_path:
        probs.append("PIE_ASSET|%s|%s" % (fig, r.get("asset")))
    if r.get("material0") != mi_path:
        probs.append("PIE_MATERIAL|%s|%s" % (fig, r.get("material0")))
    if not r.get("parent_is_this_body") or r.get("attach_socket") != "head":
        probs.append("PIE_PARENT|%s|%s|%s" % (fig, r.get("attach_parent_path"), r.get("attach_socket")))
    if any(abs(s - 1.0) > 1e-4 for s in r.get("relative_scale") or [0, 0, 0]):
        probs.append("PIE_SCALE|%s|%s" % (fig, r.get("relative_scale")))
    if r.get("simulation_enabled") is not True:
        probs.append("PIE_SIM_DISABLED|%s" % fig)
    if r.get("follows_head_cm") is None or r["follows_head_cm"] > 1.0:
        probs.append("PIE_NOT_RIDING|%s|component is %s cm from where the head socket puts it" % (fig, r.get("follows_head_cm")))
    return probs


def bounds_metrics(origin, extent, feet_z, head_z):
    lo, hi = origin[2] - extent[2], origin[2] + extent[2]
    return {"bounds_bottom_above_feet_cm": lo - feet_z, "bounds_top_above_head_cm": hi - head_z,
            "footprint_cm": [2 * extent[0], 2 * extent[1]],
            "note": "component bounds: INDICATIVE (cloth bounds may be padded; curtain saw ~128 cm)"}


# ============================================================================================== unreal glue
def _path(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def _full(obj):
    return str(obj.get_path_name()) if obj is not None else None


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _rot(r):
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())


def _read(path):
    with open(path, encoding="utf-8") as h:
        return json.load(h)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def _temp_actor_guard(world):
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
        _require(unreal.EditorAssetLibrary.does_asset_exist(p), "PLANNED_ASSET_MISSING|" + p)
        _require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), "SAVE_ASSET_FAILED|" + p)
    if dirty["maps"]:
        _require(dirty["maps"] == [WORLD], "MAP_SCOPE|%s" % dirty["maps"])
        _require(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "SAVE_MAP_FAILED")
    after = _census()
    _require(after == {"content": [], "maps": []}, "POST_SAVE_DIRTY|" + json.dumps(after))
    return dirty


def _backup(run, figs):
    d = BACKUP_ROOT + run
    os.makedirs(d)
    files = [UMAP] + [CONTENT + names(f, 1)["bp"][len("/Game/"):] + ".uasset" for f in figs]
    rows = []
    for src in files:
        dst = os.path.join(d, os.path.relpath(src, CONTENT))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        _require(sha256_file(src) == sha256_file(dst), "BACKUP_HASH|" + src)
        rows.append({"src": src, "dst": dst, "bytes": os.path.getsize(dst), "sha256": sha256_file(dst)})
    return d, rows


def _figure_actors(figs, world=None):
    """{fig: actor}: label "<id> Clam" AND class BP_<id>_Draped_C, exactly one each (s3_sack_install.py:852)."""
    if world is None:
        acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    else:
        acts = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    index = {}
    for a in acts:
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


def _one(actor, name, cls_name=None):
    hits = [c for c in actor.get_components_by_class(unreal.ActorComponent) if str(c.get_name()) == name]
    if cls_name:
        hits = [c for c in hits if str(c.get_class().get_name()) == cls_name]
    _require(len(hits) == 1, "COMPONENT|%s|%s|%d" % (actor.get_actor_label(), name, len(hits)))
    return hits[0]


def _comp_state(c):
    st = {"class": str(c.get_class().get_name()), "asset": _path(c.get_asset()),
          "override_materials": [_path(m) for m in (c.get_editor_property("override_materials") or [])],
          "relative_location": _vec(c.get_editor_property("relative_location")),
          "relative_rotation": _rot(c.get_editor_property("relative_rotation")),
          "relative_scale": _vec(c.get_editor_property("relative_scale3d")),
          "absolute_rotation": bool(c.get_editor_property("absolute_rotation"))}
    try:
        st["attach_socket"] = str(c.get_attach_socket_name())
        par = c.get_attach_parent()
        st["attach_parent"] = str(par.get_name()) if par is not None else None
    except Exception as exc:  # noqa: BLE001 - templates may not resolve a parent
        st["attach_error"] = str(exc)
    for k in ("teleport_distance_threshold", "teleport_rotation_threshold", "use_attached_parent_as_pose_component"):
        try:
            v = c.get_editor_property(k)
            st[k] = bool(v) if isinstance(v, bool) else float(v)
        except Exception as exc:  # noqa: BLE001 - informational
            st[k] = "ERR %s" % exc
    return st


def _template(bp_path):
    """The BP's ShoreHeadCloth TEMPLATE (SubobjectDataSubsystem; create_pinned_shore_drape.py:54-65)."""
    bp = unreal.load_asset(bp_path)
    _require(bp is not None, "BP_MISSING|" + bp_path)
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    dl = unreal.SubobjectDataBlueprintFunctionLibrary
    hits = []
    for h in sub.k2_gather_subobject_data_for_blueprint(bp):
        d = dl.get_data(h)
        if str(dl.get_variable_name(d)) == CLOTH:
            hits.append(dl.get_object_for_blueprint(d, bp))
    # 6 Oct live: the gather returns two handles for ShoreHeadCloth; dedupe by object (same template twice), and only
    # refuse if two DIFFERENT objects remain (then name them).
    uniq = {}
    for o in hits:
        if o is not None:
            uniq.setdefault(o.get_path_name(), o)
    _require(len(uniq) == 1, "TEMPLATE_COUNT|%s|%d|%s" % (bp_path, len(uniq), sorted(uniq)))
    hits = list(uniq.values())
    return bp, hits[0]


def _template_state(bp_path):
    _bp, c = _template(bp_path)
    st = _comp_state(c)
    st["attach_socket"] = "head"   # the template socket does not survive instancing; ConfigureShoreDrape attaches
    return st                      # (Docs/ShoreCast-20260910.md:84): compared on the INSTANCE only


def _facing_live(actor, body):
    """Feet facing; 6 Oct live: the editor Body returned one point for every leg socket (ZERO_VECTOR|hip line), so
    fall back to the horizontal head->eye-midpoint direction from the Face (rigid on the head)."""
    try:
        return facing_from_feet(*[_socket(body, b) for b in ("thigh_l", "thigh_r", "ball_l", "foot_l", "ball_r", "foot_r")])
    except LiveSackError:
        face = _one(actor, FACE, "SkeletalMeshComponent")
        eye_mid, _e = _eye_mid(face)
        head = _socket(face, "head") if _norm(_sub(_socket(face, "head"), _vec(face.get_world_location()))) > 1.0 else _socket(body, "head")
        d = _sub(eye_mid, head)
        d[2] = 0.0
        return _unit(d, "eye facing"), 0.0


def _socket(comp, name):
    return _vec(comp.get_socket_location(name))


def _axes(comp):
    return [_vec(comp.get_forward_vector()), _vec(comp.get_right_vector()), _vec(comp.get_up_vector())]


def _eye_mid(face):
    names_ = [str(face.get_bone_name(i)) for i in range(face.get_num_bones())]
    want = [n for n in names_ if n in ("FACIAL_L_Eye", "FACIAL_R_Eye")]
    if len(want) != 2:
        want = sorted(n for n in names_ if n.lower().endswith("_eye") and ("_l_" in n.lower() or "_r_" in n.lower()))
    if len(want) != 2:
        return None, []
    a, b = _socket(face, want[0]), _socket(face, want[1])
    return _mul(_add(a, b), 0.5), want


def _measure(fig, actor, params, override, layout=None, accept=()):
    """Read-only: the component-frame pin geometry for one figure (see upright_frame / shore02_frame; crown+back adds
    frame["back"]: the upper-back point and the down-the-back direction in the component frame, from the editor pose)."""
    layout = layout or DECISION[fig]["pin"]
    body = _one(actor, BODY, "SkeletalMeshComponent")
    cloth = _one(actor, CLOTH, CLOTH_CLASS)
    origin, axes = _vec(cloth.get_world_location()), _axes(cloth)
    up = [0.0, 0.0, 1.0]
    feet, toes = _facing_live(actor, body)
    if layout == "crown+back":
        eye_mid, eyes = _eye_mid(_one(actor, FACE, "SkeletalMeshComponent"))
        frame, probs = upright_frame(origin, axes, eye_mid, up, feet if toes > 1.0 else None, params, override)
        sk = {b: _socket(body, b) for b in ("pelvis", "spine_03", "spine_05", "neck_01", "head")}
        target, info = back_target_world(sk["spine_05"], sk["spine_03"], sk["neck_01"], feet, params)
        pose = torso_pose(sk["pelvis"], sk["neck_01"], sk["head"])
        probs += editor_pose_problems(fig, pose, accept)
        frame["back"] = {"target_world_cm": target, "back_local_cm": to_local(target, origin, axes),
                         "down_back_local": dir_to_local(info["down_back_world"], axes),
                         "back_normal_world": info["back_normal_world"], "editor_pose": pose,
                         "spine05_world_cm": sk["spine_05"]}
    elif DECISION[fig]["pin"] == "back":
        rec = _read(SHORE02_RECORD)
        bt = body.get_world_transform()
        frame, probs = shore02_frame(rec, lambda v: _vec(unreal.MathLibrary.transform_location(bt, unreal.Vector(*v))),
                                     origin, _socket(body, "head"), axes, up, params)
        eyes = None
    else:
        eye_mid, eyes = _eye_mid(_one(actor, FACE, "SkeletalMeshComponent"))
        frame, probs = upright_frame(origin, axes, eye_mid, up, feet if toes > 1.0 else None, params, override)
    frame.update({"comp_origin_world": origin, "comp_axes_world": axes, "eye_bones": eyes, "feet_facing_world": feet})
    return frame, probs


def _api_presence():
    want = [("GeometryScript_MeshEdits", "append_buffers_to_mesh"), ("GeometryScript_UVs", "set_num_uv_sets"),
            ("GeometryScript_MeshQueries", "get_vertex_count"), ("GeometryScript_MeshQueries", "get_num_uv_sets"),
            ("GeometryScript_MeshQueries", "get_num_triangle_i_ds"),
            ("GeometryScript_NewAssetUtils", "create_new_static_mesh_asset_from_mesh"),
            ("GeometryScriptSimpleMeshBuffers", None), ("GeometryScriptCreateNewStaticMeshAssetOptions", None),
            ("StaticMeshEditorSubsystem", "get_number_verts"), ("StaticMeshEditorSubsystem", "get_num_uv_channels"),
            ("DataflowEditorBlueprintLibrary", "add_dataflow_node"),
            ("DataflowEditorBlueprintLibrary", "set_dataflow_node_property"),
            ("DataflowEditorBlueprintLibrary", "connect_dataflow_nodes"), ("DataflowBlueprintLibrary", "evaluate_dataflow"),
            ("Dataflow", None), ("DataflowAssetFactory", None), ("ChaosClothAsset", None), ("ChaosClothAssetFactory", None),
            ("ChaosClothComponent", "set_asset"), ("ChaosClothComponent", "get_cloth_outfit_interactor"),
            ("ChaosClothComponent", "set_simulate_in_editor"), ("SubobjectDataSubsystem", "k2_gather_subobject_data_for_blueprint"),
            ("MathLibrary", "transform_location"), ("SystemLibrary", "get_component_bounds"),
            ("MaterialEditingLibrary", "set_material_instance_parent"), ("EditorAssetLibrary", "duplicate_asset"),
            ("MaterialEditingLibrary", "set_material_instance_scalar_parameter_value"),
            ("MaterialEditingLibrary", "set_material_instance_vector_parameter_value")]
    out = {}
    for c, a in want:
        cls = getattr(unreal, c, None)
        out[c if a is None else c + "." + a] = cls is not None and (a is None or hasattr(cls, a))
    return out


# --------------------------------------------------------------------------------------------- BUILD
def _mi_values(mi):
    mel = unreal.MaterialEditingLibrary
    out = {"scalars": {}, "vectors": {}, "textures": {}}
    for n in mel.get_scalar_parameter_names(mi):
        if mel.is_material_instance_parameter_overridden(mi, n):
            out["scalars"][str(n)] = float(mel.get_material_instance_scalar_parameter_value(mi, n))
    for n in mel.get_vector_parameter_names(mi):
        if mel.is_material_instance_parameter_overridden(mi, n):
            c = mel.get_material_instance_vector_parameter_value(mi, n)
            out["vectors"][str(n)] = [round(float(c.r), 6), round(float(c.g), 6), round(float(c.b), 6), round(float(c.a), 6)]
    for n in mel.get_texture_parameter_names(mi):
        if mel.is_material_instance_parameter_overridden(mi, n):
            out["textures"][str(n)] = _path(mel.get_material_instance_texture_parameter_value(mi, n))
    return out


def look_target(src_values, look):
    """The MI values BUILD must read back: the source MI's overrides, then the version's look on top."""
    want = {"scalars": dict(src_values["scalars"]), "vectors": {k: list(v) for k, v in src_values["vectors"].items()},
            "textures": dict(src_values.get("textures", {}))}
    want["scalars"].update({k: float(v) for k, v in look.get("scalars", {}).items()})
    want["vectors"].update({k: [float(x) for x in v] for k, v in look.get("vectors", {}).items()})
    return want


def mi_values_match(want, got, tol=1e-5):
    """float32 read-back tolerant equality (0.6 reads back 0.6000000238)."""
    if set(want["scalars"]) != set(got["scalars"]) or set(want["vectors"]) != set(got["vectors"]):
        return False
    if want.get("textures", {}) != got.get("textures", {}):
        return False
    if any(abs(want["scalars"][k] - got["scalars"][k]) > tol for k in want["scalars"]):
        return False
    return all(abs(a - b) <= tol for k in want["vectors"] for a, b in zip(want["vectors"][k], got["vectors"][k]))


def _build_materials(nm, variant, look=None):
    """Create-only duplicates; returns (created paths, readback). Reuses them only if this tool's BUILD record made
    them (a second figure batch of the same version). v2+: the MI gets the version's look over the source values."""
    look = look or MI_LOOK[1]
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    created, rb = [], {}
    if not eal.does_asset_exist(nm["master"]):
        m = eal.duplicate_asset(SRC_MASTER[variant], nm["master"])
        _require(m is not None, "DUP_MASTER|" + nm["master"])
        src = unreal.load_asset(SRC_MASTER[variant])
        m.modify()
        m.set_editor_property("two_sided", True)
        m.set_editor_property("used_with_clothing", True)
        mel.recompile_material(m)
        _require(mel.get_num_material_expressions(m) == mel.get_num_material_expressions(src),
                 "DUP_NODES|%d vs %d" % (mel.get_num_material_expressions(m), mel.get_num_material_expressions(src)))
        created.append(nm["master"])
    m = unreal.load_asset(nm["master"])
    rb["master"] = {k: bool(m.get_editor_property(k)) for k in ("two_sided", "used_with_clothing", "used_with_skeletal_mesh")}
    _require(all(rb["master"].values()), "MASTER_FLAGS|%s" % rb["master"])
    if not eal.does_asset_exist(nm["mi"]):
        mi = eal.duplicate_asset(SRC_MI, nm["mi"])
        _require(mi is not None, "DUP_MI|" + nm["mi"])
        mi.modify()
        mel.set_material_instance_parent(mi, m)
        for k, v in look.get("scalars", {}).items():       # setter returns are not trusted: read back below
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
        for k, v in look.get("vectors", {}).items():
            mel.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*[float(x) for x in v]))
        mel.update_material_instance(mi)
        created.append(nm["mi"])
    mi = unreal.load_asset(nm["mi"])
    _require(_path(mi.get_editor_property("parent")) == nm["master"], "MI_PARENT|%s" % mi.get_editor_property("parent"))
    src = _mi_values(unreal.load_asset(SRC_MI))
    want, got = look_target(src, look), _mi_values(mi)
    _require(src["scalars"] and mi_values_match(want, got), "MI_VALUES|want=%s got=%s" % (want, got))
    rb["mi"] = got
    rb["mi_look"] = look
    return created, rb


def _dynamic_mesh(sheet, placed):
    """In-memory only (no package): the sheet as a DynamicMesh with 2 UV sets. Used by DRY as a probe of every
    struct/field name BUILD relies on, and by BUILD."""
    dm = unreal.DynamicMesh()
    unreal.GeometryScript_UVs.set_num_uv_sets(dm, 2)
    buf = unreal.GeometryScriptSimpleMeshBuffers()
    buf.set_editor_property("vertices", [unreal.Vector(*p) for p in placed["positions_cm"]])
    vn = placed.get("normals") or [placed["normal"]] * len(placed["positions_cm"])   # crown+back: per-vertex
    buf.set_editor_property("normals", [unreal.Vector(*n) for n in vn])
    buf.set_editor_property("uv0", [unreal.Vector2D(u, v) for u, v in sheet["uv0"]])
    buf.set_editor_property("uv1", [unreal.Vector2D(u, v) for u, v in sheet["uv1"]])
    buf.set_editor_property("triangles", [unreal.IntVector(a, b, c) for a, b, c in sheet["tris"]])
    res = unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dm, buf)
    dm = res[0] if isinstance(res, tuple) else res
    q = unreal.GeometryScript_MeshQueries
    # MeshQueryFunctions.h:179 GetVertexCount, :90 GetNumTriangleIDs, :257 GetNumUVSets (5.8 headers)
    rb = {"vertices": int(q.get_vertex_count(dm)), "triangles": int(q.get_num_triangle_i_ds(dm)),
          "uv_sets": int(q.get_num_uv_sets(dm))}
    probs = []
    if rb["vertices"] != len(placed["positions_cm"]):
        probs.append("DM_VERTS|%d vs %d" % (rb["vertices"], len(placed["positions_cm"])))
    if rb["triangles"] != len(sheet["tris"]):
        probs.append("DM_TRIS|%d vs %d" % (rb["triangles"], len(sheet["tris"])))
    if rb["uv_sets"] < 2:
        probs.append("DM_UV_SETS|%d" % rb["uv_sets"])
    return dm, rb, probs


def _build_mesh(path, sheet, placed, mi):
    gs = unreal
    dm, dm_rb, probs = _dynamic_mesh(sheet, placed)
    _require(not probs, "DYNAMIC_MESH|%s" % probs)
    opts = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    for k, v in (("enable_recompute_normals", False), ("enable_recompute_tangents", True), ("enable_nanite", False),
                 ("enable_collision", False), ("use_original_vertex_order", True)):
        opts.set_editor_property(k, v)
    res = gs.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dm, path, opts)
    mesh = res[0] if isinstance(res, tuple) else res
    _require(mesh is not None and unreal.EditorAssetLibrary.does_asset_exist(path), "MESH_CREATE|" + path)
    mesh.set_material(0, mi)
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    box = mesh.get_bounding_box()
    rb = {"verts": int(sub.get_number_verts(mesh, 0)), "uv_channels": int(sub.get_num_uv_channels(mesh, 0)),
          "box_min": _vec(box.min), "box_max": _vec(box.max), "material0": _path(mesh.get_material(0))}
    want_n = len(placed["positions_cm"])
    lo = [min(p[i] for p in placed["positions_cm"]) for i in range(3)]
    hi = [max(p[i] for p in placed["positions_cm"]) for i in range(3)]
    probs = []
    if rb["verts"] != want_n:
        probs.append("MESH_VERTS|%d vs %d" % (rb["verts"], want_n))
    if rb["uv_channels"] < 2:
        probs.append("MESH_UV1|%d channels (the fray fringe needs UV1)" % rb["uv_channels"])
    if any(abs(a - b) > 0.5 for a, b in zip(rb["box_min"] + rb["box_max"], lo + hi)):
        probs.append("MESH_BOX|%s..%s vs %s..%s" % (rb["box_min"], rb["box_max"], lo, hi))
    if rb["material0"] != _path(mi):
        probs.append("MESH_MATERIAL|%s" % rb["material0"])
    _require(not probs, "MESH_READBACK|%s" % probs)
    return mesh, rb


def _min_input_candidates(pin):
    """'InputSamplers[1]' -> every naming the multi-input pin may carry (the array form ran for CollectionLods[0])."""
    if not pin.startswith("InputSamplers["):
        return [pin]
    i = int(pin[len("InputSamplers["):-1])
    return [fmt % i for fmt in MIN_SAMPLER_INPUTS]


def _build_dataflow(path, mesh_path, pin_local, p, back_local=None):
    dfl = unreal.DataflowEditorBlueprintLibrary
    nodes, links, terminal = dataflow_spec(mesh_path, pin_local, p, back_local)
    probs = dataflow_problems(nodes, links, terminal, p)
    _require(not probs, "DATAFLOW_SPEC|%s" % probs)
    d, n = path.rsplit("/", 1)
    df = unreal.AssetToolsHelpers.get_asset_tools().create_asset(n, d, unreal.Dataflow, unreal.DataflowAssetFactory())
    _require(df is not None, "DF_CREATE|" + path)
    made, fails = {}, []
    for i, (key, typ, props) in enumerate(nodes):
        name = dfl.add_dataflow_node(df, typ, key, unreal.Vector2D(320.0 * i, 400.0 if key in SAMPLER_KEYS else 0.0))
        _require(name and str(name) != "None", "DF_NODE|%s|%s" % (key, typ))
        made[key] = name
        for prop, value in props.items():
            if not dfl.set_dataflow_node_property(df, name, prop, value):
                fails.append("%s.%s=%s" % (key, prop, value))
    _require(not fails, "DF_PROPS|%s" % fails)
    used_pins = {}
    for a, pa, b, pb in links:
        ok = False
        for cand in _min_input_candidates(pb):
            if dfl.connect_dataflow_nodes(df, made[a], pa, made[b], cand):
                ok, used_pins["%s.%s" % (b, pb)] = True, cand
                break
        _require(ok, "DF_LINK|%s.%s->%s.%s (tried %s)" % (a, pa, b, pb, _min_input_candidates(pb)))
    tail = [k for k, _t, _p in nodes if k not in SAMPLER_KEYS + (terminal,)][-1]
    term_in = None
    for cand in ("CollectionLods[0]", "CollectionLods_0", "CollectionLods", "Collection"):
        if dfl.connect_dataflow_nodes(df, made[tail], "Collection", made[terminal], cand):
            term_in = cand
            break
    _require(term_in is not None, "DF_TERMINAL_LINK")
    return df, {"nodes": {k: str(v) for k, v in made.items()}, "terminal_input": term_in, "terminal": str(made[terminal]),
                "link_pins": used_pins}


def _build_cloth(path, df, terminal_name, mi):
    import warnings
    d, n = path.rsplit("/", 1)
    factory = unreal.ChaosClothAssetFactory()
    factory.set_editor_property("edit_after_new", False)
    cloth = unreal.AssetToolsHelpers.get_asset_tools().create_asset(n, d, unreal.ChaosClothAsset, factory)
    _require(cloth is not None, "CA_CREATE|" + path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        inst = cloth.get_editor_property("dataflow_instance")
        inst.set_editor_property("dataflow_asset", df)
        inst.set_editor_property("dataflow_terminal", terminal_name)
        cloth.set_editor_property("dataflow_instance", inst)
    evaluated = unreal.DataflowBlueprintLibrary.evaluate_dataflow(df, cloth)   # False even on success (trap 2)
    mats = list(cloth.get_editor_property("materials") or [])
    got = [_path(m.get_editor_property("material_interface")) for m in mats]
    if got != [_path(mi)]:
        # evaluation did not carry the mesh slot: set the asset slot as create_pinned_shore_drape.py:49-52 did
        _require(len(mats) == 1, "CA_SLOTS|%s (expected one render slot)" % got)
        mats[0].set_editor_property("material_interface", mi)
        cloth.set_editor_property("materials", mats)
        got = [_path(m.get_editor_property("material_interface")) for m in cloth.get_editor_property("materials")]
    _require(got == [_path(mi)], "CA_MATERIAL|%s" % got)
    linked = cloth.get_editor_property("dataflow_instance").get_editor_property("dataflow_asset")
    _require(_path(linked) == _path(df), "CA_LINK|%s" % _path(linked))
    return cloth, {"evaluated_return": bool(evaluated), "materials": got}


def run_build(run, figs, version, params, extra, ed):
    eal = unreal.EditorAssetLibrary
    variant = params["material_variant"]
    nm0 = names(figs[0], version, variant)
    prior = _read(RECORDS["BUILD"]) if os.path.exists(RECORDS["BUILD"]) else {"versions": {}}
    vrec = prior["versions"].get(str(version), {"figures": {}, "materials_created": []})
    clash = [f for f in figs if f in vrec["figures"]]
    _require(not clash, "ALREADY_BUILT|%s v%d (bump version)" % (clash, version))
    _require(vrec.get("params", params) == params, "PARAMS_DIFFER_WITHIN_VERSION|bump version")
    for f in figs:
        for k in ("mesh", "dataflow", "cloth"):
            _require(not eal.does_asset_exist(names(f, version, variant)[k]), "EXISTS|" + names(f, version, variant)[k])
    existing = [p for p in (nm0["master"], nm0["mi"]) if eal.does_asset_exist(p)]
    _require(all(p in vrec["materials_created"] or p in _all_created_materials(prior) for p in existing),
             "FOREIGN_MATERIAL|%s exists but this tool did not create it" % existing)
    planned = planned_packages("BUILD", figs, version, variant, existing)
    actors = _figure_actors(figs)
    geo, probs = {}, []
    look = extra.get("mi_look") or mi_look(version)
    _require(vrec.get("mi_look", look) == look, "LOOK_DIFFERS_WITHIN_VERSION|bump version")
    back_figs = extra.get("back_pin_figures", list(BACK_PIN_FIGURES))
    _require(vrec.get("back_pin_figures", back_figs) == back_figs, "BACK_PIN_FIGURES_DIFFER_WITHIN_VERSION|bump version")
    for f in figs:                                       # every read before the first write
        layout = pin_layout(f, version, back_figs)
        frame, fp = _measure(f, actors[f], params, extra["forward_local_override"].get(f), layout,
                             extra.get("accept_editor_pose", ()))
        sheet, placed, m, gp = plan_geometry(f, frame, params, layout)
        probs += fp + gp
        geo[f] = (frame, sheet, placed, m, layout)
    _require(not probs, "PREFLIGHT|%s" % probs)
    unreal.log("S3LIVESACK_PLAN|run=%s|BUILD|%s" % (run, json.dumps(planned)))
    created, mats_created, out = [], [], {}
    mat_created, mat_rb = _build_materials(nm0, variant, look)
    mats_created += mat_created
    mi = unreal.load_asset(nm0["mi"])
    for f in figs:
        nm = names(f, version, variant)
        frame, sheet, placed, m, layout = geo[f]
        back_local = placed["pins"][1] if layout == "crown+back" else None
        mesh, mesh_rb = _build_mesh(nm["mesh"], sheet, placed, mi)
        df, df_rb = _build_dataflow(nm["dataflow"], nm["mesh"], placed["pin_local_cm"], params, back_local)
        cloth, ca_rb = _build_cloth(nm["cloth"], df, df_rb["terminal"], mi)
        created += [nm["mesh"], nm["dataflow"], nm["cloth"]]
        out[f] = {"names": nm, "layout": layout, "frame": frame, "metrics": m, "sheet_sha256": buffers_sha(sheet, placed),
                  "mesh": mesh_rb, "dataflow": df_rb, "cloth": ca_rb}
    saved = _save(ed, planned)
    vrec["figures"].update(out)
    vrec["materials_created"] = sorted(set(vrec["materials_created"]) | set(mats_created))
    vrec["params"] = params
    vrec["mi_look"] = look
    vrec["back_pin_figures"] = back_figs
    vrec.setdefault("runs", []).append({"run": run, "figures": figs, "saved": saved, "material_readback": mat_rb})
    prior["versions"][str(version)] = vrec
    _write(RECORDS["BUILD"], prior)
    return {"figures": figs, "version": version, "saved": len(saved["content"]), "record": RECORDS["BUILD"]}


def _all_created_materials(rec):
    return [p for v in rec.get("versions", {}).values() for p in v.get("materials_created", [])]


# --------------------------------------------------------------------------------------------- APPLY / REVERT
def _set_template(bp_path, want):
    bp, c = _template(bp_path)
    _require(str(c.get_class().get_name()) == CLOTH_CLASS, "TEMPLATE_CLASS|%s" % c.get_class().get_name())
    asset = unreal.load_asset(want["asset"])
    _require(asset is not None and str(asset.get_class().get_name()) == "ChaosClothAsset", "ASSET_CLASS|" + want["asset"])
    mats = [unreal.load_asset(p) if p else None for p in want["override_materials"]]
    c.modify()
    c.set_asset(asset)
    # the whole list by property (REVERT may need a SHORTER list than APPLY left); read back below, never trusted
    c.set_editor_property("override_materials", mats)
    c.set_editor_property("relative_scale3d", unreal.Vector(*want["relative_scale"]))
    _require(unreal.BlueprintEditorLibrary.compile_blueprint(bp), "COMPILE|" + bp_path)
    got = _template_state(bp_path)
    bad = template_diff(want, got)
    _require(not bad, "TEMPLATE_READBACK|%s|%s" % (bp_path, bad))
    return got


def _instance_state(actor, body=None):
    c = _one(actor, CLOTH, CLOTH_CLASS)
    st = _comp_state(c)
    body = body or _one(actor, BODY, "SkeletalMeshComponent")
    par = c.get_attach_parent()
    st["parent_is_this_body"] = par is not None and _full(par) == _full(body)
    return st


def run_apply(run, figs, version, params, ed):
    build = _read(RECORDS["BUILD"])["versions"].get(str(version))
    _require(build and all(f in build["figures"] for f in figs), "NOT_BUILT|%s v%d" % (figs, version))
    variant = build["params"]["material_variant"]
    actors = _figure_actors(figs)
    before, probs = {}, []
    for f in figs:                                       # every read before the first write
        nm = names(f, version, variant)
        for k in ("cloth", "mi"):
            _require(unreal.EditorAssetLibrary.does_asset_exist(nm[k]), "MISSING|" + nm[k])
        tpl, inst = _template_state(nm["bp"]), _instance_state(actors[f])
        probs += before_problems(f, tpl, inst)
        before[f] = {"template": tpl, "instance": inst}
    _require(not probs, "PREFLIGHT|%s" % probs)
    planned = planned_packages("APPLY", figs, version, variant, instances=True)
    backup, files = _backup(run, figs)
    # the instance before-values REVERT restores (before.<fig>.instance has the full state; this map is what
    # run_revert writes back, the same key the 6 Oct instance fix used)
    rec = {"run": run, "version": version, "variant": variant, "figures": figs, "before": before, "backup": backup,
           "backup_files": files, "saved": False,
           "instance_asset_override": {f: before[f]["instance"]["asset"] for f in figs}, "instance_write": True}
    _write(RECORDS["APPLY"], rec, exclusive=True)
    unreal.log("S3LIVESACK_PLAN|run=%s|APPLY|%s|backup=%s" % (run, json.dumps(planned), backup))
    after = {}
    for f in figs:
        nm = names(f, version, variant)
        after[f] = {"template": _set_template(nm["bp"], template_target(before[f]["template"], nm["cloth"], nm["mi"]))}
    # the placed figures carry their OWN asset value (6 Oct: APPLY v1 saved the templates and the level kept
    # CA_ShoreHeadDrape; S3LSFIX-20261006-172813 set it per instance): set it on each, after the compile, by a
    # FRESH lookup (the compile re-instanced the actors), read back, and only then save BPs + level together.
    for f, a in _figure_actors(figs).items():
        _set_instance_asset(a, names(f, version, variant)["cloth"])
    for f, a in _figure_actors(figs).items():
        nm = names(f, version, variant)
        inst = _instance_state(a)
        bad = template_diff({"asset": nm["cloth"], "override_materials": [nm["mi"]], "relative_scale": [1.0, 1.0, 1.0]},
                            inst, ("asset", "override_materials", "relative_scale"))
        _require(not bad and inst["parent_is_this_body"],
                 "INSTANCE_READBACK|%s|%s|parent=%s|NOTHING SAVED" % (f, bad, inst["parent_is_this_body"]))
    rec["saved_packages"] = _save(ed, planned)
    rec["saved"] = True
    for f, a in _figure_actors(figs).items():           # post-save read-back = the record's "after"
        after[f]["instance"] = _instance_state(a)
        _require(after[f]["instance"]["asset"] == names(f, version, variant)["cloth"], "POST_SAVE_INSTANCE|%s" % f)
    rec["after"] = after
    _write(RECORDS["APPLY"], rec)
    return {"figures": figs, "backup": backup, "saved": rec["saved_packages"]}


def _set_instance_asset(actor, asset_path):
    """The level instance's own ShoreHeadCloth asset value (modify() -> the level dirties: it is in the save scope)."""
    c = _one(actor, CLOTH, CLOTH_CLASS)
    asset = unreal.load_asset(asset_path)
    _require(asset is not None and str(asset.get_class().get_name()) == "ChaosClothAsset", "INSTANCE_ASSET_CLASS|" + asset_path)
    c.modify()
    c.set_asset(asset)


def run_revert(run, ed):
    rec = _read(RECORDS["APPLY"])
    figs, version, variant = rec["figures"], rec["version"], rec["variant"]
    inst_over = rec.get("instance_asset_override") or {}   # v1: written by the 6 Oct instance fix; v2+: by APPLY
    probs = []
    actors = _figure_actors(figs)
    for f in figs:                                       # drift check first: BP + instance must still be what APPLY left
        nm = names(f, version, variant)
        got = _template_state(nm["bp"])
        want_after = (rec.get("after") or {}).get(f, {}).get("template") or \
            template_target(rec["before"][f]["template"], nm["cloth"], nm["mi"])
        bad = template_diff(want_after, got)
        if bad:
            probs.append("DRIFT|%s|%s" % (f, bad))
        # the instance ASSET only (v1's record carries a RECONSTRUCTED after.instance whose material/scale are the old
        # values: not a measurement; VERIFY S3LIVESACK-20261006-172851 read MI + scale 1 on every instance)
        ia = _instance_state(actors[f])["asset"]
        if inst_over and ia != nm["cloth"]:
            probs.append("INSTANCE_DRIFT|%s|%s (want %s)" % (f, ia, nm["cloth"]))
        if inst_over and f not in inst_over:
            probs.append("INSTANCE_RECORD|%s missing from instance_asset_override" % f)
    _require(not probs, "REVERT_REFUSED|%s" % probs)
    planned = planned_packages("REVERT", figs, version, variant, instances=bool(inst_over))
    for f in figs:
        _set_template(names(f, version, variant)["bp"], rec["before"][f]["template"])
    if inst_over:                                        # fresh lookups: the compile re-instanced the actors
        for f, a in _figure_actors(figs).items():
            _set_instance_asset(a, inst_over[f])
    for f, a in _figure_actors(figs).items():           # read back BEFORE the save: refuse = nothing saved
        inst = _instance_state(a)
        bad = template_diff(rec["before"][f]["instance"], inst, ("asset", "override_materials", "relative_scale"))
        _require(not bad, "REVERT_INSTANCE|%s|%s|NOTHING SAVED" % (f, bad))
    saved = _save(ed, planned)                           # one scope: the BPs (+ the level, required if instances)
    rec["reverted"] = {"run": run, "saved": saved}
    _write(RECORDS["APPLY"], rec)
    os.replace(RECORDS["APPLY"], RECORDS["APPLY"] + ".reverted-" + run)
    return {"figures": figs, "saved": saved}


# --------------------------------------------------------------------------------------------- probes
def _expected(fig):
    """(cloth, mi) the level should show: the active APPLY record, else today's drape."""
    if os.path.exists(RECORDS["APPLY"]):
        r = _read(RECORDS["APPLY"])
        if fig in r["figures"]:
            nm = names(fig, r["version"], r["variant"])
            return nm["cloth"], nm["mi"]
    return OLD_ASSET[fig], OLD_MATERIAL


def _build_row(fig, version):
    """(row, params) of the BUILD record for this figure/version, or (None, None)."""
    if not os.path.exists(RECORDS["BUILD"]):
        return None, None
    v = _read(RECORDS["BUILD"])["versions"].get(str(version)) or {}
    return (v.get("figures") or {}).get(fig), v.get("params")


def _back_pin_track(actor, row, params):
    """v2 crown+back, informational: where the (head-riding) back disc centre is NOW vs the back point the current
    pose puts it (spine_05 + back normal x (depth + lift)). Large values = the head moved relative to the torso."""
    back = ((row or {}).get("frame") or {}).get("back")
    if not back or (row or {}).get("layout") != "crown+back":
        return None
    body = _one(actor, BODY, "SkeletalMeshComponent")
    c = _one(actor, CLOTH, CLOTH_CLASS)
    pins = (row.get("metrics") or {}).get("coverage", {}).get("pins_cm") or [None, back["back_local_cm"]]
    disc = _vec(unreal.MathLibrary.transform_location(c.get_world_transform(), unreal.Vector(*pins[1])))
    feet, _t = _facing_live(actor, body)
    target, _i = back_target_world(_socket(body, "spine_05"), _socket(body, "spine_03"), _socket(body, "neck_01"), feet, params)
    return {"back_pin_track_cm": _norm(_sub(disc, target)), "disc_world_cm": disc, "target_world_cm": target}


def _reading(actor, fig, world_kind, build_row=None, build_params=None):
    body = _one(actor, BODY, "SkeletalMeshComponent")
    c = _one(actor, CLOTH, CLOTH_CLASS)
    st = _instance_state(actor, body)
    r = {"asset": st["asset"], "material0": _path(c.get_material(0)), "attach_socket": st.get("attach_socket"),
         "attach_parent_path": _full(c.get_attach_parent()), "parent_is_this_body": st["parent_is_this_body"],
         "relative_scale": st["relative_scale"], "world": world_kind}
    for k, fn in (("simulation_enabled", "is_simulation_enabled"), ("simulation_suspended", "is_simulation_suspended")):
        try:
            r[k] = bool(getattr(c, fn)())
        except Exception as exc:  # noqa: BLE001
            r[k] = "ERR %s" % exc
    try:   # does the component sit where the head socket + relative offset puts it? (rides the head, not floating)
        # absolute ROTATION (Shore02) leaves the location relative to the socket frame, so one formula serves both
        # [inferred from SceneComponent semantics; a Shore02 mismatch here is a probe question, not a proof of drift]
        want = _vec(unreal.MathLibrary.transform_location(body.get_socket_transform("head"), unreal.Vector(*st["relative_location"])))
        r["follows_head_cm"] = _norm(_sub(want, _vec(c.get_world_location())))
    except Exception as exc:  # noqa: BLE001
        r["follows_head_error"] = str(exc)
    try:
        o, e, _s = unreal.SystemLibrary.get_component_bounds(c)
        feet = min(_socket(body, "ball_l")[2], _socket(body, "ball_r")[2])
        r["bounds"] = bounds_metrics(_vec(o), _vec(e), feet, _socket(body, "head")[2])
    except Exception as exc:  # noqa: BLE001
        r["bounds_error"] = str(exc)
    try:
        it = c.get_cloth_outfit_interactor()
        if it is not None:
            r["interactor"] = {str(n): str(it.get_weighted_float_property_value(n)) for n in it.get_all_property_names()
                               if str(n) in ("MassValue", "BendingStiffness", "CollisionThickness", "NumIterations",
                                             "NumSubsteps", "MaxDistance", "DampingCoefficient", "Drag",
                                             "StretchStiffness", "FrictionCoefficient")}
    except Exception as exc:  # noqa: BLE001
        r["interactor_error"] = str(exc)
    if build_row is not None:
        try:
            bt = _back_pin_track(actor, build_row, dict(PARAMS, **(build_params or {})))
            if bt is not None:
                r["back_pin"] = bt
        except Exception as exc:  # noqa: BLE001 - informational
            r["back_pin_error"] = str(exc)
    return r


def run_pie_probe(run, figs, ed):
    gw = ed.get_game_world()
    _require(gw is not None, "PIE_NOT_RUNNING (Gary starts PIE; this probe never starts or ends it)")
    rec = _read(RECORDS["APPLY"])
    out, fails = {"run": run, "figures": {}}, []
    actors = _figure_actors([f for f in figs if f in rec["figures"]], world=gw)
    for f, a in actors.items():
        nm = names(f, rec["version"], rec["variant"])
        r = _reading(a, f, "PIE", *_build_row(f, rec["version"]))
        out["figures"][f] = r
        fails += pie_problems(f, r, nm["cloth"], nm["mi"])
    out["fails"] = fails
    _write(OUT["PIE_PROBE"], out)
    _require(not fails, "PIE_PROBE|%s|out=%s" % (fails[:6], OUT["PIE_PROBE"]))
    return {"figures": len(actors), "out": OUT["PIE_PROBE"]}


def run_sim(mode, run, figs, extra, ed):
    """Editor-world probe on the LEVEL instances (transient Simulate In Editor). Census must not move."""
    c0 = _census()
    actors = _figure_actors(figs)
    state = _read(OUT["SIM"]) if mode != "SIM_START" else {"run": run, "figures": figs, "start": {}, "reads": []}
    if mode == "SIM_START":
        for f, a in actors.items():
            c = _one(a, CLOTH, CLOTH_CLASS)
            _require(not c.is_simulation_suspended(), "SUSPENDED|%s (the probe never changes suspend)" % f)
            state["start"][f] = _reading(a, f, "editor")
            c.set_simulate_in_editor(True)
            c.force_next_update_teleport_and_reset()
    elif mode == "SIM_READ":
        row = {"run": run, "figures": {}}
        for f, a in actors.items():
            row["figures"][f] = _reading(a, f, "editor")
        if extra["camera_label"]:
            cams = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                    if str(x.get_actor_label()) == extra["camera_label"]]
            _require(len(cams) == 1, "CAMERA|%s|%d" % (extra["camera_label"], len(cams)))
            shot = HERE + "s3_sack_livecloth_sim_%s.png" % run
            unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, shot, camera=cams[0], delay=2.0)
            row["still"] = shot + " (async: written ~2 s later; run SIM_STOP after it lands)"
        state["reads"].append(row)
    else:
        for f, a in actors.items():
            c = _one(a, CLOTH, CLOTH_CLASS)
            c.set_simulate_in_editor(False)              # SIE off FIRST, nothing else (trap 10 is about suspend)
            c.force_next_update_teleport_and_reset()
        state["stopped"] = run
    c1 = _census()
    state.setdefault("census", []).append({"mode": mode, "before": c0, "after": c1})
    _write(OUT["SIM"], state)
    _require(c0 == c1, "SIM_DIRTIED|%s -> %s (transient flag dirtied a package: report, do not save)" % (c0, c1))
    return {"mode": mode, "figures": figs, "out": OUT["SIM"]}


# --------------------------------------------------------------------------------------------- DRY / VERIFY
def run_dry(run, figs, version, params, extra):
    c0 = _census()
    variant = params["material_variant"]
    out = {"run": run, "figures": figs, "version": version, "params": params, "census": c0, "api": _api_presence(),
           "problems": [], "figures_detail": {}, "mi_look": extra.get("mi_look"),
           "back_pin_figures": extra.get("back_pin_figures"),
           "predicted_albedo": {"v1_textured": predicted_albedo(MI_LOOK[1], hem=0.0),
                                "v1_in_hem_band": predicted_albedo(MI_LOOK[1], hem=1.0),
                                "this_version": predicted_albedo(extra.get("mi_look") or MI_LOOK[1], hem=1.0)}}
    out["problems"] += ["API_MISSING|%s" % k for k, v in out["api"].items() if not v]
    eal = unreal.EditorAssetLibrary
    for p in (SRC_MASTER[variant], SRC_MI):
        if not eal.does_asset_exist(p):
            out["problems"].append("SOURCE_MISSING|" + p)
    if "Shore02_F52" in figs and not os.path.exists(SHORE02_RECORD):
        out["problems"].append("SOURCE_MISSING|" + SHORE02_RECORD)
    try:   # what BUILD inherits from the source master: the duplicate only adds two_sided + used_with_clothing
        m = unreal.load_asset(SRC_MASTER[variant])
        out["source_master_flags"] = {k: bool(m.get_editor_property(k)) for k in
                                      ("two_sided", "used_with_clothing", "used_with_skeletal_mesh")}
        out["source_mi_values"] = _mi_values(unreal.load_asset(SRC_MI))
    except Exception as exc:  # noqa: BLE001
        out["problems"].append("SOURCE_READ|%s" % exc)
    actors = _figure_actors(figs)
    for f in figs:
        nm = names(f, version, variant)
        d = {"names": nm, "exists": {k: eal.does_asset_exist(v) for k, v in nm.items() if k != "bp"}}
        try:
            d["template"] = _template_state(nm["bp"])
            d["instance"] = _instance_state(actors[f])
            if not os.path.exists(RECORDS["APPLY"]):
                out["problems"] += before_problems(f, d["template"], d["instance"])
            layout = pin_layout(f, version, extra.get("back_pin_figures", list(BACK_PIN_FIGURES)))
            frame, fp = _measure(f, actors[f], params, extra["forward_local_override"].get(f), layout,
                                 extra.get("accept_editor_pose", ()))
            sheet, placed, d["metrics"], gp = plan_geometry(f, frame, params, layout)
            d["frame"], d["layout"] = frame, layout
            d["sheet_sha256"] = buffers_sha(sheet, placed)
            nodes, links, term = dataflow_spec(nm["mesh"], placed["pin_local_cm"], params,
                                               placed["pins"][1] if layout == "crown+back" else None)
            out["problems"] += fp + gp + dataflow_problems(nodes, links, term, params)
            _dm, d["dynamic_mesh_probe"], dp = _dynamic_mesh(sheet, placed)   # in memory: no package, no save
            out["problems"] += ["%s|%s" % (x, f) for x in dp]
            _dm = None
        except Exception as exc:  # noqa: BLE001 - DRY reports, never throws mid-way
            out["problems"].append("FIGURE|%s|%s" % (f, exc))
        out["figures_detail"][f] = d
    out["planned"] = {m: planned_packages(m, figs, version, variant) for m in WRITE_MODES}
    out["census_after"] = _census()
    _write(OUT["DRY"], out)
    _require(out["census_after"] == c0, "DRY_DIRTIED|%s" % out["census_after"])
    return {"problems": len(out["problems"]), "out": OUT["DRY"]}


def run_verify(run):
    out, fails = {"run": run}, []
    eal = unreal.EditorAssetLibrary
    if os.path.exists(RECORDS["BUILD"]):
        for ver, v in _read(RECORDS["BUILD"])["versions"].items():
            mi_path = next(iter(v["figures"].values()))["names"]["mi"] if v["figures"] else None
            if mi_path and v.get("mi_look") and eal.does_asset_exist(mi_path):
                want = look_target(_mi_values(unreal.load_asset(SRC_MI)), v["mi_look"])
                got = _mi_values(unreal.load_asset(mi_path))
                if not mi_values_match(want, got):
                    fails.append("MI_LOOK|v%s|%s|want=%s got=%s" % (ver, mi_path, want, got))
            for f, row in v["figures"].items():
                nm = row["names"]
                for k in ("mesh", "dataflow", "cloth", "mi", "master"):
                    if not eal.does_asset_exist(nm[k]):
                        fails.append("MISSING|v%s|%s" % (ver, nm[k]))
                ca = unreal.load_asset(nm["cloth"])
                if ca is not None:
                    got = [_path(m.get_editor_property("material_interface")) for m in ca.get_editor_property("materials")]
                    link = _path(ca.get_editor_property("dataflow_instance").get_editor_property("dataflow_asset"))
                    if got != [nm["mi"]] or link != nm["dataflow"]:
                        fails.append("CA|v%s|%s|%s|%s" % (ver, f, got, link))
    if os.path.exists(RECORDS["APPLY"]):
        rec = _read(RECORDS["APPLY"])
        actors = _figure_actors(rec["figures"])
        for f in rec["figures"]:
            nm = names(f, rec["version"], rec["variant"])
            bad = template_diff(rec["after"][f]["template"], _template_state(nm["bp"])) if "after" in rec else {"after": "missing"}
            if bad:
                fails.append("TEMPLATE|%s|%s" % (f, bad))
            r = _reading(actors[f], f, "editor", *_build_row(f, rec["version"]))
            p = [x for x in pie_problems(f, r, nm["cloth"], nm["mi"]) if not x.startswith("PIE_SIM_DISABLED")]
            fails += [x.replace("PIE_", "EDITOR_", 1) for x in p]
            out[f] = r
    out["fails"] = fails
    _write(OUT["VERIFY"], out)
    _require(not fails, "VERIFY|%s" % fails[:8])
    return {"fails": 0, "out": OUT["VERIFY"]}


# --------------------------------------------------------------------------------------------- main
def main():
    run = datetime.datetime.now().strftime("S3LIVESACK-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        args = _read(ARGS)
        mode, figs, version, params, extra = check_mode(args, {k: os.path.exists(v) for k, v in RECORDS.items()})
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = ed.get_editor_world()
        _require(world is not None and str(world.get_outermost().get_name()) == WORLD, "WRONG_WORLD")
        if mode != "PIE_PROBE":
            _require(ed.get_game_world() is None, "PIE_ACTIVE (never end PIE: refuse instead)")
        unreal.log("S3LIVESACK_START|run=%s|mode=%s|figures=%s|version=%d" % (run, mode, figs, version))
        if mode == "DRY":
            result = run_dry(run, figs, version, params, extra)
        elif mode == "VERIFY":
            result = run_verify(run)
        elif mode == "PIE_PROBE":
            result = run_pie_probe(run, figs, ed)
        elif mode in SIM_MODES:
            result = run_sim(mode, run, figs, extra, ed)
        else:
            c0 = _census()
            _require(c0 == {"content": [], "maps": []}, "DIRTY_BEFORE|" + json.dumps(c0))
            if mode == "BUILD":
                result = run_build(run, figs, version, params, extra, ed)
            elif mode == "APPLY":
                try:
                    result = run_apply(run, figs, version, params, ed)
                except Exception:
                    if os.path.exists(RECORDS["APPLY"]) and not _read(RECORDS["APPLY"]).get("saved"):
                        os.replace(RECORDS["APPLY"], RECORDS["APPLY"] + ".failed-" + run)
                    raise
            else:
                result = run_revert(run, ed)
        unreal.log("S3LIVESACK_%s_OK|run=%s|%s" % (mode, run, json.dumps(result, default=str)))
    except Exception as exc:
        census = {}
        try:
            census = _census()
        except Exception:  # noqa: BLE001
            pass
        unreal.log_error("S3LIVESACK_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            run, mode, str(exc).replace("\n", " "), json.dumps(census),
            "NOTHING SAVED unless an _OK marker printed; if anything is dirty: Don't-Save restart (never reload the "
            "open level)" if mode in WRITE_MODES else "no-write mode"))
        raise


if unreal is not None and os.environ.get("S3LIVESACK_NO_AUTORUN") != "1":
    main()
