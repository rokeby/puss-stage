"""Read-only, independent of the lip-float apply's own checks: the saved Show and
the live Passage 01 hold the planned lip floats (settings, enabled state, live
position and aim), every P01 light has a unique GUID, the portal is on, and every
structure is current. Mutates nothing.
"""
import json
import math
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
P01 = re.compile(r"^P01 Wing \d{3}$")

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
plan = json.load(open(os.path.join(HERE, "p01_lip_floats_plan.json"), encoding="utf-8"))
planned = {f"{bay['cue']} {row['slot']}": row for bay in plan["plan"] for row in bay["lights"]}
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
problems = []
guids = set()
found = {}
for cue in show.get_editor_property("cues"):
    label = str(cue.get_editor_property("label"))
    if not P01.match(label):
        continue
    for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
        g = unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid"))
        if g in guids or set(g) <= {"0"}:
            problems.append(f"bad or duplicate GUID {g}")
        guids.add(g)
        name = str(att.get_editor_property("label"))
        if " Lip " not in name:
            continue
        L = att.get_editor_property("lighting")
        found[name] = {"guid": g, "enabled": bool(att.get_editor_property("enabled")),
                       "intensity": round(L.get_editor_property("intensity"), 2),
                       "cone": [round(L.get_editor_property("inner_cone_angle_degrees"), 1),
                                round(L.get_editor_property("outer_cone_angle_degrees"), 1)],
                       "kelvin": round(L.get_editor_property("temperature_kelvin")),
                       "radius": round(L.get_editor_property("attenuation_radius_cm"), 1),
                       "shadows": bool(L.get_editor_property("cast_shadows"))}
if sorted(found) != sorted(planned):
    problems.append(f"lip floats found {len(found)}, planned {len(planned)}")
for name, rec in found.items():
    row = planned.get(name)
    if not row:
        continue
    want = {"enabled": row["enabled"], "intensity": round(row["intensity_cd"], 2),
            "cone": [row["inner"], row["outer"]], "kelvin": row["kelvin"], "radius": row["radius_cm"],
            "shadows": row["cast_shadows"]}
    got = {k: rec[k] for k in want}
    if got != want:
        problems.append(f"{name} settings off: {got} vs {want}")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
live = {}
for actor in passage.get_editor_property("managed_attachment_actors"):
    if actor:
        tag = next((str(t) for t in actor.get_editor_property("tags") if str(t).startswith("InfinityStage.Attachment.")), None)
        if tag:
            live[tag.split("|")[-1]] = actor
worst = {"cm": 0.0, "deg": 0.0}
lit_live = 0
for name, rec in found.items():
    row = planned.get(name)
    actor = live.get(rec["guid"])
    if not rec["enabled"]:
        if actor:
            problems.append(f"{name} is dark but has a live actor")
        continue
    if not actor or not row:
        problems.append(f"no live actor for {name}")
        continue
    lit_live += 1
    loc = unreal.Vector(*row["world"])
    err_cm = (actor.get_actor_location() - loc).length()
    f = actor.get_actor_forward_vector()
    # The planned throw, in world: the plan's upstage direction pitched up.
    fx, fy = plan["forward"]
    pitch = math.radians(plan["pitch"])
    want = unreal.Vector(math.cos(pitch) * fx, math.cos(pitch) * fy, math.sin(pitch))
    err_deg = math.degrees(math.acos(max(-1.0, min(1.0, f.dot(want)))))
    worst = {"cm": max(worst["cm"], round(err_cm, 2)), "deg": max(worst["deg"], round(err_deg, 3))}
    if err_cm > 1.0 or err_deg > 0.1:
        problems.append(f"{name} live pose off: {err_cm:.2f} cm, {err_deg:.3f} deg")

structures = [a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStageStructureActor)]
current = {a.get_actor_label(): bool(a.is_structure_current()) for a in structures}
if not all(current.values()):
    problems.append(f"structures not current: {current}")
ours = [a for a in structures if a.get_editor_property("passage") == passage]
if len(ours) != 1 or not ours[0].get_editor_property("portal").get_editor_property("enabled"):
    problems.append("Structure 01's portal is not on")
c = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
report = {"found": found, "worst_pose_error": worst, "lit_live": lit_live, "p01_lights": len(guids),
          "structures_current": current, "problems": problems, "dirty": {"content": c, "maps": m}}
json.dump(report, open(os.path.join(HERE, "verify_p01_lip_floats.json"), "w"), indent=1)
unreal.log(f"P01_LIP_FLOATS_VERIFY_{'OK' if not problems else 'PROBLEMS'}|lips={len(found)}|lit_live={lit_live}"
           f"|worst={worst}|p01_lights={len(guids)}|problems={len(problems)}|dirty={len(c)}+{len(m)}|mutated=0")
