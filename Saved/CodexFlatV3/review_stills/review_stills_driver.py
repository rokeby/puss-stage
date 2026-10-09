"""Q6 Gary review-stills driver (offline-authored; never starts or ends PIE).

DRY validates the shot list and writes a digest-bound plan. RUN requires that
plan and one already-running PIE session, resolves every time from the live
Master transport, captures all shots in that same session, and restores the
runtime view/frame it borrowed. REVERT only aborts an armed run and restores
runtime state; it never deletes output.

Precedents deliberately retained:
* passage_stills.py: master scrub, later-call re-pose, stable-file gate, exact
  dirty-package census, no exposure override, and never ending foreign PIE.
* s3_beach_pie_stills_driver.py: one callback for a multi-shot set and a held
  runtime camera view target.
* hp_test_pie_still.py: borrow/restore a PIE camera instead of spawning one.

Markers: REVIEW_STILLS_DRY_OK, REVIEW_STILLS_ARMED, REVIEW_STILLS_SHOT,
REVIEW_STILLS_OK, REVIEW_STILLS_FAILED, REVIEW_STILLS_REVERTED.
"""
from __future__ import annotations

import builtins
import copy
import datetime
import hashlib
import json
import math
import os
import pathlib
import re
import struct
import time
import traceback
import zlib


TOOL = "review_stills"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HANDLE_NAME = "PUSS_REVIEW_STILLS_HANDLE"
STATE_NAME = "PUSS_REVIEW_STILLS_STATE"
ABORT_NAME = "PUSS_REVIEW_STILLS_ABORT"
MANIFEST_NAME = "review_stills_manifest.json"
CONTACT_NAME = "review_stills_contact_sheet.png"
OWNER_REL = pathlib.Path("CodexConductor/pie_recording_owner.json")
MODES = ("DRY", "RUN", "REVERT")
CONFIRMS = {mode: "%s REVIEW STILLS" % mode for mode in MODES}
TIME_KINDS = ("segment_offset", "panel_pass", "panel_mid_motion")
CAMERA_KINDS = ("master", "subject_close", "actor_camera")
TICKS_PER_SECOND = 24000
DISPLAY_FPS = 24
END_GUARD_TICKS = TICKS_PER_SECOND // DISPLAY_FPS

DEFAULT_PARAMS = {
    "resolution": [1600, 900],
    "probe_resolution": [256, 144],
    "repose_seconds": 1.0,
    "camera_hold_ticks": 24,
    "settle_min_seconds": 2.0,
    "settle_max_seconds": 10.0,
    "probe_interval_seconds": 0.5,
    "settle_window": 3,
    "settle_abs_luma": 2.0,
    "settle_rel_luma": 0.03,
    "file_timeout_seconds": 45.0,
    "file_min_bytes": 1000,
    "file_stable_ticks": 4,
    "run_timeout_seconds": 480.0,
    "frame_tolerance_ticks": 1,
    "contact_columns": 4,
    "contact_thumb": [400, 225],
    "contact_gutter": 8,
}


class ReviewError(RuntimeError):
    pass


def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def write_verified(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=1, sort_keys=True, ensure_ascii=True, default=str)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
    read = json.loads(path.read_text(encoding="utf-8"))
    if read != json.loads(text):
        raise ReviewError("JSON_READBACK|%s" % path.as_posix())
    return path


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_id(value):
    text = re.sub(r"[^a-z0-9_-]+", "_", str(value).strip().lower()).strip("_")
    if not text or len(text) > 64:
        raise ReviewError("BAD_SHOT_ID|%r" % value)
    return text


def plan_payload(config):
    """Fields that must match between DRY and RUN."""
    return {
        "profile": str(config.get("profile", "custom")),
        "capture_session": str(config.get("capture_session", "existing_pie")),
        "expected_world": str(config.get("expected_world", EXPECTED_WORLD)),
        "params": config["params"],
        "shots": config["shots"],
    }


def plan_digest(config):
    return hashlib.sha256(canonical_json(plan_payload(config)).encode("utf-8")).hexdigest()


def _finite_number(value, field, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ReviewError("BAD_NUMBER|%s=%r" % (field, value))
    value = float(value)
    if minimum is not None and value < minimum:
        raise ReviewError("BAD_NUMBER|%s=%r below %r" % (field, value, minimum))
    if maximum is not None and value > maximum:
        raise ReviewError("BAD_NUMBER|%s=%r above %r" % (field, value, maximum))
    return value


def validate_config(raw, require_confirm=True):
    if not isinstance(raw, dict):
        raise ReviewError("ARGS_NOT_OBJECT")
    config = copy.deepcopy(raw)
    mode = str(config.get("mode", "")).upper()
    if mode not in MODES:
        raise ReviewError("BAD_MODE|%r" % mode)
    if require_confirm and config.get("confirm") != CONFIRMS[mode]:
        raise ReviewError("CONFIRM_REQUIRED|expected=%s" % CONFIRMS[mode])
    if mode == "REVERT":
        return config
    if config.get("capture_session", "existing_pie") != "existing_pie":
        raise ReviewError("CAPTURE_SESSION|only existing_pie is supported for timed Master shots")
    params = dict(DEFAULT_PARAMS)
    params.update(config.get("params") or {})
    for field in ("resolution", "probe_resolution", "contact_thumb"):
        value = params.get(field)
        if not isinstance(value, list) or len(value) != 2:
            raise ReviewError("BAD_SIZE|%s=%r" % (field, value))
        params[field] = [int(_finite_number(value[0], field + ".w", 1)),
                         int(_finite_number(value[1], field + ".h", 1))]
    for field in ("repose_seconds", "settle_min_seconds", "settle_max_seconds",
                  "probe_interval_seconds", "file_timeout_seconds", "run_timeout_seconds"):
        params[field] = _finite_number(params[field], field, 0.0)
    for field in ("camera_hold_ticks", "settle_window", "file_min_bytes", "file_stable_ticks",
                  "frame_tolerance_ticks", "contact_columns", "contact_gutter"):
        params[field] = int(_finite_number(params[field], field, 0))
    if params["settle_max_seconds"] < params["settle_min_seconds"]:
        raise ReviewError("SETTLE_RANGE")
    shots = config.get("shots")
    if not isinstance(shots, list) or not shots or len(shots) > 32:
        raise ReviewError("BAD_SHOT_COUNT|%r" % (None if shots is None else len(shots)))
    ids = []
    normalized = []
    forbidden_time_fields = {"master_frame", "absolute_frame", "frame"}
    for index, original in enumerate(shots):
        if not isinstance(original, dict):
            raise ReviewError("SHOT_NOT_OBJECT|index=%d" % index)
        shot = copy.deepcopy(original)
        shot["id"] = clean_id(shot.get("id"))
        ids.append(shot["id"])
        timing = shot.get("time")
        if not isinstance(timing, dict) or timing.get("kind") not in TIME_KINDS:
            raise ReviewError("BAD_TIME|shot=%s" % shot["id"])
        baked = forbidden_time_fields.intersection(timing)
        if baked:
            raise ReviewError("ABSOLUTE_FRAME_FORBIDDEN|shot=%s|fields=%s" % (shot["id"], sorted(baked)))
        passage = timing.get("passage")
        if timing["kind"].startswith("panel_"):
            if not re.fullmatch(r"P\d{2}", str(passage or "")) or not timing.get("cue_label"):
                raise ReviewError("PANEL_TIME_NEEDS_PASSAGE_AND_CUE|shot=%s" % shot["id"])
        if timing["kind"] == "segment_offset":
            if str(timing.get("cue_type", "")).upper() not in ("SCENE", "WING_PAIR", "SEQUENCE"):
                raise ReviewError("BAD_CUE_TYPE|shot=%s" % shot["id"])
            if int(timing.get("ordinal", 0)) < 1:
                raise ReviewError("BAD_ORDINAL|shot=%s" % shot["id"])
            _finite_number(timing.get("offset_seconds", 0.0), "offset_seconds", 0.0)
        camera = shot.get("camera")
        if not isinstance(camera, dict) or camera.get("kind") not in CAMERA_KINDS:
            raise ReviewError("BAD_CAMERA|shot=%s" % shot["id"])
        if camera["kind"] == "actor_camera" and not camera.get("actor_label"):
            raise ReviewError("ACTOR_CAMERA_NEEDS_LABEL|shot=%s" % shot["id"])
        if camera["kind"] == "subject_close":
            _finite_number(camera.get("distance_cm"), "distance_cm", 1.0)
            _finite_number(camera.get("fov_deg"), "fov_deg", 5.0, 170.0)
            if not isinstance(shot.get("subject"), dict):
                raise ReviewError("SUBJECT_CLOSE_NEEDS_SUBJECT|shot=%s" % shot["id"])
        normalized.append(shot)
    if len(set(ids)) != len(ids):
        raise ReviewError("DUPLICATE_SHOT_IDS")
    required = config.get("required_shot_ids") or []
    missing = sorted(set(map(str, required)) - set(ids))
    if missing:
        raise ReviewError("REQUIRED_SHOTS_MISSING|%s" % missing)
    config["mode"] = mode
    config["params"] = params
    config["shots"] = normalized
    config["expected_world"] = str(config.get("expected_world", EXPECTED_WORLD))
    return config


def segment_target_frame(start, end, offset_seconds):
    start, end = int(start), int(end)
    if end - start <= END_GUARD_TICKS:
        raise ReviewError("SEGMENT_TOO_SHORT|%d..%d" % (start, end))
    frame = start + int(round(float(offset_seconds) * TICKS_PER_SECOND))
    if frame >= end:
        raise ReviewError("OFFSET_OUTSIDE_SEGMENT|offset=%.3f|duration=%.3f" %
                          (offset_seconds, (end - start) / float(TICKS_PER_SECOND)))
    return max(start, min(frame, end - END_GUARD_TICKS))


def settle_decision(samples, elapsed, params):
    width = int(params["settle_window"])
    if len(samples) >= width and elapsed >= float(params["settle_min_seconds"]):
        values = [float(row[1]) for row in samples[-width:]]
        mean = sum(values) / len(values)
        tolerance = max(float(params["settle_abs_luma"]), float(params["settle_rel_luma"]) * mean)
        if max(values) - min(values) <= tolerance:
            return "stable"
    if elapsed > float(params["settle_max_seconds"]):
        return "timeout"
    return "wait"


# -- PNG support: standard-library only so the UE Python environment needs no Pillow.
def read_png_rgb(path):
    data = pathlib.Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("NOT_PNG")
    pos, chunks, head, ended = 8, [], None, False
    while pos + 12 <= len(data):
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + size]
        if len(body) != size:
            raise ValueError("TRUNCATED_PNG")
        pos += 12 + size
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            chunks.append(body)
        elif kind == b"IEND":
            ended = True
            break
    if head is None or not ended:
        raise ValueError("INCOMPLETE_PNG")
    width, height, depth, color, _compression, _filter, interlace = head
    if depth != 8 or interlace != 0 or color not in (0, 2, 4, 6):
        raise ValueError("UNSUPPORTED_PNG|depth=%d|color=%d|interlace=%d" % (depth, color, interlace))
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    raw = zlib.decompress(b"".join(chunks))
    stride = width * bpp
    if len(raw) != height * (stride + 1):
        raise ValueError("PNG_SIZE_MISMATCH")
    rows, previous = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        method = raw[start]
        row = bytearray(raw[start + 1:start + 1 + stride])
        if method == 1:
            for x in range(bpp, stride):
                row[x] = (row[x] + row[x - bpp]) & 255
        elif method == 2:
            for x in range(stride):
                row[x] = (row[x] + previous[x]) & 255
        elif method == 3:
            for x in range(stride):
                left = row[x - bpp] if x >= bpp else 0
                row[x] = (row[x] + ((left + previous[x]) >> 1)) & 255
        elif method == 4:
            for x in range(stride):
                left = row[x - bpp] if x >= bpp else 0
                up = previous[x]
                corner = previous[x - bpp] if x >= bpp else 0
                pa, pb, pc = abs(up - corner), abs(left - corner), abs(left + up - 2 * corner)
                pred = left if pa <= pb and pa <= pc else (up if pb <= pc else corner)
                row[x] = (row[x] + pred) & 255
        elif method != 0:
            raise ValueError("BAD_PNG_FILTER|%d" % method)
        rgb = bytearray(width * 3)
        if color in (0, 4):
            for x in range(width):
                value = row[x * bpp]
                rgb[x * 3:x * 3 + 3] = bytes((value, value, value))
        else:
            for x in range(width):
                rgb[x * 3:x * 3 + 3] = row[x * bpp:x * bpp + 3]
        rows.append(bytes(rgb))
        previous = row
    return width, height, rows


def png_luma(path):
    width, height, rows = read_png_rgb(path)
    red = green = blue = 0
    for row in rows:
        red += sum(row[0::3]); green += sum(row[1::3]); blue += sum(row[2::3])
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / float(width * height)


def write_png_rgb(path, width, height, rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    pathlib.Path(path).write_bytes(data)


def make_contact_sheet(paths, out_path, columns=4, thumb=(400, 225), gutter=8):
    decoded = [read_png_rgb(path) for path in paths]
    tw, th = int(thumb[0]), int(thumb[1])
    columns = max(1, min(int(columns), len(decoded)))
    row_count = int(math.ceil(len(decoded) / float(columns)))
    width = columns * tw + (columns + 1) * int(gutter)
    height = row_count * th + (row_count + 1) * int(gutter)
    canvas = [bytearray([24, 24, 24] * width) for _ in range(height)]
    cells = []
    for index, (source_width, source_height, source_rows) in enumerate(decoded):
        column, row_index = index % columns, index // columns
        left = int(gutter) + column * (tw + int(gutter))
        top = int(gutter) + row_index * (th + int(gutter))
        for y in range(th):
            source_y = min(source_height - 1, int(y * source_height / th))
            source = source_rows[source_y]
            target = canvas[top + y]
            for x in range(tw):
                source_x = min(source_width - 1, int(x * source_width / tw))
                target_x = (left + x) * 3
                source_x *= 3
                target[target_x:target_x + 3] = source[source_x:source_x + 3]
        cells.append({"index": index, "row": row_index, "column": column,
                      "rect": [left, top, tw, th], "path": str(paths[index])})
    write_png_rgb(out_path, width, height, canvas)
    return {"path": pathlib.Path(out_path).as_posix(), "width": width, "height": height, "cells": cells}


def owner_active(path):
    path = pathlib.Path(path)
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("active"))
    except Exception:
        return True


def armed_handles(store=builtins):
    return sorted(name for name in dir(store)
                  if name.startswith("PUSS_") and name.endswith("_HANDLE") and name != HANDLE_NAME)


class CaptureMachine:
    def __init__(self, adapter, run, params, luma_reader=png_luma, clock=time.monotonic):
        self.adapter, self.run, self.params = adapter, run, params
        self.read_luma, self.clock = luma_reader, clock
        self.phase = "start_shot"
        self.index = 0
        self.phase_started = clock()
        self.pending_probe = None
        self.last_probe = None
        self.samples = []
        self.done = False

    def shot(self):
        return self.run["shots"][self.index]

    def issue_probe(self, now):
        probe_dir = pathlib.Path(self.run["run_dir"], "_probes")
        probe_dir.mkdir(parents=True, exist_ok=True)
        path = probe_dir / ("%02d_%03d.png" % (self.index, len(self.samples)))
        width, height = self.params["probe_resolution"]
        self.adapter.capture(path.as_posix(), width, height)
        self.pending_probe = {"path": path.as_posix(), "issued": now}
        self.last_probe = now

    def read_probe(self, now):
        if self.pending_probe is None:
            return None
        try:
            value = float(self.read_luma(self.pending_probe["path"]))
        except Exception:
            if now - self.pending_probe["issued"] > 4.0:
                raise ReviewError("PROBE_TIMEOUT|shot=%s" % self.shot()["id"])
            return None
        self.pending_probe = None
        return value

    def advance(self, now):
        self.adapter.release_camera()
        self.index += 1
        if self.index >= len(self.run["shots"]):
            self.done = True
            self.phase = "done"
        else:
            self.phase = "start_shot"
            self.phase_started = now

    def step(self, now):
        if self.done:
            return
        if self.adapter.world_kind() != "game":
            raise ReviewError("PIE_ENDED_OR_CHANGED")
        shot = self.shot()
        if self.phase == "start_shot":
            self.adapter.release_camera()
            self.adapter.pause()
            result = self.adapter.scrub(shot["target_frame"])
            shot.setdefault("scrub_results", []).append(str(result))
            if "SUCCEEDED" not in str(result).upper():
                raise ReviewError("SCRUB_REFUSED|shot=%s|result=%s" % (shot["id"], result))
            shot["phase"] = "repose_wait"
            self.phase = "repose_wait"
            self.phase_started = now
            return
        if self.phase == "repose_wait":
            if now - self.phase_started < float(self.params["repose_seconds"]):
                return
            # GeometryCache precedent: the same time must be posed again in a later call.
            result = self.adapter.scrub(shot["target_frame"])
            shot.setdefault("scrub_results", []).append(str(result))
            if "SUCCEEDED" not in str(result).upper():
                raise ReviewError("REPOSE_SCRUB_REFUSED|shot=%s" % shot["id"])
            self.phase = "camera_setup"
            self.phase_started = now
            return
        if self.phase == "camera_setup":
            shot["camera_readback"] = self.adapter.configure_camera(shot)
            self.phase = "camera_hold"
            self.phase_started = now
            shot["camera_hold_ticks"] = 0
            return
        if self.phase == "camera_hold":
            self.adapter.hold_camera()
            shot["camera_hold_ticks"] += 1
            if shot["camera_hold_ticks"] < int(self.params["camera_hold_ticks"]):
                return
            self.phase = "settle"
            self.phase_started = now
            self.pending_probe = None
            self.last_probe = None
            self.samples = []
            return
        if self.phase == "settle":
            self.adapter.hold_camera()
            value = self.read_probe(now)
            if isinstance(value, float):
                self.samples.append([round(now - self.phase_started, 3), round(value, 3)])
            if self.pending_probe is None and (self.last_probe is None or
                    now - self.last_probe >= float(self.params["probe_interval_seconds"])):
                self.issue_probe(now)
            verdict = settle_decision(self.samples, now - self.phase_started, self.params)
            if verdict == "wait":
                return
            shot["settle"] = {"verdict": verdict, "samples": list(self.samples)}
            if verdict != "stable":
                raise ReviewError("VISUAL_NOT_SETTLED|shot=%s" % shot["id"])
            self.pending_probe = None
            self.phase = "capture"
            return
        if self.phase == "capture":
            self.adapter.hold_camera()
            actual = int(self.adapter.frame())
            shot["master_frame_at_capture"] = actual
            if abs(actual - int(shot["target_frame"])) > int(self.params["frame_tolerance_ticks"]):
                raise ReviewError("FRAME_DRIFT|shot=%s|target=%d|actual=%d" %
                                  (shot["id"], shot["target_frame"], actual))
            width, height = self.params["resolution"]
            self.adapter.capture(shot["path"], width, height)
            shot["phase"] = "wait_file"
            self.phase = "wait_file"
            self.phase_started = now
            shot["last_size"] = -1
            shot["stable_ticks"] = 0
            return
        if self.phase == "wait_file":
            self.adapter.hold_camera()
            path = pathlib.Path(shot["path"])
            size = path.stat().st_size if path.is_file() else -1
            if size > int(self.params["file_min_bytes"]) and size == shot["last_size"]:
                shot["stable_ticks"] += 1
            else:
                shot["stable_ticks"], shot["last_size"] = 0, size
            if shot["stable_ticks"] >= int(self.params["file_stable_ticks"]):
                shot["bytes"] = size
                shot["sha256"] = file_sha256(path)
                shot["luma"] = round(float(self.read_luma(path)), 3)
                shot["phase"] = "captured"
                self.adapter.log("REVIEW_STILLS_SHOT|run=%s|i=%d|id=%s|frame=%d|bytes=%d|path=%s" %
                                 (self.run["run_id"], self.index, shot["id"],
                                  shot["master_frame_at_capture"], size, shot["path"]))
                self.advance(now)
                return
            if now - self.phase_started > float(self.params["file_timeout_seconds"]):
                raise ReviewError("CAPTURE_TIMEOUT|shot=%s|path=%s" % (shot["id"], shot["path"]))
            return
        raise ReviewError("BAD_PHASE|%s" % self.phase)


def create_dry_report(config, base_dir, run_id=None):
    run_id = run_id or ("RSTILLS-DRY-" + utc_stamp())
    report = {
        "tool": TOOL,
        "mode": "DRY",
        "run_id": run_id,
        "created_utc": utc_iso(),
        "plan_digest": plan_digest(config),
        "plan": plan_payload(config),
        "shot_count": len(config["shots"]),
        "time_policy": "symbolic offsets/panel queries only; absolute frames forbidden; resolve from live Master during RUN",
        "pie_policy": "one already-open PIE session; driver never starts or ends it",
        "exposure_policy": "no manual exposure override",
        "saves": [],
        "status": "dry_ok",
    }
    path = pathlib.Path(base_dir, "review_stills_dry_%s.json" % run_id)
    write_verified(path, report)
    report["path"] = path.as_posix()
    return report


def verify_dry_report(config, base_dir):
    raw_path = config.get("dry_report")
    if not raw_path:
        raise ReviewError("DRY_REPORT_REQUIRED")
    path = pathlib.Path(raw_path)
    if not path.is_absolute():
        path = pathlib.Path(base_dir, path)
    report = json.loads(path.read_text(encoding="utf-8"))
    expected = plan_digest(config)
    if report.get("status") != "dry_ok" or report.get("plan_digest") != expected:
        raise ReviewError("DRY_REPORT_DIGEST_MISMATCH|path=%s" % path.as_posix())
    return path, report


def arm_run(adapter, config, base_dir, backup_root, owner_path, register=None, unregister=None,
            store=builtins, clock=time.monotonic, luma_reader=png_luma):
    dry_path, dry_report = verify_dry_report(config, base_dir)
    if adapter.world_kind() != "game":
        raise ReviewError("RUN_NEEDS_EXISTING_PIE")
    if adapter.world_name() != config["expected_world"]:
        raise ReviewError("WRONG_WORLD|actual=%s|expected=%s" % (adapter.world_name(), config["expected_world"]))
    if owner_active(owner_path):
        raise ReviewError("FOREIGN_PIE_OWNER_ACTIVE|%s" % pathlib.Path(owner_path).as_posix())
    handles = armed_handles(store)
    if handles or hasattr(store, HANDLE_NAME):
        raise ReviewError("ANOTHER_CAPTURE_ARMED|%s" % (handles + ([HANDLE_NAME] if hasattr(store, HANDLE_NAME) else [])))
    census_before = adapter.census()
    run_id = "RSTILLS-RUN-" + utc_stamp()
    run_dir = pathlib.Path(base_dir, "runs", run_id)
    backup_dir = pathlib.Path(backup_root, "PreReviewStills-" + run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    backup_dir.mkdir(parents=True, exist_ok=False)
    snapshot = adapter.snapshot_runtime()
    pre_record = {
        "tool": TOOL, "run_id": run_id, "created_utc": utc_iso(), "status": "pre_change_recorded",
        "dry_report": dry_path.as_posix(), "plan_digest": dry_report["plan_digest"],
        "census_before": census_before, "runtime_before": snapshot,
        "policy": {"ends_pie": False, "exposure_override": False, "saves": []},
    }
    write_verified(run_dir / "pre_run_record.json", pre_record)
    write_verified(backup_dir / "pre_run_record.json", pre_record)
    write_verified(backup_dir / "args_snapshot.json", config)
    write_verified(backup_dir / "dry_report_snapshot.json", dry_report)

    resolved = adapter.resolve_shots(config["shots"])
    adapter.restore_frame_only(snapshot)
    shots = []
    for index, (source, facts) in enumerate(zip(config["shots"], resolved)):
        row = copy.deepcopy(source)
        row.update(facts)
        row["index"] = index
        row["path"] = (run_dir / ("%02d_%s.png" % (index + 1, row["id"]))).as_posix()
        row["phase"] = "pending"
        shots.append(row)
    run = {
        "tool": TOOL, "mode": "RUN", "run_id": run_id, "run_dir": run_dir.as_posix(),
        "started_utc": utc_iso(), "status": "armed", "plan_digest": dry_report["plan_digest"],
        "dry_report": dry_path.as_posix(), "backup": backup_dir.as_posix(),
        "world": adapter.world_name(), "census_before": census_before, "runtime_before": snapshot,
        "params": config["params"], "shots": shots, "errors": [],
        "time_policy": "all target_frame values resolved from live Master/Show in this RUN",
        "capture_policy": "single pre-existing PIE session; re-pose same time in a later callback; no exposure override",
        "saved_packages": [], "pie_started_by_driver": False, "pie_ended_by_driver": False,
    }
    manifest = run_dir / MANIFEST_NAME
    write_verified(manifest, run)
    machine = CaptureMachine(adapter, run, config["params"], luma_reader=luma_reader, clock=clock)
    holder = {"handle": None}
    started = clock()

    def cleanup_runtime():
        problems = []
        try:
            adapter.restore_runtime(snapshot)
        except Exception:
            problems.append("runtime_restore|" + traceback.format_exc())
        return problems

    def finish(status, error=None):
        if run.get("finished"):
            return
        if error:
            run["errors"].append(str(error))
        problems = cleanup_runtime()
        try:
            census_after = adapter.census()
        except Exception:
            census_after = {"error": traceback.format_exc()}
        run["census_after"] = census_after
        if census_after != census_before:
            problems.append("DIRTY_CENSUS_CHANGED|before=%r|after=%r" % (census_before, census_after))
        for shot in shots:
            path = pathlib.Path(shot["path"])
            shot["exists"] = path.is_file()
            shot["bytes"] = path.stat().st_size if path.is_file() else 0
            if status != "revert" and (not shot["exists"] or
                                       shot["bytes"] <= int(config["params"]["file_min_bytes"])):
                problems.append("MISSING_OR_SMALL|%s" % shot["id"])
        if status == "complete" and not problems and not run["errors"]:
            try:
                contact_path = run_dir / CONTACT_NAME
                run["contact_sheet"] = make_contact_sheet(
                    [shot["path"] for shot in shots], contact_path,
                    config["params"]["contact_columns"], config["params"]["contact_thumb"],
                    config["params"]["contact_gutter"])
                read_width, read_height, _rows = read_png_rgb(contact_path)
                if [read_width, read_height] != [run["contact_sheet"]["width"],
                                                  run["contact_sheet"]["height"]]:
                    raise ReviewError("CONTACT_SHEET_READBACK_SIZE")
                run["contact_sheet"]["sha256"] = file_sha256(contact_path)
            except Exception:
                problems.append("CONTACT_SHEET_FAILED|" + traceback.format_exc())
        run["problems"] = problems
        run["finished_utc"] = utc_iso()
        ok = status == "complete" and machine.done and not problems and not run["errors"]
        run["status"] = "passed" if ok else ("reverted" if status == "revert" else "failed")
        output = {key: value for key, value in run.items() if not key.startswith("_")}
        write_verified(manifest, output)
        if unregister is not None and holder["handle"] is not None:
            unregister(holder["handle"])
        for name in (HANDLE_NAME, STATE_NAME, ABORT_NAME):
            if hasattr(store, name):
                delattr(store, name)
        run["finished"] = True
        if ok:
            adapter.log("REVIEW_STILLS_OK|run=%s|shots=%d|contact=%s|manifest=%s|census=unchanged" %
                        (run_id, len(shots), run["contact_sheet"]["path"], manifest.as_posix()))
        elif status == "revert" and not problems:
            adapter.log("REVIEW_STILLS_REVERTED|run=%s|outputs_kept=true|manifest=%s" %
                        (run_id, manifest.as_posix()))
        else:
            adapter.log_error("REVIEW_STILLS_FAILED|run=%s|errors=%r|problems=%r|manifest=%s" %
                              (run_id, run["errors"], problems, manifest.as_posix()))

    def abort():
        run["revert_reason"] = "operator cleanup requested; outputs retained"
        finish("revert")

    def tick(_delta=0.0):
        if run.get("inside") or run.get("finished"):
            return
        run["inside"] = True
        try:
            now = clock()
            if now - started > float(config["params"]["run_timeout_seconds"]):
                raise ReviewError("RUN_TIMEOUT")
            machine.step(now)
            if machine.done:
                finish("complete")
        except Exception:
            run["errors"].append(traceback.format_exc())
            finish("failed")
        finally:
            run["inside"] = False

    adapter.prepare_capture()
    run["status"] = "capturing"
    setattr(store, STATE_NAME, run)
    setattr(store, ABORT_NAME, abort)
    if register is not None:
        holder["handle"] = register(tick)
        setattr(store, HANDLE_NAME, holder["handle"])
    run["_tick"] = tick
    adapter.log("REVIEW_STILLS_ARMED|run=%s|shots=%d|one_existing_pie=true|dir=%s" %
                (run_id, len(shots), run_dir.as_posix()))
    return run


def _enum_token(value):
    return str(value).split(".")[-1].split(":")[0].strip().rstrip(">").upper()


def _unwrap(value, count=None):
    if isinstance(value, tuple):
        values = list(value)
        if values and isinstance(values[0], bool):
            if not values[0]:
                return None
            values = values[1:]
        if count is not None and len(values) < count:
            return None
        return values if count is None else values[:count]
    return [value] if count in (None, 1) else None


def make_unreal_adapter(unreal):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    first_world = editor.get_game_world()
    first_path = first_world.get_outermost().get_name() if first_world is not None else None
    runtime = {"borrowed": None, "borrowed_state": None, "held": None, "original_view": None,
               "performance_mode": None, "messages_disabled": False}

    def world():
        current = editor.get_game_world()
        if current is None or first_path is None or current.get_outermost().get_name() != first_path:
            return None
        return current

    def root():
        current = world()
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(current, unreal.InfinityStageShowRoot)) if current else []
        if len(roots) != 1 or not roots[0].sequence_player:
            raise ReviewError("SHOW_ROOT_COUNT|%d" % len(roots))
        return roots[0]

    def all_actors():
        return list(unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor))

    def passage_actor(code):
        number = int(str(code)[1:])
        actors = list(unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.InfinityStagePassageActor))
        matches = [actor for actor in actors if re.search(r"(?:^|\D)0?%d(?:\D|$)" % number, str(actor.get_actor_label()))]
        if len(matches) != 1:
            raise ReviewError("PASSAGE_ACTOR_COUNT|%s|%d" % (code, len(matches)))
        return matches[0]

    def cue_guid(actor, label):
        show = actor.get_editor_property("show_asset")
        cues = [cue for cue in list(show.get_editor_property("cues"))
                if str(cue.get_editor_property("label")) == str(label)]
        if len(cues) != 1:
            raise ReviewError("CUE_COUNT|%s|%d" % (label, len(cues)))
        return cues[0].get_editor_property("cue_guid")

    def guid_text(guid):
        return str(guid.to_string()).replace("-", "").lower()

    def panel_refs(subject):
        actor = passage_actor(subject["passage"])
        target_guid = guid_text(cue_guid(actor, subject["cue_label"]))
        wanted = str(subject.get("side", "BOTH")).upper()
        refs = []
        for ref in list(actor.get_editor_property("materialized_panels")):
            if guid_text(ref.get_editor_property("cue_guid")) != target_guid:
                continue
            side = _enum_token(ref.get_editor_property("side"))
            if wanted != "BOTH" and wanted not in side:
                continue
            refs.append(ref)
        if not refs:
            raise ReviewError("PANEL_REF_EMPTY|%s|%s" % (subject["cue_label"], wanted))
        return actor, refs

    def ref_bounds(ref):
        component = ref.get_editor_property("component")
        transform = component.get_instance_transform(int(ref.get_editor_property("instance_index")), True)
        mesh = component.get_editor_property("static_mesh")
        box = mesh.get_bounding_box()
        points = [transform.transform_location(unreal.Vector(x, y, z))
                  for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y)
                  for z in (box.min.z, box.max.z)]
        lo = [min(getattr(point, axis) for point in points) for axis in "xyz"]
        hi = [max(getattr(point, axis) for point in points) for axis in "xyz"]
        return lo, hi

    def merge_bounds(bounds):
        lo = [min(item[0][axis] for item in bounds) for axis in range(3)]
        hi = [max(item[1][axis] for item in bounds) for axis in range(3)]
        return {"min": lo, "max": hi, "centre": [(a + b) / 2.0 for a, b in zip(lo, hi)],
                "extent": [(b - a) / 2.0 for a, b in zip(lo, hi)]}

    def actor_matches(actor, selector):
        label = str(actor.get_actor_label())
        if selector.get("actor_label") is not None and label != selector["actor_label"]:
            return False
        if selector.get("actor_label_regex") is not None and not re.search(selector["actor_label_regex"], label):
            return False
        if selector.get("actor_tag") is not None and not actor.actor_has_tag(selector["actor_tag"]):
            return False
        if selector.get("mesh_name_regex") is not None:
            components = actor.get_components_by_class(unreal.StaticMeshComponent)
            names = [component.get_editor_property("static_mesh").get_name()
                     for component in components if component.get_editor_property("static_mesh") is not None]
            if not any(re.search(selector["mesh_name_regex"], name) for name in names):
                return False
        return True

    def subject_bounds(subject):
        kind = subject.get("kind")
        if kind == "panel":
            _actor, refs = panel_refs(subject)
            return merge_bounds([ref_bounds(ref) for ref in refs]), ["panel:%s:%s" %
                   (subject["cue_label"], subject.get("side", "BOTH"))]
        if kind == "actors":
            selectors = subject.get("selectors") or []
            matches = [actor for actor in all_actors() if any(actor_matches(actor, selector) for selector in selectors)]
            minimum = int(subject.get("minimum_matches", 1))
            if len(matches) < minimum:
                raise ReviewError("SUBJECT_ACTOR_COUNT|found=%d|minimum=%d|selectors=%r" %
                                  (len(matches), minimum, selectors))
            boxes = []
            for actor in matches:
                origin, extent = actor.get_actor_bounds(False, True)
                boxes.append(([origin.x - extent.x, origin.y - extent.y, origin.z - extent.z],
                              [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]))
            return merge_bounds(boxes), [str(actor.get_actor_label()) for actor in matches]
        raise ReviewError("BAD_SUBJECT_KIND|%r" % kind)

    def passage_range(actor):
        show = actor.get_editor_property("show_asset")
        guid = actor.get_editor_property("passage_guid")
        values = _unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, guid), 2)
        if not values:
            raise ReviewError("PASSAGE_RANGE_UNREADABLE|%s" % actor.get_actor_label())
        return int(values[0]), int(values[1]), show, guid

    def closest_camera_frame(subject, samples=97):
        actor, refs = panel_refs(subject)
        bounds = merge_bounds([ref_bounds(ref) for ref in refs])
        start, end, show, guid = passage_range(actor)
        target = bounds["centre"]
        rows = []
        for index in range(max(3, int(samples))):
            frame = start + int(round((end - start - END_GUARD_TICKS) * index / float(max(1, samples - 1))))
            values = _unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_camera_pose(show, guid, frame), 3)
            if not values:
                continue
            location = values[0].translation
            distance = math.sqrt((location.x - target[0]) ** 2 + (location.y - target[1]) ** 2 +
                                 (location.z - target[2]) ** 2)
            rows.append((distance, frame, [float(location.x), float(location.y), float(location.z)]))
        if not rows:
            raise ReviewError("PASSAGE_CAMERA_POSE_UNREADABLE|%s" % subject["cue_label"])
        distance, frame, location = min(rows)
        return frame, {"method": "live_passage_camera_nearest_panel", "sample_count": len(rows),
                       "nearest_distance_cm": distance, "camera_location": location,
                       "passage_range": [start, end], "panel_bounds": bounds}

    def mid_motion_frame(subject, timing):
        pass_frame, pass_facts = closest_camera_frame(subject, timing.get("camera_samples", 97))
        actor, refs = panel_refs(subject)
        if len(refs) != 1:
            raise ReviewError("MID_MOTION_NEEDS_ONE_PANEL|found=%d" % len(refs))
        start, end, _show, _guid = passage_range(actor)
        half = int(round(float(timing.get("motion_window_seconds", 6.0)) * TICKS_PER_SECOND))
        lo, hi = max(start, pass_frame - half), min(end - END_GUARD_TICKS, pass_frame + half)
        count = max(5, int(timing.get("motion_samples", 49)))
        rows = []
        ref = refs[0]
        for index in range(count):
            frame = lo + int(round((hi - lo) * index / float(count - 1)))
            if not actor.evaluate_mechanisms_at_master_frame(unreal.FrameNumber(frame)):
                raise ReviewError("MECHANISM_EVALUATE_FAILED|frame=%d" % frame)
            component = ref.get_editor_property("component")
            transform = component.get_instance_transform(int(ref.get_editor_property("instance_index")), True)
            location = transform.translation
            rows.append((frame, [float(location.x), float(location.y), float(location.z)]))
        farthest = max(((sum((a[1][axis] - b[1][axis]) ** 2 for axis in range(3)), a, b)
                        for a in rows for b in rows), key=lambda item: item[0])
        if farthest[0] < 1.0:
            raise ReviewError("PANEL_DID_NOT_MOVE|%s" % subject["cue_label"])
        midpoint = [(farthest[1][1][axis] + farthest[2][1][axis]) / 2.0 for axis in range(3)]
        chosen = min(rows, key=lambda row: sum((row[1][axis] - midpoint[axis]) ** 2 for axis in range(3)))
        return chosen[0], {"method": "live_panel_motion_midpoint", "pass_frame_probe": pass_facts,
                           "motion_window": [lo, hi], "motion_samples": len(rows),
                           "motion_endpoints": [farthest[1], farthest[2]], "chosen": chosen}

    def segment_range(cue_type, ordinal):
        wanted = str(cue_type).upper()
        segments = [segment for segment in list(root().transport.segments)
                    if wanted in _enum_token(segment.type)]
        if not 1 <= int(ordinal) <= len(segments):
            raise ReviewError("SEGMENT_ORDINAL|type=%s|ordinal=%s|count=%d" %
                              (wanted, ordinal, len(segments)))
        segment = segments[int(ordinal) - 1]
        return int(segment.start_frame.value), int(segment.end_frame.value), str(segment.label)

    class Adapter:
        def world_kind(self):
            return "game" if world() is not None else None

        def world_name(self):
            return first_path

        def log(self, message):
            unreal.log(message)

        def log_error(self, message):
            unreal.log_error(message)

        def census(self):
            names = lambda packages: sorted(str(package.get_name()).split(".", 1)[0] for package in packages)
            return {"maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
                    "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}

        def snapshot_runtime(self):
            show_root = root()
            controller = unreal.GameplayStatics.get_player_controller(world(), 0)
            runtime["original_view"] = controller.get_view_target() if controller else None
            runtime["performance_mode"] = bool(show_root.transport.get_editor_property("performance_mode"))
            return {"frame": int(show_root.transport.get_current_master_frame().value),
                    "was_playing": bool(show_root.transport.is_transport_playing()),
                    "performance_mode": runtime["performance_mode"],
                    "view_target": str(runtime["original_view"].get_path_name()) if runtime["original_view"] else None}

        def restore_frame_only(self, snapshot):
            if world() is not None:
                self.scrub(int(snapshot["frame"]))

        def prepare_capture(self):
            show_root = root()
            show_root.sequence_player.pause()
            show_root.transport.set_editor_property("performance_mode", False)
            unreal.SystemLibrary.execute_console_command(world(), "DisableAllScreenMessages")
            runtime["messages_disabled"] = True

        def restore_runtime(self, snapshot):
            self.release_camera()
            if world() is None:
                return
            show_root = root()
            show_root.transport.set_editor_property("performance_mode", bool(snapshot["performance_mode"]))
            self.scrub(int(snapshot["frame"]))
            self.release_camera()
            if runtime["messages_disabled"]:
                unreal.SystemLibrary.execute_console_command(world(), "EnableAllScreenMessages")
                runtime["messages_disabled"] = False

        def resolve_shots(self, shots):
            output = []
            for shot in shots:
                timing = shot["time"]
                if timing["kind"] == "segment_offset":
                    start, end, label = segment_range(timing["cue_type"], timing["ordinal"])
                    frame = segment_target_frame(start, end, float(timing.get("offset_seconds", 0.0)))
                    facts = {"target_frame": frame, "time_readback": {"method": "live_transport_segment_offset",
                             "segment_label": label, "segment": [start, end],
                             "offset_seconds": float(timing.get("offset_seconds", 0.0))}}
                else:
                    subject = {"kind": "panel", "passage": timing["passage"],
                               "cue_label": timing["cue_label"], "side": timing.get("side", "BOTH")}
                    if timing["kind"] == "panel_pass":
                        frame, readback = closest_camera_frame(subject, timing.get("camera_samples", 97))
                    else:
                        frame, readback = mid_motion_frame(subject, timing)
                    facts = {"target_frame": int(frame), "time_readback": readback}
                output.append(facts)
            return output

        def pause(self):
            root().sequence_player.pause()

        def scrub(self, frame):
            show_root = root()
            show_root.sequence_player.pause()
            return show_root.transport.scrub_to_master_frame(unreal.FrameNumber(int(frame)))

        def frame(self):
            return int(root().transport.get_current_master_frame().value)

        def _camera_component(self, actor):
            if isinstance(actor, unreal.CineCameraActor):
                return actor.get_cine_camera_component()
            return actor.get_editor_property("camera_component")

        def _save_borrowed(self, actor):
            component = self._camera_component(actor)
            state = {"location": actor.get_actor_location(), "rotation": actor.get_actor_rotation(),
                     "constrain": bool(component.get_editor_property("constrain_aspect_ratio"))}
            if isinstance(component, unreal.CineCameraComponent):
                state["focal"] = float(component.get_editor_property("current_focal_length"))
            else:
                state["fov"] = float(component.get_editor_property("field_of_view"))
            runtime["borrowed"], runtime["borrowed_state"] = actor, state
            return component

        def _set_fov(self, component, fov):
            if isinstance(component, unreal.CineCameraComponent):
                filmback = component.get_editor_property("filmback")
                focal = (float(filmback.sensor_width) / 2.0) / math.tan(math.radians(float(fov) / 2.0))
                component.set_editor_property("current_focal_length", focal)
            else:
                component.set_editor_property("field_of_view", float(fov))
            component.set_editor_property("constrain_aspect_ratio", False)

        def configure_camera(self, shot):
            camera = shot["camera"]
            controller = unreal.GameplayStatics.get_player_controller(world(), 0)
            if controller is None:
                raise ReviewError("NO_PLAYER_CONTROLLER")
            if camera["kind"] == "master":
                runtime["held"] = None
                return {"kind": "master", "view_target": str(controller.get_view_target().get_path_name())}
            if camera["kind"] == "actor_camera":
                matches = [actor for actor in all_actors() if str(actor.get_actor_label()) == camera["actor_label"]]
                if len(matches) != 1:
                    raise ReviewError("CAMERA_ACTOR_COUNT|%s|%d" % (camera["actor_label"], len(matches)))
                if shot.get("required_subject"):
                    subject_bounds(shot["required_subject"])
                runtime["held"] = matches[0]
                controller.set_view_target_with_blend(matches[0], 0.0)
                return {"kind": "actor_camera", "label": camera["actor_label"],
                        "path": str(matches[0].get_path_name())}
            bounds, matched = subject_bounds(shot["subject"])
            cameras = list(unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.CameraActor))
            cameras.sort(key=lambda actor: (actor == runtime["original_view"],
                                             str(actor.get_actor_label()) != "ClamCam1",
                                             str(actor.get_actor_label())))
            borrowed = cameras[0] if cameras else None
            if borrowed is None:
                raise ReviewError("NO_PIE_CAMERA_TO_BORROW")
            component = self._save_borrowed(borrowed)
            target = unreal.Vector(*bounds["centre"])
            active_location = unreal.GameplayStatics.get_player_camera_manager(world(), 0).get_camera_location()
            away = active_location - target
            if float(away.length()) < 1.0:
                away = unreal.Vector(-1.0, 0.0, 0.0)
            location = target + away * (float(camera["distance_cm"]) / float(away.length()))
            rotation = unreal.MathLibrary.find_look_at_rotation(location, target)
            borrowed.set_actor_location_and_rotation(location, rotation, False, True)
            self._set_fov(component, float(camera["fov_deg"]))
            runtime["held"] = borrowed
            controller.set_view_target_with_blend(borrowed, 0.0)
            return {"kind": "subject_close", "borrowed_camera": str(borrowed.get_actor_label()),
                    "matched": matched, "bounds": bounds,
                    "location": [float(location.x), float(location.y), float(location.z)],
                    "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
                    "fov_deg": float(camera["fov_deg"]), "distance_cm": float(camera["distance_cm"])}

        def hold_camera(self):
            if runtime["held"] is None:
                return
            controller = unreal.GameplayStatics.get_player_controller(world(), 0)
            if controller and controller.get_view_target() != runtime["held"]:
                controller.set_view_target_with_blend(runtime["held"], 0.0)

        def release_camera(self):
            controller = unreal.GameplayStatics.get_player_controller(world(), 0) if world() else None
            if controller is not None and runtime["original_view"] is not None:
                controller.set_view_target_with_blend(runtime["original_view"], 0.0)
            actor, state = runtime["borrowed"], runtime["borrowed_state"]
            if actor is not None and state is not None:
                actor.set_actor_location_and_rotation(state["location"], state["rotation"], False, True)
                component = self._camera_component(actor)
                component.set_editor_property("constrain_aspect_ratio", state["constrain"])
                if "focal" in state:
                    component.set_editor_property("current_focal_length", state["focal"])
                else:
                    component.set_editor_property("field_of_view", state["fov"])
            runtime["borrowed"] = runtime["borrowed_state"] = runtime["held"] = None

        def capture(self, path, width, height):
            unreal.SystemLibrary.execute_console_command(
                world(), 'HighResShot %dx%d filename="%s"' % (int(width), int(height), str(path)))

    return Adapter()


def main():
    import unreal
    saved = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
    project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    base = saved / "CodexFlatV3" / "review_stills"
    args_path = base / "review_stills_args.json"
    config = validate_config(json.loads(args_path.read_text(encoding="utf-8")))
    if config["mode"] == "DRY":
        report = create_dry_report(config, base)
        unreal.log("REVIEW_STILLS_DRY_OK|run=%s|shots=%d|digest=%s|report=%s" %
                   (report["run_id"], report["shot_count"], report["plan_digest"], report["path"]))
        return report["path"]
    if config["mode"] == "REVERT":
        abort = getattr(builtins, ABORT_NAME, None)
        if abort is None:
            unreal.log("REVIEW_STILLS_REVERTED|run=none|noop=true|reason=no_owned_callback")
            return "noop"
        abort()
        return "reverted"
    adapter = make_unreal_adapter(unreal)
    run = arm_run(
        adapter, config, base, project / "Backups", saved / OWNER_REL,
        register=unreal.register_slate_post_tick_callback,
        unregister=unreal.unregister_slate_post_tick_callback,
    )
    return run["run_dir"]


if __name__ == "__main__" or "REVIEW_STILLS_EXECUTE" in globals():
    main()
