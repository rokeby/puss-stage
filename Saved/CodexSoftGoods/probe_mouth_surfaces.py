"""READ-ONLY (30 Sep): what surfaces lie under the shared drape's pile at each mouth, in each mouth's ROUTE frame?

The drape cache (final13) is world-true for P01's stage front; each Interaction places it at a Passage's route start,
yawed to the route's start tangent. So every mouth is measured in its own route frame (x along the route from the curtain
line, y across), over the pile footprint (x -200..+470 cm, y +-1100). P02's mouth is rotated 22.9 deg, so world-axis boxes
would be wrong there (the Conductor's warning): every mesh is taken as its LOCAL bounds carried through its own
transform into the route frame, which is exact for pieces aligned with the route.

Surfaces only: the instances of every InstancedStaticMeshComponent and every plain StaticMeshComponent (lights, skies and
rigs are not surfaces). For each mouth:
  - the instance groups overlapping the footprint (count, x range, top and bottom z);
  - a SURFACE-TOP map on a 25 x 50 cm grid, the highest top among LOW pieces (top <= 150 cm, so posts and walls are
    excluded), summarised per x band;
  - the spill check: in the house-side band (x -200..-155) the top must be BELOW -72 cm, since the cache's spill hangs
    to z -71.3 within 1.9 m of the curtain line (final13, measured). P01, the reference, reads -120.
NOTHING IS SAVED OR MODIFIED: there is no save call in this file. Writes probe_mouth_surfaces.json; logs
PUSS_SOFTGOODS_MOUTH_SURFACES|... Crash rules: everything inside main().
"""
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
# Route starts and start-tangent yaws: fit_transition_drapes' mouths (P02-P06) and the Opening's P01.
MOUTHS = {"P01": (0.0, 0.0, 0.0), "P02": (0.0, 80000.0, 22.908), "P03": (0.0, 160000.0, 0.0),
          "P04": (0.0, 240000.0, 0.0), "P05": (0.0, 320000.0, 0.0), "P06": (0.0, 400000.0, 0.0)}
FOOT_X, FOOT_Y, LOW_TOP, NEAR_CM, SPILL_Z = (-200.0, 470.0), (-1100.0, 1100.0), 150.0, 3000.0, -72.0
BANDS = [(-200, -155, "house side"), (-155, -115, "lip/fascia line"), (-115, 0, "forestage"), (0, 250, "mouth"),
         (250, 471, "beyond the mouth")]


def to_route(p, m):
    """World point (UE cm) -> the mouth's route frame (x along the route, y across, z up)."""
    mx, my, yaw = m
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    dx, dy = p.x - mx, p.y - my
    return (dx * c + dy * s, -dx * s + dy * c, p.z)


def route_box(transform, lo_l, hi_l, m):
    pts = [to_route(transform.transform_location(unreal.Vector(x, y, z)), m)
           for x in (lo_l.x, hi_l.x) for y in (lo_l.y, hi_l.y) for z in (lo_l.z, hi_l.z)]
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


def main():
    dirty0 = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    out = {"dirty_before": dirty0, "spill_limit_z_cm": SPILL_Z, "mouths": {}}
    for tag, m in MOUTHS.items():
        boxes, groups = [], {}
        for a in actors:
            try:
                o, e = a.get_actor_bounds(False)
            except Exception:  # noqa: BLE001
                continue
            if abs(o.x - m[0]) - e.x > NEAR_CM or abs(o.y - m[1]) - e.y > NEAR_CM:
                continue                                   # nowhere near this mouth
            for comp in a.get_components_by_class(unreal.StaticMeshComponent):
                mesh = comp.get_editor_property("static_mesh")
                if mesh is None:
                    continue
                b = mesh.get_bounds()
                lo_l, hi_l = b.origin - b.box_extent, b.origin + b.box_extent
                if isinstance(comp, unreal.InstancedStaticMeshComponent):
                    transforms = [comp.get_instance_transform(i, True) for i in range(comp.get_instance_count())]
                else:
                    transforms = [comp.get_world_transform()]
                for t in transforms:
                    loc = t.translation
                    if abs(loc.x - m[0]) > 60000 or abs(loc.y - m[1]) > 60000:
                        continue
                    lo, hi = route_box(t, lo_l, hi_l, m)
                    if hi[0] < FOOT_X[0] or lo[0] > FOOT_X[1] or hi[1] < FOOT_Y[0] or lo[1] > FOOT_Y[1] \
                            or hi[2] < -400 or lo[2] > 400:
                        continue
                    key = f"{a.get_actor_label()} / {comp.get_name()}"
                    g = groups.setdefault(key, {"count": 0, "x": [1e9, -1e9], "top_z": [1e9, -1e9], "mesh": mesh.get_name()})
                    g["count"] += 1
                    g["x"] = [round(min(g["x"][0], lo[0]), 1), round(max(g["x"][1], hi[0]), 1)]
                    g["top_z"] = [round(min(g["top_z"][0], hi[2]), 2), round(max(g["top_z"][1], hi[2]), 2)]
                    boxes.append((lo, hi, key))
        low = [bx for bx in boxes if bx[1][2] <= LOW_TOP]
        bands = {}
        x = FOOT_X[0]
        while x <= FOOT_X[1]:
            label = next(bn for (a0, a1, bn) in BANDS if a0 <= x < a1)
            y = FOOT_Y[0]
            while y <= FOOT_Y[1]:
                tops = [(hi[2], name) for lo, hi, name in low if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1]]
                s = bands.setdefault(label, {"samples": 0, "no_surface": 0, "top_min": None, "top_max": None, "by": {}})
                s["samples"] += 1
                if not tops:
                    s["no_surface"] += 1
                else:
                    t, name = max(tops)
                    s["top_min"] = t if s["top_min"] is None else min(s["top_min"], t)
                    s["top_max"] = t if s["top_max"] is None else max(s["top_max"], t)
                    s["by"][name] = s["by"].get(name, 0) + 1
                y += 50.0
            x += 25.0
        for s in bands.values():
            for k in ("top_min", "top_max"):
                s[k] = round(s[k], 2) if s[k] is not None else None
        house = bands.get("house side", {})
        spill_ok = house.get("no_surface", 1) == 0 and house.get("top_max") is not None and house["top_max"] < SPILL_Z
        out["mouths"][tag] = {"route": m, "groups": groups, "surface_tops_by_band": bands, "spill_clear": spill_ok}
    dirty1 = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    out["dirty_after"], out["dirty_changed"] = dirty1, dirty0 != dirty1
    with open(os.path.join(HERE, "probe_mouth_surfaces.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    summary = {t: (v["spill_clear"], v["surface_tops_by_band"].get("house side", {}).get("top_max"))
               for t, v in out["mouths"].items()}
    del actors
    unreal.log(f"PUSS_SOFTGOODS_MOUTH_SURFACES|spill_clear,house_top={summary}|dirty_changed={dirty0 != dirty1}")


main()
