"""Offline harness for p02_brighten.py (pure Python, no unreal). Run: python test_p02_brighten_offline.py

Fixture = the real P02 Show rows: p02_rig_pattern_record.json after_cue_rows (21 cues, APPLY 6 Oct 22:38,
saved_readback_verified) + the two GAP bays (P02 Wing 007 / 022) from lighting_scores_record_P02.json after_rows, with
the 12 second-half cues REPLACED by p02_brighten_record.json before_cue_rows (live read by APPLY 20261007-022814, i.e.
exactly what REVERT restores; differs from the 6 Oct rows only in float32 rotation rounding), plus a foreign P01 cue
with a look-alike row. Stations are SYNTHETIC (inferred, not live): bay ordinal n at 250 + 500 (n-1) cm on an
11857.83 cm route (uniform intervals in passage_slow_walk_P02_latest.json; required_cm in
p02_straighten_dry_P02STR-20261007-015527.json). Every gate has a passing case and a failing control.
Prints PASS/FAIL per case and a summary; exits non-zero on any failure.
"""
from __future__ import annotations

import ast
import copy
import json
import os
import re
import struct
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p02_brighten as B  # noqa: E402

assert B.unreal is None, "harness must run with unreal absent"
RP = B.load_rig_pattern()
SCORES, TOOL = RP.load_modules()
DIFF = TOOL._state_differences
RESULTS = []
FOREIGN_FOUND = []


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


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------- fixture
RIG = load("p02_rig_pattern_record.json")
SCO = load("lighting_scores_record_P02.json")
REC1 = load("p02_brighten_record.json")          # the ACTIVE schema-1 record (APPLY 20261007-022814)
assert REC1["run"] == "20261007-022814" and REC1["status"] == "saved_readback_verified"
BAYS_INFO = {b["cue_guid"]: b for b in RIG["plan"]["bays"]}
CUES = []
for g, rows in RIG["after_cue_rows"].items():
    b = BAYS_INFO[g]
    rows = REC1["before_cue_rows"].get(g, rows)
    CUES.append({"guid": g, "label": b["cue_label"], "show_index": b["show_index"], "attachments": copy.deepcopy(rows)})
for t in SCO["plan"]["targets"]:
    if t["cue_label"] in ("P02 Wing 007", "P02 Wing 022"):
        rows = REC1["before_cue_rows"].get(t["cue_guid"], t["after_rows"])
        CUES.append({"guid": t["cue_guid"], "label": t["cue_label"], "show_index": t["show_index"],
                     "attachments": copy.deepcopy(rows)})
CUES.sort(key=lambda c: c["show_index"])
assert len(CUES) == 23, len(CUES)
assert set(REC1["before_cue_rows"]) <= {c["guid"] for c in CUES}
FOREIGN = {"guid": "F" * 32, "label": "P01 Wing 020", "show_index": 3,
           "attachments": [copy.deepcopy(CUES[-1]["attachments"][0])]}
FOREIGN["attachments"][0].update({"guid": "E" * 32, "label": "P01 SCORE B20 P02_MYSTIC TOP_L"})
FOREIGN["attachments"][0]["lighting"]["intensity"] = 0.0
ROUTE = 11857.834499999999
BAY_GUIDS = [c["guid"] for c in CUES]


def ordinal(cue):
    tokens = {B.SCORE_RE.match(r["label"]).group(1) for r in cue["attachments"] if B.SCORE_RE.match(r["label"])}
    assert len(tokens) == 1, (cue["label"], tokens)
    return int(tokens.pop())


STATIONS = [{"cue_guid": c["guid"], "distance_cm": 250.0 + 500.0 * (ordinal(c) - 1)} for c in CUES]


def plain():
    return {"cues": copy.deepcopy([FOREIGN] + CUES), "bay_guids": list(BAY_GUIDS), "passage_guid": "P2"}


def all_rows(p):
    return {c["guid"]: c["attachments"] for c in p["cues"]}


P = B.check_params({})                               # both sets ON (defaults)
PI = B.check_params({"drama": False})                # intensity set only (schema-1 behaviour)
ARGS = load("p02_brighten_args.json")
PA = B.check_args(dict(ARGS, mode="DRY"))["params"]  # the params the next DRY/APPLY will run with


def plan_for(params=None, p=None, stations=None, route=ROUTE):
    return B.build_plan(p or plain(), stations or STATIONS, route, params or P, RP.FORBIDDEN_TARGET_LABEL)


PLAN = plan_for()
PLAN_I = plan_for(PI)
PLAN_A = plan_for(PA)
BY_LABEL = {t["attachment_label"]: t for t in PLAN_I["targets"]}
DRAMA_T = [t for t in PLAN["targets"] if t["path"] != B.FIELD]


def second_half_lights(p=None):
    """Independent oracle: every enabled LIGHT 'P02 SCORE B## ..' row (not _BODY) in B12+ that strikes on approach."""
    out = []
    for c in (p or plain())["cues"]:
        if c["guid"] == FOREIGN["guid"]:
            continue
        for r in c["attachments"]:
            m = B.SCORE_RE.match(r["label"])
            if (m and int(m.group(1)) >= 12 and not m.group(3).endswith("_BODY") and r["enabled"]
                    and "LIGHT" in r["kind"] and r["lighting"]["drama"]["strike_on_approach"]):
                out.append(r)
    return out


# ---------------------------------------------------------------- A. args / files
@case("args: DRY needs no confirm; APPLY needs confirm AND expected_targets; REVERT token checked")
def _():
    assert B.check_args({"mode": "DRY"})["mode"] == "DRY"
    refuses("CONFIRM_MISSING", B.check_args, {"mode": "APPLY", "expected_targets": 26})
    refuses("EXPECTED_TARGETS_REQUIRED", B.check_args, {"mode": "APPLY", "confirm": "APPLY P02BRIGHTEN"})
    assert B.check_args({"mode": "APPLY", "confirm": "APPLY P02BRIGHTEN", "expected_targets": 26})["mode"] == "APPLY"
    refuses("CONFIRM_MISSING", B.check_args, {"mode": "REVERT", "confirm": "APPLY P02BRIGHTEN"})
    assert B.check_args({"mode": "REVERT", "confirm": "REVERT P02BRIGHTEN"})["mode"] == "REVERT"
    refuses("MODE_INVALID", B.check_args, {"mode": "SAVE"})
    refuses("EXPECTED_TARGETS_INVALID", B.check_args, {"mode": "DRY", "expected_targets": True})


@case("params: defaults (both sets); unknown key, ranges, floor>max, wide regex, non-TOP role, bad drama args refused")
def _():
    assert (P["from_fraction"], P["practical_floor"], P["top_scale"], P["top_floor_cd"], P["top_max_cd"]) == \
        (0.45, 120.0, 2.0, 60.0, 200.0) and (P["practical_units"], P["top_units"]) == ("LUMENS", "CANDELAS")
    assert (P["drama"], P["strike_distance_cm"], P["strike_ramp_cm"], P["after_pass_override"],
            P["drama_skip_roles"]) == (True, 2500.0, 600.0, "HOLD", [])
    refuses("PARAM_UNITS", B.check_params, {"practical_units": "LUX"})
    refuses("PARAMS_UNKNOWN", B.check_params, {"from_fracton": 0.4})
    refuses("PARAM_RANGE", B.check_params, {"top_scale": 0.5})            # never dims
    refuses("PARAM_RANGE", B.check_params, {"practical_floor": 5000})
    refuses("PARAM_TOP_FLOOR_ABOVE_MAX", B.check_params, {"top_floor_cd": 300, "top_max_cd": 200})
    refuses("PARAM_PRACTICAL_ROLE_RE_TOO_WIDE", B.check_params, {"practical_role_re": ".*"})
    refuses("PARAM_TOP_ROLES", B.check_params, {"top_roles": ["TOP_L", "BEAM_R"]})
    refuses("NOT_NUMBER", B.check_params, {"top_scale": True})
    refuses("PARAM_AFTER_PASS_OVERRIDE", B.check_params, {"after_pass_override": "EXTINGUISH"})
    refuses("PARAM_AFTER_PASS_OVERRIDE", B.check_params, {"after_pass_override": "hold"})
    refuses("PARAM_DRAMA_NOT_BOOL", B.check_params, {"drama": 1})
    refuses("PARAM_RANGE", B.check_params, {"strike_distance_cm": 9000})
    refuses("PARAM_RANGE", B.check_params, {"strike_ramp_cm": 0.0})
    refuses("PARAM_DRAMA_SKIP_ROLES", B.check_params, {"drama_skip_roles": "BEAM_R"})
    assert B.check_params({"after_pass_override": None})["after_pass_override"] is None


@case("files: args valid (any mode) and keep the applied intensity params; request/run parse; main guard shape")
def _():
    a = ARGS
    assert a["mode"] in B.VALID_MODES
    if a["mode"] != "DRY" and "confirm" not in a:
        refuses("CONFIRM_MISSING", B.check_args, a)              # the conductor adds the confirm token
        B.check_args(dict(a, confirm="%s P02BRIGHTEN" % a["mode"]))
    else:
        B.check_args(a)
    assert {k: PA[k] for k in REC1["args"]["params"]} == REC1["args"]["params"], "intensity params drifted"
    req = load("p02_brighten_request.json")
    assert req["arguments"]["tool_name"] == "ExecuteProjectPythonFile"
    assert req["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/p02_brighten_run.py"
    for name in ("p02_brighten.py", "p02_brighten_run.py", "test_p02_brighten_offline.py"):
        with open(os.path.join(HERE, name), encoding="utf-8") as h:
            ast.parse(h.read())
    with open(os.path.join(HERE, "p02_brighten.py"), encoding="utf-8") as h:
        tree = ast.parse(h.read())
    last = tree.body[-1]
    assert isinstance(last, ast.If) and "P02BRIGHTEN_ARGS" in ast.unparse(last.test) and "unreal" in ast.unparse(last.test)


def _set_names(path):
    with open(path, encoding="utf-8") as h:
        tree = ast.parse(h.read())
    calls = [c for c in ast.walk(tree) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
             and c.func.attr == "set_editor_property"]
    names = {c.args[0].value for c in calls if c.args and isinstance(c.args[0], ast.Constant)}
    non_const = [ast.unparse(c) for c in calls if not (c.args and isinstance(c.args[0], ast.Constant))]
    return names, non_const


@case("write path writes ONLY intensity + drama strike/ramp/after_pass (AST: every set_editor_property call)")
def _():
    names, non_const = _set_names(os.path.join(HERE, "p02_brighten.py"))
    assert not non_const, non_const                                    # every field name is a literal
    assert names == {"intensity", "lighting", "drama", "strike_distance_cm", "strike_ramp_cm", "after_pass"}, names
    assert "unstruck_intensity_scale" not in names and "strike_on_approach" not in names
    # control: the same scan on lighting_looks_apply.py finds unstruck_intensity_scale (the scan can fail)
    other, _nc = _set_names(os.path.join(HERE, "lighting_looks_apply.py"))
    assert "unstruck_intensity_scale" in other and other - names


# ---------------------------------------------------------------- B. selection by route fraction
@case("selection: fraction >= 0.45 picks B12..B23 (B11 at 0.443 out, B12 at 0.485 in), both sets")
def _():
    sel = {b["bay_token"] for b in PLAN["bays"] if b["selected"]}
    assert sel == {"%02d" % n for n in range(12, 24)}, sorted(sel)
    fr = {b["bay_token"]: b["fraction"] for b in PLAN["bays"]}
    assert 0.44 < fr["11"] < 0.45 and 0.48 < fr["12"] < 0.49
    assert PLAN["first_selected"]["bay_token"] == "12"
    assert not any(int(t["bay_token"]) < 12 for t in PLAN["targets"])
    # control: from_fraction 0.5 drops B12 from BOTH sets
    p2 = plan_for(B.check_params({"from_fraction": 0.5}))
    assert "12" not in {b["bay_token"] for b in p2["bays"] if b["selected"]}
    assert all(int(t["bay_token"]) >= 13 for t in p2["targets"])
    assert any(t["bay_token"] == "12" and t["path"] == B.P_STRIKE for t in PLAN["targets"])


@case("selection follows LIVE distances, not labels: swap two stations and the selection swaps")
def _():
    st = copy.deepcopy(STATIONS)
    g02 = next(c["guid"] for c in CUES if ordinal(c) == 2)
    g20 = next(c["guid"] for c in CUES if ordinal(c) == 20)
    for s in st:
        if s["cue_guid"] == g02:
            s["distance_cm"] = 250.0 + 500.0 * 19
        elif s["cue_guid"] == g20:
            s["distance_cm"] = 750.0
    p2 = plan_for(stations=st)
    sel = {b["bay_token"] for b in p2["bays"] if b["selected"]}
    assert "02" in sel and "20" not in sel
    assert any(t["bay_token"] == "02" and t["path"] == B.P_STRIKE for t in p2["targets"])
    assert not any(t["bay_token"] == "20" for t in p2["targets"])


@case("stations: missing / duplicate / outside-route / zero route refused")
def _():
    refuses("STATION_COUNT", plan_for, stations=STATIONS[1:])
    refuses("STATION_COUNT", plan_for, stations=STATIONS + [dict(STATIONS[0])])
    bad = copy.deepcopy(STATIONS)
    bad[0]["distance_cm"] = ROUTE + 500.0
    refuses("STATION_OUTSIDE_ROUTE", plan_for, stations=bad)
    refuses("ROUTE_LENGTH_NOT_POSITIVE", plan_for, route=0.0)
    p = plain()
    p["bay_guids"].append("D" * 32)
    refuses("BAY_GUID_UNRESOLVED", plan_for, p=p)
    p = plain()
    p["bay_guids"].append(FOREIGN["guid"])
    refuses("BAY_NOT_P02", plan_for, p=p)


# ---------------------------------------------------------------- C. intensity set (unchanged from schema 1)
@case("intensity set with the APPLIED params reproduces the active record's 32 targets exactly (guid, before, after)")
def _():
    mine = {t["attachment_guid"]: (t["before"], t["after"]) for t in PLAN_A["targets"] if t["path"] == B.FIELD}
    rec = {t["attachment_guid"]: (t["before"], t["after"]) for t in REC1["plan"]["targets"]}
    assert len(rec) == 32 and mine == rec, sorted(set(mine) ^ set(rec))
    assert PLAN_A["counts"]["intensity_rows"] == 32
    # control: the default (120/2x/60/200) params do NOT reproduce it
    assert {t["attachment_guid"]: (t["before"], t["after"]) for t in PLAN_I["targets"]} != rec


@case("practicals (LUMENS): dead (0) and dim (<120) raised to exactly 120; >=120 untouched")
def _():
    prac = [t for t in PLAN_I["targets"] if t["kind"] == "practical"]
    assert all(t["after"] == 120.0 and t["before"] < 120.0 for t in prac)
    assert BY_LABEL["P02 SCORE B19 P02_FAILING_STAGE PRACTICAL_CLAMP"]["before"] == 88.0
    assert "P02 SCORE B18 P02_FAILING_STAGE PRACTICAL_CLAMP" not in BY_LABEL          # 209 stays
    assert "P02 SCORE B20 P02_MYSTIC PRACTICAL_L" not in BY_LABEL                     # 960 stays
    for n in range(12, 20):
        assert BY_LABEL["P02 SCORE B%02d P02_FAILING_STAGE PRACTICAL_BULB_DEAD" % n]["after"] == 120.0
    for n in (20, 21, 23):
        assert BY_LABEL["P02 SCORE B%02d P02_MYSTIC PRACTICAL_R" % n]["before"] == 0.0
    assert BY_LABEL["P02 SCORE B22 GAP PRACTICAL_DEAD"]["after"] == 120.0
    assert "P02 SCORE B22 GAP PRACTICAL_GLIMMER" not in BY_LABEL                      # 160 stays
    assert len(prac) == 13, len(prac)
    # the intensity targets are the same whether the drama set is on or off
    assert [t for t in PLAN["targets"] if t["path"] == B.FIELD] == PLAN_I["targets"]


@case("tops: max(before, min(200, max(2x, 60))), never lowered; MYSTIC 0 -> 60")
def _():
    want = {"B12 P02_FAILING_STAGE TOP_L": (51.0, 102.0), "B12 P02_FAILING_STAGE TOP_R": (34.0, 68.0),
            "B13 P02_FAILING_STAGE TOP_L": (44.4, 88.8), "B13 P02_FAILING_STAGE TOP_R": (29.6, 60.0),
            "B14 P02_FAILING_STAGE TOP_L": (37.8, 75.6), "B14 P02_FAILING_STAGE TOP_R": (25.2, 60.0),
            "B15 P02_FAILING_STAGE TOP_L": (31.2, 62.4)}
    for n in (20, 21, 23):
        for side in "LR":
            want["B%02d P02_MYSTIC TOP_%s" % (n, side)] = (0.0, 60.0)
    tops = {t["attachment_label"][len("P02 SCORE "):]: t for t in PLAN_I["targets"] if t["kind"] == "top"}
    assert set(tops) == set(want), sorted(set(tops) ^ set(want))
    for k, (b, a) in want.items():
        assert B.close(tops[k]["before"], b, 1e-6) and B.close(tops[k]["after"], a, 1e-6), (k, tops[k])
        assert tops[k]["after"] == B.f32(tops[k]["after"])
    p = plain()
    row = next(r for c in p["cues"] for r in c["attachments"] if r["label"] == "P02 SCORE B12 P02_FAILING_STAGE TOP_L")
    row["lighting"]["intensity"] = 300.0
    p2 = plan_for(PI, p=p)
    assert "P02 SCORE B12 P02_FAILING_STAGE TOP_L" not in {t["attachment_label"] for t in p2["targets"]}
    assert any(u["label"] == row["label"] and u["why"] == "AT_OR_ABOVE_TARGET" for u in p2["untouched"])


@case("intensity never targets BEAM_R, LOW_SIDE_*, *_BODY, first-half bays, non-SCORE rows, the foreign P01 cue")
def _():
    roles = {t["role"] for t in PLAN["targets"] if t["path"] == B.FIELD}
    assert roles <= {"TOP_L", "TOP_R", "PRACTICAL_BULB_DEAD", "PRACTICAL_CLAMP", "PRACTICAL_R", "PRACTICAL_DEAD"}, roles
    assert all(t["cue_guid"] != FOREIGN["guid"] for t in PLAN["targets"])
    assert all(B.SCORE_RE.match(t["attachment_label"]) for t in PLAN["targets"])
    assert not any(t["role"].endswith("_BODY") for t in PLAN["targets"])
    assert PLAN_I["counts"] == {**PLAN_I["counts"], "targets": 26, "intensity_rows": 26, "practical": 13, "top": 13,
                                "bays_selected": 12, "drama_fields": 0}


@case("disabled / skip_labels / wrong-unit rows are left alone and listed (controls)")
def _():
    label = "P02 SCORE B20 P02_MYSTIC TOP_L"
    p = plain()
    next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)["enabled"] = False
    p2 = plan_for(p=p)
    assert label not in {t["attachment_label"] for t in p2["targets"]}                    # neither set
    assert any(u["label"] == label and u["why"] == "DISABLED" for u in p2["untouched"])
    assert any(u["label"] == label and u["why"] == "DISABLED" for u in p2["drama_untouched"])
    p3 = plan_for(B.check_params({"skip_labels": [label]}))
    assert label not in {t["attachment_label"] for t in p3["targets"]}
    assert p3["counts"]["intensity_rows"] == 25 and p3["counts"]["drama_rows"] == PLAN["counts"]["drama_rows"] - 1
    p = plain()
    next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)["lighting"]["intensity_units"] = \
        "<InfinityStageLightIntensityUnits.LUMENS: 2>"
    p4 = plan_for(PI, p=p)
    assert label not in {t["attachment_label"] for t in p4["targets"]}
    assert any(w.startswith("UNITS_MISMATCH|" + label) for w in p4["warnings"])
    p6 = plan_for(B.check_params({"practical_units": "CANDELAS", "drama": False}))
    assert p6["counts"]["practical"] == 0 and p6["counts"]["top"] == 13
    p = plain()
    row = next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)
    row["label"] = "P02 SCORE B20 STROBE TOP_L"
    p5 = plan_for(p=p)
    assert any(u["why"] == "FORBIDDEN_LABEL" for u in p5["untouched"])
    assert any(u["why"] == "FORBIDDEN_LABEL" for u in p5["drama_untouched"])


@case("warnings: cool dead-bulb colour flagged (kept); bays with no TOP rows flagged; struck-only counted")
def _():
    cool = [w for w in PLAN["warnings"] if w.startswith("COOL_COLOUR|")]
    assert any("B19 P02_FAILING_STAGE PRACTICAL_BULB_DEAD" in w for w in cool)
    assert not any("PRACTICAL_R" in w or "PRACTICAL_DEAD|" in w for w in cool)
    notop = {w.split("|")[2] for w in PLAN["warnings"] if w.startswith("BAY_HAS_NO_TOP_ROWS|")}
    assert {"B16", "B17", "B18", "B19", "B22"} <= {x.split()[0] for x in notop}, notop
    assert PLAN["counts"]["struck_only"] > 0


# ---------------------------------------------------------------- D. drama set
@case("drama: EVERY enabled striking SCORE light in B12+ is a drama row (independent oracle), nothing else")
def _():
    oracle = {r["guid"] for r in second_half_lights()}
    rows = {t["attachment_guid"] for t in DRAMA_T}
    assert rows == oracle, (len(rows), len(oracle))
    roles = {t["role"] for t in DRAMA_T}
    assert {"BEAM_R", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "PRACTICAL_L", "PRACTICAL_GLIMMER"} <= roles, roles
    assert not any(t["role"].endswith("_BODY") or int(t["bay_token"]) < 12 or t["cue_guid"] == FOREIGN["guid"]
                   for t in DRAMA_T)
    assert {t["path"] for t in DRAMA_T} == {B.P_STRIKE, B.P_RAMP, B.P_AFTER}


@case("drama values: strike 650->2500, ramp 150->600 on every row; DECAY/EXTINGUISH->HOLD (B15-B19 only)")
def _():
    strike = [t for t in DRAMA_T if t["path"] == B.P_STRIKE]
    ramp = [t for t in DRAMA_T if t["path"] == B.P_RAMP]
    after = [t for t in DRAMA_T if t["path"] == B.P_AFTER]
    n = len(second_half_lights())
    assert len(strike) == n and len(ramp) == n
    assert all(t["before"] == 650.0 and t["after"] == 2500.0 for t in strike)
    assert all(t["before"] == 150.0 and t["after"] == 600.0 for t in ramp)
    assert {B._enum_name(t["before"]) for t in after} == {"DECAY", "EXTINGUISH"}
    assert all(t["after"] == "HOLD" for t in after)
    assert {t["bay_token"] for t in after} == {"15", "16", "17", "18", "19"}
    by_bay = {}
    for t in after:
        by_bay.setdefault(t["bay_token"], set()).add(B._enum_name(t["before"]))
    assert by_bay["15"] == by_bay["16"] == by_bay["17"] == {"DECAY"} and by_bay["18"] == by_bay["19"] == {"EXTINGUISH"}
    assert all(t["unstruck_intensity_scale"] == 0.0 for t in DRAMA_T)          # recorded, never written


@case("drama controls: never shortens a longer strike; no-op fields skipped; override null; skip role; drama off")
def _():
    label = "P02 SCORE B13 P02_FAILING_STAGE BEAM_R"
    p = plain()
    row = next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)
    row["lighting"]["drama"]["strike_distance_cm"] = 5400.0
    p2 = plan_for(p=p)
    assert not any(t["attachment_label"] == label and t["path"] == B.P_STRIKE for t in p2["targets"])
    assert any(t["attachment_label"] == label and t["path"] == B.P_RAMP for t in p2["targets"])
    row["lighting"]["drama"]["strike_ramp_cm"] = 600.0
    p3 = plan_for(p=p)
    assert not any(t["attachment_label"] == label for t in p3["targets"])
    assert any(u["label"] == label and u["why"] == "DRAMA_AT_TARGET" for u in p3["drama_untouched"])
    p4 = plan_for(B.check_params({"after_pass_override": None}))
    assert not any(t["path"] == B.P_AFTER for t in p4["targets"])
    assert p4["counts"]["strike_fields"] == PLAN["counts"]["strike_fields"]
    p5 = plan_for(B.check_params({"drama_skip_roles": ["BEAM_R"]}))
    assert not any(t["role"] == "BEAM_R" for t in p5["targets"])
    assert any(u["why"] == "DRAMA_SKIP_ROLE" for u in p5["drama_untouched"])
    assert PLAN_I["counts"]["drama_fields"] == 0 and not any(t["path"] != B.FIELD for t in PLAN_I["targets"])
    # a non-striking light is listed, not written (drama fields are inert when bStrikeOnApproach is false)
    p = plain()
    row = next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)
    row["lighting"]["drama"]["strike_on_approach"] = False
    p6 = plan_for(p=p)
    assert not any(t["attachment_label"] == label for t in p6["targets"])
    assert any(u["label"] == label and u["why"] == "NOT_STRIKE_ON_APPROACH" for u in p6["drama_untouched"])
    # an unknown AfterPass refuses
    p = plain()
    next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)["lighting"]["drama"]["after_pass"] = "X"
    refuses("AFTER_PASS_UNKNOWN", plan_for, p=p)


@case("expected targets / bays gate (pass + fail); counts are FIELDS")
def _():
    c = PLAN["counts"]
    assert c["targets"] == c["intensity_rows"] + c["drama_fields"]
    assert c["drama_fields"] == c["strike_fields"] + c["ramp_fields"] + c["after_pass_fields"]
    B.check_expected(PLAN, c["targets"], PLAN["selected_bays"])
    refuses("EXPECTED_TARGETS", B.check_expected, PLAN, c["intensity_rows"], None)   # the old row count fails
    refuses("EXPECTED_BAYS", B.check_expected, PLAN, None, PLAN["selected_bays"][1:])


# ---------------------------------------------------------------- E. scope, revert, export
@case("model: only the targets' four fields differ (intensity + drama strike/ramp/after_pass); scope passes")
def _():
    base = all_rows(plain())
    for plan in (PLAN, PLAN_A):
        after = B.apply_rows(base, plan["targets"], "after")
        assert not B.scope_problems(base, after, plan["targets"], "after", DIFF)
        want = {}
        for t in plan["targets"]:
            want.setdefault(t["attachment_guid"], set()).add(t["path"])
        for g in base:
            for b, a in zip(base[g], after[g]):
                d = {x["path"] for x in DIFF(b, a)}
                assert d == want.get(b["guid"], set()), (b["label"], d)
                assert d <= set(B.PATHS)
    # the plain read after a live write says '<InfinityLightAfterPass.HOLD: 0>', the plan says 'HOLD': same value
    live = B.apply_rows(base, PLAN["targets"], "after")
    for t in PLAN["targets"]:
        if t["path"] == B.P_AFTER:
            B.set_field(B._row(live, t), t["path"], "<InfinityLightAfterPass.HOLD: 0>")
    assert not B.scope_problems(base, live, PLAN["targets"], "after", DIFF)


@case("scope controls: unstruck scale, after-pass distance, wrong enum, strike off, neighbour, colour, order caught")
def _():
    base = all_rows(plain())
    t = next(x for x in PLAN["targets"] if x["path"] == B.P_AFTER)
    for what in ("unstruck", "apdist", "enum", "strike_flag", "neighbour_drama", "colour", "wrong_strike", "outside",
                 "order", "decay_dist"):
        bad = B.apply_rows(base, PLAN["targets"], "after")
        rows = bad[t["cue_guid"]]
        row = next(r for r in rows if r["guid"] == t["attachment_guid"])
        if what == "unstruck":
            row["lighting"]["drama"]["unstruck_intensity_scale"] = 0.2
        elif what == "apdist":
            row["lighting"]["drama"]["after_pass_distance_cm"] = 0.0
        elif what == "enum":
            row["lighting"]["drama"]["after_pass"] = "<InfinityLightAfterPass.DECAY: 1>"
        elif what == "strike_flag":
            row["lighting"]["drama"]["strike_on_approach"] = False
        elif what == "decay_dist":
            row["lighting"]["drama"]["decay_distance_cm"] = 1.0
        elif what == "neighbour_drama":
            first = next(c for c in plain()["cues"] if c["guid"] not in PLAN["target_cue_guids"]
                         and c["guid"] != FOREIGN["guid"])
            next(r for r in bad[first["guid"]] if "LIGHT" in r["kind"])["lighting"]["drama"]["strike_distance_cm"] = 1234.0
        elif what == "colour":
            row["lighting"]["color"][0] = 0.5
        elif what == "wrong_strike":
            row["lighting"]["drama"]["strike_distance_cm"] = 2400.0
        elif what == "outside":
            bad[FOREIGN["guid"]][0]["lighting"]["drama"]["strike_ramp_cm"] = 600.0
        else:
            rows[0], rows[1] = rows[1], rows[0]
        assert B.scope_problems(base, bad, PLAN["targets"], "after", DIFF), what


@case("revert: before values restore the base exactly (floats bit-exact, enum by name); drift + 1-ulp controls")
def _():
    base = all_rows(plain())
    after = B.apply_rows(base, PLAN["targets"], "after")
    assert not B.field_drifts(after, PLAN["targets"], "after")
    back = B.apply_rows(after, PLAN["targets"], "before")
    assert all(not DIFF(b, a) for g in base for b, a in zip(base[g], back[g]))
    assert not B.exact_problems(back, PLAN["targets"], "before")
    assert not B.scope_problems(after, back, PLAN["targets"], "before", DIFF)
    hand = copy.deepcopy(after)
    t0 = next(x for x in PLAN["targets"] if x["path"] == B.FIELD)
    t1 = next(x for x in PLAN["targets"] if x["path"] == B.P_AFTER)
    B._row(hand, t0)["lighting"]["intensity"] = 7.0
    B._row(hand, t1)["lighting"]["drama"]["after_pass"] = "<InfinityLightAfterPass.EXTINGUISH: 2>"
    drifts = B.field_drifts(hand, PLAN["targets"], "after")
    assert {(d["guid"], d["path"]) for d in drifts} == {(t0["attachment_guid"], B.FIELD),
                                                       (t1["attachment_guid"], B.P_AFTER)}
    for path in (B.FIELD, B.P_STRIKE):
        ulp = copy.deepcopy(back)
        t = next(x for x in PLAN["targets"] if x["path"] == path and x["before"] > 0)
        row = B._row(ulp, t)
        v = B.get_field(row, path)
        B.set_field(row, path, struct.unpack("<d", struct.pack("<Q", struct.unpack("<Q", struct.pack("<d", v))[0] + 1))[0])
        assert B.exact_problems(ulp, PLAN["targets"], "before"), path
    rec = {"passage": "P02", "status": "saved_readback_verified", "plan": PLAN, "schema_version": 2}
    B.check_record(rec)
    refuses("REVERT_RECORD_STATUS", B.check_record, dict(rec, status="prepared"))
    refuses("RECORD_PASSAGE_MISMATCH", B.check_record, dict(rec, passage="P03"))
    refuses("RECORD_SCHEMA", B.check_record, dict(rec, schema_version=3))
    bad = copy.deepcopy(rec)
    bad["plan"]["targets"][0]["path"] = "lighting.drama.unstruck_intensity_scale"
    refuses("TARGET_PATH_NOT_ALLOWED", B.check_record, bad)
    bad = copy.deepcopy(rec)
    del bad["plan"]["targets"][0]["before"]
    refuses("RECORD_TARGET_NO_ORIGINAL", B.check_record, bad)


@case("sequence on the REAL active schema-1 record: REVERT model -> DRY -> APPLY both sets -> REVERT v2")
def _():
    B.check_record(REC1)                                              # REVERT accepts the schema-1 record
    assert all(t["path"] == B.FIELD for t in REC1["plan"]["targets"])
    base = all_rows(plain())
    live = B.apply_rows(base, REC1["plan"]["targets"], "after")      # the Show as it is now (APPLIED)
    assert not B.field_drifts(live, REC1["plan"]["targets"], "after")
    reverted = B.apply_rows(live, REC1["plan"]["targets"], "before")
    assert not B.exact_problems(reverted, REC1["plan"]["targets"], "before")
    assert not B.scope_problems(live, reverted, REC1["plan"]["targets"], "before", DIFF)
    assert all(not DIFF(b, a) for g in base for b, a in zip(base[g], reverted[g]))
    p = plain()
    for c in p["cues"]:
        c["attachments"] = reverted[c["guid"]]
    dry = plan_for(PA, p=p)
    assert dry["targets"] == PLAN_A["targets"]
    assert dry["counts"]["intensity_rows"] == 32
    applied = B.apply_rows(reverted, dry["targets"], "after")
    assert not B.scope_problems(reverted, applied, dry["targets"], "after", DIFF)
    back = B.apply_rows(applied, dry["targets"], "before")
    assert not B.exact_problems(back, dry["targets"], "before")
    # control: a DRY taken WITHOUT reverting first sees the raised intensities and plans fewer intensity rows
    p = plain()
    for c in p["cues"]:
        c["attachments"] = live[c["guid"]]
    assert plan_for(PA, p=p)["counts"]["intensity_rows"] < 32


_DEFAULT_DRAMA = {"strike_distance_cm": 2500.0, "strike_ramp_cm": 250.0, "unstruck_intensity_scale": 0.0,
                  "after_pass_distance_cm": 600.0, "decay_distance_cm": 1500.0}


def _export(rows, drama_group=True):
    """ExportText-shaped text; Drama fields at their default are OMITTED (as UE does), AfterPass is the last item."""
    parts = []
    for r in rows:
        loc = r["relative_transform"]["location"]
        d = r["lighting"]["drama"]
        items = ["bStrikeOnApproach=%s" % ("True" if d["strike_on_approach"] else "False")]
        names = (("strike_distance_cm", "StrikeDistanceCm"), ("strike_ramp_cm", "StrikeRampCm"),
                 ("unstruck_intensity_scale", "UnstruckIntensityScale"))
        for key, name in names:
            if d[key] != _DEFAULT_DRAMA[key]:
                items.append("%s=%f" % (name, d[key]))
        ap = B._enum_name(d["after_pass"])
        if ap != "HOLD":
            items.append("AfterPass=%s" % ap.title())
        for key, name in (("after_pass_distance_cm", "AfterPassDistanceCm"), ("decay_distance_cm", "DecayDistanceCm")):
            if d[key] != _DEFAULT_DRAMA[key]:
                items.append("%s=%f" % (name, d[key]))
        drama = (",Drama=(" + ",".join(items) + ")") if drama_group else ""
        parts.append("(AttachmentGuid=%s,Label=\"%s\",RelativeTransform=(Translation=(X=%r,Y=%r,Z=%r)),"
                     "Lighting=(Type=Spot,IntensityUnits=Candelas,Intensity=%r,Color=(R=%r,G=%r,B=%r,A=1.0),"
                     "VolumetricScatteringIntensity=1.0%s),Body=(Intensity=3.0))"
                     % ((r["guid"], r["label"]) + tuple(loc) + (r["lighting"]["intensity"],)
                        + tuple(r["lighting"]["color"][:3]) + (drama,)))
    return "(WingPair=(Attachments=(" + ",".join(parts) + ")))"


@case("export hash masks exactly the targets' Intensity + Drama Strike/Ramp/AfterPass (omitted-at-default safe)")
def _():
    base = all_rows(plain())
    after = B.apply_rows(base, PLAN["targets"], "after")
    tb = [_export(base[g]) for g in sorted(base)]
    ta = [_export(after[g]) for g in sorted(after)]
    assert "AfterPass=Decay," in "".join(tb) and "AfterPass=Extinguish," in "".join(tb)
    # omitted-at-default shapes: AfterPass as the LAST item, StrikeDistanceCm absent after (2500 = default)
    g = "A" * 32
    seg_b = "(AttachmentGuid=%s,Lighting=(Intensity=1.0,Drama=(bStrikeOnApproach=True,StrikeDistanceCm=650.000000,"             "AfterPass=Decay),X=1),Body=(Intensity=3.0))" % g
    seg_a = "(AttachmentGuid=%s,Lighting=(Intensity=1.0,Drama=(bStrikeOnApproach=True),X=1),Body=(Intensity=3.0))" % g
    names = ["StrikeDistanceCm", "AfterPass"]
    assert B.mask_drama(seg_b, g, names) == B.mask_drama(seg_a, g, names)
    assert B.mask_drama(seg_b, g, ["StrikeDistanceCm"]) != B.mask_drama(seg_a, g, ["StrikeDistanceCm"])  # control
    assert "AfterPassDistanceCm=1" in B.mask_drama(seg_b.replace("Decay)", "Decay,AfterPassDistanceCm=1)"), g, names)
    refuses("EXPORT_AFTERPASS_COUNT", B.mask_drama, seg_b.replace("Decay)", "Decay,AfterPass=Hold)"), g, names)
    assert ta != tb and B.export_hash(RP, ta, PLAN["targets"]) == B.export_hash(RP, tb, PLAN["targets"])
    t = next(x for x in PLAN["targets"] if x["path"] == B.P_AFTER)
    for what in ("unstruck", "apdist", "colour", "neighbour", "translation", "strike_flag"):
        bad = copy.deepcopy(after)
        row = B._row(bad, t)
        if what == "unstruck":
            row["lighting"]["drama"]["unstruck_intensity_scale"] = 0.5
        elif what == "apdist":
            row["lighting"]["drama"]["after_pass_distance_cm"] = 100.0
        elif what == "colour":
            row["lighting"]["color"][1] = 0.123
        elif what == "neighbour":
            next(r for r in bad[t["cue_guid"]] if r["guid"] not in PLAN["target_attachment_guids"]
                 and "LIGHT" in r["kind"])["lighting"]["intensity"] = 1.5
        elif what == "translation":
            row["relative_transform"]["location"][2] += 1.0
        else:
            row["lighting"]["drama"]["strike_on_approach"] = False
        tx = [_export(bad[g]) for g in sorted(bad)]
        assert B.export_hash(RP, tx, PLAN["targets"]) != B.export_hash(RP, tb, PLAN["targets"]), what
    # control: masking only intensity (the schema-1 target set) does NOT hide the drama change
    assert B.export_hash(RP, ta, PLAN_I["targets"]) != B.export_hash(RP, tb, PLAN_I["targets"])
    # control: a strike change on a NON-target row is still counted
    bad = copy.deepcopy(base)
    first = next(c for c in plain()["cues"] if c["guid"] not in PLAN["target_cue_guids"] and c["guid"] != FOREIGN["guid"])
    next(r for r in bad[first["guid"]] if "LIGHT" in r["kind"])["lighting"]["drama"]["strike_ramp_cm"] = 600.0
    assert B.export_hash(RP, [_export(bad[g]) for g in sorted(bad)], PLAN["targets"]) != \
        B.export_hash(RP, tb, PLAN["targets"])
    refuses("EXPORT_TARGET_COUNT", B.export_hash, RP, tb,
            PLAN["targets"] + [{"attachment_guid": "E" * 31 + "0", "path": B.FIELD}])
    refuses("EXPORT_NO_DRAMA", B.export_hash, RP, [_export(base[g], False) for g in sorted(base)], PLAN["targets"])
    # the intensity-only mask still works on a text without Drama (schema-1 revert path)
    nod = [_export(base[g], False) for g in sorted(base)]
    nod_a = [_export(B.apply_rows(base, PLAN_I["targets"], "after")[g], False) for g in sorted(base)]
    assert B.export_hash(RP, nod, PLAN_I["targets"]) == B.export_hash(RP, nod_a, PLAN_I["targets"])


# ---------------------------------------------------------------- F. foreign records
@case("foreign records: unacked = hits - acks; a real offline scan of Saved/Codex* runs (listed in the summary)")
def _():
    hits = [{"path": "a.json"}, {"path": "b.json"}]
    assert B.unacked_records(hits, ["a.json"]) == ["b.json"]
    assert B.unacked_records(hits, ["a.json", "b.json"]) == []
    saved = os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    found = SCORES.scan_foreign_records(roots, PLAN["target_attachment_guids"], exclude=[B.RECORD_PATH])
    FOREIGN_FOUND.extend(sorted(h["path"] for h in found))
    assert any(p.endswith("p02_rig_pattern_record.json") for p in FOREIGN_FOUND), FOREIGN_FOUND


if __name__ == "__main__":
    for name, ok, detail in RESULTS:
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            print(detail)
    print("\nPlanned with the args params (synthetic stations; the live DRY decides):")
    for t in PLAN_A["targets"]:
        print("  %-48s %-9s %-34s %s -> %s  frac=%.3f" % (t["attachment_label"], t["kind"], t["path"],
                                                         B._short(t["before"]), B._short(t["after"]), t["fraction"]))
    print("counts(args params)=%s" % json.dumps(PLAN_A["counts"], sort_keys=True))
    print("drama_untouched(args params)=%s" % json.dumps(sorted({u["why"] for u in PLAN_A["drama_untouched"]})))
    print("foreign active records naming a target (offline scan): %s" % FOREIGN_FOUND)
    failed = sum(1 for r in RESULTS if not r[1])
    print("\nPASS %d / FAIL %d" % (len(RESULTS) - failed, failed))
    sys.exit(1 if failed else 0)
