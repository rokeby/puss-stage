#!/usr/bin/env python3
"""Find large WINDOWS in a Flat V3 wing cut: enclosed transparent regions fully surrounded by paper.

Offline, pure (numpy + scipy + Pillow). No Unreal.

Input image. The authority for a Flat V3 wing's openings is its CUT MASK, not the skin alpha:
"Silhouette is geometry, not alpha" (Docs/FlatV3Spec_2026-09-30.md:103). The builder reads the mask's first channel
and treats >= 0.5 as paper (Tools/FlatV3/build_v3_flat.py:185-196), so `channel="auto"` here uses the alpha channel
when the image has one that is not constant, else the first channel (R / L) -- the builder's rule.

A WINDOW is a connected transparent region (value < threshold) that touches no image border (8-connectivity on the
transparent set, so a region that leaks to the outside through a single diagonal pixel is NOT enclosed).

Panel coordinates (declaration-proven from the builder, Tools/FlatV3/build_v3_flat.py:322-376):
  * the panel spans the paper bounding box; vertical metres-per-texel = height_cm / (rows of the bbox); the bottom
    of the bbox is z = 0 (the builder's floor_z 0 and the z renormalisation at build_v3_flat.py:984-990);
  * horizontal: the TK builders use an anisotropic texel (tk_build_v3_flat_t5j.py:12-18), so the horizontal scale
    is width_cm / (cols of the bbox) when width_cm is given (build json dimensions_m.width), else square texels.
  * u_cm runs from the IMAGE-LEFT edge of the paper bbox, rightward. Image handedness: in final image handedness
    (Docs/WingGenerationConventions.md:50-53) a *_L image has its exterior/backbone edge on the image LEFT and its
    inward edge RIGHT; a *_R image has the exterior on the RIGHT. `to_pair_y` maps u_cm to pair-local Y using the
    measured inner/outer edges of the placed panel, so the mapping never relies on the mesh's own axis signs
    (mirrored-readback trap, ue58-ism-readback-and-test-traps). The builder agrees: L puts the backbone at the
    image-left column u_min (build_v3_flat.py:363-366).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

try:
    from scipy import ndimage
except ModuleNotFoundError:  # pragma: no cover
    ndimage = None


EIGHT = np.ones((3, 3), dtype=bool)


def load_opacity(path, channel="auto"):
    """float32 opacity in [0,1], rows top-first, from an image file."""
    from PIL import Image
    image = Image.open(path)
    arr = np.asarray(image)
    if arr.dtype != np.uint8 and arr.dtype != np.uint16:
        arr = arr.astype(np.float64)
    scale = 65535.0 if arr.dtype == np.uint16 else 255.0
    if arr.ndim == 2:
        return arr.astype(np.float32) / scale, "L"
    if channel == "auto":
        if arr.shape[2] == 4 and arr[..., 3].min() != arr[..., 3].max():
            channel = "alpha"
        else:
            channel = "first"
    index = 3 if channel == "alpha" else 0
    return arr[..., index].astype(np.float32) / scale, channel


def paper_bbox(opaque):
    rows, cols = np.nonzero(opaque)
    if rows.size == 0:
        raise ValueError("EMPTY_MASK")
    return int(rows.min()), int(rows.max()), int(cols.min()), int(cols.max())


def find_holes(opacity, threshold=0.5):
    """[(label_image, [label ids of enclosed transparent regions])] -- border-touching regions excluded."""
    if ndimage is None:
        raise RuntimeError("SCIPY_REQUIRED")
    transparent = opacity < threshold
    labels, count = ndimage.label(transparent, structure=EIGHT)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])).tolist())
    border.discard(0)
    holes = [i for i in range(1, count + 1) if i not in border]
    return labels, holes


def find_windows(opacity, height_cm, width_cm=None, min_area_m2=0.5, threshold=0.5, outline_stride=4,
                 sample_stride=6):
    """Every enclosed hole, with panel-local geometry; `is_window` marks area >= min_area_m2.

    Returns {"panel": {...}, "holes": [...]} sorted by area, largest first. Each hole carries
    centroid_cm (u, z), bbox_cm (u0, z0, u1, z1), area_m2, pixel count, an outline sample and an interior sample
    (panel cm) used for projection."""
    opaque = opacity >= threshold
    r0, r1, c0, c1 = paper_bbox(opaque)
    rows_span = float(r1 - r0 + 1)
    cols_span = float(c1 - c0 + 1)
    sz = float(height_cm) / rows_span                       # cm per texel, vertical
    su = float(width_cm) / cols_span if width_cm else sz    # cm per texel, horizontal (TK anisotropic grid)
    labels, holes = find_holes(opacity, threshold)
    out = []
    if holes:
        from scipy import ndimage as nd
        objects = nd.find_objects(labels)
        for lab in holes:
            sl = objects[lab - 1]
            sub = labels[sl] == lab
            rr, cc = np.nonzero(sub)
            rr = rr + sl[0].start
            cc = cc + sl[1].start
            n = int(rr.size)
            area_m2 = n * su * sz / 1.0e4

            def to_uz(r, c):
                return (np.asarray(c, dtype=np.float64) + 0.5 - c0) * su, (r1 + 1 - (np.asarray(r, dtype=np.float64) + 0.5)) * sz

            u, z = to_uz(rr, cc)
            # outline: hole pixels with a non-hole 4-neighbour
            padded = np.pad(sub, 1)
            edge = sub & ~(padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:])
            er, ec = np.nonzero(edge)
            er = er + sl[0].start
            ec = ec + sl[1].start
            ou, oz = to_uz(er[::outline_stride], ec[::outline_stride])
            pick = np.arange(0, n, max(1, sample_stride))
            out.append({
                "pixels": n,
                "area_m2": round(area_m2, 4),
                "centroid_cm": [round(float(u.mean()), 2), round(float(z.mean()), 2)],
                "bbox_cm": [round(float(u.min() - su / 2), 2), round(float(z.min() - sz / 2), 2),
                            round(float(u.max() + su / 2), 2), round(float(z.max() + sz / 2), 2)],
                "is_window": bool(area_m2 >= min_area_m2),
                "outline_cm": [[round(float(a), 1), round(float(b), 1)] for a, b in zip(ou, oz)],
                "interior_sample_cm": [[round(float(a), 1), round(float(b), 1)] for a, b in zip(u[pick], z[pick])],
                "sample_stride": int(max(1, sample_stride)),
            })
    out.sort(key=lambda h: -h["pixels"])
    for index, hole in enumerate(out):
        hole["rank"] = index
    return {"panel": {"height_cm": float(height_cm), "width_cm": round(cols_span * su, 3),
                      "cm_per_texel_u": su, "cm_per_texel_z": sz, "bbox_px_rows_cols": [r0, r1, c0, c1],
                      "image_shape": list(opacity.shape), "threshold": threshold, "min_area_m2": min_area_m2},
            "holes": out}


def to_pair_y(u_cm, width_cm, side, inner_edge_cm, outer_edge_cm):
    """Panel u (from image-left) -> pair-local Y, final image handedness.

    L: image-left = exterior (outer edge), image-right = inner edge.  R: image-left = inner edge."""
    f = float(u_cm) / float(width_cm)
    if side == "L":
        return outer_edge_cm + f * (inner_edge_cm - outer_edge_cm)
    if side == "R":
        return inner_edge_cm + f * (outer_edge_cm - inner_edge_cm)
    raise ValueError("SIDE_INVALID|%r" % (side,))


def mask_inside(opacity, panel, u_cm, z_cm, threshold=0.5):
    """True where (u, z) panel cm is paper (outside the bbox counts as not paper)."""
    r0, r1, c0, c1 = panel["bbox_px_rows_cols"]
    c = np.floor(np.asarray(u_cm) / panel["cm_per_texel_u"] + c0).astype(np.int64)
    r = np.floor(r1 + 1 - np.asarray(z_cm) / panel["cm_per_texel_z"]).astype(np.int64)
    h, w = opacity.shape
    ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
    result = np.zeros(np.shape(c), dtype=bool)
    result[ok] = opacity[r[ok], c[ok]] >= threshold
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--mask", required=True)
    parser.add_argument("--height-cm", type=float, default=1000.0)
    parser.add_argument("--width-cm", type=float, default=None)
    parser.add_argument("--min-area-m2", type=float, default=0.5)
    parser.add_argument("--channel", default="auto", choices=("auto", "alpha", "first"))
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)
    opacity, used = load_opacity(args.mask, args.channel)
    result = find_windows(opacity, args.height_cm, args.width_cm, args.min_area_m2)
    result["source"] = {"mask": os.path.abspath(args.mask), "channel": used}
    for hole in result["holes"]:
        hole.pop("interior_sample_cm", None)
    text = json.dumps(result, indent=1)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    windows = [h for h in result["holes"] if h["is_window"]]
    print("FIND_WINDOWS_OK|mask=%s|holes=%d|windows=%d|areas_m2=%s" % (
        os.path.basename(args.mask), len(result["holes"]), len(windows), [h["area_m2"] for h in windows]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
