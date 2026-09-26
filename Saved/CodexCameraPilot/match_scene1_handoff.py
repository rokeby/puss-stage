"""Gary, 2026-09-26: "Match p1-s1". Re-take Scene 1's handoff cameras from the
current Passage endpoints, and nothing else.

Asserts the world, no PIE and zero dirty packages. Backs up the level and Scene
1's sequence to Backups/PreMatchP1S1-<ts>/. Matches Scene 1 only through
UInfinityStageCameraPilotLibrary.MatchNamedSceneHandoffs (it refuses an empty
list and needs an explicit count). Reads back the handoff check and re-measures
the P1-end to S1-entry gap. Refuses to save if anything other than the level and
Scene 1's sequence is dirty. Saves exactly those two.
Success marker: PUSS_MATCH_P1_S1_DONE
"""

import datetime
import math
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def unwrap(result, count):
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    return result


def guid_text(guid):
    return unreal.GuidLibrary.conv_guid_to_string(guid)


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    )


def package_file(package_name, extension):
    content_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    if not package_name.startswith("/Game/"):
        raise RuntimeError(f"Not a project package: {package_name}")
    return os.path.join(content_dir, package_name[len("/Game/"):] + extension)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    raise RuntimeError("Unexpected editor world")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
# Only one pre-existing dirt is acceptable: the level flag left by the
# conductor's completed 7-shot SceneCapture2D run at 05:55:42 UTC (confirmed by
# the conductor, net-nil). Re-check it here rather than trusting that message:
# content clean, no capture actors left, the level the only dirty package.
if dirty():
    content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    leftovers = [
        a.get_actor_label() for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        if a.get_class().get_name() == "SceneCapture2D" or a.get_actor_label().startswith("ZZ_")
    ]
    if content or maps != [EXPECTED_WORLD] or leftovers:
        raise RuntimeError(f"Refusing: dirty state is not the known capture flag content={content} maps={maps} leftovers={leftovers}")
    unreal.log("PUSS_MATCH_P1_S1_PRECHECK|accepted known net-nil capture flag on the level|content=0|leftovers=0")

show = unreal.load_asset(SHOW_PATH)
library = unreal.InfinityStageCameraPilotLibrary
scenes = [
    cue for cue in show.get_editor_property("cues")
    if cue.get_editor_property("type") == unreal.InfinityCueType.SCENE
    and str(cue.get_editor_property("label")).startswith("Scene 1 ")
]
if len(scenes) != 1:
    raise RuntimeError(f"Expected exactly one Scene 1 cue, found {len(scenes)}")
scene_cue = scenes[0]
scene_guid = scene_cue.get_editor_property("cue_guid")
sequence = scene_cue.get_editor_property("scene").get_editor_property("sequence")
if sequence is None:
    raise RuntimeError("Scene 1 has no sequence")
sequence_package = sequence.get_outermost().get_name()

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
backup_dir = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Backups", f"PreMatchP1S1-{stamp}")
os.makedirs(backup_dir, exist_ok=False)
shutil.copy2(package_file(EXPECTED_WORLD, ".umap"), backup_dir)
shutil.copy2(package_file(sequence_package, ".uasset"), backup_dir)

report = unwrap(library.match_named_scene_handoffs(show, [scene_guid], 1), 1)
if report is None:
    raise RuntimeError("Match refused or left Scene 1 stale; nothing saved. See INFINITY_SCENE_HANDOFF_MATCHED in the log.")
report = report[0] if isinstance(report, tuple) else report

# Independent read-back: Scene 1 must no longer be stale; re-measure the gap.
check = unwrap(unreal.InfinityStageSequenceBuilderLibrary.check_scene_handoffs(show, world), 2)
stale = [guid_text(g) for g in check[0]] if check else ["check failed"]
if guid_text(scene_guid) in stale or "check failed" in stale:
    raise RuntimeError(f"Scene 1 still stale after Match: {stale}")

passage = next(p for p in show.get_editor_property("passage_settings") if str(p.get_editor_property("label")) == "Passage 1")
frame_range = unwrap(library.get_passage_frame_range(show, passage.get_editor_property("passage_guid")), 2)
pose = unwrap(library.get_passage_camera_pose(show, passage.get_editor_property("passage_guid"), int(frame_range[1])), 3)
p1_view = pose[0]
entry = [
    a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    if isinstance(a, unreal.CineCameraActor) and a.actor_has_tag("InfinityStage.SceneEntry")
    and a.get_actor_label().startswith("Scene 1 ")
]
if len(entry) != 1:
    raise RuntimeError(f"Expected one Scene 1 Entry camera after Match, found {len(entry)}")
gap_cm = (entry[0].get_actor_location() - p1_view.translation).length()
a = p1_view.rotation
b = entry[0].get_actor_transform().rotation
angle = math.degrees(2.0 * math.acos(min(1.0, abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w))))

allowed = sorted({EXPECTED_WORLD, sequence_package})
now_dirty = dirty()
if [d for d in now_dirty if d not in allowed]:
    raise RuntimeError(f"Match dirtied more than the level and Scene 1's sequence; not saving: {now_dirty}")
if sequence_package in now_dirty and not unreal.EditorAssetLibrary.save_asset(sequence_package, only_if_is_dirty=False):
    raise RuntimeError("Scene 1 sequence save failed")
if EXPECTED_WORLD in now_dirty and not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
    raise RuntimeError("Level save failed")
if dirty():
    raise RuntimeError(f"Still dirty after save: {dirty()}")

unreal.log(
    "PUSS_MATCH_P1_S1_DONE"
    f"|gap_cm={gap_cm:.3f}|rot_deg={angle:.4f}|stale_now={len(stale)}|saved={now_dirty}"
    f"|backup={backup_dir}|report={report}"
)
