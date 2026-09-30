"""Revert key_scene4_score.py / key_scene4_score_v2.py: take the score's sub-track
out of Rig's sequences (the v1 LS_S4_HangarFold and the v2 LS_S4_HangarRise).

Removes every sub-track in either sequence whose section plays
/Game/InfinityStage/CameraScores/LS_S4_CameraScore, and saves only a sequence it changed.
It does NOT delete the score asset (deleting assets is left to a person); once
unhosted it plays nowhere. The camera component then stays as the builder left it.

Every step is ASSERTED (hardened 30 Sep after the conductor's unasserted-value sweep):
each changed host's save must return True; a read-back must find no host still playing
the score; the changed hosts must not be dirty afterwards. Nothing hosted at the start is
reported as a NO-OP, never as a revert.
Success marker: PUSS_S4_SCORE_REVERTED (also PUSS_S4_SCORE_REVERT_NOOP; failure
PUSS_S4_SCORE_REVERT_FAILED)
"""

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HOST_PATHS = ("/Game/InfinityStage/RigAtmos/LS_S4_HangarFold", "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise")
SCORE_PATH = "/Game/InfinityStage/CameraScores/LS_S4_CameraScore"


def hosting_tracks(host):
    return [track for track in host.find_tracks_by_type(unreal.MovieSceneSubTrack)
            if any(s.get_sequence() is not None and s.get_sequence().get_path_name().split(".")[0] == SCORE_PATH
                   for s in track.get_sections())]


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    removed, saves, changed = 0, {}, []
    for path in HOST_PATHS:
        host = unreal.load_asset(path)
        if host is None:
            continue
        tracks = hosting_tracks(host)
        for track in tracks:
            if not host.remove_track(track):
                unreal.log_error("PUSS_S4_SCORE_REVERT_FAILED|remove_track returned False in %s|NOT saved" % path)
                raise RuntimeError(f"remove_track failed in {path}")
        if tracks:
            removed += len(tracks)
            changed.append(path)
            saves[path] = bool(unreal.EditorAssetLibrary.save_loaded_asset(host, False))
    still = {path: len(hosting_tracks(unreal.load_asset(path))) for path in HOST_PATHS if unreal.load_asset(path)}
    dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    dirty_changed = [path for path in changed if any(d.startswith(path) for d in dirty)]
    if not all(saves.values()) or any(still.values()) or dirty_changed:
        unreal.log_error("PUSS_S4_SCORE_REVERT_FAILED|removed_tracks=%d|saves=%s|still_hosting=%s|dirty=%s"
                         % (removed, saves, still, dirty_changed))
        raise RuntimeError("revert not verified")
    if removed == 0:
        unreal.log("PUSS_S4_SCORE_REVERT_NOOP|nothing hosted the score|read_back=%s" % still)
        return
    unreal.log("PUSS_S4_SCORE_REVERTED|removed_tracks=%d|saves=%s|read_back=%s" % (removed, saves, still))


main()
