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


def gate_census(census, mode):
    clean = census == {"content": [], "maps": []}
    if mode != "DRY" and not clean:
        raise PlanError("DIRTY_BEFORE|%s" % json.dumps(census))
    return clean


MODES = ("DRY", "IMPORT_MESH", "IMPORT_TEX", "BUILD_MAT", "APPLY", "REVERT", "PLACE", "UNPLACE")


def check_mode(args, apply_record_exists, place_record_exists):
    mode = str(args.get("mode", "DRY")).upper()
    _req(mode in MODES, "MODE|%s" % mode)
    if mode != "DRY":
        _req(args.get("confirm") == "%s S3PROPS" % mode, "CONFIRM_MISSING|need %r" % ("%s S3PROPS" % mode))
    if mode in ("IMPORT_MESH", "IMPORT_TEX", "BUILD_MAT"):
        _req(args.get("prop") in PROPS, "PROP|%r" % args.get("prop"))
    _req(not (mode == "APPLY" and apply_record_exists), "ALREADY_APPLIED|" + APPLY_RECORD)
    _req(not (mode == "REVERT" and not apply_record_exists), "NO_APPLY_RECORD")
    _req(not (mode == "PLACE" and place_record_exists), "ALREADY_PLACED|" + PLACE_RECORD)
    _req(not (mode == "UNPLACE" and not place_record_exists), "NO_PLACE_RECORD")
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


def graph_problems():
    nodes, edges, props = graph_spec()
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
                if pin not in code:
                    probs.append("CUSTOM_PIN_UNUSED|%s.%s" % (k, pin))
    used = {e[0] for e in edges} | {p[0] for p in props}
    probs += ["UNUSED_NODE|%s" % k for k in nodes if k not in used]
    if {p[2] for p in props} != {"MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS"}:
        probs.append("PROPS")
    if set(MASTER_TEX_PARAMS) != {k for k, (kind, _v) in nodes.items() if kind == "texture"}:
        probs.append("TEX_PARAM_TABLE")
    return probs


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
def _pipeline(asset_name):
    """Same Interchange override as S3Shore/s3_shore_ground_ue.py _pipeline (header lines cited there)."""
    p = unreal.InterchangeGenericAssetsPipeline()
    common = p.get_editor_property("common_meshes_properties")
    mesh = p.get_editor_property("mesh_pipeline")
    mat = p.get_editor_property("material_pipeline")
    tex = mat.get_editor_property("texture_pipeline") if mat else None
    _req(all(x is not None for x in (common, mesh, mat, tex)), "PIPELINE_SUBOBJECTS")
    p.set_editor_property("asset_name", asset_name)
    wanted = [(mat, "import_materials", False), (tex, "import_textures", False),
              (mesh, "import_static_meshes", True), (mesh, "import_skeletal_meshes", False),
              (mesh, "build_nanite", True), (mesh, "collision", False),
              (common, "import_lods", False), (common, "recompute_normals", False)]
    for obj, prop, val in wanted:
        obj.set_editor_property(prop, val)
    got = {}
    for obj, prop, val in wanted:
        got[prop] = obj.get_editor_property(prop)
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


def run_import_tex(run, name, roles):
    eal = unreal.EditorAssetLibrary
    p = prop_paths(name)
    roles = list(roles or TEX_ROLES)
    _req(all(r in TEX_ROLES for r in roles), "ROLES|%s" % roles)
    if name == "GraniteMillstone" and "BaseColor" in roles:
        _req(roles == ["BaseColor"], "MILLSTONE_BASECOLOR_ALONE|8K goes in its own call (memory bulk-import-oom)")
    src = {r: tex_source_check(name, r) for r in roles}
    for r in roles:
        _req(not eal.does_asset_exist(p["tex"][r]["asset"]), "TEX_EXISTS|%s" % p["tex"][r]["asset"])
    before = _folder_assets(p["folder"])
    tasks = []
    for r in roles:
        t = unreal.AssetImportTask()
        for k, v in (("filename", p["tex"][r]["file"]), ("destination_path", p["folder"]),
                     ("destination_name", p["tex"][r]["name"]), ("automated", True), ("replace_existing", False),
                     ("save", False)):
            t.set_editor_property(k, v)
        tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    new = sorted(_folder_assets(p["folder"]) - before)
    want = sorted(p["tex"][r]["asset"] for r in roles)
    _req(new == want, "STRAY_OR_MISSING|got=%s|want=%s" % (new, want))
    got = {}
    for r in roles:
        _suffix, comp, srgb, flip, sampler = TEX_ROLES[r]
        tex = unreal.load_asset(p["tex"][r]["asset"])
        _req(isinstance(tex, unreal.Texture2D), "TEX_LOAD|%s" % r)
        tex.modify()
        tex.set_editor_property("compression_settings", getattr(unreal.TextureCompressionSettings, comp))
        tex.set_editor_property("srgb", srgb)
        tex.set_editor_property("flip_green_channel", flip)
        g = {"compression": _enum_name(tex.get_editor_property("compression_settings")),
             "srgb": bool(tex.get_editor_property("srgb")), "flip_green": bool(tex.get_editor_property("flip_green_channel")),
             "size": [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())], "source": src[r]}
        _req(g["compression"] == comp and g["srgb"] == srgb and g["flip_green"] == flip, "TEX_READBACK|%s|%s" % (r, g))
        _req(g["size"] == [src[r]["w"], src[r]["h"]], "TEX_SIZE|%s|%s" % (r, g["size"]))
        got[r] = g
    _req(_census() == {"content": want, "maps": []}, "DIRTY_SCOPE|%s" % _census())
    for a in want:
        _req(eal.save_asset(a, only_if_is_dirty=False), "SAVE|%s" % a)
    _req(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    unreal.SystemLibrary.collect_garbage()
    rec = {"run": run, "prop": name, "textures": got, "saved": True}
    _write(HERE + "s3_props_import_tex_%s_%s.json" % (name, "-".join(roles)), rec)
    return rec


def _build_master(textures):
    """Create-only (pattern S3Shore BUILD_MAT).  textures: role -> Texture2D used as parameter defaults."""
    mel = unreal.MaterialEditingLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(MASTER.rsplit("/", 1)[1], ASSET_ROOT, unreal.Material, unreal.MaterialFactoryNew())
    _req(mat is not None, "MASTER_CREATE")
    mat.modify()
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("used_with_nanite", True)
    nodes, edges, props = graph_spec()
    made = {}
    for i, (key, (kind, v)) in enumerate(nodes.items()):
        if kind == "texture":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -900, -400 + 300 * i)
            _req(n is not None, "NODE|" + key)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("texture", textures[v])
            n.set_editor_property("sampler_type", getattr(unreal.MaterialSamplerType, TEX_ROLES[v][4]))
        elif kind == "scalar":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -900, 600 + 80 * i)
            _req(n is not None, "NODE|" + key)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("default_value", float(v))
        else:
            code, ins, _t = v
            n = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -400, 300)
            _req(n is not None, "NODE|" + key)
            n.set_editor_property("code", code)
            n.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
            cis = []
            for nm in ins:
                ci = unreal.CustomInput()
                ci.set_editor_property("input_name", nm)
                cis.append(ci)
            n.set_editor_property("inputs", cis)
            _req([str(c.get_editor_property("input_name")) for c in n.get_editor_property("inputs")] == ins, "CUSTOM_INPUTS")
        made[key] = n
    for s, o, d, pin in edges:
        _req(mel.connect_material_expressions(made[s], o, made[d], pin), "LINK|%s.%s->%s.%s" % (s, o, d, pin))
    for s, o, prop in props:
        _req(mel.connect_material_property(made[s], o, getattr(unreal.MaterialProperty, prop)), "PROP|" + prop)
    errors = [str(e) for e in (mel.recompile_material(mat) or [])]
    _req(not errors, "RECOMPILE|%s" % errors)
    return mat


def _verify_master(mat):
    mel = unreal.MaterialEditingLibrary
    tp = sorted(str(x) for x in mel.get_texture_parameter_names(mat))
    sp = sorted(str(x) for x in mel.get_scalar_parameter_names(mat))
    _req(tp == sorted(MASTER_TEX_PARAMS), "MASTER_TEX_PARAMS|%s" % tp)
    _req(sp == sorted(MASTER_SCALARS), "MASTER_SCALARS|%s" % sp)
    _req(bool(mat.get_editor_property("used_with_nanite")), "MASTER_NANITE_USAGE")


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
        mode = check_mode(args, os.path.exists(APPLY_RECORD), os.path.exists(PLACE_RECORD))
        unreal.log("S3PROPS_START|run=%s|mode=%s|prop=%s" % (run, mode, args.get("prop")))
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        _req(ed.get_game_world() is None, "PIE_ACTIVE")
        world = ed.get_editor_world()
        _req(world is not None and str(world.get_outermost().get_name()) == WORLD, "WRONG_WORLD")
        census = _census()
        gate_census(census, mode)
        if mode == "DRY":
            out, path = run_dry(run, args, world, census)
            unreal.log("S3PROPS_DRY_OK|run=%s|mutated=0|apply=%s|clams=%s|out=%s" % (
                run, out["apply"], [(c["label"], c["keyed_verdict"]) for c in out["state"]["clams"]], path))
            return
        if mode == "IMPORT_MESH":
            r = run_import_mesh(run, args["prop"])
            unreal.log("S3PROPS_IMPORT_MESH_OK|run=%s|mesh=%s|bounds=%s" % (run, r["mesh"], json.dumps(r["bounds"])))
        elif mode == "IMPORT_TEX":
            r = run_import_tex(run, args["prop"], args.get("textures"))
            unreal.log("S3PROPS_IMPORT_TEX_OK|run=%s|prop=%s|%s" % (run, args["prop"], json.dumps(
                {k: [v["compression"], v["srgb"], v["size"]] for k, v in r["textures"].items()})))
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
