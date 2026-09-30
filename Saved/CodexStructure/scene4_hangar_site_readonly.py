"""Read-only, before scene4_hangar_build.py: what already occupies the hangar's
volume (x -1000..5050, y 278950..281050, z -100..3100)? Also whether the build's
materials load. Mutates nothing."""
import json
import os

import unreal

LO, HI = (-1100.0, 278900.0, -100.0), (5100.0, 281100.0, 3100.0)


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    hits = []
    for a in sub.get_all_level_actors():
        o, e = a.get_actor_bounds(False)
        if e.x > 1e6 or e.length() < 0.01:
            continue
        if all(o.to_tuple()[i] + e.to_tuple()[i] >= LO[i] and o.to_tuple()[i] - e.to_tuple()[i] <= HI[i] for i in range(3)):
            hits.append({"actor": a.get_actor_label(), "class": a.get_class().get_name(),
                         "min": [round(o.to_tuple()[i] - e.to_tuple()[i]) for i in range(3)],
                         "max": [round(o.to_tuple()[i] + e.to_tuple()[i]) for i in range(3)]})
    mats = {p: bool(unreal.EditorAssetLibrary.load_asset(p)) for p in (
        "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup",
        "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat")}
    json.dump({"occupants": hits, "materials_load": mats},
              open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                "CodexStructure", "scene4_hangar_site.json"), "w"), indent=1)
    unreal.log(f"SCENE4_HANGAR_SITE_OK|occupants={len(hits)}|mutated=0")


main()
