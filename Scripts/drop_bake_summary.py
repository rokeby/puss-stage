"""Summarise drop-bake scout runs: a table sorted by pile depth, and a contact sheet of the renders.

    python Scripts/drop_bake_summary.py v1_        (prefix of the DROP_IDs to include)
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "Saved" / "CodexSoftGoods" / "DropBake"
PREFIX = sys.argv[1] if len(sys.argv) > 1 else ""

rows = []
for p in sorted(DIR.glob(f"{PREFIX}*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    f = d["checkpoints"][str(d["frames"])]
    prev = d["checkpoints"].get(str(d["frames"] - 30), {})
    # settled = the last second changed height by < 5 cm AND depth by < 10 cm (recomputed, so all runs agree)
    d["settled"] = bool(prev) and abs(prev.get("height_m", 0) - f["height_m"]) < 0.05 and abs(prev.get("depth_m", 0) - f.get("depth_m", 0)) < 0.1
    rows.append((d, f))
rows.sort(key=lambda r: -r[1].get("layers", 0))
print(f"(all numbers from the LAST frame; 'settled' compares it with the frame 1 s earlier)")
print(f"{'id':30s} full  bend  comp  depth ratio layers foot  height meanz fold  settled solve")
for d, f in rows:
    print(f"{d['id']:30s} {d['fullness']:4.2f} {d['bend']:5.1f} {d.get('compression', 0):5.1f} {f.get('depth_m', 0):5.2f} "
          f"{f.get('depth_ratio', 0):5.1f} {f.get('layers', 0):6.1f} {f.get('footprint_m2', 0):5.1f} {f['height_m']:5.2f} {f.get('mean_z_m', 0):5.2f} {f.get('fold_size_m') or 0:5.2f}"
          f"  {str(d.get('settled')):5s} {d['solve_seconds_total']:5.0f}s")

w, h = 480, 270
sheet = Image.new("RGB", (w * 2, h * len(rows)), "black")
draw = ImageDraw.Draw(sheet)
for i, (d, f) in enumerate(rows):
    for c, view in enumerate(("34", "side")):
        png = DIR / f"{d['id']}_{view}.png"
        if png.exists():
            sheet.paste(Image.open(png).convert("RGB").resize((w, h)), (c * w, i * h))
    draw.text((6, i * h + 6), f"{d['id']}  layers {f.get('layers', 0):.1f}  depth {f.get('depth_m', 0):.2f} m  height {f['height_m']:.2f} m",
              fill="yellow")
out = DIR / f"summary_{PREFIX or 'all'}.png"
sheet.save(out)
print("sheet:", out)
