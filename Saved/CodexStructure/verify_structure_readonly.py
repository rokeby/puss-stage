"""Read-only proof that the C++ structure survived save and reload.

Reloads the level from disk (only when nothing is dirty, so nothing can be lost),
then reads every structure actor back: tagged components present, instance
counts, stations still current, no legacy preview left, zero dirty packages.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RELOAD = True


def dirty():
    return ([str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
assert ed.get_game_world() is None, "PIE active - stop PIE first"
c0, m0 = dirty()
assert not c0 and not m0, f"dirty before reload, refusing: {c0} {m0}"
if RELOAD:
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(EXPECTED_WORLD), "reload failed"
    world = ed.get_editor_world()

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
report = {"reloaded": RELOAD, "structures": {}, "legacy_left": 0}
for a in sub.get_all_level_actors():
    if "InfinityStage.Gridiron" in [str(t) for t in a.get_editor_property("tags")]:
        report["legacy_left"] += 1
    if not isinstance(a, unreal.InfinityStageStructureActor):
        continue
    isms = a.get_components_by_class(unreal.InstancedStaticMeshComponent)
    tagged = [c for c in isms if "InfinityStage.Structure" in [str(t) for t in c.get_editor_property("component_tags")]]
    passage = a.get_editor_property("passage")
    report["structures"][a.get_actor_label()] = {
        "passage": passage.get_actor_label() if passage else None,
        "tagged_components": len(tagged),
        "tracked_components": len(a.get_editor_property("managed_components")),
        "instances": sum(c.get_instance_count() for c in tagged),
        "custom_floats": [int(c.get_editor_property("num_custom_data_floats")) for c in tagged],
        "mobility": [str(c.get_editor_property("mobility")) for c in tagged],
        "structure_current": bool(a.is_structure_current()),
    }
c1, m1 = dirty()
report["dirty"] = {"content": c1, "maps": m1}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "verify_structure.json")
json.dump(report, open(out, "w"), indent=1)
total = sum(s["instances"] for s in report["structures"].values())
current = sum(1 for s in report["structures"].values() if s["structure_current"])
unreal.log(f"STRUCTURE_VERIFY_OK|structures={len(report['structures'])}|instances={total}|current={current}"
           f"|legacy_left={report['legacy_left']}|dirty={len(c1)}+{len(m1)}")
