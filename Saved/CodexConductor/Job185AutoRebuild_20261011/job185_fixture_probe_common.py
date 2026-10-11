"""Shared pure/read-only helpers for Job 185's fixture auto-rebuild probe."""

import json
import math
import os

import unreal


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PASSAGE_PREFIX = "Passage 01"
FIXTURE_TAG = "InfinityStage.Structure.Fixtures"
RECORD = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
    "Job185AutoRebuild_20261011",
    "job185_fixture_move_record.json",
)


class Job185ProbeError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Job185ProbeError(message)


def package(obj):
    return obj.get_outermost().get_name() if obj is not None else None


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def distance(a, b):
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def xy_distance(a, b):
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(2)))


def nearest_distance(point, positions):
    require(positions, "NO_POSITIONS_FOR_NEAREST")
    return min(distance(point, candidate) for candidate in positions)


def unmatched(left, right, tolerance=0.25):
    remaining = [list(value) for value in right]
    missing = []
    for value in left:
        best = min(range(len(remaining)), key=lambda i: distance(value, remaining[i]), default=None)
        if best is None or distance(value, remaining[best]) > tolerance:
            missing.append(list(value))
        else:
            remaining.pop(best)
    return missing, remaining


def context(require_clean=False):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(package(editor.get_editor_world()) == WORLD, "WRONG_WORLD|%s" % package(editor.get_editor_world()))
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    dirty_content = [package(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    dirty_maps = [package(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if require_clean:
        require(not dirty_content and not dirty_maps,
                "DIRTY_BEFORE|content=%s|maps=%s" % (dirty_content, dirty_maps))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    passages = [actor for actor in actors
                if isinstance(actor, unreal.InfinityStagePassageActor)
                and actor.get_actor_label().startswith(PASSAGE_PREFIX)]
    require(len(passages) == 1, "P01_PASSAGE_COUNT|%d" % len(passages))
    passage = passages[0]
    structures = [actor for actor in actors
                  if isinstance(actor, unreal.InfinityStageStructureActor)
                  and actor.get_editor_property("passage") == passage]
    require(len(structures) == 1, "P01_STRUCTURE_COUNT|%d" % len(structures))
    return passage, structures[0], dirty_content, dirty_maps


def fixture_positions(structure):
    components = [component for component in structure.get_editor_property("managed_components")
                  if component is not None
                  and FIXTURE_TAG in [str(tag) for tag in component.get_editor_property("component_tags")]]
    require(len(components) == 1, "FIXTURE_COMPONENT_COUNT|%d" % len(components))
    component = components[0]
    positions = []
    for index in range(int(component.get_instance_count())):
        transform = component.get_instance_transform(index, True)
        require(transform is not None, "FIXTURE_INSTANCE_READ_FAILED|%d" % index)
        positions.append(vec(transform.translation))
    require(positions, "NO_FIXTURE_BODIES")
    return positions


def find_target(passage, positions, target_label=None):
    candidates = []
    for actor in passage.get_editor_property("managed_attachment_actors"):
        if actor is None or actor.get_component_by_class(unreal.LightComponentBase) is None:
            continue
        label = actor.get_actor_label()
        if target_label is not None and label != target_label:
            continue
        location = vec(actor.get_actor_location())
        body = min(positions, key=lambda point: xy_distance(location, point))
        candidates.append((xy_distance(location, body), label, actor, body))
    require(candidates, "NO_P01_LIGHT_CANDIDATE")
    candidates.sort(key=lambda row: (row[0], row[1]))
    nearest_xy, label, actor, body = candidates[0]
    require(nearest_xy <= 1.0, "NO_BODY_AT_LIGHT_XY|label=%s|distance=%.3f" % (label, nearest_xy))
    return actor, body, nearest_xy


def relative_location(actor):
    root = actor.get_editor_property("root_component")
    require(root is not None, "ROOT_COMPONENT_MISSING")
    relative = root.get_editor_property("relative_location")
    return vec(relative)


def commit_relative_location(actor, relative_location_value):
    """Commit an actual Details-style root-location property change."""
    root = actor.get_editor_property("root_component")
    require(root is not None, "ROOT_COMPONENT_MISSING")
    root.modify()
    root.set_editor_property(
        "relative_location",
        unreal.Vector(*relative_location_value),
    )
    require(distance(relative_location(actor), relative_location_value) <= 0.01,
            "RELATIVE_LOCATION_READBACK_FAILED")


def read_record():
    with open(RECORD, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_record(payload):
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    with open(RECORD, "x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    with open(RECORD, "r", encoding="utf-8") as handle:
        require(json.load(handle)["target_label"] == payload["target_label"], "RECORD_READBACK_FAILED")

