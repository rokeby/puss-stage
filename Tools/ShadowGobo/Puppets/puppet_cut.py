"""Cut-paper shadow-puppet drawing helpers (Bezier outline, tapered knife slits, punches).

Coordinates: 1000 x 1000, y down, facing RIGHT like the reference old man.
Outline = closed chain of cubic Beziers.  Cuts = tapered 'knife slits' along a Bezier (lens-shaped holes)
or small round punches.  Renders: black-on-white cut template, and a projected-shadow preview.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(".")  # set by the caller
SS = 3  # supersample


def bez(p0, p1, p2, p3, n=40):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3


def chain(start, segs):
    """segs: list of (c1, c2, end). Returns polygon points."""
    pts, cur = [], start
    for c1, c2, end in segs:
        b = bez(cur, c1, c2, end)
        pts.extend(b[:-1].tolist())
        cur = end
    pts.append(list(cur))
    return pts


def slit(p0, p1, p2, p3, width, n=48, taper=1.0):
    """Lens-shaped cut along a Bezier: width peaks mid-curve, tapers to knife points."""
    b = bez(p0, p1, p2, p3, n)
    d = np.gradient(b, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    t = np.linspace(0, 1, n)
    w = width * 0.5 * np.sin(np.pi * t) ** taper
    left = b + nrm * w[:, None]
    right = b - nrm * w[:, None]
    return np.concatenate([left, right[::-1]]).tolist()


def punch(cx, cy, r, n=24):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1).tolist()


def render(outline, cuts, rod, name):
    W = 1000 * SS
    img = Image.new("L", (W, W), 255)
    dr = ImageDraw.Draw(img)
    s = lambda poly: [(x * SS, y * SS) for x, y in poly]
    dr.polygon(s(outline), fill=0)
    if rod:
        dr.line(s(rod), fill=0, width=int(7 * SS))
    for c in cuts:
        dr.polygon(s(c), fill=255)
    img = img.resize((1000, 1000), Image.LANCZOS)
    img.save(OUT / f"{name}_template.png")
    # projected preview: soft edge, warm/cool gradient like the reference screen
    shadow = np.asarray(img.filter(ImageFilter.GaussianBlur(1.6)), dtype=np.float64) / 255.0
    x = np.linspace(0, 1, 1000)[None, :]
    cool, warm = np.array([196, 228, 236]), np.array([236, 178, 168])
    bg = (cool[None, None, :] * (1 - x[..., None]) + warm[None, None, :] * x[..., None])
    bg = np.repeat(bg, 1000, axis=0)
    ink = np.array([28, 26, 30])
    prev = bg * shadow[..., None] + ink * (1 - shadow[..., None])
    Image.fromarray(prev.clip(0, 255).astype(np.uint8)).save(OUT / f"{name}_preview.png")
    # SVG (evenodd: cuts are holes)
    def d(poly):
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in poly) + " Z"
    body = d(outline) + " " + " ".join(d(c) for c in cuts)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="200mm" height="200mm">',
           f'<path fill="#000" fill-rule="evenodd" d="{body}"/>']
    if rod:
        svg.append(f'<polyline fill="none" stroke="#000" stroke-width="7" points="{" ".join(f"{x},{y}" for x, y in rod)}"/>')
    svg.append("</svg>")
    (OUT / f"{name}.svg").write_text("\n".join(svg), encoding="utf-8")
