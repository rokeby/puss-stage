"""Read-only: dump every ground board of every structure, for the board-drift
analysis (29 Sep). Per structure: the Passage GUID (it seeds each lane's random
stream), the route length, the Ground settings, GridHalfWidthCm; per board: its
centre's distance along the route, its lateral offset, and its custom data
[tone, length, width, thickness]. Written to Saved/CodexStructure/board_dump.json.
Mutates nothing. Lean: all work in main()."""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "board_dump.json")
GROUND_KEYS = ("board_width_cm", "board_gap_cm", "board_thickness_cm", "min_board_length_cm", "max_board_length_cm",
               "apron_cm", "slot_width_cm", "slot_inboard_cm", "cat_clearance_cm", "cut_chariot_slots", "floor_height_cm")


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    out = {}
    for a in sorted((x for x in sub.get_all_level_actors() if isinstance(x, unreal.InfinityStageStructureActor)),
                    key=lambda x: x.get_actor_label()):
        comps = [c for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent) if c.get_name().startswith("StructureGround")]
        if not comps or comps[0].get_instance_count() == 0:
            continue
        comp = comps[0]
        passage = a.get_editor_property("passage")
        route = passage.get_editor_property("route")
        g = a.get_editor_property("ground")
        n = comp.get_instance_count()
        k = int(comp.get_editor_property("num_custom_data_floats"))
        data = list(comp.get_editor_property("per_instance_sm_custom_data"))
        boards = []
        for i in range(n):
            loc = comp.get_instance_transform(i, True).translation
            key = route.find_input_key_closest_to_world_location(loc)
            d = route.get_distance_along_spline_at_spline_input_key(key)
            # Refine with the forward map BuildGround itself uses (distance -> frame): the
            # key->distance table is coarse on long segments (P02 was off by cm).
            for _ in range(6):
                frame = route.get_transform_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD, False)
                t, p0 = frame.rotation.get_axis_x(), frame.translation
                e = (loc.x - p0.x) * t.x + (loc.y - p0.y) * t.y + (loc.z - p0.z) * t.z
                d += e
                if abs(e) < 1e-4:
                    break
            frame = route.get_transform_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD, False)
            y = frame.rotation.get_axis_y()
            p = frame.translation
            lateral = (loc.x - p.x) * y.x + (loc.y - p.y) * y.y + (loc.z - p.z) * y.z
            boards.append([round(d, 5), round(lateral, 3)] + [float(v) for v in data[i * k:i * k + 4]])
        out[a.get_actor_label()] = {
            "passage": passage.get_actor_label(),
            "passage_guid": passage.get_editor_property("passage_guid").to_string(),
            "route_length_cm": route.get_spline_length(),
            "grid_half_width_cm": float(a.get_editor_property("grid_half_width_cm")),
            "board_count": int(a.get_editor_property("board_count")),
            "ground": {kk: (float(g.get_editor_property(kk)) if not isinstance(g.get_editor_property(kk), bool) else bool(g.get_editor_property(kk)))
                       for kk in GROUND_KEYS},
            "boards": boards,
        }
        unreal.log(f"BOARD_DUMP|{a.get_actor_label()}|boards={n}|custom_floats={k}|guid={out[a.get_actor_label()]['passage_guid']}")
    json.dump(out, open(OUT, "w"))
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"BOARD_DUMP_OK|structures={len(out)}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
