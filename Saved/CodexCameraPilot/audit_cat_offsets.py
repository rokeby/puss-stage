"""Read-only: where each Passage's shadow cat height comes from. Marker: PUSS_CAT_OFFSET_AUDIT"""
import json, os
import unreal
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rows = []
for rig in [a for a in actors if a.get_class().get_name() == "InfinityStageCameraRig"]:
    passage = rig.get_editor_property("passage_actor")
    route = passage.get_editor_property("route") if passage else None
    cat_actor = None
    comp = rig.get_editor_property("shadow_cat")
    if comp:
        for getter in (lambda c: c.get_editor_property("child_actor"), lambda c: c.child_actor):
            try:
                cat_actor = getter(comp)
                break
            except Exception:
                continue
    rel = rig.get_editor_property("shadow_cat_relative_transform")
    rows.append({
        "rig": rig.get_actor_label(),
        "passage": passage.get_actor_label() if passage else None,
        "route_start_z": route.get_location_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD).z if route else None,
        "rig_z": rig.get_actor_location().z,
        "camera_offset": [rig.get_editor_property("camera_offset").x, rig.get_editor_property("camera_offset").y, rig.get_editor_property("camera_offset").z],
        "shadow_figure_offset_z": rig.get_editor_property("shadow_figure_offset").z,
        "cat_position_offset_z": rig.get_editor_property("shadow_cat_position_offset").z,
        "cat_relative_z": rel.translation.z,
        "cat_scale": rig.get_editor_property("shadow_cat_uniform_scale"),
        "cat_world_z": cat_actor.get_actor_location().z if cat_actor else None,
        "bob_cm": rig.get_editor_property("current_shadow_cat_camera_bob_cm"),
    })
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexCameraPilot", "audit_cat_offsets.json")
with open(out, "w", encoding="utf-8") as handle:
    json.dump(rows, handle, indent=2)
unreal.log(f"PUSS_CAT_OFFSET_AUDIT|rigs={len(rows)}")
