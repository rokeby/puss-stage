"""S1 RE-DOCK: move the Scene 1 hangar set rigidly to the NEW P01 end after p01_shorten APPLY (7 Oct, offline-written,
NEVER RUN IN UNREAL). Plan: S1_REDOCK_PLAN.md. Harness: test_s1_redock_offline.py (system Python).

Tiers per claim: [decl] read in source/header/script (file:line), [prec] in-repo precedent call (cited), [meas] an
earlier run's read-back record (cited), [inf] inferred (why stated).

WHY A RIGID TRANSLATION (not hangar_revert + hangar_build)
  * P01's auto-fit straight route shrinks by the dropped gaps; its END VIEW moves back along the route heading
    (p01_shorten.py:27-37 [decl]; 6 bays = 3600 cm [inf, 600 cm spacing]). Heading and height are unchanged on a straight
    route, so the dock frame moves by a pure translation [inf; ASSERTED live: yaw and z gates below].
  * Every hangar piece except four is attached under "S1 Hangar Root" (hangar_build.py:424-427 attach_to_actor; the
    apron and the pinned-exposure PPV are world-fixed, :433-458 [decl]; "S1 Arrival" is spawned at the root's location,
    CodexStructure/arrivals_apply.py:212 [decl]). Moving the top-level actors carries the rest; the root's rotation
    (landed pitch 0 since 2 Oct, or rest -90) is never touched, so the sunk-REST-pose trap cannot bite a translation
    [meas s1_landed_preview_record.json: rest and landed root LOCATION are the same (29284.0135, 0, 0)].
  * Rebuilding (option b in P01_SHORTEN_PLAN.md step 9) re-runs 117 spawns, the Arrival, the nest, the hangar retime
    and the exit doors; a translation keeps every applied tune bit-for-bit relative to the root.

WHAT MOVES (each listed by the DRY with its before/after; evidence per row)
  MOVE   top-level actors of the move set = tag RigAtmos.Scene1Hangar (hangar_build.py:365, 379) + args extra_move_labels
         (S1 Pit Liner x5, CodexStructure/plane_pitliner_record.json; Opening Floor Pit Strip L/R/Far,
         plane_pithole_record.json - both laid in world space against the hinge x 29284.01 [meas]) + every actor
         attached under any of them (closure). Top-level = no attach parent inside the set.
  CARRY  descendants: the 113-odd hangar pieces, the exit-door shells (attached to the root, hangar_exit_doors.py:606
         [decl]), I1's "S1 Sleight Hangar Camera" and "S1 Sleight Twin Lantern" (attached, curtain_sleight.py:1843,
         2024 [decl]; camera keys root-relative [meas curtain_sleight_record_I1.json hangar_camera.attached_to]).
  TRIM   "Passage 01 - Opening Floor": far edge = the hinge (plane_trim_record.json far 29284.01 [meas]); the new far
         edge follows the hinge, near edge kept (-150). Otherwise the floor covers the new pit and the rising box
         sweeps through it [inf from the -90 -> 0 swing about the hinge, hangar_build.py:209-217].
  REKEY  LS_S1_HangarRise root binding: Location X/Y/Z channel DEFAULTS (and keys, if any) += delta. The Arrival sets the
         root's relative transform from the FIRST key, else the channel DEFAULT, at BeginPlay (InfinityStageArrival.cpp
         :80-121 ResolveFirstTransform, :971-1021 ApplyInitialTransformPose [decl]); unshifted, a game world would snap
         the hangar back to the old end. S1 measured: X/Y/Z defaults only, no keys [meas s1_landed_preview_record.json].
         I1 spawnables "Sleight Hangar Drape" and "Sleight Hangar Shadow Card": WORLD keys on track "CurtainSleight
         (Conductor)" (x 34883.96 / 34841.16 [meas curtain_sleight_record_I1.json]) and the template root relative
         location (= key 0, curtain_sleight.py:2062-2064, 1906-1907 [decl]) += delta.
  MATCH  MatchNamedSceneHandoffs(Scene 1) [prec match_scene1_handoff.py:96]: the Entry/Exit Handoff Cameras are
         regenerated from P01's compiled end, not moved by hand.
  REBUILD RebuildManagedMaster with a NO-CHANGE gate (Show timing is untouched, so segments/managed/keys must read back
         identical) [prec passage_retime_to_music.py:1271-1273].
NOT MOVED (listed, review): every other actor in the region window (old dock frame), classified PASSAGE_OWNED (P01
  Passage/Structure/rig/managed attachments: p01_shorten materialises them), REGENERATED (Scene 1 handoff cameras),
  ACKED (args leave_in_place), or UNKNOWN (APPLY refuses until moved via extra_move_labels or acked).
A sequence scan (Show cue sequences + one nesting level + Master + rise + I1, never GetBoundObjects) refuses any
  3D-transform binding on a moved top-level actor other than the rise root, and any spawnable whose transform keys sit
  in the old hangar box, unless handled/acked.

Modes (s1_redock_run.py <- s1_redock_args.json, confirm "<MODE> S1REDOCK"):
  DRY    read-only; s1_redock_dry.json; S1_REDOCK_DRY_OK|run=..|apply_ready=..|predicted=..  Before p01_shorten APPLY it
         PREDICTS the delta from args predicted_removed_cm (apply_ready=0).
  APPLY  gates -> refusals -> Backups/PreS1Redock-<run> (level, rise, I1, Scene 1 seq, Master, Show) -> exclusive fsynced
         record (every before value) -> actors -> slab -> rise channels -> I1 keys + templates (each read back) ->
         Match Scene 1 -> entry camera == new dock -> rebuild (no-change) -> census subset -> save those -> read back ->
         S1_REDOCK_APPLY_OK|run=..
  REVERT drift check vs record.after -> backup -> before values -> census -> save -> read back -> S1_REDOCK_REVERT_OK.
         Does NOT re-match: run it BEFORE p01_shorten REVERT, then match_scene1_handoff.py after that revert.
  Failure: S1_REDOCK_STOPPED|run=..|reason=.. (nothing saved: Don't-Save restart; backup named).
Never: Save All, reload, open/scrub Sequencer, GetBoundObjects, end PIE; no unreal objects in module globals.
Importing without `unreal` runs nothing.
"""
import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "s1_redock"
MARK = "S1_REDOCK"
CONFIRM_SUFFIX = "S1REDOCK"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ARGS_NAME = "s1_redock_args.json"
DRY_NAME = "s1_redock_dry.json"
RECORD_NAME = "s1_redock_record.json"
RETIME_FILE = "passage_retime_to_music.py"
PASSAGE_ACTOR_PREFIX = "Passage 01"
CHANNELS = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
            "Scale.X", "Scale.Y", "Scale.Z")       # InfinityStageArrival.cpp:88-108 order [decl]
CUBE_HALF_CM = 50.0                                 # /Engine/BasicShapes/Cube is +-50 cm (hangar_exit_doors.py:41)
READBACK_CM = 0.05
SLAB_EDGE_TOL_CM = 1.0
HANDOFF_TAG = "InfinityStage.SceneHandoff"
PASSAGE_CLASSES = ("InfinityStagePassageActor", "InfinityStageStructureActor", "InfinityStageCameraRig")
# Foreign records that hold the OLD S1 frame. This tool never edits them; the record and the report list them.
STALE_REFERENCES = [
    ("CodexConductor/hangar_exit_doors_record.json", "plan.scenes[S1].landed_root_transform (29284.0135) - read as the "
     "landed root by curtain_sleight.py:1533-1545 and passage_end_drape.py:44; its REVERT restores the S1 far wall at "
     "its OLD world pose (hangar_exit_doors.py:1024-1031): never revert the doors while this re-dock is applied"),
    ("CodexConductor/KlaraIngest/klara_hookin_args.json", "hangars.1.dock (28784.0135) - its DRY checks the live S1 "
     "Hangar Apron and will refuse until this is set to the record's new_dock"),
    ("CodexConductor/floor_dark_wet_apply.py:74-75", "SLABS P01 x (-150, 29284.01) hard-coded; its REVERT restores the "
     "P01 slab's 5 Oct scale (over the NEW pit): never revert it while this re-dock is applied"),
    ("CodexStructure/hangar_s1_record.json", "dock (28784.0135): history; hangar_revert.py is by tag, unaffected"),
    ("CodexStructure/scene_docks.json, plane_*_record.json", "history"),
]
STATE_FILES = {   # applied records that would conflict (composed against the S1 root/frame or reading it)
    "klara_stream": "KlaraIngest/klara_hookin_stream_record.json",
    "klara_seq": "KlaraIngest/klara_hookin_seq_record.json",
    "end_drape_s1": "passage_end_drape_record_S1.json",
    "exit_block_s1": "scene_exit_block_record_S1.json",
    "exit_move_s1": "scene_exit_move_record_S1.json",
    "heave_s1": "hangar_heave_record_S1.json",
}


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure frame maths (planar frames: loc [x,y,z] + yaw about Z; the hangar frames have pitch/roll 0 by construction,
# hangar_build.py:192-193 [decl]). Exercised with +/- controls by test_s1_redock_offline.py.
# =====================================================================================================================

def wrap(deg):
    return (float(deg) + 180.0) % 360.0 - 180.0


def xf(loc, yaw):
    return {"loc": [float(loc[0]), float(loc[1]), float(loc[2])], "yaw": float(yaw)}


def from_local(frame, local):
    c, s = math.cos(math.radians(frame["yaw"])), math.sin(math.radians(frame["yaw"]))
    return [frame["loc"][0] + c * local[0] - s * local[1], frame["loc"][1] + s * local[0] + c * local[1],
            frame["loc"][2] + local[2]]


def to_local(frame, p):
    c, s = math.cos(math.radians(frame["yaw"])), math.sin(math.radians(frame["yaw"]))
    dx, dy = p[0] - frame["loc"][0], p[1] - frame["loc"][1]
    return [c * dx + s * dy, -s * dx + c * dy, p[2] - frame["loc"][2]]


def add(p, d):
    return [float(p[0]) + d[0], float(p[1]) + d[1], float(p[2]) + d[2]]


def dist(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def dock_from_root(root_loc, root_yaw, apron, hinge_z):
    """hangar_build.py:193, 368-370 [decl]: dock = camera xy at floor level (z 0), root = dock * (apron, 0, hinge_z).
    Inverse: dock floor point = root - R(yaw)(apron, 0, hinge_z)."""
    c, s = math.cos(math.radians(root_yaw)), math.sin(math.radians(root_yaw))
    return xf([root_loc[0] - c * apron, root_loc[1] - s * apron, root_loc[2] - hinge_z], root_yaw)


def root_from_dock(dock, apron, hinge_z):
    return from_local(dock, [apron, 0.0, hinge_z])


def solve_delta(end_view, root, entry_cam, hangar, tol):
    """end_view {loc, yaw}: P01 compiled end-frame camera (the new dock seat). root {loc, rot[roll,pitch,yaw]}: the LIVE
    S1 Hangar Root. entry_cam {loc, yaw}: the live Scene 1 Entry Handoff Camera (the OLD seat until MATCH).
    Returns (solution, refusals). Translation-only: any heading change or height change refuses."""
    r = []
    ryaw = float(root["rot"][2])
    if abs(float(root["rot"][0])) > tol["deg"]:
        r.append("ROOT_ROLL_NONZERO: %.4f" % root["rot"][0])
    old_dock = dock_from_root(root["loc"], ryaw, hangar["apron_cm"], hangar["hinge_z_cm"])
    if abs(wrap(end_view["yaw"] - ryaw)) > tol["deg"]:
        r.append("YAW_CHANGE: end view %.4f vs root %.4f (translation-only tool)" % (end_view["yaw"], ryaw))
    if entry_cam is not None and abs(float(end_view["loc"][2]) - float(entry_cam["loc"][2])) > tol["z_cm"]:
        r.append("END_VIEW_HEIGHT_CHANGED: %.2f vs entry camera %.2f" % (end_view["loc"][2], entry_cam["loc"][2]))
    new_dock = xf([end_view["loc"][0], end_view["loc"][1], old_dock["loc"][2]], ryaw)
    delta = [new_dock["loc"][0] - old_dock["loc"][0], new_dock["loc"][1] - old_dock["loc"][1], 0.0]
    sol = {"old_dock": old_dock, "new_dock": new_dock, "delta": [round(v, 6) for v in delta],
           "delta_len_cm": round(math.hypot(delta[0], delta[1]), 6),
           "old_root": [float(v) for v in root["loc"]], "new_root": add(root["loc"], delta),
           "old_seat": [old_dock["loc"][0], old_dock["loc"][1], float(end_view["loc"][2])],
           "new_seat": [float(v) for v in end_view["loc"]]}
    if entry_cam is not None:
        sol["entry_cam_vs_old_dock_xy_cm"] = round(math.hypot(entry_cam["loc"][0] - old_dock["loc"][0],
                                                              entry_cam["loc"][1] - old_dock["loc"][1]), 4)
    return sol, r


def predicted_delta(removed_cm, yaw):
    """The shorten moves the end back along the route heading by removed_cm (p01_shorten.py:32-34 [decl])."""
    return [-float(removed_cm) * math.cos(math.radians(yaw)), -float(removed_cm) * math.sin(math.radians(yaw)), 0.0]


def delta_gates(delta, removed_cm, yaw, tol_cm):
    r = []
    if math.hypot(delta[0], delta[1]) < 1.0:
        r.append("NOTHING_TO_MOVE: |delta| < 1 cm (P01 not shortened yet, or already re-docked)")
        return r
    if removed_cm is None:
        r.append("SHORTEN_RECORD_MISSING: no applied p01_shorten_record.json removed_cm to check the delta against")
        return r
    want = predicted_delta(removed_cm, yaw)
    err = math.hypot(delta[0] - want[0], delta[1] - want[1])
    if err > tol_cm:
        r.append("DELTA_NOT_AS_SHORTEN: live %r vs -%.4f cm along yaw %.3f (err %.2f > %.1f)" % (
            [round(v, 3) for v in delta], removed_cm, yaw, err, tol_cm))
    return r


def in_box(dock, p, box):
    """box in the dock frame: x [x0, x1], |y| <= half_y, z [z0, z1] (any of them None = unbounded)."""
    lx, ly, lz = to_local(dock, p)
    if lx < box["x0"] or lx > box["x1"] or abs(ly) > box["half_y"]:
        return False
    if box.get("z0") is not None and lz < box["z0"]:
        return False
    if box.get("z1") is not None and lz > box["z1"]:
        return False
    return True


def region_box(region, removed_cm):
    """p01_shorten._region_inventory window in the OLD dock frame: from before_cm ahead of the NEW end to past_cm
    beyond the old end, +-half_width_cm (p01_shorten.py:476-496 [decl])."""
    return {"x0": -float(removed_cm) - float(region["before_cm"]), "x1": float(region["past_cm"]),
            "half_y": float(region["half_width_cm"]), "z0": None, "z1": None}


def hangar_box(hangar, margin):
    """The landed interior in the ROOT frame (hinge at the near edge): x [0, depth], |y| half_w, z floor..height
    (hangar_build.py:5-14, CodexConductor/KlaraIngest/HOOKIN_PLAN.md:75 [decl])."""
    return {"x0": -margin, "x1": hangar["depth_cm"] + hangar["wall_t_cm"] + margin,
            "half_y": hangar["half_w_cm"] + hangar["wall_t_cm"] + margin,
            "z0": -hangar["floor_t_cm"] - margin, "z1": hangar["height_cm"] + margin}


def inside_hangar(root_frame, p, hangar, margin=1.0):
    """memory puss-level-saved-landed-frame-trap: the guard is against the LIVE LANDED root (yaw-only frame)."""
    return in_box(root_frame, p, hangar_box(hangar, margin))


def rest_pose_point(root_frame, local):
    """Where a root-local point sits when the root hangs at REST (pitch -90 about the hinge's Y axis): local (x, y, z)
    -> (z, y, -x) [inf from hangar_build.py:209-217 phi = -90]. Only used as the harness's NEGATIVE control."""
    return from_local(root_frame, [local[2], local[1], -local[0]])


# ---- the move set -----------------------------------------------------------------------------------------------

def move_closure(rows, seed_tag, extra_labels):
    """rows: [{path, label, parent (path or None), tags, class}]. Seeds = tag OR label in extra_labels; then every
    descendant. Returns (top, carried, refusals). A seed attached to a parent OUTSIDE the set refuses (it would be
    moved twice or not at all)."""
    r = []
    by_path = {x["path"]: x for x in rows}
    kids = {}
    for x in rows:
        if x.get("parent"):
            kids.setdefault(x["parent"], []).append(x["path"])
    labels = {}
    for x in rows:
        labels.setdefault(x["label"], []).append(x["path"])
    seeds = [x["path"] for x in rows if seed_tag in (x.get("tags") or [])]
    for lab in extra_labels or []:
        hits = labels.get(lab, [])
        if len(hits) != 1:
            r.append("EXTRA_LABEL_COUNT: %r x%d" % (lab, len(hits)))
        seeds += hits
    in_set, stack = set(), list(seeds)
    while stack:
        p = stack.pop()
        if p in in_set:
            continue
        in_set.add(p)
        stack += kids.get(p, [])
    top = sorted((p for p in in_set if not by_path[p].get("parent") or by_path[p]["parent"] not in in_set),
                 key=lambda p: by_path[p]["label"])
    for p in top:
        if by_path[p].get("parent"):
            r.append("SEED_ATTACHED_OUTSIDE_SET: %s -> %s" % (by_path[p]["label"], by_path[p]["parent"]))
    carried = sorted((p for p in in_set if p not in top), key=lambda p: by_path[p]["label"])
    return top, carried, r


def classify_region(rows, in_set, trim_label, passage_owned, scene_prefix, leave_in_place, dock, box):
    """Every actor in the region window: MOVE/CARRY (in the set), TRIM, PASSAGE_OWNED, REGENERATED, ACKED, UNKNOWN."""
    out = {"PASSAGE_OWNED": [], "REGENERATED": [], "ACKED": [], "UNKNOWN": [], "TRIM": [], "IN_SET": 0}
    for x in rows:
        if x["label"] == trim_label and x["path"] not in in_set:     # listed wherever its centre is
            out["TRIM"].append({"label": x["label"], "class": x["class"], "loc": [round(v, 1) for v in x["loc"]],
                                "parent": x.get("parent_label")})
            continue
        if not in_box(dock, x["loc"], box):
            continue
        if x["path"] in in_set:
            out["IN_SET"] += 1
            continue
        row = {"label": x["label"], "class": x["class"], "loc": [round(v, 1) for v in x["loc"]],
               "parent": x.get("parent_label")}
        if x["class"] in PASSAGE_CLASSES or x["path"] in passage_owned:
            out["PASSAGE_OWNED"].append(row)
        elif HANDOFF_TAG in (x.get("tags") or []) and x["label"].startswith(scene_prefix):
            out["REGENERATED"].append(row)
        elif x["label"] in set(leave_in_place or []):
            out["ACKED"].append(row)
        else:
            out["UNKNOWN"].append(row)
    for k in ("PASSAGE_OWNED", "REGENERATED", "ACKED", "UNKNOWN", "TRIM"):
        out[k].sort(key=lambda r: r["label"])
    return out


# ---- the floor slab ---------------------------------------------------------------------------------------------

def trim_slab(slab, old_hinge, delta, yaw, tol=SLAB_EDGE_TOL_CM):
    """slab {loc, rot, scale} of an unrotated Cube StaticMeshActor (plane_trim_record.json: unrotated, untagged,
    unattached, mesh_ok [meas]). Keep the near edge; move the far edge from the OLD hinge by delta.x."""
    r = []
    if any(abs(wrap(v)) > 1e-3 for v in slab["rot"]):
        r.append("SLAB_ROTATED: %r" % slab["rot"])
    if abs(wrap(yaw)) > 1e-3 or abs(delta[1]) > 1e-3:
        r.append("SLAB_TRIM_NEEDS_AXIS_ALIGNED_DELTA: yaw %.4f dy %.4f" % (yaw, delta[1]))
    if r:
        return None, r
    half = CUBE_HALF_CM * float(slab["scale"][0])
    near, far = float(slab["loc"][0]) - half, float(slab["loc"][0]) + half
    if abs(far - float(old_hinge[0])) > tol:
        r.append("SLAB_FAR_EDGE_NOT_AT_HINGE: far %.3f vs hinge %.3f" % (far, old_hinge[0]))
        return None, r
    new_far = far + float(delta[0])
    if new_far <= near + 100.0:
        r.append("SLAB_WOULD_VANISH: near %.1f new far %.1f" % (near, new_far))
        return None, r
    after = json.loads(json.dumps(slab))
    after["scale"][0] = (new_far - near) / (2.0 * CUBE_HALF_CM)
    after["loc"][0] = (near + new_far) / 2.0
    return {"before": slab, "after": after, "near_x": near, "far_x_before": far, "far_x_after": new_far}, r


# ---- sequence channels ------------------------------------------------------------------------------------------

def channel_base(name):
    """'Location.Y_183' -> 'Location.Y' (memory ue58-sequencer-read-traps)."""
    return re.sub(r"_\d+$", "", str(name))


def shift_channels(ch, delta):
    """ch {"Location.X": {"default": v|None, "keys": [[t, v], ...]}, ...}: Location X/Y/Z defaults AND key values +=
    delta; times, tangents, every other channel untouched (a constant offset leaves cubic tangents unchanged [inf,
    standard Bezier algebra; same argument as KlaraIngest/HOOKIN_PLAN.md section 2])."""
    out = json.loads(json.dumps(ch))
    for i, name in enumerate(("Location.X", "Location.Y", "Location.Z")):
        if name not in out:
            raise PlanError("CHANNEL_MISSING: %s" % name)
        c = out[name]
        if c.get("default") is not None:
            c["default"] = float(c["default"]) + delta[i]
        c["keys"] = [[k[0], float(k[1]) + delta[i]] for k in c.get("keys") or []]
    return out


def channels_equal(a, b, tol=1.0e-4):
    if sorted(a) != sorted(b):
        return False
    for n in a:
        da, db = a[n].get("default"), b[n].get("default")
        if (da is None) != (db is None) or (da is not None and abs(da - db) > tol):
            return False
        ka, kb = a[n].get("keys") or [], b[n].get("keys") or []
        if len(ka) != len(kb) or any(p[0] != q[0] or abs(p[1] - q[1]) > tol for p, q in zip(ka, kb)):
            return False
    return True


def channel_points(ch):
    """World points a transform binding visits: its Location keys (X/Y/Z zipped by index) plus the defaults."""
    xs, ys, zs = (ch.get(n) or {} for n in ("Location.X", "Location.Y", "Location.Z"))
    pts = []
    d = [xs.get("default"), ys.get("default"), zs.get("default")]
    if all(v is not None for v in d):
        pts.append([float(v) for v in d])
    kx, ky, kz = xs.get("keys") or [], ys.get("keys") or [], zs.get("keys") or []
    for i in range(max(len(kx), len(ky), len(kz))):
        def at(k, j, dflt):
            return float(k[j][1]) if j < len(k) else (dflt if dflt is not None else 0.0)
        pts.append([at(kx, i, d[0]), at(ky, i, d[1]), at(kz, i, d[2])])
    return pts


def first_point(ch):
    pts = channel_points(ch)
    if not pts:
        return None
    xs = ch.get("Location.X") or {}
    return pts[1] if (xs.get("keys") and len(pts) > 1 and xs.get("default") is not None) else pts[0]


def classify_bindings(rows, top_paths, carried_paths, rise_key, handled, acked, dock, box):
    """rows: [{sequence, binding, guid, kind 'possessable'|'spawnable', bound (paths), has_transform, sections,
    channels, template_loc}]. Returns {REKEY_ROOT, REKEY_SPAWNABLE, RELATIVE_OK, INFO, ACKED, REFUSE} lists."""
    out = {"REKEY_ROOT": [], "REKEY_SPAWNABLE": [], "RELATIVE_OK": [], "INFO": [], "ACKED": [], "REFUSE": []}
    handled_keys = {(h["sequence"], h["binding"]) for h in handled or []}
    acked_keys = {(a["sequence"], a["binding"]) for a in acked or []}
    for b in rows:
        key = (b["sequence"], b["binding"])
        brief = {"sequence": b["sequence"], "binding": b["binding"], "guid": b["guid"], "kind": b["kind"]}
        bound = set(b.get("bound") or [])
        if (b["sequence"], b["guid"]) == rise_key:
            # identified by the Arrival's MotionBindingGuid (arrivals_record.json binding [meas]); identity is then
            # checked by value: its Location default must equal the LIVE root (build_plan RISE_ROOT_DEFAULT_NOT_LIVE_ROOT)
            out["REKEY_ROOT"].append(dict(brief, bound_resolved=bool(bound & set(top_paths))))
            continue
        if b["kind"] == "possessable":
            if bound & set(top_paths):
                if not b.get("has_transform"):
                    out["INFO"].append(dict(brief, why="moved actor, no transform track"))
                elif key in acked_keys:
                    out["ACKED"].append(brief)
                else:
                    out["REFUSE"].append(dict(brief, why="FOREIGN_WORLD_TRANSFORM on a moved top-level actor"))
            elif bound & set(carried_paths):
                out["RELATIVE_OK"].append(dict(brief, why="attached: keys are parent-relative"))
            continue
        # spawnables: judged by where their transform keys (or template) sit
        pts = channel_points(b["channels"]) if b.get("channels") else []
        if b.get("template_loc") is not None:
            pts = pts + [b["template_loc"]]
        hit = any(in_box(dock, p, box) for p in pts)
        if key in handled_keys:
            if not b.get("has_transform"):
                out["REFUSE"].append(dict(brief, why="HANDLED_SPAWNABLE_HAS_NO_TRANSFORM_TRACK"))
            elif not hit:
                out["REFUSE"].append(dict(brief, why="HANDLED_SPAWNABLE_NOT_IN_OLD_HANGAR (already moved?)"))
            else:
                out["REKEY_SPAWNABLE"].append(brief)
        elif hit:
            (out["ACKED"] if key in acked_keys else out["REFUSE"]).append(
                dict(brief, why="SPAWNABLE_IN_OLD_HANGAR_UNHANDLED"))
    return out


def spawnable_plan(name, ch, template, delta, tol=1.0):
    """Shift keys + template; the template must sit on key 0 (how curtain_sleight composed it, :1906-1907, 2062-2064)."""
    r = []
    f = first_point(ch)
    if template is None or f is None or dist(template["loc"], f) > tol:
        r.append("TEMPLATE_NOT_AT_FIRST_KEY: %s template %r first key %r" % (
            name, template and template["loc"], f))
    after_t = None if template is None else dict(template, loc=add(template["loc"], delta))
    return {"channels_before": ch, "channels_after": shift_channels(ch, delta), "template_before": template,
            "template_after": after_t}, r


# ---- gates, record models -----------------------------------------------------------------------------------------

def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    if int(args.get("scene") or 0) != 1:
        r.append("SCENE_INVALID: S1 only")
    h = args.get("hangar") or {}
    for f in ("apron_cm", "hinge_z_cm", "depth_cm", "half_w_cm", "height_cm", "wall_t_cm", "floor_t_cm"):
        if not isinstance(h.get(f), (int, float)) or isinstance(h.get(f), bool):
            r.append("HANGAR_%s_INVALID" % f.upper())
    for f in ("root_label", "tag"):
        if not str(h.get(f) or ""):
            r.append("HANGAR_%s_MISSING" % f.upper())
    if not re.match(r"^[0-9A-F]{32}$", str(args.get("rise_root_binding_guid") or "")):
        r.append("RISE_ROOT_BINDING_GUID_INVALID")
    for f in ("predicted_removed_cm", "delta_tol_cm"):
        if not isinstance(args.get(f), (int, float)) or args.get(f) <= 0:
            r.append("%s_INVALID" % f.upper())
    if mode == "APPLY":
        if not str(args.get("approved_by") or "").strip():
            r.append("NOT_APPROVED: approved_by is empty")
        exp = args.get("expected") or {}
        if not isinstance(exp.get("delta"), list) or len(exp.get("delta")) != 3:
            r.append("EXPECTED_DELTA_MISSING (copy expected_for_apply_args from the DRY)")
        for f in ("top", "carried", "rekey_spawnables"):
            if not isinstance(exp.get(f), list):
                r.append("EXPECTED_%s_MISSING (copy it from the DRY)" % f.upper())
    return r


def expected_refusals(plan, expected, mode):
    if mode != "APPLY":
        return []
    r = []
    if dist(expected.get("delta") or [9e9] * 3, plan["solution"]["delta"]) > 0.5:
        r.append("DELTA_CHANGED_SINCE_DRY: live %r args %r" % (plan["solution"]["delta"], expected.get("delta")))
    for f in ("top", "carried", "rekey_spawnables"):
        if sorted(expected.get(f) or []) != sorted(plan["expected_for_apply_args"][f]):
            r.append("%s_CHANGED_SINCE_DRY" % f.upper())
    return r


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    if state.get("confirm") != "%s %s" % (mode, CONFIRM_SUFFIX):
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s %s" % (mode, CONFIRM_SUFFIX)))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN")
    if state.get("zz_actors"):
        r.append("ZZ_ACTORS_PRESENT: %s (bench temps; memory puss-benches-are-level-activity)" % state["zz_actors"][:5])
    c = state.get("census") or {}
    if c.get("content") or c.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(c, sort_keys=True))
    if mode == "APPLY":
        if state.get("record_exists"):
            r.append("RECORD_EXISTS: %s (REVERT first)" % RECORD_NAME)
        if not state.get("shorten_applied"):
            r.append("P01_SHORTEN_NOT_APPLIED (prerequisite p01_shorten_record.json applied)")
    if mode in ("APPLY", "REVERT"):
        busy = sorted(k for k, v in (state.get("conflicts") or {}).items() if v)
        if busy:
            r.append("CONFLICTING_RECORDS_APPLIED: %s (LIFO: revert them first)" % busy)
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD: %s" % RECORD_NAME)
    return r


def build_plan(facts, args):
    """Everything APPLY writes, as data. facts: end_view, root, entry_cam, rows, passage_owned, bindings,
    removed_cm (applied shorten) or None, slab (pose) or None."""
    h = args["hangar"]
    tol = {"deg": float(args.get("yaw_tol_deg", 0.01)), "z_cm": float(args.get("z_tol_cm", 1.0))}
    refusals, warnings = [], []
    predicted = False
    ev = facts.get("end_view")
    if ev is None:
        raise PlanError("END_VIEW_UNREADABLE")
    sol, r = solve_delta(ev, facts["root"], facts.get("entry_cam"), h, tol)
    refusals += r
    yaw = float(facts["root"]["rot"][2])
    if facts.get("removed_cm") is None and sol["delta_len_cm"] < 1.0:
        predicted = True                       # DRY before the shorten: preview with the predicted delta
        d = predicted_delta(args["predicted_removed_cm"], yaw)
        sol["delta"] = [round(v, 6) for v in d]
        sol["delta_len_cm"] = round(math.hypot(d[0], d[1]), 6)
        sol["new_dock"] = xf(add(sol["old_dock"]["loc"], d), yaw)
        sol["new_root"] = add(sol["old_root"], d)
        sol["new_seat"] = add(sol["old_seat"], d)
        refusals.append("PREDICTED_ONLY: P01 not shortened yet; delta = -predicted_removed_cm (not appliable)")
    else:
        refusals += delta_gates(sol["delta"], facts.get("removed_cm"), yaw, float(args["delta_tol_cm"]))
    if facts.get("entry_cam") is not None and sol.get("entry_cam_vs_old_dock_xy_cm", 0.0) > 1.0:
        warnings.append("ENTRY_CAMERA_NOT_ON_OLD_DOCK: %.2f cm (already matched? the hangar is judged from its "
                        "live root, not the camera)" % sol["entry_cam_vs_old_dock_xy_cm"])
    delta = sol["delta"]
    rows = facts["rows"]
    by_path = {x["path"]: x for x in rows}
    top, carried, r = move_closure(rows, h["tag"], args.get("extra_move_labels"))
    refusals += r
    roots = [p for p in top if by_path[p]["label"] == h["root_label"]]
    if len(roots) != 1:
        refusals.append("ROOT_NOT_TOP_LEVEL_ONCE: %d" % len(roots))
    in_set = set(top) | set(carried)
    moves = [{"label": by_path[p]["label"], "path": p, "class": by_path[p]["class"],
              "before": by_path[p]["loc"], "after": add(by_path[p]["loc"], delta)} for p in top]
    carry = [{"label": by_path[p]["label"], "path": p, "parent": by_path[p].get("parent_label"),
              "before": by_path[p]["loc"], "after": add(by_path[p]["loc"], delta)} for p in carried]
    # the landed-frame guard on every hangar-tagged piece, BEFORE and AFTER (a piece outside the box is a composition
    # error somewhere upstream; S1 lattice flies above the box at rest, so the box z1 allows lattice_fly)
    hb = dict(h, height_cm=h["height_cm"] + float(args.get("lattice_fly_cm", 1600.0)))
    old_root_f, new_root_f = xf(sol["old_root"], yaw), xf(sol["new_root"], yaw)
    outside = [m["label"] for m in carry if h["tag"] in (by_path[m["path"]].get("tags") or [])
               and not (inside_hangar(old_root_f, m["before"], hb, 5.0) and inside_hangar(new_root_f, m["after"], hb,
                                                                                            5.0))]
    if outside:
        refusals.append("HANGAR_PIECE_OUTSIDE_LANDED_BOX: %s (root not LANDED? memory "
                        "puss-level-saved-landed-frame-trap)" % outside[:8])
    if facts.get("root_pitch") is not None and abs(float(facts["root_pitch"])) > 0.05:
        refusals.append("ROOT_NOT_LANDED: pitch %.3f (the level is saved LANDED since 2 Oct; refuse rather than move a "
                        "hanging tree)" % facts["root_pitch"])
    # slab
    trim = None
    if args.get("trim_slab_label"):
        if facts.get("slab") is None:
            refusals.append("SLAB_MISSING: %s" % args["trim_slab_label"])
        else:
            trim, r = trim_slab(facts["slab"], sol["old_root"], delta, yaw)
            refusals += r
    # region
    box = region_box(args["region"], sol["delta_len_cm"])
    region = classify_region(rows, in_set, args.get("trim_slab_label"), set(facts.get("passage_owned") or []),
                             args.get("scene_label_prefix", "Scene 1 "), args.get("leave_in_place"),
                             sol["old_dock"], box)
    if region["UNKNOWN"]:
        refusals.append("REGION_UNKNOWN_NOT_MOVED: %d actor(s) near the S1 end are neither moved nor acked: %s" % (
            len(region["UNKNOWN"]), [x["label"] for x in region["UNKNOWN"]][:12]))
    # sequences
    rise_key = (args["rise_sequence"], args["rise_root_binding_guid"])
    hangar_old = {"x0": h["apron_cm"] - 100.0, "x1": h["apron_cm"] + h["depth_cm"] + 1500.0,
                  "half_y": h["half_w_cm"] + 1500.0, "z0": -7000.0, "z1": h["height_cm"] + 3000.0}
    cls = classify_bindings(facts.get("bindings") or [], top, carried, rise_key, args.get("handled_spawnables"),
                            args.get("acked_bindings"), sol["old_dock"], hangar_old)
    for b in cls["REFUSE"]:
        refusals.append("BINDING: %s | %s | %s" % (b["sequence"], b["binding"], b["why"]))
    if len(cls["REKEY_ROOT"]) != 1:
        refusals.append("RISE_ROOT_BINDING: found %d (want exactly the Arrival's MotionBindingGuid)" %
                        len(cls["REKEY_ROOT"]))
    rows_by = {(b["sequence"], b["guid"]): b for b in facts.get("bindings") or []}
    rekeys = []
    for b in cls["REKEY_ROOT"]:
        src = rows_by[(b["sequence"], b["guid"])]
        if src.get("sections") != 1:
            refusals.append("RISE_ROOT_SECTIONS: %r (want 1)" % src.get("sections"))
            continue
        rekeys.append({"sequence": b["sequence"], "binding": b["binding"], "guid": b["guid"], "kind": "ROOT",
                       "before": src["channels"], "after": shift_channels(src["channels"], delta)})
        pts = channel_points(src["channels"])
        if not pts or dist(pts[0], sol["old_root"]) > 1.0:
            refusals.append("RISE_ROOT_DEFAULT_NOT_LIVE_ROOT: %r vs %r" % (pts[:1], sol["old_root"]))
    for b in cls["REKEY_SPAWNABLE"]:
        src = rows_by[(b["sequence"], b["guid"])]
        if src.get("sections") != 1:
            refusals.append("SPAWNABLE_SECTIONS: %s %r" % (b["binding"], src.get("sections")))
            continue
        sp, r = spawnable_plan(b["binding"], src["channels"], src.get("template"), delta)
        refusals += r
        new_pts = channel_points(sp["channels_after"])
        bad = [p for p in new_pts if not inside_hangar(new_root_f, p, hb, 50.0)]
        if bad:
            refusals.append("SPAWNABLE_OUTSIDE_NEW_HANGAR: %s %r" % (b["binding"], bad[:2]))
        rekeys.append({"sequence": b["sequence"], "binding": b["binding"], "guid": b["guid"], "kind": "SPAWNABLE",
                       "track": src.get("track"), "before": sp["channels_before"], "after": sp["channels_after"],
                       "template_before": sp["template_before"], "template_after": sp["template_after"]})
    for want in args.get("handled_spawnables") or []:
        if not any(x["sequence"] == want["sequence"] and x["binding"] == want["binding"] for x in rekeys):
            refusals.append("HANDLED_SPAWNABLE_NOT_FOUND: %s | %s" % (want["sequence"], want["binding"]))
    for k, v in (facts.get("conflicts") or {}).items():
        if v:
            refusals.append("CONFLICT_%s_APPLIED" % k.upper())
    plan = {"solution": sol, "predicted": predicted, "moves": moves, "carried": carry, "trim": trim,
            "region": region, "region_box_old_dock_frame": box, "bindings": cls, "rekeys": rekeys,
            "stale_references": [list(x) for x in STALE_REFERENCES],
            "klara_dock_for_args": {"loc": sol["new_dock"]["loc"][:2] + [float(ev["loc"][2])], "yaw": yaw},
            "refusals": refusals, "warnings": warnings}
    plan["expected_for_apply_args"] = {"delta": sol["delta"], "top": sorted(m["label"] for m in moves),
                                       "carried": sorted(m["label"] for m in carry),
                                       "rekey_spawnables": sorted(x["binding"] for x in rekeys
                                                                  if x["kind"] == "SPAWNABLE")}
    return plan


def readback_failures(plan, live, side):
    """live: {"actors": {path: loc}, "slab": pose|None, "channels": {(seq, guid): ch}, "templates": {(seq, guid): pose},
    "rel": {path: root-relative loc}} ; side 'before'|'after'. Rel invariance is checked by the caller."""
    f = []
    for m in plan["moves"] + plan["carried"]:
        got = live["actors"].get(m["path"])
        if got is None or dist(got, m[side]) > READBACK_CM:
            f.append("ACTOR_%s: %s %r != %r" % (side.upper(), m["label"], got, m[side]))
    if plan.get("trim"):
        got = live.get("slab")
        want = plan["trim"][side]
        if got is None or dist(got["loc"], want["loc"]) > READBACK_CM or dist(got["scale"], want["scale"]) > 1e-4:
            f.append("SLAB_%s: %r != %r" % (side.upper(), got, want))
    for x in plan["rekeys"]:
        got = live["channels"].get((x["sequence"], x["guid"]))
        if got is None or not channels_equal(got, x[side]):
            f.append("CHANNELS_%s: %s | %s" % (side.upper(), x["sequence"], x["binding"]))
        if x["kind"] == "SPAWNABLE":
            t = live["templates"].get((x["sequence"], x["guid"]))
            if t is None or dist(t["loc"], x["template_" + side]["loc"]) > READBACK_CM:
                f.append("TEMPLATE_%s: %s" % (side.upper(), x["binding"]))
    return f


def rel_failures(before_rel, after_rel, tol=READBACK_CM):
    return ["ROOT_RELATIVE_CHANGED: %s" % p for p in sorted(before_rel)
            if p not in after_rel or dist(before_rel[p], after_rel[p]) > tol]


def match_gate(entry_after, new_seat, yaw, tol_cm=1.0, tol_deg=0.05):
    if entry_after is None:
        return ["ENTRY_CAMERA_UNREADABLE_AFTER_MATCH"]
    r = []
    d = dist(entry_after["loc"], new_seat)
    if d > tol_cm:
        r.append("ENTRY_CAMERA_NOT_ON_NEW_SEAT: %.2f cm" % d)
    if abs(wrap(entry_after["yaw"] - yaw)) > tol_deg:
        r.append("ENTRY_CAMERA_YAW: %.4f vs %.4f" % (entry_after["yaw"], yaw))
    return r


def no_change_gate(before, after):
    return ["REBUILD_CHANGED_%s" % k.upper() for k in ("segments", "managed", "keys", "artist", "markers")
            if json.dumps(before.get(k), sort_keys=True, default=str) != json.dumps(after.get(k), sort_keys=True,
                                                                                      default=str)]


def census_gate(census, allowed_content, world=EXPECTED_WORLD):
    r = []
    extra = sorted(set(census.get("content") or []) - set(allowed_content))
    if extra:
        r.append("UNEXPECTED_DIRTY: %s" % extra)
    bad_maps = [m for m in census.get("maps") or [] if m != world]
    if bad_maps:
        r.append("MAP_DIRTY: %s" % bad_maps)
    return r


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local; R = the retime module loaded per run (p01_shorten.py:100-108).
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def load_retime(folder=None):
    path = os.path.join(folder or _here(), RETIME_FILE)
    spec = importlib.util.spec_from_file_location("s1_redock_retime_helpers", path)
    mod = importlib.util.module_from_spec(spec)
    mod.RETIME_IMPORT_ONLY = True
    spec.loader.exec_module(mod)
    return mod


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _v3(v):
    return [float(v.x), float(v.y), float(v.z)]


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _rows(actors):
    rows = []
    for a in actors:
        p = a.get_attach_parent_actor()
        r = a.get_actor_rotation()
        rows.append({"path": a.get_path_name(), "label": str(a.get_actor_label()), "class": a.get_class().get_name(),
                     "parent": p.get_path_name() if p else None, "parent_label": str(p.get_actor_label()) if p else None,
                     "tags": [str(t) for t in a.tags], "loc": _v3(a.get_actor_location()),
                     "rot": [float(r.roll), float(r.pitch), float(r.yaw)], "scale": _v3(a.get_actor_scale3d())})
    return rows


def _one(actors, label, run):
    hits = [a for a in actors if str(a.get_actor_label()) == label]
    if len(hits) != 1:
        _stop(run, "ACTOR_COUNT|%s|%d" % (label, len(hits)))
    return hits[0]


def _end_view(R, show, passage_guid_text):
    """p01_shorten.py:457-473 / match_scene1_handoff.py:104-106: compiled end-frame camera pose (no gait bob)."""
    lib = unreal.InfinityStageCameraPilotLibrary
    guid = None
    for p in show.get_editor_property("passage_settings"):
        if R._guid(p.get_editor_property("passage_guid")) == passage_guid_text:
            guid = p.get_editor_property("passage_guid")
    if guid is None:
        return None
    fr = R.unwrap(lib.get_passage_frame_range(show, guid), 2)
    pose = R.unwrap(lib.get_passage_camera_pose(show, guid, int(fr[1])), 3) if fr else None
    if pose is None:
        return None
    return {"loc": _v3(pose[0].translation), "yaw": float(pose[0].rotation.rotator().yaw)}


def _entry_cam(actors, prefix):
    cams = [a for a in actors if isinstance(a, unreal.CineCameraActor) and a.actor_has_tag("InfinityStage.SceneEntry")
            and str(a.get_actor_label()).startswith(prefix)]          # match_scene1_handoff.py:107-111
    if len(cams) != 1:
        return None
    return {"loc": _v3(cams[0].get_actor_location()), "yaw": float(cams[0].get_actor_rotation().yaw),
            "label": str(cams[0].get_actor_label())}


def _sequences(show, args):
    """p02_straighten_followons.py:305-325 + the rise and I1 explicitly (bindings only, never GetBoundObjects)."""
    seen, out = set(), []

    def addseq(s):
        if s is not None and s.get_path_name() not in seen:
            seen.add(s.get_path_name())
            out.append(s)
    for c in show.get_editor_property("cues"):
        try:
            addseq(c.get_editor_property("scene").get_editor_property("sequence"))
        except Exception:  # noqa: BLE001 - cue types without a scene struct
            pass
    for path in (MASTER_PATH, args["rise_sequence"], args["interaction_sequence"], args["scene_sequence"]):
        addseq(unreal.load_asset(path))
    for s in list(out):
        for tt in (unreal.MovieSceneCinematicShotTrack, unreal.MovieSceneSubTrack):
            for t in s.find_tracks_by_type(tt):
                for sec in t.get_sections():
                    addseq(sec.get_sequence())
    return out


def _transform_section(b):
    tracks = [t for t in b.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
    secs = [s for t in tracks for s in t.get_sections()]
    return tracks, secs


def _read_channels(section):
    """Picked by ORDER, names verified (memory ue58-sequencer-read-traps; Arrival.cpp:88-108 order)."""
    chans = list(section.get_all_channels())
    if len(chans) != 9:
        raise PlanError("TRANSFORM_CHANNEL_COUNT: %d" % len(chans))
    out = {}
    for want, c in zip(CHANNELS, chans):
        if channel_base(c.channel_name) != want:
            raise PlanError("TRANSFORM_CHANNEL_ORDER: %s at %s" % (c.channel_name, want))
        out[want] = {"default": float(c.get_default()) if c.has_default() else None,
                     "keys": [[int(k.get_time().frame_number.value), float(k.get_value())] for k in c.get_keys()]}
    return out, chans


def _template_pose(b):
    try:
        tmpl = b.get_object_template()
    except Exception:  # noqa: BLE001 - possessables have no template
        return None
    if tmpl is None:
        return None
    root = tmpl.get_editor_property("root_component")                 # curtain_sleight.py:1518-1520
    if root is None:
        return None
    return {"loc": _v3(root.get_editor_property("relative_location"))}


def _binding_rows(seqs, world, args):
    rows = []
    for s in seqs:
        path = s.get_path_name().split(".")[0]
        for b in s.get_bindings():
            tmpl = _template_pose(b)
            kind = "spawnable" if tmpl is not None else "possessable"
            bound = []
            if kind == "possessable":
                try:
                    bound = [o.get_path_name() for o in s.locate_bound_objects(b, world)]   # opening_sequence_apply:330
                except Exception:  # noqa: BLE001 - reported as unresolved
                    bound = []
            tracks, secs = _transform_section(b)
            row = {"sequence": path, "binding": str(b.get_display_name()), "guid": R_guid(b.get_id()), "kind": kind,
                   "bound": bound, "has_transform": bool(tracks), "sections": len(secs), "channels": None,
                   "template": tmpl, "template_loc": tmpl["loc"] if tmpl else None,
                   "track": str(tracks[0].get_display_name()) if tracks else None}
            if len(secs) == 1:
                try:
                    row["channels"], _c = _read_channels(secs[0])
                except PlanError as exc:
                    row["channel_error"] = str(exc)
            rows.append(row)
    return rows


def R_guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _find_binding(seq, guid_text):
    hits = [b for b in seq.get_bindings() if R_guid(b.get_id()) == guid_text]
    return hits[0] if len(hits) == 1 else None


def _passage_owned(actors, show):
    out = set()
    for a in actors:
        if a.get_class().get_name() == "InfinityStagePassageActor" and str(a.get_actor_label()).startswith(
                PASSAGE_ACTOR_PREFIX) and a.get_editor_property("show_asset") == show:
            out |= {m.get_path_name() for m in a.get_editor_property("managed_attachment_actors") if m}
    return out


def _conflicts(here):
    out = {}
    for k, rel in STATE_FILES.items():
        p = os.path.join(here, rel)
        applied = False
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as h:
                    d = json.load(h)
                applied = bool(d.get("applied")) or str(d.get("state") or d.get("status") or "") in ("applied",
                                                                                                     "saved")
            except Exception:  # noqa: BLE001 - unreadable = treat as applied (fail closed)
                applied = True
        out[k] = applied
    return out


def _shorten(here):
    p = os.path.join(here, "p01_shorten_record.json")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as h:
        d = json.load(h)
    return d if d.get("applied") else None


def _gather(R, args, run):
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_DID_NOT_LOAD")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors = _actors()
    h = args["hangar"]
    root = _one(actors, h["root_label"], run)
    rr = root.get_actor_rotation()
    rows = _rows(actors)
    slab = None
    if args.get("trim_slab_label"):
        hits = [x for x in rows if x["label"] == args["trim_slab_label"]]
        slab = {"loc": hits[0]["loc"], "rot": hits[0]["rot"], "scale": hits[0]["scale"]} if len(hits) == 1 else None
    shorten = _shorten(_here())
    facts = {"end_view": _end_view(R, show, args["passage_guid"]),
             "root": {"loc": _v3(root.get_actor_location()), "rot": [float(rr.roll), float(rr.pitch), float(rr.yaw)]},
             "root_pitch": float(rr.pitch), "entry_cam": _entry_cam(actors, args.get("scene_label_prefix", "Scene 1 ")),
             "rows": rows, "passage_owned": sorted(_passage_owned(actors, show)),
             "bindings": _binding_rows(_sequences(show, args), world, args),
             "removed_cm": float(shorten["plan"]["removed_cm"]) if shorten else None, "slab": slab,
             "conflicts": _conflicts(_here())}
    plan = build_plan(facts, args)
    return plan, facts, show, master, world


def _content_file(path, ext=".uasset"):
    proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(proj, "Content", *path[len("/Game/"):].split("/")) + ext


def _backup(run, suffix, packages):
    proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(proj, "Backups", "PreS1Redock%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for path in packages:
        src = _content_file(path, ".umap" if path == EXPECTED_WORLD else ".uasset")
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = []
        for x in (src, dst):
            with open(x, "rb") as handle:
                digest.append(hashlib.sha256(handle.read()).hexdigest())
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"asset": path, "source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _rel_map(actors, root_label, paths):
    by = {a.get_path_name(): a for a in actors}
    root = next(a for a in actors if str(a.get_actor_label()) == root_label)
    rt = root.get_actor_transform()
    return {p: _v3(unreal.MathLibrary.inverse_transform_location(rt, by[p].get_actor_location()))
            for p in paths if p in by}


def _live_view(args, plan):
    actors = _actors()
    by = {a.get_path_name(): a for a in actors}
    live = {"actors": {}, "slab": None, "channels": {}, "templates": {}}
    for m in plan["moves"] + plan["carried"]:
        if m["path"] in by:
            live["actors"][m["path"]] = _v3(by[m["path"]].get_actor_location())
    if plan.get("trim"):
        hits = [a for a in actors if str(a.get_actor_label()) == args["trim_slab_label"]]
        if len(hits) == 1:
            live["slab"] = {"loc": _v3(hits[0].get_actor_location()), "scale": _v3(hits[0].get_actor_scale3d())}
    for x in plan["rekeys"]:
        seq = unreal.load_asset(x["sequence"])
        b = _find_binding(seq, x["guid"]) if seq else None
        if b is None:
            continue
        _t, secs = _transform_section(b)
        if len(secs) == 1:
            live["channels"][(x["sequence"], x["guid"])] = _read_channels(secs[0])[0]
        t = _template_pose(b)
        if t is not None:
            live["templates"][(x["sequence"], x["guid"])] = t
    return live, actors


def _write(args, plan, side, run):
    """side 'after' (APPLY) or 'before' (REVERT). Each write read back at once."""
    actors = _actors()
    by = {a.get_path_name(): a for a in actors}
    for m in plan["moves"]:                                           # top-level only; children follow
        a = by.get(m["path"])
        if a is None:
            raise PlanError("ACTOR_GONE: %s" % m["label"])
        a.modify()
        a.set_actor_location(unreal.Vector(*m[side]), False, False)   # p02_straighten_followons.py:176-180 [prec]
        if dist(_v3(a.get_actor_location()), m[side]) > READBACK_CM:
            raise PlanError("ACTOR_READBACK: %s" % m["label"])
    if plan.get("trim"):
        hits = [a for a in actors if str(a.get_actor_label()) == args["trim_slab_label"]]
        if len(hits) != 1:
            raise PlanError("SLAB_COUNT: %d" % len(hits))
        t = plan["trim"][side]
        hits[0].modify()
        hits[0].set_actor_location(unreal.Vector(*t["loc"]), False, False)
        hits[0].set_actor_scale3d(unreal.Vector(*t["scale"]))          # hangar_exit_doors.py:1031 [prec]
    for x in plan["rekeys"]:
        seq = unreal.load_asset(x["sequence"])
        b = _find_binding(seq, x["guid"])
        if b is None:
            raise PlanError("BINDING_GONE: %s | %s" % (x["sequence"], x["binding"]))
        _t, secs = _transform_section(b)
        if len(secs) != 1:
            raise PlanError("SECTIONS_CHANGED: %s" % x["binding"])
        seq.modify()
        now, chans = _read_channels(secs[0])
        for name, c in zip(CHANNELS, chans):
            want = x[side][name]
            if [k[0] for k in now[name]["keys"]] != [k[0] for k in want["keys"]]:
                raise PlanError("KEY_FRAMES_CHANGED: %s %s" % (x["binding"], name))
            if want.get("default") is not None and (now[name]["default"] is None or
                                                    abs(now[name]["default"] - want["default"]) > 1e-6):
                c.set_default(float(want["default"]))                     # hangar_build.py:483 [prec]
            for k, row in zip(list(c.get_keys()), want["keys"]):
                if abs(float(k.get_value()) - row[1]) > 1e-6:
                    k.set_value(float(row[1]))                            # p02_straighten_followons.py:535 [prec]
        if not channels_equal(_read_channels(secs[0])[0], x[side]):
            raise PlanError("CHANNEL_READBACK: %s" % x["binding"])
        if x["kind"] == "SPAWNABLE":
            root = b.get_object_template().get_editor_property("root_component")
            root.set_editor_property("relative_location", unreal.Vector(*x["template_" + side]["loc"]))
            if dist(_template_pose(b)["loc"], x["template_" + side]["loc"]) > READBACK_CM:
                raise PlanError("TEMPLATE_READBACK: %s" % x["binding"])


def _allowed(args, with_match):
    out = [args["rise_sequence"], args["interaction_sequence"]]
    if with_match:
        out += [args["scene_sequence"], MASTER_PATH, SHOW_PATH]
    return out


def _save(R, run, packages_dirty, world, record_path, backup):
    for path in packages_dirty["content"]:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s|record=%s (REVERT or restore %s)" % (path, record_path, backup))
    if EXPECTED_WORLD in packages_dirty["maps"]:
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):   # match_scene1_handoff.py:122
            _stop(run, "LEVEL_SAVE_FAILED|record=%s (restore %s)" % (record_path, backup))


def _log(run, plan):
    s = plan["solution"]
    unreal.log("%s_PLAN|run=%s|delta=%s|old_dock=%s|new_dock=%s|top=%d|carried=%d|rekeys=%d|predicted=%d" % (
        MARK, run, s["delta"], s["old_dock"]["loc"], s["new_dock"]["loc"], len(plan["moves"]), len(plan["carried"]),
        len(plan["rekeys"]), int(plan["predicted"])))
    for m in plan["moves"]:
        unreal.log("%s_MOVE|run=%s|%s|%s -> %s" % (MARK, run, m["label"], m["before"], m["after"]))
    for k in ("UNKNOWN", "ACKED", "REGENERATED", "PASSAGE_OWNED", "TRIM"):
        for row in plan["region"][k]:
            unreal.log("%s_NOT_MOVED|run=%s|%s|%s" % (MARK, run, k, json.dumps(row, sort_keys=True)))
    for text in plan["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, text))
    for text in plan["warnings"]:
        unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, text))


def run_dry(R, args, run):
    before = R._census()
    plan, facts, _s, _m, _w = _gather(R, args, run)
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(dict(plan, tool=TOOL, run=run, mode="DRY", args=args, apply_ready=not plan["refusals"],
                       live_root=facts["root"], end_view=facts["end_view"], entry_cam=facts["entry_cam"],
                       removed_cm=facts["removed_cm"], conflicts=facts["conflicts"],
                       binding_scan=[{k: b[k] for k in ("sequence", "binding", "kind", "has_transform", "sections")}
                                     for b in facts["bindings"]]),
                  handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
    _log(run, plan)
    if R._census() != before:
        _stop(run, "DRY_DIRTIED|" + json.dumps(R._census()))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|predicted=%d|refusals=%d|delta=%s|top=%d|carried=%d|"
               "rekeys=%d|unknown=%d|report=%s" % (
                   MARK, run, int(not plan["refusals"]), int(plan["predicted"]), len(plan["refusals"]),
                   plan["solution"]["delta"], len(plan["moves"]), len(plan["carried"]), len(plan["rekeys"]),
                   len(plan["region"]["UNKNOWN"]), out))


def run_apply(R, args, run):
    plan, facts, show, master, world = _gather(R, args, run)
    plan["refusals"] += expected_refusals(plan, args.get("expected") or {}, "APPLY")
    if plan["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(plan["refusals"][:12]))
    record_path = os.path.join(_here(), RECORD_NAME)
    match = bool(args.get("match_handoff", True))
    pkgs = [EXPECTED_WORLD, args["rise_sequence"], args["interaction_sequence"], args["scene_sequence"], MASTER_PATH,
            SHOW_PATH]
    backup = _backup(run, "", pkgs)
    unreal.log("%s_BACKUP_OK|run=%s|backup=%s" % (MARK, run, backup))
    actors = _actors()
    root_label = args["hangar"]["root_label"]
    rel_paths = [m["path"] for m in plan["carried"]]
    rel_before = _rel_map(actors, root_label, rel_paths)
    snap_before = R._snapshot(show, master, ["1"])
    view_before = R.protected_view(show)
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "backup": backup, "args": args,
              "approved_by": args.get("approved_by"), "applied": False, "plan": plan,
              "entry_cam_before": facts["entry_cam"], "end_view": facts["end_view"],
              "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "stale_references": plan["stale_references"], "klara_dock_for_args": plan["klara_dock_for_args"]}
    R.write_record_exclusive(record_path, record)                  # BEFORE any change
    failures = []
    try:
        _write(args, plan, "after", run)
        live, actors = _live_view(args, plan)
        failures += readback_failures(plan, live, "after")
        failures += rel_failures(rel_before, _rel_map(actors, root_label, rel_paths))
    except (PlanError, Exception) as exc:  # noqa: BLE001 - reported, never swallowed
        failures.append("WRITE_RAISED: %r" % exc)
    if not failures and match:
        guid = None
        for c in show.get_editor_property("cues"):
            if c.get_editor_property("type") == unreal.InfinityCueType.SCENE and \
                    str(c.get_editor_property("label")).startswith(args.get("scene_label_prefix", "Scene 1 ")):
                guid = c.get_editor_property("cue_guid") if guid is None else "DUP"
        if guid is None or guid == "DUP":
            failures.append("SCENE1_CUE_NOT_UNIQUE")
        else:
            rep = R.unwrap(unreal.InfinityStageCameraPilotLibrary.match_named_scene_handoffs(show, [guid], 1), 1)
            record["match_report"] = str(rep)
            if rep is None:
                failures.append("MATCH_REFUSED")
            else:
                stale, text = R._handoffs(show)
                if stale is None or R._guid(guid) in stale:
                    failures.append("SCENE1_STILL_STALE: %s" % text)
                ent = _entry_cam(_actors(), args.get("scene_label_prefix", "Scene 1 "))
                record["entry_cam_after"] = ent
                failures += match_gate(ent, plan["solution"]["new_seat"], float(facts["root"]["rot"][2]))
    if not failures and args.get("rebuild_master", True):
        ok, text = R._rebuild(show, master)
        record["rebuild_report"] = text
        if not ok:
            failures.append("REBUILD_FAILED: %s" % text)
        else:
            snap_after = R._snapshot(show, master, ["1"])
            failures += no_change_gate(snap_before, snap_after)
            show_rows, master_rows = R._label_rows(master, snap_after["segments"], snap_after["tick"],
                                                   R._guid_by_label(show))
            failures += R.sync_gate(show_rows, master_rows)
    if R.protected_view(show) != view_before:
        failures.append("SHOW_CONTENT_CHANGED")
    census = R._census()
    failures += census_gate(census, _allowed(args, match or args.get("rebuild_master", True)))
    if failures:
        R.update_record(record_path, dict(record, applied=False, failed=failures))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|NOTHING SAVED; Don't-Save restart; backup %s" % (failures[:10], backup))
    _save(R, run, census, world, record_path, backup)
    record.update({"applied": True, "saved_census": census})
    R.update_record(record_path, record)
    live, actors = _live_view(args, plan)
    dd = readback_failures(plan, live, "after")
    if match:
        dd += match_gate(_entry_cam(actors, args.get("scene_label_prefix", "Scene 1 ")), plan["solution"]["new_seat"],
                         float(facts["root"]["rot"][2]))
    if R._census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(R._census()))
    if dd:
        record["post_save_readback_failed"] = dd
        R.update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT or restore %s)" % (dd[:8], backup))
    unreal.log("%s_APPLY_OK|run=%s|delta=%s|new_dock=%s|top=%d|carried=%d|rekeys=%d|matched=%d|saved=%s|backup=%s|"
               "record=%s|tests_required_singly=InfinityStage.Editor.SavedMasterMatchesShow,"
               "InfinityStage.Editor.SceneCutBindingsResolve|klara_dock_for_args=%s" % (
                   MARK, run, plan["solution"]["delta"], plan["solution"]["new_dock"]["loc"], len(plan["moves"]),
                   len(plan["carried"]), len(plan["rekeys"]), int(match), census, backup, record_path,
                   json.dumps(plan["klara_dock_for_args"])))


def run_revert(R, args, run):
    record_path = os.path.join(_here(), RECORD_NAME)
    with open(record_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied"):
        _stop(run, "REVERT_RECORD_CONTEXT")
    plan, rargs = record["plan"], record["args"]
    live, actors = _live_view(rargs, plan)
    drift = readback_failures(plan, live, "after")
    if drift:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r (restore from %s instead)" % (drift[:8], record["backup"]))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    backup = _backup(run, "Revert", [EXPECTED_WORLD, rargs["rise_sequence"], rargs["interaction_sequence"]])
    rel_paths = [m["path"] for m in plan["carried"]]
    rel_before = _rel_map(actors, rargs["hangar"]["root_label"], rel_paths)
    errs = []
    try:
        _write(rargs, plan, "before", run)
        live, actors = _live_view(rargs, plan)
        errs += readback_failures(plan, live, "before")
        errs += rel_failures(rel_before, _rel_map(actors, rargs["hangar"]["root_label"], rel_paths))
    except (PlanError, Exception) as exc:  # noqa: BLE001
        errs.append("WRITE_RAISED: %r" % exc)
    census = R._census()
    errs += census_gate(census, _allowed(rargs, False))
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (errs[:8],
                                                                                              record["backup"]))
    _save(R, run, census, world, record_path, backup)
    live, _a = _live_view(rargs, plan)
    final = readback_failures(plan, live, "before")
    if R._census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(R._census()))
    if final:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (final[:8], record["backup"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|moved_back=%d|rekeys=%d|backup=%s|record=%s|next=Scene 1 handoff still follows "
               "P01's CURRENT end: after p01_shorten REVERT run match_scene1_handoff.py" % (
                   MARK, run, len(plan["moves"]), len(plan["rekeys"]), backup, archived))


def main():
    g = globals()
    args = g.get("S1REDOCK_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("S1REDOCK-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    R = load_retime(_here())
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    rp = os.path.join(_here(), RECORD_NAME)
    applied = False
    if os.path.exists(rp):
        with open(rp, "r", encoding="utf-8") as handle:
            applied = bool(json.load(handle).get("applied"))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "zz_actors": [str(a.get_actor_label()) for a in _actors() if str(a.get_actor_label()).startswith("ZZ_")],
             "census": R._census(), "record_exists": os.path.exists(rp), "record_applied": applied,
             "shorten_applied": _shorten(_here()) is not None, "conflicts": _conflicts(_here())}
    early = live_gates(state) if mode != "DRY" else [x for x in live_gates(state)
                                                     if x.startswith(("CONFIRM", "PIE", "SEQUENCER", "DIRTY"))]
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        if mode == "REVERT":
            run_revert(R, args, run)
        elif mode == "APPLY":
            run_apply(R, args, run)
        else:
            run_dry(R, args, run)
    except (PlanError, R.PlanError) as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
