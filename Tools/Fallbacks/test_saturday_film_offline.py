"""Offline +/- harness for the Saturday unattended Scene filming workflow."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import saturday_film as film  # noqa: E402

post_spec = importlib.util.spec_from_file_location(
    "mrq_post", PROJECT / "Saved" / "CodexConductor" / "MRQ" / "mrq_post.py")
post = importlib.util.module_from_spec(post_spec)
post_spec.loader.exec_module(post)

passed = []


def case(name, polarity, fn):
    try:
        fn()
        passed.append((name, polarity))
        print("PASS|%s|%s" % (polarity, name))
    except Exception as exc:  # noqa: BLE001
        print("FAIL|%s|%s|%r" % (polarity, name, exc))


def require(value, message):
    if not value:
        raise AssertionError(message)


def fixture():
    built = {"scenes": {}, "built": []}
    for scene in film.SCENES:
        a, b = scene * 100, scene * 100 + 20
        built["scenes"][str(scene)] = {"master_range": [a, b]}
        built["built"].append({"name": "S%d_P_v01" % scene, "scene": scene, "tier": "P", "version": "v01",
                               "keep_range": [a, b], "render_range": [a - 2, b], "output_dir": "x", "wav": True})
        built["built"].append({"name": "S%d_C_v01" % scene, "scene": scene, "tier": "C", "version": "v01",
                               "keep_range": [a, b], "render_range": [a - 2, b], "output_dir": "x", "wav": False})
    return built


case("complete six-scene two-tier matrix", "POSITIVE",
     lambda: require(not film.validate_built_matrix(fixture()), "matrix refused"))


def missing_scene():
    data = fixture()
    del data["scenes"]["4"]
    require("MISSING_SCENE|S4" in film.validate_built_matrix(data), "missing Scene not caught")


case("missing Scene is refused", "NEGATIVE", missing_scene)


def resume_positive():
    data, checkpoint = fixture(), {"deliveries": {}}
    key = film.delivery_key(1, "P")
    for stage in ("render:S1_P_v01", "encode", "qc", "promote"):
        film.mark(checkpoint, key, stage)
    require(film.planned_actions(data, checkpoint, 1, "P", "v01") == [], "finished work was not skipped")


case("resume skips finished delivery", "POSITIVE", resume_positive)


def resume_negative():
    actions = film.planned_actions(fixture(), {"deliveries": {}}, 1, "P", "v01")
    require([a for a, _ in actions] == ["render", "encode", "qc", "promote"], "unfinished stages disappeared")


case("resume retains unfinished stages", "NEGATIVE", resume_negative)


def qc_pass_promotes():
    calls, checkpoint = [], {"deliveries": {}, "failures": []}
    def invoke(action, *_):
        calls.append(action)
        return True, {"ok": True}
    ok = film.execute_delivery(fixture(), checkpoint, 1, "P", "v01", invoke, lambda _: None)
    require(ok and calls[-1] == "promote", "passing QC did not reach promotion")


case("hard-QC pass promotes", "POSITIVE", qc_pass_promotes)


def qc_fail_blocks_promote():
    calls, checkpoint = [], {"deliveries": {}, "failures": []}
    def invoke(action, *_):
        calls.append(action)
        return (False, {"hard_fail": ["FRAME_COUNT"]}) if action == "qc" else (True, {})
    ok = film.execute_delivery(fixture(), checkpoint, 1, "P", "v01", invoke, lambda _: None)
    require(not ok and "promote" not in calls, "QC failure promoted")


case("QC fail does not promote", "NEGATIVE", qc_fail_blocks_promote)


GOOD_REGISTRY = {"schema": 1, "scenes": {"S1": {"video": "S1/a.mp4", "audio": "S1/a.wav",
                                                      "frames": 250, "seconds": 10.0, "fps": 25,
                                                      "tier": "P", "version": "v01", "sha256": {}}}}

case("schema matches CD4 parser contract", "POSITIVE",
     lambda: require(not film.cd4_schema_errors(GOOD_REGISTRY) and not post.validate_cd4_registry(GOOD_REGISTRY),
                     "valid CD4 schema refused"))


def bad_schema():
    bad = copy.deepcopy(GOOD_REGISTRY)
    del bad["scenes"]["S1"]["video"]
    require(film.cd4_schema_errors(bad) and post.validate_cd4_registry(bad), "missing video accepted")


case("schema rejects missing video", "NEGATIVE", bad_schema)


def merge_preserves():
    s2 = dict(GOOD_REGISTRY["scenes"]["S1"], video="S2/b.mp4")
    merged = post.merge_registry(GOOD_REGISTRY, "S2", s2)
    require(set(merged["scenes"]) == {"S1", "S2"}, "merge discarded a Scene")


case("promotion merge preserves prior Scenes", "POSITIVE", merge_preserves)


def freeze_negative():
    text = "freeze_start: 2.000\nfreeze_end: 5.500\nfreeze_duration: 3.500\n"
    rows = post.parse_freezedetect(text)
    require(len(rows) == 1 and rows[0]["duration_s"] == 3.5, "freeze stretch not detected")


case("frozen stretch is detected", "NEGATIVE", freeze_negative)


neg = sum(1 for _, p in passed if p == "NEGATIVE")
pos = sum(1 for _, p in passed if p == "POSITIVE")
total = 10
if len(passed) != total or neg != 5 or pos != 5:
    print("SATFILM_HARNESS_FAILED|%d/%d|negative=%d/5|positive=%d/5" % (len(passed), total, neg, pos))
    raise SystemExit(1)
print("SATFILM_HARNESS_OK|10/10|negative=5/5|positive=5/5")
