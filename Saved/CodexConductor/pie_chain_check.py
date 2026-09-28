"""What would PIE actually play right now?"""
import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
unreal.log("PIE_WORLD|%s" % world.get_name())
roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
unreal.log("PIE_SHOWROOTS|%d" % len(roots))
show = None
for r in roots:
    show = r.get_editor_property("show_asset")
    unreal.log("PIE_ROOT|%s|show=%s" % (r.get_actor_label(), show.get_name() if show else "None"))
    try:
        ms = r.get_editor_property("master_sequence")
        unreal.log("PIE_MASTER|%s" % (ms.get_name() if ms else "None"))
    except Exception as e:
        unreal.log("PIE_MASTER|<%s>" % e)
if show:
    cues = show.get_editor_property("cues")
    for i, c in enumerate(cues[:4]):
        lbl = c.get_editor_property("label")
        try:
            sc = c.get_editor_property("scene")
            seq = sc.get_editor_property("sequence")
            seqn = seq.get_asset_name() if seq else "None"
        except Exception:
            seqn = "?"
        unreal.log("PIE_CUE|%d|%s|sequence=%s" % (i, lbl, seqn))
