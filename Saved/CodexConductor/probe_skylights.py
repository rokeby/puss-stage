"""READ-ONLY: every SkyLight / SkyAtmosphere / DirectionalLight / ExponentialHeightFog component in the editor world
(all loaded levels): owner label, level, actor hidden-in-editor, component visible, intensity. PROBE_SKY|json"""
import json
import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
rows = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
    for cls in (unreal.SkyLightComponent, unreal.DirectionalLightComponent, unreal.SkyAtmosphereComponent):
        for c in a.get_components_by_class(cls):
            r = {"label": str(a.get_actor_label())[:60], "cls": cls.__name__.replace("Component", ""),
                 "level": a.get_outer().get_outer().get_name() if a.get_outer() else None,
                 "hidden_ed": bool(a.is_temporarily_hidden_in_editor()), "visible": bool(c.is_visible())}
            if hasattr(c, "intensity"):
                r["intensity"] = round(float(c.intensity), 3)
            rows.append(r)
unreal.log("PROBE_SKY|" + json.dumps(rows))
