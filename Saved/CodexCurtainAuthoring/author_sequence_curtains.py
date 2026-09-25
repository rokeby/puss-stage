"""Author the sequence-owned production curtain rig and tracks.

This is a guarded one-shot mutation. It requires the intended map, no PIE/SIE,
a clean editor, an absent target Blueprint, and eight still-empty managed
Level Sequences. It saves only the Blueprint, those sequences, and the Show.
"""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
INTERACTION_DIR = "/Game/InfinityStage/Interactions"
BLUEPRINT_PATH = INTERACTION_DIR + "/BP_InfinityStageSequenceCurtain"
CURTAIN_ASSET_PATH = "/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/SM_FireSafetyCurtain_01"
DISPLAY_RATE = unreal.FrameRate(numerator=25, denominator=1)
TICK_RESOLUTION = unreal.FrameRate(numerator=24000, denominator=1)
PLAYBACK_END = 375

DASH = chr(0x2014)
BLOCKS = [
    {
        "label": "Opening " + DASH + " Curtain",
        "asset": "LS_Opening_Curtain",
        "keys": [(0, 1.0), (50, 1.0), (150, 0.0), (375, 0.0)],
        "mode": unreal.InfinityCurtainCueMode.OPENING_REVEAL,
        "timing": (0, 48000, 96000),
        "reveal": False,
    },
    {
        "label": "Interaction 1 " + DASH + " Washing the Boy",
        "asset": "LS_Interaction_01_WashingTheBoy",
        "keys": [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
        "mode": unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL,
        "timing": (48000, 264000, 48000),
        "reveal": True,
    },
    {
        "label": "Interaction 2 " + DASH + " Turnips",
        "asset": "LS_Interaction_02_Turnips",
        "keys": [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
        "mode": unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL,
        "timing": (48000, 264000, 48000),
        "reveal": True,
    },
    {
        "label": "Interaction 3 " + DASH + " Forgets His Name",
        "asset": "LS_Interaction_03_ForgetsHisName",
        "keys": [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
        "mode": unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL,
        "timing": (48000, 264000, 48000),
        "reveal": True,
    },
    {
        "label": "Interaction 4 " + DASH + " Gets a Name",
        "asset": "LS_Interaction_04_GetsAName",
        "keys": [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
        "mode": unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL,
        "timing": (48000, 264000, 48000),
        "reveal": True,
    },
    {
        "label": "Interaction 5 " + DASH + " Becomes King",
        "asset": "LS_Interaction_05_BecomesKing",
        "keys": [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
        "mode": unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL,
        "timing": (48000, 264000, 48000),
        "reveal": True,
    },
    {
        "label": "Closing " + DASH + " Sweeping Up",
        "asset": "LS_Closing_Curtain",
        "keys": [(0, 0.0), (100, 1.0), (375, 1.0)],
        "mode": unreal.InfinityCurtainCueMode.CLOSING_COVER,
        "timing": (96000, 264000, 0),
        "reveal": False,
    },
]
TEMPLATE = {
    "asset": "LS_Interaction_Template",
    "keys": [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
}


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def package_path(value):
    return object_path(value).split(".", 1)[0]


def frame_value(value):
    try:
        return int(value.value)
    except Exception:
        return int(value)


def cue_label(cue):
    return str(cue.get_editor_property("label"))


def package_name(value):
    try:
        return str(value.get_name())
    except Exception:
        return str(value)


def require_clean_editor():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = package_path(world)
    if world_path != EXPECTED_WORLD:
        raise RuntimeError(f"Unexpected editor world: {world_path}")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    if dirty_content or dirty_maps:
        raise RuntimeError(f"Authoring requires a clean editor: {dirty_content}/{dirty_maps}")
    return world_path


def sequence_path(asset_name):
    return INTERACTION_DIR + "/" + asset_name


def require_empty_sequence(asset_name):
    path = sequence_path(asset_name)
    sequence = unreal.load_asset(path)
    if sequence is None:
        raise RuntimeError(f"Missing managed sequence: {path}")
    rate = sequence.get_display_rate()
    if int(rate.numerator) != 25 or int(rate.denominator) != 1:
        raise RuntimeError(f"Unexpected display rate for {path}: {rate}")
    if frame_value(sequence.get_playback_start()) != 0 or frame_value(sequence.get_playback_end()) != PLAYBACK_END:
        raise RuntimeError(
            f"Unexpected playback range for {path}: "
            f"{frame_value(sequence.get_playback_start())}..{frame_value(sequence.get_playback_end())}"
        )
    if sequence.get_bindings() or sequence.get_tracks() or sequence.get_root_folders_in_sequence():
        raise RuntimeError(f"Managed sequence is not empty: {path}")
    return sequence


def expected_scene_state(scene, block):
    actual_sequence = package_path(scene.get_editor_property("sequence"))
    expected_sequence = sequence_path(block["asset"])
    actual_timing = (
        frame_value(scene.get_editor_property("curtain_entry_transition_frames")),
        frame_value(scene.get_editor_property("curtain_hold_frames")),
        frame_value(scene.get_editor_property("curtain_exit_transition_frames")),
    )
    if actual_sequence != expected_sequence:
        raise RuntimeError(f"{block['label']} sequence is {actual_sequence}, expected {expected_sequence}")
    if scene.get_editor_property("curtain_mode") != block["mode"]:
        raise RuntimeError(f"{block['label']} has unexpected curtain mode")
    if actual_timing != block["timing"]:
        raise RuntimeError(f"{block['label']} timing is {actual_timing}, expected {block['timing']}")
    if bool(scene.get_editor_property("sequence_owns_curtain")):
        raise RuntimeError(f"{block['label']} already owns the curtain; refusing non-one-shot mutation")
    if bool(scene.get_editor_property("reveal_next_passage_when_covered")):
        raise RuntimeError(f"{block['label']} already has covered reveal; refusing non-one-shot mutation")


def transform_at_z(z_value):
    transform = unreal.Transform()
    transform.set_editor_property("rotation", unreal.Quat(0.0, 0.0, 0.0, 1.0))
    transform.set_editor_property("translation", unreal.Vector(0.0, 0.0, float(z_value)))
    transform.set_editor_property("scale3d", unreal.Vector(1.0, 1.0, 1.0))
    return transform


def create_curtain_blueprint(curtain_asset):
    blueprint = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(
        BLUEPRINT_PATH,
        unreal.InfinityStageCurtainRig,
    )
    if blueprint is None:
        raise RuntimeError(f"Could not create {BLUEPRINT_PATH}")
    if not unreal.BlueprintEditorLibrary.compile_blueprint(blueprint):
        raise RuntimeError(f"Initial compile failed for {BLUEPRINT_PATH}")

    generated_class = blueprint.generated_class()
    if generated_class is None:
        raise RuntimeError(f"No generated class for {BLUEPRINT_PATH}")
    cdo = unreal.get_default_object(generated_class)
    cdo.set_editor_property("curtain_active", True)
    cdo.set_editor_property("follow_player_camera", True)
    cdo.set_editor_property("use_authored_open_closed_transforms", True)
    cdo.set_editor_property("curtain_distance_cm", 500.0)
    cdo.set_editor_property("curtain_open_relative_transform", transform_at_z(700.0))
    cdo.set_editor_property("curtain_closed_relative_transform", transform_at_z(-500.0))
    cdo.set_editor_property("curtain_progress", 0.0)
    cdo.set_editor_property("tags", [unreal.Name("InfinityStage.SequenceCurtain")])

    curtain_mesh = cdo.get_editor_property("curtain_mesh")
    if curtain_mesh is None or curtain_mesh.get_class().get_name() != "StaticMeshComponent":
        raise RuntimeError(f"Unexpected curtain component on {BLUEPRINT_PATH}: {curtain_mesh}")
    curtain_mesh.set_editor_property("static_mesh", curtain_asset)
    if object_path(curtain_mesh.get_editor_property("static_mesh")) != object_path(curtain_asset):
        raise RuntimeError("Blueprint curtain component did not retain the production mesh")
    return blueprint, generated_class


def author_sequence(sequence, generated_class, key_values):
    binding = sequence.add_spawnable_from_class(generated_class)
    if binding is None:
        raise RuntimeError(f"Could not add curtain spawnable to {package_path(sequence)}")
    binding.set_display_name("Curtain Rig - Fire Safety Curtain")
    binding.tag_binding(unreal.Name("InfinityStage.SequenceCurtain"))

    track = binding.add_track(unreal.MovieSceneFloatTrack)
    if track is None:
        raise RuntimeError(f"Could not add CurtainProgress track to {package_path(sequence)}")
    track.set_property_name_and_path(unreal.Name("CurtainProgress"), "CurtainProgress")

    section = track.add_section()
    if section is None:
        raise RuntimeError(f"Could not add CurtainProgress section to {package_path(sequence)}")
    section.set_range(0, PLAYBACK_END)

    channels = list(section.get_all_channels())
    if len(channels) != 1:
        raise RuntimeError(
            f"Expected one float channel in {package_path(sequence)}, found {len(channels)}"
        )
    channel = channels[0]
    if channel.get_class().get_name() != "MovieSceneScriptingFloatChannel":
        raise RuntimeError(
            f"Unexpected channel type in {package_path(sequence)}: {channel.get_class().get_name()}"
        )
    for frame, value in key_values:
        key = channel.add_key(
            time=unreal.FrameNumber(frame),
            new_value=float(value),
            sub_frame=0.0,
            time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
            interpolation=unreal.MovieSceneKeyInterpolation.LINEAR,
        )
        if key is None:
            raise RuntimeError(f"Could not add CurtainProgress key {frame} in {package_path(sequence)}")

    active_track = binding.add_track(unreal.MovieSceneBoolTrack)
    if active_track is None:
        raise RuntimeError(f"Could not add bCurtainActive track to {package_path(sequence)}")
    active_track.set_property_name_and_path(
        unreal.Name("bCurtainActive"), "bCurtainActive"
    )
    active_section = active_track.add_section()
    if active_section is None:
        raise RuntimeError(f"Could not add bCurtainActive section to {package_path(sequence)}")
    active_section.set_range(0, PLAYBACK_END)
    active_channels = list(active_section.get_all_channels())
    if len(active_channels) != 1:
        raise RuntimeError(
            f"Expected one bool channel in {package_path(sequence)}, "
            f"found {len(active_channels)}"
        )
    active_channel = active_channels[0]
    if active_channel.get_class().get_name() != "MovieSceneScriptingBoolChannel":
        raise RuntimeError(
            f"Unexpected active channel type in {package_path(sequence)}: "
            f"{active_channel.get_class().get_name()}"
        )
    active_channel.set_default(True)
    active_key = active_channel.add_key(
        time=unreal.FrameNumber(0),
        new_value=True,
        sub_frame=0.0,
        time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
    )
    if active_key is None:
        raise RuntimeError(f"Could not add bCurtainActive key in {package_path(sequence)}")

    foreground = sequence.add_root_folder_to_sequence("01_Curtain_Foreground")
    if foreground is None or not foreground.add_child_object_binding(binding):
        raise RuntimeError(f"Could not organize curtain binding in {package_path(sequence)}")
    sequence.add_root_folder_to_sequence("02_BoyCat_Behind_Curtain")
    sequence.add_root_folder_to_sequence("03_Light_Shadow_Audio_VFX")

    return {
        "sequence": package_path(sequence),
        "binding": str(binding.get_display_name()),
        "keys": [[int(frame), float(value)] for frame, value in key_values],
        "active_track": {
            "property_name": str(active_track.get_property_name()),
            "property_path": str(active_track.get_property_path()),
            "default": bool(active_channel.get_default()),
            "keys": [[0, True]],
        },
        "folders": [
            str(folder.get_folder_name()) for folder in sequence.get_root_folders_in_sequence()
        ],
    }


world_path = require_clean_editor()
if unreal.EditorAssetLibrary.does_asset_exist(BLUEPRINT_PATH):
    raise RuntimeError(f"Target Blueprint already exists: {BLUEPRINT_PATH}")

curtain_asset = unreal.load_asset(CURTAIN_ASSET_PATH)
show = unreal.load_asset(SHOW_PATH)
if curtain_asset is None or show is None:
    raise RuntimeError(f"Missing production assets: curtain={curtain_asset}, show={show}")

sequences = {TEMPLATE["asset"]: require_empty_sequence(TEMPLATE["asset"])}
for block in BLOCKS:
    sequences[block["asset"]] = require_empty_sequence(block["asset"])

show_cues = list(show.get_editor_property("cues"))
managed_by_label = {}
for cue in show_cues:
    label = cue_label(cue)
    if any(label == block["label"] for block in BLOCKS):
        if label in managed_by_label:
            raise RuntimeError(f"Duplicate managed Show cue: {label}")
        managed_by_label[label] = cue
if set(managed_by_label) != {block["label"] for block in BLOCKS}:
    raise RuntimeError(
        f"Managed Show cue mismatch: found={sorted(managed_by_label)}, "
        f"expected={sorted(block['label'] for block in BLOCKS)}"
    )
for block in BLOCKS:
    expected_scene_state(
        managed_by_label[block["label"]].get_editor_property("scene"),
        block,
    )

blueprint, generated_class = create_curtain_blueprint(curtain_asset)
sequence_rows = [
    author_sequence(sequences[TEMPLATE["asset"]], generated_class, TEMPLATE["keys"])
]
for block in BLOCKS:
    sequence_rows.append(
        author_sequence(sequences[block["asset"]], generated_class, block["keys"])
    )

show_rows = []
for block in BLOCKS:
    cue = managed_by_label[block["label"]]
    scene = cue.get_editor_property("scene")
    scene.set_editor_property("sequence_owns_curtain", True)
    scene.set_editor_property("reveal_next_passage_when_covered", bool(block["reveal"]))
    cue.set_editor_property("scene", scene)
    show_rows.append(
        {
            "label": block["label"],
            "sequence_owns_curtain": bool(
                cue.get_editor_property("scene").get_editor_property("sequence_owns_curtain")
            ),
            "reveal_next_passage_when_covered": bool(
                cue.get_editor_property("scene").get_editor_property(
                    "reveal_next_passage_when_covered"
                )
            ),
        }
    )
show.set_editor_property("cues", show_cues)

expected_paths = {
    BLUEPRINT_PATH,
    SHOW_PATH,
    sequence_path(TEMPLATE["asset"]),
    *[sequence_path(block["asset"]) for block in BLOCKS],
}
dirty_before_save = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_before_save = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
unexpected_dirty = sorted(set(dirty_before_save) - expected_paths)
if unexpected_dirty or dirty_maps_before_save:
    raise RuntimeError(
        f"Unexpected dirty packages before save: content={dirty_before_save}, "
        f"maps={dirty_maps_before_save}, unexpected={unexpected_dirty}"
    )

assets_to_save = [blueprint]
assets_to_save.extend(sequences.values())
assets_to_save.append(show)
saved = []
for asset in assets_to_save:
    path = package_path(asset)
    if path not in expected_paths:
        raise RuntimeError(f"Refusing to save unexpected asset: {path}")
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
        raise RuntimeError(f"Save failed for {path}")
    saved.append(path)

dirty_content_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_content_after or dirty_maps_after:
    raise RuntimeError(
        f"Authoring left dirty packages: content={dirty_content_after}, maps={dirty_maps_after}"
    )

payload = {
    "status": "ok",
    "world": world_path,
    "blueprint": BLUEPRINT_PATH,
    "curtain_asset": object_path(curtain_asset),
    "sequence_rows": sequence_rows,
    "show_rows": show_rows,
    "saved": saved,
    "dirty_content_after": dirty_content_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "author_sequence_curtains.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_SEQUENCE_AUTHORING_SUCCESS"
    f"|blueprint={BLUEPRINT_PATH}|sequences={len(sequence_rows)}"
    f"|show_cues={len(show_rows)}|saved={len(saved)}|dirty_content=0|dirty_maps=0"
)
