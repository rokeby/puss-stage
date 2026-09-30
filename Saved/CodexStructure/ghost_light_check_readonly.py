"""Read-only: the Scene 4 ghost light's stand, bulb and light are unattached and at
their build positions (the mouth + 25 m, 4 m left; stand centre z 90, bulb and
light z 188). Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    cam = next(a for a in actors if "Scene 4" in a.get_actor_label() and "Entry Handoff Camera" in a.get_actor_label())
    x0, cy = cam.get_actor_location().x, cam.get_actor_location().y
    want = {"S4 Ghost Light Stand": (x0 + 2500.0, cy - 400.0, 90.0), "S4 Ghost Light Bulb": (x0 + 2500.0, cy - 400.0, 188.0),
            "S4 Ghost Light": (x0 + 2500.0, cy - 400.0, 188.0)}
    out = {}
    for a in actors:
        if a.get_actor_label() in want:
            loc = a.get_actor_location().to_tuple()
            w = want[a.get_actor_label()]
            out[a.get_actor_label()] = {"err_cm": round(max(abs(loc[i] - w[i]) for i in range(3)), 3),
                                        "attached": a.get_attach_parent_actor() is not None}
    ok = len(out) == 3 and all(v["err_cm"] < 0.1 and not v["attached"] for v in out.values())
    unreal.log(f"GHOST_LIGHT_CHECK|{'OK' if ok else 'WRONG'}|{out}")


main()
