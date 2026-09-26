import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
cap = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0,0,5000), unreal.Rotator())
try:
    comp = cap.capture_component2d
    sfs = comp.get_editor_property("show_flag_settings")
    unreal.log("SHOWFLAG_SETTINGS|%s" % [(s.get_editor_property('show_flag_name'), s.get_editor_property('enabled')) for s in sfs])
    members = [m for m in dir(comp) if 'show' in m.lower() or 'fog' in m.lower()]
    unreal.log("CAPTURE_MEMBERS|%s" % members)
    unreal.log("PRIMITIVE_RENDER_MODE|%s" % comp.get_editor_property("primitive_render_mode"))
    unreal.log("CAPTURE_SOURCE|%s" % comp.get_editor_property("capture_source"))
finally:
    unreal.EditorLevelLibrary.destroy_actor(cap)
