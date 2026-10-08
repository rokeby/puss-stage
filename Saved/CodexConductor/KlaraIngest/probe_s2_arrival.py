"""READ-ONLY probe (8 Oct): what plays in LS_DevScene_02 over the arrival [0, 400) and which lights live in Klara's
Japanese_Alley level.  Writes probe_s2_arrival.json.  PROBE_S2ARR_OK / PROBE_S2ARR_FAILED.  Saves nothing."""
import json

OUT = "E:/PussStage/Saved/CodexConductor/KlaraIngest/probe_s2_arrival.json"


def main():
    import unreal as u
    seq = u.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_02")
    rows = []

    def secs(t):
        out = []
        for s in t.get_sections():
            a = int(s.get_start_frame()) if s.has_start_frame() else None
            b = int(s.get_end_frame()) if s.has_end_frame() else None
            out.append([a, b, bool(s.is_active())])
        return out
    for t in seq.get_tracks():
        rows.append({"binding": None, "track": str(t.get_display_name()), "cls": t.get_class().get_name(), "sections": secs(t)})
    for b in seq.get_bindings():
        for t in b.get_tracks():
            rows.append({"binding": str(b.get_display_name()), "track": str(t.get_display_name()), "cls": t.get_class().get_name(), "sections": secs(t)})
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    lights = []
    for a in u.GameplayStatics.get_all_actors_of_class(w, u.Actor):
        lvl = a.get_outer().get_outer().get_name() if a.get_outer() and a.get_outer().get_outer() else "?"
        comps = a.get_components_by_class(u.LightComponentBase)
        fx = a.get_components_by_class(u.NiagaraComponent) + a.get_components_by_class(u.ParticleSystemComponent)
        if "Japanese_Alley" in lvl and (comps or fx or "Fog" in a.get_class().get_name() or "PostProcess" in a.get_class().get_name()):
            l = a.get_actor_location()
            lights.append({"label": str(a.get_actor_label()), "cls": a.get_class().get_name(), "loc": [round(l.x), round(l.y), round(l.z)],
                           "lights": [[c.get_class().get_name(), round(float(c.get_editor_property("intensity")), 2), bool(c.is_visible())] for c in comps],
                           "fx": len(fx), "hidden_game": bool(a.get_editor_property("hidden"))})
    json.dump({"tracks": rows, "her_lights": lights}, open(OUT, "w"), indent=1)
    u.log("PROBE_S2ARR_OK|tracks=%d|her_lights=%d|%s" % (len(rows), len(lights), OUT))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("PROBE_S2ARR_FAILED|%r" % (exc,))
