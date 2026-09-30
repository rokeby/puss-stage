"""Revert place_transition_stalls.py: DELETE the five transition stalls cameras.

NOT A WAY TO MOVE THEM. The Interaction cuts bind these cameras as actors (measured 30 Sep:
probe_interaction_cut_binding.json), so deleting and re-placing them breaks every Interaction cut
SILENTLY: a broken binding resolves to nothing, and the transport's claim just stays. After a docking
move, re-seat the existing cameras in place. Use this only when the stalls cameras are being withdrawn
altogether, with Soft goods' Interaction fit reverted first; CONFIRM must be set True for that.

Destroys only actors tagged InfinityStage.TransitionStalls (this stream's own additions), then saves
the map. It refuses while any ZZ_ actor exists (transient ones included: GameplayStatics, not
get_all_level_actors) or while any content package is dirty. Every step is ASSERTED (hardened 30 Sep
after the conductor's unasserted-value sweep): each destroy must return True; the save must return
True; a read-back must find no tagged actor left. Only then is the success marker printed.
Success marker: PUSS_TRANSITION_STALLS_REVERTED (failure: PUSS_TRANSITION_STALLS_REVERT_FAILED)
"""

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
STALLS_TAG = "InfinityStage.TransitionStalls"
CONFIRM = False


def tagged(world):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a.actor_has_tag(STALLS_TAG)]


def main():
    if not CONFIRM:
        raise RuntimeError("Refusing: CONFIRM is False. This DELETES the stalls cameras and breaks the Interaction "
                           "cuts that bind them; to move them, re-seat them in place instead.")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    others = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if others:
        raise RuntimeError(f"Refusing: content packages dirty {others}")
    if [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
            if a.get_actor_label().startswith("ZZ_")]:
        raise RuntimeError("Refusing: ZZ_ actors present")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    targets = tagged(world)
    labels = [a.get_actor_label() for a in targets]
    failed = [label for actor, label in zip(targets, labels) if not subsystem.destroy_actor(actor)]
    del targets
    if failed:
        unreal.log_error("PUSS_TRANSITION_STALLS_REVERT_FAILED|destroy returned False for %s|NOT saved" % failed)
        raise RuntimeError(f"destroy_actor failed for {failed}; nothing saved")
    saved = unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD) if labels else True
    survivors = [a.get_actor_label() for a in tagged(world)]
    dirty_maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if not saved or survivors or (labels and dirty_maps):
        unreal.log_error("PUSS_TRANSITION_STALLS_REVERT_FAILED|removed=%s|saved=%s|survivors=%s|dirty_maps=%s"
                         % (labels, saved, survivors, dirty_maps))
        raise RuntimeError("revert not verified")
    unreal.log("PUSS_TRANSITION_STALLS_REVERTED|removed=%d %s|saved=%s|survivors=0" % (len(labels), labels, saved))


main()
