import json, unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
tr = root.transport; seg = [s for s in list(tr.segments) if str(s.label).startswith("Scene 3")][0]
t = round((tr.get_current_master_frame().value - seg.start_frame.value) / 24000.0, 1)
rows = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
    l = str(a.get_actor_label()); tags = [str(x) for x in a.tags]
    if ("P21.S3Crowd" in tags and "Camera" not in a.get_class().get_name()) or (l.startswith("Shore0") and l.endswith("Clam")):
        p = a.get_actor_location(); rows.append([l[:28], round(p.x), round(p.y), round(p.z), bool(a.get_editor_property("hidden"))])
unreal.log("PIE_CROWDPOS|" + json.dumps({"t": t, "rows": rows}))
