"""Revert key_scene4_score.py / key_scene4_score_v2.py: take the score's sub-track
out of Rig's sequences (the v1 LS_S4_HangarFold and the v2 LS_S4_HangarRise).

Removes every sub-track in either sequence whose section plays
/Game/InfinityStage/CameraScores/LS_S4_CameraScore, and saves only a sequence it changed.
It does NOT delete the score asset (deleting assets is left to a person); once
unhosted it plays nowhere. The camera component then stays as the builder left it.
Success marker: PUSS_S4_SCORE_REVERTED
"""

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HOST_PATHS = ("/Game/InfinityStage/RigAtmos/LS_S4_HangarFold", "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise")
SCORE_PATH = "/Game/InfinityStage/CameraScores/LS_S4_CameraScore"


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    removed, saved = 0, True
    for path in HOST_PATHS:
        host = unreal.load_asset(path)
        if host is None:
            continue
        here = 0
        for track in list(host.find_tracks_by_type(unreal.MovieSceneSubTrack)):
            plays = any(s.get_sequence() is not None and s.get_sequence().get_path_name().split(".")[0] == SCORE_PATH
                        for s in track.get_sections())
            if plays:
                host.remove_track(track)
                here += 1
        if here:
            saved = unreal.EditorAssetLibrary.save_loaded_asset(host, False) and saved
            removed += here
    unreal.log("PUSS_S4_SCORE_REVERTED|removed_tracks=%d|saved=%s" % (removed, saved))


main()
