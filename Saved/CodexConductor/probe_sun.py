import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
rows = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.DirectionalLight):
    lc = a.light_component
    rows.append("DIR|%s|level=%s|int=%.3f|vis=%s|hidden_ed=%s|atmos_sun=%s|mob=%s" % (
        a.get_actor_label(), a.get_outermost().get_name().split('/')[-1], lc.intensity, lc.is_visible(),
        a.is_hidden_ed(), lc.get_editor_property("atmosphere_sun_light"), lc.get_editor_property("mobility")))
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SkyLight):
    lc = a.light_component
    rows.append("SKY|%s|level=%s|int=%.3f|vis=%s" % (a.get_actor_label(), a.get_outermost().get_name().split('/')[-1], lc.intensity, lc.is_visible()))
unreal.log("PROBE_SUN|" + " || ".join(rows))
