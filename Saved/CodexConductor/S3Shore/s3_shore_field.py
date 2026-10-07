"""S3 shore ground: deterministic height + vertex-colour field (numpy only).

Pure function of s3_shore_footprint.json + PARAMS below, so the mesh can be
regenerated when live numbers arrive (edit the footprint JSON, re-run
s3_shore_blender_build.py).  Runs under plain Python (offline tests) and inside
Blender (the build script imports it).

Frame: S3 Hangar Root LOCAL cm, LANDED pose.  h = height above floor top
(local z 115).  Mesh z = FLOOR_TOP + h.

Vertex colour channels (linear 0..1), matching the proposed
M_S3_ShoreGround master (see Docs/Conductor/S3_SHORE_GROUND_PREP_2026-10-07.md):
  R = mud (0 = wet/dry sand, 1 = dark mud)
  G = wetness (0 dry, 1 soaked: darker albedo, low roughness)
  B = moss (on mud only)
  A = 1.0 reserved (free for Gary's hand paint, e.g. a 4th layer)
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FOOTPRINT = os.path.join(HERE, "s3_shore_footprint.json")

PARAMS = {
    "seed": 3307,
    "grid_cm": 7.5,
    # Mesh extent (local cm).  Y deliberately ASYMMETRIC (-1012 / +1008) so a
    # bounds read-back after import distinguishes a Y mirror.  Edges run 8-12 cm
    # into the side walls (behind the 1 cm marble liners) and 12 cm into the far
    # wall, so no seam shows.
    "x_range": [0.0, 6012.0],
    "y_range": [-1012.0, 1008.0],
    "skirt_bottom_local_z": 95.0,       # deck underside; hides the mesh edge at the mouth / door
    # Zones (x, local cm).  "Behind" the waves read as toward the mouth (x small).
    "mud_to_sand_x": [1500.0, 2900.0],  # smoothstep: mud at x<1500, sand by 2900
    "wet_sand_from_x": [3300.0, 3900.0],
    "global_rise_cm": 5.0,              # mud plateau sits ~5 cm above the wet flats
    "global_rise_x": [2200.0, 3600.0],
    "undulation_cm": 3.5, "undulation_scale_cm": 420.0,
    "mud_lumps_cm": 2.5, "mud_lumps_scale_cm": 90.0,
    "ripple_amp_cm": 1.2, "ripple_wavelength_cm": 42.0, "ripple_meander_cm": 60.0,
    # Drifts (sand banking up the marble side and back walls).
    "drift_side_cm": [55.0, 140.0],     # min..max along the wall (noise)
    "drift_side_mud_cm": [25.0, 70.0],  # smaller banks in the mud zone
    "drift_back_cm": [60.0, 130.0],
    "drift_cap_cm": 140.0,              # hand prints start 160 cm above floor
    "drift_lambda_factor": 1.15,        # e-fold distance = factor * local drift height
    "drift_front_taper_x": [150.0, 700.0],
    "door_gap_y": [180.0, 380.0],       # back drift 0 for |y|<180, full by 380
    "wave_notch_halfwidth_cm": 45.0, "wave_notch_blend_cm": 90.0,
    # Pools / runnels: (x, y, rx, ry, depth_cm, rot_deg)
    "pools": [
        [520.0, -420.0, 160.0, 110.0, 9.0, 20.0],
        [980.0, 380.0, 210.0, 120.0, 11.0, -15.0],
        [1450.0, -120.0, 140.0, 95.0, 7.0, 40.0],
        [1850.0, 560.0, 120.0, 80.0, 6.0, 0.0],
        [1250.0, -720.0, 110.0, 70.0, 6.0, 70.0],
        [4080.0, -300.0, 90.0, 420.0, 6.0, 4.0],
        [4120.0, 520.0, 70.0, 260.0, 5.0, -6.0],
        [4880.0, 120.0, 85.0, 520.0, 7.0, 3.0],
        [5650.0, -260.0, 90.0, 450.0, 6.0, -5.0],
    ],
    # Moss hummocks in the mud zone: (x, y, r, height_cm)
    "hummocks": [
        [300.0, 640.0, 60.0, 7.0], [420.0, -760.0, 45.0, 5.0], [760.0, 120.0, 38.0, 4.0],
        [1120.0, -360.0, 55.0, 6.0], [1580.0, 820.0, 50.0, 6.0], [1720.0, -560.0, 40.0, 4.0],
        [640.0, -180.0, 30.0, 3.0], [1980.0, -840.0, 48.0, 5.0], [220.0, 120.0, 35.0, 3.5],
    ],
    "cast_blend_metric": [0.85, 1.20],  # v2 shape metric: exact v2 inside 0.85, new terrain past 1.20
    "pad_blend_cm": 40.0,
    "camera_min_vertical_clearance_cm": 80.0,
}

DOCK_FROM_LOCAL = np.array([500.0, 0.0, -120.0])


def load_footprint(path=FOOTPRINT):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class ValueNoise:
    """Deterministic 2-D value noise (quintic-interpolated lattice)."""

    def __init__(self, seed, size=257):
        rng = np.random.default_rng(seed)
        self.size = size
        self.table = rng.uniform(-1.0, 1.0, size=(size, size))

    def __call__(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        x0 = np.floor(x).astype(np.int64)
        y0 = np.floor(y).astype(np.int64)
        fx, fy = x - x0, y - y0
        ux = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
        uy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
        s = self.size
        a = self.table[x0 % s, y0 % s]
        b = self.table[(x0 + 1) % s, y0 % s]
        c = self.table[x0 % s, (y0 + 1) % s]
        d = self.table[(x0 + 1) % s, (y0 + 1) % s]
        return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy

    def fbm(self, x, y, scale, octaves=4, offset=0.0):
        total = np.zeros(np.broadcast(np.asarray(x), np.asarray(y)).shape)
        amp, freq, norm = 1.0, 1.0 / scale, 0.0
        for octave in range(octaves):
            total = total + amp * self(np.asarray(x) * freq + offset + 17.3 * octave,
                                       np.asarray(y) * freq - offset + 41.9 * octave)
            norm += amp
            amp *= 0.5
            freq *= 2.0
        return total / norm


# --- beach v2 sand, copied verbatim from Saved/CodexConductor/s3_beach_v2.py:43-55,168-182
V2_CENTER_X, V2_RX, V2_RY, V2_BASE_Z, V2_MAX_Z = 3550.0, 500.0, 700.0, -5.0, 20.0


def v2_metric(xd, yd):
    nx = (xd - V2_CENTER_X) / V2_RX
    ny = yd / V2_RY
    wobble = 0.055 * np.sin(yd / 115.0) + 0.035 * np.sin((xd + yd) / 170.0)
    return np.sqrt(nx * nx + ny * ny) + wobble


def v2_sand_dock_z(xd, yd):
    metric = v2_metric(xd, yd)
    feather = np.clip((1.0 - metric) / 0.20, 0.0, 1.0)
    noise = (3.2 * np.sin(xd / 93.0) * np.cos(yd / 127.0) + 1.7 * np.sin((xd + 2.0 * yd) / 61.0))
    z = np.minimum(V2_MAX_Z, V2_BASE_Z + feather * (14.0 + noise))
    return np.where(metric >= 1.0, V2_BASE_Z, z)


def v2_h(x, y):
    """v2 sand height above floor top at LOCAL x,y (floor top = dock z -5)."""
    return v2_sand_dock_z(np.asarray(x) + 500.0, np.asarray(y)) - V2_BASE_Z


def pads(fp, p=PARAMS):
    """Every object that stands on the ground: (label, x, y, r, pad_h, kind)."""
    rows = []
    for f in fp["figures"]["rows"]:
        x, y = f["dock_xy"][0] - 500.0, f["dock_xy"][1]
        rows.append((f["label"], x, y, fp["figures"]["pad_radius_cm"], f["foot_dock_z"] + 5.0, "figure"))
    ped = fp["pedestal"]
    x, y = ped["dock_xy"][0] - 500.0, ped["dock_xy"][1]
    rows.append((ped["label"], x, y, ped["pad_radius_cm"], float(v2_h(x, y)), "pedestal"))
    for r in fp["props"]["rows"]:
        x, y = r["dock_xy"][0] - 500.0, r["dock_xy"][1]
        rows.append((r["label"], x, y, r["r"], float(v2_h(x, y)), "prop"))
    return rows


def _ellipse_bump(x, y, cx, cy, rx, ry, rot_deg):
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    dx, dy = x - cx, y - cy
    u = (dx * c + dy * s) / rx
    v = (-dx * s + dy * c) / ry
    r2 = u * u + v * v
    return np.clip(1.0 - r2, 0.0, 1.0) ** 2   # smooth bowl, 0 at the rim


def smax(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return a * (1 - h) + b * h + k * h * (1 - h)


def field(x, y, fp=None, p=PARAMS):
    """Return dict of arrays: h (cm above floor top), r,g,b,a, plus debug masks."""
    if fp is None:
        fp = load_footprint()
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    nz = ValueNoise(p["seed"])
    nz2 = ValueNoise(p["seed"] + 1)
    nz3 = ValueNoise(p["seed"] + 2)

    # zones
    jitter = 260.0 * nz.fbm(x, y, 700.0, 3, 5.0)
    sand_f = smoothstep(p["mud_to_sand_x"][0], p["mud_to_sand_x"][1], x + jitter)
    wet_zone = smoothstep(p["wet_sand_from_x"][0], p["wet_sand_from_x"][1], x + 0.6 * jitter)

    # base terrain
    rise = p["global_rise_cm"] * (1.0 - smoothstep(p["global_rise_x"][0], p["global_rise_x"][1], x))
    und = p["undulation_cm"] * nz.fbm(x, y, p["undulation_scale_cm"], 4)
    lumps = p["mud_lumps_cm"] * (1.0 - sand_f) * nz2.fbm(x, y, p["mud_lumps_scale_cm"], 3)
    meander = p["ripple_meander_cm"] * nz3.fbm(x, y, 300.0, 2)
    ripple_phase = 2.0 * math.pi * (x + meander) / p["ripple_wavelength_cm"]
    ripple = p["ripple_amp_cm"] * sand_f * (0.55 + 0.45 * wet_zone) * np.sin(ripple_phase) \
        * (0.6 + 0.4 * nz2.fbm(x, y, 150.0, 2))
    hum = np.zeros_like(x)
    for hx, hy, hr, hh in p["hummocks"]:
        d = np.hypot(x - hx, y - hy) / hr
        hum = hum + hh * np.clip(1.0 - d * d, 0.0, 1.0) ** 1.5 * (1.0 - sand_f)
    pool = np.zeros_like(x)
    for cx, cy, rx, ry, depth, rot in p["pools"]:
        pool = np.maximum(pool, depth * _ellipse_bump(x, y, cx, cy, rx, ry, rot))
    terrain = rise + und + lumps + ripple + hum - pool

    # drifts against the side walls and the back wall
    def along_noise(t, seed_off, scale):
        return 0.5 + 0.5 * nz.fbm(t, np.full_like(t, seed_off), scale, 3)

    side_lo = p["drift_side_mud_cm"][0] * (1 - sand_f) + p["drift_side_cm"][0] * sand_f
    side_hi = p["drift_side_mud_cm"][1] * (1 - sand_f) + p["drift_side_cm"][1] * sand_f
    front_taper = smoothstep(p["drift_front_taper_x"][0], p["drift_front_taper_x"][1], x)
    hL = (side_lo + (side_hi - side_lo) * along_noise(x, 11.0, 900.0)) * front_taper
    hR = (side_lo + (side_hi - side_lo) * along_noise(x, 71.0, 900.0)) * front_taper
    ay = np.abs(y)
    door = smoothstep(p["door_gap_y"][0], p["door_gap_y"][1], ay)
    hB = (p["drift_back_cm"][0] + (p["drift_back_cm"][1] - p["drift_back_cm"][0])
          * along_noise(y, 37.0, 700.0)) * door
    cap = p["drift_cap_cm"]
    hL, hR, hB = np.minimum(hL, cap), np.minimum(hR, cap), np.minimum(hB, cap)
    dL = np.maximum(y - fp["walls"]["left_inner_face_y"]["value"], 0.0)
    dR = np.maximum(fp["walls"]["right_inner_face_y"]["value"] - y, 0.0)
    dB = np.maximum(fp["walls"]["backdrop_plane_x"]["value"] - x, 0.0)
    lam = p["drift_lambda_factor"]
    # wind-scalloped crest: modulate the e-fold distance a little
    scal = 1.0 + 0.25 * nz3.fbm(x, y, 250.0, 2)
    dL_ = hL * np.exp(-dL / np.maximum(lam * hL * scal, 1.0))
    dR_ = hR * np.exp(-dR / np.maximum(lam * hR * scal, 1.0))
    dB_ = hB * np.exp(-dB / np.maximum(lam * hB * scal, 1.0))
    drift = np.maximum(np.maximum(dL_, dR_), dB_)
    h = terrain + drift   # sand piled on top of the ground (a max() would fill the pools)

    # cast island: reproduce beach v2 exactly where things are seated on it
    xd = x + 500.0
    metric = v2_metric(xd, y)
    w_cast = 1.0 - smoothstep(p["cast_blend_metric"][0], p["cast_blend_metric"][1], metric)
    h = w_cast * v2_h(x, y) + (1.0 - w_cast) * h

    # wave-row notches: surface exactly at floor top under each flat (all Y; flats slide)
    notch_w = np.zeros_like(x)
    for row in fp["wave_rows"]["rows"]:
        cx = 0.5 * (row["x"][0] + row["x"][1])
        half = max(p["wave_notch_halfwidth_cm"], 0.5 * (row["x"][1] - row["x"][0]) + 10.0)
        d = np.abs(x - cx)
        notch_w = np.maximum(notch_w, 1.0 - smoothstep(half, half + p["wave_notch_blend_cm"], d))
    h = (1.0 - notch_w) * h

    # pads.  Figures + pedestal: FLAT at the seated height.  Props (rocks,
    # seaweed): follow the beach-v2 surface they were embedded into, so their
    # embed fractions are unchanged even where pads overlap.
    pad_w_total = np.zeros_like(x)
    v2_here = v2_h(x, y)
    for label, px, py, pr, ph, kind in pads(fp, p):
        d = np.hypot(x - px, y - py)
        w = 1.0 - smoothstep(pr, pr + p["pad_blend_cm"], d)
        target = v2_here if kind == "prop" else ph
        h = (1.0 - w) * h + w * target
        pad_w_total = np.maximum(pad_w_total, w)

    # ---- vertex colours ----
    drift_mask = smoothstep(12.0, 40.0, drift - terrain)
    mud = (1.0 - sand_f) * (1.0 - drift_mask) * (1.0 - w_cast)
    mud = np.clip(mud + 0.15 * nz2.fbm(x, y, 120.0, 2) * (1.0 - sand_f), 0.0, 1.0)
    pool_mask = smoothstep(0.5, 4.0, pool) * (1.0 - pad_w_total)
    wet = np.maximum(0.85 * wet_zone, 0.35 * (1.0 - sand_f))
    wet = np.maximum(wet, pool_mask)
    wet = np.maximum(wet, 0.9 * notch_w)
    wet = wet * (1.0 - smoothstep(8.0, 35.0, h))           # drift tops dry
    wet = np.clip(wet + 0.08 * nz3.fbm(x, y, 90.0, 2), 0.0, 1.0)
    moss_noise = smoothstep(-0.05, 0.35, nz3.fbm(x, y, 160.0, 3))
    hum_mask = smoothstep(0.5, 3.0, hum)
    wall_base = np.maximum(smoothstep(120.0, 0.0, dL), smoothstep(120.0, 0.0, dR)) * (1 - sand_f)
    moss = mud * np.clip(0.75 * moss_noise + hum_mask + 0.5 * wall_base, 0.0, 1.0) * (1.0 - 0.7 * pool_mask)
    moss = np.clip(moss, 0.0, 1.0)
    alpha = np.ones_like(x)
    return {"h": h, "r": mud, "g": wet, "b": moss, "a": alpha,
            "notch_w": notch_w, "pad_w": pad_w_total, "w_cast": w_cast, "drift": drift}


def grid_axes(p=PARAMS):
    gx = p["grid_cm"]
    nx = int(round((p["x_range"][1] - p["x_range"][0]) / gx)) + 1
    ny = int(round((p["y_range"][1] - p["y_range"][0]) / gx)) + 1
    xs = np.linspace(p["x_range"][0], p["x_range"][1], nx)
    ys = np.linspace(p["y_range"][0], p["y_range"][1], ny)
    return xs, ys


def build_grid(fp=None, p=PARAMS):
    if fp is None:
        fp = load_footprint()
    xs, ys = grid_axes(p)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    out = field(X, Y, fp, p)
    out["X"], out["Y"], out["xs"], out["ys"] = X, Y, xs, ys
    return out


def checks(fp=None, p=PARAMS, grid=None):
    """Assertions the mesh must satisfy.  Returns (failures, report)."""
    if fp is None:
        fp = load_footprint()
    failures, report = [], {}
    # pads
    pad_rows = []
    for label, px, py, pr, ph, kind in pads(fp, p):
        ring = [(px + rr * math.cos(t), py + rr * math.sin(t))
                for rr in (0.0, 0.5 * max(pr, 30.0), max(pr, 30.0)) for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
        qx = np.array([q[0] for q in ring]); qy = np.array([q[1] for q in ring])
        hs = field(qx, qy, fp, p)["h"]
        target = v2_h(qx, qy) if kind == "prop" else ph
        dev = float(np.max(np.abs(hs - target)))
        pad_rows.append({"label": label, "kind": kind, "local_xy": [round(px, 2), round(py, 2)],
                         "pad_h_cm": round(ph, 3), "pad_local_z": round(115.0 + ph, 3),
                         "max_dev_in_pad_cm": round(dev, 4)})
        if dev > 0.25:
            failures.append(f"PAD_NOT_FLAT {label} dev={dev:.3f}")
    report["pads"] = pad_rows
    ped = fp["pedestal"]
    ph = [r for r in pad_rows if r["kind"] == "pedestal"][0]["pad_h_cm"]
    report["pedestal_embed_cm"] = round(ph - (ped["base_dock_z"] + 5.0), 3)
    # cameras
    cam_rows = []
    for cam in fp["cameras"]["rows"]:
        cx, cy, cz = cam["local"]
        xs = np.linspace(cx - 150, cx + 150, 31)
        ys = np.linspace(cy - 150, cy + 150, 31)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        H = field(X, Y, fp, p)["h"]
        Z = 115.0 + H
        d3 = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2)
        vclear = cz - (115.0 + float(field(np.array([cx]), np.array([cy]), fp, p)["h"][0]))
        cam_rows.append({"label": cam["label"], "vertical_clearance_cm": round(vclear, 2),
                         "min_3d_distance_within_150cm_cm": round(float(d3.min()), 2)})
        if vclear < p["camera_min_vertical_clearance_cm"]:
            failures.append(f"CAMERA_LOW {cam['label']} {vclear:.1f}")
    report["cameras"] = cam_rows
    # wave notches
    wave_rows = []
    for row in fp["wave_rows"]["rows"]:
        xs = np.linspace(row["x"][0], row["x"][1], 9)
        ys = np.linspace(-1000, 1000, 201)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        H = field(X, Y, fp, p)["h"]
        wave_rows.append({"row": row["name"], "max_abs_h_under_flat_cm": round(float(np.abs(H).max()), 4)})
        if float(np.abs(H).max()) > 0.05:
            failures.append(f"WAVE_BASE_NOT_FLUSH {row['name']} {float(np.abs(H).max()):.3f}")
    report["wave_rows"] = wave_rows
    # walls: drift height at the inner faces vs prints
    xs = np.linspace(0, 6000, 1201)
    hL = field(xs, np.full_like(xs, -999.0), fp, p)["h"]
    hR = field(xs, np.full_like(xs, 999.0), fp, p)["h"]
    ys = np.linspace(-999, 999, 401)
    hB = field(np.full_like(ys, 5997.0), ys, fp, p)["h"]
    limit = fp["handprint_lowest_extent_above_floor_cm"]["value"]
    report["walls"] = {"left_max_cm": round(float(hL.max()), 2), "left_mean_cm": round(float(hL.mean()), 2),
                       "right_max_cm": round(float(hR.max()), 2), "right_mean_cm": round(float(hR.mean()), 2),
                       "back_max_cm": round(float(hB.max()), 2),
                       "back_at_door_max_cm": round(float(hB[np.abs(ys) < 150].max()), 2),
                       "handprint_floor_cm": limit}
    for name, arr in (("left", hL), ("right", hR), ("back", hB)):
        if float(arr.max()) > limit - 10.0:
            failures.append(f"DRIFT_HITS_PRINTS {name} {float(arr.max()):.1f}")
    if float(hB[np.abs(ys) < 150].max()) > 15.0:
        failures.append("DOOR_GAP_BLOCKED")
    # mouth edge
    ys2 = np.linspace(-1000, 1000, 201)
    h0 = field(np.zeros_like(ys2), ys2, fp, p)["h"]
    report["mouth_edge_h_range_cm"] = [round(float(h0.min()), 2), round(float(h0.max()), 2)]
    if grid is not None:
        H = grid["h"]
        report["grid"] = {"nx": int(H.shape[0]), "ny": int(H.shape[1]), "verts": int(H.size),
                          "h_min_cm": round(float(H.min()), 2), "h_max_cm": round(float(H.max()), 2),
                          "r_mean": round(float(grid["r"].mean()), 3), "g_mean": round(float(grid["g"].mean()), 3),
                          "b_mean": round(float(grid["b"].mean()), 3)}
        if float(H.min()) < -(115.0 - p["skirt_bottom_local_z"]):
            failures.append("DIP_BELOW_DECK_UNDERSIDE")
    return failures, report


if __name__ == "__main__":
    fp = load_footprint()
    g = build_grid(fp)
    f, r = checks(fp, PARAMS, g)
    print(json.dumps(r, indent=1))
    print("FAILURES", f)
