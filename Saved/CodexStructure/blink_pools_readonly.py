"""Read-only: what surface lies under each blink spot's pool (P01's and the six
planned)? Visibility traces pass through the walnut boards, so this tests the
boards directly: for every Structure ISM, is the pool point inside an instance's
footprint, and how far is that instance's top from the pool plane? Also lists
other actors whose bounds hold the point. Mutates nothing."""
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    plan = json.load(open(os.path.join(HERE, "blink_spots_plan.json"), encoding="utf-8"))
    show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    passages = {("P" + p.get_actor_label()[8:10]): p for p in actors if isinstance(p, unreal.InfinityStagePassageActor)}
    cues = {gs(c.get_editor_property("cue_guid")): c for c in show.get_editor_property("cues")}
    src_cue = next(c for c in cues.values() if str(c.get_editor_property("label")) == "P01 Wing 041")
    jobs = [("P01", gs(src_cue.get_editor_property("cue_guid")), plan["source"]["pool"])]
    for r in plan["rows"]:
        s = r["spot"]
        pr, yr = math.radians(s["pitch"]), math.radians(s["yaw"])
        u = (math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), math.sin(pr))
        jobs.append((r["passage"], r["cue_guid"], [s["loc"][i] + u[i] * r["throw_cm"] for i in range(3)]))
    boards = []
    for a in actors:
        if isinstance(a, unreal.InfinityStageStructureActor):
            for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
                boards.append((a.get_actor_label(), c))
    out = []
    for pn, cg, pool_rel in jobs:
        cue = cues[cg]
        st = next(x for x in cue.get_editor_property("wing_pair").get_editor_property("attachments")
                  if x.get_editor_property("anchor") == unreal.InfinityAttachmentAnchor.STATION)
        anchor = passages[pn].get_attachment_anchor_world_transform(cue.get_editor_property("cue_guid"), st.get_editor_property("attachment_guid"))
        p = unreal.MathLibrary.transform_location(anchor, unreal.Vector(*pool_rel))
        under = []
        for label, c in boards:
            o, e, _ = unreal.SystemLibrary.get_component_bounds(c)
            if abs(p.x - o.x) > e.x or abs(p.y - o.y) > e.y:
                continue
            for i in range(c.get_instance_count()):
                tf = c.get_instance_transform(i, True)
                loc = unreal.MathLibrary.inverse_transform_location(tf, p)
                if abs(loc.x) <= 50.0 and abs(loc.y) <= 50.0:
                    top = unreal.MathLibrary.transform_location(tf, unreal.Vector(loc.x, loc.y, 50.0)).z
                    if abs(top - p.z) < 60.0:
                        mat = c.get_material(0)
                        under.append({"structure": label, "component": c.get_name(), "instance": i,
                                      "top_minus_pool_cm": round(top - p.z, 1),
                                      "material": mat.get_path_name().split(".")[-1] if mat else None})
        others = []
        for a in actors:
            if isinstance(a, (unreal.InfinityStageStructureActor, unreal.InfinityStagePassageActor)):
                continue
            o, e = a.get_actor_bounds(False)
            if e.x < 1e5 and abs(p.x - o.x) <= e.x and abs(p.y - o.y) <= e.y and (o.z - e.z - 60.0) <= p.z <= (o.z + e.z + 60.0):
                others.append({"actor": a.get_actor_label(), "top_minus_pool_cm": round(o.z + e.z - p.z, 1)})
        out.append({"passage": pn, "cue": str(cue.get_editor_property("label")), "pool_world": [round(v) for v in p.to_tuple()],
                    "boards": under[:6], "other_actors": others[:8]})
    json.dump(out, open(os.path.join(HERE, "blink_pools.json"), "w"), indent=1)
    unreal.log(f"BLINK_POOLS_OK|pools={len(out)}|mutated=0")


main()
