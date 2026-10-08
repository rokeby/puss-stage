"""Render offline B06-band wall elevations: old, new, and side-by-side (not an Unreal render)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
NEW_TABLE = HERE / "placement_S03_dense.json"
OLD_TABLE = HERE.parent / "clamber" / "placement_S03_grease.json"
OUT_DIR = HERE / "previews"
W, H = 1200, 650
PAD = (70, 60, 35, 55)


def font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def map_xy(along, height, band):
    alo, ahi = band["along_cm"]
    zlo, zhi = band["height_cm"]
    x = PAD[0] + (along - alo) / (ahi - alo) * (W - PAD[0] - PAD[2])
    y = H - PAD[3] - (height - zlo) / (zhi - zlo) * (H - PAD[1] - PAD[3])
    return x, y


def polygon(row, band):
    a, z = row["along_cm"], row["height_cm"]
    rw, rh = row["size_cm"]
    ang = math.radians(row["roll_on_wall_deg"])
    pts = []
    for x, y in ((-rw / 2, -rh / 2), (rw / 2, -rh / 2), (rw / 2, rh / 2), (-rw / 2, rh / 2)):
        da = x * math.cos(ang) - y * math.sin(ang)
        dz = x * math.sin(ang) + y * math.cos(ang)
        pts.append(map_xy(a + da, z + dz, band))
    return pts


def dune_points(old_rows, band):
    samples = sorted((r["along_cm"], r["dune_floor_cm"]) for r in old_rows)
    points = []
    for i in range(101):
        a = band["along_cm"][0] + (band["along_cm"][1] - band["along_cm"][0]) * i / 100.0
        floor = min(samples, key=lambda p: abs(p[0] - a))[1]
        points.append(map_xy(a, floor, band))
    return points


def render(rows, old_rows, band, title, subtitle, new):
    im = Image.new("RGB", (W, H), (214, 211, 201))
    d = ImageDraw.Draw(im, "RGBA")
    left, top, right, bottom = PAD[0], PAD[1], W - PAD[2], H - PAD[3]
    for a in range(int(band["along_cm"][0] // 100) * 100, int(band["along_cm"][1]) + 1, 100):
        x, _ = map_xy(a, 0, band)
        d.line((x, top, x, bottom), fill=(120, 115, 105, 45), width=1)
    for z in range(0, 901, 100):
        _, y = map_xy(band["along_cm"][0], z, band)
        d.line((left, y, right, y), fill=(120, 115, 105, 45), width=1)
        d.text((8, y - 7), "%dm" % (z // 100), fill=(55, 52, 48, 230), font=font(13))
    dunes = dune_points(old_rows, band)
    dune_poly = [(left, bottom)] + dunes + [(right, bottom)]
    d.polygon(dune_poly, fill=(151, 129, 96, 170))
    d.line(dunes, fill=(84, 66, 43, 230), width=2)
    for row in rows:
        if new:
            if row["event_kind"] == "finger_scratch":
                fill, outline = (87, 10, 8, 150), (62, 3, 2, 215)
            elif row["event_kind"] in ("drag_smear", "cluster"):
                fill, outline = (118, 29, 23, 115), (72, 15, 12, 190)
            else:
                fill, outline = (105, 20, 17, 140), (61, 8, 6, 220)
        else:
            fill, outline = (225, 222, 205, 105), (105, 99, 83, 150)
        pts = polygon(row, band)
        d.polygon(pts, fill=fill)
        d.line(pts + [pts[0]], fill=outline, width=1)
    d.rectangle((left, top, right, bottom), outline=(40, 38, 34, 220), width=2)
    d.text((left, 12), title, fill=(30, 27, 24, 255), font=font(24))
    d.text((left, 40), subtitle, fill=(55, 50, 45, 255), font=font(14))
    d.text((left, H - 35), "right-wall local distance through B06 band (m)", fill=(45, 42, 38, 255), font=font(14))
    for a in range(int(band["along_cm"][0]), int(band["along_cm"][1]) + 1, 250):
        x, _ = map_xy(a, 0, band)
        d.text((x - 15, H - 52), "%.1f" % (a / 100.0), fill=(45, 42, 38, 255), font=font(12))
    return im


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", type=Path, default=NEW_TABLE)
    ap.add_argument("--old", type=Path, default=OLD_TABLE)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    new_doc = json.loads(args.table.read_text(encoding="utf-8"))
    old_doc = json.loads(args.old.read_text(encoding="utf-8"))
    band = new_doc["band"]
    old = [r for r in old_doc["decals"] if r["wall"] == "R" and
           band["along_cm"][0] <= r["along_cm"] <= band["along_cm"][1]]
    new = new_doc["decals"]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    old_im = render(old, old, band, "OLD: broad grease distribution", "%d marks in the B06 band" % len(old), False)
    new_im = render(new, old, band, "NEW: desperate climb trails", "%d marks = %.1fx; zero outside band" %
                    (len(new), new_doc["density"]), True)
    old_path, new_path = args.out_dir / "p12_b06_old.png", args.out_dir / "p12_b06_new.png"
    old_im.save(old_path)
    new_im.save(new_path)
    sheet = Image.new("RGB", (W * 2, H), (240, 240, 240))
    sheet.paste(old_im, (0, 0)); sheet.paste(new_im, (W, 0))
    sheet_path = args.out_dir / "p12_b06_old_vs_new.png"
    sheet.save(sheet_path)
    report = {"schema": "hp_dense_preview/1", "tier": "measured geometry; inferred Unreal look",
              "old_count": len(old), "new_count": len(new), "density": new_doc["density"], "band": band,
              "files": [p.name for p in (old_path, new_path, sheet_path)],
              "table_sha256": hashlib.sha256(args.table.read_bytes()).hexdigest()}
    (args.out_dir / "p12_b06_preview_report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n",
                                                               encoding="utf-8")
    print("P12_PREVIEW_OK|old=%d|new=%d|files=3|out=%s" % (len(old), len(new), args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
