"""Read back the saved Show and materialized actors after handedness correction."""

import collections
import json
import os
import re

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL_RE = re.compile(r"^P(?P<passage>\d{2}) Wing (?P<ordinal>\d{3})$")
EXPECTED_COUNTS = {1: 48, 2: 23, 3: 21, 4: 21, 5: 93, 6: 55}
EXPECTED_MATERIALIZED = {
    "Passage 01 — Fixed Wings": 48,
    "Passage 02 — Fixed Wings": 23,
    "Passage 04 — Fixed Wings": 21,
    "Passage 05 — Fixed Wings": 93,
    "Passage 06 — Fixed Wings": 55,
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_package(value):
    if value is None:
        return "None"
    if hasattr(value, "get_path_name"):
        return value.get_path_name().split(".", 1)[0]
    return str(value).split(".", 1)[0]


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Unexpected world: {world_path}")
require(editor.get_game_world() is None, "PIE/SIE is active")
require(not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "Dirty content before verification")
require(not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "Dirty maps before verification")

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, "Show Asset did not load")
cues = list(show.get_editor_property("cues"))
rows = []
counts = collections.Counter()
for cue_index, cue in enumerate(cues):
    label = str(cue.get_editor_property("label"))
    match = LABEL_RE.match(label)
    if match is None:
        continue
    passage = int(match.group("passage"))
    counts[passage] += 1
    pair = cue.get_editor_property("wing_pair")
    for side in ("left", "right"):
        panel = pair.get_editor_property(side)
        require(not bool(panel.get_editor_property("flip_image_horizontally")), f"Flip remains: {label} {side}")
    rows.append((cue_index, cue, passage, int(match.group("ordinal"))))
require(dict(sorted(counts.items())) == EXPECTED_COUNTS, f"Wing row counts changed: {dict(counts)}")

by_label = collections.defaultdict(list)
for row in rows:
    by_label[str(row[1].get_editor_property("label"))].append(row)
p02_root = "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2/StaticMeshes"
for label, set_number in (("P02 Wing 001", 1), ("P02 Wing 002", 2)):
    require(len(by_label[label]) == 1, f"{label} is not unique")
    pair = by_label[label][0][1].get_editor_property("wing_pair")
    left_path = asset_package(pair.get_editor_property("left").get_editor_property("mesh"))
    right_path = asset_package(pair.get_editor_property("right").get_editor_property("mesh"))
    require(left_path == f"{p02_root}/SM_P02_SET{set_number:02d}_L", f"Wrong saved left mesh: {label}")
    require(right_path == f"{p02_root}/SM_P02_SET{set_number:02d}_R", f"Wrong saved right mesh: {label}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
materialized = {}
for actor in actor_subsystem.get_all_level_actors():
    label = actor.get_actor_label()
    if actor.get_class().get_name() != "InfinityStagePassageActor" or label not in EXPECTED_MATERIALIZED:
        continue
    if actor.get_editor_property("show_asset") != show:
        continue
    count = int(actor.get_editor_property("materialized_wing_pair_count"))
    require(count == EXPECTED_MATERIALIZED[label], f"Materialized count mismatch: {label}={count}")
    materialized[label] = count
require(materialized == EXPECTED_MATERIALIZED, f"Passage actor read-back mismatch: {materialized}")
require(not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "Verification dirtied content")
require(not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "Verification dirtied maps")

result = {
    "status": "ok",
    "world": world_path,
    "wing_rows": len(rows),
    "rows_by_passage": dict(sorted(counts.items())),
    "left_right_flips": 0,
    "p02_assignments_verified": ["P02 Wing 001", "P02 Wing 002"],
    "materialized": materialized,
    "dirty": 0,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingHandedness",
    "verify_result.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)

unreal.log(
    "WING_HANDEDNESS_VERIFY_SUCCESS"
    f"|rows={len(rows)}|passages={dict(sorted(counts.items()))}"
    "|left_right_flips=0|p02_assignments=2|materialized=5|dirty=0"
)
