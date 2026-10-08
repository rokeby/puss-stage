"""Offline: sway rhythm of the six S3 shore figures inside their CALM runs (Gary 8 Oct: "create a section where they
sway together").  Reads the same FBX curves as shore_mocap_intensity.py (pelvis + spine_03 rotation) and, per CALM run,
the dominant sway period (autocorrelation of the smoothed lateral pelvis/spine signal, 1.5-8 s window) and amplitude.
Writes DerivedAssets/S3MocapIntensity/s3_sway_runs.json.  Measured from curves; 'sway' = dominant periodic component
[inferred interpretation]."""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shore_mocap_intensity as M  # noqa: E402

ROOT = HERE.parent.parent
SEG = ROOT / "DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json"
OUT = ROOT / "DerivedAssets/S3MocapIntensity/s3_sway_runs.json"
FPS = 24.0


def sample(track, t):
    kt, kv = track
    secs = np.asarray(kt, dtype=np.float64) / 46186158000.0
    return np.interp(t, secs, np.asarray(kv, dtype=np.float64))


def main():
    seg = json.loads(SEG.read_text(encoding="utf-8"))
    out = []
    for f in seg["figures"]:
        tracks, info = M.load_animation_tracks(Path(f["source_path"]))
        dur = f["analysis"]["duration_seconds"]
        t = np.arange(0, dur, 1 / FPS)
        sigs = []
        for bone in ("pelvis", "spine_03", "spine_02"):
            for ch, chans in tracks.get(bone, {}).items():
                for axis, tr in chans.items():
                    sigs.append((bone, ch, axis, sample(tr, t)))
        runs = []
        for s in f["segments"]:
            if s["class"] != "CALM" or s["source_out_seconds"] - s["source_in_seconds"] < 3.0:
                continue
            a, b = int(s["source_in_seconds"] * FPS), int(s["source_out_seconds"] * FPS)
            best = None
            for bone, ch, axis, x in sigs:
                y = x[a:b] - np.convolve(x[a:b], np.ones(int(3 * FPS)) / int(3 * FPS), mode="same")
                y = y[int(1.5 * FPS):-int(1.5 * FPS)] if len(y) > 4 * FPS else y
                if len(y) < 3 * FPS or np.std(y) < 1e-6:
                    continue
                y = (y - y.mean()) / y.std()
                ac = np.correlate(y, y, "full")[len(y) - 1:] / len(y)
                lo, hi = int(1.5 * FPS), min(int(8 * FPS), len(ac) - 1)
                if hi <= lo:
                    continue
                k = lo + int(np.argmax(ac[lo:hi]))
                score = float(ac[k])
                amp = float(np.std(x[a:b]))
                if best is None or score > best["periodicity"]:
                    best = {"signal": f"{bone}.{ch}.{axis}", "period_s_source": round(k / FPS, 2),
                            "period_s_scene": round(k / FPS / seg["config"]["play_rate"], 2),
                            "periodicity": round(score, 3), "amplitude_std": round(amp, 3)}
            runs.append({"source_in": s["source_in_seconds"], "source_out": s["source_out_seconds"],
                         "scene_len_s": s["duration_scene_seconds"], **(best or {})})
        out.append({"id": f["id"], "calm_runs": runs})
        print(f["id"], [(r["source_in"], r["source_out"], r.get("period_s_scene"), r.get("periodicity"), r.get("signal")) for r in runs])
    OUT.write_text(json.dumps({"schema": "s3_sway_runs/1", "tier": "measured curves; sway reading inferred",
                               "figures": out}, indent=1), encoding="utf-8")
    print("SWAY_OK|" + str(OUT))


if __name__ == "__main__":
    main()
