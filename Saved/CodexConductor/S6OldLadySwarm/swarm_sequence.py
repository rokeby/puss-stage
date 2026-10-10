"""DRY/APPLY/REVERT the hand-driven S6 swarm on a create-only sequence copy.

APPLY duplicates LS_Void_S6, replaces only NS_BeeSwarm translation/scale keys
in the duplicate, and switches the existing S6 shot section to that duplicate.
Klara's Niagara system, source sequence, level and the Show are never saved.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import time

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_06"
SOURCE = "/Game/InfinityStage/KlaraHookin/LS_Void_S6"
TARGET = "/Game/InfinityStage/KlaraHookin/LS_Void_S6_SwarmDriven"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import swarm_pipeline as PIPE
ARGS_PATH = os.path.join(HERE, "swarm_sequence_args.json")
RECORD_PATH = os.path.join(HERE, "swarm_sequence_record.json")
CURVES_PATH = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                           "DerivedAssets", "S6OldLadySwarm", "s6_old_lady_swarm_drive.json")
CHANNELS = ("Location.X", "Location.Y", "Location.Z", "Scale.X", "Scale.Y", "Scale.Z")


def stop(run, why):
    unreal.log_error("S6_SWARM_SEQUENCE_STOP|run=%s|%s" % (run, why))
    raise RuntimeError(why)


def asset_path(obj):
    return "" if obj is None else str(obj.get_path_name()).split(".")[0]


def enum_token(value):
    # UE 5.8 str(enum) may contain a class prefix; compare the normalized tail.
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def guid_text(value):
    # UE 5.8 str(FGuid) is not stable.  export_text carries the four uint32s.
    candidates = []
    for fn in (lambda: value.export_text(), lambda: value.to_string(), lambda: str(value)):
        try: candidates.append(str(fn()))
        except Exception: pass
    for text in candidates:
        chunks = re.findall(r"[0-9A-Fa-f]{8}", text)
        if len(chunks) >= 4:
            return "".join(chunks[-4:]).upper()
        compact = "".join(re.findall(r"[0-9A-Fa-f]", text))
        if len(compact) >= 32:
            return compact[-32:].upper()
    return ""


def channel_base(channel):
    raw = str(channel.channel_name if hasattr(channel, "channel_name") else channel.get_name())
    return re.sub(r"_\d+$", "", raw)


def dirty():
    content = sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    maps = sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    return {"content": content, "maps": maps}


def require_clean(run):
    census = dirty()
    if census != {"content": [], "maps": []}: stop(run, "DIRTY_AT_START|" + json.dumps(census))
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None: stop(run, "SEQUENCER_OPEN")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if asset_path(world) != EXPECTED_WORLD: stop(run, "WRONG_WORLD|" + asset_path(world))
    return census


def cue_row(run):
    show = unreal.load_asset(SHOW)
    if show is None: stop(run, "SHOW_MISSING")
    hits=[]
    for cue in show.get_editor_property("cues"):
        if "SCENE" not in enum_token(cue.get_editor_property("type")): continue
        scene = cue.get_editor_property("scene")
        if asset_path(scene.get_editor_property("sequence")) == SCENE: hits.append(cue)
    if len(hits) != 1: stop(run, "S6_CUE_COUNT|%d" % len(hits))
    cue=hits[0]
    guid=""
    for name in ("cue_guid", "guid", "id"):
        try:
            guid=guid_text(cue.get_editor_property(name))
            if guid: break
        except Exception: pass
    if len(guid) != 32: stop(run, "S6_CUE_GUID_UNREADABLE")
    return {"guid": guid, "label": str(cue.get_editor_property("label")), "sequence": SCENE}


def shot_section(run, sequence, wanted):
    rows=[]
    for track in sequence.get_tracks():
        if isinstance(track, unreal.MovieSceneCinematicShotTrack):
            rows.extend([s for s in track.get_sections() if asset_path(s.get_sequence()) == wanted])
    if len(rows) != 1: stop(run, "SHOT_SECTION_COUNT|sequence=%s|count=%d" % (wanted,len(rows)))
    return rows[0]


def swarm_binding(run, sequence):
    rows=[b for b in sequence.get_bindings() if str(b.get_display_name()) == "NS_BeeSwarm"]
    if len(rows) != 1: stop(run, "SWARM_BINDING_COUNT|%d" % len(rows))
    return rows[0]


def transform_section(run, binding):
    tracks=[t for t in binding.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)]
    if len(tracks) != 1: stop(run, "SWARM_TRANSFORM_TRACK_COUNT|%d" % len(tracks))
    sections=list(tracks[0].get_sections())
    if len(sections) != 1: stop(run, "SWARM_TRANSFORM_SECTION_COUNT|%d" % len(sections))
    return sections[0]


def channel_map(run, section):
    result={channel_base(c): c for c in section.get_all_channels()}
    missing=[name for name in CHANNELS if name not in result]
    if missing: stop(run, "CHANNELS_MISSING|" + ",".join(missing))
    return result


def counts(run, sequence):
    channels=channel_map(run,transform_section(run,swarm_binding(run,sequence)))
    return {name: len(channels[name].get_keys()) for name in CHANNELS}


def load_curves(run):
    if not os.path.isfile(CURVES_PATH):
        state = PIPE.pipeline_state(os.path.isfile(PIPE.HAND_SAMPLES), False)
        stop(run, "CURVES_MISSING|%s|next=%s|run_order=%s" %
             (CURVES_PATH, state["next_step"], " -> ".join(PIPE.STEP_IDS)))
    with open(CURVES_PATH,"r",encoding="utf-8") as handle: record=json.load(handle)
    if record.get("schema") != "pussstage.s6-old-lady-swarm-drive.v1": stop(run,"CURVE_SCHEMA")
    keys=record.get("keys") or []
    if len(keys) < 3 or record.get("key_count") != len(keys): stop(run,"CURVE_KEY_COUNT")
    if any(int(k["s6_frame_24"]) != int(keys[0]["s6_frame_24"]) + i for i,k in enumerate(keys)):
        stop(run,"CURVES_NOT_CONTIGUOUS_24FPS")
    return record


def backup(run):
    project=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    source=os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
                        SCENE[len("/Game/"):].replace("/",os.sep)+".uasset")
    folder=os.path.join(project,"Backups","PreS6OldLadySwarm-"+run)
    if os.path.exists(folder): stop(run,"BACKUP_EXISTS|"+folder)
    os.makedirs(folder)
    destination=os.path.join(folder,"LS_DevScene_06.uasset")
    shutil.copy2(source,destination)
    if os.path.getsize(source) != os.path.getsize(destination): stop(run,"BACKUP_SIZE_MISMATCH")
    return {"folder":folder,"scene_file":destination,"bytes":os.path.getsize(destination)}


def write_record_before(run, record):
    if os.path.exists(RECORD_PATH): stop(run,"RECORD_EXISTS|"+RECORD_PATH)
    with open(RECORD_PATH,"x",encoding="utf-8") as handle: json.dump(record,handle,indent=2); handle.write("\n")


def add_keys(run, sequence, drive):
    section=transform_section(run,swarm_binding(run,sequence)); channels=channel_map(run,section)
    for name in CHANNELS:
        for key in list(channels[name].get_keys()): key.remove()
    tick=sequence.get_tick_resolution(); tick_fps=float(tick.numerator)/float(tick.denominator)
    display=sequence.get_display_rate(); display_fps=float(display.numerator)/float(display.denominator)
    first_s=float(drive["keys"][0]["s6_seconds"])-104/25
    for row in drive["keys"]:
        local_s=float(row["s6_seconds"])-104/25
        tick_frame=int(round(local_s*tick_fps))
        values=tuple(row["swarm_local_cm"])+tuple(row["scale_xyz"])
        for name,value in zip(CHANNELS,values):
            channels[name].add_key(unreal.FrameNumber(tick_frame),float(value),time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
                                   interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    section.set_range(int(math.floor(first_s*display_fps)),
                      int(math.ceil((float(drive["keys"][-1]["s6_seconds"])-104/25)*display_fps))+1)
    return counts(run,sequence)


def dry(args, run):
    before=require_clean(run); cue=cue_row(run); drive=load_curves(run)
    scene=unreal.load_asset(SCENE); source=unreal.load_asset(SOURCE)
    if scene is None or source is None: stop(run,"SEQUENCE_MISSING")
    shot=shot_section(run,scene,SOURCE)
    if unreal.EditorAssetLibrary.does_asset_exist(TARGET): stop(run,"TARGET_EXISTS_CREATE_ONLY|"+TARGET)
    unreal.log("S6_SWARM_SEQUENCE_DRY_OK|run=%s|cue_guid=%s|keys=%d|peaks=%d|source_counts=%s|shot=[%d,%d]|dirty=%s" %
               (run,cue["guid"],drive["key_count"],drive["batting_peak_count"],json.dumps(counts(run,source)),
                int(shot.get_start_frame()),int(shot.get_end_frame()),json.dumps(before)))


def apply(args, run):
    before=require_clean(run); cue=cue_row(run); drive=load_curves(run)
    if unreal.EditorAssetLibrary.does_asset_exist(TARGET): stop(run,"TARGET_EXISTS_CREATE_ONLY|"+TARGET)
    scene=unreal.load_asset(SCENE); source=unreal.load_asset(SOURCE)
    shot=shot_section(run,scene,SOURCE); prior={"sequence":SOURCE,"start":int(shot.get_start_frame()),"end":int(shot.get_end_frame())}
    bak=backup(run)
    record={"schema":"pussstage.s6-old-lady-swarm-sequence.v1","run":run,"mode":"APPLY","cue":cue,
            "dirty_before":before,"backup":bak,"curves":CURVES_PATH,"curve_key_count":drive["key_count"],
            "before":prior,"target":TARGET,"saved_packages":[TARGET,SCENE],"state":"RECORDED_BEFORE_CHANGE"}
    write_record_before(run,record)
    duplicate=unreal.EditorAssetLibrary.duplicate_asset(SOURCE,TARGET)
    if duplicate is None: stop(run,"DUPLICATE_FAILED")
    key_counts=add_keys(run,duplicate,drive)
    shot.set_sequence(duplicate)
    for package in (TARGET,SCENE):
        if not unreal.EditorAssetLibrary.save_asset(package,only_if_is_dirty=False): stop(run,"SAVE_FAILED|"+package)
    live_scene=unreal.load_asset(SCENE); live_target=unreal.load_asset(TARGET)
    live_shot=shot_section(run,live_scene,TARGET); live_counts=counts(run,live_target)
    expected={name:drive["key_count"] for name in CHANNELS}
    if live_counts != expected or key_counts != expected: stop(run,"KEY_READBACK|"+json.dumps(live_counts))
    after=dirty()
    if after != {"content":[],"maps":[]}: stop(run,"DIRTY_AFTER|"+json.dumps(after))
    record.update({"state":"APPLIED_AND_READ_BACK","after":{"shot_sequence":asset_path(live_shot.get_sequence()),
                   "key_counts":live_counts,"dirty":after}})
    with open(RECORD_PATH,"w",encoding="utf-8") as handle: json.dump(record,handle,indent=2); handle.write("\n")
    unreal.log("S6_SWARM_SEQUENCE_APPLY_OK|run=%s|cue_guid=%s|keys=%s|saved=%s|dirty=0|record=%s" %
               (run,cue["guid"],json.dumps(live_counts),json.dumps([TARGET,SCENE]),RECORD_PATH))


def revert(args, run):
    require_clean(run)
    if not os.path.isfile(RECORD_PATH): stop(run,"RECORD_MISSING")
    with open(RECORD_PATH,"r",encoding="utf-8") as handle: record=json.load(handle)
    if record.get("state") != "APPLIED_AND_READ_BACK": stop(run,"RECORD_STATE|"+str(record.get("state")))
    if cue_row(run)["guid"] != record["cue"]["guid"]: stop(run,"CUE_GUID_DRIFT")
    scene=unreal.load_asset(SCENE); target=unreal.load_asset(TARGET)
    if target is None: stop(run,"TARGET_MISSING")
    shot=shot_section(run,scene,TARGET); shot.set_sequence(unreal.load_asset(SOURCE))
    if not unreal.EditorAssetLibrary.save_asset(SCENE,only_if_is_dirty=False): stop(run,"SAVE_SCENE_FAILED")
    archive=TARGET+"_REVERTED_"+record["run"].replace("-","")
    if not unreal.EditorAssetLibrary.rename_asset(TARGET,archive): stop(run,"ARCHIVE_RENAME_FAILED|"+archive)
    if asset_path(shot_section(run,unreal.load_asset(SCENE),SOURCE).get_sequence()) != SOURCE: stop(run,"REVERT_READBACK")
    after=dirty()
    if after != {"content":[],"maps":[]}: stop(run,"DIRTY_AFTER_REVERT|"+json.dumps(after))
    record.update({"state":"REVERTED","reverted_by":run,"archived_target":archive,"dirty_after_revert":after})
    with open(RECORD_PATH,"w",encoding="utf-8") as handle: json.dump(record,handle,indent=2); handle.write("\n")
    unreal.log("S6_SWARM_SEQUENCE_REVERT_OK|run=%s|cue_guid=%s|restored=%s|archived=%s|dirty=0" %
               (run,record["cue"]["guid"],SOURCE,archive))


def main():
    # Runtime args are deliberately ignored by .gitignore.  A missing file is
    # always the safe DRY mode; APPLY/REVERT require an explicit local file.
    if os.path.isfile(ARGS_PATH):
        with open(ARGS_PATH,"r",encoding="utf-8") as handle: args=json.load(handle)
    else:
        args={"mode":"DRY","confirm":"DRY S6_OLD_LADY_SWARM","run_id":None}
    mode=str(args.get("mode","DRY")).upper(); run=args.get("run_id") or ("S6SWARM-"+time.strftime("%Y%m%d-%H%M%S"))
    if args.get("confirm") != mode+" S6_OLD_LADY_SWARM": stop(run,"CONFIRM")
    if mode=="DRY": dry(args,run)
    elif mode=="APPLY": apply(args,run)
    elif mode=="REVERT": revert(args,run)
    else: stop(run,"MODE|"+mode)


main()
