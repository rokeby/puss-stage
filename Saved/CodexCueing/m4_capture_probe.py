"""M4: does the capture guard see a Show lamp bound by an ORDINARY possessable in an
open Sequencer (via Sequencer's object cache), keep the keyed Intensity out of the
Show, and still write a hand edit of Color?

One lamp (P01 Wing 001 House L). A TRANSIENT sequence (never saved) holds the binding.
Steps: back up the Show file -> open the transient sequence in Sequencer, key
Intensity, evaluate -> hand-edit Color -> read the Show -> close Sequencer ->
restore Color by hand edit -> read back: the lamp's Lighting text must equal the
original exactly. Saves NOTHING: the Show (and the level, from the component edit)
are left dirty for the conductor to discard or save.
Marker: M4_CAPTURE_OK|run=... only when every assertion holds; M4_STOPPED otherwise.
Never: PIE, Save All, level save, reload, GetBoundObjects.
"""
import datetime
import os
import shutil

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
ATTACHMENT_GUID = "24F0FC454E591513FB387DBE58E881DC"   # P01 Wing 001 House L (light_guid_audit 4 Oct)
RUN = "m4-" + datetime.datetime.now().strftime("%H%M%S")


def _lighting(unreal, show):
    for cue in show.get_editor_property("cues"):
        for attachment in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if unreal.GuidLibrary.conv_guid_to_string(attachment.get_editor_property("attachment_guid")).upper().replace("-", "") == ATTACHMENT_GUID:
                return attachment.get_editor_property("lighting")
    raise RuntimeError("attachment not found in the Show")


def _lamp(unreal):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        for tag in actor.tags:
            text = str(tag)
            if text.startswith("InfinityStage.Attachment.") and text.upper().endswith("|" + ATTACHMENT_GUID):
                return actor, text
    raise RuntimeError("lamp actor with the House L tag not found (Passage not materialized?)")


def run():
    import unreal
    project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_editor.is_in_play_in_editor():
        raise RuntimeError("PIE running")
    show = unreal.load_asset(SHOW_PATH)
    before = _lighting(unreal, show)
    before_text = before.export_text()
    authored_intensity = before.get_editor_property("intensity")
    authored_color = before.get_editor_property("color")

    source = os.path.join(project_dir, "Content", "InfinityStage", "Dev", "DA_InfinityStage_V1Show.uasset")
    backup_dir = os.path.join(project_dir, "Backups", "PreM4CaptureProbe-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    os.makedirs(backup_dir, exist_ok=True)
    shutil.copy2(source, os.path.join(backup_dir, os.path.basename(source)))
    unreal.log("M4_BACKUP|run=%s|dir=%s" % (RUN, backup_dir))

    actor, tag = _lamp(unreal)
    light = actor.get_component_by_class(unreal.LightComponent)
    if light is None:
        raise RuntimeError("lamp has no LightComponent")

    temp_path = "/Game/CueingProbeTemp/LS_M4_CaptureProbe"
    if unreal.EditorAssetLibrary.does_asset_exist(temp_path):
        raise RuntimeError("temp probe asset already exists: %s" % temp_path)
    # A NEW, never-saved asset (Python cannot Initialize a bare LevelSequence); deleted at the end.
    sequence = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "LS_M4_CaptureProbe", "/Game/CueingProbeTemp", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    sequence.set_playback_start(0)
    sequence.set_playback_end(48)
    binding = sequence.add_possessable(actor)
    track = binding.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path("Intensity", "%s.Intensity" % light.get_name())
    section = track.add_section()
    section.set_range(0, 48)
    channel = section.get_all_channels()[0]
    channel.add_key(unreal.FrameNumber(0), 0.0)
    original_light_color = light.get_editor_property("light_color")
    report = {"tag": tag, "authored_intensity": authored_intensity}
    try:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(1)
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
        report["live_intensity_while_keyed"] = light.get_editor_property("intensity")

        # The hand edit: Color, through the editor property path (fires PostEditChange).
        edited = unreal.Color(r=255, g=128, b=51, a=255)
        light.set_editor_property("light_color", edited)
        during = _lighting(unreal, show)
        report["show_intensity_after_edit"] = during.get_editor_property("intensity")
        report["show_color_after_edit"] = str(during.get_editor_property("color"))
        report["color_changed"] = during.get_editor_property("color") != authored_color
        report["intensity_withheld"] = abs(during.get_editor_property("intensity") - authored_intensity) < 1e-3
    finally:
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
        report["temp_deleted"] = bool(unreal.EditorAssetLibrary.delete_asset(temp_path))

    # Revert by hand edit with no Sequencer open: the normal capture writes it back.
    light.set_editor_property("light_color", original_light_color)
    after_text = _lighting(unreal, show).export_text()
    report["restored_identical"] = after_text == before_text
    unreal.log("M4_REPORT|run=%s|%s" % (RUN, report))
    if not report["restored_identical"]:
        raise RuntimeError("Show lighting not restored identically; backup at %s. before=%s after=%s" % (backup_dir, before_text, after_text))
    if not (report["color_changed"] and report["intensity_withheld"]):
        raise RuntimeError("guard did not behave: %s" % report)
    unreal.log("M4_CAPTURE_OK|run=%s|tag=%s|color_written=1|intensity_withheld=1|restored_identical=1|backup=%s" % (RUN, tag, backup_dir))


try:
    run()
except Exception as error:
    import unreal
    unreal.log_error("M4_STOPPED|run=%s|reason=%s" % (RUN, error))
    raise
