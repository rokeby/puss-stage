"""S1 entry snap probe: per-frame camera log across the Passage 1 -> Scene 1 crossing (HUD Cue 2 -> Cue 3).

READ-ONLY, PIE-ONLY. It never saves a package, never writes the editor world, never ends PIE and never quits the
editor. The only state it touches is PIE runtime state: in phase "arm" it pauses the Show Root transport, scrubs
it to (P01 end - pre_s) and plays forward through boundaries, exactly as an operator would; and it sets the runtime cvar
InfinityStage.SeamDiag (restored by phase "stop" or when the window closes). Everything it learns goes to a JSONL
file under Saved/CodexConductor/S1Snap/ and to log markers carrying run=<id>.

Args: Saved/CodexConductor/S1Snap/s1_entry_snap_probe_args.json
  {"run": "<id>", "phase": "arm" | "watch" | "stop" | "report",
   "pre_s": 2.0, "post_s": 5.0, "seam_diag": true, "max_ticks": 3000, "max_wall_s": 90}
  arm    pause -> scrub to P01 end - pre_s -> play_forward_through_boundaries, then log every tick until S1 start + post_s.
  watch  no transport action: log every tick whose Master time falls in the window (the operator plays across
         the crossing himself, e.g. from the Opening, the way Gary did).
  stop   unregister the tick logger, restore the cvar, write the report.
  report analyse an existing JSONL (also runnable offline: python s1_entry_snap_probe.py --analyze <jsonl>).

Markers: S1SNAP_ARMED|run=..  S1SNAP_ROW_COUNT|run=..  S1SNAP_VERDICT|run=..|...  S1SNAP_OK|run=..|path=..
         S1SNAP_FAILED|run=..|reason=..
S1SNAP_OK is printed only after the report asserted rows on BOTH sides of the boundary.

Facts it relies on (see Docs/Conductor/S1_ENTRY_SNAP_2026-10-07.md for tiers):
- HUD "Cue N" = transport segment index + 1 (InfinityStageDirectorHud.cpp:209-210, 376-377).
- get_sequence_player is absent in UE 5.8 Python; the transport and root.sequence_player are used instead
  (precedent pie_exposure_bench.py). EditorAssetLibrary returns None in PIE, so nothing here loads assets.
- No UObject wrapper is kept in module globals between ticks (an editor-crash class, memory note); state holds
  plain values and PIE object PATHS only, re-resolved with unreal.find_object each tick.
"""
import json
import math
import os
import sys
import time

HERE = "E:/PussStage/Saved/CodexConductor/S1Snap"
ARGS = HERE + "/s1_entry_snap_probe_args.json"
STATE_KEY = "_S1SNAP_PROBE_STATE"          # lives on builtins: plain values + the tick handle only

# Scene 1 cut layout read from LS_DevScene_01.uasset bytes on 7 Oct 19:08 (sha256 47586ab4a63e...), scene frames at
# 25 fps (960 ticks). Root cuts: Entry [0,119) Glide [119,6151) Exit [6151,6176). Nested shot section (her copy
# LS_Animals_1_S1Hangar, which carries its own cut track) [594,5769): inside it a nested cut outranks the root.
ROOT_CUTS = [("Entry", 0, 119, "Entry Handoff Camera"),
             ("Glide", 119, 6151, "Reveal Glide Camera"),
             ("Exit", 6151, 6176, "Exit Handoff Camera")]
NESTED_SLOT = (594, 5769)


def _log(msg):
    import unreal
    unreal.log(msg)


def _err(msg):
    import unreal
    unreal.log_error(msg)


def _state():
    import builtins
    return getattr(builtins, STATE_KEY, None)


def _set_state(st):
    import builtins
    setattr(builtins, STATE_KEY, st)


def _vec(v):
    return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]


def _rot(r):
    return [round(float(r.roll), 4), round(float(r.pitch), 4), round(float(r.yaw), 4)]   # roll, pitch, yaw


def _ang_deg(a, b):
    """Angle between two (roll, pitch, yaw) rotations in degrees, via forward and up vectors (no quat API needed)."""
    def basis(r):
        roll, pitch, yaw = [math.radians(x) for x in r]
        cp, sp, cy, sy, cr, sr = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw), math.cos(roll), math.sin(roll)
        fwd = (cp * cy, cp * sy, sp)
        up = (-cr * sp * cy - sr * sy, -cr * sp * sy + sr * cy, cr * cp)
        return fwd, up

    def ang(u, v):
        d = max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v))))
        return math.degrees(math.acos(d))
    fa, ua = basis(a)
    fb, ub = basis(b)
    return max(ang(fa, fb), ang(ua, ub))


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _world():
    import unreal
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def _root(world):
    import unreal
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    return roots[0] if len(roots) == 1 else None


def _segments(root):
    out = []
    for i, s in enumerate(list(root.transport.segments)):
        out.append({"i": i, "label": str(s.label), "type": str(s.type),
                    "start": int(s.start_frame.value), "end": int(s.end_frame.value)})
    return out


def _find_paths(world):
    """PIE object paths (strings) of the actors we watch; resolved once at arm/watch time."""
    import unreal
    paths = {}
    for cam in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CineCameraActor):
        lab = str(cam.get_actor_label())
        if lab.startswith("Scene 1 ") and "Entry Handoff Camera" in lab:
            paths["entry"] = cam.get_path_name()
        elif lab.startswith("Scene 1 ") and "Exit Handoff Camera" in lab:
            paths["exit"] = cam.get_path_name()
        elif "S1 Reveal Glide Camera" in lab:
            paths["glide"] = cam.get_path_name()
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor):
        if str(a.get_actor_label()) == "S1 Hangar Root":
            paths["hangar_root"] = a.get_path_name()
            break
    return paths


def _cam_row(actor):
    import unreal
    row = {"actor": actor.get_name(), "label": str(actor.get_actor_label()), "cls": actor.get_class().get_name(),
           "actor_loc": _vec(actor.get_actor_location()), "actor_rot": _rot(actor.get_actor_rotation())}
    comp = actor.get_component_by_class(unreal.CineCameraComponent)
    if comp is not None:
        fb = comp.get_editor_property("filmback")
        fs = comp.get_editor_property("focus_settings")
        row.update({
            "comp_loc": _vec(comp.get_world_location()), "comp_rot": _rot(comp.get_world_rotation()),
            "comp_rel_loc": _vec(comp.get_editor_property("relative_location")),
            "comp_rel_rot": _rot(comp.get_editor_property("relative_rotation")),
            "focal": round(float(comp.get_editor_property("current_focal_length")), 4),
            "aperture": round(float(comp.get_editor_property("current_aperture")), 4),
            "sensor": [round(float(fb.get_editor_property("sensor_width")), 4),
                       round(float(fb.get_editor_property("sensor_height")), 4)],
            "focus_cm": round(float(fs.get_editor_property("manual_focus_distance")), 3),
            "fov": round(float(comp.get_editor_property("field_of_view")), 4),
            "constrain_aspect": bool(comp.get_editor_property("constrain_aspect_ratio")),
            "pp_weight": round(float(comp.get_editor_property("post_process_blend_weight")), 4),
        })
        row["cam_vs_actor_deg"] = round(_ang_deg(row["comp_rot"], row["actor_rot"]), 4)
    if isinstance(actor, unreal.InfinityStageCameraRig):
        for k in ("current_crossing_settle_weight", "current_shadow_cat_camera_bob_cm",
                  "current_shadow_cat_bob_walk_weight", "current_shadow_cat_camera_speed_cm_per_second"):
            try:
                row[k] = round(float(actor.get_editor_property(k)), 4)
            except Exception as exc:                      # a renamed property must not kill the logger
                row[k] = "ERR %r" % (exc,)
    return row


def _expected(st, master):
    if master < st["s1_start"]:
        return "P01 rig" if master >= st["p01_start"] else "before P01"
    sf = (master - st["s1_start"]) / float(st["tpf"])
    for name, a, b, _ in ROOT_CUTS:
        if a <= sf < b:
            nested = NESTED_SLOT[0] <= sf < NESTED_SLOT[1]
            return name + (" (nested slot: her cut may outrank)" if nested else "")
    return "past S1 cuts"


def _tick(delta):
    st = _state()
    if not st or not st.get("active"):
        return
    try:
        _tick_body(st, float(delta))
    except Exception as exc:
        st["errors"] = st.get("errors", 0) + 1
        if st["errors"] <= 3:
            _err("S1SNAP_TICK_ERROR|run=%s|%r" % (st["run"], exc))
        if st["errors"] >= 20:
            _finish(st, "TICK_ERRORS")


def _tick_body(st, delta):
    import unreal
    world = _world()
    if world is None:
        _finish(st, "PIE_GONE")                          # we never end PIE; the operator did
        return
    st["ticks"] += 1
    if st["ticks"] > st["max_ticks"] or time.time() - st["t0"] > st["max_wall_s"]:
        _finish(st, "LIMIT")
        return
    root = _root(world)
    if root is None:
        return
    tr = root.transport
    master = int(tr.get_current_master_frame().value)
    if master < st["win_lo"] or master > st["win_hi"]:
        if st["rows"] and master > st["win_hi"]:
            _finish(st, "WINDOW_DONE")
        return
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    vt = pc.get_view_target() if pc else None
    pcm = pc.get_editor_property("player_camera_manager") if pc else None
    row = {"run": st["run"], "tick": st["ticks"], "dt": round(delta, 5), "wall": round(time.time() - st["t0"], 4),
           "world_s": round(float(unreal.GameplayStatics.get_time_seconds(world)), 4),
           "master": master, "master_s": round(master / st["tick_rate"], 4),
           "to_boundary_s": round((master - st["s1_start"]) / st["tick_rate"], 4),
           "scene_frame": round((master - st["s1_start"]) / float(st["tpf"]), 3),
           "seg": int(tr.find_segment_at_frame(unreal.FrameNumber(master))),
           "playing": bool(tr.is_transport_playing()),
           "held_end": int(tr.get_held_at_end_segment_index()),
           "expected_owner": _expected(st, master)}
    try:
        lh = tr.get_editor_property("last_handover")
        row["last_handover"] = {"seg": int(lh.segment_index), "frame": int(lh.frame.value),
                                "source": str(lh.source), "resolution": str(lh.resolution)}
    except Exception as exc:
        row["last_handover"] = "ERR %r" % (exc,)
    try:
        sp = root.sequence_player
        row["player_frame"] = int(sp.get_current_time().time.frame_number.value) if sp else None
    except Exception as exc:
        row["player_frame"] = "ERR %r" % (exc,)
    if pcm is not None:
        row["pov_loc"] = _vec(pcm.get_camera_location())
        row["pov_rot"] = _rot(pcm.get_camera_rotation())
        row["pov_fov"] = round(float(pcm.get_fov_angle()), 4)
    if vt is not None:
        row["vt"] = _cam_row(vt)
    for key in ("entry", "glide", "hangar_root"):
        p = st["paths"].get(key)
        obj = unreal.find_object(None, p) if p else None
        if obj is None:
            continue
        if key == "hangar_root":
            row["hangar_root_rot"] = _rot(obj.get_actor_rotation())
            row["hangar_root_loc"] = _vec(obj.get_actor_location())
        elif key == "entry" or (vt is not None and obj.get_name() != vt.get_name()):
            row[key] = _cam_row(obj)
    prev = st.get("prev")
    if prev and "pov_loc" in row and "pov_loc" in prev:
        row["step_cm"] = round(_dist(row["pov_loc"], prev["pov_loc"]), 3)
        row["step_deg"] = round(_ang_deg(row["pov_rot"], prev["pov_rot"]), 4)
        row["step_fov"] = round(row["pov_fov"] - prev["pov_fov"], 4)
        row["step_master"] = master - prev["master"]
    st["prev"] = {k: row[k] for k in ("pov_loc", "pov_rot", "pov_fov", "master") if k in row}
    with open(st["path"], "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    st["rows"] += 1


def _restore_cvars(st):
    import unreal
    if st.get("seam_diag_set"):
        world = _world()
        if world is not None:
            unreal.SystemLibrary.execute_console_command(world, "InfinityStage.SeamDiag 0")
            unreal.SystemLibrary.execute_console_command(world, "InfinityStage.SeamDiag.WindowSeconds 1.0")
        st["seam_diag_set"] = False


def _finish(st, why):
    import unreal
    st["active"] = False
    try:
        if st.get("handle") is not None:
            unreal.unregister_slate_post_tick_callback(st["handle"])
    finally:
        st["handle"] = None
    _restore_cvars(st)
    _log("S1SNAP_ROW_COUNT|run=%s|rows=%d|ticks=%d|why=%s|path=%s" % (st["run"], st["rows"], st["ticks"], why, st["path"]))
    report(st["path"], st["run"], st.get("s1_index", 2))


def _start(a, phase):
    import unreal
    run = a["run"]
    old = _state()
    if old and old.get("active"):
        _err("S1SNAP_FAILED|run=%s|reason=ALREADY_ACTIVE|other=%s (run phase stop first)" % (run, old["run"]))
        return
    world = _world()
    if world is None:
        _err("S1SNAP_FAILED|run=%s|reason=NO_PIE (start PIE first; this probe never starts or ends it)" % run)
        return
    root = _root(world)
    if root is None:
        _err("S1SNAP_FAILED|run=%s|reason=SHOW_ROOT_COUNT" % run)
        return
    segs = _segments(root)
    p01 = [s for s in segs if s["label"] == "Passage 1"]
    s1 = [s for s in segs if s["label"].startswith("Scene 1")]
    if len(p01) != 1 or len(s1) != 1 or s1[0]["i"] != p01[0]["i"] + 1:
        _err("S1SNAP_FAILED|run=%s|reason=SEGMENTS|p01=%s|s1=%s" % (run, p01, s1))
        return
    p01, s1 = p01[0], s1[0]
    tick_rate = 24000.0
    tpf = 960
    gap = s1["start"] - p01["end"]
    st = {"run": run, "active": False, "ticks": 0, "rows": 0, "errors": 0, "t0": time.time(),
          "max_ticks": int(a.get("max_ticks", 3000 if phase == "arm" else 200000)),
          "max_wall_s": float(a.get("max_wall_s", 90 if phase == "arm" else 900)),
          "tick_rate": tick_rate, "tpf": tpf, "p01_start": p01["start"], "s1_start": s1["start"],
          "s1_index": s1["i"],
          "win_lo": p01["end"] - int(round(float(a.get("pre_s", 2.0)) * tick_rate)),
          "win_hi": s1["start"] + int(round(float(a.get("post_s", 5.0)) * tick_rate)),
          "path": "%s/probe_%s.jsonl" % (HERE, run), "paths": _find_paths(world), "handle": None}
    if os.path.exists(st["path"]):
        _err("S1SNAP_FAILED|run=%s|reason=RUN_ID_REUSED|path=%s" % (run, st["path"]))
        return
    with open(st["path"], "w", encoding="utf-8") as f:
        f.write(json.dumps({"header": True, "run": run, "phase": phase, "segments": segs[:4], "p01": p01, "s1": s1,
                            "p01_end_vs_s1_start_ticks": gap, "paths": st["paths"], "root_cuts": ROOT_CUTS,
                            "nested_slot": NESTED_SLOT, "window": [st["win_lo"], st["win_hi"]]}) + "\n")
    if a.get("seam_diag", True):
        unreal.SystemLibrary.execute_console_command(world, "InfinityStage.SeamDiag 1")
        unreal.SystemLibrary.execute_console_command(
            world, "InfinityStage.SeamDiag.WindowSeconds %.1f" % max(float(a.get("pre_s", 2.0)), float(a.get("post_s", 5.0))))
        st["seam_diag_set"] = True
    if phase == "arm":
        tr = root.transport
        if root.sequence_player:
            root.sequence_player.pause()
        res = tr.scrub_to_master_frame(unreal.FrameNumber(st["win_lo"]))
        if res != unreal.InfinityTransportResult.SUCCEEDED:
            _restore_cvars(st)
            _err("S1SNAP_FAILED|run=%s|reason=SCRUB|result=%s|target=%d" % (run, res, st["win_lo"]))
            return
        got = int(tr.get_current_master_frame().value)
        if got != st["win_lo"]:
            _restore_cvars(st)
            _err("S1SNAP_FAILED|run=%s|reason=SCRUB_READBACK|want=%d|got=%d" % (run, st["win_lo"], got))
            return
    st["active"] = True
    _set_state(st)
    st["handle"] = unreal.register_slate_post_tick_callback(_tick)
    if phase == "arm":
        res = root.transport.play_forward_through_boundaries()   # precedent scene1_tail_view_pie.py:104
        if res != unreal.InfinityTransportResult.SUCCEEDED:
            _finish(st, "RESUME_REFUSED %s" % res)
            _err("S1SNAP_FAILED|run=%s|reason=RESUME|result=%s" % (run, res))
            return
    _log("S1SNAP_ARMED|run=%s|phase=%s|window=[%d,%d]|p01_end=%d|s1_start=%d|gap_ticks=%d|paths=%s|path=%s"
         % (run, phase, st["win_lo"], st["win_hi"], p01["end"], s1["start"], gap, json.dumps(st["paths"]), st["path"]))


def report(path, run, s1_index=2):
    """Pure analysis of a probe JSONL. Prints S1SNAP_VERDICT and, only if the crossing was captured, S1SNAP_OK."""
    emit = _log if "unreal" in sys.modules else print
    rows, header = [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("header"):
                header = r
            else:
                rows.append(r)
    before = [r for r in rows if r["seg"] < s1_index]
    after = [r for r in rows if r["seg"] >= s1_index]
    if not before or not after:
        msg = "S1SNAP_FAILED|run=%s|reason=CROSSING_NOT_CAPTURED|rows_before=%d|rows_after=%d" % (run, len(before), len(after))
        (_err if "unreal" in sys.modules else print)(msg)
        return None
    last, first = before[-1], after[0]
    out = {"run": run, "rows": len(rows), "gap_ticks": header and header.get("p01_end_vs_s1_start_ticks")}
    out["crossing"] = {
        "last_p01": {"master": last["master"], "vt": last.get("vt", {}).get("label"), "pov": last.get("pov_loc"),
                     "rot": last.get("pov_rot"), "fov": last.get("pov_fov"),
                     "look_deg": last.get("vt", {}).get("cam_vs_actor_deg"),
                     "settle": last.get("vt", {}).get("current_crossing_settle_weight"),
                     "bob_cm": last.get("vt", {}).get("current_shadow_cat_camera_bob_cm"),
                     "focal": last.get("vt", {}).get("focal"), "aperture": last.get("vt", {}).get("aperture"),
                     "sensor": last.get("vt", {}).get("sensor"), "pp_weight": last.get("vt", {}).get("pp_weight")},
        "first_s1": {"master": first["master"], "vt": first.get("vt", {}).get("label"), "pov": first.get("pov_loc"),
                     "rot": first.get("pov_rot"), "fov": first.get("pov_fov"),
                     "focal": first.get("vt", {}).get("focal"), "aperture": first.get("vt", {}).get("aperture"),
                     "sensor": first.get("vt", {}).get("sensor"), "pp_weight": first.get("vt", {}).get("pp_weight"),
                     "expected": first.get("expected_owner")},
    }
    if last.get("pov_loc") and first.get("pov_loc"):
        out["crossing"]["delta_cm"] = round(_dist(last["pov_loc"], first["pov_loc"]), 3)
        out["crossing"]["delta_deg"] = round(_ang_deg(last["pov_rot"], first["pov_rot"]), 4)
        out["crossing"]["delta_fov"] = round(first["pov_fov"] - last["pov_fov"], 4)
    # the walk's own per-tick motion just before the crossing, as the yardstick for "a step"
    walk = [r.get("step_cm", 0.0) for r in before[-6:-1] if "step_cm" in r]
    out["crossing"]["walk_step_cm_before"] = round(max(walk), 3) if walk else None
    steps = sorted((r for r in rows if "step_cm" in r), key=lambda r: -(r["step_cm"] + 10.0 * r["step_deg"]))[:5]
    out["largest_steps"] = [{"master": r["master"], "scene_frame": r["scene_frame"], "step_cm": r["step_cm"],
                             "step_deg": r["step_deg"], "step_fov": r["step_fov"], "vt": r.get("vt", {}).get("label")}
                            for r in steps]
    vts, changes = None, []
    for r in rows:
        lab = r.get("vt", {}).get("label")
        if lab != vts:
            changes.append({"master": r["master"], "scene_frame": r["scene_frame"], "vt": lab,
                            "expected": r.get("expected_owner")})
            vts = lab
    out["view_target_changes"] = changes
    stalls = [{"master": r["master"], "dt": r["dt"]} for r in rows
              if r.get("playing") and (r.get("step_master") == 0 or r["dt"] >= 0.25)]
    out["stalls"] = stalls[:10]
    g0 = [r for r in rows if r["seg"] >= s1_index and 118.0 <= r["scene_frame"] <= 120.5]
    out["glide_cut_rows"] = [{"scene_frame": r["scene_frame"], "vt": r.get("vt", {}).get("label"),
                              "step_cm": r.get("step_cm"), "step_deg": r.get("step_deg"), "step_fov": r.get("step_fov")}
                             for r in g0]
    c = out["crossing"]
    flags = []
    if c.get("delta_cm") is not None:
        yard = (c["walk_step_cm_before"] or 0.0) + 1.0
        if c["delta_cm"] > yard:
            flags.append("CROSSING_POSE_STEP")
        if c["delta_deg"] > 0.2:
            flags.append("CROSSING_TURN_STEP")
        if abs(c["delta_fov"]) > 0.1:
            flags.append("CROSSING_FOV_STEP")
    if (c["last_p01"].get("look_deg") or 0.0) > 0.2:
        flags.append("LOOK_OFFSET_DROPPED_AT_CUT")
    if c["last_p01"].get("aperture") != c["first_s1"].get("aperture") or \
            c["last_p01"].get("pp_weight") != c["first_s1"].get("pp_weight"):
        flags.append("LENS_OR_PP_DIFFERS")
    keyword = {name: kw for name, _, _, kw in ROOT_CUTS}
    mism = [r for r in after
            if "nested" not in str(r.get("expected_owner"))
            and str(r.get("expected_owner")) in keyword
            and keyword[str(r.get("expected_owner"))] not in str(r.get("vt", {}).get("label"))]
    out["owner_mismatch_rows"] = [{"scene_frame": r["scene_frame"], "vt": r.get("vt", {}).get("label"),
                                   "expected": r.get("expected_owner")} for r in mism[:10]]
    if mism:
        flags.append("CUT_OWNER_MISMATCH")
    if stalls:
        flags.append("STALL")
    if any((r.get("step_cm") or 0) > 1.0 or (r.get("step_deg") or 0) > 0.2 for r in g0):
        flags.append("GLIDE_CUT_STEP")
    out["flags"] = flags or ["NO_STEP_FOUND"]
    rep = path.replace(".jsonl", "_report.json")
    with open(rep, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    emit("S1SNAP_VERDICT|run=%s|flags=%s|delta_cm=%s|delta_deg=%s|delta_fov=%s|look_deg=%s|vt=%s->%s|report=%s"
         % (run, ",".join(out["flags"]), c.get("delta_cm"), c.get("delta_deg"), c.get("delta_fov"),
            c["last_p01"].get("look_deg"), c["last_p01"].get("vt"), c["first_s1"].get("vt"), rep))
    emit("S1SNAP_OK|run=%s|rows=%d|path=%s" % (run, len(rows), path))
    return out


def main():
    a = json.load(open(ARGS, encoding="utf-8"))
    run, phase = a.get("run"), a.get("phase")
    if not run or phase not in ("arm", "watch", "stop", "report"):
        _err("S1SNAP_FAILED|run=%s|reason=ARGS (run + phase arm|watch|stop|report)" % run)
        return
    if phase in ("arm", "watch"):
        _start(a, phase)
    elif phase == "stop":
        st = _state()
        if not st:
            _err("S1SNAP_FAILED|run=%s|reason=NOTHING_ACTIVE" % run)
            return
        if st.get("active"):
            _finish(st, "STOP")
        else:
            _log("S1SNAP_ROW_COUNT|run=%s|rows=%d|already_finished=1|path=%s" % (st["run"], st["rows"], st["path"]))
    else:
        report("%s/probe_%s.jsonl" % (HERE, run), run)


if __name__ == "__main__" and len(sys.argv) >= 3 and sys.argv[1] == "--analyze":
    report(sys.argv[2], os.path.basename(sys.argv[2]).replace("probe_", "").replace(".jsonl", ""))
else:
    try:
        main()
    except Exception as exc:
        import unreal
        unreal.log_error("S1SNAP_FAILED|reason=EXC|%r" % (exc,))
