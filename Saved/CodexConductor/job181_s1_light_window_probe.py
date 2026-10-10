"""Read-only S1 sequence light/visibility census around local frames 262..302."""
import importlib.util
import json
import os

import unreal


HERE = "E:/PussStage/Saved/CodexConductor"
adapter_path = os.path.join(HERE, "Job169S1FireEnding_20261010", "job169_stage_lights_out.py")
spec = importlib.util.spec_from_file_location("job181_lights_adapter", adapter_path)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
legacy = adapter._load_legacy()
seq = unreal.load_asset(legacy["SEQ_PATH"])
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
frames = [262, 269, 282, 302]
rows = []
for binding in seq.get_bindings():
    bound = legacy["_bound_objects"](seq, binding, world)
    actor = next((obj for obj in bound if hasattr(obj, "get_actor_label")), None)
    light = actor.get_component_by_class(unreal.LightComponentBase) if actor is not None else None
    visibility = []
    intensity = []
    for track in binding.get_tracks():
        cls = track.get_class().get_name()
        prop = legacy["_track_property"](track)
        if cls == "MovieSceneVisibilityTrack":
            for section in track.get_sections():
                channels = list(section.get_all_channels())
                visibility.append({
                    "range": legacy["_section_range"](section, seq),
                    "active": bool(section.is_active()),
                    "property": prop,
                    "values": {str(frame): (bool(legacy["_evaluate"](seq, channels[0], frame, "JOB181-PROBE", str(binding.get_display_name()))) if len(channels) == 1 else None) for frame in frames},
                })
        if cls == "MovieSceneFloatTrack" and prop[0] == "Intensity":
            for section in track.get_sections():
                channels = list(section.get_all_channels())
                intensity.append({
                    "range": legacy["_section_range"](section, seq),
                    "keys": [legacy["_key_row"](key) for key in (list(channels[0].get_keys()) if len(channels) == 1 else [])],
                })
    if light is not None or visibility or intensity:
        rows.append({
            "binding": str(binding.get_display_name()),
            "guid": legacy["_guid"](binding.get_id()),
            "bound": [legacy["_object_path"](obj) for obj in bound],
            "actor_label": str(actor.get_actor_label()) if actor is not None else None,
            "light_base_intensity": float(light.get_editor_property("intensity")) if light is not None else None,
            "visibility": visibility,
            "intensity_tracks": intensity,
        })
out = os.path.join(HERE, "job181_s1_light_window_probe.json")
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"frames": frames, "rows": rows}, handle, indent=2, sort_keys=True, default=str)
unreal.log("JOB181_S1_LIGHT_WINDOW_PROBE_OK|rows=%d|light_rows=%d|visibility_rows=%d|out=%s" %
           (len(rows), sum(row["light_base_intensity"] is not None for row in rows), sum(bool(row["visibility"]) for row in rows), out))
