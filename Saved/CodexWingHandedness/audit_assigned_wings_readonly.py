"""Read-only inventory of every WingPair assigned in the production Show Asset.

Writes Saved/CodexWingHandedness/assigned_wings.json and does not save assets.
"""

import collections
import json
import os
import re

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL_RE = re.compile(r"^P(?P<passage>\d{2}) Wing (?P<ordinal>\d{3})$")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_package(value):
    if value is None:
        return "None"
    if hasattr(value, "get_path_name"):
        return value.get_path_name().split(".", 1)[0]
    return str(value).split(".", 1)[0]


def dirty_packages():
    return {
        "content": [
            asset_package(item)
            for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        ],
        "maps": [
            asset_package(item)
            for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        ],
    }


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Unexpected world: {world_path}")
require(editor.get_game_world() is None, "PIE/SIE is active")

dirty_before = dirty_packages()
require(not dirty_before["content"], f"Dirty content before audit: {dirty_before['content']}")
require(not dirty_before["maps"], f"Dirty maps before audit: {dirty_before['maps']}")

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, f"Show Asset did not load: {SHOW_PATH}")
cues = list(show.get_editor_property("cues"))
library_ref = show.get_editor_property("wing_library")
library = library_ref
if library_ref is not None and hasattr(library_ref, "load_synchronous"):
    library = library_ref.load_synchronous()
require(library is not None, "Show Asset Wing Library did not load")
library_entries = {}
for entry in list(library.get_editor_property("entries")):
    mesh_path = asset_package(entry.get_editor_property("mesh"))
    adjustment = entry.get_editor_property("placement_adjustment")
    scale = adjustment.scale3d
    library_entries[mesh_path] = {
        "role": str(entry.get_editor_property("role")),
        "status": str(entry.get_editor_property("status")),
        "tall_edge_after_correction": str(
            entry.get_editor_property("tall_edge_after_correction")
        ),
        "front_axis": str(entry.get_editor_property("front_axis")),
        "placement_scale": [float(scale.x), float(scale.y), float(scale.z)],
        "photographic_mirror_approved": bool(
            entry.get_editor_property("photographic_mirror_approved")
        ),
        "source_image": str(entry.get_editor_property("source_image")),
        "notes": str(entry.get_editor_property("notes")),
    }

rows = []
by_passage = collections.Counter()
for cue_index, cue in enumerate(cues):
    label = str(cue.get_editor_property("label"))
    match = LABEL_RE.match(label)
    if match is None:
        continue
    pair = cue.get_editor_property("wing_pair")
    panels = {}
    for role in ("left", "right", "top"):
        panel = pair.get_editor_property(role)
        panels[role] = {
            "mesh": asset_package(panel.get_editor_property("mesh")),
            "flip_image_horizontally": bool(
                panel.get_editor_property("flip_image_horizontally")
            ),
        }
    passage = int(match.group("passage"))
    by_passage[passage] += 1
    rows.append(
        {
            "cue_index": cue_index,
            "label": label,
            "passage": passage,
            "ordinal": int(match.group("ordinal")),
            "has_top": bool(pair.get_editor_property("has_top")),
            "left": panels["left"],
            "right": panels["right"],
            "top": panels["top"],
        }
    )

require(rows, "No assigned WingPair cues were found")
dirty_after = dirty_packages()
require(not dirty_after["content"], f"Audit dirtied content: {dirty_after['content']}")
require(not dirty_after["maps"], f"Audit dirtied maps: {dirty_after['maps']}")

unique_by_role = {}
for role in ("left", "right", "top"):
    unique_by_role[role] = sorted(
        {row[role]["mesh"] for row in rows if row[role]["mesh"] != "None"}
    )

passage_actors = []
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    try:
        actor_show = actor.get_editor_property("show_asset")
    except Exception:
        continue
    if actor_show != show:
        continue
    passage_actors.append(
        {
            "label": actor.get_actor_label(),
            "passage_guid": str(actor.get_editor_property("passage_guid")),
        }
    )

payload = {
    "status": "ok",
    "world": world_path,
    "show_asset": SHOW_PATH,
    "wing_library": asset_package(library),
    "show_cue_count": len(cues),
    "wing_row_count": len(rows),
    "rows_by_passage": {str(key): by_passage[key] for key in sorted(by_passage)},
    "unique_by_role": unique_by_role,
    "passage_actors": sorted(passage_actors, key=lambda item: item["label"]),
    "library_entries_for_assigned_meshes": {
        mesh_path: library_entries.get(mesh_path)
        for mesh_path in sorted(
            set(unique_by_role["left"])
            | set(unique_by_role["right"])
            | set(unique_by_role["top"])
        )
    },
    "dirty_before": dirty_before,
    "dirty_after": dirty_after,
    "rows": rows,
}

output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingHandedness",
    "assigned_wings.json",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "WING_HANDEDNESS_ASSIGNMENT_AUDIT_SUCCESS"
    f"|rows={len(rows)}"
    f"|passages={dict(sorted(by_passage.items()))}"
    f"|unique_left={len(unique_by_role['left'])}"
    f"|unique_right={len(unique_by_role['right'])}"
    f"|unique_top={len(unique_by_role['top'])}"
    "|dirty=0"
)
