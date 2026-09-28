"""Read-only, independent of the warmer apply's own checks: the saved Show and the
live Passage 01 hold the two house spots as designed (settings, live position and
aim), 96 floats (78 + the 18 behind the curtain's new line), the old Opening
Light disabled with no live actor, unique GUIDs, and a current Structure 01.
Mutates nothing.
"""
import json
import math
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
P01 = re.compile(r"^P01 Wing \d{3}$")
HOUSE = {"House L": ((-2100.0, -650.0, 1265.0), (0.0, 195.0, 450.0)),
         "House R": ((-2100.0, 650.0, 1265.0), (0.0, -195.0, 450.0))}

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
problems = []
guids = set()
house = {}
floats = []
opening = []
for cue in show.get_editor_property("cues"):
    label = str(cue.get_editor_property("label"))
    if not P01.match(label):
        continue
    for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
        g = unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid"))
        if g in guids or set(g) <= {"0"}:
            problems.append(f"bad or duplicate GUID {g}")
        guids.add(g)
        slot = str(att.get_editor_property("label"))[len(label) + 1:]
        L = att.get_editor_property("lighting")
        if slot in HOUSE:
            house[slot] = {"guid": g, "cue": label, "intensity": round(L.get_editor_property("intensity"), 1),
                           "cone": [round(L.get_editor_property("inner_cone_angle_degrees"), 1),
                                    round(L.get_editor_property("outer_cone_angle_degrees"), 1)],
                           "kelvin": round(L.get_editor_property("temperature_kelvin")),
                           "shadows": bool(L.get_editor_property("cast_shadows")),
                           "enabled": bool(att.get_editor_property("enabled"))}
        elif slot in ("Float L", "Float R"):
            floats.append(g)
        elif slot == "Opening Light":
            opening.append({"guid": g, "enabled": bool(att.get_editor_property("enabled"))})

if sorted(house) != sorted(HOUSE):
    problems.append(f"house spots found: {sorted(house)}")
for slot, rec in house.items():
    if rec["intensity"] != 1740.0 or rec["cone"] != [20.0, 33.0] or rec["kelvin"] != 2800 or not rec["shadows"] or not rec["enabled"]:
        problems.append(f"{slot} settings off: {rec}")
if len(floats) != 96:
    problems.append(f"{len(floats)} floats, expected 96")
if len(opening) != 1 or opening[0]["enabled"]:
    problems.append(f"Opening Light not disabled: {opening}")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
live = {}
for actor in passage.get_editor_property("managed_attachment_actors"):
    if actor:
        tag = next((str(t) for t in actor.get_editor_property("tags") if str(t).startswith("InfinityStage.Attachment.")), None)
        if tag:
            live[tag.split("|")[-1]] = actor
spot_live = {}
for slot, (loc, aim) in HOUSE.items():
    rec = house.get(slot)
    actor = live.get(rec["guid"]) if rec else None
    if not actor:
        problems.append(f"no live actor for {slot}")
        continue
    l = actor.get_actor_location()
    f = actor.get_actor_forward_vector()
    want = unreal.Vector(aim[0] - loc[0], aim[1] - loc[1], aim[2] - loc[2])
    want = want / want.length()
    err_cm = (l - unreal.Vector(*loc)).length()
    err_deg = math.degrees(math.acos(max(-1.0, min(1.0, f.dot(want)))))
    spot_live[slot] = {"position_error_cm": round(err_cm, 2), "aim_error_deg": round(err_deg, 3)}
    if err_cm > 1.0 or err_deg > 0.1:
        problems.append(f"{slot} live pose off: {spot_live[slot]}")
if opening and opening[0]["guid"] in live:
    problems.append("the disabled Opening Light still has a live actor")

current = [a.is_structure_current() for a in sub.get_all_level_actors()
           if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage]
if current != [True]:
    problems.append(f"Structure 01 current: {current}")
c = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
report = {"house": house, "spot_live": spot_live, "floats": len(floats), "opening": opening,
          "p01_lights": len(guids), "structure_current": current, "problems": problems, "dirty": {"content": c, "maps": m}}
json.dump(report, open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                    "CodexStructure", "verify_p01_warmer.json"), "w"), indent=1)
unreal.log(f"P01_WARMER_VERIFY_{'OK' if not problems else 'PROBLEMS'}|house={len(house)}|floats={len(floats)}"
           f"|opening_disabled={bool(opening) and not opening[0]['enabled']}|spots={spot_live}|p01_lights={len(guids)}"
           f"|problems={len(problems)}|dirty={len(c)}+{len(m)}|mutated=0")
