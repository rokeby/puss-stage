"""Read-only owned-actor and census probe after a Don't-Save recovery."""
import json
import unreal

tag = "Codex.J129.P02P01FloorReplacement"
owned = []
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if tag in [str(value) for value in actor.get_editor_property("tags")]:
        owned.append({"label": str(actor.get_actor_label()), "path": str(actor.get_path_name())})
lib = unreal.EditorLoadingAndSavingUtils
result = {
    "owned": sorted(owned, key=lambda row: row["path"]),
    "content": sorted(package.get_name() for package in lib.get_dirty_content_packages()),
    "maps": sorted(package.get_name() for package in lib.get_dirty_map_packages()),
    "pie": unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None,
}
unreal.log("JOB167_P02_FLOOR_RECOVERY_PROBE|" + json.dumps(result, sort_keys=True))
