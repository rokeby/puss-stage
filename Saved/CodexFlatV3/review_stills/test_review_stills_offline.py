"""Offline +/- harness for review_stills_driver.py; no Unreal or Blender."""
from __future__ import annotations

import builtins
import copy
import importlib.util
import json
import pathlib
import re
import shutil
import struct
import tempfile
import types
import zlib


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("review_stills_driver_test", HERE / "review_stills_driver.py")
rs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rs)
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print(("PASS " if condition else "FAIL ") + name + ((" | " + str(detail)) if detail else ""))


def rejects(name, callback, token):
    try:
        callback()
    except Exception as exc:
        check(name, token in str(exc), str(exc))
    else:
        check(name, False, "accepted")


def fake_png(path, width=64, height=36, value=96):
    rows = [bytes([value, value, value] * width) for _ in range(height)]
    rs.write_png_rgb(path, width, height, rows)


class Store:
    pass


class FakeAdapter:
    def __init__(self, clock, wrong_world=False, census_change=False, no_pie=False):
        self.clock = clock
        self.no_pie = no_pie
        self.path = "/Wrong" if wrong_world else rs.EXPECTED_WORLD
        self.current = 111
        self.scrubs = []
        self.captures = []
        self.logs = []
        self.errors = []
        self.prepared = False
        self.restored = False
        self.ended_pie = False
        self.census_calls = 0
        self.census_change = census_change
        self.held = 0

    def world_kind(self):
        return None if self.no_pie else "game"

    def world_name(self):
        return self.path

    def log(self, message):
        self.logs.append(message)

    def log_error(self, message):
        self.errors.append(message)

    def census(self):
        self.census_calls += 1
        if self.census_change and self.census_calls > 1:
            return {"maps": ["/Game/Changed"], "content": []}
        return {"maps": [], "content": []}

    def snapshot_runtime(self):
        return {"frame": self.current, "was_playing": False, "performance_mode": False,
                "view_target": "FakeMasterCamera"}

    def restore_frame_only(self, snapshot):
        self.current = snapshot["frame"]

    def prepare_capture(self):
        self.prepared = True

    def restore_runtime(self, snapshot):
        self.current = snapshot["frame"]
        self.restored = True

    def resolve_shots(self, shots):
        rows = []
        for index, shot in enumerate(shots):
            rows.append({"target_frame": 100000 + index * 24000,
                         "time_readback": {"method": "fake_live_master", "index": index}})
        return rows

    def pause(self):
        pass

    def scrub(self, frame):
        self.current = int(frame)
        self.scrubs.append(int(frame))
        return "SUCCEEDED"

    def frame(self):
        return self.current

    def configure_camera(self, shot):
        return {"kind": shot["camera"]["kind"], "fake": True}

    def hold_camera(self):
        self.held += 1

    def release_camera(self):
        pass

    def capture(self, path, width, height):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        fake_png(path, int(width), int(height), 96)
        self.captures.append((path, int(width), int(height)))


tmp = pathlib.Path(tempfile.mkdtemp(prefix="review_stills_"))
try:
    raw = json.loads((HERE / "review_stills_args.json").read_text(encoding="utf-8"))
    cfg = rs.validate_config(raw)
    check("POS config validates eight required shots", len(cfg["shots"]) == 8)
    check("POS default ids exact", [row["id"] for row in cfg["shots"]] == raw["required_shot_ids"])
    check("POS absolute frames absent", not any({"master_frame", "absolute_frame", "frame"}.intersection(row["time"])
                                                 for row in cfg["shots"]))

    bad = copy.deepcopy(raw); bad["confirm"] = "yes"
    rejects("NEG wrong confirm", lambda: rs.validate_config(bad), "CONFIRM_REQUIRED")
    bad = copy.deepcopy(raw); bad["shots"][1]["id"] = bad["shots"][0]["id"]
    rejects("NEG duplicate shot id", lambda: rs.validate_config(bad), "DUPLICATE_SHOT_IDS")
    bad = copy.deepcopy(raw); bad["shots"][0]["time"]["master_frame"] = 123
    rejects("NEG baked absolute frame", lambda: rs.validate_config(bad), "ABSOLUTE_FRAME_FORBIDDEN")
    bad = copy.deepcopy(raw); bad["shots"] = bad["shots"][:-1]
    rejects("NEG missing required review shot", lambda: rs.validate_config(bad), "REQUIRED_SHOTS_MISSING")
    bad = copy.deepcopy(raw); bad["capture_session"] = "new_pie"
    rejects("NEG refuses to own a new PIE", lambda: rs.validate_config(bad), "CAPTURE_SESSION")

    dry = rs.create_dry_report(cfg, tmp, "HARNESS")
    check("POS DRY report readback", pathlib.Path(dry["path"]).is_file())
    cfg_run = copy.deepcopy(cfg)
    cfg_run["mode"] = "RUN"; cfg_run["confirm"] = rs.CONFIRMS["RUN"]
    cfg_run["dry_report"] = pathlib.Path(dry["path"]).name
    cfg_run["params"].update({
        "resolution": [64, 36], "probe_resolution": [16, 9], "repose_seconds": 0.05,
        "camera_hold_ticks": 1, "settle_min_seconds": 0.1, "settle_max_seconds": 1.0,
        "probe_interval_seconds": 0.05, "settle_window": 2, "file_min_bytes": 20,
        "file_stable_ticks": 1, "run_timeout_seconds": 20.0,
        "contact_columns": 4, "contact_thumb": [32, 18], "contact_gutter": 2,
    })
    # DRY digest includes params, so make a matching fast DRY report.
    dry2 = rs.create_dry_report(cfg_run, tmp, "HARNESS-FAST")
    cfg_run["dry_report"] = pathlib.Path(dry2["path"]).name
    clock = [0.0]
    fake = FakeAdapter(clock)
    store = Store()
    registry = {}

    def register(callback):
        registry["tick"] = callback
        return "HANDLE"

    def unregister(_handle):
        registry["unregistered"] = True

    run = rs.arm_run(fake, cfg_run, tmp, tmp / "Backups", tmp / "owner.json",
                     register=register, unregister=unregister, store=store,
                     clock=lambda: clock[0])
    for _index in range(1000):
        if run.get("finished"):
            break
        clock[0] += 0.05
        registry["tick"](0.05)
    check("POS RUN passed", run.get("status") == "passed", run.get("errors"))
    check("POS eight PNGs", len([shot for shot in run["shots"] if pathlib.Path(shot["path"]).is_file()]) == 8)
    check("POS later-call re-pose every shot", len(fake.scrubs) >= 2 * len(run["shots"]))
    check("POS contact sheet", pathlib.Path(run["contact_sheet"]["path"]).is_file())
    check("POS contact sheet has eight cells", len(run["contact_sheet"]["cells"]) == 8)
    check("POS runtime restored and PIE untouched", fake.restored and not fake.ended_pie)
    manifest = json.loads(pathlib.Path(run["run_dir"], rs.MANIFEST_NAME).read_text(encoding="utf-8"))
    check("POS manifest readback passed", manifest["status"] == "passed" and manifest["pie_ended_by_driver"] is False)
    check("POS exact census recorded", manifest["census_before"] == manifest["census_after"] == {"maps": [], "content": []})
    check("POS no exposure command", not any("exposure" in str(item).lower() for item in fake.captures))
    check("POS success marker", any(line.startswith("REVIEW_STILLS_OK|") for line in fake.logs))

    revert_fake = FakeAdapter([0.0])
    revert_store = Store()
    revert_registry = {}
    revert_run = rs.arm_run(
        revert_fake, cfg_negative if 'cfg_negative' in locals() else cfg_run,
        tmp, tmp / "BackupsRevert", tmp / "owner_revert.json",
        register=lambda callback: revert_registry.setdefault("tick", callback) or "HANDLE",
        unregister=lambda _handle: revert_registry.setdefault("unregistered", True),
        store=revert_store, clock=lambda: 0.0)
    getattr(revert_store, rs.ABORT_NAME)()
    check("POS REVERT restores without deleting", revert_run["status"] == "reverted" and
          revert_fake.restored and not revert_fake.ended_pie)

    cfg_negative = copy.deepcopy(cfg_run)
    cfg_negative["dry_report"] = str(pathlib.Path(dry2["path"]).resolve())
    rejects("NEG RUN without PIE", lambda: rs.arm_run(
        FakeAdapter([0.0], no_pie=True), cfg_negative, tmp / "nopie", tmp / "nopie_b", tmp / "none.json",
        store=Store()), "RUN_NEEDS_EXISTING_PIE")
    rejects("NEG RUN wrong world", lambda: rs.arm_run(
        FakeAdapter([0.0], wrong_world=True), cfg_negative, tmp / "wrong", tmp / "wrong_b", tmp / "none2.json",
        store=Store()), "WRONG_WORLD")
    owner = tmp / "active_owner.json"; owner.write_text('{"active":true}', encoding="utf-8")
    rejects("NEG active foreign owner", lambda: rs.arm_run(
        FakeAdapter([0.0]), cfg_negative, tmp / "owned", tmp / "owned_b", owner, store=Store()),
        "FOREIGN_PIE_OWNER_ACTIVE")

    # from_end_seconds (9 Oct). +/- controls.
    _tps = rs.TICKS_PER_SECOND
    check("POS from_end 2 s before end", rs.segment_target_frame_from_end(0, 100 * _tps, 2.0) == 98 * _tps, "")
    rejects("NEG from_end before segment start", lambda: rs.segment_target_frame_from_end(0, 10 * _tps, 11.0),
            "FROM_END_BEFORE_SEGMENT")
    check("POS from_end 0 clamps inside the end guard",
          rs.segment_target_frame_from_end(0, 100 * _tps, 0.0) == 100 * _tps - rs.END_GUARD_TICKS, "")

    # PIE world prefix (9 Oct RUN refusal: UEDPIE_0_ on the leaf). +/- controls.
    _ok = rs.EXPECTED_WORLD
    _dir, _leaf = _ok.rsplit("/", 1)
    check("POS PIE world UEDPIE_0_ accepted", rs.editor_world_name(_dir + "/UEDPIE_0_" + _leaf) == _ok, _ok)
    check("POS PIE world UEDPIE_12_ accepted", rs.editor_world_name(_dir + "/UEDPIE_12_" + _leaf) == _ok, _ok)
    check("POS editor world unchanged", rs.editor_world_name(_ok) == _ok, _ok)
    check("NEG other map under PIE still differs", rs.editor_world_name(_dir + "/UEDPIE_0_L_Other") != _ok, _dir)
    check("NEG prefix stripped on the leaf only",
          rs.editor_world_name("/Game/UEDPIE_0_Maps/L_InfinityStage_V1VerticalSlice") != _ok, "")
    _pie_other = FakeAdapter([0.0]); _pie_other.path = _dir + "/UEDPIE_0_L_Other"
    rejects("NEG RUN other map under PIE", lambda: rs.arm_run(
        _pie_other, cfg_negative, tmp / "pieother", tmp / "pieother_b", tmp / "none3.json", store=Store()), "WRONG_WORLD")

    # Source-level destructive and ownership controls.
    source = (HERE / "review_stills_driver.py").read_text(encoding="utf-8")
    forbidden = ("editor_request_begin_play", "editor_request_end_play", "save_package(",
                 "save_packages(", "save_dirty_packages(", "quit_editor", "auto_exposure")
    check("NEG source contains no PIE/save/exposure authority", not [token for token in forbidden if token in source],
          [token for token in forbidden if token in source])
    check("POS request uses guarded project Python", json.loads((HERE / "review_stills_request.json").read_text())
          ["arguments"]["tool_name"] == "ExecuteProjectPythonFile")

    passed = sum(1 for _name, ok, _detail in RESULTS if ok)
    failed = len(RESULTS) - passed
    report = {"tool": rs.TOOL, "passed": passed, "failed": failed,
              "results": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in RESULTS]}
    (HERE / "test_review_stills_offline_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("REVIEW_STILLS_OFFLINE_HARNESS|passed=%d|failed=%d" % (passed, failed))
    if failed:
        raise SystemExit(1)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

