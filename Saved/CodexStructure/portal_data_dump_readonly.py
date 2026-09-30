"""Read-only: dump every portal-layer instanced component's custom data, in
instance order, for Structures 02 and 06, to find the order the current binary
evaluates the stage front's two length draws in (board-drift follow-up, 29 Sep).
Written to Saved/CodexStructure/portal_data_dump.json. Mutates nothing."""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "portal_data_dump.json")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    out = {}
    for a in sub.get_all_level_actors():
        if not isinstance(a, unreal.InfinityStageStructureActor) or a.get_actor_label()[-2:] not in ("02", "06"):
            continue
        comps = []
        for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
            tags = [str(t) for t in c.get_editor_property("component_tags")]
            if not any("Portal" in t or "Front" in t for t in tags) and not c.get_name().startswith("StructurePortal"):
                continue
            comps.append({"name": c.get_name(), "tags": tags, "count": c.get_instance_count(),
                          "k": int(c.get_editor_property("num_custom_data_floats")),
                          "data": [float(v) for v in c.get_editor_property("per_instance_sm_custom_data")]})
        out[a.get_actor_label()] = {"passage_guid": a.get_editor_property("passage").get_editor_property("passage_guid").to_string(),
                                    "portal_piece_count": int(a.get_editor_property("portal_piece_count")), "components": comps}
        unreal.log(f"PORTAL_DUMP|{a.get_actor_label()}|components={[(c['name'], c['count']) for c in comps]}")
    json.dump(out, open(OUT, "w"))
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"PORTAL_DUMP_OK|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
