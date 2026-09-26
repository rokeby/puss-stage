"""A.5 read-only audit: who owns the camera in each of the Show's segments.

Writes nothing. Lists every Passage (PassageSettings.CameraOwner) and every
Scene/Sequence cue (Scene.CameraOwner) in Show order, plus the Show Root's live
override. Success marker: PUSS_CAMERA_OWNER_AUDIT_SUCCESS
"""

import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def guid_text(guid):
    return unreal.GuidLibrary.conv_guid_to_string(guid)


def scene_camera_cut_info(sequence):
    """Camera cuts in a Scene sequence and whether each cut camera carries keyed rotation (F.5)."""
    if sequence is None:
        return None
    try:
        cuts = []
        bindings = {guid_text(b.get_id()): b for b in sequence.get_bindings()}
        for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
            for section in track.get_sections():
                binding_guid = guid_text(section.get_camera_binding_id().get_editor_property("guid"))
                binding = bindings.get(binding_guid)
                keyed_rotation = False
                name = binding.get_display_name() if binding else None
                if binding:
                    for camera_track in binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack):
                        for transform_section in camera_track.get_sections():
                            channels = transform_section.get_all_channels()
                            if any(ch.get_num_keys() > 0 for ch in channels[3:6]):
                                keyed_rotation = True
                cuts.append({"camera": str(name), "keyed_rotation": keyed_rotation})
        return cuts
    except Exception as error:  # read-only probe: report, never fail the audit on API drift
        return {"error": str(error)}

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None:
    raise RuntimeError("No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")

show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError("Show asset did not load")

cues = list(show.get_editor_property("cues"))
passages = list(show.get_editor_property("passage_settings"))
first_cue_to_passage = {guid_text(p.get_editor_property("first_cue_guid")): p for p in passages}

segments = []
open_passage = None
for index, cue in enumerate(cues):
    guid = guid_text(cue.get_editor_property("cue_guid"))
    cue_type = str(cue.get_editor_property("type"))
    enabled = bool(cue.get_editor_property("enabled"))
    if guid in first_cue_to_passage:
        passage = first_cue_to_passage[guid]
        open_passage = passage
        segments.append({
            "kind": "Passage",
            "label": str(passage.get_editor_property("label")),
            "first_cue_index": index,
            "camera_owner": str(passage.get_editor_property("camera_owner")),
        })
    if "WING_PAIR" in cue_type.upper():
        continue
    scene = cue.get_editor_property("scene")
    cut_info = scene_camera_cut_info(scene.get_editor_property("sequence"))
    segments.append({
        "cut_cameras": cut_info,
        "kind": cue_type.split(".")[-1],
        "label": str(cue.get_editor_property("label")),
        "cue_index": index,
        "enabled": enabled,
        "camera_owner": str(scene.get_editor_property("camera_owner")),
        "retain_previous_camera": bool(scene.get_editor_property("retain_previous_camera")),
        "curtain_mode": str(scene.get_editor_property("curtain_mode")),
        "has_sequence": scene.get_editor_property("sequence") is not None,
    })

passage_rows = [
    {
        "label": str(p.get_editor_property("label")),
        "camera_owner": str(p.get_editor_property("camera_owner")),
        "first_cue_guid": guid_text(p.get_editor_property("first_cue_guid")),
        "last_cue_guid": guid_text(p.get_editor_property("last_cue_guid")),
    }
    for p in passages
]
cue_guid_strings = [guid_text(c.get_editor_property("cue_guid")) for c in cues]

roots = [
    actor for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    if actor.get_class().get_name() == "InfinityStageShowRoot"
]
root_state = [
    {
        "label": actor.get_actor_label(),
        "override": bool(actor.get_editor_property("override_camera_owner")),
        "override_owner": str(actor.get_editor_property("camera_owner_override")),
    }
    for actor in roots
]

owners = {}
for segment in segments:
    owners[segment["camera_owner"]] = owners.get(segment["camera_owner"], 0) + 1

for row in passage_rows:
    row["first_cue_index"] = cue_guid_strings.index(row["first_cue_guid"]) if row["first_cue_guid"] in cue_guid_strings else None

payload = {"world": world_path, "segments": segments, "passages": passage_rows, "show_roots": root_state, "owner_counts": owners}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCameraPilot",
    "audit_camera_owners.json",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)

unreal.log(
    "PUSS_CAMERA_OWNER_AUDIT_SUCCESS"
    f"|segments={len(segments)}|passages={len(passage_rows)}|owners={json.dumps(owners, sort_keys=True)}|roots={len(roots)}"
)
