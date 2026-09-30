"""Read-only: find the Scene 4 lattice glow lights (labels, components, intensity, units). Marker: PUSS_LATTICE_GLOW_PROBE"""
import json
import os

import unreal


def main():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    rows = []
    for actor in actors:
        label = actor.get_actor_label()
        if "S4" not in label and "Hangar" not in label and "Lattice" not in label:
            continue
        lights = actor.get_components_by_class(unreal.LightComponent)
        if not lights and "Lattice" not in label:
            continue
        rows.append({"label": label, "class": actor.get_class().get_name(),
                     "lights": [{"name": l.get_name(), "class": l.get_class().get_name(),
                                 "intensity": round(l.get_editor_property("intensity"), 3),
                                 "units": str(l.get_editor_property("intensity_units")) if hasattr(l, "get_editor_property") and l.get_class().get_name() != "DirectionalLightComponent" else None}
                                for l in lights]})
    del actors
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "probe_lattice_glow.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=1)
    unreal.log("PUSS_LATTICE_GLOW_PROBE|actors=%d|lights=%d" % (len(rows), sum(len(r["lights"]) for r in rows)))


main()
