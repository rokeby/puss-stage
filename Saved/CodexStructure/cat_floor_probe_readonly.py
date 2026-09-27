"""Read-only: does the shadow cat stand ON the new boards, or in them?

The camera rig places the cat by a fixed offset (-155.49 cm below a rig at
150 cm, i.e. its root near z = -5.5), tuned before any floor existed. The
structure pass now lays boards with their tops at z = 0 in P01/P02/P04/P05/P06.
This reads each rig's cat skeletal mesh world bounds and reports its lowest
point against the board top. Bounds are conservative (animation can extend them),
so a small gap either way is not proof, but a paw line well below 0 would be.
Mutates nothing.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"

rows = []
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    is_rig = a.get_class().get_name() == "InfinityStageCameraRig"
    for sk in a.get_components_by_class(unreal.SkeletalMeshComponent):
        # The rig's own cat, or any other visible cat-named skeletal mesh (the
        # mouse stand-in may carry its own).
        if not sk.is_visible() or not (is_rig or "cat" in (a.get_actor_label() + sk.get_name()).lower()):
            continue
        origin, ext, _ = unreal.SystemLibrary.get_component_bounds(sk)
        loc = sk.get_world_location()
        mesh = sk.get_editor_property("skeletal_mesh_asset") if hasattr(sk, "get_editor_property") else None
        rows.append({
            "rig": a.get_actor_label(), "component": sk.get_name(),
            "mesh": mesh.get_path_name() if mesh else None,
            "root_xy_cm": [round(loc.x), round(loc.y)],
            "passage_by_y": f"P0{int(round(loc.y / 80000.0)) + 1}",
            "root_z_cm": round(loc.z, 2),
            "bounds_min_z_cm": round(origin.z - ext.z, 2),
            "bounds_max_z_cm": round(origin.z + ext.z, 2),
            "world_scale": round(sk.get_world_scale().z, 3),
        })

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "cat_floor_probe.json")
json.dump(rows, open(out, "w"), indent=1)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"CAT_FLOOR_PROBE_OK|rigs={len(rows)}|dirty={dirty[0]}+{dirty[1]}|mutated=0")
