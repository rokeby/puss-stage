"""Controlled experiment on P01 Wing 002 (a replicated row): set Cross +Y rel rotation to a simple known value,
materialize Passage 01, read the actor back, then restore the previous value and materialize again."""
import json, unreal
def rot(r): return [round(r.pitch,2), round(r.yaw,2), round(r.roll,2)]
def vec(v): return [round(v.x,1), round(v.y,1), round(v.z,1)]
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
pa = [a for a in sub.get_all_level_actors() if a.get_actor_label().startswith("Passage 01") and a.get_class().get_name() == "InfinityStagePassageActor"][0]
def actor_world(label):
    for a in sub.get_all_level_actors():
        if isinstance(a, unreal.Light) and a.get_actor_label() == label:
            t = a.get_actor_transform(); return {"loc": vec(t.translation), "rot": rot(t.rotation.rotator())}
def set_rel(pitch, yaw, roll, loc=None):
    cues = list(show.get_editor_property("cues"))
    for i, cue in enumerate(cues):
        if str(cue.get_editor_property("label")) != "P01 Wing 002": continue
        pair = cue.get_editor_property("wing_pair"); atts = list(pair.get_editor_property("attachments"))
        for k, att in enumerate(atts):
            if str(att.get_editor_property("label")) == "P01 Wing 002 Cross +Y":
                t = att.get_editor_property("relative_transform"); prev = {"loc": vec(t.translation), "rot": rot(t.rotation.rotator())}
                t2 = unreal.Transform(); t2.translation = t.translation if loc is None else unreal.Vector(*loc)
                t2.rotation = unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw).quaternion()
                att.set_editor_property("relative_transform", t2); atts[k] = att
                pair.set_editor_property("attachments", atts); cue.set_editor_property("wing_pair", pair); cues[i] = cue
                show.modify(); show.set_editor_property("cues", cues); return prev
    raise RuntimeError("row 2 Cross +Y not found")
result = {"passage_actor": {"loc": vec(pa.get_actor_location()), "rot": rot(pa.get_actor_rotation())}, "before_actor": actor_world("P01 Wing 002 Cross +Y")}
prev = set_rel(-45.0, 0.0, 0.0); result["prev_rel"] = prev
assert pa.materialize_passage(); result["simple_(-45,0,0)_actor"] = actor_world("P01 Wing 002 Cross +Y")
set_rel(-30.0, 60.0, -120.0); assert pa.materialize_passage(); result["compound_(-30,60,-120)_actor"] = actor_world("P01 Wing 002 Cross +Y")
set_rel(prev["rot"][0], prev["rot"][1], prev["rot"][2]); assert pa.materialize_passage(); result["restored_actor"] = actor_world("P01 Wing 002 Cross +Y")
unreal.log("PUSS_EXPERIMENT|" + json.dumps(result))
