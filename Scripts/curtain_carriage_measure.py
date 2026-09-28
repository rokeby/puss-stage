"""Measure the carriage probe: does the hem move WITH the heading (carried) or lag (free cloth)?

    python Scripts/curtain_carriage_measure.py

From the side orthographic show-only frames (screen-right = world +X upstage, up = +Z, 2600 cm wide):
per capture, the heading = cloth pixels within BAND cm of the top, the hem = within BAND cm of the
bottom; reports their mean x and the z extremes relative to the curtain's start.
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FR = ROOT / "Saved" / "CodexSoftGoods" / "Frames" / "carriage"
LOG = json.loads((ROOT / "Saved" / "CodexSoftGoods" / "carriage_bench.json").read_text(encoding="utf-8"))
W, H = LOG["side"]["w"], LOG["side"]["h"]
CM_PX = LOG["side"]["ortho_width"] / W
BAND = 40.0


def pts(path, center, base):
    im = Image.open(path).convert("RGB")
    px = im.load()
    out = []
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            if r > 25 and r > 1.6 * g and r > 1.6 * b:
                out.append((center[0] - base[0] + (x - W / 2) * CM_PX, center[2] + (H / 2 - y) * CM_PX))
    return out


caps = LOG["captures"]
hold = LOG["hold"]
result = {}
for tag, info in LOG["variants"].items():
    rows = []
    for c, t in caps:
        if c < hold - 2 or c > hold + 25:
            continue
        p = pts(FR / f"{tag}_side_{c:04d}.png", info["side_center"], info["base"])
        if not p:
            continue
        zmax, zmin = max(z for _, z in p), min(z for _, z in p)
        top = [x for x, z in p if z > zmax - BAND]
        bot = [x for x, z in p if z < zmin + BAND]
        rows.append({"cap": c, "t": round(t - LOG["hold"] * 0 - (caps[hold][1] if hold < len(caps) else 0), 3),
                     "head_x": round(sum(top) / len(top)), "hem_x": round(sum(bot) / len(bot)),
                     "z_max": round(zmax), "z_min": round(zmin)})
    result[tag] = rows
(ROOT / "Saved" / "CodexSoftGoods" / "carriage_measure.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
for tag, rows in result.items():
    print(tag)
    for r in rows:
        print(f"  t{r['t']:+.3f}s  head_x {r['head_x']:5d}  hem_x {r['hem_x']:5d}  z_max {r['z_max']:5d}  z_min {r['z_min']:5d}")
