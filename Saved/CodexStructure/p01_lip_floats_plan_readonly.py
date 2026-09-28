"""Read-only: plan the lip floats for the curtain warmer (Docs/OpeningLight_2026-09-27.md,
"Re-staging 2": "a float trough along the lip, glowing up the cloth"), placed from
the portal's float trough as Structure 01 actually built it. Run after
portal_enable_apply.py; writes p01_lip_floats_plan.json for the apply. Mutates nothing.

Footlights, not corridor floats: a row across the curtain's width, standing just
upstage of the trough so it masks their feet from the stalls, thrown up the cloth.
Shadowless (P01 already overflows VSM; the house spots carry the shadows), warm
(2500 K, under the 2800 K house spots), steady, no drama. The curtain falls
upstage, so after the fall the same row lights the heap on the threshold.

Each lamp's housing (the structure pass gives every station lamp one, 45 x 32 x 32 cm,
behind its source) sits partly in the trough and shows its head above it, like
lamps nested in a float trough. The report gives how far; it is Gary's to judge
in the capture.
"""
import json
import math
import os
import random
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL = re.compile(r"^P01 Wing (\d{3})$")
PORTAL_TAG = "InfinityStage.Structure.Portal"

LIP_COUNT = 16
LIP_HALF_SPAN = 825.0        # inside the curtain's 888 cm half-width, well inside the posts
BEHIND_TROUGH = 15.0         # source this far upstage of the trough's back face
SOURCE_HEIGHT = 30.0         # above the floor; the trough is 25 cm
PITCH = 40.0                 # up the cloth: centre ray meets it about 1.1 m up
CURTAIN_CLEARANCE = 60.0     # pleats swing about the line; keep sources clear of them
LIP = {"outer": 40.0, "inner": 20.0, "kelvin": 2500, "cast_shadows": False, "cast_volumetric_shadow": False,
       "volumetric_scattering": 0.3, "radius_cm": 600.0}
LIP_CD = 8.0                 # about 4 lux per lamp at the hem, 8 where neighbours overlap; the house spots give ~6
LIP_JITTER = 0.15
LIP_DEAD_CHANCE = 1.0 / 12.0  # the float rule's wear, by a fixed seed per lamp
HOUSING = (45.0, 32.0, 32.0)  # FInfinityStageFixtureSettings::BodySizeCm default, for the report only

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
structure = [a for a in sub.get_all_level_actors()
             if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage]
assert len(structure) == 1, f"expected one structure on Passage 01, found {len(structure)}"
structure = structure[0]
portal = structure.get_editor_property("portal")
assert portal.get_editor_property("enabled"), "the portal is off: run portal_enable_apply.py first"
assert structure.is_structure_current(), "Structure 01 is not current"
show = passage.get_editor_property("show_asset")

# ---- The first bay by route order: the anchor, and the direction upstage -------
bays = []
for cue in show.get_editor_property("cues"):
    m = LABEL.match(str(cue.get_editor_property("label")))
    if not m:
        continue
    station_lights = [a for a in cue.get_editor_property("wing_pair").get_editor_property("attachments")
                      if "STATION" in str(a.get_editor_property("anchor"))]
    assert station_lights, f"{m.group(0)} has no station attachment to read its pair root from"
    pair_world = passage.get_attachment_anchor_world_transform(cue.get_editor_property("cue_guid"),
                                                               station_lights[0].get_editor_property("attachment_guid"))
    assert isinstance(pair_world, unreal.Transform), f"no anchor for {m.group(0)}"
    bays.append({"label": m.group(0), "pair_world": pair_world})
passage_tf = passage.get_actor_transform()
for bay in bays:
    bay["route_x"] = unreal.MathLibrary.inverse_transform_location(passage_tf, bay["pair_world"].translation).x
bays.sort(key=lambda b: b["route_x"])
first = bays[0]
existing = {str(a.get_editor_property("label")) for cue in show.get_editor_property("cues")
            if str(cue.get_editor_property("label")) == first["label"]
            for a in cue.get_editor_property("wing_pair").get_editor_property("attachments")}
assert not any(" Lip " in name for name in existing), "lip floats already authored"


# ---- The portal as built: world boxes of its timber instances -----------------
def world_boxes(component):
    box = component.get_editor_property("static_mesh").get_bounding_box()
    out = []
    for i in range(component.get_instance_count()):
        tf = component.get_instance_transform(i, True)
        pts = [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
               for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
        out.append(pts)
    return out


pieces = []
for comp in structure.get_editor_property("managed_components"):
    if comp and PORTAL_TAG in [str(t) for t in comp.get_editor_property("component_tags")]:
        pieces.extend(world_boxes(comp))
assert pieces, "no portal instances found"
trough_h = portal.get_editor_property("trough_height_cm")


def zspan(pts):
    return min(p.z for p in pts), max(p.z for p in pts)


def centre(pts):
    n = float(len(pts))
    return unreal.Vector(sum(p.x for p in pts) / n, sum(p.y for p in pts) / n, sum(p.z for p in pts) / n)


def xyspan(pts):
    return math.hypot(max(p.x for p in pts) - min(p.x for p in pts), max(p.y for p in pts) - min(p.y for p in pts))


# The trough is the one long, low timber; the posts the two tall, slim ones. The
# floor is read from the trough's underside (it sits on the boards), and the posts
# must stand on the same floor, which checks the reading.
troughs = [p for p in pieces if abs(zspan(p)[1] - zspan(p)[0] - trough_h) < 3.0 and xyspan(p) > 1000.0]
assert len(troughs) == 1, f"expected one trough, found {len(troughs)}"
trough = troughs[0]
floor_z = zspan(trough)[0]
posts = [p for p in pieces if zspan(p)[1] - zspan(p)[0] > 1000.0 and xyspan(p) < 200.0]
assert len(posts) == 2, f"expected two posts, found {len(posts)}"
assert all(abs(zspan(p)[0] - floor_z) < 3.0 for p in posts), "posts and trough disagree about the floor"
tc = centre(trough)
# Upstage: from the trough toward the first station, level.
d = first["pair_world"].translation - tc
forward = unreal.Vector(d.x, d.y, 0.0)
forward = forward / forward.length()
across = unreal.Vector(-forward.y, forward.x, 0.0)
up = unreal.Vector(0.0, 0.0, 1.0)


def along(p):
    return (p - tc).dot(forward)


trough_back = max(along(p) for p in trough)
portal_line = sum(along(centre(p)) for p in posts) / 2.0
post_lateral = sorted((centre(p) - tc).dot(across) for p in posts)
source_along = trough_back + BEHIND_TROUGH
clearance = portal_line - source_along
assert clearance >= CURTAIN_CLEARANCE, f"sources {clearance:.0f} cm from the curtain line, need {CURTAIN_CLEARANCE}"
assert LIP_HALF_SPAN < min(abs(v) for v in post_lateral) - 50.0, "lip row reaches the posts"

yaw = math.degrees(math.atan2(forward.y, forward.x))
rotation = unreal.Rotator(roll=0.0, pitch=PITCH, yaw=yaw)


def to_local(pair_world, loc_world):
    rel = unreal.MathLibrary.make_relative_transform(unreal.Transform(location=loc_world, rotation=rotation), pair_world)
    r = rel.rotation.rotator()
    return {"loc": [round(rel.translation.x, 1), round(rel.translation.y, 1), round(rel.translation.z, 1)],
            "pitch": round(r.pitch, 3), "yaw": round(r.yaw, 3), "roll": round(r.roll, 3)}


rows = []
dead = 0
throw = unreal.Vector(math.cos(math.radians(PITCH)) * forward.x, math.cos(math.radians(PITCH)) * forward.y,
                      math.sin(math.radians(PITCH)))
for i in range(LIP_COUNT):
    lateral = -LIP_HALF_SPAN + i * (2.0 * LIP_HALF_SPAN / (LIP_COUNT - 1))
    loc = tc + forward * source_along + across * lateral
    loc = unreal.Vector(loc.x, loc.y, floor_z + SOURCE_HEIGHT)
    rng = random.Random(f"P01-lip-float-{i:02d}")
    enabled = rng.random() >= LIP_DEAD_CHANCE
    dead += int(not enabled)
    cd = LIP_CD * rng.uniform(1.0 - LIP_JITTER, 1.0 + LIP_JITTER)
    rows.append(dict(LIP, slot=f"Lip {i + 1:02d}", intensity_cd=round(cd, 2), enabled=enabled,
                     offset=to_local(first["pair_world"], loc), throw_cm=0,
                     world=[round(loc.x, 1), round(loc.y, 1), round(loc.z, 1)]))

# The housing the structure pass will hang on each (report only: its box behind the source).
s, c = math.sin(math.radians(PITCH)), math.cos(math.radians(PITCH))
housing_centre_z = SOURCE_HEIGHT - throw.z * HOUSING[0] * 0.5
housing_half_z = HOUSING[0] * 0.5 * s + HOUSING[2] * 0.5 * c
report = {"passage": "Passage 01", "anchor_cue": first["label"], "structure": structure.get_actor_label(),
          "floor_z": round(floor_z, 1), "trough_centre": [round(tc.x, 1), round(tc.y, 1), round(tc.z, 1)],
          "forward": [round(forward.x, 4), round(forward.y, 4)], "pitch": PITCH, "trough_back_along": round(trough_back, 1),
          "portal_line_along": round(portal_line, 1), "post_lateral": [round(v, 1) for v in post_lateral],
          "source_to_curtain_cm": round(clearance, 1),
          "cloth_hit": {"centre_ray_z": round(SOURCE_HEIGHT + clearance * math.tan(math.radians(PITCH)), 1),
                        "upper_edge_z": round(SOURCE_HEIGHT + clearance * math.tan(math.radians(min(89.0, PITCH + LIP["outer"]))), 1)},
          "housing": {"top_above_floor": round(housing_centre_z + housing_half_z, 1),
                      "top_above_trough": round(housing_centre_z + housing_half_z - trough_h, 1),
                      "bottom_above_floor": round(housing_centre_z - housing_half_z, 1)},
          "lamps": LIP_COUNT, "dark": dead,
          "plan": [{"cue": first["label"], "route_x": round(first["route_x"]), "lights": rows}]}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "p01_lip_floats_plan.json")
json.dump(report, open(out, "w"), indent=1)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"P01_LIP_FLOATS_PLAN_OK|anchor={first['label']}|lamps={LIP_COUNT}|dark={dead}"
           f"|to_curtain_cm={clearance:.0f}|housing_above_trough={report['housing']['top_above_trough']}"
           f"|dirty={dirty[0]}+{dirty[1]}|mutated=0")
