"""Offline harness for the S6 bee swarm: replay, metrics, plots, GIF/MP4, tuning.

Runs the Python mirror (bee_swarm_mirror.py) of the held C++ simulation for 120 s
with a moving, GO1-like camera, then writes to Saved/CodexBeeSwarm/harness/:

  trails_top.png / trails_side.png   trail plots (top-down XY, side XZ)
  swarm_dots.gif (+ swarm_dots.mp4 if ffmpeg is on PATH)
  metrics.json                       all metrics + pass/fail per pre-registered gate
  tuning.json                        every candidate scored (with --tune)
  golden.json                        1-second state for the C++ PythonMirrorGolden test

Usage (CPython 3.10+, numpy, Pillow; no Unreal):
  python Tools/BeeSwarm/bee_swarm_harness.py              # tuned defaults, full outputs
  python Tools/BeeSwarm/bee_swarm_harness.py --tune       # re-run the candidate sweep
  python Tools/BeeSwarm/bee_swarm_harness.py --v2         # the v2 defaults, for comparison
  python Tools/BeeSwarm/bee_swarm_harness.py --golden     # only print/write golden.json
  python Tools/BeeSwarm/bee_swarm_harness.py --selftest   # negative/positive controls

Coordinates are swarm-local cm: origin = the swarm actor, +Z up.  The S6 layout
assumed here (an INFERRED placement, see the runbook): actor 150 cm above the
floor, so the floor is z = -150 and the GO1 camera (55 cm lens height) is z = -95.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bee_swarm_mirror as M  # noqa: E402

PROJECT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(PROJECT, "Saved", "CodexBeeSwarm", "harness")

FLOOR_Z = -150.0
CAMERA_Z = FLOOR_Z + 55.0
FPS = 60
DURATION_S = 120.0

# Pre-registered gates (written before tuning; the tuning may not move them).
GATES = {
    "bounds_violations": ("==", 0),
    "bubble_violations": ("==", 0),
    "return_map_min_recurrence": (">=", 0.01),     # C++ NonRepetitionReturnMap gate
    "bee0_autocorr_10s_abs": ("<", 0.85),          # design gate (BeeSwarmDesign:191)
    "median_dist_to_target_cm": ("between", (50.0, 150.0)),
    "median_speed_cm_s": ("between", (100.0, 300.0)),
    "p90_speed_cm_s": ("between", (250.0, 700.0)),
    "median_heading_rate_deg_s": (">=", 180.0),
    "frac_frames_bee_within_60cm": ("between", (0.30, 0.85)),
    "close_pass_entries_per_min": (">=", 10.0),
    "mean_bees_within_200cm": (">=", 8.0),
    "min_camera_distance_cm": (">=", 24.99),
    "target_p90_speed_cm_s": (">=", 250.0),
}


def camera_path(t):
    """GO1-like lens path: runs in from the dark, then wanders round the candle.

    0-7 s: trots forward along +X from x=-560 (about 1.2 m/s, easing in);
    then a slow figure-of-eight round the candle (r about 1.5-2.5 m) with pauses,
    speed 0-90 cm/s.  Deterministic, smooth (C1) so the camera interpolation in
    Advance sees realistic motion.
    """
    run_end = 7.0
    x_start, x_run_end = -560.0, -180.0
    if t <= run_end:
        u = t / run_end
        ease = u * u * (3.0 - 2.0 * u) * 0.35 + u * 0.65
        x = x_start + (x_run_end - x_start) * ease
        return np.array([x, 0.0, CAMERA_Z + 2.0 * math.sin(t * 9.0)])
    s = t - run_end
    # Stop-and-look: a phase that slows to near zero every ~11 s.
    phase = s * 0.32 - 0.22 * math.sin(s * 2.0 * math.pi / 11.0) * (11.0 / (2.0 * math.pi))
    x = -180.0 * math.cos(phase * 0.5) + 30.0 * math.sin(phase * 1.7)
    y = 210.0 * math.sin(phase) * 0.8 + 25.0 * math.sin(phase * 2.3 + 1.0)
    # Blend from the run's end so the path is continuous at run_end.
    blend = min(1.0, s / 3.0)
    x = (-180.0) * (1.0 - blend) + x * blend
    y = y * blend
    return np.array([x, y, CAMERA_Z + 2.0 * math.sin(t * 9.0)])


def run(params, duration=DURATION_S, fps=FPS, record_every=1, origin=(0.0, 0.0, 0.0),
        camera_fn=camera_path):
    sim = M.Simulation().reset(params, origin, camera_fn(0.0))
    frames = int(round(duration * fps))
    dt = float(M.F32(1.0 / fps))
    pos, vel, tgt, cams = [], [], [], []
    bounds_viol = bubble_viol = 0
    lo = np.array(origin) - sim.ext - 0.01
    hi = np.array(origin) + sim.ext + 0.01
    r = float(sim.p.camera_repulsion_radius)
    t = 0.0
    for frame in range(1, frames + 1):
        t = frame / fps
        cam = camera_fn(t)
        sim.advance(dt, cam)
        if np.any(sim.pos < lo) or np.any(sim.pos > hi):
            bounds_viol += int(np.sum(np.any((sim.pos < lo) | (sim.pos > hi), axis=1)))
        d = np.linalg.norm(sim.pos - cam, axis=1)
        if r > 0:
            bubble_viol += int(np.sum(d + 0.01 < r))
        if frame % record_every == 0:
            pos.append(sim.pos.copy())
            vel.append(sim.vel.copy())
            tgt.append(sim.target.copy())
            cams.append(cam.copy())
    return {
        "sim": sim,
        "pos": np.array(pos), "vel": np.array(vel), "target": np.array(tgt), "camera": np.array(cams),
        "fps": fps / record_every, "bounds_violations": bounds_viol, "bubble_violations": bubble_viol,
    }


def return_map_min_recurrence(frames, min_lag, max_lag, norm):
    """Exact port of MinimumReturnMapRecurrence in the C++ test."""
    frames = np.asarray(frames)
    best = float("inf")
    n = frames.shape[0]
    for lag in range(min_lag, max_lag + 1):
        count = n - lag - 1
        if count <= 0:
            continue
        a = frames[:count]
        b = frames[lag:lag + count]
        step_a = frames[1:count + 1] - a
        step_b = frames[lag + 1:lag + count + 1] - b
        sq = np.sum((a - b) ** 2) + np.sum((step_a - step_b) ** 2)
        values = 2 * count * frames.shape[1]
        best = min(best, math.sqrt(sq / values) / max(1.0, norm))
    return best


def autocorr_abs(series, lag):
    """Unbiased normalised autocorrelation of position about its mean (|value|)."""
    x = series - series.mean(axis=0)
    num = float(np.sum(x[:-lag] * x[lag:])) / (len(x) - lag)
    den = float(np.sum(x * x)) / len(x)
    return abs(num / den) if den > 0 else 1.0


def heading_rate_deg_s(vel, fps):
    v = vel / np.maximum(np.linalg.norm(vel, axis=2, keepdims=True), 1e-6)
    dots = np.clip(np.sum(v[1:] * v[:-1], axis=2), -1.0, 1.0)
    return np.degrees(np.arccos(dots)) * fps


def metrics(result, params):
    pos, vel, tgt, cam, fps = result["pos"], result["vel"], result["target"], result["camera"], result["fps"]
    sim = result["sim"]
    speed = np.linalg.norm(vel, axis=2)
    dist_t = np.linalg.norm(pos - tgt[:, None, :], axis=2)
    dist_c = np.linalg.norm(pos - cam[:, None, :], axis=2)
    within60 = dist_c < 60.0
    entries = np.sum(within60[1:] & ~within60[:-1])
    minutes = pos.shape[0] / fps / 60.0
    tspeed = np.linalg.norm(np.diff(tgt, axis=0), axis=1) * fps
    # C++ NonRepetition test: 4 bees, 10 Hz, lags 2..30 s, normalised by |extent|.
    step = max(1, int(round(fps / 10.0)))
    sampled = pos[step - 1::step, :4, :]
    rm = return_map_min_recurrence(sampled, 20, 300, float(np.linalg.norm(sim.ext)))
    bee0 = pos[:, 0, :]
    ac = autocorr_abs(bee0, int(round(10.0 * fps)))
    hr = heading_rate_deg_s(vel, fps)
    floor_frac = float(np.mean(pos[:, :, 2] < FLOOR_Z + 5.0))
    out = {
        "bees": int(pos.shape[1]),
        "seconds": round(pos.shape[0] / fps, 3),
        "bounds_violations": result["bounds_violations"],
        "bubble_violations": result["bubble_violations"],
        "return_map_min_recurrence": round(rm, 5),
        "bee0_autocorr_10s_abs": round(ac, 4),
        "median_dist_to_target_cm": round(float(np.median(dist_t)), 1),
        "p90_dist_to_target_cm": round(float(np.percentile(dist_t, 90)), 1),
        "median_speed_cm_s": round(float(np.median(speed)), 1),
        "p90_speed_cm_s": round(float(np.percentile(speed, 90)), 1),
        "median_heading_rate_deg_s": round(float(np.median(hr)), 1),
        "frac_frames_bee_within_60cm": round(float(np.mean(np.any(within60, axis=1))), 3),
        "close_pass_entries_per_min": round(float(entries / minutes), 1),
        "mean_bees_within_200cm": round(float(np.mean(np.sum(dist_c < 200.0, axis=1))), 2),
        "mean_bees_within_100cm": round(float(np.mean(np.sum(dist_c < 100.0, axis=1))), 2),
        "min_camera_distance_cm": round(float(dist_c.min()), 3),
        "target_median_speed_cm_s": round(float(np.median(tspeed)), 1),
        "target_p90_speed_cm_s": round(float(np.percentile(tspeed, 90)), 1),
        "frac_bee_samples_within_5cm_of_floor": round(floor_frac, 4),
        "flybys": sim.flyby_count, "darts": sim.dart_count, "target_jumps": sim.jump_count,
    }
    out["gates"] = check_gates(out)
    out["all_gates_pass"] = all(g["pass"] for g in out["gates"].values())
    return out


def check_gates(m):
    rows = {}
    for key, (op, ref) in GATES.items():
        v = m[key]
        if op == "==":
            ok = v == ref
        elif op == ">=":
            ok = v >= ref
        elif op == "<":
            ok = v < ref
        else:
            ok = ref[0] <= v <= ref[1]
        rows[key] = {"value": v, "op": op, "ref": ref, "pass": bool(ok)}
    return rows


def score(m):
    """Lower is better: summed normalised gate misses (0 when every gate passes)."""
    total = 0.0
    for key, row in m["gates"].items():
        if row["pass"]:
            continue
        v, op, ref = row["value"], row["op"], row["ref"]
        if op == "between":
            span = ref[1] - ref[0]
            total += (ref[0] - v) / span if v < ref[0] else (v - ref[1]) / span
        elif op in (">=", "<"):
            total += abs(v - ref) / max(abs(ref), 1e-6)
        else:
            total += 10.0
    return round(total, 4)


# ---------------------------------------------------------------- drawing ----
W, H = 1100, 820
BG = (12, 12, 16)


def _font(size=16):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _mapper(extent_a, extent_b, origin_a, origin_b, margin=70):
    scale = min((W - 2 * margin) / (2 * extent_a), (H - 2 * margin - 40) / (2 * extent_b))
    cx, cy = W / 2, (H + 40) / 2

    def m(a, b):
        return (cx + (a - origin_a) * scale, cy - (b - origin_b) * scale)
    return m, scale


def plot_trails(result, path, axes=(0, 1), title="", bees=14, extra_lines=()):
    pos, tgt, cam, fps = result["pos"], result["target"], result["camera"], result["fps"]
    ext = result["sim"].ext
    a, b = axes
    img = Image.new("RGB", (W, H), BG)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    m, scale = _mapper(ext[a], ext[b], 0.0, 0.0)
    x0, y0 = m(-ext[a], ext[b])
    x1, y1 = m(ext[a], -ext[b])
    d.rectangle([x0, y0, x1, y1], outline=(90, 90, 110, 255), width=1)
    tb = ext * 0.45
    tx0, ty0 = m(-tb[a], tb[b])
    tx1, ty1 = m(tb[a], -tb[b])
    d.rectangle([tx0, ty0, tx1, ty1], outline=(70, 60, 40, 255), width=1)
    for label, value, color in extra_lines:
        ya = m(0, value)[1]
        d.line([(x0, ya), (x1, ya)], fill=color, width=1)
        d.text((x0 + 4, ya - 16), label, fill=color, font=_font(13))
    rng = np.random.default_rng(7)
    picks = sorted(rng.choice(pos.shape[1], size=min(bees, pos.shape[1]), replace=False))
    stride = max(1, int(fps / 30))
    for k, i in enumerate(picks):
        hue = k / max(1, len(picks))
        col = tuple(int(160 + 95 * math.sin(2 * math.pi * (hue + o))) for o in (0.0, 0.33, 0.66))
        pts = [m(p[a], p[b]) for p in pos[::stride, i, :]]
        d.line(pts, fill=col + (70,), width=1)
    d.line([m(p[a], p[b]) for p in tgt[::stride]], fill=(255, 200, 60, 230), width=2)
    d.line([m(p[a], p[b]) for p in cam[::stride]], fill=(80, 200, 255, 255), width=3)
    cx, cy = m(cam[-1][a], cam[-1][b])
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(80, 200, 255, 255))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    t = ImageDraw.Draw(img)
    t.text((16, 10), title, fill=(230, 230, 230), font=_font(18))
    axis_names = "XYZ"
    t.text((16, 36), "%s right, %s up; box = behaviour bounds, inner box = target bounds; 1 m = %.0f px"
           % (axis_names[a], axis_names[b], 100 * scale), fill=(150, 150, 160), font=_font(13))
    t.text((16, H - 26), "cyan = camera (GO1 path)   amber = swarm target   colours = %d of %d bees"
           % (len(picks), pos.shape[1]), fill=(150, 150, 160), font=_font(13))
    img.save(path)


def render_gif(result, gif_path, seconds=12.0, start=20.0, out_fps=20, mp4_path=None):
    pos, tgt, cam, fps = result["pos"], result["target"], result["camera"], result["fps"]
    ext = result["sim"].ext
    stride = int(round(fps / out_fps))
    first = int(start * fps)
    last = min(pos.shape[0], first + int(seconds * fps))
    w2 = W // 2
    frames = []
    m_top, s_top = _mapper(ext[0], ext[1], 0, 0)
    for f in range(first, last, stride):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        x0, y0 = m_top(-ext[0], ext[1])
        x1, y1 = m_top(ext[0], -ext[1])
        d.rectangle([x0, y0, x1, y1], outline=(60, 60, 80))
        trail = range(max(first, f - 6 * stride), f + 1, stride)
        for i in range(pos.shape[1]):
            pts = [m_top(pos[k, i, 0], pos[k, i, 1]) for k in trail]
            if len(pts) > 1:
                d.line(pts, fill=(120, 110, 70), width=1)
            x, y = pts[-1]
            # Size and brightness by height, a cheap depth cue.
            h = (pos[f, i, 2] + ext[2]) / (2 * ext[2])
            r = 1.5 + 2.0 * h
            g = int(170 + 85 * h)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(g, int(g * 0.85), 90))
        tx, ty = m_top(tgt[f][0], tgt[f][1])
        d.line([(tx - 7, ty), (tx + 7, ty)], fill=(255, 140, 40), width=2)
        d.line([(tx, ty - 7), (tx, ty + 7)], fill=(255, 140, 40), width=2)
        cx, cy = m_top(cam[f][0], cam[f][1])
        rr = 60 * s_top
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(60, 140, 190))
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(80, 200, 255))
        d.text((16, 10), "S6 swarm, top-down, t = %5.2f s   (ring = 60 cm round the camera)" % (f / fps),
               fill=(220, 220, 220), font=_font(16))
        frames.append(img.resize((w2, H // 2)))
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=int(1000 / out_fps), loop=0)
    if mp4_path and shutil.which("ffmpeg"):
        tmp = os.path.join(os.path.dirname(mp4_path), "_frames")
        os.makedirs(tmp, exist_ok=True)
        for k, fr in enumerate(frames):
            fr.save(os.path.join(tmp, "f%04d.png" % k))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(out_fps), "-i",
                        os.path.join(tmp, "f%04d.png"), "-pix_fmt", "yuv420p", "-vf",
                        "pad=ceil(iw/2)*2:ceil(ih/2)*2", mp4_path], check=True)
        shutil.rmtree(tmp)
    return len(frames)


# ---------------------------------------------------------------- golden -----
def golden(params=None):
    """States after 1 s and 3 s for the C++ PythonMirrorGolden test (24 bees, moving camera).

    The camera lerps (-300,40,-60)->(-240,10,-50) over the first 60 Advance(1/60)
    calls and then holds.  1 s: no jump/fly-by yet, strict tolerance.  3 s: one
    target jump and one fly-by have fired; chaos amplifies CRT-level differences
    (measured on the mirror: a 1e-9 cm nudge grows to 2e-4 cm by 3 s), so its
    tolerance is loose and its failure is diagnostic, not a defect by itself.
    """
    p = dataclasses.replace(params or M.Params(), bee_count=24)
    start = np.array([-300.0, 40.0, -60.0])
    end = np.array([-240.0, 10.0, -50.0])
    sim = M.Simulation().reset(p, (0.0, 0.0, 0.0), start)
    out = {"scenario": "24 bees, header defaults, origin 0, camera lerp (-300,40,-60)->(-240,10,-50) "
                       "over 60 Advance(1/60) calls, then held"}
    for frame in range(1, 181):
        sim.advance(float(M.F32(1.0 / 60.0)), start + (end - start) * min(1.0, frame / 60.0))
        if frame in (60, 180):
            out["t%d" % (frame // 60)] = {
                "sim_seconds": sim.sim_seconds,
                "target": sim.target.tolist(),
                "bees": {str(i): sim.pos[i].tolist() for i in range(4)},
                "flybys": sim.flyby_count, "darts": sim.dart_count, "jumps": sim.jump_count,
            }
    return out


# ---------------------------------------------------------------- selftest ---
def selftest():
    """Controls: the metrics must be able to fail."""
    rows = {}
    # (-) a perfect 12 s loop must FAIL the return-map gate (mirrors the C++ control).
    n = 600
    ph = 2 * np.pi * (np.arange(n) % 120) / 120.0
    loop = np.stack([np.stack([100 * np.cos(ph), 100 * np.sin(ph), 0 * ph], 1),
                     np.stack([50 * np.cos(ph + .7), 50 * np.sin(ph + .7), 20 + 0 * ph], 1)], 1)
    rows["loop_return_map"] = return_map_min_recurrence(loop, 20, 300, 100.0)
    # (-) a 10 s periodic orbit must FAIL the 10 s-lag autocorrelation gate.
    tt = np.arange(1200) / 60.0
    orbit = np.stack([np.cos(2 * np.pi * tt / 10.0), np.sin(2 * np.pi * tt / 10.0), 0 * tt], 1)
    rows["periodic_autocorr"] = autocorr_abs(orbit, 600)
    # (+) RNG: first FRand of FRandomStream(0) = header arithmetic by hand.
    s = M.RandomStream(0)
    seed1 = 907633515
    expect = np.frombuffer(np.uint32(0x3F800000 | (seed1 >> 9)).tobytes(), dtype=np.float32)[0] - np.float32(1)
    rows["rng_first"] = (s.frand(), float(expect))
    ok = (rows["loop_return_map"] < 0.01 and rows["periodic_autocorr"] >= 0.85
          and rows["rng_first"][0] == rows["rng_first"][1])
    rows["controls_ok"] = bool(ok)
    return rows


# ------------------------------------------------- C++ automation tests -------
def cpp_tests():
    """Replays each InfinityStage.Effects.BeeSwarm.* test on the mirror (prediction only)."""
    f32 = M.f32
    def make():
        return dataclasses.replace(M.Params(), bee_count=24, seed=0xBEE62026,
                                   bounds_extent_cm=(600.0, 450.0, 300.0))
    def states_match(a, b, pt=1e-4, vt=1e-4):
        return (np.all(np.abs(a.pos - b.pos) <= pt) and np.all(np.abs(a.vel - b.vel) <= vt)
                and np.all(np.abs(a.target - b.target) <= pt) and abs(a.sim_seconds - b.sim_seconds) <= 1e-8)
    def bounds_bubble(sim, p, origin, cam):
        rel = sim.pos - np.array(origin)
        ext = np.array(p.bounds_extent_cm)
        if np.any(np.abs(rel) > ext + 0.01):
            return False
        return bool(np.all(np.linalg.norm(sim.pos - np.array(cam), axis=1) + 0.01 >= sim.p.camera_repulsion_radius))
    out = {}
    p = make(); cam = (0.0, 0.0, 0.0)
    a = M.Simulation().reset(p, (0, 0, 0), cam); b = M.Simulation().reset(p, (0, 0, 0), cam)
    for _ in range(600):
        a.advance(f32(1 / 60), cam); b.advance(f32(1 / 60), cam)
    out["SeedRepeat"] = bool(states_match(a, b, 0.0, 0.0))
    step = p.fixed_step_seconds
    s30 = M.Simulation().reset(p, (0, 0, 0), cam); s60 = M.Simulation().reset(p, (0, 0, 0), cam)
    sj = M.Simulation().reset(p, (0, 0, 0), cam)
    for _ in range(300):
        s30.advance(f32(np.float32(step) * np.float32(4)), cam)
    for _ in range(600):
        s60.advance(f32(np.float32(step) * np.float32(2)), cam)
    pattern = [1, 7, 2, 5, 3, 6]; done = 0; k = 0
    while done < 1200:
        n = min(pattern[k % 6], 1200 - done)
        sj.advance(f32(np.float32(step) * np.float32(n)), cam); done += n; k += 1
    out["VariableFrameRate"] = bool(states_match(s30, s60) and states_match(s30, sj))
    pm = dataclasses.replace(p, camera_repulsion_radius=0.0, flyby_rate=0.0)
    c0 = np.array([-1000.0, -200.0, 100.0]); c1 = np.array([1000.0, 200.0, 100.0])
    a = M.Simulation().reset(pm, (0, 0, 0), c0); b = M.Simulation().reset(pm, (0, 0, 0), c0)
    for f in range(1, 121):
        a.advance(f32(1 / 30), c0 + (c1 - c0) * (f / 120))
    for f in range(1, 241):
        b.advance(f32(1 / 60), c0 + (c1 - c0) * (f / 240))
    out["MovingCameraInterpolation"] = bool(states_match(a, b, 0.01, 0.01))
    out["MovingCameraInterpolation_maxdiff_cm"] = float(np.max(np.abs(a.pos - b.pos)))
    sim = M.Simulation().reset(p, (0, 0, 0), (1000.0, 0, 0)); cut = sim.pos[0].copy(); t0 = sim.sim_seconds
    sim.advance(0.0, cut, True)
    out["CameraCutBubble"] = bool(sim.sim_seconds == t0 and bounds_bubble(sim, p, (0, 0, 0), cut))
    sim = M.Simulation().reset(p, (0, 0, 0), (1000.0, 0, 0)); sim.advance(f32(1 / 60), (1000.0, 0, 0))
    paused = sim.pos[1].copy(); t0 = sim.sim_seconds; sim.advance(0.0, paused)
    out["PauseBubble"] = bool(sim.sim_seconds == t0 and bounds_bubble(sim, p, (0, 0, 0), paused))
    pb = dataclasses.replace(p, bounds_extent_cm=(40.0, 30.0, 20.0), camera_repulsion_radius=25.0)
    origin = np.array([50.0, -25.0, 10.0])
    cams = [origin + [40, 0, 0], origin + [-40, -30, -20], origin + [40, 30, 20]]
    sim = M.Simulation().reset(pb, origin, cams[0]); ok = bounds_bubble(sim, pb, origin, cams[0])
    for c in cams:
        sim.advance(0.0, c, True); ok = ok and bounds_bubble(sim, pb, origin, c)
        for _ in range(120):
            sim.advance(pb.fixed_step_seconds, c)
        ok = ok and bounds_bubble(sim, pb, origin, c)
    out["BoundaryConstraints"] = bool(ok)
    sim = M.Simulation().reset(p, (0, 0, 0), (0, 0, 0)); frames = []
    for _ in range(600):
        sim.advance(f32(0.1), (0, 0, 0)); frames.append(sim.pos[:4].copy())
    rm = return_map_min_recurrence(np.array(frames), 20, 300, float(np.linalg.norm(sim.ext)))
    out["NonRepetitionReturnMap"] = bool(rm >= 0.01); out["NonRepetitionReturnMap_value"] = rm
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--v2", action="store_true")
    ap.add_argument("--golden", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cpp-tests", action="store_true")
    ap.add_argument("--bees", type=int, default=200)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if args.selftest:
        print(json.dumps(selftest(), indent=2, default=float))
        return
    if args.cpp_tests:
        r = cpp_tests()
        print(json.dumps(r, indent=2, default=float))
        with open(os.path.join(OUT, "cpp_tests_prediction.json"), "w") as fh:
            json.dump(r, fh, indent=2, default=float)
        return
    if args.golden:
        g = golden()
        with open(os.path.join(OUT, "golden.json"), "w") as fh:
            json.dump(g, fh, indent=2)
        print(json.dumps(g, indent=2))
        return
    if args.tune:
        tune()
        return

    params = M.V2_DEFAULTS if args.v2 else M.Params()
    params = dataclasses.replace(params, bee_count=args.bees)
    tag = "v2" if args.v2 else "tuned"
    t0 = time.time()
    res = run(params)
    m = metrics(res, params)
    m["wall_seconds"] = round(time.time() - t0, 1)
    m["params"] = params.as_cpp()
    m["score"] = score(m)
    lines = (("floor", FLOOR_Z, (120, 90, 90, 255)), ("camera height", CAMERA_Z, (80, 160, 200, 255)))
    plot_trails(res, os.path.join(OUT, "trails_top_%s.png" % tag), (0, 1),
                "S6 bee swarm (%s), 120 s, top-down XY" % tag)
    plot_trails(res, os.path.join(OUT, "trails_side_%s.png" % tag), (0, 2),
                "S6 bee swarm (%s), 120 s, side XZ" % tag, extra_lines=lines)
    sub = {k: res[k] for k in res}
    nframes = render_gif(sub, os.path.join(OUT, "swarm_dots_%s.gif" % tag),
                         mp4_path=os.path.join(OUT, "swarm_dots_%s.mp4" % tag))
    m["gif_frames"] = nframes
    with open(os.path.join(OUT, "metrics_%s.json" % tag), "w") as fh:
        json.dump(m, fh, indent=2, default=float)
    print(json.dumps({k: v for k, v in m.items() if k != "gates"}, indent=2, default=float))
    print("GATES:", {k: ("PASS" if g["pass"] else "FAIL %s" % g["value"]) for k, g in m["gates"].items()})
    print("BEE_SWARM_HARNESS_DONE|tag=%s|all_gates_pass=%s|score=%s|out=%s"
          % (tag, m["all_gates_pass"], m["score"], OUT))


def tune():
    """Coarse one-factor sweep around a base, then a short combined refinement.

    Tuning uses 64 bees and 120 s.  Each candidate is scored by `score` (summed
    gate misses), ties broken by more close passes.
    """
    base = M.Params(bee_count=64)
    candidates = [("base", base)]
    sweeps = {
        "camera_attract_weight": [0.2, 0.4, 0.6, 0.9],
        "flyby_rate": [0.35, 0.5, 0.8],
        "dart_rate": [0.2, 0.45, 0.8],
        "small_noise_accel": [200.0, 380.0, 600.0],
        "large_noise_accel": [220.0, 420.0, 650.0],
        "max_speed": [500.0, 650.0, 900.0],
        "drag": [1.0, 1.6, 2.4],
        "target_wander_speed": [110.0, 150.0, 200.0],
    }
    for key, values in sweeps.items():
        for v in values:
            if getattr(base, key) == v:
                continue
            candidates.append(("%s=%s" % (key, v), dataclasses.replace(base, **{key: v})))
    for key, values in (("orbit_radius_range", [(25.0, 110.0), (30.0, 140.0), (35.0, 180.0)]),
                        ("target_jump_interval", [(0.8, 2.6), (1.5, 4.5)]),
                        ("bounds_extent_cm", [(600.0, 450.0, 140.0), (600.0, 450.0, 300.0)])):
        for v in values:
            if tuple(getattr(base, key)) == tuple(v):
                continue
            candidates.append(("%s=%s" % (key, v), dataclasses.replace(base, **{key: v})))
    rows = []
    for name, p in candidates:
        t0 = time.time()
        m = metrics(run(p), p)
        rows.append({"name": name, "score": score(m), "all_gates_pass": m["all_gates_pass"],
                     "failed": [k for k, g in m["gates"].items() if not g["pass"]],
                     "metrics": {k: v for k, v in m.items() if k != "gates"},
                     "wall": round(time.time() - t0, 1)})
        print("%-42s score=%-7s pass=%s failed=%s" % (name, rows[-1]["score"], m["all_gates_pass"],
                                                     rows[-1]["failed"]), flush=True)
    rows.sort(key=lambda r: (r["score"], -r["metrics"]["close_pass_entries_per_min"]))
    with open(os.path.join(OUT, "tuning.json"), "w") as fh:
        json.dump(rows, fh, indent=2, default=float)
    print("BEE_SWARM_TUNE_DONE|candidates=%d|best=%s|score=%s" % (len(rows), rows[0]["name"], rows[0]["score"]))


if __name__ == "__main__":
    main()
