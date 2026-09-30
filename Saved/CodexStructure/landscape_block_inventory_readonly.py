"""Read-only inventory before the landscape block (30 Sep): Structure 02's and 03's `ground` struct (every field,
so the switch that lays boards is known rather than guessed) and board counts; every actor whose label contains
"Floor" (P03 may still own its original floor: P05's plane is a copy named "Passage 03 - Dark Wood Floor2");
the two landscapes' visibility/collision state; the S2 and S3 hangar build params. Mutates nothing."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def fields(struct):
    out = {}
    for name in dir(struct):
        if name.startswith("_") or callable(getattr(struct, name, None)):
            continue
        try:
            v = struct.get_editor_property(name)
            out[name] = v if isinstance(v, (int, float, bool, str)) else str(v)[:80]
        except Exception:  # noqa: BLE001
            pass
    return out


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    out = {"structures": {}, "floors": [], "landscapes": [], "hangars": {}}
    for a in actors:
        if isinstance(a, unreal.InfinityStageStructureActor) and a.get_actor_label()[-2:] in ("02", "03", "04"):
            g = a.get_editor_property("ground")
            out["structures"][a.get_actor_label()] = {"ground": fields(g), "board_count": a.get_editor_property("board_count"),
                                                     "current": a.is_structure_current()}
        if "Floor" in a.get_actor_label() and not a.get_actor_label().startswith(("S1 ", "S2 ", "S3 ", "S4 ", "S5 ", "S6 ")):
            o, e = a.get_actor_bounds(False)
            smc = a.get_component_by_class(unreal.StaticMeshComponent)
            out["floors"].append({"label": a.get_actor_label(), "hidden": a.is_hidden_ed(), "hidden_game": a.get_editor_property("hidden"),
                                  "x": [round(o.x - e.x), round(o.x + e.x)], "y": [round(o.y - e.y), round(o.y + e.y)], "z_top": round(o.z + e.z, 1),
                                  "material": smc.get_material(0).get_name() if smc and smc.get_material(0) else None})
        if isinstance(a, unreal.LandscapeProxy):
            out["landscapes"].append({"label": a.get_actor_label(), "hidden_game": a.get_editor_property("hidden"),
                                      "collision": a.get_actor_enable_collision()})
    for n in (2, 3):
        out["hangars"][n] = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8"))["hangar"]
    json.dump(out, open(os.path.join(HERE, "landscape_block_inventory.json"), "w"), indent=1, default=str)
    unreal.log("LANDSCAPE_INVENTORY_OK|floors=" + str(len(out["floors"])))


main()
