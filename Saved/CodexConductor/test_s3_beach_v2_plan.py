"""Offline positive and negative controls for the S3 beach-v2 contract."""
import copy
import sys

from s3_beach_v2 import (CAMERA_CLEARANCE_CM, CLEAN_CENSUS, FIGURE_LABELS,
                         OBJ_WRITE_CONVENTION, PROP_SPECS, SAND_ASSET, PlanError,
                         apply_sequence, build_sand_mesh, classify_sand_bounds,
                         expected_sand_bounds, obj_text, obj_to_ue, plan_prop,
                         sand_height, validate_imported_sand_bounds,
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


def obj_readback_bounds(mesh, editor_mapping):
    """Parse the OBJ text the tool writes and map it the way a given editor would."""
    points = []
    for line in obj_text(mesh).splitlines():
        if line.startswith("v "):
            points.append(obj_to_ue([float(value) for value in line.split()[1:4]], editor_mapping))
    return {"min": [min(point[axis] for point in points) for axis in range(3)],
            "max": [max(point[axis] for point in points) for axis in range(3)]}


class FakeOps(object):
    """Records apply_sequence's call order; simulates the editor's import result."""
    DESTRUCTIVE = ("write_pending", "destroy_legacy", "spawn_v2", "raise_figures",
                   "save_level", "commit")

    def __init__(self, mesh, editor_mapping=OBJ_WRITE_CONVENTION, extra_dirty=()):
        self.mesh, self.editor_mapping, self.extra_dirty = mesh, editor_mapping, list(extra_dirty)
        self.calls, self.dirty, self.saved = [], [], False

    def _log(name):
        def method(self, *args):
            self.calls.append(name)
        return method

    preflight = _log("preflight")
    backup = _log("backup")
    write_pending = _log("write_pending")
    destroy_legacy = _log("destroy_legacy")
    spawn_v2 = _log("spawn_v2")
    raise_figures = _log("raise_figures")
    save_level = _log("save_level")
    commit = _log("commit")

    def import_sand(self, mesh_plan):
        self.calls.append("import_sand")
        self.dirty = [SAND_ASSET] + self.extra_dirty

    def sand_bounds(self):
        self.calls.append("sand_bounds")
        return obj_readback_bounds(self.mesh, self.editor_mapping)

    def census(self):
        self.calls.append("census")
        return {"maps": [], "content": sorted(self.dirty)}

    def save_sand(self):
        self.calls.append("save_sand")
        self.dirty = [name for name in self.dirty if name != SAND_ASSET]
        self.saved = True

    def cleanup_unsaved_new(self):
        self.calls.append("cleanup_unsaved_new")
        deleted = [name for name in self.dirty if not (self.saved and name == SAND_ASSET)]
        self.dirty = []
        return {"deleted": deleted, "kept": {}}

    def destructive_calls(self):
        return [name for name in self.calls if name in self.DESTRUCTIVE]


def sequence_stop(name, ops, contains):
    try:
        apply_sequence(ops, ops.mesh)
    except PlanError as exc:
        text = str(exc)
        if contains not in text or "PRE_DESTRUCTIVE_STOP|level_untouched" not in text:
            print("FAIL negative %s: wrong refusal %s" % (name, text[:300]))
            return 1
        if ops.destructive_calls():
            print("FAIL negative %s: destructive steps ran before STOP: %s" % (name, ops.destructive_calls()))
            return 1
        if "cleanup_unsaved_new" not in ops.calls:
            print("FAIL negative %s: no cleanup of never-saved packages" % name)
            return 1
        print("PASS negative %s: STOP before any destructive step; calls=%s" % (name, ",".join(ops.calls)))
        return 0
    print("FAIL negative %s: sequence completed" % name)
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

    # --- Review risk 1: sand orientation is explicit and verified. ---
    text = obj_text(mesh)
    if "usemtl" in text or "mtllib" in text:
        print("FAIL positive: OBJ still carries a material reference"); failures += 1
    else:
        print("PASS positive: OBJ has no usemtl/mtllib")
    expected = expected_sand_bounds(mesh)
    unique = classify_sand_bounds(mesh, expected)
    if unique != [OBJ_WRITE_CONVENTION]:
        print("FAIL positive: bounds do not identify the axis mapping uniquely: %s" % unique); failures += 1
    else:
        print("PASS positive: of 48 signed axis mappings only %s yields the planned bbox %s" %
              (OBJ_WRITE_CONVENTION, expected))
    try:
        validate_imported_sand_bounds(mesh, obj_readback_bounds(mesh, OBJ_WRITE_CONVENTION))
        print("PASS positive: OBJ parsed back under the assumed mapping passes the bounds gate")
    except PlanError as exc:
        print("FAIL positive: correct import refused: %s" % exc); failures += 1
    failures += reject("vertical sand (editor keeps OBJ XYZ)",
                       lambda: validate_imported_sand_bounds(mesh, obj_readback_bounds(mesh, "+x,+y,+z")),
                       'matches=["+x,+y,+z"]')
    failures += reject("Y-mirrored sand (editor swaps Y/Z without flip)",
                       lambda: validate_imported_sand_bounds(mesh, obj_readback_bounds(mesh, "+x,+z,+y")),
                       "SAND_BOUNDS_MISMATCH")
    failures += reject("sand imported in metres (x100)",
                       lambda: validate_imported_sand_bounds(
                           mesh, {key: [100.0 * v for v in value] for key, value in expected.items()}),
                       "SAND_BOUNDS_MISMATCH")

    # --- Review risk 2: no half-apply; risky steps precede destruction. ---
    ops = FakeOps(mesh)
    apply_sequence(ops, mesh)
    order = ["preflight", "backup", "import_sand", "sand_bounds", "census", "save_sand", "census",
             "write_pending", "destroy_legacy", "spawn_v2", "raise_figures", "save_level", "commit"]
    if ops.calls != order:
        print("FAIL positive: apply order %s" % ops.calls); failures += 1
    else:
        print("PASS positive: normal APPLY order " + ",".join(ops.calls))
    failures += sequence_stop("unexpected material package dirtied by import",
                              FakeOps(mesh, extra_dirty=[SAND_ASSET.rsplit("/", 1)[0] + "/Sand"]),
                              "unexpected_content=" + SAND_ASSET.rsplit("/", 1)[0] + "/Sand")
    failures += sequence_stop("vertical sand import",
                              FakeOps(mesh, editor_mapping="+x,+y,+z"), "SAND_BOUNDS_MISMATCH")

    if failures == 0:
        print("S3_BEACH_V2_HARNESS_OK|positive=6|negative=11|actors=9|figures=6|triangles=%d|min_camera_cm=%.3f" %
              (len(mesh["faces"]), mesh["min_camera_clearance_cm"]))
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
