"""Measure the floor control bench from its SIDE orthographic show-only frames (plain Python + PIL).

    python Scripts/curtain_floor_bench_measure.py [floor_control|floor_timing]

Side camera: at +Y looking -Y, so screen-right is world +X (upstage) and up is +Z; ortho width
2600 cm over 640 px. Cloth pixels are the base-colour red. Per frame: z-range, x-spread (upstage,
relative to the curtain's start) and the fraction of cloth pixels below z = 0. Writes
Saved/CodexSoftGoods/<bench>_measure.json and <bench>_side_sheet.png.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
NAME = sys.argv[1] if len(sys.argv) > 1 else "floor_control"
FR = ROOT / "Saved" / "CodexSoftGoods" / "Frames" / NAME
LOG = json.loads((ROOT / "Saved" / "CodexSoftGoods" / f"{NAME}_bench.json").read_text(encoding="utf-8"))
W, H = LOG["side"]["w"], LOG["side"]["h"]
CM_PX = LOG["side"]["ortho_width"] / W


def is_cloth(p):
    r, g, b = p[:3]
    return r > 25 and r > 1.6 * g and r > 1.6 * b


def measure(path, center, base):
    im = Image.open(path).convert("RGB")
    px = im.load()
    zs, xs = [], []
    for y in range(H):
        for x in range(W):
            if is_cloth(px[x, y]):
                zs.append(center[2] + (H / 2 - y) * CM_PX)
                xs.append(center[0] - base[0] + (x - W / 2) * CM_PX)
    if not zs:
        return {"pixels": 0}
    below = sum(1 for z in zs if z < -5.0) / len(zs)
    return {"pixels": len(zs), "z_min": round(min(zs)), "z_max": round(max(zs)), "x_min": round(min(xs)),
            "x_max": round(max(xs)), "spread_x": round(max(xs) - min(xs)), "frac_below_floor": round(below, 3)}


result = {}
ticks = sorted({int(p.stem.split("_")[-1]) for p in FR.glob("*_side_*.png")})
for tag, info in LOG["variants"].items():
    result[tag] = {t: measure(FR / f"{tag}_side_{t:04d}.png", info["side_center"], info["base"]) for t in ticks}
(ROOT / "Saved" / "CodexSoftGoods" / f"{NAME}_measure.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

hold, drop = LOG["hold"], LOG["drop"]
show = [t for t in sorted({hold - 2, hold + drop // 2, hold + drop, hold + 16, hold + 30, ticks[-1]}) if t in ticks]
tw, th = 320, 180
sheet = Image.new("RGB", (tw * len(show), (th + 4) * len(result)), "black")
d = ImageDraw.Draw(sheet)
for r, tag in enumerate(result):
    for c, t in enumerate(show):
        im = Image.open(FR / f"{tag}_side_{t:04d}.png").convert("RGB").resize((tw, th))
        x0, y0 = c * tw, r * (th + 4)
        sheet.paste(im, (x0, y0))
        info = LOG["variants"][tag]
        y_floor = y0 + (H / 2 - (0 - info["side_center"][2]) / CM_PX) * th / H     # z = 0 line
        d.line([(x0, y_floor), (x0 + tw, y_floor)], fill=(0, 200, 255))
        d.text((x0 + 4, y0 + 4), f"{tag} t{t}", fill="yellow")
sheet.save(ROOT / "Saved" / "CodexSoftGoods" / f"{NAME}_side_sheet.png")

for tag, rows in result.items():
    print(tag, " | ".join(f"t{t} z[{rows[t].get('z_min')},{rows[t].get('z_max')}] sp {rows[t].get('spread_x')} bl {rows[t].get('frac_below_floor')}"
                          for t in show))
