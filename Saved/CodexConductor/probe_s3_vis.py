import json, unreal
a = json.load(open("E:/PussStage/Saved/CodexConductor/probe_s3_vis_args.json", encoding="utf-8"))
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
if a["phase"] == "scrub":
    segs = [s for s in list(root.transport.segments) if s.type == unreal.InfinityCueType.SCENE and str(s.label).startswith("Scene 3")]
    f = int(segs[0].start_frame.value) + int(a["t"] * 24000)
    root.sequence_player.pause()
    r = root.transport.scrub_to_master_frame(unreal.FrameNumber(f))
    unreal.log("S3VIS_SCRUB|run=%s|result=%s" % (a["run"], r))
else:
    want = ["S3 Granite Millstone", "Clam_Pedastal", "source_Anim", "Clam_with_Pearl_Clam_with_Pearl_0", "Shore01_M56 Clam", "Shore04_F55 Clam"]
    out = []
    for act in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        lab = str(act.get_actor_label())
        if lab in want:
            rc = act.root_component
            out.append("%s:hidden=%s,vis=%s,z=%.0f" % (lab, act.get_editor_property("hidden"), rc.is_visible() if rc else None, act.get_actor_location().z))
    unreal.log("S3VIS_READ|run=%s|%s" % (a["run"], " ; ".join(sorted(out))))
