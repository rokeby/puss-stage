"""Offline harness for dead_bulbs_warm.py (pure Python, no unreal). Run: python test_dead_bulbs_warm_offline.py

Fixture (inferred: "the Show as last recorded", the live DRY decides): per passage P01-P06, the bay cues of
lighting_scores_record_P0N.json plan.targets (after_rows, show_index), overlaid with p0N_rig_pattern_record.json
after_cue_rows where present (P01-P04, P06; 6 Oct, saved_readback_verified), then the p02_brighten_record.json targets'
after intensities (7 Oct 02:28, saved_readback_verified). Plus one synthetic P06 cue carrying a REAL events-protected
cue guid (plan.yield_to_events.cue_guids) with cloned rows, to exercise the protected gate.
Every gate has a passing case and a failing control. Prints PASS/FAIL per case, per-passage counts and a summary;
exits non-zero on any failure.
"""
from __future__ import annotations

import ast
import collections
import copy
import json
import os
import struct
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dead_bulbs_warm as W  # noqa: E402

assert W.unreal is None, "harness must run with unreal absent"
RP = W.load_rig_pattern()
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
CUES = {}
PASSAGES = {}
for key in W.ALL_PASSAGES:
    sco = load("lighting_scores_record_%s.json" % key)
    bays = []
    for t in sorted(sco["plan"]["targets"], key=lambda x: x["show_index"]):
        CUES[t["cue_guid"]] = {"guid": t["cue_guid"], "label": t["cue_label"], "show_index": t["show_index"],
                               "attachments": copy.deepcopy(t["after_rows"])}
        bays.append(t["cue_guid"])
    PASSAGES[key] = {"passage_guid": sco["plan"]["passage_guid"], "bay_guids": bays}
    rig = "p%s_rig_pattern_record.json" % key[1:].zfill(2)
    if os.path.exists(os.path.join(HERE, rig)):
        for g, rows in load(rig)["after_cue_rows"].items():
            if g in CUES:
                CUES[g]["attachments"] = copy.deepcopy(rows)
BRIGHT = load("p02_brighten_record.json")
for t in BRIGHT["plan"]["targets"]:
    for r in CUES[t["cue_guid"]]["attachments"]:
        if r["guid"] == t["attachment_guid"]:
            r["lighting"]["intensity"] = t["after"]
PROTECTED = RP.load_protected(os.path.join(HERE, "lighting_scores_record_P06.json"))
_src = next(CUES[g] for g in PASSAGES["P06"]["bay_guids"]
            if any("PRACTICAL_BULB_DEAD" in r["label"] and not r["label"].endswith("_BODY")
                   for r in CUES[g]["attachments"]))
PROT_CUE = {"guid": PROTECTED[0], "label": "P06 Wing PROTECTED", "show_index": 9999,
            "attachments": copy.deepcopy(_src["attachments"])}
for i, r in enumerate(PROT_CUE["attachments"]):
    r["guid"] = "%032X" % (0xABC000 + i)
CUES[PROT_CUE["guid"]] = PROT_CUE
PASSAGES["P06"]["bay_guids"].append(PROT_CUE["guid"])
FOREIGN = {"guid": "F" * 32, "label": "P07 Elsewhere", "show_index": 10000,
           "attachments": [dict(copy.deepcopy(_src["attachments"][0]), guid="E" * 32)]}


def plain():
    return {"cues": copy.deepcopy(sorted(CUES.values(), key=lambda c: c["show_index"]) + [FOREIGN]),
            "passages": copy.deepcopy(PASSAGES)}


def all_rows(p):
    return {c["guid"]: c["attachments"] for c in p["cues"]}


def row_in(p, label):
    hits = [r for c in p["cues"] for r in c["attachments"] if label in (r["label"], r["guid"])]
    assert len(hits) == 1, (label, len(hits))
    return hits[0]


P = W.check_params({})


def plan_for(params=None, p=None, protected=PROTECTED):
    return W.build_plan(p or plain(), params or P, RP.FORBIDDEN_TARGET_LABEL, protected)


PLAN = plan_for()
BY_LABEL = {t["attachment_label"]: t for t in PLAN["targets"]}
BASE = all_rows(plain())


def before_row(t):
    return next(r for r in BASE[t["cue_guid"]] if r["guid"] == t["attachment_guid"])


# ---------------------------------------------------------------- A. args / files
@case("args: DRY needs no confirm; APPLY needs confirm AND expected_targets; REVERT token checked")
def _():
    assert W.check_args({"mode": "DRY"})["mode"] == "DRY"
    refuses("CONFIRM_MISSING", W.check_args, {"mode": "APPLY", "expected_targets": 5})
    refuses("CONFIRM_MISSING", W.check_args, {"mode": "APPLY", "confirm": "APPLY P02BRIGHTEN", "expected_targets": 5})
    refuses("EXPECTED_TARGETS_REQUIRED", W.check_args, {"mode": "APPLY", "confirm": "APPLY DEADBULBSWARM"})
    assert W.check_args({"mode": "APPLY", "confirm": "APPLY DEADBULBSWARM", "expected_targets": 5})["mode"] == "APPLY"
    assert W.check_args({"mode": "REVERT", "confirm": "REVERT DEADBULBSWARM"})["mode"] == "REVERT"
    refuses("MODE_INVALID", W.check_args, {"mode": "SAVE"})
    refuses("EXPECTED_PER_PASSAGE_INVALID", W.check_args, {"mode": "DRY", "expected_per_passage": {"P09": 1}})


@case("params: defaults; unknown key, range, bad passage, bool seed, bad units refused")
def _():
    assert P["passages"] == list(W.ALL_PASSAGES) and P["glow_floor_lm"] == 40.0 and P["cool_kelvin"] == 4000.0
    refuses("PARAMS_UNKNOWN", W.check_params, {"glow_flor_lm": 40})
    refuses("PARAM_RANGE", W.check_params, {"glow_floor_lm": 5000})
    refuses("PARAM_PASSAGES", W.check_params, {"passages": ["P07"]})
    refuses("PARAM_PASSAGES", W.check_params, {"passages": ["P02", "P02"]})
    refuses("PARAM_SEED", W.check_params, {"seed": True})
    refuses("PARAM_UNITS", W.check_params, {"units": "LUX"})
    refuses("PARAM_INCLUDE_PROTECTED", W.check_params, {"include_protected": 1})


@case("files: args DRY + valid, request runs dead_bulbs_warm_run.py, all files parse, main guard shape")
def _():
    a = load("dead_bulbs_warm_args.json")
    assert a["mode"] == "DRY" and W.check_args(a)["mode"] == "DRY" and "confirm" not in a
    req = load("dead_bulbs_warm_request.json")
    assert req["arguments"]["tool_name"] == "ExecuteProjectPythonFile"
    assert req["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/dead_bulbs_warm_run.py"
    for name in ("dead_bulbs_warm.py", "dead_bulbs_warm_run.py", "test_dead_bulbs_warm_offline.py"):
        with open(os.path.join(HERE, name), encoding="utf-8") as h:
            ast.parse(h.read())
    with open(os.path.join(HERE, "dead_bulbs_warm.py"), encoding="utf-8") as h:
        last = ast.parse(h.read()).body[-1]
    assert isinstance(last, ast.If) and "DEADBULBSWARM_ARGS" in ast.unparse(last.test)


def _set_names(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as h:
        tree = ast.parse(h.read())
    return {c.args[0].value for c in ast.walk(tree) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == "set_editor_property" and c.args and isinstance(c.args[0], ast.Constant)}


@case("write path writes ONLY lighting intensity/color/use_temperature/temperature_kelvin (AST scan + control)")
def _():
    assert _set_names("dead_bulbs_warm.py") == {"lighting", "intensity", "color", "use_temperature",
                                               "temperature_kelvin"}, _set_names("dead_bulbs_warm.py")
    assert _set_names("p01_rig_pattern.py") - {"lighting", "intensity", "color", "use_temperature",
                                               "temperature_kelvin"}   # control: the scan can fail


def _dotted_attr(node):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id + "." + node.attr
    return None


@case("palette: one sha256 draw per statement (AST), deterministic per GUID, seed changes it (control)")
def _():
    with open(os.path.join(HERE, "dead_bulbs_warm.py"), encoding="utf-8") as h:
        tree = ast.parse(h.read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "palette_index")
    for stmt in fn.body:
        draws = [c for c in ast.walk(stmt) if isinstance(c, ast.Call) and _dotted_attr(c.func) in
                 ("hashlib.sha256", "random.random", "random.randint", "random.choice")]
        assert len(draws) <= 1, ast.unparse(stmt)
    g = PLAN["targets"][0]["attachment_guid"]
    assert W.palette_index(P["seed"], g) == W.palette_index(P["seed"], g.lower())
    p2 = plan_for(W.check_params({"seed": 1}))
    a = {t["attachment_guid"]: t["swatch"] for t in PLAN["targets"]}
    b = {t["attachment_guid"]: t["swatch"] for t in p2["targets"]}
    assert set(a) == set(b) and a != b
    again = {t["attachment_guid"]: t["swatch"] for t in plan_for()["targets"]}
    assert again == a                                     # stable across rebuilds
    counts = PLAN["counts"]["palette"]
    assert all(v >= PLAN["counts"]["targets"] // 6 for v in counts.values()), counts   # a real mix of all three


# ---------------------------------------------------------------- B. selection
@case("selection: cool dead bulbs in P02/P04/P06 only; P01/P03/P05 dead bulbs are already warm (listed)")
def _():
    per = {k: v["targets"] for k, v in PLAN["per_passage"].items()}
    assert per["P01"] == 0 and per["P03"] == 0 and per["P05"] == 0, per
    assert per["P02"] > 0 and per["P04"] > 0 and per["P06"] > 0, per
    warm = collections.Counter(u["cue_label"][:3] for u in PLAN["untouched"] if u["why"] == "ALREADY_WARM")
    assert warm["P01"] > 0 and warm["P03"] > 0 and warm["P05"] > 0, warm
    for t in PLAN["targets"]:
        b = before_row(t)
        assert W.is_cool(b["lighting"], 4000.0), t["attachment_label"]
        assert t["role"].endswith("_DEAD") or b["lighting"]["intensity"] < 40.0
        assert not t["role"].endswith(("_BODY", "_CAP"))
        assert t["attachment_label"].startswith(t["passage"] + " ")
    after = W.apply_rows(BASE, PLAN["targets"], "after")
    for t in PLAN["targets"]:
        lit = next(r for r in after[t["cue_guid"]] if r["guid"] == t["attachment_guid"])["lighting"]
        assert not W.is_cool(lit, 4000.0), t["attachment_label"]
    assert all(t["cue_guid"] != FOREIGN["guid"] for t in PLAN["targets"])
    for n in range(1, 24):
        label = "P02 SCORE B%02d P02_FAILING_STAGE PRACTICAL_BULB_DEAD" % n
        if any(r["label"] == label for c in plain()["cues"] for r in c["attachments"]):
            assert label in BY_LABEL, label


@case("values: orange 2200 K / warm white 2900 K use_temperature on, white rgb; pink rgb, use_temperature off")
def _():
    for t in PLAN["targets"]:
        b = before_row(t)["lighting"]
        col = t["writes"]["color"][1]
        ut = t["writes"].get("use_temperature", [None, b["use_temperature"]])[1]
        k = t["writes"].get("temperature_kelvin", [None, b["temperature_kelvin"]])[1]
        if t["swatch"] == "pink":
            assert col[:3] == [W.f32(1.0), W.f32(0.55), W.f32(0.7)] and ut is False and k == b["temperature_kelvin"]
        else:
            assert col[:3] == [1.0, 1.0, 1.0] and ut is True
            assert k == (2200.0 if t["swatch"] == "orange" else 2900.0)
        assert col[3] == b["color"][3]
        for f, (bv, av) in t["writes"].items():
            assert bv != av, (t["attachment_label"], f)
            if f == "color":
                assert all(x == W.f32(x) for x in av)


@case("glow floor: intensity written only where it was exactly 0 (-> 40 lm); P02 B12-B19 keep p02_brighten 800")
def _():
    for t in PLAN["targets"]:
        b = before_row(t)["lighting"]["intensity"]
        if b == 0.0:
            assert t["writes"]["intensity"] == [0.0, 40.0], t
        else:
            assert "intensity" not in t["writes"], t
    for n in range(12, 20):
        t = BY_LABEL["P02 SCORE B%02d P02_FAILING_STAGE PRACTICAL_BULB_DEAD" % n]
        assert before_row(t)["lighting"]["intensity"] == 800.0 and "intensity" not in t["writes"]
    assert sum(1 for t in PLAN["targets"] if t["passage"] == "P02" and t["glow_floor"]) > 0
    p2 = plan_for(W.check_params({"glow_floor_lm": 60}))      # control: the floor arg is honoured
    assert {tuple(t["writes"]["intensity"]) for t in p2["targets"] if "intensity" in t["writes"]} == {(0.0, 60.0)}


@case("dead rule: a cool CLAMP below 40 lm becomes a target; at 50 lm it does not (controls)")
def _():
    label = next(r["label"] for g in PASSAGES["P04"]["bay_guids"] for r in CUES[g]["attachments"]
                 if r["label"].endswith(" PRACTICAL_CLAMP"))
    for value, expect in ((10.0, True), (50.0, False)):
        p = plain()
        r = row_in(p, label)
        r["lighting"].update({"intensity": value, "use_temperature": True, "temperature_kelvin": 6000.0,
                              "color": [0.5, 0.7, 1.0, 1.0]})
        got = label in {t["attachment_label"] for t in plan_for(p=p)["targets"]}
        assert got is expect, (value, got)


@case("cool rule: K>4000 with use_temperature; blue rgb with it off; warm rgb + 6500 K but off = warm (controls)")
def _():
    assert W.is_cool({"use_temperature": True, "temperature_kelvin": 4500.0, "color": [1, 0.7, 0.4, 1]}, 4000.0)
    assert not W.is_cool({"use_temperature": True, "temperature_kelvin": 4000.0, "color": [1, 0.7, 0.4, 1]}, 4000.0)
    assert W.is_cool({"use_temperature": False, "temperature_kelvin": 2000.0, "color": [0.5, 0.7, 1, 1]}, 4000.0)
    assert not W.is_cool({"use_temperature": False, "temperature_kelvin": 6500.0, "color": [1, 0.7, 0.4, 1]}, 4000.0)


@case("never targeted: props, warm, disabled, wrong units, forbidden, skip, events-protected (include_protected ctl)")
def _():
    t0 = next(t for t in PLAN["targets"] if t["passage"] == "P06")
    label = t0["attachment_label"]
    whys = {}
    for what in ("disabled", "units", "forbidden"):
        p = plain()
        r = row_in(p, t0["attachment_guid"])
        if what == "disabled":
            r["enabled"] = False
        elif what == "units":
            r["lighting"]["intensity_units"] = "<InfinityStageLightIntensityUnits.CANDELAS: 1>"
        else:
            r["label"] = label.replace(" P06_", " STROBE_P06_", 1)
        p2 = plan_for(p=p)
        assert r["guid"] not in p2["target_attachment_guids"], what
        whys[what] = {u["why"] for u in p2["untouched"] if u["label"] == r["label"]
                      and u["cue_label"] == t0["cue_label"]}
    assert whys == {"disabled": {"DISABLED"}, "units": {"UNITS_MISMATCH"}, "forbidden": {"FORBIDDEN_LABEL"}}, whys
    p3 = plan_for(W.check_params({"skip_labels": [label]}))
    assert label not in {t["attachment_label"] for t in p3["targets"]}
    prot = {r["guid"] for r in PROT_CUE["attachments"]}
    assert not prot & set(PLAN["target_attachment_guids"])
    assert any(u["why"] == "PROTECTED_EVENTS_CUE" for u in PLAN["untouched"])
    p4 = plan_for(W.check_params({"include_protected": True}))
    assert prot & set(p4["target_attachment_guids"])           # control: the gate is what kept them out
    assert not any(t["role"].endswith(("_BODY", "_CAP")) for t in p4["targets"])


@case("passages param narrows; passage_cfg: P05 built (inferred), P02 equals rig_pattern's, P07 refused")
def _():
    p2 = plan_for(W.check_params({"passages": ["P02"]}))
    assert {t["passage"] for t in p2["targets"]} == {"P02"}
    c5 = W.passage_cfg(RP, "P05")
    assert c5["inferred_names"] and c5["label"] == "Passage 5" and c5["actor_prefix"] == "Passage 05"
    assert load("lighting_scores_record_P05.json")["plan"]["passage_label"] == c5["label"]
    assert not W.passage_cfg(RP, "P02")["inferred_names"]
    refuses("PASSAGE_INVALID", W.passage_cfg, RP, "P07")
    p = plain()
    p["passages"]["P02"]["bay_guids"].append(FOREIGN["guid"])
    refuses("BAY_NOT_P02", plan_for, p=p)


@case("expected targets / per-passage gate (pass + fail)")
def _():
    per = {k: v["targets"] for k, v in PLAN["per_passage"].items()}
    W.check_expected(PLAN, PLAN["counts"]["targets"], per)
    refuses("EXPECTED_TARGETS", W.check_expected, PLAN, PLAN["counts"]["targets"] - 1, None)
    refuses("EXPECTED_PER_PASSAGE", W.check_expected, PLAN, None, dict(per, P02=per["P02"] + 1))


# ---------------------------------------------------------------- C. scope, revert, export
@case("model: only the targets' written fields differ; scope passes")
def _():
    after = W.apply_rows(BASE, PLAN["targets"], "after")
    assert not W.scope_problems(BASE, after, PLAN["targets"], "after", DIFF)
    written = {t["attachment_guid"]: t for t in PLAN["targets"]}
    for g in BASE:
        for b, a in zip(BASE[g], after[g]):
            d = DIFF(b, a)
            if b["guid"] not in written:
                assert not d, b["label"]
            else:
                paths = {x["path"].split("[")[0] for x in d}
                assert paths == {"lighting." + f for f in written[b["guid"]]["writes"]}, (b["label"], paths)


@case("scope controls: other field on a target, neighbour colour, wrong value, outside cue, row order all caught")
def _():
    t = next(x for x in PLAN["targets"] if x["glow_floor"])
    for what in ("cone", "neighbour", "wrong", "outside", "order"):
        bad = W.apply_rows(BASE, PLAN["targets"], "after")
        rows = bad[t["cue_guid"]]
        if what == "cone":
            next(r for r in rows if r["guid"] == t["attachment_guid"])["lighting"]["attenuation_radius_cm"] = 1.0
        elif what == "neighbour":
            next(r for r in rows if r["guid"] not in PLAN["target_attachment_guids"]
                 and "lighting" in r)["lighting"]["color"][0] = 0.123
        elif what == "wrong":
            next(r for r in rows if r["guid"] == t["attachment_guid"])["lighting"]["color"][1] = 0.9
        elif what == "outside":
            bad[FOREIGN["guid"]][0]["lighting"]["intensity"] = 5.0
        else:
            rows[0], rows[1] = rows[1], rows[0]
        assert W.scope_problems(BASE, bad, PLAN["targets"], "after", DIFF), what


@case("revert: before values restore the base exactly; ALL drifts listed; 1-ulp colour control caught")
def _():
    after = W.apply_rows(BASE, PLAN["targets"], "after")
    assert not W.field_drifts(after, PLAN["targets"], "after")
    back = W.apply_rows(after, PLAN["targets"], "before")
    assert all(not DIFF(b, a) for g in BASE for b, a in zip(BASE[g], back[g]))
    assert not W.exact_problems(back, PLAN["targets"], "before")
    assert not W.scope_problems(after, back, PLAN["targets"], "before", DIFF)
    hand = copy.deepcopy(after)
    t0, t1 = PLAN["targets"][0], PLAN["targets"][3]
    next(r for r in hand[t0["cue_guid"]] if r["guid"] == t0["attachment_guid"])["lighting"]["color"][0] = 0.2
    next(r for r in hand[t1["cue_guid"]] if r["guid"] == t1["attachment_guid"])["lighting"]["use_temperature"] = \
        not t1["writes"].get("use_temperature", [None, True])[1] if "use_temperature" in t1["writes"] else None
    drifts = W.field_drifts(hand, PLAN["targets"], "after")
    assert {d["guid"] for d in drifts} == ({t0["attachment_guid"], t1["attachment_guid"]}
                                           if "use_temperature" in t1["writes"] else {t0["attachment_guid"]}), drifts
    ulp = copy.deepcopy(back)
    t = PLAN["targets"][0]
    row = next(r for r in ulp[t["cue_guid"]] if r["guid"] == t["attachment_guid"])
    bits = struct.unpack("<I", struct.pack("<f", row["lighting"]["color"][1]))[0]
    row["lighting"]["color"][1] = struct.unpack("<f", struct.pack("<I", bits + 1))[0]
    assert W.exact_problems(ulp, PLAN["targets"], "before")
    rec = {"tool": W.MARK, "status": "saved_readback_verified", "plan": PLAN}
    W.check_record(rec)
    refuses("REVERT_RECORD_STATUS", W.check_record, dict(rec, status="prepared"))
    refuses("RECORD_TOOL_MISMATCH", W.check_record, dict(rec, tool="P02BRIGHTEN"))


def _export(rows):
    parts = []
    for r in rows:
        L = r["lighting"]
        bits = ["Type=Point", "IntensityUnits=Lumens", "Intensity=%r" % L["intensity"]]
        c = L["color"]
        if c[:4] != [1.0, 1.0, 1.0, 1.0]:                                   # ExportText omits defaults
            bits.append("Color=(R=%r,G=%r,B=%r,A=%r)" % tuple(c[:4]))
        if L["use_temperature"]:
            bits.append("bUseTemperature=True")
        if L["temperature_kelvin"] != 6500.0:
            bits.append("TemperatureKelvin=%r" % L["temperature_kelvin"])
        bits += ["VolumetricScatteringIntensity=1.0", "Drama=(UnstruckIntensityScale=0.0)"]
        parts.append("(AttachmentGuid=%s,Label=\"%s\",Lighting=(%s),Body=(Intensity=3.0))"
                     % (r["guid"], r["label"], ",".join(bits)))
    return "(WingPair=(Attachments=(" + ",".join(parts) + ")))"


@case("export hash removes exactly the targets' written fields (defaults omitted either side); controls caught")
def _():
    after = W.apply_rows(BASE, PLAN["targets"], "after")
    tb = [_export(BASE[g]) for g in sorted(BASE)]
    ta = [_export(after[g]) for g in sorted(after)]
    assert ta != tb and W.export_hash(RP, ta, PLAN["targets"]) == W.export_hash(RP, tb, PLAN["targets"])
    # some targets go white (Color omitted after) and some pink go use_temperature off (bUseTemperature omitted)
    assert any(t["swatch"] != "pink" for t in PLAN["targets"]) and any(t["swatch"] == "pink" for t in PLAN["targets"])
    t = PLAN["targets"][0]
    h0 = W.export_hash(RP, tb, PLAN["targets"])
    for what in ("neighbour", "scatter", "nested", "unwritten_intensity"):
        bad = copy.deepcopy(after)
        rows = bad[t["cue_guid"]]
        if what == "neighbour":
            next(r for r in rows if r["guid"] not in PLAN["target_attachment_guids"])["lighting"]["intensity"] = 1.5
            tx = [_export(bad[g]) for g in sorted(bad)]
        elif what == "unwritten_intensity":
            tt = next(x for x in PLAN["targets"] if "intensity" not in x["writes"])
            next(r for r in bad[tt["cue_guid"]] if r["guid"] == tt["attachment_guid"])["lighting"]["intensity"] = 1.0
            tx = [_export(bad[g]) for g in sorted(bad)]
        else:
            tx = [_export(bad[g]) for g in sorted(bad)]
            old = "VolumetricScatteringIntensity=1.0" if what == "scatter" else "UnstruckIntensityScale=0.0"
            seg = "AttachmentGuid=%s" % t["attachment_guid"]
            tx = [x.replace(seg + x.split(seg, 1)[1].split(old, 1)[0] + old,
                            seg + x.split(seg, 1)[1].split(old, 1)[0] + old.replace("0.0", "0.5").replace("1.0", "2.0"),
                            1) if seg in x else x for x in tx]
        assert W.export_hash(RP, tx, PLAN["targets"]) != h0, what
    refuses("EXPORT_TARGET_COUNT", W.export_hash, RP, tb,
            PLAN["targets"] + [dict(PLAN["targets"][0], attachment_guid="E" * 31 + "0")])


# ---------------------------------------------------------------- D. foreign records, p02_brighten
@case("p02_brighten overlap: its B12-B19 dead bulbs listed, our writes exclude intensity; reverted record -> none")
def _():
    ov = W.overlap_with_record(PLAN, BRIGHT)
    labels = {o["label"] for o in ov}
    assert {"P02 SCORE B%02d P02_FAILING_STAGE PRACTICAL_BULB_DEAD" % n for n in range(12, 20)} <= labels, labels
    assert all("intensity" not in o["our_fields"] for o in ov)
    assert W.overlap_with_record(PLAN, dict(BRIGHT, status="reverted")) == []


@case("foreign records: unacked = hits - acks; real offline scan names p02_brighten_record.json")
def _():
    hits = [{"path": "a.json"}, {"path": "b.json"}]
    assert W.unacked_records(hits, ["a.json"]) == ["b.json"] and W.unacked_records(hits, ["a.json", "b.json"]) == []
    saved = os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    found = SCORES.scan_foreign_records(roots, PLAN["target_attachment_guids"], exclude=[W.RECORD_PATH])
    FOREIGN_FOUND.extend(sorted(h["path"] for h in found))
    assert any(p.endswith("p02_brighten_record.json") for p in FOREIGN_FOUND), FOREIGN_FOUND


if __name__ == "__main__":
    for name, ok, detail in RESULTS:
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            print(detail)
    print("\nPer passage (fixture = last records; the live DRY decides):")
    for k, v in sorted(PLAN["per_passage"].items()):
        print("  %s targets=%d glow_floor=%d palette=%s already_warm=%d" % (
            k, v["targets"], v["glow_floor"], json.dumps(v["palette"], sort_keys=True), v["already_warm"]))
    print("counts=%s" % json.dumps(PLAN["counts"], sort_keys=True))
    print("roles targeted=%s" % dict(collections.Counter(t["role"] for t in PLAN["targets"])))
    print("untouched by reason=%s" % dict(collections.Counter(u["why"] for u in PLAN["untouched"])))
    print("foreign active records naming a target (offline scan): %s" % [os.path.basename(p) for p in FOREIGN_FOUND])
    failed = sum(1 for r in RESULTS if not r[1])
    print("\nPASS %d / FAIL %d" % (len(RESULTS) - failed, failed))
    sys.exit(1 if failed else 0)
