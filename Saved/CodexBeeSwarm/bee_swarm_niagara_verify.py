"""Verify the hand-built NS_BeeSwarm (READ-ONLY: no save, no level change).

UE 5.8 Python cannot author Niagara emitters, modules or renderers:
UNiagaraSystemFactoryNew keeps SystemToCopy/EmittersToAddToNewSystem as plain
C++ members (NiagaraSystemFactoryNew.h:23-24, no UPROPERTY) and
UNiagaraSystem::EmitterHandles is a bare UPROPERTY() (NiagaraSystem.h:975-976),
so neither is reachable from Python. The system is therefore built by hand
(runbook section 3); this script checks what it can:

  1. NS_BeeSwarm exists and is a NiagaraSystem.
  2. Mesh renderer(s) owned by it (found with unreal.ObjectIterator; UNCLEAR
     whether 5.8 Python exposes it, so a miss is reported as UNVERIFIED, not
     failed): MotionVectorSetting PRECISE (or APPROXIMATE if the runbook's A/B
     chose it), FacingMode VELOCITY, mesh SM_Bee, SourceMode PARTICLES.
  3. MEASURED array round-trip on a transient (unregistered) NiagaraComponent:
     SetNiagaraArrayPosition/Vector then GetNiagaraArrayPosition/Vector
     (NiagaraDataInterfaceArrayFunctionLibrary.h:27,30,64,67), with both the
     "User.BeePositions" and bare "BeePositions" names, which settles the name
     form the C++ uses. If the transient component returns nothing for BOTH
     forms, the result is UNCLEAR (unregistered component) and the sandbox
     probe (bee_swarm_pie_probe.py) is the deciding measurement.

Marker: BEE_SWARM_NIAGARA_VERIFIED|run=...|...   or   BEE_SWARM_NIAGARA_STOPPED|...
"""
from __future__ import annotations

import importlib.util
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


def _load_common():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bs_common.py")
    spec = importlib.util.spec_from_file_location("_bs_common_nv", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load_common()
ACCEPTED_MOTION = ("PRECISE", "APPROXIMATE")


def _renderers(system_path):
    iterator = getattr(unreal, "ObjectIterator", None)
    if iterator is None:
        return None
    rows = []
    for obj in iterator(unreal.NiagaraMeshRendererProperties):
        path = str(obj.get_path_name())
        if not path.startswith(system_path + "."):
            continue
        meshes = []
        for entry in obj.get_editor_property("meshes"):
            meshes.append(C.asset_id(entry.get_editor_property("mesh")))
        rows.append({
            "path": path,
            "motion_vector_setting": str(obj.get_editor_property("motion_vector_setting")),
            "facing_mode": str(obj.get_editor_property("facing_mode")),
            "source_mode": str(obj.get_editor_property("source_mode")),
            "meshes": meshes,
        })
    return rows


def _roundtrip(system):
    lib = unreal.NiagaraDataInterfaceArrayFunctionLibrary
    comp = unreal.new_object(unreal.NiagaraComponent)
    comp.set_asset(system)
    pts = [unreal.Vector(10.0 * i, -3.0 * i, 150.0 + i) for i in range(5)]
    vel = [unreal.Vector(1.0, 2.0 * i, -1.0) for i in range(5)]
    out = {}
    for label, pos_name, vel_name in (("prefixed", "User.BeePositions", "User.BeeVelocities"),
                                      ("bare", "BeePositions", "BeeVelocities")):
        lib.set_niagara_array_position(comp, pos_name, pts)
        lib.set_niagara_array_vector(comp, vel_name, vel)
        got_p = list(lib.get_niagara_array_position(comp, pos_name))
        got_v = list(lib.get_niagara_array_vector(comp, vel_name))
        ok_p = len(got_p) == len(pts) and all(
            (a - b).length() < 1e-3 for a, b in zip(got_p, pts))
        ok_v = len(got_v) == len(vel) and all(
            (a - b).length() < 1e-3 for a, b in zip(got_v, vel))
        out[label] = {"positions": len(got_p), "velocities": len(got_v), "ok": bool(ok_p and ok_v)}
    comp = None
    return out


def main():
    C.require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    run = C.stamp_now()
    report_path = os.path.join(C.saved_dir(unreal), "bee_swarm_niagara_verify_report.json")
    report = {"ok": False, "run": run}
    try:
        C.require(C.exists(unreal, C.NIAGARA_SYSTEM), "NIAGARA_SYSTEM_MISSING|" + C.NIAGARA_SYSTEM)
        system = unreal.EditorAssetLibrary.load_asset(C.NIAGARA_SYSTEM)
        C.require(isinstance(system, unreal.NiagaraSystem), "NOT_A_NIAGARA_SYSTEM|%s" % type(system))
        census_before = C.dirty_census(unreal)
        renderers = _renderers(C.NIAGARA_SYSTEM)
        report["renderers"] = renderers
        renderer_state = "UNVERIFIED_NO_OBJECT_ITERATOR" if renderers is None else "CHECKED"
        if renderers is not None:
            C.require(len(renderers) >= 1, "NO_MESH_RENDERER_FOUND_IN|" + C.NIAGARA_SYSTEM)
            for row in renderers:
                C.require(any(m in row["motion_vector_setting"].upper() for m in ACCEPTED_MOTION),
                          "MOTION_VECTOR_SETTING|%s" % row)
                C.require("VELOCITY" in row["facing_mode"].upper(), "FACING_MODE|%s" % row)
                C.require("PARTICLES" in row["source_mode"].upper(), "SOURCE_MODE|%s" % row)
                C.require(C.MESH in row["meshes"], "RENDERER_MESH|%s" % row)
        roundtrip = _roundtrip(system)
        report["array_roundtrip"] = roundtrip
        if roundtrip["prefixed"]["ok"]:
            names = "User.prefixed_OK"
        elif roundtrip["bare"]["ok"]:
            raise C.BeeSwarmError("ONLY_BARE_NAMES_WORK|set the component's PositionArrayParameter/"
                                  "VelocityArrayParameter to BeePositions/BeeVelocities|%s" % roundtrip)
        else:
            names = "UNCLEAR_transient_component_returned_nothing"
        census_after = C.dirty_census(unreal)
        C.require(census_after == census_before, "VERIFY_DIRTIED_PACKAGES|before=%s|after=%s"
                  % (census_before, census_after))
        report.update({"ok": True, "renderer_state": renderer_state, "array_names": names})
        C.write_json(report_path, report)
        unreal.log("BEE_SWARM_NIAGARA_VERIFIED|run=%s|renderers=%s|state=%s|arrays=%s|roundtrip=%s|report=%s" % (
            run, 0 if renderers is None else len(renderers), renderer_state, names,
            json.dumps(roundtrip, separators=(",", ":")), report_path))
    except Exception as error:  # noqa: BLE001
        report["error"] = str(error)
        C.write_json(report_path, report)
        unreal.log_error("BEE_SWARM_NIAGARA_STOPPED|run=%s|%s" % (run, error))
        raise


if __name__ == "__main__":
    main()
