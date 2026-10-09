import unreal as u
ls = sorted(str(a.get_actor_label()) + "|" + a.get_class().get_name() for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors() if str(a.get_actor_label()).startswith("Shore"))
u.log("SHORELABELS_OK|%s" % ls)
