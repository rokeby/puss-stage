"""Close the 18.5 cm hole at the end of Passage 4's floor (30 Sep, for Soft goods' backcloth
bake): Structure 04's Ground.ApronCm 400 -> 420, so the boards run to the route's end
(last station 10250 + 420 is clamped to the route length 10668.47) and meet the Scene 4
hangar's fixed apron at x 10668.5. A re-fit of one structure; with patch S built the lanes'
random draws are pinned, so only the lanes' last boards change.
Guards: world, no PIE, 0+0 dirty, no Sequencer, no ZZ_. Plain record first, level backup,
read-back (apron, the boards' far end, the structure current), level saved, dirty 0+0.
Revert: S04_FLOOR_APRON_REVERT=True runs this back to the recorded value. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "s04_floor_apron_record.json")
LABEL = "Infinity Stage - Structure 04"
NEW_APRON = 420.0


def fail(msg):
    unreal.log_error("S04_FLOOR_APRON_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    revert = bool(globals().get("S04_FLOOR_APRON_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith("ZZ_") for a in actors):
        fail("bench actors (ZZ_) in the level")
    s = next(a for a in actors if a.get_actor_label() == LABEL)
    g = s.get_editor_property("ground")
    before = {"apron_cm": float(g.get_editor_property("apron_cm")), "board_count": int(s.get_editor_property("board_count"))}
    if revert:
        target = json.load(open(RECORD, encoding="utf-8"))["before"]["apron_cm"]
    else:
        if abs(before["apron_cm"] - NEW_APRON) < 1e-6:
            fail("already at 420")
        target = NEW_APRON
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": datetime.datetime.now().isoformat(timespec="seconds"), "before": before}, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreS04FloorApron-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(RECORD, backup)
    s.modify()
    g.set_editor_property("apron_cm", float(target))
    s.set_editor_property("ground", g)
    if not s.materialize_structure():
        fail("re-fit failed")
    # Read back: the apron, the boards' far end along the route, and the structure current.
    route = s.get_editor_property("passage").get_editor_property("route")
    comp = next(c for c in s.get_components_by_class(unreal.InstancedStaticMeshComponent) if c.get_name().startswith("StructureGround"))
    k = int(comp.get_editor_property("num_custom_data_floats"))
    data = list(comp.get_editor_property("per_instance_sm_custom_data"))
    far_end = 0.0
    for i in range(comp.get_instance_count()):
        loc = comp.get_instance_transform(i, True).translation
        key = route.find_input_key_closest_to_world_location(loc)
        far_end = max(far_end, route.get_distance_along_spline_at_spline_input_key(key) + data[i * k + 1] / 2.0)
    got = float(s.get_editor_property("ground").get_editor_property("apron_cm"))
    if abs(got - target) > 1e-6 or not s.is_structure_current():
        fail(f"read-back: apron {got}, current {s.is_structure_current()}")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
        fail("content dirtied")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    after = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"S04_FLOOR_APRON_OK|{'reverted' if revert else 'applied'}|apron={got}|boards {before['board_count']}->{s.get_editor_property('board_count')}"
               f"|boards_far_end_route_cm={far_end:.1f}|route_length_cm={route.get_spline_length():.2f}|dirty_after={after[0]}+{after[1]}")


main()
