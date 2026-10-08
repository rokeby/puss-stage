"""S3 waves t5o -- PURE planning core for s3waves_t5o.py (no `unreal` import; the offline harness drives it).

Gary 8 Oct (own answers): (1) rebuild the 12 S3 WaveV3 pieces at 5 cm with outward V3 edges; (2) "More space between
layers" inside the shore bands; (3) edge colour "Painted sea colour".
Conductor 8 Oct: touch ONLY the 12 wave bindings' transform Location.X channels in LS_DevScene_03; every other binding
/ track / channel must read back identical (fingerprint before vs after); the S3.Fire.* / S3.Crowd.Light /
S3.Opening.Ghost tracks are expected and must not fail the tool.

Tiers per claim: [decl] read in a file (cited), [prec] an in-repo tool did the same and it ran (cited), [meas] measured
offline here, [inf] inferred (reason given).
"""
import copy
import hashlib
import json
import math

TOOL = "s3waves_t5o"
MARK = "S3T5O"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"            # s3_waves_v3_core.py:18 [decl]
ROOT_SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"                      # s3_waves_v3_core.py:19 [decl]
UMAP_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
ROOT_SEQ_REL = "Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
ROOT_LABEL = "S3 Hangar Root"
MOTION_TRACK = "S3.WavesV3.Motion"                                                 # s3_waves_v3_core.py:31 [decl]
ASSET_ROOT = "/Game/Scenes/Wings/FlatV3/Scene3/WavesV3"                            # s3_waves_v3_core.py:33 [decl]
T5O = "_t5o"
EDGE_V3_MASTER = "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master_v3"   # build_canvas_edge_master_v3.py:47
TIMBER_V1 = "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master"           # live Timber slot (mat records)
MI_EDGE = ASSET_ROOT + "/Materials/Instances/MI_WaveEdge_SeaPaint"
SLOTS = ("Front", "Flap", "Timber", "Edge")
SCREEN_SIZES = (2.0, 0.3)                                                          # s3_waves_v3_core.py:48 [decl]
EXPECTED_OTHER_TRACKS = ("S3.Fire.Light", "S3.Fire.Visible", "S3.Crowd.Light", "S3.Opening.Ghost")  # conductor 8 Oct
LOC_X = "Location.X"
CHANNELS = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
            "Scale.X", "Scale.Y", "Scale.Z")
KEY_TOL_CM = 0.01
REL_TOL_CM = 0.01

# ------------------------------------------------------------------------------------------------ edge MI (Gary's look)
# Sampled from the LIVE wave Front skins' 3 cm edge band (sample_edge_sea_colour.py -> edge_sea_colour.json) [meas];
# which cluster = "painted sea colour" is [inf] and adjustable on the MI (Gary's look call).
MI_SCALARS = {"EdgeCentreXCm": -12.5, "HalfThicknessCm": 2.5}   # thick5 Edge x -15..-10 [meas, edge probes, 12/12]
MI_VECTORS = {"TimberLight": (0.0908, 0.117, 0.1144),            # sRGB (85, 96, 95): mid grey-green sea, 13 % of band
              "TimberDark": (0.0726, 0.0936, 0.0915),            # 0.8 x TimberLight: brush grain only
              "CanvasColor": (0.1845, 0.2122, 0.1946)}           # sRGB (119, 127, 122): the lighter wrap/lip
MASTER_PARAMS = {"scalars": ("HalfThicknessCm", "EdgeCentreXCm", "CanvasLipCm", "FrayAmount", "Specular", "BevelCm",
                             "BackBevelCm", "BevelRoughness", "BevelSpecular"),
                 "vectors": ("TimberDark", "TimberLight", "CanvasColor")}        # build_canvas_edge_master_v3_result

# ------------------------------------------------------------------------------------------------ layout
# Shore flat bands: s3_shore_field.notch_half() on s3_shore_footprint.json wave_rows, run 8 Oct [meas]
# (centre +- max(45, half + notch_flush_margin 10)); the 90 cm smoothstep blend lies outside these.
BANDS = {"Row1": (3639.0, 3745.0), "Row2": (4439.0, 4545.0), "Row3": (5239.0, 5342.0)}
LAYER_BAND = {"L1_Breakers": "Row1", "L2_SwellNear": "Row1", "L3_SwellMid": "Row2", "L4_SwellFar": "Row2",
              "L5_Rollers": "Row3", "L6_Foam": "Row3"}
PITCH_MIN_CM = 17.0              # conductor: P1<->P2 >= 17 cm (read as origin pitch; clear gap reported too)
LEGACY_BACK_CM = -3.2            # live legacy_1p8 pieces: x max -3.2 cm (build_report_B bounds) [decl]
# NEW piece origins (root-local x, cm).  Pitch 20 inside a layer, every piece inside its flat band, the two layers of
# a band pushed to the band's front and back.  [inf] = a proposal; Gary may trade band margin for more gap.
NEW_X = {"S3_WaveV3_L1Breakers_P1": 3656.0, "S3_WaveV3_L1Breakers_P2": 3676.0,
         "S3_WaveV3_L2SwellNear_P1": 3724.0, "S3_WaveV3_L2SwellNear_P2": 3744.0,
         "S3_WaveV3_L3SwellMid_P1": 4456.0, "S3_WaveV3_L3SwellMid_P2": 4476.0,
         "S3_WaveV3_L4SwellFar_P1": 4524.0, "S3_WaveV3_L4SwellFar_P2": 4544.0,
         "S3_WaveV3_L5Rollers_P1": 5256.0, "S3_WaveV3_L5Rollers_P2": 5276.0,
         "S3_WaveV3_L6Foam_P1": 5321.0, "S3_WaveV3_L6Foam_P2": 5341.0}
BAND_MARGIN_CM = 0.5

MODES = ("DRY", "MI", "IMPORT", "MATS", "VERIFY", "APPLY", "REVERT")
READ_ONLY = ("DRY", "VERIFY")
PIE_OK = ()
BATCH_CAP = {"IMPORT": 3, "MATS": 4}


class PlanError(ValueError):
    pass


def req(cond, msg):
    if not cond:
        raise PlanError(msg)


def confirm_for(mode):
    return "%s %s" % (mode, MARK)


def check_mode(args, in_pie, records):
    """records: {"apply": bool (apply record present), "applied": bool (it says applied+saved)}."""
    mode = str(args.get("mode", "DRY")).upper()
    req(mode in MODES, "MODE|%s" % mode)
    if mode not in READ_ONLY:
        req(args.get("confirm") == confirm_for(mode), "CONFIRM_MISSING|need %r" % confirm_for(mode))
    req(not in_pie, "PIE_ACTIVE|%s refused in PIE" % mode)
    if mode in BATCH_CAP:
        pieces = list(args.get("pieces") or [])
        req(1 <= len(pieces) <= BATCH_CAP[mode], "BATCH|%s takes 1..%d pieces, got %d" % (
            mode, BATCH_CAP[mode], len(pieces)))
        req(len(set(pieces)) == len(pieces), "BATCH_DUPLICATES|%s" % pieces)
    req(not (mode == "APPLY" and records["apply"]), "ALREADY_APPLIED (REVERT first)")
    req(not (mode == "REVERT" and not records["apply"]), "NO_APPLY_RECORD")
    req(not (mode in ("MI", "IMPORT", "MATS") and records["apply"]),
        "ASSET_WRITE_WHILE_APPLIED|%s refused while the apply record exists (the level uses these meshes)" % mode)
    return mode


# ------------------------------------------------------------------------------------------------ pieces
def short(suffix):
    return suffix[len("S3_WaveV3_"):]


def t5o_paths(suffix):
    return {"mesh": "%s/StaticMeshes/SM_FlatV3_%s%s" % (ASSET_ROOT, suffix, T5O),
            "live_mesh": "%s/StaticMeshes/SM_FlatV3_%s" % (ASSET_ROOT, suffix),
            "mi": {s: "%s/Materials/Instances/MI_FlatV3_%s_%s" % (ASSET_ROOT, suffix, s) for s in ("Front", "Flap")},
            "label": "S3 WaveV3 %s" % short(suffix).replace("_", " ")}


def ue_bounds_from_validation(bounds_m):
    """Blender -> UE: X kept, Y reflected, Z kept (s3_waves_v3_core.ue_bounds_from_validation) [prec]; m -> cm."""
    mn, mx = bounds_m["min"], bounds_m["max"]
    return {"min": [mn[0] * 100.0, -mx[1] * 100.0, mn[2] * 100.0], "max": [mx[0] * 100.0, -mn[1] * 100.0, mx[2] * 100.0]}


def piece_rows(build_plan, t5o_report, apply_record):
    """12 rows: live mount (build_plan_B), t5o build gates (build_report_t5o.json), live actor path (v3 apply record)."""
    req(len(build_plan["pieces"]) == 12, "PLAN_PIECES|%d" % len(build_plan["pieces"]))
    actors = {c["label"]: c["actor_path"] for c in apply_record["created"]}
    rows = []
    for p in build_plan["pieces"]:
        suffix = p["asset"][len("SM_FlatV3_"):]
        b = t5o_report["pieces"].get(suffix) or {}
        req(b.get("pass") is True, "T5O_NOT_BUILT|%s" % suffix)
        for g in ("G0_live_inputs", "G2_validation", "G3_edge", "G4_uv0_registration"):
            req((b.get(g) or {}).get("pass") is True, "T5O_GATE|%s|%s" % (suffix, g))
        req(b["mount_local_live"] == p["mount_local"], "MOUNT_DRIFT|%s" % suffix)
        paths = t5o_paths(suffix)
        req(paths["label"] in actors, "NO_LIVE_ACTOR|%s" % paths["label"])
        val = b["G2_validation"]
        rows.append({"suffix": suffix, "layer": p["layer"], "piece": p["piece"], "mount_local": list(p["mount_local"]),
                     "u_range_cm": list(p["u_range_cm"]), "bounds_cm": ue_bounds_from_validation(val["bounds_m"]),
                     "triangle_counts": val["triangle_counts"], "fbx": b["out_dir"] + "\\SM_FlatV3_%s%s.fbx" % (suffix, T5O),
                     "fbx_sha256": b["fbx_sha256"], "actor_path": actors[paths["label"]],
                     "foam": p["layer"] in ("L1_Breakers", "L6_Foam"), **paths})
    req(sorted(r["suffix"] for r in rows) == sorted(NEW_X), "NEW_X_KEYS")
    return rows


def pick(rows, names):
    by = {short(r["suffix"]): r for r in rows}
    out = []
    for n in names:
        n = short(n) if n.startswith("S3_WaveV3_") else n
        req(n in by, "UNKNOWN_PIECE|%s|known=%s" % (n, sorted(by)))
        out.append(by[n])
    return out


def slot_plan(row):
    """Mesh slots for a t5o mesh: 0/1 reuse the LIVE Front/Flap MIs, 2 Timber keeps v1 master, 3 Edge = the new MI."""
    return [row["mi"]["Front"], row["mi"]["Flap"], TIMBER_V1, MI_EDGE]


def mi_plan(vectors=None, scalars=None):
    v = dict(MI_VECTORS if vectors is None else {k: tuple(x) for k, x in vectors.items()})
    s = dict(MI_SCALARS if scalars is None else scalars)
    req(set(v) <= set(MASTER_PARAMS["vectors"]), "MI_VECTOR_NAMES|%s" % sorted(v))
    req(set(s) <= set(MASTER_PARAMS["scalars"]), "MI_SCALAR_NAMES|%s" % sorted(s))
    for k, c in v.items():
        req(len(c) == 3 and all(0.0 <= float(x) <= 1.0 for x in c), "MI_VECTOR_RANGE|%s|%s" % (k, c))
    req(abs(s.get("EdgeCentreXCm", -12.5) + 12.5) < 1e-6 and abs(s.get("HalfThicknessCm", 2.5) - 2.5) < 1e-6,
        "MI_EDGE_GEOMETRY|thick5 Edge is x -15..-10: centre -12.5, half 2.5")
    return {"path": MI_EDGE, "parent": EDGE_V3_MASTER, "vectors": {k: [float(x) for x in c] for k, c in v.items()},
            "scalars": {k: float(x) for k, x in s.items()}}


# ------------------------------------------------------------------------------------------------ layout plan
def depth_cm(row):
    return -float(row["bounds_cm"]["min"][0])


def back_cm(row):
    return float(row["bounds_cm"]["max"][0])


def y_range(row, x0=None):
    """Root-local y interval of the piece at rest (mount y + local bounds)."""
    y = row["mount_local"][1]
    return [y + row["bounds_cm"]["min"][1], y + row["bounds_cm"]["max"][1]]


def overlap(a, b):
    return min(a[1], b[1]) - max(a[0], b[0])


def plan_layout(rows, new_x=None):
    new_x = dict(NEW_X if new_x is None else new_x)
    pieces = []
    for r in rows:
        nx = float(new_x[r["suffix"]])
        band = BANDS[LAYER_BAND[r["layer"]]]
        ext_new = [nx - depth_cm(r), nx + back_cm(r)]
        ext_old_live = [r["mount_local"][0] - depth_cm(r), r["mount_local"][0] + LEGACY_BACK_CM]
        ext_old_t5o = [r["mount_local"][0] - depth_cm(r), r["mount_local"][0] + back_cm(r)]
        inside = ext_new[0] >= band[0] + BAND_MARGIN_CM - 1e-9 and ext_new[1] <= band[1] - BAND_MARGIN_CM + 1e-9
        pieces.append({"suffix": r["suffix"], "layer": r["layer"], "piece": r["piece"], "band": LAYER_BAND[r["layer"]],
                       "band_x": list(band), "old_x": r["mount_local"][0], "new_x": nx,
                       "dx": round(nx - r["mount_local"][0], 6), "depth_cm": round(depth_cm(r), 3),
                       "extent_new": [round(v, 3) for v in ext_new], "extent_old_live": [round(v, 3) for v in ext_old_live],
                       "extent_old_if_t5o": [round(v, 3) for v in ext_old_t5o],
                       "inside_band": inside, "y_range": [round(v, 2) for v in y_range(r)]})
        req(inside, "OUTSIDE_BAND|%s|%s|band=%s" % (r["suffix"], ext_new, band))
    by = {p["suffix"]: p for p in pieces}
    pairs = []
    order = sorted(pieces, key=lambda p: p["new_x"])
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            if a["band"] != b["band"]:
                continue
            yo = overlap(a["y_range"], b["y_range"])
            kind = "P1_P2" if a["layer"] == b["layer"] else "layer"
            gap = lambda key: round(b[key][0] - a[key][1], 3)
            row = {"a": a["suffix"], "b": b["suffix"], "kind": kind, "y_overlap_cm": round(yo, 2),
                   "pitch_new": round(b["new_x"] - a["new_x"], 3), "pitch_old": round(b["old_x"] - a["old_x"], 3),
                   "clear_new": gap("extent_new"), "clear_old_live": gap("extent_old_live"),
                   "clear_old_if_t5o": gap("extent_old_if_t5o")}
            pairs.append(row)
            if kind == "P1_P2":
                req(row["pitch_new"] >= PITCH_MIN_CM - 1e-9, "P1P2_PITCH|%s|%s" % (a["suffix"], row["pitch_new"]))
            req(row["clear_new"] > 0.0, "INTERPENETRATION_AT_REST|%s|%s|%.3f" % (a["suffix"], b["suffix"],
                                                                                 row["clear_new"]))
    adjacent = [p for p in pairs if p["kind"] == "layer" and
                by[p["a"]]["piece"] == "P2" and by[p["b"]]["piece"] == "P1"]
    return {"pieces": pieces, "pairs": pairs, "layer_gaps": adjacent, "bands": BANDS, "pitch_min_cm": PITCH_MIN_CM}


# ------------------------------------------------------------------------------------------------ motion keys
def rot_matrix(rpy):
    """UE FRotationMatrix rows; = s3_waves_v3_core.rot_matrix [prec]."""
    r, p, y = [math.radians(float(v)) for v in rpy]
    sr, cr, sp, cp, sy, cy = math.sin(r), math.cos(r), math.sin(p), math.cos(p), math.sin(y), math.cos(y)
    return ((cp * cy, cp * sy, sp),
            (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp),
            (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp))


def tf_box(key, box):
    """AABB (root-local) of a local box under a key transform (8 corners; conservative for the tiny roll)."""
    m = rot_matrix(key["rotation"])
    lo, hi = [1e18] * 3, [-1e18] * 3
    for cx in (box["min"][0], box["max"][0]):
        for cy in (box["min"][1], box["max"][1]):
            for cz in (box["min"][2], box["max"][2]):
                p = [key["location"][j] + cx * m[0][j] + cy * m[1][j] + cz * m[2][j] for j in range(3)]
                lo = [min(a, b) for a, b in zip(lo, p)]
                hi = [max(a, b) for a, b in zip(hi, p)]
    return lo, hi


def shifted_rows(rows, new_x=None):
    new_x = dict(NEW_X if new_x is None else new_x)
    out = []
    for r in rows:
        q = copy.deepcopy(r)
        q["mount_local"] = [float(new_x[r["suffix"]]), r["mount_local"][1], r["mount_local"][2]]
        out.append(q)
    return out


def path_clearance(plan_old, plan_new, rows, new_x=None):
    """plan_*: s3_waves_v3_core.plan_motion() outputs for the old and the shifted mounts.  Checks (1) the shifted keys
    differ from the old ONLY in Location.X, by exactly dx, at every key; (2) at EVERY keyed frame no two pieces'
    root-local AABBs intersect; returns the minimum x clearance among pairs whose y and z intervals overlap."""
    new_x = dict(NEW_X if new_x is None else new_x)
    by_row = {r["suffix"]: r for r in rows}
    po = {p["suffix"]: p for p in plan_old["pieces"]}
    pn = {p["suffix"]: p for p in plan_new["pieces"]}
    req(sorted(po) == sorted(pn) == sorted(by_row), "PLAN_PIECES")
    worst_other = 0.0
    for s in po:
        dx = new_x[s] - by_row[s]["mount_local"][0]
        req(len(po[s]["keys"]) == len(pn[s]["keys"]), "KEY_COUNT|%s" % s)
        for ko, kn in zip(po[s]["keys"], pn[s]["keys"]):
            req(ko["frame"] == kn["frame"], "KEY_FRAME|%s" % s)
            req(abs((kn["location"][0] - ko["location"][0]) - dx) < 1e-9, "KEY_DX|%s|%d" % (s, ko["frame"]))
            other = [abs(a - b) for a, b in zip(ko["location"][1:] + ko["rotation"] + ko["scale"],
                                               kn["location"][1:] + kn["rotation"] + kn["scale"])]
            worst_other = max(worst_other, max(other))
    req(worst_other < 1e-9, "NON_X_CHANNEL_CHANGED|%g" % worst_other)
    frames = [k["frame"] for k in next(iter(pn.values()))["keys"]]
    names = sorted(pn)
    min_x_clear = {"cm": 1e9, "frame": None, "pair": None}
    hits = []
    x_extent_drift = 0.0
    for i, f in enumerate(frames):
        boxes = {s: tf_box(pn[s]["keys"][i], by_row[s]["bounds_cm"]) for s in names}
        for s in names:
            rest = [new_x[s] + by_row[s]["bounds_cm"]["min"][0], new_x[s] + by_row[s]["bounds_cm"]["max"][0]]
            x_extent_drift = max(x_extent_drift, abs(boxes[s][0][0] - rest[0]), abs(boxes[s][1][0] - rest[1]))
        for a_i, a in enumerate(names):
            for b in names[a_i + 1:]:
                (alo, ahi), (blo, bhi) = boxes[a], boxes[b]
                ov = [min(ahi[j], bhi[j]) - max(alo[j], blo[j]) for j in range(3)]
                if ov[1] > 0 and ov[2] > 0:
                    xc = -ov[0]
                    if xc < min_x_clear["cm"]:
                        min_x_clear = {"cm": round(xc, 4), "frame": f, "pair": [a, b]}
                    if ov[0] > 0:
                        hits.append({"frame": f, "a": a, "b": b, "overlap": ov})
    req(not hits, "PATH_INTERPENETRATION|%s" % hits[:3])
    return {"frames_checked": len(frames), "first": frames[0], "last": frames[-1], "pieces": len(names),
            "non_x_max_diff": worst_other, "min_x_clearance_yz_overlapping": min_x_clear, "hits": 0,
            "x_extent_drift_max_cm": round(x_extent_drift, 9),
            "note": "keys recomputed from the v3 motion formula (s3_waves_v3_core.plan_motion) -- [inf] equal to the "
                    "live keys (MOTION_APPLY read them back at 0.001: s3_waves_v3_motion_record.json); APPLY re-reads "
                    "every live key and refuses unless every Location.X key equals the old mount x"}


def shift_x_keys(orig, old_x, dx, tol=KEY_TOL_CM):
    """orig: [[frame, value], ...] read live.  Every value must equal old_x (the v3 motion keys are rest x + 0:
    s3_waves_v3_core.piece_key, roll-only rotation -> x term 0) -> new [[frame, value + dx]]."""
    req(len(orig) > 0, "NO_X_KEYS")
    bad = [k for k in orig if abs(float(k[1]) - float(old_x)) > tol]
    req(not bad, "X_KEY_NOT_REST|%d keys off old x %.3f, first %s" % (len(bad), old_x, bad[:2]))
    frames = [int(k[0]) for k in orig]
    req(frames == sorted(frames) and len(set(frames)) == len(frames), "X_KEY_FRAMES_UNSORTED")
    return [[int(f), float(v) + float(dx)] for f, v in orig]


def revert_x_keys(current, originals, dx, tol=KEY_TOL_CM):
    """Field-scoped revert: frames must match the recorded originals and every current value must be original + dx
    (no foreign edit since APPLY) -> the recorded original values."""
    req([int(k[0]) for k in current] == [int(k[0]) for k in originals], "REVERT_X_FRAMES_CHANGED")
    drift = [c for c, o in zip(current, originals) if abs(float(c[1]) - (float(o[1]) + dx)) > tol]
    req(not drift, "REVERT_X_DRIFT|%d keys not original+dx, first %s" % (len(drift), drift[:2]))
    return [[int(f), float(v)] for f, v in originals]


# ------------------------------------------------------------------------------------------------ sequence fingerprint
def value_sha(rows):
    """sha256 of a canonical key list (values rounded to 1e-4 so float->double transport noise cannot matter)."""
    canon = [[r[0], round(float(r[1]), 4) if isinstance(r[1], (int, float)) and not isinstance(r[1], bool) else r[1]]
             for r in rows]
    return hashlib.sha256(json.dumps(canon, sort_keys=True).encode("utf-8")).hexdigest()


def fingerprint_diff(before, after, allowed=None):
    """before/after: {channel_path: {"n": int, "sha": str, "default": ..., ...}} for EVERY binding/track/section/channel
    of LS_DevScene_03 (plus "struct" rows for bindings/tracks/sections).  allowed: {channel_path: expected_after_sha}.
    -> list of violations (empty = only the allowed channels changed, each exactly as planned)."""
    allowed = dict(allowed or {})
    v = []
    for k in sorted(set(before) | set(after)):
        if k in allowed:
            if k not in after or after[k].get("sha") != allowed[k]:
                v.append({"path": k, "why": "ALLOWED_CHANNEL_NOT_AS_PLANNED", "got": (after.get(k) or {}).get("sha"),
                          "want": allowed[k]})
            elif k in before and {kk: vv for kk, vv in before[k].items() if kk != "sha"} != \
                    {kk: vv for kk, vv in after[k].items() if kk != "sha"}:
                v.append({"path": k, "why": "ALLOWED_CHANNEL_META_CHANGED"})
            continue
        if k not in before:
            v.append({"path": k, "why": "ADDED"})
        elif k not in after:
            v.append({"path": k, "why": "REMOVED"})
        elif before[k] != after[k]:
            v.append({"path": k, "why": "CHANGED", "before": before[k], "after": after[k]})
    missing = [k for k in allowed if k not in before]
    for k in missing:
        v.append({"path": k, "why": "ALLOWED_PATH_NOT_IN_BEFORE"})
    return v


def track_path(prefix, ti, cls, name):
    return "%s/T%d:%s:%s" % (prefix, ti, cls, name)


def channel_path(track_p, si, ci, cname):
    return "%s/S%d/C%d:%s" % (track_p, si, ci, cname)


def x_channel_path(guid, track_index, section_index, channel_index):
    """Fingerprint path of a wave binding's motion-track Location.X channel (same format the UE fingerprint writes)."""
    return channel_path(track_path("B:%s" % guid, track_index, "MovieScene3DTransformTrack", MOTION_TRACK),
                        section_index, channel_index, LOC_X)


def near(a, b, tol):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def expected_tracks_report(track_names):
    present = sorted(n for n in EXPECTED_OTHER_TRACKS if n in track_names)
    return {"expected": list(EXPECTED_OTHER_TRACKS), "present": present,
            "absent": sorted(set(EXPECTED_OTHER_TRACKS) - set(present)), "blocking": False}


# ------------------------------------------------------------------------------------------------ census
def census_scope_ok(census, content, maps):
    """Exact dirty set: content == content, maps == maps.  Anything else (e.g. a Klara streamed level) -> refuse."""
    return census == {"content": sorted(content), "maps": sorted(maps)}


def apply_scope(census):
    """After APPLY's edits the dirty set must be EXACTLY the level + LS_DevScene_03.  A clean level = the swap did not
    register (2 Oct: a swap 'never dirtied the level') -> refuse, save nothing."""
    req(WORLD in census["maps"], "LEVEL_NOT_DIRTY|the mesh/x edits did not dirty %s: nothing saved" % WORLD)
    req(census["maps"] == [WORLD], "FOREIGN_MAP_DIRTY|%s (Klara streamed level? stop, Don't-Save restart)" %
        [m for m in census["maps"] if m != WORLD])
    req(census["content"] == [ROOT_SEQ], "CONTENT_SCOPE|%s" % census["content"])
    return True


# ------------------------------------------------------------------------------------------------ apply plan / records
def plan_apply(rows, live, layout):
    """live: {suffix: {"actor_path", "label_count", "parent_label", "mesh", "relative", "binding_guid",
    "motion_tracks": [names], "x_keys": [[f, v]], "x_channel_path"}} -> per-piece ops + allowed fingerprint map."""
    lay = {p["suffix"]: p for p in layout["pieces"]}
    ops, allowed = [], {}
    for r in rows:
        s = r["suffix"]
        L = live.get(s)
        req(L is not None, "LIVE_MISSING|%s" % s)
        req(L["label_count"] == 1, "LABEL_COUNT|%s|%d" % (r["label"], L["label_count"]))
        req(L["actor_path"] == r["actor_path"], "ACTOR_PATH|%s|%s" % (r["label"], L["actor_path"]))
        req(L["parent_label"] == ROOT_LABEL, "PARENT|%s|%s" % (r["label"], L["parent_label"]))
        req(L["mesh"] == r["live_mesh"], "MESH_NOT_LIVE_V3|%s|%s" % (r["label"], L["mesh"]))
        rel = L["relative"]["location"]
        req(all(abs(a - b) <= REL_TOL_CM for a, b in zip(rel, r["mount_local"])), "RELATIVE|%s|%s" % (r["label"], rel))
        req(L.get("binding_guid") and L.get("x_keys") is not None, "NO_MOTION_BINDING|%s" % r["label"])
        req(L["motion_tracks"] == [MOTION_TRACK], "MOTION_TRACKS|%s|%s" % (r["label"], L["motion_tracks"]))
        dx = lay[s]["dx"]
        new_keys = shift_x_keys(L["x_keys"], r["mount_local"][0], dx)
        allowed[L["x_channel_path"]] = value_sha(new_keys)
        ops.append({"suffix": s, "label": r["label"], "actor_path": r["actor_path"], "binding_guid": L["binding_guid"],
                    "x_channel_path": L["x_channel_path"],
                    "mesh": {"before": r["live_mesh"], "after": r["mesh"]},
                    "relative_location": {"before": list(rel), "after": [lay[s]["new_x"], rel[1], rel[2]]},
                    "dx": dx, "x_keys": {"count": len(new_keys), "before_sha": value_sha(L["x_keys"]),
                                         "after_sha": value_sha(new_keys), "before_first_last": [L["x_keys"][0],
                                                                                                 L["x_keys"][-1]]}})
    return {"ops": ops, "allowed": allowed}


def originals_from_live(rows, live):
    return {"schema": "s3waves_t5o_originals/1",
            "pieces": {r["suffix"]: {"actor_path": live[r["suffix"]]["actor_path"], "mesh": live[r["suffix"]]["mesh"],
                                     "relative": live[r["suffix"]]["relative"],
                                     "binding_guid": live[r["suffix"]]["binding_guid"],
                                     "x_channel_path": live[r["suffix"]]["x_channel_path"],
                                     "x_keys": live[r["suffix"]]["x_keys"]} for r in rows}}


def revert_plan(record, originals, live):
    """Field-scoped: per piece mesh (must be the t5o mesh now), relative x (must be the new x), X keys (original+dx)."""
    ops, allowed = [], {}
    for op in record["plan"]["ops"]:
        s = op["suffix"]
        o, L = originals["pieces"][s], live[s]
        req(L["actor_path"] == o["actor_path"], "REVERT_ACTOR|%s" % s)
        req(L["mesh"] == op["mesh"]["after"], "REVERT_MESH_DRIFT|%s|%s" % (s, L["mesh"]))
        req(all(abs(a - b) <= REL_TOL_CM for a, b in zip(L["relative"]["location"], op["relative_location"]["after"])),
            "REVERT_RELATIVE_DRIFT|%s|%s" % (s, L["relative"]["location"]))
        keys = revert_x_keys(L["x_keys"], o["x_keys"], op["dx"])
        allowed[L["x_channel_path"]] = value_sha(keys)
        ops.append({"suffix": s, "actor_path": o["actor_path"], "mesh": o["mesh"],
                    "relative_location": o["relative"]["location"], "x_keys": keys,
                    "x_channel_path": L["x_channel_path"]})
    return {"ops": ops, "allowed": allowed}
