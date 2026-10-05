"""Offline harness for opening_readback.py's pure parts (system Python, no Unreal). Every finding has a failing control.

Fixture numbers, cited: last APPLY read-back (run OPENING-APPLY-20261004-131449, opening_sequence_report_apply.json):
playback [0, 2409] @25 fps, tick 24000; GC [[0,1871,23200,240799],[1871,2121,23200,0],[2121,2409,263999,0]];
release 74.8733 s, landed 79.2067 s; segments Opening 0-96.36, Passage 1 96.36-192.696 [meas 4 Oct].
Gary's 14:02 end is NOT known offline: 2600 below is a hypothetical stand-in, labelled as such.
Run: python test_opening_readback.py -> OPENING_READBACK_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("opening_readback", os.path.join(HERE, "opening_readback.py"))
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)
assert rb.unreal is None

CHECKS = {"n": 0, "failed": []}
TESTS = []
GC = [[0, 1871, 23200, 240799], [1871, 2121, 23200, 0], [2121, 2409, 263999, 0]]
with open(os.path.join(HERE, "opening_timing.json"), encoding="utf-8") as _h:
    CFG = json.load(_h)
HYPOTHETICAL_GARY_END = 2600


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def has(findings, prefix):
    return any(text.startswith(prefix) for _lvl, text in findings)


@test
def curtain_matches_last_apply():
    c = rb.curtain_timing(GC, 25.0, 24000.0, CFG["curtain"])
    check(abs(c["release_s"] - 74.8733) < 1e-3, "release 74.873 s: %r" % c)
    check(abs(c["landed_s"] - 79.2067) < 1e-3, "landed 79.207 s")
    check(c["contiguous"] and c["pile_end_frame"] == 2409, "contiguous, pile to 2409")
    moved = copy.deepcopy(GC)
    moved[1][0] += 25
    moved[0][1] += 25
    check(abs(rb.curtain_timing(moved, 25.0, 24000.0, CFG["curtain"])["release_s"] - 75.8733) < 1e-3,
          "FALL moved 25 frames -> release +1 s (control)")
    gap = copy.deepcopy(GC)
    gap[2][0] += 1
    check(not rb.curtain_timing(gap, 25.0, 24000.0, CFG["curtain"])["contiguous"], "gap detected")
    check("error" in rb.curtain_timing(GC[:2], 25.0, 24000.0, CFG["curtain"]), "2 sections refused")


@test
def digest_is_the_apply_hash():
    g = {"__name__": "p"}
    exec(open(os.path.join(HERE, "opening_sequence_plan.py"), encoding="utf-8").read(), g)
    rows = [[0, 0.0], [38, 0.35], [100, 1.2]]
    check(rb.digest(rows) == g["track_hash"](rows), "same 16-hex digest as the planner/apply")
    check(rb.digest(rows) != rb.digest([[0, 0.0], [38, 0.35], [100, 1.2001]]), "a 1e-4 edit changes it (control)")


@test
def hash_compare_controls():
    live = {"A": [[0, 1.0]], "B": [[0, 2.0]], "C": [[1, 1.0]]}
    rec = {"A": rb.digest([[0, 1.0]]), "B": rb.digest([[0, 9.0]]), "D": "x"}
    st = rb.hash_compare(rec, live)
    check(st == {"A": "match", "B": "EDITED", "C": "NEW_TRACK", "D": "MISSING_NOW"}, "statuses %r" % st)


@test
def marker_and_key_diff():
    m = rb.marker_compare([["OPN curtain_release", 1872], ["OPN opening_end", 2500], ["other", 5]],
                          {"curtain_release": 1872, "opening_end": 2409, "walkin_start": 2144})
    check(not m["curtain_release"]["moved"] and m["opening_end"]["moved"], "moved marker found")
    check(m["walkin_start"]["now"] is None and m["walkin_start"]["moved"], "deleted marker = moved")
    d = rb.key_diff([[0, 0.0], [38, 0.5], [50, 1.0]], [[0, 0.0], [38, 0.7], [60, 1.0]])
    check(d == {"changed": [38], "only_before": [50], "only_now": [60]}, "key diff %r" % d)


def facts(**kw):
    f = {"fps": 25.0, "playback": [0, 2409], "seg_opening": [0.0, 96.36], "master_opening": [0.0, 96.36],
         "seg_p01": [96.36, 192.696], "master_p01": [96.36, 192.696],
         "music_opening": {"range_s": [0.0, 96.36]}, "cut": [0, 2409],
         "curtain": rb.curtain_timing(GC, 25.0, 24000.0, CFG["curtain"]), "rig_section_ends": {"x": 2410},
         "walk_section_ends": {"y": 2410}, "music_s": 96.336}
    f.update(kw)
    return f


@test
def drift_findings_controls():
    check(rb.drift_findings(facts()) == [], "4 Oct state: no findings %r" % rb.drift_findings(facts()))
    end = HYPOTHETICAL_GARY_END
    g = facts(playback=[0, end], seg_opening=[0.0, end / 25.0], seg_p01=[end / 25.0, end / 25.0 + 96.336],
              music_s=95.503673)
    out = rb.drift_findings(g)
    check(has(out, "MASTER_STALE"), "stale Master found")
    check(has(out, "P01_STARTS_EARLY_IN_MASTER"), "P01 early in Master found")
    check(has(out, "OPENING_MUSIC_SECTION"), "Opening music section short found")
    check(has(out, "CAMERA_CUT_ENDS_EARLY") and has(out, "PILE_ENDS_EARLY"), "cut + pile gaps found")
    check(has(out, "RIG_SECTION_ENDS") and has(out, "WALK_SECTION_ENDS"), "rig/walk section ends found")
    check(has(out, "OPENING_LONGER_THAN_SKETCH2"), "Gary's end vs sketch 2 reported")
    short = rb.drift_findings(facts(playback=[0, 2300], seg_opening=[0.0, 92.0], master_opening=[0.0, 92.0],
                                    music_opening={"range_s": [0.0, 92.0]}, music_s=95.503673,
                                    cut=[0, 2300], seg_p01=None))
    check(has(short, "SKETCH2_LONGER_THAN_OPENING"), "track longer than the Opening flagged")
    check(has(rb.drift_findings(facts(seg_opening=[0.0, 90.0])), "SHOW_OPENING_END"), "Show not following flagged")
    check(rb.drift_findings(facts(seg_opening=None))[0][1] == "SHOW_HAS_NO_OPENING_SEGMENT", "no segment = error")


@test
def planner_preview_sketch2():
    g = {"__name__": "opening_sequence_plan"}
    exec(open(os.path.join(HERE, "opening_sequence_plan.py"), encoding="utf-8").read(), g)
    analysis = g["load_json"](os.path.join(os.path.dirname(HERE), CFG["analysis"]))
    walk = os.path.join(os.path.dirname(HERE), "CodexCameraPilot", "walkin_plan.py")
    record = json.load(open(os.path.join(HERE, "opening_sequence_record.json"), encoding="utf-8"))
    last = record["last_applied_frames"]
    markers = [["OPN %s" % k, v] for k, v in last.items()]          # markers where the last APPLY left them
    pv = rb.planner_preview(g, CFG, analysis, walk, markers, last, HYPOTHETICAL_GARY_END, 25.0)
    a, k = pv["as_is"], pv["keep_gary_end"]
    check("error" not in a and "error" not in k, "both previews plan: %r" % {n: v.get("error") for n, v in pv.items()})
    check(a["frames"]["opening_end"] == 2388, "as-is: auto end = 95.504 s rounded up = frame 2388 (SHRINKS a longer "
                                              "hand-set range)")
    check(k["frames"]["opening_end"] == HYPOTHETICAL_GARY_END, "pinned end kept")
    check(a["frames"]["curtain_release"] == 1935 and k["frames"]["curtain_release"] == 1935,
          "release 77.4 s either way (auto after the last swell)")
    check(not a["conflicts"] and not a["failures"] and not k["failures"], "no conflicts/failures")
    PREVIEW.update(pv)


PREVIEW = {}


@test
def soft_path_same_as_walking_tool():
    check(rb.soft_path_from_export("(Sound=/Game/A/SW.SW,X=1)", "Sound") == "/Game/A/SW", "parser")


@test
def module_runs_nothing_offline():
    src = open(os.path.join(HERE, "opening_readback.py"), encoding="utf-8").read()
    check(src.rstrip().endswith("if unreal is not None:\n    main()"), "main gated on unreal")
    for verb in ("save_asset", "save_map", "set_editor_property", "set_playback", "set_range", "add_key", "modify()"):
        check(verb not in src, "read-only: no %s" % verb)


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:   # noqa: BLE001
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    for name, p in sorted(PREVIEW.items()):
        print("PREVIEW %s end=%d (%.2f s) release=%.3f s landed=%.3f s walk=%.2f-%.2f s swivel=%d-%d sources(end)=%s"
              % (name, p["frames"]["opening_end"], p["frames"]["opening_end"] / 25.0, p["curtain"]["release_s"],
                 p["curtain"]["landed_s"], p["walkin"]["start_s"], p["walkin"]["end_s"], p["frames"]["swivel_start"],
                 p["frames"]["swivel_end"], p["sources"]["opening_end"]))
    for f in CHECKS["failed"]:
        print("FAIL: " + f)
    print("OPENING_READBACK_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
