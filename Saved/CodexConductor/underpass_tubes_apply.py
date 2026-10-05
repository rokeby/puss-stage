"""Underpass fluorescent tubes (Gary 5 Oct): "fluorescent light tubes along the top of the metal rig, two rows at the centre
top and a row on each top left and top right corner"; "only occasionally in use, having a dingy office light feel".
Layer built in a52051c (suite 166/0). First use: P02's failing stretch, bays 12-19 = stations 11-18.

Args (underpass_tubes_args.json): {"mode": "DRY"|"APPLY"|"REVERT", "structure": "...", "from_station": 11, "to_station": 18,
       "confirm": "<MODE> <structure>"}.
APPLY: guards (no PIE, clean census, tubes currently off) -> record (fsync) + umap backup -> CREATE-ONLY material
  M_UP_TubeEmissive (unlit, emissive = Colour * Intensity * PerInstanceCustomData[3] (alive)) and MI_UP_Tube_Office,
  each read back (never edits a pre-existing asset; reuses them only if they already exist from a previous run) ->
  set the Structure's tube fields -> MaterializeStructure -> IsStructureCurrent -> census must be the level plus
  the two new material packages only -> save them, then the level -> census clean.
  Marker UNDERPASS_TUBES_APPLY_OK|run=..; the INFINITY_STAGE_STRUCTURE_OK line after it carries the counts.
REVERT: restore the tube fields from the record, re-fit, save the level (the materials stay).
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
MATDIR = "/Game/InfinityStage/RigAtmos/Underpass/Materials"
MASTER = MATDIR + "/M_UP_TubeEmissive"
MI = MATDIR + "/MI_UP_Tube_Office"
OFFICE = {"Colour": (0.92, 1.0, 0.88, 1.0), "Intensity": 6.0}
FIELDS = ("tubes", "tube_mesh", "tube_material", "tube_from_station", "tube_to_station", "tube_corner_inset_cm",
          "tube_lights", "tube_light_function_material")
RUN = datetime.datetime.now().strftime("UPT-%Y%m%d-%H%M%S")
MEL = unreal.MaterialEditingLibrary


def stop(msg):
    unreal.log_error("UNDERPASS_TUBES_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def plain(s):
    out = {}
    for k in FIELDS:
        v = s.get_editor_property(k)
        out[k] = v if isinstance(v, (bool, int, float)) else (v.get_path_name() if v else None)
    return out


def ensure_materials():
    """CREATE-ONLY. Returns (mi_asset, created_package_names)."""
    created = []
    eal = unreal.EditorAssetLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    if not eal.does_asset_exist(MASTER):
        m = tools.create_asset("M_UP_TubeEmissive", MATDIR, unreal.Material, unreal.MaterialFactoryNew())
        if m is None:
            stop("MASTER_CREATE_FAILED")
        m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        m.set_editor_property("used_with_instanced_static_meshes", True)
        col = MEL.create_material_expression(m, unreal.MaterialExpressionVectorParameter, -600, 0)
        col.set_editor_property("parameter_name", "Colour")
        col.set_editor_property("default_value", unreal.LinearColor(*OFFICE["Colour"]))
        inten = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -600, 200)
        inten.set_editor_property("parameter_name", "Intensity")
        inten.set_editor_property("default_value", OFFICE["Intensity"])
        alive = MEL.create_material_expression(m, unreal.MaterialExpressionPerInstanceCustomData, -600, 350)
        alive.set_editor_property("data_index", 3)
        alive.set_editor_property("const_default_value", 1.0)
        mul1 = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -300, 100)
        mul2 = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -150, 200)
        links = [(col, "", mul1, "A"), (inten, "", mul1, "B"), (mul1, "", mul2, "A"), (alive, "", mul2, "B")]
        for a, ao, b, bi in links:
            MEL.connect_material_expressions(a, ao, b, bi)
        MEL.connect_material_property(mul2, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        MEL.recompile_material(m)
        # read-back: the emissive input must be the second multiply (judge by the graph, not by return values)
        got = MEL.get_material_property_input_node(m, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        if got is None or got.get_name() != mul2.get_name():
            stop("MASTER_EMISSIVE_NOT_WIRED")
        created.append(MASTER)
    master = unreal.load_asset(MASTER)
    if not eal.does_asset_exist(MI):
        mi = tools.create_asset("MI_UP_Tube_Office", MATDIR, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
        if mi is None:
            stop("MI_CREATE_FAILED")
        MEL.set_material_instance_parent(mi, master)
        MEL.set_material_instance_vector_parameter_value(mi, "Colour", unreal.LinearColor(*OFFICE["Colour"]))
        MEL.set_material_instance_scalar_parameter_value(mi, "Intensity", OFFICE["Intensity"])
        created.append(MI)
    mi = unreal.load_asset(MI)
    if mi.get_editor_property("parent") != master:
        stop("MI_PARENT_READBACK")
    got = MEL.get_material_instance_scalar_parameter_value(mi, "Intensity")
    if abs(got - OFFICE["Intensity"]) > 1e-4 and MI in created:
        stop("MI_INTENSITY_READBACK|%s" % got)
    return mi, created


def main():
    a = json.load(open(HERE + "underpass_tubes_args.json", encoding="utf-8"))
    mode, label = str(a.get("mode", "DRY")).upper(), str(a["structure"])
    if mode != "DRY" and a.get("confirm") != "%s %s" % (mode, label):
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    actors = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if str(x.get_actor_label()) == label]
    if len(actors) != 1:
        stop("STRUCTURE_COUNT|%d" % len(actors))
    actor = actors[0]
    under = actor.get_editor_property("underpass")
    before = plain(under)
    unreal.log("UNDERPASS_TUBES_START|run=%s|mode=%s|structure=%s|underpass_enabled=%s|before=%s"
               % (RUN, mode, label, under.get_editor_property("enabled"), json.dumps(before)))
    if mode == "DRY":
        if not under.get_editor_property("enabled"):
            stop("UNDERPASS_OFF")
        unreal.log("UNDERPASS_TUBES_DRY_OK|run=%s|stations=%s-%s|master_exists=%s|mi_exists=%s"
                   % (RUN, a.get("from_station"), a.get("to_station"),
                      unreal.EditorAssetLibrary.does_asset_exist(MASTER), unreal.EditorAssetLibrary.does_asset_exist(MI)))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    rec = HERE + "underpass_tubes_record_%s.json" % label.split()[-1]
    if mode == "APPLY":
        if before["tubes"]:
            stop("ALREADY_ON")
        if os.path.exists(rec):
            stop("RECORD_EXISTS|" + rec)
        backup = "E:/PussStage/Backups/PreUnderpassTubes-%s-%s" % (label.split()[-1], RUN)
        os.makedirs(backup)
        with open(rec, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "structure": label, "before": before, "backup": backup}, h, indent=1)
            h.flush()
            os.fsync(h.fileno())
        shutil.copy2(UMAP, backup)
        mi, created = ensure_materials()
        target = {"tubes": True, "tube_mesh": unreal.load_asset("/Engine/BasicShapes/Cylinder"), "tube_material": mi,
                  "tube_from_station": int(a["from_station"]), "tube_to_station": int(a["to_station"]),
                  "tube_corner_inset_cm": float(a.get("corner_inset_cm", 45.0)), "tube_lights": True,
                  "tube_light_function_material": unreal.load_asset("/Game/InfinityStage/Lighting/MI_LF_Flicker_Hum")}
    else:
        if not os.path.exists(rec):
            stop("NO_RECORD|" + rec)
        created = []
        b = json.load(open(rec, encoding="utf-8"))["before"]
        target = {k: (unreal.load_asset(v) if isinstance(v, str) else v) for k, v in b.items()}
    for k, v in target.items():
        under.set_editor_property(k, v)
    actor.modify()
    actor.set_editor_property("underpass", under)
    back = plain(actor.get_editor_property("underpass"))
    want = {k: (v.get_path_name() if hasattr(v, "get_path_name") else v) for k, v in target.items()}
    bad = {k: (back[k], want[k]) for k in want if back[k] != want[k]}
    if bad:
        stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(bad, default=str))
    if not actor.materialize_structure():
        stop("MATERIALIZE_FAILED|NOTHING SAVED; Don't-Save restart")
    if not actor.is_structure_current():
        stop("NOT_CURRENT|NOTHING SAVED; Don't-Save restart")
    dirty = census()
    allowed = sorted(set(created))
    if dirty["maps"] != [WORLD] or sorted(dirty["content"]) != allowed:
        stop("DIRTY_SCOPE|%s|allowed=%s|NOTHING SAVED; Don't-Save restart" % (json.dumps(dirty), allowed))
    for p in allowed:
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            stop("SAVE_ASSET_FAILED|" + p)
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_MAP_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    if mode == "REVERT":
        os.replace(rec, rec + ".reverted-" + RUN)
    unreal.log("UNDERPASS_TUBES_%s_OK|run=%s|structure=%s|after=%s|created=%s|saved=level+%d|dirty_after=0+0"
               % (mode, RUN, label, json.dumps(back), allowed, len(allowed)))


main()
