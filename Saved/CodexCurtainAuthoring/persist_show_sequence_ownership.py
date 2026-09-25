"""Persist the seven nested sequence-owned curtain fields in the Show cue array."""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
INTERACTION_DIR = "/Game/InfinityStage/Interactions"
DASH = chr(0x2014)
BLOCKS = [
    ("Opening " + DASH + " Curtain", "LS_Opening_Curtain", False),
    ("Interaction 1 " + DASH + " Washing the Boy", "LS_Interaction_01_WashingTheBoy", True),
    ("Interaction 2 " + DASH + " Turnips", "LS_Interaction_02_Turnips", True),
    ("Interaction 3 " + DASH + " Forgets His Name", "LS_Interaction_03_ForgetsHisName", True),
    ("Interaction 4 " + DASH + " Gets a Name", "LS_Interaction_04_GetsAName", True),
    ("Interaction 5 " + DASH + " Becomes King", "LS_Interaction_05_BecomesKing", True),
    ("Closing " + DASH + " Sweeping Up", "LS_Closing_Curtain", False),
]


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def package_path(value):
    return object_path(value).split(".", 1)[0]


def package_name(value):
    try:
        return str(value.get_name())
    except Exception:
        return str(value)


def cue_label(cue):
    return str(cue.get_editor_property("label"))


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world_path = package_path(editor.get_editor_world())
if world_path != EXPECTED_WORLD or editor.get_game_world() is not None:
    raise RuntimeError(f"Unsafe editor state: world={world_path}, game_world={editor.get_game_world()}")

dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
if dirty_content or dirty_maps:
    raise RuntimeError(f"Show fix requires a clean editor: {dirty_content}/{dirty_maps}")

show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError(f"Missing Show: {SHOW_PATH}")
cues = list(show.get_editor_property("cues"))
managed = {}
for cue in cues:
    label = cue_label(cue)
    if any(label == block[0] for block in BLOCKS):
        if label in managed:
            raise RuntimeError(f"Duplicate managed cue: {label}")
        managed[label] = cue
if set(managed) != {block[0] for block in BLOCKS}:
    raise RuntimeError(f"Managed cue mismatch: {sorted(managed)}")

for label, asset_name, _ in BLOCKS:
    scene = managed[label].get_editor_property("scene")
    if package_path(scene.get_editor_property("sequence")) != INTERACTION_DIR + "/" + asset_name:
        raise RuntimeError(f"Unexpected sequence on {label}")
    if bool(scene.get_editor_property("sequence_owns_curtain")):
        raise RuntimeError(f"{label} already sequence-owns curtain; refusing non-one-shot fix")
    if bool(scene.get_editor_property("reveal_next_passage_when_covered")):
        raise RuntimeError(f"{label} already reveals covered passage; refusing non-one-shot fix")

for label, _, reveal in BLOCKS:
    cue = managed[label]
    scene = cue.get_editor_property("scene")
    scene.set_editor_property("sequence_owns_curtain", True)
    scene.set_editor_property("reveal_next_passage_when_covered", bool(reveal))
    cue.set_editor_property("scene", scene)

show.set_editor_property("cues", cues)
dirty_before_save = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_before_save = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_before_save != [SHOW_PATH] or dirty_maps_before_save:
    raise RuntimeError(
        f"Unexpected dirty scope before Show save: "
        f"content={dirty_before_save}, maps={dirty_maps_before_save}"
    )
if not unreal.EditorAssetLibrary.save_loaded_asset(show, False):
    raise RuntimeError(f"Save failed for {SHOW_PATH}")

dirty_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_after or dirty_maps_after:
    raise RuntimeError(f"Show fix left dirty packages: {dirty_after}/{dirty_maps_after}")

saved_rows = []
readback = {cue_label(cue): cue for cue in show.get_editor_property("cues")}
for label, _, reveal in BLOCKS:
    scene = readback[label].get_editor_property("scene")
    owns = bool(scene.get_editor_property("sequence_owns_curtain"))
    actual_reveal = bool(scene.get_editor_property("reveal_next_passage_when_covered"))
    if not owns or actual_reveal != reveal:
        raise RuntimeError(
            f"In-memory Show readback mismatch on {label}: owns={owns}, "
            f"reveal={actual_reveal}, expected_reveal={reveal}"
        )
    saved_rows.append(
        {
            "label": label,
            "sequence_owns_curtain": owns,
            "reveal_next_passage_when_covered": actual_reveal,
        }
    )

payload = {
    "status": "ok",
    "world": world_path,
    "saved": [SHOW_PATH],
    "rows": saved_rows,
    "dirty_content_after": dirty_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "persist_show_sequence_ownership.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_SHOW_PERSIST_SUCCESS"
    f"|show_cues={len(saved_rows)}|saved=1|dirty_content=0|dirty_maps=0"
)
