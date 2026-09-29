"""READ-ONLY census (29 Sep): which actors TICK in the editor world (they can churn render state with PIE off), how
many light actors there are by class, and how many InfinityStageEffectSource instances exist. Writes nothing."""
import collections
import json
import os

import unreal


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        unreal.log("PUSS_SOFTGOODS_TICKERS_STOPPED|PIE running")
        return
    world = editor.get_editor_world()
    ticking = collections.Counter()
    lights = collections.Counter()
    effects = []
    total = 0
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        total += 1
        cls = actor.get_class().get_name()
        if actor.is_actor_tick_enabled():
            ticking[cls] += 1
        if "Light" in cls and cls not in ("LightmassImportanceVolume",):
            lights[cls] += 1
        if cls.startswith("InfinityStageEffectSource") or "EffectSource" in cls:
            effects.append({"label": actor.get_actor_label(), "class": cls,
                            "fx": len(actor.get_components_by_class(unreal.FXSystemComponent))})
    del world
    report = {"actors": total, "ticking_by_class": dict(ticking.most_common(40)), "lights_by_class": dict(lights),
              "effect_sources": len(effects), "effect_samples": effects[:15]}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "inspect_tickers.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1)
    unreal.log("PUSS_SOFTGOODS_TICKERS|" + json.dumps({"actors": total, "effect_sources": len(effects)}))


main()
