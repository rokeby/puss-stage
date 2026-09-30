"""Read-only: what the Scene 4 lattice is made of, for the "too dark to read as
architecture" note (30 Sep). Per lattice actor: class, mesh, materials, attach parent;
per material its base colour / emissive scalar parameters where it is an instance;
whether any real light rides the lattice. Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = {}
    lights = 0
    for a in sub.get_all_level_actors():
        label = a.get_actor_label()
        if not (label.startswith("S4 Hangar Lattice") or label.startswith("S4 Lattice Bulb")):
            continue
        parent = a.get_attach_parent_actor()
        if isinstance(a, unreal.Light):
            lights += 1
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        mesh = smc.get_editor_property("static_mesh").get_name() if smc and smc.get_editor_property("static_mesh") else None
        mats = []
        if smc:
            for m in smc.get_materials():
                if not m:
                    continue
                info = m.get_path_name().split(".")[-1]
                if isinstance(m, unreal.MaterialInstance):
                    for p in m.get_editor_property("scalar_parameter_values"):
                        info += f"|{p.get_editor_property('parameter_info').get_editor_property('name')}={round(p.get_editor_property('parameter_value'), 3)}"
                    for p in m.get_editor_property("vector_parameter_values"):
                        c = p.get_editor_property("parameter_value")
                        info += f"|{p.get_editor_property('parameter_info').get_editor_property('name')}=({c.r:.2f},{c.g:.2f},{c.b:.2f})"
                mats.append(info)
        key = (a.get_class().get_name(), mesh, tuple(mats), parent.get_actor_label() if parent else None)
        rows.setdefault(key, []).append(label)
    for (cls, mesh, mats, parent), labels in rows.items():
        unreal.log(f"LATTICE_PROBE|n={len(labels)}|e.g.={labels[0]}|class={cls}|mesh={mesh}|mats={list(mats)}|parent={parent}")
    unreal.log(f"LATTICE_PROBE_OK|groups={len(rows)}|lights_on_lattice={lights}")


main()
