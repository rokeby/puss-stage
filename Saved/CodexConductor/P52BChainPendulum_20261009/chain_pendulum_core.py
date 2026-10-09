"""Offline-safe P52b coupled chain pendulum built on P52's numerical helpers."""
from __future__ import annotations

import importlib.util
import math
import os


HERE = os.path.dirname(os.path.abspath(__file__))
P52_DIR = os.path.normpath(os.path.join(HERE, "..", "P52PendulumSwing_20261009"))
SPEC = importlib.util.spec_from_file_location("p52_pendulum_core_shared", os.path.join(P52_DIR, "pendulum_core.py"))
P52 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P52)

ChainPendulumError = P52.PendulumError
require = P52.require
finite = P52.finite
canonical_fingerprint = P52.canonical_fingerprint

SCHEMA_KEYS = {"count", "length_cm", "links", "body"}
LINK_KEYS = {"index", "pivot_cm", "length_cm", "mass_kg"}
BODY_KEYS = {"attach_cm", "mass_kg"}
DEFAULT_NULL_LINK_MASS_RATIO = 0.05
GEOMETRY_TOLERANCE_CM = 0.05


def _strict_keys(value, expected, label):
    require(isinstance(value, dict), "SCHEMA_TYPE|%s|object" % label)
    actual = set(value)
    require(actual == expected,
            "SCHEMA_KEYS|%s|missing=%s|extra=%s" %
            (label, sorted(expected - actual), sorted(actual - expected)))


def _schema_number(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            "SCHEMA_NUMBER|%s" % label)
    return finite(value, label)


def _vector3(value, label):
    require(isinstance(value, list) and len(value) == 3, "SCHEMA_VECTOR3|%s" % label)
    return [_schema_number(component, "%s[%d]" % (label, index)) for index, component in enumerate(value)]


def _distance(a, b):
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def validate_schema(raw, null_link_mass_ratio=DEFAULT_NULL_LINK_MASS_RATIO):
    """Validate the exact Hyper3D contract and resolve only null link masses."""
    _strict_keys(raw, SCHEMA_KEYS, "root")
    require(isinstance(raw["count"], int) and not isinstance(raw["count"], bool), "SCHEMA_COUNT_TYPE")
    count = raw["count"]
    require(1 <= count <= 32, "SCHEMA_COUNT_RANGE")
    total_length = _schema_number(raw["length_cm"], "length_cm")
    require(total_length > 0.0, "SCHEMA_LENGTH_RANGE")
    require(isinstance(raw["links"], list) and len(raw["links"]) == count,
            "SCHEMA_LINK_COUNT|want=%d|got=%s" % (count, len(raw["links"]) if isinstance(raw["links"], list) else "non-list"))
    _strict_keys(raw["body"], BODY_KEYS, "body")
    attach = _vector3(raw["body"]["attach_cm"], "body.attach_cm")
    body_mass = _schema_number(raw["body"]["mass_kg"], "body.mass_kg")
    require(body_mass > 0.0, "SCHEMA_BODY_MASS_RANGE")
    ratio = finite(null_link_mass_ratio, "null_link_mass_ratio")
    require(0.001 <= ratio <= 1.0, "NULL_MASS_RATIO_RANGE")

    links = []
    inferred = []
    for position, link in enumerate(raw["links"]):
        _strict_keys(link, LINK_KEYS, "links[%d]" % position)
        require(isinstance(link["index"], int) and not isinstance(link["index"], bool),
                "SCHEMA_LINK_INDEX_TYPE|%d" % position)
        require(link["index"] == position, "SCHEMA_LINK_INDEX_ORDER|want=%d|got=%r" % (position, link["index"]))
        pivot = _vector3(link["pivot_cm"], "links[%d].pivot_cm" % position)
        length = _schema_number(link["length_cm"], "links[%d].length_cm" % position)
        require(length > 0.0, "SCHEMA_LINK_LENGTH_RANGE|%d" % position)
        if link["mass_kg"] is None:
            mass = body_mass * ratio
            inferred.append({"index": position, "mass_kg": mass, "rule": "body_mass_kg * null_link_mass_ratio"})
        else:
            mass = _schema_number(link["mass_kg"], "links[%d].mass_kg" % position)
            require(mass > 0.0, "SCHEMA_LINK_MASS_RANGE|%d" % position)
        links.append({"index": position, "pivot_cm": pivot, "length_cm": length, "mass_kg": mass,
                      "mass_inferred": link["mass_kg"] is None})

    require(_distance(links[0]["pivot_cm"], [0.0, 0.0, 0.0]) <= GEOMETRY_TOLERANCE_CM,
            "SCHEMA_ORIGIN_NOT_TOP_HANG")
    for index, link in enumerate(links):
        endpoint = attach if index == count - 1 else links[index + 1]["pivot_cm"]
        measured = _distance(link["pivot_cm"], endpoint)
        require(abs(measured - link["length_cm"]) <= GEOMETRY_TOLERANCE_CM,
                "SCHEMA_LINK_GEOMETRY|index=%d|declared=%.6f|measured=%.6f" %
                (index, link["length_cm"], measured))
    sum_length = sum(link["length_cm"] for link in links)
    require(abs(sum_length - total_length) <= GEOMETRY_TOLERANCE_CM,
            "SCHEMA_TOTAL_LENGTH|declared=%.6f|sum=%.6f" % (total_length, sum_length))
    return {"count": count, "length_cm": total_length, "links": links,
            "body": {"attach_cm": attach, "mass_kg": body_mass},
            "mass_inference": {"null_link_mass_ratio": ratio, "resolved": inferred}}


def check_config(raw, schema):
    base = P52.check_config(dict(raw, length_cm=schema["length_cm"]))
    mode = str(raw.get("stability_guard", "refuse")).lower()
    require(mode in ("refuse", "clip"), "STABILITY_GUARD_MODE")
    max_velocity = finite(raw.get("max_angular_velocity_degrees_s", 360.0),
                          "max_angular_velocity_degrees_s")
    require(10.0 <= max_velocity <= 5000.0, "MAX_ANGULAR_VELOCITY_RANGE")
    base.update(stability_guard=mode, max_angular_velocity_degrees_s=max_velocity,
                null_link_mass_ratio=schema["mass_inference"]["null_link_mass_ratio"])
    return base


def _mass_system(schema):
    links = schema["links"]
    count = schema["count"]
    lengths = [row["length_cm"] for row in links]
    masses = [row["mass_kg"] for row in links]
    body_mass = schema["body"]["mass_kg"]
    matrix = [[0.0] * count for _ in range(count)]
    for body_index, mass in enumerate(masses):
        coeff = [lengths[k] if k < body_index else (0.5 * lengths[k] if k == body_index else 0.0)
                 for k in range(count)]
        for row in range(count):
            for column in range(count):
                matrix[row][column] += mass * coeff[row] * coeff[column]
        matrix[body_index][body_index] += mass * lengths[body_index] ** 2 / 12.0
    for row in range(count):
        for column in range(count):
            matrix[row][column] += body_mass * lengths[row] * lengths[column]
    lever = [lengths[index] * (body_mass + sum(masses[index + 1:]) + 0.5 * masses[index])
             for index in range(count)]
    stiffness = [980.665 * value for value in lever]
    return matrix, stiffness, lever


def _solve(matrix, rhs):
    count = len(rhs)
    augmented = [list(matrix[row]) + [float(rhs[row])] for row in range(count)]
    for column in range(count):
        pivot = max(range(column, count), key=lambda row: abs(augmented[row][column]))
        require(abs(augmented[pivot][column]) > 1.0e-12, "MASS_MATRIX_SINGULAR")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(count):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[column])]
    result = [augmented[row][-1] for row in range(count)]
    require(all(math.isfinite(value) for value in result), "SIM_NON_FINITE")
    return result


def _max_natural_frequency(matrix, stiffness):
    vector = [1.0 / math.sqrt(len(stiffness))] * len(stiffness)
    eigenvalue = 0.0
    for _ in range(48):
        projected = _solve(matrix, [stiffness[index] * vector[index] for index in range(len(vector))])
        norm = math.sqrt(sum(value * value for value in projected))
        require(norm > 0.0 and math.isfinite(norm), "STABILITY_EIGENVALUE")
        vector = [value / norm for value in projected]
        eigenvalue = sum(vector[index] * projected[index] for index in range(len(vector)))
    require(eigenvalue > 0.0, "STABILITY_EIGENVALUE")
    return math.sqrt(eigenvalue)


def _simulate_axis(acceleration, dt, matrix, stiffness, lever, cfg):
    count = len(stiffness)
    angle = [0.0] * count
    velocity = [0.0] * count
    damping = [2.0 * cfg["damping_ratio"] * math.sqrt(matrix[i][i] * stiffness[i]) for i in range(count)]
    max_angle = math.radians(cfg["max_angle_degrees"])
    max_velocity = math.radians(cfg["max_angular_velocity_degrees_s"])
    dense = []
    clipped = 0
    for sample_index, support_accel in enumerate(acceleration):
        rhs = [-lever[i] * support_accel - stiffness[i] * angle[i] - damping[i] * velocity[i]
               for i in range(count)]
        angular_accel = _solve(matrix, rhs)
        for index in range(count):
            velocity[index] += angular_accel[index] * dt
            candidate = angle[index] + velocity[index] * dt
            blown = (not math.isfinite(candidate) or not math.isfinite(velocity[index])
                     or abs(candidate) > max_angle or abs(velocity[index]) > max_velocity)
            if blown and cfg["stability_guard"] == "refuse":
                raise ChainPendulumError("STABILITY_BLOWUP|sample=%d|link=%d|dt=%.9f" %
                                         (sample_index, index, dt))
            if blown:
                clipped += 1
                require(math.isfinite(candidate) and math.isfinite(velocity[index]), "SIM_NON_FINITE")
                candidate = max(-max_angle, min(max_angle, candidate))
                velocity[index] = max(-max_velocity, min(max_velocity, velocity[index]))
            angle[index] = candidate
        dense.append(list(angle))
    return dense, clipped


def _compatibility_n1(positions, schema, cfg, dt):
    omega = math.sqrt(980.665 / schema["length_cm"])
    require(dt * omega <= 0.20,
            "STABILITY_DT|dt=%.9f|omega_max=%.9f|product=%.9f|limit=0.20" %
            (dt, omega, dt * omega))
    legacy = P52.simulate(positions, cfg)
    dense = [[[row[0], row[1], row[2]] for row in legacy["dense"]]]
    keys = [legacy["keys"]]
    return {"config": cfg, "schema": schema, "dense_links": dense, "dense_body": list(dense[0]),
            "link_keys": keys, "body_keys": list(keys[0]), "compatibility_mode": "p52_exact_n1",
            "stability": {"dt_seconds": dt, "omega_max_rad_s": omega,
                          "dt_times_omega_max": dt * omega, "limit": 0.20,
                          "clipped_state_updates": 0},
            "max_reconstruction_error_degrees": P52.max_reconstruction_error(legacy["dense"], legacy["keys"])}


def simulate_chain(positions, raw_schema, raw_config):
    ratio = raw_config.get("null_link_mass_ratio", DEFAULT_NULL_LINK_MASS_RATIO)
    schema = validate_schema(raw_schema, ratio)
    cfg = check_config(raw_config, schema)
    rows, dt = P52._rows(positions)
    expected = 1.0 / cfg["fixed_step_hz"]
    require(abs(dt - expected) <= max(1.0e-9, expected * 1.0e-4), "DT_CONFIG_MISMATCH")
    if schema["count"] == 1:
        return _compatibility_n1(positions, schema, cfg, dt)

    local_acceleration = P52._kinematics(rows, dt)
    matrix, stiffness, lever = _mass_system(schema)
    omega_max = _max_natural_frequency(matrix, stiffness)
    dt_omega = dt * omega_max
    require(dt_omega <= 0.20,
            "STABILITY_DT|dt=%.9f|omega_max=%.9f|product=%.9f|limit=0.20" %
            (dt, omega_max, dt_omega))
    forward, clipped_forward = _simulate_axis([row[0] for row in local_acceleration], dt,
                                               matrix, stiffness, lever, cfg)
    lateral, clipped_lateral = _simulate_axis([row[1] for row in local_acceleration], dt,
                                               matrix, stiffness, lever, cfg)
    phase = cfg["idle_phase_cycles"] * 2.0 * math.pi
    dense_links = [[] for _ in range(schema["count"])]
    for sample_index, (t, _x, _y) in enumerate(rows):
        idle = t * 2.0 * math.pi / cfg["idle_period_seconds"] + phase
        for link_index in range(schema["count"]):
            pitch = math.degrees(forward[sample_index][link_index]) + cfg["idle_pitch_degrees"] * math.sin(idle + math.pi * 0.5)
            yaw = math.degrees(lateral[sample_index][link_index]) + cfg["idle_yaw_degrees"] * math.sin(idle)
            require(math.isfinite(pitch) and math.isfinite(yaw), "SIM_NON_FINITE")
            dense_links[link_index].append([t, pitch, yaw])
    link_keys = [P52.decimate(dense, cfg["decimation_error_degrees"]) for dense in dense_links]
    body_dense = [list(row) for row in dense_links[-1]]
    body_keys = P52.decimate(body_dense, cfg["decimation_error_degrees"])
    errors = [P52.max_reconstruction_error(dense, keys) for dense, keys in zip(dense_links, link_keys)]
    errors.append(P52.max_reconstruction_error(body_dense, body_keys))
    return {"config": cfg, "schema": schema, "dense_links": dense_links, "dense_body": body_dense,
            "link_keys": link_keys, "body_keys": body_keys, "compatibility_mode": None,
            "stability": {"dt_seconds": dt, "omega_max_rad_s": omega_max,
                          "dt_times_omega_max": dt_omega, "limit": 0.20,
                          "clipped_state_updates": clipped_forward + clipped_lateral},
            "max_reconstruction_error_degrees": max(errors)}


def drift_matches_tracks(recorded, live, tolerance=1.0e-5):
    if set(recorded) != set(live):
        return False
    return all(P52.drift_matches(recorded[name], live[name], tolerance) for name in recorded)
