"""Make a phone-friendly card for Gary from one drop-bake run: side view on top (with a 1 m scale bar), 3/4 below.

    python Scripts/drop_bake_card.py <DROP_ID> <out_name> "<title>"
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DIR = Path(__file__).resolve().parents[1] / "Saved" / "CodexSoftGoods" / "DropBake"
run, out_name, title = sys.argv[1], sys.argv[2], sys.argv[3]
side = Image.open(DIR / f"{run}_side.png").convert("RGB")          # 1280 px = 8 m (ortho)
view = Image.open(DIR / f"{run}_34.png").convert("RGB")
W = side.width
card = Image.new("RGB", (W, 60 + side.height + view.height), (20, 20, 20))
d = ImageDraw.Draw(card)
try:
    font = ImageFont.truetype("arial.ttf", 30)
    small = ImageFont.truetype("arial.ttf", 22)
except OSError:
    font = small = ImageFont.load_default()
d.text((16, 14), title, fill=(240, 230, 200), font=font)
card.paste(side, (0, 60))
card.paste(view, (0, 60 + side.height))
px_per_m = W / 8.0
y = 60 + side.height - 40
d.line([(40, y), (40 + px_per_m, y)], fill=(0, 0, 0), width=6)
d.text((40, y - 32), "1 m", fill=(0, 0, 0), font=small)
d.text((W - 380, 70), "SIDE VIEW (front-to-back)", fill=(60, 60, 60), font=small)
d.text((W - 300, 70 + side.height), "3/4 VIEW", fill=(220, 220, 220), font=small)
out = DIR / f"{out_name}.png"
card.save(out)
print(out)
