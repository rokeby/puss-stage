"""No-mutation probe: construct transient attachment/light structs and check enum names and guid settability."""
import unreal
out = {}
try:
    att = unreal.InfinityCueAttachment()
    g = unreal.GuidLibrary.new_guid()
    try:
        att.set_editor_property("attachment_guid", g); out["guid_settable"] = str(att.get_editor_property("attachment_guid")) != str(unreal.Guid())
    except Exception as exc: out["guid_settable"] = f"NO: {exc!r}"
    att.set_editor_property("kind", unreal.InfinityAttachmentKind.LIGHT)
    att.set_editor_property("anchor", unreal.InfinityAttachmentAnchor.STATION)
    L = unreal.InfinityStageLightSettings()
    L.set_editor_property("type", unreal.InfinityStageLightType.RECT)
    L.set_editor_property("intensity_units", unreal.InfinityStageLightIntensityUnits.CANDELAS)
    L.set_editor_property("intensity", 2.0); L.set_editor_property("color", unreal.LinearColor(0.3, 0.33, 0.4, 1.0))
    L.set_editor_property("use_temperature", True); L.set_editor_property("temperature_kelvin", 10000.0)
    L.set_editor_property("attenuation_radius_cm", 656.8); L.set_editor_property("inner_cone_angle_degrees", 8.0)
    L.set_editor_property("outer_cone_angle_degrees", 32.0); L.set_editor_property("rect_source_width_cm", 138.7); L.set_editor_property("rect_source_height_cm", 186.7)
    att.set_editor_property("lighting", L)
    t = unreal.Transform(); t.translation = unreal.Vector(1, 2, 3); t.rotation = unreal.Rotator(-9.0, -66.4, 0.0).quaternion()
    att.set_editor_property("relative_transform", t); att.set_editor_property("label", unreal.Text("probe"))
    out["units_enum"] = [str(x) for x in (unreal.InfinityStageLightIntensityUnits.EV, unreal.InfinityStageLightIntensityUnits.CANDELAS, unreal.InfinityStageLightIntensityUnits.LUMENS)]
    out["ok"] = True
except Exception as exc:
    out["error"] = repr(exc)
unreal.log("PUSS_PROBE|" + str(out))
