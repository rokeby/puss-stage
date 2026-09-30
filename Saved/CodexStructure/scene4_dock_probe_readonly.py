"""Read-only, before re-docking the Scene 4 hangar (conductor, from
Docs/Conductor/SCENE_DOCKING_AUDIT_2026-09-29.md; Gary: mouth at the arrival,
keep the height, grow Scene 4, a speed dial).

Reports:
1. The "Entry Handoff Camera" for Scene 4: label, world location and rotation.
2. Passage 04's route end in world, and its direction there.
3. Everything within the hangar's FULL swept volume at the new site, with the
   mouth on the camera and the nave along its forward. The side walls lie up to
   41 m out; the far wall and the roof, lying in line, reach 151 m past the
   mouth. A downward ground trace every 10 m along the nave.
4. LS_DevScene_04: playback range, display rate, and every track and section,
   with its sequence and range.

Writes scene4_dock_probe.json. Mutates nothing. Lean: all work in main().
"""
import json
import os

import unreal

SCENE4 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
NAVE_LEN, HALF_W, HEIGHT = 6000.0, 1000.0, 3000.0
PACKED_REACH_X = NAVE_LEN + 50.0 + HEIGHT + 6050.0   # far wall lying + the roof in line beyond it
PACKED_REACH_Y = HALF_W + 50.0 + HEIGHT + 100.0       # side walls lying outward


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    out = {}
    cams = [a for a in actors if "Entry Handoff Camera" in a.get_actor_label()]
    out["entry_handoff_cameras"] = [{"label": a.get_actor_label(), "loc": [round(v, 1) for v in a.get_actor_location().to_tuple()],
                                     "rot": [round(v, 2) for v in (a.get_actor_rotation().roll, a.get_actor_rotation().pitch,
                                                                   a.get_actor_rotation().yaw)]} for a in cams]
    s4 = [c for c in out["entry_handoff_cameras"] if "04" in c["label"] or "Scene 4" in c["label"]]
    out["scene4_camera"] = s4
    p04 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 04"))
    route = p04.get_editor_property("route")
    length = route.get_spline_length()
    end = route.get_location_at_distance_along_spline(length, unreal.SplineCoordinateSpace.WORLD)
    direction = route.get_direction_at_distance_along_spline(length, unreal.SplineCoordinateSpace.WORLD)
    out["p04_route_end"] = {"loc": [round(v, 1) for v in end.to_tuple()], "dir": [round(v, 4) for v in direction.to_tuple()],
                            "length_cm": round(length, 1)}
    if len(s4) == 1:
        mouth = unreal.Vector(*s4[0]["loc"])
        lo = (mouth.x - 100.0, mouth.y - PACKED_REACH_Y, -100.0)
        hi = (mouth.x + PACKED_REACH_X, mouth.y + PACKED_REACH_Y, HEIGHT + 200.0)
        occ = []
        for a in actors:
            o, e = a.get_actor_bounds(False)
            if e.length() < 0.01 or e.x > 1e6:
                continue
            ot, et = o.to_tuple(), e.to_tuple()
            if all(ot[i] + et[i] >= lo[i] and ot[i] - et[i] <= hi[i] for i in range(3)):
                occ.append({"actor": a.get_actor_label(), "class": a.get_class().get_name(),
                            "min": [round(ot[i] - et[i]) for i in range(3)], "max": [round(ot[i] + et[i]) for i in range(3)]})
        out["swept_box"] = {"min": lo, "max": hi, "occupants": occ[:60], "n": len(occ)}
        ground = []
        for k in range(0, 7):
            p = mouth + unreal.Vector(k * 1000.0, 0.0, 0.0)
            hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(p.x, p.y, 3000.0), unreal.Vector(p.x, p.y, -3000.0),
                                                         unreal.TraceTypeQuery.ECC_VISIBILITY, True, [],
                                                         unreal.DrawDebugTrace.NONE, True)
            h = hit.to_tuple() if hit else None
            actor = next((x for x in h if isinstance(x, unreal.Actor)), None) if h and h[0] else None
            ground.append({"x": round(p.x), "hit": actor.get_actor_label() if actor else None,
                           "z": round(h[4].z, 1) if h and h[0] and isinstance(h[4], unreal.Vector) else None})
        out["ground_along_nave"] = ground
    seq = unreal.EditorAssetLibrary.load_asset(SCENE4)
    rate = seq.get_display_rate()
    tracks = []
    for t in seq.get_tracks():
        secs = []
        for s in t.get_sections():
            child = s.get_sequence() if hasattr(s, "get_sequence") else None
            secs.append({"class": s.get_class().get_name(), "child": child.get_path_name() if child else None,
                         "start_s": round(s.get_start_frame_seconds(), 3) if s.has_start_frame() else None,
                         "end_s": round(s.get_end_frame_seconds(), 3) if s.has_end_frame() else None,
                         "active": bool(s.is_active())})
        tracks.append({"track": t.get_class().get_name(), "name": str(t.get_display_name()), "sections": secs})
    out["scene4_sequence"] = {"display_rate": [rate.numerator, rate.denominator],
                              "playback_s": [round(seq.get_playback_start_seconds(), 3), round(seq.get_playback_end_seconds(), 3)],
                              "tracks": tracks,
                              "bindings": [str(b.get_display_name()) for b in seq.get_bindings()]}
    json.dump(out, open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                     "CodexStructure", "scene4_dock_probe.json"), "w"), indent=1, default=str)
    unreal.log(f"SCENE4_DOCK_PROBE_OK|cams={len(cams)}|s4={len(s4)}|occupants={out.get('swept_box', {}).get('n')}|mutated=0")


main()
