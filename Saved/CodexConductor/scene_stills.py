"""PASSAGE STILLS: still frames of one Passage at chosen fractions of its length, captured
inside a PIE session the conductor has ALREADY started (conductor_pie_begin.py). For
reviewing look changes (first use: P05 after the underpass rig; then P01-P04/P06 after
the lighting scores). Output: PNGs + passage_stills_manifest.json in
Saved/CodexConductor/PassageStills/<run_id>/.

Inputs (runpy init_globals, see passage_stills_run.py):
  STILLS_PASSAGE   "P05"
  STILLS_FRACTIONS [0.1, 0.3, 0.5, 0.7, 0.9]   (fractions of the Passage segment span)
  STILLS_LABEL     optional short tag added to the run id

ROUTE (why the Master, not a placed camera). The Passage camera is the show's own
camera, driven by the Master sequence. Two routes were proven by earlier runs:
  - Master scrub: UInfinityStageTransportController::ScrubToMasterFrame
    (InfinityStageTransportController.h:597, impl .cpp:1423-1455 pauses the player,
    jumps, and claims the segment camera). Used by look_bench.py:1638-1641,
    s3_beach_pie_stills_driver.py:119 and fx_stills_pie_driver.py:132; every
    recorded scrub_result was SUCCEEDED (33 runtime_result.json rows).
  - Moving the view-target actor (s3_beach_pie_stills_driver.py:132-159), which
    mutates a runtime actor that the sequence also drives.
This tool uses ONLY the Master scrub and then READS the live camera pose
(look_bench.py:1564-1576): the frame is exactly what the show shows at that time,
with the time-keyed lighting cues active, and no actor is moved. The look bench's
measured PIE clips show the Passage camera travelling the route at eye height
(LookBench/20261005-062436/capture_20261005-064434_capture: y 240000, z 180, yaw 0).

Per still: scrub -> wait repose_seconds -> re-scrub (a jump's first frame can be
stale) -> luma settle gate (small HighResShot probes until stable; copied from
look_bench.py:1026-1107) -> master-frame gate (still on target) -> HighResShot ->
wait until the file is non-trivial and stable -> one post-capture probe (picture
must not have moved) -> record pose, master frame and luma.

Safety: refuses without PIE, with another PUSS_* tick handle armed, or with an active
pie_recording_owner.json. Never ends PIE, never quits, never saves, never spawns, never
reloads a level (the harness scans for those names). Package census (dirty maps +
dirty content) before == after or the run FAILS. Screen messages are disabled for the
captures and restored on every exit. At the end the transport is scrubbed back to the
frame it was on (not resumed). Unreal objects live only inside make_pie_adapter's
closure; module globals hold plain data.

Markers: PASSAGE_STILLS_START|run=..., PASSAGE_STILLS_FRAME|run=...|i=...,
PASSAGE_STILLS_OK|run=...|n=...|dir=... (only after every file exists, the census
matched and the manifest read back), PASSAGE_STILLS_FAILED|run=...|reason=...
(raised at arm time; in the tick it is logged as an error and the run is finished).
"""
from __future__ import annotations

import builtins
import datetime
import json
import math
import pathlib
import re
import struct
import time
import traceback
import zlib

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
OUT_ROOT = BASE / "PassageStills"
OWNER = BASE / "pie_recording_owner.json"
HANDLE_NAME = "PUSS_PASSAGE_STILLS_HANDLE"
STATE_NAME = "PUSS_PASSAGE_STILLS_STATE"
MANIFEST_NAME = "passage_stills_manifest.json"
TICKS_PER_SECOND = 24000          # Master tick rate (fx_stills_pie_driver.py:20, s3_beach_pie_stills_driver.py:21)
DISPLAY_FPS = 24                  # s3_beach_pie_stills_driver.py:22
END_GUARD_TICKS = TICKS_PER_SECOND // DISPLAY_FPS   # fraction 1.0 lands one display frame before the end
DEFAULT_FRACTIONS = (0.1, 0.3, 0.5, 0.7, 0.9)
MAX_STILLS = 24

DEFAULTS = {
    "resolution": (1600, 900),       # the drivers' still size
    "repose_seconds": 1.0,           # look_bench DEFAULTS
    "settle_min_seconds": 4.0,
    "settle_max_seconds": 20.0,
    "settle_ticks": 45,
    "probe_interval_s": 0.5,
    "probe_timeout_s": 4.0,
    "probe_resolution": (256, 144),
    "settle_window": 4,
    "settle_tol_abs": 2.0,
    "settle_tol_rel": 0.03,
    "frame_tol_ticks": 1,            # fx_stills_pie_driver.py:135 allows 1 tick
    "file_min_bytes": 1000,          # drivers' undersize threshold
    "file_stable_ticks": 4,
    "file_timeout_s": 45.0,
    "fov_fallback_deg": 90.0,
    "run_timeout_s_per_still": 75.0,
    "screen_messages": "off",        # "off" = DisableAllScreenMessages for the run, restored at the end
}


# --------------------------------------------------------------------------
# pure helpers (no Unreal): tested offline by test_passage_stills.py
# --------------------------------------------------------------------------

class StillsRefused(RuntimeError):
    def __init__(self, reason, detail="", run="?"):
        self.reason, self.detail = reason, str(detail)
        super().__init__("PASSAGE_STILLS_FAILED|run=%s|reason=%s%s" % (run, reason, ("|" + self.detail) if detail else ""))


def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def passage_label(passage):
    """'P05' -> (5, 'Passage 5'), the runtime segment label (lighting_looks_p04_driver.py:166)."""
    if str(passage).strip().lower() == "opening":   # 8 Oct: the Opening segment (stage front stills)
        return 0, "Opening"
    ms = re.fullmatch(r"[Ss](\d{1,2})", str(passage).strip())
    if ms:                                   # scene_stills variant (7 Oct): 'S1' -> segment label prefix 'Scene 1'
        return int(ms.group(1)), "Scene %d" % int(ms.group(1))
    m = re.fullmatch(r"[Pp](\d{1,2})", str(passage).strip())
    if not m or int(m.group(1)) < 1:
        raise StillsRefused("bad_passage", repr(passage))
    n = int(m.group(1))
    return n, "Passage %d" % n


def validate_fractions(fractions):
    if fractions is None:
        fractions = DEFAULT_FRACTIONS
    if isinstance(fractions, (str, bytes)) or not hasattr(fractions, "__iter__"):
        raise StillsRefused("bad_fractions", repr(fractions))
    out = []
    for f in fractions:
        if isinstance(f, bool) or not isinstance(f, (int, float)) or not math.isfinite(float(f)):
            raise StillsRefused("bad_fractions", repr(f))
        if not 0.0 <= float(f) <= 1.0:
            raise StillsRefused("bad_fractions", "%r outside [0,1]" % f)
        out.append(float(f))
    if not out or len(out) > MAX_STILLS:
        raise StillsRefused("bad_fractions", "count %d" % len(out))
    if len(set(out)) != len(out):
        raise StillsRefused("bad_fractions", "duplicates")
    return out


def fraction_to_frame(start, end, fraction):
    """Segment [start, end) in Master ticks -> absolute Master frame. 1.0 is clamped one
    display frame before the end (memory: the end frame is the restored REST pose)."""
    start, end = int(start), int(end)
    if end - start <= END_GUARD_TICKS:
        raise StillsRefused("segment_too_short", "%d..%d" % (start, end))
    frame = start + int(round(float(fraction) * (end - start)))
    return max(start, min(frame, end - END_GUARD_TICKS))


def plan_stills(start, end, fractions, run_dir):
    rows = []
    for i, f in enumerate(fractions):
        frame = fraction_to_frame(start, end, f)
        rows.append({"i": i, "fraction": f, "target_frame": frame,
                     "seconds_into_passage": (frame - int(start)) / float(TICKS_PER_SECOND),
                     "path": (pathlib.Path(run_dir) / ("%02d_f%03d.png" % (i, int(round(f * 1000))))).as_posix(),
                     "phase": "pending"})
    frames = [r["target_frame"] for r in rows]
    if len(set(frames)) != len(frames):
        raise StillsRefused("fractions_collide", "two fractions land on the same frame")
    return rows


def package_names(packages):
    return sorted(str(p.get_name()).split(".", 1)[0] for p in packages)


def png_luma(path):
    """Mean Rec.709 luma of an 8-bit non-interlaced PNG on stored sRGB 0-255 values. Copy of
    look_bench.py:1026-1092 (harness checks parity). Raises on a half-written file."""
    data = pathlib.Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PASSAGE_STILLS_PNG|not a PNG")
    pos, idat, head, ended = 8, [], None, False
    while pos + 8 <= len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        if len(body) != n:
            raise ValueError("PASSAGE_STILLS_PNG|truncated chunk")
        pos += 12 + n
        if typ == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            ended = True
            break
    if head is None or not ended:
        raise ValueError("PASSAGE_STILLS_PNG|incomplete")
    w, h, depth, ctype, _comp, _filt, interlace = head
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 4, 6):
        raise ValueError("PASSAGE_STILLS_PNG|unsupported depth=%d type=%d interlace=%d" % (depth, ctype, interlace))
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride = w * bpp
    if len(raw) != h * (stride + 1):
        raise ValueError("PASSAGE_STILLS_PNG|size mismatch")
    prev = bytearray(stride)
    sr = sg = sb = 0
    for y in range(h):
        base = y * (stride + 1)
        ftype = raw[base]
        line = bytearray(raw[base + 1:base + 1 + stride])
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ftype == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        elif ftype != 0:
            raise ValueError("PASSAGE_STILLS_PNG|bad filter %d" % ftype)
        if ctype in (0, 4):
            v = sum(line[0::bpp])
            sr, sg, sb = sr + v, sg + v, sb + v
        else:
            sr += sum(line[0::bpp])
            sg += sum(line[1::bpp])
            sb += sum(line[2::bpp])
        prev = line
    return (0.2126 * sr + 0.7152 * sg + 0.0722 * sb) / float(w * h)


def settle_decision(samples, elapsed, p):
    """Copy of look_bench.py:1095-1107: 'stable' | 'wait' | 'timeout'."""
    k = int(p["settle_window"])
    if len(samples) >= k and elapsed >= float(p["settle_min_seconds"]):
        last = [float(s[1]) for s in samples[-k:]]
        mean = sum(last) / k
        if max(last) - min(last) <= max(float(p["settle_tol_abs"]), float(p["settle_tol_rel"]) * mean):
            return "stable"
    if elapsed > float(p["settle_max_seconds"]):
        return "timeout"
    return "wait"


def luma_tol(p, ref):
    return max(float(p["settle_tol_abs"]), float(p["settle_tol_rel"]) * float(ref))


def scrub_ok(result):
    return "SUCCEEDED" in str(result).upper()


def write_verified(path, data):
    """Write JSON, re-read, compare. Returns the path; raises on mismatch."""
    path = pathlib.Path(path)
    text = json.dumps(data, indent=1, sort_keys=True, default=str)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
    if json.loads(path.read_text(encoding="utf-8")) != json.loads(text):
        raise RuntimeError("PASSAGE_STILLS_MANIFEST_READBACK|" + path.as_posix())
    return path


# --------------------------------------------------------------------------
# engine-free state machine (driven by the Slate tick; the harness drives it with a fake clock)
# --------------------------------------------------------------------------

class StillsMachine:
    """Phases per still: jump -> repose -> settle -> capture -> wait_file -> post_probe -> next.
    Gate failures (settle timeout, frame drift, post-capture drift) are recorded and the run goes
    on (every still is still useful to look at) but they turn the result into FAILED. Hard errors
    (scrub refused, PIE gone, file timeout) stop the run; finish() always runs."""

    def __init__(self, adapter, run, params, luma_reader=None, clock=time.monotonic):
        self.a, self.run, self.p = adapter, run, params
        self.read_luma = luma_reader or png_luma
        self.clock = clock
        self.st = {"phase": "jump", "index": 0, "probe_n": 0, "probe_timeouts": 0, "gate_failures": []}
        self.done = False

    # ---- helpers
    def _still(self):
        return self.run["stills"][self.st["index"]]

    def _fail(self, why):
        self.st["gate_failures"].append(why)
        self._still().setdefault("gate_failures", []).append(why)

    def _scrub(self, still, now):
        res = self.a.transport_scrub(still["target_frame"])
        still.setdefault("scrub_results", []).append(str(res))
        if not scrub_ok(res):
            raise StillsRefused("scrub_refused", "i=%d frame=%d result=%s" % (still["i"], still["target_frame"], res))

    def _probe_path(self, tag):
        d = pathlib.Path(self.run["run_dir"]) / "_probes"
        d.mkdir(parents=True, exist_ok=True)
        self.st["probe_n"] += 1
        return (d / ("%02d_%s_%03d.png" % (self.st["index"], tag, self.st["probe_n"]))).as_posix()

    def _issue_probe(self, now, tag):
        path = self._probe_path(tag)
        w, h = self.p["probe_resolution"]
        self.a.console('HighResShot %dx%d filename="%s"' % (w, h, path))
        self.st["pending"] = {"path": path, "t": now}
        self.st["last_issue"] = now

    def _read_pending(self, now):
        """None while not yet readable; a float once read; 'timeout' after probe_timeout_s."""
        pend = self.st.get("pending")
        if not pend:
            return None
        try:
            y = float(self.read_luma(pend["path"]))
        except Exception:                        # HighResShot writes asynchronously: retry next tick
            if now - pend["t"] > float(self.p["probe_timeout_s"]):
                self.st["probe_timeouts"] += 1
                self.st["pending"] = None
                return "timeout"
            return None
        self.st["pending"] = None
        return y

    def _next_still(self):
        self.st["index"] += 1
        if self.st["index"] >= len(self.run["stills"]):
            self.st["phase"] = "done"
            self.done = True
        else:
            self.st["phase"] = "jump"

    # ---- the step
    def step(self, now):
        st, p, a = self.st, self.p, self.a
        if self.done:
            return
        if a.world_kind() != "game":
            raise StillsRefused("pie_ended", "PIE world gone or replaced mid-run")
        still = self._still()
        phase = st["phase"]
        if phase == "jump":
            a.transport_pause()
            self._scrub(still, now)
            still["phase"] = "settling"
            st.update(phase="repose", t0=now, reposed=False, samples=[], settle_ticks=0, pending=None,
                      last_issue=None)
            return
        if phase == "repose":
            if now - st["t0"] >= float(p["repose_seconds"]):
                self._scrub(still, now)          # re-pose: a jump's first frame can be stale
                st["phase"] = "settle"
            return
        if phase == "settle":
            st["settle_ticks"] += 1
            el = now - st["t0"]
            got = self._read_pending(now)
            if isinstance(got, float):
                st["samples"].append([round(el, 3), round(got, 3)])
            if st.get("pending") is None and (st["last_issue"] is None or
                                              now - st["last_issue"] >= float(p["probe_interval_s"])):
                self._issue_probe(now, "settle")
            verdict = settle_decision(st["samples"], el, p)
            if verdict == "wait" or (verdict == "stable" and st["settle_ticks"] < int(p["settle_ticks"])):
                return
            luma = st["samples"][-1][1] if st["samples"] else None
            still["settle"] = {"verdict": verdict, "seconds": round(el, 3), "samples": list(st["samples"]),
                               "luma": luma}
            if verdict != "stable":
                self._fail("settle i=%d: picture still changing after %.1f s" % (still["i"], el))
            st["pending"] = None
            st["phase"] = "capture"
            return
        if phase == "capture":
            frame = int(a.transport_frame())
            still["master_frame_at_capture"] = frame
            if abs(frame - still["target_frame"]) > int(p["frame_tol_ticks"]):
                self._fail("frame i=%d: at %d, target %d" % (still["i"], frame, still["target_frame"]))
            w, h = p["resolution"]
            pose = a.camera_pose(float(w) / float(h), p["fov_fallback_deg"])
            if pose is None:
                raise StillsRefused("no_camera", "no player camera manager in PIE")
            still["pose"] = pose
            still["command"] = 'HighResShot %dx%d filename="%s"' % (w, h, still["path"])
            a.console(still["command"])
            still["phase"] = "wait_file"
            st.update(phase="wait_file", issued=now, last_size=-1, stable=0)
            return
        if phase == "wait_file":
            path = pathlib.Path(still["path"])
            size = path.stat().st_size if path.is_file() else -1
            if size > int(p["file_min_bytes"]) and size == st["last_size"]:
                st["stable"] += 1
            else:
                st["stable"], st["last_size"] = 0, size
            if st["stable"] >= int(p["file_stable_ticks"]):
                still["bytes"] = size
                still["master_frame_after_file"] = int(a.transport_frame())
                self._issue_probe(now, "post")
                st["phase"] = "post_probe"
                return
            if now - st["issued"] > float(p["file_timeout_s"]):
                raise StillsRefused("capture_timeout", still["path"])
            return
        if phase == "post_probe":
            got = self._read_pending(now)
            if got is None:
                return
            ref = (still.get("settle") or {}).get("luma")
            if got == "timeout":
                still["luma_after_capture"] = None
                self._fail("post_probe i=%d: probe never readable" % still["i"])
            else:
                still["luma_after_capture"] = round(got, 3)
                if ref is not None and abs(got - ref) > luma_tol(p, ref):
                    self._fail("post_capture_drift i=%d: %.1f vs settled %.1f" % (still["i"], got, ref))
            still["luma"] = ref
            if still["master_frame_after_file"] != still["master_frame_at_capture"]:
                self._fail("frame_moved i=%d: %d -> %d" % (still["i"], still["master_frame_at_capture"],
                                                            still["master_frame_after_file"]))
            still["phase"] = "captured"
            loc = still["pose"]["loc"]
            rot = still["pose"]["rot"]
            a.log("PASSAGE_STILLS_FRAME|run=%s|i=%d|fraction=%.3f|master_frame=%d|luma=%s|cam=%.0f,%.0f,%.0f|yaw=%.1f"
                  "|pitch=%.1f|bytes=%d|path=%s" % (
                      self.run["run_id"], still["i"], still["fraction"], still["master_frame_at_capture"],
                      "%.1f" % ref if ref is not None else "none", loc[0], loc[1], loc[2], rot["yaw"],
                      rot["pitch"], still["bytes"], still["path"]))
            self._next_still()
            return
        raise RuntimeError("PASSAGE_STILLS_BAD_PHASE|" + str(phase))


# --------------------------------------------------------------------------
# run lifecycle (engine-free; the adapter and the tick registrar are injected)
# --------------------------------------------------------------------------

def owner_active(owner_path):
    path = pathlib.Path(owner_path)
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("active"))
    except Exception:
        return True                                  # unreadable owner file: assume someone owns PIE


def armed_handles(store):
    return sorted(n for n in dir(store) if n.startswith("PUSS_") and n.endswith("_HANDLE"))


def arm(adapter, passage, fractions, label=None, params=None, out_root=OUT_ROOT, owner_path=OWNER,
        register=None, unregister=None, store=builtins, luma_reader=None, clock=time.monotonic):
    """Validate, plan, write the manifest, then register the tick. Returns the run dict."""
    p = dict(DEFAULTS)
    p.update(params or {})
    tag = re.sub(r"[^A-Za-z0-9_-]+", "", str(label or ""))[:24]
    pass_tag = re.sub(r"[^A-Za-z0-9]+", "", str(passage))[:4].upper() or "X"
    run_id = "PSTILLS-%s-%s%s" % (pass_tag, utc_stamp(), ("-" + tag) if tag else "")
    adapter.log("PASSAGE_STILLS_START|run=%s|passage=%s|fractions=%s" % (run_id, passage, json.dumps(fractions)))

    def refuse(exc):
        tagged = StillsRefused(exc.reason, exc.detail, run_id)
        adapter.log_error(str(tagged))
        raise tagged from exc

    try:
        n, seg_label = passage_label(passage)
        fr = validate_fractions(fractions)
        if adapter.world_kind() != "game":
            raise StillsRefused("no_pie", "start PIE first (conductor_pie_begin.py)")
        handles = armed_handles(store)
        if handles:
            raise StillsRefused("tick_armed", ",".join(handles))
        if owner_active(owner_path):
            raise StillsRefused("pie_owner_active", pathlib.Path(owner_path).as_posix())
        start, end = adapter.passage_segment(seg_label)
        census_before = adapter.census()
        run_dir = pathlib.Path(out_root) / run_id
        stills = plan_stills(start, end, fr, run_dir)
    except StillsRefused as exc:
        refuse(exc)
    except Exception as exc:                           # an Unreal read failed while arming
        refuse(StillsRefused("arm_error", "%s: %s" % (type(exc).__name__, exc)))
    original_frame = int(adapter.transport_frame())
    was_playing = bool(adapter.is_playing())
    run_dir.mkdir(parents=True, exist_ok=False)
    run = {"run_id": run_id, "run_dir": run_dir.as_posix(), "passage": (seg_label[:1] + "%02d" % n) if seg_label.startswith("Scene") else "P%02d" % n, "segment_label": seg_label,
           "segment": {"start": int(start), "end": int(end)}, "label": tag or None, "fractions": fr,
           "params": p, "census_before": census_before, "original_frame": original_frame,
           "was_playing": was_playing, "world": adapter.world_name(), "started_utc": utc_iso(),
           "route": "master_scrub (ScrubToMasterFrame) + live camera pose read; no actor moved",
           "stills": stills, "status": "armed", "errors": []}
    manifest = run_dir / MANIFEST_NAME
    write_verified(manifest, run)                      # plan on disk before the first change
    machine = StillsMachine(adapter, run, p, luma_reader=luma_reader, clock=clock)
    run["_t_start"] = clock()
    holder = {"handle": None}

    def finish(status_hint):
        run["status"] = "finishing"
        problems = []
        if run.get("screen_messages_disabled"):
            try:
                adapter.console("EnableAllScreenMessages")
                run["screen_messages_restored"] = True
            except Exception:
                problems.append("screen messages not restored: " + traceback.format_exc())
        try:
            if adapter.world_kind() == "game":
                res = adapter.transport_scrub(original_frame)
                run["restore_scrub"] = {"frame": original_frame, "result": str(res),
                                        "landed": int(adapter.transport_frame())}
            else:
                run["restore_scrub"] = {"skipped": "PIE gone"}
        except Exception:
            run["restore_scrub"] = {"error": traceback.format_exc()}
        census_after = adapter.census()
        run["census_after"] = census_after
        if census_after != census_before:
            problems.append("census changed %r -> %r" % (census_before, census_after))
        for s in stills:
            path = pathlib.Path(s["path"])
            s["exists"] = path.is_file()
            s["bytes"] = path.stat().st_size if s["exists"] else 0
            if not s["exists"] or s["bytes"] <= int(p["file_min_bytes"]):
                problems.append("missing or undersized still: " + s["path"])
        gates = list(machine.st["gate_failures"])
        run["gate_failures"] = gates
        run["problems"] = problems
        run["finished_utc"] = utc_iso()
        ok = status_hint == "complete" and machine.done and not problems and not gates and not run["errors"]
        run["status"] = "passed" if ok else "failed"
        out = {k: v for k, v in run.items() if not k.startswith("_")}
        try:
            write_verified(manifest, out)
        except Exception:
            ok = False
            problems.append("manifest write/readback failed: " + traceback.format_exc())
        if unregister is not None and holder["handle"] is not None:
            unregister(holder["handle"])
        if hasattr(store, HANDLE_NAME):
            delattr(store, HANDLE_NAME)
        if ok and all(pathlib.Path(s["path"]).is_file() for s in stills):
            adapter.log("PASSAGE_STILLS_OK|run=%s|n=%d|dir=%s" % (run_id, len(stills), run_dir.as_posix()))
        else:
            reasons = [r.split(" ")[0].split(":")[0] for r in (problems + gates)] or [status_hint]
            if run["errors"]:
                reasons.insert(0, run.get("error_reason", "error"))
            adapter.log_error("PASSAGE_STILLS_FAILED|run=%s|reason=%s|problems=%r|gate_failures=%r|manifest=%s" % (
                run_id, ";".join(reasons), problems, gates, manifest.as_posix()))
        run["finished"] = True

    def tick(_delta=0.0):
        if run.get("inside") or run.get("finished"):
            return
        run["inside"] = True
        try:
            now = clock()
            limit = float(p["run_timeout_s_per_still"]) * len(stills) + 30.0
            if now - run["_t_start"] > limit:
                raise StillsRefused("run_timeout", "%.0f s" % limit)
            machine.step(now)
            if machine.done:
                finish("complete")
        except Exception as exc:
            run["errors"].append(traceback.format_exc())
            run["error_reason"] = getattr(exc, "reason", type(exc).__name__)
            try:
                finish("error")
            except Exception:
                run["errors"].append(traceback.format_exc())
                run["finished"] = True
                adapter.log_error("PASSAGE_STILLS_FAILED|run=%s|reason=finish_raised" % run_id)
        finally:
            run["inside"] = False

    if p["screen_messages"] == "off":
        adapter.console("DisableAllScreenMessages")
        run["screen_messages_disabled"] = True
        run["screen_messages_restored"] = False
    run["status"] = "capturing"
    setattr(store, STATE_NAME, run)
    if register is not None:
        holder["handle"] = register(tick)
        setattr(store, HANDLE_NAME, holder["handle"])
    adapter.log("PASSAGE_STILLS_ARMED|run=%s|passage=%s|n=%d|segment=%d..%d|dir=%s" % (
        run_id, run["passage"], len(stills), start, end, run_dir.as_posix()))
    run["_tick"] = tick
    return run


# --------------------------------------------------------------------------
# Unreal side. Everything below runs only inside the editor.
# --------------------------------------------------------------------------

def make_pie_adapter(unreal):
    """Read + transport operations on the CURRENT PIE world. Unreal refs live only here."""
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    first = editor_sub.get_game_world()
    first_name = first.get_path_name() if first is not None else None

    def live_world():
        world = editor_sub.get_game_world()
        if world is None or first_name is None or world.get_path_name() != first_name:
            return None
        return world

    def show_root():
        world = live_world()
        if world is None:
            raise StillsRefused("pie_ended", "no PIE world")
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
        if len(roots) != 1 or not roots[0].sequence_player:
            raise StillsRefused("no_show_root", "runtime Show Roots: %d" % len(roots))
        return roots[0]

    class PieAdapter:
        def world_kind(self):
            return "game" if live_world() is not None else None

        def world_name(self):
            return first_name

        def log(self, message):
            unreal.log(message)

        def log_error(self, message):
            unreal.log_error(message)

        def census(self):
            return {"maps": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
                    "content": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}

        def passage_segment(self, label):
            if label == "Opening":                     # 8 Oct: 'Opening — Curtain' (any cue type)
                segs = [s for s in list(show_root().transport.segments) if str(s.label).startswith("Opening")]
            elif label.startswith("Scene "):
                segs = [s for s in list(show_root().transport.segments)
                        if s.type == unreal.InfinityCueType.SCENE and (str(s.label) == label or str(s.label).startswith(label + " "))]
            else:
                segs = [s for s in list(show_root().transport.segments)
                        if s.type == unreal.InfinityCueType.WING_PAIR and str(s.label) == label]
            if len(segs) != 1:
                raise StillsRefused("no_segment", "%s segments: %d" % (label, len(segs)))
            return int(segs[0].start_frame.value), int(segs[0].end_frame.value)

        def transport_scrub(self, frame):
            root = show_root()
            root.sequence_player.pause()
            return root.transport.scrub_to_master_frame(unreal.FrameNumber(int(frame)))

        def transport_pause(self):
            show_root().sequence_player.pause()

        def transport_frame(self):
            return int(show_root().transport.get_current_master_frame().value)

        def is_playing(self):
            return bool(show_root().transport.is_transport_playing())

        def camera_pose(self, aspect, fov_fallback):
            """look_bench.py:1564-1576 (PlayerCameraManager GetCameraLocation/Rotation/FOVAngle)."""
            world = live_world()
            cam = unreal.GameplayStatics.get_player_camera_manager(world, 0) if world is not None else None
            if cam is None:
                return None
            loc, rot = cam.get_camera_location(), cam.get_camera_rotation()
            fov = float(cam.get_fov_angle() or 0.0)
            return {"loc": [float(loc.x), float(loc.y), float(loc.z)],
                    "rot": {"yaw": float(rot.yaw), "pitch": float(rot.pitch), "roll": float(rot.roll)},
                    "fov_deg": fov if fov > 1.0 else float(fov_fallback), "fov_read": fov, "aspect": float(aspect)}

        def console(self, command):
            world = live_world()
            if world is None:
                raise StillsRefused("pie_ended", "console with no PIE world")
            unreal.SystemLibrary.execute_console_command(world, command)

    return PieAdapter()


def main():
    import unreal
    g = globals()
    passage = g.get("STILLS_PASSAGE")
    fractions = g.get("STILLS_FRACTIONS", list(DEFAULT_FRACTIONS))
    label = g.get("STILLS_LABEL")
    params = dict(g.get("STILLS_PARAMS", {}) or {})
    adapter = make_pie_adapter(unreal)
    return arm(adapter, passage, fractions, label, params,
               register=unreal.register_slate_post_tick_callback,
               unregister=unreal.unregister_slate_post_tick_callback)["run_dir"]


if __name__ == "__main__" or "STILLS_PASSAGE" in globals():
    main()
