"""S3 CROWD REGATHER (Gary 8 Oct ~20:00: "I'm going to move the fire spots to better spots, so you can regather the
clusters").  Reads the fires LIVE (where Gary left them) and huddles each copy cluster around its fire:
  cluster B (S3 Crowd 01-07) -> 'S3 Fire B';  cluster C (S3 Crowd 08-15) -> 'S3 Fire C'.
  Cluster A = the 5 Shore heroes (keyed in LS_Clams): NOT moved.
Placement: an arc of ARC_DEG around the fire, leaving the gap facing the hangar mouth (-x, the camera side) so the
fire reads through the group; radius R_BY_N; small deterministic jitter (radius +-JIT_R, angle +-JIT_A); each figure
faces the fire (actor +X = body forward [inf: Body rel yaw -90 on every figure, pie_crowd_pelvis]).  Z = floor under the
new spot by a downward trace that ignores every figure and fire (fallback: current z).
Also: each 'S3 Fire X Light' snaps to its emitter's x/y (z kept).
Copies carry no ABSOLUTE transform section since S3CROWDBODY-20261008-1, so level transforms hold (additive sway stays).
Map-only save; record s3_crowd_regather_record.json + Backups/PreS3Regather-<run>.  Args s3_crowd_regather_args.json
{"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3REGATHER", "run"}.  S3REGATHER_<MODE>_OK / _FAILED."""
import json, math, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_crowd_regather_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
CLUSTERS = {"S3 Fire B": ["S3 Crowd %02d" % i for i in range(1, 8)], "S3 Fire C": ["S3 Crowd %02d" % i for i in range(8, 16)]}
ARC_DEG = 290.0
R_BY_N = {7: 135.0, 8: 150.0}
JIT_R, JIT_A = 12.0, 6.0
WALLS_Y = (159001.0, 160999.0)          # marble inner faces [meas grease placement]


def _jit(i, k):
    return math.sin(i * 12.9898 + k * 78.233) * 0.5 + math.sin(i * 4.1414 + k * 1.618) * 0.5


def main():
    import unreal
    a = json.load(open(HERE + "s3_crowd_regather_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    w = ed.get_editor_world()
    all_acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_prefix = {}
    for x in all_acts:
        l = str(x.get_actor_label())
        by_prefix.setdefault(l[:12], []).append(x)                         # 'S3 Crowd 01' -> 'S3 Crowd 01 (from ...)'
    acts = {str(x.get_actor_label()): x for x in all_acts}
    ignore = [x for x in all_acts if str(x.get_actor_label()).startswith(("S3 Crowd", "Shore0", "S3 Fire", "S3 Ghost"))]
    plan = {"figures": [], "lights": []}
    for fire, members in CLUSTERS.items():
        f = acts.get(fire)
        if f is None: raise RuntimeError("NO_FIRE|" + fire)
        fl = f.get_actor_location()
        n = len(members); r0 = R_BY_N[n]
        start = 180.0 + (360.0 - ARC_DEG) / 2.0                            # gap centred on -x (angle 180)
        for i, m in enumerate(members):
            hits = [x for x in all_acts if str(x.get_actor_label()).startswith(m + " (")]
            if len(hits) != 1: raise RuntimeError("MEMBER|%s|%d" % (m, len(hits)))
            x = hits[0]
            ang = math.radians(start + ARC_DEG * (i + 0.5) / n + JIT_A * _jit(i, 1))
            r = r0 + JIT_R * _jit(i, 2)
            px, py = fl.x + r * math.cos(ang), fl.y + r * math.sin(ang)
            py = min(max(py, WALLS_Y[0] + 60.0), WALLS_Y[1] - 60.0)
            cur = x.get_actor_location()
            hit = unreal.SystemLibrary.line_trace_single(w, unreal.Vector(px, py, cur.z + 400.0), unreal.Vector(px, py, cur.z - 600.0),
                                                         unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore,
                                                         unreal.DrawDebugTrace.NONE, True)
            tup = hit.to_tuple() if hit else None
            pz = float(tup[4].z) if tup and tup[0] else cur.z
            yaw = math.degrees(math.atan2(fl.y - py, fl.x - px))
            plan["figures"].append({"label": str(x.get_actor_label()), "fire": fire, "old": [cur.x, cur.y, cur.z, x.get_actor_rotation().yaw],
                                    "new": [round(px, 1), round(py, 1), round(pz, 1), round(yaw, 2)], "floor_hit": bool(tup and tup[0])})
    for fire in ("S3 Fire A", "S3 Fire B", "S3 Fire C"):
        f, l = acts.get(fire), acts.get(fire + " Light")
        if f is None or l is None: raise RuntimeError("NO_FIRE_LIGHT|" + fire)
        fl, ll = f.get_actor_location(), l.get_actor_location()
        plan["lights"].append({"label": fire + " Light", "old": [ll.x, ll.y, ll.z], "new": [round(fl.x, 1), round(fl.y, 1), ll.z]})
    if mode == "DRY":
        json.dump(plan, open(HERE + "s3_crowd_regather_dry.json", "w"), indent=1)
        unreal.log("S3REGATHER_DRY_OK|run=%s|figures=%d|no_floor=%s|fires=%s" % (run, len(plan["figures"]),
                   [p["label"][:12] for p in plan["figures"] if not p["floor_hit"]],
                   {k: [round(acts[k].get_actor_location().x), round(acts[k].get_actor_location().y)] for k in ("S3 Fire A", "S3 Fire B", "S3 Fire C")}))
        return
    if a.get("confirm") != "%s S3REGATHER" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3Regather-%s" % run
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        os.makedirs(bd); shutil.copy2(UMAP, bd)
        json.dump({"run": run, "backup": bd, "plan": plan}, open(REC, "w"), indent=1)
        moves = [(p["label"], p["new"]) for p in plan["figures"]] + [(p["label"], p["new"] + [None]) for p in plan["lights"]]
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        old = json.load(open(REC))["plan"]
        os.makedirs(bd); shutil.copy2(UMAP, bd)
        moves = [(p["label"], p["old"]) for p in old["figures"]] + [(p["label"], p["old"] + [None]) for p in old["lights"]]
    else:
        raise RuntimeError("MODE")
    for lab, v in moves:
        x = acts[lab]; x.modify()
        rot = x.get_actor_rotation() if v[3] is None else unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(v[3]))
        x.set_actor_location_and_rotation(unreal.Vector(v[0], v[1], v[2]), rot, False, True)
    bad = [lab for lab, v in moves if math.hypot(acts[lab].get_actor_location().x - v[0], acts[lab].get_actor_location().y - v[1]) > 1.0]
    if bad: raise RuntimeError("READBACK_BEFORE_SAVE|%s|NOTHING SAVED; Don't-Save restart" % bad)
    if census() != ([], [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3REGATHER_%s_OK|run=%s|moved=%d|backup=%s" % (mode, run, len(moves), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3REGATHER_FAILED|%r" % (exc,))
