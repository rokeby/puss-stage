"""FX CONTENT PROBE (read-only). OFFLINE-WRITTEN 7 Oct, never run in Unreal.

Why: the rain bench (P04RainBench/p04_rain_bench_probe.json) and the bee swarm stream MEASURED that Niagara graphs are
not authorable from Python here, and concluded "Niagara session tomorrow" for rain, smoke, fire and motes. That scan
looked only for the class string "NiagaraSystem" (p04_rain_bench.py:10-11). The project ALSO holds Cascade
ParticleSystems that are already rain / smoke / fire / steam / dust [binary-proven: uasset name tables, re-derived by
test_fx_content_probe_offline.py]:
  /Game/Japanese_Alley/VFX/Rain2              GPU sprites, AccelerationConstant, SizeScaleBySpeed (rain streaks)
  /Game/Japanese_Alley/VFX/Humo_Par           GPU, SubUV (smoke)
  /Game/KK_S2_Shrine/StarterContent/Particles/P_Smoke, P_Fire (has ParticleModuleLight), P_Steam_Lit, P_Ambient_Dust
Cascade components are UFXSystemComponents, which AInfinityStageEffectSource already gates by camera distance
(InfinityStageEffectSource.cpp:536-549, TInlineComponentArray<UFXSystemComponent*>) [declaration-proven], and AEmitter
still exists in 5.8 (Engine/Classes/Particles/Emitter.h:54) [declaration-proven]. Whether 5.8 still RENDERS them and
what Python can READ/SET on them is unknown: this probe measures it, read-only.

WHAT IT READS (nothing is spawned, edited, compiled or saved; census must be identical before/after):
  1. per asset: exists, loads, class; Cascade: emitters reachable? per emitter LOD0 module classes; spawn module rate
     distribution reachable (get_editor_property chain) - the fact a cued "plume" tune would need; Niagara: class,
     emitter_handles reachable?
  2. API presence (hasattr only, nothing called): unreal.Emitter, GameplayStatics.spawn_emitter_at_location,
     NiagaraFunctionLibrary.spawn_system_at_location, ParticleSystemComponent.set_float_parameter.
  3. the C++ default Effect classes /Game/Scenes/Effects/BP_Effect_<Type> (InfinityStageEffectSource.cpp:47-64) and
     the C++ swarm renderer /Game/Scenes/Effects/Swarm/NS_BeeSwarm (InfinityStageBeeSwarmActor.cpp:24): exist?
Output: fx_content_probe.json next to this file; marker FXPROBE_OK|run=..|census_equal=1 or FXPROBE_STOPPED|..
Never: PIE end, Save, spawn, set_editor_property, reload. No unreal objects in module globals.
"""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor", "Effects_20261007")
OUT = os.path.join(HERE, "fx_content_probe.json")
RUN = datetime.datetime.now().strftime("FXPROBE-%Y%m%d-%H%M%S")
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CASCADE = ("/Game/Japanese_Alley/VFX/Rain2", "/Game/Japanese_Alley/VFX/Humo_Par",
           "/Game/KK_S2_Shrine/StarterContent/Particles/P_Smoke", "/Game/KK_S2_Shrine/StarterContent/Particles/P_Fire",
           "/Game/KK_S2_Shrine/StarterContent/Particles/P_Steam_Lit",
           "/Game/KK_S2_Shrine/StarterContent/Particles/P_Ambient_Dust")
NIAGARA = ("/Game/FX/NS_BeeSwarm", "/Game/KK_S2_Shrine/Falling_Leaves/FX/NS_Falling_Leaves",
           "/Game/Scenes/Effects/Swarm/NS_BeeSwarm")
EFFECT_BPS = tuple("/Game/Scenes/Effects/BP_Effect_%s" % n
                   for n in ("HazePot", "SmokePot", "SteamKettle", "FireBasket", "WingBurn", "Motes", "Candle"))
APIS = (("Emitter", None), ("GameplayStatics", "spawn_emitter_at_location"),
        ("NiagaraFunctionLibrary", "spawn_system_at_location"), ("ParticleSystemComponent", "set_float_parameter"),
        ("NiagaraComponent", "set_variable_float"))


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def read(obj, name):
    try:
        return True, obj.get_editor_property(name)
    except Exception as error:  # noqa: BLE001 - "not reachable" is the measurement
        return False, "%s: %s" % (type(error).__name__, error)


def cascade_row(path):
    row = {"path": path, "exists": bool(unreal.EditorAssetLibrary.does_asset_exist(path))}
    if not row["exists"]:
        return row
    asset = unreal.load_asset(path)
    row["class"] = asset.get_class().get_name() if asset else None
    ok, emitters = read(asset, "emitters")
    row["emitters_reachable"] = ok
    if not ok:
        row["emitters_error"] = emitters
        return row
    row["emitters"] = []
    for em in list(emitters or []):
        e = {"class": em.get_class().get_name() if em else None}
        ok_l, lods = read(em, "lod_levels")
        e["lods_reachable"] = ok_l
        if ok_l and lods:
            lod0 = lods[0]
            ok_m, modules = read(lod0, "modules")
            e["modules_reachable"] = ok_m
            e["modules"] = [m.get_class().get_name() for m in list(modules or [])] if ok_m else modules
            ok_s, spawn = read(lod0, "spawn_module")
            if ok_s and spawn is not None:
                ok_r, rate = read(spawn, "rate")
                e["spawn_rate_reachable"] = ok_r
                e["spawn_rate_type"] = type(rate).__name__ if ok_r else rate
        row["emitters"].append(e)
    return row


def niagara_row(path):
    row = {"path": path, "exists": bool(unreal.EditorAssetLibrary.does_asset_exist(path))}
    if row["exists"]:
        asset = unreal.load_asset(path)
        row["class"] = asset.get_class().get_name() if asset else None
        ok, handles = read(asset, "emitter_handles")
        row["emitter_handles_reachable"] = ok
        row["emitter_handles"] = len(handles) if ok and handles is not None else str(handles)
        ok_w, warm = read(asset, "warmup_time")
        row["warmup_time"] = float(warm) if ok_w else str(warm)
    return row


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    world_path = world.get_path_name().split(".", 1)[0] if world else None
    if world_path != EXPECTED_WORLD:
        unreal.log_error("FXPROBE_STOPPED|run=%s|WRONG_WORLD|%s" % (RUN, world_path))
        return
    before = census()
    report = {"run": RUN, "world": world_path, "pie_active": ed.get_game_world() is not None,
              "census_before": before}
    report["cascade"] = [cascade_row(p) for p in CASCADE]
    report["niagara"] = [niagara_row(p) for p in NIAGARA]
    report["effect_bps"] = {p: bool(unreal.EditorAssetLibrary.does_asset_exist(p)) for p in EFFECT_BPS}
    report["apis"] = {("%s.%s" % (c, f) if f else c): bool(hasattr(unreal, c) and (f is None or hasattr(getattr(
        unreal, c), f))) for c, f in APIS}
    after = census()
    report["census_after"] = after
    report["census_equal"] = after == before
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, default=str)
    if after != before:
        unreal.log_error("FXPROBE_STOPPED|run=%s|CENSUS_CHANGED|%s -> %s|Don't-Save restart if anything new is dirty"
                         % (RUN, before, after))
        return
    unreal.log("FXPROBE_OK|run=%s|cascade=%d|cascade_emitters_reachable=%d|niagara=%d|effect_bps=%s|census_equal=1|"
               "out=%s" % (RUN, len(report["cascade"]), sum(1 for r in report["cascade"] if r.get("emitters_reachable")),
                          len(report["niagara"]), sum(report["effect_bps"].values()), OUT))


main()
