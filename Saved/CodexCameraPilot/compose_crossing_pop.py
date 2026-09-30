"""Offline: turn a crossing-pop PIE run into a picture Gary can judge on a phone. (30 Sep)

Usage: python compose_crossing_pop.py <run json name> <first ScreenShot number of the run>
e.g.   python compose_crossing_pop.py scene4_crossing_pop 22

The run (scene1_tail_view_pie.py with crossing_shots_s) screenshots every tick near a Passage -> Scene
crossing, in order. The pop frame is found from the PIXELS: the consecutive pair with the largest mean
difference, not a guessed tick. Writes <name>_pair.png (before | after, labelled with the logged camera
move) and <name>_flip.gif (the two frames alternating, 0.7 s each), plus <name>_pop.json with the numbers.
Needs Pillow. Reads Saved/Screenshots/WindowsEditor; writes Saved/CodexCameraPilot/Captures/CrossingPop.
"""
import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "..", "Screenshots", "WindowsEditor")
OUT = os.path.join(HERE, "Captures", "CrossingPop")


def main():
    name, first = sys.argv[1], int(sys.argv[2])
    with open(os.path.join(HERE, name + ".json"), encoding="utf-8") as handle:
        run = json.load(handle)
    shots = run["crossing_shots_in_order"]
    files = [os.path.join(SHOTS, "ScreenShot%05d.png" % (first + i)) for i in range(len(shots))]
    missing = [f for f in files if not os.path.exists(f)]
    if missing:
        raise SystemExit("missing screenshots: %s" % missing)
    images = [Image.open(f).convert("RGB") for f in files]
    diffs = [sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3.0 for a, b in zip(images, images[1:])]
    pop = max(range(len(diffs)), key=lambda i: diffs[i])
    rows = run["rows"]

    def row_for(shot):
        return rows[shot["tick"]]

    # The camera move across the whole crossing window, from the log (location and rotation).
    window = [row_for(s) for s in shots]
    a, b = window[0], window[-1]
    moved = [round(q - p, 2) for p, q in zip(a["camera_xyz_precise"], b["camera_xyz_precise"])]
    turned = [round(q - p, 3) for p, q in zip(a["camera_pyr"], b["camera_pyr"])]
    before, after = images[pop], images[pop + 1]
    width, height = before.size
    pair = Image.new("RGB", (width * 2 + 20, height + 90), (20, 20, 20))
    pair.paste(before, (0, 90))
    pair.paste(after, (width + 20, 90))
    draw = ImageDraw.Draw(pair)
    draw.text((20, 15), "%s crossing: BEFORE (%+.3f s)  |  AFTER (%+.3f s)" % (
        run.get("scene", "?"), shots[pop]["relative_s"], shots[pop + 1]["relative_s"]), fill=(255, 255, 255))
    draw.text((20, 45), "camera moved (x, y, z cm) %s, turned (pitch, yaw, roll deg) %s across +/-%.2f s" % (
        moved, turned, abs(shots[0]["relative_s"])), fill=(255, 220, 120))
    for y in (90 + height // 3, 90 + 2 * height // 3):            # guides to read a vertical shift against
        draw.line([(0, y), (pair.width, y)], fill=(80, 200, 255), width=1)
    os.makedirs(OUT, exist_ok=True)
    pair_path = os.path.join(OUT, name + "_pair.png")
    pair.save(pair_path)
    small = [im.resize((width // 2, height // 2)) for im in (before, after)]
    gif_path = os.path.join(OUT, name + "_flip.gif")
    small[0].save(gif_path, save_all=True, append_images=[small[1]], duration=700, loop=0)
    with open(os.path.join(OUT, name + "_pop.json"), "w", encoding="utf-8") as handle:
        json.dump({"pair_diffs": [round(d, 2) for d in diffs], "pop_index": pop,
                   "before": shots[pop], "after": shots[pop + 1],
                   "window_moved_cm": moved, "window_turned_deg": turned}, handle, indent=1)
    print("pop between shots %d and %d (mean diff %.2f; others max %.2f) -> %s, %s" % (
        pop, pop + 1, diffs[pop], max([d for i, d in enumerate(diffs) if i != pop] or [0]), pair_path, gif_path))


main()
