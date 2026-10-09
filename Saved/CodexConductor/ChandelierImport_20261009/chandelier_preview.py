"""Offline look preview for P80. This does not write Unreal assets."""
from __future__ import annotations

import argparse
import json
import os

from PIL import Image, ImageDraw

import chandelier_import_core as core


def render(dusty_path, clean_path, masks_path, out_path, values=None):
    values = dict(core.DEFAULTS, **(values or {}))
    dusty = Image.open(dusty_path).convert("RGB")
    clean = Image.open(clean_path).convert("RGB").resize(dusty.size)
    masks = Image.open(masks_path).convert("RGBA").resize(dusty.size)
    dpx, cpx, mpx = dusty.load(), clean.load(), masks.load()
    w, h = dusty.size
    aged = Image.new("RGB", (w, h))
    apx = aged.load()
    for y in range(h):
        for x in range(w):
            d, m = dpx[x, y], mpx[x, y]
            dark = max(0.0, 1.0 - (m[0] / 255.0) * values["dust_strength"] * 0.35
                       - (m[1] / 255.0) * values["soot_strength"] * 0.55)
            peel = min(1.0, (m[3] / 255.0) * values["peel_strength"])
            iron = (46, 41, 33)
            apx[x, y] = tuple(int(max(0, min(255, d[i] * dark * (1.0 - peel) + iron[i] * peel))) for i in range(3))
    thumb = (512, 512)
    panels = [dusty.resize(thumb), aged.resize(thumb), clean.resize(thumb), masks.resize(thumb).convert("RGB")]
    sheet = Image.new("RGB", (thumb[0] * 2, thumb[1] * 2 + 72), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    labels = ("Dusty source", "Aged master default", "Clean switch", "Masks RGBA")
    for i, (panel, label) in enumerate(zip(panels, labels)):
        x, y = (i % 2) * thumb[0], (i // 2) * thumb[1] + 36
        sheet.paste(panel, (x, y))
        draw.text((x + 8, y - 25), label, fill=(240, 240, 240))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path)
    return {"output": os.path.abspath(out_path), "size": list(sheet.size), "values": values}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dusty", required=True)
    ap.add_argument("--clean", required=True)
    ap.add_argument("--masks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--values-json")
    ns = ap.parse_args()
    values = json.loads(ns.values_json) if ns.values_json else None
    print("CHANDELIER_PREVIEW_OK|" + json.dumps(render(ns.dusty, ns.clean, ns.masks, ns.out, values), sort_keys=True))


if __name__ == "__main__":
    main()
