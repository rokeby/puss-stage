"""Pure, offline-safe pendulum simulation and ownership helpers for P52."""
from __future__ import annotations

import hashlib
import json
import math


class PendulumError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise PendulumError(message)


def finite(value, label):
    value = float(value)
    require(math.isfinite(value), "NON_FINITE|%s" % label)
    return value


def validate_cue_kick(amplitude_degrees, cue_ids):
    """Mirror the held patch's authoring guard for the offline negative control."""
    amplitude = finite(amplitude_degrees, "kick_amplitude_degrees")
    ids = [str(value).strip() for value in (cue_ids or []) if str(value).strip()]
    require(abs(amplitude) < 1.0e-12 or ids, "KICK_REQUIRES_CUE_ID")
    return {"amplitude_degrees": amplitude, "cue_ids": ids}


def canonical_fingerprint(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def check_config(config):
    out = {
        "length_cm": finite(config.get("length_cm", 300.0), "length_cm"),
        "damping_ratio": finite(config.get("damping_ratio", 0.12), "damping_ratio"),
        "fixed_step_hz": finite(config.get("fixed_step_hz", 120.0), "fixed_step_hz"),
        "idle_yaw_degrees": finite(config.get("idle_yaw_degrees", 2.5), "idle_yaw_degrees"),
        "idle_pitch_degrees": finite(config.get("idle_pitch_degrees", 1.5), "idle_pitch_degrees"),
        "idle_period_seconds": finite(config.get("idle_period_seconds", 7.0), "idle_period_seconds"),
        "idle_phase_cycles": finite(config.get("idle_phase_cycles", 0.0), "idle_phase_cycles"),
        "max_angle_degrees": finite(config.get("max_angle_degrees", 35.0), "max_angle_degrees"),
        "decimation_error_degrees": finite(config.get("decimation_error_degrees", 0.08),
                                             "decimation_error_degrees"),
    }
    require(1.0 <= out["length_cm"] <= 10000.0, "LENGTH_RANGE")
    require(0.0 <= out["damping_ratio"] <= 2.0, "DAMPING_RANGE")
    require(30.0 <= out["fixed_step_hz"] <= 1000.0, "FIXED_STEP_RANGE")
    require(0.25 <= out["idle_period_seconds"] <= 120.0, "IDLE_PERIOD_RANGE")
    require(0.1 <= out["max_angle_degrees"] <= 80.0, "MAX_ANGLE_RANGE")
    require(0.0001 <= out["decimation_error_degrees"] <= 5.0, "DECIMATION_RANGE")
    return out


def _rows(positions):
    rows = []
    last_t = None
    for index, row in enumerate(positions):
        require(len(row) >= 3, "POSITION_ARITY|%d" % index)
        t, x, y = (finite(row[0], "t[%d]" % index), finite(row[1], "x[%d]" % index),
                   finite(row[2], "y[%d]" % index))
        require(last_t is None or t > last_t, "TIME_NOT_STRICT|%d" % index)
        rows.append((t, x, y))
        last_t = t
    require(len(rows) >= 4, "POSITIONS_TOO_SHORT")
    dt = rows[1][0] - rows[0][0]
    require(dt > 0.0, "DT_INVALID")
    require(all(abs((rows[i][0] - rows[i - 1][0]) - dt) <= max(1.0e-9, dt * 1.0e-5)
                for i in range(2, len(rows))), "FIXED_STEP_REQUIRED")
    return rows, dt


def _kinematics(rows, dt):
    n = len(rows)
    vx = [0.0] * n
    vy = [0.0] * n
    for i in range(n):
        a, b = (0, 1) if i == 0 else ((n - 2, n - 1) if i == n - 1 else (i - 1, i + 1))
        span = rows[b][0] - rows[a][0]
        vx[i] = (rows[b][1] - rows[a][1]) / span
        vy[i] = (rows[b][2] - rows[a][2]) / span
    ax = [0.0] * n
    ay = [0.0] * n
    for i in range(1, n - 1):
        ax[i] = (vx[i + 1] - vx[i - 1]) / (2.0 * dt)
        ay[i] = (vy[i + 1] - vy[i - 1]) / (2.0 * dt)
    ax[0], ay[0], ax[-1], ay[-1] = ax[1], ay[1], ax[-2], ay[-2]
    local = []
    tangent = (1.0, 0.0)
    for i in range(n):
        speed = math.hypot(vx[i], vy[i])
        if speed > 1.0e-6:
            tangent = (vx[i] / speed, vy[i] / speed)
        normal = (-tangent[1], tangent[0])
        local.append((ax[i] * tangent[0] + ay[i] * tangent[1],
                      ax[i] * normal[0] + ay[i] * normal[1]))
    return local


def simulate(positions, config):
    """Small-angle damped pendulum forced by support acceleration, semi-implicit fixed step."""
    cfg = check_config(config)
    rows, dt = _rows(positions)
    expected = 1.0 / cfg["fixed_step_hz"]
    require(abs(dt - expected) <= max(1.0e-9, expected * 1.0e-4), "DT_CONFIG_MISMATCH")
    acceleration = _kinematics(rows, dt)
    gravity = 980.665
    omega = math.sqrt(gravity / cfg["length_cm"])
    decay = 2.0 * cfg["damping_ratio"] * omega
    phase = cfg["idle_phase_cycles"] * 2.0 * math.pi
    state = [0.0, 0.0, 0.0, 0.0]  # forward angle/velocity, lateral angle/velocity
    dense = []
    max_radians = math.radians(cfg["max_angle_degrees"])
    for (t, _x, _y), (a_forward, a_lateral) in zip(rows, acceleration):
        # Support acceleration pushes the bob in the opposite direction.
        state[1] += (-a_forward / cfg["length_cm"] - decay * state[1] - omega * omega * state[0]) * dt
        state[3] += (-a_lateral / cfg["length_cm"] - decay * state[3] - omega * omega * state[2]) * dt
        state[0] = max(-max_radians, min(max_radians, state[0] + state[1] * dt))
        state[2] = max(-max_radians, min(max_radians, state[2] + state[3] * dt))
        idle = t * 2.0 * math.pi / cfg["idle_period_seconds"] + phase
        pitch = math.degrees(state[0]) + cfg["idle_pitch_degrees"] * math.sin(idle + math.pi * 0.5)
        yaw = math.degrees(state[2]) + cfg["idle_yaw_degrees"] * math.sin(idle)
        require(math.isfinite(pitch) and math.isfinite(yaw), "SIM_NON_FINITE")
        dense.append([t, pitch, yaw, math.degrees(state[0]), math.degrees(state[2])])
    keys = decimate(dense, cfg["decimation_error_degrees"])
    return {
        "config": cfg,
        "dense": dense,
        "keys": keys,
        "max_abs_pitch_degrees": max(abs(row[1]) for row in dense),
        "max_abs_yaw_degrees": max(abs(row[2]) for row in dense),
        "max_motion_pitch_degrees": max(abs(row[3]) for row in dense),
        "max_motion_yaw_degrees": max(abs(row[4]) for row in dense),
        "peak_times_seconds": peak_times(dense),
    }


def _segment_error(rows, first, last, index):
    if last == first:
        return 0.0
    u = (rows[index][0] - rows[first][0]) / (rows[last][0] - rows[first][0])
    pitch = rows[first][1] + (rows[last][1] - rows[first][1]) * u
    yaw = rows[first][2] + (rows[last][2] - rows[first][2]) * u
    return max(abs(rows[index][1] - pitch), abs(rows[index][2] - yaw))


def decimate(dense, tolerance):
    tolerance = finite(tolerance, "decimation_tolerance")
    require(tolerance > 0.0, "DECIMATION_NONPOSITIVE")
    keep = {0, len(dense) - 1}
    stack = [(0, len(dense) - 1)]
    while stack:
        first, last = stack.pop()
        worst, split = -1.0, None
        for index in range(first + 1, last):
            error = _segment_error(dense, first, last, index)
            if error > worst:
                worst, split = error, index
        if split is not None and worst > tolerance:
            keep.add(split)
            stack.extend(((first, split), (split, last)))
    return [[dense[i][0], dense[i][1], dense[i][2]] for i in sorted(keep)]


def max_reconstruction_error(dense, keys):
    worst = 0.0
    cursor = 0
    for row in dense:
        while cursor + 1 < len(keys) - 1 and row[0] > keys[cursor + 1][0]:
            cursor += 1
        a, b = keys[cursor], keys[min(cursor + 1, len(keys) - 1)]
        u = 0.0 if b[0] == a[0] else (row[0] - a[0]) / (b[0] - a[0])
        worst = max(worst, abs(row[1] - (a[1] + (b[1] - a[1]) * u)),
                    abs(row[2] - (a[2] + (b[2] - a[2]) * u)))
    return worst


def peak_times(dense):
    out = []
    for channel, name in ((1, "pitch"), (2, "yaw")):
        candidates = []
        for i in range(1, len(dense) - 1):
            value = abs(dense[i][channel])
            if value >= abs(dense[i - 1][channel]) and value > abs(dense[i + 1][channel]):
                candidates.append((value, dense[i][0], dense[i][channel]))
        for value, time, signed in sorted(candidates, reverse=True)[:4]:
            out.append({"channel": name, "time_seconds": time, "degrees": signed, "magnitude": value})
    return sorted(out, key=lambda row: row["time_seconds"])


def drift_matches(recorded_keys, live_keys, tolerance=1.0e-5):
    if len(recorded_keys) != len(live_keys):
        return False
    return all(int(a[0]) == int(b[0]) and abs(float(a[1]) - float(b[1])) <= tolerance
               and abs(float(a[2]) - float(b[2])) <= tolerance
               for a, b in zip(recorded_keys, live_keys))
