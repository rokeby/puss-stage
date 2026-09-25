"""Independent, read-only verification of the curtain staging repair."""

import json
import math
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
INTERACTION_DIR = "/Game/InfinityStage/Interactions"
BLUEPRINT_PATH = INTERACTION_DIR + "/BP_InfinityStageSequenceCurtain"
CURTAIN_MESH_PATH = (
    "/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/"
    "SM_FireSafetyCurtain_01.SM_FireSafetyCurtain_01"
)
NEW_KEYS = [(0, 0.0), (75, 1.0), (400, 1.0), (500, 0.0)]
EXPECTED_MARKERS = [
    (75, "InfinityStage.CurtainFullyDown"),
    (75, "InfinityStage.BoyCatStart"),
    (375, "InfinityStage.HiddenChangeover"),
    (400, "InfinityStage.CurtainRiseStart"),
    (500, "InfinityStage.CurtainFullyOpen"),
]
EXPECTED_FOLDERS = [
    "01_Curtain_Foreground",
    "02_BoyCat_Behind_Curtain",
    "03_Light_Shadow_Audio_VFX",
]
SEQUENCE_NAMES = [
    "LS_Interaction_Template",
    "LS_Opening_Curtain",
    "LS_Interaction_01_WashingTheBoy",
    "LS_Interaction_02_Turnips",
    "LS_Interaction_03_ForgetsHisName",
    "LS_Interaction_04_GetsAName",
    "LS_Interaction_05_BecomesKing",
    "LS_Closing_Curtain",
]
RETIMED_NAMES = {
    "LS_Interaction_Template",
    "LS_Interaction_01_WashingTheBoy",
    "LS_Interaction_02_Turnips",
    "LS_Interaction_03_ForgetsHisName",
    "LS_Interaction_04_GetsAName",
    "LS_Interaction_05_BecomesKing",
}
DASH = chr(0x2014)
INTERACTIONS = [
    ("Interaction 1 " + DASH + " Washing the Boy", "LS_Interaction_01_WashingTheBoy"),
    ("Interaction 2 " + DASH + " Turnips", "LS_Interaction_02_Turnips"),
    ("Interaction 3 " + DASH + " Forgets His Name", "LS_Interaction_03_ForgetsHisName"),
    ("Interaction 4 " + DASH + " Gets a Name", "LS_Interaction_04_GetsAName"),
    ("Interaction 5 " + DASH + " Becomes King", "LS_Interaction_05_BecomesKing"),
]


def object_path(value):
    if value is None:
        return ""
    return value.get_path_name() if hasattr(value, "get_path_name") else str(value)


def package_path(value):
    return object_path(value).split(".", 1)[0]


def frame_value(value):
    try:
        return int(value.value)
    except Exception:
        return int(value)


def near(left, right, tolerance=0.001):
    return math.isclose(float(left), float(right), abs_tol=tolerance)


def vector_near(value, expected):
    return near(value.x, expected[0]) and near(value.y, expected[1]) and near(value.z, expected[2])


def add_problem(problems, condition, message):
    if not condition:
        problems.append(message)


def verify_framing(problems, owner, label):
    add_problem(problems, bool(owner.get_editor_property("curtain_active")), f"{label} inactive")
    add_problem(problems, bool(owner.get_editor_property("follow_player_camera")), f"{label} not camera-following")
    add_problem(
        problems,
        bool(owner.get_editor_property("use_authored_open_closed_transforms")),
        f"{label} not using authored transforms",
    )
    add_problem(problems, near(owner.get_editor_property("curtain_distance_cm"), 1500.0), f"{label} distance mismatch")
    add_problem(
        problems,
        vector_near(owner.get_editor_property("curtain_view_local_offset_cm"), (0.0, 0.0, 0.0)),
        f"{label} view-local offset mismatch",
    )
    rotation = owner.get_editor_property("curtain_view_rotation_offset")
    add_problem(
        problems,
        near(rotation.pitch, 0.0) and near(rotation.yaw, 0.0) and near(rotation.roll, 0.0),
        f"{label} view rotation mismatch",
    )
    opened = owner.get_editor_property("curtain_open_relative_transform")
    closed = owner.get_editor_property("curtain_closed_relative_transform")
    add_problem(
        problems,
        vector_near(opened.translation, (0.0, 0.0, 1400.0))
        and vector_near(opened.scale3d, (3.5, 3.5, 3.5)),
        f"{label} open transform mismatch: {opened}",
    )
    add_problem(
        problems,
        vector_near(closed.translation, (0.0, 0.0, -1750.0))
        and vector_near(closed.scale3d, (3.5, 3.5, 3.5)),
        f"{label} closed transform mismatch: {closed}",
    )


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = package_path(world)
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
dirty_content_before = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps_before = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
if dirty_content_before or dirty_maps_before:
    raise RuntimeError(f"Verification requires a clean editor: {dirty_content_before}/{dirty_maps_before}")

problems = []
rows = []
blueprint = unreal.load_asset(BLUEPRINT_PATH)
show = unreal.load_asset(SHOW_PATH)
master = unreal.load_asset(MASTER_PATH)
if blueprint is None or show is None or master is None:
    raise RuntimeError(f"Missing production assets: blueprint={blueprint}, show={show}, master={master}")

generated_class = blueprint.generated_class()
cdo = unreal.get_default_object(generated_class) if generated_class else None
add_problem(problems, cdo is not None, "Curtain Blueprint has no generated-class CDO")
if cdo is not None:
    verify_framing(problems, cdo, "Blueprint CDO")
    curtain_mesh = cdo.get_editor_property("curtain_mesh")
    add_problem(
        problems,
        object_path(curtain_mesh.get_editor_property("static_mesh")) == CURTAIN_MESH_PATH,
        "Curtain Blueprint does not use the approved fire-safety curtain mesh",
    )

for name in SEQUENCE_NAMES:
    path = INTERACTION_DIR + "/" + name
    sequence = unreal.load_asset(path)
    if sequence is None:
        problems.append(f"Missing {path}")
        continue
    bindings = list(sequence.get_bindings())
    spawnables = list(sequence.get_spawnables())
    folders = [str(folder.get_folder_name()) for folder in sequence.get_root_folders_in_sequence()]
    add_problem(problems, len(bindings) == 1, f"{path} binding count is {len(bindings)}")
    add_problem(problems, len(spawnables) == 1, f"{path} spawnable count is {len(spawnables)}")
    add_problem(problems, folders == EXPECTED_FOLDERS, f"{path} folders are {folders}")
    if not bindings:
        continue
    binding = bindings[0]
    verify_framing(problems, binding.get_object_template(), path + " template")
    tracks = list(binding.get_tracks())
    float_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneFloatTrack"]
    bool_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneBoolTrack"]
    spawn_tracks = [track for track in tracks if track.get_class().get_name() == "MovieSceneSpawnTrack"]
    add_problem(problems, len(tracks) == 3, f"{path} track count is {len(tracks)}")
    add_problem(problems, len(float_tracks) == 1, f"{path} float-track count is {len(float_tracks)}")
    add_problem(problems, len(bool_tracks) == 1, f"{path} bool-track count is {len(bool_tracks)}")
    add_problem(problems, len(spawn_tracks) == 1, f"{path} spawn-track count is {len(spawn_tracks)}")
    actual_keys = []
    section_ranges = []
    if float_tracks:
        sections = list(float_tracks[0].get_sections())
        if sections:
            section = sections[0]
            section_ranges.append((frame_value(section.get_start_frame()), frame_value(section.get_end_frame())))
            channels = list(section.get_all_channels())
            if channels:
                for key in channels[0].get_keys():
                    time = key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                    actual_keys.append((frame_value(time.frame_number), float(key.get_value())))
                actual_keys.sort(key=lambda row: row[0])
    if name in RETIMED_NAMES:
        add_problem(problems, frame_value(sequence.get_playback_start()) == 0, f"{path} playback start mismatch")
        add_problem(problems, frame_value(sequence.get_playback_end()) == 500, f"{path} playback end mismatch")
        add_problem(
            problems,
            len(actual_keys) == len(NEW_KEYS) and all(
                actual[0] == expected[0] and near(actual[1], expected[1])
                for actual, expected in zip(actual_keys, NEW_KEYS)
            ),
            f"{path} CurtainProgress keys are {actual_keys}",
        )
        add_problem(problems, section_ranges == [(0, 500)], f"{path} float section range is {section_ranges}")
        for track in bool_tracks + spawn_tracks:
            for section in track.get_sections():
                track_range = (frame_value(section.get_start_frame()), frame_value(section.get_end_frame()))
                add_problem(problems, track_range == (0, 500), f"{path} {track.get_class().get_name()} range is {track_range}")
        actual_markers = sorted(
            (frame_value(marked.frame_number), str(marked.label))
            for marked in unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(sequence, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
        )
        add_problem(
            problems,
            actual_markers == sorted(EXPECTED_MARKERS),
            f"{path} markers are {actual_markers}",
        )
    rows.append({
        "path": path,
        "playback": [frame_value(sequence.get_playback_start()), frame_value(sequence.get_playback_end())],
        "keys": actual_keys,
        "folders": folders,
    })

cues = list(show.get_editor_property("cues"))
managed = {}
for cue in cues:
    label = str(cue.get_editor_property("label"))
    if label in {row[0] for row in INTERACTIONS}:
        if label in managed:
            problems.append(f"Duplicate Show cue {label}")
        managed[label] = cue
for label, asset_name in INTERACTIONS:
    cue = managed.get(label)
    if cue is None:
        problems.append(f"Missing Show cue {label}")
        continue
    scene = cue.get_editor_property("scene")
    timing = tuple(
        frame_value(scene.get_editor_property(field))
        for field in (
            "curtain_entry_transition_frames",
            "curtain_hold_frames",
            "curtain_exit_transition_frames",
        )
    )
    add_problem(problems, package_path(scene.get_editor_property("sequence")) == INTERACTION_DIR + "/" + asset_name, f"{label} sequence mismatch")
    add_problem(problems, timing == (72000, 312000, 96000), f"{label} timing is {timing}")
    add_problem(problems, frame_value(scene.get_editor_property("duration_frames")) == 480000, f"{label} duration mismatch")
    add_problem(problems, bool(scene.get_editor_property("use_sequence_length")), f"{label} is not sequence-length driven")
    add_problem(problems, bool(scene.get_editor_property("sequence_owns_curtain")), f"{label} does not sequence-own curtain")
    add_problem(problems, bool(scene.get_editor_property("retain_previous_camera")), f"{label} does not retain Scene camera")
    add_problem(problems, bool(scene.get_editor_property("reveal_next_passage_when_covered")), f"{label} does not reveal when covered")

derived_types = []
for cue in cues:
    if not bool(cue.get_editor_property("enabled")):
        continue
    cue_type = cue.get_editor_property("type")
    if cue_type == unreal.InfinityCueType.WING_PAIR:
        if not derived_types or derived_types[-1] != "Passage":
            derived_types.append("Passage")
    elif cue_type == unreal.InfinityCueType.SCENE:
        derived_types.append("Scene")
    else:
        derived_types.append("Sequence")
expected_types = ["Sequence"]
for _ in range(6):
    expected_types.extend(["Passage", "Scene", "Sequence"])
add_problem(problems, derived_types == expected_types, f"Compiled block topology is {derived_types}")

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
add_problem(problems, passage_sections == 6, f"Master Passage section count is {passage_sections}")
add_problem(problems, scene_sections == 13, f"Master Scene/Sequence section count is {scene_sections}")
for _, asset_name in INTERACTIONS:
    expected_path = INTERACTION_DIR + "/" + asset_name
    add_problem(problems, master_sequences.count(expected_path) == 1, f"Master reference count for {expected_path} is {master_sequences.count(expected_path)}")

dirty_content_after = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps_after = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
add_problem(problems, not dirty_content_after, f"Verifier dirtied content: {dirty_content_after}")
add_problem(problems, not dirty_maps_after, f"Verifier dirtied maps: {dirty_maps_after}")

payload = {
    "status": "fail" if problems else "ok",
    "problems": problems,
    "world": world_path,
    "sequence_rows": rows,
    "derived_segment_count": len(derived_types),
    "master_passage_sections": passage_sections,
    "master_scene_sections": scene_sections,
    "dirty_content_after": dirty_content_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "verify_curtain_staging.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

if problems:
    raise RuntimeError("CURTAIN_STAGING_VERIFY_FAILED: " + " | ".join(problems))

unreal.log(
    "PUSS_CURTAIN_STAGING_VERIFY_SUCCESS"
    f"|framed={len(SEQUENCE_NAMES)}|retimed={len(RETIMED_NAMES)}"
    f"|segments={len(derived_types)}|dirty_content=0|dirty_maps=0"
)
