"""Read back the placed S3 beach actors and marble-wall slot deltas without saving."""
import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor")
BEACH_RECORD = os.path.join(BASE, "s3_beach_place_record.json")
MARBLE_RECORD = os.path.join(BASE, "s3_walls_marble_record.json")
OUTPUT = os.path.join(BASE, "s3_beach_actor_audit.json")


def census():
    def names(packages):
        return sorted(str(package.get_name()).split(".", 1)[0] for package in packages)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def one(index, label):
    matches = index.get(label, [])
    if len(matches) != 1:
        raise RuntimeError("ACTOR_COUNT|label=%s|count=%d" % (label, len(matches)))
    return matches[0]


def material_paths(actor):
    component = actor.get_editor_property("static_mesh_component")
    return [str(value.get_path_name()) if value else None for value in component.get_materials()]


def canonical_asset_path(value):
    if value is None:
        return None
    return str(value).split(".", 1)[0]


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
    raise RuntimeError("WRONG_WORLD")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE_OR_SIE_ACTIVE")
before = census()
if before != {"content": [], "maps": []}:
    raise RuntimeError("DIRTY_BEFORE|" + json.dumps(before, sort_keys=True))

with open(BEACH_RECORD, encoding="utf-8") as handle:
    beach = json.load(handle)
with open(MARBLE_RECORD, encoding="utf-8") as handle:
    marble = json.load(handle)
if not beach.get("applied") or beach.get("world") != EXPECTED_WORLD:
    raise RuntimeError("BEACH_RECORD_INVALID")
if not marble.get("applied") or marble.get("world") != EXPECTED_WORLD:
    raise RuntimeError("MARBLE_RECORD_INVALID")

index = {}
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    index.setdefault(str(actor.get_actor_label()), []).append(actor)

actors = []
for placed in beach.get("spawned", []):
    actor = one(index, str(placed["label"]))
    parent = actor.get_attach_parent_actor()
    origin, extent = actor.get_actor_bounds(False, True)
    component = actor.get_editor_property("static_mesh_component")
    hidden_actor = None
    try:
        hidden_actor = bool(actor.is_hidden())
    except Exception:
        try:
            hidden_actor = bool(actor.get_editor_property("hidden"))
        except Exception:
            pass
    hidden_component = None
    try:
        hidden_component = bool(component.get_editor_property("hidden_in_game"))
    except Exception:
        pass
    actors.append({
        "label": str(actor.get_actor_label()),
        "kind": str(placed.get("kind")),
        "world_location_cm": [float(value) for value in actor.get_actor_location().to_tuple()],
        "world_bounds_cm": {
            "min": [float(origin.x - extent.x), float(origin.y - extent.y), float(origin.z - extent.z)],
            "max": [float(origin.x + extent.x), float(origin.y + extent.y), float(origin.z + extent.z)],
        },
        "hidden_in_game_actor": hidden_actor,
        "hidden_in_game_component": hidden_component,
        "attach_parent": str(parent.get_actor_label()) if parent else None,
    })

walls = []
for row in marble["plan"]["rows"]:
    actor = one(index, str(row["wall_label"]))
    before_slots = list(row["wall_before"]["materials"])
    current_slots = material_paths(actor)
    changed = []
    for slot in range(max(len(before_slots), len(current_slots))):
        old = before_slots[slot] if slot < len(before_slots) else None
        new = current_slots[slot] if slot < len(current_slots) else None
        if canonical_asset_path(old) != canonical_asset_path(new):
            changed.append({"slot": slot, "before": old, "after": new})
    liner = one(index, str(row["liner_label"]))
    walls.append({
        "wall_label": str(row["wall_label"]),
        "wall_slots_before": before_slots,
        "wall_slots_live": current_slots,
        "changed_slots": changed,
        "liner_label": str(row["liner_label"]),
        "liner_materials_live": material_paths(liner),
        "strategy": str(row["strategy"]),
    })

after = census()
if after != before:
    raise RuntimeError("CENSUS_CHANGED|before=%s|after=%s" %
                       (json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True)))
report = {
    "world": EXPECTED_WORLD,
    "mode": "read_only",
    "actors": actors,
    "marble_walls": walls,
    "census_before": before,
    "census_after": after,
}
with open(OUTPUT, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
unreal.log("S3_BEACH_ACTOR_AUDIT_OK|actors=%d|walls=%d|changed_slots=%d|census=%s|output=%s" %
           (len(actors), len(walls), sum(len(row["changed_slots"]) for row in walls),
            json.dumps(after, separators=(",", ":"), sort_keys=True), OUTPUT.replace("\\", "/")))
