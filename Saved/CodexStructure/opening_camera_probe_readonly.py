"""Read-only: where the audience's camera actually is during the opening curtain.

LS_Opening_Curtain has no camera-cut track, so the opening shot comes from
elsewhere. Report that sequence's own bindings and tracks, the Show's managed
Master sequence camera cuts over the Opening cue's frames, and the P01 camera
rig's route-evaluated position at distance 0 and at its first wing. Mutates
nothing.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
report = {}

seq = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Interactions/LS_Opening_Curtain")
report["opening_sequence"] = {
    "bindings": [str(b.get_display_name()) for b in seq.get_bindings()],
    "tracks": [t.get_class().get_name() for t in seq.get_tracks()],
    "binding_tracks": {str(b.get_display_name()): [t.get_class().get_name() for t in b.get_tracks()]
                       for b in seq.get_bindings()},
}

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
master = show.get_editor_property("managed_master_sequence")
cuts = []
if master:
    ms = master if isinstance(master, unreal.LevelSequence) else master.load_synchronous() if hasattr(master, "load_synchronous") else None
    if ms:
        bindings = {unreal.GuidLibrary.conv_guid_to_string(b.get_id()): str(b.get_display_name()) for b in ms.get_bindings()}
        for track in ms.get_tracks():
            if isinstance(track, unreal.MovieSceneCameraCutTrack):
                for sec in track.get_sections():
                    guid = unreal.GuidLibrary.conv_guid_to_string(sec.get_camera_binding_id().get_editor_property("guid"))
                    cuts.append({"start": sec.get_start_frame(), "end": sec.get_end_frame(),
                                 "camera": bindings.get(guid, guid)})
        report["master"] = {"path": ms.get_path_name(), "tick": str(ms.get_tick_resolution()),
                            "first_cuts": sorted(cuts, key=lambda c: c["start"])[:6],
                            "track_types": sorted({t.get_class().get_name() for t in ms.get_tracks()})}

rigs = []
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if a.get_class().get_name() == "InfinityStageCameraRig":
        loc = a.get_actor_location()
        entry = {"label": a.get_actor_label(), "saved_location": [round(loc.x), round(loc.y), round(loc.z)]}
        for name in ("passage_actor", "passage", "camera_offset", "camera_offset_cm"):
            try:
                v = a.get_editor_property(name)
                entry[name] = v.get_actor_label() if isinstance(v, unreal.Actor) else str(v)
            except Exception:
                pass
        rigs.append(entry)
report["camera_rigs"] = rigs

p01 = next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
           if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
route = p01.get_editor_property("route")
report["p01_route_start"] = [round(c) for c in (route.get_location_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD).x,
                                                route.get_location_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD).y)]

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "opening_camera_probe.json")
json.dump(report, open(out, "w"), indent=1, default=str)
unreal.log(f"OPENING_CAMERA_PROBE_OK|master_cuts={len(cuts)}|rigs={len(rigs)}|mutated=0")
