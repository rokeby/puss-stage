"""Seat report: every standing object (LIVE DRY read) vs the NEW shore surface under its footprint.

python Saved/CodexConductor/S3Shore/s3_shore_seat_report.py
  -> Saved/CodexConductor/S3Shore/s3_shore_seat_report.json

Inputs: s3_shore_live_reads.json (DRY run S3SHORE-20261007-181646, root-local cm, LANDED) and the mesh grid
from s3_shore_field.build_grid() (the same arrays the FBX is built from; surface sampled bilinearly between
grid vertices, i.e. within the 7.5 cm cell -- the triangulated mesh can differ from bilinear by < ~0.3 cm on
the ripples [inf: ripple amplitude 1.2 cm over a 42 cm wavelength]).

Footprint = the object's LIVE local AABB in XY (for draped figures this includes the drape, so it is wider than
the feet).  Base = figure foot_local_z (AABB min z) / prop AABB min z.
Verdict on the MEAN surface under the footprint:
  FLOATING  base - mean > +2 cm      BURIED  mean - base > +2 cm      OK otherwise.
Also reported: base vs min/max (touches_somewhere = base <= max surface).
Objects are NOT moved (Gary 7 Oct: he re-arranges them himself).
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s3_shore_field as F  # noqa: E402

LIVE = os.path.join(HERE, "s3_shore_live_reads.json")
OUT = os.path.join(HERE, "s3_shore_seat_report.json")
TOL_CM = 2.0
STEP_CM = 5.0


class Surface:
    def __init__(self, grid):
        self.xs, self.ys, self.z = grid["xs"], grid["ys"], 115.0 + grid["h"]

    def __call__(self, x, y):
        xs, ys, z = self.xs, self.ys, self.z
        x = np.clip(x, xs[0], xs[-1])
        y = np.clip(y, ys[0], ys[-1])
        i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
        j = np.clip(np.searchsorted(ys, y) - 1, 0, len(ys) - 2)
        tx = (x - xs[i]) / (xs[i + 1] - xs[i])
        ty = (y - ys[j]) / (ys[j + 1] - ys[j])
        return ((z[i, j] * (1 - tx) + z[i + 1, j] * tx) * (1 - ty) + (z[i, j + 1] * (1 - tx) + z[i + 1, j + 1] * tx) * ty)


def objects_from_live(live):
    rows = []
    for label, f in sorted(live["figures"].items()):
        rows.append({"label": label, "kind": "figure", "base_local_z": f["foot_local_z"], "aabb": f["local_aabb"],
                     "pivot_local_xy": f["local"], "parent": f.get("parent")})
    for label, a in sorted(live["actors"].items()):
        if label == "Clam_Pedastal":
            rows.append({"label": label, "kind": "pedestal", "base_local_z": a["local_aabb"]["min"][2],
                         "aabb": a["local_aabb"], "parent": a.get("parent"), "hidden_in_game": a.get("hidden_in_game")})
        elif label.startswith("S3 Beach V2 Rock") or label.startswith("S3 Beach V2 Seaweed"):
            rows.append({"label": label, "kind": "rock" if "Rock" in label else "seaweed",
                         "base_local_z": a["local_aabb"]["min"][2], "aabb": a["local_aabb"]})
    return rows


def verdict(base, mean, tol=TOL_CM):
    if base - mean > tol:
        return "FLOATING"
    if mean - base > tol:
        return "BURIED"
    return "OK"


def seat_rows(objects, surface, tol=TOL_CM, step=STEP_CM):
    out = []
    for o in objects:
        lo, hi = o["aabb"]["min"], o["aabb"]["max"]
        nx = max(2, int(np.ceil((hi[0] - lo[0]) / step)) + 1)
        ny = max(2, int(np.ceil((hi[1] - lo[1]) / step)) + 1)
        X, Y = np.meshgrid(np.linspace(lo[0], hi[0], nx), np.linspace(lo[1], hi[1], ny), indexing="ij")
        Z = surface(X, Y)
        base = float(o["base_local_z"])
        mn, mx, me = float(Z.min()), float(Z.max()), float(Z.mean())
        row = {k: v for k, v in o.items() if k not in ("aabb",)}
        row.update({
            "footprint_local_xy": [[round(lo[0], 1), round(lo[1], 1)], [round(hi[0], 1), round(hi[1], 1)]],
            "footprint_samples": int(Z.size),
            "base_local_z": round(base, 3),
            "surface_local_z": {"min": round(mn, 3), "max": round(mx, 3), "mean": round(me, 3)},
            "gap_vs_mean_cm": round(base - me, 3),
            "gap_vs_max_cm": round(base - mx, 3),
            "touches_somewhere": base <= mx,
            "verdict": verdict(base, me, tol),
        })
        out.append(row)
    return out


def build(live_path=LIVE, out_path=OUT, grid=None):
    live = json.load(open(live_path, encoding="utf-8"))
    if grid is None:
        grid = F.build_grid()
    surf = Surface(grid)
    rows = seat_rows(objects_from_live(live), surf)
    report = {
        "schema": "s3_shore_seat_report/1",
        "live_reads_run": live.get("run"),
        "frame": "S3 Hangar Root local cm, LANDED; floor top z 115",
        "rule": "verdict on mean surface under the live XY AABB: FLOATING base-mean>2, BURIED mean-base>2, else OK",
        "params": {"preserve_v2_cast": F.PARAMS["preserve_v2_cast"], "use_pads": F.PARAMS["use_pads"],
                   "grid_cm": F.PARAMS["grid_cm"], "seed": F.PARAMS["seed"]},
        "counts": {v: sum(r["verdict"] == v for r in rows) for v in ("OK", "FLOATING", "BURIED")},
        "rows": rows,
        "note": "Objects are not moved; Gary re-arranges them. Rocks/seaweed were deliberately embedded 12-40% in v2 sand "
                "(s3_beach_v2.py:80-89), so BURIED there may be intended; figures and the pedestal stand ON the ground.",
    }
    with open(out_path, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1)
    return report


if __name__ == "__main__":
    r = build()
    print("S3SHORE_SEAT", json.dumps(r["counts"]))
    for row in r["rows"]:
        s = row["surface_local_z"]
        print("%-26s %-8s base %7.2f  surf min %7.2f max %7.2f mean %7.2f  gap %+6.2f  %s" % (
            row["label"], row["kind"], row["base_local_z"], s["min"], s["max"], s["mean"], row["gap_vs_mean_cm"], row["verdict"]))
