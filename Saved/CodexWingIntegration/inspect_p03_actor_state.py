"""Read-only check that the Passage 3 actor is materialized and using the meshes.

If the wings look unchanged after a mesh reimport, this distinguishes "the actor
never materialized / points elsewhere" from "the actor is correct and the visual
difference is just subtle".
"""

import importlib
import json
import os
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wing_integration_common

importlib.reload(wing_integration_common)

config = wing_integration_common.config_for(3)
show = wing_integration_common.load_asset(wing_integration_common.SHOW_PATH)
actor = wing_integration_common.find_passage_actor(config, show)

materialized = int(actor.get_editor_property("materialized_wing_pair_count"))

# Which static meshes are actually referenced by components in the level right now.
used = {}
for component in actor.get_components_by_class(unreal.StaticMeshComponent):
    mesh = component.get_editor_property("static_mesh")
    if mesh is None:
        continue
    name = mesh.get_name()
    used[name] = used.get(name, 0) + 1

p03_used = {k: v for k, v in used.items() if k.startswith("SM_P03_")}
other_used = {k: v for k, v in used.items() if not k.startswith("SM_P03_")}

payload = {
    "actor_label": str(actor.get_actor_label()),
    "materialized_wing_pair_count": materialized,
    "expected_row_count": config["row_count"],
    "static_mesh_components": sum(used.values()),
    "distinct_p03_meshes_in_use": len(p03_used),
    "p03_mesh_usage": p03_used,
    "non_p03_meshes_in_use": other_used,
    "actor_hidden": bool(actor.is_hidden_ed()),
}
output = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "inspect_p03_actor_state.json",
)
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    f"P03_ACTOR_STATE|materialized={materialized}|components={sum(used.values())}"
    f"|distinct_p03_meshes={len(p03_used)}|hidden={payload['actor_hidden']}"
)
