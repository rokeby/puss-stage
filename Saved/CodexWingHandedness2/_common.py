"""Shared helpers for the wing-facing repair scripts (imported by path inside Unreal)."""
import collections
import json
import os
import re

import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL_RE = re.compile(r"^P(?P<passage>\d{2}) Wing (?P<ordinal>\d{3})$")
ACTOR_RE = re.compile(r"^Passage 0(?P<passage>[1-6])\b")
OUT_DIR = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingHandedness2",
)


def require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def pkg(v):
    if v is None:
        return None
    return v.get_path_name().split(".", 1)[0] if hasattr(v, "get_path_name") else str(v).split(".", 1)[0]


def dirty():
    return {
        "content": sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}),
        "maps": sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()}),
    }


def editor_ready():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "No editor world")
    require(world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "Unexpected world")
    require(editor.get_game_world() is None, "PIE/SIE is active")


def load_show():
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    require(show is not None, "Show did not load")
    return show


def library_front_axis(show):
    out = {}
    lib = show.get_editor_property("wing_library")
    if lib:
        for e in lib.get_editor_property("entries"):
            out[pkg(e.get_editor_property("mesh"))] = str(e.get_editor_property("front_axis"))
    return out


def is_effectively_rotated(panel, front_axis_by_mesh):
    pol = panel.get_editor_property("facing_policy")
    if pol == unreal.InfinityPanelFacingPolicy.ROTATE180_AROUND_UP:
        return True
    if pol == unreal.InfinityPanelFacingPolicy.PRESERVE_ASSET:
        return False
    return "NEGATIVE_X" in front_axis_by_mesh.get(pkg(panel.get_editor_property("mesh")), "")


def passage_actors(show):
    found = {}
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in sub.get_all_level_actors():
        if actor.get_class().get_name() != "InfinityStagePassageActor":
            continue
        try:
            if actor.get_editor_property("show_asset") != show:
                continue
        except Exception:  # noqa: BLE001
            continue
        m = ACTOR_RE.match(actor.get_actor_label())
        if m:
            p = int(m.group("passage"))
            require(p not in found, f"Duplicate Passage actor for {p}")
            found[p] = actor
    return found


def write_json(name, payload):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True, default=str)
