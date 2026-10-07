"""S3 waves v3 (variant B) -- PURE planning core for s3_waves_v3_ue.py.  No `unreal` import; the offline harness
(test_s3_waves_v3_offline.py) drives every function here directly.

Written 7 Oct 2026 OFFLINE.  Tiers per claim: [decl] read in a file/header (cited), [prec] an in-repo tool made the same
call and it RAN (cited with its record), [meas] measured offline here, [inf] inferred (reason given).

Gary 7 Oct (own words, relayed by the conductor): Variant B; back foam may cover the mural figures' feet; ADD the
warm side light; foam flicker (Flap-slot flutter); sway + bob with periods dividing the 30 s vamp; clamp L5's sway so
it stays within the 200 cm side cap.
"""
import copy
import json
import math

# ----------------------------------------------------------------------------------------------- identity / paths
TOOL = "s3_waves_v3"
MARK = "S3WAVESV3"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"           # s3_wave_split_apply.py:22 [decl]
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"                  # s3_wave_split_apply.py:23 [decl]
UMAP_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
ROOT_SEQ_REL = "Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
RISE_REL = "Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset"
ROOT_LABEL = "S3 Hangar Root"
UPLIGHT_LABEL = "S3 Uplight 1"
RAKE_LABEL = "S3 Daylight Rake Key"
SPLIT_LABELS = tuple("S3 Wave Split Row%d Piece%d" % (r, p) for r in (1, 2, 3) for p in (1, 2, 3))
TAG = "S3.WavesV3.ToolOwned"
LIGHT_TAG = "S3.WavesV3.Light"
FOLDER = "RigAtmos/S3WavesV3"
MOTION_TRACK = "S3.WavesV3.Motion"
LIGHT_TRACK = "S3.WavesV3.Light"
ASSET_ROOT = "/Game/Scenes/Wings/FlatV3/Scene3/WavesV3"                 # redesign doc s5 "Names" [decl]
PARENTS = {"Front": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front",
           "Flap": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap",
           # S3 wave precedent, revision 2: Timber AND Edge = the CanvasEdge master directly (no MI)
           # (s3_flats_import.py:22-29, waves/IMPORT_PLAN.md "Timber and Edge") [decl]
           "Timber": "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master",
           "Edge": "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master"}
SLOTS = ("Front", "Flap", "Timber", "Edge")
TEX_KINDS = ("SkinColor", "SkinMask", "SkinNormal")
# SkinColor BC7 (FlatV3Spec "Colour (sRGB, BC7)"; s3_flats_import.py:203-205 [decl]); mask TC_Masks; normal BC5
TEX_PROFILE = {"SkinColor": ("TC_BC7", True), "SkinMask": ("TC_MASKS", False), "SkinNormal": ("TC_NORMALMAP", False)}
FOAM_LAYERS = ("L1_Breakers", "L6_Foam")
FOAM_FLUTTER = {"FlutterAmpCm": 4.0, "FlutterHz": 1.3}     # [inf] creative start values; Gary tunes (max WPO 6 cm)
FLUTTER_NAMES = ("FlutterAmpCm", "FlutterHz")              # flutter_lod_core.py:31-32 [decl]
LOD1_SCREEN_SIZE = 0.3                                     # Gary 7 Oct for P04-P06 flaps (flutter_lod_core.py:36) [decl]

# ----------------------------------------------------------------------------------------------- live geometry
ROOT_LANDED_WORLD = (11421.97275, 160000.0, -120.0)        # S3Millstone/s3_props_ue.py:77 [meas there, 7 Oct]
FLOOR_TOP_LOCAL_Z = 115.0                                  # s3_shore_footprint.json floor_top_local_z [decl]
WAVE_GUARD_LOCAL = {"min": [3590.0, -1110.0, 85.0], "max": [5400.0, 1110.0, 420.0]}   # root-local cm, rest pose
SIDE_LIMIT_CM = 1000.0                                     # hangar half-width (s3_wave_split_apply.py:41) [decl]
MAX_OVERHANG_CM = 200.0                                    # s3_wave_split_apply.py:44 [decl]; Gary: L5 clamp
SKIRT_CM = 20.0

# ----------------------------------------------------------------------------------------------- sequence timing
EXPECTED_FPS = 24.0
EXPECTED_PLAYBACK = (0, 6240)                              # Scene 3, brief + s3_wave_split_apply.py:27 [decl]
RISE_SUBSECTION_END = 744                                  # Hangar Fold [0,744) (s3_hangar_float_hold_record.json)
EXPECTED_STRIKE_FRAME = 240                                # +10 s in the 24 fps root (s3_wave_split_apply.py:28)
STRIKE_TOL = 1
KEY_STEP = 3                                               # s3_wave_split_apply.py:31 [decl]
VAMP_RANGE = (3480, 4200)                                  # s3_wave_split_apply.py:36 [decl] (30 s)
RAMP_S = 2.0                                               # sway fade-in after the strike (no pop at the gate)
LIGHT_RAMP_S = 0.20                                        # s3_daylight_apply.py:37 [decl]

# ----------------------------------------------------------------------------------------------- confirm strings
MODES = ("DRY", "IMPORT", "VERIFY", "BUILD_MAT", "APPLY", "REVERT",
         "MOTION_DRY", "MOTION_APPLY", "MOTION_REVERT", "LIGHT_DRY", "LIGHT_APPLY", "LIGHT_REVERT")
READ_ONLY = ("DRY", "VERIFY", "MOTION_DRY", "LIGHT_DRY")
PIE_OK = ("VERIFY",)                                       # asset reads only; get_editor_world() is None in PIE
BATCH_CAP = {"IMPORT": 1, "BUILD_MAT": 4}


class PlanError(ValueError):
    pass


def req(cond, msg):
    if not cond:
        raise PlanError(msg)


def confirm_for(mode):
    return "%s S3WAVESV3" % mode


def check_mode(args, in_pie, records):
    """records: {"apply": bool, "motion": bool, "light": bool} = record files present."""
    mode = str(args.get("mode", "DRY")).upper()
    req(mode in MODES, "MODE|%s" % mode)
    if mode not in READ_ONLY:
        req(args.get("confirm") == confirm_for(mode), "CONFIRM_MISSING|need %r" % confirm_for(mode))
    req(not in_pie or mode in PIE_OK, "PIE_ACTIVE|%s refused in PIE (editor world is None there)" % mode)
    if mode in BATCH_CAP:
        pieces = list(args.get("pieces") or [])
        req(1 <= len(pieces) <= BATCH_CAP[mode], "BATCH|%s takes 1..%d pieces, got %d" % (mode, BATCH_CAP[mode],
                                                                                           len(pieces)))
    req(not (mode == "APPLY" and records["apply"]), "ALREADY_APPLIED (REVERT first)")
    req(not (mode == "REVERT" and not records["apply"]), "NO_APPLY_RECORD")
    req(not (mode == "REVERT" and records["motion"]), "MOTION_RECORD_PRESENT (MOTION_REVERT first: its bindings "
                                                     "point at the actors REVERT destroys)")
    req(not (mode in ("MOTION_DRY", "MOTION_APPLY") and not records["apply"]), "NO_APPLY_RECORD (APPLY first)")
    req(not (mode == "MOTION_APPLY" and records["motion"]), "MOTION_ALREADY_APPLIED")
    req(not (mode == "MOTION_REVERT" and not records["motion"]), "NO_MOTION_RECORD")
    req(not (mode == "LIGHT_APPLY" and records["light"]), "LIGHT_ALREADY_APPLIED")
    req(not (mode == "LIGHT_REVERT" and not records["light"]), "NO_LIGHT_RECORD")
    return mode


# ----------------------------------------------------------------------------------------------- piece table
def piece_paths(suffix):
    """suffix = 'S3_WaveV3_L1Breakers_P1'."""
    short = suffix[len("S3_WaveV3_"):]
    return {"mesh": "%s/StaticMeshes/SM_FlatV3_%s" % (ASSET_ROOT, suffix),
            "tex": {k: "%s/Textures/%s/T_%s_%s" % (ASSET_ROOT, short, suffix, k) for k in TEX_KINDS},
            "mi": {s: "%s/Materials/Instances/MI_FlatV3_%s_%s" % (ASSET_ROOT, suffix, s) for s in ("Front", "Flap")},
            "label": "S3 WaveV3 %s" % short.replace("_", " ")}


def ue_bounds_from_validation(bounds_m):
    """Blender -> UE: X kept, Y reflected, Z kept (phase1_import.verify_flat comment: 'Interchange reflects Y;
    X/Z retain sign', phase1_import.py:588) [prec]; metres -> cm."""
    mn, mx = bounds_m["min"], bounds_m["max"]
    return {"min": [mn[0] * 100.0, -mx[1] * 100.0, mn[2] * 100.0], "max": [mx[0] * 100.0, -mn[1] * 100.0, mx[2] * 100.0]}


def piece_table(build_report, build_plan):
    """Rows for the 12 pieces from B_build/build_report_B.json (validated build) + build_plan_B.json (mounts)."""
    rows = []
    req(len(build_plan["pieces"]) == 12, "PLAN_PIECES|%d" % len(build_plan["pieces"]))
    for p in build_plan["pieces"]:
        suffix = p["asset"][len("SM_FlatV3_"):]
        b = build_report["pieces"].get(suffix)
        req(b and b.get("validation_pass"), "PIECE_NOT_BUILT|%s" % suffix)
        req(b["mount_local"] == p["mount_local"], "MOUNT_DRIFT|%s" % suffix)
        rows.append({"suffix": suffix, "layer": p["layer"], "piece": p["piece"], "mount_local": list(p["mount_local"]),
                     "u_range_cm": list(p["u_range_cm"]), "bounds_cm": ue_bounds_from_validation(b["bounds_m"]),
                     "triangles": b["triangle_counts"], "foam": p["layer"] in FOAM_LAYERS,
                     "flaps": int(b["flaps"]), **piece_paths(suffix)})
    return rows


# ----------------------------------------------------------------------------------------------- transforms (UE)
def rot_matrix(rpy):
    """UE FRotationMatrix rows = local X/Y/Z axes in parent space; rpy = [roll, pitch, yaw] deg.  Same as
    S3Millstone/s3_props_ue.py:229-234 (ran S3PROPS-20261007-173446) [prec]."""
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
    pts = [tf_inv_point(root_tf, [box["max"][0] if i & 1 else box["min"][0], box["max"][1] if i & 2 else box["min"][1],
                                  box["max"][2] if i & 4 else box["min"][2]]) for i in range(8)]
    return {"min": [min(p[i] for p in pts) for i in range(3)], "max": [max(p[i] for p in pts) for i in range(3)]}


def box_inside(box, guard, tol=0.5):
    return all(box["min"][i] >= guard["min"][i] - tol and box["max"][i] <= guard["max"][i] + tol for i in range(3))


def piece_local_box(row):
    """Root-local AABB of a piece at rest (rotation 0, scale 1)."""
    m, b = row["mount_local"], row["bounds_cm"]
    return {"min": [m[i] + b["min"][i] for i in range(3)], "max": [m[i] + b["max"][i] for i in range(3)]}


# ----------------------------------------------------------------------------------------------- APPLY plan
def reveal_decision(split_rows):
    """split_rows[i]["rise_visibility"] = list of visibility sections on the rise binding(s) resolving to that split
    piece ([] = none found; "UNREAD" = could not read).  -> {"mode": "none"} or {"mode": "copy", "section": {...}}."""
    secs = [r.get("rise_visibility") for r in split_rows]
    req(all(s != "UNREAD" for s in secs), "REVEAL_UNREAD")
    if all(not s for s in secs):
        return {"mode": "none", "why": "no split piece has a rise visibility track: they are visible whenever the "
                                       "hangar is (same for the new pieces)"}
    req(all(s and len(s) == 1 for s in secs), "REVEAL_MIXED|%s" % [len(s) if s else 0 for s in secs])
    first = json.dumps(secs[0][0], sort_keys=True)
    req(all(json.dumps(s[0], sort_keys=True) == first for s in secs), "REVEAL_SECTIONS_DIFFER")
    sec = secs[0][0]
    req(sec.get("keys") and sec.get("completion_mode") and sec.get("range_s"), "REVEAL_SECTION_EMPTY")
    return {"mode": "copy", "section": sec, "why": "all nine split pieces carry the same rise visibility section; "
                                                   "copied per new actor (the millstone reveal pattern)"}


def plan_apply(state, rows):
    """state: live read (see s3_waves_v3_ue.live_state).  rows: piece_table()."""
    req(not state.get("temp_actors"), "TEMP_ACTORS_PRESENT|%s" % (state.get("temp_actors") or [])[:5])
    req(root_is_landed(state["root"]["world"]), "ROOT_NOT_LANDED|%s" % json.dumps(state["root"]["world"]))
    req(state["root"].get("attached_count_ok", True), "ROOT_IDENTITY")
    for r in rows:
        req(state["label_count"].get(r["label"], 0) == 0, "LABEL_EXISTS|%s" % r["label"])
        a = state["assets"].get(r["suffix"], {})
        req(a.get("verified"), "ASSETS_NOT_VERIFIED|%s (IMPORT, BUILD_MAT, then VERIFY)" % r["suffix"])
        box = piece_local_box(r)
        req(box_inside(box, WAVE_GUARD_LOCAL), "GUARD_LOCAL_BOX|%s|%s" % (r["suffix"], json.dumps(box)))
    split = state["split"]
    req(sorted(s["label"] for s in split) == sorted(SPLIT_LABELS), "SPLIT_PIECES|%s" % [s["label"] for s in split])
    for s in split:
        req(s["count"] == 1, "SPLIT_COUNT|%s|%d" % (s["label"], s["count"]))
        req(s["parent"] == ROOT_LABEL, "SPLIT_PARENT|%s|%s" % (s["label"], s["parent"]))
        req(not s["tool_owned_v3"], "SPLIT_IS_OURS|%s" % s["label"])
    reveal = reveal_decision(split)
    spawns = [{"label": r["label"], "suffix": r["suffix"], "mesh": r["mesh"], "tags": [TAG, "S3.WavesV3." + r["layer"]],
               "folder": FOLDER, "relative": {"location": list(r["mount_local"]), "rotation": [0.0, 0.0, 0.0],
                                              "scale": [1.0, 1.0, 1.0]},
               "local_box": piece_local_box(r)} for r in rows]
    hide_after = {"actor_hidden": True, "comp_visible": False, "comp_hidden_in_game": True}
    hides = [{"label": s["label"], "object_path": s["object_path"], "before": dict(s["flags"]), "after": dict(hide_after)}
             for s in sorted(split, key=lambda x: x["label"])]
    saves = []                                   # APPLY touches no sequence unless a reveal is copied
    if reveal["mode"] == "copy":
        saves.append(RISE)
    return {"spawns": spawns, "hides": hides, "reveal": reveal, "content_saves": saves, "map": WORLD}


def apply_ops(plan):
    ops = [{"op": "hide", "label": h["label"], "object_path": h["object_path"], "flags": h["after"]} for h in plan["hides"]]
    for s in plan["spawns"]:
        ops.append({"op": "spawn", "label": s["label"], "mesh": s["mesh"], "relative": s["relative"], "tags": s["tags"]})
        if plan["reveal"]["mode"] == "copy":
            ops.append({"op": "add_reveal", "label": s["label"], "section": plan["reveal"]["section"]})
    return ops


def revert_ops(record):
    plan = record["plan"]
    ops = []
    for c in reversed(record["created"]):
        if c.get("reveal_guid"):
            ops.append({"op": "remove_reveal", "guid": c["reveal_guid"], "actor_path": c["actor_path"]})
        ops.append({"op": "destroy", "actor_path": c["actor_path"], "label": c["label"]})
    for h in plan["hides"]:
        ops.append({"op": "hide", "label": h["label"], "object_path": h["object_path"], "flags": h["before"]})
    return ops


def simulate(world, ops):
    """World model {object_path: {...}} + __bindings__.  Spawned actors get path NEW_<label>."""
    w = copy.deepcopy(world)
    b = w.setdefault("__bindings__", {})
    for op in ops:
        if op["op"] == "spawn":
            path = "NEW_" + op["label"]
            req(path not in w, "SIM_SPAWN_EXISTS|%s" % path)
            w[path] = {"label": op["label"], "relative": copy.deepcopy(op["relative"]), "tags": list(op["tags"])}
        elif op["op"] == "add_reveal":
            b["GUID_" + op["label"]] = "NEW_" + op["label"]
        elif op["op"] == "hide":
            req(op["object_path"] in w, "SIM_HIDE_MISSING|%s" % op["object_path"])
            w[op["object_path"]]["flags"] = dict(op["flags"])
        elif op["op"] == "remove_reveal":
            req(b.get(op["guid"]) == op["actor_path"], "SIM_BINDING_MISMATCH")
            del b[op["guid"]]
        elif op["op"] == "destroy":
            req(op["actor_path"] in w, "SIM_DESTROY_MISSING|%s" % op["actor_path"])
            del w[op["actor_path"]]
    return w


def record_from_sim(plan):
    """What APPLY writes into its record for the harness (actor paths = the simulator's)."""
    return {"plan": plan, "created": [{"label": s["label"], "actor_path": "NEW_" + s["label"],
                                       "reveal_guid": ("GUID_" + s["label"]) if plan["reveal"]["mode"] == "copy" else None}
                                      for s in plan["spawns"]]}


# ----------------------------------------------------------------------------------------------- MOTION
def motion_layers(motion_plan, cap_cm=MAX_OVERHANG_CM, strip_overhang_cm=100.0, clamp=True):
    """Layer params from s3_waves_v3_motion_plan.json with Gary's L5 clamp (sway <= cap - strip overhang)."""
    out = []
    limit = cap_cm - strip_overhang_cm
    for L in motion_plan["layers"]:
        a = float(L["sway_y_cm"])
        row = {"id": L["id"], "period_s": float(L["period_s"]), "sway_cm": a, "dir": int(L["dir"]),
               "phase": float(L["phase"]), "bob_cm": float(L["bob_z_cm"]), "roll_deg": float(L["roll_deg"]),
               "clamped_from": None}
        if clamp and a > limit + 1e-9:
            row["sway_cm"], row["clamped_from"] = limit, a
        out.append(row)
    return out


def periods_divide(layers, vamp, fps):
    n = vamp[1] - vamp[0]
    bad = []
    for L in layers:
        pf = L["period_s"] * fps
        if abs(pf - round(pf)) > 1e-9 or n % int(round(pf)) != 0:      # bob (T/2) and roll (T) follow
            bad.append((L["id"], L["period_s"]))
    return bad


def envelope(t):
    if t <= 0.0:
        return 0.0
    if t >= RAMP_S:
        return 1.0
    x = t / RAMP_S
    return x * x * (3.0 - 2.0 * x)


def layer_offsets(L, t):
    """(dy, dz, roll_deg) of the LAYER at t seconds after the strike (formulas: s3_waves_v3_motion_plan.json)."""
    e = envelope(t)
    s = 2.0 * math.pi * (t / L["period_s"] + L["phase"])
    dy = L["dir"] * L["sway_cm"] * e * math.sin(s)
    dz = -L["bob_cm"] * e * (1.0 - math.cos(2.0 * s)) / 2.0
    roll = L["roll_deg"] * e * math.sin(s - math.pi / 2.0)
    return dy, dz, roll


def piece_key(row, L, t):
    """Relative (to the root) transform of a piece: the LAYER is rigid; pivot = layer centre line (y 0) at the
    piece origin height; P1 and P2 differ only in their rest y (u centre) and x."""
    dy, dz, roll = layer_offsets(L, t)
    x, yc, z0 = row["mount_local"]
    m = rot_matrix([roll, 0.0, 0.0])
    loc = [x + yc * m[1][0], dy + yc * m[1][1], z0 + dz + yc * m[1][2]]
    return {"location": loc, "rotation": [roll, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}


def key_frames(strike, end):
    frames = [strike - 1] + list(range(strike, end + 1, KEY_STEP))
    if frames[-1] != end:
        frames.append(end)
    return frames


def plan_motion(state, rows, motion_plan, clamp=True, vamp=VAMP_RANGE):
    fps = float(state["fps"])
    req(abs(fps - EXPECTED_FPS) < 1e-6, "FPS|%s" % fps)
    playback = tuple(int(v) for v in state["playback"])
    req(playback == EXPECTED_PLAYBACK, "PLAYBACK|%s (Scene 3 must be 0..6240; re-plan if relengthed)" % (playback,))
    strike = int(state["strike"]["frame"])
    req(abs(strike - EXPECTED_STRIKE_FRAME) <= STRIKE_TOL, "STRIKE|%d" % strike)
    req(playback[0] <= vamp[0] < vamp[1] <= playback[1], "VAMP_OUTSIDE|%s" % (vamp,))
    layers = motion_layers(motion_plan, clamp=clamp)
    bad = periods_divide(layers, vamp, fps)
    req(not bad, "PERIODS_DO_NOT_DIVIDE_VAMP|%s" % bad)
    req(strike + RAMP_S * fps < vamp[0], "RAMP_REACHES_VAMP")
    by = {L["id"]: L for L in layers}
    frames = key_frames(strike, playback[1])
    req(frames[0] < playback[1] and frames[-1] == playback[1], "KEYS_DO_NOT_REACH_SCENE_END")
    req(frames[-1] > RISE_SUBSECTION_END, "KEYS_END_AT_RISE")
    req(vamp[0] in frames and vamp[1] in frames, "VAMP_NOT_ON_KEY_GRID")
    pieces, worst = [], {"overhang_cm": 0.0, "skirt_lift_cm": 0.0, "seam_cm": 0.0, "split_cm": 0.0}
    for r in rows:
        L = by[r["layer"]]
        keys = []
        for f in frames:
            t = max(0.0, (f - strike) / fps)
            k = piece_key(r, L, t)
            keys.append({"frame": f, **k})
        # vamp seam: identical transform at both ends
        kv = {k["frame"]: k for k in keys}
        seam = max(abs(a - b) for a, b in zip(kv[vamp[0]]["location"] + kv[vamp[0]]["rotation"],
                                              kv[vamp[1]]["location"] + kv[vamp[1]]["rotation"]))
        worst["seam_cm"] = max(worst["seam_cm"], seam)
        # side overhang: the piece's outer end (u_range end beyond the box)
        u0, u1 = r["u_range_cm"]
        over = 0.0
        lift = 0.0
        for k in keys:
            m = rot_matrix(k["rotation"])
            for u in (u0, u1):
                y = k["location"][1] + (u - r["mount_local"][1]) * m[1][1]
                over = max(over, abs(y) - SIDE_LIMIT_CM)
                zb = k["location"][2] + (u - r["mount_local"][1]) * m[1][2]
                lift = max(lift, zb - r["mount_local"][2])
        worst["overhang_cm"] = max(worst["overhang_cm"], over)
        worst["skirt_lift_cm"] = max(worst["skirt_lift_cm"], lift)
        req(over <= MAX_OVERHANG_CM + 1e-6, "OVERHANG|%s|%.2f cm > %.0f (L5 clamp off?)" % (r["suffix"], over,
                                                                                         MAX_OVERHANG_CM))
        req(lift < SKIRT_CM, "SKIRT_LIFT|%s|%.2f" % (r["suffix"], lift))
        req(seam < 1e-6, "VAMP_SEAM|%s|%.6f" % (r["suffix"], seam))
        pieces.append({"suffix": r["suffix"], "label": r["label"], "layer": r["layer"], "keys": keys})
    # P1/P2 never split: the same layer point (u) maps to the same (y, z) in both pieces at every key
    for lid in by:
        pr = [p for p in pieces if p["layer"] == lid]
        rr = {r["suffix"]: r for r in rows}
        req(len(pr) == 2, "LAYER_PIECES|%s" % lid)
        a, b = pr
        ua, ub = rr[a["suffix"]]["u_range_cm"], rr[b["suffix"]]["u_range_cm"]
        u = 0.5 * (max(ua[0], ub[0]) + min(ua[1], ub[1]))             # a point inside the overlap
        for ka, kb in zip(a["keys"], b["keys"]):
            pa = tf_point(ka, [0.0, u - rr[a["suffix"]]["mount_local"][1], 50.0])
            pb = tf_point(kb, [0.0, u - rr[b["suffix"]]["mount_local"][1], 50.0])
            d = max(abs(pa[1] - pb[1]), abs(pa[2] - pb[2]))
            worst["split_cm"] = max(worst["split_cm"], d)
        req(worst["split_cm"] < 1e-6, "P1_P2_SPLIT|%s|%.6f" % (lid, worst["split_cm"]))
    return {"fps": fps, "playback": list(playback), "strike": state["strike"], "vamp": list(vamp),
            "frames": {"first": frames[0], "last": frames[-1], "count": len(frames), "step": KEY_STEP},
            "layers": layers, "pieces": pieces, "worst": worst, "track": MOTION_TRACK}


def flicker_verdict(mesh_rows):
    """mesh_rows: {suffix: {"foam": bool, "lod0_flap_triangles": int, "flap_r_range": [lo, hi], "flutter_switch": bool|None,
    "flutter_amp": float|None, "lod1_screen_size": float}} -> per-piece LIVE / NOT_FOAM / REFUSED (reason)."""
    out = {}
    for s, m in sorted(mesh_rows.items()):
        if not m.get("foam"):
            out[s] = "NOT_FOAM (peel-flap flutter only)"
            continue
        why = []
        if not m.get("lod0_flap_triangles"):
            why.append("no Flap section in LOD0")
        rr = m.get("flap_r_range") or [0, 0]
        if not (rr[0] <= 0.01 and rr[1] >= 0.99):
            why.append("Flap VC.R not 0..1 (%s)" % rr)
        if m.get("flutter_switch") is not True:
            why.append("Flap MI Flutter switch %s" % m.get("flutter_switch"))
        if not m.get("flutter_amp") or m["flutter_amp"] <= 0:
            why.append("FlutterAmpCm %s" % m.get("flutter_amp"))
        out[s] = "LIVE (Flap WPO, LOD0 within screen size %.2f)" % m.get("lod1_screen_size", -1) if not why \
            else "REFUSED: " + "; ".join(why)
    return out


# ----------------------------------------------------------------------------------------------- LIGHT
LAYER_X = {"L1_Breakers": 3650.0, "L2_SwellNear": 3695.0, "L3_SwellMid": 4450.0, "L4_SwellFar": 4495.0,
           "L5_Rollers": 5250.0, "L6_Foam": 5295.0}                       # design_B.json layers[].x [decl]
BACKDROP_X = 5997.0                                                        # preview script backdrop plane [decl]
RAKE_TEMPERATURE_K = 7500.0          # redesign s4 item 1: 7000-8000 K [decl]; value [inf], Gary tunes
GROUND_ROW = {"intensity_cd": 120.0, "temperature_k": 9000.0, "rect_cm": [1900.0, 12.0], "z_above_floor_cm": 8.0,
              "behind_layer_cm": 20.0, "aim_height_cm": 160.0, "attenuation_cm": 1500.0}      # [inf] values
WARM_SIDE = {"label": "S3 WaveV3 Warm Side", "location": [2600.0, -980.0, 260.0], "target": [5000.0, 400.0, 230.0],
             "intensity_cd": 250.0, "temperature_k": 3200.0, "rect_cm": [200.0, 120.0], "shadows": True,
             "attenuation_cm": 4000.0}       # placement = the B preview (s3_waves_v3_preview_blender.py:45) [decl]
HAZE = {"label": "S3 WaveV3 Sea Haze", "box_local": {"min": [3550.0, -995.0, 115.0], "max": [5990.0, 995.0, 715.0]},
        "base_size_cm": 500.0,               # ULocalFogVolumeComponent::GetBaseVolumeSize (LocalFogVolumeComponent.h:74)
        "radial_fog_extinction": 0.25, "height_fog_extinction": 0.15, "height_fog_falloff": 300.0,
        "fog_albedo": [0.70, 0.74, 0.74, 1.0]}                               # [inf] values; preview haze_rgb B


def look_rotation(loc, target):
    """[roll, pitch, yaw] deg pointing local X from loc at target (s3_daylight_apply._rotation, :354-357) [prec]."""
    dx, dy, dz = (float(target[i]) - float(loc[i]) for i in range(3))
    return [0.0, math.degrees(math.atan2(dz, math.hypot(dx, dy))), math.degrees(math.atan2(dy, dx))]


def light_specs():
    xs = sorted(LAYER_X.items(), key=lambda kv: kv[1])
    out = []
    for i, (lid, x) in enumerate(xs):
        loc = [x + GROUND_ROW["behind_layer_cm"], 0.0, FLOOR_TOP_LOCAL_Z + GROUND_ROW["z_above_floor_cm"]]
        if i + 1 < len(xs):
            tgt = [xs[i + 1][1], 0.0, FLOOR_TOP_LOCAL_Z + GROUND_ROW["aim_height_cm"]]
        else:
            tgt = [BACKDROP_X, 0.0, FLOOR_TOP_LOCAL_Z + 400.0]
        out.append({"label": "S3 WaveV3 Ground Row %d" % (i + 1), "kind": "ground_row", "behind": lid,
                    "location": loc, "rotation": look_rotation(loc, tgt), "target": tgt,
                    "intensity_cd": GROUND_ROW["intensity_cd"], "temperature_k": GROUND_ROW["temperature_k"],
                    "rect_cm": list(GROUND_ROW["rect_cm"]), "shadows": False,
                    "attenuation_cm": GROUND_ROW["attenuation_cm"]})
    w = dict(WARM_SIDE)
    out.append({"label": w["label"], "kind": "warm_side", "location": list(w["location"]),
                "rotation": look_rotation(w["location"], w["target"]), "target": list(w["target"]),
                "intensity_cd": w["intensity_cd"], "temperature_k": w["temperature_k"], "rect_cm": list(w["rect_cm"]),
                "shadows": w["shadows"], "attenuation_cm": w["attenuation_cm"]})
    return out


def light_keys(strike_frame, fps, end_frame, intensity):
    """Frames (display rate) -> value: 0 until the strike, LIGHT_RAMP_S ramp, then held to the Scene end.  One section
    over the WHOLE Scene in LS_DevScene_03, so nothing ends at the 744 rise boundary (S3FLOATHOLD exists only because
    the rise tracks stop there, s3_hangar_float_hold_record.json plan.range [744, 6240])."""
    ramp_end = strike_frame + int(round(LIGHT_RAMP_S * fps))
    keys = [[0, 0.0], [strike_frame, 0.0], [ramp_end, float(intensity)], [end_frame, float(intensity)]]
    return keys


def plan_light(state, ehf_rule="in_s3"):
    """state: fps, playback, strike, rake {...}, ehf [...], label_count, root."""
    req(root_is_landed(state["root"]["world"]), "ROOT_NOT_LANDED")
    fps = float(state["fps"])
    req(abs(fps - EXPECTED_FPS) < 1e-6, "FPS|%s" % fps)
    playback = tuple(int(v) for v in state["playback"])
    req(playback == EXPECTED_PLAYBACK, "PLAYBACK|%s" % (playback,))
    strike = int(state["strike"]["frame"])
    req(abs(strike - EXPECTED_STRIKE_FRAME) <= STRIKE_TOL, "STRIKE|%d" % strike)
    rake = state["rake"]
    req(rake.get("count") == 1, "RAKE_COUNT|%s" % rake.get("count"))
    animated = sorted(set(rake.get("animated_properties", [])) &
                      {"Temperature", "LightColor", "bUseTemperature", "UseTemperature"})
    req(not animated, "RAKE_COLOUR_IS_KEYED|%s (retint would be overridden)" % animated)
    specs = light_specs()
    for s in specs:
        req(state["label_count"].get(s["label"], 0) == 0, "LABEL_EXISTS|%s" % s["label"])
        s["keys"] = light_keys(strike, fps, playback[1], s["intensity_cd"])
        req(s["keys"][0][0] == playback[0] and s["keys"][-1][0] == playback[1], "LIGHT_KEYS_SPAN|%s" % s["label"])
    in_s3 = [e for e in state.get("ehf", []) if e.get("in_s3")]
    if in_s3:
        req(state["label_count"].get(HAZE["label"], 0) == 0, "LABEL_EXISTS|%s" % HAZE["label"])
        req(state.get("local_fog_class"), "LOCAL_FOG_CLASS_MISSING (unreal.LocalFogVolume not exposed)")
        b = HAZE["box_local"]
        centre = [(b["min"][i] + b["max"][i]) / 2.0 for i in range(3)]
        scale = [(b["max"][i] - b["min"][i]) / 2.0 / HAZE["base_size_cm"] for i in range(3)]
        haze = {"mode": "APPLY", "label": HAZE["label"], "relative": {"location": centre, "rotation": [0, 0, 0],
                                                                      "scale": scale},
                "params": {k: HAZE[k] for k in ("radial_fog_extinction", "height_fog_extinction", "height_fog_falloff",
                                                "fog_albedo")}, "ehf": in_s3}
    else:
        haze = {"mode": "SPEC_ONLY", "why": "no ExponentialHeightFog in S3 (found: %s); spec: a LocalFogVolume over "
                                            "local box %s, radial 0.25 / height 0.15 / falloff 300 (needs an EHF to "
                                            "render [inf])" % ([e.get("label") for e in state.get("ehf", [])],
                                                               HAZE["box_local"])}
    return {"fps": fps, "playback": list(playback), "strike": state["strike"],
            "rake": {"label": RAKE_LABEL, "object_path": rake["object_path"], "before": rake["colour"],
                     "after": {"use_temperature": True, "temperature": RAKE_TEMPERATURE_K},
                     "intensity": "UNCHANGED (keyed in the rise + held by S3FLOATHOLD; the -30 % is a separate "
                                  "decision, not done here)"},
            "lights": specs, "haze": haze, "track": LIGHT_TRACK, "saves": [ROOT_SEQ], "map": WORLD}


# ----------------------------------------------------------------------------------------------- readiness
def verify_ready(verify_report, rows, newest_write_mtime):
    """APPLY needs a VERIFY report that is newer than every IMPORT/BUILD_MAT record and passes all 12 pieces."""
    req(verify_report is not None, "NO_VERIFY_REPORT (run VERIFY after the last BUILD_MAT)")
    req(verify_report.get("written_mtime", 0) > newest_write_mtime, "VERIFY_STALE (an IMPORT/BUILD_MAT ran after it)")
    bad = [r["suffix"] for r in rows if verify_report.get("pieces", {}).get(r["suffix"], {}).get("status") != "READY"]
    req(not bad, "PIECES_NOT_READY|%s" % bad)
    return True
