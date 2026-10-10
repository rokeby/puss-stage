"""Read-only census after a stopped P75 APPLY."""
import json
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
owned = []
for actor in actors:
    tags = sorted(str(tag) for tag in actor.get_editor_property("tags"))
    if "P75_CHANDELIER_STAGING" in tags:
        owned.append({
            "label": str(actor.get_actor_label()),
            "class": actor.get_class().get_name(),
            "tags": tags,
        })
lib = unreal.EditorLoadingAndSavingUtils
result = {
    "actors": sorted(owned, key=lambda row: row["label"]),
    "content": sorted(package.get_name() for package in lib.get_dirty_content_packages()),
    "maps": sorted(package.get_name() for package in lib.get_dirty_map_packages()),
    "pie": unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None,
}
unreal.log("P75_POSTFAILURE_CENSUS|" + json.dumps(result, sort_keys=True))
