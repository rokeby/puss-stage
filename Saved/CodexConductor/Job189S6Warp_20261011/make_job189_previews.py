"""Generate compact SVG timeline previews for the three Job 189 score proposals."""

from pathlib import Path
import json

import job189_core as core


HERE = Path(__file__).resolve().parent
OUT = HERE / "previews"
COLOURS = {
    "Weird": "#ffffff", "Invert": "#ffcf4a", "HueDrift": "#e45cff",
    "Solarize": "#ff6d4a", "ChromaSplit": "#3be6ff", "Warp": "#63ff82", "Mirror": "#7794ff",
}


def svg_for(name, rows):
    width, height = 1280, 520
    left, right, top, bottom = 100, 30, 55, 70
    plot_w, plot_h = width - left - right, height - top - bottom
    duration = rows[-1]["time"]
    x = lambda sec: left + plot_w * sec / duration
    y = lambda value: top + plot_h * (1.0 - value)
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (width, height, width, height),
        '<rect width="100%%" height="100%%" fill="#090b12"/>',
        '<text x="%d" y="30" fill="#fff" font-family="Segoe UI, sans-serif" font-size="20">Job 189 — %s</text>' % (left, name.replace("&", "&amp;")),
    ]
    for level in (0.0, 0.25, 0.5, 0.75, 1.0):
        yy = y(level)
        elements.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#303745" stroke-width="1"/>' % (left, yy, width-right, yy))
        elements.append('<text x="%g" y="%g" fill="#8d96a8" font-family="monospace" font-size="12">%.2f</text>' % (left-45, yy+4, level))
    for second in (0, 4.16, 54.96, 120.12, 160.0, 177.92, 194.0):
        xx = x(second)
        elements.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#252b36" stroke-width="1"/>' % (xx, top, xx, top+plot_h))
        elements.append('<text x="%g" y="%g" fill="#8d96a8" text-anchor="middle" font-family="monospace" font-size="11">%.1fs</text>' % (xx, height-48, second))
    legend_x = left
    for parameter in core.PARAMETERS[:-1]:
        points = " ".join("%.2f,%.2f" % (x(row["time"]), y(row[parameter])) for row in rows)
        colour = COLOURS[parameter]
        elements.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="3"/>' % (points, colour))
        elements.append('<rect x="%g" y="%g" width="12" height="4" fill="%s"/>' % (legend_x, height-22, colour))
        elements.append('<text x="%g" y="%g" fill="#cdd4df" font-family="Segoe UI, sans-serif" font-size="12">%s</text>' % (legend_x+18, height-16, parameter))
        legend_x += 145
    elements.append('</svg>')
    return "\n".join(elements) + "\n"


def main():
    document = json.loads((HERE / "warp_scores.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    for preset in core.PRESETS:
        rows = core.compile_score(document, preset)
        slug = preset.lower().replace("->", "_to_").replace(" ", "_")
        (OUT / (slug + ".svg")).write_text(svg_for(preset, rows), encoding="utf-8")
    print("JOB189_PREVIEWS_OK|count=3|dir=%s" % OUT)


if __name__ == "__main__":
    main()
