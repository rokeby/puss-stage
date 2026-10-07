"""P04 RAIN PIE BENCH: does Cascade render in UE 5.8, and does Rain2 read in P04? PIE-ONLY, NOTHING SAVED.
OFFLINE-WRITTEN 7 Oct, never run. Gary approved (7 Oct, own words) "Rain on P04" with a PIE test first.

RUNS INSIDE THE CONDUCTOR'S OWN PIE. Start it with ../conductor_pie_begin.py (refuses if PIE already runs). This bench
NEVER begins or ends PIE, never quits, never saves, never reloads a level and never spawns an ACTOR (harness scan).
It arms only with args confirm "CONDUCTOR PIE P04RAIN" (the operator's statement that this PIE is the conductor's,
not Gary's), with no other PUSS_*_HANDLE armed, no active pie_recording_owner.json and an empty live ledger.

WHAT IT DOES (per still i at Passage fraction f; default P04 at 0.25 / 0.5 / 0.75):
  scrub the Master to f (UInfinityStageTransportController::ScrubToMasterFrame, the passage_stills.py route), re-scrub
  after repose_seconds (a jump's first frame can be stale), read the live camera pose, then capture in order:
    off_a            nothing spawned                                  baseline
    rain             Rain2 emitters ahead of the camera, warmed       the measurement
    rain_noparticles same emitters, console ShowFlag.Particles 0      NEGATIVE control: the rain difference must vanish
    off_b            emitters destroyed, Particles 1                  NEGATIVE control: off_a vs off_b = noise floor
    alt              Humo_Par (the SmokePot plume) ahead, warmed      FALLBACK: a second Cascade system
    ctrl             nothing spawned, console ShowFlag.Lighting 0     POSITIVE control: the capture sees a change
  Each capture = settle (small HighResShot probes until the mean luma is stable, passage_stills.settle_decision) ->
  full-res HighResShot -> file stable. Then everything spawned is destroyed and both show flags are restored.
  Emitters are actor-less ParticleSystemComponents in the PIE world via GameplayStatics::SpawnEmitterAtLocation
  (Engine/Classes/Kismet/GameplayStatics.h:533-534; bAutoDestroy False, EPSCPoolMethod::None) [declaration-proven];
  the PIE world dies with PIE, the backstop for a crash mid-run [inferred: standard PIE teardown].

THE MEASURE ("renders"), computed on the settled probes (fast, in-editor) and recomputable on the full stills
offline:  python p04_rain_pie_bench.py analyse <run_dir> [--full]
  noise    = MAD(off_a, off_b)                    mean |pixel difference| per channel, 0..255
  seen(v)  = min(MAD(v, off_a), MAD(v, off_b)) > max(k_noise * noise, min_mad)
  a still is VALID when noise <= max_noise_mad AND seen(ctrl) with MAD >= min_ctrl_mad (else captures are stale or the
  scene is not static) AND, for the rain verdict, NOT seen(rain_noparticles) (the difference is particle rendering).
  verdict per system over valid stills: RENDERS (seen in >= 2/3), NOT_SEEN (seen in none), else UNCLEAR; no valid
  still -> INVALID. Mean-luma deltas (v - mean(off_a, off_b)) are reported alongside, as asked.
  NOT_SEEN for both Rain2 and Humo_Par with valid controls = "Cascade does not render at these placements in 5.8"
  [measured, for these placements only]; Humo_Par RENDERS but Rain2 NOT_SEEN = Rain2 specifically (scale / bounds /
  placement / material), not Cascade.

PLACEMENT (camera frame: forward, right, up cm from the live camera pose; yaw/pitch from the pose):
  rain_offsets_cm default 4 emitters 6-24 m ahead, 2.5 m above the eye. Rain2's own spawn volume and fall speed are
  UNKNOWN (its emitters are protected from Python: fx_content_probe.json) [measured unreadable]; so the scale and
  offsets are args. Every spawn is read back (valid, active, template, world location, inside the view frustum).

ARGS p04_rain_pie_bench_args.json: {"mode": "RUN"|"TEARDOWN", "confirm": "CONDUCTOR PIE P04RAIN", "params": {...}}
  TEARDOWN (PIE): destroys every component in the live ledger and restores Particles/Lighting show flags.
MARKERS P04RAINPIE_START / _ARMED / _CAPTURE|i=..|name=.. / _OK|run=..|rain=..|alt=.. / _FAILED|run=..|reason=..
  / _TEARDOWN_OK. OK only after: every still file exists, nothing spawned is left valid, the editor census
  (UEDPIE_ packages excluded) is unchanged, and the manifest read back.
Outputs: Effects_20261007/P04RainPIE/<run>/ (stills, _probes/, manifest.json); live ledger
Effects_20261007/p04_rain_pie_bench_live.json (written BEFORE each spawn and after each destroy).
"""
from __future__ import annotations

import builtins
import json
import math
import pathlib
import re
import struct
import sys
import time
import traceback
import zlib

HERE = pathlib.Path(__file__).resolve().parent if "__file__" in globals() else pathlib.Path(
    "E:/PussStage/Saved/CodexConductor/Effects_20261007")
BASE = HERE.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
import passage_stills as ps  # noqa: E402  (pure helpers + make_pie_adapter; no unreal import at module level)

OUT_ROOT = HERE / "P04RainPIE"
LEDGER = HERE / "p04_rain_pie_bench_live.json"
OWNER = BASE / "pie_recording_owner.json"
HANDLE_NAME = "PUSS_P04RAINPIE_HANDLE"
STATE_NAME = "PUSS_P04RAINPIE_STATE"
MANIFEST_NAME = "manifest.json"
MARK = "P04RAINPIE"
CONFIRM = "CONDUCTOR PIE P04RAIN"
DEFAULT_FLAGS = {"Particles": 1, "Lighting": 1}
SPECS = {   # name -> (spawn kind or None, show-flag overrides)
    "off_a": (None, {}),
    "rain": ("rain", {}),
    "rain_noparticles": ("rain", {"Particles": 0}),
    "off_b": (None, {}),
    "alt": ("alt", {}),
    "ctrl": (None, {"Lighting": 0}),
}
REQUIRED = ("off_a", "off_b", "ctrl")
DEFAULTS = {
    "passage": "P04",
    "fractions": [0.25, 0.5, 0.75],
    "captures": ["off_a", "rain", "rain_noparticles", "off_b", "alt", "ctrl"],
    "rain_template": "/Game/Japanese_Alley/VFX/Rain2",
    "alt_template": "/Game/Japanese_Alley/VFX/Humo_Par",
    "rain_offsets_cm": [[600.0, 0.0, 250.0], [1400.0, -300.0, 250.0], [1400.0, 300.0, 250.0], [2400.0, 0.0, 250.0]],
    "alt_offsets_cm": [[700.0, 0.0, -150.0]],      # ~30 cm over the floor at a 180 cm eye (P04 stills pose z 180)
    "scale": 1.0,
    "warm_seconds": 3.0,
    "flag_seconds": 1.0,
    "repose_seconds": 1.0,
    "settle_min_seconds": 1.5,
    "settle_max_seconds": 12.0,
    "settle_window": 3,
    "settle_tol_abs": 2.0,
    "settle_tol_rel": 0.03,
    "probe_interval_s": 0.5,
    "probe_timeout_s": 4.0,
    "probe_resolution": [256, 144],
    "resolution": [1600, 900],
    "file_min_bytes": 1000,
    "file_stable_ticks": 4,
    "file_timeout_s": 45.0,
    "frame_tol_ticks": 1,
    "fov_fallback_deg": 90.0,
    "k_noise": 3.0,
    "min_mad": 0.4,
    "max_noise_mad": 2.0,
    "min_ctrl_mad": 4.0,
    "run_timeout_s": 900.0,
    "screen_messages": "off",
}


class RainPieRefused(RuntimeError):
    def __init__(self, reason, detail="", run="?"):
        self.reason, self.detail = reason, str(detail)
        super().__init__("%s_FAILED|run=%s|reason=%s%s" % (MARK, run, reason, ("|" + self.detail) if detail else ""))


# --------------------------------------------------------------------------------------------- pure (offline-tested)
def params_of(overrides=None):
    p = json.loads(json.dumps(DEFAULTS))
    for k, v in (overrides or {}).items():
        if k not in DEFAULTS:
            raise RainPieRefused("bad_param", k)
        p[k] = v
    caps = p["captures"]
    if not isinstance(caps, list) or len(set(caps)) != len(caps) or not set(caps) <= set(SPECS):
        raise RainPieRefused("bad_captures", repr(caps))
    missing = [c for c in REQUIRED if c not in caps]
    if missing:
        raise RainPieRefused("controls_removed", "captures must keep %s" % missing)
    for key in ("rain_offsets_cm", "alt_offsets_cm"):
        offs = p[key]
        if not isinstance(offs, list) or not 1 <= len(offs) <= 8 or not all(
                isinstance(o, list) and len(o) == 3 and all(isinstance(x, (int, float)) and math.isfinite(x)
                                                            and abs(x) <= 6000 for x in o) for o in offs):
            raise RainPieRefused("bad_offsets", key)
    if not (isinstance(p["scale"], (int, float)) and 0.1 <= float(p["scale"]) <= 20.0):
        raise RainPieRefused("bad_scale", p["scale"])
    for key in ("rain_template", "alt_template"):
        if not str(p[key]).startswith("/Game/"):
            raise RainPieRefused("bad_template", key)
    ps.validate_fractions(p["fractions"])
    return p


def check_confirm(args):
    if not isinstance(args, dict) or args.get("confirm") != CONFIRM:
        raise RainPieRefused("confirm_missing", "args confirm must be '%s' (this PIE is the conductor's own)" % CONFIRM)
    return True


def transition(cur, want):
    """cur/want: {"spawn": None|"rain"|"alt", "flags": {name: 0|1}} -> ordered actions:
    destroy the old spawn, set changed flags, spawn the new kind."""
    acts = []
    if cur.get("spawn") and cur.get("spawn") != want.get("spawn"):
        acts.append(("destroy", cur["spawn"]))
    names = sorted(set(cur.get("flags", {})) | set(want.get("flags", {})))
    for n in names:
        a = cur.get("flags", {}).get(n, DEFAULT_FLAGS[n])
        b = want.get("flags", {}).get(n, DEFAULT_FLAGS[n])
        if a != b:
            acts.append(("flag", n, b))
    if want.get("spawn") and want.get("spawn") != cur.get("spawn"):
        acts.append(("spawn", want["spawn"]))
    return acts


def want_state(name):
    kind, flags = SPECS[name]
    return {"spawn": kind, "flags": dict(flags)}


OFF_STATE = {"spawn": None, "flags": {}}


def wait_for(acts, p):
    if any(a[0] == "spawn" for a in acts):
        return float(p["warm_seconds"])
    if any(a[0] in ("flag", "destroy") for a in acts):
        return float(p["flag_seconds"])
    return 0.0


def camera_basis(pose):
    yaw = math.radians(float(pose["rot"]["yaw"]))
    pitch = math.radians(float(pose["rot"].get("pitch", 0.0)))
    fwd = [math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)]
    right = [-math.sin(yaw), math.cos(yaw), 0.0]              # UE: yaw 0 -> forward +X, right +Y
    up = [-math.sin(pitch) * math.cos(yaw), -math.sin(pitch) * math.sin(yaw), math.cos(pitch)]
    return fwd, right, up


def world_points(pose, offsets):
    fwd, right, up = camera_basis(pose)
    c = [float(v) for v in pose["loc"]]
    return [[c[k] + o[0] * fwd[k] + o[1] * right[k] + o[2] * up[k] for k in range(3)] for o in offsets]


def in_view(pose, point, aspect):
    fwd, right, up = camera_basis(pose)
    d = [float(point[k]) - float(pose["loc"][k]) for k in range(3)]
    z = sum(d[k] * fwd[k] for k in range(3))
    if z <= 1.0:
        return False
    x = sum(d[k] * right[k] for k in range(3))
    y = sum(d[k] * up[k] for k in range(3))
    tan_h = math.tan(math.radians(float(pose.get("fov_deg") or 90.0)) / 2.0)
    return abs(x) <= z * tan_h and abs(y) <= z * tan_h / float(aspect)


def census_filtered(c):
    return {k: sorted(x for x in c.get(k, []) if "UEDPIE_" not in str(x)) for k in ("maps", "content")}


def seen(d, noise, p):
    return d is not None and d > max(float(p["k_noise"]) * float(noise), float(p["min_mad"]))


def still_measure(caps, mad, p):
    """caps: {name: {"luma": float|None, "img": path}}; mad(path_a, path_b) -> float. Returns the per-still row."""
    row = {"captures": sorted(caps), "mad": {}, "luma_delta": {}, "problems": []}
    noise = mad(caps["off_a"]["img"], caps["off_b"]["img"])
    row["noise_mad"] = round(noise, 4)
    base_l = [caps[n]["luma"] for n in ("off_a", "off_b") if caps[n].get("luma") is not None]
    base = sum(base_l) / len(base_l) if base_l else None
    for name in caps:
        if name in ("off_a", "off_b"):
            continue
        d = min(mad(caps[name]["img"], caps["off_a"]["img"]), mad(caps[name]["img"], caps["off_b"]["img"]))
        row["mad"][name] = round(d, 4)
        row["luma_delta"][name] = (round(caps[name]["luma"] - base, 3)
                                   if base is not None and caps[name].get("luma") is not None else None)
    row["seen"] = {n: seen(d, noise, p) for n, d in row["mad"].items()}
    if noise > float(p["max_noise_mad"]):
        row["problems"].append("scene_not_static|noise_mad=%.3f>%.3f" % (noise, float(p["max_noise_mad"])))
    ctrl = row["mad"].get("ctrl")
    if ctrl is None or ctrl < float(p["min_ctrl_mad"]) or not row["seen"].get("ctrl"):
        row["problems"].append("positive_control_failed|ctrl_mad=%s" % ctrl)
    row["valid"] = not row["problems"]
    row["rain_attributable"] = ("rain_noparticles" not in row["mad"]) or not row["seen"]["rain_noparticles"]
    return row


def verdict(rows):
    """rows: still_measure rows -> {"rain": .., "alt": .., "valid_stills": n, ...}."""
    valid = [r for r in rows if r["valid"]]
    out = {"valid_stills": len(valid), "stills": len(rows)}
    for system in ("rain", "alt"):
        use = [r for r in valid if system in r["mad"] and (system != "rain" or r["rain_attributable"])]
        if not any(system in r["mad"] for r in rows):
            out[system] = "NOT_RUN"
            continue
        if not use:
            out[system] = "INVALID" if not valid else "UNCLEAR"
            out[system + "_why"] = "no valid still" if not valid else "rain difference survived ShowFlag.Particles 0"
            continue
        hits = sum(1 for r in use if r["seen"][system])
        out[system + "_seen_in"] = "%d/%d" % (hits, len(use))
        if hits == 0:
            out[system] = "NOT_SEEN"
        elif 3 * hits >= 2 * len(use):
            out[system] = "RENDERS"
        else:
            out[system] = "UNCLEAR"
    return out


def png_rows(path):
    """(w, h, bpp, rows) of an 8-bit non-interlaced PNG; passage_stills.png_luma's decoder, keeping the rows
    (same as ../p04_rain_bench.py png_pixels)."""
    data = pathlib.Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, head = 8, [], None
    while pos + 8 <= len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        typ, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if typ == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    w, h, depth, ctype, _c, _f, interlace = head
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 4, 6):
        raise ValueError("unsupported PNG")
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride = w * bpp
    prev, rows = bytearray(stride), []
    for y in range(h):
        base = y * (stride + 1)
        ft = raw[base]
        line = bytearray(raw[base + 1:base + 1 + stride])
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ft == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif ft == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 255
        elif ft != 0:
            raise ValueError("bad filter")
        rows.append(bytes(line))
        prev = line
    return w, h, bpp, rows


def mean_abs_diff(path_a, path_b):
    wa, ha, ba, ra = png_rows(path_a)
    wb, hb, bb, rb = png_rows(path_b)
    if (wa, ha, ba) != (wb, hb, bb):
        raise ValueError("size mismatch %s vs %s" % ((wa, ha, ba), (wb, hb, bb)))
    tot = 0
    for x, y in zip(ra, rb):
        tot += sum(abs(i - j) for i, j in zip(x, y))
    return tot / float(wa * ha * ba)


def analyse(run, p, mad=mean_abs_diff, use_full=False):
    rows = []
    for still in run["stills"]:
        caps = {}
        for name, c in still["captures"].items():
            img = c.get("path") if use_full else c.get("probe")
            if c.get("phase") == "captured" and img:
                caps[name] = {"luma": c.get("luma"), "img": img}
        if not all(n in caps for n in REQUIRED):
            rows.append({"i": still["i"], "valid": False, "problems": ["captures_missing|%s" % sorted(caps)],
                         "mad": {}, "seen": {}, "rain_attributable": False})
            continue
        row = still_measure(caps, mad, p)
        row["i"] = still["i"]
        rows.append(row)
    return {"rows": rows, "verdict": verdict(rows), "images": "full" if use_full else "probes"}


def write_verified(path, data):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    return ps.write_verified(path, data)


def ledger_read(path=LEDGER):
    path = pathlib.Path(path)
    if not path.is_file():
        return {"run": None, "live": []}
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------- engine-free state machine
class BenchMachine:
    """jump -> repose -> [prepare -> wait -> settle -> capture -> wait_file] per capture -> next still."""

    def __init__(self, adapter, run, p, ledger_path=LEDGER, luma_reader=None):
        self.a, self.run, self.p = adapter, run, p
        self.ledger_path = pathlib.Path(ledger_path)
        self.read_luma = luma_reader or ps.png_luma
        self.st = {"phase": "jump", "i": 0, "k": 0, "probe_n": 0}
        self.state = {"spawn": None, "flags": {}}
        self.done = False
        self.flags_touched = set()

    # ledger: what is alive in PIE right now, on disk before every spawn and after every destroy
    def _ledger(self):
        return ledger_read(self.ledger_path)

    def _ledger_write(self, live):
        write_verified(self.ledger_path, {"run": self.run["run_id"], "live": live})

    def _still(self):
        return self.run["stills"][self.st["i"]]

    def _cap(self):
        return self._still()["captures"][self.p["captures"][self.st["k"]]]

    def apply_actions(self, acts, pose):
        for act in acts:
            if act[0] == "destroy":
                live = self._ledger()["live"]
                keep = []
                for row in live:
                    if row["kind"] != act[1]:
                        keep.append(row)
                        continue
                    if row.get("path") and not self.a.destroy(row["path"]):
                        raise RainPieRefused("destroy_failed", row["path"], self.run["run_id"])
                self._ledger_write(keep)
            elif act[0] == "flag":
                self.a.console("ShowFlag.%s %d" % (act[1], int(act[2])))
                self.flags_touched.add(act[1])
            elif act[0] == "spawn":
                kind = act[1]
                template = self.p[kind + "_template"]
                points = world_points(pose, self.p[kind + "_offsets_cm"])
                yaw = float(pose["rot"]["yaw"])
                spawned = []
                for j, pt in enumerate(points):
                    live = self._ledger()["live"]
                    intent = {"kind": kind, "j": j, "template": template, "loc": [round(v, 2) for v in pt],
                              "path": None}
                    self._ledger_write(live + [intent])           # intent on disk BEFORE the spawn
                    path = self.a.spawn_emitter(template, pt, yaw, float(self.p["scale"]))
                    intent["path"] = path
                    self._ledger_write(live + [intent])
                    rb = self.a.readback(path)
                    rb["in_view"] = in_view(pose, pt, float(self.p["resolution"][0]) / float(self.p["resolution"][1]))
                    spawned.append(dict(intent, readback=rb))
                    if not rb.get("valid") or rb.get("template") != template:
                        raise RainPieRefused("spawn_readback", json.dumps(rb), self.run["run_id"])
                self._cap()["spawned"] = spawned
        return acts

    def to_state(self, want, pose):
        acts = transition(self.state, want)
        self.apply_actions(acts, pose)
        self.state = {"spawn": want["spawn"], "flags": dict(want["flags"])}
        return acts

    def _probe(self, now, name):
        d = pathlib.Path(self.run["run_dir"]) / "_probes"
        d.mkdir(parents=True, exist_ok=True)
        self.st["probe_n"] += 1
        path = (d / ("%02d_%s_%03d.png" % (self.st["i"], name, self.st["probe_n"]))).as_posix()
        w, h = self.p["probe_resolution"]
        self.a.console('HighResShot %dx%d filename="%s"' % (w, h, path))
        self.st["pending"] = {"path": path, "t": now}
        self.st["last_issue"] = now

    def _read_pending(self, now):
        pend = self.st.get("pending")
        if not pend:
            return None
        try:
            y = float(self.read_luma(pend["path"]))
        except Exception:  # noqa: BLE001 - HighResShot writes asynchronously
            if now - pend["t"] > float(self.p["probe_timeout_s"]):
                self.st["pending"] = None
                return "timeout"
            return None
        self.st["pending"] = None
        return (y, pend["path"])

    def _scrub(self, still):
        res = self.a.transport_scrub(still["target_frame"])
        still.setdefault("scrub_results", []).append(str(res))
        if not ps.scrub_ok(res):
            raise RainPieRefused("scrub_refused", "i=%d result=%s" % (still["i"], res), self.run["run_id"])

    def step(self, now):
        st, p, a = self.st, self.p, self.a
        if self.done:
            return
        if a.world_kind() != "game":
            raise RainPieRefused("pie_ended", "PIE world gone or replaced mid-run", self.run["run_id"])
        still = self._still()
        phase = st["phase"]
        if phase == "jump":
            self.to_state(OFF_STATE, still.get("pose"))
            a.transport_pause()
            self._scrub(still)
            st.update(phase="repose", t0=now)
            return
        if phase == "repose":
            if now - st["t0"] >= float(p["repose_seconds"]):
                self._scrub(still)
                w, h = p["resolution"]
                pose = a.camera_pose(float(w) / float(h), p["fov_fallback_deg"])
                if pose is None:
                    raise RainPieRefused("no_camera", "", self.run["run_id"])
                still["pose"] = pose
                st.update(phase="prepare", k=0)
            return
        if phase == "prepare":
            name = p["captures"][st["k"]]
            acts = self.to_state(want_state(name), still["pose"])
            self._cap()["actions"] = [list(x) for x in acts]
            st.update(phase="wait", tw=now, wait_s=wait_for(acts, p))
            return
        if phase == "wait":
            if now - st["tw"] >= st["wait_s"]:
                st.update(phase="settle", t0=now, samples=[], pending=None, last_issue=None, last_probe=None)
            return
        if phase == "settle":
            el = now - st["t0"]
            got = self._read_pending(now)
            if isinstance(got, tuple):
                st["samples"].append([round(el, 3), round(got[0], 3)])
                st["last_probe"] = got[1]
            if st.get("pending") is None and (st["last_issue"] is None
                                              or now - st["last_issue"] >= float(p["probe_interval_s"])):
                self._probe(now, p["captures"][st["k"]])
            v = ps.settle_decision(st["samples"], el, p)
            if v == "wait":
                return
            cap = self._cap()
            cap["settle"] = {"verdict": v, "seconds": round(el, 3), "samples": list(st["samples"])}
            cap["luma"] = st["samples"][-1][1] if st["samples"] else None
            cap["probe"] = st["last_probe"]
            if v != "stable":
                cap.setdefault("gate_failures", []).append("settle_timeout")
            st.update(phase="capture", pending=None)
            return
        if phase == "capture":
            cap = self._cap()
            frame = int(a.transport_frame())
            cap["master_frame"] = frame
            if abs(frame - still["target_frame"]) > int(p["frame_tol_ticks"]):
                cap.setdefault("gate_failures", []).append("frame %d vs %d" % (frame, still["target_frame"]))
            w, h = p["resolution"]
            a.console('HighResShot %dx%d filename="%s"' % (w, h, cap["path"]))
            st.update(phase="wait_file", issued=now, last_size=-1, stable=0)
            return
        if phase == "wait_file":
            cap = self._cap()
            path = pathlib.Path(cap["path"])
            size = path.stat().st_size if path.is_file() else -1
            if size > int(p["file_min_bytes"]) and size == st["last_size"]:
                st["stable"] += 1
            else:
                st["stable"], st["last_size"] = 0, size
            if st["stable"] >= int(p["file_stable_ticks"]):
                cap.update(bytes=size, phase="captured")
                a.log("%s_CAPTURE|run=%s|i=%d|name=%s|luma=%s|path=%s" % (
                    MARK, self.run["run_id"], still["i"], p["captures"][st["k"]], cap.get("luma"), cap["path"]))
                st["k"] += 1
                if st["k"] < len(p["captures"]):
                    st["phase"] = "prepare"
                    return
                self.to_state(OFF_STATE, still["pose"])
                st["i"] += 1
                if st["i"] >= len(self.run["stills"]):
                    st["phase"] = "done"
                    self.done = True
                else:
                    st["phase"] = "jump"
                return
            if now - st["issued"] > float(p["file_timeout_s"]):
                raise RainPieRefused("capture_timeout", cap["path"], self.run["run_id"])
            return
        raise RuntimeError("%s_BAD_PHASE|%s" % (MARK, phase))

    def cleanup(self):
        """Destroy everything in the ledger, restore every show flag this run touched. Returns problems."""
        problems = []
        live = self._ledger()["live"]
        for row in live:
            if row.get("path"):
                try:
                    if not self.a.destroy(row["path"]):
                        problems.append("destroy_failed|" + row["path"])
                except Exception:  # noqa: BLE001
                    problems.append("destroy_raised|%s|%s" % (row["path"], traceback.format_exc(limit=1)))
        left = [r for r in live if r.get("path") and self.a.is_live(r["path"])]
        if left:
            problems.append("left_alive|%s" % [r["path"] for r in left])
        else:
            self._ledger_write([])
        for n in sorted(self.flags_touched | set(self.state.get("flags", {}))):
            try:
                self.a.console("ShowFlag.%s %d" % (n, DEFAULT_FLAGS[n]))
            except Exception:  # noqa: BLE001
                problems.append("flag_not_restored|" + n)
        self.state = {"spawn": None, "flags": {}}
        return problems


def plan_run(run_id, run_dir, segment, p):
    start, end = segment
    stills = ps.plan_stills(start, end, ps.validate_fractions(p["fractions"]), run_dir)
    out = []
    for s in stills:
        caps = {n: {"path": (pathlib.Path(run_dir) / ("%02d_%s.png" % (s["i"], n))).as_posix(), "phase": "pending"}
                for n in p["captures"]}
        out.append({"i": s["i"], "fraction": s["fraction"], "target_frame": s["target_frame"],
                    "seconds_into_passage": s["seconds_into_passage"], "captures": caps})
    return out


def arm(adapter, args, out_root=OUT_ROOT, owner_path=OWNER, ledger_path=LEDGER, register=None, unregister=None,
        store=builtins, luma_reader=None, mad=mean_abs_diff, clock=time.monotonic):
    run_id = "P04RAINPIE-%s" % ps.utc_stamp()
    adapter.log("%s_START|run=%s" % (MARK, run_id))
    try:
        check_confirm(args)
        p = params_of(args.get("params"))
        n, seg_label = ps.passage_label(p["passage"])
        if adapter.world_kind() != "game":
            raise RainPieRefused("no_pie", "start the conductor's PIE first (conductor_pie_begin.py)")
        handles = ps.armed_handles(store)
        if handles:
            raise RainPieRefused("tick_armed", ",".join(handles))
        if ps.owner_active(owner_path):
            raise RainPieRefused("pie_owner_active", pathlib.Path(owner_path).as_posix())
        if ledger_read(ledger_path)["live"]:
            raise RainPieRefused("ledger_not_empty", "run mode TEARDOWN first: %s" % pathlib.Path(ledger_path).as_posix())
        segment = adapter.passage_segment(seg_label)
        census_before = adapter.census()
        run_dir = pathlib.Path(out_root) / run_id
        stills = plan_run(run_id, run_dir, segment, p)
    except RainPieRefused as exc:
        tagged = RainPieRefused(exc.reason, exc.detail, run_id)
        adapter.log_error(str(tagged))
        raise tagged from exc
    except Exception as exc:  # noqa: BLE001
        tagged = RainPieRefused("arm_error", "%s: %s" % (type(exc).__name__, exc), run_id)
        adapter.log_error(str(tagged))
        raise tagged from exc
    run_dir.mkdir(parents=True, exist_ok=False)
    run = {"run_id": run_id, "run_dir": run_dir.as_posix(), "passage": "P%02d" % n, "segment_label": seg_label,
           "segment": list(segment), "params": p, "census_before": census_before,
           "original_frame": int(adapter.transport_frame()), "was_playing": bool(adapter.is_playing()),
           "world": adapter.world_name(), "started_utc": ps.utc_iso(), "stills": stills, "status": "armed",
           "errors": [], "route": "master scrub + live pose; actor-less Cascade PSCs in PIE; nothing saved"}
    manifest = run_dir / MANIFEST_NAME
    write_verified(manifest, run)
    write_verified(ledger_path, {"run": run_id, "live": []})
    machine = BenchMachine(adapter, run, p, ledger_path=ledger_path, luma_reader=luma_reader)
    t_start = clock()
    holder = {"handle": None}

    def finish(hint):
        problems = machine.cleanup()
        if run.get("screen_messages_disabled"):
            try:
                adapter.console("EnableAllScreenMessages")
            except Exception:  # noqa: BLE001
                problems.append("screen_messages_not_restored")
        try:
            if adapter.world_kind() == "game":
                res = adapter.transport_scrub(run["original_frame"])
                run["restore_scrub"] = {"frame": run["original_frame"], "result": str(res)}
        except Exception:  # noqa: BLE001
            run["restore_scrub"] = {"error": traceback.format_exc(limit=2)}
        after = adapter.census()
        run["census_after"] = after
        if census_filtered(after) != census_filtered(census_before):
            problems.append("census_changed|%r->%r" % (census_before, after))
        for s in stills:
            for name, c in s["captures"].items():
                path = pathlib.Path(c["path"])
                if not path.is_file() or path.stat().st_size <= int(p["file_min_bytes"]):
                    problems.append("missing_still|%s" % c["path"])
        try:
            run["analysis"] = analyse(run, p, mad=mad)
        except Exception:  # noqa: BLE001
            run["analysis"] = {"error": traceback.format_exc(limit=3)}
            problems.append("analysis_failed")
        run["problems"] = problems
        run["finished_utc"] = ps.utc_iso()
        ok = hint == "complete" and machine.done and not problems and not run["errors"]
        run["status"] = "passed" if ok else "failed"
        try:
            write_verified(manifest, {k: v for k, v in run.items() if not k.startswith("_")})
        except Exception:  # noqa: BLE001
            ok = False
        if unregister is not None and holder["handle"] is not None:
            unregister(holder["handle"])
        if hasattr(store, HANDLE_NAME):
            delattr(store, HANDLE_NAME)
        v = (run.get("analysis") or {}).get("verdict", {})
        if ok:
            adapter.log("%s_OK|run=%s|rain=%s|alt=%s|valid_stills=%s|dir=%s" % (
                MARK, run_id, v.get("rain"), v.get("alt"), v.get("valid_stills"), run_dir.as_posix()))
        else:
            adapter.log_error("%s_FAILED|run=%s|reason=%s|problems=%r|verdict=%r|manifest=%s" % (
                MARK, run_id, run.get("error_reason", hint), problems, v, manifest.as_posix()))
        run["finished"] = True

    def tick(_delta=0.0):
        if run.get("inside") or run.get("finished"):
            return
        run["inside"] = True
        try:
            now = clock()
            if now - t_start > float(p["run_timeout_s"]):
                raise RainPieRefused("run_timeout", "%.0f s" % float(p["run_timeout_s"]), run_id)
            machine.step(now)
            if machine.done:
                finish("complete")
        except Exception as exc:  # noqa: BLE001
            run["errors"].append(traceback.format_exc())
            run["error_reason"] = getattr(exc, "reason", type(exc).__name__)
            try:
                finish("error")
            except Exception:  # noqa: BLE001
                run["finished"] = True
                adapter.log_error("%s_FAILED|run=%s|reason=finish_raised|%s" % (MARK, run_id, traceback.format_exc()))
        finally:
            run["inside"] = False

    if p["screen_messages"] == "off":
        adapter.console("DisableAllScreenMessages")
        run["screen_messages_disabled"] = True
    run["status"] = "capturing"
    setattr(store, STATE_NAME, run)
    if register is not None:
        holder["handle"] = register(tick)
        setattr(store, HANDLE_NAME, holder["handle"])
    adapter.log("%s_ARMED|run=%s|passage=%s|stills=%d|captures=%s|dir=%s" % (
        MARK, run_id, run["passage"], len(stills), ",".join(p["captures"]), run_dir.as_posix()))
    run["_tick"] = tick
    return run


def teardown(adapter, ledger_path=LEDGER):
    """PIE: destroy whatever the ledger says is alive and restore both show flags. Never ends PIE."""
    if adapter.world_kind() != "game":
        raise RainPieRefused("no_pie", "nothing to tear down (PIE end already destroyed the PIE world)")
    fake_run = {"run_id": "TEARDOWN-" + ps.utc_stamp()}
    m = BenchMachine(adapter, fake_run, dict(DEFAULTS), ledger_path=ledger_path)
    m.flags_touched = set(DEFAULT_FLAGS)
    problems = m.cleanup()
    if problems:
        adapter.log_error("%s_TEARDOWN_FAILED|%r" % (MARK, problems))
        raise RainPieRefused("teardown", problems)
    adapter.log("%s_TEARDOWN_OK|ledger=%s" % (MARK, pathlib.Path(ledger_path).as_posix()))
    return True


# ---------------------------------------------------------------------------------------------- Unreal side
def make_adapter(unreal):
    """passage_stills.make_pie_adapter (PIE reads, Master scrub, pose, console) + actor-less Cascade components."""
    base = ps.make_pie_adapter(unreal)
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

    def world():
        w = editor_sub.get_game_world()
        if w is None or base.world_kind() != "game":
            raise RainPieRefused("pie_ended")
        return w

    def find(path):
        obj = unreal.find_object(None, path)
        return obj if obj is not None and unreal.SystemLibrary.is_valid(obj) else None

    class Adapter:
        def __getattr__(self, name):
            return getattr(base, name)

        def spawn_emitter(self, template, loc, yaw, scale):
            system = unreal.load_asset(template)
            if not isinstance(system, unreal.ParticleSystem):
                raise RainPieRefused("not_cascade", "%s -> %r" % (template, system))
            comp = unreal.GameplayStatics.spawn_emitter_at_location(
                world(), system, unreal.Vector(*loc), unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(yaw)),
                unreal.Vector(scale, scale, scale), False, unreal.PSCPoolMethod.NONE, True)
            if comp is None:
                raise RainPieRefused("spawn_returned_none", template)
            path = str(comp.get_path_name())
            if "UEDPIE_" not in path:
                comp.destroy_component(comp.get_owner() or comp)
                raise RainPieRefused("spawned_outside_pie", path)
            return path

        def readback(self, path):
            comp = find(path)
            if comp is None:
                return {"valid": False}
            loc = comp.get_world_location()
            tpl = comp.get_editor_property("template")
            return {"valid": True, "active": bool(comp.is_active()),
                    "template": str(tpl.get_path_name()).split(".", 1)[0] if tpl is not None else None,
                    "world_location": [float(loc.x), float(loc.y), float(loc.z)],
                    "class": comp.get_class().get_name()}

        def is_live(self, path):
            return find(path) is not None

        def destroy(self, path):
            comp = find(path)
            if comp is None:
                return True
            try:
                comp.deactivate_immediate()
            except Exception:  # noqa: BLE001
                comp.deactivate()
            comp.destroy_component(comp.get_owner() or comp)
            return find(path) is None

    return Adapter()


def main():
    import unreal
    g = globals()
    args = dict(g.get("BENCH_ARGS") or {})
    adapter = make_adapter(unreal)
    mode = str(args.get("mode", "RUN")).upper()
    if mode == "TEARDOWN":
        return teardown(adapter)
    if mode != "RUN":
        raise RainPieRefused("bad_mode", mode)
    return arm(adapter, args, register=unreal.register_slate_post_tick_callback,
               unregister=unreal.unregister_slate_post_tick_callback)["run_dir"]


def _cli(argv):
    if len(argv) >= 3 and argv[1] == "analyse":
        run_dir = pathlib.Path(argv[2])
        run = json.loads((run_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        res = analyse(run, run["params"], use_full="--full" in argv)
        print(json.dumps(res, indent=1))
        return 0
    print("usage: python p04_rain_pie_bench.py analyse <run_dir> [--full]")
    return 2


if __name__ == "__main__" and "BENCH_ARGS" not in globals():
    sys.exit(_cli(sys.argv))
elif "BENCH_ARGS" in globals():
    main()
