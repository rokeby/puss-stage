"""Offline twin of M_ShadowGobo_LightFunction (animated_gobo.py CODE_UV / CODE_AVG / CODE_EDGE / CODE_BORDER).

Renders what a camera behind the spot sees on the screen: UE light-function UVs are U = light UP, V = light RIGHT
(measured 8 Oct, GOBOREVIEW-20261008-175603), so screen (sx right, sy down) -> (U, V) = (1 - sy, sx).

    python gobo_twin.py <manifest.json> <out.gif> [--params '{"BorderDepth":1,...}'] [--approach '[[t,v],...]']
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import os  # noqa: E402

sys.path.insert(0, os.environ.get("GOBO_TOOL_DIR") or
                str(Path(__file__).resolve().parents[2] / "Saved" / "CodexConductor"))
import animated_gobo as ag  # noqa: E402


def load_atlas(path):
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0
    return a[..., 0], a[..., 1]


def bilinear(tex, uv):
    H, W = tex.shape
    x = np.clip(uv[..., 0] * W - 0.5, 0, W - 1)
    y = np.clip(uv[..., 1] * H - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = x - x0, y - y0
    return (tex[y0, x0] * (1 - fx) + tex[y0, x1] * fx) * (1 - fy) + (tex[y1, x0] * (1 - fx) + tex[y1, x1] * fx) * fy


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def noise(P, clock):
    ht = clock * P["HandSpeed"]
    s = lambda f, ph: math.sin(6.2832 * f * ht + ph)  # noqa: E731
    n1 = s(0.31, 1.3) * 0.6 + s(0.53, 4.1) * 0.3 + s(0.89, 2.2) * 0.1
    n2 = s(0.23, 0.4) * 0.6 + s(0.41, 5.0) * 0.3 + s(0.97, 3.3) * 0.1
    n3 = s(0.27, 2.7) * 0.6 + s(0.61, 0.9) * 0.3 + s(1.13, 5.5) * 0.1
    n4 = s(0.19, 3.9) * 0.7 + s(0.37, 1.7) * 0.3
    return n1, n2, n3, n4


def light_function(R, G, P, UV, frame, clock, approach):
    """UV: (..., 2) cone UVs (U, V).  Returns the LF value (0..1)."""
    U, V = UV[..., 0], UV[..., 1]
    c = 0.5 - P["UVCentre"]
    a = min(max(P["SpotAxes"], 0.0), 1.0)
    U2, V2 = U + (V - U) * a, V + ((2 * c - U) - V) * a
    n1, n2, n3, n4 = noise(P, clock)
    count = max(1.0, P["Frames"])
    f = math.floor(min(max(frame, 0.0), count - 1.0) + 1e-4)
    col, row = math.fmod(f, max(1.0, P["Cols"])), math.floor(f / max(1.0, P["Cols"]))
    grow = 1.0 + P["ApproachGrow"] * min(max(approach, 0), 1) + P["HandBreath"] * P["HandAmp"] * n4
    ang = math.radians(P["HandTurn"] * P["HandAmp"] * n3)
    dx, dy = U2 + P["UVCentre"] - 0.5, V2 + P["UVCentre"] - 0.5
    dx, dy = dx * math.cos(ang) - dy * math.sin(ang), dx * math.sin(ang) + dy * math.cos(ang)
    dx, dy = dx - P["HandShift"] * P["HandAmp"] * n1, dy - P["HandShift"] * P["HandAmp"] * n2
    px, py = dx / max(P["Scale"] * grow, 1e-4) + 0.5, dy / max(P["Scale"] * grow, 1e-4) + 0.5
    px = px + (1 - 2 * px) * min(max(P["FlipU"], 0), 1)
    py = py + (1 - 2 * py) * min(max(P["FlipV"], 0), 1)
    sx = np.clip(px, 0, 1) * (1 - 2 * P["GutterUV"]) + P["GutterUV"]
    sy = np.clip(py, 0, 1) * (1 - 2 * P["GutterUV"]) + P["GutterUV"]
    auv = np.stack([(col + sx) * P["CellUV"], (row + sy) * P["CellUV"]], -1)
    blur = min(max(P["BlurUV"], 0.0), 0.003)
    taps = [auv] + [auv + np.array(d) * blur for d in ((-1, 0), (1, 0), (0, -1), (0, 1))]
    mr = sum(bilinear(R, t) for t in taps) * 0.2
    mg = sum(bilinear(G, t) for t in taps) * 0.2
    de = min(max(P["Defocus"] + P["ApproachBlur"] * min(max(approach, 0), 1) + P["HandBlur"] * P["HandAmp"] * max(0.0, n4), 0), 1)
    m = mr + (mg - mr) * de
    w = max(1e-4, P["Softness"])
    shaped = smoothstep(0.5 - w, 0.5 + w, m)
    shaped = shaped + (m - shaped) * de
    shaped = np.clip((shaped - 0.5) * max(0.0, P["Contrast"]) + 0.5, 0, 1)
    out = 1.0 + (shaped - 1.0) * min(max(P["Depth"], 0), 1)
    qx, qy = np.abs(U2 + P["UVCentre"] - 0.5) / max(P["Scale"], 1e-4), np.abs(V2 + P["UVCentre"] - 0.5) / max(P["Scale"], 1e-4)
    hx = 0.5 * max(P["BorderWidth"], 1e-4)
    hy = hx / max(P["BorderAspect"], 1e-4)
    fe = max(P["BorderFeather"], 1e-4)
    rect = smoothstep(0.0, fe, hx - qx) * smoothstep(0.0, fe, hy - qy)
    border = 1.0 + (rect - 1.0) * min(max(P["BorderDepth"], 0), 1)
    return out * border


def step_value(keys, t, fps):
    """CONSTANT keys in display frames -> value at time t (frame-quantised)."""
    fr = int(math.floor(t * fps + 1e-6))
    v = keys[0][1]
    for f, val in keys:
        if f <= fr:
            v = val
    return v


def linear_value(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return keys[-1][1]


def render_images(manifest_path, *, params=None, approach=None, fps=None, px=520, clock0=7.0, times=None):
    """Render all twin frames, or only the requested absolute ``times``."""
    manifest_path = Path(manifest_path)
    man = json.loads(manifest_path.read_text(encoding="utf-8"))
    R, G = load_atlas(manifest_path.parent / man["atlas"]["file"])
    P = dict(ag.SCALAR_DEFAULTS)
    P.update({k: float(v) for k, v in man["light_function_params"].items() if k in P})
    P.update({k: float(v) for k, v in (params or {}).items()})
    display_fps = float(man.get("display_fps", man["take"]["fps"]))
    output_fps = display_fps if fps is None else float(fps)
    keys = ag.schedule_keys(man["schedule"], 0, display_fps)
    approach = [[0, 0]] if approach is None else approach
    N = int(px)
    s = (np.arange(N) + 0.5) / N
    SX, SY = np.meshgrid(s, s)
    UV = np.stack([1.0 - SY, SX], -1)
    band = int(N / P["BorderAspect"] * P["Scale"] * 1.12) if P["BorderDepth"] > 0 else N
    y0 = max(0, (N - band) // 2)
    frames = []
    total = man["take"]["duration_s"]
    sample_times = ([i / output_fps for i in range(int(round(total * output_fps)))]
                    if times is None else [float(value) for value in times])
    for t in sample_times:
        lf = light_function(R, G, P, UV, step_value(keys, t, display_fps), clock0 + t,
                            linear_value(approach, t))
        warm = np.array([255, 196, 120]) / 255.0
        img = (lf[..., None] * warm[None, None, :] * 0.95 + 0.03) ** (1 / 1.4)
        frames.append(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)[y0:y0 + band]))
    return frames, band, output_fps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("out")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--approach", default="[[0,0]]")
    ap.add_argument("--fps", type=float)
    ap.add_argument("--px", type=int, default=520)
    ap.add_argument("--clock0", type=float, default=7.0)
    a = ap.parse_args()
    frames, band, output_fps = render_images(
        a.manifest, params=json.loads(a.params), approach=json.loads(a.approach),
        fps=a.fps, px=a.px, clock0=a.clock0,
    )
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=int(round(1000 / output_fps)), loop=0)
    stills = [frames[int(x * output_fps)] for x in (0.5, 2.5, 3.7, 4.1, 6.0, 8.5)
              if int(x * output_fps) < len(frames)]
    sheet = Image.new("RGB", (stills[0].width * 3, stills[0].height * 2))
    for k, im in enumerate(stills):
        sheet.paste(im, ((k % 3) * im.width, (k // 3) * im.height))
    sheet.save(Path(a.out).with_suffix(".png"))
    print("TWIN|frames=%d|display_fps=%g|band=%d|out=%s" % (len(frames), output_fps, band, a.out))


if __name__ == "__main__":
    main()
