"""Correct obvious active Wing handedness without altering source assets or Top panels."""

import collections
import json
import os
import re

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL_RE = re.compile(r"^P(?P<passage>\d{2}) Wing (?P<ordinal>\d{3})$")
EXPECTED_COUNTS = {1: 48, 2: 23, 3: 21, 4: 21, 5: 93, 6: 55}
EXPECTED_LEFT_FLIPS = 173
EXPECTED_RIGHT_FLIPS = 48
BACKUP_FOLDER = "Backups/PreWingHandedness-20260915-190308"
AFFECTED_ACTORS = {
    "Passage 01 — Fixed Wings",
    "Passage 02 — Fixed Wings",
    "Passage 04 — Fixed Wings",
    "Passage 05 — Fixed Wings",
    "Passage 06 — Fixed Wings",
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


def dirty_packages():
    return {
        "content": {
            asset_package(item)
            for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        },
        "maps": {
            asset_package(item)
            for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        },
    }


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Unexpected world: {world_path}")
require(editor.get_game_world() is None, "PIE/SIE is active")
require(not dirty_packages()["content"], "Dirty content exists before mutation")
require(not dirty_packages()["maps"], "Dirty maps exist before mutation")
require(
    os.path.isfile(os.path.join(unreal.Paths.project_dir(), BACKUP_FOLDER, "DA_InfinityStage_V1Show.uasset")),
    "Timestamped Show backup is missing",
)
require(
    os.path.isfile(os.path.join(unreal.Paths.project_dir(), BACKUP_FOLDER, "L_InfinityStage_V1VerticalSlice.umap")),
    "Timestamped level backup is missing",
)

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, f"Show Asset did not load: {SHOW_PATH}")
cues = list(show.get_editor_property("cues"))
rows = []
counts = collections.Counter()
left_flips = 0
right_flips = 0
for cue_index, cue in enumerate(cues):
    label = str(cue.get_editor_property("label"))
    match = LABEL_RE.match(label)
    if match is None:
        continue
    passage = int(match.group("passage"))
    counts[passage] += 1
    pair = cue.get_editor_property("wing_pair")
    left_flips += int(bool(pair.get_editor_property("left").get_editor_property("flip_image_horizontally")))
    right_flips += int(bool(pair.get_editor_property("right").get_editor_property("flip_image_horizontally")))
    rows.append((cue_index, cue, passage, int(match.group("ordinal"))))

require(dict(sorted(counts.items())) == EXPECTED_COUNTS, f"Wing row counts changed: {dict(counts)}")
require(left_flips == EXPECTED_LEFT_FLIPS, f"Expected {EXPECTED_LEFT_FLIPS} left flips, found {left_flips}")
require(right_flips == EXPECTED_RIGHT_FLIPS, f"Expected {EXPECTED_RIGHT_FLIPS} right flips, found {right_flips}")

by_label = collections.defaultdict(list)
for row in rows:
    by_label[str(row[1].get_editor_property("label"))].append(row)
require(len(by_label["P02 Wing 001"]) == 1, "P02 Wing 001 is not unique")
require(len(by_label["P02 Wing 002"]) == 1, "P02 Wing 002 is not unique")

p02_root = "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2/StaticMeshes"
p02_expected = {
    "P02 Wing 001": {
        "before_left": f"{p02_root}/SM_P02_SET01_R",
        "before_right": f"{p02_root}/SM_P02_SET01_L",
        "after_left": f"{p02_root}/SM_P02_SET01_L",
        "after_right": f"{p02_root}/SM_P02_SET01_R",
    },
    "P02 Wing 002": {
        "before_left": f"{p02_root}/SM_P02_SET02_L",
        "before_right": f"{p02_root}/SM_P02_SET02_L",
        "after_left": f"{p02_root}/SM_P02_SET02_L",
        "after_right": f"{p02_root}/SM_P02_SET02_R",
    },
}

for label, expected in p02_expected.items():
    cue_index, cue, _passage, _ordinal = by_label[label][0]
    pair = cue.get_editor_property("wing_pair")
    left = pair.get_editor_property("left")
    right = pair.get_editor_property("right")
    require(asset_package(left.get_editor_property("mesh")) == expected["before_left"], f"{label} left assignment changed")
    require(asset_package(right.get_editor_property("mesh")) == expected["before_right"], f"{label} right assignment changed")
    left_mesh = unreal.EditorAssetLibrary.load_asset(expected["after_left"])
    right_mesh = unreal.EditorAssetLibrary.load_asset(expected["after_right"])
    require(left_mesh is not None and right_mesh is not None, f"{label} replacement mesh did not load")
    left.set_editor_property("mesh", left_mesh)
    right.set_editor_property("mesh", right_mesh)
    pair.set_editor_property("left", left)
    pair.set_editor_property("right", right)
    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue

changed_left = 0
changed_right = 0
for cue_index, cue, _passage, _ordinal in rows:
    pair = cue.get_editor_property("wing_pair")
    for side in ("left", "right"):
        panel = pair.get_editor_property(side)
        was_flipped = bool(panel.get_editor_property("flip_image_horizontally"))
        if was_flipped:
            if side == "left":
                changed_left += 1
            else:
                changed_right += 1
            panel.set_editor_property("flip_image_horizontally", False)
            pair.set_editor_property(side, panel)
    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue

require(changed_left == EXPECTED_LEFT_FLIPS, f"Left repair count mismatch: {changed_left}")
require(changed_right == EXPECTED_RIGHT_FLIPS, f"Right repair count mismatch: {changed_right}")
show.modify()
show.set_editor_property("cues", cues)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = []
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    if actor.get_actor_label() not in AFFECTED_ACTORS:
        continue
    try:
        actor_show = actor.get_editor_property("show_asset")
    except Exception:
        continue
    if actor_show == show:
        actors.append(actor)
require({actor.get_actor_label() for actor in actors} == AFFECTED_ACTORS, "Affected Passage actors did not resolve exactly")

materialized = {}
for actor in sorted(actors, key=lambda item: item.get_actor_label()):
    require(bool(actor.materialize_passage()), f"Materialization failed: {actor.get_actor_label()}")
    materialized[actor.get_actor_label()] = int(actor.get_editor_property("materialized_wing_pair_count"))

dirty_mid = dirty_packages()
require(dirty_mid["content"].issubset({SHOW_PATH}), f"Unexpected dirty content: {sorted(dirty_mid['content'])}")
require(dirty_mid["maps"].issubset({EXPECTED_WORLD}), f"Unexpected dirty maps: {sorted(dirty_mid['maps'])}")
require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False), "Show Asset save failed")
level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
require(bool(level_editor.save_current_level()), "Current level save failed")
dirty_after = dirty_packages()
require(not dirty_after["content"], f"Dirty content after targeted save: {sorted(dirty_after['content'])}")
require(not dirty_after["maps"], f"Dirty maps after targeted save: {sorted(dirty_after['maps'])}")

result = {
    "status": "ok",
    "backup_folder": BACKUP_FOLDER,
    "wing_rows": len(rows),
    "left_flips_cleared": changed_left,
    "right_flips_cleared": changed_right,
    "p02_assignments_repaired": sorted(p02_expected),
    "materialized": materialized,
    "show_saved": True,
    "level_saved": True,
    "dirty_after": {"content": [], "maps": []},
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingHandedness",
    "apply_result.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)

unreal.log(
    "WING_HANDEDNESS_FIX_SUCCESS"
    f"|rows={len(rows)}|left_flips_cleared={changed_left}"
    f"|right_flips_cleared={changed_right}|p02_assignments=2"
    f"|materialized={len(materialized)}|show_saved=1|level_saved=1|dirty=0"
)
