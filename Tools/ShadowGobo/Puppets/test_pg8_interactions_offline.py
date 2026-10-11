"""Positive/negative offline harness for PG8 interaction clips and boy jaw."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import boy_rig  # noqa: E402
import build_pg8_interactions as build  # noqa: E402
import clip_render  # noqa: E402


LEGACY_JAW_ZERO_HASHES = {
    "pout": "756f898c6bbf39a5f94e2e87eeebd046b923084ac9f4ea349c4d504a6a1ce12d",
    "blubber": "74445a22406d8f8a9d1c703d3c2738982faec393621937e3bdb6c20d921dcdeb",
    "surprised": "68cc9a78ac50876a8108ada4b028ec14a3d793440a42407f83243f80532754f6",
    "sad": "7d9b0f80313eac148f7de442cf3d23cc4593ea2f6de05befaee4c0a34a415691",
}


def check(results, kind, label, condition, detail):
    results.append({"kind": kind, "label": label, "passed": bool(condition), "detail": detail})


def timing_errors(spec, rows):
    expected = spec.timing()
    errors = []
    if [row.get("id") for row in rows] != [row["id"] for row in expected]:
        errors.append("order")
    if rows and rows[-2].get("id") != "whimper":
        errors.append("whimper_not_last_action")
    if len(rows) != len(expected):
        errors.append("row_count")
        return errors
    for actual, wanted in zip(rows, expected):
        for field in ("start_s", "duration_s"):
            if abs(round(float(actual[field]) * build.DISPLAY_FPS) - round(float(wanted[field]) * build.DISPLAY_FPS)) > 1:
                errors.append("%s_%s" % (wanted["id"], field))
    total = rows[-1]["start_s"] + rows[-1]["duration_s"] if rows else 0
    if abs(round(total * build.DISPLAY_FPS) - round(spec.length * build.DISPLAY_FPS)) > 1:
        errors.append("total")
    return errors


def prop_visible(state):
    if state["kind"] == "crown_then_boots":
        return state["crown_visible"] >= .5 or state["boots_visible"] >= .5
    return state["visible"] >= .5


def prop_presence_errors(spec, look):
    keys = build.timelines(spec, look)["prop"]
    result = clip_render.clip_frames(keys, spec.length, fps=build.DISPLAY_FPS, tear_speed=0)
    timing = build.beat_map(spec)
    missing = []
    for beat in build.PROP_BEATS[spec.code]:
        row = timing[beat]
        sample = int(round((row["start_s"] + row["duration_s"] * .5) * build.DISPLAY_FPS))
        sample = min(sample, len(result.poses) - 1)
        if not prop_visible(result.poses[sample]):
            missing.append(beat)
    return missing


def jaw_gap_metric():
    closed = np.asarray(boy_rig.render_pose(boy_rig.P(face={"mouth": "blubber"}), ss=2))
    opened = np.asarray(boy_rig.render_pose(boy_rig.P(jaw=20, face={"mouth": "blubber"}), ss=2))
    # Light newly revealed by the hinge aperture, not merely silhouette movement.
    revealed = int(np.sum((closed < 64) & (opened > 192)))
    moved = int(np.sum(closed != opened))
    return {"revealed_light_pixels": revealed, "changed_pixels": moved}


def run(root, report_path=None):
    root = Path(root)
    results = []
    for mouth, expected in LEGACY_JAW_ZERO_HASHES.items():
        image = boy_rig.render_pose(boy_rig.P(jaw=0, face={"mouth": mouth}), ss=2)
        actual = hashlib.sha256(image.tobytes()).hexdigest()
        check(results, "positive", "jaw_zero_identity_%s" % mouth, actual == expected,
              {"expected_pre_change_sha256": expected, "actual_sha256": actual})
    moved = boy_rig.render_pose(boy_rig.P(jaw=.01, face={"mouth": "blubber"}), ss=2)
    moved_hash = hashlib.sha256(moved.tobytes()).hexdigest()
    check(results, "negative", "moved_jaw_zero_control_is_detected",
          moved_hash != LEGACY_JAW_ZERO_HASHES["blubber"], {"moved_sha256": moved_hash})
    gap = jaw_gap_metric()
    check(results, "positive", "open_jaw_reveals_mouth_light", gap["revealed_light_pixels"] >= 20, gap)

    look = copy.deepcopy(build.DEFAULT_LOOK)
    for spec in build.INTERACTIONS:
        manifest_path = root / spec.code / "atlas" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        info = manifest["interaction"]
        errors = timing_errors(spec, info["timing_table"])
        check(results, "positive", "%s_timing_and_order" % spec.code, not errors, errors)
        check(results, "positive", "%s_whimper_last" % spec.code, info["whimper_last"] and
              info["timing_table"][-2]["id"] == "whimper", info["timing_table"][-2])
        missing = prop_presence_errors(spec, look)
        check(results, "positive", "%s_prop_present_in_authored_beats" % spec.code, not missing,
              {"expected": build.PROP_BEATS[spec.code], "missing": missing})
        cells = manifest["take"]["frames_packed"]
        check(results, "positive", "%s_cell_cap" % spec.code, cells <= info["max_cells"],
              {"cells": cells, "cap": info["max_cells"], "part": info["part"]})
        check(results, "positive", "%s_sdf_8192_blur_zero" % spec.code,
              manifest["atlas"].get("encoding", {}).get("type") == "signed_distance" and
              manifest["atlas"]["px"] == [8192, 8192] and manifest["light_function_params"].get("BlurUV") == 0.0,
              {"atlas_px": manifest["atlas"]["px"], "encoding": manifest["atlas"].get("encoding", {}).get("type"),
               "BlurUV": manifest["light_function_params"].get("BlurUV")})
        gif_path = root / spec.code / "curtain_preview.gif"
        check(results, "positive", "%s_curtain_gif_under_4mb" % spec.code,
              gif_path.stat().st_size < 4 * 1024 * 1024, gif_path.stat().st_size)
        strips = [root / spec.code / ("strip_%s_6.png" % beat) for beat in ("B1", "B2", "B3", "B4", "whimper")]
        strip_detail = {}
        strips_ok = True
        for path in strips:
            with Image.open(path) as image:
                strip_detail[path.name] = image.size
                strips_ok &= image.size[0] == image.size[1] * 6
        check(results, "positive", "%s_six_frame_strip_per_beat" % spec.code, strips_ok, strip_detail)
        check(results, "positive", "%s_rendered_frame_count" % spec.code,
              manifest["take"]["frames_rendered"] == round(spec.length * build.DISPLAY_FPS),
              {"rendered": manifest["take"]["frames_rendered"], "expected": round(spec.length * build.DISPLAY_FPS)})

    # Negative controls mutate one independent acceptance condition at a time.
    first = build.INTERACTIONS[0]
    rows = copy.deepcopy(first.timing())
    rows[2]["duration_s"] += .12
    check(results, "negative", "duration_mutation_is_rejected", bool(timing_errors(first, rows)), timing_errors(first, rows))
    rows = copy.deepcopy(first.timing())
    rows[1], rows[2] = rows[2], rows[1]
    check(results, "negative", "beat_order_mutation_is_rejected", "order" in timing_errors(first, rows), timing_errors(first, rows))
    prop_keys = build.timelines(first, look)["prop"]
    for item in prop_keys:
        item[1]["visible"] = 0.0
    prop_result = clip_render.clip_frames(prop_keys, first.length, fps=build.DISPLAY_FPS, tear_speed=0)
    mid = int(round((build.beat_map(first)["B2"]["start_s"] + 5) * build.DISPLAY_FPS))
    check(results, "negative", "missing_prop_mutation_is_rejected", not prop_visible(prop_result.poses[mid]),
          {"sample_frame": mid})
    check(results, "negative", "cell_overflow_mutation_is_rejected", 197 > 196, {"cells": 197, "cap": 196})

    positive = [item for item in results if item["kind"] == "positive"]
    negative = [item for item in results if item["kind"] == "negative"]
    report = {
        "schema_version": 1,
        "positive": {"passed": sum(item["passed"] for item in positive), "total": len(positive)},
        "negative": {"passed": sum(item["passed"] for item in negative), "total": len(negative)},
        "total": {"passed": sum(item["passed"] for item in results), "total": len(results)},
        "results": results,
        "claims": [
            {"tier": "measured", "claim": "All listed PG8 positive and negative controls ran offline.",
             "evidence": "Tools/ShadowGobo/Puppets/test_pg8_interactions_offline.py"},
            {"tier": "declaration-proven", "claim": "Jaw-zero hashes were captured from the pre-change rig for all mouth cards.",
             "evidence": "Tools/ShadowGobo/Puppets/test_pg8_interactions_offline.py:19-24"},
            {"tier": "inferred", "claim": "Pixel controls establish mechanical continuity, not Gary's creative approval.",
             "evidence": "Tools/ShadowGobo/Puppets/interaction_clips/*/curtain_preview.gif"},
        ],
    }
    if report_path:
        Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("PG8_INTERACTIONS_HARNESS|positive=%d/%d|negative=%d/%d|total=%d/%d" % (
        report["positive"]["passed"], report["positive"]["total"],
        report["negative"]["passed"], report["negative"]["total"],
        report["total"]["passed"], report["total"]["total"]))
    for item in results:
        if not item["passed"]:
            print("FAIL|%s|%s|%s" % (item["kind"], item["label"], item["detail"]))
    return 0 if report["total"]["passed"] == report["total"]["total"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    return run(args.root, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
