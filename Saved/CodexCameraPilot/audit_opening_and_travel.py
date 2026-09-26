"""Read-only audit for the transitions-and-scale brief (Gary, 2026-09-26).

Part one: what the Opening segment is today and how it hands to Passage 1.
Part two: how each Passage's travel is timed in the managed Master (speed
channel, anchors) and what music analysis is attached.
Writes nothing. Success marker: PUSS_OPENING_TRAVEL_AUDIT
"""

import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def unwrap(result, count):
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    return result


def guid_text(guid):
    return unreal.GuidLibrary.conv_guid_to_string(guid)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    raise RuntimeError("Unexpected editor world")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
dirty_before = sorted(
    [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])

show = unreal.load_asset(SHOW_PATH)
tick = show.get_editor_property("tick_resolution")
tick_rate = tick.numerator / tick.denominator
library = unreal.InfinityStageCameraPilotLibrary
cues = list(show.get_editor_property("cues"))
passages = list(show.get_editor_property("passage_settings"))

# ---- Part one: the Opening -------------------------------------------------
opening = cues[0]
scene = opening.get_editor_property("scene")
sequence = scene.get_editor_property("sequence")
opening_info = {
    "label": str(opening.get_editor_property("label")),
    "type": str(opening.get_editor_property("type")),
    "camera_owner": str(scene.get_editor_property("camera_owner")),
    "curtain_mode": str(scene.get_editor_property("curtain_mode")),
    "sequence_owns_curtain": bool(scene.get_editor_property("sequence_owns_curtain")),
    "retain_previous_camera": bool(scene.get_editor_property("retain_previous_camera")),
    "use_sequence_length": bool(scene.get_editor_property("use_sequence_length")),
    "duration_s": scene.get_editor_property("duration_frames").value / tick_rate,
    "curtain_entry_s": scene.get_editor_property("curtain_entry_transition_frames").value / tick_rate,
    "curtain_hold_s": scene.get_editor_property("curtain_hold_frames").value / tick_rate,
    "curtain_exit_s": scene.get_editor_property("curtain_exit_transition_frames").value / tick_rate,
    "sequence": sequence.get_path_name() if sequence else None,
}
if sequence:
    cut_tracks = sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)
    opening_info["sequence_camera_cuts"] = sum(len(t.get_sections()) for t in cut_tracks)
    opening_info["sequence_bindings"] = [str(b.get_display_name()) for b in sequence.get_bindings()]
    opening_info["sequence_playback_s"] = [
        sequence.get_playback_start_seconds(), sequence.get_playback_end_seconds()]

# ---- Part two: Passage travel timing ----------------------------------------
master = show.get_editor_property("managed_master_sequence")
sections = {}
if master:
    for track in master.get_tracks():
        if track.get_class().get_name() != "MovieSceneInfinityPassageTrack":
            continue
        for section in track.get_sections():
            guid = guid_text(section.get_editor_property("passage_guid"))
            channels = {}
            for channel in section.get_all_channels():
                name = str(channel.channel_name) if hasattr(channel, "channel_name") else str(channel.get_name())
                keys = channel.get_keys()
                values = [k.get_value() for k in keys]
                channels[name] = {
                    "keys": len(keys),
                    "min": min(values) if values else None,
                    "max": max(values) if values else None,
                }
            sections[guid] = {
                "channels": channels,
                "pinned_wings": len(section.get_editor_property("pinned_wing_cue_guids")),
                "pinned_music_frames": len(section.get_editor_property("pinned_passage_frames")),
            }

rails = {guid_text(r.get_editor_property("rail_guid")): r for r in show.get_editor_property("music_rails")}
travel = []
for settings in passages:
    guid = settings.get_editor_property("passage_guid")
    frame_range = unwrap(library.get_passage_frame_range(show, guid), 2)
    music = settings.get_editor_property("music")
    rail = rails.get(guid_text(music.get_editor_property("primary_rail_guid")))
    analysis = None
    if rail is not None:
        try:
            amap = rail.get_editor_property("analysis_map")
            if amap:
                curves = amap.get_editor_property("feature_curves")
                names = []
                for curve in curves:
                    for field in ("curve_name", "name", "feature"):
                        try:
                            names.append(str(curve.get_editor_property(field)))
                            break
                        except Exception:
                            continue
                analysis = {"feature_curves": len(curves), "features": names,
                            "expressive_sections": len(amap.get_editor_property("expressive_sections"))}
            else:
                analysis = {"analysis_map": None}
        except Exception as error:
            analysis = {"error": str(error)}
    travel.append({
        "label": str(settings.get_editor_property("label")),
        "camera_owner": str(settings.get_editor_property("camera_owner")),
        "duration_s": (frame_range[1] - frame_range[0]) / tick_rate if frame_range else None,
        "start_s": frame_range[0] / tick_rate if frame_range else None,
        "lead_in_s": settings.get_editor_property("lead_in_frames").value / tick_rate,
        "lead_in_cm": settings.get_editor_property("lead_in_distance_cm"),
        "tail_s": settings.get_editor_property("tail_frames").value / tick_rate,
        "preferred_speed_cm_s": settings.get_editor_property("preferred_camera_speed_cm_per_second"),
        "fit_mode": str(settings.get_editor_property("fit_mode")),
        "section": sections.get(guid_text(guid)),
        "music_analysis": analysis,
    })

dirty_after = sorted(
    [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
payload = {"opening": opening_info, "passages": travel, "dirty_before": dirty_before, "dirty_after": dirty_after}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexCameraPilot", "audit_opening_and_travel.json")
with open(out, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, default=str)
if dirty_after != dirty_before:
    raise RuntimeError(f"Audit changed dirty state: {dirty_before} -> {dirty_after}")
unreal.log(f"PUSS_OPENING_TRAVEL_AUDIT|passages={len(travel)}|sections={len(sections)}|dirty_unchanged=1")
