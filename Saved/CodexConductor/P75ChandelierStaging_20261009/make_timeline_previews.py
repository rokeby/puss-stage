"""Render the two required P75 timeline PNGs from the same plan as the live tool."""
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

BG = (13, 16, 23)
PANEL = (26, 31, 42)
GRID = (66, 75, 91)
TEXT = (230, 235, 242)
MUTED = (155, 166, 183)
AMBER = (238, 172, 82)
BLUE = (105, 168, 255)
RED = (235, 95, 95)
GREEN = (98, 204, 143)


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
    left, right, top = 300, width - 55, 105
    draw.text((45, 30), title, fill=TEXT, font=title_font)
    draw.text((45, 70), "P75 offline forecast — values remain Gary-owned args until live DRY/APPLY", fill=MUTED, font=small_font)
    for second in range(0, int(duration) + 1, 5):
        x = left + (right - left) * second / duration
        draw.line((x, top - 15, x, top + 72 * len(rows)), fill=GRID, width=1)
        draw.text((x - 10, top - 42), str(second), fill=MUTED, font=small_font)
    draw.text((right + 8, top - 42), "s", fill=MUTED, font=small_font)
    for index, row in enumerate(rows):
        y = top + index * 72
        draw.rounded_rectangle((35, y, width - 35, y + 54), radius=8, fill=PANEL)
        draw.text((52, y + 14), row["label"], fill=TEXT, font=row_font)
        for segment in row.get("segments", []):
            x0 = left + (right - left) * segment[0] / duration
            x1 = left + (right - left) * segment[1] / duration
            draw.rounded_rectangle((x0, y + 12, max(x0 + 3, x1), y + 42), radius=6,
                                   fill=segment[2])
        for marker in row.get("markers", []):
            x = left + (right - left) * marker[0] / duration
            draw.line((x, y + 7, x, y + 47), fill=marker[2], width=3)
            draw.text((x + 5, y + 15), marker[1], fill=marker[2], font=small_font)
    note_y = top + 72 * len(rows) + 30
    for note in notes:
        draw.text((45, note_y), note, fill=MUTED, font=small_font)
        note_y += 34
    image.save(path, format="PNG", optimize=True)


def render(args_path: str | None = None) -> dict[str, str]:
    args_path = args_path or os.path.join(HERE, "chandelier_staging_args.json")
    with open(args_path, encoding="utf-8") as handle:
        args = json.load(handle)
    plan = CORE.build_plan(args)
    opening = plan["opening"]
    candle_end = opening["candles"][-1]["time_s"]
    opening_path = os.path.join(HERE, "p75_opening_timeline.png")
    _timeline(opening_path, "P75 — Opening hidden-shadow chandelier", opening["duration_s"], [
        {"label": "Body + chain", "segments": [(0.0, opening["duration_s"], BLUE)]},
        {"label": "Drive-by yaw arc", "segments": [(opening["drive_by"]["start_s"], opening["drive_by"]["end_s"], AMBER)],
         "markers": [(opening["drive_by"]["peak_s"], "peak", TEXT)]},
        {"label": "44 candle ignitions", "segments": [(opening["candles"][0]["time_s"], candle_end, GREEN)]},
        {"label": "4 grouped lights", "segments": [(opening["candles"][0]["time_s"], opening["duration_s"], AMBER)]},
    ], [
        "Blue means the mesh exists but is Hidden In Game; Cast Hidden Shadow remains ON.",
        "Projected peak shadow: %.1f × %.1f cm (similar-triangle forecast)." %
        (opening["projected_shadow_at_peak"]["width_cm"], opening["projected_shadow_at_peak"]["height_cm"]),
        "GPU guard: %d grouped point lights, %d shadow casters; 44 individual candle lights are forbidden." %
        (plan["lights"]["grouped_count"], plan["lights"]["shadow_casters"]),
    ])
    p06 = plan["p06"]
    p06_path = os.path.join(HERE, "p75_p06_0_30_timeline.png")
    _timeline(p06_path, "P75 — P06 silent return, 0–30 s", 30.0, [
        {"label": "Visible return", "segments": [(p06["visible_start_s"], 30.0, BLUE)]},
        {"label": "Candles + groups", "segments": [(p06["candle_start_s"], 30.0, AMBER)]},
        {"label": "P52/P52B swing", "segments": [(p06["visible_start_s"], 30.0, GREEN)]},
        {"label": "Chain A", "markers": [(p06["first_chain_creak_s"], "first creak 24.89", RED)]},
        {"label": "New sound", "segments": []},
    ], [
        "Hang station %.0f cm; nearest topple row %.0f cm away; nearest wing station %.0f cm away." %
        (p06["hang_station_cm"], p06["clearances_cm"]["nearest_topple_row"],
         p06["clearances_cm"]["nearest_wing_station"]),
        "Silent means P75 adds no audio section. Optional cue kick defaults OFF.",
        "Swing keys remain owned by P52/P52B REBUILD; P75 does not duplicate the pendulum solver.",
    ])
    return {"opening": opening_path, "p06": p06_path}


if __name__ == "__main__":
    for name, path in render().items():
        print("P75_TIMELINE|%s=%s" % (name.upper(), path))
