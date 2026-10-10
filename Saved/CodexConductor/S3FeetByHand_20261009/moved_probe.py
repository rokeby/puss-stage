import json, unreal
snap = json.load(open(unreal.Paths.project_saved_dir() + "CodexConductor/S3FeetByHand_20261009/s3_feet_snapshot.json"))
old = {a["path"]: a for a in snap["all_actors"]}
tgt = {t["actor_path"] for t in snap["targets"]}
moved = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    p = a.get_path_name(); o = old.get(p)
    if not o: continue
    l = a.get_actor_location(); ol = o["transform"]["location"]
    d = [l.x - ol[0], l.y - ol[1], l.z - ol[2]]
    if max(abs(x) for x in d) > 0.01:
        moved.append("%s%s dz=%.1f dxy=%.1f,%.1f" % ("T:" if p in tgt else "N:", a.get_actor_label(), d[2], d[0], d[1]))
unreal.log("FEET_MOVED_PROBE|n=%d|%s" % (len(moved), ";".join(moved)))
