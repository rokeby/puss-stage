#!/usr/bin/env python3
"""Generate a 24 fps S6 bee-swarm drive from read-only old-lady hand samples.

The input is written by Saved/CodexConductor/S6OldLadySwarm/sample_hands.py.
No Unreal packages are read or written here.  Creative response constants are
arguments; the defaults are only a reviewable first proposal.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 24.0
SCHEMA = "pussstage.s6-old-lady-swarm-drive.v1"


class DriveError(RuntimeError):
    pass


def _array(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    try:
        value = np.asarray([row[key] for row in rows], dtype=float)
    except (KeyError, TypeError, ValueError) as exc:
        raise DriveError("BAD_VECTOR_ROWS|" + key) from exc
    if value.shape != (len(rows), 3) or not np.isfinite(value).all():
        raise DriveError("BAD_VECTOR_ROWS|" + key)
    return value


def _smooth(values: np.ndarray, seconds: float, fps: float = FPS) -> np.ndarray:
    width = max(1, int(round(seconds * fps)))
    if width <= 1:
        return values.copy()
    kernel = np.hanning(width * 2 + 1)
    kernel /= kernel.sum()
    if values.ndim == 1:
        return np.convolve(np.pad(values, width, mode="edge"), kernel, mode="valid")
    return np.column_stack([_smooth(values[:, i], seconds, fps) for i in range(values.shape[1])])


def _velocity(pos: np.ndarray, fps: float = FPS) -> np.ndarray:
    return np.gradient(pos, 1.0 / fps, axis=0, edge_order=1)


def _normalise(values: np.ndarray, low_q: float, high_q: float) -> tuple[np.ndarray, float, float]:
    lo, hi = np.quantile(values, [low_q, high_q])
    if hi <= lo + 1e-6:
        return np.zeros_like(values), float(lo), float(hi)
    return np.clip((values - lo) / (hi - lo), 0.0, 1.0), float(lo), float(hi)


def _peaks(values: np.ndarray, threshold: float, separation_frames: int) -> list[int]:
    candidates = [i for i in range(1, len(values) - 1)
                  if values[i] >= threshold and values[i] >= values[i - 1] and values[i] > values[i + 1]]
    selected: list[int] = []
    for index in sorted(candidates, key=lambda i: float(values[i]), reverse=True):
        if all(abs(index - other) >= separation_frames for other in selected):
            selected.append(index)
    return sorted(selected)


def generate(sample: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    rows = sample.get("samples") or []
    if len(rows) < 3:
        raise DriveError("TOO_FEW_SAMPLES")
    times = np.asarray([float(r["s6_seconds"]) for r in rows])
    if np.any(np.diff(times) <= 0):
        raise DriveError("NON_MONOTONIC_TIME")
    expected = np.arange(len(rows), dtype=float) / FPS + times[0]
    if np.max(np.abs(times - expected)) > 1e-4:
        raise DriveError("NOT_24FPS_S6_TIME")

    left, right = _array(rows, "left_hand_world_cm"), _array(rows, "right_hand_world_cm")
    lv, rv = _velocity(left), _velocity(right)
    ls, rs = np.linalg.norm(lv, axis=1), np.linalg.norm(rv, axis=1)
    raw = np.maximum(ls, rs)
    energy, p10, p95 = _normalise(_smooth(raw, args.energy_smooth), 0.10, 0.95)
    peak_ids = _peaks(energy, args.peak_threshold, max(1, int(round(args.peak_separation * FPS))))

    # Batting impulse: fast attack, slower exponential release.  This is causal
    # and therefore does not make the swarm anticipate the performer.
    response = np.zeros(len(rows), dtype=float)
    release = math.exp(-1.0 / max(1e-6, args.release_seconds * FPS))
    peak_set = set(peak_ids)
    for i in range(len(rows)):
        response[i] = max(energy[i] if i in peak_set else 0.0,
                          (response[i - 1] * release) if i else 0.0)

    midpoint = 0.5 * (left + right)
    faster_velocity = np.where((ls >= rs)[:, None], lv, rv)
    direction = faster_velocity / np.maximum(np.linalg.norm(faster_velocity, axis=1)[:, None], 1e-6)
    desired_world = midpoint - direction * (response * args.recoil_cm)[:, None]
    desired_world = _smooth(desired_world, args.position_smooth)
    outer = np.asarray(args.outer_translation_cm, dtype=float)
    local = desired_world - outer[None, :]
    base_scale = np.asarray(args.base_scale, dtype=float)
    scale = base_scale[None, :] * (1.0 + args.disperse_gain * response[:, None])
    density = 1.0 / np.prod(scale / base_scale[None, :], axis=1)

    out_rows = []
    for i, row in enumerate(rows):
        out_rows.append({
            "s6_frame_24": int(round(times[i] * FPS)), "s6_seconds": round(float(times[i]), 6),
            "source_seconds": round(float(row.get("source_seconds", times[i] - args.nesting_seconds)), 6),
            "left_hand_world_cm": [round(float(v), 4) for v in left[i]],
            "right_hand_world_cm": [round(float(v), 4) for v in right[i]],
            "left_hand_speed_cm_s": round(float(ls[i]), 4),
            "right_hand_speed_cm_s": round(float(rs[i]), 4),
            "hand_energy": round(float(energy[i]), 6), "batting_peak": i in peak_set,
            "response": round(float(response[i]), 6),
            "swarm_world_cm": [round(float(v), 4) for v in desired_world[i]],
            "swarm_local_cm": [round(float(v), 4) for v in local[i]],
            "scale_xyz": [round(float(v), 6) for v in scale[i]],
            "concentration_density": round(float(density[i]), 6),
        })
    return {
        "schema": SCHEMA, "state": "GENERATED_FROM_EDITOR_SAMPLES",
        "source": sample.get("source", {}), "fps": FPS,
        "s6_nesting": {"start_frame_25": 104, "start_seconds": args.nesting_seconds,
                       "outer_translation_cm": list(args.outer_translation_cm)},
        "design": {"route": "create-only LS_Void_S6 copy; key existing NS_BeeSwarm transform",
                   "position": "hand midpoint minus faster-hand velocity recoil",
                   "concentration": "uniform transform scale; batting disperses cloud; density is inverse volume",
                   "energy_p10_cm_s": p10, "energy_p95_cm_s": p95,
                   "peak_threshold": args.peak_threshold, "peak_separation_seconds": args.peak_separation,
                   "release_seconds": args.release_seconds, "recoil_cm": args.recoil_cm,
                   "disperse_gain": args.disperse_gain, "creative_authority": "Gary"},
        "key_count": len(out_rows), "batting_peak_count": len(peak_ids), "keys": out_rows,
    }


def render_png(record: dict[str, Any], path: Path) -> None:
    keys = record["keys"]
    w, h, m = 1800, 720, 90
    image = Image.new("RGB", (w, h), (16, 17, 21)); d = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    t = np.asarray([k["s6_seconds"] for k in keys]); span = max(1e-6, t[-1] - t[0])
    x = lambda value: m + int((value - t[0]) / span * (w - 2 * m))
    panels = [(100, 310, "Hand speed / energy"), (395, 625, "Swarm response / concentration")]
    for top, bottom, title in panels:
        d.rectangle((m, top, w - m, bottom), outline=(75, 78, 88)); d.text((m, top - 24), title, fill="white", font=font)
    max_speed = max(1.0, max(max(k["left_hand_speed_cm_s"], k["right_hand_speed_cm_s"]) for k in keys))
    def line(values, top, bottom, vmax, colour):
        pts=[(x(k["s6_seconds"]), bottom-int(float(v)/vmax*(bottom-top))) for k,v in zip(keys,values)]
        d.line(pts, fill=colour, width=3)
    line([k["left_hand_speed_cm_s"] for k in keys], 100, 310, max_speed, (76, 173, 255))
    line([k["right_hand_speed_cm_s"] for k in keys], 100, 310, max_speed, (255, 111, 97))
    line([k["hand_energy"] for k in keys], 100, 310, 1.0, (255, 210, 70))
    line([k["response"] for k in keys], 395, 625, 1.0, (230, 105, 255))
    line([k["concentration_density"] for k in keys], 395, 625, 1.0, (95, 235, 160))
    centres = np.asarray([k["swarm_world_cm"] for k in keys], dtype=float)
    travel = np.linalg.norm(centres - centres[0], axis=1)
    line(travel, 395, 625, max(1.0, float(travel.max())), (80, 210, 245))
    for k in keys:
        if k["batting_peak"]:
            xx=x(k["s6_seconds"]); d.line((xx,100,xx,625), fill=(255,255,255), width=1)
    d.text((m, 35), "S6 OLD LADY: hand energy -> swarm position and concentration (24 fps)", fill="white", font=font)
    d.text((m, 655), "blue L speed | red R speed | yellow energy | white bat peaks | magenta response | green density | cyan centre travel", fill=(205,205,210), font=font)
    path.parent.mkdir(parents=True, exist_ok=True); image.save(path)


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path); p.add_argument("--json", type=Path, required=True); p.add_argument("--png", type=Path, required=True)
    p.add_argument("--nesting-seconds", type=float, default=104/25)
    p.add_argument("--outer-translation-cm", type=float, nargs=3, default=(29339.2835,399920.0,135.0))
    p.add_argument("--base-scale", type=float, nargs=3, default=(6.375,1.5,3.375))
    p.add_argument("--energy-smooth", type=float, default=.18); p.add_argument("--position-smooth", type=float, default=.28)
    p.add_argument("--peak-threshold", type=float, default=.68); p.add_argument("--peak-separation", type=float, default=.35)
    p.add_argument("--release-seconds", type=float, default=.65); p.add_argument("--recoil-cm", type=float, default=180.0)
    p.add_argument("--disperse-gain", type=float, default=.55)
    return p


def main(argv: list[str] | None=None) -> int:
    a=parser().parse_args(argv); sample=json.loads(a.input.read_text(encoding="utf-8")); rec=generate(sample,a)
    a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(rec,indent=2)+"\n",encoding="utf-8")
    render_png(rec,a.png)
    check=json.loads(a.json.read_text(encoding="utf-8"))
    if check["key_count"] != len(check["keys"]) or Image.open(a.png).size != (1800,720): raise DriveError("READBACK_FAILED")
    print(f"S6_SWARM_CURVES_OK|keys={check['key_count']}|peaks={check['batting_peak_count']}|json={a.json}|png={a.png}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
