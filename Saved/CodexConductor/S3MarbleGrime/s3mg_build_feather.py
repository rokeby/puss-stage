"""Feathered-rectangle RectLight SourceTexture for variant C_soft (Gary 7 Oct: "500 cd, softer edges").

Writes DerivedAssets/S3Marble/Grime_20261007/T_S3MG_StripFeather.png: 1024 x 512 (power of two, <= 1024; 2:1 is
close to the 300 x 120 cm strip, and a RectLight maps the texture onto its whole rectangle regardless of aspect).
Intended import: LINEAR (sRGB OFF), TC_DEFAULT, RGB grey. Value = s(u) * s(v), s(t) = smoothstep(0, F, t) *
smoothstep(0, F, 1 - t), F = FEATHER (fraction of each side over which the edge falls from 1 to 0).
Shared with s3mg_preview_soft.py through feather_profile(), so the preview uses the exact same falloff.
"""
import hashlib
import json

import numpy as np
from PIL import Image

OUT = "E:/PussStage/DerivedAssets/S3Marble/Grime_20261007"
NAME = "T_S3MG_StripFeather.png"
SIZE = (1024, 512)          # (w, h)
FEATHER = 0.22


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def feather_1d(t, f=FEATHER):
    return smoothstep(0.0, f, t) * smoothstep(0.0, f, 1.0 - t)


def feather_profile(u, v, f=FEATHER):
    """u, v in [0, 1] across the light rectangle; 0 outside."""
    inside = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
    return np.where(inside, feather_1d(np.clip(u, 0, 1), f) * feather_1d(np.clip(v, 0, 1), f), 0.0)


def build():
    w, h = SIZE
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    img = feather_profile(u[None, :], v[:, None])
    a8 = (img * 255.0 + 0.5).astype(np.uint8)
    path = OUT + "/" + NAME
    Image.fromarray(np.stack([a8] * 3, -1), "RGB").save(path)
    rep = {"file": path, "size": [w, h], "feather_fraction": FEATHER, "srgb": False, "compression": "TC_DEFAULT",
           "mean": round(float(img.mean()), 4), "centre": round(float(img[h // 2, w // 2]), 4),
           "edge": round(float(img[h // 2, 0]), 4), "corner": round(float(img[0, 0]), 4),
           "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
           "note": "mean < 1 => a textured strip emits ~mean x the untextured energy [inferred: radiance is "
                   "multiplied by the texture; UE 5.8 renderer .cpp not in the install]"}
    json.dump(rep, open(OUT + "/T_S3MG_StripFeather.json", "w"), indent=1)
    return rep


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
