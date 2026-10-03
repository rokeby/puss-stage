"""Render the offline Scene 3 beach plan JSON as a top-down PNG."""
import json
import os

from PIL import Image, ImageDraw, ImageFont


HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "s3_beach_plan.json")
OUTPUT = os.path.join(HERE, "s3_beach_plan_topdown.png")
WIDTH, HEIGHT = 1600, 760
MARGIN = 70


def main():
    with open(PLAN, encoding="utf-8") as handle:
        plan = json.load(handle)
    x0, x1 = plan["coordinate_system"]["box_x_cm"]
    y0, y1 = plan["coordinate_system"]["box_y_cm"]
    sx = (WIDTH - 2 * MARGIN) / (x1 - x0)
    sy = (HEIGHT - 2 * MARGIN) / (y1 - y0)

    def xy(x, y):
        return (MARGIN + (x - x0) * sx, HEIGHT - MARGIN - (y - y0) * sy)

    def rect(bounds):
        left, top = xy(bounds["min"][0], bounds["max"][1])
        right, bottom = xy(bounds["max"][0], bounds["min"][1])
        return (left, top, right, bottom)

    image = Image.new("RGB", (WIDTH, HEIGHT), "#f6f0df")
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default(size=16)
    small = ImageFont.load_default(size=12)
    draw.rectangle((MARGIN, MARGIN, WIDTH - MARGIN, HEIGHT - MARGIN),
                   fill="#ede3cc", outline="#332d25", width=3)
    for band in plan["guards"]["wave_row_x_hazard_bands_cm"]:
        left, top = xy(band[0], y1)
        right, bottom = xy(band[1], y0)
        draw.rectangle((left, top, right, bottom), fill="#5b91c955", outline="#356b9d", width=2)
        draw.text((left + 4, MARGIN + 8), "wave +/-100", fill="#234b70", font=small)
    gap = plan["guards"]["camera_side_gap"]
    left, top = xy(gap["x_cm"][0], gap["y_cm"][1])
    right, bottom = xy(gap["x_cm"][1], gap["y_cm"][0])
    draw.rectangle((left, top, right, bottom), fill="#e58a6b55", outline="#b94f32", width=2)
    draw.text((left + 8, top + 6), "KEEP OPEN: camera-side gap", fill="#8b321f", font=font)
    centre = xy(3500.0, 0.0)
    for radius, colour in ((260.0, "#75624d"), (320.0, "#4f4032")):
        rx, ry = radius * sx, radius * sy
        draw.ellipse((centre[0] - rx, centre[1] - ry, centre[0] + rx, centre[1] + ry),
                     outline=colour, width=2)
    draw.text((centre[0] - 40, centre[1] - 14), "clam/ring", fill="#3d3025", font=font)
    clearance = plan["guards"]["camera_clearance_cm"]
    for camera in plan["shot_cameras_dock_cm"]:
        px, py = xy(camera["location"][0], camera["location"][1])
        rx, ry = clearance * sx, clearance * sy
        draw.ellipse((px - rx, py - ry, px + rx, py + ry), fill="#7b57a018", outline="#7b57a0", width=1)
        draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill="#5e3f80")
        draw.text((px + 6, py - 14), camera["label"].replace("S3 Shot ", ""), fill="#5e3f80", font=small)
    colours = {"mound": "#c6a45f", "rock": "#6f746f", "shingle": "#9a8e78",
               "plant_fallback": "#4f8060"}
    for row in plan["placements"]:
        box = rect(row["estimated_aabb"])
        colour = colours[row["kind"]]
        draw.rectangle(box, fill=colour + "bb", outline="#2e2b27", width=2)
        draw.text((box[0] + 3, box[1] + 3), row["label"].replace("S3 Beach ", ""),
                  fill="#191714", font=small)
    draw.text((MARGIN, 20), "Scene 3 beach draft - landed dock top view (offline Pass 1)",
              fill="#211d18", font=font)
    draw.text((WIDTH - 470, 20), "PROVISIONAL: exact asset bounds + live cameras gated by probe/dry run",
              fill="#8b321f", font=small)
    draw.text((MARGIN, HEIGHT - 38), "camera -> +X into scene     box: x 5-65 m, y +/-10 m     marble liners: side walls only",
              fill="#332d25", font=font)
    image.save(OUTPUT)
    print("S3_BEACH_PLAN_DIAGRAM_OK|%s" % OUTPUT)


if __name__ == "__main__":
    main()
