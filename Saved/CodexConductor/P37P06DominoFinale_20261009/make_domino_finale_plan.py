"""Offline DRY planner and timeline renderer for P37/P06 domino finale."""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import domino_finale_core as core


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def font(size, bold=False):
    candidates = ([Path("C:/Windows/Fonts/arialbd.ttf")] if bold else []) + [
        Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def render_timeline(plan, out):
    width, height = 1800, 760
    image = Image.new("RGB", (width, height), (13, 15, 20))
    draw = ImageDraw.Draw(image)
    left, right = 155, width - 55
    top, bottom = 95, height - 85
    duration = 126.001125

    def x(sec):
        return left + (right - left) * float(sec) / duration

    draw.text((55, 28), "P06 domino finale — OFFLINE DRY timeline", fill=(238, 241, 245), font=font(28, True))
    draw.text((55, 62), "No Unreal / no render acceptance • times are P06-relative", fill=(155, 164, 178), font=font(17))
    for t in range(0, 127, 10):
        xx = x(t)
        draw.line((xx, top, xx, bottom), fill=(42, 47, 58), width=1)
        draw.text((xx - 12, bottom + 15), "%ds" % t, fill=(170, 178, 190), font=font(14))

    lanes = [
        (130, "Chain A", (227, 142, 73)),
        (220, "Chain B", (238, 79, 93)),
        (310, "Sunset", (219, 181, 77)),
        (400, "Car / bees", (105, 188, 241)),
        (490, "P06 FX", (111, 205, 151)),
        (580, "Dust / slam", (185, 123, 231)),
    ]
    for y, name, color in lanes:
        draw.text((28, y - 13), name, fill=color, font=font(18, True))
        draw.line((left, y, right, y), fill=(75, 81, 95), width=2)

    a = plan["chain_a"]
    draw.line((x(a["creak_s"]), 130, x(a["rest_s"]), 130), fill=(227, 142, 73), width=10)
    for value, label in ((a["creak_s"], "creak"), (a["final_impact_s"], "impact"), (a["rest_s"], "rest")):
        draw.ellipse((x(value) - 5, 125, x(value) + 5, 135), fill=(245, 206, 155))
    draw.text((x(a["creak_s"]) - 22, 146), "%.2f creak" % a["creak_s"], fill=(220, 203, 180), font=font(12))
    draw.text((x(a["final_impact_s"]) - 62, 102), "%.2f impact" % a["final_impact_s"],
              fill=(220, 203, 180), font=font(12))
    draw.text((x(a["rest_s"]) + 9, 146), "%.2f rest" % a["rest_s"], fill=(220, 203, 180), font=font(12))

    b = plan.get("chain_b")
    if b:
        draw.line((x(b["timing"]["creak_s"]), 220, x(b["timing"]["rest_s"]), 220), fill=(238, 79, 93), width=10)
        for row in b["rows"]:
            draw.ellipse((x(row["timing"]["impact_s"]) - 4, 216, x(row["timing"]["impact_s"]) + 4, 224),
                         fill=(255, 190, 196))
    else:
        draw.line((x(122.0), 198, x(122.0), 242), fill=(238, 79, 93), width=3)
        draw.text((x(122.0) - 155, 245), "122.0 candidate — APPLY REFUSED", fill=(255, 130, 141), font=font(15, True))

    draw.line((x(21.85), 310, x(90), 310), fill=(219, 181, 77), width=9)
    for value, label in ((37, "half"), (52, "dark"), (90, "black")):
        draw.ellipse((x(value) - 5, 305, x(value) + 5, 315), fill=(246, 222, 141))
        draw.text((x(value) - 18, 326), label, fill=(221, 209, 164), font=font(13))

    draw.ellipse((x(68.55) - 7, 393, x(68.55) + 7, 407), fill=(105, 188, 241))
    draw.text((x(68.55) - 15, 417), "car", fill=(154, 210, 246), font=font(13))
    for value in (80, 100, 118):
        draw.ellipse((x(value) - 6, 394, x(value) + 6, 406), fill=(173, 224, 255))
        draw.text((x(value) - 12, 417), "bee", fill=(154, 210, 246), font=font(13))

    for start, end, name in ((68.55, 102.7, "motes"), (86.7, 102.7, "burn"), (94.6, 126, "fire")):
        yy = 480 + (0 if name == "motes" else 14 if name == "burn" else 28)
        draw.line((x(start), yy, x(end), yy), fill=(111, 205, 151), width=6)
        draw.text((x(start), yy - 18), name, fill=(151, 222, 180), font=font(12))

    bursts = plan.get("dust_bursts") or []
    for item in bursts:
        draw.ellipse((x(item["impact_s"]) - 5, 575, x(item["impact_s"]) + 5, 585), fill=(207, 169, 239))
    if plan.get("slam_sound"):
        draw.line((x(122.0), 558, x(122.0), 604), fill=(235, 194, 255), width=3)
        draw.text((x(122.0) - 85, 612), "Collapse01 candidate", fill=(207, 169, 239), font=font(13))

    banner = ("APPLY READY" if plan["apply_ready"] else
              "APPLY REFUSED — no >=2-row physical suffix reaches the P06 end")
    color = (80, 195, 123) if plan["apply_ready"] else (238, 79, 93)
    draw.rounded_rectangle((55, 690, width - 55, 735), radius=10, fill=(29, 33, 42), outline=color, width=2)
    draw.text((75, 701), banner, fill=color, font=font(18, True))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements", required=True)
    parser.add_argument("--chain-a-plan", required=True)
    parser.add_argument("--chain-a-active", required=True)
    parser.add_argument("--asset-inventory", required=True)
    parser.add_argument("--args")
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeline", required=True)
    ns = parser.parse_args(argv)
    raw_args = read(ns.args) if ns.args else {}
    topple = load_module("p37_topple_core", PROJECT / "Saved/CodexFlatV3/topple/topple_core.py")
    plan = core.build_plan(read(ns.measurements), read(ns.chain_a_plan), read(ns.chain_a_active),
                           read(ns.asset_inventory), raw_args, topple)
    plan["made_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    plan["sources"] = {"measurements": str(Path(ns.measurements).resolve()),
                       "chain_a_plan": str(Path(ns.chain_a_plan).resolve()),
                       "chain_a_active": str(Path(ns.chain_a_active).resolve()),
                       "asset_inventory": str(Path(ns.asset_inventory).resolve())}
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    render_timeline(plan, ns.timeline)
    print("P37_P06_DOMINO_DRY|apply_ready=%d|chain_b=%d/%d|blockers=%d|plan=%s|timeline=%s" %
          (int(plan["apply_ready"]), plan["selected_rows"], plan["requested_rows"], len(plan["blockers"]),
           out, Path(ns.timeline)))


if __name__ == "__main__":
    main()
