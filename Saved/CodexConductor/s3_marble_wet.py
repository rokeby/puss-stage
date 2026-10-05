"""Gary 5 Oct: S3 "the marble needs to be shinier and wetter looking with more light to make it kinda white walls".
Edits ONLY scalar parameters on MI_S3_Marble_Heavy_Daylight (the S3 liner MI from s3_marble_tune.py, 4 Oct), recording
the before values first; saves only that MI; read-back is the gate (setters can lie). DRY lists every scalar parameter.
Args s3_marble_wet_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> MARBLE", "targets": {...}}.
"""
import datetime
import json
import os

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
MI = "/Game/InfinityStage/Dev/Materials/MI_S3_Marble_Heavy_Daylight"
REC = HERE + "s3_marble_wet_record.json"
DEFAULT_TARGETS = {"Brightness": 1.0, "Min Roughness": 0.06, "Max Roughness": 0.14}
RUN = datetime.datetime.now().strftime("MARBLE-%Y%m%d-%H%M%S")
MEL = unreal.MaterialEditingLibrary


def stop(msg):
    unreal.log_error("S3_MARBLE_WET_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def main():
    a = json.load(open(HERE + "s3_marble_wet_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    targets = a.get("targets") or DEFAULT_TARGETS
    if mode != "DRY" and a.get("confirm") != "%s MARBLE" % mode:
        stop("CONFIRM_MISSING")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        stop("PIE_ACTIVE")
    mi = unreal.load_asset(MI)
    if mi is None:
        stop("MI_MISSING")
    names = [str(n) for n in MEL.get_scalar_parameter_names(mi)]
    cur = {n: float(MEL.get_material_instance_scalar_parameter_value(mi, n)) for n in names}
    unreal.log("S3_MARBLE_WET_PARAMS|run=%s|%s" % (RUN, json.dumps(cur)))
    missing = [k for k in targets if k not in cur]
    if missing:
        stop("PARAM_MISSING|%s" % missing)
    if mode == "DRY":
        unreal.log("S3_MARBLE_WET_DRY_OK|run=%s|targets=%s" % (RUN, json.dumps(targets)))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    if mode == "APPLY":
        if os.path.exists(REC):
            stop("RECORD_EXISTS")
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "before": {k: cur[k] for k in targets}}, h, indent=1)
            h.flush()
            os.fsync(h.fileno())
        want = targets
    else:
        if not os.path.exists(REC):
            stop("NO_RECORD")
        want = json.load(open(REC, encoding="utf-8"))["before"]
    for k, v in want.items():
        MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
    MEL.update_material_instance(mi)
    back = {k: float(MEL.get_material_instance_scalar_parameter_value(mi, k)) for k in want}
    bad = {k: (back[k], v) for k, v in want.items() if abs(back[k] - float(v)) > 1e-4}
    if bad:
        stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(bad))
    dirty = census()
    if dirty["maps"] or len(dirty["content"]) != 1 or not dirty["content"][0].endswith("MI_S3_Marble_Heavy_Daylight"):
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorAssetLibrary.save_asset(MI, only_if_is_dirty=False):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    if mode == "REVERT":
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("S3_MARBLE_WET_%s_OK|run=%s|now=%s|saved=MI" % (mode, RUN, json.dumps(back)))


main()
