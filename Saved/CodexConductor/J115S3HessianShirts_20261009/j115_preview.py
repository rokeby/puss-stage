"""Generate the offline source/target review sheet for job 115."""
from __future__ import annotations

import os
import json

from PIL import Image, ImageDraw, ImageFont

import j115_core as C

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SOURCE = os.path.join(PROJECT, "Saved", "CodexConductor", "ShroudHessian_20261008", "T_Shroud_Weave_BC.png")
MEASURE = C.texture_mean(SOURCE)
with open(os.path.join(HERE, "j115_source_measurement.json"), "w", encoding="utf-8", newline="\n") as handle:
    json.dump(MEASURE, handle, indent=2, sort_keys=True)
    handle.write("\n")


def font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


source = Image.open(SOURCE).convert("RGB")
source.thumbnail((620, 620))
canvas = Image.new("RGB", (1500, 850), "#15191c")
draw = ImageDraw.Draw(canvas)
draw.text((50, 30), "Job 115 - S3 shirt match to hessian", fill="#f1e6ce", font=font(34))
draw.text((50, 78), "Offline source measurement; rendered scene approval remains required", fill="#aeb9c2", font=font(20))
canvas.paste(source, (50, 130))
mean = MEASURE["mean_srgb"]
rgb = tuple(round(x * 255) for x in mean)
draw.rectangle((760, 155, 1390, 455), fill=rgb, outline="#eeeeee", width=3)
draw.text((760, 485), "Measured hessian mean sRGB", fill="#eeeeee", font=font(24))
draw.text((760, 525), str(tuple(round(x, 6) for x in mean)), fill="#c9d2d9", font=font(20))
draw.text((760, 565), "Measured hessian mean linear", fill="#eeeeee", font=font(24))
draw.text((760, 605), str(tuple(round(x, 6) for x in MEASURE["mean_linear"])), fill="#c9d2d9", font=font(20))
draw.text((760, 665), "Texture-param parents: shared weave BC + N", fill="#e6c68f", font=font(20))
draw.text((760, 700), "Fallback parents: mean tint + roughness 0.84", fill="#e6c68f", font=font(20))
draw.text((50, 790), "Stills: B02 overlap, B08 body-shape pair, B11 Shore05/P40 variants.", fill="#d4bea0", font=font(19))
out = os.path.join(HERE, "J115_Shirt_Hessian_Preview.png")
canvas.save(out)
print("J115_PREVIEW_OK|%s|mean_srgb=%s|mean_linear=%s" %
      (out, tuple(MEASURE["mean_srgb"]), tuple(MEASURE["mean_linear"])))
