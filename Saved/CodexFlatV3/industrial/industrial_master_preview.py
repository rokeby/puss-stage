"""Offline-only schematic preview of the Q3 industrial UV1-metre tile defaults."""
from __future__ import annotations

import importlib.util
import os

from PIL import Image, ImageDraw, ImageFont


HERE = os.path.dirname(os.path.abspath(__file__))
Q3_DEFAULTS = os.path.abspath(os.path.join(
    HERE, "..", "..", "CodexConductor", "Q3_P02IND_P06UV_Scaffold_20261009", "q3_defaults.py"))
OUTPUT = os.path.join(HERE, "industrial_master_uv1_preview.png")


def load_defaults():
    spec = importlib.util.spec_from_file_location("industrial_preview_q3_defaults", Q3_DEFAULTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.P02_DEFAULTS["tile_size_cm"]


def main(output=OUTPUT):
    spans = load_defaults()
    width, height = 1200, 660
    image = Image.new("RGB", (width, height), (25, 27, 28))
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
    except OSError:
        title_font = ImageFont.load_default()
        font = title_font
    draw.text((40, 24), "M_Wing_IndustrialTiling_Master - UV1 metres to centimetre tiles",
              fill=(235, 235, 230), font=title_font)
    draw.text((40, 58), "Schematic only: each panel shows a 6 m x 2 m UV1 surface.",
              fill=(170, 175, 175), font=font)
    colours = {"zinc": ((105, 120, 125), (155, 170, 175)),
               "tarp": ((88, 94, 82), (140, 146, 126)),
               "painted": ((94, 79, 65), (151, 126, 102))}
    for row, name in enumerate(("zinc", "tarp", "painted")):
        x0, y0, x1, y1 = 40, 105 + row * 175, 1160, 245 + row * 175
        u_cm, v_cm = map(float, spans[name])
        cell_w = (x1 - x0) * u_cm / 600.0
        cell_h = (y1 - y0) * v_cm / 200.0
        a, b = colours[name]
        col = 0
        x = x0
        while x < x1:
            y = y0
            rr = 0
            while y < y1:
                draw.rectangle((x, y, min(x + cell_w, x1), min(y + cell_h, y1)),
                               fill=a if (col + rr) % 2 == 0 else b, outline=(205, 205, 195), width=1)
                y += cell_h
                rr += 1
            x += cell_w
            col += 1
        draw.rectangle((x0, y0, x1, y1), outline=(235, 235, 230), width=2)
        draw.text((x0, y1 + 8), "%s  TileSizeCmU=%.0f  TileSizeCmV=%.0f" % (name, u_cm, v_cm),
                  fill=(230, 230, 225), font=font)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    image.save(output)
    return output


if __name__ == "__main__":
    print(main())
