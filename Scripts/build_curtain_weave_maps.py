"""Derive the curtain's tiling weave maps from the fire-safety curtain's weave detail.

    python Scripts/build_curtain_weave_maps.py

Source: DerivedAssets/FireSafetyCurtainV2/TextureRefinements/FireSafetyCurtain_01_WeaveDetail_v1.png
(1254 px square, tiles cleanly). Outputs to DerivedAssets/CurtainCloth/Chaos/Textures/:

- T_CurtainWeave.png    grey detail, mean 0.5, contrast-normalised: the material multiplies
                        the flat velvet colour by it, so nothing is painted into the colour.
- T_CurtainWeave_N.png  tangent-space normal map (DirectX green, as Unreal expects) from the
                        detail's high-passed luminance.

The weave is thread-scale texture only. Folds and creases come from the Chaos solver.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "DerivedAssets" / "FireSafetyCurtainV2" / "TextureRefinements" / "FireSafetyCurtain_01_WeaveDetail_v1.png"
OUT = ROOT / "DerivedAssets" / "CurtainCloth" / "Chaos" / "Textures"
SIZE = 1024
NORMAL_STRENGTH = 2.5


def wrap_blur(a: np.ndarray, radius: int) -> np.ndarray:
    """Box blur with wrap-around, so the high-pass stays tileable."""
    k = 2 * radius + 1
    out = a.copy()
    for axis in (0, 1):
        acc = np.zeros_like(out)
        for s in range(-radius, radius + 1):
            acc += np.roll(out, s, axis=axis)
        out = acc / k
    return out


def seam_ratio(a: np.ndarray, axis: int) -> float:
    """Wrap-around step over the mean interior step; ~1 means the tile edge is invisible."""
    first, last = np.take(a, 0, axis=axis), np.take(a, -1, axis=axis)
    return float(np.abs(first - last).mean() / np.abs(np.diff(a, axis=axis)).mean())


def make_tileable(a: np.ndarray, axis: int, shift: int, ramp: int) -> np.ndarray:
    """Cross-fade the tile's edges with a copy rolled by `shift`, a whole number of thread
    periods, so the threads stay in phase through the blend and the wrap is continuous."""
    n = a.shape[axis]
    x = np.arange(n, dtype=np.float64)
    edge = np.minimum(x, n - 1 - x)
    w = np.clip(edge / ramp, 0.0, 1.0)
    w = w * w * (3.0 - 2.0 * w)
    shape = [1, 1]
    shape[axis] = n
    w = w.reshape(shape)
    return w * a + (1.0 - w) * np.roll(a, shift, axis=axis)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rgb = np.asarray(Image.open(SOURCE).convert("RGB"), dtype=np.float64) / 255.0
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    # The source repeats every ~13.34 px but its left/right edges do not meet (seam ratio ~1.8).
    # Half the tile is 47 thread periods, so roll by that and fade the edges in.
    source_seam = {"x": seam_ratio(lum, 1), "y": seam_ratio(lum, 0)}
    lum = make_tileable(lum, axis=1, shift=int(round(47 * 13.34)), ramp=160)
    lum = make_tileable(lum, axis=0, shift=int(round(47 * 13.34)), ramp=160)
    lum = np.asarray(Image.fromarray((np.clip(lum, 0, 1) * 65535).astype(np.uint16)).resize((SIZE, SIZE), Image.LANCZOS),
                     dtype=np.float64) / 65535.0

    # High-pass: keep the threads, drop any colour drift across the tile.
    detail = lum - wrap_blur(lum, 24)
    detail = detail / (np.percentile(np.abs(detail), 99) + 1e-9)
    grey = np.clip(0.5 + 0.5 * detail, 0.0, 1.0)
    Image.fromarray((grey * 255.0 + 0.5).astype(np.uint8), "L").save(OUT / "T_CurtainWeave.png")

    # Normal map from the high-passed height, central differences with wrap.
    h = np.clip(detail, -1.0, 1.0)
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * NORMAL_STRENGTH
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5 * NORMAL_STRENGTH
    n = np.dstack((-dx, dy, np.ones_like(h)))   # +dy: DirectX green (image rows run down)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255.0 + 0.5).astype(np.uint8), "RGB").save(OUT / "T_CurtainWeave_N.png")

    report = {"source": str(SOURCE), "size": SIZE, "normal_strength": NORMAL_STRENGTH,
              "grey_mean": float(grey.mean()), "grey_std": float(grey.std()),
              "source_seam_ratio": source_seam, "tile_seam_ratio": {"x": seam_ratio(grey, 1), "y": seam_ratio(grey, 0)}}
    if max(report["tile_seam_ratio"].values()) > 1.25:
        raise SystemExit(f"Weave tile still shows a seam: {report['tile_seam_ratio']}")
    (OUT / "weave_maps_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("CURTAIN_WEAVE_MAPS_SUCCESS|" + json.dumps(report))


if __name__ == "__main__":
    main()
