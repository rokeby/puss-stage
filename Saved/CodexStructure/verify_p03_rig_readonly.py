"""Read-only, independent of p03_rig_apply.py's own checks: read the saved Show
and the live Passage 03 back and confirm the rig and fill landed as designed.

Show side: per-pair light counts, rig slots, every non-rig light one of the
revert record's pre-existing GUIDs and now shadowless, rig lamps shadowed, drama
states, unique valid GUIDs. Colour is not re-checked here (the record does not
hold it); the apply keeps it by construction and its own full-field fingerprint
comparison, which includes colour, verified it before saving. Level side: one live light actor per enabled light,
its component intensity equal to the Show's authored value (drama is PIE-only,
so the editor must show authored values), and Structure 03 current. Mutates
nothing.
"""
import collections
import json
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
LABEL = re.compile(r"^P03 Wing \d{3}$")

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
record = json.load(open(os.path.join(HERE, "p03_rig_revert_record.json"), encoding="utf-8"))
existing_guids = {row["guid"] for c in record["cues"] for row in c["lights"]}
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)

problems = []
slots = collections.Counter()
drama = collections.Counter()
guids = set()
authored = {}
enabled_lights = 0
for cue in show.get_editor_property("cues"):
    label = str(cue.get_editor_property("label"))
    if not LABEL.match(label):
        continue
    for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
        g = unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid"))
        if g in guids or set(g) <= {"0"}:
            problems.append(f"bad or duplicate guid {g} on {label}")
        guids.add(g)
        L = att.get_editor_property("lighting")
        name = str(att.get_editor_property("label"))
        is_rig = name.startswith(f"{label} Rig ")
        slots["rig " + name[len(label) + 5:] if is_rig else "existing"] += 1
        shadows = bool(L.get_editor_property("cast_shadows"))
        if is_rig and not shadows:
            problems.append(f"rig lamp without shadow: {name}")
        if not is_rig and att.get_editor_property("enabled") and shadows:
            problems.append(f"fill light still shadowed: {name}")
        if not is_rig and g not in existing_guids:
            problems.append(f"unknown non-rig light {name}")
        d = L.get_editor_property("drama")
        drama[("strike" if d.get_editor_property("strike_on_approach") else "")
              + ("sweep" if d.get_editor_property("slow_move") else "") or "steady"] += 1
        if att.get_editor_property("enabled"):
            enabled_lights += 1
            authored[g] = float(L.get_editor_property("intensity"))

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 03"))
live = 0
mismatched = 0
for actor in passage.get_editor_property("managed_attachment_actors"):
    if not actor:
        continue
    tag = next((str(t) for t in actor.get_editor_property("tags") if str(t).startswith("InfinityStage.Attachment.")), None)
    lc = actor.get_component_by_class(unreal.LightComponent)
    if not tag or not lc:
        continue
    g = tag.split("|")[-1]
    if g in authored:
        live += 1
        if abs(float(lc.get_editor_property("intensity")) - authored[g]) > 1e-3:
            mismatched += 1
if live != enabled_lights:
    problems.append(f"{live} live P03 lights for {enabled_lights} enabled in the Show")
if mismatched:
    problems.append(f"{mismatched} live lights differ from authored intensity")

structure_current = None
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        structure_current = bool(a.is_structure_current())
if not structure_current:
    problems.append("Structure 03 is not current")

c = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
report = {"slots": dict(slots), "drama": dict(drama), "enabled_lights": enabled_lights, "live_lights": live,
          "live_intensity_mismatches": mismatched, "structure_current": structure_current,
          "problems": problems, "dirty": {"content": c, "maps": m}}
json.dump(report, open(os.path.join(HERE, "verify_p03_rig.json"), "w"), indent=1)
unreal.log(f"P03_RIG_VERIFY_{'OK' if not problems else 'PROBLEMS'}|existing={slots['existing']}"
           f"|rig={sum(n for k, n in slots.items() if k.startswith('rig'))}|enabled={enabled_lights}|live={live}"
           f"|mismatch={mismatched}|problems={len(problems)}|dirty={len(c)}+{len(m)}|mutated=0")
