"""Live-only, one-frame A/B check for job 117's additive yaw composition.

This file was authored and syntax-tested offline. It must be run separately by
the conductor. It never writes the real LS_Clams binding: that binding is read
before and after and must retain an identical hash. The only sequence is an
unsaved object in the transient package, and the only actor is spawned by this
probe and destroyed in finally.
"""
from __future__ import annotations

import json
import math
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import s3_feet_core as core  # noqa: E402
import s3_feet_editor as editor  # noqa: E402

ARGS = os.path.join(HERE, "s3_feet_yaw_probe_args.json")
OUT = os.path.join(HERE, "s3_feet_yaw_probe_report.json")
REAL_BINDING_READ_ONLY = True
PROBE_FRAME = 0
PROBE_FRAME_COUNT = 1


def require(condition, message):
    core.require(condition, message)


def set_defaults(section, location, yaw):
    channels = {core.channel_base(ch.get_name()): ch for ch in section.get_all_channels()}
    require(set(core.TRANSFORM_CHANNELS) <= set(channels), "PROBE_CHANNELS")
    values = {
        "Location.X": location[0], "Location.Y": location[1], "Location.Z": location[2],
        "Rotation.X": 0.0, "Rotation.Y": 0.0, "Rotation.Z": yaw,
        # Additive scale's neutral contribution is zero.
        "Scale.X": 0.0, "Scale.Y": 0.0, "Scale.Z": 0.0,
    }
    for name, value in values.items():
        channels[name].set_default(float(value))


def frame_params(frame):
    return unreal.MovieSceneSequencePlaybackParams(
        frame=unreal.FrameTime(unreal.FrameNumber(int(frame))),
        position_type=unreal.MovieScenePositionType.FRAME,
        update_method=unreal.UpdatePositionMethod.PLAY,
    )


def real_binding_state(label):
    root = unreal.load_asset(core.ROOT_SEQUENCE)
    require(root is not None, "ROOT_SEQUENCE_LOAD")
    row = editor.resolve_bindings(root, {label: None})[label]
    return row, core.stable_hash(row)


def main():
    cfg = json.load(open(ARGS, "r", encoding="utf-8"))
    require(cfg.get("confirm") == "RUN TRANSIENT S3 YAW A/B", "PROBE_CONFIRM")
    require(cfg.get("label") == "S3 Crowd 15 (from Shore04_F55)", "PROBE_LABEL")
    yaw_delta = float(cfg.get("yaw_delta_deg", -40.0))
    tolerance = float(cfg.get("tolerance_cm", 0.01))
    before_dirty = editor.census()
    _world, actors = editor.context(require_clean=False)
    matches = [a for a in actors if str(a.get_actor_label()) == cfg["label"]]
    require(len(matches) == 1, "PROBE_REAL_ACTOR_COUNT|%d" % len(matches))
    real_actor = matches[0]
    real_before, real_hash_before = real_binding_state(cfg["label"])
    require(all(section["blend_type"] == "ADDITIVE" for section in real_before["transform_sections"]),
            "PROBE_REAL_BINDING_NOT_ALL_ADDITIVE")

    temp_actor = None
    player = None
    sequence_actor = None
    report = None
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        temp_actor = subsystem.spawn_actor_from_class(real_actor.get_class(), unreal.Vector(0.0, 0.0, 500000.0),
                                                       unreal.Rotator(0.0, 0.0, 0.0), transient=True)
        require(temp_actor is not None, "PROBE_TEMP_ACTOR_CREATE")
        temp_actor.set_actor_label("TEMP_S3_YAW_AB_DO_NOT_SAVE")

        temp_sequence = unreal.new_object(unreal.LevelSequence, outer=unreal.get_transient_package(),
                                          name="TEMP_S3_YAW_AB_SEQUENCE")
        require(temp_sequence is not None, "PROBE_TEMP_SEQUENCE_CREATE")
        temp_sequence.initialize()
        temp_sequence.set_display_rate(unreal.FrameRate(24, 1))
        binding = temp_sequence.add_possessable(temp_actor)
        track = binding.add_track(unreal.MovieScene3DTransformTrack)
        section = track.add_section()
        section.set_range(PROBE_FRAME, PROBE_FRAME_COUNT)
        section.set_blend_type(unreal.MovieSceneBlendType.ADDITIVE)

        base = [0.0, 0.0, 500000.0]
        hand_delta = [13.0, -7.0, 5.0]
        original_motion = [31.0, 11.0, 2.0]
        rotated_xy = core.rotate_xy(original_motion[0], original_motion[1], yaw_delta)
        rewritten = [hand_delta[0] + rotated_xy[0], hand_delta[1] + rotated_xy[1],
                     hand_delta[2] + original_motion[2]]
        expected = [base[0] + rewritten[0], base[1] + rewritten[1], base[2] + rewritten[2]]
        set_defaults(section, rewritten, yaw_delta)

        created = unreal.LevelSequencePlayer.create_level_sequence_player(
            editor.context(require_clean=False)[0], temp_sequence, unreal.MovieSceneSequencePlaybackSettings())
        player = created[0] if isinstance(created, tuple) else created
        sequence_actor = created[1] if isinstance(created, tuple) and len(created) > 1 else None
        require(player is not None, "PROBE_PLAYER_CREATE")
        player.set_playback_position(frame_params(PROBE_FRAME))
        got = editor.xyz(temp_actor.get_actor_location())
        error = math.sqrt(sum((got[i] - expected[i]) ** 2 for i in range(3)))
        require(error <= tolerance, "PROBE_WORLD_POSITION|got=%r|expected=%r|error=%.6f" %
                (got, expected, error))

        real_after, real_hash_after = real_binding_state(cfg["label"])
        require(real_hash_after == real_hash_before and real_after == real_before,
                "PROBE_REAL_BINDING_CHANGED")
        report = {"schema": core.SCHEMA, "mode": "TRANSIENT_YAW_AB", "label": cfg["label"],
                  "frame": PROBE_FRAME, "frame_count": PROBE_FRAME_COUNT,
                  "yaw_delta_deg": yaw_delta, "base_location": base,
                  "hand_delta": hand_delta, "original_motion": original_motion,
                  "rewritten_additive": rewritten, "expected_world": expected,
                  "evaluated_world": got, "world_error_cm": error,
                  "real_binding_hash_before": real_hash_before,
                  "real_binding_hash_after": real_hash_after,
                  "real_binding_writes": 0, "temporary_sequence_saved": False}
    finally:
        if player is not None:
            try:
                player.stop()
            except Exception:
                pass
        if sequence_actor is not None:
            try:
                unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(sequence_actor)
            except Exception:
                pass
        if temp_actor is not None:
            unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(temp_actor)

    require(editor.census() == before_dirty, "PROBE_DIRTY_CENSUS_CHANGED")
    report["dirty_before"] = before_dirty
    report["dirty_after"] = editor.census()
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    unreal.log("S3_FEET_YAW_AB_OK|frame=%d|error_cm=%.6f|real_binding_writes=0|temp_saved=0|report=%s" %
               (PROBE_FRAME, report["world_error_cm"], OUT))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        unreal.log_error("S3_FEET_YAW_AB_FAILED|%s|trace=%s" %
                         (exc, traceback.format_exc().replace("\n", " <NL> ")))
        raise
