"""In-session display fix (no Show change, no save): for every wing pair, derive the true anchor from the
round-tripping Low rects and re-place each spot actor at Rel(spot) x Anchor, undoing SpawnActor's -90 pitch
composition. Any later materialize re-applies the bug until the C++ fix is built."""
import json, os, re, unreal
def rot(r): return [round(r.pitch,2), round(r.yaw,2), round(r.roll,2)]
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
assert show, "Show did not load (PIE?)"
# index materialized light actors by their attachment tag (cue|attachment guids)
by_tag = {}
for a in sub.get_all_level_actors():
    if not isinstance(a, unreal.Light): continue
    for t in a.get_editor_property("tags"):
        s = str(t)
        if s.startswith("InfinityStage.Attachment."): by_tag[s[len("InfinityStage.Attachment."):]] = a
fixed = 0; rows_ok = 0; rows_skipped = []; row1 = {}
for cue in show.get_editor_property("cues"):
    label = str(cue.get_editor_property("label"))
    if not re.match(r"^P\d{2} Wing \d{3}$", label): continue
    cue_guid = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
    atts = [a for a in cue.get_editor_property("wing_pair").get_editor_property("attachments") if a.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT]
    anchor = None
    for att in atts:   # anchor from a rect (its CDO has no rotation, so it round-trips)
        if att.get_editor_property("lighting").get_editor_property("type") != unreal.InfinityStageLightType.RECT or not att.get_editor_property("enabled"): continue
        actor = by_tag.get(cue_guid + "|" + unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid")))
        if actor:
            anchor = unreal.MathLibrary.compose_transforms(unreal.MathLibrary.invert_transform(att.get_editor_property("relative_transform")), actor.get_actor_transform()); break
    if anchor is None:
        rows_skipped.append(label); continue
    for att in atts:
        if att.get_editor_property("lighting").get_editor_property("type") != unreal.InfinityStageLightType.SPOT or not att.get_editor_property("enabled"): continue
        actor = by_tag.get(cue_guid + "|" + unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid")))
        if not actor: continue
        world = unreal.MathLibrary.compose_transforms(att.get_editor_property("relative_transform"), anchor)
        actor.set_actor_transform(world, False, False); fixed += 1
        if label == "P01 Wing 001":
            row1[str(att.get_editor_property("label"))[13:]] = {"rel": rot(att.get_editor_property("relative_transform").rotation.rotator()), "actor_now": rot(actor.get_actor_rotation())}
    rows_ok += 1
match = sum(1 for v in row1.values() if all(abs(v["rel"][j] - v["actor_now"][j]) < 0.05 for j in range(3)))
unreal.log(f"SPOT_DISPLAY_FIXED_SESSION|spots_replaced={fixed}|rows={rows_ok}|rows_skipped={len(rows_skipped)}|row1_spot_rot_equals_rel={match}/{len(row1)}|saved=0")
