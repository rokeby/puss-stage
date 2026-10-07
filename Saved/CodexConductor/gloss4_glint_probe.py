"""READ-ONLY PIE probe: state of the borrowed glint light (PointLight_0) after the spawn script ran."""
import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.PointLight):
    if a.get_name() != "PointLight_0":
        continue
    c = a.point_light_component
    p = a.get_actor_location()
    ch = c.get_editor_property("lighting_channels")
    unreal.log("GLOSS4_GLINT_PROBE|loc=%.0f,%.0f,%.0f|int=%.0f|units=%s|vis=%s|hidden=%s|affects_world=%s|enabled_ch0=%s|mob=%s|tags=%s|owner_label=%s" % (
        p.x, p.y, p.z, c.get_editor_property("intensity"), c.get_editor_property("intensity_units"), c.is_visible(),
        a.is_hidden_ed() if hasattr(a, "is_hidden_ed") else a.get_editor_property("hidden"),
        c.get_editor_property("affects_world"), ch.get_editor_property("channel0"), c.get_editor_property("mobility"),
        [str(t) for t in a.tags], a.get_actor_label() if hasattr(a, "get_actor_label") else ""))
