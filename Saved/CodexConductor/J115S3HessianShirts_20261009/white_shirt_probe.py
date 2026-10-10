import sys, unreal
HERE = unreal.Paths.project_saved_dir() + "CodexConductor/J115S3HessianShirts_20261009"
sys.path.insert(0, HERE)
import importlib, j115_core as core, j115_editor as ed
out = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
        m = c.get_skeletal_mesh_asset()
        if m is None or "_outfits" not in (ed.path_of(m) or "").lower(): continue
        mats = [ed.path_of(c.get_material(i)) for i in range(c.get_num_materials())]
        sh = [p for p in mats if core.classify_material(p) == "shirt"]
        if sh and not all("Shirt_Hessian" in (p or "") for p in sh):
            out.append("%s|%s|%s" % (a.get_actor_label(), a.get_path_name().split(".")[-1], sorted(set(sh))))
unreal.log("WHITE_SHIRT_PROBE|n=%d|%s" % (len(out), " ;; ".join(out)))
