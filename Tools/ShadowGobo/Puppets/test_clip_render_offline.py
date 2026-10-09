"""Offline positive/negative controls for display-rate puppet clip rendering."""
from __future__ import annotations

import hashlib
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import boy_rig as boy  # noqa: E402
import cat_rig as cat  # noqa: E402
import clip_render as clip  # noqa: E402


RESULTS = []


def check(kind, label, condition, detail=""):
    RESULTS.append((kind, label, bool(condition), detail))


def hash_pose(pose):
    view = dict(x0=-185.0, y0=-165.0, scale=160.0 / 1450.0, w=160, h=160)
    image = boy.render_pose(pose, ss=1, view=view)
    return hashlib.sha256(image.tobytes()).hexdigest()


def target_world(pose, key):
    lean = pose.get("lean", 0.0)
    root_rotation = boy.rot(lean)
    base = np.asarray(boy.FEET) + np.asarray(pose.get("offset", (0.0, 0.0)))
    neck_world = (np.asarray(boy.NECK) - np.asarray(boy.FEET)) @ root_rotation.T + base
    head_rotation = boy.rot(lean + pose.get("neck", 0.0))
    return (np.asarray(pose[key]) - boy.NECK) @ head_rotation.T + neck_world


def run():
    fps = 25.0
    face = {"eyes": "shut", "brows": "worried", "mouth": "blubber"}
    a = boy.P(**boy.RUB_A, face=face)
    b = boy.P(**boy.RUB_B, face=face)
    keys = [(0.0, a, 0.0, "snap"), (1.0, b, 0.4, "ease_in_out"),
            (2.0, a, 0.4, "ease_in_out")]
    result = clip.clip_frames(keys, 2.5, fps=fps,
                              point_keys=("near_hand_on_head", "far_hand_on_head"),
                              point_resolver=boy.hand_target_for_pose)

    check("positive", "hold_one_cell", len(set(map(hash_pose, result.poses[:25]))) == 1)
    check("positive", "point_four_seconds_is_ten_inbetweens", result.move_frames[1] == 10,
          result.move_frames)
    hashes = list(map(hash_pose, result.poses))
    forward = [hashes[24]] + hashes[25:35]
    reverse = [hashes[49]] + hashes[50:60]
    check("positive", "exact_reverse_reuses_forward_cells", reverse == list(reversed(forward)),
          "forward=%d reverse=%d shared=%d" % (len(set(forward)), len(set(reverse)),
                                                len(set(forward) & set(reverse))))

    angle_keys = [(0.0, boy.P(neck=0.0), 0.0, "snap"),
                  (1.0, boy.P(neck=100.0), 0.4, "ease_in_out")]
    angled = clip.clip_frames(angle_keys, 1.5, fps=fps)
    values = [angled.poses[index]["neck"] for index in range(24, 35)]
    deltas = [abs(y - x) for x, y in zip(values, values[1:])]
    check("positive", "ease_has_small_ends", deltas[0] < max(deltas[3:7]) and deltas[-1] < max(deltas[3:7]),
          deltas)

    start = boy.P()
    end = boy.P(**boy.RUB_A, face=face)
    desired_start = np.asarray(boy.hand_target_for_pose(start, "near_hand_on_head"))
    desired_end = np.asarray(end["near_hand_on_head"])
    good_errors, bad_errors = [], []
    for step in range(1, 11):
        raw = step / 10.0
        eased = clip.ease_amount("ease_in_out", raw)
        good = clip.interpolate_pose(start, end, eased,
                                     point_keys=("near_hand_on_head", "far_hand_on_head"),
                                     point_resolver=boy.hand_target_for_pose)
        good_errors.append(float(np.linalg.norm(boy.hand_world(good, "near") -
                                                target_world(good, "near_hand_on_head"))))
        bad = boy.lerp_pose(start, end, eased)
        desired = desired_start + (desired_end - desired_start) * eased
        bad_with_target = dict(bad)
        bad_with_target["near_hand_on_head"] = tuple(desired)
        desired_world = target_world(bad_with_target, "near_hand_on_head")
        bad_errors.append(float(np.linalg.norm(boy.hand_world(bad, "near") - desired_world)))
    check("positive", "ik_point_path_stays_within_five_units", max(good_errors) < 5.0, max(good_errors))
    check("negative", "angle_lerped_ik_drift_is_detected", max(bad_errors) > 10.0, max(bad_errors))

    event_frames = [clip.display_frame(item[0], fps) for item in keys]
    check("positive", "event_frames_strictly_increasing",
          all(b > a for a, b in zip(event_frames, event_frames[1:])), event_frames)
    try:
        clip.clip_frames([(0.0, a, 0.0, "snap"), (0.01, b, 0.4, "linear")], 1.0, fps=fps,
                         point_keys=("near_hand_on_head", "far_hand_on_head"),
                         point_resolver=boy.hand_target_for_pose)
        check("negative", "collapsed_event_refused", False, "accepted")
    except ValueError as exc:
        check("negative", "collapsed_event_refused", "collapse" in str(exc), str(exc))

    first = boy.render_pose(a, ss=1)
    second = boy.render_pose(a, ss=1)
    check("positive", "held_frames_byte_identical", first.tobytes() == second.tobytes())

    reduced, report = clip.reduce_longest_moves({1: 10, 2: 8, 3: 6}, 5)
    check("positive", "budget_reduces_longest_first_above_floor",
          sum(reduced.values()) == 19 and min(reduced.values()) >= 4 and reduced[1] < 10,
          {"counts": reduced, "report": report})

    def tiny_render(pose):
        image = Image.new("L", (32, 32), 255)
        ImageDraw.Draw(image).line((2, 16, int(round(pose["joint"])), 16), fill=0, width=2)
        return image

    tiny_keys = [(0.0, {"joint": 2.0, "face": {}}, 0.0, "snap"),
                 (0.5, {"joint": 29.0, "face": {}}, 0.4, "linear")]
    with tempfile.TemporaryDirectory(prefix="clip_rt_test_") as temp:
        bounded = clip.render_clip(tiny_keys, 1.1, Path(temp), tiny_render, fps=fps, max_cells=6)
        check("positive", "max_cells_enforced", bounded.unique_cells <= 6 and bool(bounded.reductions),
              {"unique": bounded.unique_cells, "reductions": bounded.reductions})
    try:
        with tempfile.TemporaryDirectory(prefix="clip_rt_fail_") as temp:
            clip.render_clip(tiny_keys, 1.1, Path(temp), tiny_render, fps=fps, max_cells=2)
        check("negative", "impossible_budget_refused", False, "accepted")
    except ValueError as exc:
        check("negative", "impossible_budget_refused", "cannot be met" in str(exc), str(exc))

    tear_keys = [(0.0, boy.P(face=dict(face, tears=[0.0])), 0.0, "snap")]
    tears = clip.clip_frames(tear_keys, 0.2, fps=fps, tear_speed=0.5)
    tear_values = [pose["face"]["tears"][0] for pose in tears.poses]
    check("positive", "tears_move_each_display_frame", len(set(tear_values)) == len(tear_values), tear_values)

    cat_keys, cat_length = cat.realtime_clip()
    cat_result = clip.clip_frames(cat_keys, cat_length, fps=fps)
    check("positive", "cat_uses_shared_interface", len(cat_result.poses) == round(cat_length * fps),
          len(cat_result.poses))

    check("positive", "default_render_scale_is_two", clip.scaled_render_size(803) == 1606)
    try:
        clip.scaled_render_size(803, 0.5)
        check("negative", "sub_1x_render_scale_refused", False, "accepted")
    except ValueError as exc:
        check("negative", "sub_1x_render_scale_refused", "at least 1" in str(exc), str(exc))

    passed = sum(ok for _kind, _label, ok, _detail in RESULTS)
    positive = [item for item in RESULTS if item[0] == "positive"]
    negative = [item for item in RESULTS if item[0] == "negative"]
    for kind, label, ok, detail in RESULTS:
        if not ok:
            print("FAIL|%s|%s|%s" % (kind, label, detail))
    print("CLIP_RENDER_HARNESS|positive=%d/%d|negative=%d/%d|total=%d/%d" % (
        sum(ok for _kind, _label, ok, _detail in positive), len(positive),
        sum(ok for _kind, _label, ok, _detail in negative), len(negative), passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(run())
