"""Render P75 ownership/timing PNGs from the same pure plan as the live tool."""
from __future__ import annotations

import importlib.util
import json
import os
from typing import Any

from PIL import Image, ImageDraw, ImageFont


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p75_core", os.path.join(HERE, "chandelier_staging_core.py"))
CORE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CORE)

BG, PANEL, GRID = (13, 16, 23), (26, 31, 42), (66, 75, 91)
TEXT, MUTED = (230, 235, 242), (155, 166, 183)
AMBER, BLUE, RED, GREEN = (238, 172, 82), (105, 168, 255), (235, 95, 95), (98, 204, 143)


def _font(size: int) -> ImageFont.ImageFont:
    for path in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _timeline(path: str, title: str, duration: float, rows: list[dict[str, Any]], notes: list[str]) -> None:
    width, height = 1500, 250 + 72 * len(rows) + 34 * len(notes)
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    title_font, row_font, small_font = _font(30), _font(20), _font(17)
    left, right, top = 330, width - 55, 105
    draw.text((45, 30), title, fill=TEXT, font=title_font)
    draw.text((45, 70), "P75 offline forecast - live DRY and rendered acceptance remain required", fill=MUTED, font=small_font)
    for second in range(0, int(duration) + 1, 5):
        x = left + (right - left) * second / duration
        draw.line((x, top - 15, x, top + 72 * len(rows)), fill=GRID, width=1)
        draw.text((x - 10, top - 42), str(second), fill=MUTED, font=small_font)
    draw.text((right + 8, top - 42), "s", fill=MUTED, font=small_font)
    for index, row in enumerate(rows):
        y = top + index * 72
        draw.rounded_rectangle((35, y, width - 35, y + 54), radius=8, fill=PANEL)
        draw.text((52, y + 14), row["label"], fill=TEXT, font=row_font)
        for start, end, color in row.get("segments", []):
            x0, x1 = (left + (right - left) * start / duration,
                      left + (right - left) * end / duration)
            draw.rounded_rectangle((x0, y + 12, max(x0 + 3, x1), y + 42), radius=6, fill=color)
        for moment, label, color in row.get("markers", []):
            x = left + (right - left) * moment / duration
            draw.line((x, y + 7, x, y + 47), fill=color, width=3)
            draw.text((x + 5, y + 15), label, fill=color, font=small_font)
    note_y = top + 72 * len(rows) + 30
    for note in notes:
        draw.text((45, note_y), note, fill=MUTED, font=small_font)
        note_y += 34
    image.save(path, format="PNG", optimize=True)


def render(args_path: str | None = None) -> dict[str, str]:
    with open(args_path or os.path.join(HERE, "chandelier_staging_args.json"), encoding="utf-8") as handle:
        args = json.load(handle)
    with open(os.path.join(HERE, "chandelier_Iron3_chain.json"), encoding="utf-8") as handle:
        chain = json.load(handle)
    plan = CORE.build_plan(args, chain)
    opening = plan["parts"]["opening"]
    opening_path = os.path.join(HERE, "p75_opening_timeline.png")
    _timeline(opening_path, "P75 - Opening hidden-shadow chandelier", args["opening_duration_s"], [
        {"label": "Body + 24 chain links", "segments": [(0.0, args["opening_duration_s"], BLUE)]},
        {"label": "Drive-by spot keys (P75)",
         "segments": [(opening["drive_by"]["start_s"], opening["drive_by"]["end_s"], AMBER)],
         "markers": [(opening["drive_by"]["peak_s"], "peak", TEXT)]},
        {"label": "2 opening grouped lights", "segments": [(0.0, args["opening_duration_s"], AMBER)]},
        {"label": "Flames (P56, not P75)", "segments": []},
        {"label": "Swing keys (P52/52b, not P75)", "segments": []},
    ], [
        "Body and links are Hidden In Game with Cast Hidden Shadow ON.",
        "Projected peak shadow: %.1f x %.1f cm (similar-triangle forecast)." %
        (opening["projected_shadow_at_peak"]["width_cm"], opening["projected_shadow_at_peak"]["height_cm"]),
        "Global guard including P06: 4 P75 lights total, 2 shadow casters total.",
    ])
    p06 = plan["parts"]["p06"]
    p06_path = os.path.join(HERE, "p75_p06_0_30_timeline.png")
    _timeline(p06_path, "P75 - P06 placement and ownership, 0-30 s", 30.0, [
        {"label": "Body + 24 chain links", "segments": [(0.0, 30.0, BLUE)]},
        {"label": "1 P06 grouped light (OFF)", "segments": []},
        {"label": "Flames (P56, not P75)", "segments": []},
        {"label": "Swing keys (P52/52b, not P75)", "segments": []},
        {"label": "Chain A", "markers": [(p06["first_chain_creak_s"], "first creak 24.89", RED)]},
    ], [
        "Hang station %.0f cm; topple clearance %.0f cm; wing clearance %.0f cm." %
        (p06["hang_station_cm"], p06["clearances_cm"]["nearest_topple_row"],
         p06["clearances_cm"]["nearest_wing_station"]),
        "P75 writes no P06 sequence tracks and adds no sound.",
        "Actor labels for P56 and P52b are emitted in p75_offline_plan.json and each APPLY record.",
    ])
    return {"opening": opening_path, "p06": p06_path}


if __name__ == "__main__":
    for name, path in render().items():
        print("P75_TIMELINE|%s=%s" % (name.upper(), path))
