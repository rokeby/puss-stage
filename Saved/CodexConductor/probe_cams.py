import json, unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
rows = [(str(a.get_actor_label()), a.get_class().get_name(), a.get_outer().get_outer().get_name()) for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.CameraActor)]
unreal.log("PROBE_CAMS|" + json.dumps(rows))
