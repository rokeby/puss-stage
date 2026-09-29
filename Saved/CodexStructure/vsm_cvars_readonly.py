"""Read-only: the live values of the lighting and shadow console variables, with
PROOF each name exists. The 25 Sep version could not tell a real 0 from a
misspelt name: it queried r.Deferred.UseLightFunctionAtlas, and the real name is
r.Deferred.UsesLightFunctionAtlas. UE's string getter returns "" for an unknown
cvar, so "exists" is recorded, and a value counts only where it is true.

Added 29 Sep, after the lighting audit (Docs/LightingEfficiencyPlan_2026-09-29.md):
- scalability groups (is sg.ShadowQuality at Cinematic, 4?);
- SMRT ray and sample counts;
- MegaLights (live state unknown);
- light draw-distance scaling (distance culling was not biting at the hitch).

Queries only; sets nothing. Lean: all work in main().
"""
import datetime
import json
import os

import unreal

NAMES = [
    "sg.ShadowQuality", "sg.GlobalIlluminationQuality", "sg.ReflectionQuality", "sg.PostProcessQuality",
    "sg.EffectsQuality", "sg.ViewDistanceQuality",
    "r.Shadow.Virtual.Enable", "r.Shadow.Virtual.MaxPhysicalPages", "r.Shadow.Virtual.Cache",
    "r.Shadow.Virtual.OnePassProjection", "r.Shadow.Virtual.OnePassProjection.MaxLightsPerPixel",
    "r.Shadow.Virtual.SMRT.RayCountLocal", "r.Shadow.Virtual.SMRT.SamplesPerRayLocal",
    "r.Shadow.Virtual.SMRT.RayCountDirectional", "r.Shadow.Virtual.SMRT.SamplesPerRayDirectional",
    "r.Shadow.Virtual.ResolutionLodBiasLocal", "r.Shadow.Virtual.ResolutionLodBiasLocalMoving",
    "r.Shadow.Virtual.ResolutionLodBiasDirectional",
    "r.LightMaxDrawDistanceScale", "r.Shadow.DistanceScale", "r.Shadow.RadiusThreshold",
    "r.MegaLights.EnableForProject", "r.MegaLights.Allowed", "r.MegaLights.LightFunctions",
    "r.LightFunctionAtlas", "r.LightFunctionAtlas.Size", "r.LightFunctionAtlas.MaxLightCount",
    "r.Deferred.UsesLightFunctionAtlas", "r.VolumetricFog.UseLightFunctionAtlas", "r.VolumetricFog.LightFunction",
    "r.VolumetricFog", "r.VolumetricFog.GridPixelSize", "r.VolumetricFog.GridSizeZ",
    "r.VolumetricFog.InjectShadowedLightsSeparately",
    "r.DynamicGlobalIlluminationMethod", "r.ReflectionMethod", "r.Lumen.HardwareRayTracing", "r.RayTracing",
]


def main():
    values = {}
    for name in NAMES:
        text = unreal.SystemLibrary.get_console_variable_string_value(name)
        values[name] = {"exists": text != "", "value": text}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexStructure", "vsm_cvars.json")
    json.dump({"read": datetime.datetime.now().isoformat(timespec="seconds"), "values": values}, open(out, "w"), indent=1)
    missing = [k for k, v in values.items() if not v["exists"]]
    unreal.log(f"VSM_CVARS_READ_OK|n={len(values)}|missing={missing}|sg.ShadowQuality={values['sg.ShadowQuality']['value']}")


main()
