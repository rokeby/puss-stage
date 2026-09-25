import json
import os

import unreal


def guid_parts(value):
    parts = {}
    for name in ("a", "b", "c", "d"):
        try:
            parts[name] = int(getattr(value, name))
            continue
        except Exception:
            pass
        try:
            parts[name] = int(value.get_editor_property(name))
        except Exception as exc:
            parts[name] = f"unavailable:{exc}"
    return parts


rows = []
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    show = actor.get_editor_property("show_asset")
    rows.append(
        {
            "label": actor.get_actor_label(),
            "show": show.get_path_name() if show else "None",
            "passage_guid": guid_parts(actor.get_editor_property("passage_guid")),
            "materialized": int(actor.get_editor_property("materialized_wing_pair_count")),
            "budget": int(actor.get_editor_property("component_budget")),
        }
    )
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "inspect_passage_actors.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(rows, handle, indent=2, sort_keys=True)
unreal.log(f"PUSS_PASSAGE_ACTOR_INSPECT_SUCCESS|actors={len(rows)}")
