"""Create the deterministic P06 FX timing/route preview PNG (offline only)."""
from __future__ import annotations

import json
import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "p06_fx_preview.png"
DATA = HERE / "p06_fx_preview_data.json"
DURATION = 126.0011
SECTIONS = [0.0, 12.6317, 36.5018, 49.0870, 62.2295, 68.9168, 74.0717, 80.2946, 88.2358, 95.5269, 124.8305]
EVENTS = [
    {"name": "domino creak", "start": 29.7896, "end": 29.7896, "kind": "existing"},
    {"name": "domino impact", "start": 37.0, "end": 37.0, "kind": "existing"},
    {"name": "dark", "start": 52.1488, "end": 126.0011, "kind": "existing"},
    {"name": "car", "start": 68.55, "end": 68.55, "kind": "existing"},
    {"name": "motes", "start": 68.55, "end": 82.7, "kind": "proposal"},
    {"name": "wing burn", "start": 86.7, "end": 102.7, "kind": "proposal"},
    {"name": "fire basket", "start": 94.6, "end": 126.0, "kind": "proposal"},
    {"name": "bee 1", "start": 80.0, "end": 82.5, "kind": "existing"},
    {"name": "bee 2", "start": 100.0, "end": 103.0, "kind": "existing"},
    {"name": "bee 3", "start": 118.0, "end": 122.0, "kind": "existing"},
]
ROUTE = [
    {"name": "motes / Wing 052", "station_cm": 18750, "kind": "proposal"},
    {"name": "burn / Wing 044 L", "station_cm": 24750, "kind": "proposal"},
    {"name": "fire / Wing 049 L", "station_cm": 25950, "kind": "proposal"},
]


def font(size, bold=False):
    candidates = [
        pathlib.Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        pathlib.Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def main():
    width, height = 1800, 980
    image = Image.new("RGB", (width, height), "#101218")
    draw = ImageDraw.Draw(image)
    title, body, small = font(34, True), font(22), font(17)
    left, right = 210, 1560
    scale = (right - left) / DURATION
    x = lambda t: left + t * scale
    draw.text((60, 35), "P06 FX - offline cue proposal (NOT APPLIED)", font=title, fill="#f2eee6")
    draw.text((60, 84), "Times are P06-relative. Grey = measured existing event; amber = proposed args default.",
              font=small, fill="#aeb7c6")

    y = 150
    draw.text((60, y), "Music sections", font=body, fill="#dce4ef")
    for i in range(len(SECTIONS) - 1):
        a, b = SECTIONS[i], SECTIONS[i + 1]
        color = "#26303c" if i % 2 == 0 else "#303947"
        draw.rectangle((x(a), y, x(b), y + 45), fill=color, outline="#627085")
        if b - a > 7:
            draw.text((x(a) + 5, y + 12), "%.1f" % a, font=small, fill="#c4cedb")
    draw.text((x(SECTIONS[-1]) + 5, y + 12), "124.8", font=small, fill="#c4cedb")

    y += 85
    row_h = 48
    for event in EVENTS:
        draw.text((60, y + 12), event["name"], font=small, fill="#dce4ef")
        color = "#e6a23c" if event["kind"] == "proposal" else "#7f8b99"
        if abs(event["end"] - event["start"]) < 0.01:
            draw.line((x(event["start"]), y + 5, x(event["start"]), y + 39), fill=color, width=5)
        else:
            draw.rounded_rectangle((x(event["start"]), y + 7, max(x(event["end"]), x(event["start"]) + 5), y + 37),
                                   radius=7, fill=color)
        draw.text((right + 18, y + 12), "%.1f%s" % (event["start"],
                  ("-%.1f" % event["end"]) if event["end"] != event["start"] else ""),
                  font=small, fill="#aeb7c6")
        y += row_h

    axis_y = y + 10
    draw.line((left, axis_y, right, axis_y), fill="#8e99a8", width=2)
    for t in range(0, 127, 10):
        draw.line((x(t), axis_y - 5, x(t), axis_y + 6), fill="#8e99a8", width=2)
        draw.text((x(t) - 10, axis_y + 10), str(t), font=small, fill="#aeb7c6")
    draw.text((right + 10, axis_y + 10), "s", font=small, fill="#aeb7c6")

    route_y = axis_y + 70
    draw.text((60, route_y), "Route placement (station)", font=body, fill="#dce4ef")
    route_min, route_max = 0.0, 28000.0
    route_scale = (right - left) / (route_max - route_min)
    xr = lambda cm: left + (cm - route_min) * route_scale
    draw.line((left, route_y + 55, right, route_y + 55), fill="#6e7886", width=5)
    label_dx = {"motes / Wing 052": -110, "burn / Wing 044 L": -185,
                "fire / Wing 049 L": 15}
    for row in ROUTE:
        px = xr(row["station_cm"])
        draw.line((px, route_y + 25, px, route_y + 80), fill="#e6a23c", width=6)
        draw.text((px + label_dx[row["name"]], route_y + 88),
                  "%s\n%.1f m" % (row["name"], row["station_cm"] / 100.0),
                  font=small, fill="#f0c57d", spacing=3)
    draw.text((60, height - 45), "Creative windows are inferred proposals. Rendered acceptance remains open.",
              font=small, fill="#d67f79")

    image.save(OUT)
    DATA.write_text(json.dumps({"duration_s": DURATION, "sections_s": SECTIONS,
                                "events": EVENTS, "route": ROUTE, "status": "not_applied"}, indent=2),
                    encoding="utf-8")
    print("P06FX_PREVIEW_OK|png=%s|events=%d|route=%d" % (OUT, len(EVENTS), len(ROUTE)))


if __name__ == "__main__":
    main()
