import unreal, re
out = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    lab = str(a.get_actor_label())
    meshes = []
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        m = c.get_editor_property("static_mesh")
        if m: meshes.append(m.get_name())
    txt = lab + " " + " ".join(meshes)
    if re.search(r"(?i)smoke|haze|fog ?machine|hazer|fogger", txt) and re.search(r"(?i)P04|Passage 4|Passage_4|P4", lab + " " + str(a.get_folder_path())):
        l = a.get_actor_location()
        out.append("%s|%s|%s|%.0f,%.0f,%.0f|hidden=%s" % (lab, a.get_folder_path(), ",".join(meshes[:3]), l.x, l.y, l.z, a.is_hidden_ed()))
unreal.log("SMOKE_PROBE|n=%d|%s" % (len(out), " ;; ".join(out)))
