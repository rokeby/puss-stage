"""Read-only, before Gary's "gridiron 1150 -> ~760": what a lower grid would hit.
Per passage: the wing cards' tops and lateral reach (cross beams sit in each
station's plane, rails at +-GridHalfWidth), the borders' bottoms, the grid's
half-width, and the station lamps above a given height (they would lose their
hemp lines and float above the grid). Mutates nothing.
"""
import json
import os

import unreal

CANDIDATES = (760.0, 1150.0)
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "gridiron_height_check.json")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world() and ed.get_game_world() is None, "PIE is running or no editor world; try again when it ends"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()
structures = {}
for a in actors:
    if isinstance(a, unreal.InfinityStageStructureActor):
        structures[a.get_actor_label()] = a
unreal.log(f"GRIDIRON_HEIGHT_CHECK_STRUCTURES|{len(structures)}|actors={len(actors)}")
report = {}
for passage_label, structure in sorted(structures.items()):
    passage = structure.get_editor_property("passage")
    assert passage, f"{passage_label} has no passage"
    grid = structure.get_editor_property("gridiron")
    half = float(structure.get_editor_property("grid_half_width_cm"))
    route_tf = passage.get_actor_transform()
    sides, tops = [], []
    box_cache = {}
    for ref in passage.get_editor_property("materialized_panels"):
        comp = ref.get_editor_property("component")
        idx = ref.get_editor_property("instance_index")
        mesh = comp.get_editor_property("static_mesh")
        if not mesh:
            continue
        box = box_cache.setdefault(mesh.get_path_name(), mesh.get_bounding_box())
        tf = comp.get_instance_transform(idx, True)
        pts = [unreal.MathLibrary.transform_location(tf, unreal.Vector(x, y, z))
               for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
        local = [unreal.MathLibrary.inverse_transform_location(route_tf, p) for p in pts]
        side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0]
        rec = {"top": max(p.z for p in local), "bottom": min(p.z for p in local),
               "lateral": [min(p.y for p in local), max(p.y for p in local)]}
        (tops if side == "TOP" else sides).append(rec)
    lamps = []
    show = passage.get_editor_property("show_asset")
    for cue in show.get_editor_property("cues"):
        if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if not att.get_editor_property("enabled") or "STATION" not in str(att.get_editor_property("anchor")):
                continue
            wt = passage.get_attachment_world_transform(cue.get_editor_property("cue_guid"),
                                                       att.get_editor_property("attachment_guid"))
            if isinstance(wt, unreal.Transform):
                lamps.append(unreal.MathLibrary.inverse_transform_location(route_tf, wt.translation).z)
    report[passage_label] = {
        "grid_height_cm": grid.get_editor_property("height_cm"), "beam_depth_cm": grid.get_editor_property("beam_depth_cm"),
        "grid_half_width_cm": half,
        "wing_cards": {"count": len(sides), "max_top": round(max((s["top"] for s in sides), default=0), 1),
                       "reach_outside_rails": sum(1 for s in sides if max(abs(s["lateral"][0]), abs(s["lateral"][1])) > half),
                       "max_abs_lateral": round(max((max(abs(s["lateral"][0]), abs(s["lateral"][1])) for s in sides), default=0), 1)},
        "borders": {"count": len(tops), "min_bottom": round(min((t["bottom"] for t in tops), default=0), 1)},
        "lamps": {"enabled_station": len(lamps),
                  **{f"above_{int(c)}": sum(1 for z in lamps if z > c) for c in CANDIDATES},
                  "max_z": round(max(lamps, default=0), 1)},
    }
json.dump(report, open(OUT, "w"), indent=1)
unreal.log(f"GRIDIRON_HEIGHT_CHECK_OK|passages={len(report)}|mutated=0")
