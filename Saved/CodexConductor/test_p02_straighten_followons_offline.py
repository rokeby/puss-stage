"""Offline harness for p02_straighten_followons.py (system Python, no Unreal). Every gate has a failing control.

Fixtures, cited:
  P02 OLD spline (3 points, local, actor at (0, 80000, 0) yaw 0), compiled distance 11857.8345 cm, S2 dock
      (10742.23, 81299.02) yaw -43.5725, DOCK straight start (2151.20, 89472.30) yaw -43.5725:
      p02_straighten_dry_P02STR-20261006-014311.json [meas 6 Oct]. The spline is evaluated here as UE's Hermite
      (FMath::CubicInterp per segment, leave tangent of the start point, arrive of the end point) [inf]; the test
      CHECKS that inference against two measured numbers (spline length 13582.59 cm, camera end view = dock).
  I1 sleight keys: curtain_sleight_record_I1.json plan.mouth_camera.keys / mouth_card.keys / frames_of_reference
      [meas 5 Oct APPLY record]. Stalls camera: CodexCameraPilot/place_transition_stalls.json [meas]. Lantern rel pose:
      curtain_sleight_I1_dry.json inputs.lantern.rel_loc [meas]. Car light: place_p02_car_light_record.json [meas].
      Pit liner near wall: CodexStructure/landscape_floors_record.json [meas].
Run: python test_p02_straighten_followons_offline.py -> P02_FOLLOWONS_HARNESS|tests=..|checks=..|controls=..|failed=..
     (also prints PREDICT| rows: the offline-predicted move of every route actor, tier [inf]).
"""
import copy
import importlib.util
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("p02_straighten_followons", os.path.join(HERE, "p02_straighten_followons.py"))
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)
assert pf.unreal is None, "harness must run without Unreal"

DRY = json.load(open(os.path.join(HERE, "p02_straighten_dry_P02STR-20261006-014311.json"), encoding="utf-8"))
SLEIGHT = json.load(open(os.path.join(HERE, "curtain_sleight_record_I1.json"), encoding="utf-8"))
L = float(DRY["required_cm"])
ACTOR = DRY["actor"]
DOCK = DRY["dock"]
NEW_START = DRY["preds"]["DOCK"]["route"]["start"]

CHECKS = {"n": 0, "controls": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def control(cond_that_must_be_false, what):
    CHECKS["controls"] += 1
    check(not cond_that_must_be_false, "CONTROL " + what)


def test(fn):
    TESTS.append(fn)
    return fn


def close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# ---------------------------------------------------------------- curve fixtures ---------------------------------------
class Curve:
    """Arc-length parametrised planar curve from a point function on [0, 1] (dense table)."""

    def __init__(self, fn, n=20000):
        self.pts = [fn(i / n) for i in range(n + 1)]
        self.s = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            self.s.append(self.s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.length = self.s[-1]

    def frame(self, s):
        s = max(0.0, min(self.length, s))
        lo, hi = 0, len(self.s) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.s[mid] <= s:
                lo = mid
            else:
                hi = mid
        a, b = self.pts[lo], self.pts[hi]
        u = 0.0 if self.s[hi] == self.s[lo] else (s - self.s[lo]) / (self.s[hi] - self.s[lo])
        return pf.xf([a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]), 0.0],
                     math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))

    def samples(self, step=10.0):
        out, s = [], 0.0
        while s < self.length:
            f = self.frame(s)
            out.append([s, f["loc"][0], f["loc"][1]])
            s += step
        f = self.frame(self.length)
        out.append([self.length, f["loc"][0], f["loc"][1]])
        return out


def hermite(p0, t0, p1, t1, u):
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return [h00 * p0[i] + h10 * t0[i] + h01 * p1[i] + h11 * t1[i] for i in range(2)]


def p02_old_curve():
    pts = DRY["spline"]["points"]
    ox, oy = ACTOR["loc"][0], ACTOR["loc"][1]   # actor yaw 0, route_rel identity [meas DRY]

    def fn(t):
        k = t * 2.0
        i = min(1, int(k))
        u = k - i
        q = hermite(pts[i]["loc"], pts[i]["leave"], pts[i + 1]["loc"], pts[i + 1]["arrive"], u)
        return (q[0] + ox, q[1] + oy)
    return Curve(fn, 40000)


def arc_curve(radius, start_yaw, length, origin=(0.0, 0.0)):
    """Circular arc turning left, start at origin heading start_yaw."""
    c = math.radians(start_yaw)
    cx, cy = origin[0] - radius * math.sin(c), origin[1] + radius * math.cos(c)

    def fn(t):
        a = c + t * length / radius
        return (cx + radius * math.sin(a), cy - radius * math.cos(a))
    return Curve(fn, 20000)


OLD = p02_old_curve()


def dock_new_start(old, d_end):
    """DOCK: straight route whose frame at d_end equals the old frame at d_end."""
    fe = old.frame(d_end)
    return pf.compose(fe, pf.xf([-d_end, 0, 0], 0.0))


def capture_from(old, d_end, actors, seq_items, policy=None):
    """Offline CAPTURE: same fields capture_mode writes, old frames from the fixture curve."""
    samples = old.samples()
    rows = {}
    pol = policy or pf.POLICY
    for label, pose in actors.items():
        s_near, lat = pf.nearest_s(samples, pose["loc"])
        row = {"policy": pol[label], "pose": pose, "nearest_s": s_near, "lateral_cm": lat}
        st = pf.station(pol[label], s_near, d_end)
        if st is not None:
            row["station_s"] = st
            row["old_frame"] = old.frame(st)
            row["local"] = pf.to_local(row["old_frame"], pose["loc"])
        rows[label] = row
    return {"d_end_cm": d_end, "samples": samples, "mouth_frame_old": old.frame(0.0), "actors": rows,
            "missing": [], "unclassified": [],
            "sequence": {"items": seq_items, "foreign_transform_bindings": []}}


def pose(loc, yaw, roll=0.0, pitch=0.0):
    return {"loc": list(loc), "rot": [roll, pitch, yaw], "scale": [1.0, 1.0, 1.0]}


def keys_to_channels(keys):
    """curtain_sleight key tuples (f, x, y, z, pitch, yaw, roll, ...) -> channel rows (POSE_CHANNELS map)."""
    ch = {"Location.X": [], "Location.Y": [], "Location.Z": [], "Rotation.X": [], "Rotation.Y": [], "Rotation.Z": []}
    for k in keys:
        f = int(k[0])
        ch["Location.X"].append([f, float(k[1])])
        ch["Location.Y"].append([f, float(k[2])])
        ch["Location.Z"].append([f, float(k[3])])
        ch["Rotation.Y"].append([f, float(k[4])])
        ch["Rotation.Z"].append([f, float(k[5])])
        ch["Rotation.X"].append([f, float(k[6])])
    return ch


def real_fixture():
    plan_ = SLEIGHT["plan"]
    mc = plan_["mouth_camera"]["level_world"]
    stalls = next(r for r in json.load(open(os.path.join(SAVED, "CodexCameraPilot", "place_transition_stalls.json"),
                                            encoding="utf-8"))["plan"] if r["mouth_tag"] == "InfinityStage.Mouth.P02")
    lantern_rel = json.load(open(os.path.join(HERE, "curtain_sleight_I1_dry.json"), encoding="utf-8"))["inputs"]["lantern"]["rel_loc"]
    mouth = plan_["frames_of_reference"]["mouth_drape_world"]
    lan = pf.from_local(pf.xf(mouth["loc"], mouth["yaw"]), lantern_rel)
    car = json.load(open(os.path.join(HERE, "place_p02_car_light_record.json"), encoding="utf-8"))
    liner = next(r for r in json.load(open(os.path.join(SAVED, "CodexStructure", "landscape_floors_record.json"),
                                           encoding="utf-8"))["plan"] if r["label"] == "S2 Pit Liner Near Wall")
    actors = {
        "I1 Sleight Mouth Camera": pose(mc["loc"], mc["yaw"], 0.0, mc["pitch"]),
        "Interaction 1 — Stalls Camera": pose(stalls["location"], stalls["rotation"][1], stalls["rotation"][2],
                                                   stalls["rotation"][0]),
        "S02 Mouth Lantern": pose(lan, 30.0, 0.0, -6.0),
        "P02 Car Light (trial, Gary to tune)": pose(car["location"], car["yaw"]),
        "S2 Pit Liner Near Wall": pose(liner["loc"], liner["yaw"]),
        "Scene 2 — External Sound — Entry Handoff Camera": pose(DOCK["loc"], DOCK["yaw"]),
        "Scene 2 — External Sound — Exit Handoff Camera": pose([DOCK["loc"][0] + 500, DOCK["loc"][1], 180], 0.0),
    }
    items = [{"binding": "I1 Sleight Mouth Camera", "kind": "TRANSFORM_TRACK",
              "channels": keys_to_channels(plan_["mouth_camera"]["keys"])},
             {"binding": "Sleight Mouth Shadow Card", "kind": "TRANSFORM_TRACK",
              "channels": keys_to_channels(plan_["mouth_card"]["keys"])},
             {"binding": "Transition Drape (baked)", "kind": "SPAWNABLE_TEMPLATE",
              "pose": pose(mouth["loc"], mouth["yaw"])}]
    return actors, items


# ---------------------------------------------------------------- tests ------------------------------------------------
@test
def t_frame_algebra():
    f0, f1 = pf.xf([10, 20, 0], 30.0), pf.xf([-500, 900, 0], -66.48)
    p = pose([123.0, -45.0, 7.0], 170.0, 2.0, -3.0)
    q = pf.re_express_pose(pf.re_express_pose(p, f0, f1), f1, f0)
    check(close(q["loc"], p["loc"], 1e-9) and abs(q["rot"][2] - p["rot"][2]) < 1e-9 and q["rot"][:2] == p["rot"][:2],
          "re_express round trip")
    check(close(pf.from_local(f1, pf.to_local(f1, [5, 6, 7])), [5, 6, 7], 1e-9), "local round trip")
    control(close(pf.re_express_point([123.0, -45.0, 7.0], f0, f1), [123.0, -45.0, 7.0], 1e-3),
            "identity map passes for a moved frame")


@test
def t_fixture_matches_measured():
    check(abs(OLD.length - DRY["spline"]["length_cm"]) < 2.0,
          "Hermite P02 fixture length %.2f vs measured %.2f" % (OLD.length, DRY["spline"]["length_cm"]))
    fe = OLD.frame(L)
    d = math.hypot(fe["loc"][0] - DOCK["loc"][0], fe["loc"][1] - DOCK["loc"][1])
    # UE maps distance -> input key through a coarse reparam table (10 steps/segment) [inf]; the fixture integrates
    # exactly, so ~10 cm / 0.07 deg at 118 m is fixture fidelity. The TOOL never uses this fixture: CAPTURE stores
    # Unreal's own frames.
    check(d < 15.0 and abs(pf.wrap(fe["yaw"] - DOCK["yaw"])) < 0.1,
          "fixture end frame vs measured dock: %.2f cm %.3f deg" % (d, pf.wrap(fe["yaw"] - DOCK["yaw"])))
    f0 = OLD.frame(0.0)
    check(abs(f0["yaw"] - 22.9077) < 0.05, "fixture start yaw 22.91 [meas]")
    ns = dock_new_start(OLD, L)
    check(math.hypot(ns["loc"][0] - NEW_START["loc"][0], ns["loc"][1] - NEW_START["loc"][1]) < 30.0
          and abs(pf.wrap(ns["yaw"] - NEW_START["yaw"])) < 0.1, "DOCK new start matches the straighten DRY (fixture fidelity)")
    control(abs(OLD.length - 11857.8345) < 2.0, "fixture length equals the compiled distance (it must not)")


@test
def t_known_curve_to_straight():
    old = arc_curve(9000.0, 30.0, 12000.0)
    d_end = 11000.0
    ns = dock_new_start(old, d_end)
    new = lambda s: pf.straight_frame(ns, s)   # noqa: E731
    near_end = pf.from_local(old.frame(10950.0), [0.0, 800.0, 50.0])
    beyond = pf.from_local(old.frame(old.length), [0.0, -300.0, 0.0])
    mouth = pf.from_local(old.frame(0.0), [-1200.0, 300.0, 400.0])
    actors = {"END": pose(near_end, 12.0), "BEYOND": pose(beyond, 0.0), "MOUTH": pose(mouth, 40.0, 1.5, -4.0)}
    cap = capture_from(old, d_end, actors, [], {"END": "STATION", "BEYOND": "STATION", "MOUTH": "MOUTH"})
    p = pf.plan(cap, new)
    by = {a["label"]: a for a in p["actors"]}
    check(by["END"]["move"]["xy_cm"] < 5.0 and abs(by["END"]["move"]["yaw_deg"]) < 0.5,
          "point near the docked end barely moves: %r" % by["END"]["move"])
    check(by["BEYOND"]["station_s"] == d_end and by["BEYOND"]["move"]["xy_cm"] < 1e-6,
          "past the camera end clamps to the end frame and stays")
    check(by["MOUTH"]["station_s"] == 0.0, "behind the mouth -> s = 0")
    loc_rel = pf.to_local(new(0.0), by["MOUTH"]["after"]["loc"])
    check(close(loc_rel, [-1200.0, 300.0, 400.0], 1e-6), "mouth actor keeps its pose in the mouth frame")
    expect_dyaw = pf.wrap(new(0.0)["yaw"] - old.frame(0.0)["yaw"])
    check(abs(pf.wrap(by["MOUTH"]["after"]["rot"][2] - (40.0 + expect_dyaw))) < 1e-9, "yaw rides the mouth")
    check(by["MOUTH"]["after"]["rot"][:2] == [1.5, -4.0], "roll/pitch untouched")
    check(by["MOUTH"]["move"]["xy_cm"] > 1000.0, "mouth actually moved on this curve")
    # controls
    control(pf.poses_equal(by["MOUTH"]["after"], actors["MOUTH"]), "a not-moved mouth actor passes")
    bad = copy.deepcopy(by["MOUTH"]["after"])
    bad["rot"][2] -= expect_dyaw
    control(abs(pf.wrap(bad["rot"][2] - (40.0 + expect_dyaw))) < 0.5, "forgetting dyaw passes")
    wrong = pf.re_express_pose(actors["END"], old.frame(0.0), new(0.0))
    control(pf.pose_delta(wrong, actors["END"])["xy_cm"] < 5.0, "mouth-station for an end actor still 'stays'")


@test
def t_nearest_and_station():
    old = arc_curve(5000.0, 0.0, 6000.0)
    smp = old.samples()
    for s0 in (500.0, 2500.0, 5500.0):
        p = pf.from_local(old.frame(s0), [0.0, -1500.0, 0.0])
        s, lat = pf.nearest_s(smp, p)
        check(abs(s - s0) < 2.0 and abs(lat - 1500.0) < 1.0, "nearest s on the normal: %r vs %r" % (s, s0))
    s, _ = pf.nearest_s(smp, pf.from_local(old.frame(0.0), [-3000.0, 100.0, 0.0]))
    check(s == 0.0, "behind the start -> 0")
    check(pf.station("STATION", 9000.0, 4000.0) == 4000.0 and pf.station("STAY", 10.0, 4000.0) is None
          and pf.station("HANDOFF", 10.0, 4000.0) is None and pf.station("MOUTH", 3000.0, 4000.0) == 0.0, "policies")
    control(pf.station("STATION", 9000.0, 4000.0) == 9000.0, "unclamped station beyond the end")


@test
def t_keys_rigid_and_yaw_continuous():
    old0, new0 = pf.xf([0, 80000, 0], 22.9), pf.xf([2151.2, 89472.3, 0], 27.9)   # dyaw +5: keys 175..202 cross 180
    ch = {"Location.X": [[f, 100.0 * f] for f in range(10)], "Location.Y": [[f, 80000.0 - 5.0 * f] for f in range(10)],
          "Location.Z": [[f, 180.0] for f in range(10)], "Rotation.Z": [[f, 170.0 + 3.0 * f] for f in range(10)],
          "Rotation.X": [[f, 0.0] for f in range(10)]}
    new, why = pf.rekey(ch, old0, new0)
    check(why is None, "rekey ok")
    check(pf.max_yaw_step(new) < 3.0 + 1e-9, "yaw stays continuous across +-180 (no 360 jump)")
    for i in range(10):
        a, b = pf.key_pose(ch, i), pf.key_pose(new, i)
        check(close(pf.to_local(old0, a["loc"]), pf.to_local(new0, b["loc"]), 1e-6), "key %d rigid" % i)
    d01 = math.dist(pf.key_pose(ch, 0)["loc"][:2], pf.key_pose(ch, 9)["loc"][:2])
    check(abs(d01 - math.dist(pf.key_pose(new, 0)["loc"][:2], pf.key_pose(new, 9)["loc"][:2])) < 1e-6,
          "path length preserved (walk speed unchanged)")
    wrapped = copy.deepcopy(new)
    wrapped["Rotation.Z"] = [[f, pf.wrap(v)] for f, v in new["Rotation.Z"]]
    control(pf.max_yaw_step(wrapped) < 10.0, "per-key wrapped yaw has no 360 jump")
    bad = copy.deepcopy(ch)
    bad["Location.Y"][3][0] = 99
    check(pf.rekey(bad, old0, new0)[1] == "XY_KEY_FRAMES_DIFFER", "XY frame mismatch refused")
    control(pf.rekey(bad, old0, new0)[1] is None, "XY frame mismatch accepted")
    check(pf.channel_base("Location.Y_183") == "Location.Y" and pf.channel_base("Rotation.Z") == "Rotation.Z",
          "channel suffix stripped")


@test
def t_real_p02_plan():
    actors, items = real_fixture()
    cap = capture_from(OLD, L, actors, items)
    ns = dock_new_start(OLD, L)
    p = pf.plan(cap, lambda s: pf.straight_frame(ns, s))
    by = {a["label"]: a for a in p["actors"]}
    check(not p["refusals"], "real plan has no refusals: %r" % p["refusals"])
    for lab in ("I1 Sleight Mouth Camera", "Interaction 1 — Stalls Camera", "S02 Mouth Lantern"):
        check(by[lab]["nearest_s"] < 1.0, "%s sits behind the mouth (nearest s %.1f)" % (lab, by[lab]["nearest_s"]))
        check(by[lab]["move"]["xy_cm"] > 9000.0, "%s moves with the mouth" % lab)
    for lab in ("S2 Pit Liner Near Wall", "Scene 2 — External Sound — Entry Handoff Camera",
                "Scene 2 — External Sound — Exit Handoff Camera"):
        check(by[lab]["move"] is None and by[lab]["after"] == by[lab]["before"], "%s untouched" % lab)
    # the walk ends exactly on P02's new start view (camera = route frame + (0,0,180) [meas DRY rel_start])
    cam_new = pf.compose(ns, pf.xf([0, 0, 180.0], 0.0))
    we = p["walk_end_planned"]
    check(math.hypot(we["loc"][0] - cam_new["loc"][0], we["loc"][1] - cam_new["loc"][1]) < 3.0
          and abs(we["loc"][2] - 180.0) < 1e-6 and abs(pf.wrap(we["rot"][2] - cam_new["yaw"])) < 0.05,
          "walk end lands on the new P02 start view: %r vs %r" % (we, cam_new))
    # the sleight seat keeps its pose relative to the moved drape; level actor == key 0
    cam_seq = next(s for s in p["sequence"] if s["binding"] == "I1 Sleight Mouth Camera")
    drape = next(s for s in p["sequence"] if s["binding"] == "Transition Drape (baked)")
    k0 = pf.key_pose(cam_seq["after"], 0)
    check(pf.poses_equal(k0, by["I1 Sleight Mouth Camera"]["after"], 1e-6, 1e-6), "level camera == key 0 after")
    rel_b = pf.to_local(pf.xf(drape["before"]["loc"], drape["before"]["rot"][2]), pf.key_pose(cam_seq["before"], 0)["loc"])
    rel_a = pf.to_local(pf.xf(drape["after"]["loc"], drape["after"]["rot"][2]), k0["loc"])
    check(close(rel_a, rel_b, 1e-6), "sleight camera vs drape unchanged (the matched framing)")
    check(abs(cam_seq["yaw_step_after"] - cam_seq["yaw_step_before"]) < 1e-9, "walk yaw steps unchanged")
    check(math.hypot(drape["after"]["loc"][0] - ns["loc"][0], drape["after"]["loc"][1] - ns["loc"][1]) < 3.0,
          "drape template lands on the new route start (fit_transition_drapes' rule)")
    car = by["P02 Car Light (trial, Gary to tune)"]
    # placed at (0, +2400, 90) in the route frame at spline_length*14.5/23 = 8563.5 cm (place_p02_car_light.py:20-21,58-61)
    check(abs(car["nearest_s"] - DRY["spline"]["length_cm"] * 14.5 / 23.0) < 15.0 and abs(car["lateral_cm"] - 2400.0) < 15.0,
          "car light nearest s/lateral = its placement: %.1f / %.1f" % (car["nearest_s"], car["lateral_cm"]))
    check(close(pf.to_local(car["new_frame"], car["after"]["loc"]), pf.to_local(car["old_frame"], car["before"]["loc"]), 1e-6),
          "car light keeps its station-frame pose")
    for a in p["actors"]:
        print("PREDICT|%s|policy=%s|nearest_s=%.0f|station=%s|move=%s" % (
            a["label"], a["policy"], a["nearest_s"], None if a["station_s"] is None else round(a["station_s"]),
            None if a["move"] is None else {k: round(v, 1) for k, v in a["move"].items()}))
    control(pf.poses_equal(k0, pf.key_pose(cam_seq["before"], 0)), "sleight key 0 unchanged")


@test
def t_round_trip_and_drift():
    actors, items = real_fixture()
    cap = capture_from(OLD, L, actors, items)
    ns = dock_new_start(OLD, L)
    p = pf.plan(cap, lambda s: pf.straight_frame(ns, s))
    rec = pf.record_from_plan(p, "T", "B")
    live0 = {"actors": {l: copy.deepcopy(r["pose"]) for l, r in cap["actors"].items()},
             "sequence": {i["binding"]: copy.deepcopy(i["channels"] if i["kind"] == "TRANSFORM_TRACK" else i["pose"])
                          for i in items}}
    live1 = pf.apply_model(live0, rec)
    check(pf.drift(live1, rec, "after") == [], "applied state == record.after")
    check(len(pf.drift(live0, rec, "after")) == 7, "pre-apply state differs on 4 actors + 3 sequence items")
    live2 = pf.revert_model(live1, rec)
    check(json.dumps(live2, sort_keys=True) == json.dumps(live0, sort_keys=True), "CAPTURE -> APPLY -> REVERT exact")
    check(json.dumps(json.loads(json.dumps(rec)), sort_keys=True) == json.dumps(rec, sort_keys=True),
          "record survives JSON")
    moved = copy.deepcopy(live1)
    moved["actors"]["S02 Mouth Lantern"]["loc"][0] += 5.0
    check(pf.drift(moved, rec, "after") == ["actor:S02 Mouth Lantern"], "drift found")
    control(pf.drift(moved, rec, "after") == [], "drift missed")
    k = copy.deepcopy(live1)
    k["sequence"]["Sleight Mouth Shadow Card"]["Location.X"][0][1] += 0.01
    check(pf.drift(k, rec, "after") == ["seq:Sleight Mouth Shadow Card"], "key drift found")


@test
def t_gates():
    straight_rec = {"status": "saved", "anchor": "DOCK", "before": {"spline": DRY["spline"]}}
    cap = {"spline": DRY["spline"]}
    ok = {"capture": cap, "record_exists": False, "straighten_record": straight_rec, "route_straight": True,
          "new_route_bad": None, "moved_since_capture": [], "plan_refusals": []}
    A = {"confirm": "APPLY P02FOLLOW"}
    check(pf.refusals("APPLY", A, ok) == [], "clean APPLY passes: %r" % pf.refusals("APPLY", A, ok))
    cases = [("no confirm", {}, {}, "CONFIRM_MISSING"),
             ("anchor START", A, {"straighten_record": dict(straight_rec, anchor="START")}, "ANCHOR_NOT_DOCK"),
             ("not saved", A, {"straighten_record": dict(straight_rec, status="started")}, "STRAIGHTEN_NOT_SAVED"),
             ("not straight", A, {"route_straight": False}, "ROUTE_NOT_STRAIGHT"),
             ("moved", A, {"moved_since_capture": ["S02 Mouth Lantern"]}, "MOVED_SINCE_CAPTURE"),
             ("record", A, {"record_exists": True}, "RECORD_EXISTS"),
             ("no capture", A, {"capture": None}, "NO_CAPTURE"),
             ("plan", A, {"plan_refusals": ["UNCLASSIFIED_ROUTE_ACTORS|X"]}, "UNCLASSIFIED"),
             ("bad route", A, {"new_route_bad": "s=0:4cm"}, "NEW_ROUTE_NOT_AS_PREDICTED")]
    for name, args, over, want in cases:
        got = pf.refusals("APPLY", args, dict(ok, **over))
        check(any(want in r for r in got), "gate %s -> %s (got %r)" % (name, want, got))
    other = copy.deepcopy(DRY["spline"])
    other["points"][1]["loc"][1] += 10.0
    got = pf.refusals("APPLY", A, dict(ok, capture={"spline": other}))
    check(any("CAPTURE_IS_NOT_THE_STRAIGHTENED_CURVE" in r for r in got), "capture of another curve refused")
    control(pf.refusals("APPLY", A, dict(ok, capture={"spline": other})) == [], "capture of another curve accepted")
    c = pf.refusals("CAPTURE", {}, {"route_straight": True, "capture_exists": True, "straighten_saved": True})
    check(len(c) == 3, "CAPTURE refuses after the straighten / over an existing capture: %r" % c)
    check(pf.refusals("CAPTURE", {}, {}) == [], "clean CAPTURE")
    r = pf.refusals("REVERT", {"confirm": "REVERT P02FOLLOW"}, {"record": {"status": "saved"}, "drift_vs_after": ["actor:X"]})
    check(any("DRIFT" in x for x in r), "REVERT refuses on drift")
    check(pf.refusals("REVERT", {"confirm": "REVERT P02FOLLOW"}, {"record": {"status": "saved"}, "drift_vs_after": []}) == [],
          "clean REVERT")
    control(pf.refusals("REVERT", {}, {"record": {"status": "saved"}, "drift_vs_after": []}) == [], "REVERT without confirm")
    # plan-level refusals
    actors, items = real_fixture()
    capx = capture_from(OLD, L, actors, items)
    capx["unclassified"] = ["Mystery Prop"]
    capx["sequence"]["foreign_transform_bindings"] = [{"sequence": "/Game/X", "binding": "S02 Mouth Lantern"}]
    pr = pf.plan(capx, lambda s: pf.straight_frame(dock_new_start(OLD, L), s))["refusals"]
    check(any("UNCLASSIFIED" in x for x in pr) and any("UNHANDLED_TRANSFORM_BINDING" in x for x in pr),
          "unclassified actor + foreign transform binding refused: %r" % pr)


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    print("P02_FOLLOWONS_HARNESS|tests=%d|checks=%d|controls=%d|failed=%d"
          % (len(TESTS), CHECKS["n"], CHECKS["controls"], len(CHECKS["failed"])))
    for f in CHECKS["failed"]:
        print("FAILED|" + f)
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
