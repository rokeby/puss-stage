"""Read-only: for every NESTED scene, the Arrival's pitch one Master tick before the Scene vs the rise channel at Scene
time 0 (the AUTO two-key rise is an exact smoothstep). Equal = seamless handover. Mutates nothing."""
import unreal


def main():
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    starts = {str(s.get_editor_property("label")).split()[1]: s.get_editor_property("start_frame").value
              for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")).startswith("Scene ")}
    del tr
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for a in sub.get_all_level_actors():
        if not isinstance(a, unreal.InfinityStageArrival):
            continue
        n = a.get_actor_label()[1]
        last = a.resolve_rotation_at_master_frame(show, unreal.FrameTime(frame_number=unreal.FrameNumber(starts[n] - 1), sub_frame=0.0))
        if last is None:
            rows.append(f"S{n}:inert")
            continue
        rise = unreal.load_asset(f"/Game/InfinityStage/RigAtmos/LS_S{n}_HangarRise")
        b = next(x for x in rise.get_bindings() if str(x.get_display_name()) == f"S{n} Hangar Root")
        trk = next(t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack))
        keys = [k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value / 30.0 for k in trk.get_sections()[0].get_all_channels()[4].get_keys()]
        u = -keys[0] / (keys[-1] - keys[0])
        at0 = -90.0 + 90.0 * (3 * u * u - 2 * u ** 3)
        rows.append(f"S{n}:arrival_last_tick={last.pitch:.3f}:channel_at_0={at0:.3f}:seam={'OK' if abs(last.pitch - at0) < 0.05 else 'GAP'}")
    unreal.log("SEAM_CHECK|" + " ".join(sorted(rows)))


main()
