"""Score the pin check frames: does each curtain's top edge stay where it started?

    python Scripts/curtain_pin_check_score.py

For each curtain, finds the topmost lit-cloth pixel in every image column at t0 and after the hang.
PASS needs >= 95% of the t0 top edge's columns to stay within TOL_PX, and the cloth to still span
>= 95% of its t0 width. A wrong pin collapses one side (the left-edge hang of 28 Sep fails both).
Writes Saved/CodexSoftGoods/curtain_pin_check_result.json and exits non-zero on FAIL.
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "Saved" / "CodexSoftGoods" / "Frames" / "pin_check"
CAPTURE = json.loads((ROOT / "Saved" / "CodexSoftGoods" / "curtain_pin_check.json").read_text(encoding="utf-8"))
HANG = CAPTURE["hang_ticks"]
TOL_PX = 8          # at 360 px tall, ~2% of frame height
NEED = 0.95


def top_edge(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    edge = {}
    for x in range(w):
        for y in range(h):
            r, g, b = px[x, y]
            # Lit velvet under the check lamp reads pink (R~250, G~130), so test hue by difference, not ratio.
            if r > 110 and r - g > 60 and r - b > 60:
                edge[x] = y
                break
    return edge


result = {"curtains": {}, "tol_px": TOL_PX, "need": NEED}
ok_all = bool(CAPTURE.get("captures")) and not CAPTURE.get("errors") and not CAPTURE.get("stray_after")
for tag in CAPTURE["curtains"]:
    e0 = top_edge(FRAMES / f"{tag}_0000.png")
    e1 = top_edge(FRAMES / f"{tag}_{HANG:04d}.png")
    top_y = sorted(e0.values())[len(e0) // 2] if e0 else 0          # median top line at t0
    cols = [x for x in e0 if abs(e0[x] - top_y) < 30]              # the t0 top edge (not side hems or holes)
    held = sum(1 for x in cols if x in e1 and abs(e1[x] - e0[x]) <= TOL_PX)
    width_ratio = (len(e1) / len(e0)) if e0 else 0.0
    frac = held / len(cols) if cols else 0.0
    passed = frac >= NEED and width_ratio >= NEED
    result["curtains"][tag] = {"top_edge_columns": len(cols), "held_fraction": round(frac, 3),
                               "width_ratio": round(width_ratio, 3), "pass": passed}
    ok_all = ok_all and passed
result["pass"] = ok_all
(ROOT / "Saved" / "CodexSoftGoods" / "curtain_pin_check_result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
print(("PIN_CHECK_PASS|" if ok_all else "PIN_CHECK_FAIL|") + json.dumps(result["curtains"]))
sys.exit(0 if ok_all else 1)
