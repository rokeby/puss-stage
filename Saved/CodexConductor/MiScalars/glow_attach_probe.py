"""Read-only: is 'S3 Drama Pearl Glow' still attached to 'S3 PearlClam Pearl'? Marker GLOWPROBE|run=..."""
import datetime
import unreal
run = datetime.datetime.now().strftime("%H%M%S")
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rows = []
for a in eas.get_all_level_actors():
    lab = a.get_actor_label()
    if lab in ("S3 Drama Pearl Glow", "S3 PearlClam Pearl"):
        par = a.get_attach_parent_actor()
        mats = []
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            mats = [m.get_path_name().split(".")[0] if m else None for m in smc.get_materials()]
        rows.append("%s->%s mats=%s" % (lab, par.get_actor_label() if par else None, mats))
unreal.log("GLOWPROBE|run=%s|%s" % (run, " ; ".join(rows)))
