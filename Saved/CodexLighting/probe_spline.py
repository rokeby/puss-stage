import unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_actor_label().startswith("Passage 01")][0]
r = p1.get_editor_property("route")
api = sorted({n for n in dir(r) if n.startswith("set_") and any(k in n.lower() for k in ("up_vector","roll","rotation","location","point"))})
unreal.log("PUSS_SPLINEAPI|points=%d|len=%.0f|autofit=%s|%s" % (
    r.get_number_of_spline_points(), r.get_spline_length(),
    p1.get_editor_property("auto_fit_straight_route"), ", ".join(api)))
