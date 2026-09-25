import unreal


def get_game_world():
    for world in unreal.EditorLevelLibrary.get_pie_worlds(False):
        if world and world.get_world_type() == unreal.WorldType.PIE:
            return world
    return None


world = get_game_world()
if world is None:
    unreal.log_error("P02_HIT_LIGHTING_TEST_FAILED|reason=no_pie_world")
    raise RuntimeError("No active PIE world")

before = unreal.SystemLibrary.get_console_variable_int_value(
    "r.Lumen.HardwareRayTracing.LightingMode"
)
unreal.SystemLibrary.execute_console_command(
    world,
    "r.Lumen.HardwareRayTracing.LightingMode 2",
)
after = unreal.SystemLibrary.get_console_variable_int_value(
    "r.Lumen.HardwareRayTracing.LightingMode"
)

if after != 2:
    unreal.log_error(
        f"P02_HIT_LIGHTING_TEST_FAILED|reason=value_not_applied|before={before}|after={after}"
    )
    raise RuntimeError("Hit Lighting test value did not apply")

unreal.log(
    f"P02_HIT_LIGHTING_TEST_SUCCESS|before={before}|after={after}|pie=1"
)
