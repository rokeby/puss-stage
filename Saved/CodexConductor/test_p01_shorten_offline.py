"""Offline harness for p01_shorten.py (system Python, no Unreal). Every gate has a failing control.

Fixture (the live DRY re-reads all of it):
  P01 segment 2312640..4624705 = 2312065 ticks (96.336 s) and every segment after it
    [meas walking_music_swap_record_P01.json segments_before, 5 Oct].
  48 bays, GUIDs in order [meas lighting_scores_record_P01.json plan.bay_guids, 5 Oct]; meshes per bay
    [meas CodexFlatV3/swapkit/show_wing_dump.json, 4 Oct - may be stale for meshes, the DRY re-reads the Show].
  Timing split INFERRED: 48 x (48000 ticks, 600 cm) = 300 cm/s [inf: 300.0 cm/s measured between the
    PSTILLS-P01-20261005-070532 stills at 9.634 s and 86.702 s; 600 cm p456_baseline_plan.json p01_spacing]; lead 19008
    ticks / 198 cm [inf: ~250 cm/s at the start, opening_walkin_probe.json]; tail closes the measured length and the
    measured route 28784.0135 cm [meas probe_routes.json; hangar_s1_record.json dock].
  Song 73.516032 s, rail fade 1 s [meas walking_music_swap_record_P01.json]; 25 fps / 24000 ticks; settle 1.0 s
    [meas passage_retime_to_music_dry.json settle_source rig(s), 6 Oct].
Run: python test_p01_shorten_offline.py [--table] -> P01_SHORTEN_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.dirname(HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load("p01_shorten")
assert ps.unreal is None, "harness must run without Unreal"
R = ps.load_retime(HERE)

with open(os.path.join(HERE, "p01_shorten_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)
with open(os.path.join(HERE, "walking_music_swap_record_P01.json"), encoding="utf-8") as _h:
    _W = json.load(_h)
SEGMENTS = [{"label": s["label"], "start": int(s["start"]), "end": int(s["end"])} for s in _W["segments_before"]]
P01_SEG = [s for s in SEGMENTS if s["label"] == "Passage 1"][0]
with open(os.path.join(SAVED, "CodexFlatV3", "swapkit", "show_wing_dump.json"), encoding="utf-8") as _h:
    DUMP = [r for r in json.load(_h) if r.get("passage") == "P01"]
TICK, FPS = 24000.0, (25, 1)
GUIDS = list(ARGS["bay_guids"])
LABELS = ps.bay_labels(ARGS["bay_label_format"], 48)
SHOW_ORDER_LABELS = [r["label"] for r in DUMP]          # positions 10-12 read 011, 012, 010 [meas 4 Oct]


def facts(**over):
    f = {"labels": list(SHOW_ORDER_LABELS), "guids": list(GUIDS), "intervals": [48000] * 48, "gaps": [600.0] * 48,
         "lead": 19008, "tail": 2312065 - 19008 - 47 * 48000, "lead_cm": 198.0,
         "tail_cm": 28784.0135 - 198.0 - 47 * 600.0, "segment": dict(P01_SEG)}
    f.update(over)
    return f


def args_with(**over):
    a = copy.deepcopy(ARGS)
    a.update(over)
    return a


CHECKS = {"n": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def raises(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except (ps.PlanError, R.PlanError, ValueError):
        return True
    return False


# ---------------------------------------------------------------------------------------------------------------------
@test
def t_fixture():
    f = facts()
    check(ps.compiled_length(f["lead"], f["intervals"], f["tail"]) == P01_SEG["end"] - P01_SEG["start"] == 2312065,
          "fixture sums to the measured 96.336 s")
    check(abs(ps.route_length(f["lead_cm"], f["gaps"], f["tail_cm"]) - 28784.0135) < 1e-6, "fixture route measured")
    check(len(GUIDS) == 48 and GUIDS[0] == DUMP[0]["cue_guid"] and GUIDS[-1] == DUMP[-1]["cue_guid"],
          "bay GUID order = Show order in the 4 Oct dump")
    check(sorted(SHOW_ORDER_LABELS) == LABELS, "dump labels are P01 Wing 001..048 once each")
    check(SHOW_ORDER_LABELS != LABELS and SHOW_ORDER_LABELS[9:12] == ["P01 Wing 011", "P01 Wing 012", "P01 Wing 010"],
          "Show order != label order at positions 10-12 (why the drop is by position)")
    check(SHOW_ORDER_LABELS[42:] == LABELS[42:], "positions 43-48 carry labels 043-048")
    check(all(r["enabled"] for r in DUMP), "no P01 cue disabled today (disable path never exercised on this Show)")


@test
def t_validate_args():
    check(ps.validate_args(ARGS) == [], "shipped DRY args valid: %r" % ps.validate_args(ARGS))
    check(ARGS["mode"] == "DRY" and not ARGS["decided_by"], "shipped args are DRY and undecided")
    check(any("DROP_LAST" in x for x in ps.validate_args(args_with(drop_last=0))), "control: drop 0")
    check(any("DROP_LAST" in x for x in ps.validate_args(args_with(drop_last=47))), "control: drop leaves 1 bay")
    check(any("PASSAGE_LABEL" in x for x in ps.validate_args(args_with(passage_label="Passage 2"))), "control: P02")
    check(any("BAY_GUIDS" in x for x in ps.validate_args(args_with(bay_guids=GUIDS[:47]))), "control: 47 guids")
    check(any("BAY_GUIDS" in x for x in ps.validate_args(args_with(bay_guids=GUIDS[:47] + GUIDS[:1]))),
          "control: duplicate guid")
    a = args_with(mode="APPLY")
    bad = ps.validate_args(a)
    check(any("NOT_DECIDED" in x for x in bad) and any("FOLLOWONS_NOT_ACKED" in x for x in bad)
          and any("EXPECTED_OLD_LEN" in x for x in bad), "control: APPLY needs decision, acks, DRY numbers")
    a = args_with(mode="APPLY", decided_by="Gary", followons_ack=list(ps.REQUIRED_ACKS),
                  expected={"old_len_ticks": 1, "new_len_ticks": 1, "removed_ticks": 1, "removed_cm": 1.0,
                            "dropped_guids": ["x"]})
    check(ps.validate_args(a) == [], "complete APPLY args valid")
    a["followons_ack"] = ["S1_REDOCK"]
    check(any("MATCH_S1_HANDOFF" in x for x in ps.validate_args(a)), "control: one ack missing")


@test
def t_plan_drop():
    plan, r = ps.plan_drop(facts(), 6, ARGS["keep_labels"], ARGS["bay_label_format"], 48, GUIDS)
    check(r == [], "drop 6 plans clean: %r" % r)
    check(plan["removed_ticks"] == 6 * 48000 and abs(plan["removed_cm"] - 3600.0) < 1e-9, "6 bays = 12 s / 3600 cm")
    check(plan["new_len_ticks"] == 2312065 - 288000 and plan["bays_after"] == 42, "new length 84.336 s, 42 bays")
    check(abs(plan["route_new_cm"] - 25184.0135) < 1e-6, "route 28784.01 -> 25184.01 cm")
    check([d["label"] for d in plan["dropped"]] == LABELS[42:], "drops P01 Wing 043..048")
    check(ps.dropped_numbers(plan) == list(range(43, 49)), "orphan numbers 43-48")
    pl = ps.plan_drop(facts(labels=SHOW_ORDER_LABELS[:42] + ["P01 Wing 044", "P01 Wing 043"] + SHOW_ORDER_LABELS[44:]),
                      6, [], ARGS["bay_label_format"], 48)[0]
    check(ps.dropped_numbers(pl) == list(range(43, 49)), "swapped labels inside the drop: same numbers")
    pl = ps.plan_drop(facts(labels=["P01 Wing 043"] + SHOW_ORDER_LABELS[1:42] + ["P01 Wing 001"] + SHOW_ORDER_LABELS[43:]),
                      6, [], ARGS["bay_label_format"], 48)[0]
    check(1 in ps.dropped_numbers(pl) and 43 in ps.dropped_numbers(pl), "control: a moved label adds its number")
    check(plan["dropped_guids"] == GUIDS[42:] and plan["new_last"]["guid"] == GUIDS[41] == "B198C7F004497AB3F87E92BDD9780FD6",
          "new last = P01 Wing 042 (B198C7F0...)")
    check(plan["old_last"]["guid"] == "10D28FD6C64C2D8B7D6CE586A94C8402", "old last = P01 Wing 048")
    # controls
    _p, r = ps.plan_drop(facts(), 6, ["P01 Wing 045"], ARGS["bay_label_format"], 48, GUIDS)
    check(any("KEEP_BAY_IN_DROP" in x for x in r), "control: a kept bay inside the drop refuses")
    lab = list(SHOW_ORDER_LABELS)
    lab[10] = "P01 Wing 099"
    _p, r = ps.plan_drop(facts(labels=lab), 6, [], ARGS["bay_label_format"], 48, GUIDS)
    check(any("BAY_LABEL_SET" in x for x in r), "control: a foreign label refuses")
    plan_o, r = ps.plan_drop(facts(), 6, [], ARGS["bay_label_format"], 48, GUIDS)
    check(r == [] and [x[0] for x in plan_o["reordered_positions"]] == [10, 11, 12],
          "the measured 10-12 reorder is reported, not refused")
    _p, r = ps.plan_drop(facts(), 6, [], ARGS["bay_label_format"], 48, list(reversed(GUIDS)))
    check(any("BAY_GUIDS_CHANGED" in x for x in r), "control: reordered guids refuse")
    _p, r = ps.plan_drop(facts(tail=1), 6, [], ARGS["bay_label_format"], 48, GUIDS)
    check(any("COMPILE_MODEL_MISMATCH" in x for x in r), "control: timing that does not sum refuses")
    _p, r = ps.plan_drop(facts(labels=SHOW_ORDER_LABELS[:47], guids=GUIDS[:47], intervals=[48000] * 47, gaps=[600.0] * 47),
                         6, [], ARGS["bay_label_format"], 48, None)
    check(any("BAY_COUNT" in x for x in r), "control: 47 live bays refuse")
    check(raises(ps.plan_drop, facts(), 47, [], ARGS["bay_label_format"], 48), "control: drop 47 raises")
    # uneven intervals: the dropped spans are exactly intervals[kept-1 : bays-1]
    iv = [48000] * 48
    iv[41], iv[46], iv[47] = 50000, 52000, 99999      # 42->43 dropped, 47->48 dropped, 48's own unused
    plan, _r = ps.plan_drop(facts(intervals=iv, tail=2312065 - 19008 - 47 * 48000 - 2000 - 4000), 6, [],
                            ARGS["bay_label_format"], 48)
    check(plan["removed_ticks"] == 4 * 48000 + 50000 + 52000, "removed = the 6 spans after the new last bay")
    check(plan["unused_last_interval"] == 50000, "new last bay's own interval becomes unused (kept for REVERT)")


@test
def t_chain_numbers():
    rows = {n: ps.chain_numbers(R, facts(), n, 73.516032, 2.0, 1.0, TICK, FPS) for n in range(0, 9)}
    check(all(abs(r["new_len_s"] - 75.52) < 1e-9 for r in rows.values()), "every N ends at song + 2 s = 75.52 s")
    check(abs(rows[6]["bay_speed_new"] - 337.25) < 0.05 and abs(rows[6]["bay_speed_rise_pct"] - 12.42) < 0.05,
          "N=6: ~337 cm/s, +12.4%%: %r" % rows[6])
    check(abs(rows[5]["bay_speed_rise_pct"] - 15.1) < 0.1, "N=5: +15.1%%: %r" % rows[5]["bay_speed_rise_pct"])
    check(rows[0]["bay_speed_rise_pct"] > 28.0, "control: N=0 (retime only) is +28%")
    rises = [rows[n]["bay_speed_rise_pct"] for n in range(0, 9)]
    check(all(a > b for a, b in zip(rises, rises[1:])), "more bays dropped -> smaller speed rise (monotonic)")
    check(12.0 <= rows[6]["bay_speed_rise_pct"] <= 15.0 and 12.0 <= rows[5]["bay_speed_rise_pct"] <= 15.5,
          "N=5..6 is the brief's 12-15% window")
    check(not (12.0 <= rows[8]["bay_speed_rise_pct"] <= 15.0), "control: N=8 falls outside the window")
    check(abs(rows[6]["route_cm"] - 25184.0135) < 1e-3, "N=6 route 25184 cm")
    check(rows[6]["lead_speed_new"] > rows[6]["lead_speed_old"], "lead-in speeds up too (walk-in step)")
    nc = ps.chain_numbers(R, facts(), 6, 73.516032, 2.0, 1.0, TICK, FPS, settle_compensation=False)
    check(nc["tail_pre_settle_new"] > rows[6]["tail_pre_settle_new"], "control: no settle compensation -> tail surge")


@test
def t_look_period():
    """Recommendation evidence: the P01 look repeats every 6 bays (3 wing meshes x 2 ceilings) [meas 4 Oct dump]."""
    def look(r):
        return (r["left"], r["right"], r.get("top"))
    looks = [look(r) for r in DUMP]
    off = [i + 1 for i in range(48) if looks[i] != looks[i % 6]]
    check(off == [10, 11, 12], "6-bay look period everywhere except the reordered 10-12: %r" % off)
    check(all(looks[i] == looks[i - 6] for i in range(36, 48)), "period holds over bays 31-48 (the end)")
    check(looks[41] == looks[47], "N=6: new last bay 42 looks like today's last bay 48")
    check(looks[42] != looks[47], "control: N=5 (last bay 43) does not")
    check(looks[40] != looks[47], "control: N=7 (last bay 41) does not")


@test
def t_segments_shift():
    plan, _r = ps.plan_drop(facts(), 6, [], ARGS["bay_label_format"], 48)
    pred = R.predict_segments(SEGMENTS, {"Passage 1": -plan["removed_ticks"]})
    by = {p["label"]: p for p in pred}
    check(by["Opening — Curtain"]["shift"] == 0 and by["Passage 1"]["new_start"] == P01_SEG["start"],
          "Opening and P01 start do not move")
    check(by["Passage 1"]["new_end"] == P01_SEG["end"] - 288000, "P01 end moves 12 s earlier")
    later = [p for p in pred if p["start"] >= P01_SEG["end"]]
    check(later and all(p["shift"] == -288000 and p["new_len"] == p["old_len"] for p in later),
          "every later segment moves -12 s, length unchanged")
    spans = R.retimed_spans(SEGMENTS, {"Passage 1": -288000})
    check(R.shift_at(P01_SEG["start"], spans) == 0 and R.shift_at(P01_SEG["end"], spans) == -288000,
          "boundary shifts")
    check(R.shift_at(P01_SEG["start"] + 10, spans) is None, "control: a boundary inside P01 has no single shift")


@test
def t_orphan_scan():
    plan6, _r = ps.plan_drop(facts(), 6, [], ARGS["bay_label_format"], 48)
    plan5, _r = ps.plan_drop(facts(), 5, [], ARGS["bay_label_format"], 48)
    paths = [os.path.normpath(os.path.join(SAVED, p)) for p in ARGS["orphan_records"]]
    rows6 = {os.path.basename(r["path"]): r for r in ps.scan_orphans(
        paths, plan6["dropped_guids"], ps.dropped_numbers(plan6), ARGS["bay_label_format"])}
    rows5 = {os.path.basename(r["path"]): r for r in ps.scan_orphans(
        paths, plan5["dropped_guids"], ps.dropped_numbers(plan5), ARGS["bay_label_format"])}
    check(all(r["exists"] for r in rows6.values()), "every listed record exists: %r" % [
        k for k, r in rows6.items() if not r["exists"]])
    check(rows6["lighting_scores_record_P01.json"]["orphaned"], "scores record names dropped bays")
    check(rows6["blink_spots_revert_record.json"]["guid_hits"].get("10D28FD6C64C2D8B7D6CE586A94C8402"),
          "blink spots record holds bay 48")
    check(rows6["p01_note_lamps_plan.json"]["label_hits"].get("P01 Wing 043(?!d)") is not None or
          any("043" in k for k in rows6["p01_note_lamps_plan.json"]["label_hits"]), "note-lamp plan uses bay 43 (N=6)")
    check(not any("043" in k for k in rows5["p01_note_lamps_plan.json"]["label_hits"]),
          "control: N=5 keeps bay 43, no 043 hit")
    tmp = tempfile.mkdtemp()
    try:
        clean = os.path.join(tmp, "clean.json")
        with open(clean, "w", encoding="utf-8") as h:
            json.dump({"bays": ["P01 Wing 0430", "P01 Wing 042", "P01 SCORE B420"]}, h)
        r = ps.scan_orphans([clean, os.path.join(tmp, "missing.json")], plan6["dropped_guids"],
                            [d["pos"] for d in plan6["dropped"]], ARGS["bay_label_format"])
        check(not r[0]["orphaned"], "control: near-miss labels (0430, 042, B420) are not hits")
        check(not r[1]["exists"] and not r[1]["orphaned"], "missing file reported, not a hit")
        dirty = os.path.join(tmp, "dirty.json")
        with open(dirty, "w", encoding="utf-8") as h:
            json.dump({"x": "P01 SCORE B44 TOP_L", "g": GUIDS[45].lower()}, h)
        r = ps.scan_orphans([dirty], plan6["dropped_guids"], [d["pos"] for d in plan6["dropped"]],
                            ARGS["bay_label_format"])
        check(r[0]["orphaned"] and r[0]["guid_hits"] and r[0]["label_hits"], "score label + lower-case guid found")
    finally:
        shutil.rmtree(tmp)


@test
def t_view_and_gates():
    before = {"cue000": ["g0", "Opening", "SCENE", True, 1], "cue043": ["g43", "P01 Wing 043", "WP", True, "x"],
              "cue044": ["g44", "P01 Wing 044", "WP", True, "x"],
              "passage00": ["p", "Passage 1", "first", "old_last", 198.0]}
    want = ps.expected_view_after(before, ["cue043", "cue044"], "passage00", "new_last")
    got = json.loads(json.dumps(want))
    check(ps.view_diff(want, got) == [], "exact write passes")
    got["cue000"][4] = 2
    check(ps.view_diff(want, got) == ["cue000"], "control: a stray change elsewhere is caught")
    got = json.loads(json.dumps(want))
    got["passage00"][4] = 199.0
    check(ps.view_diff(want, got) == ["passage00"], "control: a stray P01 field change is caught")
    check(before["cue043"][3] is True, "expected_view_after does not mutate its input")
    check(raises(ps.expected_view_after, before, ["cue099"], "passage00", "n"), "control: unknown row raises")
    check(ps.handoff_after_gate(["a"], ["a", "S1"], ["S1"]) == [], "Scene 1 going stale is allowed")
    check(ps.handoff_after_gate([], ["S2"], ["S1"]), "control: another Scene going stale fails")
    check(ps.end_view_gate([28784.0, 0, 150], [25184.0, 0, 150], 3600.0) == [], "end view moved 3600 cm")
    check(ps.end_view_gate([28784.0, 0, 150], [28784.0, 0, 150], 3600.0), "control: end view did not move")
    check(ps.end_view_gate(None, [0, 0, 0], 3600.0), "control: unreadable end view")
    check(ps.wing_pin_refusals(["a"], ["b"]) == [] and ps.wing_pin_refusals(["b"], ["b"]), "wing pin gate + control")
    check(ps.relative_pin_refusals([100], 200) == [] and ps.relative_pin_refusals([300], 200),
          "relative pin gate + control")
    plan, _r = ps.plan_drop(facts(), 6, [], ARGS["bay_label_format"], 48)
    exp = {k: plan[k] for k in ("old_len_ticks", "new_len_ticks", "removed_ticks", "removed_cm", "dropped_guids")}
    check(ps.expected_refusals(plan, exp, "APPLY") == [], "DRY numbers match")
    check(ps.expected_refusals(plan, dict(exp, removed_ticks=1), "APPLY"), "control: changed since DRY")
    check(ps.expected_refusals(plan, {}, "DRY") == [], "DRY never checks expected")


@test
def t_live_gates():
    ok = {"mode": "DRY", "confirm": "DRY P01SHORTEN", "census": {"content": [], "maps": []}}
    check(ps.live_gates(ok) == [], "clean DRY state")
    check(ps.live_gates(dict(ok, confirm="DRY RETIME")), "control: wrong confirm")
    check(ps.live_gates(dict(ok, pie=True)), "control: PIE")
    check(ps.live_gates(dict(ok, sequencer_open=True)), "control: Sequencer open")
    check(ps.live_gates(dict(ok, census={"content": ["/Game/X"], "maps": []})), "control: dirty census")
    ap = dict(ok, mode="APPLY", confirm="APPLY P01SHORTEN")
    check(ps.live_gates(ap) == [] and ps.live_gates(dict(ap, record_exists=True)), "APPLY + control: record exists")
    rv = dict(ok, mode="REVERT", confirm="REVERT P01SHORTEN", record_applied=True)
    check(ps.live_gates(rv) == [], "REVERT with an applied record")
    check(any("LIFO" in x for x in ps.live_gates(dict(rv, retime_records=["passage_retime_to_music_record_P01.json"]))),
          "control: REVERT refused while the P01 retime is applied")
    check(ps.live_gates(dict(rv, record_applied=False)), "control: REVERT without record")
    rec = {"before": {"timing": 1, "segments": 2, "managed": 3, "keys": 4, "flags": 5},
           "after": {"timing": 6, "segments": 7, "managed": 8, "keys": 9, "flags": 10}}
    check(ps.drift_refusals(dict(rec["after"]), rec) == [], "no drift")
    check(ps.drift_refusals(dict(rec["after"], flags=0), rec), "control: drift in flags")
    check(ps.revert_exact_gate(dict(rec["before"]), rec) == [], "revert exact")
    check(ps.revert_exact_gate(dict(rec["before"], timing=0), rec), "control: revert not exact")


@test
def t_retime_module_link():
    check("1" in R.VALID_KEYS and R.label_of("1") == "Passage 1", "retime accepts P01 (extension present)")
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(HERE, ps.RETIME_FILE), encoding="utf-8") as h:
            src = h.read()
        old = src.replace('VALID_KEYS = ("1", "2", "3", "4", "5")', 'VALID_KEYS = ("2", "3", "4", "5")')
        check(old != src, "fixture: could build a pre-extension copy")
        with open(os.path.join(tmp, ps.RETIME_FILE), "w", encoding="utf-8") as h:
            h.write(old)
        check(raises(ps.load_retime, tmp), "control: a retime tool without P01 is refused")
    finally:
        shutil.rmtree(tmp)
    with open(os.path.join(HERE, "passage_retime_to_music_args.json"), encoding="utf-8") as h:
        rargs = json.load(h)
    check(rargs["prerequisite_records"].get("1") == ps.RECORD_NAME, "retime args gate P01 on this tool's record")
    check(rargs["per_passage"]["1"]["guid"] == ARGS["passage_guid"] and
          abs(rargs["per_passage"]["1"]["song_s"] - ARGS["song_s"]) < 1e-9, "retime args P01 row = these args")


def offline_table():
    print("OFFLINE_CHAIN (INFERRED split: 48 x 600 cm @ 300 cm/s; lead 198 cm @ 250; measured length + route)")
    for n in range(0, 9):
        r = ps.chain_numbers(R, facts(), n, 73.516032, 2.0, 1.0, TICK, FPS)
        print("  drop %d -> %d bays | shortened %.3f s | route %.1f cm | retime k=%.4f -> %.2f s | bay %.1f -> %.1f "
              "cm/s (%+.1f%%) | lead-in %.1f -> %.1f | tail pre-settle %.1f" % (
                  n, r["bays"], r["shortened_len_s"], r["route_cm"], r["k"], r["new_len_s"], r["bay_speed_old"],
                  r["bay_speed_new"], r["bay_speed_rise_pct"], r["lead_speed_old"], r["lead_speed_new"],
                  r["tail_pre_settle_new"]))


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - counted as a failure
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    if "--table" in sys.argv:
        offline_table()
    for f in CHECKS["failed"]:
        print("FAIL:", f)
    print("P01_SHORTEN_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
