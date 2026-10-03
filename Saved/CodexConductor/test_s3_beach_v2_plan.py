"""Offline positive and negative controls for the S3 beach-v2 contract."""
import copy
import sys

from s3_beach_v2 import (CAMERA_CLEARANCE_CM, FIGURE_LABELS, PROP_SPECS,
                         PlanError, build_sand_mesh, plan_prop, sand_height,
                         validate_v2_plan)


CAMERAS = [
    {"label": "S3 Shot B02", "location": [2700.0, -250.0, 170.0]},
    {"label": "S3 Shot B03", "location": [3050.0, 40.0, 160.0]},
    {"label": "S3 Shot B04", "location": [3500.0, -750.0, 120.0]},
    {"label": "S3 Shot B05", "location": [3200.0, 0.0, 140.0]},
    {"label": "S3 Shot B06", "location": [3380.0, 0.0, 115.0]},
    {"label": "S3 Shot B07", "location": [3300.0, 60.0, 120.0]},
    {"label": "S3 Shot B08", "location": [3360.0, -40.0, 110.0]},
    {"label": "S3 Shot B09", "location": [2600.0, 0.0, 170.0]},
    {"label": "S3 Shot B10", "location": [2600.0, 0.0, 170.0]},
    {"label": "S3 Shot B11", "location": [3420.0, 0.0, 105.0]},
    {"label": "S3 Shot B12", "location": [3420.0, 0.0, 105.0]},
]

FIGURE_XY = ((3649.13, -212.98), (3199.30, 109.45), (3390.55, 300.70),
             (3683.54, 262.13), (3411.07, -244.32), (3760.0, 0.0))

LOCAL_BOUNDS = {
    "03_Flat_Rock": {"min": [-59.61, -56.81, -1.69], "max": [56.03, 56.78, 39.88]},
    "05_Rock": {"min": [-58.09, -44.40, -8.60], "max": [53.93, 48.32, 49.74]},
    "13_Granite": {"min": [-31.32, -30.19, -6.72], "max": [33.69, 33.12, 36.58]},
    "20_Mossy": {"min": [-46.70, -29.97, -3.46], "max": [45.31, 34.08, 29.33]},
    "09_Rock": {"min": [-23.06, -14.52, -0.98], "max": [21.95, 13.55, 20.28]},
    "SM_SeaweedA": {"min": [-88.28, -45.05, -5.74], "max": [65.64, 48.62, 135.84]},
    "SM_SeaweedB": {"min": [-103.09, -115.41, -6.60], "max": [106.43, 101.05, 104.42]},
}


def bounds_for(spec):
    for token, bounds in LOCAL_BOUNDS.items():
        if token in spec["mesh_path"]:
            return copy.deepcopy(bounds)
    raise AssertionError(spec["mesh_path"])


def fixture():
    mesh = build_sand_mesh(CAMERAS)
    props = [plan_prop(spec, bounds_for(spec), CAMERAS) for spec in PROP_SPECS]
    figures = []
    for label, xy in zip(FIGURE_LABELS, FIGURE_XY):
        surface = sand_height(*xy)
        before_foot = -28.0
        figures.append({"label": label, "dock_xy": list(xy),
                        "surface_z_cm": surface, "raise_cm": surface - before_foot,
                        "planned_foot_z_cm": surface})
    return mesh, props, figures


def reject(name, function, contains):
    try:
        function()
    except PlanError as exc:
        if contains not in str(exc):
            print("FAIL negative %s: wrong refusal %s" % (name, exc))
            return 1
        print("PASS negative %s: STOP observed as required" % name)
        return 0
    print("FAIL negative %s: invalid plan accepted" % name)
    return 1


def main():
    failures = 0
    mesh, props, figures = fixture()
    validate_v2_plan(mesh, props, figures, CAMERAS, {})
    rock_embeds = [row["embedded_fraction"] for row in props if row["kind"] == "rock"]
    if (mesh["min_camera_clearance_cm"] >= CAMERA_CLEARANCE_CM and len(mesh["faces"]) > 500 and
            min(rock_embeds) >= 0.20 and max(rock_embeds) <= 0.40 and len(figures) == 6):
        print("PASS positive: shaped sand, 1.5 m camera cutouts, embedded rocks, seaweed, six feet on surface")
    else:
        print("FAIL positive: beach-v2 metrics are incomplete")
        failures += 1

    bad = copy.deepcopy(mesh); bad["min_camera_clearance_cm"] = 149.0
    failures += reject("sand in camera exclusion",
                       lambda: validate_v2_plan(bad, props, figures, CAMERAS, {}),
                       "sand enters")
    bad_props = copy.deepcopy(props); bad_props[0]["embedded_fraction"] = 0.10
    failures += reject("rock not embedded 20-40 percent",
                       lambda: validate_v2_plan(mesh, bad_props, figures, CAMERAS, {}),
                       "embed")
    bad_figures = copy.deepcopy(figures); bad_figures[0]["raise_cm"] = 120.0
    failures += reject("unsafe figure lift",
                       lambda: validate_v2_plan(mesh, props, bad_figures, CAMERAS, {}),
                       "unsafe vertical")
    failures += reject("v2 label collision",
                       lambda: validate_v2_plan(mesh, props, figures, CAMERAS,
                                                {props[0]["label"]: 1}),
                       "already exist")
    failures += reject("no live cameras",
                       lambda: validate_v2_plan(mesh, props, figures, [], {}),
                       "no S3 Shot cameras")
    bad_figures = copy.deepcopy(figures); bad_figures[0]["dock_xy"] = [5000.0, 0.0]
    failures += reject("figure feet outside sand",
                       lambda: validate_v2_plan(mesh, props, bad_figures, CAMERAS, {}),
                       "outside the sand")
    if failures == 0:
        print("S3_BEACH_V2_HARNESS_OK|positive=1|negative=6|actors=9|figures=6|triangles=%d|min_camera_cm=%.3f" %
              (len(mesh["faces"]), mesh["min_camera_clearance_cm"]))
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
