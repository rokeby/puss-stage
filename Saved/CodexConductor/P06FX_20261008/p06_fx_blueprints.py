"""DRY/APPLY/REVERT the complete default Effect Blueprint set.

Existing matching assets are verified and never edited. Missing assets are
create-only children of AInfinityStageEffectSource. With the default
fire_particle_light_enabled=false, P_Fire is duplicated to a private template
and every nested ParticleModuleLight gets SpawnFraction=0 plus HQ/shadows off;
the source StarterContent asset is never touched.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p06_fx_common as C  # noqa: E402

unreal = C.unreal
RUN = C.stamp("P06FXBPS")
ARGS = os.path.join(HERE, "p06_fx_blueprints_args.json")
PROBE = os.path.join(HERE, "p06_fx_probe_report.json")
RECORD = os.path.join(HERE, "p06_fx_blueprints_record.json")
REPORT = os.path.join(HERE, "p06_fx_blueprints_report.json")


def rows_for(args):
    rows = []
    for name in args["types"]:
        row = dict(C.D.EFFECT_SPECS[name])
        row["name"] = name
        if name in ("FireBasket", "WingBurn") and args["fire_particle_light_enabled"]:
            row["template"] = C.D.FIRE_SOURCE
        rows.append(row)
    return rows


def gate(probe, rows, fire_light_enabled):
    bad = []
    if not probe:
        return ["PROBE_MISSING"]
    if not probe.get("census_equal"):
        bad.append("PROBE_CENSUS")
    if not probe.get("cascade_render", {}).get("confirmed"):
        bad.append("CASCADE_RENDER_UNPROVEN")
    by_path = {r["path"]: r for r in probe.get("particle_assets", [])}
    for row in rows:
        source = C.D.FIRE_SOURCE if row["template"] == C.D.FIRE_NO_LIGHT else row["template"]
        if by_path.get(source, {}).get("class") != "ParticleSystem":
            bad.append("TEMPLATE_UNPROVEN|" + source)
    if not fire_light_enabled:
        light = probe.get("fire_particle_light", {})
        if not light.get("readable") or not light.get("modules"):
            bad.append("FIRE_LIGHT_MODULE_UNREADABLE")
    return bad


def _objects_with_outer(asset):
    C.require(hasattr(unreal, "get_objects_with_outer"), "OBJECTS_WITH_OUTER_API")
    try:
        return list(unreal.get_objects_with_outer(asset, include_nested_objects=True))
    except TypeError:
        return list(unreal.get_objects_with_outer(asset, True))


def _light_modules(asset):
    return [obj for obj in _objects_with_outer(asset)
            if obj and obj.get_class().get_name() == "ParticleModuleLight"]


def _fire_light_readback(asset):
    out = []
    for module in _light_modules(asset):
        out.append({"path": str(module.get_path_name()),
                    "spawn_fraction": float(module.get_editor_property("spawn_fraction")),
                    "high_quality_lights": bool(module.get_editor_property("high_quality_lights")),
                    "shadow_casting_lights": bool(module.get_editor_property("shadow_casting_lights"))})
    return out


def _create_no_light_fire():
    eal = unreal.EditorAssetLibrary
    C.require(not eal.does_asset_exist(C.D.FIRE_NO_LIGHT), "FIRE_PRIVATE_EXISTS")
    asset = eal.duplicate_asset(C.D.FIRE_SOURCE, C.D.FIRE_NO_LIGHT)
    C.require(asset is not None, "FIRE_DUPLICATE_FAILED")
    modules = _light_modules(asset)
    C.require(modules, "FIRE_LIGHT_MODULE_NOT_FOUND")
    for module in modules:
        module.set_editor_property("spawn_fraction", 0.0)
        module.set_editor_property("high_quality_lights", False)
        module.set_editor_property("shadow_casting_lights", False)
    C.require(eal.save_loaded_asset(asset, only_if_is_dirty=False), "FIRE_PRIVATE_SAVE")
    rb = _fire_light_readback(unreal.load_asset(C.D.FIRE_NO_LIGHT))
    C.require(rb and all(abs(r["spawn_fraction"]) <= 1e-8
                         and not r["high_quality_lights"] and not r["shadow_casting_lights"] for r in rb),
              "FIRE_LIGHT_READBACK|" + json.dumps(rb, sort_keys=True))
    return rb


def _subobject_component(bp, variable):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    for handle in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = lib.get_data(handle)
        if str(lib.get_variable_name(data)) == variable:
            return lib.get_object_for_blueprint(data, bp) or lib.get_associated_object(data)
    return None


def _readback(row):
    bp = unreal.load_asset(row["bp"])
    C.require(bp is not None, "BP_LOAD|" + row["bp"])
    parent = bp.get_editor_property("parent_class")
    parent_path = str(parent.get_path_name()) if parent is not None else ""
    C.require(parent_path == "/Script/InfinityStage.InfinityStageEffectSource",
              "BP_PARENT|%s|%s" % (row["bp"], parent_path))
    comp = _subobject_component(bp, row["component"])
    C.require(isinstance(comp, unreal.ParticleSystemComponent), "BP_COMPONENT|" + row["bp"])
    got = {"parent": parent_path, "component": row["component"],
           "template": C.asset_id(comp.get_editor_property("template")),
           "auto_activate": bool(comp.get_editor_property("auto_activate")),
           "relative_location": [float(comp.get_editor_property("relative_location").x),
                                 float(comp.get_editor_property("relative_location").y),
                                 float(comp.get_editor_property("relative_location").z)]}
    C.require(got["template"] == row["template"] and got["auto_activate"] is False,
              "BP_READBACK|%s|%s" % (row["bp"], json.dumps(got, sort_keys=True)))
    return got


def _build(row):
    bp = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(row["bp"], unreal.InfinityStageEffectSource)
    C.require(bp is not None, "BP_CREATE|" + row["bp"])
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = {str(lib.get_variable_name(lib.get_data(h))): h
               for h in sds.k2_gather_subobject_data_for_blueprint(bp)}
    C.require(handles.get("TrackingRoot") is not None, "TRACKING_ROOT|" + row["bp"])
    handle, reason = sds.add_new_subobject(unreal.AddNewSubobjectParams(
        parent_handle=handles["TrackingRoot"], new_class=unreal.ParticleSystemComponent, blueprint_context=bp))
    C.require(lib.is_handle_valid(handle), "ADD_COMPONENT|%s|%s" % (row["bp"], reason))
    sds.rename_subobject(handle, unreal.Text(row["component"]))
    comp = lib.get_associated_object(lib.get_data(handle))
    template = unreal.load_asset(row["template"])
    C.require(isinstance(template, unreal.ParticleSystem), "TEMPLATE_LOAD|" + row["template"])
    comp.set_editor_property("template", template)
    comp.set_editor_property("auto_activate", False)
    comp.set_editor_property("relative_location", unreal.Vector(*row["loc"]))
    C.require(unreal.BlueprintEditorLibrary.compile_blueprint(bp), "BP_COMPILE|" + row["bp"])
    C.require(unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False), "BP_SAVE|" + row["bp"])
    return _readback(row)


def _external_refs(path, created):
    refs = [str(x).split(".", 1)[0] for x in unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)]
    return sorted(r for r in refs if r not in created and r != path)


def main():
    try:
        args = C.D.validate_blueprints(C.read_json(ARGS))
    except C.D.ConfigError as error:
        raise C.ToolError(str(error))
    C.editor_guard()
    before = C.require_clean("PRE")
    rows = rows_for(args)
    probe = C.read_json(PROBE) if os.path.isfile(PROBE) else None
    refusals = gate(probe, rows, args["fire_particle_light_enabled"])
    exists = {row["bp"]: bool(unreal.EditorAssetLibrary.does_asset_exist(row["bp"])) for row in rows}
    private_exists = bool(unreal.EditorAssetLibrary.does_asset_exist(C.D.FIRE_NO_LIGHT))
    plan = {"rows": rows, "existing": exists, "private_fire_exists": private_exists,
            "fire_particle_light_enabled": args["fire_particle_light_enabled"], "gate_refusals": refusals}
    if args["mode"] == "DRY":
        verified = {row["bp"]: _readback(row) for row in rows if exists[row["bp"]]}
        C.require(C.census() == before, "DRY_CENSUS")
        C.write_json(REPORT, {"run": RUN, "mode": "DRY", "plan": plan, "verified": verified,
                              "census_before": before, "census_after": C.census()})
        unreal.log("P06FXBPS_DRY_OK|run=%s|create=%d|verify=%d|gate_refusals=%d|fire_particle_light=%s" %
                   (RUN, sum(not x for x in exists.values()), sum(exists.values()), len(refusals),
                    "on" if args["fire_particle_light_enabled"] else "off"))
        return
    if args["mode"] == "APPLY":
        C.require(not refusals, "GATE|" + ";".join(refusals))
        C.require(not os.path.exists(RECORD), "RECORD_EXISTS")
        need_private = (not args["fire_particle_light_enabled"]
                        and any(r["name"] in ("FireBasket", "WingBurn") for r in rows))
        if need_private:
            C.require(not private_exists, "PRIVATE_FIRE_EXISTS_UNRECORDED")
        source_packages = sorted({C.D.FIRE_SOURCE if r["template"] == C.D.FIRE_NO_LIGHT else r["template"]
                                  for r in rows})
        backup = C.backup("PreP06FxBlueprints", RUN, source_packages,
                          "Source Cascade assets copied for provenance; targets are create-only and absent.")
        record = {"run": RUN, "status": "prepared", "args": args, "plan": plan, "backup": backup,
                  "created": [], "readback": {}}
        C.write_json(RECORD, record, exclusive=True)  # before first Content mutation
        if need_private:
            record["created"].append(C.D.FIRE_NO_LIGHT)
            C.write_json(RECORD, record)  # claim deterministic absent target before mutation
            record["fire_light_readback"] = _create_no_light_fire()
            C.write_json(RECORD, record)
        for row in rows:
            if exists[row["bp"]]:
                record["readback"][row["bp"]] = _readback(row)
                continue
            record["created"].append(row["bp"])
            C.write_json(RECORD, record)  # claim deterministic absent target before mutation
            record["readback"][row["bp"]] = _build(row)
            C.write_json(RECORD, record)
        C.require_clean("POST_APPLY")
        record["status"] = "applied"
        C.write_json(RECORD, record)
        C.write_json(REPORT, {"run": RUN, "mode": "APPLY", "created": record["created"],
                              "readback": record["readback"], "backup": backup, "census_after": C.census()})
        unreal.log("P06FXBPS_APPLY_OK|run=%s|created=%d|verified=%d|fire_particle_light=%s|backup=%s|dirty_after=0+0" %
                   (RUN, len(record["created"]), len(record["readback"]),
                    "on" if args["fire_particle_light_enabled"] else "off", backup["root"]))
        return
    C.require(os.path.isfile(RECORD), "RECORD_MISSING")
    record = C.read_json(RECORD)
    C.require(record.get("status") in ("prepared", "applied"), "RECORD_STATUS")
    claimed = list(record.get("created", []))
    created = [p for p in claimed if unreal.EditorAssetLibrary.does_asset_exist(p)]
    backup = (C.backup("PreP06FxBlueprintsRevert", RUN, created,
                       "Exact created assets before confirmed permanent REVERT deletion.")
              if created else None)
    record["revert_intent"] = {"run": RUN, "backup": backup, "delete": created,
                               "claimed_but_absent": sorted(set(claimed) - set(created))}
    C.write_json(RECORD, record)
    for path in reversed(created):
        C.require(not _external_refs(path, set(claimed)), "EXTERNAL_REFS|%s|%s" % (path, _external_refs(path, set(claimed))))
        C.require(unreal.EditorAssetLibrary.delete_asset(path), "DELETE|" + path)
    C.require_clean("POST_REVERT")
    archived = C.archive_record(RECORD, RUN)
    C.write_json(REPORT, {"run": RUN, "mode": "REVERT", "claimed": claimed, "deleted": created,
                          "backup": backup, "archived_record": archived, "census_after": C.census()})
    unreal.log("P06FXBPS_REVERT_OK|run=%s|deleted=%d|backup=%s|record=%s|dirty_after=0+0" %
               (RUN, len(created), backup["root"] if backup else "none", archived))


if unreal is not None and __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001
        unreal.log_error("P06FXBPS_STOPPED|run=%s|%s|do not Save All; inspect exact census" % (RUN, error))
        raise
