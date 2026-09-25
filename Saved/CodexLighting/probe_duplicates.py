import json, collections, unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
labels = collections.Counter(); untracked = 0; tracked_total = 0; by_tag = collections.Counter()
pa = [a for a in sub.get_all_level_actors() if a.get_actor_label().startswith("Passage 01") and a.get_class().get_name() == "InfinityStagePassageActor"][0]
try:
    managed = set(x.get_name() for x in pa.get_editor_property("managed_attachment_actors")); tracked_total = len(managed)
except Exception as exc:
    managed = None; tracked_total = repr(exc)
rows = []
for a in sub.get_all_level_actors():
    if not isinstance(a, unreal.Light): continue
    lbl = a.get_actor_label()
    if not lbl.startswith("P01 Wing 001 "): 
        if lbl.startswith("P0"): labels["(other rows)"] += 1
        continue
    labels[lbl[13:]] += 1
    tags = [str(t) for t in a.get_editor_property("tags")]
    r = a.get_actor_rotation()
    rows.append({"label": lbl[13:], "name": a.get_name(), "tracked": (a.get_name() in managed) if managed is not None else None, "tag": tags[0][-12:] if tags else None,
                 "parent": a.get_attach_parent_actor().get_actor_label()[:10] if a.get_attach_parent_actor() else None, "rot": [round(r.pitch,1), round(r.yaw,1), round(r.roll,1)]})
unreal.log("PUSS_DUP|" + json.dumps({"counts": dict(labels), "tracked_total_p01": tracked_total, "row1_actors": rows}))
