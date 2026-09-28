import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
cap = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0,0,9000), unreal.Rotator())
try:
    c = cap.capture_component2d
    ms = [m for m in dir(c) if "hid" in m.lower() or "show_only" in m.lower() or "render_mode" in m.lower()]
    unreal.log("HIDE_MEMBERS|%s" % ms)
finally:
    unreal.EditorLevelLibrary.destroy_actor(cap)
