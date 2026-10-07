"""Offline harness for p02_brighten.py (pure Python, no unreal). Run: python test_p02_brighten_offline.py

Fixture = the real P02 Show rows as last recorded: p02_rig_pattern_record.json after_cue_rows (21 cues, APPLY 6 Oct
22:38, saved_readback_verified) + the two GAP bays (P02 Wing 007 / 022) from lighting_scores_record_P02.json
after_rows, plus a foreign P01 cue with a look-alike row. Stations are SYNTHETIC (inferred, not live): bay ordinal n at
250 + 500 (n-1) cm on an 11857.83 cm route (uniform intervals in passage_slow_walk_P02_latest.json; required_cm in
p02_straighten_dry_P02STR-20261007-015527.json). Every gate has a passing case and a failing control.
Prints PASS/FAIL per case and a summary; exits non-zero on any failure.
"""
from __future__ import annotations

import ast
import copy
import json
import os
import re
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
BAYS_INFO = {b["cue_guid"]: b for b in RIG["plan"]["bays"]}
CUES = []
for g, rows in RIG["after_cue_rows"].items():
    b = BAYS_INFO[g]
    CUES.append({"guid": g, "label": b["cue_label"], "show_index": b["show_index"], "attachments": copy.deepcopy(rows)})
for t in SCO["plan"]["targets"]:
    if t["cue_label"] in ("P02 Wing 007", "P02 Wing 022"):
        CUES.append({"guid": t["cue_guid"], "label": t["cue_label"], "show_index": t["show_index"],
                     "attachments": copy.deepcopy(t["after_rows"])})
CUES.sort(key=lambda c: c["show_index"])
assert len(CUES) == 23, len(CUES)
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


P = B.check_params({})


def plan_for(params=None, p=None, stations=None, route=ROUTE):
    return B.build_plan(p or plain(), stations or STATIONS, route, params or P, RP.FORBIDDEN_TARGET_LABEL)


PLAN = plan_for()
BY_LABEL = {t["attachment_label"]: t for t in PLAN["targets"]}


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


@case("params: defaults; unknown key, out-of-range, floor>max, too-wide practical regex, non-TOP role refused")
def _():
    assert (P["from_fraction"], P["practical_floor"], P["top_scale"], P["top_floor_cd"], P["top_max_cd"]) == \
        (0.45, 120.0, 2.0, 60.0, 200.0) and (P["practical_units"], P["top_units"]) == ("LUMENS", "CANDELAS")
    refuses("PARAM_UNITS", B.check_params, {"practical_units": "LUX"})
    refuses("PARAMS_UNKNOWN", B.check_params, {"from_fracton": 0.4})
    refuses("PARAM_RANGE", B.check_params, {"top_scale": 0.5})            # never dims
    refuses("PARAM_RANGE", B.check_params, {"practical_floor": 5000})
    refuses("PARAM_TOP_FLOOR_ABOVE_MAX", B.check_params, {"top_floor_cd": 300, "top_max_cd": 200})
    refuses("PARAM_PRACTICAL_ROLE_RE_TOO_WIDE", B.check_params, {"practical_role_re": ".*"})
    refuses("PARAM_TOP_ROLES", B.check_params, {"top_roles": ["TOP_L", "BEAM_R"]})
    refuses("NOT_NUMBER", B.check_params, {"top_scale": True})


@case("files: args DRY + valid, request runs p02_brighten_run.py, all files parse, main guard shape")
def _():
    a = load("p02_brighten_args.json")
    assert a["mode"] == "DRY" and B.check_args(a)["mode"] == "DRY"
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


@case("write path writes ONLY lighting.intensity (AST: every set_editor_property call in p02_brighten.py)")
def _():
    with open(os.path.join(HERE, "p02_brighten.py"), encoding="utf-8") as h:
        tree = ast.parse(h.read())
    names = [c.args[0].value for c in ast.walk(tree) if isinstance(c, ast.Call)
             and isinstance(c.func, ast.Attribute) and c.func.attr == "set_editor_property"
             and c.args and isinstance(c.args[0], ast.Constant)]
    assert sorted(set(names)) == ["intensity", "lighting"], names
    # control: the same scan on p03_atmos.py finds other fields (the scan can fail)
    with open(os.path.join(HERE, "p03_atmos.py"), encoding="utf-8") as h:
        other = ast.parse(h.read())
    names2 = {c.args[0].value for c in ast.walk(other) if isinstance(c, ast.Call)
              and isinstance(c.func, ast.Attribute) and c.func.attr == "set_editor_property"
              and c.args and isinstance(c.args[0], ast.Constant)}
    assert names2 - {"intensity", "lighting"}


# ---------------------------------------------------------------- B. selection by route fraction
@case("selection: fraction >= 0.45 picks B12..B23 (B11 at 0.443 out, B12 at 0.485 in)")
def _():
    sel = {b["bay_token"] for b in PLAN["bays"] if b["selected"]}
    assert sel == {"%02d" % n for n in range(12, 24)}, sorted(sel)
    fr = {b["bay_token"]: b["fraction"] for b in PLAN["bays"]}
    assert 0.44 < fr["11"] < 0.45 and 0.48 < fr["12"] < 0.49
    assert PLAN["first_selected"]["bay_token"] == "12"
    assert not any(int(t["bay_token"]) < 12 for t in PLAN["targets"])
    # control: from_fraction 0.5 drops B12
    p2 = plan_for(B.check_params({"from_fraction": 0.5}))
    assert "12" not in {b["bay_token"] for b in p2["bays"] if b["selected"]}
    assert all(int(t["bay_token"]) >= 13 for t in p2["targets"])


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


# ---------------------------------------------------------------- C. targets and values
@case("practicals (LUMENS): dead (0) and dim (<120) raised to exactly 120; >=120 untouched")
def _():
    prac = [t for t in PLAN["targets"] if t["kind"] == "practical"]
    assert all(t["after"] == 120.0 and t["before"] < 120.0 for t in prac)
    assert BY_LABEL["P02 SCORE B19 P02_FAILING_STAGE PRACTICAL_CLAMP"]["before"] == 88.0
    assert "P02 SCORE B18 P02_FAILING_STAGE PRACTICAL_CLAMP" not in BY_LABEL          # 209 cd stays
    assert "P02 SCORE B20 P02_MYSTIC PRACTICAL_L" not in BY_LABEL                     # 960 cd stays
    for n in range(12, 20):
        assert BY_LABEL["P02 SCORE B%02d P02_FAILING_STAGE PRACTICAL_BULB_DEAD" % n]["after"] == 120.0
    for n in (20, 21, 23):
        assert BY_LABEL["P02 SCORE B%02d P02_MYSTIC PRACTICAL_R" % n]["before"] == 0.0
    assert BY_LABEL["P02 SCORE B22 GAP PRACTICAL_DEAD"]["after"] == 120.0
    assert "P02 SCORE B22 GAP PRACTICAL_GLIMMER" not in BY_LABEL                      # 160 cd stays
    assert len(prac) == 13, len(prac)


@case("tops: max(before, min(200, max(2x, 60))), never lowered; MYSTIC 0 -> 60")
def _():
    want = {"B12 P02_FAILING_STAGE TOP_L": (51.0, 102.0), "B12 P02_FAILING_STAGE TOP_R": (34.0, 68.0),
            "B13 P02_FAILING_STAGE TOP_L": (44.4, 88.8), "B13 P02_FAILING_STAGE TOP_R": (29.6, 60.0),
            "B14 P02_FAILING_STAGE TOP_L": (37.8, 75.6), "B14 P02_FAILING_STAGE TOP_R": (25.2, 60.0),
            "B15 P02_FAILING_STAGE TOP_L": (31.2, 62.4)}
    for n in (20, 21, 23):
        for side in "LR":
            want["B%02d P02_MYSTIC TOP_%s" % (n, side)] = (0.0, 60.0)
    tops = {t["attachment_label"][len("P02 SCORE "):]: t for t in PLAN["targets"] if t["kind"] == "top"}
    assert set(tops) == set(want), sorted(set(tops) ^ set(want))
    for k, (b, a) in want.items():
        assert B.close(tops[k]["before"], b, 1e-6) and B.close(tops[k]["after"], a, 1e-6), (k, tops[k])
        assert tops[k]["after"] == B.f32(tops[k]["after"])
    # control: a TOP already at 300 is left alone (never lowered by the 200 cap)
    p = plain()
    row = next(r for c in p["cues"] for r in c["attachments"] if r["label"] == "P02 SCORE B12 P02_FAILING_STAGE TOP_L")
    row["lighting"]["intensity"] = 300.0
    p2 = plan_for(p=p)
    assert "P02 SCORE B12 P02_FAILING_STAGE TOP_L" not in {t["attachment_label"] for t in p2["targets"]}
    assert any(u["label"] == row["label"] and u["why"] == "AT_OR_ABOVE_TARGET" for u in p2["untouched"])


@case("never targeted: BEAM_R, LOW_SIDE_*, *_BODY, first-half bays, non-SCORE rows, the foreign P01 cue")
def _():
    roles = {t["role"] for t in PLAN["targets"]}
    assert roles <= {"TOP_L", "TOP_R", "PRACTICAL_BULB_DEAD", "PRACTICAL_CLAMP", "PRACTICAL_R", "PRACTICAL_DEAD"}, roles
    assert not any("BEAM" in r or "LOW_SIDE" in r or r.endswith("_BODY") for r in roles)
    assert all(t["cue_guid"] != FOREIGN["guid"] for t in PLAN["targets"])
    assert all(B.SCORE_RE.match(t["attachment_label"]) for t in PLAN["targets"])
    assert PLAN["counts"] == {**PLAN["counts"], "targets": 26, "practical": 13, "top": 13, "bays_selected": 12}


@case("disabled / skip_labels / wrong-unit rows are left alone and listed (controls)")
def _():
    label = "P02 SCORE B20 P02_MYSTIC TOP_L"
    p = plain()
    next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)["enabled"] = False
    p2 = plan_for(p=p)
    assert label not in {t["attachment_label"] for t in p2["targets"]}
    assert any(u["label"] == label and u["why"] == "DISABLED" for u in p2["untouched"])
    p3 = plan_for(B.check_params({"skip_labels": [label]}))
    assert label not in {t["attachment_label"] for t in p3["targets"]} and p3["counts"]["targets"] == 25
    p = plain()
    next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)["lighting"]["intensity_units"] = \
        "<InfinityStageLightIntensityUnits.LUMENS: 2>"
    p4 = plan_for(p=p)
    assert label not in {t["attachment_label"] for t in p4["targets"]}
    assert any(w.startswith("UNITS_MISMATCH|" + label) for w in p4["warnings"])
    # control: practical_units CANDELAS refuses every P02 practical (they are LUMENS) -> only tops remain
    p6 = plan_for(B.check_params({"practical_units": "CANDELAS"}))
    assert p6["counts"]["practical"] == 0 and p6["counts"]["top"] == 13
    # control: a forbidden word in a label keeps the row out
    p = plain()
    row = next(r for c in p["cues"] for r in c["attachments"] if r["label"] == label)
    row["label"] = "P02 SCORE B20 STROBE TOP_L"
    p5 = plan_for(p=p)
    assert any(u["why"] == "FORBIDDEN_LABEL" for u in p5["untouched"])


@case("warnings: cool dead-bulb colour flagged (kept); bays with no TOP rows flagged; struck-only counted")
def _():
    cool = [w for w in PLAN["warnings"] if w.startswith("COOL_COLOUR|")]
    assert any("B19 P02_FAILING_STAGE PRACTICAL_BULB_DEAD" in w for w in cool)
    assert not any("PRACTICAL_R" in w or "PRACTICAL_DEAD|" in w for w in cool)    # warm ones not flagged
    notop = {w.split("|")[2] for w in PLAN["warnings"] if w.startswith("BAY_HAS_NO_TOP_ROWS|")}
    assert {"B16", "B17", "B18", "B19", "B22"} <= {x.split()[0] for x in notop}, notop
    assert PLAN["counts"]["struck_only"] > 0


@case("expected targets / bays gate (pass + fail)")
def _():
    B.check_expected(PLAN, 26, PLAN["selected_bays"])
    refuses("EXPECTED_TARGETS", B.check_expected, PLAN, 25, None)
    refuses("EXPECTED_BAYS", B.check_expected, PLAN, None, PLAN["selected_bays"][1:])


# ---------------------------------------------------------------- D. scope, revert, export
@case("model: only targets' lighting.intensity differs; scope passes")
def _():
    base = all_rows(plain())
    after = B.apply_rows(base, PLAN["targets"], "after")
    assert not B.scope_problems(base, after, PLAN["targets"], "after", DIFF)
    targets = set(PLAN["target_attachment_guids"])
    changed = 0
    for g in base:
        for b, a in zip(base[g], after[g]):
            d = DIFF(b, a)
            if b["guid"] not in targets:
                assert not d, b["label"]
            else:
                assert [x["path"] for x in d] == ["lighting.intensity"], d
                changed += 1
    assert changed == 26


@case("scope controls: colour on a target, neighbour intensity, wrong value, outside cue, row order all caught")
def _():
    base = all_rows(plain())
    t = PLAN["targets"][0]
    for what in ("colour", "neighbour", "wrong", "outside", "order"):
        bad = B.apply_rows(base, PLAN["targets"], "after")
        rows = bad[t["cue_guid"]]
        if what == "colour":
            next(r for r in rows if r["guid"] == t["attachment_guid"])["lighting"]["color"][0] = 0.5
        elif what == "neighbour":
            next(r for r in rows if r["guid"] not in PLAN["target_attachment_guids"])["lighting"]["intensity"] += 1.0
        elif what == "wrong":
            next(r for r in rows if r["guid"] == t["attachment_guid"])["lighting"]["intensity"] = 999.0
        elif what == "outside":
            bad[FOREIGN["guid"]][0]["lighting"]["intensity"] = 5.0
        else:
            rows[0], rows[1] = rows[1], rows[0]
        assert B.scope_problems(base, bad, PLAN["targets"], "after", DIFF), what


@case("revert: before values restore the base exactly; drift and 1-ulp controls caught")
def _():
    base = all_rows(plain())
    after = B.apply_rows(base, PLAN["targets"], "after")
    assert not B.field_drifts(after, PLAN["targets"], "after")
    back = B.apply_rows(after, PLAN["targets"], "before")
    assert all(not DIFF(b, a) for g in base for b, a in zip(base[g], back[g]))
    assert not B.exact_problems(back, PLAN["targets"], "before")
    assert not B.scope_problems(after, back, PLAN["targets"], "before", DIFF)
    hand = copy.deepcopy(after)
    t0, t1 = PLAN["targets"][0], PLAN["targets"][5]
    for t in (t0, t1):
        next(r for r in hand[t["cue_guid"]] if r["guid"] == t["attachment_guid"])["lighting"]["intensity"] = 7.0
    drifts = B.field_drifts(hand, PLAN["targets"], "after")
    assert {d["guid"] for d in drifts} == {t0["attachment_guid"], t1["attachment_guid"]}   # ALL drifts listed
    import struct
    ulp = copy.deepcopy(back)
    t = next(x for x in PLAN["targets"] if x["before"] > 0)
    row = next(r for r in ulp[t["cue_guid"]] if r["guid"] == t["attachment_guid"])
    bits = struct.unpack("<I", struct.pack("<f", row["lighting"]["intensity"]))[0]
    row["lighting"]["intensity"] = struct.unpack("<f", struct.pack("<I", bits + 1))[0]
    assert B.exact_problems(ulp, PLAN["targets"], "before")
    rec = {"passage": "P02", "status": "saved_readback_verified", "plan": PLAN}
    B.check_record(rec)
    refuses("REVERT_RECORD_STATUS", B.check_record, dict(rec, status="prepared"))
    refuses("RECORD_PASSAGE_MISMATCH", B.check_record, dict(rec, passage="P03"))


def _export(rows):
    parts = []
    for r in rows:
        loc = r["relative_transform"]["location"]
        parts.append("(AttachmentGuid=%s,Label=\"%s\",RelativeTransform=(Translation=(X=%r,Y=%r,Z=%r)),"
                     "Lighting=(Type=Spot,IntensityUnits=Candelas,Intensity=%r,Color=(R=%r,G=%r,B=%r,A=1.0),"
                     "VolumetricScatteringIntensity=1.0,Drama=(UnstruckIntensityScale=0.0)),Body=(Intensity=3.0))"
                     % ((r["guid"], r["label"]) + tuple(loc) + (r["lighting"]["intensity"],)
                        + tuple(r["lighting"]["color"][:3])))
    return "(WingPair=(Attachments=(" + ",".join(parts) + ")))"


@case("export hash masks exactly the targets' Lighting.Intensity (colour, nested, neighbours still counted)")
def _():
    base = all_rows(plain())
    after = B.apply_rows(base, PLAN["targets"], "after")
    tb = [_export(base[g]) for g in sorted(base)]
    ta = [_export(after[g]) for g in sorted(after)]
    guids = PLAN["target_attachment_guids"]
    assert ta != tb and B.export_hash(RP, ta, guids) == B.export_hash(RP, tb, guids)
    t = PLAN["targets"][0]
    for what in ("colour", "neighbour", "unmasked_scale"):
        bad = copy.deepcopy(after)
        rows = bad[t["cue_guid"]]
        if what == "colour":
            next(r for r in rows if r["guid"] == t["attachment_guid"])["lighting"]["color"][1] = 0.123
        elif what == "neighbour":
            next(r for r in rows if r["guid"] not in guids)["lighting"]["intensity"] = 1.5
        else:
            next(r for r in rows if r["guid"] == t["attachment_guid"])["relative_transform"]["location"][2] += 1.0
        tx = [_export(bad[g]) for g in sorted(bad)]
        assert B.export_hash(RP, tx, guids) != B.export_hash(RP, tb, guids), what
    # nested Drama UnstruckIntensityScale and Body Intensity are NOT masked
    nested = [x.replace("UnstruckIntensityScale=0.0", "UnstruckIntensityScale=0.5", 1) for x in ta]
    assert B.export_hash(RP, nested, guids) != B.export_hash(RP, tb, guids)
    refuses("EXPORT_TARGET_COUNT", B.export_hash, RP, tb, guids + ["E" * 31 + "0"])


# ---------------------------------------------------------------- E. foreign records
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
    print("\nPlanned rows (synthetic stations; the live DRY decides):")
    for t in PLAN["targets"]:
        print("  %-48s %-9s %7.1f -> %6.1f  frac=%.3f" % (t["attachment_label"], t["kind"], t["before"], t["after"],
                                                        t["fraction"]))
    print("counts=%s" % json.dumps(PLAN["counts"], sort_keys=True))
    print("foreign active records naming a target (offline scan): %s" % FOREIGN_FOUND)
    failed = sum(1 for r in RESULTS if not r[1])
    print("\nPASS %d / FAIL %d" % (len(RESULTS) - failed, failed))
    sys.exit(1 if failed else 0)
