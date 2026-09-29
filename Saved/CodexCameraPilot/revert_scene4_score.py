"""Revert key_scene4_score.py: take the score's sub-track out of Rig's fold.

Removes every sub-track in LS_S4_HangarFold whose section plays
/Game/InfinityStage/CameraScores/LS_S4_CameraScore, and saves the fold only.
It does NOT delete the score asset (deleting assets is left to a person); once
unhosted it plays nowhere. The camera component then stays as the builder left it.
Success marker: PUSS_S4_SCORE_REVERTED
"""

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FOLD_PATH = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"
SCORE_PATH = "/Game/InfinityStage/CameraScores/LS_S4_CameraScore"


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    fold = unreal.load_asset(FOLD_PATH)
    removed = 0
    for track in list(fold.find_tracks_by_type(unreal.MovieSceneSubTrack)):
        hosts = any(s.get_sequence() is not None and s.get_sequence().get_path_name().split(".")[0] == SCORE_PATH
                    for s in track.get_sections())
        if hosts:
            fold.remove_track(track)
            removed += 1
    saved = unreal.EditorAssetLibrary.save_loaded_asset(fold, False) if removed else True
    unreal.log("PUSS_S4_SCORE_REVERTED|removed_tracks=%d|saved=%s" % (removed, saved))


main()
