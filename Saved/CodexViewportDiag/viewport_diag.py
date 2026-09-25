"""Read-only editor viewport diagnostic. Saves nothing, mutates nothing."""
import json
import os

import unreal

payload = {}

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
payload["world"] = world.get_path_name().split(".", 1)[0] if world else None
payload["pie_active"] = editor.get_game_world() is not None

# Viewport camera
try:
    info = editor.get_level_viewport_camera_info()
    if info:
        loc, rot = info
        payload["viewport_camera"] = {
            "location": [loc.x, loc.y, loc.z],
            "rotation": [rot.pitch, rot.yaw, rot.roll],
        }
    else:
        payload["viewport_camera"] = None
except Exception as exc:  # noqa: BLE001
    payload["viewport_camera_error"] = repr(exc)

# Pilot state
level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
try:
    pilot = level_editor.get_pilot_level_actor()
    payload["pilot_actor"] = pilot.get_path_name() if pilot else None
    payload["pilot_actor_class"] = pilot.get_class().get_name() if pilot else None
except Exception as exc:  # noqa: BLE001
    payload["pilot_error"] = repr(exc)

# Sequencer state
try:
    seq_lib = unreal.LevelSequenceEditorBlueprintLibrary
    current = seq_lib.get_current_level_sequence()
    focused = seq_lib.get_focused_level_sequence()
    payload["sequencer"] = {
        "current": current.get_path_name() if current else None,
        "focused": focused.get_path_name() if focused else None,
        "camera_cut_locked_to_viewport": bool(seq_lib.is_camera_cut_locked_to_viewport()),
        "is_playing": bool(seq_lib.is_playing()),
    }
except Exception as exc:  # noqa: BLE001
    payload["sequencer_error"] = repr(exc)

# Viewport settings (camera speed)
try:
    settings = unreal.get_default_object(unreal.LevelEditorViewportSettings)
    speed = {}
    for prop in ("camera_speed", "camera_speed_scalar", "mouse_sensitivty", "mouse_sensitivity",
                 "flight_camera_control_type", "level_editor_joystick_controls",
                 "invert_middle_mouse_pan", "invert_orbit_y_axis", "invert_right_mouse_dolly_y_axis"):
        try:
            speed[prop] = settings.get_editor_property(prop)
        except Exception:  # noqa: BLE001
            pass
    payload["viewport_settings"] = {k: (str(v) if not isinstance(v, (int, float, bool)) else v) for k, v in speed.items()}
except Exception as exc:  # noqa: BLE001
    payload["viewport_settings_error"] = repr(exc)

# Selection
try:
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    payload["selected_actors"] = [a.get_path_name() for a in actor_sub.get_selected_level_actors()]
except Exception as exc:  # noqa: BLE001
    payload["selection_error"] = repr(exc)

# Dirty state (informational)
payload["dirty_content"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
payload["dirty_maps"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexViewportDiag", "viewport_diag.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True, default=str)
unreal.log(f"PUSS_VIEWPORT_DIAG_SUCCESS|pilot={payload.get('pilot_actor')}|pie={payload['pie_active']}")
