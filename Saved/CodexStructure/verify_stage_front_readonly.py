"""Read-only, after the stage-front build and portal_enable_apply.py: prove the
BUILT portal and stage front match Docs/StageFrontColliders_2026-09-28.json, the
file the curtain bake's colliders came from, to 1 cm. Mutates nothing.

For each box it gathers the built portal-layer instances that lie inside it
(each instance's world AABB within the box plus 1 cm) and checks that their
union reaches every face of the box to 1 cm: the built edges are the colliders'
edges. Lamp housings are matched one to one against the fixture layer's
instances. Lip-float housings that aren't authored yet (3b) are reported as
pending, not as failures. The file's delta_from_v2_cm records how the baked v2
differs.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
COLLIDERS = os.path.normpath(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                                          "Docs", "StageFrontColliders_2026-09-28.json"))
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "verify_stage_front.json")
TOL = 1.0
# The stage front laps its corners: a return or fascia board runs one board
# thickness (5 cm) past the neighbouring face to close the corner. A board that
# overruns a box by up to that much still belongs to it; the union is clipped to
# the box before the edges are compared. (29 Sep: counting only boards WHOLLY
# inside flagged both complete end returns as 223 and 98 cm short.)
CORNER = 5.0 + TOL
NOT_PORTAL = ("Stage floor: ground beyond the mouth",)   # the ground layer's own floor

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
spec = json.load(open(COLLIDERS, encoding="utf-8"))
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
structure = next(a for a in sub.get_all_level_actors()
                 if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage)
assert structure.get_editor_property("portal").get_editor_property("enabled"), "the portal is off"


def aabbs(component):
    box = component.get_editor_property("static_mesh").get_bounding_box()
    out = []
    for i in range(component.get_instance_count()):
        tf = component.get_instance_transform(i, True)
        pts = [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
               for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
        out.append(([min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)],
                    [max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)]))
    return out


portal, fixtures = [], []
for comp in structure.get_editor_property("managed_components"):
    if not comp:
        continue
    tags = [str(t) for t in comp.get_editor_property("component_tags")]
    if "InfinityStage.Structure.Portal" in tags:
        portal.extend(aabbs(comp))
    elif "InfinityStage.Structure.Fixtures" in tags:
        fixtures.extend(aabbs(comp))

problems, report = [], {"boxes": {}, "housings": {}}
for b in spec["boxes"]:
    if b["name"] in NOT_PORTAL:
        continue
    lo, hi = b["min_cm"], b["max_cm"]
    inside = [(l, h) for l, h in portal
              if all(l[i] >= lo[i] - CORNER and h[i] <= hi[i] + CORNER for i in range(3))
              and all(l[i] < hi[i] - TOL and h[i] > lo[i] + TOL for i in range(3))]
    if not inside:
        problems.append(f"{b['name']}: nothing built inside it")
        report["boxes"][b["name"]] = None
        continue
    ulo = [max(lo[i], min(l[i] for l, _ in inside)) for i in range(3)]
    uhi = [min(hi[i], max(h[i] for _, h in inside)) for i in range(3)]
    err = max(max(abs(ulo[i] - lo[i]), abs(uhi[i] - hi[i])) for i in range(3))
    report["boxes"][b["name"]] = {"pieces": len(inside), "worst_edge_cm": round(err, 2)}
    if err > TOL:
        problems.append(f"{b['name']}: built edges off by {err:.2f} cm "
                        f"({[round(v, 1) for v in ulo]}..{[round(v, 1) for v in uhi]})")

pending = []
for h in spec["lamp_housings"]:
    lo, hi = h["min_cm"], h["max_cm"]
    match = [1 for l, u in fixtures if all(abs(l[i] - lo[i]) <= TOL and abs(u[i] - hi[i]) <= TOL for i in range(3))]
    report["housings"][h["name"]] = len(match)
    if len(match) != 1:
        if h["name"].startswith("Lip ") and not match:
            pending.append(h["name"])       # 3b not authored yet
        else:
            problems.append(f"{h['name']}: {len(match)} built housings match")

report.update({"problems": problems, "pending_lip_housings": pending, "tolerance_cm": TOL,
               "collider_version": spec.get("version"), "delta_from_v2_cm": spec.get("delta_from_v2_cm")})
json.dump(report, open(OUT, "w"), indent=1)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"STAGE_FRONT_VERIFY_{'OK' if not problems else 'PROBLEMS'}|boxes={len(report['boxes'])}"
           f"|housings_matched={sum(1 for v in report['housings'].values() if v == 1)}|pending_lips={len(pending)}"
           f"|problems={len(problems)}|dirty={dirty[0]}+{dirty[1]}|mutated=0")
