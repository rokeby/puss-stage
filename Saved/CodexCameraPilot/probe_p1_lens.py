"""Read-only: Passage 1's lens channel state and the rig camera's aperture. Marker: PUSS_P1_LENS_PROBE"""
import unreal
show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
master = show.get_editor_property("managed_master_sequence")
p1 = next(p for p in show.get_editor_property("passage_settings") if str(p.get_editor_property("label")) == "Passage 1")
g = unreal.GuidLibrary.conv_guid_to_string(p1.get_editor_property("passage_guid"))
info = {}
for track in master.get_tracks():
    if track.get_class().get_name() != "MovieSceneInfinityPassageTrack": continue
    for s in track.get_sections():
        if unreal.GuidLibrary.conv_guid_to_string(s.get_editor_property("passage_guid")) != g: continue
        for ch in s.get_all_channels():
            name = str(ch.channel_name)
            if "Focal" in name or "Focus" in name:
                info[name] = {"keys": len(ch.get_keys()), "default": ch.get_default() if ch.has_default() else None}
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rig = next(a for a in actors if a.get_class().get_name() == "InfinityStageCameraRig" and a.get_actor_label().startswith("Passage 01"))
cam = rig.get_editor_property("camera")
unreal.log(f"PUSS_P1_LENS_PROBE|channels={info}|aperture={cam.get_editor_property('current_aperture')}")
