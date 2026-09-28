"""Read-only: plan the curtain warmer for the re-staged opening (Docs/OpeningLight_2026-09-27.md,
"Re-staging 2"): the camera at (-1400, 0, 150) tilted up 14 degrees on 15 mm (Gary's
stalls view), the curtain at x 0. Replaces the lone 4-degree lamp. Mutates nothing.

Previous docstring, kept for the float rules this reuses:
from live P01 geometry, and write it as JSON for the apply step. Mutates nothing.

Opening light: one warm, steady, narrow spot behind the opening camera (which is
at x 0, z 150, facing +X for the whole Opening; Look & camera measured it via
GetPassageCameraPose). It lights the Chaos curtain at x 5400; when the curtain
falls, the same beam runs on down P01's floor. Anchored to P01's first pair by
route order, as a Station offset.

Floats: a shadowless, short-throw warm lamp just inboard of each wing's pivot
line, 60 cm downstream of each station's slot, only at stations beyond
the curtain, fanning inward and forward. About 1 in 12 left dark by a fixed seed.
"""
import json
import math
import os
import random
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL = re.compile(r"^P01 Wing (\d{3})$")
CURTAIN_X = 0.0
EXISTING_FLOATS_FROM_X = 5400.0   # floats past 5400 were authored on 28 Sep

HOUSE = [("House L", unreal.Vector(-2100.0, -650.0, 1265.0), unreal.Vector(0.0, 195.0, 450.0)),
         ("House R", unreal.Vector(-2100.0, 650.0, 1265.0), unreal.Vector(0.0, -195.0, 450.0))]
HOUSE_ROW = {"outer": 33.0, "inner": 20.0, "intensity_cd": 1740.0, "kelvin": 2800, "cast_shadows": True,
             "cast_volumetric_shadow": False, "volumetric_scattering": 1.0, "radius_cm": 4500.0, "enabled": True}
DISABLE = ["P01 Wing 001 Opening Light"]

FLOAT_HEIGHT = 25.0
FLOAT_INBOARD = 40.0
FLOAT_DOWNSTREAM = 60.0
FLOAT_YAW_IN = 60.0
FLOAT_PITCH = 5.0
FLOAT = {"outer": 35.0, "inner": 20.0, "kelvin": 2500, "cast_shadows": False, "cast_volumetric_shadow": False,
         "volumetric_scattering": 0.3, "radius_cm": 350.0}
FLOAT_CD = 6.0
FLOAT_JITTER = 0.15
FLOAT_DEAD_CHANCE = 1.0 / 12.0

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
show = passage.get_editor_property("show_asset")


def side_of(ref):
    return str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")


def world_box(ref):
    comp = ref.get_editor_property("component")
    box = comp.get_editor_property("static_mesh").get_bounding_box()
    tf = ref.get_editor_property("base_world_transform")
    pts = [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
           for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
    return ([min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)],
            [max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)])


panels = {}
for ref in passage.get_editor_property("materialized_panels"):
    s = side_of(ref)
    if s in ("LEFT", "RIGHT"):
        # The pivot line, not the bounds: P01's painted wing cards are wide and
        # mostly transparent, so their bounds reach within ~55 cm of the route
        # line and say nothing about where the wing visibly stands.
        panels.setdefault(unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid")), {})[s] =             ref.get_editor_property("base_world_transform").translation

bays = []
for cue in show.get_editor_property("cues"):
    m = LABEL.match(str(cue.get_editor_property("label")))
    if not m:
        continue
    guid = cue.get_editor_property("cue_guid")
    station_lights = [a for a in cue.get_editor_property("wing_pair").get_editor_property("attachments")
                      if "STATION" in str(a.get_editor_property("anchor"))]
    assert station_lights, f"{m.group(0)} has no station attachment to read its pair root from"
    pair_world = passage.get_attachment_anchor_world_transform(guid, station_lights[0].get_editor_property("attachment_guid"))
    assert isinstance(pair_world, unreal.Transform), f"no anchor for {m.group(0)}"
    bays.append({"label": m.group(0), "pair_world": pair_world,
                 "panels": panels.get(unreal.GuidLibrary.conv_guid_to_string(guid), {})})
passage_tf = passage.get_actor_transform()
for bay in bays:
    bay["route_x"] = unreal.MathLibrary.inverse_transform_location(passage_tf, bay["pair_world"].translation).x
bays.sort(key=lambda b: b["route_x"])


def to_local(pair_world, loc_world, rotation_world):
    lamp = unreal.Transform(location=loc_world, rotation=rotation_world)
    rel = unreal.MathLibrary.make_relative_transform(lamp, pair_world)
    r = rel.rotation.rotator()
    return {"loc": [round(rel.translation.x, 1), round(rel.translation.y, 1), round(rel.translation.z, 1)],
            "pitch": round(r.pitch, 3), "yaw": round(r.yaw, 3), "roll": round(r.roll, 3)}


plan = []
# The two house spots, on the first pair by route order, crossing onto the cloth.
first = bays[0]
entries = {first["label"]: []}
for slot, world_loc, aim in HOUSE:
    d = aim - world_loc
    rot = unreal.Rotator(roll=0.0, pitch=math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))),
                         yaw=math.degrees(math.atan2(d.y, d.x)))
    entries[first["label"]].append(dict(HOUSE_ROW, slot=slot, offset=to_local(first["pair_world"], world_loc, rot),
                                        throw_cm=round(d.length()), world=[world_loc.x, world_loc.y, world_loc.z]))

floats = dead = 0
for bay in bays:
    origin = bay["pair_world"].translation
    # Floats burn behind the curtain; the ones past 5400 already exist.
    if origin.x <= CURTAIN_X or origin.x > EXISTING_FLOATS_FROM_X:
        continue
    rng = random.Random(f"P01-float-{bay['label']}")
    for side, sign in (("LEFT", -1.0), ("RIGHT", 1.0)):
        pivot = bay["panels"].get(side)
        if pivot is None:
            continue
        # Just inboard of the wing's line, and 60 cm behind its card, so the card
        # hides the lamp from the approaching camera like a footlight in a trough.
        y = pivot.y - sign * FLOAT_INBOARD
        if abs(y - origin.y) < 300.0:
            raise RuntimeError(f"{bay['label']} {side}: float at {y - origin.y:.0f} cm would stand on the cat's line")
        loc = unreal.Vector(origin.x + FLOAT_DOWNSTREAM, y, origin.z + FLOAT_HEIGHT)
        # Inward (toward the route line) and forward.
        yaw = -sign * FLOAT_YAW_IN
        enabled = rng.random() >= FLOAT_DEAD_CHANCE
        cd = FLOAT_CD * rng.uniform(1.0 - FLOAT_JITTER, 1.0 + FLOAT_JITTER)
        row = dict(FLOAT, slot=f"Float {side[0]}", intensity_cd=round(cd, 2), enabled=enabled,
                   offset=to_local(bay["pair_world"], loc, unreal.Rotator(roll=0.0, pitch=FLOAT_PITCH, yaw=yaw)),
                   throw_cm=0, world=[round(loc.x), round(loc.y), round(loc.z)])
        entries.setdefault(bay["label"], []).append(row)
        floats += 1
        dead += int(not enabled)

for bay in bays:
    if bay["label"] in entries:
        plan.append({"cue": bay["label"], "route_x": round(bay["route_x"]), "lights": entries[bay["label"]]})

report = {"passage": "Passage 01", "camera": [-1400, 0, 150], "camera_pitch": 14.0, "curtain_x": CURTAIN_X,
          "disable_labels": DISABLE,
          "opening_cue": first["label"], "floats": floats, "floats_dark": dead,
          "lamps": sum(len(p["lights"]) for p in plan), "plan": plan}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "p01_warmer_plan.json")
json.dump(report, open(out, "w"), indent=1)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"P01_WARMER_PLAN_OK|house_cue={first['label']}|floats={floats}|dark={dead}|lamps={report['lamps']}"
           f"|dirty={dirty[0]}+{dirty[1]}|mutated=0")
