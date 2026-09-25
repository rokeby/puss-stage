import unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
a = [x for x in sub.get_all_level_actors() if x.get_actor_label() == "CurtainCloth Preview"][0]
a.set_actor_location(unreal.Vector(4400.0, 0.0, 0.0), False, False); a.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0), False)
b = a.get_actor_bounds(False)
unreal.log(f"CURTAIN_PREVIEW_PLACED|origin={[round(b[0].x),round(b[0].y),round(b[0].z)]}|extent={[round(b[1].x),round(b[1].y),round(b[1].z)]}")
