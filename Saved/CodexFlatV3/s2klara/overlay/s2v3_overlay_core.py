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
import struct

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
DEFAULT_OWNERS = {"L": "S2K_shrine_L", "R": "S2K_shrine_R", "C": "S2K_ceiling_C"}            # coordinator 8 Oct
LEVELS_TRACK = "Klara Levels (hookin)"                                            # klara_hookin.py:75 [decl]
HER_LEVEL_SHORT = "Japanese_Alley"
COVERAGES = ("scene", "cinematic")
PRE_POSES = ("auto", "rest", "first")
KIT = {"manifest_path": "DerivedAssets/FlatV3/KlaraS2/IMPORT_MANIFEST_KlaraS2.json",
       "pivot_path": "DerivedAssets/FlatV3/KlaraS2/pivot/pivot_offsets.json",
       "rzimport_plan_path": "DerivedAssets/FlatV3/KlaraS2/rzimport_plan_offline_KlaraS2.json"}
PIVOT_FRAMES = ("her_local_world_cm", "our_local_cm")
DEFAULTS = {"align_tol_cm": 25.0, "align_refuse": True, "midpoint_tol_cm": 0.5, "midpoint_tol_deg": 0.05,
            "fit_tol_cm": 0.1, "fit_tol_deg": 0.01,
            "copy_channels": "all", "variant": "A", "rest_vs_actor_tol_cm": 2.0, "coverage": "scene",
            "pre_section_pose": "auto"}


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
    if str(a.get("coverage") or DEFAULTS["coverage"]) not in COVERAGES:
        p.append("COVERAGE: %r not in %s" % (a.get("coverage"), COVERAGES))
    if str(a.get("pre_section_pose") or DEFAULTS["pre_section_pose"]) not in PRE_POSES:
        p.append("PRE_SECTION_POSE: %r not in %s" % (a.get("pre_section_pose"), PRE_POSES))
    for t in TYPES:
        row = types.get(t) or {}
        if row.get("pivot_frame", "her_local_world_cm") not in PIVOT_FRAMES:
            p.append("TYPES.%s.pivot_frame: %r not in %s" % (t, row.get("pivot_frame"), PIVOT_FRAMES))
        if not str(row.get("owner") or DEFAULT_OWNERS[t]).startswith("S2K_"):
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


# ===================================================================================================== kit (manifest)
def _vec3(v, what):
    req(isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v),
        "BAD_VEC3|%s|%r" % (what, v))
    return [float(x) for x in v]


def _close3(a, b, tol=1e-6):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def _parse_mat(text, fallback_folder):
    """A front_variants slot string -> (UE path | None, how).  Forms in IMPORT_MANIFEST_KlaraS2.json [meas]:
    '/Game/.../MI_X = ...' -> that path; 'MI_X (...)' / 'MI_X = ...' -> fallback_folder/MI_X; 'unchanged ...' -> None
    (the mesh's own slot material).  Anything else -> refusal."""
    s = str(text).strip()
    if s.lower().startswith("unchanged"):
        return None, "unchanged"
    m = re.match(r"^(/Game/[A-Za-z0-9_/]+)", s)
    if m:
        return m.group(1).rstrip("/"), "path"
    m = re.match(r"^(MI_[A-Za-z0-9_]+)\b", s)
    if m:
        req(fallback_folder, "MATERIAL_FOLDER_UNKNOWN|%s" % m.group(1))
        return "%s/%s" % (fallback_folder.rstrip("/"), m.group(1)), "name+folder"
    raise PlanError("MATERIAL_UNPARSEABLE|%r" % s[:80])


def kit_entry(owner, manifest, pivots, rzplan):
    """Our S2K kit for one owner (e.g. 'S2K_shrine_L') -> (row, problems).  Sources [meas, read 8 Oct ~20:30]:
      * pivot/pivot_offsets.json wings[<owner minus 'S2K_'>].child_relative_transform_ue (UE cm, roll-pitch-yaw) under
        child_transform_rule 'world(ours) = HerActorTransform(location, rotation only) * Translate(T) * RotZ(180)',
        which is compose_pose(..., pivot_frame='her_local_world_cm');
      * IMPORT_MANIFEST_KlaraS2.json meshes[asset 'SM_FlatV3_<owner>_*'].klara_s2 (pivot copy, her_actors,
        front_variants A/B);
      * rzimport_plan_offline_KlaraS2.json what_if_S2K_token.destinations[owner] (planned UE mesh + A MIs).  That is a
        PLAN (the import has not run: unreal_imported=false), so DRY re-checks that every path loads."""
    p, key = [], owner[4:] if owner.startswith("S2K_") else owner
    row = {"owner": owner, "sources": {}}
    pw = ((pivots or {}).get("wings") or {}).get(key)
    if pw is None:
        return row, ["PIVOT_ENTRY_MISSING|%s (pivot_offsets.json)" % key]
    rule = str((pivots or {}).get("child_transform_rule") or "")
    if "HerActorTransform(location, rotation only) * Translate(T) * RotZ" not in rule:
        p.append("PIVOT_RULE_UNKNOWN|%r (the tool composes Her * Translate(T) * Rot)" % rule[:90])
    ct = pw.get("child_relative_transform_ue") or {}
    try:
        row["pivot_offset_cm"] = _vec3(ct.get("location_cm"), "%s.location_cm" % key)
        row["rot_offset_deg"] = _vec3(ct.get("rotation_deg_roll_pitch_yaw"), "%s.rotation" % key)
        if not _close3(ct.get("scale") or [0, 0, 0], [1, 1, 1]):
            p.append("CHILD_SCALE_NOT_1|%s|%s" % (key, ct.get("scale")))
    except PlanError as e:
        p.append(str(e))
    row["pivot_frame"] = "her_local_world_cm"
    row["sources"]["pivot"] = "pivot_offsets.json wings.%s.child_relative_transform_ue" % key
    row["her_actors"] = list(pw.get("her_actors") or [])
    entries = [m for m in (manifest or {}).get("meshes") or []
               if str(m.get("asset", "")).startswith("SM_FlatV3_%s_" % owner)]
    if len(entries) != 1:
        p.append("MANIFEST_ENTRY_COUNT|%s|%d" % (owner, len(entries)))
        return row, p
    me = entries[0]
    ks = me.get("klara_s2") or {}
    row["asset"], row["slots_manifest"] = me.get("asset"), me.get("slots")
    if me.get("asset") != pw.get("our_asset"):
        p.append("ASSET_DISAGREE|manifest %s pivot %s" % (me.get("asset"), pw.get("our_asset")))
    mp = ks.get("pivot") or {}
    if not (_close3(mp.get("location_cm") or [1e9] * 3, row.get("pivot_offset_cm") or [0] * 3) and
            _close3(mp.get("rotation_deg_roll_pitch_yaw") or [1e9] * 3, row.get("rot_offset_deg") or [0] * 3)):
        p.append("PIVOT_SOURCES_DISAGREE|%s|manifest %s vs pivot file %s" % (owner, mp, ct))
    if sorted(ks.get("her_actors") or []) != sorted(row["her_actors"]):
        p.append("HER_ACTORS_DISAGREE|%s|manifest vs pivot file" % owner)
    dest = (((rzplan or {}).get("what_if_S2K_token") or {}).get("destinations") or {}).get(owner) or {}
    mesh = dest.get("mesh")
    if not mesh:
        folders = ((rzplan or {}).get("plan") or {}).get("mesh_folders") or {}
        suf = str(me.get("asset", "")).rsplit("_", 1)[-1]
        if folders.get(suf):
            mesh = "%s/%s" % (folders[suf], me["asset"])
    row["mesh"] = mesh
    row["sources"]["mesh"] = ("rzimport plan destinations" if dest.get("mesh") else
                              "rzimport plan mesh_folders" if mesh else None)
    if not mesh or mesh.rsplit("/", 1)[-1] != me.get("asset"):
        p.append("MESH_PATH_UNRESOLVED|%s|%s" % (owner, mesh))
    root = ((rzplan or {}).get("plan") or {}).get("root")
    row["variants"] = {}
    for v in VARIANTS:
        fv = (ks.get("front_variants") or {}).get(v) or {}
        vmap, folder = {}, None
        for slot in ("Front", "Flap", "Timber", "Edge"):     # other keys (notes, evidence) are not slots
            if slot not in fv:
                continue
            if v == "A":
                fb = dest[slot].rsplit("/", 1)[0] if dest.get(slot) else (root + "/Materials/Instances" if root else None)
            else:
                fb = folder                                  # B: a bare MI name lives beside B's Front path
            try:
                path, how = _parse_mat(fv[slot], fb)
            except PlanError as e:
                p.append("%s.%s.%s|%s" % (owner, v, slot, e))
                continue
            if path is None:
                continue
            if v == "A" and dest.get(slot) and dest[slot] != path:
                p.append("A_PATH_DISAGREE|%s|%s vs %s" % (slot, path, dest[slot]))
            if is_klara_package(path) or path.startswith("/Game/WetGround/"):
                p.append("VARIANT_USES_KLARA_ASSET|%s.%s|%s (copies only; never hers)" % (owner, v, path))
                continue
            vmap[slot] = path
            if how == "path" and folder is None:
                folder = path.rsplit("/", 1)[0]
        if not vmap.get("Front"):
            p.append("VARIANT_NO_FRONT|%s.%s" % (owner, v))
        row["variants"][v] = vmap
    row["sources"]["variants"] = "manifest klara_s2.front_variants"
    return row, p


def resolve_types(args, manifest, pivots, rzplan):
    """-> ({type: row}, problems).  args.types.T fields (mesh / pivot_offset_cm / rot_offset_deg / pivot_frame /
    variants) override the kit; everything else comes from kit_entry."""
    out, problems = {}, []
    for t in TYPES:
        a = dict((args.get("types") or {}).get(t) or {})
        owner = a.get("owner") or DEFAULT_OWNERS[t]
        row, p = kit_entry(owner, manifest, pivots, rzplan)
        row["type"] = t
        for field in ("mesh", "pivot_offset_cm", "rot_offset_deg", "pivot_frame", "variants"):
            if a.get(field) not in (None, "", {}):
                row[field] = a[field]
                row["sources"][field] = "args"
                if field == "mesh":
                    p = [x for x in p if not x.startswith("MESH_PATH_UNRESOLVED")]
        problems += ["%s|%s" % (t, x) for x in p]
        if not str(row.get("mesh") or "").startswith("/Game/"):
            problems.append("%s: mesh path unresolved (%r)" % (t, row.get("mesh")))
        if row.get("pivot_offset_cm") is None:
            problems.append("%s: pivot_offset_cm unresolved" % t)
        row.setdefault("rot_offset_deg", [0.0, 0.0, 0.0])
        row.setdefault("pivot_frame", "her_local_world_cm")
        row.setdefault("variants", {})
        out[t] = row
    return out, problems


def check_her_actor_lists(types, wings):
    """The kit's her_actors per type must be exactly the census labels of that type."""
    p = []
    for t, row in types.items():
        want = sorted(w["label"] for w in wings if w["type"] == t)
        if sorted(row.get("her_actors") or []) != want:
            p.append("KIT_HER_ACTORS|%s|kit %s census %s" % (t, sorted(row.get("her_actors") or []), want))
    return p


# ===================================================================================================== coverage / hold
def coverage_plan(mode, hookin_range, level_vis_range, parent_fps, child_tick):
    """'scene' (Gary 8 Oct, 'ours throughout'): our subsection covers [her level becomes visible, hookin end).  Her
    level is hidden before that by the hookin's Level Visibility track [meas seq record S2: [104, 3891]], so our wings
    must not appear earlier either.  'cinematic': exactly the hookin section.
    -> {"range", "pre_frames", "pre_ticks"}; pre_ticks shifts her keys inside OUR sequence (our local 0 == range start)."""
    hs, he = int(hookin_range[0]), int(hookin_range[1])
    if mode == "cinematic":
        return {"range": [hs, he], "pre_frames": 0, "pre_ticks": 0, "pre_seconds": 0.0}
    req(mode == "scene", "COVERAGE_MODE|%r" % mode)
    req(level_vis_range is not None, "LEVEL_VIS_SECTION_MISSING (cannot read when her level becomes visible)")
    ls, le = int(level_vis_range[0]), int(level_vis_range[1])
    req(ls <= hs, "LEVEL_VISIBLE_AFTER_HOOKIN|%s vs %s" % (ls, hs))
    req(le >= he, "LEVEL_HIDDEN_BEFORE_HOOKIN_END|%s vs %s" % (le, he))
    secs = (hs - ls) * float(parent_fps[1]) / float(parent_fps[0])
    ticks = secs * float(child_tick[0]) / float(child_tick[1])
    req(abs(ticks - round(ticks)) < 1e-6, "PRE_ROLL_NOT_ON_TICK_GRID|%.6f" % ticks)
    return {"range": [ls, he], "pre_frames": hs - ls, "pre_ticks": int(round(ticks)), "pre_seconds": secs}


def classify_pre_pose(live, first, rest, tol_cm=2.0, tol_deg=0.05):
    """What her wing shows BEFORE her section starts.  live = her actor's editor-world pose (Sequencer closed = the
    level state); first/rest = her keys' first/last pose.  -> 'rest' | 'first' | 'unclear'."""
    def near(a, b):
        return (sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5 <= tol_cm and
                all(angle_diff(a[i], b[i]) <= tol_deg for i in (3, 4, 5)))
    if near(live, rest):
        return "rest"
    if near(live, first):
        return "first"
    return "unclear"


def with_hold(keys, pre_ticks, hold_pose):
    """Shift her-timed keys by pre_ticks and prepend a CONSTANT hold key at 0, so our wing sits in her pre-section
    pose over [range start, her section start), then follows her keys.  -> (keys, interps)."""
    if not pre_ticks:
        return [list(k) for k in keys], ["RCIM_LINEAR"] * len(keys)
    req(keys and keys[0][0] >= 0, "NEGATIVE_KEY_TICK")
    shifted = [[k[0] + pre_ticks] + list(k[1:]) for k in keys]
    hold = [0] + list(hold_pose)
    for i in (4, 5, 6):                                   # Euler continuity with the first fall key
        hold[i] = unwrap_near(hold[i], shifted[0][i])
    return [hold] + shifted, ["RCIM_CONSTANT"] + ["RCIM_LINEAR"] * len(shifted)


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


def source_problems(chans, linear_only=True):
    """chans: {name: {"keys", "default", "pre", "post"}} -> refusals.  linear_only=False (the SAMPLED path, live DRY
    S2V3OV-20261008-212010: the hookin copy's keys are RCIM_CUBIC) accepts any interpolation, because UE evaluates them."""
    out = []
    for n in CHANNELS:
        c = chans.get(n)
        if c is None:
            out.append("MISSING_CHANNEL:%s" % n)
            continue
        bad = sorted({k[2] for k in c["keys"][:-1] if k[2] not in INTERP_OK})
        if bad and linear_only:
            out.append("NONLINEAR_SOURCE:%s:%s" % (n, bad))
        for side in ("pre", "post"):
            if c["keys"] and c.get(side) not in EXTRAP_OK:
                out.append("EXTRAPOLATION:%s.%s=%s" % (n, side, c.get(side)))
        ts = [k[0] for k in c["keys"]]
        if ts != sorted(ts) or len(set(ts)) != len(ts):
            out.append("KEY_ORDER:%s" % n)
    return out


def canonical_rows(c):
    """[tick, value, interp] plus, when read live, tangent mode / arrive / leave / weight mode: a re-ingest that only
    changes a tangent still changes the hash (cubic keys, live DRY 8 Oct)."""
    return [[int(k[0]), round(float(k[1]), 4), str(k[2])] +
            [round(float(x), 4) if isinstance(x, (int, float)) else str(x) for x in k[3:]] for k in c["keys"]]


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


def q32(v):
    """float -> the nearest IEEE float32, back as a Python float.  WHY (measured 8 Oct, APPLY S2V3OV-20261008-212744):
    the read-back keys_sha of all 6 wings named in the failure equals keys_sha(plan keys with every LOCATION value
    float32-quantised) -- i.e. our keys come back float32 although MovieScene3DTransformSection.h:307,311 declares
    FMovieSceneDoubleChannel and MovieSceneScriptingDouble.h:245 AddKey takes a double [decl]; where the narrowing
    happens is NOT known [inf: not in the headers we have; no private .cpp in UE_5.8]."""
    return struct.unpack("<f", struct.pack("<f", float(v)))[0]


def _canon_value(v, is_angle):
    if is_angle:
        v = wrap180(float(v))
    return round(q32(v), 2) + 0.0                         # + 0.0: -0.0 and 0.0 hash alike


def keys_sha(keys, interps=None):
    """Drift-detection hash of a key list [[tick, x, y, z, roll, pitch, yaw]].  Values: angles wrapped to (-180, 180],
    float32-quantised, rounded to 2 decimals (0.01 cm / 0.01 deg).  NOT the read-back proof (that is keys_compare); the
    APPLY record stores the sha of the READ-BACK keys so VERIFY/RESYNC compare read-back to read-back."""
    canon = [[int(k[0])] + [_canon_value(v, i >= 3) for i, v in enumerate(k[1:])] for k in keys]
    blob = canon if interps is None else [canon, list(interps)]
    return hashlib.sha256(json.dumps(blob).encode("utf-8")).hexdigest()


def keys_from_channels(chans):
    """Read-back form: {name: {"keys": [[tick, v, interp]]}} of OUR track -> ([[tick, x..yaw]], interps).  All
    channels must share ticks AND per-key interpolation, else refuse."""
    ticks = [k[0] for k in chans["x"]["keys"]]
    interps = [k[2] for k in chans["x"]["keys"]]
    for n in CHANNELS:
        req([k[0] for k in chans[n]["keys"]] == ticks, "OUR_KEY_TICKS_DIFFER:%s" % n)
        req([k[2] for k in chans[n]["keys"]] == interps, "OUR_KEY_INTERP_DIFFER:%s" % n)
    return [[t] + [float(chans[n]["keys"][i][1]) for n in CHANNELS] for i, t in enumerate(ticks)], interps


KEY_TOL_CM = 0.01                                         # float32 spacing at |v| <= 131072 cm is <= 0.0078 cm
KEY_TOL_DEG = 0.001                                       # after wrapping the difference to (-180, 180]


def keys_compare(wrote, wrote_interps, read, read_interps, tol_cm=KEY_TOL_CM, tol_deg=KEY_TOL_DEG):
    """NUMERIC read-back proof for OUR keys.  Tick list must be identical, interpolation identical per key, each value
    within tol_cm (location) / tol_deg (rotation, difference wrapped so 316.43 vs -43.57 is 0).  ->
    {"ok", "problems": [...], "worst": {channel: {"diff", "tick", "wrote", "read"}}, "first_bad": {...} | None}."""
    out = {"ok": True, "problems": [], "worst": {}, "first_bad": None}
    wt, rt = [int(k[0]) for k in wrote], [int(k[0]) for k in read]
    if wt != rt:
        i = next((j for j, (a, b) in enumerate(zip(wt, rt)) if a != b), min(len(wt), len(rt)))
        out["problems"].append("TICKS|wrote %d keys read %d|first differing index %d: wrote %s read %s" % (
            len(wt), len(rt), i, wt[i] if i < len(wt) else None, rt[i] if i < len(rt) else None))
        out["ok"] = False
        return out
    wi, ri = list(wrote_interps or []), list(read_interps or [])
    if wi != ri:
        i = next((j for j, (a, b) in enumerate(zip(wi, ri)) if a != b), min(len(wi), len(ri)))
        out["problems"].append("INTERP|first differing key %d tick %s: wrote %s read %s" % (
            i, wt[i] if i < len(wt) else None, wi[i] if i < len(wi) else None, ri[i] if i < len(ri) else None))
        out["ok"] = False
    for ci, ch in enumerate(CHANNELS):
        is_angle = ci >= 3
        tol = tol_deg if is_angle else tol_cm
        worst = {"diff": 0.0, "tick": None, "wrote": None, "read": None}
        for kw, kr in zip(wrote, read):
            a, b = float(kw[1 + ci]), float(kr[1 + ci])
            d = angle_diff(a, b) if is_angle else abs(a - b)
            if d > worst["diff"] or worst["tick"] is None:
                worst = {"diff": d, "tick": int(kw[0]), "wrote": a, "read": b}
            if d > tol and out["first_bad"] is None:
                out["first_bad"] = {"tick": int(kw[0]), "channel": ch, "wrote": a, "read": b, "diff": d, "tol": tol}
        out["worst"][ch] = worst
        if worst["diff"] > tol:
            out["ok"] = False
            out["problems"].append("VALUE|%s worst %.6g > tol %g @tick %s (wrote %r read %r)" % (
                ch, worst["diff"], tol, worst["tick"], worst["wrote"], worst["read"]))
    if out["problems"]:
        out["ok"] = False
    return out


def keys_compare_text(res):
    """One line for a failure message: problems, first bad key, worst diff per channel."""
    fb = res.get("first_bad")
    first = ("first_bad tick=%s ch=%s wrote=%r read=%r diff=%.6g" % (fb["tick"], fb["channel"], fb["wrote"],
                                                                     fb["read"], fb["diff"]) if fb else "first_bad none")
    worst = ",".join("%s=%.3g@%s" % (c, w["diff"], w["tick"]) for c, w in (res.get("worst") or {}).items())
    return "%s; %s; worst[%s]" % (" / ".join(res.get("problems") or []) or "ok", first, worst)


def keys_equal(a, b, tol_cm=KEY_TOL_CM, tol_deg=KEY_TOL_DEG):
    """Values + ticks only (no interps): keys_compare with the interps taken as equal."""
    return keys_compare(a, None, b, None, tol_cm, tol_deg)["ok"]


# ===================================================================================================== sampled source
def sampling_grid(key_ticks, tick_res, child_fps, parent_fps, pre_ticks=0):
    """Where to sample her channels.  UE's EvaluateKeys steps one frame of the REQUESTED rate (in ticks) from the range's
    inclusive lower tick to its exclusive upper tick and evaluates at each snapped tick
    [decl MovieSceneScriptingChannel.h:218-245].  The interval is chosen as gcd(child frame, parent frame) in ticks, so the
    samples include EVERY tick the show can render at: each child display frame (30 fps = 800 ticks) and each parent
    frame mapped into the child (25 fps = 960 ticks; the pre-roll 261120 is a multiple too) -> 160 ticks = 150 fps.
    The range is built with make_range(start, duration) in DISPLAY frames (memory/coordinator: a default
    SequencerScriptingRange is 60000 fps and returns ~1 value).  -> {"start_frame", "duration", "rate", "interval",
    "ticks", "expected_count"}."""
    req(key_ticks, "NO_SOURCE_KEYS")
    tr = float(tick_res[0]) / float(tick_res[1])
    tpc = tr * child_fps[1] / float(child_fps[0])
    tpp = tr * parent_fps[1] / float(parent_fps[0])
    req(abs(tpc - round(tpc)) < 1e-9 and abs(tpp - round(tpp)) < 1e-9, "FRAME_NOT_ON_TICK_GRID|%s|%s" % (tpc, tpp))
    interval = math.gcd(int(round(tpc)), int(round(tpp)))
    req(pre_ticks % interval == 0, "PRE_ROLL_OFF_SAMPLE_GRID|%s|%s" % (pre_ticks, interval))
    rate = tr / interval
    req(abs(rate - round(rate)) < 1e-9, "SAMPLE_RATE_NOT_INTEGER|%s" % rate)
    start = int(math.floor(min(key_ticks) / tpc))
    end = int(math.floor(max(key_ticks) / tpc)) + 2               # one display frame past the last key: proves the hold
    duration = end - start
    per = int(round(tpc)) // interval
    ticks = [int(round(start * tpc)) + i * interval for i in range(duration * per)]
    return {"start_frame": start, "duration": duration, "rate": [int(round(rate)), 1], "interval": interval,
            "ticks": ticks, "expected_count": duration * per, "ticks_per_child_frame": int(round(tpc)),
            "ticks_per_parent_frame": int(round(tpp))}


def lerp_pose(a, b, t):
    """Pose at tick t between keys a=[tick, 6 values], b=[...] (linear per channel, as Sequencer's LINEAR keys)."""
    f = (t - a[0]) / float(b[0] - a[0])
    return [a[i] + (b[i] - a[i]) * f for i in range(1, 7)]


def _within(p, q, tol_cm, tol_deg):
    return (math.sqrt(sum((p[i] - q[i]) ** 2 for i in range(3))) <= tol_cm and
            all(abs(p[i] - q[i]) <= tol_deg for i in (3, 4, 5)))


def decimate(samples, fit_cm, fit_deg):
    """Greedy: keep the fewest sample points such that LINEAR interpolation between kept points reproduces every sample
    within (fit_cm, fit_deg).  samples = [[tick, x, y, z, roll, pitch, yaw]] (angles already unwrapped)."""
    keep, i, n = [0], 0, len(samples)
    while i < n - 1:
        j = i + 1
        while j + 1 < n:
            cand, ok = j + 1, True
            for k in range(i + 1, cand):
                if not _within(lerp_pose(samples[i], samples[cand], samples[k][0]), samples[k][1:], fit_cm, fit_deg):
                    ok = False
                    break
            if not ok:
                break
            j = cand
        keep.append(j)
        i = j
    return [samples[k] for k in keep]


def eval_linear_keys(keys, t):
    if t <= keys[0][0]:
        return list(keys[0][1:])
    if t >= keys[-1][0]:
        return list(keys[-1][1:])
    lo, hi = 0, len(keys) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if keys[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    return lerp_pose(keys[lo], keys[hi], t)


def plan_wing_keys_sampled(samples, ticks, row, copy_channels="all", tol_cm=0.5, tol_deg=0.05, fit_cm=0.1,
                           fit_deg=0.01):
    """samples = {channel: [UE-evaluated values at `ticks`]} of HER binding (any interpolation: cubic, linear, constant).
    Compose each sample with the child transform, decimate to LINEAR keys, then GATE: our keys evaluated at EVERY sample
    tick (= every renderable tick) vs her composed pose: max <= tol_cm / tol_deg, else refused."""
    req(all(len(samples[n]) == len(ticks) for n in CHANNELS), "SAMPLE_LENGTHS_DIFFER")
    src = {n: list(samples[n]) for n in CHANNELS}
    if copy_channels == "z_only":
        for n in CHANNELS:
            if n != "z":
                src[n] = [src[n][-1]] * len(ticks)
    truth, prev = [], None
    for i, t in enumerate(ticks):
        p = compose_pose([src[n][i] for n in CHANNELS], row)
        if prev is not None:
            for a in (3, 4, 5):
                p[a] = unwrap_near(p[a], prev[a])
        truth.append([t] + p)
        prev = p
    keys = decimate(truth, fit_cm, fit_deg)
    dev_cm = dev_deg = 0.0
    for tr in truth:
        q = eval_linear_keys(keys, tr[0])
        dev_cm = max(dev_cm, math.sqrt(sum((q[i] - tr[1 + i]) ** 2 for i in range(3))))
        dev_deg = max(dev_deg, max(angle_diff(q[i], tr[1 + i]) for i in (3, 4, 5)))
    problems = []
    if dev_cm > tol_cm or dev_deg > tol_deg:
        problems.append("SAMPLED_GATE|%.4f cm|%.5f deg (tol %s cm / %s deg)" % (dev_cm, dev_deg, tol_cm, tol_deg))
    return {"keys": keys, "first": keys[0], "rest": keys[-1], "n": len(keys), "samples": len(truth),
            "max_dev_cm": round(dev_cm, 5), "max_dev_deg": round(dev_deg, 6), "problems": problems}


def key_alignment(chans, ticks, samples, tol=1e-3):
    """Proof that sample i really is tick ticks[i]: at every key tick on the grid, UE's evaluated value must equal the
    key's own value.  -> {"checked", "on_grid", "max_err", "problems"}."""
    idx = {t: i for i, t in enumerate(ticks)}
    checked, err, total = 0, 0.0, 0
    for n in CHANNELS:
        for k in chans[n]["keys"]:
            total += 1
            i = idx.get(int(k[0]))
            if i is None:
                continue
            checked += 1
            err = max(err, abs(float(samples[n][i]) - float(k[1])))
    probs = []
    if total and checked < 0.9 * total:
        probs.append("KEYS_OFF_SAMPLE_GRID|%d of %d keys on the grid" % (checked, total))
    if err > tol:
        probs.append("SAMPLE_ALIGNMENT|max |eval - key| = %.6f at key ticks (samples shifted or wrong range)" % err)
    return {"checked": checked, "keys": total, "max_err": round(err, 7), "problems": probs}


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


def track_path(prefix, occurrence, cls, name):
    """Stable track identity: class + display name + occurrence among tracks with that same identity."""
    return "%s/T%d:%s:%s" % (prefix, occurrence, cls, name)


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
            "coverage": plan.get("coverage"), "overlay_playback": plan.get("overlay_playback"),
            "copy": plan.get("copy"), "variant": plan.get("variant"), "copy_rates": plan.get("copy_rates"),
            "types": {t: {k: r.get(k) for k in ("mesh", "pivot_offset_cm", "rot_offset_deg", "pivot_frame",
                                                 "variants")} for t, r in sorted((plan.get("types") or {}).items())},
            "wings": [{k: w.get(k) for k in ("label", "type", "her_actor_path", "source_hashes", "keys_sha",
                                              "pre_pose")}
                      for w in plan.get("wings") or []]}
    return hashlib.sha256(json.dumps(core, sort_keys=True, default=str).encode("utf-8")).hexdigest()
