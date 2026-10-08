"""Read-only UE 5.8 FX inventory and controlled Cascade-render evidence probe.

It never spawns, edits, compiles, saves, or starts/stops PIE. It lists every
ParticleSystem/NiagaraSystem/NiagaraEmitter asset under /Game, inventories the
six Effect BP paths, reads P_Fire's nested ParticleModuleLight when the wrapper
exposes it, and verifies the prior controlled P04 rain evidence on disk.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p06_fx_common as C

unreal = C.unreal
RUN = C.stamp("P06FXPROBE")


def particle_rows(asset_data_rows):
    wanted = {"ParticleSystem", "NiagaraSystem", "NiagaraEmitter"}
    rows = []
    for data in asset_data_rows:
        cls = str(data.asset_class_path.asset_name)
        if cls in wanted:
            rows.append({"path": str(data.package_name), "name": str(data.asset_name), "class": cls})
    return sorted(rows, key=lambda r: (r["class"], r["path"]))


def render_evidence(path, exists=os.path.isfile, loader=C.read_json, hasher=C.sha256):
    if not exists(path):
        return {"confirmed": False, "reason": "MANIFEST_MISSING", "path": path}
    doc = loader(path)
    analysis = doc.get("analysis") or {}
    verdict = analysis.get("verdict") or {}
    valid = [r for r in analysis.get("rows", []) if r.get("valid")]
    controlled = any(r.get("seen", {}).get("ctrl") is True
                     and r.get("seen", {}).get("rain") is True
                     and r.get("seen", {}).get("rain_noparticles") is False
                     and r.get("rain_attributable") is True for r in valid)
    confirmed = (doc.get("run_id") == "P04RAINPIE-20261007-063520"
                 and verdict.get("rain") == "RENDERS"
                 and int(verdict.get("valid_stills", 0)) >= 1 and controlled
                 and not doc.get("errors") and not doc.get("problems"))
    return {"confirmed": confirmed, "kind": "prior_controlled_render_measurement",
            "run": doc.get("run_id"), "verdict": verdict, "controlled_valid_row": controlled,
            "manifest_sha256": hasher(path), "path": path}


def fire_light_row(asset):
    out = {"objects_api": bool(hasattr(unreal, "get_objects_with_outer")), "modules": []}
    if not out["objects_api"] or asset is None:
        return out
    try:
        objects = unreal.get_objects_with_outer(asset, include_nested_objects=True)
    except TypeError:
        objects = unreal.get_objects_with_outer(asset, True)
    for obj in objects:
        if obj and obj.get_class().get_name() == "ParticleModuleLight":
            row = {"path": str(obj.get_path_name())}
            for prop in ("spawn_fraction", "high_quality_lights", "shadow_casting_lights"):
                try:
                    row[prop] = obj.get_editor_property(prop)
                except Exception as error:  # noqa: BLE001 - report wrapper reachability
                    row[prop + "_error"] = "%s: %s" % (type(error).__name__, error)
            out["modules"].append(row)
    out["readable"] = bool(out["modules"] and all("spawn_fraction" in r for r in out["modules"]))
    return out


def main():
    C.editor_guard()
    before = C.census()
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = particle_rows(registry.get_assets_by_path("/Game", recursive=True, include_only_on_disk_assets=False))
    fire = unreal.load_asset(C.D.FIRE_SOURCE)
    root = C.saved_here()
    manifest = os.path.normpath(os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor", "Effects_20261007", "P04RainPIE", "P04RAINPIE-20261007-063520", "manifest.json"))
    report = {
        "run": RUN,
        "world": C.D.EXPECTED_WORLD,
        "engine": str(unreal.SystemLibrary.get_engine_version()),
        "particle_assets": assets,
        "counts": {k: sum(r["class"] == k for r in assets)
                   for k in ("ParticleSystem", "NiagaraSystem", "NiagaraEmitter")},
        "effect_bps": {name: bool(unreal.EditorAssetLibrary.does_asset_exist(spec["bp"]))
                       for name, spec in C.D.EFFECT_SPECS.items()},
        "fire_particle_light": fire_light_row(fire),
        "cascade_render": render_evidence(manifest),
        "census_before": before,
    }
    report["census_after"] = C.census()
    report["census_equal"] = report["census_after"] == before
    C.write_json(os.path.join(root, "p06_fx_probe_report.json"), report)
    C.require(report["census_equal"], "CENSUS_CHANGED")
    C.require(report["cascade_render"]["confirmed"], "CASCADE_RENDER_EVIDENCE_NOT_CONFIRMED")
    unreal.log("P06FXPROBE_OK|run=%s|cascade=%d|niagara_systems=%d|niagara_emitters=%d|render=confirmed|census_equal=1|out=%s" %
               (RUN, report["counts"]["ParticleSystem"], report["counts"]["NiagaraSystem"],
                report["counts"]["NiagaraEmitter"], os.path.join(root, "p06_fx_probe_report.json")))


if unreal is not None and __name__ in ("__main__", "__p06_fx_probe_runner__"):
    try:
        main()
    except Exception as error:  # noqa: BLE001
        unreal.log_error("P06FXPROBE_STOPPED|run=%s|%s" % (RUN, error))
        raise
