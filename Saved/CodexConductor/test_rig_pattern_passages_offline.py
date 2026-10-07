"""Offline harness for the P02/P03 generalisation of p01_rig_pattern.py (pure Python, no unreal).

Run: python test_rig_pattern_passages_offline.py   (test_p01_rig_pattern_offline.py must still pass unchanged too)
Reuses the P01 harness's fake-Show builders; adds P02/P03 bays (FAILING_STAGE bays with missing roles, MYSTIC,
GAP, parity-fallback bays). Every gate has a passing case and a failing control. Also replays the REAL files:
the live P01 record (REVERT model), and P02/P03 plans built from lighting_scores_record_P02/P03.json after_rows
with the P01 record's template roles (record state, not live state). Prints "PASS n/FAIL m".
"""
from __future__ import annotations

import ast
import copy
import glob
import importlib.util
import json
import os
import re
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = _load("test_p01_rig_pattern_offline", os.path.join(HERE, "test_p01_rig_pattern_offline.py"))   # builders
M, TOOL, SCORES = H.M, H.TOOL, H.SCORES
OLD_PATHS = sorted(glob.glob(os.path.join(PROJECT, "Backups", "PreRigPatternGeneralise-*", "p01_rig_pattern.py")))
OLD = _load("p01_rig_pattern_pre_generalise", OLD_PATHS[0]) if OLD_PATHS else None

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


refuses = H.refuses
LIGHT, PROP = H.LIGHT, H.PROP
_row, warm, candle, practical, _q = H._row, H.warm, H.candle, H.practical, H._q


def drop_roles(rows, roles):
    return [r for r in rows if not any(r["label"].endswith(" " + x) or r["label"].endswith(" " + x + "_BODY")
                                       for x in roles)]


def make_show_p02():
    """P01 show (templates live in it) + P02 bays shaped like lighting_scores_record_P02.json."""
    plain = H.make_show()
    plain["cues"] = [c for c in plain["cues"] if not c["label"].startswith("P02 ")]   # drop the P01 look-alike
    spec = [("P02 Wing 001", warm("P02", "01", "-")), ("P02 Wing 004", warm("P02", "03", "+")),
            ("P02 Wing 007", [_row(r["label"].replace("P01 ", "P02 "), r["kind"], r["relative_transform"]["location"],
                                   r["relative_transform"]["rotation_xyzw"]) for r in practical("06")]),
            # FAILING_STAGE B13: L_KEY '+' but BEAM '-' (record shape), B16: no TOP_*/BEAM, B18: L_KEY only
            ("P02 Wing 014", warm("P02", "13", "+", {"BEAM_R": ([-150.0, -1250.0, 140.0], _q(80))})),
            ("P02 Wing 016", drop_roles(warm("P02", "16", "-"), ["TOP_L", "TOP_R", "BEAM_R"])),
            ("P02 Wing 018", drop_roles(warm("P02", "18", "-"), ["TOP_L", "TOP_R", "BEAM_R", "LOW_SIDE_R_FILL"])),
            # parity fallbacks: no L_KEY, R_FILL at +y -> '-'; only BEAM_R at +y -> '+'; nothing -> NO_PARITY
            ("P02 Wing 030", drop_roles(warm("P02", "30", "-"), ["LOW_SIDE_L_KEY"])),
            ("P02 Wing 031", drop_roles(warm("P02", "31", "+"), ["LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL"])),
            ("P02 Wing 032", drop_roles(warm("P02", "32", "-"), ["LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "BEAM_R"])),
            ("P02 Wing 020", [_row(r["label"].replace("P01 SCORE", "P02 SCORE").replace("P01_CANDLE", "P02_MYSTIC"),
                                   r["kind"], r["relative_transform"]["location"], r["relative_transform"]["rotation_xyzw"])
                              for r in candle("20", "-")]),
            ("P03 Wing 001", warm("P03", "01", "-"))]
    base = len(plain["cues"])
    for offset, (label, rows) in enumerate(spec):
        plain["cues"].append({"show_index": base + offset, "guid": "%032X" % (0xD000 + offset), "label": label,
                              "attachments": rows})
    p01 = list(plain["bay_guids"])
    plain["template_bay_guids"] = p01
    plain["bay_guids"] = [c["guid"] for c in plain["cues"] if c["label"].startswith("P02 ")]
    return plain


def opts2(**over):
    base = {"mode": "DRY", "target_passage": "P02", "jitter": dict(H.ZERO_JITTER)}
    base.update(over)
    return M.check_args(base)


def plan2(plain=None, **over):
    plain = plain or make_show_p02()
    return plain, M.build_plan(plain, opts2(**over), H.aims_for(plain))


def cue_targets(plan, label):
    return {t["role"]: t for t in plan["targets"] if t["cue_label"] == label}


def status_of(plan, label):
    return next(b["status"] for b in plan["bays"] if b["cue_label"] == label)


# ---------------------------------------------------------------- P01 unchanged
@case("P01 unchanged: new build_plan targets == pre-generalisation tool (zero jitter, Gary jitter, default args)")
def _():
    assert OLD is not None, "no Backups/PreRigPatternGeneralise-*/p01_rig_pattern.py"
    for over in ({}, {"jitter": dict(H.JIT)}, None):
        plain = H.make_show()
        if over is None:
            new_args, old_args = M.check_args({}), OLD.check_args({})
        else:
            new_args, old_args = H.opts(**over), OLD.check_args(dict({"mode": "DRY", "roles": list(H.FULL_ROLES),
                                                                      "jitter": dict(H.ZERO_JITTER)}, **over))
        new = M.build_plan(plain, new_args, H.aims_for(plain))
        old = OLD.build_plan(copy.deepcopy(plain), old_args, H.aims_for(plain))
        for key in old:
            if key == "bays":   # new keys only (missing_roles) are added per bay
                assert [{k: b[k] for k in ob} for b, ob in zip(new[key], old[key])] == old[key]
            else:
                assert M._canonical(new[key]) == M._canonical(old[key]), key
        assert new["passage"] == "P01" and new["template_passage"] == "P01" and new["parity_fallback"] is False
        assert {k: v for k, v in new_args.items() if k in old_args} == old_args
        assert set(new_args) - set(old_args) == {"target_passage", "template_passage"}


@case("P01 names unchanged: record path, marker, confirm, backup prefix, report path; P02/P03 get their own")
def _():
    c1 = M.passage_config("P01")
    assert c1["record_path"] == M.RECORD_PATH == os.path.join(HERE, "p01_rig_pattern_record.json")
    assert c1["mark"] == "P01RIGPATTERN" and c1["confirm_token"] == "P01RIGPATTERN"
    assert M.backup_prefix() == "PreP01RigPattern-" and M.backup_prefix(True) == "PreP01RigPatternRevert-"
    assert M.report_path("DRY", "x") == os.path.join(HERE, "p01_rig_pattern_report_DRY_x.json")
    seen = {c1["record_path"]}
    for key, n in (("P02", 2), ("P03", 3), ("P04", 4)):
        c = M.passage_config(key)
        assert c["record_path"] == os.path.join(HERE, "p%02d_rig_pattern_record.json" % n) and c["record_path"] not in seen
        seen.add(c["record_path"])
        assert c["mark"] == key + "RIGPATTERN" and c["label"] == "Passage %d" % n
        assert c["actor_prefix"] == "Passage %02d" % n and c["structure_label"] == "Infinity Stage - Structure %02d" % n
        assert c["scores_record"].endswith("lighting_scores_record_%s.json" % key)
        assert M.backup_prefix(passage=key) == "Pre%sRigPattern-" % key
        assert M.report_path("APPLY", "r", passage=key).endswith("p%02d_rig_pattern_report_APPLY_r.json" % n)
    assert M.mark_for_raw({"target_passage": "P02"}) == "P02RIGPATTERN" and M.mark_for_raw(None) == "P01RIGPATTERN"
    assert M.mark_for_raw({"target_passage": "P09"}) == "P01RIGPATTERN"
    refuses("PASSAGE_INVALID", M.passage_config, "P05")
    assert M.passage_config("P04")["record_path"] == os.path.join(HERE, "p04_rig_pattern_record.json")


@case("live P01 record: check_record passes; REVERT model restores before rows exactly; wrong passage refuses")
def _():
    with open(M.RECORD_PATH, encoding="utf-8") as handle:
        record = json.load(handle)
    M.check_record(record)
    refuses("RECORD_PASSAGE_MISMATCH", M.check_record, record, "P02")
    live = {g: copy.deepcopy(rows) for g, rows in record["after_cue_rows"].items()}
    reverted = M.revert_plain(TOOL, live, record)
    for g, rows in record["before_cue_rows"].items():
        for want, got in zip(rows, reverted[g]):
            assert want["relative_transform"] == got["relative_transform"], want["label"]
    # control: drift one row -> REVERT_DRIFT
    t = record["plan"]["targets"][0]
    row = next(r for r in live[t["cue_guid"]] if r["guid"] == t["attachment_guid"])
    row["relative_transform"]["location"][2] += 5.0
    refuses("REVERT_DRIFT|count=1", M.revert_plain, TOOL, live, record)


# ---------------------------------------------------------------- args
@case("args: P02/P03 confirm tokens, aliases, P01-only defaults, no_parity_template guards")
def _():
    a = M.check_args({"target_passage": "P02"})
    assert a["skip"] == [] and a["exclude_cues"] == [] and a["templates"] == M.DEFAULT_TEMPLATES
    assert a["parity_fallback"] is True and a["no_parity_template"] is None
    assert M.check_args({"mode": "APPLY", "confirm": "APPLY P02RIGPATTERN", "target_passage": "P02"})["mode"] == "APPLY"
    refuses("CONFIRM_MISSING", M.check_args, {"mode": "APPLY", "confirm": "APPLY P01RIGPATTERN", "target_passage": "P02"})
    refuses("CONFIRM_MISSING", M.check_args, {"mode": "REVERT", "confirm": "REVERT P02RIGPATTERN"})   # target P01
    refuses("CONFIRM_MISSING", M.check_args, {"mode": "REVERT", "confirm": "REVERT P02RIGPATTERN", "target_passage": "P03"})
    assert M.check_args({"mode": "REVERT", "confirm": "REVERT P03RIGPATTERN", "target_passage": "P03"})
    refuses("PASSAGE_INVALID", M.check_args, {"target_passage": "P07"})
    refuses("PASSAGE_INVALID", M.check_args, {"target_passage": "P02", "template_passage": "PX"})
    tc = {"-": "P01 Wing 005", "+": "P01 Wing 006"}
    assert M.check_args({"target_passage": "P02", "template_cues": tc})["templates"] == tc
    assert M.check_args({"target_passage": "P02", "template_cues": tc, "templates": dict(tc)})["templates"] == tc
    refuses("TEMPLATE_CUES_CONFLICT", M.check_args, {"target_passage": "P02", "template_cues": tc,
                                                       "templates": M.DEFAULT_TEMPLATES})
    refuses("TEMPLATE_CUE_NOT_IN_TEMPLATE_PASSAGE", M.check_args,
            {"target_passage": "P02", "template_cues": {"-": "P02 Wing 001", "+": "P01 Wing 004"}})
    refuses("NO_PARITY_TEMPLATE_INVALID", M.check_args, {"target_passage": "P02", "no_parity_template": "L"})
    refuses("NO_PARITY_TEMPLATE_NOT_FOR_P01", M.check_args, {"no_parity_template": "-"})


@case("args/request/run files: P02, P03, P04 parse, DRY, right target, right token, P01 files untouched in shape")
def _():
    for key, n in (("P02", 2), ("P03", 3), ("P04", 4)):
        with open(os.path.join(HERE, "p%02d_rig_pattern_args.json" % n), encoding="utf-8") as handle:
            a = M.check_args(json.load(handle))
        assert a["intensity_scale"] is None
        assert a["mode"] == "DRY" and a["target_passage"] == key and a["template_passage"] == "P01"
        assert a["templates"] == M.DEFAULT_TEMPLATES and a["skip"] == [] and a["exclude_cues"] == []
        assert a["roles"] == list(M.DEFAULT_ROLES) and a["jitter"] == M.DEFAULT_JITTER
        with open(os.path.join(HERE, "p%02d_rig_pattern_request.json" % n), encoding="utf-8") as handle:
            req = json.load(handle)
        assert req["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/p%02d_rig_pattern_run.py" % n
        with open(os.path.join(HERE, "p%02d_rig_pattern_run.py" % n), encoding="utf-8") as handle:
            src = handle.read()
        ast.parse(src)
        assert '"p%02d_rig_pattern_args.json"' % n in src and '"%%s %sRIGPATTERN"' % key in src
        assert 'args.get("target_passage") != "%s"' % key in src and '"p01_rig_pattern.py"' in src
        assert "P01RIGPATTERN" not in src.replace("P01RIGPATTERN_ARGS", "")
    with open(os.path.join(HERE, "p01_rig_pattern_args.json"), encoding="utf-8") as handle:
        assert "target_passage" not in json.load(handle)    # the P01 args keep their 6 Oct shape


# ---------------------------------------------------------------- P02 plan
@case("P02: templates read from P01 Wing 003/004; every P02 target copies the same-parity template exactly")
def _():
    plain, plan = plan2()
    b03, b04 = H.by_label(plain, "P01 Wing 003"), H.by_label(plain, "P01 Wing 004")
    assert plan["passage"] == "P02" and plan["template_passage"] == "P01"
    assert plan["templates"]["-"]["cue_guid"] == b03["guid"] and plan["templates"]["+"]["cue_guid"] == b04["guid"]
    assert plan["targets"] and all(t["cue_label"].startswith("P02 ") for t in plan["targets"])
    for t in plan["targets"]:
        src = b03 if t["parity"] == "-" else b04
        want = H.role_row(src, t["role"])["relative_transform"]
        assert t["location_after"] == want["location"] and t["rotation_after"] == want["rotation_xyzw"], t["attachment_label"]
    # P01 cues (incl. the templates) and the P03 cue are never targets
    assert not [g for g in plan["target_cue_guids"] if g in plain["template_bay_guids"]]
    assert "P03 Wing 001" not in plan["target_bays"]


@case("P02: only location+rotation of P02 rows change; mutated intensity / P01 template row fails scope (-)")
def _():
    plain, plan = plan2(jitter=dict(H.JIT))
    before = H.all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    M.check_scope(TOOL, before, after, plan, "after")
    bad = copy.deepcopy(after)
    t = plan["targets"][0]
    next(r for r in bad[t["cue_guid"]] if r["guid"] == t["attachment_guid"])["lighting"]["color"] = [0, 0, 1, 1]
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan, "after")
    bad = copy.deepcopy(after)
    H.role_row(next(c for c in plain["cues"] if c["label"] == "P01 Wing 003"), "TOP_L")
    bad[H.by_label(plain, "P01 Wing 003")["guid"]][1]["relative_transform"]["location"][0] += 1.0
    refuses("OUTSIDE_TARGET_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan, "after")


@case("P02 missing roles: FAILING_STAGE bays move what exists; missing_roles and role_counts report the rest")
def _():
    unused, plan = plan2()
    assert sorted(cue_targets(plan, "P02 Wing 016")) == ["LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "PRACTICAL_BULB_DEAD",
                                                       "PRACTICAL_CLAMP"]
    assert sorted(cue_targets(plan, "P02 Wing 018")) == ["LOW_SIDE_L_KEY", "PRACTICAL_BULB_DEAD", "PRACTICAL_CLAMP"]
    bay = next(b for b in plan["bays"] if b["cue_label"] == "P02 Wing 018")
    assert bay["missing_roles"] == ["TOP_L", "TOP_R", "LOW_SIDE_R_FILL", "BEAM_R"], bay["missing_roles"]
    counts = plan["role_counts"]
    assert sum(c["moved"] for c in counts.values()) == len(plan["targets"])
    assert counts["TOP_L"]["moved"] == len([t for t in plan["targets"] if t["role"] == "TOP_L"])
    # control: the full warm bay moves all seven lights
    assert len(cue_targets(plan, "P02 Wing 001")) == 7


@case("P02 parity: own LOW_SIDE_L_KEY sign; fallback R_FILL inverted, then BEAM_R; none -> NO_PARITY (reported)")
def _():
    unused, plan = plan2()
    par = {b["cue_label"]: (b["parity"], b.get("parity_source"), b["status"]) for b in plan["bays"]}
    assert par["P02 Wing 001"] == ("-", "LOW_SIDE_L_KEY", "TARGET")
    assert par["P02 Wing 004"] == ("+", "LOW_SIDE_L_KEY", "TARGET")
    assert par["P02 Wing 014"] == ("+", "LOW_SIDE_L_KEY", "TARGET")          # BEAM disagrees: warned, key wins
    assert any(w.startswith("BEAM_PARITY_MISMATCH|cue=P02 Wing 014") for w in plan["warnings"])
    assert par["P02 Wing 030"] == ("-", "LOW_SIDE_R_FILL", "TARGET"), par["P02 Wing 030"]
    assert par["P02 Wing 031"] == ("+", "BEAM_R", "TARGET"), par["P02 Wing 031"]
    assert par["P02 Wing 032"] == (None, None, "NO_PARITY"), par["P02 Wing 032"]
    assert any(w.startswith("PARITY_FALLBACK|cue=P02 Wing 030|via=LOW_SIDE_R_FILL") for w in plan["warnings"])
    assert any(w.startswith("NO_PARITY|cue=P02 Wing 032") for w in plan["warnings"])
    assert not cue_targets(plan, "P02 Wing 032")
    assert all(t["template_cue"] == "P01 Wing 003" for t in cue_targets(plan, "P02 Wing 030").values())
    assert all(t["template_cue"] == "P01 Wing 004" for t in cue_targets(plan, "P02 Wing 031").values())
    # flipping the live R_FILL flips the fallback parity
    plain = make_show_p02()
    H.role_row(H.by_label(plain, "P02 Wing 030"), "LOW_SIDE_R_FILL")["relative_transform"]["location"][1] = -1100.0
    unused, p2 = plan2(plain)
    assert next(b for b in p2["bays"] if b["cue_label"] == "P02 Wing 030")["parity"] == "+"


@case("no_parity_template: '+' moves the NO_PARITY bay from B04 (warned); P01 never falls back (control)")
def _():
    unused, plan = plan2(no_parity_template="+")
    t = cue_targets(plan, "P02 Wing 032")
    assert sorted(t) == ["PRACTICAL_BULB_DEAD", "PRACTICAL_CLAMP", "TOP_L", "TOP_R"]
    assert all(x["template_cue"] == "P01 Wing 004" for x in t.values())
    assert any(w.startswith("NO_PARITY_TEMPLATE_USED|cue=P02 Wing 032") for w in plan["warnings"])
    # P01 target: a bay with no LOW_SIDE_L_KEY is PRACTICAL_ONLY (6 Oct behaviour), no fallback
    plain = H.make_show()
    cue = H.by_label(plain, "P01 Wing 006")
    cue["attachments"] = drop_roles(cue["attachments"], ["LOW_SIDE_L_KEY"])
    p1 = M.build_plan(plain, H.opts(), H.aims_for(plain))
    assert {u["cue_label"]: u["status"] for u in p1["untouched_bays"]}["P01 Wing 006"] == "PRACTICAL_ONLY"


@case("P02 GAP untouched (PRACTICAL_ONLY); MYSTIC PRACTICAL_L/R never moved, its TOP/LOW_SIDE are")
def _():
    unused, plan = plan2()
    assert status_of(plan, "P02 Wing 007") == "PRACTICAL_ONLY" and not cue_targets(plan, "P02 Wing 007")
    assert sorted(cue_targets(plan, "P02 Wing 020")) == ["LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "TOP_L", "TOP_R"]
    assert not [t for t in plan["targets"] if t["role"].startswith("PRACTICAL_L") or t["role"].startswith("PRACTICAL_R")]


@case("P02 guards (-): non-P02 bay, template cue absent from template passage, template pool is target, kind")
def _():
    plain = make_show_p02()
    plain["bay_guids"].append(H.by_label(plain, "P03 Wing 001")["guid"])
    refuses("BAY_NOT_P02", M.build_plan, plain, opts2(), {})
    plain = make_show_p02()
    plain["template_bay_guids"] = [g for g in plain["template_bay_guids"] if g != H.by_label(plain, "P01 Wing 003")["guid"]]
    refuses("TEMPLATE_CUE_COUNT|label=P01 Wing 003", M.build_plan, plain, opts2(), {})
    plain = make_show_p02()
    H.role_row(H.by_label(plain, "P01 Wing 004"), "LOW_SIDE_L_KEY")["relative_transform"]["location"][1] = -5.0
    refuses("TEMPLATE_PARITY_WRONG", M.build_plan, plain, opts2(), {})
    plain = make_show_p02()
    H.role_row(H.by_label(plain, "P02 Wing 001"), "TOP_L")["kind"] = PROP
    refuses("KIND_MISMATCH", M.build_plan, plain, opts2(), {})


@case("P02 REVERT model + record check use the P02 passage key")
def _():
    plain, plan = plan2(jitter=dict(H.JIT))
    before = H.all_rows(plain)
    record = {"status": "saved_readback_verified", "passage": "P02", "plan": plan,
              "before_target_rows": M.target_rows(before, plan)}
    M.check_record(record, "P02")
    refuses("RECORD_PASSAGE_MISMATCH", M.check_record, record)
    live = M.apply_plain(before, plan, "after")
    reverted = M.revert_plain(TOOL, live, record)
    for g, rows in before.items():
        for o, r in zip(rows, reverted[g]):
            assert o["relative_transform"] == r["relative_transform"]


@case("P02 PANEL_BAND stays advisory and uses the bay's own aims (narrower panel -> more warnings)")
def _():
    plain = make_show_p02()
    aims = H.aims_for(plain)
    p_wide = M.build_plan(plain, opts2(), aims)
    narrow = {g: [{"panel": "L", "target_cm": [0.0, -1500.0, 0.0]}, {"panel": "R", "target_cm": [0.0, 1500.0, 0.0]}]
              for g in aims}
    p_narrow = M.build_plan(plain, opts2(), narrow)
    w1 = [w for w in p_wide["warnings"] if w.startswith("PANEL_BAND|cue=P02")]
    w2 = [w for w in p_narrow["warnings"] if w.startswith("PANEL_BAND|cue=P02")]
    assert w1 and len(w2) > len(w1) and len(p_narrow["targets"]) == len(p_wide["targets"])


# ---------------------------------------------------------------- real data (record state, not live)
def _real_plain(key):
    with open(M.RECORD_PATH, encoding="utf-8") as handle:
        p01 = json.load(handle)
    with open(M.passage_config(key)["scores_record"], encoding="utf-8") as handle:
        scores = json.load(handle)
    cues = []
    for sign, tpl in sorted(p01["plan"]["templates"].items()):
        rows = []
        for role, r in tpl["roles"].items():
            rows.append({"guid": r["guid"], "label": r["label"], "kind": "<x.%s: 0>" % r["kind"], "enabled": True,
                         "anchor": "<x.%s: 0>" % r["anchor"],
                         "relative_transform": {"location": r["location"], "rotation_xyzw": r["rotation_xyzw"],
                                                "scale": [1.0, 1.0, 1.0]}})
        cues.append({"show_index": len(cues), "guid": tpl["cue_guid"], "label": tpl["cue_label"], "attachments": rows})
    for t in scores["plan"]["targets"]:
        cues.append({"show_index": 100 + t["show_index"], "guid": t["cue_guid"], "label": t["cue_label"],
                     "attachments": t["after_rows"]})
    known = {c["guid"] for c in cues}
    for guid in scores["plan"]["bay_guids"]:   # bays the scores tool did not score (P04 B01-B06): rows unknown offline
        if guid not in known:
            cues.append({"show_index": 900 + len(cues), "guid": guid, "label": "%s unscored %s" % (key, guid[:8]),
                         "attachments": []})
    aims = {t["cue_guid"]: t.get("aims") or [] for t in scores["plan"]["targets"]}
    return ({"cues": cues, "bay_guids": list(scores["plan"]["bay_guids"]),
             "template_bay_guids": [c["guid"] for c in cues[:2]]}, aims)


REAL = {}


@case("REAL P02 (scores record rows + P01 record templates): 21 bays planned, GAP B06/B22 untouched")
def _():
    plain, aims = _real_plain("P02")
    plan = M.build_plan(plain, M.check_args({"target_passage": "P02"}), aims)
    REAL["P02"] = plan
    st = {b["cue_label"]: b["status"] for b in plan["bays"]}
    assert st["P02 Wing 007"] == "PRACTICAL_ONLY" and st["P02 Wing 022"] == "PRACTICAL_ONLY"
    assert len(plan["target_bays"]) == 21 and not [b for b in st.values() if b == "NO_PARITY"], st
    assert plan["role_counts"]["LOW_SIDE_L_KEY"]["moved"] == 21
    with open(os.path.join(HERE, "p02_rig_pattern_args.json"), encoding="utf-8") as handle:
        assert M.build_plan(plain, M.check_args(json.load(handle)), aims)["targets"] == plan["targets"]


@case("REAL P03: 4 side bays by own parity; 13 TOP-only bays NO_PARITY by default, moved with no_parity_template")
def _():
    plain, aims = _real_plain("P03")
    plan = M.build_plan(plain, M.check_args({"target_passage": "P03"}), aims)
    REAL["P03"] = plan
    st = [b["status"] for b in plan["bays"]]
    assert st.count("TARGET") == 4 and st.count("NO_PARITY") == 13 and st.count("PRACTICAL_ONLY") == 4, st
    full = M.build_plan(plain, M.check_args({"target_passage": "P03", "no_parity_template": "-"}), aims)
    REAL["P03-"] = full
    assert len(full["target_bays"]) == 17 and full["role_counts"]["TOP_L"]["moved"] == 17
    assert not [t for t in full["targets"] if t["role"].endswith("_CAP") or t["kind"] != "LIGHT"]


@case("REAL foreign scan (offline prediction of the DRY ack list): P02/P03 scores records hit, P01 record does not")
def _():
    saved = os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    for key, plan in (("P02", REAL["P02"]), ("P03", REAL["P03-"])):
        hits = SCORES.scan_foreign_records(roots, plan["target_attachment_guids"],
                                           exclude=[M.passage_config(key)["record_path"]])
        names = sorted(os.path.basename(h["path"]) for h in hits)
        REAL["ack_" + key] = names
        assert "lighting_scores_record_%s.json" % key in names, names
        assert "p01_rig_pattern_record.json" not in names


# ---------------------------------------------------------------- P04 (Gary 7 Oct: rig + optional dimming)
def make_show_p04():
    plain = make_show_p02()
    plain["cues"] = [c for c in plain["cues"] if not c["label"].startswith("P02 ")]
    strobe = [_row("P04 Wing 001 STROBE", LIGHT, [0, 0, 1500], _q(0, -90), intensity=9000.0),
              _row("P04 MOONLIGHT KEY", LIGHT, [-4000, 2000, 3000], _q(30, -20), intensity=2.0),
              _row("P04 Wing 011 Cross +Y", LIGHT, [0, 600, 400], _q(90), intensity=3.0)]
    industrial = [_row("P04 SCORE B12 INDUSTRIAL %s" % role, LIGHT, loc, _q(0))
                  for role, loc in (("TOP_L", [0, -360, 1180]), ("TOP_R", [0, 360, 1180]),
                                    ("LOW_SIDE_L", [80, -820, 130]), ("LOW_SIDE_R", [80, 820, 150]),
                                    ("BEAM_L", [-150, -1080, 140]))]
    spec = [("P04 Wing 011", warm("P04", "11", "-") + strobe[2:]), ("P04 Wing 015", warm("P04", "15", "+")),
            ("P04 Wing 001", strobe[:2]), ("P04 Wing 012", industrial),
            ("P04 Wing 014", [_row("P04 SCORE B14 VOID PRACTICAL_DEAD", LIGHT, [-10, 700, 115], [0, 0, 0, 1])])]
    base = len(plain["cues"])
    for offset, (label, rows) in enumerate(spec):
        plain["cues"].append({"show_index": base + offset, "guid": "%032X" % (0xE000 + offset), "label": label,
                              "attachments": rows})
    plain["bay_guids"] = [c["guid"] for c in plain["cues"] if c["label"].startswith("P04 ")]
    return plain


def plan4(plain=None, **over):
    plain = plain or make_show_p04()
    return plain, M.build_plan(plain, opts2(target_passage="P04", **over), H.aims_for(plain))


def intensity_untouched(before, after):
    return all(b.get("lighting", {}).get("intensity") == a.get("lighting", {}).get("intensity")
               for g in before for b, a in zip(before[g], after[g]))


@case("P04: only 'P04 SCORE' rows move; strobe/moonlight/Cross rows untouched; INDUSTRIAL NO_PARITY; VOID practical")
def _():
    plain, plan = plan4()
    assert plan["targets"] and all(t["attachment_label"].startswith("P04 SCORE B") for t in plan["targets"])
    st = {b["cue_label"]: b["status"] for b in plan["bays"]}
    assert st == {"P04 Wing 011": "TARGET", "P04 Wing 015": "TARGET", "P04 Wing 001": "NO_SCORE_ROWS",
                  "P04 Wing 012": "NO_PARITY", "P04 Wing 014": "PRACTICAL_ONLY"}, st
    before = H.all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    M.check_scope(TOOL, before, after, plan, "after")
    for g, rows in before.items():
        for b, a in zip(rows, after[g]):
            if "SCORE" not in b["label"]:
                assert b == a, b["label"]
    bad = copy.deepcopy(after)   # control: the Cross row in a target cue moved -> scope fails
    next(r for r in bad[H.by_label(plain, "P04 Wing 011")["guid"]] if r["label"].endswith("Cross +Y")
         )["relative_transform"]["rotation_xyzw"] = _q(10)
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan, "after")
    bad = copy.deepcopy(after)   # control: the strobe cue (non-target cue) touched -> outside scope
    bad[H.by_label(plain, "P04 Wing 001")["guid"]][0]["relative_transform"]["rotation_xyzw"] = _q(10)
    refuses("OUTSIDE_TARGET_SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan, "after")
    assert intensity_untouched(before, after)


@case("P04 forbidden label (-): a SCORE row naming STROBE/HALO/MOON/OPENING refuses; plain SCORE row passes")
def _():
    for look in ("P04_STROBE_HALO", "MOONLIGHT", "OPENING_FLARE"):
        plain = make_show_p04()
        H.role_row(H.by_label(plain, "P04 Wing 015"), "TOP_L")["label"] = "P04 SCORE B15 %s TOP_L" % look
        refuses("FORBIDDEN_TARGET_LABEL", M.build_plan, plain, opts2(target_passage="P04"), {})
    plan4()


@case("P04 intensity_scale: moved LIGHT rows scaled (float32), others untouched, scope allows it only there")
def _():
    plain, plan = plan4(intensity_scale=0.35)
    before = H.all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    M.check_scope(TOOL, before, after, plan, "after")
    lights = [t for t in plan["targets"] if t["kind"] == "LIGHT"]
    assert lights and sorted(t["attachment_guid"] for t in lights) == plan["intensity_guids"]
    for t in lights:
        assert t["intensity_after"] == M.f32(t["intensity_before"] * 0.35) and t["intensity_after"] != t["intensity_before"]
    moved = set(plan["target_attachment_guids"])
    for g, rows in before.items():
        for b, a in zip(rows, after[g]):
            if b["guid"] not in moved:
                assert b == a, b["label"]
    bad = copy.deepcopy(after)   # (-) intensity on a non-target row of a target cue
    next(r for r in bad[H.by_label(plain, "P04 Wing 011")["guid"]] if "PRE-SCORE" in r["label"])["lighting"]["intensity"] = 1.0
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan, "after")
    bad = copy.deepcopy(after)   # (-) a scaled row off by 0.1 %
    t = lights[0]
    next(r for r in bad[t["cue_guid"]] if r["guid"] == t["attachment_guid"])["lighting"]["intensity"] *= 1.001
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plan, "after")
    unused, plain_plan = plan4(plain)   # (-) without intensity_scale a moved row's intensity is out of scope
    bad = M.apply_plain(before, plain_plan, "after")
    t = plain_plan["targets"][0]
    next(r for r in bad[t["cue_guid"]] if r["guid"] == t["attachment_guid"])["lighting"]["intensity"] = 1.0
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, before, bad, plain_plan, "after")
    assert plain_plan["intensity_guids"] == [] and "intensity_after" not in plain_plan["targets"][0]


@case("P04 intensity REVERT: intensity drift listed; revert restores before intensity; readback checks it")
def _():
    plain, plan = plan4(intensity_scale=0.5, jitter=dict(H.JIT))
    before = H.all_rows(plain)
    record = {"status": "saved_readback_verified", "passage": "P04", "plan": plan,
              "before_target_rows": M.target_rows(before, plan)}
    live = M.apply_plain(before, plan, "after")
    assert M.revert_drifts(live, record) == []
    assert all(r["ok"] for r in M.readback_rows(live, plan, "after"))
    reverted = M.revert_plain(TOOL, live, record)
    for g, rows in before.items():
        for o, r in zip(rows, reverted[g]):
            assert o == r, o["label"]
    t = plan["intensity_guids"][0]
    tt = next(x for x in plan["targets"] if x["attachment_guid"] == t)
    next(r for r in live[tt["cue_guid"]] if r["guid"] == t)["lighting"]["intensity"] = 77.0
    drifts = M.revert_drifts(live, record)
    assert [d["field"] for d in drifts] == ["lighting.intensity"], drifts
    refuses("READBACK_ROWS", M.readback_rows, live, plan, "after")


def _export_l(rows):
    parts = []
    for r in rows:
        loc, rot = r["relative_transform"]["location"], r["relative_transform"]["rotation_xyzw"]
        parts.append('(Label="%s",AttachmentGuid=%s,RelativeTransform=(Rotation=(X=%r,Y=%r,Z=%r,W=%r),'
                     'Translation=(X=%r,Y=%r,Z=%r),Scale3D=(X=1.0,Y=1.0,Z=1.0)),Lighting=(Type=Spot,Intensity=%r,'
                     'IndirectLightingIntensity=1.0,Drama=(UnstruckIntensityScale=0.0)))'
                     % ((r["label"], r["guid"]) + tuple(rot) + tuple(loc) + (r["lighting"]["intensity"],)))
    return "(Attachments=(" + ",".join(parts) + "))"


@case("export hash: scaled targets' Intensity masked; Indirect/Unstruck still counted; P01 normalised text == old tool")
def _():
    plain, plan = plan4(intensity_scale=0.5)
    before = H.all_rows(plain)
    after = M.apply_plain(before, plan, "after")
    guids, ig = plan["target_attachment_guids"], plan["intensity_guids"]
    tb = [_export_l(before[g]) for g in sorted(before)]
    ta = [_export_l(after[g]) for g in sorted(after)]
    assert M.export_hash(ta, guids, ig) == M.export_hash(tb, guids, ig)
    assert M.export_hash(ta, guids) != M.export_hash(tb, guids)          # (-) unmasked intensity is seen
    first = plan["intensity_guids"][0]
    for field in ("IndirectLightingIntensity=1.0", "UnstruckIntensityScale=0.0"):
        tx = []
        for t in ta:
            at = t.find(first)
            tx.append(t[:at] + t[at:].replace(field, field[:-1] + "5", 1) if at >= 0 else t)
        assert tx != ta and M.export_hash(tx, guids, ig) != M.export_hash(tb, guids, ig), field
    refuses("EXPORT_INTENSITY_NOT_TARGET", M.normalize_export, tb, guids[:1], ["F" * 32])
    p1, pl = H.plan_for(jitter=dict(H.JIT))
    rows = H.all_rows(p1)
    texts = [H._export(rows[g]) for g in sorted(rows)]
    assert M.normalize_export(texts, pl["target_attachment_guids"]) == OLD.normalize_export(texts, pl["target_attachment_guids"])


@case("intensity_scale args: P01 refuses, range/bool/nan refuse, P04 0.5 accepted")
def _():
    refuses("INTENSITY_SCALE_NOT_FOR_P01", M.check_args, {"intensity_scale": 0.5})
    refuses("INTENSITY_SCALE_RANGE", M.check_args, {"target_passage": "P04", "intensity_scale": 0.0})
    refuses("INTENSITY_SCALE_RANGE", M.check_args, {"target_passage": "P04", "intensity_scale": 9.0})
    refuses("INTENSITY_SCALE_INVALID", M.check_args, {"target_passage": "P04", "intensity_scale": True})
    refuses("INTENSITY_SCALE_NOT_FINITE", M.check_args, {"target_passage": "P04", "intensity_scale": float("nan")})
    assert M.check_args({"target_passage": "P04", "intensity_scale": 0.5})["intensity_scale"] == 0.5


@case("REAL P04 (scores record + P01 templates): bay statuses, INDUSTRIAL NO_PARITY, foreign-hit prediction")
def _():
    plain, aims = _real_plain("P04")
    plan = M.build_plan(plain, M.check_args({"target_passage": "P04"}), aims)
    REAL["P04"] = plan
    REAL["P04_status"] = {b["cue_label"]: b["status"] for b in plan["bays"]}
    assert REAL["P04_status"]["P04 Wing 012"] == "NO_PARITY"
    assert all(t["attachment_label"].startswith("P04 SCORE B") for t in plan["targets"])
    saved = os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    hits = SCORES.scan_foreign_records(roots, plan["target_attachment_guids"],
                                       exclude=[M.passage_config("P04")["record_path"]])
    REAL["ack_P04"] = sorted(os.path.basename(h["path"]) for h in hits)
    assert "lighting_scores_record_P04.json" in REAL["ack_P04"]


def main():
    passed = sum(1 for r in RESULTS if r[1])
    failed = len(RESULTS) - passed
    for name, ok, detail in RESULTS:
        print("%s  %s" % ("PASS" if ok else "FAIL", name))
        if not ok:
            print(detail)
    for key in ("P02", "P03", "P03-", "P04"):
        plan = REAL.get(key)
        if plan:
            print("EVIDENCE real %s: bays=%d rows=%d warnings=%d panel_band=%d role_moved=%s"
                  % (key, len(plan["target_bays"]), len(plan["targets"]), len(plan["warnings"]),
                     sum(1 for t in plan["targets"] if t["inside_panel_band"]),
                     {r: c["moved"] for r, c in plan["role_counts"].items()}))
    print("EVIDENCE real P04 bay status: %s" % REAL.get("P04_status"))
    for key in ("P02", "P03", "P04"):
        print("EVIDENCE predicted foreign hits %s: %s" % (key, REAL.get("ack_" + key)))
    print("PASS %d/FAIL %d" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
