"""Read-only dump of the Passage 3 cue rows and their assigned wing meshes.

Compares what the Show Asset currently holds against the canonical row pattern in
wing_integration_common, so a verifier row mismatch can be told apart from an
intentional re-ordering in the cue desk. Writes inspect_p03_rows.json.
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
mesh_root = f"{config['content_root']}/StaticMeshes"

cues = list(show.get_editor_property("cues"))
rows = [
    (index, cue)
    for index, cue in enumerate(cues)
    if str(cue.get_editor_property("label")).startswith(config["label_prefix"])
]

records = []
mismatches = 0
for ordinal, ((index, cue), expected) in enumerate(zip(rows, config["rows"]), start=1):
    pair = cue.get_editor_property("wing_pair")
    entry = {
        "ordinal": ordinal,
        "cue_index": index,
        "label": str(cue.get_editor_property("label")),
        "has_top": bool(pair.get_editor_property("has_top")),
    }
    for role in ("left", "right", "top"):
        panel = pair.get_editor_property(role)
        actual = wing_integration_common.asset_package(panel.get_editor_property("mesh"))
        want = f"{mesh_root}/SM_{expected[role]}"
        entry[role] = {
            "actual": actual.rsplit("/", 1)[-1],
            "expected": want.rsplit("/", 1)[-1],
            "match": actual == want,
            "flip": bool(panel.get_editor_property("flip_image_horizontally")),
        }
        if actual != want:
            mismatches += 1
    records.append(entry)

payload = {
    "row_count": len(rows),
    "expected_row_count": config["row_count"],
    "cue_indexes": [index for index, _ in rows],
    "role_mismatches": mismatches,
    "rows": records,
}
output = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "inspect_p03_rows.json",
)
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(f"P03_ROW_INSPECT_SUCCESS|rows={len(rows)}|role_mismatches={mismatches}")
