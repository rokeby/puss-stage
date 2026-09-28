"""Read-only, after the station-1 apply stopped at its final check: where the live
materialized Right panel of P01 Wing 001 is (GUIDs compared as strings), which
packages are dirty, and whether Structure 01 is current. Mutates nothing."""
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
show = passage.get_editor_property("show_asset")
cue = next(c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == "P01 Wing 001")
guid = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
sides = {}
for ref in passage.get_editor_property("materialized_panels"):
    if unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid")) == guid:
        side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")
        sides[side] = round(ref.get_editor_property("base_world_transform").translation.y - passage.get_actor_location().y, 2)
current = [a.is_structure_current() for a in sub.get_all_level_actors()
           if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage]
content = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
strays = [a.get_actor_label() for a in sub.get_all_level_actors() if a.get_actor_label().startswith("ZZ_")]
unreal.log(f"P01_STATION1_STATE|live={sides}|structure_current={current}|dirty_content={content}|dirty_maps={maps}|strays={strays}|mutated=0")
