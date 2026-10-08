import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
rows = []
for cls in (unreal.SceneCapture2D, unreal.CineCameraActor, unreal.CameraActor):
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, cls):
        rows.append("%s|%s|%s" % (cls.__name__, a.get_actor_label(), a.get_name()))
pc = unreal.GameplayStatics.get_player_controller(w, 0)
vt = pc.get_view_target() if pc else None
unreal.log("PIECAMPROBE|n=%d|view_target=%s|%s" % (len(rows), vt.get_name() if vt else None, " ; ".join(rows[:40])))
