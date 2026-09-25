"""Independent read-only verification of sequence-owned curtain authoring."""

import json
import math
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
INTERACTION_DIR = "/Game/InfinityStage/Interactions"
BLUEPRINT_PATH = INTERACTION_DIR + "/BP_InfinityStageSequenceCurtain"
CURTAIN_ASSET_OBJECT_PATH = (
    "/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/"
    "SM_FireSafetyCurtain_01.SM_FireSafetyCurtain_01"
)
PLAYBACK_END = 375
EXPECTED_FOLDERS = [
    "01_Curtain_Foreground",
    "02_BoyCat_Behind_Curtain",
    "03_Light_Shadow_Audio_VFX",
]

DASH = chr(0x2014)
BLOCKS = [
    ("Opening " + DASH + " Curtain", "LS_Opening_Curtain",
     [(0, 1.0), (50, 1.0), (150, 0.0), (375, 0.0)],
     unreal.InfinityCurtainCueMode.OPENING_REVEAL, (0, 48000, 96000), False),
    ("Interaction 1 " + DASH + " Washing the Boy", "LS_Interaction_01_WashingTheBoy",
     [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
     unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL, (48000, 264000, 48000), True),
    ("Interaction 2 " + DASH + " Turnips", "LS_Interaction_02_Turnips",
     [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
     unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL, (48000, 264000, 48000), True),
    ("Interaction 3 " + DASH + " Forgets His Name", "LS_Interaction_03_ForgetsHisName",
     [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
     unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL, (48000, 264000, 48000), True),
    ("Interaction 4 " + DASH + " Gets a Name", "LS_Interaction_04_GetsAName",
     [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
     unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL, (48000, 264000, 48000), True),
    ("Interaction 5 " + DASH + " Becomes King", "LS_Interaction_05_BecomesKing",
     [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
     unreal.InfinityCurtainCueMode.POST_SCENE_INTERSTITIAL, (48000, 264000, 48000), True),
    ("Closing " + DASH + " Sweeping Up", "LS_Closing_Curtain",
     [(0, 0.0), (100, 1.0), (375, 1.0)],
     unreal.InfinityCurtainCueMode.CLOSING_COVER, (96000, 264000, 0), False),
]
TEMPLATE = (
    "LS_Interaction_Template",
    [(0, 0.0), (50, 1.0), (325, 1.0), (375, 0.0)],
)


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
        try:
            return int(value.frame_number.value)
        except Exception:
            return int(value)


def cue_label(cue):
    return str(cue.get_editor_property("label"))


def add_problem(problems, condition, message):
    if not condition:
        problems.append(message)


def nearly_equal(left, right):
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=0.0001)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = package_path(world)
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")

dirty_content = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if dirty_content or dirty_maps:
    raise RuntimeError(f"Verification requires clean editor: {dirty_content}/{dirty_maps}")

problems = []
blueprint = unreal.load_asset(BLUEPRINT_PATH)
show = unreal.load_asset(SHOW_PATH)
master = unreal.load_asset(MASTER_PATH)
add_problem(problems, blueprint is not None, f"missing Blueprint {BLUEPRINT_PATH}")
add_problem(problems, show is not None, f"missing Show {SHOW_PATH}")
add_problem(problems, master is not None, f"missing Master {MASTER_PATH}")
if problems:
    raise RuntimeError("; ".join(problems))

parent_class = unreal.BlueprintEditorLibrary.get_blueprint_parent_class(blueprint)
add_problem(
    problems,
    object_path(parent_class) == "/Script/InfinityStage.InfinityStageCurtainRig",
    f"Blueprint parent is {object_path(parent_class)}, expected InfinityStageCurtainRig",
)
generated_class = blueprint.generated_class()
add_problem(problems, generated_class is not None, "Blueprint has no generated class")
cdo = unreal.get_default_object(generated_class) if generated_class is not None else None
if cdo is not None:
    add_problem(problems, bool(cdo.get_editor_property("curtain_active")),
                "Blueprint curtain_active is false")
    add_problem(problems, bool(cdo.get_editor_property("follow_player_camera")),
                "Blueprint follow_player_camera is false")
    add_problem(problems, bool(cdo.get_editor_property("use_authored_open_closed_transforms")),
                "Blueprint does not use authored transforms")
    add_problem(problems, nearly_equal(cdo.get_editor_property("curtain_distance_cm"), 500.0),
                "Blueprint curtain distance is not 500 cm")
    add_problem(problems, nearly_equal(cdo.get_editor_property("curtain_progress"), 0.0),
                "Blueprint default CurtainProgress is not 0")
    open_transform = cdo.get_editor_property("curtain_open_relative_transform")
    closed_transform = cdo.get_editor_property("curtain_closed_relative_transform")
    open_translation = open_transform.get_editor_property("translation")
    closed_translation = closed_transform.get_editor_property("translation")
    open_scale = open_transform.get_editor_property("scale3d")
    closed_scale = closed_transform.get_editor_property("scale3d")
    add_problem(problems, nearly_equal(open_translation.z, 700.0),
                f"Blueprint open Z is {open_translation.z}, expected 700")
    add_problem(problems, nearly_equal(closed_translation.z, -500.0),
                f"Blueprint closed Z is {closed_translation.z}, expected -500")
    add_problem(
        problems,
        all(nearly_equal(value, 1.0) for value in
            (open_scale.x, open_scale.y, open_scale.z,
             closed_scale.x, closed_scale.y, closed_scale.z)),
        "Blueprint authored transform scale is not 1.0",
    )
    curtain_mesh = cdo.get_editor_property("curtain_mesh")
    add_problem(
        problems,
        curtain_mesh is not None and curtain_mesh.get_class().get_name() == "StaticMeshComponent",
        f"Blueprint curtain component is {curtain_mesh}",
    )
    if curtain_mesh is not None:
        add_problem(
            problems,
            object_path(curtain_mesh.get_editor_property("static_mesh")) == CURTAIN_ASSET_OBJECT_PATH,
            f"Blueprint curtain mesh is {object_path(curtain_mesh.get_editor_property('static_mesh'))}",
        )

sequence_specs = [TEMPLATE]
sequence_specs.extend((asset_name, keys) for _, asset_name, keys, _, _, _ in BLOCKS)
sequence_rows = []
for asset_name, expected_keys in sequence_specs:
    path = INTERACTION_DIR + "/" + asset_name
    sequence = unreal.load_asset(path)
    if sequence is None:
        problems.append(f"missing sequence {path}")
        continue
    bindings = list(sequence.get_bindings())
    spawnables = list(sequence.get_spawnables())
    possessables = list(sequence.get_possessables())
    root_tracks = list(sequence.get_tracks())
    folders = list(sequence.get_root_folders_in_sequence())
    folder_names = [str(folder.get_folder_name()) for folder in folders]
    add_problem(problems, len(bindings) == 1, f"{path} binding count is {len(bindings)}")
    add_problem(problems, len(spawnables) == 1, f"{path} spawnable count is {len(spawnables)}")
    add_problem(problems, len(possessables) == 0, f"{path} has possessables")
    add_problem(problems, frame_value(sequence.get_playback_start()) == 0,
                f"{path} playback start is not 0")
    add_problem(problems, frame_value(sequence.get_playback_end()) == PLAYBACK_END,
                f"{path} playback end is not {PLAYBACK_END}")
    add_problem(problems, folder_names == EXPECTED_FOLDERS,
                f"{path} folders are {folder_names}")
    camera_cut_tracks = [
        track.get_class().get_name()
        for track in root_tracks
        if "CameraCut" in track.get_class().get_name()
    ]
    add_problem(problems, not camera_cut_tracks, f"{path} has Camera Cut tracks {camera_cut_tracks}")

    actual_keys = []
    track_class = ""
    property_name = ""
    property_path = ""
    section_range = [-1, -1]
    binding_name = ""
    binding_tags = []
    foreground_children = 0
    active_property_name = ""
    active_property_path = ""
    active_section_range = [-1, -1]
    active_default = None
    active_keys = []
    if bindings:
        binding = bindings[0]
        binding_name = str(binding.get_display_name())
        binding_tags = sorted(str(value) for value in binding.get_binding_tags())
        add_problem(problems, binding_name == "Curtain Rig - Fire Safety Curtain",
                    f"{path} binding name is {binding_name}")
        add_problem(
            problems,
            "InfinityStage.SequenceCurtain" in binding_tags,
            f"{path} binding tags are {binding_tags}",
        )
        tracks = list(binding.get_tracks())
        track_classes = [track.get_class().get_name() for track in tracks]
        float_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneFloatTrack"]
        bool_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneBoolTrack"]
        spawn_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneSpawnTrack"]
        add_problem(problems, len(tracks) == 3,
                    f"{path} binding tracks are {track_classes}")
        add_problem(problems, len(spawn_tracks) == 1,
                    f"{path} spawn track count is {len(spawn_tracks)}")
        add_problem(problems, len(float_tracks) == 1,
                    f"{path} float track count is {len(float_tracks)}")
        add_problem(problems, len(bool_tracks) == 1,
                    f"{path} bool track count is {len(bool_tracks)}")
        if float_tracks:
            track = float_tracks[0]
            track_class = track.get_class().get_name()
            property_name = str(track.get_property_name())
            property_path = str(track.get_property_path())
            add_problem(problems, track_class == "MovieSceneFloatTrack",
                        f"{path} track class is {track_class}")
            add_problem(problems, property_name == "CurtainProgress",
                        f"{path} property name is {property_name}")
            add_problem(problems, property_path == "CurtainProgress",
                        f"{path} property path is {property_path}")
            sections = list(track.get_sections())
            add_problem(problems, len(sections) == 1,
                        f"{path} section count is {len(sections)}")
            if sections:
                section = sections[0]
                section_range = [
                    frame_value(section.get_start_frame()),
                    frame_value(section.get_end_frame()),
                ]
                add_problem(problems, section_range == [0, PLAYBACK_END],
                            f"{path} section range is {section_range}")
                channels = list(section.get_all_channels())
                add_problem(problems, len(channels) == 1,
                            f"{path} channel count is {len(channels)}")
                if channels:
                    channel = channels[0]
                    add_problem(
                        problems,
                        channel.get_class().get_name() == "MovieSceneScriptingFloatChannel",
                        f"{path} channel class is {channel.get_class().get_name()}",
                    )
                    for key in channel.get_keys():
                        key_time = key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                        actual_keys.append((frame_value(key_time), float(key.get_value())))
                    actual_keys.sort(key=lambda row: row[0])
                    add_problem(
                        problems,
                        len(actual_keys) == len(expected_keys)
                        and all(
                            actual[0] == expected[0] and nearly_equal(actual[1], expected[1])
                            for actual, expected in zip(actual_keys, expected_keys)
                        ),
                        f"{path} keys are {actual_keys}, expected {expected_keys}",
                    )
        if bool_tracks:
            active_track = bool_tracks[0]
            active_property_name = str(active_track.get_property_name())
            active_property_path = str(active_track.get_property_path())
            add_problem(
                problems,
                active_property_name == "bCurtainActive",
                f"{path} active property name is {active_property_name}",
            )
            add_problem(
                problems,
                active_property_path == "bCurtainActive",
                f"{path} active property path is {active_property_path}",
            )
            active_sections = list(active_track.get_sections())
            add_problem(
                problems,
                len(active_sections) == 1,
                f"{path} active section count is {len(active_sections)}",
            )
            if active_sections:
                active_section = active_sections[0]
                active_section_range = [
                    frame_value(active_section.get_start_frame()),
                    frame_value(active_section.get_end_frame()),
                ]
                add_problem(
                    problems,
                    active_section_range == [0, PLAYBACK_END],
                    f"{path} active section range is {active_section_range}",
                )
                active_channels = list(active_section.get_all_channels())
                add_problem(
                    problems,
                    len(active_channels) == 1,
                    f"{path} active channel count is {len(active_channels)}",
                )
                if active_channels:
                    active_channel = active_channels[0]
                    add_problem(
                        problems,
                        active_channel.get_class().get_name()
                        == "MovieSceneScriptingBoolChannel",
                        f"{path} active channel class is "
                        f"{active_channel.get_class().get_name()}",
                    )
                    active_default = (
                        bool(active_channel.get_default())
                        if active_channel.has_default()
                        else None
                    )
                    add_problem(
                        problems,
                        active_default is True,
                        f"{path} active default is {active_default}",
                    )
                    for key in active_channel.get_keys():
                        key_time = key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                        active_keys.append((frame_value(key_time), bool(key.get_value())))
                    active_keys.sort(key=lambda row: row[0])
                    add_problem(
                        problems,
                        active_keys == [(0, True)],
                        f"{path} active keys are {active_keys}",
                    )
        if folders:
            foreground_children = len(folders[0].get_child_object_bindings())
            add_problem(problems, foreground_children == 1,
                        f"{path} foreground folder binding count is {foreground_children}")

    sequence_rows.append(
        {
            "path": path,
            "binding": binding_name,
            "binding_tags": binding_tags,
            "track_class": track_class,
            "property_name": property_name,
            "property_path": property_path,
            "section_range": section_range,
            "keys": [[frame, value] for frame, value in actual_keys],
            "active_track": {
                "property_name": active_property_name,
                "property_path": active_property_path,
                "section_range": active_section_range,
                "default": active_default,
                "keys": [[frame, value] for frame, value in active_keys],
            },
            "folders": folder_names,
            "foreground_children": foreground_children,
            "camera_cut_tracks": camera_cut_tracks,
        }
    )

cues = list(show.get_editor_property("cues"))
add_problem(problems, len(cues) == 274, f"Show raw cue count is {len(cues)}, expected 274")
managed = {}
for cue in cues:
    label = cue_label(cue)
    if any(label == block[0] for block in BLOCKS):
        if label in managed:
            problems.append(f"duplicate managed cue {label}")
        managed[label] = cue
show_rows = []
for label, asset_name, _, mode, timing, reveal in BLOCKS:
    cue = managed.get(label)
    if cue is None:
        problems.append(f"missing Show cue {label}")
        continue
    scene = cue.get_editor_property("scene")
    actual_timing = (
        frame_value(scene.get_editor_property("curtain_entry_transition_frames")),
        frame_value(scene.get_editor_property("curtain_hold_frames")),
        frame_value(scene.get_editor_property("curtain_exit_transition_frames")),
    )
    actual_sequence = package_path(scene.get_editor_property("sequence"))
    owns = bool(scene.get_editor_property("sequence_owns_curtain"))
    actual_reveal = bool(scene.get_editor_property("reveal_next_passage_when_covered"))
    add_problem(problems, actual_sequence == INTERACTION_DIR + "/" + asset_name,
                f"{label} sequence is {actual_sequence}")
    add_problem(problems, scene.get_editor_property("curtain_mode") == mode,
                f"{label} curtain mode is incorrect")
    add_problem(problems, actual_timing == timing,
                f"{label} timing is {actual_timing}, expected {timing}")
    add_problem(problems, owns, f"{label} does not sequence-own its curtain")
    add_problem(problems, actual_reveal == reveal,
                f"{label} covered reveal is {actual_reveal}, expected {reveal}")
    show_rows.append(
        {
            "label": label,
            "sequence": actual_sequence,
            "timing": list(actual_timing),
            "sequence_owns_curtain": owns,
            "reveal_next_passage_when_covered": actual_reveal,
        }
    )

derived_segment_types = []
for cue in cues:
    if not bool(cue.get_editor_property("enabled")):
        continue
    cue_type = cue.get_editor_property("type")
    if cue_type == unreal.InfinityCueType.WING_PAIR:
        if not derived_segment_types or derived_segment_types[-1] != "Passage":
            derived_segment_types.append("Passage")
    elif cue_type == unreal.InfinityCueType.SCENE:
        derived_segment_types.append("Scene")
    else:
        derived_segment_types.append("Sequence")
expected_segment_types = ["Sequence"]
for _ in range(6):
    expected_segment_types.extend(["Passage", "Scene", "Sequence"])
add_problem(problems, derived_segment_types == expected_segment_types,
            f"derived segment types are {derived_segment_types}")

passage_sections = 0
scene_sections = 0
master_sequences = []
for track in master.get_tracks():
    if isinstance(track, unreal.MovieSceneInfinityPassageTrack):
        passage_sections += len(track.get_sections())
    if isinstance(track, unreal.MovieSceneInfinitySceneTrack):
        sections = list(track.get_sections())
        scene_sections += len(sections)
        for section in sections:
            try:
                master_sequences.append(package_path(section.get_sequence()))
            except Exception:
                master_sequences.append("")
add_problem(problems, passage_sections == 6,
            f"Master Passage section count is {passage_sections}")
add_problem(problems, scene_sections == 13,
            f"Master Scene/Sequence section count is {scene_sections}")
for _, asset_name, _, _, _, _ in BLOCKS:
    expected_path = INTERACTION_DIR + "/" + asset_name
    add_problem(problems, master_sequences.count(expected_path) == 1,
                f"Master reference count for {expected_path} is {master_sequences.count(expected_path)}")

dirty_content_after = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps_after = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
add_problem(problems, not dirty_content_after,
            f"verification dirtied content packages {dirty_content_after}")
add_problem(problems, not dirty_maps_after,
            f"verification dirtied maps {dirty_maps_after}")

payload = {
    "status": "fail" if problems else "ok",
    "problems": problems,
    "world": world_path,
    "blueprint": BLUEPRINT_PATH,
    "curtain_asset": CURTAIN_ASSET_OBJECT_PATH,
    "sequence_rows": sequence_rows,
    "show_rows": show_rows,
    "raw_cue_count": len(cues),
    "derived_segment_count": len(derived_segment_types),
    "derived_segment_types": derived_segment_types,
    "master_passage_sections": passage_sections,
    "master_scene_sections": scene_sections,
    "master_sequence_references": master_sequences,
    "dirty_content_after": dirty_content_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "verify_sequence_curtains.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

if problems:
    raise RuntimeError("CURTAIN_SEQUENCE_VERIFY_FAILED: " + " | ".join(problems))

unreal.log(
    "PUSS_CURTAIN_SEQUENCE_VERIFY_SUCCESS"
    f"|blueprint=1|sequences={len(sequence_rows)}|show_cues={len(show_rows)}"
    f"|segments={len(derived_segment_types)}|passage_sections={passage_sections}"
    f"|scene_sections={scene_sections}|dirty_content=0|dirty_maps=0"
)
