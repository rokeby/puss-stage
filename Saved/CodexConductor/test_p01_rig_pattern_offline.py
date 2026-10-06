"""Offline harness for p01_rig_pattern.py (pure Python, no unreal). Run: python test_p01_rig_pattern_offline.py

Fake Show: P01 bays B01/B02 (excluded), B03 (template '-'), B04 (template '+'), B05 (target '-', BEAM_R skipped),
B06 (target '+'), "P01 Wing 011" carrying label token B10 (target '-'), B08 (practical-only), B14 (candle '+'),
and a P02 cue with look-alike rows outside the passage. Every gate has a passing case and a failing control.
Prints "PASS n/FAIL m"; exits non-zero on any failure.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import random
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p01_rig_pattern", os.path.join(HERE, "p01_rig_pattern.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
assert M.unreal is None, "harness must run with unreal absent"
SCORES, TOOL = M.load_modules()

RESULTS = []


def case(name):
    def wrap(fn):
        try:
            fn()
            RESULTS.append((name, True, ""))
        except Exception as error:  # noqa: BLE001
            RESULTS.append((name, False, "%s: %s\n%s" % (type(error).__name__, error, traceback.format_exc())))
        return fn
    return wrap


def refuses(reason, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as error:  # noqa: BLE001
        assert reason in str(error), "expected %s, got %s" % (reason, error)
        return str(error)
    raise AssertionError("expected refusal %s, but it passed" % reason)


# ---------------------------------------------------------------- fake Show
LIGHT = "<InfinityAttachmentKind.LIGHT: 1>"
PROP = "<InfinityAttachmentKind.PROP: 0>"
STATION = "<InfinityAttachmentAnchor.STATION: 0>"
_GUIDS = [0]


def _guid():
    _GUIDS[0] += 1
    return "%032X" % (0xA000 + _GUIDS[0])


def _q(yaw_deg, pitch_deg=0.0):
    return M.canonical_quat(M.delta_quat(yaw_deg, pitch_deg))


def _row(label, kind, loc, rot, intensity=100.0, anchor=STATION):
    return {"guid": _guid(), "label": label, "kind": kind, "enabled": True, "actor_class": None,
            "mesh": "/Engine/BasicShapes/Sphere.Sphere" if kind == PROP else None, "anchor": anchor,
            "relative_transform": {"location": [float(v) for v in loc], "rotation_xyzw": list(rot),
                                   "scale": [1.0, 1.0, 1.0]},
            "lighting": {"intensity": intensity, "color": [1.0, 0.8, 0.6, 1.0], "inner_cone_angle_degrees": 8.0,
                         "outer_cone_angle_degrees": 22.0, "attenuation_radius_cm": 1700.0,
                         "drama": {"strike_on_approach": True}},
            "effect": {"type": "<InfinityAttachmentEffectType.NONE: 0>"}, "trigger_distance_cm": 0.0}


def warm(prefix, bay, parity, hand=None):
    """WARM_THEATRICAL rows; parity flips LOW_SIDE/BEAM y like the scores tool did (measured record shape)."""
    s = -1.0 if parity == "-" else 1.0
    base = {
        "TOP_L": ([0.0, -360.0, 1180.0], _q(-90, -60)), "TOP_R": ([0.0, 360.0, 1180.0], _q(90, -70)),
        "LOW_SIDE_L_KEY": ([80.0, 1100.0 * s, 130.0], _q(70 * s)),
        "LOW_SIDE_R_FILL": ([80.0, -1100.0 * s, 150.0], _q(-70 * s)),
        "BEAM_R": ([-150.0, 1250.0 * s, 140.0], _q(-80 * s)),
        "PRACTICAL_CLAMP": ([-30.0, -720.0, 145.0], [0.0, 0.0, 0.0, 1.0]),
        "PRACTICAL_CLAMP_BODY": ([-30.0, -720.0, 145.0], [0.0, 0.0, 0.0, 1.0]),
        "PRACTICAL_BULB_DEAD": ([-20.0, 700.0, 125.0], [0.0, 0.0, 0.0, 1.0]),
        "PRACTICAL_BULB_DEAD_BODY": ([-20.0, 700.0, 125.0], [0.0, 0.0, 0.0, 1.0]),
    }
    rows = [_row("PRE-SCORE house warmer %s" % bay, LIGHT, [0, 0, 900], [0, 0, 0, 1], intensity=5.0)]
    for role, (loc, rot) in base.items():
        if hand and role in hand:
            loc, rot = hand[role]
        rows.append(_row("%s SCORE B%s P01_WARM_THEATRICAL %s" % (prefix, bay, role),
                         PROP if role.endswith("_BODY") else LIGHT, loc, rot))
    return rows


def candle(bay, parity):
    s = -1.0 if parity == "-" else 1.0
    rows = []
    for role, loc, rot in (("TOP_L", [0, -360, 1180], _q(-90, -60)), ("TOP_R", [0, 360, 1180], _q(90, -60)),
                           ("LOW_SIDE_L_KEY", [80, 1450 * s, 130], _q(60 * s)),
                           ("LOW_SIDE_R_FILL", [80, -1450 * s, 150], _q(-60 * s)),
                           ("PRACTICAL_L", [-20, -700, 120], [0, 0, 0, 1]),
                           ("PRACTICAL_L_BODY", [-20, -700, 120], [0, 0, 0, 1]),
                           ("PRACTICAL_R", [-20, 700, 120], [0, 0, 0, 1]),
                           ("PRACTICAL_R_BODY", [-20, 700, 120], [0, 0, 0, 1])):
        rows.append(_row("P01 SCORE B%s P01_CANDLE_MOODY %s" % (bay, role),
                         PROP if role.endswith("_BODY") else LIGHT, loc, rot))
    return rows


def practical(bay):
    return [_row("P01 SCORE B%s GAP PRACTICAL_GLIMMER" % bay, LIGHT, [-20, -700, 140], [0, 0, 0, 1]),
            _row("P01 SCORE B%s GAP PRACTICAL_GLIMMER_BODY" % bay, PROP, [-20, -700, 140], [0, 0, 0, 1]),
            _row("P01 SCORE B%s GAP PRACTICAL_DEAD" % bay, LIGHT, [-10, 700, 115], [0, 0, 0, 1]),
            _row("P01 SCORE B%s GAP PRACTICAL_DEAD_BODY" % bay, PROP, [-10, 700, 115], [0, 0, 0, 1])]


# Gary's hand values (shaped like DRIFT-20261006-182900: lights pushed out past the panels, raised).
HAND_B03 = {"TOP_L": ([-453.0, -1395.4, 1407.7], _q(-120, -40)), "TOP_R": ([-313.0, 1353.3, 1271.9], _q(110, -35)),
            "LOW_SIDE_L_KEY": ([-495.0, -1173.5, 873.2], _q(40, -20)),
            "LOW_SIDE_R_FILL": ([-471.8, 1345.0, 738.3], _q(-50, -15)),
            "BEAM_R": ([-590.1, -1248.5, 153.8], _q(-60)),
            "PRACTICAL_CLAMP": ([-57.8, -811.4, 138.6], [0.0, 0.0, 0.0, 1.0]),
            "PRACTICAL_CLAMP_BODY": ([-73.3, -722.2, 145.0], [0.0, 0.0, 0.0, 1.0])}
HAND_B04 = {"TOP_L": ([-484.5, -1309.6, 1362.7], _q(-118, -42)), "TOP_R": ([-489.7, 1341.4, 1421.0], _q(112, -38)),
            "LOW_SIDE_L_KEY": ([-544.5, 1124.8, 227.7], _q(-45, -18)),
            "LOW_SIDE_R_FILL": ([-543.2, -1144.3, 626.8], _q(55, -12)),
            "BEAM_R": ([-516.0, 970.1, 364.0], _q(62)),
            "PRACTICAL_CLAMP": ([-79.8, -720.0, 145.0], [0.0, 0.0, 0.0, 1.0]),
            "PRACTICAL_BULB_DEAD": ([-46.1, 700.0, 194.2], [0.0, 0.0, 0.0, 1.0])}


def make_show():
    _GUIDS[0] = 0
    spec = [("P01 Wing 001", practical("01")), ("P01 Wing 002", practical("02")),
            ("P01 Wing 003", warm("P01", "03", "-", HAND_B03)), ("P01 Wing 004", warm("P01", "04", "+", HAND_B04)),
            ("P01 Wing 005", warm("P01", "05", "-")), ("P01 Wing 006", warm("P01", "06", "+")),
            ("P01 Wing 008", practical("08")), ("P01 Wing 011", warm("P01", "10", "-")),
            ("P01 Wing 014", candle("14", "+")), ("P02 Wing 001", warm("P02", "01", "-"))]
    cues = []
    for index, (label, rows) in enumerate(spec):
        cues.append({"show_index": index, "guid": "%032X" % (0xC000 + index), "label": label, "attachments": rows})
    bays = [c["guid"] for c in cues if c["label"].startswith("P01 ")]
    return {"cues": cues, "bay_guids": bays}


AIMS = {}   # filled per show: B05 panel narrow so its practical sits "inside"


def aims_for(plain):
    out = {}
    for cue in plain["cues"]:
        out[cue["guid"]] = [{"panel": "L", "target_cm": [0.0, -1015.6, 0.0]}, {"panel": "R", "target_cm": [0.0, 750.0, 0.0]}]
    return out


FULL_ROLES = ["TOP_L", "TOP_R", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "BEAM_R", "PRACTICAL_CLAMP",
              "PRACTICAL_CLAMP_BODY", "PRACTICAL_BULB_DEAD", "PRACTICAL_BULB_DEAD_BODY"]
ZERO_JITTER = {"loc_cm": 0.0, "rot_deg": 0.0, "seed": 0}


def opts(**over):
    # Explicit roles incl. _BODY + zero jitter unless a case overrides (the defaults are tested separately).
    base = {"mode": "DRY", "roles": list(FULL_ROLES), "jitter": dict(ZERO_JITTER)}
    base.update(over)
    return M.check_args(base)


def by_label(plain, label):
    return next(c for c in plain["cues"] if c["label"] == label)


def role_row(cue, role):
    return next(r for r in cue["attachments"] if r["label"].endswith(" " + role))


def plan_for(plain=None, **over):
    plain = plain or make_show()
    return plain, M.build_plan(plain, opts(**over), aims_for(plain))


def all_rows(plain):
    return {c["guid"]: c["attachments"] for c in plain["cues"]}


# ---------------------------------------------------------------- cases
@case("templates by parity: '-' bays copy B03, '+' bays copy B04, role by role, exact")
def _():
    plain, plan = plan_for()
    b03, b04 = by_label(plain, "P01 Wing 003"), by_label(plain, "P01 Wing 004")
    assert plan["templates"]["-"]["cue_label"] == "P01 Wing 003" and plan["templates"]["+"]["cue_label"] == "P01 Wing 004"
    seen = 0
    for t in plan["targets"]:
        src = b03 if t["parity"] == "-" else b04
        want = role_row(src, t["role"])["relative_transform"]
        assert t["location_after"] == want["location"], (t["cue_label"], t["role"])
        assert t["rotation_after"] == want["rotation_xyzw"], (t["cue_label"], t["role"])
        seen += 1
    parities = {t["cue_label"]: t["parity"] for t in plan["targets"]}
    assert parities == {"P01 Wing 005": "-", "P01 Wing 006": "+", "P01 Wing 011": "-", "P01 Wing 014": "+"}, parities
    assert seen == len(plan["targets"]) > 0


@case("parity is read from the LIVE row, not the bay number (Wing 011 carries B10, parity '-')")
def _():
    plain, plan = plan_for()
    t = [x for x in plan["targets"] if x["cue_label"] == "P01 Wing 011"]
    assert t and all(x["bay_token"] == "10" and x["parity"] == "-" for x in t)
    # flip its LOW_SIDE_L_KEY y -> parity flips -> B04 template used
    cue = by_label(plain, "P01 Wing 011")
    role_row(cue, "LOW_SIDE_L_KEY")["relative_transform"]["location"][1] = 1100.0
    plan2 = M.build_plan(plain, opts(), aims_for(plain))
    t2 = [x for x in plan2["targets"] if x["cue_label"] == "P01 Wing 011"]
    assert all(x["parity"] == "+" and x["template_cue"] == "P01 Wing 004" for x in t2)


@case("only location+rotation change; check_scope passes on the model")
def _():
    plain, plan = plan_for()
    before = all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    M.check_scope(TOOL, before, after, plan, "after")
    targets = set(plan["target_attachment_guids"])
    changed = 0
    for guid in before:
        for b, a in zip(before[guid], after[guid]):
            diffs = TOOL._state_differences(b, a)
            if b["guid"] not in targets:
                assert not diffs, b["label"]
            for d in diffs:
                assert d["path"].startswith("relative_transform.location") or \
                    d["path"].startswith("relative_transform.rotation_xyzw"), d["path"]
            changed += bool(diffs)
    assert changed > 0


@case("skip honoured: B05 BEAM_R untouched and listed")
def _():
    plain, plan = plan_for()
    assert not [t for t in plan["targets"] if t["cue_label"] == "P01 Wing 005" and t["role"] == "BEAM_R"]
    assert [s for s in plan["skipped"] if s["cue_label"] == "P01 Wing 005" and s["role"] == "BEAM_R"]
    assert [t for t in plan["targets"] if t["cue_label"] == "P01 Wing 006" and t["role"] == "BEAM_R"]
    # skip [] -> B05 BEAM_R becomes a target
    unused, plan2 = plan_for(skip=[])
    assert [t for t in plan2["targets"] if t["cue_label"] == "P01 Wing 005" and t["role"] == "BEAM_R"]


@case("templates, B01/B02, practical-only B08 and P02 are never targets")
def _():
    plain, plan = plan_for()
    never = {"P01 Wing 001", "P01 Wing 002", "P01 Wing 003", "P01 Wing 004", "P01 Wing 008", "P02 Wing 001"}
    assert not ({t["cue_label"] for t in plan["targets"]} & never), plan["target_bays"]
    status = {u["cue_label"]: u["status"] for u in plan["untouched_bays"]}
    assert status == {"P01 Wing 001": "EXCLUDED", "P01 Wing 002": "EXCLUDED", "P01 Wing 003": "TEMPLATE",
                      "P01 Wing 004": "TEMPLATE", "P01 Wing 008": "PRACTICAL_ONLY"}, status
    p02 = by_label(plain, "P02 Wing 001")["guid"]
    assert p02 not in plain["bay_guids"] and p02 not in plan["target_cue_guids"]
    # non-score pre-score rows never targeted
    assert not [t for t in plan["targets"] if "PRE-SCORE" in t["attachment_label"]]


@case("candle bay: TOP/LOW_SIDE copied, PRACTICAL_L/_R untouched (not in roles); no-template role listed")
def _():
    plain, plan = plan_for()
    roles = sorted(t["role"] for t in plan["targets"] if t["cue_label"] == "P01 Wing 014")
    assert roles == ["LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "TOP_L", "TOP_R"], roles
    unused, plan2 = plan_for(roles=list(M.DEFAULT_ROLES) + ["PRACTICAL_L"])
    assert [n for n in plan2["no_template"] if n["cue_label"] == "P01 Wing 014" and n["role"] == "PRACTICAL_L"]
    assert not [t for t in plan2["targets"] if t["role"] == "PRACTICAL_L"]


@case("jitter 0 == exact template (no float noise)")
def _():
    plain, plan = plan_for()
    assert all(t["jitter"] == {"dx": 0.0, "dy": 0.0, "dz": 0.0, "yaw": 0.0, "pitch": 0.0} for t in plan["targets"])
    b03 = by_label(plain, "P01 Wing 003")
    t = next(x for x in plan["targets"] if x["cue_label"] == "P01 Wing 005" and x["role"] == "TOP_L")
    assert t["location_after"] == role_row(b03, "TOP_L")["relative_transform"]["location"]
    assert t["rotation_after"] == role_row(b03, "TOP_L")["relative_transform"]["rotation_xyzw"]


JIT = {"loc_cm": 25.0, "rot_deg": 4.0, "seed": 7}


@case("jitter deterministic across runs and independent of bay/cue order")
def _():
    unused, p1 = plan_for(jitter=JIT)
    unused, p2 = plan_for(jitter=JIT)
    assert M._canonical(p1["targets"]) == M._canonical(p2["targets"])
    plain = make_show()
    rng = random.Random(1234)
    rng.shuffle(plain["bay_guids"])
    rng.shuffle(plain["cues"])          # show_index values travel with the cue, list order shuffled
    p3 = M.build_plan(plain, opts(jitter=JIT), aims_for(plain))
    assert M._canonical(p1["targets"]) == M._canonical(p3["targets"])
    # a different seed changes the plan
    unused, p4 = plan_for(jitter=dict(JIT, seed=8))
    assert M._canonical(p1["targets"]) != M._canonical(p4["targets"])


@case("jitter bounds: |offset| <= loc_cm, rotation within rot_deg of template, unit + canonical quaternion")
def _():
    plain, plan = plan_for(jitter=JIT)
    for t in plan["targets"]:
        j = t["jitter"]
        assert all(abs(j[a]) <= JIT["loc_cm"] for a in ("dx", "dy", "dz"))
        assert all(abs(j[a]) <= JIT["rot_deg"] for a in ("yaw", "pitch"))
        q = t["rotation_after"]
        assert abs(math.sqrt(sum(c * c for c in q)) - 1.0) < 1e-12 and q == M.canonical_quat(q)
    offsets = {(t["cue_label"], t["role"]): (t["jitter"]["dx"], t["jitter"]["dy"]) for t in plan["targets"]}
    assert len(set(offsets.values())) > len(offsets) // 2, "offsets should vary"


@case("a light and its _BODY prop share the same location offset (and rotation delta)")
def _():
    plain, plan = plan_for(jitter=JIT)
    pairs = 0
    for t in plan["targets"]:
        if not t["role"].endswith("_BODY"):
            continue
        light = next(x for x in plan["targets"] if x["cue_guid"] == t["cue_guid"] and x["role"] == M.base_role(t["role"]))
        assert t["jitter"] == light["jitter"], (t["cue_label"], t["role"])
        pairs += 1
    assert pairs >= 4, pairs


@case("Gary defaults (6 Oct): lights only, bodies untouched, jitter 25 cm / 3 deg / seed 20261006, B05 BEAM_R skipped")
def _():
    a = M.check_args({})
    assert a["jitter"] == {"loc_cm": 25.0, "rot_deg": 3.0, "seed": 20261006}, a["jitter"]
    assert a["roles"] == ["TOP_L", "TOP_R", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "BEAM_R",
                          "PRACTICAL_CLAMP", "PRACTICAL_BULB_DEAD"], a["roles"]
    assert a["skip"] == [["P01 Wing 005", "BEAM_R"]]
    plain = make_show()
    plan = M.build_plan(plain, a, aims_for(plain))
    assert plan["targets"] and not [t for t in plan["targets"] if t["role"].endswith("_BODY") or t["kind"] != "LIGHT"]
    assert all(any(t["jitter"][k] != 0.0 for k in t["jitter"]) for t in plan["targets"])
    before = all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    for guid in before:
        for b, x in zip(before[guid], after[guid]):
            if b["label"].endswith("_BODY"):
                assert b == x, b["label"]
    M.check_scope(TOOL, before, after, plan, "after")
    with open(os.path.join(HERE, "p01_rig_pattern_args.json"), encoding="utf-8") as handle:
        assert M.check_args(json.load(handle)) == a


@case("expected_targets pin: match passes, mismatch refuses")
def _():
    unused, plan = plan_for()
    n = len(plan["targets"])
    plan_for(expected_targets=n)
    refuses("EXPECTED_TARGETS", plan_for, expected_targets=n + 1)


@case("PANEL_BAND warning: planned light with |y| < bay panel |y| is flagged, not a stop")
def _():
    plain, plan = plan_for()
    inside = [t for t in plan["targets"] if t["inside_panel_band"]]
    # B03 PRACTICAL_CLAMP sits at y=-811.4 < panel L 1015.6
    assert [t for t in inside if t["role"] == "PRACTICAL_CLAMP" and t["parity"] == "-"]
    assert any(w.startswith("PANEL_BAND|") for w in plan["warnings"])
    # TOP_L at -1395 is outside the band
    assert not [t for t in inside if t["role"] == "TOP_L" and t["parity"] == "-"]
    for bay in plan["bays"]:
        for r in bay["rows"]:
            assert len(r["abs_y"]) == 2 and len(r["z"]) == 2


@case("NEGATIVE: wrong-parity template (B03/B04 swapped) fails an assertion")
def _():
    refuses("TEMPLATE_PARITY_WRONG", plan_for, templates={"-": "P01 Wing 004", "+": "P01 Wing 003"})
    plain = make_show()
    role_row(by_label(plain, "P01 Wing 003"), "LOW_SIDE_L_KEY")["relative_transform"]["location"][1] = 900.0
    refuses("TEMPLATE_PARITY_WRONG", M.build_plan, plain, opts(), {})


@case("NEGATIVE: a mutated plan that writes intensity FAILS the scope check")
def _():
    plain, plan = plan_for()
    before = all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    t = plan["targets"][0]
    row = next(r for r in after[t["cue_guid"]] if r["guid"] == t["attachment_guid"])
    row["lighting"]["intensity"] = 999.0
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, before, after, plan, "after")


@case("NEGATIVE: scale change on a target, or any change to a non-target row / non-target cue, fails scope")
def _():
    plain, plan = plan_for()
    before = all_rows(plain)
    for mutate in ("scale", "neighbour", "outside"):
        after = M.apply_plain(before, plan, "after")
        t = plan["targets"][0]
        if mutate == "scale":
            next(r for r in after[t["cue_guid"]] if r["guid"] == t["attachment_guid"])["relative_transform"]["scale"][0] = 0.99
            reason = "SCOPE_CHANGED"
        elif mutate == "neighbour":
            next(r for r in after[t["cue_guid"]] if "PRE-SCORE" in r["label"])["relative_transform"]["location"][2] += 1.0
            reason = "SCOPE_CHANGED"
        else:
            after[by_label(plain, "P01 Wing 003")["guid"]][1]["relative_transform"]["location"][0] += 1.0
            reason = "OUTSIDE_TARGET_SCOPE_CHANGED"
        refuses(reason, M.check_scope, TOOL, before, after, plan, "after")


@case("NEGATIVE: a write that misses location by > tol, or the wrong rotation, fails scope")
def _():
    plain, plan = plan_for()
    before = all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    t = plan["targets"][1]
    row = next(r for r in after[t["cue_guid"]] if r["guid"] == t["attachment_guid"])
    row["relative_transform"]["location"][1] += 1.0e-3
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, before, after, plan, "after")
    after = M.apply_plain(before, plan, "after")
    row = next(r for r in after[t["cue_guid"]] if r["guid"] == t["attachment_guid"])
    row["relative_transform"]["rotation_xyzw"] = _q(5.0)
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, before, after, plan, "after")
    # q and -q are the same rotation: accepted
    after = M.apply_plain(before, plan, "after")
    row = next(r for r in after[t["cue_guid"]] if r["guid"] == t["attachment_guid"])
    row["relative_transform"]["rotation_xyzw"] = [-c for c in row["relative_transform"]["rotation_xyzw"]]
    M.check_scope(TOOL, before, after, plan, "after")


def make_record(plain, plan):
    before = all_rows(plain)
    return {"status": "saved_readback_verified", "passage": "P01", "plan": plan,
            "before_target_rows": M.target_rows(before, plan),
            "after_target_rows": M.target_rows(M.apply_plain(before, plan, "after"), plan)}


@case("REVERT: drift detection lists ALL drifts (not just the first)")
def _():
    plain, plan = plan_for(jitter=JIT)
    record = make_record(plain, plan)
    live = M.apply_plain(all_rows(plain), plan, "after")
    assert M.revert_drifts(live, record) == []
    t0, t1, t2 = plan["targets"][0], plan["targets"][5], plan["targets"][9]
    for t, loc, rot in ((t0, True, False), (t1, False, True), (t2, True, True)):
        row = next(r for r in live[t["cue_guid"]] if r["guid"] == t["attachment_guid"])
        if loc:
            row["relative_transform"]["location"][2] += 10.0
        if rot:
            row["relative_transform"]["rotation_xyzw"] = _q(33.0)
    drifts = M.revert_drifts(live, record)
    assert len(drifts) == 4, drifts
    assert {d["guid"] for d in drifts} == {t0["attachment_guid"], t1["attachment_guid"], t2["attachment_guid"]}
    refuses("REVERT_DRIFT|count=4", M.check_revert_drift, live, record)
    refuses("REVERT_DRIFT", M.revert_plain, TOOL, live, record)


@case("REVERT: restores before loc/rot exactly; a later hand intensity change is preserved; scope holds")
def _():
    plain, plan = plan_for(jitter=JIT)
    record = make_record(plain, plan)
    original = all_rows(plain)
    live = M.apply_plain(original, plan, "after")
    t = plan["targets"][3]
    next(r for r in live[t["cue_guid"]] if r["guid"] == t["attachment_guid"])["lighting"]["intensity"] = 321.0
    reverted = M.revert_plain(TOOL, live, record)
    M.check_scope(TOOL, live, reverted, plan, "before")
    for guid, rows in original.items():
        for o, r in zip(rows, reverted[guid]):
            assert o["relative_transform"] == r["relative_transform"], r["label"]
    assert next(r for r in reverted[t["cue_guid"]] if r["guid"] == t["attachment_guid"])["lighting"]["intensity"] == 321.0
    refuses("REVERT_RECORD_STATUS", M.check_record, dict(record, status="prepared"))
    M.check_record(record)


@case("guards: duplicate role, kind/anchor mismatch, bay outside P01, args confirm")
def _():
    plain = make_show()
    cue = by_label(plain, "P01 Wing 006")
    cue["attachments"].append(copy.deepcopy(role_row(cue, "TOP_L")))
    cue["attachments"][-1]["guid"] = "F" * 32
    refuses("DUPLICATE_ROLE", M.build_plan, plain, opts(), {})
    plain = make_show()
    role_row(by_label(plain, "P01 Wing 006"), "TOP_R")["anchor"] = "<InfinityAttachmentAnchor.CAMERA: 1>"
    refuses("ANCHOR_MISMATCH", M.build_plan, plain, opts(), {})
    plain = make_show()
    role_row(by_label(plain, "P01 Wing 006"), "PRACTICAL_CLAMP_BODY")["kind"] = LIGHT
    refuses("KIND_MISMATCH", M.build_plan, plain, opts(), {})
    plain = make_show()
    plain["bay_guids"].append(by_label(plain, "P02 Wing 001")["guid"])
    refuses("BAY_NOT_P01", M.build_plan, plain, opts(), {})
    refuses("CONFIRM_MISSING", M.check_args, {"mode": "APPLY"})
    refuses("CONFIRM_MISSING", M.check_args, {"mode": "REVERT", "confirm": "REVERT P01"})
    assert M.check_args({"mode": "APPLY", "confirm": "APPLY P01RIGPATTERN"})["mode"] == "APPLY"
    refuses("JITTER_SEED_NOT_INT", M.check_args, {"jitter": {"seed": "x"}})
    refuses("MODE_INVALID", M.check_args, {"mode": "SAVE"})


@case("context gate: DRY tolerates dirty census; APPLY refuses dirty/PIE/ZZ_ unless allowed (Show/World only)")
def _():
    clean = {"census": {"content": [], "maps": []}}
    dirty = {"census": {"content": ["/Game/X"], "maps": []}}
    M.check_context(dirty, "DRY")
    M.check_context(clean, "APPLY", [], "/Game/Show", "/Game/World")
    refuses("DIRTY_BEFORE", M.check_context, dirty, "APPLY", [], "/Game/Show", "/Game/World")
    refuses("PIE_OR_SIE_ACTIVE", M.check_context, dict(clean, pie=True), "APPLY", [], "/Game/Show", "/Game/World")
    refuses("STRAY_ZZ_ACTORS", M.check_context, dict(clean, zz_actors=["ZZ_x"]), "REVERT", [], "/Game/Show", "/Game/World")
    refuses("ALLOW_DIRTY_OUT_OF_SCOPE", M.check_context, dirty, "APPLY", ["/Game/X"], "/Game/Show", "/Game/World")
    M.check_context({"census": {"content": [], "maps": ["/Game/World"]}}, "APPLY", ["/Game/World"], "/Game/Show", "/Game/World")
    refuses("WRONG_WORLD", M.check_context, dict(clean, world_ok=False), "DRY")


@case("apply gate: existing record or unacked foreign record refuses")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rec.json")
        M.check_apply_gate([], path)
        refuses("FOREIGN_ACTIVE_RECORDS_OVERLAP", M.check_apply_gate, ["a.json"], path)
        open(path, "w").close()
        refuses("ACTIVE_RECORD_EXISTS", M.check_apply_gate, [], path)


def _export(rows):
    parts = []
    for r in rows:
        loc, rot, sc = (r["relative_transform"][k] for k in ("location", "rotation_xyzw", "scale"))
        parts.append("(Label=\"%s\",AttachmentGuid=%s,RelativeTransform=(Rotation=(X=%r,Y=%r,Z=%r,W=%r),"
                     "Translation=(X=%r,Y=%r,Z=%r),Scale3D=(X=%r,Y=%r,Z=%r)),Lighting=(Intensity=%r))"
                     % ((r["label"], r["guid"]) + tuple(rot) + tuple(loc) + tuple(sc) + (r["lighting"]["intensity"],)))
    return "(Attachments=(" + ",".join(parts) + "))"


@case("export hash masks exactly the targets' Rotation+Translation (scale/intensity/non-targets still counted)")
def _():
    plain, plan = plan_for(jitter=JIT)
    before = all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    texts_b = [_export(before[g]) for g in sorted(before)]
    texts_a = [_export(after[g]) for g in sorted(after)]
    assert texts_a != texts_b
    assert M.export_hash(texts_a, plan["target_attachment_guids"]) == M.export_hash(texts_b, plan["target_attachment_guids"])
    t = plan["targets"][0]
    for field in ("scale", "intensity", "neighbour"):
        bad = copy.deepcopy(after)
        rows = bad[t["cue_guid"]]
        if field == "scale":
            next(r for r in rows if r["guid"] == t["attachment_guid"])["relative_transform"]["scale"][2] = 2.0
        elif field == "intensity":
            next(r for r in rows if r["guid"] == t["attachment_guid"])["lighting"]["intensity"] = 1.0
        else:
            next(r for r in rows if "PRE-SCORE" in r["label"])["relative_transform"]["location"][0] = 5.0
        texts_x = [_export(bad[g]) for g in sorted(bad)]
        assert M.export_hash(texts_x, plan["target_attachment_guids"]) != M.export_hash(texts_b, plan["target_attachment_guids"]), field
    refuses("EXPORT_TARGET_COUNT", M.export_hash, texts_b, plan["target_attachment_guids"] + ["E" * 32])


@case("readback_rows asserts every row and names the bad ones")
def _():
    plain, plan = plan_for()
    after = M.apply_plain(all_rows(plain), plan, "after")
    assert all(r["ok"] for r in M.readback_rows(after, plan, "after"))
    refuses("READBACK_ROWS|side=before", M.readback_rows, after, plan, "before")


@case("self-check: no module-level UE object; main guard shape; files parse")
def _():
    import ast
    for name in ("p01_rig_pattern.py", "p01_rig_pattern_run.py", "test_p01_rig_pattern_offline.py"):
        with open(os.path.join(HERE, name), encoding="utf-8") as handle:
            ast.parse(handle.read())
    for name in ("p01_rig_pattern_args.json", "p01_rig_pattern_request.json"):
        with open(os.path.join(HERE, name), encoding="utf-8") as handle:
            json.load(handle)
    with open(os.path.join(HERE, "p01_rig_pattern_args.json"), encoding="utf-8") as handle:
        assert M.check_args(json.load(handle))["mode"] == "DRY"
    with open(os.path.join(HERE, "p01_rig_pattern.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    assert M._is_main_guard(tree.body[-1])
    for node in tree.body[:-1]:
        if isinstance(node, ast.Assign):
            assert "unreal." not in ast.unparse(node.value), ast.unparse(node)


def main():
    passed = sum(1 for r in RESULTS if r[1])
    failed = len(RESULTS) - passed
    for name, ok, detail in RESULTS:
        print("%s  %s" % ("PASS" if ok else "FAIL", name))
        if not ok:
            print(detail)
    plain, plan = plan_for()
    print("EVIDENCE default plan: bays=%d rows=%d skipped=%d warnings=%d"
          % (len(plan["target_bays"]), len(plan["targets"]), len(plan["skipped"]), len(plan["warnings"])))
    print("PASS %d/FAIL %d" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
