"""READ-ONLY (29 Sep): what does LS_Opening_Curtain_Baked's drape spawnable TEMPLATE hold right now? The fall bench's
transient running=True was copied back into the template by Sequencer, dirtying the (unsaved) sequence. Writes nothing."""
import json
import os

import unreal


def main():
    seq = unreal.load_asset("/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked")
    report = {"dirty": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
              + sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
    for b in seq.get_bindings():
        if str(b.get_display_name()) != "Opening Drape (baked)":
            continue
        tmpl = b.get_object_template()
        comp = tmpl.get_editor_property("geometry_cache_component")
        row = {"template_class": tmpl.get_class().get_name(), "loc": str(tmpl.get_actor_location()),
               "rot": str(tmpl.get_actor_rotation())}
        for prop in ("running", "looping", "manual_tick", "extrapolate_frames", "start_time_offset", "playback_speed",
                     "geometry_cache", "elapsed_time"):
            try:
                v = comp.get_editor_property(prop)
                row[prop] = v.get_path_name() if hasattr(v, "get_path_name") else v
            except Exception as exc:  # noqa: BLE001
                row[prop] = f"n/a ({type(exc).__name__})"
        row["tracks"] = [t.get_class().get_name() for t in b.get_tracks()]
        report["drape_template"] = row
        del tmpl, comp
    del seq
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "inspect_opening_template.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log("PUSS_SOFTGOODS_OPENING_TEMPLATE|" + json.dumps(report, default=str))


main()
