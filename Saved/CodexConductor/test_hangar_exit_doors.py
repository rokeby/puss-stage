"""Offline positive and required negative controls for hangar_exit_doors.py."""
import copy
import sys

from hangar_exit_doors import (
    DOOR_HEIGHT_CM,
    DOOR_WIDTH_CM,
    PlanError,
    plan_doors,
)


def fixture_probe(with_s3_backdrop=False):
    scenes = []
    for n in range(1, 7):
        depth = 15000.0 if n == 5 else 6000.0
        half_w = 10000.0 if n == 5 else 1000.0
        height = 5000.0 if n == 5 else 3000.0
        wall_t = 50.0
        backdrops = []
        if n == 3 and with_s3_backdrop:
            backdrops = [{
                "label": "S3 Backdrop",
                "bounds_dock_cm": {
                    "min": [depth - 5.0, -900.0, 0.0],
                    "max": [depth + 5.0, 900.0, 1200.0],
                },
            }]
        scenes.append({
            "scene": n,
            "root_count": 1,
            "landed_preview_root_up": True,
            "far_wall_count": 1,
            "far_walls": [{
                "label": "S%d Hangar Far Wall" % n,
                "components": [{
                    "static_mesh": "/Engine/BasicShapes/Cube.Cube",
                    "materials": [{"slot": 0, "material": "/Game/Test/M_Wall"}],
                }],
            }],
            "far_wall_union_bounds_dock_cm": {
                "min": [depth, -(half_w + wall_t), 0.0],
                "max": [depth + wall_t, half_w + wall_t, height],
            },
            "backdrops": backdrops,
            "backdrop_count": len(backdrops),
            "exit_camera_count": 1,
            "exit_cameras": [{"label": "Scene %d Exit Handoff Camera" % n}],
            "camera_to_door_distance_cm": depth - 100.0,
            "straight_walk": {"clear": n not in (3, 5), "blockers": [] if n not in (3, 5) else [
                {"label": "S%d Cast" % n}
            ]},
            "hangar": {
                "depth": depth, "half_w": half_w, "height": height,
                "wall_t": wall_t, "roof": n != 6, "hinge_z": 0.0,
            },
        })
    return {
        "schema_version": 1,
        "run": "fixture",
        "world": "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice",
        "census_before": {"content": [], "maps": []},
        "census_after": {"content": [], "maps": []},
        "scenes": scenes,
    }


def expect_failure(name, callback, text):
    try:
        callback()
    except PlanError as exc:
        if text not in str(exc):
            print("FAIL negative %s: wrong refusal %s" % (name, exc))
            return 1
        print("PASS negative %s: FAIL observed as required" % name)
        return 0
    print("FAIL negative %s: invalid input accepted" % name)
    return 1


def main():
    failures = 0
    plan = plan_doors(fixture_probe())
    leaves = [next(piece for piece in row["pieces"] if piece["role"] == "leaf")
              for row in plan["scenes"]]
    positive = (
        plan["apply_ready"] and len(plan["scenes"]) == 6 and
        all(piece["state"] == "closed" for piece in leaves) and
        all(abs(piece["size_cm"][1] - (DOOR_WIDTH_CM - 1.0)) < 1.0e-9 for piece in leaves) and
        all(abs(piece["size_cm"][2] - (DOOR_HEIGHT_CM - 1.0)) < 1.0e-9 for piece in leaves) and
        next(row for row in plan["scenes"] if row["scene"] == 5)["pieces"][0]["size_cm"][1] == 20100.0 and
        not next(row for row in plan["scenes"] if row["scene"] == 6)["roof"] and
        next(row for row in plan["scenes"] if row["scene"] == 3)["straight_walk"]["clear"] is False
    )
    if positive:
        print("PASS positive: six closed 3m x 4.5m doorway plans; S5 scale and roofless S6 retained")
    else:
        print("FAIL positive: unexpected plan %r" % plan)
        failures += 1

    blocked = plan_doors(fixture_probe(with_s3_backdrop=True))
    if (not blocked["apply_ready"] and blocked["open_questions"] == [{
            "scene": 3, "reason": "backdrop_uv_match_required",
            "backdrops": ["S3 Backdrop"], "draft_offset_y_cm": 0.0}]):
        print("PASS negative backdrop gate: S3 UV/offset remains an explicit open question")
    else:
        print("FAIL negative backdrop gate: %r" % blocked["open_questions"])
        failures += 1

    missing = fixture_probe()
    missing["scenes"].pop()
    failures += expect_failure("missing scene", lambda: plan_doors(missing), "scenes 1..6")

    duplicate = fixture_probe()
    duplicate["scenes"][0]["far_walls"].append(copy.deepcopy(
        duplicate["scenes"][0]["far_walls"][0]))
    failures += expect_failure("duplicate far wall", lambda: plan_doors(duplicate),
                               "far-wall count")

    changed = fixture_probe()
    changed["census_after"]["maps"] = ["/Game/Unexpected"]
    failures += expect_failure("probe changed census", lambda: plan_doors(changed),
                               "census changed")

    narrow = fixture_probe()
    failures += expect_failure(
        "offset outside wall",
        lambda: plan_doors(narrow, {"scenes": {"1": {"door_offset_y_cm": 1000.0}}}),
        "no side-wall margin",
    )

    if failures == 0:
        print("HANGAR_EXIT_DOORS_HARNESS_OK|positive=1|negative=5|scenes=6|state=closed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
