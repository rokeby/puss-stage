import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
rows = []
for cls in (unreal.SkyAtmosphere, unreal.SkyLight, unreal.DirectionalLight, unreal.ExponentialHeightFog, unreal.VolumetricCloud):
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, cls):
        rows.append("%s|%s|level=%s|hidden_ed=%s" % (cls.__name__, a.get_actor_label(), a.get_outermost().get_name().split('/')[-1], a.is_hidden_ed()))
unreal.log("PROBE_SKY|" + " || ".join(rows))
