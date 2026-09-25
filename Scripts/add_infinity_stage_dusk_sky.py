"""Add or update the editable celestial environment in the Infinity Stage map.

The native InfinityStageCelestialRig supplies the runtime/Sequencer evaluation;
this one-shot editor script creates and binds its ordinary, artist-editable Sun,
Moon, Skylight, fog, atmosphere and cloud actors. Existing artist lights, scene
dressing, grounds and cameras are never changed.

Run with UnrealEditor-Cmd and -ExecutePythonScript after closing the interactive
editor, because both processes must not save the same map concurrently.
"""

import unreal


MAP_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FOLDER_PATH = "Infinity Stage/Environment - Dusk"
MANAGED_TAG = "InfinityStage.DuskEnvironment"
SUN_TAG = "InfinityStage.CelestialSun"
MOON_TAG = "InfinityStage.CelestialMoon"
SKYLIGHT_TAG = "InfinityStage.CelestialSkyLight"
FOG_TAG = "InfinityStage.CelestialFog"


def _log(message):
    unreal.log("InfinityStage dusk setup: " + message)


def _set_property(obj, name, value, required=True):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as error:
        message = "could not set {}.{}: {}".format(obj.get_class().get_name(), name, error)
        if required:
            raise RuntimeError(message)
        unreal.log_warning("InfinityStage dusk setup: " + message)
        return False


def _component(actor, component_class):
    component = actor.get_component_by_class(component_class)
    if not component:
        raise RuntimeError(
            "{} has no {}".format(actor.get_actor_label(), component_class.get_name())
        )
    return component


def _find_or_spawn(actor_subsystem, actor_class, label):
    for actor in actor_subsystem.get_all_level_actors():
        if actor.get_actor_label() == label:
            if not isinstance(actor, actor_class):
                raise RuntimeError(
                    "Actor '{}' already exists but is a {}".format(
                        label, actor.get_class().get_name()
                    )
                )
            _log("updating " + label)
            return actor, False

    actor = actor_subsystem.spawn_actor_from_class(
        actor_class, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator()
    )
    if not actor:
        raise RuntimeError("Could not spawn " + label)
    actor.set_actor_label(label)
    _log("created " + label)
    return actor, True


def _mark_managed(actor, role_tag=None):
    actor.set_folder_path(FOLDER_PATH)
    tags = list(actor.tags)
    for value in (MANAGED_TAG, role_tag):
        if not value:
            continue
        tag = unreal.Name(value)
        if tag not in tags:
            tags.append(tag)
    actor.tags = tags


def _configure_sun(actor):
    # A five-degree-high sun gives a recognisable dusk direction without making
    # the base environment so bright that it competes with theatrical lighting.
    actor.set_actor_rotation(
        unreal.Rotator(pitch=-5.0, yaw=225.0, roll=0.0), False
    )
    component = _component(actor, unreal.DirectionalLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_intensity(5.0)
    component.set_light_color(unreal.LinearColor(1.0, 0.72, 0.48, 1.0))
    component.set_atmosphere_sun_light(True)
    component.set_atmosphere_sun_light_index(0)
    _set_property(component, "cast_shadows", True)
    _set_property(component, "cast_volumetric_shadow", True)


def _configure_moon(actor):
    # The celestial rig keeps this exactly opposite the sun and drives its
    # intensity. Index 1 asks Sky Atmosphere to draw the corresponding moon disk.
    actor.set_actor_rotation(
        unreal.Rotator(pitch=175.0, yaw=225.0, roll=0.0), False
    )
    component = _component(actor, unreal.DirectionalLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_intensity(0.20)
    component.set_light_color(unreal.LinearColor(0.34, 0.46, 0.72, 1.0))
    component.set_atmosphere_sun_light(True)
    component.set_atmosphere_sun_light_index(1)
    _set_property(component, "cast_shadows", True)
    _set_property(component, "cast_volumetric_shadow", True)


def _configure_atmosphere(actor):
    component = _component(actor, unreal.SkyAtmosphereComponent)
    # The standard Earth model is deliberately retained. The low sun supplies
    # the dusk colour naturally and leaves all parameters artist-adjustable.
    _set_property(component, "transform_mode", unreal.SkyAtmosphereTransformMode.PLANET_TOP_AT_ABSOLUTE_WORLD_ORIGIN)
    _set_property(component, "multi_scattering_factor", 1.0)


def _configure_skylight(actor):
    component = _component(actor, unreal.SkyLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    _set_property(component, "source_type", unreal.SkyLightSourceType.SLS_CAPTURED_SCENE)
    component.set_real_time_capture(True)
    component.set_intensity(0.28)
    _set_property(component, "lower_hemisphere_is_black", True)
    component.set_lower_hemisphere_color(unreal.LinearColor(0.008, 0.012, 0.025, 1.0))
    _set_property(component, "cast_shadows", True)


def _configure_fog(actor):
    component = _component(actor, unreal.ExponentialHeightFogComponent)
    component.set_fog_density(0.006)
    component.set_fog_height_falloff(0.20)
    component.set_fog_inscattering_color(unreal.LinearColor(0.11, 0.14, 0.24, 1.0))
    component.set_directional_inscattering_color(unreal.LinearColor(0.62, 0.28, 0.14, 1.0))
    component.set_start_distance(500.0)
    component.set_volumetric_fog(True)
    component.set_volumetric_fog_scattering_distribution(0.25)
    component.set_volumetric_fog_albedo(unreal.Color(176, 190, 230, 255))
    component.set_volumetric_fog_extinction_scale(0.65)
    component.set_volumetric_fog_distance(30000.0)


def _configure_cloud(actor):
    component = _component(actor, unreal.VolumetricCloudComponent)
    # Keep the stock cloud material/settings and make the layer subtle. This is
    # present mainly so the level has the normal UE5 sky stack and can be art-led.
    _set_property(component, "layer_bottom_altitude", 2.0, required=False)
    _set_property(component, "layer_height", 5.0, required=False)
    _set_property(component, "tracing_start_max_distance", 100.0, required=False)


def main():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not level_subsystem.load_level(MAP_PATH):
        raise RuntimeError("Could not load " + MAP_PATH)

    definitions = (
        ("atmosphere", unreal.SkyAtmosphere, "Infinity Stage - Dusk Sky Atmosphere", _configure_atmosphere, None),
        ("sun", unreal.DirectionalLight, "Infinity Stage - Dusk Sun", _configure_sun, SUN_TAG),
        ("moon", unreal.DirectionalLight, "Infinity Stage - Moon", _configure_moon, MOON_TAG),
        ("skylight", unreal.SkyLight, "Infinity Stage - Dusk Skylight", _configure_skylight, SKYLIGHT_TAG),
        ("fog", unreal.ExponentialHeightFog, "Infinity Stage - Dusk Height Fog", _configure_fog, FOG_TAG),
        ("clouds", unreal.VolumetricCloud, "Infinity Stage - Dusk Volumetric Clouds", _configure_cloud, None),
    )

    created = 0
    actors = {}
    for key, actor_class, label, configure, role_tag in definitions:
        actor, was_created = _find_or_spawn(actor_subsystem, actor_class, label)
        _mark_managed(actor, role_tag)
        configure(actor)
        actors[key] = actor
        created += int(was_created)

    rig, was_created = _find_or_spawn(
        actor_subsystem,
        unreal.InfinityStageCelestialRig,
        "Infinity Stage - Sun Moon Stars Cycle",
    )
    _mark_managed(rig)
    _set_property(rig, "sun_light_actor", actors["sun"])
    _set_property(rig, "moon_light_actor", actors["moon"])
    _set_property(rig, "sky_light_actor", actors["skylight"])
    _set_property(rig, "height_fog_actor", actors["fog"])
    # The saved map opens at sunrise. Master Sequence evaluation takes over as
    # soon as a Passage is evaluated and then applies its integrated rate.
    rig.apply_cycle_phase(0.25)
    created += int(was_created)

    if not level_subsystem.save_current_level():
        raise RuntimeError("The celestial actors were configured but the map did not save")

    definition_count = len(definitions) + 1
    _log(
        "complete; created {}, updated {}, saved {}".format(
            created, definition_count - created, MAP_PATH
        )
    )


main()
