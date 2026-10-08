import json
def main():
    import unreal
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    L = unreal.LevelSequenceEditorBlueprintLibrary
    w = ed.get_editor_world()
    out = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        l = str(a.get_actor_label())
        sm = a.get_component_by_class(unreal.StaticMeshComponent)
        mesh = sm.static_mesh.get_name() if sm and sm.static_mesh else ""
        if "Hominid" in l or "Hominid" in mesh or l == "S3 Shot B03":
            b = a.get_actor_bounds(False)
            out[l] = {"mesh": mesh, "loc": [round(v) for v in (a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z)],
                      "rot": [round(a.get_actor_rotation().pitch, 1), round(a.get_actor_rotation().yaw, 1)],
                      "bc": [round(b[0].x), round(b[0].y), round(b[0].z)], "be": [round(b[1].x), round(b[1].y), round(b[1].z)]}
    unreal.log("PROBE_JAW_OK|" + json.dumps(out))
main()
