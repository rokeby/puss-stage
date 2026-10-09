"""READ-ONLY UE5.8 sampler for the S6 old lady's hands at 24 fps.

It opens the already-created Klara hook-in COPY, evaluates it without PIE, and
writes only Saved/CodexConductor/S6OldLadySwarm/hand_samples.json.  It never
saves a package or loads/saves a level.  Close Sequencer before running.
"""
from __future__ import annotations

import json
import os
import time

import unreal

SEQUENCE = "/Game/InfinityStage/KlaraHookin/LS_Void_S6"
ANIMATION = "/Game/CaptureManager/Imports/Mono_Video_Ingest/Old_woman_1/AS_MHP_Void_woman"
NEST_START_25 = 104
OUTER_TRANSLATION = (29339.2835, 399920.0, 135.0)
FPS = 24.0
RUN = "S6HAND-" + time.strftime("%Y%m%d-%H%M%S")


def stop(reason):
    unreal.log_error("S6_OLD_LADY_HAND_SAMPLE_STOP|run=%s|%s" % (RUN, reason))
    raise RuntimeError(reason)


def path(obj):
    return "" if obj is None else str(obj.get_path_name()).split(".")[0]


def dirty():
    rows = []
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        rows.append(str(package.get_name()))
    return sorted(set(rows))


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def binding_named(sequence, name):
    rows = [b for b in sequence.get_bindings() if str(b.get_display_name()) == name]
    if len(rows) != 1:
        stop("BINDING_COUNT|name=%s|count=%d" % (name, len(rows)))
    return rows[0]


def animation_section(body):
    rows = []
    for track in body.get_tracks():
        if track.get_class().get_name() == "MovieSceneSkeletalAnimationTrack":
            rows.extend(track.get_sections())
    hits = []
    for section in rows:
        params = section.get_editor_property("params")
        if path(params.get_editor_property("animation")) == ANIMATION:
            hits.append((section, params))
    if len(hits) != 1:
        stop("ANIMATION_SECTION_COUNT|count=%d" % len(hits))
    return hits[0]


def component_for(world, sequence, body):
    result = unreal.SequencerTools.get_bound_objects(world, sequence, [body], sequence.get_playback_range())
    objects = list(result[0].bound_objects) if result else []
    comps = [o for o in objects if isinstance(o, unreal.SkeletalMeshComponent)]
    if len(comps) != 1:
        stop("BODY_COMPONENT_COUNT|count=%d|objects=%s" % (len(comps), [path(o) for o in objects]))
    return comps[0]


def bone(comp, candidates):
    names = {str(comp.get_bone_name(i)).lower(): str(comp.get_bone_name(i)) for i in range(int(comp.get_num_bones()))}
    for candidate in candidates:
        if candidate.lower() in names:
            return names[candidate.lower()]
    stop("HAND_BONE_MISSING|candidates=%s" % ",".join(candidates))


def main():
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        stop("SEQUENCER_OPEN")
    before = dirty()
    if before:
        stop("DIRTY_AT_START|" + json.dumps(before))
    sequence = unreal.load_asset(SEQUENCE)
    if sequence is None:
        stop("SEQUENCE_MISSING")
    body = binding_named(sequence, "Body")
    section, params = animation_section(body)
    source = params.get_editor_property("animation")
    if source is None:
        stop("ANIMATION_MISSING")
    display = sequence.get_display_rate()
    display_fps = float(display.numerator) / float(display.denominator)
    start = int(section.get_start_frame())
    end = int(section.get_end_frame())
    if end <= start:
        stop("ANIMATION_RANGE_EMPTY")

    lib = unreal.LevelSequenceEditorBlueprintLibrary
    lib.open_level_sequence(sequence)
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        comp = component_for(world, sequence, body)
        left_name = bone(comp, ("hand_l", "wrist_l", "LeftHand"))
        right_name = bone(comp, ("hand_r", "wrist_r", "RightHand"))
        start_s, end_s = start / display_fps, end / display_fps
        count = int((end_s - start_s) * FPS) + 1
        samples = []
        for index in range(count):
            inner_s = start_s + index / FPS
            display_value = inner_s * display_fps
            whole = int(display_value)
            frame_time = unreal.FrameTime(unreal.FrameNumber(whole), float(display_value - whole))
            lib.set_global_time(frame_time)
            lib.refresh_current_level_sequence()
            lp = vec(comp.get_bone_location(left_name, unreal.BoneSpaces.WORLD_SPACE))
            rp = vec(comp.get_bone_location(right_name, unreal.BoneSpaces.WORLD_SPACE))
            samples.append({
                "s6_seconds": round(NEST_START_25 / 25.0 + inner_s, 9),
                "source_seconds": round(inner_s, 9),
                "left_hand_world_cm": [lp[i] + OUTER_TRANSLATION[i] for i in range(3)],
                "right_hand_world_cm": [rp[i] + OUTER_TRANSLATION[i] for i in range(3)],
            })
    finally:
        lib.close_level_sequence()

    after = dirty()
    if after != before:
        stop("DIRTY_CHANGED|before=%s|after=%s" % (json.dumps(before), json.dumps(after)))
    offset = params.get_editor_property("start_frame_offset")
    rate = params.get_editor_property("play_rate")
    record = {
        "schema": "pussstage.s6-old-lady-hand-samples.v1", "run": RUN,
        "source": {"sequence": SEQUENCE, "animation": path(source),
                   "section_display_frames": [start, end], "sequence_display_fps": display_fps,
                   "start_frame_offset": int(offset.value), "play_rate": float(rate),
                   "left_bone": left_name, "right_bone": right_name,
                   "s6_nesting_start_frame_25": NEST_START_25,
                   "evidence": "measured by evaluated copy; no package writes"},
        "fps": FPS, "sample_count": len(samples), "dirty_before": before, "dirty_after": after,
        "samples": samples,
    }
    here = os.path.dirname(os.path.abspath(__file__))
    output = os.path.join(here, "hand_samples.json")
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    with open(output, "r", encoding="utf-8") as handle:
        check = json.load(handle)
    if check["sample_count"] != len(samples):
        stop("FILE_READBACK_COUNT")
    unreal.log("S6_OLD_LADY_HAND_SAMPLE_OK|run=%s|samples=%d|animation=%s|offset=%d|rate=%.6f|dirty=0|output=%s" %
               (RUN, len(samples), path(source), int(offset.value), float(rate), output))


main()
