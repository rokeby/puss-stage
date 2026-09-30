"""RETIRED 30 Sep 2026 (Look & camera, approved under the conductor's delegation). DO NOT RUN; refuses at import.

Gary (30 Sep, via the conductor): "the camera should not be constrained when we get into the hangar even though
we might look up manually (with free dog view)", and he chose free dog look for ALL hangar Scenes 1-6. Nobody keys
a tilt during or after the hangar rise; the look-up is the dog's, live. This script keyed exactly such a tilt (the
post-landing 0 -> 30 -> 0 deg score). The original body is kept below the refusal, unreachable, for the record.
"""
raise RuntimeError("key_scene4_score_v2.py is RETIRED (30 Sep): the hangar look is the dog's (free look), not keyed.")

"""Scene 4 v2: re-key the camera score (post-landing only) and host it in LS_S4_HangarRise.

Gary (30 Sep): the rise belongs to the DOG (Scene 4 is Dog Gaze): the look over
the lip and up at the stars are performed live, not keyed. So the authored score
keys nothing during the rise. It moves only after landing, against things the
rise-curve change does not move (HangarRise time, speed 1.0):
  0 .. 18.8   0 deg   (the dog owns the look; the base stays level)
  18.8 -> 22.0  0 -> 30  up WITH the roof swing (starts 18.5), lagging its first
                         movement; the underside reads at 30 deg by 21.5
                         (p99 213, no exposure override) and is black at 17.8
  22.0 .. 24.8  30       held still through the rest of the swing (18.5-24.5)
  24.8 -> 29.6  30 -> 0  down with the lattice (24.5-28.5), level before the
                         Entry->Exit cut at 30.0
Flat tangents, so each segment is a smoothstep. The dog's Gaze composes on top
(Go1 look layering, 01d3152).

DRY_RUN = True only reports. The write replaces the score's pitch keys, sets the
score's range to the host's, adds ONE sub-track to LS_S4_HangarRise over the
host's playback range, and saves the score and the host only. Refuses if the
score is hosted anywhere already, if anything but the map is dirty, or if a key
would fall outside the host. Revert: revert_scene4_score.py (unhosts from
either sequence). Back up LS_S4_HangarRise.uasset first.
Success markers: PUSS_S4_SCORE_V2_DRYRUN / PUSS_S4_SCORE_V2_KEYED
"""

import json
import os

import unreal

DRY_RUN = True

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCORE_PATH = "/Game/InfinityStage/CameraScores/LS_S4_CameraScore"
HOST_PATH = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
OLD_HOST_PATH = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"
SUB_TRACK_NAME = "Look & camera: Scene 4 score"
KEYS = [(0.0, 0.0), (18.8, 0.0), (22.0, 30.0), (24.8, 30.0), (29.6, 0.0)]


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def hosts(sequence):
    if sequence is None:
        return 0
    count = 0
    for track in sequence.find_tracks_by_type(unreal.MovieSceneSubTrack):
        for section in track.get_sections():
            sub = section.get_sequence()
            if sub is not None and sub.get_path_name().split(".")[0] == SCORE_PATH:
                count += 1
    return count


def pitch_channel(score):
    for binding in score.get_bindings():
        for track in binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack):
            for section in track.get_sections():
                for channel in section.get_all_channels():
                    if str(channel.channel_name) == "Rotation.Y":
                        return section, channel
    return None, None


def read(channel):
    return [(k.get_time().frame_number.value, round(k.get_value(), 3)) for k in channel.get_keys()]


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world (or PIE is running)")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    others = [p for p in dirty() if p != EXPECTED_WORLD]
    if others:
        raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")
    score = unreal.load_asset(SCORE_PATH)
    host = unreal.load_asset(HOST_PATH)
    old_host = unreal.load_asset(OLD_HOST_PATH)
    if score is None or host is None:
        raise RuntimeError("Score or host sequence missing")
    if hosts(host) or hosts(old_host):
        raise RuntimeError(f"Refusing: score already hosted (rise {hosts(host)}, fold {hosts(old_host)}); revert first")
    section, channel = pitch_channel(score)
    if channel is None:
        raise RuntimeError("No pitch channel on the score")

    rate = host.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    start, end = host.get_playback_start(), host.get_playback_end()
    new_frames = [(int(round(t * fps)), p) for t, p in KEYS]
    if new_frames[-1][0] >= end:
        raise RuntimeError(f"Last key {new_frames[-1][0]} is not inside the host range {start}-{end}")
    plan = {"host": HOST_PATH, "host_fps": fps, "host_range": [start, end],
            "keys_seconds_pitch": KEYS, "key_frames": new_frames, "old_keys": read(channel),
            "score_fps_before": [score.get_display_rate().numerator, score.get_display_rate().denominator]}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "key_scene4_score_v2.json")
    if DRY_RUN:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump({"dry_run": True, "plan": plan}, handle, indent=2)
        unreal.log("PUSS_S4_SCORE_V2_DRYRUN|%s" % json.dumps(plan))
        return

    score.set_display_rate(rate)
    score.set_playback_start(start)
    score.set_playback_end(end)
    section.set_range(start, end)
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    for frame, pitch in new_frames:
        channel.add_key(unreal.FrameNumber(frame), pitch, interpolation=unreal.MovieSceneKeyInterpolation.USER)

    sub_track = host.add_track(unreal.MovieSceneSubTrack)
    sub_track.set_display_name(SUB_TRACK_NAME)
    sub_section = sub_track.add_section()
    sub_section.set_sequence(score)
    sub_section.set_range(start, end)

    saved_score = unreal.EditorAssetLibrary.save_loaded_asset(score, False)
    saved_host = unreal.EditorAssetLibrary.save_loaded_asset(host, False)
    keys = read(channel)
    problems = []
    if not (saved_score and saved_host):
        problems.append("save failed")
    if keys != [(f, float(p)) for f, p in new_frames]:
        problems.append(f"keys read back as {keys}")
    if hosts(host) != 1 or hosts(old_host) != 0:
        problems.append(f"hosting rise={hosts(host)} fold={hosts(old_host)}")
    if [p for p in dirty() if p != EXPECTED_WORLD]:
        problems.append(f"left dirty {dirty()}")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"dry_run": False, "plan": plan, "keys": keys, "problems": problems}, handle, indent=2)
    if problems:
        raise RuntimeError(f"Read-back failed: {problems}")
    unreal.log("PUSS_S4_SCORE_V2_KEYED|keys=%s|hosted_in_rise=1|dirty_after=%s" % (keys, dirty()))


main()
