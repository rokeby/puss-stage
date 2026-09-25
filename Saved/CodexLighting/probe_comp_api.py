import unreal
a = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if x.get_class().get_name()=="StaticMeshActor"]
actor_methods = sorted({m for m in dir(unreal.Actor) if "component" in m.lower() or "subobject" in m.lower()})
sds = hasattr(unreal, "SubobjectDataSubsystem")
sds_methods = sorted({m for m in dir(unreal.SubobjectDataSubsystem) if not m.startswith("_")})[:24] if sds else []
have_params = hasattr(unreal, "AddNewSubobjectParams")
unreal.log("PUSS_COMPAPI|actor=%s|SDS=%s|params=%s|sds_methods=%s" % (actor_methods, sds, have_params, sds_methods))
