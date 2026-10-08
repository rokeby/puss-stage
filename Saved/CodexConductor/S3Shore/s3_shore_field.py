"""S3 shore ground: deterministic height + vertex-colour field (numpy only).

Pure function of s3_shore_footprint.json + PARAMS below, so the mesh can be
regenerated when live numbers arrive (edit the footprint JSON, re-run
s3_shore_blender_build.py).  Runs under plain Python (offline tests) and inside
Blender (the build script imports it).

Frame: S3 Hangar Root LOCAL cm, LANDED pose.  h = height above floor top
(local z 115).  Mesh z = FLOOR_TOP + h.

v2 (7 Oct evening, Gary: "naturalistic, wild beach ... sand piling into uneven
dunes towards the edges of the box ... claustrophobia"): the smooth exponential
wall banks are gone.  The sand is now SIMULATED, deterministically, on a 15 cm
grid:

  1. supply   : loose sand heaped against the side and back walls, uneven along
                each wall (fbm), with lobes reaching toward the centre and the
                corners deepest (one seeded numpy Generator, ONE draw per
                statement -- memory puss-random-draw-order).
  2. wind     : deterministic stoss-scour transport (no random numbers).
                Wind from the wave rows toward the mouth, a little toward the
                left wall (wind_to_deg 196).  Wherever the surface rises
                DOWNWIND more steeply than ~13 deg, the excess is lifted off the
                higher cell and carried one cell further downwind, over the
                crest.  Stoss slopes relax to ~13 deg; the dunes creep downwind.
  3. talus    : angle-of-repose relaxation (31 +- 2 deg, jittered so slip faces
                scallop) after every wind step: lee sides become slip faces
                with sharp crests and spill fans.
  4. fine pass: upsample to the 7.5 cm mesh grid, add asymmetric wind ripples
                (5-9 cm crest-to-trough, crests across the wind, fading on slip
                faces, in wet sand and in thin sand), clamp to the hard
                constraints, final 33 deg talus, clamp again.

Hard constraints (an upper bound U on the surface, itself never steeper than
31 deg, so min() keeps the repose limit): wave notches flush, door corridor
open from row 3 to the door, keep-clear cones under the listed S3 cameras.

Vertex colour channels (linear 0..1), matching the proposed
M_S3_ShoreGround master (see Docs/Conductor/S3_SHORE_GROUND_PREP_2026-10-07.md):
  R = mud (0 = wet/dry sand, 1 = dark mud)
  G = wetness (0 dry, 1 soaked: darker albedo, low roughness; > 0.85 = puddle)
  B = moss (on mud only)
  A = 1.0 reserved (free for Gary's hand paint, e.g. a 4th layer)
"""
import copy
import hashlib
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FOOTPRINT = os.path.join(HERE, "s3_shore_footprint.json")
HEIGHT_SETS_JSON = os.path.join(HERE, "s3_shore_height_sets.json")

PARAMS = {
    "seed": 3307,
    "grid_cm": 7.5,
    # Mesh extent (local cm).  Y deliberately ASYMMETRIC (-1012 / +1008) so a
    # bounds read-back after import distinguishes a Y mirror.
    "x_range": [0.0, 6012.0],
    "y_range": [-1012.0, 1008.0],
    "skirt_bottom_local_z": 95.0,       # deck underside; hides the mesh edge at the mouth / door
    # Zones (x, local cm).  Mud toward the mouth (x small), sand toward the waves.
    "mud_to_sand_x": [1500.0, 2900.0],
    "wet_sand_from_x": [3300.0, 3900.0],
    "global_rise_cm": 5.0,
    "global_rise_x": [2200.0, 3600.0],
    "undulation_cm": 3.5, "undulation_scale_cm": 420.0,
    "mud_lumps_cm": 2.5, "mud_lumps_scale_cm": 90.0,
    # water ripples on the wet flats (bed, not wind)
    "ripple_amp_cm": 1.2, "ripple_wavelength_cm": 42.0, "ripple_meander_cm": 60.0,
    "wave_notch": True,
    "wave_notch_halfwidth_cm": 45.0, "wave_notch_blend_cm": 90.0,
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
    "hummocks": [
        [300.0, 640.0, 60.0, 7.0], [420.0, -760.0, 45.0, 5.0], [760.0, 120.0, 38.0, 4.0],
        [1120.0, -360.0, 55.0, 6.0], [1580.0, 820.0, 50.0, 6.0], [1720.0, -560.0, 40.0, 4.0],
        [640.0, -180.0, 30.0, 3.0], [1980.0, -840.0, 48.0, 5.0], [220.0, 120.0, 35.0, 3.5],
    ],
    # Gary 7 Oct: cast area is the same field as everywhere else (no beach-v2 preservation, no pads).
    "preserve_v2_cast": False,
    "use_pads": False,
    "cast_blend_metric": [0.85, 1.20],
    "pad_blend_cm": 40.0,
    "camera_min_vertical_clearance_cm": 80.0,

    # ---------------- dunes (v2) ----------------
    "height_set": "B",
    # Supply per set.  target = intended max dune height AT the wall faces; the MEASURED value is what
    # s3_shore_height_sets.json reports.  print_line = the proposed lowest hand-print extent for that set
    # (measured wall max + print_clearance_cm, rounded up to 5 cm); the build gate checks it.
    "height_sets": {
        "A": {"target_wall_max_cm": 180.0, "supply_cm": 194.0, "print_line_cm": 215.0},
        "B": {"target_wall_max_cm": 240.0, "supply_cm": 265.0, "print_line_cm": 265.0},
        "C": {"target_wall_max_cm": 300.0, "supply_cm": 350.0, "print_line_cm": 330.0},
        # Gary 7 Oct, queued for later: about twice B, but keep a 4 m centre lane and the clam/millstone clear.
        # D owns only its overrides; A/B/C remain byte-for-byte reproducible from the 7 Oct field.
        "D": {"target_wall_max_cm": 480.0, "supply_cm": 4000.0, "print_line_cm": 500.0,
              "dune_overrides": {"dune_reach_cm": [550.0, 700.0], "tongue_prob": 0.0,
                                 "steps": 110, "windward_deg": 11.0, "scour_k": 0.55},
              "constraints_overrides": {"centre_lane_halfwidth_cm": 200.0, "centre_lane_h_cm": 30.0,
                                         "millstone_clear_radius_cm": 110.0, "millstone_clear_h_cm": 12.0},
              "gates": {"centre_lane_max_cm": 30.05, "dune_inward_reach_cm": [600.0, 850.0],
                        # The doubled, centre-clipped heaps retain a lee bias, but the hard lane cone raises the
                        # windward median.  Keep an explicit D-only gate; A/B/C retain the 4 deg / 0.60 gate below.
                        "wind_asymmetry_min_delta_deg": 2.5, "steep_lee_share_min": 0.60},
              "seat_after_triangle_clamp": True},
    },
    "print_clearance_cm": 20.0,
    "dune": {
        "sim_grid_cm": 15.0,
        "bank_frac": 0.12, "bank_width_cm": 200.0, "bank_gap": [0.45, 0.7],   # broken low bank, saddles show the wall base
        "dune_height_frac": [0.3, 1.0], "dune_reach_cm": [220.0, 480.0], "dune_halflength_cm": [170.0, 380.0],
        "dune_spacing_cm": [480.0, 900.0], "tongue_prob": 0.3, "tongue_extra_cm": [250.0, 480.0],
        "crest_standoff_cm": 140.0,
        "pile_exponent": 0.9, "along_scale_cm": 650.0,
        "corner_boost": 0.45, "corner_radius_cm": 520.0,
        "notch_keep": 0.25, "notch_taper_cm": 260.0, "door_taper_cm": 220.0,
        "mud_zone_supply_frac": 0.8,          # supply in the mud zone vs the sand zone
        "front_taper_x": [120.0, 900.0],
        "sheet_cm": 2.0,                      # thin loose sand sheet over the beach
        # wind (deterministic, no random numbers).  wind_to_deg: direction the wind blows TOWARD in the
        # root-local XY plane (0 = +x toward the waves, 180 = -x toward the mouth, 90 = +y toward the right wall).
        "wind_to_deg": 196.0, "windward_deg": 13.0, "shadow_deg": 15.0, "scour_k": 0.5,
        "steps": 90,
        "repose_jitter_deg": 1.5,
        "camera_blowout_radius_cm": 230.0,
        "repose_deg": 30.5, "talus_passes_per_step": 4, "final_coarse_talus_passes": 160,
    },
    "constraints": {
        "notch_flush_margin_cm": 10.0,        # flush strip beyond each flat's x extent
        "notch_repose_deg": 31.0,
        "door_corridor_halfwidth_cm": 180.0, "door_corridor_h_cm": 2.0,
        "camera_keep_clear_cm": 95.0, "camera_keep_radius_cm": 60.0, "camera_cone_deg": 31.0,
    },
    "wind_ripple": {
        "height_cm": [5.0, 9.0],              # crest-to-trough
        "mode": "natural",
        "wavelength_cm": 62.0,                # regular mode only
        "wavelength_range_cm": [36.0, 80.0], "wavelength_noise_cm": 520.0, "lee_shorten": 0.3,
        "bend_cycles_per_m": 1.2, "phase_noise_cycles": 1.6, "phase_noise_scale_cm": 160.0,
        "patch_gap": [0.32, 0.5], "ripple_lee_max_deg": 28.0,
        "lee_frac": 0.35, "meander_cm": 45.0,
        "fade_slope_deg": [8.0, 16.0],        # only on gentle sand: gone on heap flanks and slip faces
        "min_sand_cm": 6.0,                   # thin sand carries only beach ripples
        "beach_frac": 0.5,                    # ripple height on the dry beach sheet vs on the heaps
    },
    "fine": {"sand_blur_cells": 3, "sand_blur_passes": 2, "talus_k": 0.1, "ripples_before_talus": False,
             "post_ripple_talus_passes": 40},
    "sheet": {"beach_cm": 5.0, "heap_feed_cm": 6.0, "thin_per_m_cm": 0.22, "streak_len_cm": 1400.0,
              "streak_wid_cm": 110.0, "patch_lo": 0.62, "patch_hi": 0.78, "patch_scale_cm": 380.0,
              "mouth_strip_x": [120.0, 650.0], "min_cm": 0.6},
    "final_repose_deg": 32.0, "final_talus_passes": 160,  # pairwise 32 deg -> any triangle <= ~34.1 deg
    "slip_face_max_deg": 35.0,
    "checks": {"pits_on_dunes_max_m2": 0.25, "ripple_peak_share_max": 0.5, "ripple_rms_min_cm": 0.45, "terracing_rms_max_deg": 3.4},
    "millstone_seat": True,                   # footprint['millstone_seat']: level disc for the GraniteMillstone
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


def active_set(p=PARAMS):
    return p["height_sets"][p["height_set"]]


def dune_params(p=PARAMS):
    """Dune parameters with only the active height-set overrides applied."""
    out = copy.deepcopy(p["dune"])
    out.update(active_set(p).get("dune_overrides", {}))
    return out


def constraint_params(p=PARAMS):
    """Constraint parameters with only the active height-set overrides applied."""
    out = copy.deepcopy(p["constraints"])
    out.update(active_set(p).get("constraints_overrides", {}))
    return out


# ----------------------------------------------------------------------------- bed (the old ground, no drifts)
def zones(x, y, p, nz):
    jitter = 260.0 * nz.fbm(x, y, 700.0, 3, 5.0)
    sand_f = smoothstep(p["mud_to_sand_x"][0], p["mud_to_sand_x"][1], x + jitter)
    wet_zone = smoothstep(p["wet_sand_from_x"][0], p["wet_sand_from_x"][1], x + 0.6 * jitter)
    return sand_f, wet_zone


def notch_weight(x, fp, p):
    notch_w = np.zeros_like(x)
    for row in (fp["wave_rows"]["rows"] if p.get("wave_notch", True) else []):
        cx = 0.5 * (row["x"][0] + row["x"][1])
        half = notch_half(row, p)
        d = np.abs(x - cx)
        notch_w = np.maximum(notch_w, 1.0 - smoothstep(half, half + p["wave_notch_blend_cm"], d))
    return notch_w


def notch_half(row, p):
    return max(p["wave_notch_halfwidth_cm"],
               0.5 * (row["x"][1] - row["x"][0]) + p["constraints"]["notch_flush_margin_cm"])


def bed(x, y, fp, p):
    """The ground under the loose sand: plateau, undulation, mud lumps, water ripples, hummocks, pools."""
    nz = ValueNoise(p["seed"])
    nz2 = ValueNoise(p["seed"] + 1)
    nz3 = ValueNoise(p["seed"] + 2)
    sand_f, wet_zone = zones(x, y, p, nz)
    rise = p["global_rise_cm"] * (1.0 - smoothstep(p["global_rise_x"][0], p["global_rise_x"][1], x))
    und = p["undulation_cm"] * nz.fbm(x, y, p["undulation_scale_cm"], 4)
    lumps = p["mud_lumps_cm"] * (1.0 - sand_f) * nz2.fbm(x, y, p["mud_lumps_scale_cm"], 3)
    meander = p["ripple_meander_cm"] * nz3.fbm(x, y, 300.0, 2)
    ripple_phase = 2.0 * math.pi * (x + meander) / p["ripple_wavelength_cm"]
    ripple = p["ripple_amp_cm"] * sand_f * wet_zone * np.sin(ripple_phase) * (0.6 + 0.4 * nz2.fbm(x, y, 150.0, 2))
    hum = np.zeros_like(x)
    for hx, hy, hr, hh in p["hummocks"]:
        d = np.hypot(x - hx, y - hy) / hr
        hum = hum + hh * np.clip(1.0 - d * d, 0.0, 1.0) ** 1.5 * (1.0 - sand_f)
    pool = np.zeros_like(x)
    for cx, cy, rx, ry, depth, rot in p["pools"]:
        pool = np.maximum(pool, depth * _ellipse_bump(x, y, cx, cy, rx, ry, rot))
    b = rise + und + lumps + ripple + hum - pool
    notch_w = notch_weight(x, fp, p)
    b = (1.0 - notch_w) * b
    return {"bed": b, "sand_f": sand_f, "wet_zone": wet_zone, "hum": hum, "pool": pool, "notch_w": notch_w}


# ----------------------------------------------------------------------------- constraints
def upper_bound(x, y, fp, p):
    """Surface ceiling U (cm above floor top).  Every term is a distance cone with slope <= 31 deg."""
    c = constraint_params(p)
    big = 1.0e6
    U = np.full(np.shape(x), big)
    t = math.tan(math.radians(c["notch_repose_deg"]))
    for row in (fp["wave_rows"]["rows"] if p.get("wave_notch", True) else []):
        cx = 0.5 * (row["x"][0] + row["x"][1])
        U = np.minimum(U, np.maximum(np.abs(x - cx) - notch_half(row, p), 0.0) * t)
    # door corridor: from the row-3 notch edge to the far wall, |y| <= halfwidth (door is |y| < 150)
    rows = fp["wave_rows"]["rows"]
    x0 = max(0.5 * (r["x"][0] + r["x"][1]) + notch_half(r, p) for r in rows) if rows else 5400.0
    hw = c["door_corridor_halfwidth_cm"]
    dx = np.maximum(x0 - x, 0.0)
    dy = np.maximum(np.abs(y) - hw, 0.0)
    U = np.minimum(U, c["door_corridor_h_cm"] + np.hypot(dx, dy) * t)
    # cameras: keep-clear cone under each listed S3 camera
    tc = math.tan(math.radians(c["camera_cone_deg"]))
    for cam in fp["cameras"]["rows"]:
        cx, cy, cz = cam["local"]
        top = cz - 115.0 - c["camera_keep_clear_cm"]
        r = np.maximum(np.hypot(x - cx, y - cy) - c["camera_keep_radius_cm"], 0.0)
        U = np.minimum(U, top + r * tc)
    # Set D only: a low central aisle remains between the two 6-8 m side heaps.  The cone itself is no steeper
    # than repose, so min(surface, U) cannot introduce an impossible retaining edge.
    if "centre_lane_halfwidth_cm" in c:
        lane = c["centre_lane_h_cm"] + np.maximum(np.abs(y) - c["centre_lane_halfwidth_cm"], 0.0) * t
        U = np.minimum(U, lane)
    # The new PearlClam sits on the millstone at this footprint point.  Keep its whole seat low, then allow sand
    # to rise away from it at repose rather than cutting a cylindrical hole.
    if "millstone_clear_radius_cm" in c and "millstone_seat" in fp:
        mx, my = fp["millstone_seat"]["local_xy"]
        radial = np.maximum(np.hypot(x - mx, y - my) - c["millstone_clear_radius_cm"], 0.0)
        U = np.minimum(U, c["millstone_clear_h_cm"] + radial * t)
    return U


# ----------------------------------------------------------------------------- grid helpers
def _axes(p, step):
    nx = int(round((p["x_range"][1] - p["x_range"][0]) / step)) + 1
    ny = int(round((p["y_range"][1] - p["y_range"][0]) / step)) + 1
    return np.linspace(p["x_range"][0], p["x_range"][1], nx), np.linspace(p["y_range"][0], p["y_range"][1], ny)


def grid_axes(p=PARAMS):
    return _axes(p, p["grid_cm"])


def interp2(xs, ys, A, x, y):
    """Bilinear sample of grid A (indexed [ix, iy]) at points x, y (clamped to the grid)."""
    x = np.clip(np.asarray(x, dtype=float), xs[0], xs[-1])
    y = np.clip(np.asarray(y, dtype=float), ys[0], ys[-1])
    i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
    j = np.clip(np.searchsorted(ys, y) - 1, 0, len(ys) - 2)
    tx = (x - xs[i]) / (xs[i + 1] - xs[i])
    ty = (y - ys[j]) / (ys[j + 1] - ys[j])
    return ((A[i, j] * (1 - tx) + A[i + 1, j] * tx) * (1 - ty)
            + (A[i, j + 1] * (1 - tx) + A[i + 1, j + 1] * tx) * ty)


def _nb(a, di, dj):
    """Value of the neighbour (i+di, j+dj), edge-replicated (no flux across the grid border)."""
    pad = np.pad(a, 1, mode="edge")
    return pad[1 + di:1 + di + a.shape[0], 1 + dj:1 + dj + a.shape[1]]


def _send(f, di, dj):
    """Move f[i, j] to (i+di, j+dj); amounts that would leave the grid stay put (they never occur: f=0 there)."""
    out = np.zeros_like(f)
    n, m = f.shape
    si = slice(max(-di, 0), n - max(di, 0))
    sj = slice(max(-dj, 0), m - max(dj, 0))
    ti = slice(max(di, 0), n - max(-di, 0))
    tj = slice(max(dj, 0), m - max(-dj, 0))
    out[ti, tj] = f[si, sj]
    return out


NB8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def talus(h, floor, tan_rep, dx, dy, passes, k=0.12, tol=None, max_passes=4000):
    """Angle-of-repose relaxation.  Only material above `floor` moves.  Deterministic, mass-conserving.
    With tol: keep going (in blocks of `passes`) until no neighbour pair exceeds the angle by more than tol cm."""
    h = h.copy()
    dist = {(a, b): math.hypot(a * dx, b * dy) for a, b in NB8}
    done = 0
    while True:
        h = _talus_passes(h, floor, tan_rep, dist, passes, k)
        done += passes
        if tol is None or done >= max_passes or max_excess(h, tan_rep, dx, dy) <= tol:
            return h


def _talus_passes(h, floor, tan_rep, dist, passes, k):
    for _ in range(passes):
        flows = []
        total = np.zeros_like(h)
        for di, dj in NB8:
            ex = h - _nb(h, di, dj) - tan_rep * dist[(di, dj)]
            f = np.where(ex > 0.0, ex * k, 0.0)
            flows.append(f)
            total += f
        avail = np.maximum(h - floor, 0.0)
        scale = np.where(total > avail, avail / np.maximum(total, 1e-12), 1.0)
        for (di, dj), f in zip(NB8, flows):
            f = f * scale
            h -= f
            h += _send(f, di, dj)
    return h


def relax_triangles(h, floor, tan_max, dx, dy, max_iter=1500, k=0.3):
    """Triangle-aware talus (mass-conserving).  Pairwise talus cannot bound triangle slopes (a twisted quad passes
    every neighbour test yet one triangle reaches sqrt(2) x the limit).  Every quad with a triangle (either
    diagonal split) steeper than atan(tan_max) moves a little sand from its highest corner to its lowest.
    Returns (h, iterations, moved_cm3, steep_quads_left)."""
    h = h.copy()
    moved = 0.0
    offs = ((0, 0), (1, 0), (1, 1), (0, 1))
    n0, n1 = h.shape[0] - 1, h.shape[1] - 1
    for it in range(max_iter):
        a, b, c, d = h[:-1, :-1], h[1:, :-1], h[1:, 1:], h[:-1, 1:]
        g = np.maximum.reduce([np.hypot((b - a) / dx, (c - b) / dy), np.hypot((c - d) / dx, (d - a) / dy),
                               np.hypot((b - a) / dx, (d - a) / dy), np.hypot((c - d) / dx, (c - b) / dy)])
        bad = g > tan_max
        if not bad.any():
            return h, it, moved, 0
        st = np.stack([a, b, c, d])
        top = np.argmax(st, axis=0)
        bot = np.argmin(st, axis=0)
        amt = np.where(bad, np.minimum(k * (g - tan_max) * min(dx, dy) + 0.002, 0.25 * (st.max(0) - st.min(0))), 0.0)
        out = np.zeros_like(h)
        for kk, (oi, oj) in enumerate(offs):
            out[oi:oi + n0, oj:oj + n1] += np.where(top == kk, amt, 0.0)
        avail = np.maximum(h - floor, 0.0)
        sc = np.where(out > avail, avail / np.maximum(out, 1e-12), 1.0)
        # per-quad scale = the scale of its source corner
        sq = np.zeros_like(amt)
        for kk, (oi, oj) in enumerate(offs):
            sq = np.where(top == kk, sc[oi:oi + n0, oj:oj + n1], sq)
        amt = amt * sq
        delta = np.zeros_like(h)
        for kk, (oi, oj) in enumerate(offs):
            delta[oi:oi + n0, oj:oj + n1] -= np.where(top == kk, amt, 0.0)
            delta[oi:oi + n0, oj:oj + n1] += np.where(bot == kk, amt, 0.0)
        h = h + delta
        moved += float(amt.sum()) * dx * dy
    return h, max_iter, moved, int(bad.sum())


def max_excess(h, tan_rep, dx, dy):
    m = 0.0
    for di, dj in NB8:
        ex = h - _nb(h, di, dj) - tan_rep * math.hypot(di * dx, dj * dy)
        m = max(m, float(ex.max()))
    return m


# ----------------------------------------------------------------------------- supply
def supply(X, Y, fp, p, sand_f):
    """Loose sand before the wind: a low continuous bank on every wall plus a CHAIN of dune bodies along each
    wall (random spacing, height, reach), corners heaviest, some reaching far toward the centre.  One seeded
    Generator, ONE draw per statement, in a fixed order (memory puss-random-draw-order)."""
    d = dune_params(p)
    amp = active_set(p)["supply_cm"]
    nzA = ValueNoise(p["seed"] + 11)
    rng = np.random.default_rng(p["seed"] + 101)
    yl = fp["walls"]["left_inner_face_y"]["value"]
    yr = fp["walls"]["right_inner_face_y"]["value"]
    xb = fp["walls"]["backdrop_plane_x"]["value"]
    dL = np.maximum(Y - yl, 0.0)
    dR = np.maximum(yr - Y, 0.0)
    dB = np.maximum(xb - X, 0.0)
    front = smoothstep(d["front_taper_x"][0], d["front_taper_x"][1], X)
    zone = d["mud_zone_supply_frac"] + (1.0 - d["mud_zone_supply_frac"]) * sand_f
    s = np.zeros_like(X)
    # side walls: base bank + dune chain
    for dist, off in ((dL, 3.0), (dR, 29.0)):
        along = 0.5 + 0.5 * nzA.fbm(X, np.full_like(X, off), d["along_scale_cm"], 3)
        bank_w = d["bank_width_cm"] * (0.7 + 0.6 * along)
        # Gary 7 Oct: NOT one continuous bank -- the low bank exists only where the along-wall noise is high,
        # so saddles between heaps show the bare wall base
        gaps = smoothstep(d["bank_gap"][0], d["bank_gap"][1], along)
        s = np.maximum(s, amp * d["bank_frac"] * gaps * np.clip(1.0 - dist / bank_w, 0.0, 1.0) ** 1.5 * front * zone)
        x = d["front_taper_x"][0] + rng.uniform(0.0, 300.0)
        while x < 6150.0:
            hf = rng.uniform(d["dune_height_frac"][0], d["dune_height_frac"][1])
            reach = rng.uniform(d["dune_reach_cm"][0], d["dune_reach_cm"][1])
            half = rng.uniform(d["dune_halflength_cm"][0], d["dune_halflength_cm"][1])
            tongue = rng.uniform(0.0, 1.0)
            if tongue < d["tongue_prob"]:
                reach = reach + rng.uniform(d["tongue_extra_cm"][0], d["tongue_extra_cm"][1])
            standoff = rng.uniform(0.0, d["crest_standoff_cm"])   # crest off the wall: broken, offset crest lines
            shear = rng.uniform(-0.6, 0.6)                          # heap leans along the wall
            u = (X - x - shear * dist) / half
            v = np.maximum(dist - standoff, 0.0) / reach + np.minimum(dist - standoff, 0.0) / (3.0 * reach)
            mound = np.clip(1.0 - u * u - v * v, 0.0, 1.0) ** d["pile_exponent"]
            s = np.maximum(s, amp * hf * mound * front * zone)
            x = x + rng.uniform(d["dune_spacing_cm"][0], d["dune_spacing_cm"][1])
    # back wall: bank + chain along y (the door corridor is kept clear below)
    along_b = 0.5 + 0.5 * nzA.fbm(np.full_like(Y, 53.0), Y, d["along_scale_cm"] * 0.8, 3)
    s = np.maximum(s, amp * d["bank_frac"] * (0.6 + 0.4 * along_b)
                   * np.clip(1.0 - dB / (d["bank_width_cm"] * (0.7 + 0.6 * along_b)), 0.0, 1.0) ** 1.5)
    y = -1000.0 + rng.uniform(0.0, 150.0)
    while y < 1000.0:
        hf = rng.uniform(d["dune_height_frac"][0], d["dune_height_frac"][1])
        reach = rng.uniform(d["dune_reach_cm"][0], d["dune_reach_cm"][1])
        half = rng.uniform(d["dune_halflength_cm"][0], d["dune_halflength_cm"][1])
        u = (Y - y) / half
        v = dB / reach
        s = np.maximum(s, amp * hf * np.clip(1.0 - u * u - v * v, 0.0, 1.0) ** d["pile_exponent"])
        y = y + rng.uniform(d["dune_spacing_cm"][0], d["dune_spacing_cm"][1])
    # corners deepest
    R = d["corner_radius_cm"]
    corner = np.exp(-(np.minimum(dL, dR) ** 2 + dB ** 2) / R ** 2)
    s = s * (1.0 + d["corner_boost"] * corner)
    # keep the hard constraints from biting: taper the supply toward the wave notches and the door corridor
    c = constraint_params(p)
    for row in (fp["wave_rows"]["rows"] if p.get("wave_notch", True) else []):
        cx = 0.5 * (row["x"][0] + row["x"][1])
        hn = notch_half(row, p)
        s = s * (d["notch_keep"] + (1.0 - d["notch_keep"]) * smoothstep(hn, hn + d["notch_taper_cm"], np.abs(X - cx)))
    rows = fp["wave_rows"]["rows"]
    x0 = max(0.5 * (r["x"][0] + r["x"][1]) + notch_half(r, p) for r in rows) if rows else 5400.0
    dcor = np.hypot(np.maximum(x0 - X, 0.0), np.maximum(np.abs(Y) - c["door_corridor_halfwidth_cm"], 0.0))
    s = s * smoothstep(0.0, d["door_taper_cm"], dcor)
    s = s + d["sheet_cm"] * sand_f
    # blowouts under the listed S3 cameras: the dunes dip there naturally instead of meeting a hard cone
    c = p["constraints"]
    for cam in fp["cameras"]["rows"]:
        cx, cy, cz = cam["local"]
        allow = max(cz - 115.0 - c["camera_keep_clear_cm"], 0.0)
        w = np.exp(-0.5 * (np.hypot(X - cx, Y - cy) / d["camera_blowout_radius_cm"]) ** 2)
        s = np.minimum(s, s * (1.0 - w) + w * allow)
    return np.maximum(s, 0.0)


# ----------------------------------------------------------------------------- wind
def wind_vector(d):
    a = math.radians(d["wind_to_deg"])
    return math.cos(a), math.sin(a)


def wind_transport(h, floor, d, dx, dy):
    """One deterministic wind step (no random numbers).

    Scour: wherever the surface rises DOWNWIND more steeply than windward_deg (a stoss slope steeper than the
    wind tolerates), loose sand is lifted, in proportion to the excess.
    Carry: the lifted sand travels downwind (scan along x toward the mouth, drifting sideways at the wind's
    angle) and lands in the FIRST lee shadow it meets: a cell below the 15 deg line from the crest upwind of
    it.  The talus step then turns those deposits into slip faces.  Sand that reaches a side wall stays
    against it; sand that crosses the mouth (x < 0) leaves.  Returns (h, lifted_cm3, lost_cm3)."""
    wx, wy = wind_vector(d)
    if wx >= 0.0:
        raise ValueError("wind_transport scans toward -x: wind_to_deg must be in (90, 270)")
    tan_ww = math.tan(math.radians(d["windward_deg"]))
    tan_s = math.tan(math.radians(d["shadow_deg"]))
    # slope along the wind: d h / d s, s = downwind distance
    gx = np.gradient(h, dx, axis=0)
    gy = np.gradient(h, dy, axis=1)
    gw = gx * wx + gy * wy
    lift = np.clip(d["scour_k"] * (gw - tan_ww) * dx, 0.0, None)
    lift = np.minimum(lift, np.maximum(h - floor, 0.0))
    h = h - lift
    nx, ny = h.shape
    carry = np.zeros(ny)
    crest = np.full(ny, -1.0e9)            # running 15 deg shadow line from upwind
    drift_per_col = abs(wy / wx) * dx / dy  # sideways cells per column
    side = -1 if wy < 0 else 1
    acc = 0.0
    out = h.copy()
    for i in range(nx - 1, -1, -1):
        col = out[i]
        shadow = col < crest - 0.25
        dep = np.where(shadow, carry, 0.0)
        out[i] = col + dep
        carry = carry - dep + lift[i]
        crest = np.maximum(crest - dx * tan_s, out[i])
        acc += drift_per_col
        while acc >= 1.0:
            acc -= 1.0
            moved = np.zeros_like(carry)
            if side < 0:
                moved[:-1] = carry[1:]
                moved[0] += carry[0]
            else:
                moved[1:] = carry[:-1]
                moved[-1] += carry[-1]
            carry = moved
            crest_m = np.full(ny, -1.0e9)
            if side < 0:
                crest_m[:-1] = crest[1:]
            else:
                crest_m[1:] = crest[:-1]
            crest = np.maximum(crest_m, crest - 1.0e9 * 0)  # shift the shadow line with the wind
    lost = float(carry.sum()) * dx * dy
    return out, float(lift.sum()) * dx * dy, lost


def simulate(fp, p):
    """Coarse dune simulation.  Returns coarse axes and the loose-sand thickness S (cm)."""
    d = dune_params(p)
    xs, ys = _axes(p, d["sim_grid_cm"])
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    bd = bed(X, Y, fp, p)
    B = bd["bed"]
    U = upper_bound(X, Y, fp, p)
    S = supply(X, Y, fp, p, bd["sand_f"])
    nzr = ValueNoise(p["seed"] + 31)
    rep = d["repose_deg"] + d["repose_jitter_deg"] * nzr.fbm(X, Y, 180.0, 3)   # scalloped, uneven slip faces
    tan_r = np.tan(np.radians(rep))
    # sand may be carried into every cell except the outermost wall rows (no transport into walls)
    wall_ok = np.ones(X.shape, dtype=bool)
    wall_ok[:, 0] = wall_ok[:, -1] = False
    wall_ok[-1, :] = False

    def clamp(S):
        return np.maximum(np.minimum(B + S, U) - B, 0.0)

    S = clamp(S)
    h = talus(B + S, B, tan_r, dx, dy, d["talus_passes_per_step"] * 10)
    for step in range(int(d["steps"])):
        h, _lifted, _lost = wind_transport(h, B, d, dx, dy)
        h = talus(h, B, tan_r, dx, dy, d["talus_passes_per_step"])
        if step % 5 == 4:
            h = B + clamp(h - B)
    h = talus(h, B, tan_r, dx, dy, d["final_coarse_talus_passes"], tol=0.05, max_passes=4000)
    S = clamp(h - B)
    return xs, ys, S


# ----------------------------------------------------------------------------- sand sheets over the soil
def sand_sheet(X, Y, S, bd, p):
    """Wind-blown sand advancing over the mud/moss toward the mouth (wind toward -x): sheets of a few cm that
    thin downwind, tongues and fans spilling from every heap, ragged wind-aligned (x-streaked) edges.  Mud
    survives in patches, in the hollows/pools and in a reduced strip at the mouth.  Returns (thickness_cm,
    coverage 0..1).  Deterministic scan (no random numbers)."""
    q = p["sheet"]
    dx = X[1, 0] - X[0, 0]
    nzs = ValueNoise(p["seed"] + 41)
    # streak noise: long along the wind (x), short across it (y)
    streak = 0.5 + 0.5 * nzs.fbm(X / q["streak_len_cm"], Y / q["streak_wid_cm"], 1.0, 3)
    src = q["beach_cm"] * bd["sand_f"] + q["heap_feed_cm"] * smoothstep(3.0, 40.0, S)
    decay = q["thin_per_m_cm"] * dx / 100.0 * (0.35 + 1.3 * (1.0 - streak))
    sh = np.zeros_like(S)
    run = np.zeros(S.shape[1])
    for i in range(S.shape[0] - 1, -1, -1):
        run = np.maximum(src[i], run - decay[i])
        sh[i] = run
    sh = box_blur(sh, 2)
    patches = smoothstep(q["patch_lo"], q["patch_hi"], 0.5 + 0.5 * nzs.fbm(X, Y, q["patch_scale_cm"], 3, 7.0))
    # soil shows in hollows and on the moss hummocks -- partly, with ragged edges (no punched discs)
    if q.get("hollow_soft", True):
        hollow = 0.75 * (smoothstep(1.0, 6.0, bd["pool"]) + smoothstep(1.0, 4.0, bd["hum"])) * (
            0.55 + 0.45 * smoothstep(0.3, 0.7, 0.5 + 0.5 * nzs.fbm(X, Y, 60.0, 2, 13.0)))
    else:                                                  # the 17:04 punched discs (harness - control only)
        hollow = smoothstep(0.5, 4.0, bd["pool"]) + smoothstep(0.5, 3.0, bd["hum"])
    mouth = smoothstep(q["mouth_strip_x"][0], q["mouth_strip_x"][1], X + 250.0 * (streak - 0.5))
    sh = sh * (1.0 - patches) * np.clip(1.0 - hollow, 0.0, 1.0) * mouth
    if q.get("hollow_soft", True):
        sh = box_blur(sh, 3)                              # soft rims: no stamped holes in the sheet
    sh = np.where(sh > q["min_cm"], sh, sh * smoothstep(0.0, q["min_cm"], sh))
    cover = smoothstep(0.4, 2.0, sh)
    return sh, cover


# ----------------------------------------------------------------------------- wind ripples
def wind_ripples(X, Y, S, slope_tan, wet, p, cover, h_smooth=None):
    """Wind ripples in the geometry.  mode 'natural' (Gary 7 Oct: the regular lines read too regular):
      - wavelength varies over the floor (longer on flats, shorter in lee/near heaps), integrated along the wind
        so the LOCAL spacing is exactly lambda(x, y) (no stretching artefacts far from the origin);
      - crest direction bends around the heaps (phase offset proportional to the smoothed surface height) and
        meanders (domain-warp noise);
      - phase noise strong enough to break crests into Y-junctions and terminations;
      - patchy amplitude (smooth patches with no ripples);
      - fades to zero on slopes (slip faces), in wet sand and on soil.
    mode 'regular' = the earlier single sinusoid (harness - control only).  Deterministic (value noise only).
    Note: the 7.5 cm mesh grid cannot carry the 6-15 cm ripple scale (Nyquist 15 cm); that scale belongs to
    the material normal map.  Geometry ripples here are the 35-80 cm megaripple scale."""
    r = p["wind_ripple"]
    if r["height_cm"][1] <= 0.0:
        return np.zeros_like(X)
    nz = ValueNoise(p["seed"] + 21)
    nzb = ValueNoise(p["seed"] + 22)
    d = p["dune"]
    wx, wy = wind_vector(d)
    if r.get("mode", "natural") == "regular":
        s = X * wx + Y * wy + r["meander_cm"] * nz.fbm(X, Y, 260.0, 2)
        cyc = s / r["wavelength_cm"]
        amp_patch = np.ones_like(X)
    else:
        lam = r["wavelength_range_cm"][0] + (r["wavelength_range_cm"][1] - r["wavelength_range_cm"][0]) *             (0.5 + 0.5 * nz.fbm(X, Y, r["wavelength_noise_cm"], 3))
        if h_smooth is not None:
            lam = lam * (1.0 - r["lee_shorten"] * smoothstep(5.0, 60.0, h_smooth))
        dx = X[1, 0] - X[0, 0]
        # cycles accumulated along -x (downwind) so the local spacing along the wind is lambda
        steps = dx * abs(wx) / lam
        cyc_x = np.cumsum(steps[::-1], axis=0)[::-1]
        cyc = cyc_x + Y * wy / lam.mean()
        if h_smooth is not None:
            cyc = cyc + r["bend_cycles_per_m"] * h_smooth / 100.0       # crests bend around the heaps
        warp = r["meander_cm"] * nz.fbm(X + 911.0, Y, 300.0, 3)
        cyc = cyc + warp / lam
        cyc = cyc + r["phase_noise_cycles"] * nzb.fbm(X, Y, r["phase_noise_scale_cm"], 3)   # Y-junctions
        amp_patch = smoothstep(r["patch_gap"][0], r["patch_gap"][1], 0.5 + 0.5 * nzb.fbm(X, Y, 420.0, 3, 3.0))
    t = np.mod(cyc, 1.0)
    lee = r["lee_frac"]
    prof = np.where(t < 1.0 - lee, t / (1.0 - lee), (1.0 - t) / lee)
    prof = prof * prof * (3.0 - 2.0 * prof)
    hgt = r["height_cm"][0] + (r["height_cm"][1] - r["height_cm"][0]) * (0.5 + 0.5 * nz.fbm(X, Y, 340.0, 3))
    if r.get("mode", "natural") != "regular":
        # ripple index: the lee face of a ripple may not exceed ripple_lee_max_deg (short ripples are lower)
        # use the LOCAL spacing (1 / |grad phase|): phase noise squeezes ripples at Y-junctions
        gcx = np.gradient(cyc, X[1, 0] - X[0, 0], axis=0)
        gcy = np.gradient(cyc, Y[0, 1] - Y[0, 0], axis=1)
        lam_loc = 1.0 / np.maximum(np.hypot(gcx, gcy), 1e-6)
        hgt = np.minimum(hgt, lee * lam_loc * math.tan(math.radians(r["ripple_lee_max_deg"])))
    fade = (1.0 - smoothstep(math.tan(math.radians(r["fade_slope_deg"][0])),
                             math.tan(math.radians(r["fade_slope_deg"][1])), slope_tan))
    on_sand = np.maximum(smoothstep(r["min_sand_cm"], 2.0 * r["min_sand_cm"] + 4.0, S), r["beach_frac"] * cover)
    fade = fade * on_sand * (1.0 - smoothstep(0.35, 0.7, wet)) * amp_patch
    return hgt * (prof - 0.5) * fade


def slope_tan_grid(h, dx, dy):
    gx = np.gradient(h, dx, axis=0)
    gy = np.gradient(h, dy, axis=1)
    return np.hypot(gx, gy)


def box_blur(a, r):
    """Separable box blur with edge replicate, radius r cells."""
    out = a
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        ap = np.pad(out, pad, mode="edge")
        c = np.cumsum(ap, axis=axis, dtype=float)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
        n = out.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        out = (hi - lo) / (2 * r + 1)
    return out


# ----------------------------------------------------------------------------- the full grid
_CACHE = {}


def _key(fp, p):
    return hashlib.sha256((json.dumps(p, sort_keys=True) + json.dumps(fp, sort_keys=True)).encode()).hexdigest()


def build_grid(fp=None, p=PARAMS):
    if fp is None:
        fp = load_footprint()
    k = _key(fp, p)
    if k in _CACHE:
        return _CACHE[k]
    xs, ys = grid_axes(p)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    bd = bed(X, Y, fp, p)
    B = bd["bed"]
    U = upper_bound(X, Y, fp, p)
    cxs, cys, Sc = simulate(fp, p)
    S = np.maximum(interp2(cxs, cys, Sc, X, Y), 0.0)
    if p["fine"].get("pools_avoid_sand", True):
        # puddles only on low, flat, open ground (conductor review 17:04): a pool within ~1 m of a heap is
        # removed from the bed instead of printing a pit into the dune; the rest become shallow, irregular
        nzp = ValueNoise(p["seed"] + 51)
        irregular = 0.45 + 0.55 * smoothstep(0.25, 0.75, 0.5 + 0.5 * nzp.fbm(X, Y, 70.0, 3))
        base_slope = slope_tan_grid(box_blur(B + bd["pool"] * (1.0 - bd["notch_w"]) + S, 8), dx, dy)
        flat = 1.0 - smoothstep(math.tan(math.radians(3.0)), math.tan(math.radians(6.0)), base_slope)
        keep = (1.0 - smoothstep(2.0, 12.0, box_blur(S, 14))) * flat * irregular
        B = B + bd["pool"] * (1.0 - bd["notch_w"]) * (1.0 - keep)
        bd["pool"] = bd["pool"] * keep
    # de-terrace (conductor review 7 Oct): the 15 cm sim + 8-neighbour relaxation leaves diagonal facet stripes;
    # a light blur of the loose sand removes them before the fine relaxation re-forms clean slip faces
    for _ in range(int(p["fine"]["sand_blur_passes"])):
        if p["fine"].get("fill_pools_under_sand", True):
            # blur the SURFACE where sand is thick (so a bed pool under a heap is filled, not printed through
            # as a pit on the dune -- conductor review 17:04), the sand thickness elsewhere
            w = smoothstep(3.0, 20.0, S)
            Sb = np.maximum(box_blur(B + S, int(p["fine"]["sand_blur_cells"])) - B, 0.0)
            S = w * Sb + (1.0 - w) * box_blur(S, int(p["fine"]["sand_blur_cells"]))
        else:
            S = box_blur(S, int(p["fine"]["sand_blur_cells"]))
    # wind-blown sand sheets, tongues and fans over the soil toward the mouth (Gary 7 Oct)
    sheet, cover = sand_sheet(X, Y, S, bd, p)
    S = S + sheet
    h = B + S
    nz2 = ValueNoise(p["seed"] + 1)
    nz3 = ValueNoise(p["seed"] + 2)
    floor = np.minimum(B, U)
    tan_f = math.tan(math.radians(p["final_repose_deg"]))
    wet0 = np.maximum(0.85 * bd["wet_zone"], 0.35 * (1.0 - bd["sand_f"]) * (1.0 - cover)) * (1.0 - smoothstep(4.0, 25.0, S))
    if p["fine"].get("ripples_before_talus", False):        # the old order: harness - control only
        sl = slope_tan_grid(box_blur(h, 2), dx, dy)
        h = h + wind_ripples(X, Y, S, sl, wet0, p, cover, box_blur(h, 10))
        h = np.minimum(h, U)
        h = talus(h, floor, tan_f, dx, dy, p["final_talus_passes"])
    else:
        h = np.minimum(h, U)
        h = talus(h, floor, tan_f, dx, dy, p["final_talus_passes"], k=p["fine"]["talus_k"], tol=0.1, max_passes=3000)
        sl = slope_tan_grid(box_blur(h, 2), dx, dy)
        h = h + wind_ripples(X, Y, np.maximum(h - B, 0.0), sl, wet0, p, cover, box_blur(h, 10))
        h = np.minimum(h, U)
        h = talus(h, floor, tan_f, dx, dy, p["fine"]["post_ripple_talus_passes"], k=p["fine"]["talus_k"],
                  tol=0.1, max_passes=2000)
    h = np.minimum(h, U)
    # millstone seat (Gary 7 Oct): level disc at the mean surface under it, soft blend outward, no pad edge.
    # A/B/C keep the shipped ordering.  D seats after the triangle clamp: at 4.8 m the clamp otherwise pulls the
    # disc 7 cm out of level while repairing the much larger adjacent heaps.
    def apply_millstone_seat(surface):
        seat_ = None
        if not p.get("millstone_seat", True) or "millstone_seat" not in fp:
            return surface, seat_
        ms = fp["millstone_seat"]
        sx, sy = ms["local_xy"]
        dd = np.hypot(X - sx, Y - sy)
        inside_seat = dd <= ms["radius_cm"]
        seat_h = float(surface[inside_seat].mean())
        w = 1.0 - smoothstep(ms["radius_cm"], ms["radius_cm"] + ms["blend_cm"], dd)
        surface = (1.0 - w) * surface + w * seat_h
        seat_ = {"local_xy": [sx, sy], "radius_cm": ms["radius_cm"], "blend_cm": ms["blend_cm"],
                 "h_above_floor_cm": round(seat_h, 3), "local_z": round(115.0 + seat_h, 3)}
        return surface, seat_

    seat = None
    seat_after = bool(active_set(p).get("seat_after_triangle_clamp", False))
    if not seat_after:
        h, seat = apply_millstone_seat(h)
    if p.get("triangle_clamp", True):
        h, clamp_iters, clamp_removed, steep_left = relax_triangles(
            h, floor, math.tan(math.radians(p["slip_face_max_deg"] - 0.5)), dx, dy)
    else:
        clamp_iters, clamp_removed, steep_left = 0, 0.0, -1
    if seat_after:
        h, seat = apply_millstone_seat(h)
    S = np.maximum(h - B, 0.0)

    # cast island (control only)
    if p.get("preserve_v2_cast", False):
        metric = v2_metric(X + 500.0, Y)
        w_cast = 1.0 - smoothstep(p["cast_blend_metric"][0], p["cast_blend_metric"][1], metric)
        h = w_cast * v2_h(X, Y) + (1.0 - w_cast) * h
    else:
        w_cast = np.zeros_like(X)
    pad_w_total = np.zeros_like(X)
    v2_here = v2_h(X, Y)
    for label, px, py, pr, ph, kind in (pads(fp, p) if p.get("use_pads", False) else []):
        dd = np.hypot(X - px, Y - py)
        w = 1.0 - smoothstep(pr, pr + p["pad_blend_cm"], dd)
        target = v2_here if kind == "prop" else ph
        h = (1.0 - w) * h + w * target
        pad_w_total = np.maximum(pad_w_total, w)
    if p.get("wave_notch", True):
        h = h * (1.0 - (bd["notch_w"] >= 1.0))           # exactly flush under the flats

    # ---- vertex colours ----
    sand_f, wet_zone, notch_w, pool, hum = bd["sand_f"], bd["wet_zone"], bd["notch_w"], bd["pool"], bd["hum"]
    dune = smoothstep(6.0, 30.0, S)
    hs = box_blur(h, 6)                                    # ~45 cm
    curv = box_blur(h, 14) - hs                            # >0 = hollow (concave), <0 = crest (convex)
    crest = smoothstep(2.0, 10.0, -curv) * dune
    hollow = smoothstep(1.5, 8.0, curv) * dune
    soil = (1.0 - sand_f) * (1.0 - cover)                  # soil left uncovered by the sand sheets
    mud = soil * (1.0 - dune) * (1.0 - w_cast)
    mud = np.clip(mud + 0.15 * nz2.fbm(X, Y, 120.0, 2) * soil * (1.0 - dune), 0.0, 1.0)
    pool_mask = smoothstep(0.5, 4.0, pool) * (1.0 - pad_w_total) * (1.0 - dune)
    wet = np.maximum(0.85 * wet_zone, 0.35 * soil)
    wet = np.maximum(wet, pool_mask)
    wet = np.maximum(wet, 0.9 * notch_w)
    wet = wet * (1.0 - smoothstep(4.0, 30.0, S))           # piled sand dries out
    wet = np.maximum(wet, (0.12 + 0.33 * hollow) * dune)   # damp, darker hollows between dunes
    wet = wet * (1.0 - 0.9 * crest)                        # dry, pale crests
    # dune feet in the wave zone stay wet (sand creeping onto the wet flats)
    wet = np.maximum(wet, 0.6 * wet_zone * (1.0 - smoothstep(3.0, 18.0, S)))
    wet = np.clip(wet + 0.06 * nz3.fbm(X, Y, 90.0, 2), 0.0, 0.8 + 0.2 * np.maximum(pool_mask, notch_w))
    moss_noise = smoothstep(-0.05, 0.35, nz3.fbm(X, Y, 160.0, 3))
    hum_mask = smoothstep(0.5, 3.0, hum)
    yl = fp["walls"]["left_inner_face_y"]["value"]
    yr = fp["walls"]["right_inner_face_y"]["value"]
    dL = np.maximum(Y - yl, 0.0)
    dR = np.maximum(yr - Y, 0.0)
    wall_base = np.maximum(smoothstep(120.0, 0.0, dL), smoothstep(120.0, 0.0, dR)) * soil
    # moss creeps onto the toes of the dunes in the mud zone
    toe = smoothstep(2.0, 10.0, S) * (1.0 - smoothstep(14.0, 40.0, S)) * soil
    moss = np.clip(mud * np.clip(0.75 * moss_noise + hum_mask + 0.5 * wall_base, 0.0, 1.0) * (1.0 - 0.7 * pool_mask)
                   + 0.45 * toe * moss_noise, 0.0, 1.0)
    alpha = np.ones_like(X)
    out = {"h": h, "r": mud, "g": wet, "b": moss, "a": alpha, "notch_w": notch_w, "pad_w": pad_w_total,
           "w_cast": w_cast, "drift": S, "bed": B, "U": U, "X": X, "Y": Y, "xs": xs, "ys": ys,
           "coarse": {"xs": cxs, "ys": cys, "S": Sc},
           "millstone_seat": seat, "sheet": sheet, "cover": cover, "pool_eff": bd["pool"],
           "slope_clamp": {"iterations": clamp_iters, "moved_m3": round(clamp_removed / 1e6, 4), "steep_quads_left": steep_left}}
    _CACHE[k] = out
    return out


def field(x, y, fp=None, p=PARAMS):
    """Point query: bilinear sample of the mesh grid (the mesh IS this grid)."""
    g = build_grid(fp, p)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return {k: interp2(g["xs"], g["ys"], g[k], x, y) for k in ("h", "r", "g", "b", "a", "notch_w", "pad_w", "w_cast",
                                                                 "drift")}


def grid_sha256(grid):
    hsh = hashlib.sha256()
    for k in ("h", "r", "g", "b", "a"):
        hsh.update(np.ascontiguousarray(grid[k], dtype=np.float64).tobytes())
    return hsh.hexdigest()


# ----------------------------------------------------------------------------- measurements
def triangle_slopes_deg(h, dx, dy):
    """Max slope (deg) over the 4 triangles of each quad (both diagonal choices: UE may pick either)."""
    a, b, c, d = h[:-1, :-1], h[1:, :-1], h[1:, 1:], h[:-1, 1:]
    s = []
    s.append(np.hypot((b - a) / dx, (c - b) / dy))      # a b c
    s.append(np.hypot((c - d) / dx, (d - a) / dy))      # a c d
    s.append(np.hypot((b - a) / dx, (d - a) / dy))      # a b d
    s.append(np.hypot((c - d) / dx, (c - b) / dy))      # b c d
    return np.degrees(np.arctan(np.maximum.reduce(s)))


def wall_profiles(fp, p, grid):
    xs = np.linspace(0, 6000, 1201)
    ys = np.linspace(-999, 999, 401)
    yl = fp["walls"]["left_inner_face_y"]["value"]
    yr = fp["walls"]["right_inner_face_y"]["value"]
    xb = fp["walls"]["backdrop_plane_x"]["value"]
    hL = interp2(grid["xs"], grid["ys"], grid["h"], xs, np.full_like(xs, yl))
    hR = interp2(grid["xs"], grid["ys"], grid["h"], xs, np.full_like(xs, yr))
    hB = interp2(grid["xs"], grid["ys"], grid["h"], np.full_like(ys, xb), ys)
    return xs, ys, hL, hR, hB


def dune_clearance_metrics(fp, p, grid):
    """Measure D's physical brief: 6-8 m side heaps, a clear centre lane, and a clear clam/millstone seat."""
    X, Y, H, S = grid["X"], grid["Y"], grid["h"], grid["drift"]
    c = constraint_params(p)
    yl = fp["walls"]["left_inner_face_y"]["value"]
    yr = fp["walls"]["right_inner_face_y"]["value"]
    xb = fp["walls"]["backdrop_plane_x"]["value"]
    lane_hw = float(c.get("centre_lane_halfwidth_cm", 0.0))
    lane = (np.abs(Y) <= lane_hw) & (X >= 0.0) & (X <= xb)
    # Attribute each half of the room to its nearest side wall.  Exclude the first/last 6 m along x so corner and
    # back-wall heaps cannot masquerade as side-wall reach.  >30 cm is the established dune-area threshold.
    along = (X >= 600.0) & (X <= xb - 600.0)
    left = (Y <= 0.0) & along & (S > 30.0)
    right = (Y >= 0.0) & along & (S > 30.0)
    left_reach = float(np.max(Y[left] - yl)) if left.any() else 0.0
    right_reach = float(np.max(yr - Y[right])) if right.any() else 0.0
    out = {"centre_lane_halfwidth_cm": lane_hw,
           "centre_lane_max_h_cm": round(float(H[lane].max()), 2) if lane.any() else None,
           "side_heap_inward_reach_cm": {"left": round(left_reach, 1), "right": round(right_reach, 1)}}
    if "millstone_seat" in fp:
        mx, my = fp["millstone_seat"]["local_xy"]
        rr = np.hypot(X - mx, Y - my) <= c.get("millstone_clear_radius_cm", fp["millstone_seat"]["radius_cm"])
        out["clam_millstone_clear_max_h_cm"] = round(float(H[rr].max()), 2)
    return out


def dune_clearance_failures(p, clear):
    failures = []
    gates = active_set(p).get("gates", {})
    if not gates:
        return failures
    if clear["centre_lane_max_h_cm"] > gates["centre_lane_max_cm"]:
        failures.append("CENTRE_LANE_BLOCKED %.2f > %.2f"
                        % (clear["centre_lane_max_h_cm"], gates["centre_lane_max_cm"]))
    lo, hi = gates["dune_inward_reach_cm"]
    for wall, reach in clear["side_heap_inward_reach_cm"].items():
        if not lo <= reach <= hi:
            failures.append("DUNE_REACH_%s %.1f not in %.1f..%.1f" % (wall.upper(), reach, lo, hi))
    return failures


def realism_metrics(fp, p, grid):
    X, Y, h, S = grid["X"], grid["Y"], grid["h"], grid["drift"]
    dx, dy = grid["xs"][1] - grid["xs"][0], grid["ys"][1] - grid["ys"][0]
    tri = triangle_slopes_deg(h, dx, dy)
    yl = fp["walls"]["left_inner_face_y"]["value"]
    yr = fp["walls"]["right_inner_face_y"]["value"]
    inside = ((Y > yl) & (Y < yr) & (X < fp["walls"]["backdrop_plane_x"]["value"]))[:-1, :-1]
    tri_in = tri[inside]
    sand = (S[:-1, :-1] > 20.0) & inside
    # slip faces measured on the SMOOTHED surface (ripples removed) so they are dune faces, not ripple lees
    hs = box_blur(h, 4)
    gx = np.gradient(hs, dx, axis=0)
    gy = np.gradient(hs, dy, axis=1)
    sl = np.degrees(np.arctan(np.hypot(gx, gy)))
    big = (S > 30.0)
    big &= (Y > yl) & (Y < yr)
    slip = big & (sl >= 27.0)
    # wind asymmetry: faces dipping DOWNWIND (lee) vs faces dipping UPWIND (windward)
    wcx, wcy = wind_vector(p["dune"])
    gw = gx * wcx + gy * wcy          # slope along the wind; < 0 = the surface falls away downwind (lee)
    lee = big & (gw < -0.05)
    wnd = big & (gw > 0.05)
    mid = sl > 5.0
    lee_med = float(np.median(sl[lee & mid])) if (lee & mid).any() else 0.0
    wnd_med = float(np.median(sl[wnd & mid])) if (wnd & mid).any() else 0.0
    steep = sl >= 27.0
    n_lee, n_wnd = int((lee & steep).sum()), int((wnd & steep).sum())
    # ripples: high-pass of the surface on gentle dry sand
    hp = h - box_blur(h, 5)
    gentle = (S > 20.0) & (sl < 12.0) & (grid["g"] < 0.3)
    rip = hp[gentle]
    rip_amp = float(np.percentile(rip, 97) - np.percentile(rip, 3)) if rip.size > 100 else 0.0
    # terracing: on dune faces (45 cm-smoothed slope 20-34 deg) the fine slope should follow the smooth slope;
    # diagonal facet stripes / stacked ledges show up as a large residual (conductor review 7 Oct)
    fine = np.degrees(np.arctan(slope_tan_grid(h, dx, dy)))
    smooth45 = np.degrees(np.arctan(slope_tan_grid(box_blur(h, 6), dx, dy)))
    face = (S > 30.0) & (smooth45 > 20.0) & (smooth45 < 34.0)
    resid = (fine - smooth45)[face]
    terr_rms = float(np.sqrt(np.mean(resid ** 2))) if resid.size else 0.0
    ledge = float((fine[face] < smooth45[face] - 8.0).mean()) if resid.size else 0.0
    # sand coverage (vertex paint): floor inside the walls painted sand (R mud < 0.5) vs soil
    floor_in = (Y > yl) & (Y < yr) & (X < fp["walls"]["backdrop_plane_x"]["value"])
    soilish = grid["r"] > 0.5
    mudzone = floor_in & (X < p["mud_to_sand_x"][0] + 600.0)
    spec = ripple_spectrum(grid, S, sl)
    # pits: depressions (45 cm-scale surface below its 2.4 m surroundings by > 3 cm) on a dune or a slope > 8 deg
    dip = box_blur(h, 16) - box_blur(h, 3)
    on_dune = (S > 20.0) | (smooth45 > 8.0)
    pit = (dip > 3.0) & on_dune & ((Y > yl) & (Y < yr))
    # closed pits: a cell lower by > 2 cm than EVERY point of a 45 cm ring around it, on/next to a dune or on
    # a slope > 8 deg (interdune saddles and dune toes are not closed, ripple troughs are shallower)
    ring = np.full(h.shape, np.inf)
    for k in range(16):
        a_ = 2.0 * math.pi * k / 16.0
        ri, rj = int(round(6 * math.cos(a_))), int(round(6 * math.sin(a_)))
        pad = np.pad(h, 6, mode="edge")
        ring = np.minimum(ring, pad[6 + ri:6 + ri + h.shape[0], 6 + rj:6 + rj + h.shape[1]])
    near = (box_blur(S, 8) > 10.0) | (smooth45 > 8.0)
    pit = (h < ring - 2.0) & near & ((Y > yl) & (Y < yr))
    pit_area = float(pit.sum()) * dx * dy / 1e4
    # puddles where they do not belong: an applied pool dip (> 1 cm) on a dune (sand > 20 cm within ~1 m) or on
    # a slope > 8 deg.  This inspects the dip field the mesh was built with (not a geometric detector).
    filled = np.degrees(np.arctan(slope_tan_grid(box_blur(h + grid["pool_eff"], 6), dx, dy)))  # the puddle's own rim excluded
    bad_pool = (grid["pool_eff"] > 1.0) & ((box_blur(S, 14) > 20.0) | (filled > 8.0))
    bad_pool_area = float(bad_pool.sum()) * dx * dy / 1e4
    return {
        "ripple_peak_concentration": spec["mean_peak_share"], "ripple_hp_rms_cm": spec["mean_hp_rms_cm"],
        "ripple_spectrum_windows": spec["windows"],
        "closed_pits_near_dunes_m2_info": round(pit_area, 2),
        "pool_dips_on_dunes_or_slopes_m2": round(bad_pool_area, 2),
        "terracing_rms_deg": round(terr_rms, 2), "terracing_ledge_share": round(ledge, 4), "face_cells": int(face.sum()),
        "sand_painted_floor_pct": round(100.0 * float((~soilish & floor_in).sum()) / float(floor_in.sum()), 1),
        "soil_painted_floor_pct": round(100.0 * float((soilish & floor_in).sum()) / float(floor_in.sum()), 1),
        "soil_pct_in_mud_zone_x_lt_2100": round(100.0 * float((soilish & mudzone).sum()) / float(mudzone.sum()), 1),
        "max_triangle_slope_deg": round(float(tri_in.max()), 2),
        "p999_triangle_slope_deg_on_sand": round(float(np.percentile(tri[sand], 99.9)), 2) if sand.any() else 0.0,
        "slip_face_area_m2": round(float(slip.sum()) * dx * dy / 1e4, 2),
        "slip_face_slope_p50_p95_deg": [round(float(np.percentile(sl[slip], 50)), 2),
                                        round(float(np.percentile(sl[slip], 95)), 2)] if slip.any() else [0, 0],
        "lee_vs_windward_median_slope_deg": [round(lee_med, 2), round(wnd_med, 2)],
        "steep_faces_facing_downwind_share": round(n_lee / max(n_lee + n_wnd, 1), 3),
        "ripple_p3_p97_cm": round(rip_amp, 2), "ripple_samples": int(rip.size),
        "dune_area_m2_over_30cm": round(float((S > 30).sum()) * dx * dy / 1e4, 1),
        "sand_volume_m3": round(float(S.sum()) * dx * dy / 1e6, 1),
    }


def ripple_spectrum(grid, S, slope_deg, win=64, n_windows=5):
    """Spectral spread of the geometry ripples.  Windows (64 x 64 cells, 4.8 m) are picked where gentle dry sand
    is most continuous; in each, the high-passed surface is Hann-windowed and FFT'd.  peak_share = power in the
    3x3 bins around the strongest peak (and its mirror) / power in the 25-120 cm wavelength band.  One regular
    sinusoid concentrates nearly all power in one peak; a natural field (varying spacing, bending crests,
    Y-junctions) spreads it."""
    h = grid["h"]
    dx = grid["xs"][1] - grid["xs"][0]
    dy = grid["ys"][1] - grid["ys"][0]
    good = ((S > 4.0) & (slope_deg < 8.0) & (grid["g"] < 0.3)).astype(float)
    hp = h - box_blur(h, 8)
    nx, ny = h.shape
    cands = []
    for i in range(0, nx - win, win // 2):
        for j in range(0, ny - win, win // 2):
            cands.append((float(good[i:i + win, j:j + win].mean()), i, j))
    cands.sort(key=lambda t: (-t[0], t[1], t[2]))
    picked = []
    for frac, i, j in cands:
        if frac < 0.6 or len(picked) >= n_windows:
            break
        if all(abs(i - a) >= win or abs(j - b) >= win for _f, a, b in picked):
            picked.append((frac, i, j))
    hann = np.outer(np.hanning(win), np.hanning(win))
    fx = np.fft.fftfreq(win, dx)
    fy = np.fft.fftfreq(win, dy)
    FX, FY = np.meshgrid(fx, fy, indexing="ij")
    fr = np.hypot(FX, FY)
    band = (fr > 1.0 / 120.0) & (fr < 1.0 / 25.0)
    rip_band = (fr > 1.0 / 95.0) & (fr < 1.0 / 25.0)     # the ripple scale only (RMS in cm, Parseval)
    rows = []
    for frac, i, j in picked:
        P = np.abs(np.fft.fft2(hp[i:i + win, j:j + win] * hann)) ** 2
        Pb = np.where(band, P, 0.0)
        tot = float(Pb.sum())
        if tot <= 0.0:
            continue
        a, b = np.unravel_index(np.argmax(Pb), Pb.shape)
        share = 0.0
        for (ca, cb) in ((a, b), ((-a) % win, (-b) % win)):
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    share += float(Pb[(ca + da) % win, (cb + db) % win])
        rows.append({"x": round(float(grid["xs"][i]), 0), "y": round(float(grid["ys"][j]), 0),
                     "hp_rms_cm": round(float(np.sqrt(np.sum(np.where(rip_band, P, 0.0)) / np.sum(hann ** 2))) / win, 3),
                     "peak_share": round(share / tot, 3),
                     "peak_wavelength_cm": round(1.0 / max(float(fr[a, b]), 1e-9), 1)})
    mean = round(float(np.mean([r["peak_share"] for r in rows])), 3) if rows else 1.0
    rms = round(float(np.mean([r["hp_rms_cm"] for r in rows])), 3) if rows else 0.0
    return {"mean_peak_share": mean, "mean_hp_rms_cm": rms, "windows": rows}


def height_set_summary(fp, p, grid):
    xs, ys, hL, hR, hB = wall_profiles(fp, p, grid)
    wall_max = float(max(hL.max(), hR.max(), hB.max()))
    clr = p["print_clearance_cm"]
    per_m = {"left": [], "right": []}
    for i in range(0, 60):
        sel = (xs >= i * 100) & (xs <= (i + 1) * 100)
        per_m["left"].append(round(float(hL[sel].max()), 1))
        per_m["right"].append(round(float(hR[sel].max()), 1))
    per_m["back_by_y_m"] = [round(float(hB[(ys >= -1000 + i * 100) & (ys <= -900 + i * 100)].max()), 1)
                            for i in range(20)]
    return {
        "set": p["height_set"], "target_wall_max_cm": active_set(p)["target_wall_max_cm"],
        "supply_cm": active_set(p)["supply_cm"],
        "measured_wall_max_cm": {"left": round(float(hL.max()), 1), "right": round(float(hR.max()), 1),
                                 "back": round(float(hB.max()), 1), "all": round(wall_max, 1)},
        "measured_wall_mean_cm": {"left": round(float(hL.mean()), 1), "right": round(float(hR.mean()), 1),
                                  "back": round(float(hB.mean()), 1)},
        "print_clearance_cm": clr,
        "min_print_line_cm_above_floor_top": float(math.ceil((wall_max + clr) / 5.0) * 5.0),
        "print_line_cm_in_params": active_set(p)["print_line_cm"],
        "max_dune_anywhere_cm": round(float(grid["h"].max()), 1),
        "clearance": dune_clearance_metrics(fp, p, grid),
        "wall_profile_max_per_metre_cm": per_m,
    }


# ----------------------------------------------------------------------------- checks
def checks(fp=None, p=PARAMS, grid=None):
    """Assertions the mesh must satisfy.  Returns (failures, report)."""
    if fp is None:
        fp = load_footprint()
    if grid is None:
        grid = build_grid(fp, p)
    failures, report = [], {}

    def F(x, y):
        return interp2(grid["xs"], grid["ys"], grid["h"], x, y)

    # cast area: must be re-sculpted (not the beach-v2 surface) unless preservation is switched on
    xs_c = np.linspace(2600.0, 3500.0, 61)
    ys_c = np.linspace(-650.0, 650.0, 61)
    Xc, Yc = np.meshgrid(xs_c, ys_c, indexing="ij")
    inside = v2_metric(Xc + 500.0, Yc) < 0.85
    dv = np.abs(F(Xc, Yc) - v2_h(Xc, Yc))[inside]
    same_frac = float((dv < 0.5).mean())
    report["cast_area_vs_v2"] = {"samples": int(inside.sum()), "fraction_within_0p5cm_of_v2": round(same_frac, 4),
                                 "mean_abs_diff_cm": round(float(dv.mean()), 3), "max_abs_diff_cm": round(float(dv.max()), 3)}
    if not p.get("preserve_v2_cast", False) and same_frac > 0.5:
        failures.append("CAST_STILL_V2 fraction=%.3f" % same_frac)
    pad_rows = []
    for label, px, py, pr, ph, kind in (pads(fp, p) if p.get("use_pads", False) else []):
        ring = [(px + rr * math.cos(t), py + rr * math.sin(t))
                for rr in (0.0, 0.5 * max(pr, 30.0), max(pr, 30.0)) for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
        qx = np.array([q[0] for q in ring]); qy = np.array([q[1] for q in ring])
        hs = F(qx, qy)
        target = v2_h(qx, qy) if kind == "prop" else ph
        dev = float(np.max(np.abs(hs - target)))
        pad_rows.append({"label": label, "kind": kind, "max_dev_in_pad_cm": round(dev, 4)})
        if dev > 1.0:
            failures.append(f"PAD_NOT_FLAT {label} dev={dev:.3f}")
    report["pads"] = pad_rows
    # millstone seat: level within the radius (gentle; the stone may sink a few cm)
    if "millstone_seat" in fp:           # checked whenever the footprint asks for a seat (param only builds it)
        ms = fp["millstone_seat"]
        sx, sy = ms["local_xy"]
        rr = np.linspace(0.0, ms["radius_cm"], 9)
        tt = np.linspace(0.0, 2 * math.pi, 24, endpoint=False)
        R_, T_ = np.meshgrid(rr, tt)
        hs = F(sx + R_ * np.cos(T_), sy + R_ * np.sin(T_))
        dev = float(hs.max() - hs.min())
        report["millstone_seat"] = {"local_xy": [sx, sy], "radius_cm": ms["radius_cm"],
                                    "h_mean_cm": round(float(hs.mean()), 3), "local_z": round(115.0 + float(hs.mean()), 3),
                                    "range_within_radius_cm": round(dev, 3)}
        if dev > 1.0:
            failures.append("SEAT_NOT_LEVEL range=%.2f" % dev)
    # cameras
    cam_rows = []
    for cam in fp["cameras"]["rows"]:
        cx, cy, cz = cam["local"]
        vclear = cz - (115.0 + float(F(np.array([cx]), np.array([cy]))[0]))
        cam_rows.append({"label": cam["label"], "vertical_clearance_cm": round(vclear, 2)})
        if vclear < p["camera_min_vertical_clearance_cm"]:
            failures.append(f"CAMERA_LOW {cam['label']} {vclear:.1f}")
    report["cameras"] = cam_rows
    # wave notches
    wave_rows = []
    for row in fp["wave_rows"]["rows"]:
        xs = np.linspace(row["x"][0], row["x"][1], 9)
        ys = np.linspace(-1000, 1000, 201)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        H = F(X, Y)
        wave_rows.append({"row": row["name"], "max_abs_h_under_flat_cm": round(float(np.abs(H).max()), 4)})
        if float(np.abs(H).max()) > 0.05:
            failures.append(f"WAVE_BASE_NOT_FLUSH {row['name']} {float(np.abs(H).max()):.3f}")
    report["wave_rows"] = wave_rows
    # walls vs the proposed print line of the active set
    xs, ys, hL, hR, hB = wall_profiles(fp, p, grid)
    line = active_set(p)["print_line_cm"]
    clr = p["print_clearance_cm"]
    current = fp["handprint_lowest_extent_above_floor_cm"]["value"]
    report["walls"] = {"left_max_cm": round(float(hL.max()), 2), "left_mean_cm": round(float(hL.mean()), 2),
                       "right_max_cm": round(float(hR.max()), 2), "right_mean_cm": round(float(hR.mean()), 2),
                       "back_max_cm": round(float(hB.max()), 2),
                       "back_at_door_max_cm": round(float(hB[np.abs(ys) < 150].max()), 2),
                       "proposed_print_line_cm": line, "print_clearance_cm": clr,
                       "current_print_line_cm": current,
                       "current_prints_would_be_covered": bool(max(hL.max(), hR.max(), hB.max()) > current - 10.0)}
    for name, arr in (("left", hL), ("right", hR), ("back", hB)):
        if float(arr.max()) > line - clr:
            failures.append(f"DRIFT_HITS_PRINTS {name} {float(arr.max()):.1f} > {line - clr:.1f}")
    if float(hB[np.abs(ys) < 150].max()) > 15.0:
        failures.append("DOOR_GAP_BLOCKED")
    clear = dune_clearance_metrics(fp, p, grid)
    report["clearance"] = clear
    failures.extend(dune_clearance_failures(p, clear))
    # realism
    rm = realism_metrics(fp, p, grid)
    report["realism"] = rm
    if rm["max_triangle_slope_deg"] > p["slip_face_max_deg"]:
        failures.append("SLOPE_OVER_REPOSE %.2f" % rm["max_triangle_slope_deg"])
    if rm["slip_face_area_m2"] < 2.0:
        failures.append("SLIP_FACES_ABSENT %.2f" % rm["slip_face_area_m2"])
    lm, wm = rm["lee_vs_windward_median_slope_deg"]
    gates = active_set(p).get("gates", {})
    min_asym = gates.get("wind_asymmetry_min_delta_deg", 4.0)
    min_lee_share = gates.get("steep_lee_share_min", 0.6)
    if lm < wm + min_asym or rm["steep_faces_facing_downwind_share"] < min_lee_share:
        failures.append("NO_WIND_ASYMMETRY lee %.1f vs windward %.1f deg, steep lee share %.2f"
                        % (lm, wm, rm["steep_faces_facing_downwind_share"]))
    if rm["ripple_hp_rms_cm"] < p["checks"]["ripple_rms_min_cm"]:
        failures.append("RIPPLES_ABSENT ripple-band rms %.3f cm" % rm["ripple_hp_rms_cm"])
    elif rm["ripple_peak_concentration"] > p["checks"]["ripple_peak_share_max"]:
        failures.append("RIPPLES_TOO_REGULAR peak share %.3f" % rm["ripple_peak_concentration"])
    if rm["pool_dips_on_dunes_or_slopes_m2"] > p["checks"]["pits_on_dunes_max_m2"]:
        failures.append("PITS_ON_DUNES %.2f m2" % rm["pool_dips_on_dunes_or_slopes_m2"])
    if rm["terracing_rms_deg"] > p["checks"]["terracing_rms_max_deg"]:
        failures.append("TERRACING rms %.2f deg" % rm["terracing_rms_deg"])
    ys2 = np.linspace(-1000, 1000, 201)
    h0 = F(np.zeros_like(ys2), ys2)
    report["mouth_edge_h_range_cm"] = [round(float(h0.min()), 2), round(float(h0.max()), 2)]
    H = grid["h"]
    report["grid"] = {"nx": int(H.shape[0]), "ny": int(H.shape[1]), "verts": int(H.size),
                      "h_min_cm": round(float(H.min()), 2), "h_max_cm": round(float(H.max()), 2),
                      "r_mean": round(float(grid["r"].mean()), 3), "g_mean": round(float(grid["g"].mean()), 3),
                      "b_mean": round(float(grid["b"].mean()), 3), "sha256": grid_sha256(grid)}
    if float(H.min()) < -(115.0 - p["skirt_bottom_local_z"]):
        failures.append("DIP_BELOW_DECK_UNDERSIDE")
    if float(grid["g"].max()) > 1.0 or float(grid["r"].min()) < 0.0:
        failures.append("COLOUR_OUT_OF_RANGE")
    return failures, report


def with_set(name, p=PARAMS):
    q = copy.deepcopy(p)
    q["height_set"] = name
    return q


def write_height_sets(fp=None, path=HEIGHT_SETS_JSON):
    """A/B/C/D summary for the hand-print stream (measured from the same grids the FBX is built from)."""
    if fp is None:
        fp = load_footprint()
    out = {"schema": "s3_shore_height_sets/1",
           "frame": "heights in cm above S3 floor top (root-local z 115), measured at the marble inner faces "
                    "y=-999 / +999 and the backdrop plane x=5997",
           "rule": "min_print_line = ceil5(measured wall max + print_clearance_cm); prints must sit at or above it",
           "current_print_line_cm": fp["handprint_lowest_extent_above_floor_cm"]["value"],
           "recommended": PARAMS["height_set"], "sets": {}}
    for name in sorted(PARAMS["height_sets"]):
        q = with_set(name)
        g = build_grid(fp, q)
        fails, rep = checks(fp, q, g)
        s = height_set_summary(fp, q, g)
        s["checks_failures"] = fails
        s["realism"] = rep["realism"]
        s["cameras_min_vertical_clearance_cm"] = min(r["vertical_clearance_cm"] for r in rep["cameras"])
        s["grid_sha256"] = rep["grid"]["sha256"]
        out["sets"][name] = s
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    return out


if __name__ == "__main__":
    import sys
    import time
    t0 = time.time()
    fp = load_footprint()
    if "--sets" in sys.argv:
        o = write_height_sets(fp)
        for k, s in o["sets"].items():
            print(k, json.dumps({kk: s[kk] for kk in ("measured_wall_max_cm", "min_print_line_cm_above_floor_top",
                                                       "checks_failures", "realism")}))
    else:
        g = build_grid(fp)
        f, r = checks(fp, PARAMS, g)
        print(json.dumps(r, indent=1))
        print("FAILURES", f)
    print("seconds", round(time.time() - t0, 1))
