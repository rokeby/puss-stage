"""Read-only: current values of the shadow / light-count console variables that
bear on the VSM one-pass overflow. Queries only; sets nothing."""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"

NAMES = [
    "r.LightFunctionAtlas",
    "r.LightFunctionAtlas.Size",
    "r.LightFunctionAtlas.MaxLightCount",
    "r.VolumetricFog.LightFunction",
    "r.VolumetricFog.UseLightFunctionAtlas",
    "r.Deferred.UseLightFunctionAtlas",
    "r.MegaLights.LightFunctions",
    "r.VolumetricFog.InjectShadowedLightsSeparately",
    "r.Shadow.Virtual.OnePassProjection",
    "r.Shadow.Virtual.OnePassProjection.MaxLightsPerPixel",
    "r.Shadow.Virtual.Enable",
    "r.Shadow.Virtual.MaxPhysicalPages",
    "r.MegaLights.EnableForProject",
    "r.MegaLights.Allowed",
    "r.RayTracing",
    "r.Lumen.HardwareRayTracing",
    "r.VolumetricFog.GridPixelSize",
    "r.VolumetricFog.GridSizeZ",
]
values = {}
for name in NAMES:
    values[name] = {
        "int": unreal.SystemLibrary.get_console_variable_int_value(name),
        "float": unreal.SystemLibrary.get_console_variable_float_value(name),
    }
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "vsm_cvars.json")
json.dump(values, open(out, "w"), indent=1)
unreal.log("VSM_CVARS_READ_OK|" + "|".join(f"{k}={v['float']}" for k, v in values.items()))
