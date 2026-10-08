"""PIE bench: perf mode off (original saved), scrub to the Scene 1 segment start + offset_s (negative = before it, in
Passage 1), play.  Args pie_s1_goto_args.json {"offset_s":-1.5} or {"restore":true}.  PIE_S1_GOTO_OK."""
import json
HERE = "E:/PussStage/Saved/CodexConductor/"
def main():
    import unreal
    a = json.load(open(HERE + "pie_s1_goto_args.json"))
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
    tr = root.transport
    if a.get("restore"):
        tr.set_editor_property("performance_mode", json.load(open(HERE + "pie_s1_goto_orig.json"))["pm"])
        unreal.log("PIE_S1_GOTO_OK|restored"); return
    json.dump({"pm": bool(tr.get_editor_property("performance_mode"))}, open(HERE + "pie_s1_goto_orig.json", "w"))
    tr.set_editor_property("performance_mode", False)
    seg = [s for s in list(tr.segments) if str(s.label).startswith("Scene 1")][0]
    target = int(seg.start_frame.value) + int(round(float(a["offset_s"]) * 24000))
    root.sequence_player.pause()
    res = tr.scrub_to_master_frame(unreal.FrameNumber(target))
    root.sequence_player.play()
    unreal.log("PIE_S1_GOTO_OK|scrub=%s|target=%d|seg_start=%d" % (res, target, seg.start_frame.value))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIE_S1_GOTO_FAILED|%r" % (exc,))
