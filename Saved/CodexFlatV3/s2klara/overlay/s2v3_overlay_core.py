"""S2 V3 wings overlay -- PURE core (no unreal import; the offline harness exercises every function here).

Used by s2v3_overlay.py (the editor tool).  Holds: constants, args validation, her-wing table from the offline census,
manifest/record resolution of our meshes + pivot offsets, UE rotator maths (FRotationMatrix / FMatrix::Rotator),
key evaluation (LINEAR/CONSTANT only), the per-wing key plan (our pose = her pose composed with the pivot offset),
source-key hashes, box alignment check, sequence-fingerprint diff, census gates.

Tiers per claim: [decl] header/source we can read, [prec] in-repo precedent, [meas] a record/parse with a result,
[inf] inferred (reason given).
"""
import hashlib
import json
import math
import re

TOOL = "s2v3_overlay"
MARK = "S2V3OV"
CONFIRM_WORD = "S2V3OVERLAY"
MODES = ("DRY", "APPLY", "VARIANT", "RESYNC", "VERIFY", "REVERT")
READ_ONLY = ("DRY", "VERIFY")
VARIANTS = ("A", "B")

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"         # klara_hookin.py:61 [decl]
SCENE_SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"                   # klara_hookin_s2_args.json [meas]
HER_LEVEL = "/Game/Japanese_Alley/Maps/Japanese_Alley"                            # klara_hookin_s2_args.json [meas]
KLARA_LEVEL_HINTS = ("/Game/Japanese_Alley/", "/Game/KK_", "/Game/L_KK_")        # her map roots (memory klara-streamed)
HOOKIN_COPY = "/Game/InfinityStage/KlaraHookin/LS_NEW_SHRINE_S2Hangar"            # seq record S2 'copy' [meas]
HOOKIN_TRACK = "Klara Hookin - Replacement Shot"                                  # klara_hookin.py:76 [decl]
OVERLAY_TRACK = "S2 V3 Wings Overlay"                                             # conductor 8 Oct
HIDE_PREFIX = "S2 V3 Hide: "
OURS_PREFIX = "S2 V3 Wing: "
OUR_TRANSFORM_TRACK = "S2 V3 Fall (copied from Klara)"
EXPECTED_FOREIGN_PREFIXES = ("Klara Hookin - Ours Off: ", "Klara Hookin - Hers Dark: ",
                             "S2 Arrival Ours Dark: ", "S2 Arrival Strike: ")     # conductor 8 Oct; s2_vis_fix.py:13
EXPECTED_SECTION = (376, 3891)                                                    # seq record S2 after.target [meas]
TYPES = ("L", "R", "C")
TYPE_RE = {"L": re.compile(r"^SM_S2_L_Wing_Shrine\d*$"), "R": re.compile(r"^SM_S2_R_Wing_Shrine\d*$"),
           "C": re.compile(r"^SM_S2_ceiling_wing\d*$")}
CHANNELS = ("x", "y", "z", "roll", "pitch", "yaw")
UE_CHANNEL = {"x": "Location.X", "y": "Location.Y", "z": "Location.Z",
              "roll": "Rotation.X", "pitch": "Rotation.Y", "yaw": "Rotation.Z"}  # memory: Rotator is roll-pitch-yaw
INTERP_OK = ("RCIM_LINEAR", "RCIM_CONSTANT")
EXTRAP_OK = ("RCCE_CONSTANT", "CONSTANT")
PATH_KEYS = ("ue_path", "ue_asset", "asset_path", "unreal_path", "ue_mesh", "mesh_path", "mesh")
PIVOT_KEYS = ("pivot_offset_cm", "pivot_offset", "pivot_cm")
ROT_KEYS = ("rot_offset_deg", "rotation_offset_deg")
OWNER_KEYS = ("owner", "owners", "owner_tag", "owner_id")
PIVOT_FRAMES = ("her_local_world_cm", "our_local_cm")
DEFAULTS = {"align_tol_cm": 25.0, "align_refuse": True, "midpoint_tol_cm": 0.5, "midpoint_tol_deg": 0.05,
            "copy_channels": "all", "variant": "A", "rest_vs_actor_tol_cm": 2.0}


class PlanError(Exception):
    pass


def req(cond, msg):
    if not cond:
        raise PlanError(msg)


# ===================================================================================================== args
def confirm_for(mode):
    return "%s %s" % (mode, CONFIRM_WORD)


def validate_args(a):
    """-> list of problems (empty = ok).  Pure."""
    p = []
    mode = str(a.get("mode") or "").upper()
    if mode not in MODES:
        p.append("MODE: %r not in %s" % (a.get("mode"), MODES))
    if mode not in READ_ONLY and a.get("confirm") != confirm_for(mode):
        p.append("CONFIRM: want %r" % confirm_for(mode))
    if mode in ("APPLY", "VARIANT", "RESYNC", "REVERT") and not str(a.get("decided_by") or "").strip():
        p.append("NOT_DECIDED: decided_by is empty")
    v = str(a.get("variant") or DEFAULTS["variant"]).upper()
    if v not in VARIANTS:
        p.append("VARIANT: %r not in %s" % (a.get("variant"), VARIANTS))
    if str(a.get("copy_channels") or DEFAULTS["copy_channels"]) not in ("all", "z_only"):
        p.append("COPY_CHANNELS: 'all' or 'z_only'")
    ov = str(a.get("overlay_asset") or "")
    if not (ov.startswith("/Game/") and "/" in ov[6:]) or ov.startswith(("/Game/Japanese_Alley", "/Game/KK_")) or \
            ov in (SCENE_SEQ, HOOKIN_COPY):
        p.append("OVERLAY_ASSET: %r must be a new /Game/<ours>/<name> path" % ov)
    types = a.get("types") or {}
    for t in TYPES:
        if t not in types:
            p.append("TYPES: missing %s" % t)
            continue
        row = types[t]
        if row.get("pivot_frame", "her_local_world_cm") not in PIVOT_FRAMES:
            p.append("TYPES.%s.pivot_frame: %r not in %s" % (t, row.get("pivot_frame"), PIVOT_FRAMES))
        if not str(row.get("owner") or "").startswith("S2K_"):
            p.append("TYPES.%s.owner: %r must start with S2K_" % (t, row.get("owner")))
    sec = a.get("expected_section")
    if sec is not None and (not isinstance(sec, list) or len(sec) != 2):
        p.append("EXPECTED_SECTION: [start, end] display frames")
    return p


def opt(a, k):
    return a.get(k, DEFAULTS[k])


# ===================================================================================================== her wings
def her_wings_from_census(census):
    """her_wings_census.json -> 15 rows {label, actor_name, actor_path_rel, type, mesh, rel_loc, rel_scale}.
    Refuses unless exactly 5 L, 5 R, 5 C (her_wings_census.json [meas])."""
    rows = []
    for r in census.get("rows") or []:
        label = str(r.get("label") or "")
        t = next((k for k, rx in TYPE_RE.items() if rx.match(label)), None)
        if t is None:
            continue
        rows.append({"label": label, "type": t, "actor_name": str(r["actor"]).rsplit(".", 1)[-1],
                     "actor_path_rel": r["actor"], "mesh": r.get("mesh"), "rel_loc": r.get("RelativeLocation"),
                     "rel_scale": r.get("RelativeScale3D") or [1.0, 1.0, 1.0]})
    counts = {t: sum(1 for r in rows if r["type"] == t) for t in TYPES}
    req(counts == {"L": 5, "R": 5, "C": 5}, "HER_WING_COUNT|%s" % counts)
    req(len({r["label"] for r in rows}) == 15 and len({r["actor_name"] for r in rows}) == 15, "HER_WING_DUPLICATES")
    return sorted(rows, key=lambda r: r["label"])


# ===================================================================================================== manifest
def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _first(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return k, d[k]
    return None, None


def _owner_match(d, owner):
    for k in OWNER_KEYS:
        v = d.get(k)
        if isinstance(v, str) and v == owner:
            return True
        if isinstance(v, list) and owner in v:
            return True
    return False


def _vec3(v, what):
    req(isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v),
        "BAD_VEC3|%s|%r" % (what, v))
    return [float(x) for x in v]


def resolve_types(args, manifest, record):
    """-> ({type: resolved}, [unresolved problems]).  Precedence per field: args.types.T > pivot record > manifest.
    The manifest schema is UNKNOWN today (DerivedAssets/FlatV3/KlaraS2/ did not exist on 8 Oct 19:30) [meas], so
    entries are found by owner (owner/owners/owner_tag/owner_id == args.types.T.owner) and fields by alias lists."""
    out, problems = {}, []
    for t in TYPES:
        a = dict((args.get("types") or {}).get(t) or {})
        owner = a.get("owner")
        hits = {}
        for src_name, src in (("record", record), ("manifest", manifest)):
            if not src:
                continue
            cand = [d for d in _walk(src) if _owner_match(d, owner)]
            if len(cand) > 1:
                problems.append("%s: %d %s entries for owner %s (ambiguous)" % (t, len(cand), src_name, owner))
            elif cand:
                hits[src_name] = cand[0]
        row = {"type": t, "owner": owner, "sources": {}}
        for field, keys in (("mesh", PATH_KEYS), ("pivot_offset_cm", PIVOT_KEYS), ("rot_offset_deg", ROT_KEYS),
                            ("pivot_frame", ("pivot_frame",)), ("variants", ("variants",))):
            val, src = None, None
            if a.get(field) not in (None, "", {}):
                val, src = a[field], "args"
            else:
                for s in ("record", "manifest"):
                    if s in hits:
                        k, v = _first(hits[s], keys)
                        if k is not None:
                            val, src = v, "%s.%s" % (s, k)
                            break
            row[field] = val
            row["sources"][field] = src
        if row["rot_offset_deg"] is None:
            row["rot_offset_deg"], row["sources"]["rot_offset_deg"] = [0.0, 0.0, 0.0], "default(0,0,0)"
        if row["pivot_frame"] is None:
            row["pivot_frame"], row["sources"]["pivot_frame"] = "her_local_world_cm", "default"
        if not row["mesh"] or not str(row["mesh"]).startswith("/Game/"):
            problems.append("%s: mesh path unresolved (%r)" % (t, row["mesh"]))
        if row["pivot_offset_cm"] is None:
            problems.append("%s: pivot_offset_cm unresolved (manifest/record not present or no field)" % t)
        else:
            try:
                row["pivot_offset_cm"] = _vec3(row["pivot_offset_cm"], "%s.pivot" % t)
            except PlanError as e:
                problems.append(str(e))
        try:
            row["rot_offset_deg"] = _vec3(row["rot_offset_deg"], "%s.rot" % t)
        except PlanError as e:
            problems.append(str(e))
        v = row["variants"] or {}
        for name in VARIANTS:
            if not isinstance(v.get(name), dict) or not v[name]:
                problems.append("%s: variant %s material map missing ({slot_name: material path})" % (t, name))
        out[t] = row
    return out, problems


# ===================================================================================================== rotator maths
def rot_matrix(roll, pitch, yaw):
    """UE FRotationMatrix rows (X, Y, Z axes), row-vector convention: world = v.x*X + v.y*Y + v.z*Z
    [decl UE RotationTranslationMatrix.h -- FRotationTranslationMatrix ctor; reproduced, inf for 5.8 = unchanged]."""
    P, Y, R = (math.radians(pitch), math.radians(yaw), math.radians(roll))
    SP, CP, SY, CY, SR, CR = math.sin(P), math.cos(P), math.sin(Y), math.cos(Y), math.sin(R), math.cos(R)
    return [[CP * CY, CP * SY, SP],
            [SR * SP * CY - CR * SY, SR * SP * SY + CR * CY, -SR * CP],
            [-(CR * SP * CY + SR * SY), CY * SR - CR * SP * SY, CR * CP]]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def mat_mul(a, b):
    """Row-vector composition: v*a*b (apply a, then b)."""
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def apply_rot(m, v):
    return [v[0] * m[0][j] + v[1] * m[1][j] + v[2] * m[2][j] for j in range(3)]


def matrix_rotator(m):
    """FMatrix::Rotator() -> (roll, pitch, yaw) degrees [decl UE Matrix.cpp FMatrix::Rotator; inf unchanged in 5.8]."""
    X, Yax, Z = m
    pitch = math.degrees(math.atan2(X[2], math.sqrt(X[0] ** 2 + X[1] ** 2)))
    yaw = math.degrees(math.atan2(X[1], X[0]))
    sy = rot_matrix(0.0, pitch, yaw)[1]
    roll = math.degrees(math.atan2(_dot(Z, sy), _dot(Yax, sy)))
    return roll, pitch, yaw


def compose_pose(her, row):
    """her = (x, y, z, roll, pitch, yaw) world pose of HER actor; row = resolved type row.
    her_local_world_cm: pivot_offset is OUR origin in HER local axes, world cm (her scale already applied):
        our_loc = her_loc + R_her . offset ;   R_our = R_off then R_her.
    our_local_cm: pivot_offset is HER origin expressed in OUR local frame:  our_loc = her_loc - R_our . offset."""
    mh = rot_matrix(her[3], her[4], her[5])
    mo = rot_matrix(*row["rot_offset_deg"])
    mour = mat_mul(mo, mh)
    off = row["pivot_offset_cm"]
    if row["pivot_frame"] == "her_local_world_cm":
        d = apply_rot(mh, off)
        loc = [her[i] + d[i] for i in range(3)]
    else:
        d = apply_rot(mour, off)
        loc = [her[i] - d[i] for i in range(3)]
    roll, pitch, yaw = matrix_rotator(mour)
    return loc + [roll, pitch, yaw]


def wrap180(a):
    a = math.fmod(a + 180.0, 360.0)
    if a <= 0:
        a += 360.0
    return a - 180.0


def unwrap_near(value, ref):
    return value + 360.0 * round((ref - value) / 360.0)


def angle_diff(a, b):
    return abs(wrap180(a - b))


# ===================================================================================================== keys
def eval_channel(ch, t):
    """ch = {"keys": [[tick, value, interp], ...] sorted, "default": float|None}.  Constant extrapolation; LINEAR or
    CONSTANT segments only (anything else raises -- her keys are all RCIM_LINEAR [meas her_seq_decode.json])."""
    ks = ch["keys"]
    if not ks:
        req(ch.get("default") is not None, "CHANNEL_EMPTY_NO_DEFAULT")
        return float(ch["default"])
    if t <= ks[0][0]:
        return float(ks[0][1])
    if t >= ks[-1][0]:
        return float(ks[-1][1])
    lo, hi = 0, len(ks) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ks[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    t0, v0, i0 = ks[lo]
    t1, v1 = ks[hi][0], ks[hi][1]
    if i0 == "RCIM_CONSTANT":
        return float(v0)
    req(i0 == "RCIM_LINEAR", "NONLINEAR_SOURCE_KEY|interp=%s@%s" % (i0, t0))
    return float(v0) + (float(v1) - float(v0)) * (t - t0) / float(t1 - t0)


def source_problems(chans):
    """chans: {name: {"keys", "default", "pre", "post"}} -> refusals."""
    out = []
    for n in CHANNELS:
        c = chans.get(n)
        if c is None:
            out.append("MISSING_CHANNEL:%s" % n)
            continue
        bad = sorted({k[2] for k in c["keys"][:-1] if k[2] not in INTERP_OK})
        if bad:
            out.append("NONLINEAR_SOURCE:%s:%s" % (n, bad))
        for side in ("pre", "post"):
            if c["keys"] and c.get(side) not in EXTRAP_OK:
                out.append("EXTRAPOLATION:%s.%s=%s" % (n, side, c.get(side)))
        ts = [k[0] for k in c["keys"]]
        if ts != sorted(ts) or len(set(ts)) != len(ts):
            out.append("KEY_ORDER:%s" % n)
    return out


def canonical_rows(c):
    return [[int(k[0]), round(float(k[1]), 4), str(k[2])] for k in c["keys"]]


def channel_sha(c):
    blob = {"keys": canonical_rows(c), "default": None if c.get("default") is None else round(float(c["default"]), 4)}
    return hashlib.sha256(json.dumps(blob, sort_keys=True).encode("utf-8")).hexdigest()


def source_hashes(chans):
    per = {n: channel_sha(chans[n]) for n in CHANNELS}
    per["all"] = hashlib.sha256(json.dumps([per[n] for n in CHANNELS]).encode("utf-8")).hexdigest()
    return per


def plan_wing_keys(chans, row, copy_channels="all", tol_cm=0.5, tol_deg=0.05):
    """Our keys at the union of her key ticks.  -> {"keys": [[tick, x, y, z, roll, pitch, yaw]], "first", "rest",
    "midpoint_dev_cm", "midpoint_dev_deg", "problems"}.  z_only holds x/y/rotation at her REST (last) values."""
    probs = source_problems(chans)
    if probs:
        return {"keys": [], "problems": probs}
    src = dict(chans)
    if copy_channels == "z_only":
        last = max(max((k[0] for k in chans[n]["keys"]), default=0) for n in CHANNELS)
        for n in CHANNELS:
            if n != "z":
                src[n] = {"keys": [], "default": eval_channel(chans[n], last)}
    ticks = sorted({int(k[0]) for n in CHANNELS for k in src[n]["keys"]})
    req(ticks, "NO_SOURCE_KEYS")

    def pose_at(t):
        return compose_pose([eval_channel(src[n], t) for n in CHANNELS], row)

    keys, prev = [], None
    for t in ticks:
        p = pose_at(t)
        if prev is not None:
            for i in (3, 4, 5):
                p[i] = unwrap_near(p[i], prev[i])
        keys.append([t] + p)
        prev = p
    dev_cm, dev_deg = 0.0, 0.0
    for a, b in zip(keys, keys[1:]):
        tm = (a[0] + b[0]) / 2.0
        true = pose_at(tm)
        lin = [(a[i] + b[i]) / 2.0 for i in range(1, 7)]
        dev_cm = max(dev_cm, math.sqrt(sum((true[i] - lin[i]) ** 2 for i in range(3))))
        dev_deg = max(dev_deg, max(angle_diff(true[i], lin[i]) for i in (3, 4, 5)))
    problems = []
    if dev_cm > tol_cm or dev_deg > tol_deg:
        problems.append("MIDPOINT_DEVIATION|%.3f cm|%.4f deg (tol %s cm / %s deg)" % (dev_cm, dev_deg, tol_cm, tol_deg))
    return {"keys": keys, "first": keys[0], "rest": keys[-1], "midpoint_dev_cm": round(dev_cm, 4),
            "midpoint_dev_deg": round(dev_deg, 5), "problems": problems, "n": len(keys)}


def keys_sha(keys):
    canon = [[int(k[0])] + [round(float(v), 3) for v in k[1:]] for k in keys]
    return hashlib.sha256(json.dumps(canon).encode("utf-8")).hexdigest()


def keys_from_channels(chans):
    """Read-back form: {name: {"keys": [[tick, v, interp]]}} of OUR track -> [[tick, x..yaw]] (all channels must share
    ticks, else refuse)."""
    ticks = [k[0] for k in chans["x"]["keys"]]
    for n in CHANNELS:
        req([k[0] for k in chans[n]["keys"]] == ticks, "OUR_KEY_TICKS_DIFFER:%s" % n)
    return [[t] + [float(chans[n]["keys"][i][1]) for n in CHANNELS] for i, t in enumerate(ticks)]


def keys_equal(a, b, tol_cm=0.01, tol_deg=0.001):
    if len(a) != len(b):
        return False
    for ka, kb in zip(a, b):
        if int(ka[0]) != int(kb[0]):
            return False
        if any(abs(ka[i] - kb[i]) > tol_cm for i in (1, 2, 3)):
            return False
        if any(angle_diff(ka[i], kb[i]) > tol_deg for i in (4, 5, 6)):
            return False
    return True


# ===================================================================================================== box check
def box_alignment(our_box, her_box, her_scale, row):
    """our_box/her_box = [[minx,miny,minz],[maxx,maxy,maxz]] MESH-local.  Places our box in HER local (world-cm) frame
    via the pivot offset and compares with her box x her scale.  -> {"delta": {axis: [dmin, dmax]}, "max_yz_cm"}."""
    hb = [[her_box[0][i] * her_scale[i] for i in range(3)], [her_box[1][i] * her_scale[i] for i in range(3)]]
    hb = [[min(hb[0][i], hb[1][i]) for i in range(3)], [max(hb[0][i], hb[1][i]) for i in range(3)]]
    mo = rot_matrix(*row["rot_offset_deg"])
    corners = [[our_box[a][0], our_box[b][1], our_box[c][2]] for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    if row["pivot_frame"] == "her_local_world_cm":
        pts = [[apply_rot(mo, p)[i] + row["pivot_offset_cm"][i] for i in range(3)] for p in corners]
    else:
        off = apply_rot(mo, row["pivot_offset_cm"])
        pts = [[apply_rot(mo, p)[i] - off[i] for i in range(3)] for p in corners]
    ob = [[min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]]
    delta = {ax: [round(ob[0][i] - hb[0][i], 2), round(ob[1][i] - hb[1][i], 2)] for i, ax in enumerate("xyz")}
    return {"ours_in_her_frame": ob, "hers_scaled": hb, "delta": delta,
            "max_yz_cm": max(abs(v) for ax in "yz" for v in delta[ax])}


# ===================================================================================================== fingerprint
def value_sha(rows):
    canon = [[r[0], round(float(r[1]), 4) if isinstance(r[1], (int, float)) and not isinstance(r[1], bool) else r[1]]
             for r in rows]
    return hashlib.sha256(json.dumps(canon, sort_keys=True).encode("utf-8")).hexdigest()


def track_path(prefix, ti, cls, name):
    return "%s/T%d:%s:%s" % (prefix, ti, cls, name)


def fingerprint_diff(before, after, new_prefix=None):
    """Every row of `before` must be in `after`, identical.  Rows only in `after` must start with new_prefix (our
    track).  -> violations list.  new_prefix None = exact equality."""
    v = []
    for k in sorted(set(before) | set(after)):
        if k not in after:
            v.append({"path": k, "why": "REMOVED"})
        elif k not in before:
            if not (new_prefix and (k == new_prefix or k.startswith(new_prefix + "/"))):
                v.append({"path": k, "why": "UNEXPECTED_NEW"})
        elif before[k] != after[k]:
            v.append({"path": k, "why": "CHANGED", "before": before[k], "after": after[k]})
    return v


def our_track_prefix(fp_after, track_name=OVERLAY_TRACK):
    hits = [k for k, r in fp_after.items() if r.get("struct") == "track" and k.startswith("M/T")
            and k.endswith(":MovieSceneSubTrack:" + track_name)]
    return hits


def expected_foreign_report(bindings):
    """bindings: [{"name", "vis_props": [property names of MovieSceneVisibilityTrack]}] -> (report, problems)."""
    rep = {p: {"bindings": 0, "vis_tracks": 0, "not_bHidden": []} for p in EXPECTED_FOREIGN_PREFIXES}
    for b in bindings:
        for p in EXPECTED_FOREIGN_PREFIXES:
            if b["name"].startswith(p):
                rep[p]["bindings"] += 1
                rep[p]["vis_tracks"] += len(b["vis_props"])
                rep[p]["not_bHidden"] += [b["name"] for x in b["vis_props"] if x != "bHidden"]
    problems = ["FOREIGN_NOT_BHIDDEN_FIXED|%s|%s" % (p, r["not_bHidden"][:3]) for p, r in rep.items()
                if r["not_bHidden"]]
    if not any(r["bindings"] for r in rep.values()):
        problems.append("FOREIGN_PREFIXES_ABSENT (hookin/arrival bindings expected in LS_DevScene_02)")
    return rep, problems


# ===================================================================================================== census
def is_klara_package(p):
    return any(str(p).startswith(h) for h in KLARA_LEVEL_HINTS)


def census_gate(census, content, maps=()):
    """Exact scope: dirty content == content, dirty maps == maps; any Klara package dirty is named separately."""
    out = []
    klara = sorted(p for p in (census.get("content") or []) + (census.get("maps") or []) if is_klara_package(p))
    if klara:
        out.append("KLARA_PACKAGE_DIRTY|%s|STOP: nothing saved; Don't-Save restart" % klara)
    if sorted(census.get("content") or []) != sorted(content):
        out.append("CONTENT_CENSUS|got %s want %s" % (sorted(census.get("content") or []), sorted(content)))
    if sorted(census.get("maps") or []) != sorted(maps):
        out.append("MAP_CENSUS|got %s want %s" % (sorted(census.get("maps") or []), sorted(maps)))
    return out


def check_mode(args, in_pie, sequencer_open, record):
    """Early live gates -> problems."""
    p = list(validate_args(args))
    mode = str(args.get("mode") or "").upper()
    if in_pie:
        p.append("PIE_RUNNING (never end PIE: ask the operator to stop it)")
    if sequencer_open:
        p.append("SEQUENCER_OPEN|%s (close it: opening/scrubbing dirties the map)" % sequencer_open)
    applied = bool(record and record.get("applied"))
    if mode == "APPLY" and record is not None:
        p.append("RECORD_EXISTS (REVERT first, or rename a .failed record)")
    if mode in ("VARIANT", "RESYNC", "REVERT") and not applied:
        p.append("NO_APPLIED_RECORD")
    return p


# ===================================================================================================== plan digest
def plan_digest(plan):
    """Digest of what APPLY would write (DRY -> APPLY must match, else 'PLAN_CHANGED_SINCE_DRY')."""
    core = {"overlay": plan.get("overlay_asset"), "section": plan.get("section"), "params": plan.get("section_params"),
            "copy": plan.get("copy"), "variant": plan.get("variant"), "copy_rates": plan.get("copy_rates"),
            "types": {t: {k: r.get(k) for k in ("mesh", "pivot_offset_cm", "rot_offset_deg", "pivot_frame",
                                                 "variants")} for t, r in sorted((plan.get("types") or {}).items())},
            "wings": [{k: w.get(k) for k in ("label", "type", "her_actor_path", "source_hashes", "keys_sha")}
                      for w in plan.get("wings") or []]}
    return hashlib.sha256(json.dumps(core, sort_keys=True, default=str).encode("utf-8")).hexdigest()
