"""Gary 5 Oct: "we should basically never see the dusky horizon, the outer world of the stage can be entirely black, so that
the rig emerges to swallow us from nothing into its rigging light" + "keep the possibility of a sky, but shouldn't S03 be
'artificial' lighting that creates the beach light?"

Sets the Celestial rig's sky contributions to black/zero (sun, moon, sky light, stars, fog colours), recording every
original value first so the sky can come back (REVERT). Level-only write. Args black_void_args.json
{"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> VOID"}. Marker BLACK_VOID_<MODE>_OK|run=..
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
REC = HERE + "black_void_record.json"
RUN = datetime.datetime.now().strftime("VOID-%Y%m%d-%H%M%S")
BLACK = {"maximum_sun_intensity": 0.0, "maximum_moon_intensity": 0.0, "day_sky_light_intensity": 0.0,
         "night_sky_light_intensity": 0.0, "maximum_stars_brightness": 0.0, "show_built_in_stars": False,
         "day_fog_color": (0.0, 0.0, 0.0, 1.0), "night_fog_color": (0.0, 0.0, 0.0, 1.0)}


def stop(msg):
    unreal.log_error("BLACK_VOID_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def read(rig):
    out = {}
    for k in BLACK:
        v = rig.get_editor_property(k)
        out[k] = (v.r, v.g, v.b, v.a) if isinstance(v, unreal.LinearColor) else v
    return out


def write(rig, values):
    rig.modify()
    for k, v in values.items():
        rig.set_editor_property(k, unreal.LinearColor(*v) if isinstance(v, (list, tuple)) else v)
    back = read(rig)
    bad = {k: (back[k], v) for k, v in values.items()
           if (list(back[k]) if isinstance(back[k], tuple) else back[k]) != (list(v) if isinstance(v, (list, tuple)) else v)}
    if bad:
        stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(bad, default=str))


def main():
    a = json.load(open(HERE + "black_void_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    if mode != "DRY" and a.get("confirm") != "%s VOID" % mode:
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    rigs = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if x.get_class().get_name() == "InfinityStageCelestialRig"]
    if len(rigs) != 1:
        stop("RIG_COUNT|%d" % len(rigs))
    rig = rigs[0]
    before = read(rig)
    unreal.log("BLACK_VOID_START|run=%s|mode=%s|rig=%s|before=%s" % (RUN, mode, rig.get_actor_label(), json.dumps(before, default=str)))
    if mode == "DRY":
        unreal.log("BLACK_VOID_DRY_OK|run=%s|planned=%s" % (RUN, json.dumps(BLACK)))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    if mode == "APPLY":
        if os.path.exists(REC):
            stop("RECORD_EXISTS")
        backup = "E:/PussStage/Backups/PreBlackVoid-" + RUN
        os.makedirs(backup)
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "before": before, "backup": backup}, h, indent=1, default=str)
            h.flush()
            os.fsync(h.fileno())
        shutil.copy2(UMAP, backup)
        write(rig, BLACK)
    else:
        if not os.path.exists(REC):
            stop("NO_RECORD")
        write(rig, json.load(open(REC, encoding="utf-8"))["before"])
    dirty = census()
    if dirty["content"] or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    if mode == "REVERT":
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("BLACK_VOID_%s_OK|run=%s|level_saved=1|dirty_after=0+0" % (mode, RUN))


main()
