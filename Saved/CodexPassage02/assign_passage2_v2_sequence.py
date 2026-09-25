import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
BACKUP_PATH = (
    "/Game/InfinityStage/Dev/SavedVersions/"
    "DA_InfinityStage_V1Show_P02_PreAnimalsToShrineV2_20260815"
)
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MESH_ROOT = "/Game/Wings/Passage02_AnimalsToShrineV2/StaticMeshes"
ACTOR_LABEL = "Passage 02 — Fixed Wings"
SET_SEQUENCE = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2,
    13, 14, 15, 16, 13,
    17, 18, 19, 20,
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def package_name(value):
    if value is None:
        return "None"
    if hasattr(value, "get_path_name"):
        return value.get_path_name().split(".", 1)[0]
    return str(value)


def load_asset(path, expected_class=None):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    require(asset is not None, f"Asset did not load: {path}")
    if expected_class is not None:
        require(isinstance(asset, expected_class), f"Wrong asset class: {path}")
    return asset


editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor_subsystem.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Wrong world open: {world_path}")
require(editor_subsystem.get_game_world() is None, "PIE/SIE is active")

dirty_content_before = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps_before = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(
    "P02_V2_ASSIGN_PREFLIGHT"
    f"|dirty_content={','.join(package_name(item) for item in dirty_content_before)}"
    f"|dirty_maps={','.join(package_name(item) for item in dirty_maps_before)}"
)
require(not dirty_content_before, "Unrelated dirty content packages are present")
require(not dirty_maps_before, "The current level is already dirty; refusing scoped save")

show = load_asset(SHOW_PATH)
if not unreal.EditorAssetLibrary.does_asset_exist(BACKUP_PATH):
    backup = unreal.EditorAssetLibrary.duplicate_asset(SHOW_PATH, BACKUP_PATH)
    require(backup is not None, "Failed to create pre-Passage-2 backup")
    require(
        unreal.EditorAssetLibrary.save_asset(BACKUP_PATH, only_if_is_dirty=False),
        "Failed to save pre-Passage-2 backup",
    )
else:
    backup = load_asset(BACKUP_PATH)

cues = list(show.get_editor_property("cues"))
p02_rows = [
    (index, cue)
    for index, cue in enumerate(cues)
    if str(cue.get_editor_property("label")).startswith("P02 Wing ")
]
require(len(p02_rows) == 23, f"Expected 23 Passage 2 rows, found {len(p02_rows)}")
require(
    [index for index, _cue in p02_rows] == list(range(49, 72)),
    f"Unexpected Passage 2 cue indexes: {[index for index, _cue in p02_rows]}",
)
require(
    [str(cue.get_editor_property("label")) for _index, cue in p02_rows]
    == [f"P02 Wing {ordinal:03d}" for ordinal in range(1, 24)],
    "Passage 2 row labels are not the expected stable sequence",
)

template_pair = p02_rows[0][1].get_editor_property("wing_pair")
template_top = template_pair.get_editor_property("top")
top_transform = template_top.get_editor_property("local_transform")
top_facing_policy = template_top.get_editor_property("facing_policy")

for ordinal, ((cue_index, cue), set_number) in enumerate(
    zip(p02_rows, SET_SEQUENCE), start=1
):
    pair = cue.get_editor_property("wing_pair")
    left = pair.get_editor_property("left")
    right = pair.get_editor_property("right")
    top = pair.get_editor_property("top")

    left_mesh = load_asset(
        f"{MESH_ROOT}/SM_P02_SET{set_number:02d}_L", unreal.StaticMesh
    )
    right_mesh = load_asset(
        f"{MESH_ROOT}/SM_P02_SET{set_number:02d}_R", unreal.StaticMesh
    )
    top_mesh = load_asset(
        f"{MESH_ROOT}/SM_P02_SET{set_number:02d}_T", unreal.StaticMesh
    )

    left.set_editor_property("mesh", left_mesh)
    left.set_editor_property("flip_image_horizontally", False)
    left.set_editor_property("material_overrides", [])
    pair.set_editor_property("left", left)

    right.set_editor_property("mesh", right_mesh)
    right.set_editor_property("flip_image_horizontally", False)
    right.set_editor_property("material_overrides", [])
    pair.set_editor_property("right", right)

    top.set_editor_property("mesh", top_mesh)
    top.set_editor_property("local_transform", top_transform)
    top.set_editor_property("facing_policy", top_facing_policy)
    top.set_editor_property("flip_image_horizontally", False)
    top.set_editor_property("material_overrides", [])
    pair.set_editor_property("top", top)
    pair.set_editor_property("has_top", True)

    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue
    unreal.log(
        "P02_V2_ASSIGN_ROW"
        f"|ordinal={ordinal}|cue_index={cue_index}|set={set_number:02d}"
    )

show.set_editor_property("cues", cues)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
matches = []
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    if actor.get_actor_label() != ACTOR_LABEL:
        continue
    try:
        actor_show = actor.get_editor_property("show_asset")
    except Exception:
        continue
    if actor_show == show:
        matches.append(actor)
require(len(matches) == 1, f"Expected one Passage 2 actor, found {len(matches)}")
actor = matches[0]
materialized = actor.materialize_passage()
require(bool(materialized), "Passage 2 materialization failed")

dirty_content_mid = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps_mid = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
content_names_mid = {package_name(item) for item in dirty_content_mid}
map_names_mid = {package_name(item) for item in dirty_maps_mid}
require(
    content_names_mid.issubset({SHOW_PATH}),
    f"Unexpected dirty content after scoped mutation: {sorted(content_names_mid)}",
)
require(
    map_names_mid.issubset({EXPECTED_WORLD}),
    f"Unexpected dirty maps after scoped mutation: {sorted(map_names_mid)}",
)

show_saved = unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False)
require(show_saved, "Show Asset save failed")
level_saved = unreal.EditorLevelLibrary.save_current_level()
require(level_saved, "Current level save failed")

unreal.log(
    "P02_ANIMALS_SHRINE_ASSIGN_SUCCESS"
    "|rows=23|stage_counts=14,5,4"
    "|sets=01,02,03,04,05,06,07,08,09,10,11,12,01,02,13,14,15,16,13,17,18,19,20"
    "|left_flips=0|right_flips=0|top_flips=0|tops=23"
    f"|materialized=1|show_saved={int(bool(show_saved))}"
    f"|level_saved={int(bool(level_saved))}|backup={BACKUP_PATH}"
)
