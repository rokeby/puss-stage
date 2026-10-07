"""Standing-stone proposal on the FINAL shore field (offline; no Unreal).

python Saved/CodexConductor/S3Shore/s3_shore_standing_stones.py
  -> Saved/CodexConductor/S3Shore/standing_stones_proposal.json

Gary 7 Oct (via the Blender session): 2-3 SM_HoledStandingStone (143.7 x 102.7 x 330 cm, pivot 30 cm above the
root bottom), HALF-BURIED in the dunes toward the box edges.  Pivot = local dune surface (HIGH side of the
rotated 144 x 103 footprint, so it never floats) - 135 cm.  Through-hole ~234 cm above the root bottom
(= 204 cm above the pivot), faces +-Y of the stone's local frame; it must read from the main S3 camera on at
least one stone.  Clear of the millstone seat, the cast area, the wave notches and the door corridor.

Row format follows Saved/CodexConductor/S3Millstone/s3_props_placements.json (plan_place, s3_props_ue.py:495-530):
{prop, label, xy_root_local, yaw_deg, burial_cm, floor_radius_cm, reveal, mobility}.  burial_cm there is
"pivot below the MEDIAN floor sampled within floor_radius_cm" (s3_props_ue.py:513-514), so it is computed here
as median(surface within floor_radius) - wanted pivot.  LEAN: plan_place writes rotation [0, 0, yaw]
(s3_props_ue.py:515) -- roll/pitch are NOT applied by that tool; they are carried as extra fields
(lean_roll_deg / lean_pitch_deg) for the props stream to add.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s3_shore_field as F  # noqa: E402

OUT = os.path.join(HERE, "standing_stones_proposal.json")
STONE = {"size_cm": [143.65, 102.73, 330.0], "pivot_above_root_bottom_cm": 30.0, "hole_above_root_bottom_cm": 234.0,
         "hole_axis_local": "+-Y", "src": "DerivedAssets/HoledStandingStone/Export/SM_HoledStandingStone_manifest.json"}
BURY_BELOW_HIGH_SIDE_CM = 135.0
FLOOR_RADIUS_CM = 45.0
MAIN_CAM = {"local": [3000.03, -750.0, 240.0], "yaw": 75.5, "pitch": -5.5, "hfov": 37.5}

# candidates (root-local xy, yaw, roll, pitch).  Yaw ~0 puts the hole axis (local Y) along world Y, i.e. facing the
# main camera, which looks toward +Y.
CANDIDATES = [
    {"label": "S3 Standing Stone A", "xy": [3330.0, 760.0], "yaw": 6.0, "roll": 4.0, "pitch": -2.5,
     "why": "right-wall dunes inside the MAIN camera frame; hole axis within ~20 deg of the view ray"},
    {"label": "S3 Standing Stone B", "xy": [4930.0, -780.0], "yaw": 68.0, "roll": -3.0, "pitch": 5.0,
     "why": "left-wall dunes between wave rows 2 and 3, back half of the box"},
    {"label": "S3 Standing Stone C", "xy": [1420.0, 780.0], "yaw": -38.0, "roll": 5.5, "pitch": 2.0,
     "why": "right-wall dunes toward the mouth, seen past the cast from the entry side"},
]


def footprint_points(x, y, yaw, step=7.5):
    hx, hy = STONE["size_cm"][0] / 2.0, STONE["size_cm"][1] / 2.0
    us = np.arange(-hx, hx + 0.01, step)
    vs = np.arange(-hy, hy + 0.01, step)
    U, V = np.meshgrid(us, vs, indexing="ij")
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return x + U * c - V * s, y + U * s + V * c


def keepouts(fp, x, y, yaw):
    """Distance checks (cm) of the rotated footprint against every keep-out.  Returns {name: (ok, detail)}."""
    X, Y = footprint_points(x, y, yaw)
    out = {}
    ms = fp["millstone_seat"]
    d = float(np.min(np.hypot(X - ms["local_xy"][0], Y - ms["local_xy"][1])))
    out["millstone_seat_plus_blend"] = (d > ms["radius_cm"] + ms["blend_cm"] + 60.0, round(d, 1))
    # cast area: live figure / pedestal / prop AABBs (DRY S3SHORE-20261007-181646) grown by 150 cm
    live = json.load(open(os.path.join(HERE, "s3_shore_live_reads.json"), encoding="utf-8"))
    boxes = [f["local_aabb"] for f in live["figures"].values()] + [
        a["local_aabb"] for k, a in live["actors"].items()
        if k == "Clam_Pedastal" or k.startswith("S3 Beach V2 Rock") or k.startswith("S3 Beach V2 Seaweed")]
    xmin = min(b["min"][0] for b in boxes) - 150.0
    xmax = max(b["max"][0] for b in boxes) + 150.0
    ymin = min(b["min"][1] for b in boxes) - 150.0
    ymax = max(b["max"][1] for b in boxes) + 150.0
    inside = (X > xmin) & (X < xmax) & (Y > ymin) & (Y < ymax)
    out["cast_area_aabb_plus_150"] = (not bool(inside.any()), [round(xmin), round(xmax), round(ymin), round(ymax)])
    p = F.PARAMS
    notch_ok = True
    for row in fp["wave_rows"]["rows"]:
        cx = 0.5 * (row["x"][0] + row["x"][1])
        if float(np.min(np.abs(X - cx))) < F.notch_half(row, p) + p["wave_notch_blend_cm"]:
            notch_ok = False
    out["wave_notches_plus_blend"] = (notch_ok, None)
    rows = fp["wave_rows"]["rows"]
    x0 = max(0.5 * (r["x"][0] + r["x"][1]) + F.notch_half(r, p) for r in rows)
    door = (X > x0 - 50.0) & (np.abs(Y) < p["constraints"]["door_corridor_halfwidth_cm"] + 100.0)
    out["door_corridor_plus_100"] = (not bool(door.any()), None)
    yl = fp["walls"]["left_inner_face_y"]["value"]
    yr = fp["walls"]["right_inner_face_y"]["value"]
    out["inside_side_walls_by_10"] = (bool((Y > yl + 10).all() and (Y < yr - 10).all()),
                                      [round(float(Y.min()), 1), round(float(Y.max()), 1)])
    return out


def in_main_frame(x, y, z):
    cx, cy, cz = MAIN_CAM["local"]
    yaw = math.degrees(math.atan2(y - cy, x - cx))
    dist = math.hypot(x - cx, y - cy)
    elev = math.degrees(math.atan2(z - cz, dist))
    vfov = 2 * math.degrees(math.atan(math.tan(math.radians(MAIN_CAM["hfov"] / 2)) * 9.0 / 16.0))
    dyaw = yaw - MAIN_CAM["yaw"]
    return (abs(dyaw) < MAIN_CAM["hfov"] / 2 - 2.0 and abs(elev - MAIN_CAM["pitch"]) < vfov / 2 - 1.0,
            round(dyaw, 1), round(elev - MAIN_CAM["pitch"], 1), round(dist, 0), round(yaw, 1))


def build():
    fp = F.load_footprint()
    grid = F.build_grid(fp)
    rows, report = [], []
    for c in CANDIDATES:
        x, y = c["xy"]
        X, Y = footprint_points(x, y, c["yaw"])
        hs = F.interp2(grid["xs"], grid["ys"], grid["h"], X, Y)
        hi, lo = float(hs.max()), float(hs.min())
        Xr, Yr = np.meshgrid(np.linspace(x - FLOOR_RADIUS_CM, x + FLOOR_RADIUS_CM, 13),
                             np.linspace(y - FLOOR_RADIUS_CM, y + FLOOR_RADIUS_CM, 13), indexing="ij")
        disc = np.hypot(Xr - x, Yr - y) <= FLOOR_RADIUS_CM
        med = float(np.median(F.interp2(grid["xs"], grid["ys"], grid["h"], Xr[disc], Yr[disc])))
        pivot_h = hi - BURY_BELOW_HIGH_SIDE_CM                       # above floor top
        burial = med - pivot_h
        hole_h = pivot_h + STONE["hole_above_root_bottom_cm"] - STONE["pivot_above_root_bottom_cm"]
        hole_local_z = 115.0 + hole_h
        frame = in_main_frame(x, y, hole_local_z)
        cam = MAIN_CAM["local"]
        view_yaw = math.degrees(math.atan2(y - cam[1], x - cam[0]))
        hole_axis_yaw = c["yaw"] + 90.0                              # local +Y in world
        off = (view_yaw - hole_axis_yaw + 90.0) % 180.0 - 90.0     # +-Y: either face
        ko = keepouts(fp, x, y, c["yaw"])
        ok = all(v[0] for v in ko.values()) and hi - lo < 165.0
        rows.append({
            "prop": "HoledStandingStone", "label": c["label"], "xy_root_local": [x, y], "yaw_deg": c["yaw"],
            "burial_cm": round(burial, 1), "floor_radius_cm": FLOOR_RADIUS_CM, "reveal": "rise_track",
            "mobility": "STATIC",
            "lean_roll_deg": c["roll"], "lean_pitch_deg": c["pitch"],
            "lean_note": "NOT applied by s3_props_ue.plan_place (rotation = [0,0,yaw], s3_props_ue.py:515)",
        })
        report.append({
            "label": c["label"], "why": c["why"], "keepouts_ok": ok, "keepouts": {k: v[1] for k, v in ko.items()},
            "keepout_pass": {k: v[0] for k, v in ko.items()},
            "surface_under_footprint_cm": {"high": round(hi, 1), "low": round(lo, 1),
                                           "median_r45": round(med, 1)},
            "pivot_above_floor_top_cm": round(pivot_h, 1), "pivot_root_local_z": round(115.0 + pivot_h, 1),
            "stone_buried_below_high_side_cm": BURY_BELOW_HIGH_SIDE_CM + STONE["pivot_above_root_bottom_cm"],
            "stone_buried_below_low_side_cm": round(lo - (pivot_h - STONE["pivot_above_root_bottom_cm"]), 1),
            "visible_above_high_side_cm": round(STONE["size_cm"][2] - BURY_BELOW_HIGH_SIDE_CM
                                                - STONE["pivot_above_root_bottom_cm"], 1),
            "hole_centre_above_high_side_cm": round(hole_h - hi, 1), "hole_root_local_z": round(hole_local_z, 1),
            "main_camera": {"hole_in_frame": frame[0], "d_yaw_from_centre_deg": frame[1],
                            "d_elev_from_centre_deg": frame[2], "distance_cm": frame[3],
                            "hole_axis_off_view_ray_deg": round(off, 1)},
        })
    out = {"schema": "s3_props_placements/1 (rows) + s3_shore report",
           "note": "Proposal only (offline).  Copy 'placements' into S3Millstone/s3_props_placements.json to use; "
                   "PLACE re-measures the floor live, so burial_cm reproduces pivot = high-side surface - 135 cm only "
                   "if the shore ground is applied as built (grid sha below).",
           "field_grid_sha256": F.grid_sha256(grid), "height_set": F.PARAMS["height_set"],
           "stone": STONE, "rule": "pivot = max surface under the rotated 144x103 footprint - 135 cm",
           "if_only_two": ["S3 Standing Stone A", "S3 Standing Stone B"],
           "placements": rows, "report": report}
    with open(OUT, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    return out


if __name__ == "__main__":
    o = build()
    for r in o["report"]:
        print(r["label"], r["keepouts_ok"], r["keepout_pass"], r["surface_under_footprint_cm"], r["main_camera"],
              "hole above high", r["hole_centre_above_high_side_cm"])
