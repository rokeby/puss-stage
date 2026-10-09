"""Offline: build the silhouette contact sheet from a CATSIL run dir (manifest.json + *.rgba from the bench).
Mask polarity is decided per image from the 8-bit capture: the cat is whichever of {alpha-low, alpha-high, lit}
covers the smaller non-empty area (show-only SceneColorHDR writes coverage into alpha; polarity not assumed).
Usage: python make_sheet.py <run_dir>   -> <run_dir>/silhouettes_<view>.png (one row per clip, 4 poses)."""
import json
import os
import sys

from PIL import Image, ImageDraw


def mask_of(raw, w, h):
    a = raw[3::4]
    lum = [max(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 4)]
    cands = [[v < 128 for v in a], [v >= 128 for v in a], [v > 8 for v in lum]]
    sizes = [sum(c) for c in cands]
    best = min((s, i) for i, s in enumerate(sizes) if 0 < s < w * h * 0.9) if any(0 < s < w * h * 0.9 for s in sizes) else (0, 0)
    return cands[best[1]]


def main(run_dir):
    man = json.load(open(os.path.join(run_dir, "manifest.json")))
    w, h = man["res"]
    cw, ch = w // 2, h // 2
    for view in sorted({r["view"] for r in man["rows"]}):
        rows = [r for r in man["rows"] if r["view"] == view]
        clips = []
        for r in rows:
            if r["clip"] not in clips:
                clips.append(r["clip"])
        sheet = Image.new("RGB", (190 + 4 * cw, len(clips) * ch), (245, 240, 230))
        d = ImageDraw.Draw(sheet)
        for ci, clip in enumerate(clips):
            d.text((6, ci * ch + ch // 2 - 6), clip.split("/")[-1].replace("A_Cat_", ""), fill=(0, 0, 0))
            for r in [x for x in rows if x["clip"] == clip]:
                raw = open(os.path.join(run_dir, r["file"]), "rb").read()
                m = mask_of(raw, w, h)
                im = Image.new("L", (w, h), 240)
                im.putdata([20 if v else 240 for v in m])
                sheet.paste(im.resize((cw, ch)).convert("RGB"), (190 + r["k"] * cw, ci * ch))
        p = os.path.join(run_dir, "silhouettes_%s.png" % view)
        sheet.save(p)
        print(p)


if __name__ == "__main__":
    main(sys.argv[1])
