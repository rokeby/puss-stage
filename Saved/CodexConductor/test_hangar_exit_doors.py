"""Offline positive and required negative controls for hangar_exit_doors.py."""
import copy
import math
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
        root_yaw = -43.57 if n == 2 else 0.0
        root_location = [10000.0 * n, 20000.0 * n, 0.0]
        radians = math.radians(root_yaw)
        wall_root_location = [depth + wall_t / 2.0, 0.0, height / 2.0]
        wall_world_location = [
            root_location[0] + math.cos(radians) * wall_root_location[0],
            root_location[1] + math.sin(radians) * wall_root_location[0],
            wall_root_location[2],
        ]
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
                "transform": {
                    "world_location_cm": wall_world_location,
                    "world_rotation_rpy": [0.0, 0.0, root_yaw],
                    "world_scale": [wall_t / 100.0, 2.0 * (half_w + wall_t) / 100.0,
                                    height / 100.0],
                },
                "components": [{
                    "static_mesh": "/Engine/BasicShapes/Cube.Cube",
                    "static_mesh_local_bounds_cm": {
                        "min": [-50.0, -50.0, -50.0],
                        "max": [50.0, 50.0, 50.0],
                    },
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
            "root": {
                "transform": {
                    "world_location_cm": root_location,
                    "world_rotation_rpy": [0.0, 0.0, root_yaw],
                    "world_scale": [1.0, 1.0, 1.0],
                },
            },
        })
        if n == 2:
            # Deliberately emulate the inflated world AABB from the real
            # yaw=-43.57 probe.  The oriented root-frame mesh bounds must win.
            scenes[-1]["far_wall_union_bounds_dock_cm"] = {
                "min": [4951.303, -1074.969, 0.0],
                "max": [7098.697, 1074.969, 3000.0],
            }
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

    rotated = next(row for row in plan["scenes"] if row["scene"] == 2)
    rotated_bounds = rotated["wall_bounds_root_cm"]
    if (rotated["piece_coordinate_frame"] == "hangar_root" and
            all(abs(value - expected) < 0.01 for value, expected in zip(
                [rotated_bounds["max"][axis] - rotated_bounds["min"][axis]
                 for axis in range(3)], [50.0, 2100.0, 3000.0]))):
        print("PASS positive rotated hangar: S2 yaw -43.57 uses 50 x 2100 x 3000 root-frame bounds")
    else:
        print("FAIL positive rotated hangar: %r" % rotated)
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

    wrong_size = fixture_probe()
    wrong_size["scenes"][3]["far_walls"][0]["transform"]["world_scale"][1] = 22.0
    failures += expect_failure(
        "genuinely wrong-sized wall",
        lambda: plan_doors(wrong_size),
        "far-wall size disagrees with the builder",
    )

    if failures == 0:
        print("HANGAR_EXIT_DOORS_HARNESS_OK|positive=2|negative=6|scenes=6|state=closed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
