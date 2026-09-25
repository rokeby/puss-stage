"""Author a sway animation on the Manny component inside BP_OrtalanSheet.

This script is intended to run inside the Unreal editor:

    py "<PussStage>/Scripts/build_manny_sway.py"

(or Tools -> Execute Python Script)

Manny is a SkeletalMeshComponent sibling of the ChaosClothComponent inside
BP_OrtalanSheet, so we key the component's *relative* transform. The cloth
component itself never moves, which keeps the sim out of teleport-threshold
territory -- only the collision capsules travel, which is exactly what makes
the sheet swing.

The sheet is given SETTLE_SECONDS to drape before any motion starts, then the
sway amplitude ramps in over RAMP_SECONDS so the first swing doesn't snap the
cloth. Re-run the script freely: it rebuilds the sequence bindings in place.
"""

from __future__ import annotations

import math

import unreal


# --- what we're driving -----------------------------------------------------

ACTOR_CLASS_PREFIX = "BP_OrtalanSheet"
SEQUENCE_PACKAGE_PATH = "/Game/Scenes"
SEQUENCE_NAME = "LS_OrtalanSheetSway"

# --- timing -----------------------------------------------------------------

FPS = 30
SETTLE_SECONDS = 1.5      # sheet drapes, Manny static
RAMP_SECONDS = 2.0        # amplitude eases in over this long
TOTAL_SECONDS = 12.0
SWAY_PERIOD = 3.0         # seconds per full left-right-left cycle
KEYS_PER_CYCLE = 8        # sampled sine; 8 + auto tangents reads as smooth

# --- how much he moves ------------------------------------------------------

AMPLITUDE_YAW_DEG = 22.0    # twist about vertical -- the main driver
AMPLITUDE_ROLL_DEG = 7.0    # lean, 90 deg out of phase with the twist
AMPLITUDE_SHIFT_CM = 9.0    # lateral weight shift, in phase with the lean

# --- playback ---------------------------------------------------------------

SPAWN_SEQUENCE_ACTOR = True   # drop a LevelSequenceActor set to auto-play + loop
REBUILD_BINDINGS = True       # wipe existing bindings so re-runs stay clean


def log(message: str) -> None:
    unreal.log(f"[manny_sway] {message}")


def find_target_actor() -> unreal.Actor:
    """Locate the BP_OrtalanSheet actor in the currently open level."""
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if actor.get_class().get_name().startswith(ACTOR_CLASS_PREFIX)
    ]

    if not matches:
        raise RuntimeError(
            f"No actor whose class starts with '{ACTOR_CLASS_PREFIX}' in this level. "
            "Open the level containing the cloth test and re-run."
        )
    if len(matches) > 1:
        names = ", ".join(actor.get_actor_label() for actor in matches)
        log(f"WARNING: {len(matches)} candidate actors ({names}); using the first.")

    actor = matches[0]
    log(f"Target actor: {actor.get_actor_label()} ({actor.get_class().get_name()})")
    return actor


def find_components(actor: unreal.Actor):
    """Return (manny_component, cloth_component) from the actor's components.

    UChaosClothComponent derives from USkinnedMeshComponent rather than
    USkeletalMeshComponent, so the class filter should already exclude it --
    but it is cheap to be explicit about which one is which.
    """
    cloth_class = getattr(unreal, "ChaosClothComponent", None)

    cloth = None
    if cloth_class is not None:
        cloth_components = actor.get_components_by_class(cloth_class)
        cloth = cloth_components[0] if cloth_components else None

    skeletal = [
        component
        for component in actor.get_components_by_class(unreal.SkeletalMeshComponent)
        if cloth_class is None or not isinstance(component, cloth_class)
    ]
    if not skeletal:
        raise RuntimeError(
            "No SkeletalMeshComponent found on the actor -- expected the Manny component."
        )

    manny = skeletal[0]
    for component in skeletal:
        mesh = component.get_editor_property("skeletal_mesh_asset")
        if mesh is not None and "manny" in mesh.get_name().lower():
            manny = component
            break

    log(f"Manny component: {manny.get_name()}")
    log(f"Cloth component: {cloth.get_name() if cloth else 'NOT FOUND (check the BP)'}")
    return manny, cloth


def get_or_create_sequence() -> unreal.LevelSequence:
    asset_path = f"{SEQUENCE_PACKAGE_PATH}/{SEQUENCE_NAME}"

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        sequence = unreal.EditorAssetLibrary.load_asset(asset_path)
        log(f"Reusing existing sequence {asset_path}")
    else:
        sequence = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name=SEQUENCE_NAME,
            package_path=SEQUENCE_PACKAGE_PATH,
            asset_class=unreal.LevelSequence,
            factory=unreal.LevelSequenceFactoryNew(),
        )
        log(f"Created sequence {asset_path}")

    sequence.set_display_rate(unreal.FrameRate(FPS, 1))
    sequence.set_playback_start(0)
    sequence.set_playback_end(int(round(TOTAL_SECONDS * FPS)))

    if REBUILD_BINDINGS:
        for binding in sequence.get_bindings():
            binding.remove()

    return sequence


def build_keyframes():
    """Sample the sway curve. Returns [(frame, yaw, roll, lateral_offset), ...]."""
    settle_frames = int(round(SETTLE_SECONDS * FPS))
    total_frames = int(round(TOTAL_SECONDS * FPS))
    frames_per_key = max(1, int(round(FPS * SWAY_PERIOD / KEYS_PER_CYCLE)))

    # Frame 0 holds the rest pose so the sheet has time to settle onto him.
    keyframes = [(0, 0.0, 0.0, 0.0), (settle_frames, 0.0, 0.0, 0.0)]

    frame = settle_frames + frames_per_key
    while frame <= total_frames:
        elapsed = (frame - settle_frames) / float(FPS)
        ramp = smoothstep(elapsed / RAMP_SECONDS) if RAMP_SECONDS > 0 else 1.0
        phase = 2.0 * math.pi * elapsed / SWAY_PERIOD

        yaw = AMPLITUDE_YAW_DEG * math.sin(phase) * ramp
        # Lean and weight shift lead the twist by a quarter cycle, which is what
        # makes it read as a body shifting weight rather than a turntable.
        roll = AMPLITUDE_ROLL_DEG * math.sin(phase + math.pi * 0.5) * ramp
        shift = AMPLITUDE_SHIFT_CM * math.sin(phase + math.pi * 0.5) * ramp

        keyframes.append((frame, yaw, roll, shift))
        frame += frames_per_key

    return keyframes


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def channel_map(section: unreal.MovieSceneSection):
    """Map 'Location.X' -> channel, falling back to positional order.

    Transform sections use double channels in UE5 and expose nine of them in
    the order Location XYZ / Rotation XYZ / Scale XYZ.
    """
    channels = section.get_all_channels()
    order = [
        "Location.X", "Location.Y", "Location.Z",
        "Rotation.X", "Rotation.Y", "Rotation.Z",
        "Scale.X", "Scale.Y", "Scale.Z",
    ]

    by_name = {}
    for channel in channels:
        try:
            by_name[str(channel.get_name())] = channel
        except Exception:
            pass

    if all(name in by_name for name in order):
        return by_name

    if len(channels) < 9:
        raise RuntimeError(
            f"Transform section exposed {len(channels)} channels, expected at least 9."
        )
    log("Channel names unavailable; falling back to positional channel order.")
    return dict(zip(order, channels))


def key_transform(section: unreal.MovieSceneSection, component, keyframes) -> None:
    base_location = component.get_relative_location()
    base_rotation = component.get_relative_rotation()
    base_scale = component.get_relative_scale3d()
    log(
        f"Base relative transform: loc={base_location} "
        f"rot={base_rotation} scale={base_scale}"
    )

    channels = channel_map(section)

    # Every channel gets its current value as a default. An unkeyed channel
    # otherwise falls back to zero, which would collapse Manny's scale to
    # nothing the moment the section evaluates.
    defaults = {
        "Location.X": base_location.x, "Location.Y": base_location.y,
        "Location.Z": base_location.z,
        "Rotation.X": base_rotation.roll, "Rotation.Y": base_rotation.pitch,
        "Rotation.Z": base_rotation.yaw,
        "Scale.X": base_scale.x, "Scale.Y": base_scale.y, "Scale.Z": base_scale.z,
    }
    for name, value in defaults.items():
        channels[name].set_default(value)

    animated = ("Location.Y", "Rotation.X", "Rotation.Z")
    for name in animated:
        for key in list(channels[name].get_keys()):
            channels[name].remove_key(key)

    for frame, yaw, roll, shift in keyframes:
        frame_number = unreal.FrameNumber(int(frame))
        values = {
            "Location.Y": base_location.y + shift,
            "Rotation.X": base_rotation.roll + roll,
            "Rotation.Z": base_rotation.yaw + yaw,
        }
        for name, value in values.items():
            channels[name].add_key(
                frame_number,
                value,
                interpolation=unreal.MovieSceneKeyInterpolation.AUTO,
            )

    log(f"Keyed {len(keyframes)} keys across {', '.join(animated)}.")


def ensure_sequence_actor(sequence: unreal.LevelSequence) -> None:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    existing = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if isinstance(actor, unreal.LevelSequenceActor)
        and actor.get_actor_label().startswith(SEQUENCE_NAME)
    ]
    if existing:
        sequence_actor = existing[0]
        log(f"Reusing LevelSequenceActor {sequence_actor.get_actor_label()}")
    else:
        sequence_actor = actor_subsystem.spawn_actor_from_class(
            unreal.LevelSequenceActor, unreal.Vector(0.0, 0.0, 0.0)
        )
        sequence_actor.set_actor_label(f"{SEQUENCE_NAME}_Player")
        log("Spawned LevelSequenceActor")

    sequence_actor.set_sequence(sequence)

    # Auto-play + infinite loop so the sway runs the moment you hit PIE/Simulate.
    try:
        sequence_actor.set_editor_property("auto_play", True)
    except Exception as error:
        log(f"WARNING: could not set auto_play ({error}); tick it by hand.")

    try:
        settings = sequence_actor.get_editor_property("playback_settings")
        loop_count = settings.get_editor_property("loop_count")
        loop_count.set_editor_property("value", -1)
        settings.set_editor_property("loop_count", loop_count)
        sequence_actor.set_editor_property("playback_settings", settings)
    except Exception as error:
        log(f"WARNING: could not set loop count ({error}); set Loop by hand.")


def main() -> None:
    actor = find_target_actor()
    manny, _cloth = find_components(actor)

    sequence = get_or_create_sequence()

    # Binding the component creates the parent actor binding automatically.
    sequence.add_possessable(actor)
    binding = sequence.add_possessable(manny)

    for track in binding.get_tracks():
        binding.remove_track(track)

    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(0, int(round(TOTAL_SECONDS * FPS)))

    key_transform(section, manny, build_keyframes())

    if SPAWN_SEQUENCE_ACTOR:
        ensure_sequence_actor(sequence)

    unreal.EditorAssetLibrary.save_loaded_asset(sequence)

    # The spawned LevelSequenceActor lives in the level, not the sequence asset,
    # so without this it evaporates on the next level reload.
    if SPAWN_SEQUENCE_ACTOR:
        try:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
            log("Saved current level (LevelSequenceActor persisted).")
        except Exception as error:
            log(f"WARNING: could not save the level ({error}); save it by hand.")

    log(f"Done. Open {SEQUENCE_PACKAGE_PATH}/{SEQUENCE_NAME} and hit Simulate.")


if __name__ == "__main__":
    main()
