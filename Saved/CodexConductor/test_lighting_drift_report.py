"""Offline harness for lighting_drift_report.py (no Unreal). Run: python test_lighting_drift_report.py

Loads the REAL scores tool and, through it, the real P04 tool (offline, unreal=None), so the drift verdict
under test is the tools' own comparator. Every classification has a passing case and a failing control.
The last block runs the pure pipeline over the REAL records with live == recorded after (must find zero drift)
and replays the real rig_lamp_drop / opening records onto their GUIDs (must attribute them, not UNKNOWN).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("lighting_drift_report", os.path.join(HERE, "lighting_drift_report.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
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


def refuses(reason, fn, *args):
    try:
        fn(*args)
    except Exception as error:  # noqa: BLE001
        assert reason in str(error), "expected %s, got %s" % (reason, error)
        return
    raise AssertionError("expected refusal " + reason)


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as handle:
        return json.load(handle)


P02 = load("lighting_scores_record_P02.json")
T0 = P02["plan"]["targets"][0]          # P02 Wing 001
BEAM = T0["after_rows"][10]             # the [10] Gary tuned (P02 SCORE B01 THEATRICAL BEAM_R)
TOP_L = next(r for r in T0["after_rows"] if r["label"].endswith("TOP_L"))


def live_copy(target=T0):
    return copy.deepcopy(target["after_rows"])


def analyse(current, foreign=(), opening=None, mentions=None, target=T0):
    return M.analyse_target(TOOL, target, current, list(foreign), opening or {}, mentions or {})


def only_light(result):
    assert len(result["lights"]) == 1, [l["label"] for l in result["lights"]]
    return result["lights"][0]


@case("comparator: identical rows -> no drift; the tool's own raise is the verdict")
def _():
    r = analyse(live_copy())
    assert r["drift"] is False and r["lights"] == [] and r["comparator_consistent"]
    cur = live_copy()
    cur[10]["lighting"]["intensity"] += 1.0
    r = analyse(cur)
    assert r["drift"] and r["revert_verdict"].startswith("REVERT_CURRENT_STATE_DRIFT|cue=P02 Wing 001|differences=")
    # control: the same rows through the scores tool's offline revert model raise the same reason
    refuses("REVERT_CURRENT_STATE_DRIFT", TOOL._require_attachment_rows_equal, cur, T0["after_rows"],
            "REVERT_CURRENT_STATE_DRIFT|x")


@case("hand edit on P02 Wing 001 [10]: colour, cone, position -> UNKNOWN with slot and old->new")
def _():
    cur = live_copy()
    cur[10]["lighting"]["color"] = [1.0, 0.5, 0.2, 1.0]
    cur[10]["lighting"]["outer_cone_angle_degrees"] = 30.0
    cur[10]["relative_transform"]["location"][1] += 40.0
    light = only_light(analyse(cur))
    assert light["class"] == M.UNKNOWN and light["slot"] == "BEAM_R", light
    fields = {f["field"]: f for f in light["fields"]}
    assert set(fields) == {"lighting.color", "lighting.outer_cone_angle_degrees",
                           "relative_transform.location[1]"}, sorted(fields)
    assert fields["lighting.color"]["old"] == BEAM["lighting"]["color"]
    assert fields["lighting.color"]["new"] == [1.0, 0.5, 0.2, 1.0]
    assert all(f["class"] == M.UNKNOWN for f in fields.values())


def rig_record(rows_before, rows_after, run="20261006-022035", name="rig_lamp_drop_record_P02.json"):
    return {"path": os.path.join(HERE, name), "class": M.record_class(name), "status": "saved_readback_verified",
            "run": run, "snapshots": M.index_record_snapshots(
                {"before_target_rows": {r["guid"]: r for r in rows_before},
                 "after_target_rows": {r["guid"]: r for r in rows_after}})}


@case("rig lamp drop: z lowered by the record -> RIG_LAMP_DROP (expected, chain exact); control -> UNKNOWN")
def _():
    dropped = copy.deepcopy(TOP_L)
    dropped["relative_transform"]["location"][2] -= 25.0
    rec = rig_record([TOP_L], [dropped])
    cur = live_copy()
    index = next(i for i, r in enumerate(cur) if r["guid"] == TOP_L["guid"])
    cur[index] = copy.deepcopy(dropped)
    result = analyse(cur, [rec])
    light = only_light(result)
    assert light["class"] == "RIG_LAMP_DROP" and light["fields"][0]["evidence"][0]["chain_exact"], light
    assert light["fields"][0]["field"] == "relative_transform.location[2]"
    summary = M.summarise_passage("P02", "saved_readback_verified", [result])
    assert summary["expected_only"] and summary["lights_by_class"] == {"RIG_LAMP_DROP": 1}
    cur[index]["relative_transform"]["location"][2] -= 5.0      # moved again after the drop
    light = only_light(analyse(cur, [rec]))
    assert light["class"] == M.UNKNOWN and "changed after" in light["fields"][0]["notes"][0], light


@case("present_at: a record that SAW the value but did not write it dates the change; stays UNKNOWN")
def _():
    edited = copy.deepcopy(BEAM)
    edited["lighting"]["intensity"] = 999.0
    rec = rig_record([edited], [edited])
    cur = live_copy()
    cur[10] = copy.deepcopy(edited)
    light = only_light(analyse(cur, [rec]))
    assert light["class"] == M.UNKNOWN and light["fields"][0]["notes"][0].startswith("present_at=20261006-022035")


def opening_dir(enabled_target=False, changes=("enabled",), planner_ok=True):
    root = tempfile.mkdtemp(prefix="drift_open_")
    warm = copy.deepcopy(BEAM)
    warm["label"] = "W L"
    with open(os.path.join(root, M.OPENING_RECORD), "w", encoding="utf-8") as h:
        json.dump({"status": "applied", "warmers_attachment_original": {"W L": warm}}, h)
    with open(os.path.join(root, M.OPENING_REPORT), "w", encoding="utf-8") as h:
        json.dump({"run": "OPENING-APPLY-X", "house_warmer_write": {
            "targets": {"W L": {"enabled": enabled_target, "inner_cone_angle_degrees": 12.5}},
            "changes": ["W L:" + c for c in changes]}}, h)
    with open(os.path.join(root, M.OPENING_PLAN), "w", encoding="utf-8") as h:
        h.write('WARMER_WRITE_PATHS = (("enabled",), ("lighting", "inner_cone_angle_degrees"))\n' if planner_ok
                else 'WARMER_WRITE_PATHS = (("enabled",),)\n')
    return root


@case("opening warmers: enabled=record-proven, cone=inferred, intensity=UNKNOWN -> light UNKNOWN; controls")
def _():
    root = opening_dir()
    try:
        info = M.load_opening_info(root)
        cur = live_copy()
        cur[10]["enabled"] = False
        cur[10]["lighting"]["inner_cone_angle_degrees"] = 12.5
        cur[10]["lighting"]["intensity"] = 123.0
        light = only_light(analyse(cur, opening=info))
        fields = {f["field"]: f for f in light["fields"]}
        assert fields["enabled"]["class"] == "OPENING_SEQUENCE_WARMERS"
        assert fields["enabled"]["tier"].startswith("record-proven")
        assert fields["lighting.inner_cone_angle_degrees"]["tier"].startswith("inferred")
        assert fields["lighting.intensity"]["class"] == M.UNKNOWN and light["class"] == M.UNKNOWN
        cur[10]["lighting"]["intensity"] = BEAM["lighting"]["intensity"]
        assert only_light(analyse(cur, opening=info))["class"] == "OPENING_SEQUENCE_WARMERS"
    finally:
        shutil.rmtree(root)
    root = opening_dir(enabled_target=True)      # control: opening wanted it ON, live is OFF
    try:
        cur = live_copy()
        cur[10]["enabled"] = False
        light = only_light(analyse(cur, opening=M.load_opening_info(root)))
        assert light["class"] == M.UNKNOWN and "opening target" in light["fields"][0]["notes"][0]
    finally:
        shutil.rmtree(root)
    root = opening_dir(planner_ok=False)
    try:
        refuses("OPENING_WARMER_WRITE_PATHS_CHANGED", M.load_opening_info, root)
    finally:
        shutil.rmtree(root)


@case("mentions: an unmodelled record naming the GUID -> OTHER_RECORD; a modelled one never does")
def _():
    hits = [{"path": os.path.join(HERE, "p01_score_shift_record.json"), "guids": [BEAM["guid"]]},
            {"path": os.path.join(HERE, "rig_lamp_drop_record_P02.json"), "guids": [BEAM["guid"]]}]
    cur = live_copy()
    cur[10]["lighting"]["intensity"] = 5.0
    m = M.mentions_by_guid(hits, [])
    assert only_light(analyse(cur, mentions=m))["class"] == "OTHER_RECORD:p01_score_shift_record.json"
    m = M.mentions_by_guid(hits, [os.path.join(HERE, "p01_score_shift_record.json"),
                                  os.path.join(HERE, "rig_lamp_drop_record_P02.json")])
    assert only_light(analyse(cur, mentions=m))["class"] == M.UNKNOWN


@case("records: terminal status ignored, opening record not used as a before/after snapshot")
def _():
    root = tempfile.mkdtemp(prefix="drift_rec_")
    try:
        for name, status in (("a_record.json", "reverted"), ("b_record.json", "saved_readback_verified")):
            with open(os.path.join(root, name), "w", encoding="utf-8") as h:
                json.dump({"status": status, "after_target_rows": {BEAM["guid"]: BEAM}}, h)
        with open(os.path.join(root, M.OPENING_RECORD), "w", encoding="utf-8") as h:
            json.dump({"status": "applied", "warmers_attachment_original": {"x": BEAM}}, h)
        got = M.load_foreign_records(root, [], SCORES.TERMINAL_STATUSES)
        assert [os.path.basename(r["path"]) for r in got] == ["b_record.json"], got
    finally:
        shutil.rmtree(root)


@case("structure: removed, added (record-added -> LIGHTING_EVENTS) and reordered rows all drift")
def _():
    cur = live_copy()
    del cur[3]
    r = analyse(cur)
    assert r["drift"] and r["lights"][0]["fields"][0]["field"] == "<row removed>"
    extra = copy.deepcopy(BEAM)
    extra["guid"], extra["label"] = "E" * 32, "EVENT ROW"
    cur = live_copy() + [extra]
    ev = {"path": os.path.join(HERE, "lighting_events_revert_record.json"), "class": "LIGHTING_EVENTS",
          "status": "saved_readback_verified", "run": "R", "snapshots": M.index_record_snapshots(
              {"plan": {"targets": [{"before_rows": [], "after_rows": [extra]}]}})}
    light = only_light(analyse(cur, [ev]))
    assert light["class"] == "LIGHTING_EVENTS" and light["slot"] == "NEW (not in record)"
    assert only_light(analyse(cur))["class"] == M.UNKNOWN          # control: no record -> UNKNOWN
    cur = live_copy()
    cur[0], cur[1] = cur[1], cur[0]
    r = analyse(cur)
    assert r["drift"] and r["order_changed"] and r["lights"] == []


@case("markdown lists cue label, slot, field, old -> new; rig drops counted, not tabled")
def _():
    cur = live_copy()
    cur[10]["lighting"]["outer_cone_angle_degrees"] = 30.0
    summary = M.summarise_passage("P02", "saved_readback_verified", [analyse(cur)])
    text = M.render_markdown({"run": "DRIFT-T", "census_equal": True, "passages": [
        summary, {"passage": "P03", "skipped": "no active record"}]})
    assert "| P02 Wing 001 | P02 SCORE B01 THEATRICAL BEAM_R | BEAM_R | lighting.outer_cone_angle_degrees:" in text
    assert "-> 30 |" in text and "UNKNOWN (likely hand edit) 1" in text and "Skipped: no active record" in text


@case("read-only self audit: no setter/save/modify/materialize call in the tool; control file is caught")
def _():
    assert M.forbidden_calls() == [], M.forbidden_calls()
    path = os.path.join(tempfile.mkdtemp(prefix="drift_src_"), "bad.py")
    with open(path, "w", encoding="utf-8") as h:
        h.write("def f(a, show):\n    a.set_editor_property('enabled', False)\n    show.modify()\n")
    assert len(M.forbidden_calls(path)) == 2
    shutil.rmtree(os.path.dirname(path))


@case("loader refuses an unguarded main() and a top-level call")
def _():
    root = tempfile.mkdtemp(prefix="drift_ld_")
    try:
        for name, src, reason in (("a.py", "def main():\n    pass\nmain()\n", "MAIN_GUARD_SHAPE"),
                                  ("b.py", "x = 1\nprint(x)\nif unreal is not None:\n    main()\n",
                                   "TOP_LEVEL_SIDE_EFFECT")):
            with open(os.path.join(root, name), "w", encoding="utf-8") as h:
                h.write(src)
            refuses(reason, M.load_without_main, os.path.join(root, name), "_t")
    finally:
        shutil.rmtree(root)


MEASURED = {}


@case("REAL records, live == after: zero drift on every target of every active record")
def _():
    for passage in M.PASSAGES:
        path = SCORES._record_path(passage)
        if not os.path.isfile(path):
            MEASURED[passage] = "no record"
            continue
        rec = load(os.path.basename(path))
        foreign = M.load_foreign_records(HERE, [path], SCORES.TERMINAL_STATUSES)
        cues = [analyse(copy.deepcopy(t["after_rows"]), foreign, target=t) for t in rec["plan"]["targets"]]
        s = M.summarise_passage(passage, rec["status"], cues)
        assert s["drifted_cues"] == 0 and all(c["comparator_consistent"] for c in cues), passage
        MEASURED[passage] = "%d targets, 0 drift, %d foreign records with rows" % (len(cues), len(foreign))


@case("REAL replay: each active rig_lamp_drop record's after rows -> RIG_LAMP_DROP, never UNKNOWN")
def _():
    for passage in M.PASSAGES:
        rig_path = os.path.join(HERE, "rig_lamp_drop_record_%s.json" % passage)
        path = SCORES._record_path(passage)
        if not (os.path.isfile(rig_path) and os.path.isfile(path)):
            continue
        rig, rec = load(os.path.basename(rig_path)), load(os.path.basename(path))
        foreign = M.load_foreign_records(HERE, [path], SCORES.TERMINAL_STATUSES)
        counts, chain = {}, 0
        for t in rec["plan"]["targets"]:
            cur = [copy.deepcopy(rig["after_target_rows"].get(r["guid"], r)) for r in t["after_rows"]]
            result = analyse(cur, foreign, target=t)
            for light in result["lights"]:
                counts[light["class"]] = counts.get(light["class"], 0) + 1
                chain += all(e.get("chain_exact") for f in light["fields"] for e in f["evidence"][:1])
        assert M.UNKNOWN not in counts, (passage, counts)
        MEASURED["rig " + passage] = "%s, chain_exact %d" % (counts, chain)


@case("REAL replay: P01 House L/R disabled per the real opening report -> OPENING_SEQUENCE_WARMERS")
def _():
    rec = load("lighting_scores_record_P01.json")
    info = M.load_opening_info(HERE)
    assert info, "opening record absent"
    t = next(t for t in rec["plan"]["targets"] if any(r["guid"] in info for r in t["after_rows"]))
    cur = copy.deepcopy(t["after_rows"])
    for r in cur:
        if r["guid"] in info:
            r["enabled"] = False
    lights = analyse(cur, opening=info, target=t)["lights"]
    assert len(lights) == 2 and {l["class"] for l in lights} == {"OPENING_SEQUENCE_WARMERS"}, lights
    MEASURED["opening P01"] = "%s slots=%s" % (t["cue_label"], sorted({l["slot"] for l in lights}))


if __name__ == "__main__":
    for name, ok, detail in RESULTS:
        print("%s  %s" % ("PASS" if ok else "FAIL", name))
        if detail:
            print(detail)
    for key, value in MEASURED.items():
        print("  measured %s: %s" % (key, value))
    failed = sum(1 for r in RESULTS if not r[1])
    print("LIGHTING_DRIFT_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - failed, failed))
    raise SystemExit(1 if failed else 0)
