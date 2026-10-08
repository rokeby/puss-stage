#!/usr/bin/env python3
"""Temporal low-pass of a streamed curtain solve, into a NEW stream file (the source is never written).

Why (8 Oct, unfurl_sleight_b1hop10_p02): from ~1 s after release the whole curtain buzzes in place. The median vertex
step is 5-8 mm/frame and 40-65 % of vertices reverse direction every frame; over the last 1 s path/net = 263/14 mm.
The buzz is zero-mean, so a centred moving average removes it and keeps the slow sway. Frames before --from are copied
bit-identical; a --ramp blends raw -> smoothed so there is no step at the seam.

  python stream_lowpass.py --src X_stream.f32 --sidecar X_stream.json --out Y_stream.f32 [--from 266 --window 9 --ramp 12]
    (frames are 1-based like the sidecar's first_frame; --from is the first frame that may be smoothed)
Writes Y_stream.f32 + Y_stream.json (the sidecar copied, plus a "lowpass" block) and prints STREAM_LOWPASS_OK with
before/after jitter metrics. Refuses if --out exists or equals --src. Pure numpy; the reading is memory-mapped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np


def metrics(s: np.ndarray, frames: list[int]) -> dict:
    """Per-frame median step (mm), reversing share (cos(step, prev step) < -0.5 among verts moving > 2 mm)."""
    out = {}
    for f in frames:
        d1 = np.asarray(s[f] - s[f - 1], dtype=np.float64)
        d0 = np.asarray(s[f - 1] - s[f - 2], dtype=np.float64)
        n1, n0 = np.linalg.norm(d1, axis=1), np.linalg.norm(d0, axis=1)
        m = (n1 > 0.002) & (n0 > 0.002)
        rev = float(((d1[m] * d0[m]).sum(1) / (n1[m] * n0[m]) < -0.5).mean()) if m.any() else 0.0
        out[f + 1] = {"median_step_mm": round(float(np.median(n1)) * 1000, 3), "reversing": round(rev, 3)}
    return out


def end_still_mm(s: np.ndarray) -> float:
    return round(float(np.linalg.norm(np.asarray(s[-1] - s[-2], dtype=np.float64), axis=1).max()) * 1000, 2)


def lowpass(src: np.ndarray, start_idx: int, window: int, ramp: int) -> np.ndarray:
    """Centred average over `window` (odd) frames with HALF weight on the two end frames (a trapezoid kernel: it
    cancels a frame-to-frame alternation exactly, which a plain moving average leaves at 1/window). Near the ends of
    the clip, where the full window is missing, a plain average of the available frames is used. Applied from
    start_idx (0-based), blended in linearly over `ramp` frames. Frames < start_idx come back bit-identical."""
    if window < 3 or window % 2 == 0:
        raise ValueError("window must be odd and >= 3")
    n = src.shape[0]
    k = window // 2
    out = np.array(src, dtype=np.float32, copy=True)
    x = np.asarray(src, dtype=np.float64)
    csum = np.concatenate([np.zeros((1,) + src.shape[1:]), np.cumsum(x, axis=0)], axis=0)
    for i in range(start_idx, n):
        if i - k >= 0 and i + k < n:
            avg = (csum[i + k] - csum[i - k + 1] + 0.5 * (x[i - k] + x[i + k])) / (2.0 * k)
        else:
            a, b = max(0, i - k), min(n, i + k + 1)
            avg = (csum[b] - csum[a]) / (b - a)
        w = 1.0 if ramp <= 0 else min(1.0, (i - start_idx + 1) / float(ramp))
        out[i] = ((1.0 - w) * x[i] + w * avg).astype(np.float32)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--sidecar", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--from", dest="from_frame", type=int, default=266)
    ap.add_argument("--window", type=int, default=9)
    ap.add_argument("--ramp", type=int, default=12)
    a = ap.parse_args(argv)
    if a.out.resolve() == a.src.resolve():
        print("STREAM_LOWPASS_FAILED|out equals src", file=sys.stderr)
        return 2
    if a.out.exists():
        print("STREAM_LOWPASS_FAILED|out exists: %s" % a.out, file=sys.stderr)
        return 2
    side = json.loads(a.sidecar.read_text(encoding="utf-8"))
    if side.get("dtype") != "float32" or side.get("layout") != "frame-major xyz":
        print("STREAM_LOWPASS_FAILED|unexpected sidecar layout", file=sys.stderr)
        return 2
    v = int(side["vertices"])
    size = a.src.stat().st_size
    if size % (v * 12):
        print("STREAM_LOWPASS_FAILED|partial frame: %d bytes, %d verts" % (size, v), file=sys.stderr)
        return 2
    n = size // (v * 12)
    first = int(side["first_frame"])
    start_idx = a.from_frame - first
    if not 2 <= start_idx < n:
        print("STREAM_LOWPASS_FAILED|--from %d outside frames %d..%d" % (a.from_frame, first, first + n - 1), file=sys.stderr)
        return 2
    src = np.memmap(a.src, dtype="<f4", mode="r").reshape(n, v, 3)
    out = lowpass(src, start_idx, a.window, a.ramp)
    if not np.array_equal(out[:start_idx], np.asarray(src[:start_idx])):
        print("STREAM_LOWPASS_FAILED|frames before --from changed", file=sys.stderr)
        return 3
    probe = [i for i in (start_idx + 6, (start_idx + n) // 2, n - 2) if 2 <= i < n]
    report = {"src": str(a.src), "frames": n, "vertices": v, "from": a.from_frame, "window": a.window, "ramp": a.ramp,
              "before": {"metrics": metrics(src, probe), "end_still_mm": end_still_mm(src)},
              "after": {"metrics": metrics(out, probe), "end_still_mm": end_still_mm(out)},
              "max_shift_from_raw_mm": round(float(np.linalg.norm(out.astype(np.float64) - np.asarray(src, dtype=np.float64),
                                                                   axis=2).max()) * 1000, 2)}
    tmp = a.out.with_name(a.out.name + ".tmp")
    out.astype("<f4").tofile(tmp)
    os.replace(tmp, a.out)
    side_out = dict(side, lowpass=report)
    a.out.with_suffix(".json").write_text(json.dumps(side_out, indent=1), encoding="utf-8")
    print("STREAM_LOWPASS_OK|out=%s|end_still_mm %s -> %s|max_shift_mm=%s"
          % (a.out, report["before"]["end_still_mm"], report["after"]["end_still_mm"], report["max_shift_from_raw_mm"]))
    print(json.dumps({k: report[k] for k in ("before", "after")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
