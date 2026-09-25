"""Write the beam/haze scattering into the Show's light attachments so it survives
materialize, then rematerialize and verify against the live actors. No save."""
import json, os, re, unreal
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
BASE_SCATTER = float(os.environ.get("PUSS_SCATTER_BASE", "0.6"))
BEAM_SCATTER = float(os.environ.get("PUSS_SCATTER_BEAM", "9.0"))
BEAM_EVERY   = int(os.environ.get("PUSS_BEAM_EVERY", "4"))
BEAM_SLOTS   = {"Cross +Y", "Cross -Y"}
LABEL = re.compile(r"^P(?P<p>\d{2}) Wing (?P<o>\d{3})$")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = ed.get_editor_world(); assert w and w.get_path_name().split(".",1)[0] == EXPECTED_WORLD, "wrong project"
assert ed.get_game_world() is None, "PIE active - stop PIE first"
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH); assert show, "Show did not load"
show.modify()
cues = list(show.get_editor_property("cues"))
beams = base = 0
for i, cue in enumerate(cues):
    m = LABEL.match(str(cue.get_editor_property("label")))
    if not m: continue
    ordinal = int(m.group("o")); prefix = str(cue.get_editor_property("label")) + " "
    pair = cue.get_editor_property("wing_pair"); atts = list(pair.get_editor_property("attachments"))
    changed = False
    for k, att in enumerate(atts):
        if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT: continue
        slot = str(att.get_editor_property("label"))[len(prefix):]
        is_beam = (ordinal % BEAM_EVERY == 1) and (slot in BEAM_SLOTS)
        L = att.get_editor_property("lighting")
        L.set_editor_property("volumetric_scattering_intensity", BEAM_SCATTER if is_beam else BASE_SCATTER)
        L.set_editor_property("cast_volumetric_shadow", bool(is_beam))
        att.set_editor_property("lighting", L); atts[k] = att; changed = True
        beams += int(is_beam); base += int(not is_beam)
    if changed:
        pair.set_editor_property("attachments", atts); cue.set_editor_property("wing_pair", pair); cues[i] = cue
show.set_editor_property("cues", cues)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); mat = {}
for a in sub.get_all_level_actors():
    if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_editor_property("show_asset") == show:
        assert a.materialize_passage(), a.get_actor_label()
        mat[a.get_actor_label()[:10]] = int(a.get_editor_property("materialized_wing_pair_count"))
# verify from the freshly materialized actors
ROW = re.compile(r"^P(\d{2}) Wing (\d{3}) (.+)$")
vb = vbase = 0
for a in sub.get_all_level_actors():
    mm = ROW.match(a.get_actor_label())
    if not mm or not isinstance(a, unreal.Light): continue
    lc = a.get_component_by_class(unreal.LightComponent)
    if not lc: continue
    s = float(lc.get_editor_property("volumetric_scattering_intensity"))
    if abs(s - BEAM_SCATTER) < 0.01: vb += 1
    elif abs(s - BASE_SCATTER) < 0.01: vbase += 1
d = {"content": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
     "maps": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
json.dump({"show_beams": beams, "show_base": base, "verified_beams": vb, "verified_base": vbase, "materialized": mat, "dirty": d},
          open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "persist_beams.json"), "w"), indent=1)
unreal.log(f"BEAMS_PERSISTED|show_beams={beams}|show_base={base}|verified_beams={vb}|verified_base={vbase}|materialized={mat}|dirty={len(d['content'])}+{len(d['maps'])}|saved=0")
