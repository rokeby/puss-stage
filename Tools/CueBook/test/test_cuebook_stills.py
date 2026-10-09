"""Offline positive/negative harness for cb2 Cue Book stills."""
from __future__ import annotations

import csv
import importlib.util
import json
import pathlib
import tempfile
import types

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[3]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


segment_map = load(ROOT / "Tools" / "CueBook" / "segment_map.py", "test_segment_map")
driver = load(ROOT / "Tools" / "CueBook" / "unreal" / "cuebook_stills_driver.py", "test_stills_driver")
publisher = load(ROOT / "Tools" / "CueBook" / "publish_stills.py", "test_stills_publisher")
scene_stills = load(ROOT / "Saved" / "CodexConductor" / "scene_stills.py", "test_scene_stills")


checks = []


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def refused(call, exception, label):
    try:
        call()
    except exception:
        checks.append(label)
        return
    raise AssertionError(label + " did not refuse")


class FakeTransport:
    def __init__(self, spans):
        self.spans = spans

    def segment_span(self, key):
        return self.spans[key]


class MotionAdapter:
    def __init__(self, frame, pose):
        self.frame, self.pose = frame, pose

    def world_kind(self):
        return "game"

    def transport_frame(self):
        return self.frame

    def camera_pose(self, _aspect, _fallback):
        return self.pose

    def log(self, _message):
        pass


def motion_drift_checks():
    pose = {"loc": [1.0, 2.0, 3.0], "rot": {"yaw": 4.0, "pitch": 5.0, "roll": 6.0},
            "fov_deg": 60.0, "aspect": 16.0 / 9.0}
    params = dict(scene_stills.DEFAULTS, accept_motion_drift=True, drift_tolerance=4.0)

    def run_probe(after_pose):
        still = {"i": 0, "fraction": 0.5, "target_frame": 100, "master_frame_at_capture": 100,
                 "master_frame_after_file": 100, "pose": pose, "settle": {"luma": 36.9}, "phase": "post_probe"}
        still.update(bytes=2000, path="still.png")
        run = {"run_id": "PSTILLS-TEST", "run_dir": ".", "stills": [still]}
        machine = scene_stills.StillsMachine(MotionAdapter(100, after_pose), run, params)
        machine.st.update(phase="post_probe", pending={"path": "unused", "t": 0.0})
        machine._read_pending = lambda _now: 39.3
        machine.step(1.0)
        return still, machine.st["gate_failures"]

    accepted, gates = run_probe(pose)
    check(accepted["motion_drift"] == 2.4 and not gates,
          "motion-only post-capture drift is accepted and recorded")
    moved = dict(pose, loc=[1.0, 2.0, 4.0])
    rejected, gates = run_probe(moved)
    check("motion_drift" not in rejected and any("camera_unchanged=False" in reason for reason in gates),
          "negative changed camera pose still rejects post-capture drift")


class QueueAdapter:
    def __init__(self, restore_ok=True):
        self.frame, self.restore_ok, self.restore_calls = 77, restore_ok, 0

    def world_kind(self):
        return "game"

    def world_name(self):
        return "FakePIE"

    def census(self):
        return {"maps": [], "content": []}

    def transport_frame(self):
        return self.frame

    def transport_scrub(self, frame):
        self.restore_calls += 1
        self.frame = int(frame) if self.restore_ok else int(frame) + 1
        return "SUCCEEDED"

    def passage_segment(self, label):
        return {"Scene 3": (100, 10100), "Scene 4": (12000, 22000)}[label]


def queue_driver_run(root, restore_ok=True):
    cue_path = root / "cuebook.json"
    cue_path.write_text(json.dumps({"cues": [
        {"key": "R1", "ord": 1, "videoCue": "First", "at": ""},
        {"key": "R2", "ord": 2, "videoCue": "Second", "at": ""},
    ]}), encoding="utf-8")
    adapter = QueueAdapter(restore_ok)
    callbacks, logs = [], []
    unreal = types.SimpleNamespace(
        register_slate_post_tick_callback=lambda callback: callbacks.append(callback) or len(callbacks),
        unregister_slate_post_tick_callback=lambda _handle: None,
        log=logs.append, log_error=logs.append)
    arm_count = {"value": 0}

    def write_verified(path, data):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, default=str), encoding="utf-8")

    def arm(forced, _passage, fractions, label=None, params=None, out_root=None, **_kwargs):
        arm_count["value"] += 1
        child_dir = pathlib.Path(out_root) / ("child-" + label)
        child_dir.mkdir(parents=True)
        target = scene_stills.fraction_to_frame(*forced.span, fractions[0])
        if arm_count["value"] == 1:
            saved = {"status": "failed", "stills": [], "gate_failures": ["camera moved"]}
        else:
            saved = {"status": "passed", "finished_utc": "2026-10-09T12:00:00+00:00", "stills": [{
                "path": (child_dir / "still.png").as_posix(), "master_frame_at_capture": target,
                "motion_drift": 4.3}]}
        write_verified(child_dir / "child.json", saved)
        return {"run_dir": child_dir.as_posix(), "status": saved["status"], "finished": True}

    scene_api = types.SimpleNamespace(
        END_GUARD_TICKS=1, DISPLAY_FPS=24, TICKS_PER_SECOND=24,
        MANIFEST_NAME="child.json", make_pie_adapter=lambda _unreal: adapter,
        owner_active=lambda _path: False, armed_handles=lambda _store: [],
        passage_label=lambda key: (int(key[1:]), "Scene %d" % int(key[1:])),
        fraction_to_frame=scene_stills.fraction_to_frame, write_verified=write_verified,
        scrub_ok=scene_stills.scrub_ok, arm=arm)
    mapping_api = types.SimpleNamespace(
        load_segment_map=lambda _path: {},
        map_segment_names=lambda _names, _config: [{"name": "First", "key": "S3"},
                                                    {"name": "Second", "key": "S4"}])
    original_load = driver.load_module
    driver.load_module = lambda _path, name: scene_api if name == "cuebook_scene_stills" else mapping_api
    try:
        run = driver.start_driver(unreal, root, {"mode": "APPLY", "confirm": driver.APPLY_CONFIRM,
                                                 "cuebook_json": cue_path.as_posix(),
                                                 "drift_tolerance_by_segment": {"S3": 4.0}})
        for _ in range(8):
            if run["_state"]["finished"]:
                break
            callbacks[0]()
        return run, adapter, logs
    finally:
        driver.load_module = original_load
        for name in (driver.DRIVER_HANDLE, driver.DRIVER_STATE):
            if hasattr(__import__("builtins"), name):
                delattr(__import__("builtins"), name)


def queue_driver_checks():
    with tempfile.TemporaryDirectory(prefix="cuebook-stills-queue-") as folder:
        run, adapter, logs = queue_driver_run(pathlib.Path(folder))
        check(run["status"] == "partial" and run["skipped"][0]["segment"] == "S3" and
              [row["segment_key"] for row in run["captures"]] == ["S4"],
              "failing segment is recorded as skipped and the next segment is captured")
        check(run["captures"][0]["motion_drift"] == 4.3,
              "accepted child motion_drift is copied into the Cue Book manifest")
        check(adapter.restore_calls == 1 and run["final_frame"] == run["original_frame"] and
              any(message.startswith("CUEBOOK_STILLS_PARTIAL") for message in logs),
              "partial completion restores the starting frame and emits a partial marker")
    with tempfile.TemporaryDirectory(prefix="cuebook-stills-restore-fail-") as folder:
        run, adapter, _logs = queue_driver_run(pathlib.Path(folder), restore_ok=False)
        check(adapter.restore_calls == 1 and run["status"] == "failed" and
              "frame_restore_failed" in run["problems"],
              "negative failed frame restore fails the whole run")


def mapping_checks():
    config = segment_map.load_segment_map(ROOT / "Tools" / "CueBook" / "segment_map.json")
    with open(ROOT / "Docs" / "CueSheet" / "working.csv", encoding="utf-8", newline="") as handle:
        working = list(csv.DictReader(handle))
    current_names = ["Prologue"] + [row["Video Cue"].strip().splitlines()[0] for row in working
                                     if row["Video Cue"].strip()]
    check(current_names == config["known_segments"], "canonical map names match working.csv in page order")
    rows = segment_map.map_segment_names(current_names, config)
    check(len(rows) == 19, "mapping covers the current 19 Cue Book segment names")
    check(segment_map.unmapped(rows) == ["Prologue"], "pre-show Prologue is explicitly reported unmapped")
    check([row["key"] for row in rows if row["name"] == "Transition"] == ["I1", "I2", "I3", "I4"],
          "ordered Transition rules produce I1-I4 without inventing I5")
    by_name = {row["name"]: row["key"] for row in rows if row["name"] != "Transition"}
    check(by_name["Passage 6"] == "P06" and by_name["S1 Animals"] == "S1" and
          by_name["Scene 5: Mountains"] == "S5" and by_name["Ending"] == "Closing",
          "passage scene opening and ending rules resolve current names")
    custom = {"schema_version": 1, "closing_key": "Closing",
              "overrides": {"Scene 2: Shrine": "S99", "Transition#2": "I5"}}
    got = segment_map.map_segment_names(["Scene 2: Shrine", "Transition", "Transition"], custom)
    check([row["key"] for row in got] == ["S99", "I1", "I5"], "explicit name and occurrence overrides win")
    unknown = segment_map.map_segment_names(["A plausible but unknown scene"], config)
    check(unknown[0]["key"] is None and unknown[0]["reason"] == "unmapped",
          "negative unknown name is reported and never guessed")
    check((ROOT / "Tools" / "CueBook" / "segment_map.json").read_bytes() ==
          (ROOT / "Tools" / "CueBook" / "site" / "segment_map.json").read_bytes(),
          "site ships the canonical segment map byte-for-byte")


def driver_checks():
    config = segment_map.load_segment_map(ROOT / "Tools" / "CueBook" / "segment_map.json")
    cues = [
        {"key": "R0001", "ord": 10, "videoCue": "", "at": ""},
        {"key": "R0002", "ord": 20, "videoCue": "Curtain opening to fully lit stage/passage", "at": ""},
        {"key": "R0003", "ord": 30, "videoCue": "Passage 1", "at": "2.0"},
        {"key": "R0004", "ord": 40, "videoCue": "", "at": "3.0"},
        {"key": "R0005", "ord": 50, "videoCue": "S1 Animals", "at": "1.0"},
        {"key": "R0006", "ord": 60, "videoCue": "Transition", "at": "not-a-time"},
    ]
    spans = {"Opening": (0, 240000), "P01": (300000, 540000),
             "S1": (600000, 840000), "I1": (900000, 1140000)}
    plan = driver.build_capture_plan(FakeTransport(spans), segment_map, scene_stills, cues, config,
                                     {"fraction": 0.5, "transition_fraction": 0.3, "max_cue_stills": 2})
    check(plan["segment_count"] == 4 and plan["cue_count"] == 2,
          "fake transport plans one still per mapped segment and enforces cue cap")
    transition = next(item for item in plan["items"] if item["kind"] == "segment" and item["segment_key"] == "I1")
    check(transition["fraction"] == 0.3 and transition["target_frame"] == 972000,
          "transition default fraction maps through the proven frame helper")
    cues_by_key = {item["cue_key"]: item for item in plan["items"] if item["kind"] == "cue"}
    check(cues_by_key["R0003"]["target_frame"] == 348000 and cues_by_key["R0004"]["target_frame"] == 372000,
          "cue At seconds convert to exact absolute Master frames")
    check(any(row.get("cue_key") == "R0005" and row["reason"] == "max_cue_stills" for row in plan["skipped"]) and
          any(row.get("cue_key") == "R0006" and row["reason"] == "invalid_at" for row in plan["skipped"]),
          "negative invalid and over-cap cues are reported rather than captured")
    source = (ROOT / "Tools" / "CueBook" / "unreal" / "cuebook_stills_driver.py").read_text(encoding="utf-8")
    check("scene_api.arm(" in source and "scene_stills.py" in source,
          "driver imports and arms the Conductor capture implementation")
    check(all(token not in source for token in ("save_asset(", "save_all", "end_play_map", "request_exit")),
          "driver source has no save end-PIE or quit route")


def publisher_checks():
    with tempfile.TemporaryDirectory(prefix="cuebook-stills-") as folder:
        root = pathlib.Path(folder)
        run, site, backups = root / "run", root / "site", root / "Backups"
        (run / "captures").mkdir(parents=True)
        (site / "stills").mkdir(parents=True)
        first, second = run / "captures" / "segment.png", run / "captures" / "cue.png"
        Image.new("RGB", (1600, 900), (120, 30, 20)).save(first)
        Image.new("RGB", (1920, 1080), (20, 80, 140)).save(second)
        manifest = {"run_id": "CBSTILLS-TEST", "status": "partial",
                    "skipped": [{"segment": "S3", "status": "skipped", "reason": "camera moved"}],
                    "captures": [
            {"kind": "segment", "segment_key": "P01", "unreal_id": "P01", "master_frame": 12000,
             "captured": "2026-10-09T12:00:00+00:00", "path": first.as_posix()},
            {"kind": "cue", "cue_key": "R0042", "segment_key": "P02", "unreal_id": "P02",
             "master_frame": 24000, "captured": "2026-10-09T12:01:00+00:00", "path": second.as_posix()},
        ]}
        (run / publisher.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        old_jpeg = b"existing-still-is-preserved"
        (site / "stills" / "P01.jpg").write_bytes(old_jpeg)
        skipped_jpeg = b"existing-skipped-still-is-preserved"
        (site / "stills" / "S3.jpg").write_bytes(skipped_jpeg)
        old_manifest = {"old": True}
        (site / "stills.json").write_text(json.dumps(old_manifest), encoding="utf-8")
        plan = publisher.build_publish_plan(run, site)
        check((site / "stills" / "P01.jpg").read_bytes() == old_jpeg and not backups.exists(),
              "publish DRY planning changes no files")
        refused(lambda: publisher.apply_publish(plan, backups, "WRONG"), publisher.PublishRefused,
                "negative APPLY refuses without exact confirm")
        record, published = publisher.apply_publish(plan, backups, publisher.APPLY_CONFIRM)
        with Image.open(site / "stills" / "P01.jpg") as image:
            check(image.format == "JPEG" and image.size == (1280, 720),
                  "APPLY writes a read-back 1280-pixel JPEG")
        check(published["segments"]["P01"]["master_frame"] == 12000 and
               published["cues"]["R0042"]["file"] == "stills/cue/R0042.jpg" and
               json.loads((site / "stills.json").read_text(encoding="utf-8")) == published,
               "APPLY manifest reads back with segment and cue metadata")
        check(published["skipped"] == manifest["skipped"] and
              (site / "stills" / "S3.jpg").read_bytes() == skipped_jpeg,
              "partial publish lists skipped segments and preserves their existing stills")
        backup = pathlib.Path(record["backup_dir"])
        check((backup / "site" / "stills" / "P01.jpg").read_bytes() == old_jpeg and
              json.loads((backup / "site" / "stills.json").read_text(encoding="utf-8")) == old_manifest,
              "replacement moves every existing target into PreCueBookStills backup")
        refused(lambda: publisher.revert_publish(backup, backups, "WRONG"), publisher.PublishRefused,
                "negative REVERT refuses without exact confirm")
        reverted = publisher.revert_publish(backup, backups, publisher.REVERT_CONFIRM)
        revert_backup = backups / ("PreCueBookStillsRevert-%s" % reverted["run_id"])
        check((site / "stills" / "P01.jpg").read_bytes() == old_jpeg and
              json.loads((site / "stills.json").read_text(encoding="utf-8")) == old_manifest,
              "REVERT restores the pre-publish still and manifest")
        check(not (site / "stills" / "cue" / "R0042.jpg").exists() and
              (revert_backup / "published" / "stills" / "cue" / "R0042.jpg").is_file(),
              "REVERT moves new output to a recovery backup instead of deleting it")
        check(record["census_before"] == record["census_after"] == publisher.EMPTY_CENSUS and
              record["saved_packages"] == [], "offline publisher records exact empty package census and no saves")


def page_checks():
    page = (ROOT / "Tools" / "CueBook" / "site" / "index.html").read_text(encoding="utf-8")
    check("loadStillsManifest" in page and "fallbackStill" in page and "stillsManifest.cues[c.key]" in page,
          "page loads manifest with legacy-table fallback and cue thumbnails")


def main():
    mapping_checks()
    driver_checks()
    motion_drift_checks()
    queue_driver_checks()
    publisher_checks()
    page_checks()
    print("CUEBOOK_STILLS_HARNESS_OK %d/%d" % (len(checks), len(checks)))
    for label in checks:
        print("PASS " + label)


if __name__ == "__main__":
    main()
