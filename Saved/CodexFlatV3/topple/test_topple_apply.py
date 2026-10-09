"""Offline harness for the P06 STILL + CHAIN tool (system Python + numpy, no Unreal). Every gate has a failing control.
  python test_topple_apply.py  ->  TOPPLE_HARNESS|tests=..|checks=..|failed=..
Fixture: a P06-like passage shaped on the live DRY (TOPPLE-20261007-022206): 428.57 cm rows every 41143 ticks
(2.5 m/s), 1 s / 250 cm lead-in, every row Slide/ContinuousLoop on the preset undulation curve with offsets that are
integers (rest) or .333 (a held 75 % slide), 10 m x 10 cm cards, 11.2 m x 19.9 cm Flat V3 rows, 13 m x 96.8 cm 3D
fences from row 22. The fake editor implements the C++ phase law (PassageActor.cpp:1378-1475) for the pose probe.
What it CANNOT show: that UE's export_text/import_text/eval/EvaluateMechanismsAtMasterFrame behave like the fake.
"""
import copy
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _load("tc", os.path.join(HERE, "topple_core.py"))
app = _load("ta", os.path.join(HERE, "topple_apply.py"))
mk = _load("mk", os.path.join(HERE, "make_keys.py"))
chain = mk.tc
assert app.unreal is None, "harness must run without Unreal"
SOLVER_DIR = os.path.dirname(mk.SOLVER)

CHECKS = {"n": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def raises(fn, prefix):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001  -- make_keys loads its own copy of core: match by class name
        if type(exc).__name__ != "PlanError":
            raise
        return prefix in str(exc)
    return False


# =====================================================================================================================
# Fixture
# =====================================================================================================================
TICK = 24000.0
GAP = 3000.0 / 7.0                 # 428.571 cm [meas live DRY]
IV = 41143                         # ticks per row [meas live DRY: 65143 - 24000]
LEAD_IN_F, LEAD_IN_CM = 24000, 250.0
N_ROWS_FIX = 32
THICK_3D = (22, 26, 30)


def wave():
    """WriteSmoothUndulationCurve [decl InfinityStageShowAsset.cpp:22-29]."""
    k = dict(core.KEY_DEFAULTS, InterpMode="RCIM_Cubic", TangentMode="RCTM_User")
    pts = [(0.0, 0.0, 0.0), (0.25, 0.5, math.pi), (0.5, 1.0, 0.0), (0.75, 0.5, -math.pi), (1.0, 0.0, 0.0)]
    return [dict(k, Time=t, Value=v, ArriveTangent=a, LeaveTangent=a) for t, v, a in pts]


def geometry(i):
    if i in THICK_3D:
        return 1300.0, 96.8, "/Game/W/SM_FenceTarp"
    if i % 4 == 0:
        return 1120.0, 19.9, "/Game/W/SM_FlatV3_pavilion"
    return 1000.0, 10.0, "/Game/W/SM_Card%02d" % (i % 5)


class FakeShow:
    def __init__(self, n=N_ROWS_FIX):
        self.cues = []
        for i in range(n):
            self.cues.append({
                "CueGuid": ("%08X" % (0xA0000000 + i)) * 4, "Label": "P06 Wing %03d" % ((i * 7) % 61 + 1),
                "WingPair": {"bHasTop": i == 18, "LocalOverrideMask": 0, "GapToNextCm": GAP,
                             "Mechanism": {"Kind": "Slide", "PlaybackMode": "ContinuousLoop", "CycleRateHz": 0.18,
                                           "PhaseOrigin": "PassageStart",
                                           "PhaseOffsetCycles": float(i % 7) if i % 3 == 0 else i % 7 + 1.0 / 3,
                                           "MaxAngleDeg": 90.0, "InwardTravelCm": 75.0,
                                           "L": wave(), "R": wave(), "T": wave(), "bTopFollowsMechanism": True}}})

    @staticmethod
    def curve(keys):
        return core.curve_text(keys) if keys else "(EditorCurveData=(),ExternalCurve=None)"

    def mech_text(self, m):
        return ("(Kind=%s,PlaybackMode=%s,CycleRateHz=%.17g,PhaseOrigin=%s,PhaseOffsetCycles=%.17g,MaxAngleDeg=%.17g,"
                "InwardTravelCm=%.17g,LeftNormalizedCurve=%s,RightNormalizedCurve=%s,TopNormalizedCurve=%s,"
                "bTopFollowsMechanism=%s,CameraGust=(GroupSize=1))") % (
            m["Kind"], m["PlaybackMode"], m["CycleRateHz"], m["PhaseOrigin"], m["PhaseOffsetCycles"], m["MaxAngleDeg"],
            m["InwardTravelCm"], self.curve(m["L"]), self.curve(m["R"]), self.curve(m["T"]),
            "True" if m["bTopFollowsMechanism"] else "False")

    def cue_text(self, c):
        wp = c["WingPair"]
        # Attachments (with their Lighting blocks) only when a test sets them: the default fixture text is unchanged
        att = (",Attachments=(%s)" % ",".join("(Label=\"%s\",Lighting=(Intensity=%.6f,Color=(R=1.0,G=0.8,B=0.6,A=1.0)))"
                                               % (a["Label"], a["Intensity"]) for a in wp["Attachments"])
               if wp.get("Attachments") else "")
        return ('(CueGuid=%s,Label=NSLOCTEXT("", "K%s", "%s, (a \\"quoted\\" label)"),bEnabled=True,'
                "WingPair=(bHasTop=%s,GapToNextCm=%.1f,Mechanism=%s,LocalOverrideMask=%d%s))") % (
            c["CueGuid"], c["CueGuid"][:4], c["Label"], wp["bHasTop"], wp["GapToNextCm"],
            self.mech_text(wp["Mechanism"]), wp["LocalOverrideMask"], att)


ENUM = {"OneShot": "ONE_SHOT", "Static": "STATIC", "ContinuousLoop": "CONTINUOUS_LOOP",
        "PassFrame": "PASS_FRAME", "PassageStart": "PASSAGE_START", "Slide": "SLIDE", "Topple": "TOPPLE"}
FROM_ENUM = {v: k for k, v in ENUM.items()}


def law_fix(n=N_ROWS_FIX):
    return core.route_law(LEAD_IN_F, LEAD_IN_CM, [(IV, GAP)] * n, 2 * IV, 2 * GAP)


class FakeOps:
    def __init__(self, show, here):
        self.show, self.here = show, here
        self.calls, self.logs, self.errors = [], [], []
        self.dirty = {"content": [], "maps": []}
        self.zz = []
        self.lying_setter = False
        self.extra_dirty_on_materialize = None
        self.write_excluded_guid = None  # harness fault: mutate a row the plan explicitly excludes
        self.snapshots = {}
        self.posed = None
        self.restore_also = None      # harness fault: restore_rows also edits "attachment" (a target) or "nontarget"

    def log(self, m):
        self.logs.append(m)

    def log_error(self, m):
        self.errors.append(m)

    def guard_context(self):
        self.calls.append("guard")

    def census(self):
        return copy.deepcopy(self.dirty)

    def zz_actors(self):
        return list(self.zz)

    def _side(self, i, hinge, lat_sign):
        h, t, mesh = geometry(i)
        lo, hi = 430.0, 1000.0
        lat = (lo, hi) if lat_sign > 0 else (-hi, -lo)
        return {"mesh": mesh, "materialized": True, "has_hinge_socket": False, "pivot_local": [0.0, 0.0, 0.0],
                "height_cm": h, "thickness_cm": t, "width_cm": 570.0, "hinge_route_cm": hinge,
                "lateral_min_cm": lat[0], "lateral_max_cm": lat[1], "axis_dot_tangent": 0.0, "upright": True,
                "external_curve": None}

    def measure(self):
        self.calls.append("measure")
        law = law_fix(len(self.show.cues))
        rows = []
        for i, c in enumerate(self.show.cues):
            m = c["WingPair"]["Mechanism"]
            mt = self.show.mech_text(m)
            pf, st = law["stations"][i]
            hinge = st - (6.0 if i % 4 == 0 else 0.0)
            sides = {"L": self._side(i, hinge, -1), "R": self._side(i, hinge, +1)}
            for s in ("L", "R"):
                sides[s].update({"curve_export": self.show.curve(m[s]), "curve_keys": len(m[s]),
                                 "curve_flat": not m[s], "value_at_offset": core.hermite(m[s], m["PhaseOffsetCycles"])})
            rows.append({"ordinal": i, "show_index": i, "cue_guid": c["CueGuid"], "label": c["Label"], "enabled": True,
                         "has_top": c["WingPair"]["bHasTop"], "top_mesh": None,
                         "local_override_mask": c["WingPair"]["LocalOverrideMask"],
                         "curve_at0": {s: core.hermite(m[s], 0.0) for s in ("L", "R", "T")},
                         "mechanism_sha": app._sha(mt + "|mask=%d" % c["WingPair"]["LocalOverrideMask"]),
                         "mechanism_export": mt,
                         "mechanism": {"kind": "<InfinityMechanismKind.%s: 0>" % ENUM[m["Kind"]],
                                       "playback_mode": "<InfinityMotionPlaybackMode.%s: 2>" % ENUM[m["PlaybackMode"]],
                                       "phase_offset_cycles": m["PhaseOffsetCycles"], "top_curve_flat": not m["T"]},
                         "sides": sides, "pass_frame": pf, "station_cm": st})
        return {"passage_guid": core.P06_GUID, "passage_label": core.P06_LABEL, "tick": TICK, "law": law, "rows": rows,
                "modulation": {"section_found": True, "wing_modulation": False, "speed_shaped": False,
                               "longitudinal_offset": False}}

    def mechanism_sounds(self):
        self.calls.append("sounds")
        if getattr(self, "sounds_raise", False):
            raise RuntimeError("boom")
        return [{"ordinal": 0, "label": "Passage 1", "enabled": True, "sound_count": 2, "policy": "STABLE_RANDOM",
                 "non_static_unmuted_rows": 3, "would_sound": True},
                {"ordinal": 1, "label": "Passage 6", "error": "AttributeError: x"}]

    def api_probe(self, text):
        self.calls.append("probe")
        return {"pass": True, "failures": []}

    def cue_texts(self):
        return [self.show.cue_text(c) for c in self.show.cues]

    def _cue(self, g):
        return [c for c in self.show.cues if c["CueGuid"] == g][0]

    def read_row(self, g):
        c = self._cue(g)
        m = c["WingPair"]["Mechanism"]
        mt = self.show.mech_text(m)
        self.snapshots[mt] = copy.deepcopy(m)
        return {"mech_text": mt, "mask": c["WingPair"]["LocalOverrideMask"],
                "kind": "InfinityMechanismKind." + ENUM[m["Kind"]],
                "playback_mode": "InfinityMotionPlaybackMode." + ENUM[m["PlaybackMode"]],
                "phase_origin": "InfinityMotionPhaseOrigin." + ENUM[m["PhaseOrigin"]],
                "cycle_rate_hz": m["CycleRateHz"], "phase_offset_cycles": m["PhaseOffsetCycles"],
                "max_angle_deg": m["MaxAngleDeg"], "top_follows_mechanism": m["bTopFollowsMechanism"],
                "has_top": c["WingPair"]["bHasTop"], "curves": {s: self.show.curve(m[s]) for s in ("L", "R", "T")}}

    def curve_eval(self, g, side, phases):
        keys = self._cue(g)["WingPair"]["Mechanism"][side]
        return [core.hermite(keys, p) for p in phases]

    def write_rows(self, plan_rows, bits):
        self.calls.append("write")
        self.write_saw_originals = os.path.exists(os.path.join(self.here, app.ACTIVE_NAME))
        for row in plan_rows:
            c = self._cue(row["cue_guid"])
            m = c["WingPair"]["Mechanism"]
            s = row["set"]
            m["PlaybackMode"] = FROM_ENUM[s["playback_mode"]]
            m["PhaseOffsetCycles"] = s["phase_offset_cycles"]
            if row["action"] == "chain":
                m.update({"Kind": FROM_ENUM[s["kind"]], "PhaseOrigin": FROM_ENUM[s["phase_origin"]],
                          "CycleRateHz": s["cycle_rate_hz"], "MaxAngleDeg": s["max_angle_deg"]})
                keys = core.parse_curve_keys(row["curve_text"])
                if self.lying_setter:
                    keys = [dict(k, ArriveTangent=0.0, LeaveTangent=0.0) for k in keys]
                m[row["side"]] = keys
                m[row["other_side"]] = core.parse_curve_keys(row["other_curve_text"])
                if s.get("top_follows_mechanism") is False:
                    m["bTopFollowsMechanism"] = False
                c["WingPair"]["LocalOverrideMask"] |= bits
        if self.write_excluded_guid:
            self._cue(self.write_excluded_guid)["WingPair"]["GapToNextCm"] += 1.0
        self.dirty["content"] = sorted(set(self.dirty["content"]) | {core.SHOW_PATH})

    def restore_rows(self, rows):
        self.calls.append("restore")
        for r in rows:
            c = self._cue(r["cue_guid"])
            c["WingPair"]["Mechanism"] = copy.deepcopy(self.snapshots[r["mech_text"]])
            c["WingPair"]["LocalOverrideMask"] = r["mask"]
        if self.restore_also == "attachment":     # a whole-cue restore would do this: put back an old attachment
            c = self._cue(rows[0]["cue_guid"])
            c["WingPair"]["Attachments"] = [{"Label": "Bulb", "Intensity": 1.0}]
        elif self.restore_also == "nontarget":
            targets = {r["cue_guid"] for r in rows}
            c = [x for x in self.show.cues if x["CueGuid"] not in targets][0]
            c["WingPair"]["GapToNextCm"] += 1.0
        self.dirty["content"] = sorted(set(self.dirty["content"]) | {core.SHOW_PATH})

    def materialize(self):
        self.calls.append("materialize")
        self.posed = None
        self.dirty["maps"] = [core.WORLD_PATH]
        if self.extra_dirty_on_materialize:
            self.dirty["content"].append(self.extra_dirty_on_materialize)
        return True

    def materialized_pivots(self, guids, side):
        return {g: [[0.0, 0.0, 0.0]] for g in guids}

    # ---- the C++ law, for the pose probe
    def _panel_state(self, i, c, side, frame):
        m = c["WingPair"]["Mechanism"]
        if frame is None:
            return {"dev_cm": 0.0, "tilt_deg": 0.0, "top_route_shift_cm": 0.0}
        law = law_fix(len(self.show.cues))
        origin = law["stations"][i][0] if m["PhaseOrigin"] == "PassFrame" else 0
        ph = m["PhaseOffsetCycles"] + (frame - origin) / TICK * m["CycleRateHz"]
        if m["PlaybackMode"] == "Static":
            ph = m["PhaseOffsetCycles"]
        elif m["PlaybackMode"] == "OneShot":
            ph = min(1.0, max(0.0, ph))
        else:
            ph -= math.floor(ph)
        if side == "T":
            curve = None if not m["bTopFollowsMechanism"] else (m["T"] or m["L"])
        else:
            curve = m[side]
        v = core.hermite(curve, ph) if curve else 0.0
        if m["Kind"] == "Topple" and side != "T":
            ang = v * m["MaxAngleDeg"]
            h = geometry(i)[0]
            return {"dev_cm": abs(h * math.sin(math.radians(ang))), "tilt_deg": abs(ang),
                    "top_route_shift_cm": -h * math.sin(math.radians(ang))}
        return {"dev_cm": abs(v * m["InwardTravelCm"]), "tilt_deg": 0.0, "top_route_shift_cm": 0.0}

    def instance_state(self, guids):
        out = {}
        for i, c in enumerate(self.show.cues):
            if c["CueGuid"] not in guids:
                continue
            for side in ("L", "R") + (("T",) if c["WingPair"]["bHasTop"] else ()):
                out["%s|%s" % (c["CueGuid"], side)] = self._panel_state(i, c, side, self.posed)
        return out

    def pose_probe(self, guids, frames):
        self.calls.append("pose_probe")
        seg = law_fix(len(self.show.cues))["segment_end"]
        out = {}
        for f in frames:
            self.posed = f
            out[str(int(f))] = {"evaluated": 0 <= f <= seg, "panels": self.instance_state(guids)}
        return out

    def backup(self, name):
        self.calls.append("backup")
        return os.path.join(self.here, "Backups", name), ["show.uasset", "level.umap"]

    def save_show(self):
        self.calls.append("save_show")
        self.dirty["content"] = [p for p in self.dirty["content"] if p != core.SHOW_PATH]
        return True

    def save_level(self):
        self.calls.append("save_level")
        self.dirty["maps"] = []
        return True


SUNSET = [{"t": t, "daylight": d} for t, d in ((0, 1.0), (22, 1.0), (26, 0.949), (30, 0.822), (34, 0.647),
                                                (38, 0.451), (42, 0.261), (46, 0.107), (50, 0.014), (54, 0.0))]
SLAM = 25.3


def fresh(tag):
    return tempfile.mkdtemp(prefix=tag), FakeShow()


def dry_and_plan(here, show, **kw):
    ops = FakeOps(show, here)
    meas = app.run_dry(ops, core, {"mode": "DRY"}, "TESTDRY", here)
    args = dict(slam_s=SLAM, sunset=SUNSET)
    args.update(kw)
    plan = mk.build(meas, **args)
    with open(os.path.join(here, app.PLAN_NAME), "w") as fh:
        json.dump(plan, fh)
    return ops, meas, plan


def _apply(here, show, ops=None, args=None, run="TESTAPPLY", plan=None):
    plan = plan or json.load(open(os.path.join(here, app.PLAN_NAME)))
    ops = ops or FakeOps(show, here)
    a = {"mode": "APPLY", "confirm": "APPLY TOPPLE " + plan["confirm_token"], "decided_by": "harness"}
    a.update(args or {})
    core.validate_args(a, plan)
    return ops, app.run_apply(ops, core, a, plan, run, here)


# =====================================================================================================================
# Tests
# =====================================================================================================================

@test
def t_struct_text():
    t = '(A=1,B=(C=2,D=(E=3)),Label=NSLOCTEXT("", "k", "x, (y) \\"z\\""),F=((G=1),(G=2)))'
    check([k for k, _ in core.fields(t)] == ["A", "B", "Label", "F"], "top-level names")
    check(core.get_field(core.get_field(t, "B"), "D") == "(E=3)", "nested get")
    check([v for _, v in core.fields(core.get_field(t, "F"))] == ["(G=1)", "(G=2)"], "array items")
    check(raises(lambda: core.fields("(A=(1)"), "STRUCT_TEXT"), "-control unbalanced text refused")
    check(raises(lambda: core.replace_field(t, "Nope", "1"), "FIELD_MISSING"), "-control replace missing field")
    show = FakeShow()
    a = show.cue_text(show.cues[3])
    show.cues[3]["WingPair"]["Mechanism"]["CycleRateHz"] = 9.0
    show.cues[3]["WingPair"]["LocalOverrideMask"] = 12
    b = show.cue_text(show.cues[3])
    check(a != b and core.cue_text_outside_mechanism(a) == core.cue_text_outside_mechanism(b),
          "+control mechanism/mask change invisible outside the mechanism")
    show.cues[3]["WingPair"]["GapToNextCm"] = 1.0
    check(core.cue_text_outside_mechanism(b) != core.cue_text_outside_mechanism(show.cue_text(show.cues[3])),
          "-control a WingPair field outside Mechanism is visible")
    m = show.mech_text(show.cues[3]["WingPair"]["Mechanism"])
    m2 = m.replace("PhaseOffsetCycles=", "PhaseOffsetCycles=9")
    check(core.mechanism_outside_planned(m, "still") == core.mechanism_outside_planned(m2, "still"),
          "+control still blanks the offset")
    m3 = m.replace("InwardTravelCm=75", "InwardTravelCm=76")
    check(core.mechanism_outside_planned(m, "still") != core.mechanism_outside_planned(m3, "still"),
          "-control still sees an InwardTravel change")
    m4 = m.replace("Kind=Slide", "Kind=Topple")
    check(core.mechanism_outside_planned(m, "still") != core.mechanism_outside_planned(m4, "still"),
          "-control still sees a Kind change")


@test
def t_curve_text():
    keys = core.plan_keys(core.PROBE_SOLVER_KEYS)
    check([k["TangentMode"] for k in keys][-1] == "RCTM_User" and keys[0]["TangentMode"] == "RCTM_Break",
          "break where arrive != leave, user where equal")
    check(core.keys_match(keys, core.parse_curve_keys(core.curve_text(keys))) == [], "curve text round trip")
    live = ("(EditorCurveData=(Keys=((InterpMode=RCIM_Cubic,TangentMode=RCTM_User),(InterpMode=RCIM_Cubic,"
            "TangentMode=RCTM_User,Time=0.250000,Value=0.500000,ArriveTangent=3.141593,LeaveTangent=3.141593),"
            "(InterpMode=RCIM_Cubic,TangentMode=RCTM_User,Time=0.500000,Value=1.000000)),"
            "DefaultValue=340282346638528859811704183484516925440.000000,PreInfinityExtrap=RCCE_Constant,"
            "PostInfinityExtrap=RCCE_Constant),ExternalCurve=None)")   # shape of the live export, 7 Oct DRY
    p = core.parse_curve_keys(live)
    check(len(p) == 3 and p[0]["Time"] == 0.0 and p[0]["Value"] == 0.0 and abs(p[1]["ArriveTangent"] - 3.141593) < 1e-9,
          "live export shape parsed (delta fields default)")
    check(core.external_curve(live) is None, "ExternalCurve None")
    fk = core.flat_keys()
    check(all(core.hermite(fk, t / 10) == 0.0 for t in range(-2, 13)), "flat keys evaluate 0 everywhere")
    bad = core.parse_curve_keys(core.curve_text(keys))
    bad[2]["LeaveTangent"] += 0.01
    check(core.keys_match(keys, bad) != [], "-control tangent drift caught")
    check(raises(lambda: core.plan_keys(core.PROBE_SOLVER_KEYS[1:]), "KEYS_MUST_SPAN"), "-control keys not from 0")


@test
def t_hermite_equals_solver():
    import numpy as np
    keys = core.plan_keys(core.PROBE_SOLVER_KEYS)
    tup = [(k["Time"], k["Value"], k["ArriveTangent"], k["LeaveTangent"]) for k in keys]
    ph = np.array(core.sample_phases(keys))
    ref = chain.ts.hermite_eval(tup, ph)
    err = max(abs(core.hermite(keys, float(p)) - float(r)) for p, r in zip(ph, ref))
    check(err < 1e-12, "core.hermite == topple_solver.hermite_eval (%.2e)" % err)


@test
def t_chain_solver():
    r = chain.run_chain([10.0] * 4, [0.0, 4.6, 9.2, 13.8], [0.15] * 4)
    ref = json.load(open(os.path.join(SOLVER_DIR, "variant_C_chain4_away.json")))
    got, want = [x["CycleRateHz"] for x in r["rows"]], [x["CycleRateHz"] for x in ref["rows"]]
    check(all(abs(a - b) < 2e-6 for a, b in zip(got, want)), "+control 4 equal slabs == 7 Oct variant C %r" % got)
    h, x, t = [11.2, 10, 10, 10, 11.2, 10], [0, 4.2857, 8.5714, 12.857, 17.137, 21.4286], [.199, .1, .1, .1, .199, .1]
    b = chain.run_chain(h, x, t, {"hinge_m": 25.765, "thickness_m": 0.968})
    check(b["final_impact_type"] == "wall" and len(b["rows"]) == 6, "braced 6: final impact on the brace")
    check(abs(b["rows"][-1]["final_deg"] - b["contact_deg"][-1]) < 0.5, "last slab rests at its brace contact angle")
    check(all(a["final_deg"] > c["final_deg"] for a, c in zip(b["rows"][:-1], b["rows"][1:])),
          "leaners form a falling staircase toward the brace")
    f = chain.run_chain(h, x, t, None)
    check(f["final_impact_type"] == "floor" and abs(f["rows"][-1]["final_deg"] - 90.0) < 1e-6, "floor end lies flat")
    x2 = list(x)
    x2[3] += 0.3
    f2 = chain.run_chain(h, x2, t, None)
    check(abs(f2["contact_deg"][2] - f["contact_deg"][2]) > 0.5, "-control a gap change moves that contact angle")
    check(all(k["fit_max_err_deg"] < 0.5 for k in b["rows"] + f["rows"]), "fits within 0.5 deg")


@test
def t_route_law_and_timing():
    law = law_fix(5)
    check(law["stations"][0] == (LEAD_IN_F, LEAD_IN_CM), "first station = lead-in")
    check(abs(core.speed_at_distance(law, 600.0, TICK) - 2.5) < 1e-3, "speed 2.5 m/s")
    for d in (0.0, 250.0, 1000.0, 1460.0):
        check(abs(core.distance_at_frame(law, core.frame_at_distance(law, d)) - d) < 1e-6, "inverse at %.0f" % d)
    check(raises(lambda: core.frame_at_distance(law, 99999.0), "DISTANCE_PAST"), "-control past end")
    check(abs(core.daylight_at(SUNSET, 28.0) - 0.8855) < 1e-3 and core.daylight_at(SUNSET, 60) == 0.0, "daylight interp")


@test
def t_eligibility_and_still():
    here, show = fresh("tp_elig")
    rows = FakeOps(show, here).measure()["rows"]
    check(core.side_reasons(rows[3], "L") == [], "+control a LOOPING thin card is eligible now (STILL stops it)")
    check(any("TOO_THICK" in r for r in core.side_reasons(rows[22], "L")), "-control 96.8 cm 3D fence refused")
    check(any("KEEPER" in r for r in core.side_reasons(rows[27], "L", rows[27]["cue_guid"])), "-control keeper refused")
    w = core.window_report(rows, 16, "L", 6)
    check(not w["refusals"] and w["brace"]["label"] == rows[22]["label"] and w["brace"]["reached"]
          and not w["brace"].get("problem"), "+control rows 16-21 braced by the row-22 fence: %s" % w["refusals"])
    check([h["cue_guid"] for h in w["floor_end_hits"]] == [rows[22]["cue_guid"], rows[23]["cue_guid"]],
          "floor end would lie through rows 22 and 23")
    check(any("TOO_THICK" in x for x in core.window_report(rows, 17, "L", 6)["refusals"]), "-control window over the fence")
    rr = copy.deepcopy(rows)
    rr[22]["sides"]["L"]["height_cm"] = 500.0
    check("PASSES_OVER" in (core.window_report(rr, 16, "L", 6)["brace"].get("problem") or ""),
          "-control a brace lower than the contact point")
    rr = copy.deepcopy(rows)
    rr[18]["sides"]["L"]["lateral_min_cm"], rr[18]["sides"]["L"]["lateral_max_cm"] = -3000.0, -2500.0
    check(any("LATERAL_OVERLAP" in x for x in core.window_report(rr, 16, "L", 6)["refusals"]), "-control lateral gap")
    ok, counts = core.eligible_windows(rows, 6)
    check(len(ok) == 34 and all(w["start_ordinal"] <= 16 for w in ok), "34 windows, none past the fences: %d" % len(ok))
    keeper = core.default_keeper(rows, TICK)
    check(keeper is not None and keeper["ordinal"] == 27, "default keeper = deepest thin moving row lit: %s" % (
        keeper and keeper["ordinal"]))
    plan, ref = core.still_plan(rows, keeper["cue_guid"], set())
    acts = {p["action"] for p in plan}
    check(not ref and acts == {"still", "keep"}, "+control every row still except the keeper: %s %s" % (acts, ref))
    r = copy.deepcopy(rows[1])
    r["mechanism"]["playback_mode"] = "<InfinityMotionPlaybackMode.STATIC: 0>"
    check(not core.at_rest_now(r), "-control Static with offset 1.333 is NOT rest (held 75 %% slide)")
    r["mechanism"]["phase_offset_cycles"] = 0.0
    check(core.at_rest_now(r), "+control Static + offset 0 + curve(0)=0 is rest")
    rr = copy.deepcopy(rows)
    rr[5]["curve_at0"]["R"] = 0.4
    check(any("STILL_CURVE_NOT_ZERO" in x for x in core.still_plan(rr, None, set())[1]), "-control curve(0) != 0 refused")
    check(core.daylight_at([], 3) is None, "no sunset -> None")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_args():
    pd = {"confirm_token": "P06 still+chain L AAAA..BBBB #12345678", "gates_ok": True, "chain": {"next_row_hits": []}}
    check(core.validate_args({"mode": "DRY", "confirm": "DRY TOPPLE P06"}) == "DRY", "+control DRY")
    ok = {"mode": "APPLY", "confirm": "APPLY TOPPLE " + pd["confirm_token"], "decided_by": "Gary 7 Oct"}
    check(core.validate_args(ok, pd) == "APPLY", "+control APPLY")
    check(raises(lambda: core.validate_args(dict(ok, decided_by=""), pd), "NOT_DECIDED"), "-control undecided")
    check(raises(lambda: core.validate_args(dict(ok, confirm="APPLY TOPPLE P06"), pd), "CONFIRM_MISMATCH"),
          "-control confirm lacks the token")
    check(raises(lambda: core.validate_args(ok, dict(pd, gates_ok=False)), "PLAN_GATES_FAILED"), "-control gates failed")
    hit = dict(pd, chain={"next_row_hits": [{"x": 1}]})
    check(raises(lambda: core.validate_args(ok, hit), "NEXT_ROW_INTERSECTION_NOT_ACKED"), "-control floor hit not acked")
    check(core.validate_args(dict(ok, ack_next_row_intersection=True), hit) == "APPLY", "+control acknowledged")
    check(raises(lambda: core.validate_args({"mode": "REVERT", "confirm": "REVERT TOPPLE X"}), "REVERT_NEEDS"),
          "-control REVERT without originals")


@test
def t_make_plan():
    here, show = fresh("tp_mk")
    ops, meas, plan = dry_and_plan(here, show)
    c = plan["chain"]
    tm = c["timing"]
    check(plan["gates_ok"] and not plan["refusals"], "gates ok: %s" % plan["refusals"])
    check(c["start_ordinal"] == 16 and c["end"] == "braced" and len(c["rows"]) == 6, "window 16-21 braced, 6 rows")
    check(abs(tm["final_impact_s"] - SLAM) < 1e-6 and tm["final_impact_type"] == "wall", "final impact at --slam-s")
    check(2500.0 <= tm["lead_cm_at_creak"] <= 3500.0, "lead in range: %.0f" % tm["lead_cm_at_creak"])
    check(tm.get("daylight_at_final_impact") is not None and tm["frame_share_at_final_impact"] > 0.1,
          "daylight + frame share reported: %s %s" % (tm.get("daylight_at_final_impact"), tm["frame_share_at_final_impact"]))
    for r in tm["rows"]:
        f0 = tm["creak_frame_rel"] + r["start_s"] * TICK
        f1 = f0 + r["duration_s"] * TICK
        p0 = r["PhaseOffsetCycles"] + (f0 - r["pass_frame_rel"]) / TICK * r["CycleRateHz"]
        p1 = r["PhaseOffsetCycles"] + (f1 - r["pass_frame_rel"]) / TICK * r["CycleRateHz"]
        check(abs(p0) < 1e-9 and abs(p1 - 1.0) < 5e-5, "C++ phase law reproduces the solver: %.2e %.6f" % (p0, p1))
    cr = c["rows"][0]
    check(cr["set"]["max_angle_deg"] == -90.0 and cr["set"]["phase_origin"] == "PASS_FRAME", "away + PassFrame")
    check(core.keys_match(core.flat_keys(), core.parse_curve_keys(cr["other_curve_text"])) == [], "other side zero curve")
    sc = plan["still_counts"]
    check(sc["keep"] == 1 and sc["chain"] == 6 and sc["still"] + sc["already_still"] == N_ROWS_FIX - 7, "still counts %s" % sc)
    check(core.inputs_hash(plan["inputs"]) == plan["inputs_hash"], "hash self-consistent")
    p37 = mk.build(meas, slam_s=37.0)
    check(any("NO_WINDOW_FOR_SLAM" in r for r in p37["refusals"]) and not p37["gates_ok"],
          "-control slam 37 s: no window (the 3D fences block rows 22+)")
    check(any(r.get("final_impact_s_at_mid_lead") for r in p37["window_table"]), "table offers the mid-lead slam times")
    ps = mk.build(meas, parts=("still",))
    check(ps["chain"] is None and ps["gates_ok"] and ps["still_counts"]["chain"] == 0, "STILL-only plan")
    check(ps["confirm_token"].startswith("P06 still #"), "STILL-only token: %s" % ps["confirm_token"])
    pf = mk.build(meas, slam_s=SLAM + 0.5, end="floor", candidate=16, side="L")
    check(pf["chain"]["next_row_hits"] and pf["chain"]["timing"]["final_impact_type"] == "floor",
          "floor end lists its hits (needs ack)")
    m2 = copy.deepcopy(meas)
    m2["modulation"]["wing_modulation"] = ["Wing.CycleRateScale"]
    check(any("WING_MODULATION" in r for r in mk.build(m2, slam_s=SLAM)["refusals"]), "-control wing modulation")
    m2 = copy.deepcopy(meas)
    m2["api_probe"] = {"pass": False, "failures": ["CURVE_ROUNDTRIP"]}
    check(raises(lambda: mk.build(m2, slam_s=SLAM), "API_PROBE_NOT_PASSED"), "-control failed API probe")
    check(raises(lambda: mk.build(meas, slam_s=SLAM, lead_cm=3000.0), "GIVE_ONE_OF"), "-control both timings")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_excluded_rows_plan_dry_apply():
    """Chain-B record excludes its R side as a whole row; A neither stills nor chains it and fingerprints it."""
    here, show = fresh("tp_exclude")
    excluded_guid = show.cues[2]["CueGuid"]
    record_path = os.path.join(here, "chain_b_apply.json")
    with open(record_path, "w", encoding="utf-8") as fh:
        json.dump({"rows": [{"cue_guid": excluded_guid, "side": "R"}]}, fh)
    dry_ops = FakeOps(show, here)
    meas = app.run_dry(dry_ops, core, {"mode": "DRY", "exclude_from_record": record_path}, "EXDRY", here)
    check(meas["exclude_rows"] == [excluded_guid] and meas["excluded_rows"][0]["requested_sides"] == ["R"],
          "+control excluded whole row is listed in DRY with chain-B side provenance")
    check(meas["still_preview"]["counts"]["exclude"] == 1 and
          any("excluded=['P06 Wing 015:A0000002']" in x for x in dry_ops.logs),
          "DRY preview/log explicitly lists one excluded row")
    plan = mk.build(meas, slam_s=SLAM, sunset=SUNSET, exclude_from_record=record_path, exclude_base_dir=here)
    carried = mk.build(meas, slam_s=SLAM, sunset=SUNSET)
    check(carried["exclude_rows"] == [excluded_guid] and carried["inputs_hash"] == plan["inputs_hash"],
          "make_keys carries the exclusions listed by DRY when no exclusion args are repeated")
    with open(os.path.join(here, app.PLAN_NAME), "w", encoding="utf-8") as fh:
        json.dump(plan, fh)
    check(plan["exclude_rows"] == [excluded_guid] and plan["inputs"]["exclude_rows"] == [excluded_guid],
          "plan and signed inputs carry the canonical exclude list")
    check([x["action"] for x in plan["still"] if x["cue_guid"] == excluded_guid] == ["exclude"],
          "excluded row is neither STILL nor chain")
    before = show.cue_text(show.cues[2])
    ops, _ = _apply(here, show, args={"exclude_from_record": record_path}, plan=plan, run="EXAPPLY")
    check(show.cue_text(show.cues[2]) == before, "+control excluded row untouched by APPLY")
    originals = json.load(open(json.load(open(os.path.join(here, app.ACTIVE_NAME)))["originals"]))
    check(excluded_guid not in {r["cue_guid"] for r in originals["rows"]}, "excluded row absent from originals/write set")
    rec = json.load(open(os.path.join(here, "topple_apply_EXAPPLY.json")))
    fps = rec["excluded_row_fingerprints"]
    check(fps["before"] == fps["after_write"] == fps["before_save"] == fps["after_save"] and
          excluded_guid in fps["before"],
          "excluded full-cue fingerprint unchanged after write, pre-save and post-save read-back")
    check(any("excluded=1 fingerprint=unchanged" in x for x in ops.logs if "_APPLY_OK" in x),
          "APPLY_OK reports excluded fingerprint success")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_excluded_rows_controls():
    here, show = fresh("tp_exclude_controls")
    _, meas, legacy = dry_and_plan(here, show)
    explicit_empty = mk.build(meas, slam_s=SLAM, sunset=SUNSET, exclude_rows=[])
    explicit_empty["made"] = legacy["made"]  # isolate the payload from its wall-clock provenance field
    check(json.dumps(explicit_empty, separators=(",", ":")) == json.dumps(legacy, separators=(",", ":")),
          "+control legacy run and explicit empty excludes produce byte-identical plan JSON")
    safe_guid = show.cues[2]["CueGuid"]
    excluded = mk.build(meas, slam_s=SLAM, sunset=SUNSET, exclude_rows=[safe_guid])
    check(excluded["inputs_hash"] != legacy["inputs_hash"] and
          excluded["confirm_token"] != legacy["confirm_token"],
          "+control exclude list changes the plan digest and confirm token")
    chain_guid = legacy["chain"]["rows"][0]["cue_guid"]
    keeper_guid = legacy["keeper"]["cue_guid"]
    check(raises(lambda: mk.build(meas, slam_s=SLAM, sunset=SUNSET, exclude_rows=[chain_guid]),
                 "EXCLUDED_ROW_CONFLICT"), "-control chain-A window/exclude conflict refused")
    check(raises(lambda: mk.build(meas, slam_s=SLAM, sunset=SUNSET, exclude_rows=[keeper_guid]),
                 "EXCLUDED_ROW_CONFLICT"), "-control keeper/exclude conflict refused")
    check(raises(lambda: mk.build(meas, slam_s=SLAM, sunset=SUNSET,
                                 exclude_rows=["FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"]),
                 "EXCLUDED_ROW_UNKNOWN"), "-control unknown excluded GUID refused")
    bad_record = os.path.join(here, "bad_chain_b.json")
    with open(bad_record, "w", encoding="utf-8") as fh:
        json.dump({"rows": [{"cue_guid": safe_guid, "side": "TOP"}]}, fh)
    check(raises(lambda: core.resolve_exclusions(None, bad_record, here), "EXCLUDED_ROW_SIDE_INVALID"),
          "-control chain-B record side outside L/R refused")
    with open(os.path.join(here, app.PLAN_NAME), "w", encoding="utf-8") as fh:
        json.dump(excluded, fh)
    mismatch_ops = FakeOps(show, here)
    check(raises(lambda: _apply(here, show, mismatch_ops, args={"exclude_rows": []}, plan=excluded,
                                run="EXMISMATCH"), "EXCLUDED_ROWS_MISMATCH"),
          "-control APPLY exclusion args must match the signed plan")
    check("write" not in mismatch_ops.calls and "backup" not in mismatch_ops.calls,
          "APPLY exclusion mismatch stops before backup or write")
    ops = FakeOps(show, here)
    ops.write_excluded_guid = safe_guid
    check(raises(lambda: _apply(here, show, ops, args={"exclude_rows": [safe_guid]}, plan=excluded,
                                run="EXFAULT"), "READBACK_FAILED"),
          "-control an excluded-row write is caught before save")
    check(any("EXCLUDED_ROW_CHANGED" in x for x in ops.errors) and "save_show" not in ops.calls,
          "excluded-row fingerprint names the fault and nothing is saved")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_dry_guards():
    here, show = fresh("tp_dry")
    ops = FakeOps(show, here)
    ops.dirty = {"content": ["/Game/Other/Stream"], "maps": []}
    check(raises(lambda: app.run_dry(ops, core, {}, "D1", here), "DIRTY_CENSUS"), "-control DRY refuses a dirty census")
    check("measure" not in ops.calls and "sounds" not in ops.calls, "nothing read when refused")
    ops = FakeOps(show, here)
    ops.measure = lambda: (_ for _ in ()).throw(core.PlanError("MEASURE_BLEW_UP"))
    check(raises(lambda: app.run_dry(ops, core, {}, "D0", here), "MEASURE_BLEW_UP"), "measure failure propagates")
    sp = os.path.join(here, "topple_mechanism_sounds_D0.json")
    check(os.path.exists(sp) and json.load(open(sp))["passages"][0]["would_sound"] is True,
          "+control mechanism-sound file written FIRST, even when the P06 measurement then fails")
    check(any("_MECHSOUND|run=D0|passage=Passage 6" in m and "error=" in m for m in ops.logs),
          "a per-Passage read error is logged, not swallowed")
    ops = FakeOps(show, here)
    ops.sounds_raise = True
    app.run_dry(ops, core, {}, "D1b", here)
    d = json.load(open(os.path.join(here, "topple_mechanism_sounds_D1b.json")))
    check(d["ok"] is False and "boom" in d["error"], "-control whole sound read failing is recorded, DRY continues")
    ops = FakeOps(show, here)
    app.run_dry(ops, core, {}, "D2", here)
    m = json.load(open(os.path.join(here, app.MEAS_NAME)))
    check(list(m.keys())[0] == "mechanism_sounds", "mechanism sounds are the first block of the DRY output")
    check(m["proposed_keeper"]["ordinal"] == 27 and m["eligible_windows"] == 34, "DRY proposes keeper + windows")
    check(any("_DRY_OK|run=D2" in x for x in ops.logs), "+control DRY_OK run-id marker")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_apply_positive_and_revert():
    here, show = fresh("tp_apply")
    _, meas, plan = dry_and_plan(here, show)
    before = [show.cue_text(c) for c in show.cues]
    keeper = plan["keeper"]["cue_guid"]
    keeper_before = copy.deepcopy(next(c for c in show.cues if c["CueGuid"] == keeper))
    ops, after = _apply(here, show)
    c = ops.calls
    check(c.index("backup") < c.index("write") and ops.write_saw_originals, "backup + originals BEFORE the first write")
    check(c.index("write") < c.index("materialize") < c.index("pose_probe") < c.index("save_show") < c.index("save_level"),
          "order write, materialize, pose probe, (re)materialize, save Show, save level: %r" % c)
    check(c.count("materialize") == 2, "re-materialized after the pose probe")
    check(any("_APPLY_OK|run=TESTAPPLY|parts=still+chain" in m for m in ops.logs) and not ops.errors,
          "+control APPLY_OK marker: %s" % ops.errors)
    chain_g = {r["cue_guid"]: r for r in plan["chain"]["rows"]}
    for x in show.cues:
        m = x["WingPair"]["Mechanism"]
        if x["CueGuid"] == keeper:
            check(x == keeper_before, "keeper untouched (keeps its loop)")
        elif x["CueGuid"] in chain_g:
            r = chain_g[x["CueGuid"]]
            check(m["Kind"] == "Topple" and m["PlaybackMode"] == "OneShot" and m["PhaseOrigin"] == "PassFrame",
                  "chain row fields")
            check(all(core.hermite(m[r["other_side"]], t / 10) == 0 for t in range(11)), "chain other side zeroed")
        else:
            check(m["PlaybackMode"] == "Static" and m["PhaseOffsetCycles"] == 0.0 and m["Kind"] == "Slide",
                  "still row: Static, offset 0, Kind untouched")
    orig = json.load(open(json.load(open(os.path.join(here, app.ACTIVE_NAME)))["originals"]))
    check(len(orig["rows"]) == N_ROWS_FIX - 1, "originals hold every written row (all but the keeper)")
    rec = json.load(open(os.path.join(here, "topple_apply_TESTAPPLY.json")))
    check(rec["pose_probe"] and all(v["evaluated"] for v in rec["pose_probe"].values()), "pose probe recorded")
    check(raises(lambda: _apply(here, show, run="TESTAPPLY2"), "UNREVERTED_APPLY_EXISTS"), "-control second APPLY")
    ops2 = FakeOps(show, here)
    ops2.snapshots = ops.snapshots
    core.validate_args({"mode": "REVERT", "confirm": "REVERT TOPPLE TESTAPPLY"}, None, orig)
    app.run_revert(ops2, core, {}, orig, "TESTREVERT", here)
    check([show.cue_text(x) for x in show.cues] == before, "+control REVERT restores every cue text exactly")
    check(not os.path.exists(os.path.join(here, app.ACTIVE_NAME)), "originals retired")
    check(any("_REVERT_OK|run=TESTREVERT" in m for m in ops2.logs), "REVERT_OK marker")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_apply_still_only():
    here, show = fresh("tp_still")
    ops = FakeOps(show, here)
    meas = app.run_dry(ops, core, {}, "SD", here)
    plan = mk.build(meas, parts=("still",))
    ops, _ = _apply(here, show, plan=plan, run="STILLONLY")
    check(any("_APPLY_OK|run=STILLONLY|parts=still|" in m for m in ops.logs), "+control STILL-only APPLY: %s" % ops.errors)
    moving = [x["CueGuid"] for x in show.cues if x["WingPair"]["Mechanism"]["PlaybackMode"] != "Static"]
    check(moving == [plan["keeper"]["cue_guid"]], "only the keeper still moves")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_apply_negatives():
    here, show = fresh("tp_neg")
    _, meas, plan = dry_and_plan(here, show)
    g = plan["still"][2]["cue_guid"]
    tgt = next(x for x in show.cues if x["CueGuid"] == g)
    tgt["WingPair"]["Mechanism"]["InwardTravelCm"] = 55.0
    ops = FakeOps(show, here)
    check(raises(lambda: _apply(here, show, ops), "PLAN_STALE"), "-control a STILL row edited after DRY -> stale")
    check("write" not in ops.calls and "backup" not in ops.calls, "stale: nothing backed up or written")
    tgt["WingPair"]["Mechanism"]["InwardTravelCm"] = 75.0
    ops = FakeOps(show, here)
    ops.dirty = {"content": [], "maps": [core.WORLD_PATH]}
    check(raises(lambda: _apply(here, show, ops), "DIRTY_CENSUS"), "-control another stream's dirty level")
    ops = FakeOps(show, here)
    ops.zz = ["ZZ_Bench"]
    check(raises(lambda: _apply(here, show, ops), "ZZ_OR_TEMP"), "-control ZZ_ actor")
    before = [show.cue_text(c) for c in show.cues]
    ops = FakeOps(show, here)
    ops.lying_setter = True
    check(raises(lambda: _apply(here, show, ops, run="LIE"), "READBACK_FAILED"), "-control lying setter caught")
    check("save_show" not in ops.calls and [show.cue_text(c) for c in show.cues] == before,
          "lying setter: restored in memory, nothing saved")
    os.remove(os.path.join(here, app.ACTIVE_NAME))   # the documented manual step after a Don't-Save relaunch
    # a STILL plan that would hold a pose: offset 0.333 passes the field read-back but not the pose probe
    bad = copy.deepcopy(plan)
    for x in bad["still"]:
        if x["action"] == "still":
            x["set"]["phase_offset_cycles"] = 1.0 / 3
    ops = FakeOps(show, here)
    check(raises(lambda: _apply(here, show, ops, run="POSE", plan=bad), "NOT_AT_REST"),
          "-control pose probe catches a STILL row held off rest")
    check("save_show" not in ops.calls, "pose failure: nothing saved")
    for x in show.cues:   # undo the in-memory write (stands in for the Don't-Save relaunch)
        pass
    show.__init__()
    os.remove(os.path.join(here, app.ACTIVE_NAME))
    flip = copy.deepcopy(plan)
    for r in flip["chain"]["rows"]:
        r["set"]["max_angle_deg"] = 90.0
    ops = FakeOps(show, here)
    check(raises(lambda: _apply(here, show, ops, run="FLIP", plan=flip), "CHAIN_FELL_TOWARD_CAMERA"),
          "-control pose probe catches a chain falling toward the camera")
    show.__init__()
    os.remove(os.path.join(here, app.ACTIVE_NAME))
    ops = FakeOps(show, here)
    ops.extra_dirty_on_materialize = "/Game/Someone/Else"
    check(raises(lambda: _apply(here, show, ops, run="SCOPE"), "DIRTY_SCOPE"), "-control foreign package dirtied")
    check("save_show" not in ops.calls, "dirty scope: nothing saved")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_revert_drift():
    here, show = fresh("tp_drift")
    dry_and_plan(here, show)
    ops, _ = _apply(here, show, run="DRIFTAPPLY")
    plan = json.load(open(os.path.join(here, app.PLAN_NAME)))
    g = plan["chain"]["rows"][0]["cue_guid"]
    next(x for x in show.cues if x["CueGuid"] == g)["WingPair"]["Mechanism"]["CycleRateHz"] = 0.5
    orig = json.load(open(json.load(open(os.path.join(here, app.ACTIVE_NAME)))["originals"]))
    ops2 = FakeOps(show, here)
    ops2.snapshots = ops.snapshots
    check(raises(lambda: app.run_revert(ops2, core, {}, orig, "R", here), "DRIFT_SINCE_APPLY"),
          "-control REVERT refuses a row edited after APPLY")
    check("restore" not in ops2.calls, "drift: nothing restored")
    shutil.rmtree(here, ignore_errors=True)


def _applied_with_foreign_edits(tag, run):
    """APPLY, then another stream's edits between APPLY and REVERT (what happened 7 Oct 08:0x-08:29): light
    intensities on a target and on the keeper, a new bulb fixture Attachment on a chain row, and a reorder of two
    cues (a relayout moves rows; REVERT must find targets by CueGuid)."""
    here, show = fresh(tag)
    dry_and_plan(here, show)
    ops, _ = _apply(here, show, run=run)
    plan = json.load(open(os.path.join(here, app.PLAN_NAME)))
    keeper = plan["keeper"]["cue_guid"]
    still_g = [x["cue_guid"] for x in plan["still"] if x["action"] == "still"][3]
    chain_g = plan["chain"]["rows"][1]["cue_guid"]
    cue = lambda g: next(x for x in show.cues if x["CueGuid"] == g)
    cue(still_g)["WingPair"]["Attachments"] = [{"Label": "Bulb", "Intensity": 7.5}]
    cue(keeper)["WingPair"]["Attachments"] = [{"Label": "Bulb", "Intensity": 3.25}]
    cue(chain_g)["WingPair"]["Attachments"] = [{"Label": "MeshyBulbFixture", "Intensity": 0.0}]
    show.cues[0], show.cues[1] = show.cues[1], show.cues[0]
    orig = json.load(open(json.load(open(os.path.join(here, app.ACTIVE_NAME)))["originals"]))
    ops2 = FakeOps(show, here)
    ops2.snapshots = ops.snapshots
    return here, show, plan, orig, ops2, {"still": still_g, "chain": chain_g, "keeper": keeper}


@test
def t_revert_field_scoped_foreign_edits():
    """(a) +control: foreign Attachments/Lighting edits between APPLY and REVERT -> REVERT succeeds, edits survive."""
    here, show, plan, orig, ops2, g = _applied_with_foreign_edits("tp_fs_pos", "FSAPPLY")
    foreign = {k: [x for x in show.cues if x["CueGuid"] == v][0]["WingPair"]["Attachments"] for k, v in g.items()}
    app.run_revert(ops2, core, {}, orig, "FSREVERT", here)
    check(any("_REVERT_OK|run=FSREVERT" in m for m in ops2.logs) and not ops2.errors,
          "+control (a) REVERT succeeds after foreign light/attachment edits: %s" % ops2.errors)
    check(any("foreign_edits_kept=2" in m for m in ops2.logs if "_REVERT_OK" in m),
          "REVERT_OK reports the 2 target rows whose foreign edits were kept")
    for k, v in g.items():
        check([x for x in show.cues if x["CueGuid"] == v][0]["WingPair"]["Attachments"] == foreign[k],
              "(a) foreign edit on the %s row survives REVERT" % k)
    by = {x["CueGuid"]: x for x in show.cues}
    check(all(show.mech_text(by[r["cue_guid"]]["WingPair"]["Mechanism"]) == r["mech_text"] and
              by[r["cue_guid"]]["WingPair"]["LocalOverrideMask"] == r["mask"] for r in orig["rows"]),
          "(a) every target's mechanism + mask == originals")
    check(ops2.calls.count("save_show") == 1 and not os.path.exists(os.path.join(here, app.ACTIVE_NAME)),
          "(a) saved once, originals retired")
    shutil.rmtree(here, ignore_errors=True)
    # legacy APPLY record (no after_mask, like TOPPLE-20261007-081114): mask derived from the originals
    here, show, plan, orig, ops2, g = _applied_with_foreign_edits("tp_fs_legacy", "FSLEGACY")
    rec_path = os.path.join(here, "topple_apply_FSLEGACY.json")
    rec = json.load(open(rec_path))
    check("after_mask" in rec, "APPLY record now carries after_mask")
    rec.pop("after_mask")
    json.dump(rec, open(rec_path, "w"))
    app.run_revert(ops2, core, {}, orig, "FSLEGACYREV", here)
    check(any("_REVERT_OK|run=FSLEGACYREV" in m for m in ops2.logs), "+control legacy record (no after_mask) reverts")
    shutil.rmtree(here, ignore_errors=True)


@test
def t_revert_field_scoped_negatives():
    """(b) a restore that also changes an attachment / a non-target -> stops, nothing saved; (c) mask drift."""
    for fault, token in (("attachment", "TARGET_CHANGED_OUTSIDE_MECHANISM"), ("nontarget", "NONTARGET_CUE_CHANGED")):
        here, show, plan, orig, ops2, g = _applied_with_foreign_edits("tp_fs_neg", "FSNEG")
        ops2.restore_also = fault
        check(raises(lambda: app.run_revert(ops2, core, {}, orig, "FSNEGREV", here), token),
              "-control (b) restore that also changes %s -> %s: %s" % (fault, token, ops2.errors))
        check("save_show" not in ops2.calls and os.path.exists(os.path.join(here, app.ACTIVE_NAME)),
              "(b) %s: nothing saved, originals kept ACTIVE" % fault)
        shutil.rmtree(here, ignore_errors=True)
    here, show, plan, orig, ops2, g = _applied_with_foreign_edits("tp_fs_mask", "FSMASK")
    next(x for x in show.cues if x["CueGuid"] == g["still"])["WingPair"]["LocalOverrideMask"] |= 4
    check(raises(lambda: app.run_revert(ops2, core, {}, orig, "FSMASKREV", here), "DRIFT_SINCE_APPLY"),
          "-control (c) LocalOverrideMask edited after APPLY -> DRIFT refuse")
    check("restore" not in ops2.calls and "backup" not in ops2.calls, "(c) mask drift: nothing backed up or restored")
    shutil.rmtree(here, ignore_errors=True)
    here, show, plan, orig, ops2, g = _applied_with_foreign_edits("tp_fs_gone", "FSGONE")
    show.cues = [x for x in show.cues if x["CueGuid"] != g["chain"]]
    check(raises(lambda: app.run_revert(ops2, core, {}, orig, "FSGONEREV", here), "TARGET_CUE_GONE"),
          "-control a target cue deleted after APPLY -> TARGET_CUE_GONE")
    shutil.rmtree(here, ignore_errors=True)


def main():
    for fn in TESTS:
        before = len(CHECKS["failed"])
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            CHECKS["failed"].append("%s raised %s: %s" % (fn.__name__, type(exc).__name__, exc))
        print("%-34s %s" % (fn.__name__, "ok" if len(CHECKS["failed"]) == before else "FAIL"))
    for f in CHECKS["failed"]:
        print("  FAILED: " + f)
    print("TOPPLE_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
