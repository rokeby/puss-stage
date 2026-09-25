"""No-save: set MaxDrawDistance/fade to 0 (unlimited) on every Light attachment in the Show; transforms untouched.
Rematerializes all Passages and verifies P01 row 1 actors still match the Show."""
import re, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); assert ed.get_game_world() is None, "PIE active"
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"); show.modify()
cues = list(show.get_editor_property("cues")); n = 0
for i, cue in enumerate(cues):
    if not re.match(r"^P\d{2} Wing \d{3}$", str(cue.get_editor_property("label"))): continue
    pair = cue.get_editor_property("wing_pair"); atts = list(pair.get_editor_property("attachments")); changed = False
    for k, att in enumerate(atts):
        if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT: continue
        L = att.get_editor_property("lighting")
        if L.get_editor_property("max_draw_distance_cm") == 0.0 and L.get_editor_property("max_distance_fade_range_cm") == 0.0: continue
        L.set_editor_property("max_draw_distance_cm", 0.0); L.set_editor_property("max_distance_fade_range_cm", 0.0)
        att.set_editor_property("lighting", L); atts[k] = att; changed = True; n += 1
    if changed:
        pair.set_editor_property("attachments", atts); cue.set_editor_property("wing_pair", pair); cues[i] = cue
show.set_editor_property("cues", cues)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); mat = 0
for a in sub.get_all_level_actors():
    if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_editor_property("show_asset") == show:
        assert a.materialize_passage(), a.get_actor_label(); mat += 1
sample = [a for a in sub.get_all_level_actors() if isinstance(a, unreal.Light) and a.get_actor_label().startswith("P01 Wing 001 Cross")]
dd = [float(a.get_component_by_class(unreal.LightComponent).get_editor_property("max_draw_distance")) for a in sample]
unreal.log(f"LIGHT_CULL_CLEARED|attachments_changed={n}|passages_materialized={mat}|sample_actor_max_draw={dd}|saved=0")
