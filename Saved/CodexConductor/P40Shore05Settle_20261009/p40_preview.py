"""Generate offline placement and colour review sheets from the pure P40 plan."""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p40_core as C  # noqa: E402


def font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


cfg = C.validate_args({"mode": "DRY", "extra_count": 5, "seed": 4005})
cams = [{"label": "B-shot camera envelope", "xy": [12000.0, 158000.0], "yaw_deg": -90.0}]
plan = C.build_placement_plan(cfg, [], cams)

im = Image.new("RGB", (1500, 900), "#111820")
d = ImageDraw.Draw(im)
d.text((50, 35), "P40 Shore05 + optional variants — seeded free-spot plan", fill="#f1e6ce", font=font(34))
d.text((50, 82), "Diagram only: live DRY re-reads B-shot keys and existing actors before APPLY", fill="#a8b4c0", font=font(20))
x0, x1, y0, y1 = 2350.0, 4050.0, -800.0, 850.0
box = (90, 145, 1410, 815)
d.rectangle(box, outline="#768493", width=3)


def sx(x): return box[0] + (x - x0) / (x1 - x0) * (box[2] - box[0])
def sy(y): return box[3] - (y - y0) / (y1 - y0) * (box[3] - box[1])


for row in plan["placements"]:
    x, y = row["local_xy_cm"]
    r = 24 if row["slot"] == 0 else 18
    colour = "#e5a65a" if row["slot"] == 0 else "#8ac4a5"
    d.ellipse((sx(x)-r, sy(y)-r, sx(x)+r, sy(y)+r), fill=colour, outline="#ffffff", width=2)
    d.text((sx(x)+r+6, sy(y)-10), row["label"], fill="#e8edf2", font=font(15))
d.text((100, 825), "Orange = required Shore05. Green = optional extra_count 1..5. Dune Z uses s3_beach_v2.sand_height.",
       fill="#c4ccd4", font=font(18))
im.save(os.path.join(HERE, "P40_Placement_Preview.png"))

sw = Image.new("RGB", (1500, 700), "#171717")
d = ImageDraw.Draw(sw)
d.text((50, 35), "P40 underwear colour target — weave mean × WeaveTint", fill="#f1e6ce", font=font(34))
d.text((50, 82), "Live DRY reads each MI_Shroud_Hessian_* WeaveTint; these swatches show representative multipliers.",
       fill="#a8b4c0", font=font(20))
tints = [(1.0, 1.0, 1.0, 1.0), (0.90, 0.78, 0.62, 1.0), (0.70, 0.82, 0.92, 1.0)]
for index, tint in enumerate(tints):
    linear = C.cloth_colour(tint)
    srgb = [12.92*x if x <= 0.0031308 else 1.055*(x ** (1/2.4))-0.055 for x in linear[:3]]
    rgb = tuple(max(0, min(255, round(x * 255))) for x in srgb)
    y = 150 + index * 165
    d.rectangle((80, y, 520, y+110), fill=rgb, outline="#eeeeee", width=2)
    d.text((560, y+8), "WeaveTint = %s" % (tuple(round(x, 3) for x in tint[:3]),), fill="#eeeeee", font=font(20))
    d.text((560, y+48), "Target linear RGBA = %s" % (tuple(round(x, 6) for x in linear),), fill="#c6d0da", font=font(19))
    d.text((560, y+80), "Preview sRGB8 = %s" % (rgb,), fill="#9daab5", font=font(17))
d.text((80, 650), "Colour math is measured offline; rendered material response remains Gary's acceptance.",
       fill="#d0b98e", font=font(18))
sw.save(os.path.join(HERE, "P40_Underwear_Colour_Preview.png"))
print("P40_PREVIEWS_OK|placement=P40_Placement_Preview.png|colour=P40_Underwear_Colour_Preview.png")

