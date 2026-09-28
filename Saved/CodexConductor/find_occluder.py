"""What is standing between the opening camera and the curtain?"""
import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
CAM = unreal.Vector(0.0, 0.0, 150.0)
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    l = a.get_actor_location()
    if l.x < -200 or l.x > 5400:          # between camera and curtain
        continue
    if abs(l.y) > 1200 or l.z < -200 or l.z > 1200:
        continue
    cls = a.get_class().get_name()
    if any(k in cls for k in ("Camera", "Capture", "Rig", "Cine")) or "Camera" in a.get_actor_label():
        unreal.log("OCCLUDER|%s|%s|x=%.0f y=%.0f z=%.0f|hidden_in_game=%s" % (
            a.get_actor_label(), cls, l.x, l.y, l.z,
            a.get_editor_property("hidden")  if hasattr(a, "hidden") else "?"))
