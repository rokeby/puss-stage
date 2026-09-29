"""Scene 4 score: move the first tilt off the arrival and onto the rising walls.

Rig rebuilt the opening (29 Sep evening): 0-2 s near black, a glow breaks along
the horizon at 2.25-2.75 s, and the ghost light rises into view from below at
3.0-3.5 s. Those are LOW events, and a first tilt starting at 2.3 s looked up
before anything above had moved. Anticipation, which the creature rule forbids.
New opening: level to 4.3 s, then 0 -> 8 deg over 4.3-6.3 s, locked to the side
walls rising (4-8.5 s). Everything from 8.8 s on is unchanged.

Only the two opening keys move (frames at the score's 30 fps): 69 -> 129 (0 deg)
and 129 -> 189 (8 deg). It refuses unless the keys are exactly the 18:40 set.
DRY_RUN = True only reports. Saves the score asset only.
Revert: run it back with OLD/NEW swapped, or revert_scene4_score.py to unhost.
Success markers: PUSS_S4_OPENING_DRYRUN / PUSS_S4_OPENING_MOVED
"""

import unreal

DRY_RUN = True

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCORE_PATH = "/Game/InfinityStage/CameraScores/LS_S4_CameraScore"
OLD = [(0, 0.0), (69, 0.0), (129, 8.0), (264, 8.0), (330, 30.0), (564, 30.0), (717, 0.0)]
NEW = [(0, 0.0), (129, 0.0), (189, 8.0), (264, 8.0), (330, 30.0), (564, 30.0), (717, 0.0)]


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def pitch_channel(score):
    for binding in score.get_bindings():
        for track in binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack):
            for section in track.get_sections():
                for channel in section.get_all_channels():
                    if str(channel.channel_name) == "Rotation.Y":
                        return channel
    return None


def read(channel):
    return [(k.get_time().frame_number.value, round(k.get_value(), 3)) for k in channel.get_keys()]


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    others = [p for p in dirty() if p != EXPECTED_WORLD]
    if others:
        raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")
    score = unreal.load_asset(SCORE_PATH)
    channel = pitch_channel(score) if score else None
    if channel is None:
        raise RuntimeError("Score or its pitch channel not found")
    before = read(channel)
    if before != OLD:
        raise RuntimeError(f"Refusing: keys are {before}, expected {OLD}")
    if DRY_RUN:
        unreal.log("PUSS_S4_OPENING_DRYRUN|before=%s|after=%s" % (before, NEW))
        return
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    for frame, value in NEW:
        channel.add_key(unreal.FrameNumber(frame), value, interpolation=unreal.MovieSceneKeyInterpolation.USER)
    saved = unreal.EditorAssetLibrary.save_loaded_asset(score, False)
    after = read(channel)
    if after != NEW or not saved:
        raise RuntimeError(f"Read-back failed: saved={saved} keys={after}")
    unreal.log("PUSS_S4_OPENING_MOVED|keys=%s|dirty_after=%s" % (after, dirty()))


main()
