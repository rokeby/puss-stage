"""Read-only: does the S4 Arrival hand the rise to Scene 4 without a seam? Asks the Arrival
(ResolveRotationAtMasterFrame, no side effects) for the root's pitch at Master times before
Scene 4's first frame, and compares the last one with the rise channel itself at Scene 4's
time 0, which is what Sequencer plays from that frame on. Also: at and after the first frame
the Arrival must decline. Scene 4's start comes from the transport's own segments. Mutates
nothing."""
import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RISE = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"


def main():
    show = unreal.load_asset(SHOW)
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    seg = next(s for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")).startswith("Scene 4"))
    start = seg.get_editor_property("start_frame").value
    del tr
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    arrival = next(a for a in sub.get_all_level_actors() if a.get_actor_label() == "S4 Arrival")
    rows = []
    for secs in (6.0, 3.574, 3.0, 2.0, 1.0, 0.5, 1.0 / rate, 0.0, -1.0):
        mt = unreal.FrameTime(frame_number=unreal.FrameNumber(int(round(start - secs * rate))), sub_frame=0.0)
        # UE Python returns the out-parameter on success and None when the bool is false.
        rot = arrival.resolve_rotation_at_master_frame(show, mt)
        rows.append(f"{-secs:+.4f}s:{'%.3f' % rot.pitch if rot is not None else 'declined'}")
    # Sequencer's value at Scene 4's time 0: the AUTO keys (-90 at the release, 0 at 16 s) are an
    # exact smoothstep (verified on the v2 rise), so the expected pitch is computed from them.
    rise = unreal.load_asset(RISE)
    fps = rise.get_display_rate().numerator / rise.get_display_rate().denominator
    binding = next(b for b in rise.get_bindings() if str(b.get_display_name()) == "S4 Hangar Root")
    track = next(t for t in binding.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack))
    keys = [k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value / fps
            for k in track.get_sections()[0].get_all_channels()[4].get_keys()]
    u = (0.0 - keys[0]) / (keys[-1] - keys[0])
    at0 = -90.0 + 90.0 * (3 * u * u - 2 * u ** 3)
    unreal.log(f"P04_ARRIVAL_CHECK|scene4_start_frame={start}|{'|'.join(rows)}|channel_at_scene_time_0={at0}")


main()
