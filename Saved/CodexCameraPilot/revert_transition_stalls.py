"""Revert place_transition_stalls.py: remove the five transition stalls cameras.

Destroys only actors tagged InfinityStage.TransitionStalls (this stream's own
additions), then saves the map. It refuses while any ZZ_ actor exists, or while
anything other than the map is dirty. Soft goods' cut sections that bind these
cameras will then resolve to nothing, so revert their fit first.
Success marker: PUSS_TRANSITION_STALLS_REVERTED
"""

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
STALLS_TAG = "InfinityStage.TransitionStalls"


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world (or PIE is running)")
    others = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if others:
        raise RuntimeError(f"Refusing: content packages dirty {others}")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    if [a for a in actors if a.get_actor_label().startswith("ZZ_")]:
        raise RuntimeError("Refusing: ZZ_ actors present")
    removed = 0
    for actor in [a for a in actors if a.actor_has_tag(STALLS_TAG)]:
        subsystem.destroy_actor(actor)
        removed += 1
    del actors
    saved = unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD) if removed else True
    unreal.log("PUSS_TRANSITION_STALLS_REVERTED|removed=%d|saved=%s" % (removed, saved))


main()
