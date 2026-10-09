"""Offline positive/negative harness for cat_rig.py (numpy/Pillow only)."""
from __future__ import annotations

import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import cat_rig as cat  # noqa: E402
from puppet_cut import punch  # noqa: E402


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def point_segment_distance(point, start, end):
    p = np.asarray(point, dtype=float)
    a = np.asarray(start, dtype=float)
    b = np.asarray(end, dtype=float)
    segment = b - a
    amount = np.dot(p - a, segment) / (np.dot(segment, segment) + 1e-12)
    closest = a + np.clip(amount, 0.0, 1.0) * segment
    return float(np.linalg.norm(p - closest))


def cut_has_margin(outline, cut, margin=6.0):
    edges = list(zip(outline, outline[1:] + outline[:1]))
    for point in cut:
        if not point_in_polygon(point, outline):
            return False
        if min(point_segment_distance(point, a, b) for a, b in edges) + 1e-6 < margin:
            return False
    return True


def component_count(image, threshold=128):
    black = np.asarray(image) < threshold
    seen = np.zeros(black.shape, dtype=bool)
    count = 0
    height, width = black.shape
    for y, x in zip(*np.nonzero(black & ~seen)):
        if seen[y, x]:
            continue
        count += 1
        queue = deque([(y, x)])
        seen[y, x] = True
        while queue:
            cy, cx = queue.popleft()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1),
                           (-1, 1), (1, -1), (1, 1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < height and 0 <= nx < width and black[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
    return count


def enclosed_hole_count(image, threshold=128):
    """Count light regions that cannot reach the raster border."""
    light = np.asarray(image) >= threshold
    seen = np.zeros(light.shape, dtype=bool)
    height, width = light.shape
    queue = deque()
    for x in range(width):
        for y in (0, height - 1):
            if light[y, x] and not seen[y, x]:
                seen[y, x] = True
                queue.append((y, x))
    for y in range(height):
        for x in (0, width - 1):
            if light[y, x] and not seen[y, x]:
                seen[y, x] = True
                queue.append((y, x))

    def flood(active):
        while active:
            cy, cx = active.popleft()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = cy + dy, cx + dx
                if (0 <= ny < height and 0 <= nx < width and
                        light[ny, nx] and not seen[ny, nx]):
                    seen[ny, nx] = True
                    active.append((ny, nx))

    flood(queue)
    holes = 0
    for y, x in zip(*np.nonzero(light & ~seen)):
        if seen[y, x]:
            continue
        holes += 1
        seen[y, x] = True
        flood(deque([(y, x)]))
    return holes


def dynamic_part_raster(parts, padding=16.0):
    """Raster local controls without clipping them to the review camera."""
    points = np.asarray([point for _name, outline, _cuts, _z in parts for point in outline])
    minimum = points.min(axis=0) - padding
    maximum = points.max(axis=0) + padding
    view = {
        "x0": float(minimum[0]),
        "y0": float(minimum[1]),
        "scale": 1.0,
        "w": int(math.ceil(maximum[0] - minimum[0])),
        "h": int(math.ceil(maximum[1] - minimum[1])),
    }
    return cat.render_parts(parts, view=view, ss=1)


def slice_span(outline, coordinate, axis):
    """Span across a polygon at x/y=coordinate; used for real outline widths."""
    hits = []
    other = 1 - axis
    for start, end in zip(outline, outline[1:] + outline[:1]):
        a, b = start[axis], end[axis]
        if (a <= coordinate < b) or (b <= coordinate < a):
            amount = (coordinate - a) / (b - a)
            hits.append(start[other] + amount * (end[other] - start[other]))
    if len(hits) < 2:
        return 0.0
    return max(hits) - min(hits)


def local_parts_catalog():
    parts = [("body", *cat.body_part()), ("front_leg", *cat.upper_leg_part()),
             ("front_paw", *cat.paw_part())]
    for index in range(3):
        parts.append((f"tail_{index + 1}", *cat.tail_part(index)))
    for ears in cat.EAR_OUTLINES:
        for eyes in cat.EYE_CUTS:
            for mouth in cat.MOUTH_CUTS:
                face = {"ears": ears, "eyes": eyes, "mouth": mouth}
                parts.append((f"head_{ears}_{eyes}_{mouth}", *cat.head_part(face)))
    parts.append(("lower_jaw", *cat.jaw_part()))
    return parts


def facing_left(outline, nose):
    min_x = min(point[0] for point in outline)
    return math.isclose(nose[0], min_x, abs_tol=1e-6)


def convex_hull(points):
    """Monotonic-chain hull; collinear interior points are discarded."""
    ordered = sorted(set(tuple(point) for point in points))
    if len(ordered) <= 1:
        return ordered

    def cross(origin, a, b):
        return ((a[0] - origin[0]) * (b[1] - origin[1]) -
                (a[1] - origin[1]) * (b[0] - origin[0]))

    lower = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def check(condition, label, failures):
    if not condition:
        failures.append(label)


def run():
    failures = []
    counts = {
        "named_pose_render_positive": 0,
        "determinism_positive": 0,
        "connected_positive": 0,
        "cut_margin_positive": 0,
        "cut_margin_negative": 0,
        "overlap_positive": 0,
        "facing_positive": 0,
        "facing_negative": 0,
        "tail_tip_positive": 0,
        "tail_tip_negative": 0,
        "tail_union_positive": 0,
        "tail_body_holes_positive": 0,
        "tail_filled_positive": 0,
        "tail_width_positive": 0,
        "tail_width_negative": 0,
        "tail_gap_negative": 0,
        "demo_positive": 0,
    }
    components = {}

    # Every named pose renders, is byte-deterministic, and is one connected shadow including its wires.
    for name in cat.POSE_TABLE:
        pose = cat.make_pose(name)
        first = cat.render_pose(pose)
        second = cat.render_pose(pose)
        ok_render = first.size == (cat.VIEW["w"], cat.VIEW["h"]) and first.mode == "L"
        check(ok_render, f"render:{name}", failures)
        counts["named_pose_render_positive"] += int(ok_render)
        deterministic = first.tobytes() == second.tobytes()
        check(deterministic, f"determinism:{name}", failures)
        counts["determinism_positive"] += int(deterministic)
        components[name] = component_count(first)
        connected = components[name] == 1
        check(connected, f"components:{name}={components[name]}", failures)
        counts["connected_positive"] += int(connected)

    # The second tail-flick pose is part of the promised two-frame move.
    second_flick = cat.make_pose("tail_flick", **cat.TAIL_FLICK_FRAMES[1])
    check(cat.render_pose(second_flick).tobytes() != cat.render_pose(cat.make_pose("tail_flick")).tobytes(),
          "tail_flick_frames_differ", failures)

    # All local cuts remain inside their own card part with Gary's six-unit safety margin.
    cut_total = 0
    for part_name, outline, cuts in local_parts_catalog():
        for index, cut in enumerate(cuts):
            cut_total += 1
            good = cut_has_margin(outline, cut, cat.LOOK["cut_margin"])
            check(good, f"cut_margin:{part_name}:{index}", failures)
            counts["cut_margin_positive"] += int(good)

    misplaced = punch(500.0, 500.0, 8.0)
    rejected = not cut_has_margin(cat.body_part()[0], misplaced, cat.LOOK["cut_margin"])
    check(rejected, "negative_cut_was_not_rejected", failures)
    counts["cut_margin_negative"] += int(rejected)

    # Product-of-transmissions control: uncovered hole is light; the same hole under card is black.
    view = {"x0": 0.0, "y0": 0.0, "scale": 1.0, "w": 100, "h": 100}
    base = ("base", [(10, 10), (90, 10), (90, 90), (10, 90)], [punch(50, 50, 12)], 0)
    cover = ("cover", [(42, 42), (58, 42), (58, 58), (42, 58)], [], 1)
    open_image = cat.render_parts([base], view=view, ss=2)
    covered_image = cat.render_parts([base, cover], view=view, ss=2)
    open_ok = np.asarray(open_image)[50, 50] > 250
    covered_ok = np.asarray(covered_image)[50, 50] < 5
    check(open_ok, "uncovered_cut_not_light", failures)
    check(covered_ok, "covered_cut_not_black", failures)
    counts["overlap_positive"] += int(open_ok) + int(covered_ok)

    # The nose, not an ear or ruff, is the left-most point of the upright head. Mirroring must fail.
    pose = cat.make_pose("sit_upright")
    parts, _, _ = cat.pose_parts(pose)
    head = next(outline for name, outline, _cuts, _z in parts if name == "head")
    root = np.asarray(cat.RIG["root"])
    neck = np.asarray(cat.RIG["neck"]) @ cat.rot(pose["body_lean"]).T + root
    head_matrix = cat.rot(pose["body_lean"] + pose["neck"]) @ np.diag(cat.RIG["head_scale"])
    nose = np.asarray((-214.0, -90.0)) @ head_matrix.T + neck
    left_ok = facing_left(head, nose)
    check(left_ok, "upright_head_not_left_facing", failures)
    counts["facing_positive"] += int(left_ok)
    mirrored_head = [[-x, y] for x, y in head]
    mirrored_nose = [-nose[0], nose[1]]
    mirror_rejected = not facing_left(mirrored_head, mirrored_nose)
    check(mirror_rejected, "mirrored_head_not_rejected", failures)
    counts["facing_negative"] += int(mirror_rejected)

    # The wrapped upright tip must emerge beyond the main (non-tail) silhouette hull.
    body_points = [point for name, outline, _cuts, _z in parts
                   if not name.startswith("tail_") for point in outline]
    body_hull = convex_hull(body_points)
    tail_tip = cat.tail_tip_for_pose(pose)
    tip_outside = not point_in_polygon(tail_tip, body_hull)
    check(tip_outside, f"upright_tail_tip_inside_body_hull:{tail_tip.tolist()}", failures)
    counts["tail_tip_positive"] += int(tip_outside)

    # Negative control: a tail tip drawn in the body mass must be rejected by the same predicate.
    body_outline = next(outline for name, outline, _cuts, _z in parts if name == "body")
    inside_tip = np.mean(np.asarray(body_outline), axis=0)
    inside_rejected = point_in_polygon(inside_tip, body_hull)
    check(inside_rejected, "inside_tail_tip_not_rejected", failures)
    counts["tail_tip_negative"] += int(inside_rejected)

    # A tail is a single filled card silhouette: connected, without enclosed
    # light, and without making a light ring where it meets the body.
    tail_topology = {}
    topology_poses = [(name, cat.make_pose(name)) for name in cat.POSE_TABLE]
    topology_poses.append(("tail_flick_frame_2", second_flick))
    for name, topology_pose in topology_poses:
        pose_parts, _, _ = cat.pose_parts(topology_pose)
        tail_parts = [part for part in pose_parts if part[0].startswith("tail_")]
        tail_image = dynamic_part_raster(tail_parts)
        tail_components = component_count(tail_image)
        tail_holes = enclosed_hole_count(tail_image)
        tail_topology[name] = {"components": tail_components, "holes": tail_holes}
        topology_ok = tail_components == 1 and tail_holes == 0
        check(topology_ok, f"tail_topology:{name}:{tail_topology[name]}", failures)
        counts["tail_union_positive"] += int(topology_ok)

        body_and_tail = [part for part in pose_parts
                         if part[0].startswith("tail_") or part[0] == "body"]
        solid_body_and_tail = [(part_name, outline, [], z)
                               for part_name, outline, _cuts, z in body_and_tail]
        body_tail_holes = enclosed_hole_count(dynamic_part_raster(solid_body_and_tail))
        no_body_ring = body_tail_holes == 0
        check(no_body_ring, f"tail_body_holes:{name}={body_tail_holes}", failures)
        counts["tail_body_holes_positive"] += int(no_body_ring)

    local_tails = [cat.tail_part(index) for index in range(3)]
    filled = sum(not cuts for _outline, cuts in local_tails)
    check(filled == 3, f"tail_segments_not_filled:{filled}/3", failures)
    counts["tail_filled_positive"] += filled

    # Measure widths from the generated outlines, not merely from the look dict.
    leg_width = slice_span(cat.upper_leg_part()[0], 0.0, axis=1)
    root_outline = local_tails[0][0]
    tip_outline = local_tails[-1][0]
    root_width = slice_span(root_outline, 0.0, axis=0)
    tip_width = slice_span(tip_outline, cat.RIG["tail_lengths"][-1], axis=0)
    root_heavy = root_width + 1e-6 >= leg_width
    tip_taper = tip_width + 1e-6 >= 0.45 * root_width
    check(root_heavy, f"tail_root_too_thin:root={root_width:.2f}:leg={leg_width:.2f}", failures)
    check(tip_taper, f"tail_tip_over_tapered:tip={tip_width:.2f}:root={root_width:.2f}", failures)
    counts["tail_width_positive"] += int(root_heavy) + int(tip_taper)

    # Negative width control: the same root sleeve squeezed below 40% of the leg.
    thin_scale = (0.35 * leg_width) / root_width
    thin_tail = [[x, y * thin_scale] for x, y in root_outline]
    thin_width = slice_span(thin_tail, 0.0, axis=0)
    thin_rejected = not (thin_width + 1e-6 >= leg_width)
    check(thin_rejected and thin_width < 0.40 * leg_width,
          f"thin_tail_not_rejected:tail={thin_width:.2f}:leg={leg_width:.2f}", failures)
    counts["tail_width_negative"] += int(thin_rejected and thin_width < 0.40 * leg_width)

    # Negative connectivity control: preserve joints 2/3 but open a visible gap at joint 1.
    gap = (cat.TAIL_SPECS["overlap"] * 2.0 +
           cat.RIG["tail_widths"][0][1] / 2.0 +
           cat.RIG["tail_widths"][1][0] / 2.0 + 32.0)
    tail_1 = ("tail_1", local_tails[0][0], [], 0)
    tail_2_origin = cat.RIG["tail_lengths"][0] + gap
    tail_2 = ("tail_2", cat.place(local_tails[1][0], cat.rot(0.0), (tail_2_origin, 0.0)), [], 1)
    tail_3_origin = tail_2_origin + cat.RIG["tail_lengths"][1]
    tail_3 = ("tail_3", cat.place(local_tails[2][0], cat.rot(0.0), (tail_3_origin, 0.0)), [], 2)
    gap_components = component_count(dynamic_part_raster([tail_1, tail_2, tail_3]))
    gap_rejected = gap_components > 1
    check(gap_rejected, f"gapped_tail_not_rejected:components={gap_components}", failures)
    counts["tail_gap_negative"] += int(gap_rejected)

    # Source frames preserve exact still holds and use only the requested stepped transitions.
    demo = cat.stepped_demo_poses()
    first_hold = [cat.render_pose(frame).tobytes() for frame in demo[:cat.CLI_DEFAULTS["hold_frames"]]]
    hold_ok = len(set(first_hold)) == 1
    transition_start = cat.CLI_DEFAULTS["hold_frames"]
    transition = [cat.render_pose(frame).tobytes() for frame in
                  demo[transition_start:transition_start + cat.CLI_DEFAULTS["move_frames"]]]
    transition_ok = len(set(transition)) == cat.CLI_DEFAULTS["move_frames"]
    durations = cat.gif_frame_durations(len(demo), cat.CLI_DEFAULTS["fps"])
    timing_ok = (len(durations) == len(demo) and
                 sum(durations) == round(len(demo) * 1000 / cat.CLI_DEFAULTS["fps"]))
    check(hold_ok, "demo_hold_frames_not_identical", failures)
    check(transition_ok, "demo_transition_not_stepped", failures)
    check(timing_ok, "demo_gif_timing_not_eight_fps", failures)
    counts["demo_positive"] += int(hold_ok) + int(transition_ok) + int(timing_ok)

    positive_passed = (counts["named_pose_render_positive"] + counts["determinism_positive"] +
                       counts["connected_positive"] + counts["cut_margin_positive"] +
                       counts["overlap_positive"] + counts["facing_positive"] +
                       counts["tail_tip_positive"] + counts["tail_union_positive"] +
                       counts["tail_body_holes_positive"] + counts["tail_filled_positive"] +
                       counts["tail_width_positive"] + counts["demo_positive"] + 1)  # tail flick
    positive_total = (len(cat.POSE_TABLE) * 3 + cut_total + 2 + 1 + 1 + 3 + 1 +
                      len(topology_poses) * 2 + 3 + 2)
    negative_passed = (counts["cut_margin_negative"] + counts["facing_negative"] +
                       counts["tail_tip_negative"] + counts["tail_width_negative"] +
                       counts["tail_gap_negative"])
    negative_total = 5

    print(f"positive {positive_passed}/{positive_total}")
    print(f"negative {negative_passed}/{negative_total}")
    print(f"named_poses {counts['named_pose_render_positive']}/{len(cat.POSE_TABLE)}")
    print(f"deterministic {counts['determinism_positive']}/{len(cat.POSE_TABLE)}")
    print(f"connected {counts['connected_positive']}/{len(cat.POSE_TABLE)} components={components}")
    print(f"cut_margin {counts['cut_margin_positive']}/{cut_total} margin={cat.LOOK['cut_margin']}")
    print(f"overlap {counts['overlap_positive']}/2")
    print(f"facing_positive {counts['facing_positive']}/1 facing_negative {counts['facing_negative']}/1")
    print(f"tail_tip_hull_positive {counts['tail_tip_positive']}/1 "
          f"tail_tip_hull_negative {counts['tail_tip_negative']}/1")
    print(f"tail_topology {counts['tail_union_positive']}/{len(topology_poses)} "
          f"details={tail_topology}")
    print(f"tail_body_no_holes {counts['tail_body_holes_positive']}/{len(topology_poses)}")
    print(f"tail_filled_segments {counts['tail_filled_positive']}/3")
    print(f"tail_width {counts['tail_width_positive']}/2 root={root_width:.2f} "
          f"leg={leg_width:.2f} tip={tip_width:.2f} thin_control={thin_width:.2f}")
    print(f"tail_negative_width {counts['tail_width_negative']}/1 "
          f"tail_negative_gap {counts['tail_gap_negative']}/1 gap_components={gap_components}")
    print(f"demo_source_frames_and_timing {counts['demo_positive']}/3 "
          f"hold={cat.CLI_DEFAULTS['hold_frames']} move={cat.CLI_DEFAULTS['move_frames']}")
    if failures:
        print("FAIL " + ", ".join(failures))
        return 1
    print("CAT_RIG_HARNESS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
