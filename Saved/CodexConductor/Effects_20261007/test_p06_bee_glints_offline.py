"""Offline harness for p06_bee_glints.py (system Python, no Unreal). Every property has a + case and a - control that
must fail or refuse; then SEEDED MUTATIONS of the tool's source must each be killed by at least one check.
Fixture: P06 as measured - segment [47949592, 50973621) ticks at 24000/s (p06_tail_extend_record.json), straight route
x 0 -> 27640.28 at y 400000, camera z 180, ~250 cm/s then a 17 s tail of 390.28 cm
(passage_speed_probe_PSPEED-20261006-223036.json). The camera model is a fixture, not a measurement of the live rig.
Run: python Saved/CodexConductor/Effects_20261007/test_p06_bee_glints_offline.py"""
import ast
import copy
import importlib.util
import json
import math
import pathlib
import sys
import tempfile
from fractions import Fraction

HERE = pathlib.Path(__file__).resolve().parent
TOOL_PATH = HERE / "p06_bee_glints.py"
ARGS_PATH = HERE / "p06_bee_glints_args.json"

TICK, FPS = 24000, 25
SEG = {"start": 47949592, "end": 50973621}
ROUTE_L = 27640.28
TAIL_START = (ROUTE_L - 390.28) / 250.0          # 109.0 s
LEN_S = (SEG["end"] - SEG["start"]) / TICK
FORBIDDEN_ATTRS = {"save_all", "save_dirty_packages", "save_map", "load_map", "load_level", "request_end_play_map",
                   "end_play", "open_level_sequence", "set_current_time", "set_global_time", "get_bound_objects",
                   "evaluate_at_master_frame", "play_to", "set_playback_position"}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cam_x(t):
    if t <= TAIL_START:
        return 250.0 * t
    u = min(1.0, (t - TAIL_START) / (LEN_S - TAIL_START))
    return 250.0 * TAIL_START + 390.28 * (1.0 - (1.0 - u) ** 2)


def make_view(z=180.0, y=400000.0, yaw=0.0, pitch=0.0, focal=35.0):
    def view(abs_ticks):
        t = (abs_ticks - SEG["start"]) / float(TICK)
        return {"loc": [cam_x(t), y, z], "rot": [0.0, pitch, yaw], "focal": focal}
    return view


def straight_route():
    n = int(math.ceil(ROUTE_L / 100.0)) + 1
    return [[ROUTE_L * i / (n - 1), 400000.0, 0.0] for i in range(n)]


def arc_route(radius=20000.0, n=400, span_deg=60.0):
    return [[radius * math.sin(math.radians(span_deg * i / (n - 1))),
             400000.0 + radius * (1 - math.cos(math.radians(span_deg * i / (n - 1)))), 0.0] for i in range(n)]


def base_args():
    return json.loads(ARGS_PATH.read_text(encoding="utf-8"))


def raises(fn, token=None):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        return token is None or token in str(exc)
    return False


def has(refusals, token):
    return any(token in r for r in refusals)


def suite(M):
    R = []

    def check(name, cond):
        R.append((name, bool(cond)))

    A = base_args()
    rates = {"tick": TICK, "fps": FPS}
    route = straight_route()

    # ---- A. shipped args
    check("A1 args validate clean", M.validate_args(A) == [])
    check("A2 shipped mode DRY, confirm empty, decided_by empty, ack empty",
          A["mode"] == "DRY" and A["confirm"] == "" and A["decided_by"] == "" and A["cueing_ack"] == "")
    check("A3 bursts at 80/100/118 s", [b["t_s"] for b in A["bursts"]] == [80.0, 100.0, 118.0])
    for bad, token in ((dict(A, mode="GO"), "MODE_INVALID"), (dict(A, attach="master_subtrack"), "ATTACH_REFUSED"),
                       (dict(A, attach="nope"), "ATTACH_INVALID"), (dict(A, system="NS_BeeSwarm"), "SYSTEM_NOT_GAME"),
                       (dict(A, glints_sequence=A["choreo"]), "GLINTS_PATH_IS_AN_EXISTING"),
                       (dict(A, basis="sky"), "BASIS_INVALID"), (dict(A, her_scale=[1, 2]), "HER_SCALE_INVALID")):
        check("A4- validate refuses %s" % token, has(M.validate_args(bad), token))
    b5 = copy.deepcopy(A)
    b5["bursts"][0]["life_s"] = 5.0
    check("A5- life 5 s refused (brief: 2-4 s)", has(M.validate_args(b5), "LIFE_OUTSIDE"))
    b6 = copy.deepcopy(A)
    b6["bursts"][2]["scale"] = 1.0
    check("A6- full-size swarm refused (smaller volumes)", has(M.validate_args(b6), "SCALE_NOT_SMALLER"))
    b7 = copy.deepcopy(A)
    del b7["limits"]["dark_from_s"]
    check("A7- a missing limit refused", has(M.validate_args(b7), "LIMIT_MISSING_DARK_FROM_S"))

    # ---- B. windows
    check("B1 shipped windows clean", M.burst_windows(A["bursts"], LEN_S, 52.1, 1.0) == [])
    check("B2- burst at 40 s is not in the dark",
          has(M.burst_windows([{"t_s": 40.0, "life_s": 3.0}], LEN_S, 52.1, 1.0), "NOT_IN_THE_DARK"))
    check("B3- burst ending past P06 refused",
          has(M.burst_windows([{"t_s": 123.5, "life_s": 2.0}], LEN_S, 52.1, 1.0), "PAST_PASSAGE_END"))
    check("B4- overlapping bursts refused",
          has(M.burst_windows([{"t_s": 80.0, "life_s": 3.0}, {"t_s": 82.0, "life_s": 2.0}], LEN_S, 52.1, 1.0),
              "OVERLAPS"))

    # ---- C. route maths
    poly = M.route_polyline(route)
    st, lat, rz = M.route_nearest(poly, [12345.6, 400050.0, 180.0])
    check("C1 nearest station exact on straight route", abs(st - 12345.6) < 1e-6 and abs(lat - 50.0) < 1e-6)
    p, yaw = M.route_point(poly, ROUTE_L + 2000.0)
    check("C2 extrapolates PAST the route end (no clamp)", abs(p[0] - (ROUTE_L + 2000.0)) < 1e-6 and abs(yaw) < 1e-9)
    check("C2- a clamp would sit 2000 cm short", abs(min(ROUTE_L + 2000.0, ROUTE_L) - p[0]) > 1999.0)
    arc = M.route_polyline(arc_route())
    pa, _ = M.route_point(arc, 5000.0)
    r_on = math.hypot(pa[0], pa[1] - 400000.0 - 20000.0)
    check("C3 route point lies on a curved route (radius 20000 +-2 cm)", abs(r_on - 20000.0) < 2.0)
    check("C4- degenerate route refused", raises(lambda: M.route_polyline([[0, 0, 0]]), "ROUTE_DEGENERATE"))

    # ---- D. end-to-end plan (choreo)
    plan = M.plan_glints(A, SEG, make_view(), route, rates, None, 140.56)
    check("D1 plan has no refusals", plan["refusals"] == [])
    b1 = plan["bursts"][0]
    check("D2 burst 1 sits 15 m ahead on the route at eye+60",
          max(abs(b1["pose"]["loc"][i] - [cam_x(80.0) + 1500.0, 400000.0, 240.0][i]) for i in range(3)) < 1e-6)
    check("D3 burst 1 long axis across the view (yaw 90) and 0.2 of her scale",
          abs(b1["pose"]["rot"][2] - 90.0) < 1e-9 and
          max(abs(b1["pose"]["scale"][i] - 0.2 * A["her_scale"][i]) for i in range(3)) < 1e-12)
    want_on = [int(round(t * FPS)) for t in (80.0, 100.0, 118.0)]
    check("D4 choreo frames are PASSAGE-RELATIVE display frames", [b["frames"][0] for b in plan["bursts"]] == want_on)
    check("D5 every burst has CHECK_SAMPLES visibility rows, all clear",
          all(len(b["checks"]) == M.CHECK_SAMPLES for b in plan["bursts"]))
    check("D6 choreo span = [0, P06 length in frames]", plan["span_frames"] == [0, int(round(LEN_S * FPS))])
    check("D7 frame rounding error <= half a frame", all(b["frame_err_s"] <= 0.5 / FPS + 1e-9 for b in plan["bursts"]))
    b3 = plan["bursts"][2]
    check("D8 the 118 s burst lands beyond the route end, still ahead (extrapolated)",
          b3["pose"]["loc"][0] > cam_x(118.0) + 1499.0)
    # master frames
    pm = M.plan_glints(dict(A, attach="master_bindings"), SEG, make_view(), route, rates)
    exact = [Fraction(SEG["start"] + int(round(t * TICK)), 1) * FPS / TICK for t in (80.0, 100.0, 118.0)]
    check("D9 master frames are ABSOLUTE display frames",
          [b["frames"][0] for b in pm["bursts"]] == [int(round(float(x))) for x in exact])
    check("D9- relative frames would be 49947 frames early", pm["bursts"][0]["frames"][0] - want_on[0] > 49000)
    check("D10 master span = P06's own range",
          pm["span_frames"] == [int(round(SEG["start"] * FPS / TICK)), int(round(SEG["end"] * FPS / TICK))])
    pc = M.plan_glints(dict(A, basis="camera"), SEG, make_view(), route, rates, None, 140.56)
    check("D11 camera basis == route basis on a straight route, yaw 0",
          all(max(abs(x - y) for x, y in zip(a["pose"]["loc"], b["pose"]["loc"])) < 1e-6
              for a, b in zip(pc["bursts"], plan["bursts"])))

    # ---- E. refusals from the plan
    short = M.plan_glints(A, {"start": SEG["start"], "end": SEG["start"] + int(110.56 * TICK)}, make_view(), route,
                          rates, None, 140.56)
    check("E1- a 110.56 s P06 (its 4 Oct length) refuses the 118 s burst", has(short["refusals"], "PAST_PASSAGE_END"))
    ch = M.plan_glints(A, SEG, make_view(), route, rates, None, 110.0)
    check("E2- a Choreo ending at 110 s refuses (CHOREO_SHORT)", has(ch["refusals"], "CHOREO_SHORT"))
    check("E2+ master_bindings ignores the Choreo length",
          not has(M.plan_glints(dict(A, attach="master_bindings"), SEG, make_view(), route, rates, None, 110.0)
                  ["refusals"], "CHOREO_SHORT"))
    sunk = M.plan_glints(A, SEG, make_view(z=-3320.0), route, rates, None, 140.56)
    check("E3- camera 35 m underground -> FRAME_TRAP", has(sunk["refusals"], "FRAME_TRAP"))
    off = M.plan_glints(A, SEG, make_view(y=401000.0), route, rates, None, 140.56)
    check("E4- camera 10 m off its route -> FRAME_TRAP", has(off["refusals"], "FRAME_TRAP"))
    near = copy.deepcopy(A)
    near["bursts"][0]["ahead_cm"] = 100.0
    check("E5- 1 m ahead: the camera runs into it -> TOO_CLOSE",
          has(M.plan_glints(near, SEG, make_view(), route, rates, None, 140.56)["refusals"], "BURST1_TOO_CLOSE"))
    wide = copy.deepcopy(A)
    wide["bursts"][1]["side_cm"] = 3000.0
    check("E6- 30 m to the side -> OUT_OF_FRAME",
          has(M.plan_glints(wide, SEG, make_view(), route, rates, None, 140.56)["refusals"], "BURST2_OUT_OF_FRAME"))
    back = M.plan_glints(A, SEG, make_view(yaw=180.0), route, rates, None, 140.56)
    check("E7- camera looking back -> OUT_OF_FRAME", has(back["refusals"], "OUT_OF_FRAME"))
    high = copy.deepcopy(A)
    high["bursts"][0]["up_cm"] = 400.0
    check("E8- 4 m above the eye leaves the frame as the camera closes",
          has(M.plan_glints(high, SEG, make_view(), route, rates, None, 140.56)["refusals"], "BURST1_OUT_OF_FRAME"))
    none = M.plan_glints(A, SEG, lambda f: None, route, rates, None, 140.56)
    check("E9- no camera view -> refused", has(none["refusals"], "NO_CAMERA_VIEW"))
    lw = M.plan_glints(dict(A, expected_length_s=110.0), SEG, make_view(), route, rates, None, 140.56)
    check("E10 a changed P06 length is warned", has(lw["warnings"], "P06_LENGTH_CHANGED"))

    # ---- F. gates
    clean = {"mode": "DRY", "census": {"content": [], "maps": []}}
    check("F1 clean DRY passes", M.live_gates(clean) == [])
    ap = {"mode": "APPLY", "confirm": "APPLY P06BEEGLINTS", "decided_by": "Gary", "attach": "choreo_subtrack",
          "cueing_ack": "cueing 7 Oct", "census": {"content": [], "maps": []}}
    check("F2 a full APPLY passes", M.live_gates(ap) == [])
    for patch, token in (({"confirm": "APPLY"}, "CONFIRM_MISMATCH"), ({"cueing_ack": ""}, "CUEING_ACK_MISSING"),
                         ({"decided_by": " "}, "NOT_DECIDED"), ({"pie": True}, "PIE_OR_SIE"),
                         ({"sequencer_open": "/Game/X"}, "SEQUENCER_OPEN"),
                         ({"census": {"content": ["/Game/A"], "maps": []}}, "DIRTY_CENSUS"),
                         ({"record_exists": "r.json"}, "RECORD_EXISTS"), ({"glints_exists": "/Game/G"}, "GLINTS_SEQUENCE"),
                         ({"wrong_world": "/Game/Other"}, "WRONG_WORLD")):
        check("F3- APPLY refuses %s" % token, has(M.live_gates(dict(ap, **patch)), token))
    check("F4 master_bindings APPLY needs no cueing ack",
          not has(M.live_gates(dict(ap, attach="master_bindings", cueing_ack="")), "CUEING_ACK"))
    check("F5- REVERT without an applied record refused",
          has(M.live_gates({"mode": "REVERT", "confirm": "REVERT P06BEEGLINTS", "census": {}}), "NO_APPLIED_RECORD"))
    check("F6 census gate + exact", M.census_gate({"content": ["/Game/B", "/Game/A"], "maps": []},
                                                  ["/Game/A", "/Game/B"], []) == [])
    check("F6- census gate catches an extra package",
          M.census_gate({"content": ["/Game/A", "/Game/C"], "maps": []}, ["/Game/A"], []) != [])
    check("F6- census gate catches a dirty map", M.census_gate({"content": [], "maps": ["/Game/M"]}, [], []) != [])

    # ---- G. drift (master_bindings does not travel)
    rec = {"applied": True, "plan": {"attach": "master_bindings", "segment": [SEG["start"], SEG["end"]]}}
    check("G1 same P06 start: no drift", M.drift_check(rec, {"start": SEG["start"] + 3})["drifted"] is False)
    check("G2- P06 moved (41532952, measured 6 Oct 22:30) -> drifted",
          M.drift_check(rec, {"start": 41532952})["drifted"] is True)
    check("G3 a choreo record never drifts (it travels)",
          M.drift_check({"applied": True, "plan": {"attach": "choreo_subtrack", "segment": [0, 1]}}, {"start": 9}) is None)

    # ---- H. expected state and read-back compare
    want = M.expected_state(plan, A)
    check("H1 choreo expected state carries the sub-track over the span",
          want["subtrack"] == {"name": M.SUBTRACK_NAME, "sequence": A["glints_sequence"], "range": plan["span_frames"]})
    check("H2 master expected state has no sub-track", "subtrack" not in M.expected_state(pm, A))
    check("H3 spawn keys ON then OFF", all(r["spawn_keys"][0][1] is True and r["spawn_keys"][1][1] is False
                                           and r["spawn_keys"][1][0] > r["spawn_keys"][0][0] for r in want["glints"]))
    got = copy.deepcopy(want)
    check("H4 _close accepts an identical read-back", M._close(got, want))
    got["glints"][0]["loc"][0] += 0.5
    check("H4- _close rejects 0.5 cm", not M._close(got, want))
    got = copy.deepcopy(want)
    got["glints"][1]["spawn_keys"][1][0] += 1
    check("H4- _close rejects a key one frame late", not M._close(got, want))
    check("H5 binding names carry the prefix", all(M.is_ours(r["name"]) for r in want["glints"])
          and not M.is_ours("Klara Void S6 - Glimmer: Bee Swarm"))

    # ---- I. record exclusivity
    tmp = pathlib.Path(tempfile.mkdtemp()) / "rec.json"
    M.write_record_exclusive(str(tmp), {"a": 1})
    check("I1- a second exclusive record write raises", raises(lambda: M.write_record_exclusive(str(tmp), {"a": 2})))
    M.update_record(str(tmp), {"a": 3})
    check("I2 update_record replaces atomically", M.load_record(str(tmp)) == {"a": 3})
    return R


def static_checks(src):
    R = []
    tree = ast.parse(src)
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    R.append(("S1 no forbidden editor call (save-all, map load/reload, scrub, PIE end, GetBoundObjects, "
              "EvaluateAtMasterFrame)", not (attrs & FORBIDDEN_ATTRS)))
    bad_globals = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for sub_ in ast.walk(node):
                if isinstance(sub_, ast.Name) and sub_.id == "unreal":
                    bad_globals.append(ast.unparse(node)[:60])
    R.append(("S2 no unreal object in a module global", not bad_globals))
    saves = [ast.unparse(n)[:80] for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "save_asset"]
    R.append(("S3 saves only through save_asset (2 call sites: the APPLY loop, REVERT)", len(saves) == 2))
    return R


def main():
    src = TOOL_PATH.read_text(encoding="utf-8")
    M = load(TOOL_PATH, "__p06_bee_glints_import__")
    results = suite(M) + static_checks(src)
    tmpd = pathlib.Path(tempfile.mkdtemp())
    poisoned = src.replace("def _census():", "def _poison():\n    unreal.EditorLoadingAndSavingUtils.save_dirty_packages("
                           "True, True)\n\n\ndef _census():", 1)
    results.append(("S1- the static check catches an injected save_dirty_packages",
                    not all(ok for _, ok in static_checks(poisoned))))
    poisoned2 = src.replace("TOOL = \"p06_bee_glints\"", "TOOL = \"p06_bee_glints\"\nWORLD = unreal.EditorLevelLibrary", 1)
    results.append(("S2- the static check catches an unreal global", not all(ok for _, ok in static_checks(poisoned2))))
    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    passed = sum(1 for _, ok in results if ok)

    mutations = [
        ("dark gate off", "if t0 < dark_from_s:", "if t0 < 0:"),
        ("end gate off", "if t1 > length_s - end_margin_s:", "if t1 > length_s + 999:"),
        ("overlap gate off", "if prev_end is not None and t0 < prev_end:", "if prev_end is not None and t0 < -1:"),
        ("extrapolation -> clamp", "    u = (dist - d0) / seg\n", "    u = max(0.0, min(1.0, (dist - d0) / seg))\n"),
        ("clearance off", "if dist < lim[\"min_clear_cm\"]:", "if dist < 0:"),
        ("fov off", "if ang > lim_ang:", "if ang > 999:"),
        ("fov fraction ignored", "* lim[\"fov_fraction\"]", "* 10"),
        ("choreo frames absolute", "on, e0 = display_frame(rel0, tick, fps)",
         "on, e0 = display_frame(seg[\"start\"] + rel0, tick, fps)"),
        ("cueing ack ignored", "if state.get(\"attach\") == \"choreo_subtrack\" and not", "if False and not"),
        ("master_subtrack not refused", "if att in REFUSED_ATTACHES:", "if att in ():"),
        ("lateral trap off", "if lat > lim[\"max_lateral_cm\"]:", "if lat > 1e12:"),
        ("eye trap off", "if not (lim[\"eye_min_cm\"] <= dz <= lim[\"eye_max_cm\"]):", "if False:"),
        ("drift tolerance huge", "\"drifted\": abs(d) > tol_ticks", "\"drifted\": abs(d) > 1e12"),
        ("census content unchecked", "if sorted(census.get(\"content\") or []) != sorted(want_content):", "if False:"),
        ("scale limit off", "if not (0.0 < b[\"scale\"] <= lim[\"scale_max\"]):", "if not (0.0 < b[\"scale\"]):"),
        ("ahead dropped", "route_point(poly, station + float(burst[\"ahead_cm\"]))", "route_point(poly, station)"),
        ("up dropped", "base[2] + float(burst[\"up_cm\"])]", "base[2]]"),
        ("choreo short off", "if choreo_end_s + 1e-6 < last:", "if False:"),
        ("confirm unchecked", "if mode != \"DRY\" and state.get(\"confirm\") !=", "if False and state.get(\"confirm\") !="),
        ("exclusive record -> overwrite", "os.O_WRONLY | os.O_CREAT | os.O_EXCL", "os.O_WRONLY | os.O_CREAT"),
    ]
    killed = 0
    for i, (label, a, b) in enumerate(mutations):
        if src.count(a) != 1:
            print("FAIL mutation %d (%s): anchor found %d times" % (i + 1, label, src.count(a)))
            continue
        p = tmpd / ("mut_%02d.py" % i)
        p.write_text(src.replace(a, b, 1), encoding="utf-8")
        try:
            res = suite(load(p, "__p06_bee_glints_import__"))
            dead = not all(ok for _, ok in res)
        except Exception:  # noqa: BLE001 - a crash also kills the mutant
            dead = True
        killed += int(dead)
        print(("KILLED  " if dead else "SURVIVED ") + "mutation %d: %s" % (i + 1, label))
    total = len(results)
    print("\n%d/%d checks passed; %d/%d seeded mutations killed" % (passed, total, killed, len(mutations)))
    sys.exit(0 if passed == total and killed == len(mutations) else 1)


if __name__ == "__main__":
    main()
