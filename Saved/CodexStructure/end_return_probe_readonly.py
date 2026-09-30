"""Read-only: every stage-front board whose world AABB OVERLAPS each end-return
collider box (the verify counts only boards wholly inside), with the union of
their extents. Tells whether the verify's 223/98 cm shortfall is a real gap or
boards running 5 cm past the box to close the corner. Mutates nothing."""
import json
import os

import unreal

COLLIDERS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Docs", "StageFrontColliders_2026-09-28.json")
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "end_return_probe.json")


def main():
    boxes = [b for b in json.load(open(COLLIDERS, encoding="utf-8"))["boxes"] if b["name"].startswith("End return")]
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    s01 = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStageStructureActor) and a.get_actor_label().endswith("01"))
    comps = [c for c in s01.get_components_by_class(unreal.InstancedStaticMeshComponent) if c.get_name().startswith("StructureStageFront")]
    out = {}
    for b in boxes:
        lo, hi = b["min_cm"], b["max_cm"]
        pieces = []
        for c in comps:
            for i in range(c.get_instance_count()):
                tf = c.get_instance_transform(i, True)
                pts = [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
                       for x in (-50.0, 50.0) for y in (-50.0, 50.0) for z in (-50.0, 50.0)]
                mn = [min(getattr(p, a) for p in pts) for a in "xyz"]
                mx = [max(getattr(p, a) for p in pts) for a in "xyz"]
                if all(mn[k] < hi[k] - 0.1 and mx[k] > lo[k] + 0.1 for k in range(3)):
                    pieces.append({"min": [round(v, 1) for v in mn], "max": [round(v, 1) for v in mx]})
        union = ([round(min(p["min"][k] for p in pieces), 1) for k in range(3)],
                 [round(max(p["max"][k] for p in pieces), 1) for k in range(3)]) if pieces else None
        out[b["name"]] = {"box": [lo, hi], "overlapping": len(pieces), "union": union, "pieces": pieces}
    json.dump(out, open(OUT, "w"), indent=1)
    unreal.log(f"END_RETURN_PROBE_OK|boxes={len(out)}|mutated=0")


main()
