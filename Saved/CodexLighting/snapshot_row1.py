import json, os, unreal
def rot(r): return [round(r.pitch,3), round(r.yaw,3), round(r.roll,3)]
def vec(v): return [round(v.x,2), round(v.y,2), round(v.z,2)]
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
assert show, "Show did not load (PIE?)"
out = {}
for cue in show.get_editor_property("cues"):
    if str(cue.get_editor_property("label")) == "P01 Wing 001":
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if att.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT:
                t = att.get_editor_property("relative_transform")
                out[str(att.get_editor_property("label"))[13:]] = {"loc": vec(t.translation), "rot": rot(t.rotation.rotator()), "enabled": bool(att.get_editor_property("enabled")), "int": float(att.get_editor_property("lighting").get_editor_property("intensity"))}
        break
p = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "row1_snapshot.json")
json.dump(out, open(p, "w"), indent=1)
unreal.log("PUSS_ROW1_SNAPSHOT|" + json.dumps(out))
