"""PIE bench (no saves): performance mode OFF on the PIE transport (original written to pie_s3_goto_orig.json first),
scrub to Scene 3 + offset_s, play.  Args pie_s3_goto_args.json {"offset_s":..,"restore":false}.  With restore=true it only
restores performance mode.  PIE_S3_GOTO_OK / _FAILED."""
import json
HERE = "E:/PussStage/Saved/CodexConductor/"
def main():
    import unreal
    a = json.load(open(HERE + "pie_s3_goto_args.json"))
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if w is None:
        raise RuntimeError("NO_PIE")
    root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
    tr = root.transport
    if a.get("restore"):
        o = json.load(open(HERE + "pie_s3_goto_orig.json"))
        tr.set_editor_property("performance_mode", o["performance_mode"])
        unreal.log("PIE_S3_GOTO_OK|restored performance_mode=%s" % tr.get_editor_property("performance_mode"))
        return
    json.dump({"performance_mode": bool(tr.get_editor_property("performance_mode"))}, open(HERE + "pie_s3_goto_orig.json", "w"))
    tr.set_editor_property("performance_mode", False)
    segs = [s for s in list(tr.segments) if str(s.label).startswith("Scene 3")]
    target = int(segs[0].start_frame.value) + int(round(float(a["offset_s"]) * 24000))
    root.sequence_player.pause()
    res = tr.scrub_to_master_frame(unreal.FrameNumber(target))
    root.sequence_player.play()
    unreal.log("PIE_S3_GOTO_OK|scrub=%s|target=%d" % (res, target))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIE_S3_GOTO_FAILED|%r" % (exc,))
