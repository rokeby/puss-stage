"""PG5 offline positive/negative harness for composite framing and stretch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_boy_puss_composite as build  # noqa: E402
import cat_rig  # noqa: E402
import clip_render  # noqa: E402


def check(results, kind, label, condition, detail):
    results.append({"kind": kind, "label": label, "passed": bool(condition), "detail": detail})


def product_control():
    boy = Image.new("L", (32, 32), 255)
    ImageDraw.Draw(boy).rectangle((5, 5, 26, 26), fill=0)
    puss = Image.new("L", (32, 32), 255)
    draw = ImageDraw.Draw(puss)
    draw.rectangle((10, 10, 28, 28), fill=0)
    draw.rectangle((14, 14, 20, 20), fill=255)  # a cut in Puss over the boy card
    product = clip_render.product_transmissions([boy, puss])

    painter = boy.copy()
    draw = ImageDraw.Draw(painter)
    draw.rectangle((10, 10, 28, 28), fill=0)
    draw.rectangle((14, 14, 20, 20), fill=255)
    return product.getpixel((17, 17)), painter.getpixel((17, 17))


def stretch_metrics(px=900):
    pose = cat_rig.make_pose("stretch")
    rendered = cat_rig.render_pose(pose, view=build.placement_view(build.PUSS_PLACEMENT, px), ss=2)
    blocked = np.asarray(rendered) < 128
    labels, count = ndimage.label(blocked, structure=np.ones((3, 3), dtype=np.uint8))
    sizes = np.bincount(labels.ravel())[1:]
    material_components = int(np.sum(sizes >= 8))

    parts, _rods, _whiskers = cat_rig.pose_parts(pose)
    masks = {}
    for group, names in (("near", {"front_leg", "front_paw"}),
                         ("far", {"far_front_leg", "far_front_paw"})):
        image = Image.new("1", (px, px), 0)
        draw = ImageDraw.Draw(image)
        for name, outline, _cuts, _z in parts:
            if name in names:
                points = [tuple(build.map_point(point, build.PUSS_PLACEMENT) * px) for point in outline]
                draw.polygon(points, fill=1)
        masks[group] = np.asarray(image, dtype=bool)

    gaps = []
    for y in range(px):
        near_x = np.flatnonzero(masks["near"][y])
        far_x = np.flatnonzero(masks["far"][y])
        if not len(near_x) or not len(far_x):
            continue
        if near_x.max() < far_x.min():
            gaps.append(int(far_x.min() - near_x.max() - 1))
        elif far_x.max() < near_x.min():
            gaps.append(int(near_x.min() - far_x.max() - 1))
    return {"material_components": material_components,
            "largest_component_px": int(sizes.max()) if len(sizes) else 0,
            "leg_light_gap_px": max(gaps) if gaps else 0}


def run(manifest_path, report_path=None):
    results = []
    product_pixel, painter_pixel = product_control()
    check(results, "positive", "composite_is_product", product_pixel == 0,
          {"overlap_cut_pixel": product_pixel})
    check(results, "negative", "painter_overwrite_punches_hole", painter_pixel == 255,
          {"overlap_cut_pixel": painter_pixel})

    framing = build.framing_report()
    boy = framing["boy"]
    puss = framing["puss"]
    check(results, "positive", "boy_head_inside_band_and_knees_cut",
          boy["head_top_cell_y"] > build.VISIBLE_BAND["top"] and
          boy["knee_cell_y"] > build.VISIBLE_BAND["bottom"],
          {"band": build.VISIBLE_BAND, "head_y": boy["head_top_cell_y"],
           "knee_y": boy["knee_cell_y"]})
    limit_y = build.VISIBLE_BAND["bottom"] - build.PUSS_LIMIT_RATIO * boy["visible_height_cell"]
    check(results, "positive", "puss_head_below_limit_line",
          puss["head_top_cell_y"] >= limit_y - 1e-9,
          {"puss_head_y": puss["head_top_cell_y"], "limit_y": limit_y, "ratio": puss["visible_height_ratio_to_boy"]})
    check(results, "positive", "puss_is_25pct_bigger_than_v1",
          abs(puss["visible_height_ratio_to_boy"] - 0.5625) < 0.01, puss["visible_height_ratio_to_boy"])

    too_large = dict(build.PUSS_PLACEMENT, scale=build.PUSS_PLACEMENT["scale"] * 1.45)
    pose = cat_rig.make_pose("sit_look_up")
    parts, _rods, _whiskers = cat_rig.pose_parts(pose)
    head = np.concatenate([np.asarray(outline) for name, outline, _cuts, _z in parts if name == "head"])
    bad_top = float(build.map_point((0.0, head[:, 1].min()), too_large)[1])
    check(results, "negative", "mis_scaled_puss_fails_halfway_limit",
          bad_top < limit_y,
          {"bad_head_y": bad_top, "limit_y": limit_y, "scale_multiplier": 1.45})

    stretch = stretch_metrics()
    check(results, "positive", "stretch_is_one_connected_silhouette",
          stretch["material_components"] == 1, stretch)
    check(results, "positive", "stretch_legs_have_light_between_them",
          stretch["leg_light_gap_px"] >= 2, stretch)

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    first_second_cells = {cell for seconds, cell in manifest["schedule"] if seconds < 1.0}
    check(results, "positive", "two_puppet_hold_is_one_cell",
          len(first_second_cells) == 1, {"cells": sorted(first_second_cells)})
    check(results, "positive", "sdf_8192_and_bluruv_zero",
          manifest["atlas"].get("encoding", {}).get("type") == "signed_distance" and
          manifest["atlas"]["px"] == [8192, 8192] and
          manifest["light_function_params"].get("BlurUV") == 0.0,
          {"atlas_px": manifest["atlas"]["px"],
           "encoding": manifest["atlas"].get("encoding", {}).get("type"),
           "BlurUV": manifest["light_function_params"].get("BlurUV")})

    positive = [item for item in results if item["kind"] == "positive"]
    negative = [item for item in results if item["kind"] == "negative"]
    report = {
        "schema_version": 1,
        "positive": {"passed": sum(item["passed"] for item in positive), "total": len(positive)},
        "negative": {"passed": sum(item["passed"] for item in negative), "total": len(negative)},
        "total": {"passed": sum(item["passed"] for item in results), "total": len(results)},
        "results": results,
        "claims": [
            {"tier": "measured", "claim": "All positive and negative PG5 controls below ran offline.",
             "evidence": "Tools/ShadowGobo/Puppets/test_boy_puss_composite_offline.py:24-135"},
            {"tier": "inferred", "claim": "Silhouette connectivity and leg-gap metrics support readability; Gary's eye remains the look authority.",
             "evidence": "Tools/ShadowGobo/Puppets/clip_boy_puss_rub/stretch_pose_preview.png"},
        ],
    }
    if report_path:
        Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("BOY_PUSS_HARNESS|positive=%d/%d|negative=%d/%d|total=%d/%d" % (
        report["positive"]["passed"], report["positive"]["total"],
        report["negative"]["passed"], report["negative"]["total"],
        report["total"]["passed"], report["total"]["total"]))
    for item in results:
        if not item["passed"]:
            print("FAIL|%s|%s|%s" % (item["kind"], item["label"], item["detail"]))
    return 0 if report["total"]["passed"] == report["total"]["total"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    return run(args.manifest, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
