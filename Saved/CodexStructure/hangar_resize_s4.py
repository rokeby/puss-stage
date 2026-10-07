"""S4 HANGAR RESIZE IN PLACE (7 Oct, offline-written, NEVER RUN IN UNREAL). Plan: Saved/CodexConductor/
S4_HANGAR_REBUILD_PLAN.md (conductor-approved 7 Oct under Gary's "Rebuild the S4 hangar bigger"). Targets:
hangar_resize_s4_targets.json from hangar_resize_s4_plan.py (system Python; hangar_build.py's own plan_for by AST).
Harness: test_hangar_resize_s4_offline.py.

Tiers: [decl] read in source (file:line), [prec] in-repo precedent call, [meas] a run record, [inf] inferred (why).

WHAT IT DOES
  Moves and rescales the EXISTING S4 hangar actors to depth 6000 / half_w 1400 / height 3000 / lattice_z 1700 /
  lattice_fly 1200 / ghost_x 3500, and rewrites the VALUES of the lattice fly's Location.Z keys (+ default) in
  LS_S4_HangarRise: 2800 -> 2900, 1200 -> 1700. Key TIMES, every other channel, the root, the Arrival, its 39
  PreSceneFloatDrives and every binding are untouched (same actors, same labels) [the reason this is not a
  hangar_build rebuild: S4_HANGAR_REBUILD_PLAN.md section 1].
  Composition: every pose is ROOT-RELATIVE ("S4 Hangar Root" live transform, never written; memory
  puss-level-saved-landed-frame-trap). The live lattice fly is either at rest (2800) or landed (1200) and the roof hinge
  either upright (rel pitch -90) or flat (0); both are read live and the expectations follow (hangar_build.py:299-323
  compare does the same for the roof [decl]).

MODES (hangar_resize_s4_run.py <- hangar_resize_s4_args.json; confirm "<MODE> HANGARRESIZES4")
  DRY    read-only. Label contract (refuses on a missing, duplicated or EXTRA owned label), drift (every piece within
         drift_tol_cm of its OLD pose, every scaled piece at its OLD scale, hinges unit-scale, resized slabs
         childless), the key plan (only keys valued 2800/1200 change; any other value refuses), the API table, the
         per-actor rows and plan_sha256. Writes hangar_resize_s4_dry.json. HANGAR_RESIZE_S4_DRY_OK|run=..|apply_ready=..
  APPLY  needs plan_sha256 == the DRY's (recomputed live). Gates -> Backups/PreHangarResizeS4-<run> (umap,
         LS_S4_HangarRise, LS_DevScene_04) -> exclusive fsynced record (every before value) -> actor writes, parents
         first -> in-memory read-back of ALL pieces -> key VALUE edits on exact keys -> read-back -> census (only the
         level + the rise dirty) -> save those two only -> post-save read-back of every written value -> census 0+0 ->
         HANGAR_RESIZE_S4_APPLY_OK|run=..
  REVERT drift check (live == record.after, root unchanged) -> backup -> record.before -> read-back -> narrow save ->
         read-back -> census 0+0 -> record renamed .reverted-<run> -> HANGAR_RESIZE_S4_REVERT_OK|run=..
  Failure: HANGAR_RESIZE_S4_STOPPED|run=..|reason=.. (NOTHING saved unless the reason says so: Don't-Save restart,
  then rename the record .failed-<run>; the backup is named).
Never: hangar_build APPLY, hangar_exit_doors, s4_rekey_window, arrivals tools, Save All, reload, open/scrub Sequencer,
GetBoundObjects, end PIE; no unreal objects in module globals. Importing without `unreal` runs nothing.
"""
import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "hangar_resize_s4"
MARK = "HANGAR_RESIZE_S4"
CONFIRM_SUFFIX = "HANGARRESIZES4"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
SCENE_SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
ROOT_LABEL = "S4 Hangar Root"
FLY_LABEL = "S4 Hangar Lattice Fly"
ROOF_HINGE_LABEL = "S4 Hangar Roof Hinge"
APRON_LABEL = "S4 Hangar Apron"
PPV_LABEL = "S4 Hangar Pinned Exposure"
TAG = "RigAtmos.Scene4Hangar"                                    # hangar_build.py:179 naming [decl]
OWNED_PREFIXES = ("S4 Hangar", "S4 Lattice", "S4 Practical", "S4 Uplight", "S4 Ghost")
FLY_CHANNEL_INDEX = 2                                            # Location.Z (hangar_build.py:501, s4_rekey_window_apply.py) [decl]
TARGETS_NAME = "hangar_resize_s4_targets.json"
DRY_NAME = "hangar_resize_s4_dry.json"
RECORD_NAME = "hangar_resize_s4_record.json"
TEMP_PREFIX = "ZZ_"

if unreal is not None:
    HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
else:
    HERE = os.path.dirname(os.path.abspath(__file__))


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure planning (no Unreal). Exercised with +/- controls by test_hangar_resize_s4_offline.py.
# =====================================================================================================================

def _dist(a, b):
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _maxabs(a, b):
    return max(abs(float(a[i]) - float(b[i])) for i in range(len(a)))


def expected_labels(targets):
    return sorted([p["label"] for p in targets["pieces"]] + [APRON_LABEL, PPV_LABEL])


def label_contract(targets, live_labels, allow_extra):
    """live_labels: {label: {"count": n, "owned": bool}} for every level actor that has an owned prefix or the S4 tag
    or an expected label. -> (missing, duplicated, extra)."""
    want = set(expected_labels(targets))
    missing = sorted(l for l in want if live_labels.get(l, {}).get("count", 0) == 0)
    duplicated = sorted(l for l in want if live_labels.get(l, {}).get("count", 0) > 1)
    extra = sorted(l for l, row in live_labels.items()
                   if l not in want and row.get("owned") and l not in set(allow_extra or []))
    return missing, duplicated, extra


def fly_state(fly_rel_z, targets, tol):
    lf = targets["lattice_fly"]
    if abs(float(fly_rel_z) - lf["rest_z_old"]) <= tol:
        return {"state": "rest", "off_old": 0.0, "off_new": 0.0}
    if abs(float(fly_rel_z) - lf["landed_z_old"]) <= tol:
        return {"state": "landed", "off_old": lf["landed_z_old"] - lf["rest_z_old"],
                "off_new": lf["landed_z_new"] - lf["rest_z_new"]}
    raise PlanError("FLY_STATE_UNKNOWN: root-relative z %.3f is neither rest %.1f nor landed %.1f"
                    % (float(fly_rel_z), lf["rest_z_old"], lf["landed_z_old"]))


def roof_state(rel_pitch, tol_deg=0.5):
    if abs(float(rel_pitch) + 90.0) <= tol_deg:
        return "upright"
    if abs(float(rel_pitch)) <= tol_deg:
        return "flat"
    raise PlanError("ROOF_STATE_UNKNOWN: roof hinge relative pitch %.3f" % float(rel_pitch))


def pose_rel(piece, which, fly, roof, roof_hinge_loc):
    """Root-relative location of a piece in the LIVE state. which = 'old' | 'new'."""
    x, y, z = [float(v) for v in piece["loc_" + which]]
    if piece.get("fly_subtree"):
        z += fly["off_" + which]
    if piece.get("roof_subtree") and roof == "upright":       # hangar_build.py:309-311 [decl]
        hx, _hy, hz = [float(v) for v in roof_hinge_loc]
        x, z = hx + (z - hz), hz - (x - hx)
    return [x, y, z]


def scale_of(size, cube_cm):
    return [float(s) / float(cube_cm) for s in size]


def plan_actor_writes(targets, live, tol):
    """live = {"pieces": {label: {"rel": [3], "scale": [3], "depth": int, "children": int}}, "fly_rel_z": float,
    "roof_pitch": float, "world_fixed": {APRON_LABEL: {"scale": [3]}, PPV_LABEL: {"scale": [3]}}}.
    tol = {"drift_cm", "scale"}. -> {"fly", "roof", "writes", "all_after", "world_fixed", "drift", "refusals"}."""
    refusals, drift = [], []
    fly = fly_state(live["fly_rel_z"], targets, tol["drift_cm"])
    roof = roof_state(live["roof_pitch"])
    rh = targets["roof_hinge_loc"]
    cube = float(targets.get("cube_cm", 100.0))
    writes, all_after = [], {}
    for p in targets["pieces"]:
        lab = p["label"]
        row = live["pieces"].get(lab)
        if row is None:
            refusals.append("PIECE_NOT_READ: " + lab)
            continue
        old, new = pose_rel(p, "old", fly, roof, rh), pose_rel(p, "new", fly, roof, rh)
        all_after[lab] = new
        if _dist(row["rel"], old) > tol["drift_cm"]:
            drift.append("%s at %s, want %s (%.2f cm)" % (lab, [round(v, 2) for v in row["rel"]],
                                                       [round(v, 2) for v in old], _dist(row["rel"], old)))
        resized = bool(p["size_old"]) and _maxabs(p["size_old"], p["size_new"]) > 1e-6
        if p["kind"] == "hinge" and _maxabs(row["scale"], [1.0, 1.0, 1.0]) > tol["scale"]:
            refusals.append("HINGE_NOT_UNIT_SCALE: %s %s" % (lab, row["scale"]))
        scale_before = scale_after = None
        if resized:
            want_old = scale_of(p["size_old"], cube)
            if _maxabs(row["scale"], want_old) > tol["scale"] * max(1.0, max(abs(v) for v in want_old)):
                drift.append("%s scale %s, want %s" % (lab, [round(v, 5) for v in row["scale"]], want_old))
            if row.get("children", 0):
                refusals.append("RESIZED_PIECE_HAS_CHILDREN: %s (%d) - a scale would carry them" % (lab, row["children"]))
            scale_before, scale_after = list(row["scale"]), scale_of(p["size_new"], cube)
        if _dist(old, new) > 1e-6 or resized:
            writes.append({"label": lab, "kind": p["kind"], "depth": int(row["depth"]), "rel_before": list(row["rel"]),
                           "rel_after": new, "scale_before": scale_before, "scale_after": scale_after})
    writes.sort(key=lambda w: (w["depth"], w["label"]))          # parents first: children ride, then are set exactly
    wf = targets["world_fixed"]
    fixed = []
    ap = live["world_fixed"].get(APRON_LABEL)
    if ap is None:
        refusals.append("PIECE_NOT_READ: " + APRON_LABEL)
    else:
        if _maxabs(ap["scale"], wf[APRON_LABEL]["scale_old"]) > tol["scale"] * 100.0:
            drift.append("%s scale %s, want %s" % (APRON_LABEL, ap["scale"], wf[APRON_LABEL]["scale_old"]))
        fixed.append({"label": APRON_LABEL, "scale_before": list(ap["scale"]), "scale_after": list(wf[APRON_LABEL]["scale_new"])})
    pv = live["world_fixed"].get(PPV_LABEL)
    if pv is None:
        refusals.append("PIECE_NOT_READ: " + PPV_LABEL)
    else:
        if abs(float(pv["scale"][1]) - wf[PPV_LABEL]["scale_y_old"]) > tol["scale"] * 100.0:
            drift.append("%s scale.y %s, want %s" % (PPV_LABEL, pv["scale"][1], wf[PPV_LABEL]["scale_y_old"]))
        after = list(pv["scale"])
        after[1] = wf[PPV_LABEL]["scale_y_new"]
        fixed.append({"label": PPV_LABEL, "scale_before": list(pv["scale"]), "scale_after": after})
    return {"fly": fly, "roof": roof, "writes": writes, "all_after": all_after, "world_fixed": fixed,
            "drift": drift, "refusals": refusals}


def plan_key_values(keys, default, targets, tol):
    """keys = [[frame_number, value]] in channel order; default = float or None. Only VALUES that equal the old rest
    or landed z change (times never). -> {"keys_before", "keys_after", "default_before", "default_after", "refusals"}."""
    lf = targets["lattice_fly"]
    mapping = [(lf["rest_z_old"], lf["rest_z_new"]), (lf["landed_z_old"], lf["landed_z_new"])]

    def remap(v):
        for a, b in mapping:
            if abs(float(v) - a) <= tol:
                return b
        return None

    refusals, after = [], []
    for t, v in keys:
        nv = remap(v)
        if nv is None:
            refusals.append("KEY_VALUE_UNMAPPED: frame %s value %.4f" % (t, float(v)))
            nv = float(v)
        after.append([t, nv])
    if not keys:
        refusals.append("NO_FLY_KEYS")
    d_after = None
    if default is not None:
        d_after = remap(default)
        if d_after is None:
            refusals.append("DEFAULT_UNMAPPED: %.4f" % float(default))
            d_after = float(default)
    return {"keys_before": [[t, float(v)] for t, v in keys], "keys_after": after, "default_before": default,
            "default_after": d_after, "refusals": refusals}


def plan_sha256(actor_plan, key_plan, targets_sha):
    r = lambda v: None if v is None else [round(float(x), 3) for x in v]
    body = {"targets_sha256": targets_sha, "fly": actor_plan["fly"]["state"], "roof": actor_plan["roof"],
            "writes": [[w["label"], r(w["rel_before"]), r(w["rel_after"]), r(w["scale_before"]), r(w["scale_after"])]
                       for w in actor_plan["writes"]],
            "fixed": [[f["label"], r(f["scale_before"]), r(f["scale_after"])] for f in actor_plan["world_fixed"]],
            "keys": [key_plan["keys_before"], key_plan["keys_after"]],
            "default": [key_plan["default_before"], key_plan["default_after"]]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def check_confirm(args):
    mode = str(args.get("mode", "DRY")).upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise PlanError("MODE_INVALID: %r" % mode)
    if args.get("confirm") != "%s %s" % (mode, CONFIRM_SUFFIX):
        raise PlanError("CONFIRM_MISMATCH: want %r" % ("%s %s" % (mode, CONFIRM_SUFFIX)))
    if mode == "APPLY" and not args.get("approved_by"):
        raise PlanError("APPROVAL_MISSING: approved_by is empty")
    if mode == "APPLY" and not args.get("plan_sha256"):
        raise PlanError("PLAN_SHA_MISSING: copy the DRY's plan_sha256 into the args")
    return mode


def tolerances(args):
    return {"drift_cm": float(args.get("drift_tol_cm", 1.0)), "scale": float(args.get("scale_tol", 1e-4)),
            "readback_cm": float(args.get("readback_tol_cm", 0.05)), "key": float(args.get("key_tol", 0.01))}


def readback_bad(want_rel, got_pieces, tol_cm, scales=None, scale_tol=1e-4):
    """want_rel {label: [3]}, got_pieces {label: {"rel", "scale"}}, scales {label: [3] or None}. -> list of misses."""
    bad = []
    for lab, want in sorted(want_rel.items()):
        got = got_pieces.get(lab)
        if got is None or _dist(got["rel"], want) > tol_cm:
            bad.append("%s rel %s want %s" % (lab, got and [round(v, 3) for v in got["rel"]], [round(v, 3) for v in want]))
    for lab, want in sorted((scales or {}).items()):
        got = got_pieces.get(lab)
        if want is not None and (got is None or _maxabs(got["scale"], want) > scale_tol * max(1.0, max(abs(v) for v in want))):
            bad.append("%s scale %s want %s" % (lab, got and got["scale"], want))
    return bad


def keys_bad(got_keys, want_keys, got_default, want_default, tol):
    """Float32-tolerant: times must be IDENTICAL frame numbers, values within tol."""
    bad = []
    if len(got_keys) != len(want_keys):
        return ["KEY_COUNT %d != %d" % (len(got_keys), len(want_keys))]
    for (gt, gv), (wt, wv) in zip(got_keys, want_keys):
        if gt != wt or abs(float(gv) - float(wv)) > tol:
            bad.append("key %s=%.4f want %s=%.4f" % (gt, float(gv), wt, float(wv)))
    if want_default is not None and (got_default is None or abs(float(got_default) - float(want_default)) > tol):
        bad.append("default %r want %r" % (got_default, want_default))
    return bad


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# =====================================================================================================================
# Unreal side (everything inside functions: no unreal objects in module globals).
# =====================================================================================================================

def stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def census():
    return {"dirty_maps": sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "dirty_content": sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def context(run, mutating):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop(run, "PIE_OR_SIE_ACTIVE")
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        stop(run, "WRONG_WORLD")
    if mutating:
        c = census()
        if c["dirty_maps"] or c["dirty_content"]:
            stop(run, "ALREADY_DIRTY|%s" % json.dumps(c))
        if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
            stop(run, "SEQUENCER_OPEN")
    return world


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _depth(actor):
    k, p = 0, actor.get_attach_parent_actor()
    while p is not None:
        k, p = k + 1, p.get_attach_parent_actor()
    return k


def gather(run, targets):
    """-> (live dict for plan_actor_writes, label rows for label_contract, actors by label, root transform row)."""
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith(TEMP_PREFIX) for a in actors):
        stop(run, "BENCH_ACTORS_ZZ_PRESENT")
    want = set(expected_labels(targets))
    rows, by_label = {}, {}
    for a in actors:
        lab = str(a.get_actor_label())
        tags = [str(t) for t in a.get_editor_property("tags")]
        owned = lab.startswith(OWNED_PREFIXES) or TAG in tags
        if lab in want or owned:
            r = rows.setdefault(lab, {"count": 0, "owned": owned})
            r["count"] += 1
            by_label.setdefault(lab, []).append(a)
    roots = by_label.get(ROOT_LABEL, [])
    if len(roots) != 1:
        stop(run, "ROOT_COUNT|%d" % len(roots))
    rt = roots[0].get_actor_transform()
    root_row = {"loc": _vec(rt.translation), "rot": [float(rt.rotation.rotator().roll), float(rt.rotation.rotator().pitch),
                                                     float(rt.rotation.rotator().yaw)], "scale": _vec(rt.scale3d)}
    pieces = {}
    for p in targets["pieces"]:
        found = by_label.get(p["label"], [])
        if len(found) != 1:
            continue
        a = found[0]
        pieces[p["label"]] = {"rel": _vec(unreal.MathLibrary.inverse_transform_location(rt, a.get_actor_location())),
                              "scale": _vec(a.get_actor_relative_scale3d()), "depth": _depth(a),
                              "children": len(a.get_attached_actors())}
    fixed = {}
    for lab in (APRON_LABEL, PPV_LABEL):
        found = by_label.get(lab, [])
        if len(found) == 1:
            fixed[lab] = {"scale": _vec(found[0].get_actor_scale3d())}
    fly = by_label.get(FLY_LABEL, [])
    roof = by_label.get(ROOF_HINGE_LABEL, [])
    live = {"pieces": pieces, "world_fixed": fixed,
            "fly_rel_z": pieces.get(FLY_LABEL, {"rel": [0, 0, float("nan")]})["rel"][2],
            "roof_pitch": float(roof[0].root_component.get_editor_property("relative_rotation").pitch) if len(roof) == 1 else float("nan")}
    return live, rows, by_label, rt, root_row


def fly_channel(run):
    seq = unreal.load_asset(SEQ)
    if seq is None:
        stop(run, "RISE_NOT_LOADED")
    found = [b for b in seq.get_bindings() if str(b.get_display_name()) == FLY_LABEL]   # s4_rekey_window_apply.py [prec]
    if len(found) != 1:
        stop(run, "FLY_BINDING_COUNT|%d" % len(found))
    tracks = [t for t in found[0].get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)]
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        stop(run, "FLY_TRANSFORM_TRACK_SHAPE")
    chans = list(tracks[0].get_sections()[0].get_all_channels())
    if len(chans) <= FLY_CHANNEL_INDEX:
        stop(run, "FLY_CHANNEL_MISSING")
    ch = chans[FLY_CHANNEL_INDEX]
    if not str(ch.get_name()).startswith("Location.Z"):          # names carry a suffix (memory ue58-sequencer-read-traps)
        stop(run, "FLY_CHANNEL_NAME|%s" % ch.get_name())
    return seq, ch


def read_keys(ch):
    keys = [[int(k.get_time().frame_number.value), float(k.get_value())] for k in ch.get_keys()]
    default = float(ch.get_default()) if ch.has_default() else None
    return keys, default


def write_key_values(ch, values, default):
    ks = list(ch.get_keys())
    if len(ks) != len(values):
        raise PlanError("KEY_COUNT_CHANGED")
    for k, (_t, v) in zip(ks, values):
        if abs(float(k.get_value()) - float(v)) > 1e-9:
            k.set_value(float(v))                                # value only: time and tangents untouched [inf]
    if default is not None:
        ch.set_default(float(default))                           # hangar_build.py:478 set_default [prec]


def api_table():
    rows = []
    for name, ok in (("Actor.get_actor_relative_scale3d", hasattr(unreal.Actor, "get_actor_relative_scale3d")),
                     ("Actor.set_actor_relative_scale3d (hangar_exit_doors.py:613 prec)", hasattr(unreal.Actor, "set_actor_relative_scale3d")),
                     ("Actor.get_attached_actors", hasattr(unreal.Actor, "get_attached_actors")),
                     ("MovieSceneScriptingDoubleKey.set_value", hasattr(unreal, "MovieSceneScriptingDoubleKey") and hasattr(unreal.MovieSceneScriptingDoubleKey, "set_value")),
                     ("MovieSceneScriptingDoubleChannel.get_default/has_default/set_default",
                      hasattr(unreal, "MovieSceneScriptingDoubleChannel") and all(hasattr(unreal.MovieSceneScriptingDoubleChannel, m) for m in ("get_default", "has_default", "set_default")))):
        rows.append({"api": name, "ok": bool(ok), "tier": "inf (hasattr probe, this run)"})
    return rows


def plan_live(run, args):
    targets_path = os.path.join(HERE, TARGETS_NAME)
    targets = json.load(open(targets_path, encoding="utf-8"))
    if targets.get("fails"):
        stop(run, "TARGETS_HAVE_FAILS")
    live, rows, by_label, rt, root_row = gather(run, targets)
    missing, duplicated, extra = label_contract(targets, rows, args.get("allow_extra_labels"))
    tol = tolerances(args)
    refusals = []
    if missing:
        refusals.append("LABELS_MISSING: %s" % missing[:20])
    if duplicated:
        refusals.append("LABELS_DUPLICATED: %s" % duplicated[:20])
    if extra:
        refusals.append("LABELS_EXTRA: %s (add to allow_extra_labels only after review)" % extra[:20])
    if refusals:
        return {"refusals": refusals, "targets": targets, "root": root_row}, None, None, by_label, rt
    try:
        ap = plan_actor_writes(targets, live, tol)
    except PlanError as e:
        return {"refusals": [str(e)], "targets": targets, "root": root_row}, None, None, by_label, rt
    seq, ch = fly_channel(run)
    keys, default = read_keys(ch)
    kp = plan_key_values(keys, default, targets, tol["key"])
    refusals += ap["refusals"] + kp["refusals"] + (["DRIFT: %s" % ap["drift"][:12]] if ap["drift"] else [])
    sha = plan_sha256(ap, kp, sha256_file(targets_path))
    plan = {"refusals": refusals, "root": root_row, "actor_plan": ap, "key_plan": kp, "plan_sha256": sha,
            "targets_sha256": sha256_file(targets_path), "label_count": len(expected_labels(targets)),
            "fly_channel": str(ch.get_name()), "targets": targets}
    return plan, seq, ch, by_label, rt


def _backup(run, purpose, extra_files=()):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "%s-%s" % (purpose, run))
    os.makedirs(folder, exist_ok=False)
    rows = []
    for asset, ext in ((EXPECTED_WORLD, ".umap"), (SEQ, ".uasset"), (SCENE_SEQ, ".uasset")):
        src = os.path.join(project, "Content", *asset[len("/Game/"):].split("/")) + ext
        shutil.copy2(src, folder)
        rows.append({"asset": asset, "sha256": sha256_file(src)})
    for f in extra_files:
        if os.path.exists(f):
            shutil.copy2(f, folder)
    return folder, rows


def _write_exclusive(path, data):
    with open(path, "x", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())


def _rewrite(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _set_pieces(by_label, rt, rows, rel_key, scale_key):
    for w in rows:
        a = by_label[w["label"]][0]
        a.set_actor_location(rt.transform_location(unreal.Vector(*w[rel_key])), False, True)
        if w.get(scale_key) is not None:
            a.set_actor_relative_scale3d(unreal.Vector(*w[scale_key]))


def _set_fixed(by_label, rows, scale_key):
    for f in rows:
        by_label[f["label"]][0].set_actor_scale3d(unreal.Vector(*f[scale_key]))


def _verify(run, targets, want_rel, scales, fixed_want, key_want, default_want, tol, stage):
    live, _rows, _bl, _rt, _root = gather(run, targets)
    bad = readback_bad(want_rel, live["pieces"], tol["readback_cm"], scales, tol["scale"])
    for lab, want in fixed_want.items():
        got = live["world_fixed"].get(lab)
        if got is None or _maxabs(got["scale"], want) > tol["scale"] * 100.0:
            bad.append("%s scale %s want %s" % (lab, got and got["scale"], want))
    _seq, ch = fly_channel(run)
    keys, default = read_keys(ch)
    bad += keys_bad(keys, key_want, default, default_want, tol["key"])
    if bad:
        stop(run, "READBACK_%s|%s" % (stage, bad[:10]))


def _save(run):
    c = census()
    if set(c["dirty_maps"]) - {EXPECTED_WORLD} or set(c["dirty_content"]) - {SEQ}:
        stop(run, "UNEXPECTED_DIRTY|%s|NOTHING saved" % json.dumps(c))
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        stop(run, "SEQUENCE_SAVE_FAILED")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "LEVEL_SAVE_FAILED|sequence already saved")


def main():
    args = globals().get("HANGARRESIZES4_ARGS")
    run = args.get("run_id") or "HANGARRESIZES4-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        mode = check_confirm(args)
    except PlanError as e:
        stop(run, str(e))
    tol = tolerances(args)
    record_path = os.path.join(HERE, RECORD_NAME)

    if mode == "REVERT":
        context(run, True)
        if not os.path.exists(record_path):
            stop(run, "NO_RECORD")
        rec = json.load(open(record_path, encoding="utf-8"))
        if not rec.get("applied"):
            stop(run, "RECORD_NOT_APPLIED (a failed APPLY: Don't-Save restart and rename the record .failed-<run>)")
        targets = rec["targets"]
        live, _rows, by_label, rt, root_row = gather(run, targets)
        if _maxabs(root_row["loc"], rec["root"]["loc"]) > tol["readback_cm"] or _maxabs(root_row["rot"], rec["root"]["rot"]) > 0.01:
            stop(run, "ROOT_MOVED_SINCE_APPLY|%s vs %s" % (root_row, rec["root"]))
        ap, kp = rec["actor_plan"], rec["key_plan"]
        drift = readback_bad(ap["all_after"], live["pieces"], tol["readback_cm"],
                             {w["label"]: w["scale_after"] for w in ap["writes"]}, tol["scale"])
        _seq, ch = fly_channel(run)
        keys, default = read_keys(ch)
        drift += keys_bad(keys, kp["keys_after"], default, kp["default_after"], tol["key"])
        if drift:
            stop(run, "REVERT_DRIFT|%s" % drift[:10])
        backup, _b = _backup(run, "PreHangarResizeS4Revert", [record_path])
        _set_pieces(by_label, rt, sorted(ap["writes"], key=lambda w: (w["depth"], w["label"])), "rel_before", "scale_before")
        _set_fixed(by_label, ap["world_fixed"], "scale_before")
        write_key_values(ch, kp["keys_before"], kp["default_before"])
        want_before = rec["all_before"]
        scales = {w["label"]: w["scale_before"] for w in ap["writes"]}
        fixed = {f["label"]: f["scale_before"] for f in ap["world_fixed"]}
        _verify(run, targets, want_before, scales, fixed, kp["keys_before"], kp["default_before"], tol, "PRESAVE")
        _save(run)
        _verify(run, targets, want_before, scales, fixed, kp["keys_before"], kp["default_before"], tol, "POSTSAVE")
        c = census()
        if c["dirty_maps"] or c["dirty_content"]:
            stop(run, "CENSUS_AFTER|%s (saved)" % json.dumps(c))
        os.replace(record_path, record_path + ".reverted-" + run)
        unreal.log("%s_REVERT_OK|run=%s|writes=%d|backup=%s|census=0+0" % (MARK, run, len(ap["writes"]), backup))
        return

    context(run, mode == "APPLY")
    plan, seq, ch, by_label, rt = plan_live(run, args)
    ap, kp = plan.get("actor_plan"), plan.get("key_plan")
    for w in (ap or {}).get("writes", []):
        unreal.log("%s_ROW|run=%s|%s|rel %s -> %s|scale %s -> %s" % (MARK, run, w["label"], [round(v, 2) for v in w["rel_before"]],
                   [round(v, 2) for v in w["rel_after"]], w["scale_before"], w["scale_after"]))
    for f in (ap or {}).get("world_fixed", []):
        unreal.log("%s_ROW|run=%s|%s|scale %s -> %s" % (MARK, run, f["label"], f["scale_before"], f["scale_after"]))
    if kp:
        unreal.log("%s_KEYS|run=%s|%s|%s -> %s|default %s -> %s" % (MARK, run, SEQ, kp["keys_before"], kp["keys_after"],
                   kp["default_before"], kp["default_after"]))
    if mode == "DRY":
        out = dict(plan, run=run, tool=TOOL, mode="DRY", api_table=api_table(), census=census(),
                   apply_ready=not plan["refusals"])
        out.pop("targets", None)
        with open(os.path.join(HERE, DRY_NAME), "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        unreal.log("%s_DRY_OK|run=%s|apply_ready=%d|writes=%d|fly=%s|roof=%s|plan_sha256=%s|refusals=%s|mutated=0"
                   % (MARK, run, int(out["apply_ready"]), len((ap or {}).get("writes", [])), ap and ap["fly"]["state"],
                      ap and ap["roof"], plan.get("plan_sha256"), plan["refusals"][:6]))
        return

    # ---- APPLY ---------------------------------------------------------------------------------------------------
    if plan["refusals"]:
        stop(run, "REFUSED|%s" % plan["refusals"][:8])
    if plan["plan_sha256"] != args.get("plan_sha256"):
        stop(run, "PLAN_SHA_MISMATCH|live %s args %s (re-run DRY)" % (plan["plan_sha256"], args.get("plan_sha256")))
    if os.path.exists(record_path):
        stop(run, "RECORD_EXISTS (revert first, or rename a failed one)")
    if not all(r["ok"] for r in api_table()):
        stop(run, "API_MISSING|%s" % [r["api"] for r in api_table() if not r["ok"]])
    targets = plan["targets"]
    backup, brows = _backup(run, "PreHangarResizeS4", [os.path.join(HERE, TARGETS_NAME)])
    live0, _r, _b, _rt, _root = gather(run, targets)
    rec = {"tool": TOOL, "run": run, "written": datetime.datetime.now().isoformat(timespec="seconds"), "applied": False,
           "approved_by": args.get("approved_by"), "backup": backup, "backup_files": brows, "root": plan["root"],
           "plan_sha256": plan["plan_sha256"], "actor_plan": ap, "key_plan": kp, "targets": targets,
           "all_before": {lab: row["rel"] for lab, row in live0["pieces"].items()},
           "stale_references": ["s4_rekey_window_record.json after.lattice_fly_z (2800/1200): never REVERT it while this "
                                "resize is applied", "hangar_s4_plan.json (30 Sep): history",
                                "hangar_exit_doors_record.json S4 pieces (half_w 1000): its all-scene REVERT would "
                                "restore the old far wall - never run it while applied"]}
    _write_exclusive(record_path, rec)
    try:
        _set_pieces(by_label, rt, ap["writes"], "rel_after", "scale_after")
        _set_fixed(by_label, ap["world_fixed"], "scale_after")
        write_key_values(ch, kp["keys_after"], kp["default_after"])
    except Exception as e:  # noqa: BLE001 - surface as STOPPED with the backup named
        stop(run, "WRITE_FAILED|%s|NOTHING saved; Don't-Save restart; backup %s" % (e, backup))
    scales = {w["label"]: w["scale_after"] for w in ap["writes"]}
    fixed = {f["label"]: f["scale_after"] for f in ap["world_fixed"]}
    _verify(run, targets, ap["all_after"], scales, fixed, kp["keys_after"], kp["default_after"], tol, "PRESAVE")
    _save(run)
    _verify(run, targets, ap["all_after"], scales, fixed, kp["keys_after"], kp["default_after"], tol, "POSTSAVE")
    c = census()
    if c["dirty_maps"] or c["dirty_content"]:
        stop(run, "CENSUS_AFTER|%s (saved)" % json.dumps(c))
    rec["applied"] = True
    rec["applied_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    _rewrite(record_path, rec)
    unreal.log("%s_APPLY_OK|run=%s|writes=%d|fixed=%d|keys=%s|backup=%s|census=0+0|next=klara_reveal S4 DRY"
               % (MARK, run, len(ap["writes"]), len(ap["world_fixed"]), kp["keys_after"], backup))


if unreal is not None and globals().get("HANGARRESIZES4_ARGS") is not None:
    main()
