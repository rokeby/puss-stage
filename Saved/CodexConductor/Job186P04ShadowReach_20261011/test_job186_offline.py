"""Offline positive/negative controls for Job 186. No Unreal import required."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = load("job186_tag_test", "job186_p04_tag_repair.py")
S = load("job186_shadow_test", "job186_p04_shadow_reach.py")
G = load("job186_gate_test", "job186_p04_perf_gate.py")

passed = []
failed = []


def check(name, fn):
    try:
        fn()
        passed.append(name)
    except Exception as exc:
        failed.append((name, "%s: %s" % (type(exc).__name__, exc)))


def rejects(name, fn, needle):
    def run():
        try:
            fn()
        except Exception as exc:
            if needle not in str(exc):
                raise AssertionError("wanted %r in %r" % (needle, exc))
            return
        raise AssertionError("did not reject")
    check(name, run)


GUID_A = "A" * 32
GUID_B = "B" * 32
TAG = T.identity_tag(GUID_A, GUID_B)

check("positive: identity tag round trips", lambda: (_ for _ in ()).throw(
    AssertionError()) if T.parse_identity_tag_text(TAG) != (GUID_A, GUID_B) else None)
check("positive: untagged P04 light plans repair", lambda: (_ for _ in ()).throw(
    AssertionError()) if not T.plan_from_rows([TAG], [{"label": "lamp", "path": "x", "identity": None,
                                                       "has_light": True}])["needs_repair"] else None)
check("positive: exact Show identity is a no-op", lambda: T.validate_readback(
    [TAG], [{"label": "lamp", "path": "x", "identity": (GUID_A, GUID_B), "has_light": True}]))
check("positive: non-light managed prop does not enter light identity set", lambda: T.validate_readback(
    [TAG], [{"label": "lamp", "path": "x", "identity": (GUID_A, GUID_B), "has_light": True},
            {"label": "prop", "path": "y", "identity": None, "has_light": False}]))
check("positive: APPLY args require reviewed hash and count", lambda: T.check_args({
    "mode": "APPLY", "confirm": T.CONFIRM["APPLY"], "expected_plan_sha256": "a" * 64,
    "expected_light_count": 128}))
check("positive: restore args are separately confirmed", lambda: T.check_args({
    "mode": "REVERT", "confirm": T.CONFIRM["REVERT"]}))

rejects("negative: malformed managed identity rejected", lambda: T.managed_identity_tag_text(
    T.TAG_PREFIX + "bad|tag"), "MALFORMED_IDENTITY_TAG")
rejects("negative: stale actor identity rejected", lambda: T.validate_readback(
    [TAG], [{"label": "lamp", "path": "x", "identity": ("C" * 32, GUID_B), "has_light": True}]),
        "TAG_READBACK_MISMATCH")
rejects("negative: duplicate actor identity rejected", lambda: T.validate_readback(
    [TAG], [{"label": "a", "path": "x", "identity": (GUID_A, GUID_B), "has_light": True},
            {"label": "b", "path": "y", "identity": (GUID_A, GUID_B), "has_light": True}]),
        "duplicate_tags")
rejects("negative: missing expected Show light rejected", lambda: T.validate_readback([TAG], []),
        "TAG_READBACK_MISMATCH")
rejects("negative: APPLY confirmation exact", lambda: T.check_args({
    "mode": "APPLY", "confirm": "yes", "expected_plan_sha256": "a" * 64,
    "expected_light_count": 1}), "CONFIRM_MISSING")
rejects("negative: APPLY hash mandatory", lambda: T.check_args({
    "mode": "APPLY", "confirm": T.CONFIRM["APPLY"], "expected_plan_sha256": "",
    "expected_light_count": 1}), "EXPECTED_PLAN_SHA256_REQUIRED")


def geometry_control():
    stations = {"P04": [
        {"id": "1", "ordinal": 1, "center": [0, 0, 0], "left": [0, -700, 0], "right": [0, 700, 0]},
        {"id": "2", "ordinal": 2, "center": [600, 0, 0], "left": [600, -700, 0], "right": [600, 700, 0]},
        {"id": "3", "ordinal": 3, "center": [1200, 0, 0], "left": [1200, -700, 0], "right": [1200, 700, 0]},
    ]}
    result = S.passage_geometry(stations, dict(S.DEFAULTS, passages=["P04"]))["P04"]
    assert result["wing_pitch_cm"] == 600.0
    assert result["two_wing_reach_cm"] == 1200.0
    assert result["across_gap_cm"] == 1400.0
    assert result["chosen_radius_cm"] == 1500.0


check("positive: P04 middle-point rule is max(2 pitches,gap)+1m", geometry_control)
check("positive: adapter scope is P04 only", lambda: (_ for _ in ()).throw(
    AssertionError()) if S.PASSAGES != ("P04",) else None)
rejects("negative: adapter rejects P01 scope", lambda: S.check_args({
    "mode": "DRY", "params": {"passages": ["P01"]}}), "PASSAGES_INVALID")

before = {"P04:10": 30.0, "P04:50": 32.0, "P04:90": 34.0}
check("positive: three-spot perf gate passes at threshold", lambda: (_ for _ in ()).throw(
    AssertionError()) if not S.evaluate_perf(before, {"P04:10": 33.0, "P04:50": 32.0,
                                                      "P04:90": 34.0}, ["P04"], 0.10)["pass"] else None)
check("positive: perf regression requests auto-revert", lambda: (_ for _ in ()).throw(
    AssertionError()) if not S.evaluate_perf(before, {"P04:10": 34.0, "P04:50": 32.0,
                                                      "P04:90": 34.0}, ["P04"], 0.10)["auto_revert"] else None)
rejects("negative: perf requires all three spots", lambda: S.evaluate_perf(
    {"P04:10": 30.0}, {"P04:10": 30.0}, ["P04"], 0.10), "PERF_NEEDS_THREE_SPOTS")


def sample_controls():
    with tempfile.TemporaryDirectory() as root:
        paths = []
        for label, value in (("P04:10", 30), ("P04:50", 31), ("P04:90", 32)):
            path = os.path.join(root, label.replace(":", "_") + ".json")
            json.dump({"label": label, "p95_ms": value}, open(path, "w", encoding="utf-8"))
            paths.append(path)
        assert len(G.load_samples(paths, root)) == 3


check("positive: perf gate loads three P04 probe reports", sample_controls)


def bad_sample():
    with tempfile.TemporaryDirectory() as root:
        path = os.path.join(root, "bad.json")
        json.dump({"label": "P03:50", "p95_ms": 30}, open(path, "w", encoding="utf-8"))
        G.load_samples([path], root)


rejects("negative: perf gate rejects non-P04 report", bad_sample, "NON_P04_SAMPLE")


def source_contracts():
    tag_source = open(os.path.join(HERE, "job186_p04_tag_repair.py"), encoding="utf-8").read()
    restore_source = open(os.path.join(HERE, "job186_restore_backup.ps1"), encoding="utf-8").read()
    assert ".materialize_attachments()" in tag_source
    assert "actor.tags" in tag_source and ".tags.append" not in tag_source and ".tags =" not in tag_source
    assert "backup_packages(run_id)" in tag_source and "save_current_level()" in tag_source
    assert "SHOW_CHANGED_ON_DISK" in tag_source and "saved_readback_verified" in tag_source
    assert "Get-Process -Name UnrealEditor" in restore_source
    assert "PreJob186P04TagRestore" in restore_source and "Get-FileHash" in restore_source
    assert "Remove-Item" not in restore_source


check("positive: Show materializer, backup, readback and safe restore contracts present", source_contracts)

result = {"passed": len(passed), "failed": len(failed), "positive_controls": 12,
          "negative_controls": 9, "passes": passed, "failures": failed}
with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
with open(os.path.join(HERE, "harness_result.txt"), "w", encoding="utf-8") as handle:
    handle.write("JOB186_OFFLINE_HARNESS %d/%d\n" % (len(passed), len(passed) + len(failed)))
    for name in passed:
        handle.write("PASS " + name + "\n")
    for name, error in failed:
        handle.write("FAIL %s :: %s\n" % (name, error))
print("JOB186_OFFLINE_HARNESS %d/%d" % (len(passed), len(passed) + len(failed)))
for name, error in failed:
    print("FAIL", name, error)
raise SystemExit(1 if failed else 0)
