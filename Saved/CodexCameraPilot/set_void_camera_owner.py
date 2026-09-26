"""A.5 / F.5: give the Void (Scene 6) camera to the dog as Free Look.

Implements the 21 Aug decision "Dog owns the Void camera -> Free Look, not Gaze",
which was never applied to the Show. One field, idempotent, saves only the Show.
Backup: Backups/PreVoidCameraOwner-20260925-200315.
Success marker: PUSS_VOID_CAMERA_OWNER_SET
"""

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SHOW_PACKAGE = SHOW_PATH

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None:
    raise RuntimeError("No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")


def dirty_content():
    return sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())


if dirty_content():
    raise RuntimeError(f"Content is already dirty; refusing to write: {dirty_content()}")

show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError("Show asset did not load")

cues = list(show.get_editor_property("cues"))
scene_indices = [
    i for i, cue in enumerate(cues) if cue.get_editor_property("type") == unreal.InfinityCueType.SCENE
]
matches = [i for i in scene_indices if str(cues[i].get_editor_property("label")).startswith("Scene 6")]
if len(scene_indices) != 6 or len(matches) != 1 or matches[0] != scene_indices[-1]:
    raise RuntimeError(f"Expected six Scenes with Scene 6 last; scenes={scene_indices} matches={matches}")
index = matches[0]

owners_before = [
    cues[i].get_editor_property("scene").get_editor_property("camera_owner") for i in scene_indices
]
passage_owners_before = [
    p.get_editor_property("camera_owner") for p in show.get_editor_property("passage_settings")
]

cue = cues[index]
scene = cue.get_editor_property("scene")
before = scene.get_editor_property("camera_owner")
changed = False
if before == unreal.InfinityCameraOwner.DOG_FREE_LOOK:
    pass
elif before == unreal.InfinityCameraOwner.TIMELINE:
    scene.set_editor_property("camera_owner", unreal.InfinityCameraOwner.DOG_FREE_LOOK)
    cue.set_editor_property("scene", scene)
    cues[index] = cue
    show.set_editor_property("cues", cues)
    changed = True
else:
    raise RuntimeError(f"Scene 6 camera owner is {before}, neither Timeline nor DogFreeLook; not touching it")

# In-memory read-back: exactly this one field differs.
cues_after = list(show.get_editor_property("cues"))
owners_after = [
    cues_after[i].get_editor_property("scene").get_editor_property("camera_owner") for i in scene_indices
]
passage_owners_after = [
    p.get_editor_property("camera_owner") for p in show.get_editor_property("passage_settings")
]
if len(cues_after) != len(cues):
    raise RuntimeError("Cue count changed")
if owners_after[-1] != unreal.InfinityCameraOwner.DOG_FREE_LOOK:
    raise RuntimeError("Scene 6 did not take DogFreeLook")
if owners_after[:-1] != owners_before[:-1] or passage_owners_after != passage_owners_before:
    raise RuntimeError("Another camera owner changed")

saved = True
if changed:
    dirty = dirty_content()
    if dirty != [SHOW_PACKAGE]:
        raise RuntimeError(f"Unexpected dirty content before save: {dirty}")
    saved = unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False)
    if not saved:
        raise RuntimeError("Show save failed")
if dirty_content():
    raise RuntimeError(f"Content still dirty after save: {dirty_content()}")

unreal.log(
    "PUSS_VOID_CAMERA_OWNER_SET"
    f"|cue_index={index}|label={cues_after[index].get_editor_property('label')}"
    f"|before={before}|after={owners_after[-1]}|changed={int(changed)}|saved={int(saved)}"
)
