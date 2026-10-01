import datetime
import json


def error_row(exc):
    return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}


def vector_row(value):
    return [float(value.x), float(value.y), float(value.z)]


def rotator_row(value):
    return [float(value.roll), float(value.pitch), float(value.yaw)]


def transform_row(value):
    rotation = value.rotation.rotator()
    return {
        "location": vector_row(value.translation),
        "rotation_rpy": rotator_row(rotation),
        "scale": vector_row(value.scale3d),
    }


def object_row(value):
    if value is None:
        return None
    row = {"python_type": type(value).__name__}
    try:
        row["name"] = str(value.get_name())
    except Exception as exc:
        row["name_error"] = "%s: %s" % (type(exc).__name__, exc)
    try:
        row["class"] = str(value.get_class().get_name())
    except Exception as exc:
        row["class_error"] = "%s: %s" % (type(exc).__name__, exc)
    try:
        row["path"] = str(value.get_path_name())
    except Exception as exc:
        row["path_error"] = "%s: %s" % (type(exc).__name__, exc)
    return row


def component_row(component, unreal_module):
    row = object_row(component)
    if row is None:
        return None
    row["is_cine_camera_component"] = isinstance(component, unreal_module.CineCameraComponent)
    try:
        row["current_focal_length"] = float(component.get_editor_property("current_focal_length"))
    except Exception as exc:
        row["current_focal_length_error"] = "%s: %s" % (type(exc).__name__, exc)
    try:
        filmback = component.get_editor_property("filmback")
        row["filmback_sensor_width"] = float(filmback.get_editor_property("sensor_width"))
    except Exception as exc:
        row["filmback_sensor_width_error"] = "%s: %s" % (type(exc).__name__, exc)
    return row


def main():
    import unreal

    run = datetime.datetime.now().strftime("%H%M%S")
    report = {
        "run": run,
        "sequence": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03",
        "binding": "S3 Wide",
        "template": {},
        "level_actor": {"label": "Scene 3 — External Sound — Entry Handoff Camera"},
    }

    sequence = None
    try:
        sequence = unreal.load_asset(report["sequence"])
        report["sequence_load"] = {"ok": sequence is not None, "object": object_row(sequence)}
    except Exception as exc:
        report["sequence_load"] = error_row(exc)

    binding = None
    if sequence is not None:
        try:
            matches = [candidate for candidate in sequence.get_spawnables()
                       if str(candidate.get_display_name()) == report["binding"]]
            report["spawnable_lookup"] = {
                "ok": len(matches) == 1,
                "match_count": len(matches),
                "spawnable_names": [str(candidate.get_display_name()) for candidate in sequence.get_spawnables()],
            }
            if len(matches) == 1:
                binding = matches[0]
        except Exception as exc:
            report["spawnable_lookup"] = error_row(exc)
    else:
        report["spawnable_lookup"] = {"ok": False, "error": "sequence unavailable"}

    template = None
    if binding is not None:
        try:
            template = binding.get_object_template()
            report["template_object"] = {"ok": template is not None, "object": object_row(template)}
        except Exception as exc:
            report["template_object"] = error_row(exc)
    else:
        report["template_object"] = {"ok": False, "error": "binding unavailable"}

    template_report = report["template"]
    if template is not None:
        try:
            template_report["type"] = {
                "ok": True,
                "python_type": type(template).__name__,
                "unreal_class": str(template.get_class().get_name()),
            }
        except Exception as exc:
            template_report["type"] = error_row(exc)

        try:
            template_report["get_actor_transform"] = {
                "ok": True,
                "value": transform_row(template.get_actor_transform()),
            }
        except Exception as exc:
            template_report["get_actor_transform"] = error_row(exc)

        try:
            root_component = template.get_editor_property("root_component")
            root_row = component_row(root_component, unreal)
            if root_component is not None:
                root_row["relative_location"] = vector_row(root_component.get_editor_property("relative_location"))
                root_row["relative_rotation_rpy"] = rotator_row(root_component.get_editor_property("relative_rotation"))
            template_report["root_component"] = {"ok": True, "value": root_row}
        except Exception as exc:
            template_report["root_component"] = error_row(exc)

        try:
            component = template.get_cine_camera_component()
            template_report["get_cine_camera_component"] = {
                "ok": True,
                "value": component_row(component, unreal),
            }
        except Exception as exc:
            template_report["get_cine_camera_component"] = error_row(exc)

        try:
            component = template.get_editor_property("camera_component")
            template_report["get_editor_property_camera_component"] = {
                "ok": True,
                "value": component_row(component, unreal),
            }
        except Exception as exc:
            template_report["get_editor_property_camera_component"] = error_row(exc)

        try:
            component = template.get_editor_property("cine_camera_component")
            template_report["get_editor_property_cine_camera_component"] = {
                "ok": True,
                "value": component_row(component, unreal),
            }
        except Exception as exc:
            template_report["get_editor_property_cine_camera_component"] = error_row(exc)

        try:
            components = list(template.get_components_by_class(unreal.CineCameraComponent))
            template_report["get_components_by_class_CineCameraComponent"] = {
                "ok": True,
                "count": len(components),
                "values": [component_row(component, unreal) for component in components],
            }
        except Exception as exc:
            template_report["get_components_by_class_CineCameraComponent"] = error_row(exc)

        try:
            getter = getattr(template, "get_default_subobject_by_name")
            attempts = []
            found = []
            for subobject_name in ("CameraComponent", "CineCameraComponent"):
                value = getter(subobject_name)
                attempts.append({"name": subobject_name, "value": object_row(value)})
                if isinstance(value, unreal.CineCameraComponent):
                    found.append(component_row(value, unreal))
            template_report["get_default_subobject_by_name_CineCameraComponent"] = {
                "ok": True,
                "attempts": attempts,
                "found": found,
            }
        except Exception as exc:
            template_report["get_default_subobject_by_name_CineCameraComponent"] = error_row(exc)
    else:
        template_report["error"] = "template unavailable"

    try:
        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        level_matches = [actor for actor in actor_subsystem.get_all_level_actors()
                         if actor.get_actor_label() == report["level_actor"]["label"]]
        report["level_actor"]["match_count"] = len(level_matches)
        if len(level_matches) != 1:
            raise RuntimeError("expected exactly one labelled actor, found %d" % len(level_matches))
        level_actor = level_matches[0]
        report["level_actor"]["type"] = object_row(level_actor)
        report["level_actor"]["get_actor_transform"] = transform_row(level_actor.get_actor_transform())
        level_camera = level_actor.get_cine_camera_component()
        report["level_actor"]["camera_component"] = component_row(level_camera, unreal)
        report["level_actor"]["current_focal_length"] = float(
            level_camera.get_editor_property("current_focal_length")
        )
    except Exception as exc:
        report["level_actor"]["error"] = error_row(exc)

    compact = json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    unreal.log("S3_WIDE_TEMPLATE_PROBE|run=%s|%s" % (run, compact))


if __name__ == "__main__":
    main()
