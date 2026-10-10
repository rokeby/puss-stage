"""Read-only Job 179 PIE scrub to one Passage fraction; never starts/ends PIE."""
import json
import os
import re
import unreal

root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
args = json.load(open(os.path.join(root, "CodexConductor", "job179_pie_spot_args.json"), encoding="utf-8"))
passage = str(args.get("passage", "")).upper()
fraction = float(args.get("fraction", -1.0))
if not re.fullmatch(r"P0[1-6]", passage) or fraction not in (0.1, 0.5, 0.9):
    raise RuntimeError("JOB179_PIE_SPOT_ARGS|passage=%s|fraction=%s" % (passage, fraction))
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB179_PIE_SPOT_NO_PIE")
roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
if len(roots) != 1 or roots[0].sequence_player is None:
    raise RuntimeError("JOB179_PIE_SPOT_SHOW_ROOT|count=%d" % len(roots))
show = roots[0]
label = "Passage %d" % int(passage[-1])
segments = [segment for segment in list(show.transport.segments)
            if segment.type == unreal.InfinityCueType.WING_PAIR and str(segment.label) == label]
if len(segments) != 1:
    raise RuntimeError("JOB179_PIE_SPOT_SEGMENT|label=%s|count=%d" % (label, len(segments)))
start = int(segments[0].start_frame.value)
end = int(segments[0].end_frame.value)
frame = start + int(round(fraction * (end - start)))
frame = min(end - 1, max(start, frame))
show.sequence_player.pause()
if not show.transport.scrub_to_master_frame(unreal.FrameNumber(frame)):
    raise RuntimeError("JOB179_PIE_SPOT_SCRUB_FAILED|frame=%d" % frame)
unreal.log("JOB179_PIE_SPOT_OK|passage=%s|fraction=%.1f|frame=%d" % (passage, fraction, frame))
