"""Generate offline P87 timeline PNG plus stage-front/frusta SVG."""
from __future__ import annotations

import json
import os

from PIL import Image, ImageDraw, ImageFont

import p87_opening_common as C


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "DerivedAssets", "P87OpeningFixes")


def _font():
    return ImageFont.load_default()


def timeline(path, plan):
    image = Image.new("RGB", (1500, 620), (18, 18, 22)); d = ImageDraw.Draw(image); font = _font()
    d.text((35, 22), "P87 OPENING — PROPOSED, NOT APPLIED", fill=(245, 225, 180), font=font)
    left, right, y = 80, 1440, 180
    end = plan["camera"]["keys"][-1]["frame"]
    x = lambda frame: left + (right - left) * frame / end
    d.line((left, y, right, y), fill=(180, 180, 190), width=3)
    fall = plan["camera"]["hold_end_frame"]
    landed = plan["curtain"]["sections"][1]["end"]
    for frame, label, color in ((0, "Opening start", (160, 160, 170)),
                                (fall, "first flurry / ONE fall / move begins", (255, 110, 90)),
                                (landed, "curtain landed; pile holds", (210, 160, 100)),
                                (end, "exact existing end pose", (90, 220, 160))):
        xx = x(frame); d.line((xx, y - 65, xx, y + 150), fill=color, width=3)
        d.text((max(15, min(xx - 60, 1320)), y - 90), "%s\nf%d / %.2fs" % (label, frame, frame / 25.0), fill=color, font=font)
    d.rectangle((x(fall), y + 35, x(end), y + 80), fill=(45, 80, 120))
    d.text((x(fall) + 12, y + 50), "very slow smootherstep camera move", fill="white", font=font)
    d.rectangle((x(fall), y + 100, x(fall + 20), y + 140), fill=(230, 175, 85))
    d.text((x(fall + 20) + 10, y + 112), "six shadowless stage-front uplights fade on", fill=(230, 195, 120), font=font)
    d.text((35, 545), "Clock warning: Gary 00:37:50 is ambiguous at Opening 25 fps. Live DRY must pin the local frame.",
           fill=(255, 140, 110), font=font)
    os.makedirs(os.path.dirname(path), exist_ok=True); image.save(path)


def stage_front(path, plan):
    image = Image.new("RGB", (1400, 800), (24, 21, 19)); d = ImageDraw.Draw(image); font = _font()
    d.text((30, 20), "P87 STAGE FRONT — TOP VIEW / PROPOSAL", fill=(245, 225, 180), font=font)
    cx, cy, scale = 700, 380, 0.45
    d.rectangle((cx - 1050 * scale, cy - 30, cx + 1050 * scale, cy + 30), outline=(185, 140, 90), width=4)
    d.text((cx - 100, cy - 55), "paper proscenium/front", fill=(210, 170, 110), font=font)
    for row in plan["uplights"]["rows"]:
        x = cx + row["location"][1] * scale; y = cy + 90
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(255, 185, 80))
        d.line((x, y, x, cy), fill=(255, 195, 95), width=2)
    for row in plan["bulbs"]["rows"]:
        x = cx + row["location_xy_proposal"][1] * 0.25
        y = cy + 180 + row["location_xy_proposal"][0] * 0.04
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(185, 220, 255))
    d.text((30, 720), "Orange: 6 x 3200 K, 350 lm default, zero new shadow casters. Blue: seeded bulb scatter; floor Z is live-traced.",
           fill=(220, 220, 225), font=font)
    d.text((30, 750), "Creative values are args and require Gary's rendered acceptance.", fill=(255, 150, 115), font=font)
    os.makedirs(os.path.dirname(path), exist_ok=True); image.save(path)


def stage_front_svg(path, plan):
    """One review sheet: top and front views, both camera frusta, geometry and fixtures."""
    bbox = plan["camera"]["framed_bounds_cm"]
    wide = plan["camera"]["wide_pose"]; end = plan["camera"]["end_pose"]
    film_w, film_h = plan["camera"]["filmback_mm"]
    margin = plan["camera"]["wide_framing"]
    boxes = C.merge_args(json.load(open(os.path.join(HERE, "p87_opening_args.json"), encoding="utf-8")))["stage_front_occupancy_boxes_cm"]
    W, H = 1600, 1000
    # Top world mapping: X [-3200,1000] -> screen x; Y [-2100,2100] -> screen y.
    tx = lambda x: 70 + (x + 3200.0) / 4200.0 * 700
    ty = lambda y: 480 - (y + 2100.0) / 4200.0 * 400
    # Front mapping: Y horizontal, Z vertical.
    fx = lambda y: 870 + (y + 2100.0) / 4200.0 * 660
    fz = lambda z: 490 - (z + 250.0) / 2250.0 * 420
    parts = ["<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' viewBox='0 0 %d %d'>" % (W,H,W,H),
             "<rect width='100%' height='100%' fill='#17191e'/>",
             "<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#e8e2d5;font-size:15px}.small{font-size:12px}.axis{stroke:#59616d;stroke-width:1}.geom{fill:#8b6b45;stroke:#d4aa70;stroke-width:1}.paper{fill:#a58565}.frustum{fill:none;stroke:#6fc7ff;stroke-width:2}.end{stroke:#7fe0a3}.light{fill:#ffc15c;stroke:#fff0ba}.bulb{fill:#bce0ff}</style>",
             "<text x='45' y='35' font-size='22'>P87 opening re-plan — NEW 3D STAGE FRONT — PROPOSAL, NOT APPLIED</text>",
             "<text x='45' y='62'>TOP VIEW (X upstage →, Y across stage)</text>",
             "<text x='845' y='62'>FRONT VIEW (Y across, Z up)</text>"]
    # Top occupied boxes.
    for b in boxes:
        x0,x1=tx(b["min"][0]),tx(b["max"][0]); y0,y1=ty(b["max"][1]),ty(b["min"][1])
        klass = "paper" if b["name"].startswith("paper") else "geom"
        parts.append("<rect class='%s' x='%.2f' y='%.2f' width='%.2f' height='%.2f'><title>%s</title></rect>" % (klass,x0,y0,x1-x0,y1-y0,b["name"]))
    # Wide frustum to nearest bbox plane; end frustum points into P01.
    near_x=bbox["min"][0]; d=near_x-wide["location"][0]
    half_y=d*film_w/(2*wide["focal_mm"])
    parts += ["<polyline class='frustum' points='%.2f,%.2f %.2f,%.2f %.2f,%.2f'/>" %
              (tx(wide["location"][0]),ty(wide["location"][1]),tx(near_x),ty(-half_y),tx(near_x),ty(half_y)),
              "<circle cx='%.2f' cy='%.2f' r='6' fill='#6fc7ff'/>" % (tx(wide["location"][0]),ty(0)),
              "<polyline class='frustum end' points='%.2f,%.2f %.2f,%.2f %.2f,%.2f'/>" %
              (tx(end["location"][0]),ty(0),tx(900),ty(-900*film_w/(2*end["focal_mm"])),tx(900),ty(900*film_w/(2*end["focal_mm"]))),
              "<circle cx='%.2f' cy='%.2f' r='6' fill='#7fe0a3'/>" % (tx(end["location"][0]),ty(0))]
    for row in plan["uplights"]["rows"]:
        parts.append("<circle class='light' cx='%.2f' cy='%.2f' r='6'/>" % (tx(row["location"][0]),ty(row["location"][1])))
    for row in plan["bulbs"]["rows"]:
        parts.append("<circle class='bulb' cx='%.2f' cy='%.2f' r='3'/>" % (tx(row["location_xy_proposal"][0]),ty(row["location_xy_proposal"][1])))
    # Front conservative envelope and paper envelope.
    parts.append("<rect x='%.2f' y='%.2f' width='%.2f' height='%.2f' fill='#8b6b45' fill-opacity='.42' stroke='#d4aa70' stroke-width='2'/>" %
                 (fx(bbox["min"][1]),fz(bbox["max"][2]),fx(bbox["max"][1])-fx(bbox["min"][1]),fz(bbox["min"][2])-fz(bbox["max"][2])))
    # Wide image-plane coverage at the nearest depth, demonstrating margins.
    half_z=d*film_h/(2*wide["focal_mm"])
    parts.append("<rect x='%.2f' y='%.2f' width='%.2f' height='%.2f' fill='none' stroke='#6fc7ff' stroke-width='2' stroke-dasharray='8 5'/>" %
                 (fx(-half_y),fz(wide["location"][2]+half_z),fx(half_y)-fx(-half_y),fz(wide["location"][2]-half_z)-fz(wide["location"][2]+half_z)))
    for row in plan["uplights"]["rows"]:
        parts.append("<circle class='light' cx='%.2f' cy='%.2f' r='6'/>" % (fx(row["location"][1]),fz(row["location"][2])))
    parts += ["<text x='45' y='535'>WIDE: loc (−3000, 0, 819.54) cm · 14.5 mm · filmback 23.76 × 13.365 mm</text>",
              "<text x='45' y='560'>Blue frustum fits the full paper + 3D envelope; horizontal margin %.2f%%, vertical margin %.2f%%.</text>" %
              (100*margin["horizontal_margin_fraction"],100*margin["vertical_margin_fraction"]),
              "<text x='45' y='585'>Green: exact guarded move-in end / P01 start: (0,0,150) cm, 25 mm. The move begins at the single fall.</text>",
              "<text x='45' y='625'>Orange: six shadowless uplights at X −440 cm, Y −1000…1000 cm, clear of all occupancy boxes by ≥10 cm.</text>",
              "<text x='45' y='650'>Blue dots: seeded bulb proposals; every proposal is refused if within 25 cm of any new-front occupancy box.</text>",
              "<text x='45' y='690'>Combined AABB: min (−681, −1660, −120), max (−21, 1660, 1759.08) cm.</text>",
              "<text x='45' y='730'>Opening acceptance remains rendered review after stage-front placement. Requests remain HELD.</text>",
              "</svg>"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle: handle.write("\n".join(parts))


def main():
    raw = json.load(open(os.path.join(HERE, "p87_opening_args.json"), encoding="utf-8"))
    raw["first_flurry_frame"] = 950  # preview hypothesis only; live APPLY stays null until DRY resolves it
    p = C.merge_args(raw, True)
    bulbs = [{"id": "PREVIEW-%02d" % i, "wing_location": [i * 350.0, (-1) ** i * (500 + i * 25), 0.0],
              "floor_z_cm": 0.0, "side_sign": (-1) ** i} for i in range(12)]
    live = {"show_path": "Show", "level_path": "Level", "sequence_path": "LS_Opening_Curtain_Baked",
            "clock": {"status": "PREVIEW_HYPOTHESIS"},
            "camera_end_pose": {"location": [0, 0, 150], "rotation": [0, 0, 0], "focal_mm": 25, "focus_cm": 600},
            "curtain_sections": [{"role": "FALL", "start": 1900, "end": 2150},
                                 {"role": "FALL", "start": 2200, "end": 2400}], "bulbs": bulbs}
    plan = C.build_plan(p, live)
    a = os.path.join(OUT, "p87_timeline.png"); b = os.path.join(OUT, "p87_stage_front_camera_frusta.svg")
    timeline(a, plan); stage_front_svg(b, plan)
    print("P87_PREVIEW_OK|timeline=%s|stage_front_svg=%s|frame=950_PREVIEW_ONLY" % (a, b))


if __name__ == "__main__":
    main()
