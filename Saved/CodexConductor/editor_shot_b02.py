"""Editor viewport HighResShot from S3 Shot B02's evaluated pose (Sequencer at the current frame). No writes.
EDITOR_SHOT_OK|path-hint."""
def main():
    import unreal
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    w = ed.get_editor_world()
    cam = [x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor) if str(x.get_actor_label()) == "S3 Shot B02"][0]
    ed.set_level_viewport_camera_info(cam.get_actor_location(), cam.get_actor_rotation())
    unreal.SystemLibrary.execute_console_command(w, "HighResShot 1600x900")
    unreal.log("EDITOR_SHOT_OK|%s" % cam.get_actor_location())
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("EDITOR_SHOT_FAILED|%r" % (exc,))
