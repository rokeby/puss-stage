"""Read-only: plan the P03 upper rig and write it as JSON for review. Mutates nothing.

Gary: theatre lighting should come from an upper rig that lights PARTS of the
wings. So every bay hangs lamps under its cross beam and throws them forward
and down onto the next pair's faces, the faces the camera sees on approach:

  Rig L / Rig R  a pool on the near wing, inboard of the corridor edge
  Rig Slash      bays without a back-light, alternating sides, a grazing
                 cross-shot that stretches into a slash across the far wing
  Rig Back       thrown BACK toward the approaching camera and down to the
                 floor about 2.5 bays upstream, crossing eye height ~2 bays
                 back. Placed by the PATH, not by rhythm: a bay gets one when
                 the stretch its shaft crosses is dark, so the shafts come in
                 crossing pairs out of each dark trough. Forward-scattering haze
                 (g=0.55) only shows a shaft to a viewer the light travels
                 toward; the conductor's 4-state capture A/B (25 Sep) proved the
                 forward-thrown rig showed none and the fog only cost light.

Targets, cone and intensity vary per bay from a stream seeded on the cue's
ordinal, and some bays leave one wing dark, so the pools fall irregularly
rather than as an even wash. Everything is expressed as a Station-anchored
offset on the bay the lamp hangs from, so re-spacing carries the rig along.
"""
import json
import math
import os
import random
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PASSAGE = "Passage 03"
PREFIX = "P03"
LABEL = re.compile(r"^P03 Wing (\d{3})$")

GRID_HEIGHT = 1150.0      # cross-beam centre, matches the structure pass default
BEAM_DEPTH = 34.0
HANG_DROP = 55.0          # yoke drop from the beam underside to the lamp
INBOARD = 150.0           # lamps hang this far inside the corridor edge
DOWNSTREAM = 25.0         # pools hang on the throw side of the cross beam
UPSTREAM = -40.0          # slashes hang on the other face, clear of the pool lamps
POOL_OUTER_DEG = (9.0, 14.0)
SLASH_OUTER_DEG = (6.0, 9.0)
POOL_CD = 140.0
SLASH_CD = 190.0
BACK_OUTER_DEG = (10.0, 14.0)
BACK_CD = 90.0
BACK_PITCH_DEG = 40.0     # down from horizontal; shallower reads as more shaft
BACK_SCATTER = 4.0
DARK_WING_CHANCE = 0.18
# The path (Gary, 26 Sep: "attention to lighting path and wings"): the existing
# lights become fill shaped by a slow envelope along the route. This plan owns
# the envelope; p03_rig_apply.py reads it from here, so the two cannot disagree.
PATH_PERIOD_BAYS = 5.5
PATH_FLOOR = 0.35
BACK_WHEN_ENVELOPE_BELOW = 0.55
BACK_SHAFT_REACH_BAYS = 2


def envelope(route_index):
    phase = random.Random("P03-path").uniform(0.0, 2.0 * math.pi)
    return PATH_FLOOR + (1.0 - PATH_FLOOR) * (
        0.5 + 0.5 * math.cos(2.0 * math.pi * route_index / PATH_PERIOD_BAYS + phase))

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith(PASSAGE))
show = passage.get_editor_property("show_asset")


def side_of(ref):
    return str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")


def world_box(ref):
    comp = ref.get_editor_property("component")
    box = comp.get_editor_property("static_mesh").get_bounding_box()
    tf = ref.get_editor_property("base_world_transform")
    corners = [unreal.Vector(x, y, z) for x in (box.min.x, box.max.x)
               for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
    pts = [unreal.MathLibrary.transform_location(tf, c) for c in corners]
    return ([min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)],
            [max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)])


panels = {}
for ref in passage.get_editor_property("materialized_panels"):
    s = side_of(ref)
    if s in ("LEFT", "RIGHT"):
        panels.setdefault(unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid")), {})[s] = world_box(ref)

bays = []
for cue in show.get_editor_property("cues"):
    m = LABEL.match(str(cue.get_editor_property("label")))
    if not m:
        continue
    guid = cue.get_editor_property("cue_guid")
    lights = [a for a in cue.get_editor_property("wing_pair").get_editor_property("attachments")
              if str(a.get_editor_property("anchor")).find("STATION") >= 0]
    assert lights, f"{m.group(0)} has no station-anchored attachment to read its pair root from"
    # Python hands back the out-transform alone; a failed lookup returns None.
    pair_world = passage.get_attachment_anchor_world_transform(guid, lights[0].get_editor_property("attachment_guid"))
    assert isinstance(pair_world, unreal.Transform), f"no anchor for {m.group(0)}"
    bays.append({"ordinal": int(m.group(1)), "label": m.group(0),
                 "pair_world": pair_world, "panels": panels.get(unreal.GuidLibrary.conv_guid_to_string(guid), {})})
# Route order, not label order: P03's labels do not run monotonically down the
# route, and a lamp must throw at the pair the camera meets next.
passage_tf = passage.get_actor_transform()
for bay in bays:
    bay["route_x"] = unreal.MathLibrary.inverse_transform_location(passage_tf, bay["pair_world"].translation).x
bays.sort(key=lambda b: b["route_x"])


def to_local(pair_world, loc_world, aim_world):
    """World lamp position and aim point -> Station-anchored relative offset."""
    d = aim_world - loc_world
    yaw = math.degrees(math.atan2(d.y, d.x))
    pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
    lamp = unreal.Transform(location=loc_world, rotation=unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))
    rel = unreal.MathLibrary.make_relative_transform(lamp, pair_world)
    r = rel.rotation.rotator()
    return {"loc": [round(rel.translation.x, 1), round(rel.translation.y, 1), round(rel.translation.z, 1)],
            "pitch": round(r.pitch, 2), "yaw": round(r.yaw, 2), "roll": round(r.roll, 2)}, d.length()


plan = []
wing_tops = []
backs_placed = 0
for index, bay in enumerate(bays[:-1]):
    nxt = bays[index + 1]
    rng = random.Random(f"{PREFIX}-rig-{bay['ordinal']}")
    pw = bay["pair_world"]
    origin = pw.translation
    across = unreal.MathLibrary.transform_direction(pw, unreal.Vector(0.0, 1.0, 0.0))
    lamp_z = GRID_HEIGHT - BEAM_DEPTH / 2.0 - HANG_DROP
    rows = []
    for side, sign in (("LEFT", -1.0), ("RIGHT", 1.0)):
        box = nxt["panels"].get(side)
        if not box:
            continue
        lo, hi = box
        wing_tops.append(hi[2])
        inner = hi[1] if sign < 0 else lo[1]          # corridor edge of this wing
        outer = lo[1] if sign < 0 else hi[1]
        face_x = lo[0]                                # the face toward the approaching camera
        height = hi[2] - lo[2]
        edge_y_local = abs((unreal.Vector(0.0, inner, 0.0) - unreal.Vector(0.0, origin.y, 0.0)).y)

        # Pool: hung inboard on this side, thrown forward-down onto the wing.
        if rng.random() >= DARK_WING_CHANCE:
            hang = origin + across * (sign * (edge_y_local - INBOARD)) + unreal.Vector(DOWNSTREAM, 0.0, lamp_z)
            ty = inner + (outer - inner) * rng.uniform(0.08, 0.55)
            tz = lo[2] + height * rng.uniform(0.18, 0.72)
            offset, throw = to_local(pw, hang, unreal.Vector(face_x, ty, tz))
            outer_deg = rng.uniform(*POOL_OUTER_DEG)
            rows.append({"slot": f"Rig {side[0]}", "offset": offset, "throw_cm": round(throw),
                         "outer": round(outer_deg, 1), "inner": round(outer_deg * 0.55, 1),
                         "intensity_cd": round(POOL_CD * rng.uniform(0.7, 1.35) * (throw / 850.0) ** 2, 1),
                         "kelvin": 3000, "volumetric_scattering": 2.0, "cast_volumetric_shadow": False,
                         "target": [round(face_x), round(ty), round(tz)]})

    if envelope(index - BACK_SHAFT_REACH_BAYS) < BACK_WHEN_ENVELOPE_BELOW:
        # Back light: hung on the upstream face, thrown toward the audience and
        # down, crossing the corridor so the shaft passes over the cat's line.
        # Consecutive back-lights alternate sides, so a pair crosses.
        sign = 1.0 if backs_placed % 2 == 0 else -1.0
        backs_placed += 1
        own = bay["panels"].get("RIGHT" if sign > 0 else "LEFT")
        # Corridor edge of this bay's own wing on that side: its inboard face.
        edge = abs((own[0][1] if sign > 0 else own[1][1]) - origin.y) if own else 400.0
        hang = origin + across * (sign * max(edge - INBOARD, 120.0)) + unreal.Vector(UPSTREAM, 0.0, lamp_z)
        run = (lamp_z - origin.z) / math.tan(math.radians(BACK_PITCH_DEG)) * rng.uniform(0.85, 1.15)
        floor = unreal.Vector(hang.x - run, origin.y - sign * rng.uniform(0.0, 180.0), origin.z)
        offset, throw = to_local(pw, hang, floor)
        outer_deg = rng.uniform(*BACK_OUTER_DEG)
        rows.append({"slot": "Rig Back", "offset": offset, "throw_cm": round(throw),
                     "outer": round(outer_deg, 1), "inner": round(outer_deg * 0.5, 1),
                     "intensity_cd": round(BACK_CD * rng.uniform(0.8, 1.25), 1),
                     "kelvin": 3400, "volumetric_scattering": BACK_SCATTER, "cast_volumetric_shadow": True,
                     "target": [round(floor.x), round(floor.y), round(floor.z)]})
        plan.append({"cue": bay["label"], "route_x": round(bay["route_x"]),
                     "fill_envelope": round(envelope(index), 3), "lights": rows})
        continue

    # Slash: from the far side, alternating, grazing across the opposite wing.
    side, sign = (("LEFT", -1.0) if bay["ordinal"] % 2 else ("RIGHT", 1.0))
    box = nxt["panels"].get(side)
    if box:
        lo, hi = box
        inner = hi[1] if sign < 0 else lo[1]
        outer = lo[1] if sign < 0 else hi[1]
        edge_y_local = abs(inner - origin.y)
        hang = origin + across * (-sign * (edge_y_local - INBOARD)) + unreal.Vector(UPSTREAM, 0.0, lamp_z)
        ty = inner + (outer - inner) * rng.uniform(0.25, 0.8)
        tz = lo[2] + (hi[2] - lo[2]) * rng.uniform(0.35, 0.85)
        offset, throw = to_local(pw, hang, unreal.Vector(lo[0], ty, tz))
        outer_deg = rng.uniform(*SLASH_OUTER_DEG)
        rows.append({"slot": "Rig Slash", "offset": offset, "throw_cm": round(throw),
                     "outer": round(outer_deg, 1), "inner": round(outer_deg * 0.4, 1),
                     "intensity_cd": round(SLASH_CD * rng.uniform(0.75, 1.3) * (throw / 1100.0) ** 2, 1),
                     "kelvin": 3600, "volumetric_scattering": 2.0, "cast_volumetric_shadow": False,
                     "target": [round(lo[0]), round(ty), round(tz)]})
    plan.append({"cue": bay["label"], "route_x": round(bay["route_x"]),
                 "fill_envelope": round(envelope(index), 3), "lights": rows})
# The last pair hangs no rig (nothing downstream to light) but still takes fill.
plan.append({"cue": bays[-1]["label"], "route_x": round(bays[-1]["route_x"]),
             "fill_envelope": round(envelope(len(bays) - 1), 3), "lights": []})

report = {
    "passage": PASSAGE,
    "bays_rigged": sum(1 for bay in plan if bay["lights"]),
    "lamps": sum(len(p["lights"]) for p in plan),
    "wing_top_cm": [round(min(wing_tops)), round(max(wing_tops))] if wing_tops else None,
    "lamp_height_cm": GRID_HEIGHT - BEAM_DEPTH / 2.0 - HANG_DROP,
    "shared_settings": {"type": "Spot", "units": "Candelas", "cast_shadows": True,
                        "attenuation": "1.6 x throw", "light_function": None,
                        "per_lamp": "volumetric_scattering, cast_volumetric_shadow"},
    "plan": plan,
}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "p03_rig_plan.json")
json.dump(report, open(out, "w"), indent=1)
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"P03_RIG_PLAN_OK|bays={report['bays_rigged']}|lamps={report['lamps']}|wing_top={report['wing_top_cm']}"
           f"|dirty={dirty}|mutated=0")
