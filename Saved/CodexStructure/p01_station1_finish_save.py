"""Finish the station-1 apply that stopped at its own final check (a GUID-compare
bug, not a fault in the change). Re-asserts, read-only, that the change is exactly
right and that nothing else is pending, then saves only the Show and the level."""
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def fail(message):
    raise RuntimeError(f"P01_STATION1_FINISH_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
show = passage.get_editor_property("show_asset")
cue = next(c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == "P01 Wing 001")
pair = cue.get_editor_property("wing_pair")
if abs(pair.get_editor_property("right").get_editor_property("local_transform").translation.y - 750.0) > 0.01:
    fail("Show does not hold +750 for Wing 001's Right panel")
guid = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
live = [ref.get_editor_property("base_world_transform").translation.y - passage.get_actor_location().y
        for ref in passage.get_editor_property("materialized_panels")
        if unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid")) == guid
        and "RIGHT" in str(ref.get_editor_property("side"))]
if len(live) != 1 or abs(live[0] - 750.0) > 1.0:
    fail(f"live Right panel at {live}")
if any(not a.is_structure_current() for a in sub.get_all_level_actors()
       if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage):
    fail("Structure 01 not current")
if any(a.get_actor_label().startswith("ZZ_") for a in sub.get_all_level_actors()):
    fail("stray ZZ_ actors in the level")
content = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if content != [SHOW_PATH] or maps != [EXPECTED_WORLD]:
    fail(f"dirty set is not exactly this change: {content} {maps}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
c2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
m2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"P01_STATION1_FINISH_OK|live_right_y={round(live[0], 2)}|show_saved=1|level_saved=1|dirty_after={c2}+{m2}")
