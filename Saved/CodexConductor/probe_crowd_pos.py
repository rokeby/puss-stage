import json, unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
rows = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
    l = str(a.get_actor_label()); tags = [str(t) for t in a.tags]
    if "P21.S3Crowd" in tags or (l.startswith("Shore0") and l.endswith("Clam")):
        p = a.get_actor_location(); rows.append([l, round(p.x), round(p.y), round(p.z), a.get_class().get_name()[:20]])
unreal.log("PROBE_CROWDPOS|" + json.dumps(rows))
