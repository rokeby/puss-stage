"""Read-only: every actor whose bounds reach the P04 backcloth line (x 10300..10600, |y - 240000| < 600,
z 150..900): label, class, folder, tags, hidden flags, mesh/cache, bounds. Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for a in sub.get_all_level_actors():
        o, e = a.get_actor_bounds(False)
        if e.length() < 1.0 or max(e.x, e.y) > 5.0e4:
            continue
        if (o.x + e.x) >= 10300 and (o.x - e.x) <= 10600 and abs(o.y - 240000) < 600 + e.y and (o.z + e.z) >= 150 and (o.z - e.z) <= 900:
            comp = a.get_component_by_class(unreal.StaticMeshComponent) or a.get_component_by_class(unreal.GeometryCacheComponent)
            asset = None
            if isinstance(comp, unreal.StaticMeshComponent):
                m = comp.get_editor_property("static_mesh"); asset = m.get_name() if m else None
            elif comp:
                c = comp.get_editor_property("geometry_cache"); asset = c.get_name() if c else None
            rows.append(f"{a.get_actor_label()} [{a.get_class().get_name()}] folder={a.get_folder_path()} tags={[str(t) for t in a.tags][:3]} "
                        f"hidden_game={a.is_hidden_ed() if hasattr(a, 'is_hidden_ed') else '?'}/{a.get_editor_property('hidden')} asset={asset} "
                        f"x[{o.x - e.x:.0f},{o.x + e.x:.0f}] y[{o.y - e.y:.0f},{o.y + e.y:.0f}] z[{o.z - e.z:.0f},{o.z + e.z:.0f}]")
    unreal.log("P04_LINE|" + " || ".join(rows))


main()
