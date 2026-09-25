"""Post-build step 1: turn on Manual Lighting Also In Game for the production rig, rematerialize Passage 01,
and read back row 1's light actors against the Show (spot round-trip proof)."""
import json, os, re, unreal
def rot(r): return [round(r.pitch,2), round(r.yaw,2), round(r.roll,2)]
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); assert ed.get_game_world() is None, "PIE active"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rig = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStageCelestialRig"][0]
rig.modify(); rig.set_editor_property("apply_manual_lighting_in_game", True); rig.set_editor_property("use_manual_editor_lighting", True); rig.set_editor_property("editor_preview_time_hours", 0.0)
rig.apply_editor_preview_lighting()
flags = {n: rig.get_editor_property(n) for n in ("use_manual_editor_lighting", "apply_manual_lighting_in_game", "editor_preview_time_hours", "suppress_foreign_environment_lighting", "current_daylight_amount")}
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
pa = [a for a in sub.get_all_level_actors() if a.get_actor_label().startswith("Passage 01") and a.get_class().get_name() == "InfinityStagePassageActor"][0]
assert pa.materialize_passage(), "materialize failed"
by_tag = {}
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.Light):
        for t in a.get_editor_property("tags"):
            s = str(t)
            if s.startswith("InfinityStage.Attachment."): by_tag[s[len("InfinityStage.Attachment."):]] = a
cmp = {}
for cue in show.get_editor_property("cues"):
    if str(cue.get_editor_property("label")) != "P01 Wing 001": continue
    cg = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
    atts = [x for x in cue.get_editor_property("wing_pair").get_editor_property("attachments") if x.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT and x.get_editor_property("enabled")]
    rect = next(x for x in atts if x.get_editor_property("lighting").get_editor_property("type") == unreal.InfinityStageLightType.RECT)
    ra = by_tag[cg + "|" + unreal.GuidLibrary.conv_guid_to_string(rect.get_editor_property("attachment_guid"))]
    anchor = unreal.MathLibrary.compose_transforms(unreal.MathLibrary.invert_transform(rect.get_editor_property("relative_transform")), ra.get_actor_transform())
    for x in atts:
        a = by_tag.get(cg + "|" + unreal.GuidLibrary.conv_guid_to_string(x.get_editor_property("attachment_guid")))
        expect = unreal.MathLibrary.compose_transforms(x.get_editor_property("relative_transform"), anchor)
        cmp[str(x.get_editor_property("label"))[13:]] = {"expected": rot(expect.rotation.rotator()), "actual": rot(a.get_actor_rotation())}
    break
ok = sum(1 for v in cmp.values() if all(abs(v["expected"][j]-v["actual"][j]) < 0.05 for j in range(3)))
d = {"content": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()], "maps": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
unreal.log(f"REOPEN_STEP1|rig={flags}|row1_lights_match_show={ok}/{len(cmp)}|dirty={len(d['content'])}+{len(d['maps'])}")
