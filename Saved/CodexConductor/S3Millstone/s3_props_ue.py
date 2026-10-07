"""S3 props (Granite Millstone + Gary's Rodin props): DRY / IMPORT_MESH / IMPORT_TEX / BUILD_MAT / APPLY / REVERT /
PLACE / UNPLACE, plus the OFFLINE texture prep.

Written 7 Oct 2026 OFFLINE (Unreal and MCP not called).  NEVER RUN IN UNREAL.  Report, tiers and run order:
Docs/Conductor/S3_MILLSTONE_2026-10-07.md.  Runner: s3_props_run.py (one mode per call).

Args: Saved/CodexConductor/S3Millstone/s3_props_args.json
  {"mode": ..., "confirm": "<MODE> S3PROPS", "run": "<id>", "prop": "<Name>", "textures": ["BaseColor", ...] | null,
   "apply": {...APPLY_DEFAULTS overrides...}, "placements_file": "s3_props_placements.json"}

Modes (every write mode: confirm string, no PIE, editor world = the show level, dirty census 0+0 before):
  DRY          read-only.  Root landed?  Pedestal / clam actors, their Sequencer tracks (transform keyed?), the
               pedestal's reveal binding in LS_S3_HangarRise, the floor under the millstone, and the full APPLY plan
               (plus a PLACE plan if the placements file has rows).  Writes s3_props_dry_<run>.json.
  IMPORT_MESH  ONE prop's FBX -> <ASSET_ROOT>/<Name>/SM_<Name> (Interchange override: static mesh only, materials and
               textures OFF, Nanite ON, no LODs, collision off).  Gates: 1 LOD, Nanite on, ONE slot, bounds == manifest
               within tolerance (refuses 100x / rotated / wrong pivot), no stray assets, only that package dirty.
  IMPORT_TEX   ONE prop's textures (args "textures" picks a subset; the millstone BaseColor should go ALONE: 8K).
               BaseColor sRGB TC_DEFAULT; N TC_NORMALMAP sRGB off, green NOT flipped (already DirectX); Roughness
               TC_MASKS sRGB off.  Source PNG size gated from its IHDR before import (millstone BaseColor must be the
               8192 prep output, never the 12288 source).  Read back every setting; folder diff; save; GC.
  BUILD_MAT    create-only shared master M_S3Prop (once; later calls only VERIFY it) + create-only MI_<Name>.
  APPLY        millstone only.  Record FIRST, Backups/PreS3Millstone-<run> (umap + LS_S3_HangarRise), spawn
               "S3 Granite Millstone" (unattached) at the pedestal xy on the measured floor, hidden in game and
               revealed by a COPY of the pedestal's visibility track in LS_S3_HangarRise; hide Clam_Pedastal
               (component visibility off + hidden in game; actor flag recorded); re-seat the clam actors on the stone
               top ONLY if none of them has a transform track (else SKIPPED_KEYED, reported); census-exact save
               (map + rise sequence); read back after the save.  Marker S3MILL_APPLY_OK.
  REVERT       exact restore from the record: remove our binding (by GUID, after proving it resolves to our actor),
               destroy our actor, restore pedestal flags and clam transforms; save; read back.  S3MILL_REVERT_OK.
  PLACE        the other props from a placements JSON (no default placement exists yet); same discipline.
  UNPLACE      exact restore from the PLACE record.

  --- 7 Oct evening extension (PearlClam + live-run lessons; written OFFLINE, never run) ---
  IMPORT_TEX   now ONE texture per call for every prop, and it does NOT save or gate the size: a texture reads
               32x32 in its own import call [meas 7 Oct].  It writes s3_props_tex_pending.json and leaves exactly
               that package dirty.
  VERIFY_TEX   separate call: census must be exactly the pending package; size == source IHDR, settings read
               back; save; record s3_props_import_tex_<...>.json; pending file retired.  While a pending file
               exists every other write mode refuses (TEX_PENDING).  A failed VERIFY_TEX saves nothing: retry it.
  IMPORT_MESH  prop "PearlClam" + "part" Bottom|Lid|Mantle|Pearl (one per call).  Vertex colours REPLACE (read
               back), slot names == manifest, bounds == the Blender bounds with Y FLIPPED (the lid is the
               discriminator; an unflipped import names Y_NOT_FLIPPED), vertex-centroid handedness gate
               (X_MIRRORED), mantle must report vertex colours.
  BUILD_MAT    prop "PearlClam" + "material" Shell|InteriorBottom|InteriorLid|Mantle|Pearl (one MI per call).
               Shell + both interiors are MIs of the shared textured M_S3Prop (v2, 7 Oct 18:16: the untextured blush
               interior is RETIRED).  Create-only masters: M_S3PropBreathe (M_S3Prop + breathing WPO masked by
               VertexColor.R, BreathAmp default 0 = off), PearlClam/M_PearlClam_Pearl (DefaultLit, Fresnel
               warm->cool tint, Glow emissive default 0, breathing WPO with R=1).
  v2 meshes    Bottom/Lid carry CUSTOM NORMALS: imported with normals FROM THE FBX (recompute_normals False,
               tangents MikkTSpace-recomputed; read back), gated after import on the LOD0 build settings.
  CLAM_DRY     read-only: stone, B05/B06 camera poses from LS_DevScene_03, assets, the full CLAM_APPLY plan.
  CLAM_APPLY   4 actors as an assembly on the stone (root "S3 PearlClam" = Bottom; Lid/Mantle/Pearl attached at
               the manifest relative transforms), yaw from the cameras (hinge away) or explicit "yaw_deg"; each
               actor hidden in game + its own copy of the stone's LS_S3_HangarRise reveal (bHidden does not
               propagate to attached actors); the Fab stand-ins hidden at component level, recorded per component.
               Lid NOT keyed: its relative Roll is the hinge.  Marker S3CLAM_APPLY_OK.
  CLAM_REVERT  exact restore from s3_pearlclam_apply_record.json.  Marker S3CLAM_REVERT_OK.
  --- 7 Oct late: Pearl v2 (Gary: "more iridescent, slightly less perfectly spherical"; written OFFLINE, never run) ---
  IMPORT_MESH  prop "PearlClam" part "Pearl_v2" -> NEW SM_PearlClam_Pearl_v2 (v1 kept); bounds gate per the manifest
               v2 entry, same Y-flip logic; normals recomputed off (no custom normals), vertex colours IGNORE.
  IMPORT_TEX   prop "PearlClam" tex_set "Pearl" textures ["Nacre"] (TC_MASKS, sRGB off) -> VERIFY_TEX as usual.
  BUILD_MAT    prop "PearlClam" material "Pearl_v2": create-only M_PearlClam_Pearl_v2 + MI_PearlClam_Pearl_v2
               (cosine-palette thin-film hue shift over the v1 base; same BreathAmp WPO as v1, default 0).
  PEARL_MAT_CHECK  read-only, a LATER call: v2 params read back + the editor log scanned for compile failures.
  PEARL_SWAP   record first, backup, set "S3 PearlClam Pearl" mesh -> v2 and material 0 -> MI v2, relative
               transform kept, map-only save, read back.  Marker S3PEARL_SWAP_OK.  PEARL_UNSWAP restores exactly
               (S3PEARL_UNSWAP_OK).  CLAM_REVERT refuses while a swap record exists.
  --- 7 Oct evening: clam looks (Gary: pearl "subcutaneous shine/glaze", shell "mussel gloss + roughness", mantle
      "oysterlike sliminess and wetness"; written OFFLINE, never run) ---
  BUILD_MAT    prop "PearlClam" material "Pearl_v3" | "Shell_v2" | "Mantle_v2": create-only NEW master + NEW MI (refuses
               if EITHER exists).  Pearl_v3 / Mantle_v2 are MSM_SUBSURFACE (SubsurfaceColor + Opacity pins); Shell_v2
               DefaultLit.  Breathing WPO subgraphs are byte-identical to M_PearlClam_Pearl_v2 / M_S3PropBreathe, and the
               new MI COPIES BreathAmp/BreathPeriod from the MI it replaces (read at build time, recorded).  Connected
               material properties are read back (GetMaterialPropertyInputNode) and the tool fails closed on a mismatch.
  CLAM_LOOK_MAT_CHECK  read-only, a LATER call: "material" = one of the three; params vs the build record + log scan.
  CLAM_LOOK_SWAP   "look" = one of the three, ONE look per call (one record per look; the three touch disjoint slots,
               so each can be A/B'd and unswapped alone).  Record first, backup, set ONLY the look's slot(s) (Pearl_v3:
               Pearl slot 0, mesh stays SM_PearlClam_Pearl_v2 -> needs the PEARL_SWAP record; Shell_v2: Bottom slot 0
               AND Lid slot 0; Mantle_v2: Mantle slot 0), map-only save, read back.  S3CLAMLOOK_SWAP_OK.
  CLAM_LOOK_UNSWAP exact restore of that look (drift since the swap -> refuse).  S3CLAMLOOK_UNSWAP_OK.  CLAM_REVERT,
               PEARL_SWAP and PEARL_UNSWAP refuse while a look record that touches them exists.
  The tool refuses PIE.  In PIE get_editor_world() is None and EditorAssetLibrary.load_asset returns None
  [meas 7 Oct]: every load here is unreal.load_asset, and any future PIE path must keep it so.

OFFLINE (no Unreal):  python s3_props_ue.py PREP_TEXTURES   -> 12288 BaseColor -> Export/8K/ at 8192 (PIL LANCZOS),
                      keeps mode and every colour-space chunk (sRGB/gAMA/iCCP) of the source; writes a record.

Crash rules (memory puss-mcp-python-crashes-the-editor): no UE object at module level, no reloading the open level,
no SequencerTools.get_bound_objects (locate_bound_objects only, run-proven by s3_cast_reveal_apply 1 Oct), no
deleting material nodes, one heavy import per call, GC after imports.
"""
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys

try:
    import unreal
except ModuleNotFoundError:  # offline harness / PREP_TEXTURES
    unreal = None

PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/S3Millstone/"
ARGS = HERE + "s3_props_args.json"
DERIVED = PROJECT + "DerivedAssets/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = PROJECT + "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
RISE_UASSET = PROJECT + "Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset"
CLAM_SEQUENCES = ("/Game/Scenes/LS_Clams", "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03", RISE)
ASSET_ROOT = "/Game/InfinityStage/Dev/Generated/S3Props"          # ALL props incl. the millstone (one table)
MASTER = ASSET_ROOT + "/M_S3Prop"
BACKUP_ROOT = PROJECT + "Backups/PreS3Millstone-"
BACKUP_ROOT_PLACE = PROJECT + "Backups/PreS3PropsPlace-"
APPLY_RECORD = HERE + "s3_millstone_apply_record.json"
PLACE_RECORD = HERE + "s3_props_place_record.json"
PREP_RECORD = HERE + "s3_props_prep_textures_record.json"

ROOT_LABEL = "S3 Hangar Root"
PEDESTAL_LABEL = "Clam_Pedastal"
PEDESTAL_OBJECT = "StaticMeshActor_4"                  # probe_s3_clam_rock.json; cast-reveal binding 2425E62E...
FLOOR_LABELS = ("S3 Shore Ground", "S3 Beach V2 Sand Floor", "S3 Hangar Deck")
BOX_MESHES = ("/Engine/BasicShapes/Cube.Cube",)
ROOT_LANDED_WORLD = (11421.97275, 160000.0, -120.0)   # measured S3SHORE-20261007-181646
GUARD_LOCAL = {"min": [0.0, -1000.0, 100.0], "max": [6000.0, 1000.0, 700.0]}   # landed interior, root-local cm
TAG_ALL = "RigAtmos.S3Props"
FOLDER = "RigAtmos/S3Props"
TOL_CM = 0.05

# role -> (file suffix, compression, srgb, flip_green, sampler)
TEX_ROLES = {
    "BaseColor": ("_BaseColor", "TC_DEFAULT", True, False, "SAMPLERTYPE_COLOR"),
    "N": ("_N", "TC_NORMALMAP", False, False, "SAMPLERTYPE_NORMAL"),
    "Roughness": ("_Roughness", "TC_MASKS", False, False, "SAMPLERTYPE_MASKS"),
}
MASTER_TEX_PARAMS = {"BaseColor": "BaseColor", "Normal": "N", "Roughness": "Roughness"}   # param -> role
MASTER_SCALARS = {"RoughnessMultiplier": 1.0, "RoughnessOverride": -1.0}                  # override < 0 = off
ROUGH_CODE = "return O >= 0.0 ? saturate(O) : saturate(R * M);"

# Coordinator / Gary 7 Oct.  sizes are the Blender clean-reimport [meas there]; tex_src overrides a role's file.
PROPS = {
    "GraniteMillstone": {"size_cm": [143.9, 147.6, 130.0], "min_z_cm": 0.0, "pivot": "base centre",
                         "tex_src": {"BaseColor": "Export/8K/T_GraniteMillstone_BaseColor.png"},
                         "tex_dim": {"BaseColor": 8192, "N": 4096, "Roughness": 4096}, "mi_scalars": {}},
    "HoledStandingStone": {"size_cm": [143.65, 102.73, 330.0], "min_z_cm": -30.0, "pivot": "sand line (30 cm root)",
                           "tex_src": {}, "tex_dim": {"BaseColor": 4096, "N": 4096, "Roughness": 4096},
                           "mi_scalars": {}},
    "HominidRibcage": {"size_cm": [21.34, 22.0, 10.54], "min_z_cm": 0.0, "pivot": "base centre", "tex_src": {},
                       "tex_dim": {"BaseColor": 4096, "N": 4096, "Roughness": 4096}, "mi_scalars": {}},
    # roughness map median 0.40 (manifest) -> x1.95 = 0.78 median, keeps the map's variation (Gary tunes)
    "HominidLegBone": {"size_cm": [28.0, 8.48, 4.16], "min_z_cm": 0.0, "pivot": "base centre", "tex_src": {},
                       "tex_dim": {"BaseColor": 4096, "N": 4096, "Roughness": 4096},
                       "mi_scalars": {"RoughnessMultiplier": 1.95}},
    "HominidJaw": {"size_cm": [7.79, 8.0, 4.21], "min_z_cm": 0.0, "pivot": "base centre", "tex_src": {},
                   "tex_dim": {"BaseColor": 4096, "N": 4096, "Roughness": 4096}, "mi_scalars": {}},
}

APPLY_DEFAULTS = {
    "prop": "GraniteMillstone", "label": "S3 Granite Millstone", "xy_world": None, "yaw_deg": 0.0,
    "burial_cm": 2.0,                 # sink below the measured floor (pivot = base)
    "top_offset_cm": 128.6,           # stone top above its base on the axis (s3_millstone_fbx_measure.json, r<5 cm)
    "floor_radius_cm": 45.0,          # floor samples inside the base's flat band (95 x 83 cm)
    "min_floor_samples": 4, "max_floor_spread_cm": 8.0, "accept_floor_spread": False,
    "clam_labels": ["source_Anim", "Clam_with_Pearl_Clam_with_Pearl_0"], "clam_gap_cm": 0.0,
    "reseat_clams": "auto",           # auto = move only if NO clam actor has a transform track; "never"
    "reveal": "rise_track",           # copy the pedestal's LS_S3_HangarRise visibility track; "none" = always visible
}

# ============================================================================================ PearlClam (7 Oct)
# Source: DerivedAssets/PearlClam/Export/ + PearlClam_manifest.json (Gary approved AS DELIVERED, incl. the mantle slit).
# Bounds/centroids below are BLENDER cm (Z up, front -Y, hinge +Y) [meas: FBX vertices, fbx_top_measure.parse; the
# harness re-reads the FBX and the manifest and asserts both].  UE expectation = Y flipped [inf until IMPORT_MESH].
CLAM = "PearlClam"
CLAM_DIR = DERIVED + "PearlClam/Export/"
CLAM_MANIFEST = CLAM_DIR + "PearlClam_manifest.json"
CLAM_FOLDER = ASSET_ROOT + "/PearlClam"
CLAM_PARTS = {
    "Bottom": {"min_b": [-48.94, -49.864, 0.0], "max_b": [49.17, 49.711, 44.301], "centroid_b": [1.084, -1.692, 17.751],
               "slots": ["M_PearlClam_Shell", "M_PearlClam_InteriorBottom"], "vc": False, "parent": None,
               "custom_normals": True},
    "Lid": {"min_b": [-50.0, -96.445, -0.909], "max_b": [50.0, 2.0, 36.854], "centroid_b": [-1.146, -51.231, 18.819],
            "slots": ["M_PearlClam_Shell", "M_PearlClam_InteriorLid"], "vc": False, "parent": "Bottom",
            "custom_normals": True},
    "Mantle": {"min_b": [-37.878, -36.652, 15.0], "max_b": [37.878, 36.652, 38.903], "centroid_b": [1.232, -0.141, 28.113],
               "slots": ["M_PearlClam_Mantle"], "vc": True, "parent": "Bottom", "custom_normals": False},
    "Pearl": {"min_b": [-9.003, -8.998, 0.0], "max_b": [8.997, 8.992, 18.001], "centroid_b": [0.0, 0.001, 8.979],
              "slots": ["M_PearlClam_Pearl"], "vc": False, "parent": "Bottom", "custom_normals": False},
}
CLAM_PART_ORDER = ("Bottom", "Lid", "Mantle", "Pearl")
CLAM_LABELS = {"Bottom": "S3 PearlClam", "Lid": "S3 PearlClam Lid", "Mantle": "S3 PearlClam Mantle",
               "Pearl": "S3 PearlClam Pearl"}
CENTROID_TOL_CM = 0.6        # x signal is ~1.1 cm (mirror = 2.2 cm apart); stride sample error 0.07 cm [meas offline]
CENTROID_STRIDE_TARGET = 20000
CLAM_TEX = {"Shell": {"BaseColor": 8192, "N": 4096, "Roughness": 4096},
            "Mantle": {"BaseColor": 8192, "N": 8192, "Roughness": 4096},   # mantle v2 (Blender session 7 Oct): 8K BC/N
            # v2: 8K BaseColor + N kept on purpose (finest speckle ~0.5 mm, coordinator 7 Oct)
            "InteriorBottom": {"BaseColor": 8192, "N": 8192, "Roughness": 4096},
            "InteriorLid": {"BaseColor": 8192, "N": 8192, "Roughness": 4096}}
# The ONLY textures allowed above 4096 (anything else at 8K is refused by tex_source_gate, - control in the harness)
ALLOW_8K = {("GraniteMillstone", "BaseColor"), (CLAM, "Shell_BaseColor"), (CLAM, "InteriorBottom_BaseColor"),
            (CLAM, "InteriorBottom_N"), (CLAM, "InteriorLid_BaseColor"), (CLAM, "InteriorLid_N"),
            (CLAM, "Mantle_BaseColor"), (CLAM, "Mantle_N")}
MASTER_BREATHE = ASSET_ROOT + "/M_S3PropBreathe"
PEARL_MASTER = CLAM_FOLDER + "/M_PearlClam_Pearl"
CLAM_MATERIALS = {   # material key -> MI on a master; scalars/vectors are the MI's explicit values (read back)
    "Shell": {"mi": "MI_PearlClam_Shell", "master": MASTER, "tex_set": "Shell", "scalars": {}, "vectors": {}},
    "Mantle": {"mi": "MI_PearlClam_Mantle", "master": MASTER_BREATHE, "tex_set": "Mantle",
               "scalars": {"BreathAmp": 0.0, "BreathPeriod": 5.0}, "vectors": {}},
    # roughness straight from the map (porcelain 0.20, lip 0.40, speckles +0.06): multiplier 1, override off
    "InteriorBottom": {"mi": "MI_PearlClam_InteriorBottom", "master": MASTER, "tex_set": "InteriorBottom",
                       "scalars": {"RoughnessMultiplier": 1.0, "RoughnessOverride": -1.0}, "vectors": {}},
    "InteriorLid": {"mi": "MI_PearlClam_InteriorLid", "master": MASTER, "tex_set": "InteriorLid",
                    "scalars": {"RoughnessMultiplier": 1.0, "RoughnessOverride": -1.0}, "vectors": {}},
    "Pearl": {"mi": "MI_PearlClam_Pearl", "master": PEARL_MASTER, "tex_set": None,
              "scalars": {"Glow": 0.0, "BreathAmp": 0.0, "BreathPeriod": 5.0}, "vectors": {}},
}
SLOT_TO_MATERIAL = {"M_PearlClam_Shell": "Shell", "M_PearlClam_InteriorBottom": "InteriorBottom",
                    "M_PearlClam_InteriorLid": "InteriorLid",
                    "M_PearlClam_Mantle": "Mantle", "M_PearlClam_Pearl": "Pearl"}
SCENE3 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
CLAM_RECORD = HERE + "s3_pearlclam_apply_record.json"
BACKUP_ROOT_CLAM = PROJECT + "Backups/PreS3PearlClam-"
TEX_PENDING = HERE + "s3_props_tex_pending.json"
MILL_MEASURE = HERE + "s3_millstone_fbx_measure.json"
CLAM_DEFAULTS = {
    "yaw_deg": None,                  # None = from the B05/B06 cameras (refuses if unreadable); a number overrides
    "camera_beats": {"B05": 2880, "B06": 3000},   # LS_DevScene_03 display frames (s3_shotlist BEAT_FRAMES; markers)
    "max_camera_off_front_deg": 70.0, # every camera sample must lie within this of the lid's opening direction
    "seat_top_offset_cm": None,       # None = highest stone point under the footprint (s3_millstone_fbx_measure.json)
    "sink_cm": 0.0,                   # push the clam this far into the stone (contact instead of a sub-cm float)
    "reveal": "rise_track", "reveal_targets": "all",   # "all" = one reveal binding per actor (bHidden is per actor)
    "reveal_range_s": None, "reveal_completion_mode": None,   # overrides for the copied section (31 s question)
    "standin_labels": ["source_Anim", "Clam_with_Pearl_Clam_with_Pearl_0"], "hide_standins": True,
    "mobility": "MOVABLE",            # the lid is keyed later; children of a movable root
    "lid_open_deg": 80.0,
}

# ------------------------------------------------------------------ Pearl v2 (Gary 7 Oct: "more iridescent, slightly less
# perfectly spherical").  Kept OUT of CLAM_PARTS / CLAM_MATERIALS / TEX_ROLES on purpose: those tables drive CLAM_APPLY
# and the classic props, which must not change.  Bounds/centroid = BLENDER cm from the FBX vertices [meas offline,
# fbx_top_measure.parse; the harness re-reads the FBX]; UE expectation = Y flipped (same logic as v1) [inf until import].
PEARL_V2 = "Pearl_v2"
CLAM_EXTRA_PARTS = {
    PEARL_V2: {"min_b": [-8.933, -9.0, 0.0], "max_b": [8.933, 9.0, 17.997], "centroid_b": [-0.096, 0.089, 8.906],
               "slots": ["M_PearlClam_Pearl"], "vc": False, "parent": "Bottom", "custom_normals": False,
               "manifest_key": "SM_PearlClam_Pearl_v2", "tris": 65024, "place_at_cm": [0.0, 0.0, 35.65]},
}
EXTRA_TEX_ROLES = {"Nacre": ("_Nacre", "TC_MASKS", False, False, "SAMPLERTYPE_MASKS")}   # linear grey, sample .R
ROLE_SPEC = dict(TEX_ROLES, **EXTRA_TEX_ROLES)
CLAM_TEX["Pearl"] = {"Nacre": 2048}            # T_PearlClam_Pearl_Nacre.png 2048^2 [meas IHDR]; v2 UVs only
NACRE_MEDIAN = 0.44                            # manifest p50 (p5/p95 0.18/0.75) [meas offline, PIL]
PEARL_V2_MASTER = CLAM_FOLDER + "/M_PearlClam_Pearl_v2"
CLAM_EXTRA_MATERIALS = {
    PEARL_V2: {"mi": "MI_PearlClam_Pearl_v2", "master": PEARL_V2_MASTER, "tex_set": "Pearl",
               "scalars": {"Glow": 0.0, "BreathAmp": 0.0, "BreathPeriod": 5.0}, "vectors": {}},   # == v1 MI explicit
}
PEARL_SWAP_RECORD = HERE + "s3_pearl_swap_record.json"
BACKUP_ROOT_PEARL = PROJECT + "Backups/PreS3PearlSwap-"

# ------------------------------------------------------------------ Clam looks (Gary 7 Oct evening).  Same isolation as
# Pearl v2: CLAM_PARTS / CLAM_MATERIALS / SLOT_TO_MATERIAL (CLAM_APPLY) are not touched.  Every new look is a NEW master
# + NEW MI (create-only; no node on an existing asset is edited or deleted).
PEARL_V3, SHELL_V2, MANTLE_V2 = "Pearl_v3", "Shell_v2", "Mantle_v2"
CLAM_LOOK_MATERIALS = (PEARL_V3, SHELL_V2, MANTLE_V2)
PEARL_V3_MASTER = CLAM_FOLDER + "/M_PearlClam_Pearl_v3"
SHELL_V2_MASTER = CLAM_FOLDER + "/M_PearlClam_Shell_v2"
MANTLE_V2_MASTER = CLAM_FOLDER + "/M_PearlClam_Mantle_v2"
BREATH_PARAMS = ("BreathAmp", "BreathPeriod")
CLAM_EXTRA_MATERIALS.update({
    # "breath_from": the MI this look replaces; its BreathAmp/BreathPeriod are COPIED into the new MI at BUILD_MAT so the
    # breathing continues unchanged (mi_scalars_apply ClamBreath may have changed them since the BUILD_MAT defaults).
    PEARL_V3: {"mi": "MI_PearlClam_Pearl_v3", "master": PEARL_V3_MASTER, "tex_set": "Pearl",
               "scalars": {"Glow": 0.1}, "vectors": {}, "breath_from": PEARL_V2, "master_create_only": True},
    SHELL_V2: {"mi": "MI_PearlClam_Shell_v2", "master": SHELL_V2_MASTER, "tex_set": "Shell",
               "scalars": {}, "vectors": {}, "breath_from": None, "master_create_only": True},
    MANTLE_V2: {"mi": "MI_PearlClam_Mantle_v2", "master": MANTLE_V2_MASTER, "tex_set": "Mantle",
                "scalars": {}, "vectors": {}, "breath_from": "Mantle", "master_create_only": True},
})
# look -> {part: slot index}, the slot NAME that index must carry on the live mesh, the material (key) it replaces and
# the mesh (part key) each target must carry.  Slot indices == CLAM_PARTS slots (lint: look_table_problems).
CLAM_LOOKS = {
    PEARL_V3: {"targets": {"Pearl": 0}, "slot_name": "M_PearlClam_Pearl", "from_material": PEARL_V2,
               "mesh_part": {"Pearl": PEARL_V2}, "breathes": True},
    SHELL_V2: {"targets": {"Bottom": 0, "Lid": 0}, "slot_name": "M_PearlClam_Shell", "from_material": "Shell",
               "mesh_part": {"Bottom": "Bottom", "Lid": "Lid"}, "breathes": False},
    MANTLE_V2: {"targets": {"Mantle": 0}, "slot_name": "M_PearlClam_Mantle", "from_material": "Mantle",
                "mesh_part": {"Mantle": "Mantle"}, "breathes": True},
}
BACKUP_ROOT_LOOK = PROJECT + "Backups/PreS3ClamLook-"


def look_record_path(look):
    _req(look in CLAM_LOOKS, "LOOK|%r" % look)
    return HERE + "s3_clam_look_swap_%s.json" % look


def clam_part_row(part):
    _req(part in CLAM_PARTS or part in CLAM_EXTRA_PARTS, "CLAM_PART|%r" % part)
    return CLAM_PARTS.get(part) or CLAM_EXTRA_PARTS[part]


def clam_material_row(key):
    _req(key in CLAM_MATERIALS or key in CLAM_EXTRA_MATERIALS, "CLAM_MATERIAL|%r" % key)
    return CLAM_MATERIALS.get(key) or CLAM_EXTRA_MATERIALS[key]


class PlanError(ValueError):
    pass


def _req(cond, msg):
    if not cond:
        raise PlanError(msg)


# ============================================================================================ pure helpers
def prop_paths(name):
    _req(name in PROPS, "UNKNOWN_PROP|%s" % name)
    d = DERIVED + name + "/Export/"
    folder = ASSET_ROOT + "/" + name
    tex = {}
    for role, (suffix, *_rest) in TEX_ROLES.items():
        src = PROPS[name]["tex_src"].get(role)
        tex[role] = {"file": DERIVED + name + "/" + src if src else d + "T_%s%s.png" % (name, suffix),
                     "asset": folder + "/T_%s%s" % (name, suffix), "name": "T_%s%s" % (name, suffix)}
    return {"fbx": d + "SM_%s.fbx" % name, "manifest": d + "SM_%s_manifest.json" % name, "folder": folder,
            "mesh": folder + "/SM_" + name, "mesh_name": "SM_" + name, "mi": folder + "/MI_" + name,
            "mi_name": "MI_" + name, "tex": tex}


def manifest_expect(man):
    """Size / min z from either manifest layout (millstone: validation.measured_blender_clean_reimport)."""
    v = man.get("validation_blender_clean_reimport") or man.get("validation", {}).get("measured_blender_clean_reimport")
    _req(v and "size_cm" in v and "min_z_cm" in v, "MANIFEST_LAYOUT")
    return [float(x) for x in v["size_cm"]], float(v["min_z_cm"]), int(v.get("material_slots", v.get("slots", 1)))


def expected_bounds(size_cm, min_z):
    sx, sy, sz = size_cm
    return {"min": [-sx / 2.0, -sy / 2.0, min_z], "max": [sx / 2.0, sy / 2.0, min_z + sz]}


def bounds_tol(size_cm):
    """1 cm for the stones; 0.3 cm (or 0.5 % of the axis) for the small bones."""
    return [1.0 if s >= 50.0 else max(0.3, 0.005 * s) for s in size_cm]


def bounds_check(got, size_cm, min_z):
    """got = {"min": [x,y,z], "max": [...]} in UE cm, Z up.  Returns [] or failure strings naming the fault."""
    exp = expected_bounds(size_cm, min_z)
    tol = bounds_tol(size_cm)
    gs = [got["max"][i] - got["min"][i] for i in range(3)]
    f = []
    for i, ax in enumerate("XYZ"):
        if abs(gs[i] - size_cm[i]) > tol[i]:
            f.append("SIZE_%s|got=%.3f|want=%.3f" % (ax, gs[i], size_cm[i]))
        for k in ("min", "max"):
            if abs(got[k][i] - exp[k][i]) > tol[i]:
                f.append("%s_%s|got=%.3f|want=%.3f" % (k.upper(), ax, got[k][i], exp[k][i]))
    if f:
        ratio = [gs[i] / size_cm[i] for i in range(3) if size_cm[i] > 0]
        if all(abs(r - 100.0) < 5.0 for r in ratio) or all(abs(r - 0.01) < 0.0005 for r in ratio):
            f.insert(0, "SCALE_100X|ratio=%s" % [round(r, 4) for r in ratio])
        elif sorted(round(x, 0) for x in gs) == sorted(round(x, 0) for x in size_cm):
            f.insert(0, "AXES_PERMUTED|got_size=%s|want=%s (rotated on import)" % ([round(x, 2) for x in gs], size_cm))
    return f


def png_ihdr(path):
    """(width, height, bit_depth, colour_type) from the PNG header; no PIL (runs inside Unreal)."""
    with open(path, "rb") as f:
        head = f.read(33)
    _req(head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR", "NOT_PNG|%s" % path)
    w, h, depth, ctype = struct.unpack(">IIBB", head[16:26])
    return w, h, depth, ctype


def tex_source_check(name, role):
    p = prop_paths(name)["tex"][role]
    _req(os.path.isfile(p["file"]), "TEX_SOURCE_MISSING|%s" % p["file"])
    w, h, depth, ctype = png_ihdr(p["file"])
    want = PROPS[name]["tex_dim"][role]
    _req(w == h == want, "TEX_DIM|%s|%dx%d|want %d (millstone BaseColor: run PREP_TEXTURES first)" % (p["file"], w, h, want))
    _req(depth == 8, "TEX_DEPTH|%s|%d" % (p["file"], depth))
    return {"file": p["file"], "w": w, "h": h, "depth": depth, "colour_type": ctype}


READ_ONLY_MODES = ("DRY", "CLAM_DRY", "PEARL_MAT_CHECK", "CLAM_LOOK_MAT_CHECK")


def gate_census(census, mode, pending_asset=None):
    """Write modes need 0+0.  VERIFY_TEX needs EXACTLY the pending texture package dirty (nothing else)."""
    clean = census == {"content": [], "maps": []}
    if mode == "VERIFY_TEX":
        _req(pending_asset and census == {"content": [pending_asset], "maps": []},
             "VERIFY_CENSUS|want only %s|got %s" % (pending_asset, json.dumps(census)))
        return False
    if mode not in READ_ONLY_MODES and not clean:
        raise PlanError("DIRTY_BEFORE|%s" % json.dumps(census))
    return clean


MODES = ("DRY", "IMPORT_MESH", "IMPORT_TEX", "VERIFY_TEX", "BUILD_MAT", "APPLY", "REVERT", "PLACE", "UNPLACE",
         "CLAM_DRY", "CLAM_APPLY", "CLAM_REVERT", "PEARL_MAT_CHECK", "PEARL_SWAP", "PEARL_UNSWAP",
         "CLAM_LOOK_MAT_CHECK", "CLAM_LOOK_SWAP", "CLAM_LOOK_UNSWAP")


def check_mode(args, apply_record_exists, place_record_exists, tex_pending_exists=False, clam_record_exists=False,
               pearl_swap_exists=False, look_swaps=()):
    """look_swaps: the looks whose CLAM_LOOK_SWAP record exists on disk (main() lists them)."""
    mode = str(args.get("mode", "DRY")).upper()
    _req(mode in MODES, "MODE|%s" % mode)
    if mode not in READ_ONLY_MODES:
        _req(args.get("confirm") == "%s S3PROPS" % mode, "CONFIRM_MISSING|need %r" % ("%s S3PROPS" % mode))
    if tex_pending_exists:
        _req(mode in READ_ONLY_MODES + ("VERIFY_TEX",), "TEX_PENDING|run VERIFY_TEX first (%s)" % TEX_PENDING)
    _req(not (mode == "VERIFY_TEX" and not tex_pending_exists), "NO_TEX_PENDING")
    if mode in ("IMPORT_MESH", "IMPORT_TEX", "BUILD_MAT"):
        _req(args.get("prop") in PROPS or args.get("prop") == CLAM, "PROP|%r" % args.get("prop"))
        if args.get("prop") == CLAM:
            if mode == "IMPORT_MESH":
                _req(args.get("part") in CLAM_PARTS or args.get("part") in CLAM_EXTRA_PARTS,
                     "CLAM_PART|%r" % args.get("part"))
            if mode == "IMPORT_TEX":
                _req(args.get("tex_set") in CLAM_TEX, "CLAM_TEX_SET|%r" % args.get("tex_set"))
            if mode == "BUILD_MAT":
                _req(args.get("material") in CLAM_MATERIALS or args.get("material") in CLAM_EXTRA_MATERIALS,
                     "CLAM_MATERIAL|%r" % args.get("material"))
    if mode == "IMPORT_TEX":
        roles = args.get("textures")
        _req(isinstance(roles, list) and len(roles) == 1 and roles[0] in ROLE_SPEC,
             "ONE_TEXTURE_PER_CALL|textures=%r (live 7 Oct: multi-file imports go one asset per call)" % roles)
        if args.get("prop") == CLAM:
            _req(roles[0] in CLAM_TEX[args["tex_set"]], "ROLE_NOT_IN_SET|%s|%s" % (args["tex_set"], roles[0]))
        else:
            _req(roles[0] in TEX_ROLES, "ROLE|%s" % roles[0])
    _req(not (mode in ("PEARL_SWAP", "PEARL_UNSWAP") and not clam_record_exists),
         "NO_CLAM_RECORD|the clam must be applied before a pearl swap")
    _req(not (mode == "PEARL_SWAP" and pearl_swap_exists), "PEARL_ALREADY_SWAPPED|" + PEARL_SWAP_RECORD)
    _req(not (mode == "PEARL_UNSWAP" and not pearl_swap_exists), "NO_PEARL_SWAP_RECORD")
    _req(not (mode == "CLAM_REVERT" and pearl_swap_exists), "PEARL_SWAPPED|run PEARL_UNSWAP before CLAM_REVERT")
    look_swaps = sorted(look_swaps or ())
    _req(set(look_swaps) <= set(CLAM_LOOKS), "LOOK_RECORDS_UNKNOWN|%s" % look_swaps)
    _req(not (mode == "CLAM_REVERT" and look_swaps), "LOOK_SWAPPED|%s: run CLAM_LOOK_UNSWAP first" % look_swaps)
    _req(not (mode in ("PEARL_SWAP", "PEARL_UNSWAP") and PEARL_V3 in look_swaps),
         "PEARL_LOOK_SWAPPED|CLAM_LOOK_UNSWAP %s first" % PEARL_V3)
    if mode == "CLAM_LOOK_MAT_CHECK":
        _req(args.get("material") in CLAM_LOOK_MATERIALS, "LOOK_MATERIAL|%r" % args.get("material"))
    if mode in ("CLAM_LOOK_SWAP", "CLAM_LOOK_UNSWAP"):
        look = args.get("look")
        _req(look in CLAM_LOOKS, "LOOK|%r (one of %s)" % (look, list(CLAM_LOOKS)))
        _req(clam_record_exists, "NO_CLAM_RECORD|the clam must be applied before a look swap")
        if mode == "CLAM_LOOK_SWAP":
            _req(look not in look_swaps, "LOOK_ALREADY_SWAPPED|%s" % look)
            _req(not (look == PEARL_V3 and not pearl_swap_exists),
                 "PEARL_V3_NEEDS_V2|the v3 MI goes on SM_PearlClam_Pearl_v2: PEARL_SWAP first")
        else:
            _req(look in look_swaps, "NO_LOOK_SWAP_RECORD|%s" % look)
    _req(not (mode == "APPLY" and apply_record_exists), "ALREADY_APPLIED|" + APPLY_RECORD)
    _req(not (mode == "REVERT" and not apply_record_exists), "NO_APPLY_RECORD")
    _req(not (mode == "PLACE" and place_record_exists), "ALREADY_PLACED|" + PLACE_RECORD)
    _req(not (mode == "UNPLACE" and not place_record_exists), "NO_PLACE_RECORD")
    _req(not (mode in ("CLAM_APPLY", "CLAM_DRY") and not apply_record_exists), "NO_STONE|millstone APPLY record missing")
    _req(not (mode == "CLAM_APPLY" and clam_record_exists), "CLAM_ALREADY_APPLIED|" + CLAM_RECORD)
    _req(not (mode == "CLAM_REVERT" and not clam_record_exists), "NO_CLAM_RECORD")
    return mode


# ------------------------------------------------------------------------------------------- transform maths (UE)
def rot_matrix(rpy):
    r, p, y = [math.radians(float(v)) for v in rpy]
    sr, cr, sp, cp, sy, cy = math.sin(r), math.cos(r), math.sin(p), math.cos(p), math.sin(y), math.cos(y)
    return ((cp * cy, cp * sy, sp),
            (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp),
            (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp))


def tf_point(tf, p):
    m = rot_matrix(tf["rotation"])
    s = [float(p[i]) * float(tf["scale"][i]) for i in range(3)]
    return [float(tf["location"][j]) + sum(s[i] * m[i][j] for i in range(3)) for j in range(3)]


def tf_inv_point(tf, p):
    m = rot_matrix(tf["rotation"])
    v = [float(p[i]) - float(tf["location"][i]) for i in range(3)]
    local = [sum(v[j] * m[i][j] for j in range(3)) for i in range(3)]
    return [local[i] / float(tf["scale"][i]) for i in range(3)]


def near(a, b, tol):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def root_is_landed(root_tf):
    return (near(root_tf["location"], ROOT_LANDED_WORLD, 1.0) and near(root_tf["rotation"], [0, 0, 0], 0.01) and
            near(root_tf["scale"], [1, 1, 1], 1e-4))


def box_local(root_tf, box):
    pts = [tf_inv_point(root_tf, [box["min"][0] if i & 1 else box["max"][0], box["min"][1] if i & 2 else box["max"][1],
                                  box["min"][2] if i & 4 else box["max"][2]]) for i in range(8)]
    return {"min": [min(p[i] for p in pts) for i in range(3)], "max": [max(p[i] for p in pts) for i in range(3)]}


def box_inside(box, guard, tol=TOL_CM):
    return all(box["min"][i] >= guard["min"][i] - tol and box["max"][i] <= guard["max"][i] + tol for i in range(3))


def prop_world_box(name, pivot_world, yaw_deg):
    sx, sy, sz = PROPS[name]["size_cm"]
    mz = PROPS[name]["min_z_cm"]
    c, s = abs(math.cos(math.radians(yaw_deg))), abs(math.sin(math.radians(yaw_deg)))
    hx, hy = (sx * c + sy * s) / 2.0, (sx * s + sy * c) / 2.0
    return {"min": [pivot_world[0] - hx, pivot_world[1] - hy, pivot_world[2] + mz],
            "max": [pivot_world[0] + hx, pivot_world[1] + hy, pivot_world[2] + mz + sz]}


# ------------------------------------------------------------------------------------------- planning (pure)
def floor_pick(floors, min_samples):
    """floors: [{label, visible, kind: mesh|box, samples_z: [...]}] already filtered to the target xy.
    Highest visible floor with enough samples wins (a box floor counts its one top sample)."""
    rows = []
    for f in floors:
        zs = sorted(float(z) for z in f.get("samples_z", []))
        need = 1 if f.get("kind") == "box" else min_samples
        if not f.get("visible") or len(zs) < need:
            continue
        med = zs[len(zs) // 2] if len(zs) % 2 else 0.5 * (zs[len(zs) // 2 - 1] + zs[len(zs) // 2])
        rows.append({"label": f["label"], "kind": f.get("kind"), "n": len(zs), "median": med, "min": zs[0],
                     "max": zs[-1], "spread": zs[-1] - zs[0]})
    _req(rows, "FLOOR_UNMEASURED|no visible floor with >= %d samples under the target" % min_samples)
    return max(rows, key=lambda r: r["median"]), rows


def target_xy(state, a):
    if a.get("xy_world"):
        return [float(a["xy_world"][0]), float(a["xy_world"][1])]
    box = state["pedestal"]["aabb_world"]
    return [0.5 * (box["min"][0] + box["max"][0]), 0.5 * (box["min"][1] + box["max"][1])]


def clam_keyed_verdict(clam):
    """clam["tracks"] = {sequence path: [track class names] | None (binding not found) }; "UNREAD" when the
    sequence could not be read.  Fail closed: anything not provably free of transform tracks counts as keyed."""
    tracks = clam.get("tracks")
    if not isinstance(tracks, dict) or not tracks:
        return "UNCLEAR"
    if any(v == "UNREAD" for v in tracks.values()):
        return "UNCLEAR"
    for v in tracks.values():
        if v and "MovieScene3DTransformTrack" in v:
            return "KEYED"
    return "UNKEYED"


def plan_apply(state, args_apply):
    a = dict(APPLY_DEFAULTS, **(args_apply or {}))
    name = a["prop"]
    _req(name == "GraniteMillstone", "APPLY_IS_MILLSTONE_ONLY|%s (use PLACE)" % name)
    _req(not state.get("temp_actors"), "TEMP_ACTORS_PRESENT|%s" % (state.get("temp_actors") or [])[:5])
    root = state["root"]["world"]
    _req(root_is_landed(root), "ROOT_NOT_LANDED|%s" % json.dumps(root))
    _req(state.get("label_count", {}).get(a["label"], 0) == 0, "LABEL_EXISTS|%s" % a["label"])
    _req(state.get("assets", {}).get("mesh") and state.get("assets", {}).get("mi"), "ASSETS_MISSING|%s" % state.get("assets"))
    ped = state["pedestal"]
    _req(ped["object_name"] == PEDESTAL_OBJECT, "PEDESTAL_OBJECT|%s" % ped["object_name"])
    _req(ped["parent"] is None, "PEDESTAL_PARENT|%s" % ped["parent"])
    xy = target_xy(state, a)
    floor, floors = floor_pick(state["floors"], int(a["min_floor_samples"]))
    if floor["spread"] > float(a["max_floor_spread_cm"]) and not a["accept_floor_spread"]:
        raise PlanError("FLOOR_SPREAD|%.2f cm under the base (%s); set accept_floor_spread" % (floor["spread"], floor["label"]))
    pivot = [xy[0], xy[1], floor["median"] - float(a["burial_cm"])]
    rot = [0.0, 0.0, float(a["yaw_deg"])]
    top_z = pivot[2] + float(a["top_offset_cm"]) - PROPS[name]["min_z_cm"]
    box = prop_world_box(name, pivot, rot[2])
    local = box_local(root, box)
    _req(box_inside(local, GUARD_LOCAL), "GUARD_LOCAL_BOX|%s" % json.dumps(local))

    clams = []
    for c in state["clams"]:
        verdict = clam_keyed_verdict(c)
        clams.append({"label": c["label"], "object_path": c["object_path"], "verdict": verdict, "parent": c["parent"],
                      "before_location": c["location"], "bottom_z": c["aabb_world"]["min"][2],
                      "inside_stone_cm": round(top_z - c["aabb_world"]["min"][2], 2),
                      "top_above_stone_cm": round(c["aabb_world"]["max"][2] - top_z, 2)})
    missing = sorted(set(a["clam_labels"]) - {c["label"] for c in clams})
    _req(not missing, "CLAM_MISSING|%s" % missing)
    any_keyed = any(c["verdict"] != "UNKEYED" for c in clams)
    if a["reseat_clams"] == "never":
        action = "SKIPPED_BY_ARGS"
    elif any_keyed:
        action = "SKIPPED_KEYED"            # coordinator 7 Oct: skip and report, no offset mechanism for the Fab clam
    else:
        action = "MOVE"
    dz = top_z + float(a["clam_gap_cm"]) - min(c["bottom_z"] for c in clams) if clams else 0.0
    for c in clams:
        c["after_location"] = ([c["before_location"][0], c["before_location"][1], c["before_location"][2] + dz]
                               if action == "MOVE" else list(c["before_location"]))
        if action == "MOVE":
            _req(c["parent"] is None, "CLAM_ATTACHED|%s|%s" % (c["label"], c["parent"]))

    reveal = {"mode": a["reveal"]}
    if a["reveal"] == "rise_track":
        src = state.get("rise", {}).get("pedestal_binding")
        _req(src and src.get("resolved") == [ped["object_path"]], "PEDESTAL_REVEAL_BINDING|%s" % (src or {}).get("resolved"))
        _req(src.get("visibility_sections") and len(src["visibility_sections"]) == 1,
             "PEDESTAL_REVEAL_SECTIONS|%s" % src.get("visibility_sections"))
        sec = src["visibility_sections"][0]
        _req(sec.get("keys") and sec.get("completion_mode"), "PEDESTAL_REVEAL_EMPTY")
        reveal.update({"copy_from_guid": src["guid"], "section": sec})
    else:
        _req(a["reveal"] == "none", "REVEAL|%r" % a["reveal"])
    hidden_in_game = a["reveal"] == "rise_track"        # revealed by the copied track, like the cast
    ped_after = {"actor_hidden": True, "comp_visible": False, "comp_hidden_in_game": True}
    return {"prop": name, "label": a["label"], "tags": [TAG_ALL, "S3Props." + name], "folder": FOLDER,
            "mesh": prop_paths(name)["mesh"], "mi": prop_paths(name)["mi"], "mobility": ped["mobility"],
            "location": pivot, "rotation": rot, "actor_hidden_in_game": hidden_in_game, "top_z": top_z,
            "world_box": box, "local_box": local, "floor": floor, "floor_candidates": floors,
            "pedestal": {"label": ped["label"], "object_path": ped["object_path"],
                         "before": {k: ped[k] for k in ("actor_hidden", "comp_visible", "comp_hidden_in_game")},
                         "after": ped_after},
            "clams": {"action": action, "delta_z": round(dz, 3), "rows": clams}, "reveal": reveal, "args": a}


def plan_place(state, placements):
    """Generic PLACE (no pedestal, no clams).  placement: {prop, label, xy_world | xy_root_local, yaw_deg,
    burial_cm (pivot below the measured surface; the standing stone's pivot IS its sand line, so 0 buries its 30 cm
    root), reveal, floor_radius_cm}.  state["floors_by_label"][label] = floor rows sampled at that placement."""
    _req(placements, "NO_PLACEMENTS")
    _req(not state.get("temp_actors"), "TEMP_ACTORS_PRESENT")
    root = state["root"]["world"]
    _req(root_is_landed(root), "ROOT_NOT_LANDED")
    labels = [p["label"] for p in placements]
    _req(len(set(labels)) == len(labels), "DUPLICATE_LABELS")
    out = []
    for p in placements:
        name = p["prop"]
        _req(name in PROPS, "UNKNOWN_PROP|%s" % name)
        _req(state["assets_by_prop"].get(name, {}).get("mesh") and state["assets_by_prop"][name].get("mi"),
             "ASSETS_MISSING|%s" % name)
        _req(state.get("label_count", {}).get(p["label"], 0) == 0, "LABEL_EXISTS|%s" % p["label"])
        xy = place_xy(root, p)
        floor, _rows = floor_pick(state["floors_by_label"][p["label"]], int(p.get("min_floor_samples", 3)))
        pivot = [xy[0], xy[1], floor["median"] - float(p.get("burial_cm", 0.0))]
        rot = [0.0, 0.0, float(p.get("yaw_deg", 0.0))]
        box = prop_world_box(name, pivot, rot[2])
        local = box_local(root, box)
        _req(box_inside(local, GUARD_LOCAL), "GUARD_LOCAL_BOX|%s|%s" % (p["label"], json.dumps(local)))
        reveal = {"mode": p.get("reveal", "rise_track")}
        if reveal["mode"] == "rise_track":
            src = state.get("rise", {}).get("pedestal_binding")
            _req(src and src.get("visibility_sections") and len(src["visibility_sections"]) == 1, "REVEAL_SOURCE")
            reveal.update({"copy_from_guid": src["guid"], "section": src["visibility_sections"][0]})
        out.append({"prop": name, "label": p["label"], "tags": [TAG_ALL, "S3Props." + name], "folder": FOLDER,
                    "mesh": prop_paths(name)["mesh"], "mi": prop_paths(name)["mi"], "mobility": p.get("mobility", "STATIC"),
                    "location": pivot, "rotation": rot, "actor_hidden_in_game": reveal["mode"] == "rise_track",
                    "world_box": box, "local_box": local, "floor": floor, "reveal": reveal,
                    "buried_cm": float(p.get("burial_cm", 0.0)) - PROPS[name]["min_z_cm"]})
    return out


def place_xy(root, p):
    if p.get("xy_world"):
        return [float(p["xy_world"][0]), float(p["xy_world"][1])]
    _req(p.get("xy_root_local"), "PLACEMENT_XY|%s" % p.get("label"))
    w = tf_point(root, [float(p["xy_root_local"][0]), float(p["xy_root_local"][1]), 0.0])
    return [w[0], w[1]]


# ------------------------------------------------------------------------------- ops model (pure; harness-checkable)
def apply_ops(plan):
    """The exact mutations APPLY performs, in order.  The glue executes these; the harness simulates them."""
    ops = [{"op": "spawn", "label": plan["label"], "mesh": plan["mesh"], "mi": plan["mi"], "location": plan["location"],
            "rotation": plan["rotation"], "tags": plan["tags"], "folder": plan["folder"], "mobility": plan["mobility"],
            "actor_hidden_in_game": plan["actor_hidden_in_game"]}]
    if plan["reveal"]["mode"] == "rise_track":
        ops.append({"op": "add_reveal", "label": plan["label"], "section": plan["reveal"]["section"]})
    if "pedestal" in plan:
        ops.append({"op": "set_flags", "object_path": plan["pedestal"]["object_path"], "flags": plan["pedestal"]["after"]})
    for c in plan.get("clams", {}).get("rows", []) if plan.get("clams", {}).get("action") == "MOVE" else []:
        ops.append({"op": "move", "object_path": c["object_path"], "location": c["after_location"]})
    return ops


def revert_ops(record):
    """Inverse of apply_ops from the RECORD (numbers on disk, never live wrappers)."""
    plan = record["plan"]
    ops = []
    for c in plan.get("clams", {}).get("rows", []) if plan.get("clams", {}).get("action") == "MOVE" else []:
        ops.append({"op": "move", "object_path": c["object_path"], "location": c["before_location"]})
    if "pedestal" in plan:
        ops.append({"op": "set_flags", "object_path": plan["pedestal"]["object_path"], "flags": plan["pedestal"]["before"]})
    if record.get("reveal_binding_guid"):
        ops.append({"op": "remove_reveal", "guid": record["reveal_binding_guid"], "actor_path": record["actor_path"]})
    ops.append({"op": "destroy", "actor_path": record["actor_path"], "label": plan["label"]})
    return ops


def simulate(world, ops):
    """Tiny world model: {path: {label, location, flags, ...}} + {"__bindings__": {guid: actor_path}}."""
    w = json.loads(json.dumps(world))
    b = w.setdefault("__bindings__", {})
    for op in ops:
        if op["op"] == "spawn":
            path = "PersistentLevel.NEW_" + op["label"]
            _req(path not in w, "SIM_SPAWN_EXISTS")
            w[path] = {"label": op["label"], "location": list(op["location"]), "rotation": list(op["rotation"]),
                       "flags": {"actor_hidden": op["actor_hidden_in_game"], "comp_visible": True,
                                 "comp_hidden_in_game": False}}
        elif op["op"] == "add_reveal":
            path = "PersistentLevel.NEW_" + op["label"]
            b["GUID_" + op["label"]] = path
        elif op["op"] == "set_flags":
            w[op["object_path"]]["flags"] = dict(op["flags"])
        elif op["op"] == "move":
            w[op["object_path"]]["location"] = list(op["location"])
        elif op["op"] == "remove_reveal":
            _req(b.get(op["guid"]) == op["actor_path"], "SIM_BINDING_MISMATCH")
            del b[op["guid"]]
        elif op["op"] == "destroy":
            _req(op["actor_path"] in w, "SIM_DESTROY_MISSING")
            del w[op["actor_path"]]
    return w


# ------------------------------------------------------------------------------------------- material graph (pure)
def graph_spec():
    nodes = {"BaseColor": ("texture", "BaseColor"), "Normal": ("texture", "N"), "Roughness": ("texture", "Roughness"),
             "RoughnessMultiplier": ("scalar", MASTER_SCALARS["RoughnessMultiplier"]),
             "RoughnessOverride": ("scalar", MASTER_SCALARS["RoughnessOverride"]),
             "RoughCalc": ("custom", (ROUGH_CODE, ["R", "M", "O"], "F1"))}
    edges = [("Roughness", "R", "RoughCalc", "R"), ("RoughnessMultiplier", "", "RoughCalc", "M"),
             ("RoughnessOverride", "", "RoughCalc", "O")]
    props = [("BaseColor", "RGB", "MP_BASE_COLOR"), ("Normal", "RGB", "MP_NORMAL"), ("RoughCalc", "", "MP_ROUGHNESS")]
    return nodes, edges, props


def spec_problems(nodes, edges, props, want_props=None):
    """Generic graph lint: edges name real nodes, every pin fed once, custom pins fed AND used (word match),
    no orphan nodes, each material property set once (and exactly want_props when given)."""
    probs = []
    fed = {}
    for s, _o, d, pin in edges:
        if s not in nodes or d not in nodes:
            probs.append("EDGE_NODE|%s->%s" % (s, d))
        fed.setdefault((d, pin), []).append(s)
    for k, v in fed.items():
        if len(v) != 1:
            probs.append("PIN_FED_TWICE|%s" % (k,))
    for k, (kind, v) in nodes.items():
        if kind == "custom":
            code, ins, _t = v
            for pin in ins:
                if (k, pin) not in fed:
                    probs.append("CUSTOM_PIN_UNFED|%s.%s" % (k, pin))
                if not re.search(r"\b%s\b" % re.escape(pin), code):
                    probs.append("CUSTOM_PIN_UNUSED|%s.%s" % (k, pin))
            for (d, pin) in fed:
                if d == k and pin not in ins:
                    probs.append("CUSTOM_PIN_UNKNOWN|%s.%s" % (k, pin))
    used = {e[0] for e in edges} | {p[0] for p in props}
    probs += ["UNUSED_NODE|%s" % k for k in nodes if k not in used]
    mp = [p[2] for p in props]
    if len(set(mp)) != len(mp):
        probs.append("PROP_SET_TWICE|%s" % mp)
    if want_props is not None and set(mp) != set(want_props):
        probs.append("PROPS|%s" % sorted(mp))
    for p in props:
        if p[0] not in nodes:
            probs.append("PROP_NODE|%s" % p[0])
    return probs


def graph_problems():
    nodes, edges, props = graph_spec()
    probs = spec_problems(nodes, edges, props, {"MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS"})
    if set(MASTER_TEX_PARAMS) != {k for k, (kind, _v) in nodes.items() if kind == "texture"}:
        probs.append("TEX_PARAM_TABLE")
    return probs


# ------------------------------------------------------------------- PearlClam material specs (pure; create-only)
BREATH_CODE = "return float3(0.0, 0.0, A * M * (0.5 - 0.5 * cos(6.2831853 * T / max(P, 0.01))));"
PEARL_BREATH_CODE = "return float3(0.0, 0.0, A * (0.5 - 0.5 * cos(6.2831853 * T / max(P, 0.01))));"
PEARL_COLOR_CODE = "return lerp(B.rgb, B.rgb * lerp(W.rgb, C.rgb, F), saturate(K));"
GLOW_CODE = "return G * GC.rgb;"
MAX_WPO_CM = 5.0     # Material.h:1214-1220 [decl]: clamps WPO per axis AND extends Nanite culling bounds
# v2 thin-film-style hue shift.  Parameters.WorldNormal / Parameters.CameraVector are FMaterialPixelParameters members
# (UE_5.8 Engine/Shaders/Private/MaterialTemplate.ush:427 struct, :437 WorldNormal, :447 CameraVector [decl]); that a
# Custom node may read them in a pixel-only path is [inf] (common practice; proven only by the BUILD_MAT recompile +
# PEARL_MAT_CHECK log scan).  Fresnel is computed here so its exponent is an MI parameter (no Fresnel pin names needed).
IRID_PHASE_CODE = ("float f = pow(1.0 - saturate(dot(normalize(Parameters.WorldNormal), "
                   "normalize(Parameters.CameraVector))), max(E, 0.01)); return f * S + N * K;")
IRID_COLOR_CODE = ("float3 pal = saturate(PA.rgb + PB.rgb * cos(6.2831853 * (PC.rgb * P + PD.rgb))); "
                   "return lerp(B.rgb, pal, saturate(S));")
IRID_GLOW_CODE = "return G * lerp(GC.rgb, I, saturate(K));"
IRID_ROUGH_CODE = "return saturate(R + (N - %.2f) * V);" % NACRE_MEDIAN
# ---- clam looks (7 Oct evening).  Pearl v3: the v2 palette moves from BaseColor into MP_SUBSURFACE_COLOR (the colour
# lives in transmitted light); the surface keeps a faint copy (IridStrength 0.1); an inner glow weighted by
# (1 - fresnel)^K lights the centre from beneath and leaves the rim cool.  Same Parameters.* reads as IRID_PHASE_CODE,
# which compiled in M_PearlClam_Pearl_v2 [meas: s3_pearl_v2_mat_check_S3PROPS-20261007-192645.json, named_errors 0].
INNER_GLOW_CODE = ("float f = pow(1.0 - saturate(dot(normalize(Parameters.WorldNormal), "
                   "normalize(Parameters.CameraVector))), max(E, 0.01)); float w = pow(saturate(1.0 - f), max(K, 0.01)); "
                   "return G * w * lerp(GC.rgb, I, saturate(M));")
# Shell v2: two-level roughness.  The shell roughness map is compressed into 0.84..0.95 (p5..p95 excluding the 1.0
# gutter) [meas offline, PIL, T_PearlClam_Shell_Roughness.png], so a contrast/threshold remap splits it into wet
# periostracum (G) vs chalky worn ridges (H); ridges from the tangent normal (1 - N.z; Z is reconstructed by
# UnpackNormalMap, Engine/Shaders/Private/Common.ush:1698-1711 [decl]) push toward rough.
SHELL_ROUGH_CODE = ("float m = saturate((R - T) * C + 0.5); float ridge = saturate((1.0 - saturate(NM.z)) * K); "
                    "return lerp(G, H, saturate(m + ridge));")
# Mantle v2: wet flesh.  Colour slightly darker + more saturated; roughness pulled toward a wet film, with a slow
# world-space glisten (no new texture).  WorldPosition is an LWC value; that a Custom input demotes it to float is [inf]
# (proven only by BUILD_MAT + CLAM_LOOK_MAT_CHECK).  Precision at ~1.6e5 cm is ~0.01 cm, ample for a 0.15/cm noise.
MANTLE_COLOR_CODE = ("float l = dot(B.rgb, float3(0.2126, 0.7152, 0.0722)); "
                     "return saturate(lerp(float3(l, l, l), B.rgb, 1.0 + S) * (1.0 - saturate(D)));")
MANTLE_ROUGH_CODE = ("float3 p = WP * GS; float t = T * GV; "
                     "float n = 0.5 + 0.25 * (sin(p.x + 1.7 * sin(p.y * 1.3 + t)) + sin(p.y * 1.1 + 1.9 * sin(p.z * 0.9 - 0.8 * t))); "
                     "float r = lerp(R, WR, saturate(WA)); return saturate(r * (1.0 + saturate(GA) * (2.0 * n - 1.0)));")
SUBSURFACE_PROPS = {"MP_SUBSURFACE_COLOR", "MP_OPACITY"}
SHADING_MODELS = ("MSM_DEFAULT_LIT", "MSM_SUBSURFACE")      # never MSM_CLEAR_COAT (no ClearCoat pins in 5.8 Python)


def material_specs():
    """path -> {nodes, edges, props, want_props, tex_params{param: role}, scalars{}, vectors{}, max_wpo, tex_set}."""
    n0, e0, p0 = graph_spec()
    base = {"nodes": n0, "edges": e0, "props": p0, "want_props": {"MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS"},
            "tex_params": dict(MASTER_TEX_PARAMS), "scalars": dict(MASTER_SCALARS), "vectors": {}, "max_wpo": None}
    nb = dict(n0)
    nb.update({"BreathAmp": ("scalar", 0.0), "BreathPeriod": ("scalar", 5.0), "Time": ("time", None),
               "VColor": ("vcolor", None), "BreathWPO": ("custom", (BREATH_CODE, ["M", "A", "T", "P"], "F3"))})
    breathe = {"nodes": nb, "edges": list(e0) + [("VColor", "R", "BreathWPO", "M"), ("BreathAmp", "", "BreathWPO", "A"),
                                                 ("Time", "", "BreathWPO", "T"), ("BreathPeriod", "", "BreathWPO", "P")],
               "props": list(p0) + [("BreathWPO", "", "MP_WORLD_POSITION_OFFSET")],
               "want_props": {"MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS", "MP_WORLD_POSITION_OFFSET"},
               "tex_params": dict(MASTER_TEX_PARAMS),
               "scalars": dict(MASTER_SCALARS, BreathAmp=0.0, BreathPeriod=5.0), "vectors": {}, "max_wpo": MAX_WPO_CM}
    pv = {"BaseColor": [0.86, 0.83, 0.78, 1.0], "WarmTint": [1.0, 0.90, 0.90, 1.0], "CoolTint": [0.88, 0.98, 1.0, 1.0],
          "GlowColor": [1.0, 0.93, 0.88, 1.0]}
    ps = {"TintAmount": 0.6, "Roughness": 0.18, "Specular": 0.55, "Glow": 0.0, "BreathAmp": 0.0, "BreathPeriod": 5.0}
    pn = {k: ("vector", v) for k, v in pv.items()}
    pn.update({k: ("scalar", v) for k, v in ps.items()})
    pn.update({"Fresnel": ("fresnel", 3.0), "Time": ("time", None),
               "PearlColor": ("custom", (PEARL_COLOR_CODE, ["B", "W", "C", "F", "K"], "F3")),
               "GlowEmissive": ("custom", (GLOW_CODE, ["G", "GC"], "F3")),
               "PearlWPO": ("custom", (PEARL_BREATH_CODE, ["A", "T", "P"], "F3"))})
    pearl = {"nodes": pn,
             "edges": [("BaseColor", "", "PearlColor", "B"), ("WarmTint", "", "PearlColor", "W"),
                       ("CoolTint", "", "PearlColor", "C"), ("Fresnel", "", "PearlColor", "F"),
                       ("TintAmount", "", "PearlColor", "K"), ("Glow", "", "GlowEmissive", "G"),
                       ("GlowColor", "", "GlowEmissive", "GC"), ("BreathAmp", "", "PearlWPO", "A"),
                       ("Time", "", "PearlWPO", "T"), ("BreathPeriod", "", "PearlWPO", "P")],
             "props": [("PearlColor", "", "MP_BASE_COLOR"), ("Roughness", "", "MP_ROUGHNESS"),
                       ("Specular", "", "MP_SPECULAR"), ("GlowEmissive", "", "MP_EMISSIVE_COLOR"),
                       ("PearlWPO", "", "MP_WORLD_POSITION_OFFSET")],
             "want_props": {"MP_BASE_COLOR", "MP_ROUGHNESS", "MP_SPECULAR", "MP_EMISSIVE_COLOR",
                            "MP_WORLD_POSITION_OFFSET"},
             "tex_params": {}, "scalars": ps, "vectors": pv, "max_wpo": MAX_WPO_CM}
    # v2: palette a + b cos(2 pi (c phase + d)); a/b chosen so the shift is visible but stays pale (0.56..1.0 per
    # channel); d = (0, 1/3, 2/3) walks the full thin-film hue cycle.  Gary tunes every value on the MI.
    v2v = {"BaseColor": [0.86, 0.83, 0.78, 1.0], "PaletteA": [0.78, 0.78, 0.78, 1.0],
           "PaletteB": [0.22, 0.22, 0.22, 1.0], "PaletteC": [1.0, 1.0, 1.0, 1.0], "PaletteD": [0.0, 0.33, 0.67, 1.0],
           "GlowColor": [1.0, 0.93, 0.88, 1.0]}
    v2s = {"IridStrength": 0.65, "IridScale": 1.2, "NacreScale": 0.5, "FresnelExponent": 1.5, "Roughness": 0.15,
           "RoughnessNacre": 0.08, "Specular": 0.6, "Glow": 0.0, "GlowIrid": 0.35, "BreathAmp": 0.0,
           "BreathPeriod": 5.0}
    vn = {k: ("vector", v) for k, v in v2v.items()}
    vn.update({k: ("scalar", v) for k, v in v2s.items()})
    vn.update({"Nacre": ("texture", "Nacre"), "Time": ("time", None),
               "IridPhase": ("custom", (IRID_PHASE_CODE, ["E", "S", "N", "K"], "F1")),
               "IridColor": ("custom", (IRID_COLOR_CODE, ["B", "PA", "PB", "PC", "PD", "P", "S"], "F3")),
               "GlowEmissive": ("custom", (IRID_GLOW_CODE, ["G", "GC", "I", "K"], "F3")),
               "PearlRough": ("custom", (IRID_ROUGH_CODE, ["R", "N", "V"], "F1")),
               "PearlWPO": ("custom", (PEARL_BREATH_CODE, ["A", "T", "P"], "F3"))})      # == v1 (parity)
    pearl_v2 = {"nodes": vn,
                "edges": [("FresnelExponent", "", "IridPhase", "E"), ("IridScale", "", "IridPhase", "S"),
                          ("Nacre", "R", "IridPhase", "N"), ("NacreScale", "", "IridPhase", "K"),
                          ("BaseColor", "", "IridColor", "B"), ("PaletteA", "", "IridColor", "PA"),
                          ("PaletteB", "", "IridColor", "PB"), ("PaletteC", "", "IridColor", "PC"),
                          ("PaletteD", "", "IridColor", "PD"), ("IridPhase", "", "IridColor", "P"),
                          ("IridStrength", "", "IridColor", "S"),
                          ("Glow", "", "GlowEmissive", "G"), ("GlowColor", "", "GlowEmissive", "GC"),
                          ("IridColor", "", "GlowEmissive", "I"), ("GlowIrid", "", "GlowEmissive", "K"),
                          ("Roughness", "", "PearlRough", "R"), ("Nacre", "R", "PearlRough", "N"),
                          ("RoughnessNacre", "", "PearlRough", "V"),
                          ("BreathAmp", "", "PearlWPO", "A"), ("Time", "", "PearlWPO", "T"),
                          ("BreathPeriod", "", "PearlWPO", "P")],
                "props": [("IridColor", "", "MP_BASE_COLOR"), ("PearlRough", "", "MP_ROUGHNESS"),
                          ("Specular", "", "MP_SPECULAR"), ("GlowEmissive", "", "MP_EMISSIVE_COLOR"),
                          ("PearlWPO", "", "MP_WORLD_POSITION_OFFSET")],
                "want_props": {"MP_BASE_COLOR", "MP_ROUGHNESS", "MP_SPECULAR", "MP_EMISSIVE_COLOR",
                               "MP_WORLD_POSITION_OFFSET"},
                "tex_params": {"Nacre": "Nacre"}, "scalars": v2s, "vectors": v2v, "max_wpo": MAX_WPO_CM}
    out = {MASTER: base, MASTER_BREATHE: breathe, PEARL_MASTER: pearl, PEARL_V2_MASTER: pearl_v2}
    out.update(look_specs(pearl_v2, breathe))
    return out


def _subgraph(spec, sink):
    """(nodes feeding `sink` incl. itself, edges into them) -- used to prove the breathing WPO is copied verbatim."""
    keep, todo = set(), [sink]
    while todo:
        k = todo.pop()
        if k in keep:
            continue
        keep.add(k)
        todo += [e[0] for e in spec["edges"] if e[2] == k]
    return ({k: spec["nodes"][k] for k in sorted(keep)},
            sorted(e for e in spec["edges"] if e[2] in keep))


def look_specs(pearl_v2, breathe):
    """Pearl_v3 / Shell_v2 / Mantle_v2 masters (create-only).  The breathing subgraphs are COPIED from the v2 pearl and
    M_S3PropBreathe specs (not retyped), and the harness asserts node + edge + default equality."""
    pwpo_nodes, pwpo_edges = _subgraph(pearl_v2, "PearlWPO")
    v3v = {"BaseColor": [0.90, 0.87, 0.82, 1.0], "SubsurfaceBase": [0.95, 0.86, 0.80, 1.0],
           "PaletteA": [0.78, 0.78, 0.78, 1.0], "PaletteB": [0.22, 0.22, 0.22, 1.0], "PaletteC": [1.0, 1.0, 1.0, 1.0],
           "PaletteD": [0.0, 0.33, 0.67, 1.0], "GlowColor": [1.0, 0.92, 0.85, 1.0]}
    v3s = {"IridStrength": 0.1, "SubsurfaceIrid": 0.85, "IridScale": 1.2, "NacreScale": 0.5, "FresnelExponent": 1.5,
           "Roughness": 0.1, "RoughnessNacre": 0.05, "Specular": 0.6, "SubsurfaceAmount": 0.6, "Glow": 0.0,
           "GlowFresnelExponent": 2.0, "GlowFalloff": 2.0, "GlowIrid": 0.6,
           "BreathAmp": pearl_v2["scalars"]["BreathAmp"], "BreathPeriod": pearl_v2["scalars"]["BreathPeriod"]}
    pn = {k: ("vector", v) for k, v in v3v.items()}
    pn.update({k: ("scalar", v) for k, v in v3s.items()})
    pn.update(pwpo_nodes)
    pal = [("PaletteA", "PA"), ("PaletteB", "PB"), ("PaletteC", "PC"), ("PaletteD", "PD")]
    pn.update({"Nacre": ("texture", "Nacre"),
               "IridPhase": ("custom", (IRID_PHASE_CODE, ["E", "S", "N", "K"], "F1")),
               "IridSurface": ("custom", (IRID_COLOR_CODE, ["B", "PA", "PB", "PC", "PD", "P", "S"], "F3")),
               "IridSubsurface": ("custom", (IRID_COLOR_CODE, ["B", "PA", "PB", "PC", "PD", "P", "S"], "F3")),
               "InnerGlow": ("custom", (INNER_GLOW_CODE, ["E", "K", "G", "GC", "I", "M"], "F3")),
               "PearlRough": ("custom", (IRID_ROUGH_CODE, ["R", "N", "V"], "F1"))})
    pearl_v3 = {"nodes": pn, "shading_model": "MSM_SUBSURFACE", "prop_readback": True,
                "edges": [("FresnelExponent", "", "IridPhase", "E"), ("IridScale", "", "IridPhase", "S"),
                          ("Nacre", "R", "IridPhase", "N"), ("NacreScale", "", "IridPhase", "K"),
                          ("BaseColor", "", "IridSurface", "B")] + [(s, "", "IridSurface", d) for s, d in pal] +
                         [("IridPhase", "", "IridSurface", "P"), ("IridStrength", "", "IridSurface", "S"),
                          ("SubsurfaceBase", "", "IridSubsurface", "B")] + [(s, "", "IridSubsurface", d) for s, d in pal] +
                         [("IridPhase", "", "IridSubsurface", "P"), ("SubsurfaceIrid", "", "IridSubsurface", "S"),
                          ("GlowFresnelExponent", "", "InnerGlow", "E"), ("GlowFalloff", "", "InnerGlow", "K"),
                          ("Glow", "", "InnerGlow", "G"), ("GlowColor", "", "InnerGlow", "GC"),
                          ("IridSubsurface", "", "InnerGlow", "I"), ("GlowIrid", "", "InnerGlow", "M"),
                          ("Roughness", "", "PearlRough", "R"), ("Nacre", "R", "PearlRough", "N"),
                          ("RoughnessNacre", "", "PearlRough", "V")] + list(pwpo_edges),
                "props": [("IridSurface", "", "MP_BASE_COLOR"), ("PearlRough", "", "MP_ROUGHNESS"),
                          ("Specular", "", "MP_SPECULAR"), ("InnerGlow", "", "MP_EMISSIVE_COLOR"),
                          ("IridSubsurface", "", "MP_SUBSURFACE_COLOR"), ("SubsurfaceAmount", "", "MP_OPACITY"),
                          ("PearlWPO", "", "MP_WORLD_POSITION_OFFSET")],
                "want_props": {"MP_BASE_COLOR", "MP_ROUGHNESS", "MP_SPECULAR", "MP_EMISSIVE_COLOR", "MP_SUBSURFACE_COLOR",
                               "MP_OPACITY", "MP_WORLD_POSITION_OFFSET"},
                "tex_params": {"Nacre": "Nacre"}, "scalars": v3s, "vectors": v3v, "max_wpo": pearl_v2["max_wpo"]}
    # Shell v2 (DefaultLit).  Same three texture parameter names as M_S3Prop, so the MI takes the Shell textures.
    shs = {"GlossRough": 0.12, "RidgeRough": 0.75, "ShellThreshold": 0.90, "ShellContrast": 15.0,
           "RidgeFromNormal": 25.0, "Specular": 0.6}
    sn = {"BaseColor": ("texture", "BaseColor"), "Normal": ("texture", "N"), "Roughness": ("texture", "Roughness")}
    sn.update({k: ("scalar", v) for k, v in shs.items()})
    sn["ShellRough"] = ("custom", (SHELL_ROUGH_CODE, ["R", "NM", "T", "C", "K", "G", "H"], "F1"))
    shell_v2 = {"nodes": sn, "shading_model": "MSM_DEFAULT_LIT", "prop_readback": True,
                "edges": [("Roughness", "R", "ShellRough", "R"), ("Normal", "RGB", "ShellRough", "NM"),
                          ("ShellThreshold", "", "ShellRough", "T"), ("ShellContrast", "", "ShellRough", "C"),
                          ("RidgeFromNormal", "", "ShellRough", "K"), ("GlossRough", "", "ShellRough", "G"),
                          ("RidgeRough", "", "ShellRough", "H")],
                "props": [("BaseColor", "RGB", "MP_BASE_COLOR"), ("Normal", "RGB", "MP_NORMAL"),
                          ("ShellRough", "", "MP_ROUGHNESS"), ("Specular", "", "MP_SPECULAR")],
                "want_props": {"MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS", "MP_SPECULAR"},
                "tex_params": dict(MASTER_TEX_PARAMS), "scalars": shs, "vectors": {}, "max_wpo": None}
    # Mantle v2 (Subsurface flesh).  BreathWPO subgraph copied from M_S3PropBreathe (VertexColor.R mask).
    bwpo_nodes, bwpo_edges = _subgraph(breathe, "BreathWPO")
    mv = {"SubsurfaceColor": [0.72, 0.52, 0.54, 1.0]}
    ms = {"SubsurfaceAmount": 0.5, "Specular": 0.7, "WetRough": 0.05, "WetAmount": 0.75, "GlistenAmount": 0.5,
          "GlistenScale": 0.15, "GlistenSpeed": 0.25, "WetDarken": 0.15, "WetSaturation": 0.2,
          "BreathAmp": breathe["scalars"]["BreathAmp"], "BreathPeriod": breathe["scalars"]["BreathPeriod"]}
    mn = {"BaseColor": ("texture", "BaseColor"), "Normal": ("texture", "N"), "Roughness": ("texture", "Roughness")}
    mn.update({k: ("vector", v) for k, v in mv.items()})
    mn.update({k: ("scalar", v) for k, v in ms.items()})
    mn.update(bwpo_nodes)
    mn.update({"WorldPos": ("worldpos", None),
               "WetColor": ("custom", (MANTLE_COLOR_CODE, ["B", "D", "S"], "F3")),
               "WetRoughCalc": ("custom", (MANTLE_ROUGH_CODE, ["R", "WR", "WA", "GA", "GS", "GV", "WP", "T"], "F1"))})
    mantle_v2 = {"nodes": mn, "shading_model": "MSM_SUBSURFACE", "prop_readback": True,
                 "edges": [("BaseColor", "RGB", "WetColor", "B"), ("WetDarken", "", "WetColor", "D"),
                           ("WetSaturation", "", "WetColor", "S"),
                           ("Roughness", "R", "WetRoughCalc", "R"), ("WetRough", "", "WetRoughCalc", "WR"),
                           ("WetAmount", "", "WetRoughCalc", "WA"), ("GlistenAmount", "", "WetRoughCalc", "GA"),
                           ("GlistenScale", "", "WetRoughCalc", "GS"), ("GlistenSpeed", "", "WetRoughCalc", "GV"),
                           ("WorldPos", "", "WetRoughCalc", "WP"), ("Time", "", "WetRoughCalc", "T")] + list(bwpo_edges),
                 "props": [("WetColor", "", "MP_BASE_COLOR"), ("Normal", "RGB", "MP_NORMAL"),
                           ("WetRoughCalc", "", "MP_ROUGHNESS"), ("Specular", "", "MP_SPECULAR"),
                           ("SubsurfaceColor", "", "MP_SUBSURFACE_COLOR"), ("SubsurfaceAmount", "", "MP_OPACITY"),
                           ("BreathWPO", "", "MP_WORLD_POSITION_OFFSET")],
                 "want_props": {"MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS", "MP_SPECULAR", "MP_SUBSURFACE_COLOR",
                                "MP_OPACITY", "MP_WORLD_POSITION_OFFSET"},
                 "tex_params": dict(MASTER_TEX_PARAMS), "scalars": ms, "vectors": mv, "max_wpo": breathe["max_wpo"]}
    return {PEARL_V3_MASTER: pearl_v3, SHELL_V2_MASTER: shell_v2, MANTLE_V2_MASTER: mantle_v2}


def material_problems(specs=None):
    out = {}
    for path, s in (specs or material_specs()).items():
        p = spec_problems(s["nodes"], s["edges"], s["props"], s["want_props"])
        if set(s["tex_params"]) != {k for k, (kind, _v) in s["nodes"].items() if kind == "texture"}:
            p.append("TEX_PARAM_TABLE")
        if set(s["scalars"]) != {k for k, (kind, _v) in s["nodes"].items() if kind == "scalar"}:
            p.append("SCALAR_TABLE")
        if set(s["vectors"]) != {k for k, (kind, _v) in s["nodes"].items() if kind == "vector"}:
            p.append("VECTOR_TABLE")
        if ("MP_WORLD_POSITION_OFFSET" in s["want_props"]) != (s["max_wpo"] is not None):
            p.append("MAX_WPO_TABLE")
        sm = s.get("shading_model", "MSM_DEFAULT_LIT")
        if sm not in SHADING_MODELS:
            p.append("SHADING_MODEL|%s" % sm)
        if (sm == "MSM_SUBSURFACE" and not SUBSURFACE_PROPS <= set(s["want_props"])) or \
                (sm != "MSM_SUBSURFACE" and SUBSURFACE_PROPS & set(s["want_props"])):
            p.append("SUBSURFACE_PINS|%s|%s" % (sm, sorted(SUBSURFACE_PROPS & set(s["want_props"]))))
        if any("CUSTOM_DATA" in x[2] or "CLEAR" in x[2] for x in s["props"]):
            p.append("CLEARCOAT_PIN")
        if p:
            out[path] = p
    for key, m in list(CLAM_MATERIALS.items()) + list(CLAM_EXTRA_MATERIALS.items()):
        s = (specs or material_specs()).get(m["master"])
        if s is not None and m["tex_set"] and set(s["tex_params"].values()) != set(CLAM_TEX.get(m["tex_set"], {})):
            out.setdefault(key, []).append("TEX_SET_ROLES|%s|%s" % (m["tex_set"], sorted(s["tex_params"].values())))
        if s is None:
            out.setdefault(key, []).append("MASTER_UNKNOWN")
            continue
        for k in m["scalars"]:
            if k not in s["scalars"]:
                out.setdefault(key, []).append("MI_SCALAR_NOT_ON_MASTER|%s" % k)
        for k in m["vectors"]:
            if k not in s["vectors"]:
                out.setdefault(key, []).append("MI_VECTOR_NOT_ON_MASTER|%s" % k)
        if bool(m["tex_set"]) != bool(s["tex_params"]):
            out.setdefault(key, []).append("TEX_SET_VS_MASTER")
    return out


def breath_eval(amp, mask, t, period):
    """Python mirror of BREATH_CODE (Z only)."""
    return amp * mask * (0.5 - 0.5 * math.cos(2.0 * math.pi * t / max(period, 0.01)))


def pearl_color_eval(b, w, c, f, k):
    """Python mirror of PEARL_COLOR_CODE."""
    k = min(1.0, max(0.0, k))
    return [b[i] + (b[i] * (w[i] + (c[i] - w[i]) * f) - b[i]) * k for i in range(3)]


def _sat(x):
    return min(1.0, max(0.0, x))


def irid_phase_eval(ndotv, e, s, n, k):
    """Python mirror of IRID_PHASE_CODE (ndotv = dot(N, V) of unit vectors)."""
    return (1.0 - _sat(ndotv)) ** max(e, 0.01) * s + n * k


def palette_eval(a, b, c, d, t):
    return [_sat(a[i] + b[i] * math.cos(2.0 * math.pi * (c[i] * t + d[i]))) for i in range(3)]


def irid_color_eval(base, a, b, c, d, phase, strength):
    """Python mirror of IRID_COLOR_CODE."""
    pal = palette_eval(a, b, c, d, phase)
    k = _sat(strength)
    return [base[i] + (pal[i] - base[i]) * k for i in range(3)]


def irid_rough_eval(r, n, v):
    """Python mirror of IRID_ROUGH_CODE."""
    return _sat(r + (n - NACRE_MEDIAN) * v)


def inner_glow_eval(ndotv, e, k, g, gc, inner, m):
    """Python mirror of INNER_GLOW_CODE."""
    f = (1.0 - _sat(ndotv)) ** max(e, 0.01)
    w = _sat(1.0 - f) ** max(k, 0.01)
    mm = _sat(m)
    return [g * w * (gc[i] + (inner[i] - gc[i]) * mm) for i in range(3)]


def shell_rough_eval(r, nz, t, c, k, g, h):
    """Python mirror of SHELL_ROUGH_CODE (nz = reconstructed tangent normal z)."""
    m = _sat((r - t) * c + 0.5)
    ridge = _sat((1.0 - _sat(nz)) * k)
    return g + (h - g) * _sat(m + ridge)


def mantle_color_eval(b, d, s):
    """Python mirror of MANTLE_COLOR_CODE."""
    lum = 0.2126 * b[0] + 0.7152 * b[1] + 0.0722 * b[2]
    return [_sat((lum + (b[i] - lum) * (1.0 + s)) * (1.0 - _sat(d))) for i in range(3)]


def glisten_noise_eval(wp, gs, t, gv):
    """The noise term n of MANTLE_ROUGH_CODE, in [0, 1]."""
    p = [x * gs for x in wp]
    tt = t * gv
    return 0.5 + 0.25 * (math.sin(p[0] + 1.7 * math.sin(p[1] * 1.3 + tt)) +
                         math.sin(p[1] * 1.1 + 1.9 * math.sin(p[2] * 0.9 - 0.8 * tt)))


def mantle_rough_eval(r, wr, wa, ga, gs, gv, wp, t):
    """Python mirror of MANTLE_ROUGH_CODE."""
    n = glisten_noise_eval(wp, gs, t, gv)
    base = r + (wr - r) * _sat(wa)
    return _sat(base * (1.0 + _sat(ga) * (2.0 * n - 1.0)))


def look_mi_scalars(key, source_breath=None):
    """The explicit scalars BUILD_MAT writes on a look MI: the row's scalars + (breathing looks) BreathAmp/BreathPeriod
    COPIED from the MI being replaced.  Refuses unreadable / out-of-range source values."""
    m = clam_material_row(key)
    out = dict(m["scalars"])
    if m.get("breath_from"):
        b = source_breath or {}
        _req(sorted(b) == sorted(BREATH_PARAMS), "BREATH_SOURCE_UNREAD|%s|%s" % (m["breath_from"], b))
        amp, per = float(b["BreathAmp"]), float(b["BreathPeriod"])
        _req(math.isfinite(amp) and math.isfinite(per) and 0.0 <= amp <= MAX_WPO_CM and 0.5 <= per <= 60.0,
             "BREATH_SOURCE_RANGE|amp=%s|period=%s" % (amp, per))
        out.update(BreathAmp=amp, BreathPeriod=per)
    else:
        _req(not source_breath, "BREATH_NOT_EXPECTED|%s" % key)
    return out


def look_table_problems():
    """Static lint of CLAM_LOOKS against the clam tables and the look specs."""
    probs = []
    specs = material_specs()
    for look, row in CLAM_LOOKS.items():
        m = CLAM_EXTRA_MATERIALS.get(look)
        if not m or not m.get("master_create_only"):
            probs.append("LOOK_MATERIAL_ROW|%s" % look)
            continue
        s = specs.get(m["master"], {})
        if row["breathes"] != bool(m.get("breath_from")) or row["breathes"] != ("BreathAmp" in s.get("scalars", {})):
            probs.append("LOOK_BREATH_TABLE|%s" % look)
        if m.get("breath_from") and m["breath_from"] != row["from_material"]:
            probs.append("LOOK_BREATH_SOURCE|%s" % look)
        for part, slot in row["targets"].items():
            mesh_row = clam_part_row(row["mesh_part"][part])
            if not (0 <= slot < len(mesh_row["slots"])) or mesh_row["slots"][slot] != row["slot_name"]:
                probs.append("LOOK_SLOT_INDEX|%s|%s|%s" % (look, part, slot))
            if part not in CLAM_LABELS:
                probs.append("LOOK_PART|%s|%s" % (look, part))
        if row["from_material"] == look:
            probs.append("LOOK_REPLACES_ITSELF|%s" % look)
    return probs


# ------------------------------------------------------------------------------- clam look swap (pure; harness-checkable)
def _breath_close(a, b):
    return all(abs(float(a[k]) - float(b[k])) < 1e-4 for k in BREATH_PARAMS)


def clam_look_swap_plan(look, clam_record, live, args_swap=None):
    """live = {"actors": {part: state as _look_actor_live}, "assets": {path: bool}, "mesh_slots": {mesh: [names]},
    "breath": {mi: {BreathAmp, BreathPeriod}}}.  Refuses unless each target actor is exactly the CLAM_APPLY actor,
    carries the expected mesh, the look's slot index names the look's slot, that slot holds the replaced MI as an
    explicit override, no sequence keys a material on it, and (breathing looks) the new MI breathes like the old one."""
    a = dict({"allow_material_tracks": False, "allow_breath_change": False}, **(args_swap or {}))
    _req(look in CLAM_LOOKS, "LOOK|%r" % look)
    row = CLAM_LOOKS[look]
    _req(clam_record.get("applied") and clam_record.get("saved"), "CLAM_RECORD_NOT_APPLIED")
    paths = clam_record.get("actor_paths") or {}
    old_mi, new_mi = clam_mi_path(row["from_material"]), clam_mi_path(look)
    master = clam_material_row(look)["master"]
    _req(live["assets"].get(new_mi) and live["assets"].get(master), "LOOK_ASSETS_MISSING|%s" % live["assets"])
    targets = []
    for part, slot in sorted(row["targets"].items()):
        L = (live.get("actors") or {}).get(part) or {}
        _req(L.get("count") == 1, "LOOK_COUNT|%s|%s" % (part, L.get("count")))
        _req(L["label"] == CLAM_LABELS[part], "LOOK_LABEL|%s|%s" % (part, L["label"]))
        _req(L["object_path"] == paths.get(part), "LOOK_PATH|%s|%s vs record %s" % (part, L["object_path"], paths.get(part)))
        parent = CLAM_PARTS[part]["parent"]
        want_parent = paths.get(parent) if parent else None
        _req(L["parent_path"] == want_parent, "LOOK_PARENT|%s|%s" % (part, L["parent_path"]))
        mesh = clam_mesh_path(row["mesh_part"][part])
        _req(L["mesh"] == mesh, "LOOK_MESH|%s|%s want %s" % (part, L["mesh"], mesh))
        slots = (live.get("mesh_slots") or {}).get(mesh)
        _req(isinstance(slots, list) and isinstance(slot, int) and 0 <= slot < len(slots) and
             slots[slot] == row["slot_name"], "LOOK_SLOT_INDEX|%s|slot %s|mesh slots %s|want %s" % (
                 part, slot, slots, row["slot_name"]))
        _req(len(L["materials"]) == len(slots), "LOOK_SLOT_COUNT|%s|%s" % (part, L["materials"]))
        _req(L["materials"][slot] == old_mi, "LOOK_MATERIAL_NOT_CURRENT|%s|slot %d|%s want %s" % (
            part, slot, L["materials"][slot], old_mi))
        ov = L["override_materials"]
        _req(len(ov) > slot and ov[slot] == old_mi, "LOOK_OVERRIDE|%s|%s (an exact unswap needs an explicit override)" % (
            part, ov))
        _req(new_mi not in L["materials"], "LOOK_ALREADY_ON|%s" % part)
        if row["breathes"]:
            _req(L["wpo_eval"] is True, "LOOK_WPO_EVAL_OFF|%s" % part)
        tracks = (live.get("tracks") or {}).get(part)
        _req(isinstance(tracks, dict) and tracks and not any(v == "UNREAD" for v in tracks.values()),
             "LOOK_TRACKS_UNREAD|%s|%s" % (part, tracks))
        mat_tracks = sorted({t for v in tracks.values() if v for t in v if "Material" in t})
        _req(not mat_tracks or a["allow_material_tracks"], "LOOK_MATERIAL_TRACKS|%s|%s" % (part, mat_tracks))
        before = {k: json.loads(json.dumps(L[k])) for k in PEARL_STATE_KEYS}
        after = json.loads(json.dumps(before))
        after["materials"][slot] = new_mi
        after["override_materials"][slot] = new_mi
        targets.append({"part": part, "slot": slot, "object_path": L["object_path"], "before": before, "after": after,
                        "tracks": tracks, "material_tracks": mat_tracks})
    breath = None
    if row["breathes"]:
        ob, nb = (live.get("breath") or {}).get(old_mi), (live.get("breath") or {}).get(new_mi)
        _req(ob and nb and sorted(ob) == sorted(BREATH_PARAMS) and sorted(nb) == sorted(BREATH_PARAMS),
             "LOOK_BREATH_UNREAD|%s|%s" % (ob, nb))
        _req(_breath_close(ob, nb) or a["allow_breath_change"],
             "LOOK_BREATH_MISMATCH|old %s|new %s (set the new MI or allow_breath_change)" % (ob, nb))
        breath = {"old": ob, "new": nb}
    return {"look": look, "old_mi": old_mi, "new_mi": new_mi, "master": master, "targets": targets, "breath": breath,
            "args": a}


def clam_look_swap_ops(plan):
    return [{"op": "set_slot_material", "part": t["part"], "object_path": t["object_path"], "slot": t["slot"],
             "material": t["after"]["materials"][t["slot"]]} for t in plan["targets"]]


def clam_look_unswap_ops(record):
    ops = []
    for t in record["plan"]["targets"]:
        b = t["before"]
        _req(b["materials"][t["slot"]] == b["override_materials"][t["slot"]], "UNSWAP_OVERRIDE|%s" % t["part"])
        _req(t["after"]["materials"][t["slot"]] == record["plan"]["new_mi"], "UNSWAP_RECORD_AFTER|%s" % t["part"])
        ops.append({"op": "set_slot_material", "part": t["part"], "object_path": t["object_path"], "slot": t["slot"],
                    "material": b["materials"][t["slot"]]})
    return ops


def clam_look_simulate(world, ops):
    """world = {object_path: state}.  set_slot_material sets the slot's material AND its explicit override."""
    w = json.loads(json.dumps(world))
    for op in ops:
        _req(op["op"] == "set_slot_material" and op["object_path"] in w, "SIM_LOOK_TARGET|%s" % op.get("object_path"))
        s = w[op["object_path"]]
        _req(s.get("label") == CLAM_LABELS.get(op["part"]), "SIM_LOOK_LABEL|%s" % s.get("label"))
        _req(0 <= op["slot"] < len(s["materials"]), "SIM_LOOK_SLOT|%s" % op["slot"])
        s["materials"][op["slot"]] = op["material"]
        while len(s["override_materials"]) <= op["slot"]:
            s["override_materials"].append(None)
        s["override_materials"][op["slot"]] = op["material"]
    return w


def clam_look_state_problems(live_actors, targets, which):
    """[] when every target actor equals targets[i][which] ("before" | "after")."""
    probs = []
    for t in targets:
        L = (live_actors or {}).get(t["part"])
        if not L or L.get("count") != 1:
            probs.append("COUNT|%s|%s" % (t["part"], (L or {}).get("count")))
            continue
        probs += ["%s|%s" % (t["part"], p) for p in pearl_state_problems(L, t[which])]
    return probs


def prop_readback_problems(rows, spec, made_paths=None, allow_unavailable=False):
    """rows = _read_props output.  Every spec property must read back to the node the spec wired (exact node path
    when made_paths is known, i.e. inside BUILD_MAT; else the node's parameter name / Custom code), with the spec's
    output pin when one is named.  ALL properties unreadable = the API answered nothing: refused unless
    allow_unavailable (then the connect bools + the MAT_CHECK compile scan are the only proof)."""
    probs = []
    rows = rows or {}
    got = {p[2]: rows.get(p[2]) or {} for p in spec["props"]}
    if all(r.get("path") is None for r in got.values()):
        return [] if allow_unavailable else [
            "PROP_READBACK_UNAVAILABLE|GetMaterialPropertyInputNode answered nothing (%s)" %
            sorted({str(r.get("error")) for r in got.values()})[:2]]
    for s, o, prop in spec["props"]:
        r = got[prop]
        if r.get("path") is None:
            probs.append("PROP_UNCONNECTED|%s" % prop)
            continue
        if made_paths is not None and r["path"] != made_paths.get(s):
            probs.append("PROP_NODE|%s|got %s|want %s" % (prop, r["path"], made_paths.get(s)))
        kind, v = spec["nodes"][s]
        if kind in ("scalar", "vector", "texture") and r.get("param") != s:
            probs.append("PROP_PARAM|%s|got %s|want %s" % (prop, r.get("param"), s))
        if kind == "custom" and (r.get("class") != "MaterialExpressionCustom" or r.get("code") != v[0]):
            probs.append("PROP_CUSTOM|%s|%s" % (prop, r.get("class")))
        # a texture's first output may be unnamed ("RGB" in the editor UI) [inf]: accept "", "None" or "RGB" for it
        ok_out = (r.get("output") in ("", "None", "RGB")) if o == "RGB" else (not o or r.get("output") == o)
        if not ok_out:
            probs.append("PROP_OUTPUT|%s|got %s|want %s" % (prop, r.get("output"), o))
    return probs


# ============================================================================================ PearlClam (pure)
def clam_mesh_path(part):
    return CLAM_FOLDER + "/SM_PearlClam_" + part


def clam_mi_path(material):
    return CLAM_FOLDER + "/" + clam_material_row(material)["mi"]


def tex_target(prop, tex_set, role):
    """One texture's source file / asset / expected size, for the classic props and the clam sets."""
    _req(role in ROLE_SPEC, "ROLE|%r" % role)
    if prop == CLAM:
        _req(tex_set in CLAM_TEX, "CLAM_TEX_SET|%r" % tex_set)
        _req(role in CLAM_TEX[tex_set], "ROLE_NOT_IN_SET|%s|%s" % (tex_set, role))
        name = "T_PearlClam_%s%s" % (tex_set, ROLE_SPEC[role][0])
        return {"file": CLAM_DIR + name + ".png", "asset": CLAM_FOLDER + "/" + name, "name": name,
                "folder": CLAM_FOLDER, "dim": CLAM_TEX[tex_set][role], "label": "%s_%s" % (tex_set, role), "prop": CLAM}
    _req(role in TEX_ROLES, "ROLE|%r" % role)
    p = prop_paths(prop)["tex"][role]
    return dict(p, folder=prop_paths(prop)["folder"], dim=PROPS[prop]["tex_dim"][role], label=role, prop=prop)


def tex_source_gate(t):
    """IHDR gate for a tex_target (runs before an import; inside Unreal too)."""
    _req(os.path.isfile(t["file"]), "TEX_SOURCE_MISSING|%s" % t["file"])
    w, h, depth, ctype = png_ihdr(t["file"])
    _req(w == h == t["dim"], "TEX_DIM|%s|%dx%d|want %d" % (t["file"], w, h, t["dim"]))
    _req(w <= 4096 or (t.get("prop"), t["label"]) in ALLOW_8K, "TEX_8K_NOT_ALLOWED|%s|%s" % (t.get("prop"), t["label"]))
    _req(depth == 8, "TEX_DEPTH|%s|%d" % (t["file"], depth))
    return {"file": t["file"], "w": w, "h": h, "depth": depth, "colour_type": ctype}


# Interchange override as data (sub-object key, property, value).  Header lines [decl]:
#   InterchangeGenericAssetsPipelineSharedSettings.h:94-95 bImportLods, :109-111 VertexColorImportOption,
#   :125-127 bRecomputeNormals ("normals in the imported mesh are ignored and recomputed"), :129-131 bRecomputeTangents,
#   :133-135 bUseMikkTSpace; InterchangeGenericMeshPipeline.h:134 bBuildNanite.
BASE_PIPELINE = [("mat", "import_materials", False), ("tex", "import_textures", False),
                 ("mesh", "import_static_meshes", True), ("mesh", "import_skeletal_meshes", False),
                 ("mesh", "build_nanite", True), ("mesh", "collision", False),
                 ("common", "import_lods", False), ("common", "recompute_normals", False)]
NORMALS_FROM_FILE = [("common", "recompute_normals", False), ("common", "recompute_tangents", True),
                     ("common", "use_mikk_t_space", True)]


def pipeline_wanted(vc_option=None, normals_from_file=False):
    """The exact settings the import writes and reads back.  normals_from_file = keep the FBX's (custom) normals;
    tangents are rebuilt with MikkTSpace (the FBX exports normals, not tangents [meas: LayerElementNormal only])."""
    rows = list(BASE_PIPELINE)
    if normals_from_file:
        drop = {n[1] for n in NORMALS_FROM_FILE}
        rows = [r for r in rows if r[1] not in drop] + list(NORMALS_FROM_FILE)
    if vc_option is not None:
        _req(vc_option in ("IVCIO_REPLACE", "IVCIO_IGNORE"), "VC_OPTION|%r" % vc_option)
        rows.append(("common", "vertex_color_import_option", vc_option))
    keys = [(r[0], r[1]) for r in rows]
    _req(len(keys) == len(set(keys)), "PIPELINE_DUP|%s" % keys)
    return rows


def clam_vc_option(part):
    """Mantle: REPLACE (BreathMask R).  Others IGNORE: the v2 Bottom/Lid FBX carry an undeclared 'LipGrad' colour
    layer [meas: FBX LayerElementColor, 7 Oct 18:15] that no material reads (header: Ignore = drop source colours)."""
    return "IVCIO_REPLACE" if clam_part_row(part)["vc"] else "IVCIO_IGNORE"


def pipeline_problems(rows, part):
    """Gate the planned settings for a clam part (harness +/-): custom-normal parts must keep the file's normals."""
    d = {(r[0], r[1]): r[2] for r in rows}
    probs = []
    if d.get(("common", "recompute_normals")) is not False:
        probs.append("RECOMPUTE_NORMALS_ON|%s" % part)
    if clam_part_row(part)["custom_normals"] and d.get(("common", "use_mikk_t_space")) is not True:
        probs.append("MIKKT_OFF|%s" % part)
    if d.get(("common", "vertex_color_import_option")) != clam_vc_option(part):
        probs.append("VC_OPTION|%s|%s" % (part, d.get(("common", "vertex_color_import_option"))))
    if (d.get(("mesh", "build_nanite")) is not True or d.get(("mat", "import_materials")) is not False or
            d.get(("tex", "import_textures")) is not False):
        probs.append("BASE|%s" % part)
    return probs


def flip_y(v):
    return [float(v[0]), -float(v[1]), float(v[2])]


def clam_expected_ue(part, flipped=True, mirror_x=False):
    """Expected UE bounds / centroid of a part from its Blender numbers.  Default hypothesis: UE = (x, -y, z)."""
    p = clam_part_row(part)
    mn, mx, c = list(p["min_b"]), list(p["max_b"]), list(p["centroid_b"])
    if flipped:
        mn, mx, c = [mn[0], -mx[1], mn[2]], [mx[0], -mn[1], mx[2]], flip_y(c)
    if mirror_x:
        mn, mx, c = [-mx[0], mn[1], mn[2]], [-mn[0], mx[1], mx[2]], [-c[0], c[1], c[2]]
    return {"min": mn, "max": mx, "centroid": c}


def clam_bounds_tol(part):
    p = clam_part_row(part)
    return 0.3 if max(p["max_b"][i] - p["min_b"][i] for i in range(3)) < 50.0 else 1.0


def _box_fits(got, exp, tol):
    return all(abs(got[k][i] - exp[k][i]) <= tol for k in ("min", "max") for i in range(3))


def clam_bounds_check(part, got):
    """[] or failures.  Names Y_NOT_FLIPPED when the import kept Blender's Y (the lid separates the cases; the
    bottom, mantle and pearl are near-symmetric in Y and cannot), and SCALE_100X / SCALE_0.01X."""
    tol = clam_bounds_tol(part)
    exp = clam_expected_ue(part)
    if _box_fits(got, exp, tol):
        return []
    f = ["BOUNDS|%s|got=%s|want=%s" % (part, [[round(x, 3) for x in got[k]] for k in ("min", "max")],
                                        [[round(x, 3) for x in exp[k]] for k in ("min", "max")])]
    if _box_fits(got, clam_expected_ue(part, flipped=False), tol):
        f.insert(0, "Y_NOT_FLIPPED|%s" % part)
    for s, tag in ((100.0, "SCALE_100X"), (0.01, "SCALE_0.01X")):
        if _box_fits(got, {k: [x * s for x in exp[k]] for k in ("min", "max")}, tol * s):
            f.insert(0, "%s|%s" % (tag, part))
    return f


def clam_centroid_check(part, got):
    """Vertex-centroid handedness gate (bounds cannot see an X mirror: the parts are near-symmetric in X)."""
    exp = clam_expected_ue(part)["centroid"]
    if near(got, exp, CENTROID_TOL_CM):
        return []
    f = ["CENTROID|%s|got=%s|want=%s" % (part, [round(x, 3) for x in got], [round(x, 3) for x in exp])]
    if near(got, clam_expected_ue(part, mirror_x=True)["centroid"], CENTROID_TOL_CM):
        f.insert(0, "X_MIRRORED|%s" % part)
    if near(got, clam_expected_ue(part, flipped=False)["centroid"], CENTROID_TOL_CM):
        f.insert(0, "Y_NOT_FLIPPED|%s" % part)
    return f


def normals_gate(part, normals, allow_unreadable=False):
    """After import: a custom-normal part must read recompute_normals False (else the FBX normals were discarded).
    Unreadable settings refuse unless allow_unreadable (then the pipeline read-back is the only evidence)."""
    if not clam_part_row(part)["custom_normals"]:
        return []
    if not normals.get("readable"):
        return [] if allow_unreadable else ["NORMALS_UNREADABLE|%s|%s" % (part, normals.get("error"))]
    return [] if normals.get("recompute_normals") is False else ["NORMALS_RECOMPUTED|%s|%s" % (part, normals)]


def centroid_discriminates(part):
    """True when the expected centroid differs from its X-mirror / Y-unflipped twin by > 2 x tolerance."""
    e = clam_expected_ue(part)["centroid"]
    mx = clam_expected_ue(part, mirror_x=True)["centroid"]
    uy = clam_expected_ue(part, flipped=False)["centroid"]
    return {"x": abs(e[0] - mx[0]) > 2 * CENTROID_TOL_CM, "y": abs(e[1] - uy[1]) > 2 * CENTROID_TOL_CM}


def clam_manifest_problems(man):
    """Table vs PearlClam_manifest.json (the harness also checks table vs FBX vertices)."""
    probs = []
    parts = man.get("parts", {})
    for part, row in CLAM_PARTS.items():
        m = parts.get("SM_PearlClam_" + part)
        if m is None:
            probs.append("MANIFEST_PART_MISSING|%s" % part)
            continue
        if list(m.get("slots", [])) != row["slots"]:
            probs.append("SLOTS|%s|%s" % (part, m.get("slots")))
        b = m.get("bounds_cm") or m.get("bounds_cm_relative_to_pivot")
        if b:
            if not (near(b["min_cm"], row["min_b"], 0.011) and near(b["max_cm"], row["max_b"], 0.011)):
                probs.append("BOUNDS|%s|%s" % (part, b))
        if "size_cm" in m:
            size = [row["max_b"][i] - row["min_b"][i] for i in range(3)]
            if not near(m["size_cm"], size, 0.06):
                probs.append("SIZE|%s|%s|%s" % (part, m["size_cm"], size))
        if "z_cm" in m and not near(m["z_cm"], [row["min_b"][2], row["max_b"][2]], 0.011):
            probs.append("Z|%s" % part)
        if "diameter_cm" in m and abs(m["diameter_cm"] - (row["max_b"][0] - row["min_b"][0])) > 0.02:
            probs.append("DIAMETER|%s" % part)
        if bool(m.get("breathing")) != row["vc"]:
            probs.append("VC_FLAG|%s" % part)
    vr = man.get("validation_reexport", {})
    for part, row in CLAM_PARTS.items():
        if row["custom_normals"]:
            v = vr.get("SM_PearlClam_" + part)
            if not v or v.get("custom_normals") is not True:
                probs.append("CUSTOM_NORMALS_UNDECLARED|%s" % part)
            elif list(v.get("slots", [])) != row["slots"]:
                probs.append("REEXPORT_SLOTS|%s|%s" % (part, v.get("slots")))
            elif not (near(v["min_cm"], row["min_b"], 0.011) and near(v["max_cm"], row["max_b"], 0.011)):
                probs.append("REEXPORT_BOUNDS|%s" % part)
    lid = parts.get("SM_PearlClam_Lid", {})
    if lid.get("hinge_axis_unit_blender") != [1, 0, 0]:
        probs.append("HINGE_AXIS|%s" % lid.get("hinge_axis_unit_blender"))
    return probs


def pearl_v2_manifest_problems(man):
    """Pearl_v2 table vs manifest parts.SM_PearlClam_Pearl_v2 (validation_blender_clean_reimport)."""
    row = CLAM_EXTRA_PARTS[PEARL_V2]
    m = man.get("parts", {}).get(row["manifest_key"])
    if m is None:
        return ["MANIFEST_PART_MISSING|%s" % PEARL_V2]
    probs = []
    v = m.get("validation_blender_clean_reimport") or {}
    size = [row["max_b"][i] - row["min_b"][i] for i in range(3)]
    if not v or not near(v.get("size_cm", []) or [1e9] * 3, size, 0.06):
        probs.append("SIZE|%s|%s" % (v.get("size_cm"), size))
    if abs(float(v.get("min_z_cm", 1e9)) - row["min_b"][2]) > 0.011:
        probs.append("MIN_Z|%s" % v.get("min_z_cm"))
    if not near(v.get("xy_centre_cm", [1e9, 1e9]), [0.5 * (row["min_b"][i] + row["max_b"][i]) for i in (0, 1)], 0.02):
        probs.append("XY_CENTRE|%s" % v.get("xy_centre_cm"))
    if v.get("identity") is not True or v.get("uv") != ["UVMap"]:
        probs.append("IDENTITY_OR_UV|%s|%s" % (v.get("identity"), v.get("uv")))
    if list(v.get("slots", [])) != row["slots"] or list(m.get("slots", [])) != row["slots"]:
        probs.append("SLOTS|%s|%s" % (v.get("slots"), m.get("slots")))
    if int(v.get("tris", -1)) != row["tris"]:
        probs.append("TRIS|%s" % v.get("tris"))
    if not near(m.get("place_at_cm", [1e9] * 3), row["place_at_cm"], 0.011):
        probs.append("PLACE_AT|%s" % m.get("place_at_cm"))
    v1 = man.get("parts", {}).get("SM_PearlClam_Pearl", {}).get("place_at_cm")
    v2 = m.get("place_at_cm")
    if not v1 or not v2 or abs(float(v2[2]) - float(v1[2])) > 0.02:
        probs.append("REST_Z_MOVED|v1=%s|v2=%s (swap keeps the v1 relative transform)" % (v1, m.get("place_at_cm")))
    return probs


def clam_rel_transforms(man):
    """Child relative transforms in the root (Bottom) frame, UE: manifest place_at_cm with Y flipped, no rotation.
    Bottom/Mantle sit at the origin, so they are identical with or without the flip; the lid and pearl are not."""
    out = {}
    for part in CLAM_PART_ORDER:
        at = man["parts"]["SM_PearlClam_" + part]["place_at_cm"]
        out[part] = {"location": flip_y(at), "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
    _req(near(out["Bottom"]["location"], [0, 0, 0], 1e-9), "BOTTOM_NOT_AT_ORIGIN")
    return out


def lid_front_sign(lid_box):
    """+1 when the lid (hinge-relative) reaches toward +Y (expected after the Y flip), -1 toward -Y."""
    return 1 if lid_box["max"][1] > -lid_box["min"][1] else -1


def lid_open_roll(front_sign, deg):
    """UE FRotationMatrix: roll r maps local +Y to (0, cos r, -sin r) [rot_matrix row Y], so the tip at +Y rises
    for r < 0.  Opening = relative Roll of -front_sign * deg."""
    return -float(front_sign) * float(deg)


def tf_chain_point(tfs, p):
    """tfs = [child_rel, ..., root_world]; UE composition (child first)."""
    for tf in tfs:
        p = tf_point(tf, p)
    return p


def box_corners(box):
    return [[box["min"][0] if i & 1 else box["max"][0], box["min"][1] if i & 2 else box["max"][1],
             box["min"][2] if i & 4 else box["max"][2]] for i in range(8)]


def chain_box(tfs, box):
    pts = [tf_chain_point(tfs, c) for c in box_corners(box)]
    return {"min": [min(p[i] for p in pts) for i in range(3)], "max": [max(p[i] for p in pts) for i in range(3)]}


def _tf(loc, rot=(0.0, 0.0, 0.0)):
    return {"location": [float(x) for x in loc], "rotation": [float(x) for x in rot], "scale": [1.0, 1.0, 1.0]}


def lid_tip(lid_box, front_sign):
    """Lid-local front tip: far end along the front, centre in X, mid height."""
    far = lid_box["max"][1] if front_sign > 0 else lid_box["min"][1]
    return [0.5 * (lid_box["min"][0] + lid_box["max"][0]), far, 0.5 * (lid_box["min"][2] + lid_box["max"][2])]


def lid_tip_rise(lid_box, rel_lid, root_tf, roll):
    front = lid_front_sign(lid_box)
    tip = lid_tip(lid_box, front)
    closed = tf_chain_point([_tf(rel_lid["location"]), root_tf], tip)
    opened = tf_chain_point([_tf(rel_lid["location"], (roll, 0.0, 0.0)), root_tf], tip)
    return closed[2], opened[2]


def assembly_problems(boxes, rel):
    """boxes: part -> part-local UE box (live mesh bounds when read, else the table).  Checks the closed assembly in
    the root frame.  The hinge side is opposite the lid's reach."""
    probs = []
    front = lid_front_sign(boxes["Lid"])
    sh = lambda part: {k: [boxes[part][k][i] + rel[part]["location"][i] for i in range(3)] for k in ("min", "max")}  # noqa: E731
    b, l, m, p = sh("Bottom"), sh("Lid"), sh("Mantle"), sh("Pearl")
    back = (lambda bx: bx["min"][1]) if front > 0 else (lambda bx: bx["max"][1])
    fwd = (lambda bx: bx["max"][1]) if front > 0 else (lambda bx: bx["min"][1])
    if abs(back(l) - back(b)) > 1.0:
        probs.append("HINGE_BACK_EDGE|lid=%.2f|bottom=%.2f" % (back(l), back(b)))
    hinge_y = rel["Lid"]["location"][1]
    if abs(hinge_y - back(b)) > 3.0:
        probs.append("HINGE_NOT_AT_BACK|hinge_y=%.2f|bottom_back=%.2f" % (hinge_y, back(b)))
    if abs(fwd(l) - fwd(b)) > 3.0:
        probs.append("LID_FRONT|lid=%.2f|bottom=%.2f" % (fwd(l), fwd(b)))
    if l["min"][0] < b["min"][0] - 1.5 or l["max"][0] > b["max"][0] + 1.5:
        probs.append("LID_X|%s|%s" % ([l["min"][0], l["max"][0]], [b["min"][0], b["max"][0]]))
    if not (b["min"][2] - 0.01 <= rel["Lid"]["location"][2] <= b["max"][2] + 0.01):
        probs.append("HINGE_Z|%.2f" % rel["Lid"]["location"][2])
    for i in (0, 1):
        if m["min"][i] < b["min"][i] - 0.5 or m["max"][i] > b["max"][i] + 0.5:
            probs.append("MANTLE_OUTSIDE_BOTTOM|axis=%d" % i)
    if m["min"][2] < b["min"][2] or m["max"][2] > l["max"][2]:
        probs.append("MANTLE_Z")
    pc = [0.5 * (p["min"][i] + p["max"][i]) for i in range(3)]
    if not all(m["min"][i] <= pc[i] <= m["max"][i] for i in (0, 1)):
        probs.append("PEARL_OFF_MANTLE|%s" % pc[:2])
    if not (m["min"][2] <= p["min"][2] <= m["max"][2]):
        probs.append("PEARL_SEAT_Z|%.2f|mantle %s" % (p["min"][2], [m["min"][2], m["max"][2]]))
    if p["max"][2] >= l["max"][2]:
        probs.append("PEARL_ABOVE_LID|%.2f|%.2f" % (p["max"][2], l["max"][2]))
    return probs


def seat_offset_from_measure(measure, span_cm):
    """Highest stone point (max_h of the radial rings) within the footprint's half-diagonal [meas: FBX height map].
    Resting there means no interpenetration; the float elsewhere is <= that minus the local height."""
    radius = 0.5 * math.hypot(float(span_cm[0]), float(span_cm[1]))
    rows = [r for r in measure["radial_upper_surface_cm"]["rows"] if r[0] <= radius and r[3] is not None]
    _req(rows, "SEAT_ROWS")
    return max(float(r[3]) for r in rows), radius


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def yaw_from_cameras(centre_xy, samples, max_off_deg):
    """samples: [[x, y], ...] camera positions.  Lid opens toward their mean bearing (hinge away).  Clam local front
    is +Y; world front at yaw psi is (-sin psi, cos psi), so psi = bearing - 90."""
    _req(samples, "NO_CAMERA_SAMPLES")
    bear = []
    for x, y in samples:
        dx, dy = float(x) - centre_xy[0], float(y) - centre_xy[1]
        _req(math.hypot(dx, dy) > 50.0, "CAMERA_AT_CLAM|%s" % [x, y])
        bear.append(math.degrees(math.atan2(dy, dx)))
    vx = sum(math.cos(math.radians(b)) for b in bear) / len(bear)
    vy = sum(math.sin(math.radians(b)) for b in bear) / len(bear)
    _req(math.hypot(vx, vy) > 0.3, "CAMERA_BEARINGS_CANCEL|%s" % [round(b, 1) for b in bear])
    theta = math.degrees(math.atan2(vy, vx))
    offs = [abs(_wrap(b - theta)) for b in bear]
    if max(offs) > max_off_deg:
        raise PlanError("CAMERA_SPREAD|bearings=%s|mean=%.1f|max_off=%.1f > %.1f (pass an explicit yaw_deg)" % (
            [round(b, 1) for b in bear], theta, max(offs), max_off_deg))
    return _wrap(theta - 90.0), {"bearings_deg": bear, "mean_bearing_deg": theta, "off_front_deg": offs}


def front_dir(yaw):
    r = math.radians(yaw)
    return [-math.sin(r), math.cos(r)]


def clam_root_location(stone_loc, yaw, fp_centre_ue, seat, sink):
    off = tf_point(_tf([0, 0, 0], (0.0, 0.0, yaw)), [fp_centre_ue[0], fp_centre_ue[1], 0.0])
    return [stone_loc[0] - off[0], stone_loc[1] - off[1], stone_loc[2] + seat - sink]


def standin_hidden(before):
    return {"actor_hidden": before["actor_hidden"],
            "components": {k: {"visible": False, "hidden_in_game": True} for k in before["components"]}}


def plan_clam(state, args_clam, man):
    a = dict(CLAM_DEFAULTS, **(args_clam or {}))
    _req(not state.get("temp_actors"), "TEMP_ACTORS_PRESENT|%s" % (state.get("temp_actors") or [])[:5])
    root_landed = state["root"]["world"]
    _req(root_is_landed(root_landed), "ROOT_NOT_LANDED|%s" % json.dumps(root_landed))
    for part, label in CLAM_LABELS.items():
        _req(state.get("label_count", {}).get(label, 0) == 0, "LABEL_EXISTS|%s" % label)
    need = [clam_mesh_path(p) for p in CLAM_PART_ORDER] + [clam_mi_path(m) for m in CLAM_MATERIALS]
    missing = [p for p in need if not state.get("assets", {}).get(p)]
    _req(not missing, "ASSETS_MISSING|%s" % missing)
    _req(not clam_manifest_problems(man), "MANIFEST|%s" % clam_manifest_problems(man))
    st = state["stone"]
    _req(st.get("found"), "STONE_MISSING|%s" % st.get("object_path"))
    _req(near(st["location"], st["record_location"], TOL_CM), "STONE_MOVED|%s vs record %s" % (
        st["location"], st["record_location"]))
    _req(near(st["rotation"], [0, 0, 0], 0.01), "STONE_ROTATED|%s" % st["rotation"])

    # part boxes (live mesh bounds when DRY/APPLY read them; else the table's UE expectation)
    boxes, slots = {}, {}
    for part in CLAM_PART_ORDER:
        mesh = (state.get("meshes") or {}).get(part)
        if mesh:
            bf = clam_bounds_check(part, mesh["bounds"])
            _req(not bf, "MESH_BOUNDS_DRIFT|%s" % bf)
            boxes[part] = mesh["bounds"]
            slots[part] = list(mesh["slots"])
        else:
            e = clam_expected_ue(part)
            boxes[part] = {"min": e["min"], "max": e["max"]}
            slots[part] = list(CLAM_PARTS[part]["slots"])
        _req(slots[part] == CLAM_PARTS[part]["slots"], "MESH_SLOTS|%s|%s" % (part, slots[part]))
    rel = clam_rel_transforms(man)
    probs = assembly_problems(boxes, rel)
    _req(not probs, "ASSEMBLY|%s" % probs)

    # yaw: cameras unless explicit
    cam = state.get("cameras") or {"ok": False, "error": "NOT_READ"}
    stone_xy = st["location"][:2]
    cam_check = None
    samples = [s["location"][:2] for r in cam.get("rows", []) for s in r["samples"]] if cam.get("ok") else []
    if a["yaw_deg"] is not None:
        yaw, source = _wrap(float(a["yaw_deg"])), "args"
        if samples:
            fd = front_dir(yaw)
            cam_check = []
            for s in samples:
                dx, dy = s[0] - stone_xy[0], s[1] - stone_xy[1]
                cam_check.append(round(math.degrees(math.acos(max(-1.0, min(1.0, (fd[0] * dx + fd[1] * dy) /
                                                                               math.hypot(dx, dy))))), 2))
    else:
        _req(cam.get("ok"), "YAW_UNRESOLVED|cameras unreadable (%s); pass apply_clam.yaw_deg" % cam.get("error"))
        yaw, cam_check = yaw_from_cameras(stone_xy, samples, float(a["max_camera_off_front_deg"]))
        source = "cameras"

    fp = man["measured"]["bottom_footprint"]
    fp_ue = flip_y(list(fp["lowest3cm_centre_cm"]) + [0.0])
    if a["seat_top_offset_cm"] is None:
        seat, seat_r = seat_offset_from_measure(state["measure"], fp["lowest3cm_span_cm"])
    else:
        seat, seat_r = float(a["seat_top_offset_cm"]), None
    root_loc = clam_root_location(st["location"], yaw, fp_ue, seat, float(a["sink_cm"]))
    root_tf = _tf(root_loc, (0.0, 0.0, yaw))
    front = lid_front_sign(boxes["Lid"])
    roll = lid_open_roll(front, a["lid_open_deg"])
    tip_closed, tip_open = lid_tip_rise(boxes["Lid"], rel["Lid"], root_tf, roll)
    _req(tip_open - tip_closed > 50.0, "OPEN_SIGN|tip %.1f -> %.1f" % (tip_closed, tip_open))
    fp_world = tf_point(root_tf, [fp_ue[0], fp_ue[1], 0.0])
    _req(near(fp_world[:2], stone_xy, 0.01), "FOOTPRINT_OFF_AXIS|%s" % fp_world)

    parts = {}
    world_closed, world_open = None, None
    for part in CLAM_PART_ORDER:
        r = rel[part]
        wl = tf_point(root_tf, r["location"]) if part != "Bottom" else list(root_loc)
        mis = {}
        for i, sname in enumerate(slots[part]):
            _req(sname in SLOT_TO_MATERIAL, "SLOT_UNMAPPED|%s|%s" % (part, sname))
            mis[i] = clam_mi_path(SLOT_TO_MATERIAL[sname])
        parts[part] = {"label": CLAM_LABELS[part], "mesh": clam_mesh_path(part), "mis": mis, "slots": slots[part],
                       "parent": None if part == "Bottom" else "Bottom", "rel": r,
                       "world_location": wl, "world_rotation": [0.0, 0.0, yaw],
                       "tags": [TAG_ALL, "S3Props.PearlClam", "S3Props.PearlClam." + part]}
        chain = [root_tf] if part == "Bottom" else [_tf(r["location"]), root_tf]
        bc = chain_box(chain, boxes[part])
        bo = chain_box([_tf(r["location"], (roll, 0.0, 0.0)), root_tf], boxes[part]) if part == "Lid" else bc
        for name, bx in (("closed", bc), ("open", bo)):
            cur = world_closed if name == "closed" else world_open
            cur = bx if cur is None else {"min": [min(cur["min"][i], bx["min"][i]) for i in range(3)],
                                          "max": [max(cur["max"][i], bx["max"][i]) for i in range(3)]}
            if name == "closed":
                world_closed = cur
            else:
                world_open = cur
    for name, bx in (("closed", world_closed), ("open", world_open)):
        loc = box_local(root_landed, bx)
        _req(box_inside(loc, GUARD_LOCAL), "GUARD_LOCAL_BOX|%s|%s" % (name, json.dumps(loc)))

    reveal = {"mode": a["reveal"], "targets": []}
    if a["reveal"] == "rise_track":
        src = st.get("reveal_binding")
        _req(src and src.get("resolved") == [st["object_path"]], "STONE_REVEAL_BINDING|%s" % (src or {}).get("resolved"))
        _req(src.get("visibility_sections") and len(src["visibility_sections"]) == 1,
             "STONE_REVEAL_SECTIONS|%s" % src.get("visibility_sections"))
        sec = dict(src["visibility_sections"][0])
        _req(sec.get("keys") and sec.get("completion_mode"), "STONE_REVEAL_EMPTY")
        overrides = {}
        if a["reveal_range_s"] is not None:
            rr = [float(x) for x in a["reveal_range_s"]]
            _req(len(rr) == 2 and rr[1] > rr[0], "REVEAL_RANGE_ARG|%s" % rr)
            first_key_s = min(k[0] for k in sec["keys"]) / float(sec["fps"])
            last_key_s = max(k[0] for k in sec["keys"]) / float(sec["fps"])
            _req(rr[0] <= first_key_s + 1e-9 and rr[1] > last_key_s,
                 "REVEAL_RANGE_CUTS_KEYS|%s|keys %.3f..%.3f s" % (rr, first_key_s, last_key_s))
            sec["range_s"], overrides["range_s"] = rr, rr
        if a["reveal_completion_mode"] is not None:
            sec["completion_mode"] = overrides["completion_mode"] = str(a["reveal_completion_mode"]).upper()
        _req(a["reveal_targets"] in ("all", "root"), "REVEAL_TARGETS|%r" % a["reveal_targets"])
        reveal.update({"copy_from_guid": src["guid"], "section": sec, "overrides": overrides,
                       "targets": list(CLAM_PART_ORDER) if a["reveal_targets"] == "all" else ["Bottom"]})
    else:
        _req(a["reveal"] == "none", "REVEAL|%r" % a["reveal"])
    hidden_parts = set(reveal["targets"])
    for part in CLAM_PART_ORDER:
        parts[part]["actor_hidden_in_game"] = part in hidden_parts
    if a["reveal"] == "rise_track" and a["reveal_targets"] == "root":
        reveal["warning"] = "children have no reveal: bHidden does not propagate to attached actors [inf]"

    rows = []
    found = {s["label"]: s for s in state.get("standins", [])}
    miss = sorted(set(a["standin_labels"]) - set(found))
    _req(not miss, "STANDIN_MISSING|%s" % miss)
    for label in a["standin_labels"]:
        s = found[label]
        _req(s.get("count", 1) == 1, "STANDIN_COUNT|%s|%s" % (label, s.get("count")))
        _req(s["flags"]["components"], "STANDIN_NO_PRIMITIVES|%s" % label)
        rows.append({"label": label, "object_path": s["object_path"], "class": s.get("class"),
                     "before": s["flags"], "after": standin_hidden(s["flags"]) if a["hide_standins"] else s["flags"]})
    return {"yaw": yaw, "yaw_source": source, "camera_check": cam_check, "cameras": cam,
            "root_location": root_loc, "seat_top_offset_cm": seat, "seat_radius_cm": seat_r,
            "footprint_centre_ue": fp_ue[:2], "footprint_world": fp_world,
            "stone": {k: st[k] for k in ("label", "object_path", "location")},
            "parts": parts, "boxes_local": boxes, "mobility": a["mobility"], "folder": FOLDER,
            "lid": {"front_sign": front, "open_relative_rotation_rpy": [roll, 0.0, 0.0], "tip_closed_z": tip_closed,
                    "tip_open_z": tip_open, "keyed": False},
            "world_box_closed": world_closed, "world_box_open": world_open, "reveal": reveal,
            "standins": {"action": "HIDE" if a["hide_standins"] else "KEEP", "rows": rows}, "args": a}


def clam_apply_ops(plan):
    ops = []
    for part in CLAM_PART_ORDER:
        p = plan["parts"][part]
        ops.append({"op": "spawn", "part": part, "label": p["label"], "mesh": p["mesh"], "mis": p["mis"],
                    "location": p["world_location"], "rotation": p["world_rotation"], "parent": p["parent"],
                    "rel": p["rel"], "tags": p["tags"], "folder": plan["folder"], "mobility": plan["mobility"],
                    "actor_hidden_in_game": p["actor_hidden_in_game"]})
    for part in plan["reveal"]["targets"]:
        ops.append({"op": "add_reveal", "part": part, "section": plan["reveal"]["section"]})
    for r in plan["standins"]["rows"]:
        if r["after"] != r["before"]:
            ops.append({"op": "set_prim_flags", "object_path": r["object_path"], "flags": r["after"]})
    return ops


def clam_revert_ops(record):
    plan = record["plan"]
    ops = []
    for r in plan["standins"]["rows"]:
        if r["after"] != r["before"]:
            ops.append({"op": "set_prim_flags", "object_path": r["object_path"], "flags": r["before"]})
    for part in reversed(CLAM_PART_ORDER):
        g = (record.get("reveal_binding_guids") or {}).get(part)
        if g:
            ops.append({"op": "remove_reveal", "part": part, "guid": g, "actor_path": record["actor_paths"][part]})
    for part in reversed(CLAM_PART_ORDER):          # children first, the root last
        if (record.get("actor_paths") or {}).get(part):
            ops.append({"op": "destroy", "part": part, "actor_path": record["actor_paths"][part],
                        "label": plan["parts"][part]["label"]})
    return ops


def clam_simulate(world, ops):
    """World model: {path: {label, location, rotation, parent, rel, flags}} + __bindings__ {guid: path}."""
    w = json.loads(json.dumps(world))
    b = w.setdefault("__bindings__", {})
    by_part = {}
    for op in ops:
        if op["op"] == "spawn":
            path = "PersistentLevel.NEW_" + op["label"]
            _req(path not in w, "SIM_SPAWN_EXISTS")
            parent = by_part.get(op["parent"]) if op["parent"] else None
            _req(op["parent"] is None or parent, "SIM_PARENT_MISSING|%s" % op["parent"])
            w[path] = {"label": op["label"], "location": list(op["location"]), "rotation": list(op["rotation"]),
                       "parent": parent, "rel": op["rel"]["location"] if parent else None,
                       "hidden": op["actor_hidden_in_game"]}
            by_part[op["part"]] = path
        elif op["op"] == "add_reveal":
            b["GUID_" + op["part"]] = by_part[op["part"]]
        elif op["op"] == "set_prim_flags":
            w[op["object_path"]]["flags"] = json.loads(json.dumps(op["flags"]))
        elif op["op"] == "remove_reveal":
            _req(b.get(op["guid"]) == op["actor_path"], "SIM_BINDING_MISMATCH")
            del b[op["guid"]]
        elif op["op"] == "destroy":
            _req(op["actor_path"] in w, "SIM_DESTROY_MISSING")
            _req(not [k for k, v in w.items() if isinstance(v, dict) and v.get("parent") == op["actor_path"]],
                 "SIM_DESTROY_HAS_CHILDREN|%s" % op["actor_path"])
            del w[op["actor_path"]]
    return w


# ------------------------------------------------------------------------------- Pearl v2 swap (pure; harness-checkable)
PEARL_STATE_KEYS = ("label", "object_path", "parent_path", "mesh", "materials", "override_materials", "rel", "world",
                    "hidden", "wpo_eval")


def pearl_swap_plan(clam_record, live, args_swap=None):
    """live = the placed pearl as read (see _pearl_live).  Refuses unless it is exactly the CLAM_APPLY pearl carrying
    the v1 mesh + v1 MI, both v2 assets exist with the v1 slot, and no sequence keys a material on it."""
    a = dict({"allow_material_tracks": False}, **(args_swap or {}))
    _req(clam_record.get("applied") and clam_record.get("saved"), "CLAM_RECORD_NOT_APPLIED")
    paths = clam_record.get("actor_paths") or {}
    _req(live.get("count") == 1, "PEARL_COUNT|%s" % live.get("count"))
    _req(live["label"] == CLAM_LABELS["Pearl"], "PEARL_LABEL|%s" % live["label"])
    _req(live["object_path"] == paths.get("Pearl"), "PEARL_PATH|%s vs record %s" % (live["object_path"], paths.get("Pearl")))
    _req(live["parent_path"] == paths.get("Bottom"), "PEARL_PARENT|%s" % live["parent_path"])
    v1_mesh, v1_mi = clam_mesh_path("Pearl"), clam_mi_path("Pearl")
    v2_mesh, v2_mi = clam_mesh_path(PEARL_V2), clam_mi_path(PEARL_V2)
    _req(live["mesh"] == v1_mesh, "PEARL_MESH_NOT_V1|%s" % live["mesh"])
    _req(live["materials"] == [v1_mi], "PEARL_MATERIALS_NOT_V1|%s" % live["materials"])
    _req(live["override_materials"] == [v1_mi], "PEARL_OVERRIDES|%s" % live["override_materials"])
    _req(live["assets"].get(v2_mesh) and live["assets"].get(v2_mi), "V2_ASSETS_MISSING|%s" % live["assets"])
    _req(live.get("v2_slots") == CLAM_EXTRA_PARTS[PEARL_V2]["slots"], "V2_SLOTS|%s" % live.get("v2_slots"))
    rec_rel = clam_record["plan"]["parts"]["Pearl"]["rel"]
    _req(near(live["rel"]["location"], rec_rel["location"], TOL_CM) and near(live["rel"]["rotation"], rec_rel["rotation"], 0.01)
         and near(live["rel"]["scale"], [1, 1, 1], 1e-6), "PEARL_REL_DRIFT|%s vs %s" % (live["rel"], rec_rel))
    _req(live["wpo_eval"] is True, "PEARL_WPO_EVAL_OFF")
    tracks = live.get("tracks")
    _req(isinstance(tracks, dict) and tracks and not any(v == "UNREAD" for v in tracks.values()),
         "PEARL_TRACKS_UNREAD|%s" % tracks)
    mat_tracks = sorted({t for v in tracks.values() if v for t in v if "Material" in t})
    _req(not mat_tracks or a["allow_material_tracks"], "PEARL_MATERIAL_TRACKS|%s (a keyed MI would be orphaned)" % mat_tracks)
    before = {k: json.loads(json.dumps(live[k])) for k in PEARL_STATE_KEYS}
    after = dict(json.loads(json.dumps(before)), mesh=v2_mesh, materials=[v2_mi], override_materials=[v2_mi])
    return {"object_path": live["object_path"], "before": before, "after": after, "tracks": tracks,
            "material_tracks": mat_tracks, "args": a,
            "note": "relative transform kept (v2 manifest rest z 35.65 vs v1 35.64: +0.01 cm not applied)"}


def pearl_swap_ops(plan):
    return [{"op": "set_mesh_material", "object_path": plan["object_path"], "mesh": plan["after"]["mesh"],
             "material0": plan["after"]["materials"][0]}]


def pearl_unswap_ops(record):
    p = record["plan"]
    _req(len(p["before"]["materials"]) == 1, "UNSWAP_SLOTS|%s" % p["before"]["materials"])
    return [{"op": "set_mesh_material", "object_path": p["object_path"], "mesh": p["before"]["mesh"],
             "material0": p["before"]["materials"][0]}]


def pearl_state_problems(live, want):
    """[] when the live pearl equals the wanted state (paths exact, transforms within TOL_CM / 0.01 deg)."""
    probs = []
    for k in ("label", "object_path", "parent_path", "mesh", "materials", "override_materials", "hidden", "wpo_eval"):
        if live.get(k) != want.get(k):
            probs.append("%s|got=%s|want=%s" % (k.upper(), live.get(k), want.get(k)))
    for k, tol in (("location", TOL_CM), ("rotation", 0.01), ("scale", 1e-6)):
        for frame in ("rel", "world"):
            g, w = live[frame][k], want[frame][k]
            if k == "rotation":
                g, w = [_wrap(x) for x in g], [_wrap(x) for x in w]
            if not near(g, w, tol):
                probs.append("%s_%s|got=%s|want=%s" % (frame.upper(), k.upper(), live[frame][k], want[frame][k]))
    return probs


def pearl_simulate(world, ops):
    w = json.loads(json.dumps(world))
    for op in ops:
        _req(op["op"] == "set_mesh_material" and op["object_path"] in w, "SIM_PEARL_TARGET|%s" % op.get("object_path"))
        w[op["object_path"]].update(mesh=op["mesh"], materials=[op["material0"]], override_materials=[op["material0"]])
    return w


def compile_log_problems(lines, names):
    """Log lines naming one of `names` that report a compile failure / error (our own S3PROPS_ markers excluded),
    plus unattributed 'Failed to compile' lines (reported, not gated: [inf] UE names the material on that line)."""
    named, unattributed = [], []
    for ln in lines:
        if "S3PROPS_" in ln or "S3PEARL_" in ln or "S3CLAMLOOK_" in ln:
            continue
        bad = "Failed to compile" in ln or re.search(r"\berror\b", ln, re.I) is not None
        if not bad:
            continue
        if any(n in ln for n in names):
            named.append(ln.strip()[:400])
        elif "Failed to compile" in ln:
            unattributed.append(ln.strip()[:400])
    return named, unattributed


def rough_eval(r, mult, override):
    """Python mirror of ROUGH_CODE (harness: override off/on, clamp)."""
    sat = lambda x: min(1.0, max(0.0, x))  # noqa: E731
    return sat(override) if override >= 0.0 else sat(r * mult)


# ============================================================================================ OFFLINE: texture prep
def prep_texture(src, dst, size=8192):
    """Downscale with PIL LANCZOS; keep mode and the colour-space chunks (sRGB intent / gAMA / iCCP) of the source.
    Returns a record; raises on any mismatch (read back from the written file)."""
    from PIL import Image, PngImagePlugin
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(src)
    info = dict(im.info)
    mode = im.mode
    im.load()
    out = im.resize((size, size), Image.LANCZOS)
    _req(out.mode == mode, "MODE_CHANGED|%s->%s" % (mode, out.mode))
    pi = PngImagePlugin.PngInfo()
    if "srgb" in info:
        pi.add(b"sRGB", bytes([int(info["srgb"])]))
    if "gamma" in info:
        pi.add(b"gAMA", struct.pack(">I", int(round(float(info["gamma"]) * 100000))))
    kw = {"pnginfo": pi}
    if info.get("icc_profile"):
        kw["icc_profile"] = info["icc_profile"]
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".tmp.png"
    out.save(tmp, format="PNG", **kw)
    chk = Image.open(tmp)
    got = dict(chk.info)
    problems = []
    if chk.size != (size, size):
        problems.append("SIZE|%s" % (chk.size,))
    if chk.mode != mode:
        problems.append("MODE|%s" % chk.mode)
    for k in ("srgb", "icc_profile"):
        if info.get(k) != got.get(k):
            problems.append("CHUNK_%s|src=%r|dst=%r" % (k, info.get(k), got.get(k)))
    if ("gamma" in info) != ("gamma" in got) or ("gamma" in info and abs(info["gamma"] - got["gamma"]) > 1e-5):
        problems.append("CHUNK_gamma|src=%r|dst=%r" % (info.get("gamma"), got.get("gamma")))
    chk.close()
    if problems:
        os.remove(tmp)
        raise PlanError("PREP_READBACK|" + ";".join(problems))
    os.replace(tmp, dst)
    return {"src": src, "dst": dst, "src_size": list(im.size), "dst_size": [size, size], "mode": mode,
            "chunks": {k: (info.get(k) if k != "icc_profile" else bool(info.get(k))) for k in ("srgb", "gamma", "icc_profile")},
            "dst_sha256": sha256_file(dst), "dst_bytes": os.path.getsize(dst)}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_prep_textures():
    name = "GraniteMillstone"
    src = DERIVED + name + "/Export/T_GraniteMillstone_BaseColor.png"
    dst = prop_paths(name)["tex"]["BaseColor"]["file"]
    _req(not os.path.exists(dst), "PREP_DST_EXISTS|%s (delete it deliberately to redo)" % dst)
    w, h, _d, _c = png_ihdr(src)
    _req((w, h) == (12288, 12288), "PREP_SRC_DIM|%dx%d" % (w, h))
    rec = prep_texture(src, dst, 8192)
    rec["utc"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(PREP_RECORD, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    return rec


# ============================================================================================ Unreal glue
def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())


def _v(x):
    return [float(x.x), float(x.y), float(x.z)]


def _r(rot):
    return [float(rot.roll), float(rot.pitch), float(rot.yaw)]


def _box(actor):
    o, e = actor.get_actor_bounds(False)
    return {"min": [o.x - e.x, o.y - e.y, o.z - e.z], "max": [o.x + e.x, o.y + e.y, o.z + e.z]}


def _world_tf(actor):
    return {"location": _v(actor.get_actor_location()), "rotation": _r(actor.get_actor_rotation()),
            "scale": _v(actor.get_actor_scale3d())}


def _path(o):
    return str(o.get_path_name()) if o is not None else None


def _enum_name(v):
    return str(getattr(v, "name", v)).split(".")[-1].split(":")[0].strip("<> ").upper()


def _guid(g):
    return str(unreal.GuidLibrary.conv_guid_to_string(g))


def _index(world):
    out = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):   # sees transient actors too
        out.setdefault(str(a.get_actor_label()), []).append(a)
    return out


def _one(index, label):
    rows = index.get(label, [])
    _req(len(rows) == 1, "COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def _by_path(world, path):
    rows = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if _path(a) == path]
    return rows[0] if len(rows) == 1 else None


def _smc(actor):
    comps = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    _req(len(comps) == 1, "SMC_COUNT|%s|%d" % (actor.get_actor_label(), len(comps)))
    return comps[0]


def _flags(actor):
    c = _smc(actor)
    return {"actor_hidden": bool(actor.get_editor_property("hidden")),       # Actor.h bHidden (memory: no is_hidden())
            "comp_visible": bool(c.is_visible()), "comp_hidden_in_game": bool(c.get_editor_property("hidden_in_game"))}


def _set_flags(actor, flags):
    actor.modify()
    c = _smc(actor)
    c.modify()
    actor.set_actor_hidden_in_game(bool(flags["actor_hidden"]))
    c.set_visibility(bool(flags["comp_visible"]), False)
    c.set_hidden_in_game(bool(flags["comp_hidden_in_game"]), False)
    got = _flags(actor)
    _req(got == {k: bool(v) for k, v in flags.items()}, "FLAGS_READBACK|%s|%s" % (actor.get_actor_label(), got))


def _sequence_tracks(seq, world, actor):
    """Track class names on bindings that resolve to `actor` (locate_bound_objects) OR whose display name equals its
    label / object name (fallback: sub-sequence possessables may not resolve outside their parent).  None = no
    binding found; "UNREAD" = the sequence could not be read."""
    if seq is None:
        return "UNREAD"
    want, label, oname = _path(actor), str(actor.get_actor_label()), str(actor.get_name())
    found = []
    try:
        for b in seq.get_bindings():
            hit = False
            try:
                hit = any(_path(o) == want for o in seq.locate_bound_objects(b, world))
            except Exception:  # noqa: BLE001
                hit = False
            if hit or str(b.get_display_name()) in (label, oname):
                found += [str(t.get_class().get_name()) for t in b.get_tracks()]
    except Exception:  # noqa: BLE001
        return "UNREAD"
    return found if found else None


def _visibility_sections(binding, fps):
    out = []
    for t in binding.get_tracks():
        if str(t.get_class().get_name()) != "MovieSceneVisibilityTrack":
            continue
        for s in t.get_sections():
            chans = list(s.get_all_channels())
            mode = None
            try:
                mode = _enum_name(s.get_completion_mode())
            except Exception:  # noqa: BLE001
                mode = _enum_name(s.get_editor_property("eval_options").get_editor_property("completion_mode"))
            out.append({"range_s": [float(s.get_start_frame_seconds()), float(s.get_end_frame_seconds())],
                        "completion_mode": mode, "channels": len(chans),
                        "keys": [[int(k.get_time().frame_number.value), bool(k.get_value())] for k in chans[0].get_keys()]
                        if len(chans) == 1 else None, "fps": fps})
    return out


def _fps(seq):
    r = seq.get_display_rate()
    return r.numerator / float(r.denominator)


def _rise_state(world, pedestal):
    rise = unreal.load_asset(RISE)
    _req(isinstance(rise, unreal.LevelSequence), "RISE_LOAD")
    fps = _fps(rise)
    want = _path(pedestal)
    rows = []
    for b in rise.get_bindings():
        try:
            resolved = [_path(o) for o in rise.locate_bound_objects(b, world)]
        except Exception:  # noqa: BLE001
            continue
        if resolved == [want]:
            rows.append({"guid": _guid(b.get_id()), "resolved": resolved, "visibility_sections": _visibility_sections(b, fps)})
    return {"fps": fps, "pedestal_binding": rows[0] if len(rows) == 1 else None, "pedestal_bindings_found": len(rows)}


def _floor_samples(world_index, xy, radius):
    rows = []
    for label in FLOOR_LABELS:
        for a in world_index.get(label, []):
            box = _box(a)
            if not (box["min"][0] <= xy[0] <= box["max"][0] and box["min"][1] <= xy[1] <= box["max"][1]):
                continue
            comps = list(a.get_components_by_class(unreal.StaticMeshComponent))
            if len(comps) != 1:
                rows.append({"label": label, "visible": False, "kind": "unreadable", "samples_z": []})
                continue
            c = comps[0]
            visible = (not bool(a.get_editor_property("hidden"))) and bool(c.is_visible())
            mesh = c.get_editor_property("static_mesh")
            if _path(mesh) in BOX_MESHES:
                rows.append({"label": label, "visible": visible, "kind": "box", "samples_z": [box["max"][2]]})
                continue
            t = c.get_world_transform()
            tf = {"location": _v(t.translation), "rotation": _r(t.rotation.rotator()), "scale": _v(t.scale3d)}
            desc = mesh.get_static_mesh_description(0)
            _req(desc is not None, "FLOOR_MESH_DESCRIPTION|%s" % label)
            n = int(desc.get_vertex_count())
            _req(n <= 4000000, "FLOOR_TOO_DENSE|%s|%d" % (label, n))
            zs = []
            for i in range(n):
                p = desc.get_vertex_position(unreal.VertexID(i))
                w = tf_point(tf, [p.x, p.y, p.z])
                if (w[0] - xy[0]) ** 2 + (w[1] - xy[1]) ** 2 <= radius * radius:
                    zs.append(w[2])
            rows.append({"label": label, "visible": visible, "kind": "mesh", "samples_z": zs, "vertices": n,
                         "mesh": _path(mesh)})
    return rows


def live_state(world, a):
    idx = _index(world)
    root = _one(idx, ROOT_LABEL)
    ped = _one(idx, PEDESTAL_LABEL)
    pc = _smc(ped)
    pp = ped.get_attach_parent_actor()
    st = {"root": {"world": _world_tf(root)},
          "pedestal": dict({"label": PEDESTAL_LABEL, "object_name": str(ped.get_name()), "object_path": _path(ped),
                            "parent": str(pp.get_actor_label()) if pp else None, "aabb_world": _box(ped),
                            "mobility": _enum_name(pc.get_editor_property("mobility"))}, **_flags(ped)),
          "temp_actors": sorted(k for k in idx if k.startswith("ZZ_") or "TEMP" in k.upper()),
          "label_count": {a["label"]: len(idx.get(a["label"], []))},
          "assets": {k: unreal.EditorAssetLibrary.does_asset_exist(prop_paths(a["prop"])[k]) for k in ("mesh", "mi")}}
    seqs = {p: unreal.load_asset(p) for p in CLAM_SEQUENCES}
    st["clams"] = []
    for label in a["clam_labels"]:
        for c in idx.get(label, []):
            cp = c.get_attach_parent_actor()
            st["clams"].append({"label": label, "object_path": _path(c), "class": str(c.get_class().get_name()),
                                "location": _v(c.get_actor_location()), "aabb_world": _box(c),
                                "parent": str(cp.get_actor_label()) if cp else None,
                                "tracks": {p: _sequence_tracks(s, world, c) for p, s in seqs.items()}})
    st["rise"] = _rise_state(world, ped)
    xy = target_xy(st, a)
    st["floors"] = _floor_samples(idx, xy, float(a["floor_radius_cm"]))
    st["target_xy"] = xy
    return st


def _backup(root, run, extra=()):
    d = root + run
    os.makedirs(d)
    for src in (UMAP, RISE_UASSET) + tuple(extra):
        dst = os.path.join(d, os.path.basename(src))
        shutil.copy2(src, dst)
        _req(os.path.getsize(dst) == os.path.getsize(src), "BACKUP_SIZE|%s" % dst)
        _req(sha256_file(dst) == sha256_file(src), "BACKUP_HASH|%s" % dst)
    return d


def _spawn(op):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*op["location"]),
                                   unreal.Rotator(roll=op["rotation"][0], pitch=op["rotation"][1], yaw=op["rotation"][2]),
                                   False)
    _req(a is not None, "SPAWN_FAILED")
    a.set_actor_label(op["label"])
    c = a.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.MOVABLE)                 # SetStaticMesh is refused on Static at runtime
    mesh, mi = unreal.load_asset(op["mesh"]), unreal.load_asset(op["mi"])
    _req(isinstance(mesh, unreal.StaticMesh) and mi is not None, "ASSET_LOAD|%s|%s" % (op["mesh"], op["mi"]))
    c.set_static_mesh(mesh)                                          # return value not trusted: read back below
    c.set_material(0, mi)
    c.set_mobility(getattr(unreal.ComponentMobility, op["mobility"]))
    a.set_editor_property("tags", [unreal.Name(t) for t in op["tags"]])
    a.set_folder_path(op["folder"])
    a.set_actor_hidden_in_game(bool(op["actor_hidden_in_game"]))
    _req(_path(c.get_editor_property("static_mesh")).split(".")[0] == op["mesh"], "READBACK_MESH")
    _req(_path(c.get_material(0)).split(".")[0] == op["mi"], "READBACK_MI")
    _req(a.get_attach_parent_actor() is None, "SPAWN_ATTACHED")
    return a


def _add_reveal(world, actor, section):
    rise = unreal.load_asset(RISE)
    fps = _fps(rise)
    _req(abs(fps - section["fps"]) < 1e-6, "RISE_FPS_CHANGED|%s|%s" % (fps, section["fps"]))
    b = rise.add_possessable(actor)
    _req(b is not None and b.is_valid(), "ADD_POSSESSABLE")
    t = b.add_track(unreal.MovieSceneVisibilityTrack)
    _req(t is not None, "ADD_VISIBILITY_TRACK")
    s = t.add_section()
    s.set_range_seconds(section["range_s"][0], section["range_s"][1])
    s.set_completion_mode(getattr(unreal.MovieSceneCompletionMode, section["completion_mode"]))
    ch = list(s.get_all_channels())
    _req(len(ch) == 1, "NEW_SECTION_CHANNELS|%d" % len(ch))
    for frame, value in section["keys"]:
        ch[0].add_key(unreal.FrameNumber(int(frame)), bool(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    guid = _guid(b.get_id())
    _verify_reveal(world, guid, actor, section)
    return guid


def _verify_reveal(world, guid, actor, section):
    rise = unreal.load_asset(RISE)
    rows = [b for b in rise.get_bindings() if _guid(b.get_id()) == guid]
    _req(len(rows) == 1, "REVEAL_BINDING_COUNT|%d" % len(rows))
    _req([_path(o) for o in rise.locate_bound_objects(rows[0], world)] == [_path(actor)], "REVEAL_RESOLVES")
    got = _visibility_sections(rows[0], _fps(rise))
    _req(len(got) == 1, "REVEAL_SECTIONS|%d" % len(got))
    g = got[0]
    _req(g["keys"] == [[int(f), bool(v)] for f, v in section["keys"]], "REVEAL_KEYS|%s" % g["keys"])
    _req(g["completion_mode"] == section["completion_mode"], "REVEAL_COMPLETION|%s" % g["completion_mode"])
    _req(near(g["range_s"], section["range_s"], 1.0 / g["fps"] + 1e-6), "REVEAL_RANGE|%s" % g["range_s"])


def _remove_reveal(world, guid, actor_path):
    rise = unreal.load_asset(RISE)
    rows = [b for b in rise.get_bindings() if _guid(b.get_id()) == guid]
    _req(len(rows) == 1, "REVERT_BINDING_COUNT|%d" % len(rows))
    _req([_path(o) for o in rise.locate_bound_objects(rows[0], world)] == [actor_path], "REVERT_BINDING_TARGET")
    rows[0].remove()                                                  # returns None even on success: re-list
    _req(not [b for b in rise.get_bindings() if _guid(b.get_id()) == guid], "REVERT_BINDING_SURVIVED")


def _save(world, want_content):
    c = _census()
    _req(c == {"content": sorted(want_content), "maps": [WORLD]}, "DIRTY_SCOPE|%s" % json.dumps(c))
    _req(not [k for k in _index(world) if k.startswith("ZZ_")], "ZZ_ACTORS_PRESENT")
    for p in want_content:
        _req(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), "SAVE|" + p)
    _req(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "SAVE_MAP")
    after = _census()
    _req(after == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % json.dumps(after))


def _verify_placed(world, path, op):
    a = _by_path(world, path)
    _req(a is not None, "PLACED_MISSING|%s" % path)
    tf = _world_tf(a)
    _req(near(tf["location"], op["location"], TOL_CM), "PLACED_LOCATION|%s" % tf["location"])
    _req(near(tf["rotation"], op["rotation"], 0.01), "PLACED_ROTATION|%s" % tf["rotation"])
    _req(near(tf["scale"], [1, 1, 1], 1e-6), "PLACED_SCALE")
    _req(bool(a.get_editor_property("hidden")) == bool(op["actor_hidden_in_game"]), "PLACED_HIDDEN_FLAG")
    _req(a.get_attach_parent_actor() is None, "PLACED_ATTACHED")
    _req(str(a.get_actor_label()) == op["label"], "PLACED_LABEL")
    return a


def _verify_apply(world, record):
    plan = record["plan"]
    ops = apply_ops(plan)
    a = _verify_placed(world, record["actor_path"], ops[0])
    ped = _by_path(world, plan["pedestal"]["object_path"])
    _req(_flags(ped) == plan["pedestal"]["after"], "PEDESTAL_FLAGS|%s" % _flags(ped))
    for c in plan["clams"]["rows"]:
        act = _by_path(world, c["object_path"])
        _req(act is not None and near(_v(act.get_actor_location()), c["after_location"], TOL_CM), "CLAM_LOCATION|%s" % c["label"])
    if record.get("reveal_binding_guid"):
        _verify_reveal(world, record["reveal_binding_guid"], a, plan["reveal"]["section"])
    root = _one(_index(world), ROOT_LABEL)
    _req(box_inside(box_local(_world_tf(root), _box(a)), GUARD_LOCAL, tol=2.0), "PLACED_OUTSIDE_LANDED_BOX")


def run_apply(run, args, world):
    a = dict(APPLY_DEFAULTS, **(args.get("apply") or {}))
    state = live_state(world, a)
    plan = plan_apply(state, a)
    record = {"run": run, "world": WORLD, "rise": RISE, "plan": plan, "saved": False, "applied": False,
              "actor_path": None, "reveal_binding_guid": None, "census_before": _census()}
    _write(APPLY_RECORD, record, exclusive=True)                       # RECORD FIRST
    unreal.log("S3MILL_RECORD|run=%s|path=%s" % (run, APPLY_RECORD))
    record["backup"] = _backup(BACKUP_ROOT, run, (APPLY_RECORD,))
    _write(APPLY_RECORD, record)
    ops = apply_ops(plan)
    actor = _spawn(ops[0])
    record["actor_path"] = _path(actor)
    _write(APPLY_RECORD, record)
    for op in ops[1:]:
        if op["op"] == "add_reveal":
            record["reveal_binding_guid"] = _add_reveal(world, actor, op["section"])
            _write(APPLY_RECORD, record)
        elif op["op"] == "set_flags":
            _set_flags(_by_path(world, op["object_path"]), op["flags"])
        elif op["op"] == "move":
            m = _by_path(world, op["object_path"])
            m.modify()
            m.set_actor_location(unreal.Vector(*op["location"]), False, False)
    _verify_apply(world, record)
    _save(world, [RISE] if record["reveal_binding_guid"] else [])
    record["saved"] = True
    _write(APPLY_RECORD, record)
    _verify_apply(world, record)                                      # fresh lookups, after the save
    record["applied"] = True
    _write(APPLY_RECORD, record)
    return {"actor": record["actor_path"], "location": plan["location"], "top_z": plan["top_z"],
            "floor": plan["floor"], "clams": plan["clams"]["action"], "reveal_guid": record["reveal_binding_guid"],
            "backup": record["backup"]}


def _revert_record(world, record, run, backup_root, record_path):
    plan = record["plan"]
    _req(record.get("saved") and record.get("actor_path"), "RECORD_INVALID")
    _verify_apply(world, record) if "pedestal" in plan else None      # drift since APPLY -> refuse before mutating
    backup = _backup(backup_root, run + "-REVERT", (record_path,))
    for op in revert_ops(record):
        if op["op"] == "move":
            m = _by_path(world, op["object_path"])
            m.modify()
            m.set_actor_location(unreal.Vector(*op["location"]), False, False)
        elif op["op"] == "set_flags":
            _set_flags(_by_path(world, op["object_path"]), op["flags"])
        elif op["op"] == "remove_reveal":
            _remove_reveal(world, op["guid"], op["actor_path"])
        elif op["op"] == "destroy":
            a = _by_path(world, op["actor_path"])
            _req(a is not None and str(a.get_actor_label()) == op["label"], "DESTROY_TARGET")
            _req(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(a), "DESTROY")
            _req(_by_path(world, op["actor_path"]) is None, "DESTROY_SURVIVED")
    _save(world, [RISE] if record.get("reveal_binding_guid") else [])
    if "pedestal" in plan:
        ped = _by_path(world, plan["pedestal"]["object_path"])
        _req(_flags(ped) == plan["pedestal"]["before"], "REVERT_PEDESTAL|%s" % _flags(ped))
        for c in plan["clams"]["rows"]:
            act = _by_path(world, c["object_path"])
            _req(near(_v(act.get_actor_location()), c["before_location"], 1e-3), "REVERT_CLAM|%s" % c["label"])
    _req(_by_path(world, record["actor_path"]) is None, "REVERT_ACTOR_PRESENT")
    os.replace(record_path, record_path + ".reverted-" + run)
    return {"backup": backup}


def run_revert(run, world):
    with open(APPLY_RECORD, encoding="utf-8") as h:
        record = json.load(h)
    return _revert_record(world, record, run, BACKUP_ROOT, APPLY_RECORD)


def run_place(run, args, world):
    pf = HERE + args.get("placements_file", "s3_props_placements.json")
    placements = json.load(open(pf, encoding="utf-8")).get("placements", [])
    idx = _index(world)
    root = _one(idx, ROOT_LABEL)
    ped = _one(idx, PEDESTAL_LABEL)
    st = {"root": {"world": _world_tf(root)}, "temp_actors": sorted(k for k in idx if k.startswith("ZZ_")),
          "label_count": {p["label"]: len(idx.get(p["label"], [])) for p in placements},
          "assets_by_prop": {p["prop"]: {k: unreal.EditorAssetLibrary.does_asset_exist(prop_paths(p["prop"])[k])
                                         for k in ("mesh", "mi")} for p in placements},
          "rise": _rise_state(world, ped), "floors_by_label": {}}
    for p in placements:
        st["floors_by_label"][p["label"]] = _floor_samples(idx, place_xy(st["root"]["world"], p),
                                                           float(p.get("floor_radius_cm", 10.0)))
    plans = plan_place(st, placements)
    record = {"run": run, "placements_file": pf, "plans": plans, "rows": [], "saved": False}
    _write(PLACE_RECORD, record, exclusive=True)
    record["backup"] = _backup(BACKUP_ROOT_PLACE, run, (PLACE_RECORD,))
    _write(PLACE_RECORD, record)
    for plan in plans:
        ops = apply_ops(plan)
        actor = _spawn(ops[0])
        row = {"label": plan["label"], "actor_path": _path(actor), "reveal_binding_guid": None, "plan": plan}
        record["rows"].append(row)
        _write(PLACE_RECORD, record)
        if plan["reveal"]["mode"] == "rise_track":
            row["reveal_binding_guid"] = _add_reveal(world, actor, plan["reveal"]["section"])
            _write(PLACE_RECORD, record)
        _verify_placed(world, row["actor_path"], ops[0])
    _save(world, [RISE] if any(r["reveal_binding_guid"] for r in record["rows"]) else [])
    record["saved"] = True
    _write(PLACE_RECORD, record)
    for row in record["rows"]:
        _verify_placed(world, row["actor_path"], apply_ops(row["plan"])[0])
    return {"placed": [r["label"] for r in record["rows"]], "backup": record["backup"]}


def run_unplace(run, world):
    with open(PLACE_RECORD, encoding="utf-8") as h:
        record = json.load(h)
    _req(record.get("saved"), "PLACE_RECORD_UNSAVED")
    backup = _backup(BACKUP_ROOT_PLACE, run + "-UNPLACE", (PLACE_RECORD,))
    for row in record["rows"]:
        _verify_placed(world, row["actor_path"], apply_ops(row["plan"])[0])     # drift -> refuse before mutating
    for row in record["rows"]:
        if row["reveal_binding_guid"]:
            _remove_reveal(world, row["reveal_binding_guid"], row["actor_path"])
        a = _by_path(world, row["actor_path"])
        _req(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(a), "DESTROY|%s" % row["label"])
        _req(_by_path(world, row["actor_path"]) is None, "DESTROY_SURVIVED|%s" % row["label"])
    _save(world, [RISE] if any(r["reveal_binding_guid"] for r in record["rows"]) else [])
    os.replace(PLACE_RECORD, PLACE_RECORD + ".reverted-" + run)
    return {"removed": [r["label"] for r in record["rows"]], "backup": backup}


# ------------------------------------------------------------------------------------------- import / material
def _pipeline(asset_name, vc_option=None, normals_from_file=False):
    """Same Interchange override as S3Shore/s3_shore_ground_ue.py _pipeline (header lines cited there).
    vc_replace: common_meshes_properties.vertex_color_import_option = IVCIO_Replace
    (InterchangeGenericAssetsPipelineSharedSettings.h:109-111 [decl]; Replace is also the declared default)."""
    p = unreal.InterchangeGenericAssetsPipeline()
    common = p.get_editor_property("common_meshes_properties")
    mesh = p.get_editor_property("mesh_pipeline")
    mat = p.get_editor_property("material_pipeline")
    tex = mat.get_editor_property("texture_pipeline") if mat else None
    _req(all(x is not None for x in (common, mesh, mat, tex)), "PIPELINE_SUBOBJECTS")
    p.set_editor_property("asset_name", asset_name)
    objs = {"mat": mat, "tex": tex, "mesh": mesh, "common": common}
    wanted = pipeline_wanted(vc_option, normals_from_file)
    for key, prop, val in wanted:
        if prop == "vertex_color_import_option":
            val = getattr(unreal.InterchangeVertexColorImportOption, val)
        objs[key].set_editor_property(prop, val)
    got = {}
    for key, prop, val in wanted:
        g = objs[key].get_editor_property(prop)
        got[prop] = _enum_name(g) if prop == "vertex_color_import_option" else g
        _req(got[prop] == val, "PIPELINE_READBACK|%s=%s" % (prop, got[prop]))
    ov = unreal.InterchangePipelineStackOverride()
    ov.add_pipeline(p)
    return ov, got


def _folder_assets(folder):
    eal = unreal.EditorAssetLibrary
    return set(str(n).split(".")[0] for n in eal.list_assets(folder, recursive=True)) if eal.does_directory_exist(folder) else set()


def run_import_mesh(run, name):
    eal = unreal.EditorAssetLibrary
    p = prop_paths(name)
    _req(not eal.does_asset_exist(p["mesh"]), "MESH_EXISTS|%s" % p["mesh"])
    man = json.load(open(p["manifest"], encoding="utf-8"))
    size, min_z, slots_want = manifest_expect(man)
    _req(near(size, PROPS[name]["size_cm"], 0.01) and abs(min_z - PROPS[name]["min_z_cm"]) < 0.01,
         "MANIFEST_VS_TABLE|%s|%s" % (size, min_z))
    before = _folder_assets(p["folder"])
    task = unreal.AssetImportTask()
    for k, v in (("filename", p["fbx"]), ("destination_path", p["folder"]), ("destination_name", p["mesh_name"]),
                 ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    ov, settings = _pipeline(p["mesh_name"])
    task.set_editor_property("options", ov)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(p["mesh"])
    _req(isinstance(mesh, unreal.StaticMesh), "IMPORT_FAILED|%s" % list(task.imported_object_paths))
    new = sorted(_folder_assets(p["folder"]) - before)
    _req(new == [p["mesh"]], "STRAY_ASSETS|%s (never saved: Don't-Save restart, do not delete)" % new)
    _req(mesh.get_num_lods() == 1, "LODS|%d" % mesh.get_num_lods())
    _req(bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")), "NANITE_OFF")
    slots = [str(m.get_editor_property("material_slot_name")) for m in mesh.get_editor_property("static_materials")]
    _req(len(slots) == slots_want == 1, "SLOTS|%s" % slots)
    bb = mesh.get_bounding_box()
    got = {"min": _v(bb.min), "max": _v(bb.max)}
    fails = bounds_check(got, size, min_z)
    _req(not fails, "BOUNDS|%s|got=%s" % (";".join(fails), json.dumps(got)))
    _req(_census() == {"content": [p["mesh"]], "maps": []}, "DIRTY_SCOPE|%s" % _census())
    _req(eal.save_asset(p["mesh"], only_if_is_dirty=False), "SAVE_MESH")
    _req(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    unreal.SystemLibrary.collect_garbage()
    rec = {"run": run, "prop": name, "mesh": p["mesh"], "bounds": got, "slots": slots, "pipeline": settings,
           "fbx_sha256": sha256_file(p["fbx"]), "saved": True}
    _write(HERE + "s3_props_import_mesh_%s.json" % name, rec)
    return rec


def run_import_tex(run, args):
    """ONE texture per call (check_mode enforces it).  Imports, sets and reads back the settings, and leaves the
    package DIRTY with a pending file: the size is not gated here because a texture reads 32x32 in its own import
    call [meas 7 Oct].  VERIFY_TEX (a later call) gates the size and saves."""
    eal = unreal.EditorAssetLibrary
    prop, role = args["prop"], args["textures"][0]
    t = tex_target(prop, args.get("tex_set"), role)
    src = tex_source_gate(t)
    src["sha256"] = sha256_file(t["file"])           # Shell BaseColor is re-tinted in place (coral): record what we took
    _req(not eal.does_asset_exist(t["asset"]), "TEX_EXISTS|%s" % t["asset"])
    before = _folder_assets(t["folder"])
    task = unreal.AssetImportTask()
    for k, v in (("filename", t["file"]), ("destination_path", t["folder"]), ("destination_name", t["name"]),
                 ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    new = sorted(_folder_assets(t["folder"]) - before)
    _req(new == [t["asset"]], "STRAY_OR_MISSING|got=%s|want=%s" % (new, [t["asset"]]))
    _suffix, comp, srgb, flip, _sampler = ROLE_SPEC[role]
    tex = unreal.load_asset(t["asset"])
    _req(isinstance(tex, unreal.Texture2D), "TEX_LOAD|%s" % role)
    tex.modify()
    tex.set_editor_property("compression_settings", getattr(unreal.TextureCompressionSettings, comp))
    tex.set_editor_property("srgb", srgb)
    tex.set_editor_property("flip_green_channel", flip)
    g = {"compression": _enum_name(tex.get_editor_property("compression_settings")),
         "srgb": bool(tex.get_editor_property("srgb")), "flip_green": bool(tex.get_editor_property("flip_green_channel")),
         "size_at_import_call": [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]}   # NOT gated
    _req(g["compression"] == comp and g["srgb"] == srgb and g["flip_green"] == flip, "TEX_READBACK|%s|%s" % (role, g))
    _req(_census() == {"content": [t["asset"]], "maps": []}, "DIRTY_SCOPE|%s" % _census())
    pending = {"run": run, "prop": prop, "tex_set": args.get("tex_set"), "role": role, "asset": t["asset"],
               "label": t["label"], "want": {"compression": comp, "srgb": srgb, "flip_green": flip},
               "source": src, "import": g, "saved": False}
    _write(TEX_PENDING, pending, exclusive=True)
    return pending


def run_verify_tex(run, pending):
    """Census == exactly the pending package (gated in main); size == source IHDR; settings; save; record."""
    eal = unreal.EditorAssetLibrary
    tex = unreal.load_asset(pending["asset"])
    _req(isinstance(tex, unreal.Texture2D), "TEX_LOAD|%s" % pending["asset"])
    g = {"compression": _enum_name(tex.get_editor_property("compression_settings")),
         "srgb": bool(tex.get_editor_property("srgb")), "flip_green": bool(tex.get_editor_property("flip_green_channel")),
         "size": [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]}
    w = pending["want"]
    _req(g["compression"] == w["compression"] and g["srgb"] == w["srgb"] and g["flip_green"] == w["flip_green"],
         "TEX_READBACK|%s" % g)
    _req(g["size"] == [pending["source"]["w"], pending["source"]["h"]],
         "TEX_SIZE|%s|%s (not saved; retry VERIFY_TEX later)" % (pending["asset"], g["size"]))
    _req(eal.save_asset(pending["asset"], only_if_is_dirty=False), "SAVE|%s" % pending["asset"])
    _req(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    unreal.SystemLibrary.collect_garbage()
    rec = dict(pending, verify_run=run, verified=g, saved=True)
    out = HERE + "s3_props_import_tex_%s_%s.json" % (pending["prop"], pending["label"])
    _write(out, rec)
    os.replace(TEX_PENDING, TEX_PENDING + ".done-" + run)
    return rec


def _mesh_centroid(mesh):
    """Strided vertex centroid of LOD0's mesh description (get_vertex_position, precedent
    Scripts/build_curtain_chaos_asset.py:362-366).  [inf] for a fresh Nanite import until run."""
    desc = mesh.get_static_mesh_description(0)
    _req(desc is not None, "MESH_DESCRIPTION")
    n = int(desc.get_vertex_count())
    _req(n > 0, "MESH_NO_VERTICES")
    stride = max(1, n // CENTROID_STRIDE_TARGET)
    s, k = [0.0, 0.0, 0.0], 0
    for i in range(0, n, stride):
        p = desc.get_vertex_position(unreal.VertexID(i))
        s[0] += p.x
        s[1] += p.y
        s[2] += p.z
        k += 1
    desc = None
    return [x / k for x in s], n, stride


def run_import_clam_part(run, part, args):
    eal = unreal.EditorAssetLibrary
    name = "SM_PearlClam_" + part
    fbx = CLAM_DIR + name + ".fbx"
    path = clam_mesh_path(part)
    man = json.load(open(CLAM_MANIFEST, encoding="utf-8"))
    _req(not clam_manifest_problems(man), "MANIFEST|%s" % clam_manifest_problems(man))
    _req(os.path.isfile(fbx), "FBX_MISSING|%s" % fbx)
    _req(not eal.does_asset_exist(path), "MESH_EXISTS|%s" % path)
    before = _folder_assets(CLAM_FOLDER)
    task = unreal.AssetImportTask()
    for k, v in (("filename", fbx), ("destination_path", CLAM_FOLDER), ("destination_name", name),
                 ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    row = clam_part_row(part)
    if part in CLAM_EXTRA_PARTS:
        _req(not pearl_v2_manifest_problems(man), "MANIFEST_V2|%s" % pearl_v2_manifest_problems(man))
    plan_rows = pipeline_wanted(clam_vc_option(part), row["custom_normals"])
    _req(not pipeline_problems(plan_rows, part), "PIPELINE_PLAN|%s" % pipeline_problems(plan_rows, part))
    ov, settings = _pipeline(name, vc_option=clam_vc_option(part), normals_from_file=row["custom_normals"])
    task.set_editor_property("options", ov)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(path)
    _req(isinstance(mesh, unreal.StaticMesh), "IMPORT_FAILED|%s" % list(task.imported_object_paths))
    new = sorted(_folder_assets(CLAM_FOLDER) - before)
    _req(new == [path], "STRAY_ASSETS|%s (never saved: Don't-Save restart, do not delete)" % new)
    _req(mesh.get_num_lods() == 1, "LODS|%d" % mesh.get_num_lods())
    _req(bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")), "NANITE_OFF")
    slots = [str(m.get_editor_property("material_slot_name")) for m in mesh.get_editor_property("static_materials")]
    _req(slots == row["slots"], "SLOTS|%s|want %s" % (slots, row["slots"]))
    bb = mesh.get_bounding_box()
    got = {"min": _v(bb.min), "max": _v(bb.max)}
    fails = clam_bounds_check(part, got)
    _req(not fails, "BOUNDS|%s" % ";".join(fails))
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    has_vc = bool(sme.has_vertex_colors(mesh))
    # LOD0 build settings: StaticMeshEditorSubsystem.h:80-81 GetLodBuildSettings (out-param, returned in Python [inf]);
    # FMeshBuildSettings EngineTypes.h:2948-2956 bRecomputeNormals / bRecomputeTangents [decl]
    normals = {"readable": False}
    try:
        bs = sme.get_lod_build_settings(mesh, 0)
        normals = {"readable": True, "recompute_normals": bool(bs.get_editor_property("recompute_normals")),
                   "recompute_tangents": bool(bs.get_editor_property("recompute_tangents")),
                   "use_mikk_t_space": bool(bs.get_editor_property("use_mikk_t_space"))}
        bs = None
    except Exception as exc:  # noqa: BLE001  (recorded; only the custom-normal parts insist)
        normals["error"] = str(exc)[:200]
    _req(normals_gate(part, normals, bool(args.get("allow_unreadable_normals"))) == [],
         "NORMALS|%s" % normals_gate(part, normals, bool(args.get("allow_unreadable_normals"))))
    if row["vc"]:
        _req(has_vc, "VERTEX_COLORS_MISSING|%s (BreathMask R must survive the import)" % part)
    centroid = None
    if args.get("centroid_gate", True):
        c, n, stride = _mesh_centroid(mesh)
        cf = clam_centroid_check(part, c)
        _req(not cf, "CENTROID|%s" % ";".join(cf))
        centroid = {"value": c, "vertices": n, "stride": stride, "discriminates": centroid_discriminates(part)}
    _req(_census() == {"content": [path], "maps": []}, "DIRTY_SCOPE|%s" % _census())
    _req(eal.save_asset(path, only_if_is_dirty=False), "SAVE_MESH")
    _req(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    mesh = None
    unreal.SystemLibrary.collect_garbage()
    rec = {"run": run, "prop": CLAM, "part": part, "mesh": path, "bounds": got, "expected": clam_expected_ue(part),
           "y_flip": "VERIFIED_BY_BOUNDS" if part == "Lid" else "CONSISTENT (part near-symmetric in Y)",
           "slots": slots, "has_vertex_colors": has_vc, "normals": normals, "centroid": centroid,
           "centroid_gate": bool(args.get("centroid_gate", True)), "pipeline": settings,
           "fbx_sha256": sha256_file(fbx), "saved": True}
    _write(HERE + "s3_props_import_mesh_PearlClam_%s.json" % part, rec)
    return rec


def _build_material(path, spec, textures):
    """Create-only (refuses an existing asset; never deletes nodes).  textures: role -> Texture2D defaults."""
    mel = unreal.MaterialEditingLibrary
    _req(not unreal.EditorAssetLibrary.does_asset_exist(path), "MATERIAL_EXISTS|%s" % path)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    folder, name = path.rsplit("/", 1)
    mat = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    _req(mat is not None, "MATERIAL_CREATE|%s" % path)
    mat.modify()
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    # EngineTypes.h:707-711 [decl] MSM_DefaultLit / MSM_Subsurface; Python name MSM_SUBSURFACE by the same mangling as
    # the MSM_DEFAULT_LIT already used here [inf until the first Subsurface BUILD_MAT; read back by _verify_material]
    mat.set_editor_property("shading_model", getattr(unreal.MaterialShadingModel,
                                                     spec.get("shading_model", "MSM_DEFAULT_LIT")))
    mat.set_editor_property("used_with_nanite", True)
    if spec["max_wpo"] is not None:
        mat.set_editor_property("max_world_position_offset_displacement", float(spec["max_wpo"]))
    made = {}
    for i, (key, (kind, v)) in enumerate(spec["nodes"].items()):
        x, y = -1100, -500 + 160 * i
        if kind == "texture":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
            _req(n is not None, "NODE|" + key)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("texture", textures[v])
            n.set_editor_property("sampler_type", getattr(unreal.MaterialSamplerType, ROLE_SPEC[v][4]))
        elif kind == "scalar":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
            _req(n is not None, "NODE|" + key)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("default_value", float(v))
        elif kind == "vector":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, x, y)
            _req(n is not None, "NODE|" + key)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("default_value", unreal.LinearColor(*[float(c) for c in v]))
        elif kind == "time":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionTime, x, y)
        elif kind == "vcolor":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionVertexColor, x, y)
        elif kind == "worldpos":                                  # MaterialExpressionWorldPosition.h:31 [decl]
            n = mel.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, x, y)
        elif kind == "fresnel":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionFresnel, x, y)
            _req(n is not None, "NODE|" + key)
            n.set_editor_property("exponent", float(v))           # MaterialExpressionFresnel.h:30 [decl]
        else:
            code, ins, otype = v
            n = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -500, y)
            _req(n is not None, "NODE|" + key)
            n.set_editor_property("code", code)
            n.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1 if otype == "F1"
                                  else unreal.CustomMaterialOutputType.CMOT_FLOAT3)
            cis = []
            for nm in ins:
                ci = unreal.CustomInput()
                ci.set_editor_property("input_name", nm)
                cis.append(ci)
            n.set_editor_property("inputs", cis)
            _req([str(c.get_editor_property("input_name")) for c in n.get_editor_property("inputs")] == ins,
                 "CUSTOM_INPUTS|" + key)
        _req(n is not None, "NODE|" + key)
        made[key] = n
    for s, o, d, pin in spec["edges"]:
        _req(mel.connect_material_expressions(made[s], o, made[d], pin), "LINK|%s.%s->%s.%s" % (s, o, d, pin))
    for s, o, prop in spec["props"]:
        _req(mel.connect_material_property(made[s], o, getattr(unreal.MaterialProperty, prop)), "PROP|" + prop)
    if spec.get("prop_readback"):
        # MP_SUBSURFACE_COLOR / MP_OPACITY: SceneTypes.h:150,164 [decl]; that ConnectMaterialProperty reaches them is
        # [inf] -> read every connected property back before the recompile (fail closed, named marker)
        rb = prop_readback_problems(_read_props(mat, spec), spec, {k: _path(v) for k, v in made.items()},
                                    bool(spec.get("allow_prop_readback_unavailable")))
        _req(not rb, "PROP_READBACK|%s" % rb)
    errors = [str(e) for e in (mel.recompile_material(mat) or [])]
    _req(not errors, "RECOMPILE|%s" % errors)
    return mat


def _read_props(mat, spec):
    """{MP_*: {path, output, class, param, code}} via GetMaterialPropertyInputNode (+OutputName)
    (MaterialEditingLibrary.h:317,321 [decl]; that it answers outside an open material editor is [inf]).
    An exception or None reads as path None (prop_readback_problems decides)."""
    mel = unreal.MaterialEditingLibrary
    out = {}
    for _s, _o, prop in spec["props"]:
        row = {"path": None, "output": None, "class": None, "param": None, "code": None}
        try:
            mp = getattr(unreal.MaterialProperty, prop)
            node = mel.get_material_property_input_node(mat, mp)
            if node is not None:
                row.update(path=_path(node), output=str(mel.get_material_property_input_node_output_name(mat, mp)),
                           **{"class": str(node.get_class().get_name())})
                if isinstance(node, unreal.MaterialExpressionCustom):
                    row["code"] = str(node.get_editor_property("code"))
                else:
                    try:
                        row["param"] = str(node.get_editor_property("parameter_name"))
                    except Exception:  # noqa: BLE001  (not a parameter node)
                        row["param"] = None
        except Exception as exc:  # noqa: BLE001
            row["error"] = str(exc)[:200]
        out[prop] = row
    return out


def _verify_material(mat, spec):
    mel = unreal.MaterialEditingLibrary
    tp = sorted(str(x) for x in mel.get_texture_parameter_names(mat))
    sp = sorted(str(x) for x in mel.get_scalar_parameter_names(mat))
    vp = sorted(str(x) for x in mel.get_vector_parameter_names(mat))
    _req(tp == sorted(spec["tex_params"]), "MASTER_TEX_PARAMS|%s" % tp)
    _req(sp == sorted(spec["scalars"]), "MASTER_SCALARS|%s" % sp)
    _req(vp == sorted(spec["vectors"]), "MASTER_VECTORS|%s" % vp)
    _req(bool(mat.get_editor_property("used_with_nanite")), "MASTER_NANITE_USAGE")
    if "shading_model" in spec:                         # look masters only (older specs never declared one)
        sm = _enum_name(mat.get_editor_property("shading_model"))
        _req(sm == spec["shading_model"], "MASTER_SHADING_MODEL|%s|want %s" % (sm, spec["shading_model"]))
    if spec["max_wpo"] is not None:
        got = float(mat.get_editor_property("max_world_position_offset_displacement"))
        _req(abs(got - spec["max_wpo"]) < 1e-4, "MASTER_MAX_WPO|%s" % got)


def _build_master(textures):
    return _build_material(MASTER, material_specs()[MASTER], textures)


def _verify_master(mat):
    _verify_material(mat, material_specs()[MASTER])


def run_build_mat(run, name):
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    _req(not graph_problems(), "GRAPH|%s" % graph_problems())
    p = prop_paths(name)
    _req(not eal.does_asset_exist(p["mi"]), "MI_EXISTS|%s" % p["mi"])
    textures = {}
    for r in TEX_ROLES:
        t = unreal.load_asset(p["tex"][r]["asset"])
        _req(isinstance(t, unreal.Texture2D), "TEX_MISSING|%s (run IMPORT_TEX)" % p["tex"][r]["asset"])
        _req(_enum_name(t.get_editor_property("compression_settings")) == TEX_ROLES[r][1], "TEX_COMPRESSION|%s" % r)
        textures[r] = t
    planned = [p["mi"]]
    created_master = not eal.does_asset_exist(MASTER)
    mat = _build_master(textures) if created_master else unreal.load_asset(MASTER)
    if created_master:
        planned.append(MASTER)
    _verify_master(mat)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mi = tools.create_asset(p["mi_name"], p["folder"], unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    _req(mi is not None, "MI_CREATE")
    mi.modify()
    mel.set_material_instance_parent(mi, mat)
    for param, role in MASTER_TEX_PARAMS.items():
        mel.set_material_instance_texture_parameter_value(mi, param, textures[role])     # bool lies: read back
    for k, v in PROPS[name]["mi_scalars"].items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    mel.update_material_instance(mi)
    _req(_path(mi.get_editor_property("parent")) == _path(mat), "MI_PARENT")
    for param, role in MASTER_TEX_PARAMS.items():
        got = mel.get_material_instance_texture_parameter_value(mi, param)
        _req(_path(got) == _path(textures[role]), "MI_TEX|%s|%s" % (param, _path(got)))
    scal = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in MASTER_SCALARS}
    want = dict(MASTER_SCALARS, **PROPS[name]["mi_scalars"])
    _req(all(abs(scal[k] - want[k]) < 1e-4 for k in want), "MI_SCALARS|%s" % scal)
    _req(_census() == {"content": sorted(planned), "maps": []}, "DIRTY_SCOPE|%s" % _census())
    for a in planned:
        _req(eal.save_asset(a, only_if_is_dirty=False), "SAVE|%s" % a)
    _req(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    unreal.SystemLibrary.collect_garbage()
    rec = {"run": run, "prop": name, "mi": p["mi"], "master_created": created_master, "scalars": scal, "saved": True}
    _write(HERE + "s3_props_build_mat_%s.json" % name, rec)
    return rec


def run_build_clam_mat(run, key, args=None):
    """One clam MI per call (Shell | InteriorBottom | InteriorLid | Mantle | Pearl); its master is created first if missing.
    Look materials (Pearl_v3 | Shell_v2 | Mantle_v2): master AND MI must both be new; breathing scalars copied from the
    MI being replaced; connected properties read back."""
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    probs = material_problems()
    _req(not probs, "GRAPH|%s" % probs)
    m = clam_material_row(key)
    spec = material_specs()[m["master"]]
    mi_path = clam_mi_path(key)
    _req(not eal.does_asset_exist(mi_path), "MI_EXISTS|%s" % mi_path)
    breath_src = None
    if m.get("master_create_only"):
        _req(not look_table_problems(), "LOOK_TABLE|%s" % look_table_problems())
        _req(not eal.does_asset_exist(m["master"]), "LOOK_MASTER_EXISTS|%s (create-only: never edit an existing master)"
             % m["master"])
        spec = dict(spec, allow_prop_readback_unavailable=bool((args or {}).get("allow_prop_readback_unavailable")))
        if m.get("breath_from"):
            src_path = clam_mi_path(m["breath_from"])
            src = unreal.load_asset(src_path)
            _req(src is not None, "BREATH_SOURCE_LOAD|%s" % src_path)
            breath_src = {k: float(mel.get_material_instance_scalar_parameter_value(src, k)) for k in BREATH_PARAMS}
            src = None
    mi_scal = look_mi_scalars(key, breath_src) if m.get("master_create_only") else m["scalars"]
    textures = {}
    if m["tex_set"]:
        for r in CLAM_TEX[m["tex_set"]]:
            t = tex_target(CLAM, m["tex_set"], r)
            tex = unreal.load_asset(t["asset"])
            _req(isinstance(tex, unreal.Texture2D), "TEX_MISSING|%s (IMPORT_TEX + VERIFY_TEX)" % t["asset"])
            _req(_enum_name(tex.get_editor_property("compression_settings")) == ROLE_SPEC[r][1], "TEX_COMPRESSION|%s" % r)
            _req(bool(tex.get_editor_property("srgb")) == ROLE_SPEC[r][2], "TEX_SRGB|%s" % r)
            sx, sy = int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())
            _req(sx == sy == t["dim"], "TEX_SIZE|%s|%dx%d" % (t["asset"], sx, sy))
            textures[r] = tex
    planned = [mi_path]
    created_master = not eal.does_asset_exist(m["master"])
    if created_master:
        _req(not spec["tex_params"] or textures, "MASTER_NEEDS_TEXTURES|%s" % m["master"])
        mat = _build_material(m["master"], spec, textures)
        planned.append(m["master"])
    else:
        mat = unreal.load_asset(m["master"])
        _req(isinstance(mat, unreal.Material), "MASTER_LOAD|%s" % m["master"])
    _verify_material(mat, spec)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mi = tools.create_asset(m["mi"], CLAM_FOLDER, unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    _req(mi is not None, "MI_CREATE")
    mi.modify()
    mel.set_material_instance_parent(mi, mat)
    for param, role in spec["tex_params"].items():
        mel.set_material_instance_texture_parameter_value(mi, param, textures[role])      # bool lies: read back
    for k, v in mi_scal.items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in m["vectors"].items():
        mel.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*[float(c) for c in v]))
    mel.update_material_instance(mi)
    _req(_path(mi.get_editor_property("parent")) == _path(mat), "MI_PARENT")
    for param, role in spec["tex_params"].items():
        got = mel.get_material_instance_texture_parameter_value(mi, param)
        _req(_path(got) == _path(textures[role]), "MI_TEX|%s|%s" % (param, _path(got)))
    scal = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in spec["scalars"]}
    want = dict(spec["scalars"], **mi_scal)
    _req(all(abs(scal[k] - want[k]) < 1e-4 for k in want), "MI_SCALARS|%s" % scal)
    vec = {}
    for k in spec["vectors"]:
        c = mel.get_material_instance_vector_parameter_value(mi, k)
        vec[k] = [float(c.r), float(c.g), float(c.b), float(c.a)]
    wantv = dict(spec["vectors"], **m["vectors"])
    _req(all(near(vec[k], wantv[k], 1e-4) for k in wantv), "MI_VECTORS|%s" % vec)
    _req(_census() == {"content": sorted(planned), "maps": []}, "DIRTY_SCOPE|%s" % _census())
    for a in planned:
        _req(eal.save_asset(a, only_if_is_dirty=False), "SAVE|%s" % a)
    _req(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    mi, mat, textures = None, None, None
    unreal.SystemLibrary.collect_garbage()
    rec = {"run": run, "prop": CLAM, "material": key, "mi": mi_path, "master": m["master"],
           "master_created": created_master, "scalars": scal, "vectors": vec, "saved": True}
    if m.get("master_create_only"):
        rec.update(mi_explicit_scalars=mi_scal, breath_source=(clam_mi_path(m["breath_from"]) if m.get("breath_from")
                                                               else None), breath_inherited=breath_src,
                   shading_model=spec.get("shading_model"))
    _write(HERE + "s3_props_build_mat_PearlClam_%s.json" % key, rec)
    return rec


# ------------------------------------------------------------------------------------------- PearlClam glue
def _prim_flags(actor):
    out = {}
    for c in actor.get_components_by_class(unreal.PrimitiveComponent):
        n = str(c.get_name())
        _req(n not in out, "COMPONENT_NAME_DUP|%s|%s" % (actor.get_actor_label(), n))
        out[n] = {"visible": bool(c.is_visible()), "hidden_in_game": bool(c.get_editor_property("hidden_in_game"))}
    return {"actor_hidden": bool(actor.get_editor_property("hidden")), "components": out}


def _set_prim_flags(actor, flags):
    _req(actor is not None, "PRIM_FLAGS_TARGET")
    actor.modify()
    comps = {str(c.get_name()): c for c in actor.get_components_by_class(unreal.PrimitiveComponent)}
    _req(sorted(comps) == sorted(flags["components"]), "COMPONENT_SET_CHANGED|%s" % sorted(comps))
    actor.set_actor_hidden_in_game(bool(flags["actor_hidden"]))
    for n, f in flags["components"].items():
        c = comps[n]
        c.modify()
        c.set_visibility(bool(f["visible"]), False)
        c.set_hidden_in_game(bool(f["hidden_in_game"]), False)
    got = _prim_flags(actor)
    _req(got == json.loads(json.dumps(flags)), "PRIM_FLAGS_READBACK|%s|%s" % (actor.get_actor_label(), got))


def _channel_value(ch, seq, frame, fallback):
    if int(ch.get_num_keys()) == 0:
        return float(ch.get_default()) if ch.has_default() else float(fallback)
    vals = list(ch.evaluate_keys(seq.make_range(int(frame), 1), seq.get_display_rate()))   # bounded range only
    _req(len(vals) >= 1, "EVALUATE_EMPTY|frame=%d" % frame)
    return float(vals[0])


def _covers(section, frame):
    return ((not section.has_start_frame() or section.get_start_frame() <= frame) and
            (not section.has_end_frame() or frame < section.get_end_frame()))


def _camera_pose(seq, world, binding, spawnable, frame):
    """Spawnable: template ROOT relative transform (memory ue58-fbx-import-traps: the actor transform reads zero).
    Possessable: the resolved actor.  A covering 3D transform section overrides (keys evaluated, else defaults)."""
    if spawnable:
        actor = binding.get_object_template()
        root = actor.get_editor_property("root_component") if actor is not None else None
        _req(root is not None and root.get_attach_parent() is None, "CAMERA_TEMPLATE|%s" % binding.get_display_name())
        base = _v(root.get_editor_property("relative_location")) + _r(root.get_editor_property("relative_rotation"))
    else:
        objs = list(seq.locate_bound_objects(binding, world))
        _req(len(objs) == 1, "CAMERA_RESOLVE|%s|%d" % (binding.get_display_name(), len(objs)))
        _req(objs[0].get_attach_parent_actor() is None, "CAMERA_ATTACHED|%s" % binding.get_display_name())
        base = _v(objs[0].get_actor_location()) + _r(objs[0].get_actor_rotation())
    tracks = [t for t in binding.get_tracks() if str(t.get_class().get_name()) == "MovieScene3DTransformTrack"]
    _req(len(tracks) <= 1, "CAMERA_TRANSFORM_TRACKS|%d" % len(tracks))
    vals, source, names = list(base), "template" if spawnable else "level_actor", None
    if tracks:
        secs = [s for s in tracks[0].get_sections() if s.is_active() and _covers(s, frame)]
        _req(len(secs) <= 1, "CAMERA_TRANSFORM_SECTIONS|%d" % len(secs))
        if secs:
            chans = list(secs[0].get_all_channels())
            _req(len(chans) >= 6, "CAMERA_CHANNELS|%d" % len(chans))
            names = [str(c.get_name()) for c in chans[:6]]           # recorded so a reader can check the order
            vals = [_channel_value(chans[i], seq, frame, base[i]) for i in range(6)]
            source = "track"
    return {"frame": int(frame), "location": vals[:3], "rotation": vals[3:6], "source": source, "channels": names}


def _clam_cameras(world, a):
    """Root camera-cut sections of LS_DevScene_03 at each beat frame -> camera poses at the cut's start, middle and
    last frame.  Refuses a beat covered by a sub-sequence that has its own cut track (nested cuts outrank root cuts,
    memory puss-camera-handover-facts)."""
    seq = unreal.load_asset(SCENE3)
    _req(isinstance(seq, unreal.LevelSequence), "SCENE3_LOAD")
    bindings = {_guid(b.get_id()): b for b in seq.get_bindings()}
    spawn_ids = {_guid(b.get_id()) for b in seq.get_spawnables()}
    tracks = list(seq.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    _req(len(tracks) == 1, "CUT_TRACK_COUNT|%d" % len(tracks))
    markers = {}
    for m in unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(seq, unreal.MovieSceneTimeUnit.DISPLAY_RATE):
        markers[str(m.label)] = int(m.frame_number.value)
    subs = {}
    for cls in (unreal.MovieSceneSubTrack, unreal.MovieSceneCinematicShotTrack):
        for t in seq.find_tracks_by_type(cls):
            for s in t.get_sections():
                subs[_path(s)] = s
    rows = []
    for beat, frame in sorted(a["camera_beats"].items()):
        frame = int(frame)
        nested = []
        for s in subs.values():
            if s.is_active() and _covers(s, frame):
                sub = s.get_sequence()
                if sub is not None and list(sub.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)):
                    nested.append(_path(sub))
        _req(not nested, "NESTED_CUT_AT_BEAT|%s|%s" % (beat, nested))
        cands = [s for s in tracks[0].get_sections() if s.is_active() and _covers(s, frame)]
        _req(cands, "NO_CUT_AT_BEAT|%s|%d" % (beat, frame))
        sec = max(cands, key=lambda s: s.get_start_frame() if s.has_start_frame() else -10 ** 9)   # latest start wins
        _req(sec.has_start_frame() and sec.has_end_frame(), "CUT_UNBOUNDED|%s" % beat)
        a0, a1 = int(sec.get_start_frame()), int(sec.get_end_frame())
        guid = _guid(sec.get_camera_binding_id().get_editor_property("guid"))
        b = bindings.get(guid)
        _req(b is not None, "CUT_BINDING_MISSING|%s|%s" % (beat, guid))
        frames = sorted({max(a0, frame), (a0 + a1) // 2, a1 - 1})
        rows.append({"beat": beat, "frame": frame, "cut_range": [a0, a1], "binding": str(b.get_display_name()),
                     "guid": guid, "spawnable": guid in spawn_ids,
                     "marker": sorted(k for k, v in markers.items() if v == frame),
                     "samples": [_camera_pose(seq, world, b, guid in spawn_ids, f) for f in frames]})
    return {"ok": True, "sequence": SCENE3, "rows": rows}


def live_clam_state(world, a):
    idx = _index(world)
    root = _one(idx, ROOT_LABEL)
    with open(APPLY_RECORD, encoding="utf-8") as h:
        mill = json.load(h)
    _req(mill.get("applied") and mill.get("actor_path"), "STONE_RECORD_NOT_APPLIED")
    stone = _by_path(world, mill["actor_path"])
    st = {"label": mill["plan"]["label"], "object_path": mill["actor_path"], "record_location": mill["plan"]["location"],
          "record_top_z": mill["plan"]["top_z"], "found": stone is not None and
          str(stone.get_actor_label()) == mill["plan"]["label"]}
    if st["found"]:
        st["location"], st["rotation"] = _v(stone.get_actor_location()), _r(stone.get_actor_rotation())
        rise = unreal.load_asset(RISE)
        _req(isinstance(rise, unreal.LevelSequence), "RISE_LOAD")
        rows = [b for b in rise.get_bindings() if _guid(b.get_id()) == mill.get("reveal_binding_guid")]
        if len(rows) == 1:
            st["reveal_binding"] = {"guid": mill["reveal_binding_guid"],
                                    "resolved": [_path(o) for o in rise.locate_bound_objects(rows[0], world)],
                                    "visibility_sections": _visibility_sections(rows[0], _fps(rise))}
    state = {"root": {"world": _world_tf(root)}, "stone": st,
             "temp_actors": sorted(k for k in idx if k.startswith("ZZ_") or "TEMP" in k.upper()),
             "label_count": {lab: len(idx.get(lab, [])) for lab in CLAM_LABELS.values()},
             "assets": {p: bool(unreal.EditorAssetLibrary.does_asset_exist(p)) for p in
                        [clam_mesh_path(x) for x in CLAM_PART_ORDER] + [clam_mi_path(m) for m in CLAM_MATERIALS]},
             "meshes": {}, "standins": []}
    for part in CLAM_PART_ORDER:
        if state["assets"][clam_mesh_path(part)]:
            mesh = unreal.load_asset(clam_mesh_path(part))
            _req(isinstance(mesh, unreal.StaticMesh), "MESH_LOAD|%s" % part)
            bb = mesh.get_bounding_box()
            state["meshes"][part] = {"bounds": {"min": _v(bb.min), "max": _v(bb.max)},
                                     "slots": [str(m.get_editor_property("material_slot_name"))
                                               for m in mesh.get_editor_property("static_materials")]}
    for label in a["standin_labels"]:
        rows = idx.get(label, [])
        row = {"label": label, "count": len(rows)}
        if len(rows) == 1:
            row.update({"object_path": _path(rows[0]), "class": str(rows[0].get_class().get_name()),
                        "flags": _prim_flags(rows[0])})
        state["standins"].append(row)
    try:
        state["cameras"] = _clam_cameras(world, a)
    except Exception as exc:  # noqa: BLE001  (recorded; the plan refuses without an explicit yaw)
        state["cameras"] = {"ok": False, "error": str(exc)[:400]}
    with open(MILL_MEASURE, encoding="utf-8") as h:
        state["measure"] = json.load(h)
    return state


def _spawn_part(op, parent_actor):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*op["location"]),
                                   unreal.Rotator(roll=op["rotation"][0], pitch=op["rotation"][1], yaw=op["rotation"][2]),
                                   False)
    _req(a is not None, "SPAWN_FAILED|%s" % op["part"])
    a.set_actor_label(op["label"])
    c = a.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    mesh = unreal.load_asset(op["mesh"])
    _req(isinstance(mesh, unreal.StaticMesh), "ASSET_LOAD|%s" % op["mesh"])
    c.set_static_mesh(mesh)
    for i, mi_path in sorted(op["mis"].items(), key=lambda kv: int(kv[0])):
        mi = unreal.load_asset(mi_path)
        _req(mi is not None, "ASSET_LOAD|%s" % mi_path)
        c.set_material(int(i), mi)
    c.set_mobility(getattr(unreal.ComponentMobility, op["mobility"]))
    if not bool(c.get_editor_property("evaluate_world_position_offset")):        # StaticMeshComponent.h:172-176 [decl]
        c.set_evaluate_world_position_offset(True)
    a.set_editor_property("tags", [unreal.Name(t) for t in op["tags"]])
    a.set_folder_path(op["folder"])
    a.set_actor_hidden_in_game(bool(op["actor_hidden_in_game"]))
    if parent_actor is not None:
        rule = unreal.AttachmentRule.KEEP_WORLD
        a.attach_to_actor(parent_actor, "", rule, rule, rule, False)              # return value not trusted
    _check_part(a, op, parent_actor)
    return a


def _check_part(a, op, parent_actor):
    c = a.static_mesh_component
    _req(str(a.get_actor_label()) == op["label"], "PART_LABEL|%s" % op["part"])
    _req(_path(c.get_editor_property("static_mesh")).split(".")[0] == op["mesh"], "READBACK_MESH|%s" % op["part"])
    for i, mi_path in op["mis"].items():
        _req(_path(c.get_material(int(i))).split(".")[0] == mi_path, "READBACK_MI|%s|%s" % (op["part"], i))
    _req(_enum_name(c.get_editor_property("mobility")) == op["mobility"], "READBACK_MOBILITY|%s" % op["part"])
    _req(bool(c.get_editor_property("evaluate_world_position_offset")), "READBACK_WPO_EVAL|%s" % op["part"])
    _req(bool(a.get_editor_property("hidden")) == bool(op["actor_hidden_in_game"]), "READBACK_HIDDEN|%s" % op["part"])
    tf = _world_tf(a)
    _req(near(tf["location"], op["location"], TOL_CM), "PART_LOCATION|%s|%s" % (op["part"], tf["location"]))
    _req(near([_wrap(x) for x in tf["rotation"]], [_wrap(x) for x in op["rotation"]], 0.01),
         "PART_ROTATION|%s|%s" % (op["part"], tf["rotation"]))
    _req(near(tf["scale"], [1, 1, 1], 1e-6), "PART_SCALE|%s" % op["part"])
    par = a.get_attach_parent_actor()
    if parent_actor is None:
        _req(par is None, "ROOT_ATTACHED|%s" % _path(par))
    else:
        _req(par is not None and _path(par) == _path(parent_actor), "NOT_ATTACHED|%s|%s" % (op["part"], _path(par)))
        rl = _v(c.get_editor_property("relative_location"))
        rr = _r(c.get_editor_property("relative_rotation"))
        _req(near(rl, op["rel"]["location"], TOL_CM), "REL_LOCATION|%s|%s" % (op["part"], rl))
        _req(near([_wrap(x) for x in rr], op["rel"]["rotation"], 0.01), "REL_ROTATION|%s|%s" % (op["part"], rr))
        if op["part"] == "Lid":    # the pivot IS the hinge: lid origin == root * hinge (1 cm, brief)
            hinge = tf_point(_world_tf(parent_actor), op["rel"]["location"])
            _req(near(tf["location"], hinge, 1.0), "HINGE_PIVOT|%s|%s" % (tf["location"], hinge))


def _verify_clam(world, record):
    plan = record["plan"]
    ops = clam_apply_ops(plan)
    actors = {}
    for op in [o for o in ops if o["op"] == "spawn"]:
        a = _by_path(world, record["actor_paths"].get(op["part"]))
        _req(a is not None, "PART_MISSING|%s" % op["part"])
        actors[op["part"]] = a
        _check_part(a, op, actors.get(op["parent"]) if op["parent"] else None)
    for part, guid in (record.get("reveal_binding_guids") or {}).items():
        _verify_reveal(world, guid, actors[part], plan["reveal"]["section"])
    _req(sorted((record.get("reveal_binding_guids") or {})) == sorted(plan["reveal"]["targets"]), "REVEAL_SET")
    for r in plan["standins"]["rows"]:
        s = _by_path(world, r["object_path"])
        _req(s is not None and _prim_flags(s) == json.loads(json.dumps(r["after"])), "STANDIN_FLAGS|%s" % r["label"])
    root = _one(_index(world), ROOT_LABEL)
    for part, a in actors.items():
        _req(box_inside(box_local(_world_tf(root), _box(a)), GUARD_LOCAL, tol=2.0), "OUTSIDE_LANDED_BOX|%s" % part)


def run_clam_apply(run, args, world):
    a = dict(CLAM_DEFAULTS, **(args.get("apply_clam") or {}))
    man = json.load(open(CLAM_MANIFEST, encoding="utf-8"))
    state = live_clam_state(world, a)
    plan = plan_clam(state, a, man)
    record = {"run": run, "world": WORLD, "rise": RISE, "plan": plan, "saved": False, "applied": False,
              "actor_paths": {}, "reveal_binding_guids": {}, "census_before": _census(),
              "manifest_sha256": sha256_file(CLAM_MANIFEST)}
    _write(CLAM_RECORD, record, exclusive=True)                         # RECORD FIRST
    unreal.log("S3CLAM_RECORD|run=%s|path=%s" % (run, CLAM_RECORD))
    record["backup"] = _backup(BACKUP_ROOT_CLAM, run, (CLAM_RECORD,))
    _write(CLAM_RECORD, record)
    actors = {}
    for op in clam_apply_ops(plan):
        if op["op"] == "spawn":
            actors[op["part"]] = _spawn_part(op, actors.get(op["parent"]) if op["parent"] else None)
            record["actor_paths"][op["part"]] = _path(actors[op["part"]])
            _write(CLAM_RECORD, record)
        elif op["op"] == "add_reveal":
            record["reveal_binding_guids"][op["part"]] = _add_reveal(world, actors[op["part"]], op["section"])
            _write(CLAM_RECORD, record)
        elif op["op"] == "set_prim_flags":
            _set_prim_flags(_by_path(world, op["object_path"]), op["flags"])
    actors = None
    _verify_clam(world, record)
    _save(world, [RISE] if record["reveal_binding_guids"] else [])
    record["saved"] = True
    _write(CLAM_RECORD, record)
    _verify_clam(world, record)                                       # fresh lookups, after the save
    record["applied"] = True
    _write(CLAM_RECORD, record)
    return {"root": record["actor_paths"]["Bottom"], "root_location": plan["root_location"], "yaw": plan["yaw"],
            "yaw_source": plan["yaw_source"], "lid_open_rpy": plan["lid"]["open_relative_rotation_rpy"],
            "reveal_guids": record["reveal_binding_guids"], "standins": plan["standins"]["action"],
            "backup": record["backup"]}


def run_clam_revert(run, world):
    with open(CLAM_RECORD, encoding="utf-8") as h:
        record = json.load(h)
    _req(record.get("saved") and record.get("actor_paths"), "RECORD_INVALID")
    _verify_clam(world, record)                                       # drift since APPLY -> refuse before mutating
    backup = _backup(BACKUP_ROOT_CLAM, run + "-REVERT", (CLAM_RECORD,))
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for op in clam_revert_ops(record):
        if op["op"] == "set_prim_flags":
            _set_prim_flags(_by_path(world, op["object_path"]), op["flags"])
        elif op["op"] == "remove_reveal":
            _remove_reveal(world, op["guid"], op["actor_path"])
        elif op["op"] == "destroy":
            a = _by_path(world, op["actor_path"])
            _req(a is not None and str(a.get_actor_label()) == op["label"], "DESTROY_TARGET|%s" % op["part"])
            _req(eas.destroy_actor(a), "DESTROY|%s" % op["part"])
            a = None
            _req(_by_path(world, op["actor_path"]) is None, "DESTROY_SURVIVED|%s" % op["part"])
    _save(world, [RISE] if record.get("reveal_binding_guids") else [])
    for r in record["plan"]["standins"]["rows"]:
        s = _by_path(world, r["object_path"])
        _req(s is not None and _prim_flags(s) == json.loads(json.dumps(r["before"])), "REVERT_STANDIN|%s" % r["label"])
    for part, p in record["actor_paths"].items():
        _req(_by_path(world, p) is None, "REVERT_ACTOR_PRESENT|%s" % part)
    rise = unreal.load_asset(RISE)
    left = {_guid(b.get_id()) for b in rise.get_bindings()} & set((record.get("reveal_binding_guids") or {}).values())
    _req(not left, "REVERT_BINDINGS_LEFT|%s" % sorted(left))
    os.replace(CLAM_RECORD, CLAM_RECORD + ".reverted-" + run)
    return {"backup": backup}


# ------------------------------------------------------------------------------------------- Pearl v2 glue
def _asset_path(o):
    return _path(o).split(".")[0] if o is not None else None


def _pearl_live(world, with_tracks=True):
    idx = _index(world)
    rows = idx.get(CLAM_LABELS["Pearl"], [])
    out = {"count": len(rows)}
    if len(rows) != 1:
        return out, None
    a = rows[0]
    c = _smc(a)
    par = a.get_attach_parent_actor()
    out.update({"label": str(a.get_actor_label()), "object_path": _path(a), "parent_path": _path(par),
                "mesh": _asset_path(c.get_editor_property("static_mesh")),
                "materials": [_asset_path(c.get_material(i)) for i in range(int(c.get_num_materials()))],
                "override_materials": [_asset_path(m) for m in c.get_editor_property("override_materials")],
                "rel": {"location": _v(c.get_editor_property("relative_location")),
                        "rotation": _r(c.get_editor_property("relative_rotation")),
                        "scale": _v(c.get_editor_property("relative_scale3d"))},
                "world": _world_tf(a), "hidden": bool(a.get_editor_property("hidden")),
                "wpo_eval": bool(c.get_editor_property("evaluate_world_position_offset"))})
    eal = unreal.EditorAssetLibrary
    v2_mesh, v2_mi = clam_mesh_path(PEARL_V2), clam_mi_path(PEARL_V2)
    out["assets"] = {p: bool(eal.does_asset_exist(p)) for p in (v2_mesh, v2_mi)}
    out["v2_slots"] = None
    if out["assets"][v2_mesh]:
        m = unreal.load_asset(v2_mesh)
        _req(isinstance(m, unreal.StaticMesh), "V2_MESH_LOAD")
        out["v2_slots"] = [str(s.get_editor_property("material_slot_name")) for s in m.get_editor_property("static_materials")]
    if with_tracks:
        out["tracks"] = {p: _sequence_tracks(unreal.load_asset(p), world, a) for p in CLAM_SEQUENCES}
    return out, a


def _set_mesh_material(world, op):
    a = _by_path(world, op["object_path"])
    _req(a is not None and str(a.get_actor_label()) == CLAM_LABELS["Pearl"], "PEARL_TARGET|%s" % op["object_path"])
    c = _smc(a)
    mesh, mi = unreal.load_asset(op["mesh"]), unreal.load_asset(op["material0"])
    _req(isinstance(mesh, unreal.StaticMesh) and mi is not None, "ASSET_LOAD|%s|%s" % (op["mesh"], op["material0"]))
    a.modify()
    c.modify()
    c.set_static_mesh(mesh)                         # return values not trusted: read back by the caller
    c.set_material(0, mi)


def _pearl_check(world, want):
    live, _a = _pearl_live(world, with_tracks=False)
    _req(live["count"] == 1, "PEARL_COUNT_AFTER|%d" % live["count"])
    probs = pearl_state_problems(live, want)
    _req(not probs, "PEARL_READBACK|%s" % ";".join(probs))
    return live


def run_pearl_swap(run, args, world):
    with open(CLAM_RECORD, encoding="utf-8") as h:
        clam = json.load(h)
    live, _a = _pearl_live(world)
    _a = None
    plan = pearl_swap_plan(clam, live, args.get("pearl_swap"))
    record = {"run": run, "world": WORLD, "plan": plan, "clam_record_run": clam.get("run"), "census_before": _census(),
              "saved": False, "applied": False}
    _write(PEARL_SWAP_RECORD, record, exclusive=True)                  # RECORD FIRST (old mesh + material paths)
    unreal.log("S3PEARL_RECORD|run=%s|path=%s|old_mesh=%s|old_mi=%s" % (
        run, PEARL_SWAP_RECORD, plan["before"]["mesh"], plan["before"]["materials"][0]))
    record["backup"] = _backup(BACKUP_ROOT_PEARL, run, (PEARL_SWAP_RECORD,))
    _write(PEARL_SWAP_RECORD, record)
    for op in pearl_swap_ops(plan):
        _set_mesh_material(world, op)
    _pearl_check(world, plan["after"])
    _save(world, [])                                                   # map only (census-exact)
    record["saved"] = True
    _write(PEARL_SWAP_RECORD, record)
    got = _pearl_check(world, plan["after"])                           # fresh lookup after the save
    record["applied"], record["after_readback"] = True, got
    _write(PEARL_SWAP_RECORD, record)
    return {"actor": plan["object_path"], "mesh": got["mesh"], "mi": got["materials"][0],
            "rel_location": got["rel"]["location"], "backup": record["backup"]}


def run_pearl_unswap(run, world):
    with open(PEARL_SWAP_RECORD, encoding="utf-8") as h:
        record = json.load(h)
    _req(record.get("saved") and record.get("applied"), "SWAP_RECORD_INVALID")
    plan = record["plan"]
    _pearl_check(world, plan["after"])                                 # drift since the swap -> refuse before mutating
    backup = _backup(BACKUP_ROOT_PEARL, run + "-UNSWAP", (PEARL_SWAP_RECORD,))
    for op in pearl_unswap_ops(record):
        _set_mesh_material(world, op)
    _pearl_check(world, plan["before"])
    _save(world, [])
    got = _pearl_check(world, plan["before"])
    os.replace(PEARL_SWAP_RECORD, PEARL_SWAP_RECORD + ".unswapped-" + run)
    return {"actor": plan["object_path"], "mesh": got["mesh"], "mi": got["materials"][0], "backup": backup}


def _current_log_lines():
    d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_log_dir())
    logs = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".log") and "backup" not in f.lower()]
    _req(logs, "NO_LOG|%s" % d)
    newest = max(logs, key=os.path.getmtime)
    with open(newest, encoding="utf-8", errors="replace") as h:
        return newest, h.readlines()


def run_pearl_mat_check(run):
    """Read-only, a LATER call than BUILD_MAT Pearl_v2: params read back again + log scan for compile failures."""
    mel = unreal.MaterialEditingLibrary
    m = CLAM_EXTRA_MATERIALS[PEARL_V2]
    spec = material_specs()[PEARL_V2_MASTER]
    mat = unreal.load_asset(PEARL_V2_MASTER)
    mi = unreal.load_asset(clam_mi_path(PEARL_V2))
    _req(isinstance(mat, unreal.Material) and mi is not None, "V2_MATERIAL_LOAD")
    _verify_material(mat, spec)
    _req(_path(mi.get_editor_property("parent")) == _path(mat), "MI_PARENT")
    nacre = tex_target(CLAM, "Pearl", "Nacre")["asset"]
    _req(_asset_path(mel.get_material_instance_texture_parameter_value(mi, "Nacre")) == nacre, "MI_NACRE")
    scal = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in spec["scalars"]}
    want = dict(spec["scalars"], **m["scalars"])
    _req(all(abs(scal[k] - want[k]) < 1e-4 for k in want), "MI_SCALARS|%s" % scal)
    stats = {}
    try:                                    # [inf] MaterialEditingLibrary.get_statistics; recorded, not gated
        s = mel.get_statistics(mat)
        stats = {"ps": int(s.get_editor_property("num_pixel_shader_instructions")),
                 "vs": int(s.get_editor_property("num_vertex_shader_instructions"))}
    except Exception as exc:  # noqa: BLE001
        stats = {"error": str(exc)[:200]}
    log, lines = _current_log_lines()
    named, unattributed = compile_log_problems(lines, ["M_PearlClam_Pearl_v2", "MI_PearlClam_Pearl_v2"])
    _req(not named, "COMPILE_ERRORS|%s" % named[:5])
    built = [ln for ln in lines if "S3PROPS_BUILD_MAT_OK" in ln and "MI_PearlClam_Pearl_v2" in ln]
    rec = {"run": run, "log": log, "build_marker_in_log": bool(built), "named_errors": named,
           "unattributed_failed_to_compile": unattributed[-10:], "stats": stats, "scalars": scal}
    _write(HERE + "s3_pearl_v2_mat_check_%s.json" % run, rec)
    return rec


# ------------------------------------------------------------------------------------------- clam look glue
def run_clam_look_mat_check(run, key):
    """Read-only, a LATER call than BUILD_MAT <key>: master spec + shading model + connected properties read back, MI
    parent / textures / scalars vs the BUILD_MAT record, then the editor log scanned for compile failures."""
    mel = unreal.MaterialEditingLibrary
    _req(key in CLAM_LOOK_MATERIALS, "LOOK_MATERIAL|%r" % key)
    m = clam_material_row(key)
    spec = material_specs()[m["master"]]
    build_path = HERE + "s3_props_build_mat_PearlClam_%s.json" % key
    _req(os.path.exists(build_path), "NO_BUILD_RECORD|%s" % build_path)
    with open(build_path, encoding="utf-8") as h:
        built_rec = json.load(h)
    mat, mi = unreal.load_asset(m["master"]), unreal.load_asset(clam_mi_path(key))
    _req(isinstance(mat, unreal.Material) and mi is not None, "LOOK_MATERIAL_LOAD|%s" % key)
    _verify_material(mat, spec)
    rows = _read_props(mat, spec)
    rb = prop_readback_problems(rows, spec, None, False)
    _req(not rb or rb[0].startswith("PROP_READBACK_UNAVAILABLE"), "PROP_READBACK|%s" % rb)
    _req(_path(mi.get_editor_property("parent")) == _path(mat), "MI_PARENT")
    for param, role in spec["tex_params"].items():
        want_tex = tex_target(CLAM, m["tex_set"], role)["asset"]
        got = _asset_path(mel.get_material_instance_texture_parameter_value(mi, param))
        _req(got == want_tex, "MI_TEX|%s|%s want %s" % (param, got, want_tex))
    scal = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in spec["scalars"]}
    _req(all(abs(scal[k] - float(built_rec["scalars"][k])) < 1e-4 for k in spec["scalars"]),
         "MI_SCALARS_VS_BUILD|%s|%s" % (scal, built_rec["scalars"]))
    stats = {}
    try:                                    # [inf] MaterialEditingLibrary.get_statistics (MaterialEditingLibrary.h:610)
        s = mel.get_statistics(mat)
        stats = {"ps": int(s.get_editor_property("num_pixel_shader_instructions")),
                 "vs": int(s.get_editor_property("num_vertex_shader_instructions"))}
    except Exception as exc:  # noqa: BLE001
        stats = {"error": str(exc)[:200]}
    mat, mi = None, None
    log, lines = _current_log_lines()
    names = [m["master"].rsplit("/", 1)[1], m["mi"]]
    named, unattributed = compile_log_problems(lines, names)
    _req(not named, "COMPILE_ERRORS|%s" % named[:5])
    built = [ln for ln in lines if "S3PROPS_BUILD_MAT_OK" in ln and m["mi"] in ln]
    rec = {"run": run, "material": key, "log": log, "build_marker_in_log": bool(built), "named_errors": named,
           "unattributed_failed_to_compile": unattributed[-10:], "stats": stats, "scalars": scal,
           "prop_readback": rows, "prop_readback_unavailable": bool(rb), "shading_model": spec.get("shading_model")}
    _write(HERE + "s3_clam_look_mat_check_%s_%s.json" % (key, run), rec)
    return rec


def _look_actor_live(world, idx, part, with_tracks=True):
    rows = idx.get(CLAM_LABELS[part], [])
    out = {"count": len(rows)}
    if len(rows) != 1:
        return out
    a = rows[0]
    c = _smc(a)
    out.update({"label": str(a.get_actor_label()), "object_path": _path(a),
                "parent_path": _path(a.get_attach_parent_actor()),
                "mesh": _asset_path(c.get_editor_property("static_mesh")),
                "materials": [_asset_path(c.get_material(i)) for i in range(int(c.get_num_materials()))],
                "override_materials": [_asset_path(m) for m in c.get_editor_property("override_materials")],
                "rel": {"location": _v(c.get_editor_property("relative_location")),
                        "rotation": _r(c.get_editor_property("relative_rotation")),
                        "scale": _v(c.get_editor_property("relative_scale3d"))},
                "world": _world_tf(a), "hidden": bool(a.get_editor_property("hidden")),
                "wpo_eval": bool(c.get_editor_property("evaluate_world_position_offset"))})
    if with_tracks:
        out["tracks"] = {p: _sequence_tracks(unreal.load_asset(p), world, a) for p in CLAM_SEQUENCES}
    return out


def _look_live(world, look, with_tracks=True):
    row = CLAM_LOOKS[look]
    mel, eal = unreal.MaterialEditingLibrary, unreal.EditorAssetLibrary
    idx = _index(world)
    actors = {p: _look_actor_live(world, idx, p, with_tracks) for p in row["targets"]}
    idx = None
    old_mi, new_mi = clam_mi_path(row["from_material"]), clam_mi_path(look)
    master = clam_material_row(look)["master"]
    live = {"actors": {p: {k: v for k, v in s.items() if k != "tracks"} for p, s in actors.items()},
            "tracks": {p: s.get("tracks") for p, s in actors.items()},
            "assets": {p: bool(eal.does_asset_exist(p)) for p in (old_mi, new_mi, master)}, "mesh_slots": {}, "breath": {}}
    for part in row["targets"]:
        mesh = clam_mesh_path(row["mesh_part"][part])
        if mesh not in live["mesh_slots"] and eal.does_asset_exist(mesh):
            sm = unreal.load_asset(mesh)
            _req(isinstance(sm, unreal.StaticMesh), "LOOK_MESH_LOAD|%s" % mesh)
            live["mesh_slots"][mesh] = [str(s.get_editor_property("material_slot_name"))
                                        for s in sm.get_editor_property("static_materials")]
    if row["breathes"]:
        for p in (old_mi, new_mi):
            if live["assets"][p]:
                mi = unreal.load_asset(p)
                _req(mi is not None, "LOOK_MI_LOAD|%s" % p)
                live["breath"][p] = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in BREATH_PARAMS}
    return live


def _set_slot_material(world, op):
    a = _by_path(world, op["object_path"])
    _req(a is not None and str(a.get_actor_label()) == CLAM_LABELS[op["part"]], "LOOK_TARGET|%s" % op["object_path"])
    c = _smc(a)
    mi = unreal.load_asset(op["material"])
    _req(mi is not None, "ASSET_LOAD|%s" % op["material"])
    _req(0 <= int(op["slot"]) < int(c.get_num_materials()), "LOOK_SLOT_RANGE|%s|%s" % (op["part"], op["slot"]))
    a.modify()
    c.modify()
    c.set_material(int(op["slot"]), mi)             # return value not trusted: read back by the caller


def _look_check(world, look, targets, which):
    idx = _index(world)
    actors = {t["part"]: _look_actor_live(world, idx, t["part"], with_tracks=False) for t in targets}
    idx = None
    probs = clam_look_state_problems(actors, targets, which)
    _req(not probs, "LOOK_READBACK|%s|%s|%s" % (look, which, ";".join(probs)))
    return actors


def run_clam_look_swap(run, args, world):
    look = args["look"]
    path = look_record_path(look)
    with open(CLAM_RECORD, encoding="utf-8") as h:
        clam = json.load(h)
    live = _look_live(world, look)
    plan = clam_look_swap_plan(look, clam, live, args.get("look_swap"))
    record = {"run": run, "world": WORLD, "look": look, "plan": plan, "clam_record_run": clam.get("run"),
              "census_before": _census(), "saved": False, "applied": False}
    _write(path, record, exclusive=True)                               # RECORD FIRST (old MI per slot)
    unreal.log("S3CLAMLOOK_RECORD|run=%s|look=%s|path=%s|old_mi=%s|slots=%s" % (
        run, look, path, plan["old_mi"], [(t["part"], t["slot"]) for t in plan["targets"]]))
    record["backup"] = _backup(BACKUP_ROOT_LOOK, run, (path,))
    _write(path, record)
    for op in clam_look_swap_ops(plan):
        _set_slot_material(world, op)
    _look_check(world, look, plan["targets"], "after")
    _save(world, [])                                                   # map only (census-exact)
    record["saved"] = True
    _write(path, record)
    got = _look_check(world, look, plan["targets"], "after")           # fresh lookup after the save
    record["applied"], record["after_readback"] = True, got
    _write(path, record)
    return {"look": look, "mi": plan["new_mi"], "targets": [(t["part"], t["slot"]) for t in plan["targets"]],
            "breath": plan["breath"], "backup": record["backup"]}


def run_clam_look_unswap(run, args, world):
    look = args["look"]
    path = look_record_path(look)
    with open(path, encoding="utf-8") as h:
        record = json.load(h)
    _req(record.get("saved") and record.get("applied") and record.get("look") == look, "LOOK_RECORD_INVALID|%s" % path)
    plan = record["plan"]
    _look_check(world, look, plan["targets"], "after")                 # drift since the swap -> refuse before mutating
    ops = clam_look_unswap_ops(record)
    backup = _backup(BACKUP_ROOT_LOOK, run + "-UNSWAP", (path,))
    for op in ops:
        _set_slot_material(world, op)
    _look_check(world, look, plan["targets"], "before")
    _save(world, [])
    _look_check(world, look, plan["targets"], "before")
    os.replace(path, path + ".unswapped-" + run)
    return {"look": look, "restored_mi": plan["old_mi"], "targets": [(t["part"], t["slot"]) for t in plan["targets"]],
            "backup": backup}


def run_clam_dry(run, args, world, census):
    a = dict(CLAM_DEFAULTS, **(args.get("apply_clam") or {}))
    man = json.load(open(CLAM_MANIFEST, encoding="utf-8"))
    state = live_clam_state(world, a)
    out = {"run": run, "census": census, "state": {k: v for k, v in state.items() if k != "measure"},
           "masters": {p: bool(unreal.EditorAssetLibrary.does_asset_exist(p)) for p in material_specs()},
           "textures": {"%s_%s" % (s, r): bool(unreal.EditorAssetLibrary.does_asset_exist(tex_target(CLAM, s, r)["asset"]))
                        for s in CLAM_TEX for r in CLAM_TEX[s]}}
    try:
        out["plan"] = plan_clam(state, a, man)
        out["apply"] = "would_apply"
    except PlanError as exc:
        out["apply"] = "CLAM_APPLY_WOULD_REFUSE|%s" % exc
    path = HERE + "s3_pearlclam_dry_%s.json" % run
    _write(path, out)
    return out, path


def run_dry(run, args, world, census):
    a = dict(APPLY_DEFAULTS, **(args.get("apply") or {}))
    state = live_state(world, a)
    out = {"run": run, "census": census, "state": state,
           "assets": {n: {k: unreal.EditorAssetLibrary.does_asset_exist(v) for k, v in
                          (("mesh", prop_paths(n)["mesh"]), ("mi", prop_paths(n)["mi"]))} for n in PROPS},
           "master_exists": unreal.EditorAssetLibrary.does_asset_exist(MASTER)}
    try:
        out["apply_plan"] = plan_apply(state, a)
        out["apply"] = "would_apply"
    except PlanError as exc:
        out["apply"] = "APPLY_WOULD_REFUSE|%s" % exc
    for c in state["clams"]:
        c["keyed_verdict"] = clam_keyed_verdict(c)
    path = HERE + "s3_props_dry_%s.json" % run
    _write(path, out)
    return out, path


def main():
    run = "S3PROPS-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = "?"
    try:
        with open(ARGS, encoding="utf-8") as h:
            args = json.load(h)
        run = args.get("run") or run
        pending = None
        if os.path.exists(TEX_PENDING):
            with open(TEX_PENDING, encoding="utf-8") as h:
                pending = json.load(h)
        look_swaps = [lk for lk in CLAM_LOOKS if os.path.exists(look_record_path(lk))]
        mode = check_mode(args, os.path.exists(APPLY_RECORD), os.path.exists(PLACE_RECORD), pending is not None,
                          os.path.exists(CLAM_RECORD), os.path.exists(PEARL_SWAP_RECORD), look_swaps)
        unreal.log("S3PROPS_START|run=%s|mode=%s|prop=%s" % (run, mode, args.get("prop")))
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        _req(ed.get_game_world() is None, "PIE_ACTIVE")
        world = ed.get_editor_world()
        _req(world is not None and str(world.get_outermost().get_name()) == WORLD, "WRONG_WORLD")
        census = _census()
        gate_census(census, mode, pending["asset"] if pending else None)
        if mode == "CLAM_DRY":
            out, path = run_clam_dry(run, args, world, census)
            cam = out["state"].get("cameras", {})
            unreal.log("S3CLAM_DRY_OK|run=%s|mutated=0|apply=%s|cameras=%s|yaw=%s|out=%s" % (
                run, out["apply"][:300], "OK" if cam.get("ok") else cam.get("error"),
                out.get("plan", {}).get("yaw"), path))
            return
        if mode == "PEARL_MAT_CHECK":
            r = run_pearl_mat_check(run)
            unreal.log("S3PEARL_MAT_CHECK_OK|run=%s|mutated=0|named_errors=0|unattributed=%d|build_marker=%s|stats=%s" % (
                run, len(r["unattributed_failed_to_compile"]), r["build_marker_in_log"], json.dumps(r["stats"])))
            return
        if mode == "CLAM_LOOK_MAT_CHECK":
            r = run_clam_look_mat_check(run, args["material"])
            unreal.log("S3CLAMLOOK_MAT_CHECK_OK|run=%s|material=%s|mutated=0|named_errors=0|unattributed=%d|"
                       "build_marker=%s|prop_readback_unavailable=%s|shading=%s|stats=%s" % (
                           run, r["material"], len(r["unattributed_failed_to_compile"]), r["build_marker_in_log"],
                           r["prop_readback_unavailable"], r["shading_model"], json.dumps(r["stats"])))
            return
        if mode == "DRY":
            out, path = run_dry(run, args, world, census)
            unreal.log("S3PROPS_DRY_OK|run=%s|mutated=0|apply=%s|clams=%s|out=%s" % (
                run, out["apply"], [(c["label"], c["keyed_verdict"]) for c in out["state"]["clams"]], path))
            return
        if mode == "IMPORT_MESH" and args["prop"] == CLAM:
            r = run_import_clam_part(run, args["part"], args)
            unreal.log("S3PROPS_IMPORT_MESH_OK|run=%s|mesh=%s|bounds=%s|vc=%s|centroid=%s" % (
                run, r["mesh"], json.dumps(r["bounds"]), r["has_vertex_colors"],
                json.dumps(r["centroid"]["value"]) if r["centroid"] else "SKIPPED_BY_ARGS"))
        elif mode == "IMPORT_MESH":
            r = run_import_mesh(run, args["prop"])
            unreal.log("S3PROPS_IMPORT_MESH_OK|run=%s|mesh=%s|bounds=%s" % (run, r["mesh"], json.dumps(r["bounds"])))
        elif mode == "IMPORT_TEX":
            r = run_import_tex(run, args)
            unreal.log("S3PROPS_IMPORT_TEX_PENDING|run=%s|asset=%s|settings=%s|size_now=%s|saved=0|next=VERIFY_TEX" % (
                run, r["asset"], json.dumps(r["want"]), r["import"]["size_at_import_call"]))
        elif mode == "VERIFY_TEX":
            r = run_verify_tex(run, pending)
            unreal.log("S3PROPS_VERIFY_TEX_OK|run=%s|asset=%s|size=%s|saved=1|sha256=%s" % (
                run, r["asset"], r["verified"]["size"], r["source"]["sha256"]))
        elif mode == "BUILD_MAT" and args["prop"] == CLAM:
            r = run_build_clam_mat(run, args["material"], args)
            unreal.log("S3PROPS_BUILD_MAT_OK|run=%s|mi=%s|master=%s|master_created=%s|scalars=%s|vectors=%s" % (
                run, r["mi"], r["master"], r["master_created"], json.dumps(r["scalars"]), json.dumps(r["vectors"])))
        elif mode == "CLAM_APPLY":
            try:
                r = run_clam_apply(run, args, world)
            except Exception:
                if os.path.exists(CLAM_RECORD):
                    with open(CLAM_RECORD, encoding="utf-8") as h:
                        saved = json.load(h).get("saved")
                    if not saved:
                        os.replace(CLAM_RECORD, CLAM_RECORD + ".failed-" + run)
                raise
            unreal.log("S3CLAM_APPLY_OK|run=%s|level_saved=1|dirty_after=0+0|%s" % (run, json.dumps(r)))
        elif mode == "PEARL_SWAP":
            try:
                r = run_pearl_swap(run, args, world)
            except Exception:
                if os.path.exists(PEARL_SWAP_RECORD):
                    with open(PEARL_SWAP_RECORD, encoding="utf-8") as h:
                        saved = json.load(h).get("saved")
                    if not saved:
                        os.replace(PEARL_SWAP_RECORD, PEARL_SWAP_RECORD + ".failed-" + run)
                raise
            unreal.log("S3PEARL_SWAP_OK|run=%s|level_saved=1|dirty_after=0+0|%s" % (run, json.dumps(r)))
        elif mode == "PEARL_UNSWAP":
            r = run_pearl_unswap(run, world)
            unreal.log("S3PEARL_UNSWAP_OK|run=%s|level_saved=1|dirty_after=0+0|%s" % (run, json.dumps(r)))
        elif mode == "CLAM_LOOK_SWAP":
            lpath = look_record_path(args["look"])
            try:
                r = run_clam_look_swap(run, args, world)
            except Exception:
                if os.path.exists(lpath):
                    with open(lpath, encoding="utf-8") as h:
                        saved = json.load(h).get("saved")
                    if not saved:
                        os.replace(lpath, lpath + ".failed-" + run)
                raise
            unreal.log("S3CLAMLOOK_SWAP_OK|run=%s|look=%s|level_saved=1|dirty_after=0+0|%s" % (
                run, args["look"], json.dumps(r)))
        elif mode == "CLAM_LOOK_UNSWAP":
            r = run_clam_look_unswap(run, args, world)
            unreal.log("S3CLAMLOOK_UNSWAP_OK|run=%s|look=%s|level_saved=1|dirty_after=0+0|%s" % (
                run, args["look"], json.dumps(r)))
        elif mode == "CLAM_REVERT":
            r = run_clam_revert(run, world)
            unreal.log("S3CLAM_REVERT_OK|run=%s|%s" % (run, json.dumps(r)))
        elif mode == "BUILD_MAT":
            r = run_build_mat(run, args["prop"])
            unreal.log("S3PROPS_BUILD_MAT_OK|run=%s|mi=%s|master_created=%s|scalars=%s" % (
                run, r["mi"], r["master_created"], json.dumps(r["scalars"])))
        elif mode == "APPLY":
            try:
                r = run_apply(run, args, world)
            except Exception:
                if os.path.exists(APPLY_RECORD):
                    with open(APPLY_RECORD, encoding="utf-8") as h:
                        saved = json.load(h).get("saved")
                    if not saved:
                        os.replace(APPLY_RECORD, APPLY_RECORD + ".failed-" + run)
                raise
            unreal.log("S3MILL_APPLY_OK|run=%s|level_saved=1|dirty_after=0+0|%s" % (run, json.dumps(r)))
        elif mode == "REVERT":
            r = run_revert(run, world)
            unreal.log("S3MILL_REVERT_OK|run=%s|%s" % (run, json.dumps(r)))
        elif mode == "PLACE":
            try:
                r = run_place(run, args, world)
            except Exception:
                if os.path.exists(PLACE_RECORD):
                    with open(PLACE_RECORD, encoding="utf-8") as h:
                        saved = json.load(h).get("saved")
                    if not saved:
                        os.replace(PLACE_RECORD, PLACE_RECORD + ".failed-" + run)
                raise
            unreal.log("S3PROPS_PLACE_OK|run=%s|%s" % (run, json.dumps(r)))
        elif mode == "UNPLACE":
            r = run_unplace(run, world)
            unreal.log("S3PROPS_UNPLACE_OK|run=%s|%s" % (run, json.dumps(r)))
    except Exception as exc:  # noqa: BLE001
        census = None
        try:
            census = _census()
        except Exception:  # noqa: BLE001
            pass
        unreal.log_error("S3PROPS_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            run, mode, str(exc).replace("\n", " "), json.dumps(census),
            "nothing saved unless an _OK marker printed; dirty map/assets: Don't-Save restart (never reload)"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "PREP_TEXTURES":
        print(json.dumps(run_prep_textures(), indent=1))
