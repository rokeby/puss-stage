import json, unreal
snap = json.load(open(unreal.Paths.project_saved_dir() + "CodexConductor/S3FeetByHand_20261009/s3_feet_snapshot.json"))
LABEL = "S3 Crowd 15 (from Shore04_F55)"
hits = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label() == LABEL]
assert len(hits) == 1, "COUNT"
a = hits[0]; row = {r["path"]: r for r in snap["all_actors"]}[a.get_path_name()]["transform"]
l, r = row["location"], row["rotation"]
a.set_actor_location_and_rotation(unreal.Vector(*l), unreal.Rotator(roll=r[0], pitch=r[1], yaw=r[2]), False, True)
n = a.get_actor_location(); y = a.get_actor_rotation()
unreal.log("CROWD15_RESTORE|loc=%.2f,%.2f,%.2f|rot=%.2f,%.2f,%.2f|snap=%s|%s" % (n.x, n.y, n.z, y.roll, y.pitch, y.yaw, l, r))
