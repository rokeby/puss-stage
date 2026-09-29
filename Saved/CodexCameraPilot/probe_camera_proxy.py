"""Read-only: is the beige camera-proxy box Gary saw in the Opening hidden in game?

Conductor item 3 (29 Sep): the diagnosis is that the box is a camera's editor
proxy mesh, hidden in PIE by default (bCameraMeshHiddenInGame). This reads the
flag, and the proxy mesh components themselves, on every camera in the level.
The P01 rig is listed first. It writes nothing and refuses to run in PIE; it
reports (does not fail on) packages that are dirty before or after.

Success marker: PUSS_CAMERA_PROXY_PROBE
"""

import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def main():
    # Everything inside a function: UE wrappers left in module globals crash the
    # editor when the script is run a second time (MCP Python, 29 Sep).
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    dirty_before = dirty()

    rows = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        cameras = actor.get_components_by_class(unreal.CameraComponent)
        if not cameras:
            continue
        for camera in cameras:
            row = {
                "actor": actor.get_actor_label(),
                "class": actor.get_class().get_name(),
                "camera": camera.get_name(),
                "camera_mesh_hidden_in_game": bool(camera.get_editor_property("camera_mesh_hidden_in_game")),
                "proxies": [],
            }
            for mesh in actor.get_components_by_class(unreal.StaticMeshComponent):
                if mesh.get_attach_parent() != camera and "proxy" not in mesh.get_name().lower():
                    continue
                static_mesh = mesh.get_editor_property("static_mesh")
                row["proxies"].append({
                    "name": mesh.get_name(),
                    "mesh": static_mesh.get_path_name() if static_mesh else None,
                    "hidden_in_game": bool(mesh.get_editor_property("hidden_in_game")),
                    "visible": bool(mesh.get_editor_property("visible")),
                    "is_editor_only": bool(mesh.get_editor_property("is_editor_only")),
                })
            rows.append(row)

    rows.sort(key=lambda r: (not r["actor"].startswith("Passage 01"), r["actor"]))
    shown = [r for r in rows if not r["camera_mesh_hidden_in_game"]
             or any(not p["hidden_in_game"] and not p["is_editor_only"] for p in r["proxies"])]
    dirty_after = dirty()

    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "probe_camera_proxy.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"cameras": rows, "shown_in_game": shown,
                   "dirty_before": dirty_before, "dirty_after": dirty_after}, handle, indent=2)

    p01 = next((r for r in rows if r["actor"].startswith("Passage 01")), None)
    unreal.log(
        "PUSS_CAMERA_PROXY_PROBE"
        f"|cameras={len(rows)}|shown_in_game={len(shown)}"
        f"|p01_hidden={p01['camera_mesh_hidden_in_game'] if p01 else 'NO_P01_RIG'}"
        f"|p01_proxies={p01['proxies'] if p01 else []}"
        f"|dirty_before={len(dirty_before)}|dirty_after={len(dirty_after)}")


main()
