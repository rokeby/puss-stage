import json, os, unreal
def rot(r): return [round(r.pitch,2), round(r.yaw,2), round(r.roll,2)]
def vec(v): return [round(v.x,1), round(v.y,1), round(v.z,1)]
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); out = {}
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.Light) and a.get_actor_label().startswith("P01 Wing 001 "):
        c = a.get_component_by_class(unreal.LightComponent)
        out[a.get_actor_label()[13:]] = {"actor_rot": rot(a.get_actor_rotation()), "actor_loc": vec(a.get_actor_location()), "comp_world_rot": rot(c.get_editor_property("relative_rotation")) if False else rot(c.get_component_to_world().rotation.rotator()) if hasattr(c,'get_component_to_world') else None,
                                          "comp_rel_rot": rot(c.get_editor_property("relative_rotation")), "forward": vec(a.get_actor_forward_vector()), "parent": a.get_attach_parent_actor().get_actor_label() if a.get_attach_parent_actor() else None, "socket": str(a.get_attach_parent_socket_name())}
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
for cue in show.get_editor_property("cues"):
    if str(cue.get_editor_property("label")) == "P01 Wing 001":
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if att.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT:
                k = str(att.get_editor_property("label"))[13:]
                if k in out: out[k]["show_rel_rot"] = rot(att.get_editor_property("relative_transform").rotation.rotator()); out[k]["show_rel_loc"] = vec(att.get_editor_property("relative_transform").translation)
        break
unreal.log("PUSS_ROW1_NOW|" + json.dumps(out))
