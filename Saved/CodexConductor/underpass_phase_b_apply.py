"""Underpass Phase B: switch the new Underpass layer on for one Structure (Gary 5 Oct: "Is big metal rig in?" -> build
approved; P05 first). Layer built in 94245bd (suite 152/0).

Args: underpass_phase_b_args.json {"mode": "DRY"|"APPLY"|"REVERT", "structure": "Infinity Stage - Structure 05",
       "confirm": "<MODE> <structure>" (APPLY/REVERT)}.
DRY    read-only: prints the current Underpass struct and the plan.
APPLY  guards (no PIE, clean census, struct currently disabled) -> originals JSON (fsync) + umap backup BEFORE change ->
       set the kit meshes/MIs, enabled -> modify(), set struct, read back -> MaterializeStructure -> IsStructureCurrent ->
       census must be exactly the level -> save level only -> census clean. Marker UNDERPASS_B_APPLY_OK|run=..
       (the INFINITY_STAGE_STRUCTURE_OK line after it carries the counts; the conductor checks them).
REVERT restores the struct from the originals JSON, re-fits, saves the level only.
Never Save All; never touches anything but the one Structure's Underpass struct.
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
MESH = "/Game/InfinityStage/RigAtmos/Underpass/Meshes/"
MAT = "/Game/InfinityStage/RigAtmos/Underpass/Materials/"
PLAN = {  # field -> value (soft refs as asset paths)
    "column_mesh": MESH + "SM_UP_LacedColumn", "column_material": MAT + "MI_UP_Steel_Green",
    "pier_mesh": MESH + "SM_UP_PierBase", "pier_material": MAT + "MI_UP_Concrete",
    "knee_mesh": MESH + "SM_UP_KneeBracket", "knee_material": MAT + "MI_UP_Steel_Green",
    "deck_mesh": MESH + "SM_UP_DeckBay", "deck_material": MAT + "MI_UP_Steel_Black",
    "catwalk_mesh": MESH + "SM_UP_CatwalkRail", "catwalk_material": MAT + "MI_UP_Steel_Green",
}
FLAGS = {"enabled": True, "columns": True, "knees": True, "deck": True, "catwalk": False}
RUN = datetime.datetime.now().strftime("UPB-%Y%m%d-%H%M%S")


def stop(msg):
    unreal.log_error("UNDERPASS_B_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def plain(struct):
    out = {}
    for name in list(PLAN) + list(FLAGS) + ["column_every", "mirror_knees", "column_cast_shadow", "pier_cast_shadow",
                                             "knee_cast_shadow", "deck_cast_shadow", "catwalk_cast_shadow"]:
        v = struct.get_editor_property(name)
        if isinstance(v, (bool, int, float)):
            out[name] = v
        else:
            out[name] = v.get_path_name() if v else None
    return out


def load(path):
    a = unreal.load_asset(path)
    if a is None:
        stop("ASSET_MISSING|" + path)
    return a


def set_fields(actor, values):
    s = actor.get_editor_property("underpass")
    for k, v in values.items():
        if k in PLAN or (k.endswith("_mesh") or k.endswith("_material")):
            s.set_editor_property(k, load(v) if v else None)
        else:
            s.set_editor_property(k, v)
    actor.modify()
    actor.set_editor_property("underpass", s)
    back = plain(actor.get_editor_property("underpass"))
    def want(k, v):
        if k.endswith("_mesh") or k.endswith("_material"):
            return load(v).get_path_name() if v else None
        return v
    bad = {k: (back.get(k), v) for k, v in values.items() if back.get(k) != want(k, v)}
    if bad:
        stop("READBACK|" + json.dumps(bad, default=str))


def main():
    args = json.load(open(HERE + "underpass_phase_b_args.json", encoding="utf-8"))
    mode = str(args.get("mode", "DRY")).upper()
    label = str(args["structure"])
    if mode != "DRY" and args.get("confirm") != "%s %s" % (mode, label):
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if str(a.get_actor_label()) == label]
    if len(actors) != 1:
        stop("STRUCTURE_COUNT|%d" % len(actors))
    actor = actors[0]
    before = plain(actor.get_editor_property("underpass"))
    unreal.log("UNDERPASS_B_START|run=%s|mode=%s|structure=%s|before=%s" % (RUN, mode, label, json.dumps(before)))
    if mode == "DRY":
        for p in PLAN.values():
            load(p)
        unreal.log("UNDERPASS_B_DRY_OK|run=%s|plan=%s|flags=%s" % (RUN, json.dumps(PLAN), json.dumps(FLAGS)))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    rec_path = HERE + "underpass_phase_b_record_%s.json" % label.split()[-1]
    if mode == "APPLY":
        if before["enabled"]:
            stop("ALREADY_ENABLED")
        if os.path.exists(rec_path):
            stop("RECORD_EXISTS|" + rec_path)
        backup = "E:/PussStage/Backups/PreUnderpassB-%s-%s" % (label.split()[-1], RUN)
        os.makedirs(backup)
        with open(rec_path, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "structure": label, "before": before, "backup": backup}, h, indent=1)
            h.flush()
            os.fsync(h.fileno())
        shutil.copy2(UMAP, backup)
        target = dict(PLAN)
        target.update(FLAGS)
    else:
        if not os.path.exists(rec_path):
            stop("NO_RECORD|" + rec_path)
        target = json.load(open(rec_path, encoding="utf-8"))["before"]
    set_fields(actor, target)
    if not actor.materialize_structure():
        stop("MATERIALIZE_FAILED|NOTHING SAVED; Don't-Save restart")
    if not actor.is_structure_current():
        stop("NOT_CURRENT|NOTHING SAVED; Don't-Save restart")
    dirty = census()
    if dirty["content"] or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    after = plain(actor.get_editor_property("underpass"))
    if mode == "REVERT":
        os.replace(rec_path, rec_path + ".reverted-" + RUN)
    unreal.log("UNDERPASS_B_%s_OK|run=%s|structure=%s|after=%s|level_saved=1|dirty_after=0+0"
               % (mode, RUN, label, json.dumps(after)))


main()
