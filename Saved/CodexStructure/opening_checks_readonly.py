"""Read-only: the three assumptions the opening-light geometry rests on
(Docs/OpeningLight_2026-09-27.md). Mutates nothing.

1. Where the opening camera is at frame 0 of LS_Opening_Curtain (assumed about
   x 3600, z 150; the lamp at x 3200 must sit behind it).
2. The true bottom edge of P01's cloud borders (pivot 800 cm; the lamp at 650
   and its beam must pass beneath them).
3. The curtain's position, track span and fall direction (assumed at x 5400,
   spanning y about -890..+890, falling toward -X; the guided fall moves the
   cloth along its component's local +Y).
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ_PATH = "/Game/InfinityStage/Interactions/LS_Opening_Curtain"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = list(sub.get_all_level_actors())
report = {"camera": {}, "borders": {}, "curtain": {}}


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


# 1. The opening camera ---------------------------------------------------------
seq = unreal.EditorAssetLibrary.load_asset(SEQ_PATH)
cam = report["camera"]
cam["sequence_loaded"] = bool(seq)
if seq:
    names = {}
    for b in seq.get_bindings():
        names[unreal.GuidLibrary.conv_guid_to_string(b.get_id())] = b
    cuts = []
    for track in seq.get_tracks():
        if isinstance(track, unreal.MovieSceneCameraCutTrack):
            for sec in track.get_sections():
                bid = sec.get_camera_binding_id()
                guid = unreal.GuidLibrary.conv_guid_to_string(bid.get_editor_property("guid"))
                binding = names.get(guid)
                cuts.append({"start": sec.get_start_frame(), "binding": str(binding.get_display_name()) if binding else guid})
    cuts.sort(key=lambda c: c["start"])
    cam["camera_cuts"] = cuts
    first = cuts[0]["binding"] if cuts else None
    cam["first_camera"] = first
    # A possessed camera in the level: its placed transform. A keyed transform
    # track overrides it; report the first keys if there are any.
    if first:
        placed = next((a for a in actors if a.get_actor_label() == first), None)
        if placed:
            cam["placed_location"] = vec(placed.get_actor_location())
            cam["placed_rotation"] = [round(placed.get_actor_rotation().pitch, 1), round(placed.get_actor_rotation().yaw, 1)]
        binding = next((b for b in seq.get_bindings() if str(b.get_display_name()) == first), None)
        if binding:
            keyed = {}
            for track in binding.get_tracks():
                if isinstance(track, unreal.MovieScene3DTransformTrack):
                    for sec in track.get_sections():
                        for ch in sec.get_all_channels():
                            keys = ch.get_keys()
                            if keys:
                                keyed[ch.get_name()] = {"first_frame": keys[0].get_time().frame_number.value,
                                                        "value": round(keys[0].get_value(), 2), "keys": len(keys)}
            cam["transform_keys"] = keyed

# 2. P01's borders ---------------------------------------------------------------
p01 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
lows = []
for ref in p01.get_editor_property("materialized_panels"):
    if "TOP" not in str(ref.get_editor_property("side")):
        continue
    comp = ref.get_editor_property("component")
    box = comp.get_editor_property("static_mesh").get_bounding_box()
    tf = ref.get_editor_property("base_world_transform")
    corners = [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
               for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
    lows.append({"x": round(tf.translation.x), "bottom_z": round(min(c.z for c in corners), 1),
                 "top_z": round(max(c.z for c in corners), 1),
                 "y_span": [round(min(c.y for c in corners)), round(max(c.y for c in corners))]})
near = [b for b in lows if 2500 <= b["x"] <= 6500]
report["borders"] = {"count": len(lows),
                     "lowest_bottom_z": min((b["bottom_z"] for b in lows), default=None),
                     "near_the_opening": sorted(near, key=lambda b: b["x"])}

# 3. The curtain ---------------------------------------------------------------
curtains = [a for a in actors if "Curtain" in a.get_actor_label() and "Chaos" in a.get_actor_label()]
for a in curtains:
    rec = {"location": vec(a.get_actor_location()), "yaw": round(a.get_actor_rotation().yaw, 1),
           "actor_forward_x": vec(a.get_actor_forward_vector()), "actor_right_y": vec(a.get_actor_right_vector()),
           "components": []}
    for comp in a.get_components_by_class(unreal.PrimitiveComponent):
        o, e, _ = unreal.SystemLibrary.get_component_bounds(comp)
        rec["components"].append({"name": comp.get_name(), "class": comp.get_class().get_name(),
                                  "min": vec(o - e), "max": vec(o + e),
                                  "local_plus_y_in_world": vec(unreal.MathLibrary.transform_direction(
                                      comp.get_world_transform(), unreal.Vector(0.0, 1.0, 0.0)))})
    report["curtain"][a.get_actor_label()] = rec

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "opening_checks.json")
json.dump(report, open(out, "w"), indent=1, default=str)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"OPENING_CHECKS_OK|first_camera={cam.get('first_camera')}|borders={report['borders']['count']}"
           f"|lowest_border={report['borders']['lowest_bottom_z']}|curtains={len(report['curtain'])}"
           f"|dirty={dirty[0]}+{dirty[1]}|mutated=0")
