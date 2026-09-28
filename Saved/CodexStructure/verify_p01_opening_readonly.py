"""Read-only, independent of the apply's own checks: read the saved Show and the
live Passage 01 back and confirm the opening light and floats landed as designed.
Mutates nothing.
"""
import json
import math
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LABEL = re.compile(r"^P01 Wing \d{3}$")
EXPECT_LAMP = unreal.Vector(-300.0, -125.0, 650.0)
EXPECT_AIM = unreal.Vector(5400.0, -125.0, 250.0)

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
problems = []
opening = []
floats = []
existing = 0
for cue in show.get_editor_property("cues"):
    label = str(cue.get_editor_property("label"))
    if not LABEL.match(label):
        continue
    for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
        slot = str(att.get_editor_property("label"))[len(label) + 1:]
        L = att.get_editor_property("lighting")
        d = L.get_editor_property("drama")
        rec = {"cue": label, "slot": slot, "enabled": bool(att.get_editor_property("enabled")),
               "intensity": round(L.get_editor_property("intensity"), 2),
               "kelvin": round(L.get_editor_property("temperature_kelvin")),
               "cone": [round(L.get_editor_property("inner_cone_angle_degrees"), 2),
                        round(L.get_editor_property("outer_cone_angle_degrees"), 2)],
               "radius": round(L.get_editor_property("attenuation_radius_cm")),
               "shadows": bool(L.get_editor_property("cast_shadows")),
               "vol_shadow": bool(L.get_editor_property("cast_volumetric_shadow")),
               "light_function": bool(L.get_editor_property("light_function_material")),
               "drama": bool(d.get_editor_property("strike_on_approach") or d.get_editor_property("slow_move")),
               "guid": unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid"))}
        if slot == "Opening Light":
            opening.append(rec)
        elif slot in ("Float L", "Float R"):
            floats.append(rec)
        else:
            existing += 1

if len(opening) != 1:
    problems.append(f"{len(opening)} opening lights")
else:
    o = opening[0]
    want = {"intensity": 19600.0, "kelvin": 2800, "cone": [2.4, 4.0], "shadows": True, "vol_shadow": False,
            "light_function": False, "drama": False, "enabled": True}
    for k, v in want.items():
        if o[k] != v:
            problems.append(f"opening light {k}={o[k]}, expected {v}")
if len(floats) != 78:
    problems.append(f"{len(floats)} floats, expected 78")
if sum(1 for f in floats if not f["enabled"]) != 5:
    problems.append("expected 5 dark floats")
if any(f["shadows"] or f["drama"] or f["radius"] != 350 for f in floats):
    problems.append("a float casts shadows, has drama or the wrong radius")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
live = {}
for actor in passage.get_editor_property("managed_attachment_actors"):
    if not actor:
        continue
    tag = next((str(t) for t in actor.get_editor_property("tags") if str(t).startswith("InfinityStage.Attachment.")), None)
    if tag:
        live[tag.split("|")[-1]] = actor
lamp_live = {}
if opening and opening[0]["guid"] in live:
    a = live[opening[0]["guid"]]
    loc = a.get_actor_location()
    fwd = a.get_actor_forward_vector()
    want_dir = (EXPECT_AIM - EXPECT_LAMP)
    want_dir = want_dir / want_dir.length()
    angle = math.degrees(math.acos(max(-1.0, min(1.0, fwd.dot(want_dir)))))
    lamp_live = {"location": [round(loc.x, 1), round(loc.y, 1), round(loc.z, 1)],
                 "position_error_cm": round((loc - EXPECT_LAMP).length(), 2), "aim_error_deg": round(angle, 3)}
    if lamp_live["position_error_cm"] > 1.0 or angle > 0.1:
        problems.append(f"live opening lamp off: {lamp_live}")
else:
    problems.append("no live actor for the opening light")
live_floats = sum(1 for f in floats if f["enabled"] and f["guid"] in live)
if live_floats != 73:
    problems.append(f"{live_floats} live floats, expected 73")

structure_current = None
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        structure_current = bool(a.is_structure_current())
if not structure_current:
    problems.append("Structure 01 not current")

c = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
report = {"existing_p01_lights": existing, "opening": opening, "lamp_live": lamp_live,
          "floats": len(floats), "floats_dark": sum(1 for f in floats if not f["enabled"]), "live_floats": live_floats,
          "structure_current": structure_current, "problems": problems, "dirty": {"content": c, "maps": m}}
json.dump(report, open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                    "CodexStructure", "verify_p01_opening.json"), "w"), indent=1)
unreal.log(f"P01_OPENING_VERIFY_{'OK' if not problems else 'PROBLEMS'}|existing={existing}|opening={len(opening)}"
           f"|floats={len(floats)}|live_floats={live_floats}|lamp={lamp_live}|problems={len(problems)}"
           f"|dirty={len(c)}+{len(m)}|mutated=0")
