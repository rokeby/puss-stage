"""FX EFFECT BLUEPRINTS: DRY / APPLY / REVERT. Create the missing default Effect classes the C++ already looks for,
each carrying an EXISTING Cascade particle system, so Show Effect attachments of type Smoke / Motes render a real
plume / motes instead of the native greybox. OFFLINE-WRITTEN 7 Oct, never run in Unreal.

Gated on fx_content_probe.json (run it first): APPLY refuses unless the probe exists, is census-clean and found every
chosen template loadable as a ParticleSystem.

WHAT (CREATE-ONLY content, no Show / level / map write):
  /Game/Scenes/Effects/BP_Effect_SmokePot  parent AInfinityStageEffectSource; + ParticleSystemComponent "PlumeFX"
        (template /Game/Japanese_Alley/VFX/Humo_Par, or P_Smoke via args) at the nozzle, auto_activate False.
  /Game/Scenes/Effects/BP_Effect_Motes     parent AInfinityStageEffectSource; + ParticleSystemComponent "MotesFX"
        (template /Game/KK_S2_Shrine/StarterContent/Particles/P_Ambient_Dust), auto_activate False.
  The C++ resolves these paths by type (InfinityStageEffectSource.cpp:47-64) [declaration-proven] and, once they
  exist, loads them instead of the greybox (:123-144). It activates / deactivates EVERY UFXSystemComponent by camera
  distance (ActiveRadiusCm; :509-549) [declaration-proven] - Cascade's UParticleSystemComponent is a UFXSystemComponent
  [inferred from UE class hierarchy; the probe's class read + the first PIE confirm]. User.Pump is pushed with
  SetFloatParameter (:727-731); Cascade templates do not read it, so pumping is a no-op and the plume runs while the
  camera is in range [inferred: no ParticleParameter distribution named User.Pump in the templates' name tables].
  Builder route = fx_create_candle_assets.py (live-proven 3-4 Oct: create_blueprint_asset_with_parent,
  SubobjectDataSubsystem add_new_subobject + rename, compile, save_loaded_asset, subobject read-back) [precedent].

REVERT: deletes ONLY assets this tool's record created, and only when no Show Effect attachment references a Smoke /
Motes type that would then fall back (the DRY lists them); never touches the templates.
Args (fx_effect_bps_args.json): {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> FXEFFECTBPS",
 "types": ["SmokePot", "Motes"], "templates": {"SmokePot": "<cascade path>", ...}}
Markers FXEFFECTBPS_DRY_OK / _APPLY_OK / _REVERT_OK |run=..; stops FXEFFECTBPS_STOPPED|run=..|<reason>.
"""
import datetime
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "fx_effect_bps_args.json")
RECORD = os.path.join(HERE, "fx_effect_bps_record.json")
PROBE = os.path.join(HERE, "fx_content_probe.json")
ROOT = "/Game/Scenes/Effects"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CONFIRM_TAIL = "FXEFFECTBPS"
SPECS = {
    "SmokePot": {"bp": ROOT + "/BP_Effect_SmokePot", "component": "PlumeFX",
                 "template": "/Game/Japanese_Alley/VFX/Humo_Par", "loc": (0.0, 0.0, 90.0),
                 "alternatives": ("/Game/KK_S2_Shrine/StarterContent/Particles/P_Smoke",)},
    "Motes": {"bp": ROOT + "/BP_Effect_Motes", "component": "MotesFX",
              "template": "/Game/KK_S2_Shrine/StarterContent/Particles/P_Ambient_Dust", "loc": (0.0, 0.0, 0.0),
              "alternatives": ()},
}
RUN = datetime.datetime.now().strftime("FXBP-%Y%m%d-%H%M%S")


class FxBpError(RuntimeError):
    pass


def require(cond, msg):
    if not cond:
        raise FxBpError(str(msg))


# ------------------------------------------------------------------ pure
def check_args(raw):
    a = {"mode": "DRY", "types": ["SmokePot", "Motes"], "templates": {}}
    a.update(raw or {})
    a["mode"] = str(a["mode"]).upper()
    require(a["mode"] in ("DRY", "APPLY", "REVERT"), "MODE|%s" % a["mode"])
    if a["mode"] != "DRY":
        require(a.get("confirm") == "%s %s" % (a["mode"], CONFIRM_TAIL), "CONFIRM_MISSING|want '%s %s'"
                % (a["mode"], CONFIRM_TAIL))
    require(isinstance(a["types"], list) and a["types"] and set(a["types"]) <= set(SPECS)
            and len(set(a["types"])) == len(a["types"]), "TYPES|%r" % (a["types"],))
    for t, path in (a["templates"] or {}).items():
        require(t in a["types"], "TEMPLATE_FOR_UNCHOSEN_TYPE|%s" % t)
        require(path == SPECS[t]["template"] or path in SPECS[t]["alternatives"], "TEMPLATE_NOT_ALLOWED|%s|%s"
                % (t, path))
    return a


def plan(a):
    return [{"type": t, "bp": SPECS[t]["bp"], "component": SPECS[t]["component"],
             "template": (a["templates"] or {}).get(t, SPECS[t]["template"]), "loc": list(SPECS[t]["loc"])}
            for t in a["types"]]


def probe_gate(probe, rows):
    """-> list of refusals. The probe must be census-clean and have loaded each template as a ParticleSystem."""
    bad = []
    if not probe:
        return ["PROBE_MISSING|run fx_content_probe.py first"]
    if not probe.get("census_equal"):
        bad.append("PROBE_NOT_CLEAN")
    by = {r["path"]: r for r in probe.get("cascade", [])}
    for row in rows:
        r = by.get(row["template"])
        if not r or not r.get("exists") or r.get("class") != "ParticleSystem":
            bad.append("TEMPLATE_NOT_PROVEN|%s|%s" % (row["template"], r))
    if not probe.get("apis", {}).get("Emitter", False):
        bad.append("CASCADE_API_ABSENT|unreal.Emitter")
    return bad


# ------------------------------------------------------------------ Unreal
def _aid(v):
    return None if v is None else str(v.get_path_name()).split(".", 1)[0]


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(_aid(p) for p in lib.get_dirty_content_packages()),
            "maps": sorted(_aid(p) for p in lib.get_dirty_map_packages())}


def _build(row):
    bp = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(row["bp"], unreal.InfinityStageEffectSource)
    require(bp is not None, "CREATE_BP_FAILED|%s" % row["bp"])
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = {str(lib.get_variable_name(lib.get_data(h))): h for h in sds.k2_gather_subobject_data_for_blueprint(bp)}
    parent = handles.get("TrackingRoot")
    require(parent is not None, "NO_TRACKING_ROOT|%s" % sorted(handles))
    handle, reason = sds.add_new_subobject(unreal.AddNewSubobjectParams(
        parent_handle=parent, new_class=unreal.ParticleSystemComponent, blueprint_context=bp))
    require(lib.is_handle_valid(handle), "ADD_COMPONENT_FAILED|%s" % reason)
    sds.rename_subobject(handle, unreal.Text(row["component"]))
    comp = lib.get_associated_object(lib.get_data(handle))
    template = unreal.load_asset(row["template"])
    require(isinstance(template, unreal.ParticleSystem), "TEMPLATE_LOAD|%s" % row["template"])
    comp.set_editor_property("template", template)
    comp.set_editor_property("auto_activate", False)
    comp.set_editor_property("relative_location", unreal.Vector(*row["loc"]))
    require(unreal.BlueprintEditorLibrary.compile_blueprint(bp), "COMPILE_FAILED|%s" % row["bp"])
    require(unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False), "SAVE_FAILED|%s" % row["bp"])
    return bp


def _readback(row):
    rbp = unreal.load_asset(row["bp"])
    require(rbp is not None, "READBACK_LOAD|%s" % row["bp"])
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    found = None
    for h in sds.k2_gather_subobject_data_for_blueprint(rbp):
        data = lib.get_data(h)
        if str(lib.get_variable_name(data)) == row["component"]:
            obj = lib.get_object_for_blueprint(data, rbp) or lib.get_associated_object(data)
            found = obj
    require(isinstance(found, unreal.ParticleSystemComponent), "READBACK_COMPONENT|%s" % row["bp"])
    got = {"template": _aid(found.get_editor_property("template")),
           "auto_activate": bool(found.get_editor_property("auto_activate")),
           "parent_class": _aid(unreal.EditorAssetLibrary.load_blueprint_class(row["bp"]))}
    require(got["template"] == row["template"] and got["auto_activate"] is False,
            "READBACK_MISMATCH|%s|%s" % (row["bp"], got))
    return got


def main():
    a = check_args(json.load(open(ARGS, encoding="utf-8")) if os.path.exists(ARGS) else {})
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(ed.get_game_world() is None, "PIE_ACTIVE")
    require(_aid(ed.get_editor_world()) == EXPECTED_WORLD, "WRONG_WORLD")
    rows = plan(a)
    eal = unreal.EditorAssetLibrary
    exists = {r["bp"]: bool(eal.does_asset_exist(r["bp"])) for r in rows}
    probe = json.load(open(PROBE, encoding="utf-8")) if os.path.exists(PROBE) else None
    gate = probe_gate(probe, rows)
    unreal.log("FXEFFECTBPS_PLAN|run=%s|mode=%s|rows=%s|exists=%s|gate=%s" % (RUN, a["mode"], rows, exists, gate))
    if a["mode"] == "DRY":
        unreal.log("FXEFFECTBPS_DRY_OK|run=%s|rows=%d|existing=%d|gate_refusals=%d"
                   % (RUN, len(rows), sum(exists.values()), len(gate)))
        return
    require(_census() == {"content": [], "maps": []}, "DIRTY_BEFORE|%s" % _census())
    if a["mode"] == "APPLY":
        require(not gate, "GATE|%s" % gate)
        require(not any(exists.values()), "TARGET_EXISTS|%s" % exists)
        require(not os.path.exists(RECORD), "RECORD_EXISTS|" + RECORD)
        record = {"run": RUN, "args": a, "rows": rows, "created": [], "readback": {}}
        with open(RECORD, "w", encoding="utf-8") as h:
            json.dump(record, h, indent=1)
            h.flush()
            os.fsync(h.fileno())
        for row in rows:
            _build(row)
            record["created"].append(row["bp"])
            record["readback"][row["bp"]] = _readback(row)
            with open(RECORD, "w", encoding="utf-8") as h:
                json.dump(record, h, indent=1)
        after = _census()
        require(after == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % after)
        unreal.log("FXEFFECTBPS_APPLY_OK|run=%s|created=%s|readback=1|dirty_after=0+0" % (RUN, record["created"]))
        return
    require(os.path.exists(RECORD), "NO_RECORD")
    rec = json.load(open(RECORD, encoding="utf-8"))
    for path in rec["created"]:
        refs = unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)
        require(not refs, "REFERENCED|%s|%s" % (path, refs))
        require(unreal.EditorAssetLibrary.delete_asset(path), "DELETE_FAILED|%s" % path)
    os.replace(RECORD, RECORD + ".reverted-" + RUN)
    unreal.log("FXEFFECTBPS_REVERT_OK|run=%s|deleted=%s" % (RUN, rec["created"]))


if unreal is not None and __name__ in ("__main__", "__fx_effect_bps_runner__"):
    try:
        main()
    except FxBpError as error:
        unreal.log_error("FXEFFECTBPS_STOPPED|run=%s|%s|check census; Don't-Save restart if anything is dirty"
                         % (RUN, error))
        raise
