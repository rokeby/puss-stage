"""Stable, exhaustive field-wise state for Infinity Stage attachments."""
from __future__ import annotations


# Keep these lists exhaustive. Unreal struct ``str()`` values include transient
# Python-wrapper identity and therefore cannot participate in restore checks.
LIGHT_FIELDS = (
    "type", "intensity_units", "intensity", "color", "use_temperature",
    "temperature_kelvin", "attenuation_radius_cm", "indirect_lighting_intensity",
    "volumetric_scattering_intensity", "diffuse_scale", "specular_scale",
    "affect_translucent_lighting", "transmission", "cast_shadows",
    "cast_volumetric_shadow", "affect_reflection", "affect_global_illumination",
    "shadow_bias", "shadow_slope_bias", "force_cached_shadows_for_movable_primitives",
    "use_ray_traced_distance_field_shadows", "lighting_channel0", "lighting_channel1",
    "lighting_channel2", "max_draw_distance_cm", "max_distance_fade_range_cm",
    "use_inverse_squared_falloff", "light_falloff_exponent", "inverse_exposure_blend",
    "source_radius_cm", "soft_source_radius_cm", "source_length_cm",
    "inner_cone_angle_degrees", "outer_cone_angle_degrees", "rect_source_width_cm",
    "rect_source_height_cm", "rect_barn_door_angle_degrees", "rect_barn_door_length_cm",
    "rect_source_texture", "ies_texture", "use_ies_brightness", "ies_brightness_scale",
    "light_function_material", "light_function_scale", "light_function_fade_distance_cm",
    "light_function_disabled_brightness",
)
LIGHT_OBJECT_FIELDS = {
    "rect_source_texture", "ies_texture", "light_function_material",
}
DRAMA_FIELDS = (
    "strike_on_approach", "strike_distance_cm", "strike_ramp_cm", "ignition_stutter",
    "unstruck_intensity_scale", "after_pass", "after_pass_distance_cm",
    "decay_distance_cm", "slow_move", "pan_amplitude_degrees", "tilt_amplitude_degrees",
    "period_seconds", "phase_from_identity", "phase_cycles",
)
EFFECT_FIELDS = (
    "type", "output", "tint", "active_radius_cm", "pulse_period_seconds", "pulse_duty",
    "feeds_local_medium", "medium_offset_cm", "medium_radius_cm", "medium_density",
    "medium_height_falloff", "linked_light_attachment_guid", "flicker_amount",
    "burn_start_ahead_cm", "burn_span_cm", "ignition_uv", "burn_u_axis", "burn_v_axis",
    "burn_uv_measured_mesh", "motes_extent_cm", "replicated_from_attachment_guid",
)
EFFECT_GUID_FIELDS = {
    "linked_light_attachment_guid", "replicated_from_attachment_guid",
}
EFFECT_OBJECT_FIELDS = {"burn_uv_measured_mesh"}


def _plain_struct_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if all(hasattr(value, name) for name in ("x", "y", "z", "w")):
        return [float(value.x), float(value.y), float(value.z), float(value.w)]
    if all(hasattr(value, name) for name in ("x", "y", "z")):
        return [float(value.x), float(value.y), float(value.z)]
    if all(hasattr(value, name) for name in ("x", "y")):
        return [float(value.x), float(value.y)]
    if all(hasattr(value, name) for name in ("r", "g", "b", "a")):
        return [float(value.r), float(value.g), float(value.b), float(value.a)]
    return str(value)


def _object_path(value):
    if value is None:
        return None
    get_path_name = getattr(value, "get_path_name", None)
    if callable(get_path_name):
        return str(get_path_name())
    to_string = getattr(value, "to_string", None)
    if callable(to_string):
        return str(to_string())
    return str(value)


def _transform_state(transform):
    location = transform.translation
    scale = transform.scale3d
    rotation = transform.rotation
    quaternion = [float(rotation.x), float(rotation.y),
                  float(rotation.z), float(rotation.w)]
    for component in quaternion:
        if component == 0.0:
            continue
        if component < 0.0:
            quaternion = [-value for value in quaternion]
        break
    return {
        "location": [float(location.x), float(location.y), float(location.z)],
        "rotation_xyzw": quaternion,
        "scale": [float(scale.x), float(scale.y), float(scale.z)],
    }


def _struct_state(value, fields, guid_text, guid_fields=(), object_fields=()):
    out = {}
    for name in fields:
        field = value.get_editor_property(name)
        if name in guid_fields:
            out[name] = guid_text(field)
        elif name in object_fields:
            out[name] = _object_path(field)
        else:
            out[name] = _plain_struct_value(field)
    return out


def attachment_state(attachment, guid_text):
    """Return every serialized attachment field without wrapper identity."""
    lighting = attachment.get_editor_property("lighting")
    lighting_state = _struct_state(
        lighting, LIGHT_FIELDS, guid_text, object_fields=LIGHT_OBJECT_FIELDS)
    lighting_state["drama"] = _struct_state(
        lighting.get_editor_property("drama"), DRAMA_FIELDS, guid_text)
    effect_state = _struct_state(
        attachment.get_editor_property("effect"), EFFECT_FIELDS, guid_text,
        guid_fields=EFFECT_GUID_FIELDS, object_fields=EFFECT_OBJECT_FIELDS)
    return {
        "guid": guid_text(attachment.get_editor_property("attachment_guid")),
        "label": str(attachment.get_editor_property("label")),
        "kind": str(attachment.get_editor_property("kind")),
        "enabled": bool(attachment.get_editor_property("enabled")),
        "actor_class": _object_path(attachment.get_editor_property("actor_class")),
        "mesh": _object_path(attachment.get_editor_property("mesh")),
        "anchor": str(attachment.get_editor_property("anchor")),
        "relative_transform": _transform_state(
            attachment.get_editor_property("relative_transform")),
        "lighting": lighting_state,
        "effect": effect_state,
        "trigger_distance_cm": float(
            attachment.get_editor_property("trigger_distance_cm")),
    }


def state_differences(before, after, path=""):
    """Return exact differing field paths; an empty list means equal state."""
    if isinstance(before, dict) and isinstance(after, dict):
        differences = []
        for key in sorted(set(before) | set(after)):
            child = "%s.%s" % (path, key) if path else str(key)
            if key not in before or key not in after:
                differences.append({"path": child, "before": before.get(key),
                                    "after": after.get(key)})
            else:
                differences.extend(state_differences(before[key], after[key], child))
        return differences
    if isinstance(before, list) and isinstance(after, list):
        differences = []
        for index in range(max(len(before), len(after))):
            child = "%s[%d]" % (path, index)
            if index >= len(before) or index >= len(after):
                differences.append({
                    "path": child,
                    "before": before[index] if index < len(before) else None,
                    "after": after[index] if index < len(after) else None,
                })
            else:
                differences.extend(state_differences(before[index], after[index], child))
        return differences
    return [] if before == after else [{"path": path, "before": before, "after": after}]

