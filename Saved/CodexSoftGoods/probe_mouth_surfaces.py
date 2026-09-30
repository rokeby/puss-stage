"""READ-ONLY (30 Sep): what surfaces lie under the shared drape's pile at a mouth? P01 (the reference the cache was baked
on) and P03 (the question: Interaction 2's drape; the landscape was deleted at 16:36; Structure 03's ground on since 12:25).

For each mouth (route start) it reports, over the pile footprint (x -200..+470 cm from the curtain line, y +-1100):
  1. every Structure's instanced-mesh instances whose world AABB overlaps the footprint, grouped by component: count,
     x range, top and bottom z. The stage front (lip, fascia, house floor) is built as instances inside the Structure
     actor, so an actor's own bounds cannot show it.
  2. every other actor overlapping it (floor planes etc.): label, class, AABB.
  3. a SURFACE-TOP map: on a 25 cm grid over the footprint, the highest top z among LOW boxes (top z at most 150 cm, so
     posts and walls are excluded) whose AABB contains the point, summarised per x band.
AABBs of rotated instances are conservative (a slightly larger box). NOTHING IS SAVED OR MODIFIED: there is no save call in
this file. Writes probe_mouth_surfaces.json; logs PUSS_SOFTGOODS_MOUTH_SURFACES|... Crash rules: everything in main().
"""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
MOUTHS = {"P01": (0.0, 0.0), "P03": (0.0, 160000.0)}
FOOT_X, FOOT_Y, LOW_TOP = (-200.0, 470.0), (-1100.0, 1100.0), 150.0
BANDS = [(-200, -155, "beyond the lip (house side)"), (-155, -115, "lip/fascia line"), (-115, 0, "forestage"),
         (0, 250, "mouth"), (250, 470, "beyond the mouth")]


def aabb_of_instance(comp, i, lo_l, hi_l):
    t = comp.get_instance_transform(i, True)
    pts = []
    for x in (lo_l.x, hi_l.x):
        for y in (lo_l.y, hi_l.y):
            for z in (lo_l.z, hi_l.z):
                p = t.transform_location(unreal.Vector(x, y, z))
                pts.append((p.x, p.y, p.z))
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


def main():
    dirty0 = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    out = {"dirty_before": dirty0, "mouths": {}}
    for tag, (mx, my) in MOUTHS.items():
        fx0, fx1, fy0, fy1 = mx + FOOT_X[0], mx + FOOT_X[1], my + FOOT_Y[0], my + FOOT_Y[1]
        overlaps = lambda lo, hi: not (hi[0] < fx0 or lo[0] > fx1 or hi[1] < fy0 or lo[1] > fy1 or hi[2] < -400 or lo[2] > 400)
        boxes, groups, others = [], {}, []
        for a in actors:
            is_structure = a.get_class().get_name() == "InfinityStageStructureActor"
            if is_structure:
                for comp in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
                    mesh = comp.get_editor_property("static_mesh")
                    if mesh is None:
                        continue
                    b = mesh.get_bounds()
                    lo_l, hi_l = b.origin - b.box_extent, b.origin + b.box_extent
                    for i in range(comp.get_instance_count()):
                        lo, hi = aabb_of_instance(comp, i, lo_l, hi_l)
                        if not overlaps(lo, hi):
                            continue
                        key = f"{a.get_actor_label()} / {comp.get_name()}"
                        g = groups.setdefault(key, {"count": 0, "x_rel": [1e9, -1e9], "top_z": [1e9, -1e9],
                                                    "bottom_z": [1e9, -1e9], "mesh": mesh.get_name()})
                        g["count"] += 1
                        g["x_rel"] = [min(g["x_rel"][0], lo[0] - mx), max(g["x_rel"][1], hi[0] - mx)]
                        g["top_z"] = [min(g["top_z"][0], hi[2]), max(g["top_z"][1], hi[2])]
                        g["bottom_z"] = [min(g["bottom_z"][0], lo[2]), max(g["bottom_z"][1], lo[2])]
                        boxes.append((lo, hi, key))
                continue
            try:
                o, e = a.get_actor_bounds(False)
            except Exception:  # noqa: BLE001
                continue
            lo, hi = [o.x - e.x, o.y - e.y, o.z - e.z], [o.x + e.x, o.y + e.y, o.z + e.z]
            if overlaps(lo, hi) and (e.x > 100 or e.y > 100):
                others.append({"label": a.get_actor_label(), "class": a.get_class().get_name(),
                               "x_rel": [round(lo[0] - mx, 1), round(hi[0] - mx, 1)], "top_z": round(hi[2], 2),
                               "bottom_z": round(lo[2], 2)})
                boxes.append((lo, hi, a.get_actor_label()))
        low = [b for b in boxes if b[1][2] <= LOW_TOP]
        bands = {}
        x = FOOT_X[0]
        while x <= FOOT_X[1]:
            y = FOOT_Y[0]
            while y <= FOOT_Y[1]:
                px, py = mx + x, my + y
                tops = [(hi[2], name) for lo, hi, name in low if lo[0] <= px <= hi[0] and lo[1] <= py <= hi[1]]
                top = max(tops) if tops else (None, None)
                label = next(bn for (a0, a1, bn) in BANDS if a0 <= x < a1) if x < 470 else BANDS[-1][2]
                s = bands.setdefault(label, {"samples": 0, "no_surface": 0, "top_min": None, "top_max": None, "by": {}})
                s["samples"] += 1
                if top[0] is None:
                    s["no_surface"] += 1
                else:
                    s["top_min"] = top[0] if s["top_min"] is None else min(s["top_min"], top[0])
                    s["top_max"] = top[0] if s["top_max"] is None else max(s["top_max"], top[0])
                    s["by"][top[1]] = s["by"].get(top[1], 0) + 1
                y += 50.0
            x += 25.0
        for s in bands.values():
            for k in ("top_min", "top_max"):
                s[k] = round(s[k], 2) if s[k] is not None else None
        out["mouths"][tag] = {"route_start": [mx, my], "structure_instances": {k: {**g,
                              "x_rel": [round(v, 1) for v in g["x_rel"]], "top_z": [round(v, 2) for v in g["top_z"]],
                              "bottom_z": [round(v, 2) for v in g["bottom_z"]]} for k, g in groups.items()},
                              "other_actors": others, "surface_tops_by_band": bands}
    dirty1 = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    out["dirty_after"] = dirty1
    out["dirty_changed"] = dirty0 != dirty1
    with open(os.path.join(HERE, "probe_mouth_surfaces.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    summary = {t: {b: (v["top_min"], v["top_max"], v["no_surface"]) for b, v in m["surface_tops_by_band"].items()}
               for t, m in out["mouths"].items()}
    del actors
    unreal.log(f"PUSS_SOFTGOODS_MOUTH_SURFACES|{summary}|dirty_changed={dirty0 != dirty1}")


main()
