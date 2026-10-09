"""Regenerate P34's two analytical SVG previews without importing Unreal."""
import importlib.util
import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "i2_sleight_move_in_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)

SPEC = importlib.util.spec_from_file_location("i2_sleight_move_in", os.path.join(HERE, "i2_sleight_move_in.py"))
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


def write_pngs(plan):
    """Pillow convenience copies; SVG remains the dependency-free authority."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return []
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        small = ImageFont.truetype("arial.ttf", 12)
        title = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        font = small = title = ImageFont.load_default()
    paths = []
    image = Image.new("RGB", (900, 560), "#101318")
    draw = ImageDraw.Draw(image)
    draw.text((40, 24), "I2 sleight move-in - analytical plan view", fill="#f1eadf", font=title)
    draw.text((40, 58), "Not a scene render. Gary judges the later rendered slot.", fill="#aeb8c5", font=small)
    rows_by_side = {}
    for side, drape in (("hangar", plan["hangar_drape"]), ("mouth", plan["mouth_drape"])):
        frames = (list(range(plan["move_start"], TOOL.CUT_FRAME + 1, 5)) if side == "hangar" else
                  list(range(TOOL.CUT_FRAME, int(plan["mouth"]["ease_end_frame"]) + 1, 5)))
        rows_by_side[side] = [TOOL.local_from_frame(drape, TOOL.pose_at(plan, side, frame)["loc"])
                              for frame in (frames or [TOOL.CUT_FRAME])]
    def project(side, row):
        return 820 + row[0] * 0.28, (220 if side == "hangar" else 390) - row[1] * 0.12
    draw.line((820, 125, 820, 465), fill="#8c2635", width=12)
    draw.text((750, 95), "drape plane", fill="#e8a5af", font=small)
    for side, color in (("hangar", "#ef9d45"), ("mouth", "#5ab7d9")):
        pixels = [project(side, row) for row in rows_by_side[side]]
        if len(pixels) > 1:
            draw.line(pixels, fill=color, width=4)
        for label, point in (("start", pixels[0]), ("end", pixels[-1])):
            x, y = point
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=color)
            draw.text((x + 9, y - 16), "%s %s" % (side, label), fill="#f1eadf", font=small)
        draw.text((75, 170 if side == "hangar" else 340), "%s path in its drape-local plan" % side,
                  fill=color, font=font)
    draw.text((40, 530), "move_start=%d  cut=%d  close=%.1f cm  mouth=%s  ease=%.2f s  HFOV=%.2f deg" %
              (plan["move_start"], TOOL.CUT_FRAME, plan["close_distance_cm"], plan["mouth_after"],
               plan["ease_out_s"], plan["hfov_deg"]), fill="#aeb8c5", font=small)
    path = os.path.join(HERE, "preview_plan.png")
    image.save(path)
    paths.append(path)
    card_w, card_h, gap = 280, 210, 15
    image = Image.new("RGB", (3 * card_w + 4 * gap, 4 * card_h + 5 * gap), "#101318")
    draw = ImageDraw.Draw(image)
    for index, frame in enumerate(TOOL.PREVIEW_FRAMES):
        col, block = index % 3, index // 3
        for side_index, side in enumerate(("hangar", "mouth")):
            x = gap + col * (card_w + gap)
            y = gap + (block * 2 + side_index) * (card_h + gap)
            cov = plan["coverage"][side][str(frame)]
            draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=8,
                                   fill="#153d32" if cov["fills_frame"] else "#472626", outline="#77818f")
            draw.text((x + 12, y + 10), "f%d - %s" % (frame, side), fill="#f1eadf", font=font)
            draw.text((x + 12, y + 40), "distance %.1f cm" % cov["distance_to_plane_cm"], fill="#d9e2ec", font=small)
            margins = cov["margins_cm"]
            draw.text((x + 12, y + 62), "L/R %.1f  T/B %.1f cm" %
                      (min(margins["left"], margins["right"]), min(margins["top"], margins["bottom"])),
                      fill="#d9e2ec", font=small)
            draw.text((x + 12, y + 88), "DRAPE FILLS FRAME" if cov["fills_frame"] else "EDGE WOULD SHOW",
                      fill="#7ff0bd" if cov["fills_frame"] else "#ff9b91", font=font)
            local = cov["camera_local_cm"]
            draw.text((x + 12, y + 119), "local [%.1f, %.1f, %.1f]" % tuple(local), fill="#aeb8c5", font=small)
            note = "live" if ((side == "hangar" and frame < TOOL.CUT_FRAME) or
                              (side == "mouth" and frame >= TOOL.CUT_FRAME)) else "comparison / not live"
            draw.text((x + 12, y + 145), note, fill="#aeb8c5", font=small)
    path = os.path.join(HERE, "preview_coverage.png")
    image.save(path)
    paths.append(path)
    return paths


def main():
    params = TOOL.merged_params(ARGS.get("params") or {})
    evidence = TOOL.load_evidence(params)
    order = TOOL.json_read(params["evidence"]["order_record"])
    tan_h = float(order["plan"]["coverage"]["twin"]["tan_h"])
    old_focal = float(order["plan"]["lens"]["focal_mm"])
    mouth_sensor_width = 2.0 * old_focal * tan_h
    mouth_sensor_height = mouth_sensor_width / float(params["output_aspect"])
    actor = evidence["hangar_actor"]
    live = {
        "snapshot": evidence["hangar_snapshot"],
        "hangar_camera": {
            "binding_guid": TOOL.HANGAR_GUID,
            "location_cm": actor["location_cm"],
            "rotation_deg": actor["rotation_deg"],
            "sensor_width_mm": actor["sensor_width_mm"],
            "sensor_height_mm": actor["sensor_height_mm"],
        },
        "mouth_camera": {
            "binding_guid": TOOL.MOUTH_GUID,
            "location_cm": [-2167.135009765625, 160000.0, 444.86566162109375],
            "rotation_deg": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
            "sensor_width_mm": mouth_sensor_width,
            "sensor_height_mm": mouth_sensor_height,
        },
    }
    plan = TOOL.build_plan(live, evidence, params)
    paths = TOOL.write_previews(plan, HERE) + write_pngs(plan)
    print("I2_MOVE_IN_PREVIEWS_OK|%s" % ",".join(paths))


if __name__ == "__main__":
    main()
