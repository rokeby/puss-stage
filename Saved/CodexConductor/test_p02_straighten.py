"""Offline harness for p02_straighten.py (system Python, no Unreal). Every gate has a failing control.

Fixture data, cited (the live DRY re-reads all of it):
  P02 route start (0, 80000, 0); curve end (11857.83, 80000, 0) yaw 0; spline 13582.59 cm
      CodexStructure/scene_docks.json route_ends, CodexStructure/mouth_survey.json "02" [meas 30 Sep]; probe_routes.json [meas 5 Oct]
  compiled distance 11857.8345 cm: passage_resize_dry_P02.json old_route_length_cm [meas 2 Oct]
  S2 dock (10742.23, 81299.02) yaw -43.5725: CodexStructure/hangar_s2_record.json [meas 30 Sep 12:31]
  four P02 slabs (loc/yaw/scale): floor_dark_wet_dry_20261005-015527.json "p02" [meas 5 Oct 01:55; z raised since]
  ASSUMED (the DRY measures them): actor yaw 0 with the route at the actor origin; camera end view = route frame at
  the end distance + (0, 0, 180) (S1 Entry sits at P01's route end +150 z, scene_docks.json); wing half width 1000 cm.
Run: python test_p02_straighten.py -> P02_STRAIGHTEN_HARNESS|tests=..|checks=..|controls=..|failed=..
"""
import copy
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("p02_straighten", os.path.join(HERE, "p02_straighten.py"))
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)
assert ps.unreal is None, "harness must run without Unreal"

L = 11857.8345
SPLINE_LEN = 13582.58984375
ACTOR = ps.xf([0.0, 80000.0, 0.0], 0.0)
ROUTE_REL = ps.xf([0, 0, 0], 0.0)
DOCK = ps.xf([10742.232211654631, 81299.0241181779, 180.0], -43.57251940082824)
REL = ps.xf([0, 0, 180.0], 0.0)
OLD_END_FRAME = ps.xf([DOCK["loc"][0], DOCK["loc"][1], 0.0], DOCK["yaw"])   # camera sits on the bend at d = L
OLD_START_FRAME = ps.xf([0, 80000, 0], 22.91)
CAM_START = ps.compose(OLD_START_FRAME, REL)
with open(os.path.join(HERE, "floor_dark_wet_dry_20261005-015527.json"), encoding="utf-8") as _h:
    _P02 = json.load(_h)["p02"]
RECTS = [ps.slab_rect(k, v["xf"]["loc"], v["xf"]["rot"][2], v["xf"]["scale"]) for k, v in _P02.items()]

CHECKS = {"n": 0, "controls": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def control(cond_that_must_be_false, what):
    """A failing control: the broken variant must be detected (cond False)."""
    CHECKS["controls"] += 1
    check(not cond_that_must_be_false, "CONTROL " + what)


def test(fn):
    TESTS.append(fn)
    return fn


def facts(rects=RECTS, mouth=("Interaction 1 — Stalls Camera", "S02 Mouth Lantern"), redock_text=None,
          record=False, reverted=False, straight=False):
    rel_end = ps.camera_rel(OLD_END_FRAME, ps.compose(OLD_END_FRAME, REL))
    rel_start = ps.camera_rel(OLD_START_FRAME, CAM_START)
    hole = ps.hangar_hole(DOCK, rects)
    preds, floor = {}, {}
    for anchor in ("START", "DOCK"):
        a = ACTOR if anchor == "START" else ps.solve_dock_anchor(DOCK, rel_end, L, ROUTE_REL, 0.0)
        sr = ps.straight_route(a, ROUTE_REL, L)
        preds[anchor] = {"actor": a, "route": sr, "cam_end": ps.predict_camera(sr["start"], L, rel_end),
                         "cam_start": ps.predict_camera(sr["start"], 0.0, rel_start)}
        floor[anchor] = ps.floor_plan(rects, ps.route_samples(sr["start"], L, 400.0, 1500.0), DOCK, hole)
    return {"preds": preds, "floor": floor, "hole": hole, "mouth_actors": list(mouth),
            "dock_delta": {k: ps.delta(v["cam_end"], DOCK) for k, v in preds.items()},
            "start_delta": {k: ps.delta(v["cam_start"], CAM_START) for k, v in preds.items()},
            "redock_tool_text": redock_text, "record_exists": record, "already_reverted": reverted,
            "already_straight": straight, "length_short": False}


APPLY_DOCK = {"confirm": "APPLY P02STRAIGHT", "anchor": "DOCK", "followons_ack": ["MATCH_HANDOFFS", "ROUTE_ACTORS"]}


@test
def t_frames():
    f = ps.xf([123.0, -45.0, 6.0], 37.0)
    rt = ps.compose(f, ps.inverse(f))
    check(max(abs(x) for x in rt["loc"]) < 1e-9 and abs(rt["yaw"]) < 1e-9, "compose(f, inverse f) = identity")
    bad = ps.xf([123.0, -45.0, 6.0], -37.0)
    rt2 = ps.compose(f, bad)
    control(max(abs(x) for x in rt2["loc"]) < 1e-6, "wrong inverse (sign flip) is not identity")


@test
def t_straight_route_keeps_the_route_end():
    sr = ps.straight_route(ACTOR, ROUTE_REL, L)
    check(abs(sr["end"]["loc"][0] - 11857.83) < 0.01 and abs(sr["end"]["loc"][1] - 80000.0) < 1e-6
          and sr["end"]["yaw"] == 0.0, "compiled-length straight route ends where the curve ends (11857.83, 80000)")
    wrong = ps.straight_route(ACTOR, ROUTE_REL, SPLINE_LEN)
    control(abs(wrong["end"]["loc"][0] - 11857.83) < 0.01, "spline length instead of compiled length moves the end")


@test
def t_start_anchor_moves_the_dock_and_refuses():
    fa = facts()
    d = fa["dock_delta"]["START"]
    check(ps.moves(d) and abs(d["yaw_deg"] - 43.57) < 0.01, "START: end view turns +43.57 deg off the S2 dock")
    check(abs(d["xy_cm"] - 1712.3) < 5.0, "START: end view moves ~17 m (route end vs dock)")
    args = dict(APPLY_DOCK, anchor="START", followons_ack=["S2_REDOCK", "MATCH_HANDOFFS", "ROUTE_ACTORS"])
    r = ps.refusals("APPLY", args, fa)
    check(any(x.startswith("DOCK_MOVES_NEEDS_REDOCK") for x in r), "START refuses without a registered re-dock tool")
    ok = ps.refusals("APPLY", dict(args, redock_ack=ps.REDOCK_ACK), facts(redock_text="x\n" + ps.REDOCK_MARK + "\n"))
    check(not any(x.startswith("DOCK_MOVES") for x in ok), "START passes the dock gate with tool + ack")
    control(not any(x.startswith("DOCK_MOVES") for x in ps.refusals(
        "APPLY", dict(args, redock_ack=ps.REDOCK_ACK), facts(redock_text="# some other tool\n"))),
        "a tool file without the REDOCK_FOR marker must not open the gate")
    control(not any(x.startswith("DOCK_MOVES") for x in ps.refusals(
        "APPLY", dict(args, redock_ack="yes"), facts(redock_text=ps.REDOCK_MARK))), "a wrong ack must not open the gate")


@test
def t_dock_anchor_lands_on_the_dock():
    fa = facts()
    d = fa["dock_delta"]["DOCK"]
    check(d["xy_cm"] < 1e-6 and abs(d["yaw_deg"]) < 1e-9, "DOCK: predicted end view on the dock")
    a = fa["preds"]["DOCK"]["actor"]
    check(abs(a["yaw"] - DOCK["yaw"]) < 1e-9, "DOCK: the lane heads -43.57 (the dock yaw)")
    check(not any(x.startswith("DOCK_MOVES") for x in ps.refusals("APPLY", APPLY_DOCK, fa)), "DOCK passes the dock gate")
    sr = ps.straight_route(a, ROUTE_REL, L)
    off = ps.predict_camera(sr["start"], L - 100.0, ps.camera_rel(OLD_END_FRAME, ps.compose(OLD_END_FRAME, REL)))
    control(not ps.moves(ps.delta(off, DOCK)), "a 1 m error in the end distance must miss the dock")
    sd = fa["start_delta"]["DOCK"]
    check(sd["xy_cm"] > 1000.0, "DOCK: the mouth moves (follow-ons needed)")


@test
def t_hangar_hole():
    h = ps.hangar_hole(DOCK, RECTS)
    check(h is not None and abs(h["x0"] - 500) < 2 and abs(h["x1"] - 11504) < 2 and abs(h["half_y"] - 1175) < 2,
          "the four slabs frame the S2 pit: dock-frame x 500..11504, |y| < 1175 (%s)" % h)
    control(ps.hangar_hole(DOCK, RECTS[:3] if RECTS[3]["label"].endswith("Far") else RECTS) is not None,
            "without the Far slab there is no framed hole")


@test
def t_floor_coverage():
    fa = facts()
    cd, cs = fa["floor"]["DOCK"]["coverage"], fa["floor"]["START"]["coverage"]
    check(not cd["gaps"] and cd["in_pit"] == 0 and not fa["floor"]["DOCK"]["moves"],
          "DOCK: slabs already cover route +-15 m incl. apron; no slab moves (%s)" % {k: v for k, v in cd.items() if k != "gaps"})
    check(not cs["gaps"] and cs["in_pit"] > 0 and cs["pit_min_d_cm"] > 10000,
          "START: only the last ~1.7 m + apron lies over the S2 pit; nothing else uncovered")
    no_near = [r for r in RECTS if not r["label"].endswith("Near")]
    fb = ps.floor_plan(no_near, ps.route_samples(fa["preds"]["DOCK"]["route"]["start"], L, 400.0, 1500.0), DOCK, None)
    control(not fb["coverage"]["gaps"], "removing the Near slab must expose gaps")


@test
def t_fit_slab():
    r = {"label": "T", "loc": [0.0, 0.0], "yaw": 30.0, "half": [100.0, 50.0]}
    new, why = ps.fit_slab(r, [(500.0, 400.0)], DOCK, None)
    check(why is None and ps.in_slab(new, (500.0, 400.0), 0.01)
          and all(ps.in_slab(new, c, 0.01) for c in ps.rect_corners(r)), "grown slab holds old footprint + gap point")
    hole = ps.hangar_hole(DOCK, RECTS)
    pit_pt = ps.compose(DOCK, ps.xf([3000, 0, 0], 0))["loc"][:2]
    near = next(x for x in RECTS if x["label"].endswith("Near"))
    _, why2 = ps.fit_slab(near, [tuple(pit_pt)], DOCK, hole)
    control(why2 is None, "growing a slab into the S2 pit must refuse")


@test
def t_rects_overlap():
    a = {"label": "a", "loc": [0, 0], "yaw": 0.0, "half": [10, 10]}
    check(ps.rects_overlap(a, {"label": "b", "loc": [15, 0], "yaw": 45.0, "half": [10, 10]}), "overlap detected")
    control(ps.rects_overlap(a, {"label": "c", "loc": [40, 0], "yaw": 45.0, "half": [10, 10]}), "disjoint not overlapping")


@test
def t_spline_snapshot():
    s = {"closed": False, "points": [
        {"loc": [0, 0, 0], "arrive": [1, 2, 0], "leave": [1, 2, 0], "type": "CURVE", "rot": [0, 0, 22.91], "scale": [1, 1, 1]},
        {"loc": [6000, 2900, 0], "arrive": [5, 0, 0], "leave": [5, 0, 0], "type": "CURVE_CUSTOM_TANGENT", "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"loc": [11857.83, 0, 0], "arrive": [9, 0, 0], "leave": [9, 0, 0], "type": "CURVE", "rot": [0, 0, 0], "scale": [1, 1, 1]}]}
    check(ps.snap_equal(s, copy.deepcopy(s)), "identical snapshot restores exactly")
    t = copy.deepcopy(s)
    t["points"][1]["arrive"][1] += 0.01
    control(ps.snap_equal(s, t), "a 0.01 tangent change must fail the exact-restore check")
    u = copy.deepcopy(s)
    u["points"][0]["type"] = "LINEAR"
    control(ps.snap_equal(s, u), "a point-type change must fail")
    control(ps.snap_equal(s, {"closed": False, "points": s["points"][:2]}), "a lost point must fail")


@test
def t_ground():
    before = {"enabled": True, "floor_height_cm": 0.0, "apron_cm": 400.0, "cut_chariot_slots": True}
    check(ps.ground_change_ok(before, dict(before, enabled=False), False), "only the enabled flag flips")
    control(ps.ground_change_ok(before, dict(before, enabled=False, floor_height_cm=5.0), False),
            "a floor height change must be rejected (fixtures/cloth/underpass read it)")
    control(ps.ground_change_ok(before, before, False), "boards still on must be rejected")


@test
def t_confirm_anchor_followons():
    fa = facts()
    r = ps.refusals("APPLY", dict(APPLY_DOCK, confirm="APPLY P02"), fa)
    check(any(x.startswith("CONFIRM_MISSING") for x in r), "wrong confirm refuses")
    check(ps.refusals("APPLY", APPLY_DOCK, fa) == [], "DOCK with the follow-ons acked: no refusal (%s)"
          % ps.refusals("APPLY", APPLY_DOCK, fa))
    control(ps.refusals("APPLY", dict(APPLY_DOCK, followons_ack=["MATCH_HANDOFFS"]), fa) == [],
            "an un-acked follow-on (route actors) must refuse")
    check(ps.followons_needed(facts(mouth=()), "DOCK") == ["MATCH_HANDOFFS"], "no route actors -> no ROUTE_ACTORS")
    control(ps.refusals("APPLY", dict(APPLY_DOCK, anchor=None), fa) == [], "a missing anchor must refuse")
    check(ps.followons_needed(fa, "DOCK") == ["MATCH_HANDOFFS", "ROUTE_ACTORS"], "DOCK follow-ons")
    check(ps.followons_needed(fa, "START") == ["S2_REDOCK", "MATCH_HANDOFFS", "ROUTE_ACTORS"], "START follow-ons")
    control(ps.refusals("APPLY", APPLY_DOCK, facts(record=True)) == [], "an existing record must refuse APPLY")
    control(ps.refusals("APPLY", APPLY_DOCK, facts(straight=True)) == [], "an already-straight route must refuse")
    control(ps.refusals("APPLY", dict(APPLY_DOCK, floor_material="GOLD"), fa) == [], "unknown floor material refuses")


@test
def t_revert_gates():
    args = {"confirm": "REVERT P02STRAIGHT"}
    check(ps.refusals("REVERT", args, facts(record=True)) == [], "REVERT with a record passes")
    control(ps.refusals("REVERT", args, facts(record=False)) == [], "REVERT without a record must refuse")
    control(ps.refusals("REVERT", args, facts(record=True, reverted=True)) == [], "a second REVERT must refuse")
    control(ps.refusals("REVERT", {"confirm": "APPLY P02STRAIGHT"}, facts(record=True)) == [], "REVERT with APPLY confirm")


for fn in TESTS:
    fn()
print("P02_STRAIGHTEN_HARNESS|tests=%d|checks=%d|controls=%d|failed=%d" % (len(TESTS), CHECKS["n"], CHECKS["controls"],
                                                                           len(CHECKS["failed"])))
for f in CHECKS["failed"]:
    print("FAILED|" + f)
raise SystemExit(1 if CHECKS["failed"] else 0)
