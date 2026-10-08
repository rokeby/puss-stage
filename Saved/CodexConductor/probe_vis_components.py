"""READ-ONLY (editor world + PIE world if running): per-component visible / hidden_in_game / owner hidden for the old clam,
source_Anim and the six shore figures.  PROBE_VISCOMP_OK|json."""
import json
def main():
    import unreal
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    out = {}
    for tag, w in (("editor", ed.get_editor_world()), ("pie", ed.get_game_world())):
        if w is None:
            continue
        for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
            l = str(a.get_actor_label()) if tag == "editor" else a.get_name()
            if not any(x in l for x in ("Clam_with_Pearl", "source_Anim", "Shore0")):
                continue
            comps = []
            for c in a.get_components_by_class(unreal.PrimitiveComponent):
                comps.append([c.get_name()[:28], c.is_visible(), bool(c.get_editor_property("hidden_in_game"))])
            out["%s|%s" % (tag, l[:40])] = {"actor_hidden": bool(a.get_editor_property("hidden")), "comps": comps[:6]}
    unreal.log("PROBE_VISCOMP_OK|" + json.dumps(out))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_VISCOMP_FAILED|%r" % (exc,))
