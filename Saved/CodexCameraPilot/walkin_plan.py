"""Pure-Python planner and checker for the Interaction 1 -> Passage 2 walk-in.

Keys are tuples in this order:
    (t, x, y, z, pitch, yaw, roll, focal, focus)

This module deliberately has no Unreal dependency so the timing and safety
contract can be exercised with the system Python before an editor is involved.
"""

import math


_FIELDS = ("x", "y", "z", "pitch", "yaw", "roll")


def _number(mapping, name):
    if name not in mapping:
        raise ValueError("pose is missing %r" % name)
    value = float(mapping[name])
    if not math.isfinite(value):
        raise ValueError("pose %s is not finite" % name)
    return value


def _angle_delta_degrees(start, end):
    """Signed shortest turn from start to end, in [-180, 180)."""
    return (end - start + 180.0) % 360.0 - 180.0


def _angle_error_degrees(a, b):
    return abs(_angle_delta_degrees(a, b))


def plan_walk(seat, target, v_end_cm_s, ease_s, end_s, fps,
              focal0, focal1, focus0, focus1, landed_s, pile_edge_cm):
    """Return per-frame walk-in keys and a report describing the plan.

    Translation accelerates quadratically from rest (linear velocity) for
    ``ease_s``, then continues at ``v_end_cm_s`` and reaches ``target`` exactly
    at ``end_s`` while still moving at that speed. Before ``start_s`` the camera
    holds the seat pose and starting lens/focus.
    """
    seat_values = {name: _number(seat, name) for name in _FIELDS}
    target_values = {name: _number(target, name) for name in _FIELDS}
    v_end = float(v_end_cm_s)
    ease = float(ease_s)
    end = float(end_s)
    frame_rate = float(fps)
    f0, f1 = float(focal0), float(focal1)
    focus_start, focus_end = float(focus0), float(focus1)
    landed = float(landed_s)
    pile_edge = float(pile_edge_cm)

    scalar_values = (v_end, ease, end, frame_rate, f0, f1, focus_start, focus_end, landed, pile_edge)
    if not all(math.isfinite(value) for value in scalar_values):
        raise ValueError("all scalar inputs must be finite")
    if v_end <= 0.0:
        raise ValueError("v_end_cm_s must be positive")
    if ease < 0.0:
        raise ValueError("ease_s must be non-negative")
    if end <= 0.0:
        raise ValueError("end_s must be positive")
    if frame_rate <= 0.0:
        raise ValueError("fps must be positive")
    if f0 <= 0.0 or f1 <= 0.0:
        raise ValueError("focal lengths must be positive for log-linear zoom")
    if landed < 0.0:
        raise ValueError("landed_s must be non-negative")
    if pile_edge < 0.0:
        raise ValueError("pile_edge_cm must be non-negative")

    final_frame_float = end * frame_rate
    final_frame = int(round(final_frame_float))
    if abs(final_frame_float - final_frame) > 1.0e-6:
        raise ValueError("end_s must lie exactly on a frame at fps")

    dx = target_values["x"] - seat_values["x"]
    dy = target_values["y"] - seat_values["y"]
    dz = target_values["z"] - seat_values["z"]
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    if distance <= 0.0:
        raise ValueError("seat and target must be different positions")
    eased_distance = 0.5 * v_end * ease
    if eased_distance > distance + 1.0e-9:
        raise ValueError("ease distance exceeds the complete walk distance")

    duration = ease + (distance - eased_distance) / v_end
    start = end - duration
    if start < -1.0e-9:
        raise ValueError("the walk would start before t=0")
    start = max(0.0, start)

    yaw_delta = _angle_delta_degrees(seat_values["yaw"], target_values["yaw"])
    pitch_delta = target_values["pitch"] - seat_values["pitch"]
    roll_delta = _angle_delta_degrees(seat_values["roll"], target_values["roll"])
    focal_ratio = f1 / f0
    direction = (dx / distance, dy / distance, dz / distance)

    keys = []
    for frame in range(final_frame + 1):
        t = frame / frame_rate
        if t <= start:
            travelled = 0.0
            u = 0.0
        else:
            elapsed = min(duration, t - start)
            if ease > 0.0 and elapsed < ease:
                travelled = 0.5 * (v_end / ease) * elapsed * elapsed
            else:
                travelled = eased_distance + v_end * (elapsed - ease)
            travelled = min(distance, max(0.0, travelled))
            u = min(1.0, max(0.0, elapsed / duration))

        position_u = travelled / distance
        smooth = u * u * (3.0 - 2.0 * u)
        x = seat_values["x"] + dx * position_u
        y = seat_values["y"] + dy * position_u
        z = seat_values["z"] + dz * position_u
        pitch = seat_values["pitch"] + pitch_delta * smooth
        yaw = seat_values["yaw"] + yaw_delta * smooth
        roll = seat_values["roll"] + roll_delta * smooth
        focal = f0 * (focal_ratio ** u)
        focus = focus_start + (focus_end - focus_start) * u
        keys.append((t, x, y, z, pitch, yaw, roll, focal, focus))

    # Assign the boundary values directly so binary floating-point cannot turn
    # an exact handoff into a tolerance-dependent one.
    keys[-1] = (
        end,
        target_values["x"], target_values["y"], target_values["z"],
        target_values["pitch"], target_values["yaw"], target_values["roll"],
        f1, focus_end,
    )

    report = {
        "distance_cm": distance,
        "duration_s": duration,
        "start_s": start,
        "end_s": end,
        "ease_s": ease,
        "fps": frame_rate,
        "final_frame": final_frame,
        "key_count": len(keys),
        "v_end_cm_s": v_end,
        "focal0_mm": f0,
        "focal1_mm": f1,
        "focus0_cm": focus_start,
        "focus1_cm": focus_end,
        "landed_s": landed,
        "pile_edge_cm": pile_edge,
        "yaw_delta_deg": yaw_delta,
        "initial_speed_cm_s": 0.0,
        "seat": dict(seat_values),
        "target": dict(target_values),
    }
    return keys, report


def check_plan(keys, report, target, v_end, landed_s, pile_edge_cm):
    """Return named validation failures; an empty list means the plan passes."""
    failures = []
    if not keys:
        return ["empty-plan: no keys"]

    target_values = {name: _number(target, name) for name in _FIELDS}
    expected_speed = float(v_end)
    landed = float(landed_s)
    pile_edge = float(pile_edge_cm)
    end_s = float(report["end_s"])
    focal0 = float(report["focal0_mm"])
    focal1 = float(report["focal1_mm"])

    last = keys[-1]
    position_error = math.sqrt(
        (last[1] - target_values["x"]) ** 2
        + (last[2] - target_values["y"]) ** 2
        + (last[3] - target_values["z"]) ** 2
    )
    angle_errors = (
        _angle_error_degrees(last[4], target_values["pitch"]),
        _angle_error_degrees(last[5], target_values["yaw"]),
        _angle_error_degrees(last[6], target_values["roll"]),
    )
    if position_error > 0.5 or max(angle_errors) > 0.05:
        failures.append(
            "end-pose: position_error=%.6fcm angle_errors=%s"
            % (position_error, tuple(round(value, 6) for value in angle_errors))
        )
    if abs(last[7] - focal1) > 0.01:
        failures.append("end-focal: expected %.6fmm got %.6fmm" % (focal1, last[7]))

    times = [float(key[0]) for key in keys]
    bad_times = [value for value in times if value < -1.0e-9 or value > end_s + 1.0e-9]
    if bad_times:
        failures.append("time-range: %d keys lie outside [0, %.6f]" % (len(bad_times), end_s))
    if any(b <= a for a, b in zip(times, times[1:])):
        failures.append("time-order: key times are not strictly increasing")

    speeds = []
    for previous, current in zip(keys, keys[1:]):
        dt = current[0] - previous[0]
        if dt <= 0.0:
            continue
        distance = math.sqrt(
            (current[1] - previous[1]) ** 2
            + (current[2] - previous[2]) ** 2
            + (current[3] - previous[3]) ** 2
        )
        speeds.append(distance / dt)

    if not speeds:
        failures.append("arrival-speed: no measurable key intervals")
    else:
        arrival = speeds[-1]
        if abs(arrival - expected_speed) > 0.03 * expected_speed:
            failures.append(
                "arrival-speed: expected %.6fcm/s got %.6fcm/s" % (expected_speed, arrival)
            )
        max_speed = max(speeds)
        if max_speed > 1.05 * expected_speed + 1.0e-6:
            failures.append(
                "over-speed: maximum %.6fcm/s exceeds %.6fcm/s"
                % (max_speed, 1.05 * expected_speed)
            )
        tolerance = max(1.0e-5, expected_speed * 1.0e-7)
        if any(current + tolerance < previous for previous, current in zip(speeds, speeds[1:])):
            failures.append("speed-decreasing: sampled translation speed decreases")
        moving = [speed for speed in speeds if speed > tolerance]
        if moving and moving[0] > 0.05 * expected_speed:
            failures.append(
                "start-speed: first moving interval is %.6fcm/s, not rest" % moving[0]
            )

    focals = [float(key[7]) for key in keys]
    focal_tolerance = 1.0e-9
    if focal1 >= focal0:
        monotone = all(b + focal_tolerance >= a for a, b in zip(focals, focals[1:]))
    else:
        monotone = all(b - focal_tolerance <= a for a, b in zip(focals, focals[1:]))
    if not monotone:
        failures.append("focal-monotonic: focal length reverses direction")

    early_crossings = []
    for key in keys:
        if key[0] >= landed - 1.0e-9:
            continue
        distance_to_target = math.sqrt(
            (key[1] - target_values["x"]) ** 2
            + (key[2] - target_values["y"]) ** 2
            + (key[3] - target_values["z"]) ** 2
        )
        if distance_to_target <= pile_edge + 1.0e-9:
            early_crossings.append((key[0], distance_to_target))
    if early_crossings:
        first_t, first_distance = early_crossings[0]
        failures.append(
            "pile-crossing: within %.3fcm at t=%.6fs (distance %.6fcm) before landed_s=%.6f"
            % (pile_edge, first_t, first_distance, landed)
        )

    return failures
