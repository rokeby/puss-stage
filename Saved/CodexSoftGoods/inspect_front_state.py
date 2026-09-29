"""READ-ONLY (29 Sep): Gary says "the drape is at the very front of the stage, held up by your structure. not seeing any
wings yet!" Which drape is he seeing, and are Passage 01's wings there? The baked-curtain placement has NOT run, so
the bake should not be in the level. Writes nothing; everything inside main().

Reports: PIE state; the dirty set (unsaved edits by anyone); every level actor whose components use a curtain/drape
asset (SM_CurtainDrape_*, GC_CurtainDrop_*, SM_FireSafetyCurtain*, Chaos cloth, BP_Curtain*); every
GeometryCacheActor; each Passage's materialized wing pairs, managed and visible component counts, and hidden flags;
each Structure actor's portal flags. Ends on PUSS_SOFTGOODS_FRONT_STATE_OK.
"""
import json
import os

import unreal

CURTAIN_HINTS = ("CurtainDrape", "CurtainDrop", "FireSafetyCurtain", "CurtainChaos", "CurtainCloth", "Curtain")


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def asset_names(comp):
    names = []
    for prop in ("static_mesh", "geometry_cache", "skeletal_mesh_asset", "asset"):
        try:
            v = comp.get_editor_property(prop)
            if v:
                names.append(v.get_path_name())
        except Exception:  # noqa: BLE001
            pass
    return names


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    report = {"world": world.get_outermost().get_name(), "pie": editor.get_game_world() is not None, "dirty": dirty(),
              "curtain_actors": [], "geometry_cache_actors": [], "passages": [], "structures": []}
    ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = ss.get_all_level_actors()
    report["actor_count"] = len(actors)
    for a in actors:
        cls = a.get_class().get_name()
        label = a.get_actor_label()
        if cls == "GeometryCacheActor":
            report["geometry_cache_actors"].append({"label": label, "loc": vec(a.get_actor_location())})
        hits = []
        if any(h in cls or h in label for h in CURTAIN_HINTS):
            hits.append(f"class/label:{cls}")
        for comp in a.get_components_by_class(unreal.PrimitiveComponent):
            for n in asset_names(comp):
                if any(h in n for h in CURTAIN_HINTS):
                    hits.append(n)
            if comp.get_class().get_name() == "ChaosClothComponent":
                hits.append("ChaosClothComponent")
        if hits:
            report["curtain_actors"].append({"label": label, "class": cls, "loc": vec(a.get_actor_location()),
                                             "hidden_in_editor": a.is_hidden_ed(), "hits": sorted(set(hits))[:6]})
        if cls == "InfinityStagePassageActor":
            row = {"label": label, "loc": vec(a.get_actor_location()), "hidden_in_editor": a.is_hidden_ed()}
            for prop in ("materialized_wing_pair_count", "component_budget"):
                try:
                    row[prop] = a.get_editor_property(prop)
                except Exception:  # noqa: BLE001
                    pass
            try:
                managed = list(a.get_editor_property("managed_components"))
                row["managed_components"] = len(managed)
                row["managed_visible"] = sum(1 for c in managed if c and c.is_visible())
            except Exception as exc:  # noqa: BLE001
                row["managed_err"] = str(exc)
            prims = a.get_components_by_class(unreal.PrimitiveComponent)
            row["primitive_components"] = len(prims)
            row["primitive_visible"] = sum(1 for c in prims if c.is_visible())
            report["passages"].append(row)
        if cls == "InfinityStageStructureActor":
            row = {"label": label}
            try:
                portal = a.get_editor_property("portal")
                for prop in ("enabled", "b_enabled", "stage_front", "b_stage_front", "hanging_lines"):
                    try:
                        row["portal_" + prop] = portal.get_editor_property(prop)
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as exc:  # noqa: BLE001
                row["portal_err"] = str(exc)
            report["structures"].append(row)
    del actors
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "inspect_front_state.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log("PUSS_SOFTGOODS_FRONT_STATE_OK|" + out)


main()
