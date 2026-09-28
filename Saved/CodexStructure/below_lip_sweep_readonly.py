"""Read-only: what, if anything, is modelled in front of and below the portal's
forestage lip, in the part of Gary's opening frame that looks below stage level
(eye z 150, tilt 14 deg, 15 mm: the bottom ray crosses the lip plane at z -305).
An exhaustive sweep of every level actor's bounds, so "void" can be stated as
measured rather than assumed. Mutates nothing, spawns nothing.

Boxes (UE world cm): FRONT, from the camera to the lip, below stage level; and
UNDER, beneath the forestage. Actors whose bounds are huge (volumes, sky, fog)
are listed separately, because they intersect everything and model no surface.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
BOXES = {"front": ((-1500.0, -1200.0, -1000.0), (-150.0, 1200.0, 0.0)),
         "under": ((-150.0, -1000.0, -1000.0), (0.0, 1000.0, -5.0))}
HUGE_CM = 20000.0

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def overlaps(lo, hi, box):
    (bx0, by0, bz0), (bx1, by1, bz1) = box
    return lo[0] < bx1 and hi[0] > bx0 and lo[1] < by1 and hi[1] > by0 and lo[2] < bz1 and hi[2] > bz0


hits = {name: [] for name in BOXES}
huge = []
count = 0
for actor in sub.get_all_level_actors():
    count += 1
    origin, extent = actor.get_actor_bounds(False)
    if extent.length() < 0.01:
        continue
    lo = [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z]
    hi = [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]
    rec = {"label": actor.get_actor_label(), "class": actor.get_class().get_name(),
           "min": [round(v) for v in lo], "max": [round(v) for v in hi],
           "hidden_in_game": bool(actor.get_editor_property("hidden"))}
    for name, box in BOXES.items():
        if overlaps(lo, hi, box):
            (huge if max(extent.x, extent.y, extent.z) * 2.0 > HUGE_CM else hits[name]).append(dict(rec, box=name))

report = {"actors_swept": count, "boxes": BOXES, "hits": hits, "huge_or_volumes": huge}
json.dump(report, open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                    "CodexStructure", "below_lip_sweep.json"), "w"), indent=1)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"BELOW_LIP_SWEEP_OK|actors={count}|front={len(hits['front'])}|under={len(hits['under'])}"
           f"|huge={len(huge)}|dirty={dirty[0]}+{dirty[1]}|mutated=0")
