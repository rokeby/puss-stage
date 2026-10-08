"""READ-ONLY in PIE: render-relevant state of the PearlClam parts + figures: per primitive component visible,
hidden_in_game, owner hidden, max draw distances, bounds, mesh, materials, recently rendered, world location.
PIE_CLAM_RENDER_OK|json."""
import json
def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if w is None:
        raise RuntimeError("NO_PIE")
    out = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        n = a.get_name()
        lab = a.get_actor_label() if hasattr(a, "get_actor_label") else n
        if not any(x in str(lab) for x in ("PearlClam", "Shore01", "Shore03")):
            continue
        rows = []
        for c in a.get_components_by_class(unreal.PrimitiveComponent)[:4]:
            r = {"c": c.get_name()[:20], "vis": c.is_visible(), "hig": bool(c.get_editor_property("hidden_in_game")),
                 "ld": c.get_editor_property("ld_max_draw_distance"), "cached": c.get_editor_property("cached_max_draw_distance"),
                 "rendered": c.was_recently_rendered(0.5) if hasattr(c, "was_recently_rendered") else None}
            o, e, _ = unreal.SystemLibrary.get_component_bounds(c)
            r["bounds"] = [round(o.x), round(o.y), round(o.z), round(e.x), round(e.y), round(e.z)]
            if isinstance(c, unreal.StaticMeshComponent):
                sm = c.static_mesh
                r["mesh"] = sm.get_name() if sm else None
                r["mats"] = [m.get_name() if m else None for m in c.get_materials()]
                try:
                    r["nanite"] = bool(sm.get_editor_property("nanite_settings").get_editor_property("enabled")) if sm else None
                except Exception:
                    pass
            rows.append(r)
        loc = a.get_actor_location()
        out[str(lab)[:30]] = {"loc": [round(loc.x), round(loc.y), round(loc.z)], "hidden": a.is_hidden() if hasattr(a, "is_hidden") else None, "comps": rows}
    unreal.log("PIE_CLAM_RENDER_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIE_CLAM_RENDER_FAILED|%r" % (exc,))
