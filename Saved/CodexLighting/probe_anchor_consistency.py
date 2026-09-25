"""Read-only: for each row-1 light, derive Anchor = Rel^-1 * ActorWorld and see whether all nine agree."""
import json, os, unreal
def rot(r): return [round(r.pitch,2), round(r.yaw,2), round(r.roll,2)]
def vec(v): return [round(v.x,1), round(v.y,1), round(v.z,1)]
def tf(t): return {"loc": vec(t.translation), "rot": rot(t.rotation.rotator()), "scale": vec(t.scale3d)}
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = {a.get_actor_label()[13:]: a for a in sub.get_all_level_actors() if isinstance(a, unreal.Light) and a.get_actor_label().startswith("P01 Wing 001 ")}
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
out = {}
for cue in show.get_editor_property("cues"):
    if str(cue.get_editor_property("label")) != "P01 Wing 001": continue
    for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
        if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT: continue
        name = str(att.get_editor_property("label"))[13:]
        rel = att.get_editor_property("relative_transform"); a = actors.get(name)
        if not a: out[name] = {"actor": None}; continue
        w = a.get_actor_transform()
        anchor = unreal.MathLibrary.compose_transforms(unreal.MathLibrary.invert_transform(rel), w)
        out[name] = {"anchor": str(att.get_editor_property("anchor")).split(".")[-1].rstrip(">"), "rel": tf(rel), "world": tf(w), "derived_anchor": tf(anchor),
                     "parent": a.get_attach_parent_actor().get_actor_label() if a.get_attach_parent_actor() else None}
    break
pa = [a for a in sub.get_all_level_actors() if a.get_actor_label().startswith("Passage 01") and a.get_class().get_name() == "InfinityStagePassageActor"][0]
out["_passage_actor"] = tf(pa.get_actor_transform())
route = pa.get_editor_property("route")
if route: out["_route_station_250"] = tf(route.get_transform_at_distance_along_spline(250.0, unreal.SplineCoordinateSpace.WORLD, True))
unreal.log("PUSS_ANCHOR|" + json.dumps(out))
