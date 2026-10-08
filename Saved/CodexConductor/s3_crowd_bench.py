"""P21 PIE performance gate for the S3 establishing and choir windows.

The conductor runs DRY/APPLY/REVERT through ExecuteProjectPythonFile. APPLY
requires an already-running PIE session and samples only while LS_DevScene_03's
player is inside the selected frame window. It never starts/stops PIE or saves a
package. Results accumulate in s3_crowd_bench_record.json; baseline must contain
both windows before s3_crowd_structure APPLY can create a 20-person crowd.
"""
from __future__ import annotations

import builtins
import datetime as dt
import json
import math
import os
import shutil
import traceback

import unreal

PROJECT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
HERE = os.path.join(PROJECT, "Saved", "CodexConductor")
ARGS = os.path.join(HERE, "s3_crowd_bench_args.json")
RECORD = os.path.join(HERE, "s3_crowd_bench_record.json")
LOG = os.path.join(PROJECT, "Saved", "Logs", "PussStage.log")
ROOT = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
WINDOWS = {"establishing": [360, 552], "choir": [2160, 4488]}
HANDLE = "PUSS_P21_S3_CROWD_BENCH"
RUN = {"value": "?"}


def atomic_json(path, data):
    temp = path + ".pending"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def gpu_timeout_count():
    if not os.path.isfile(LOG): return 0
    with open(LOG, "r", encoding="utf-8", errors="replace") as f:
        return f.read().lower().count("gpu timeout")


def pct(values, q):
    if not values: return None
    vals=sorted(values); pos=q*(len(vals)-1); lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    return vals[lo] if lo==hi else vals[lo]+(vals[hi]-vals[lo])*(pos-lo)


def stats(deltas):
    ms=[float(x)*1000.0 for x in deltas]
    return {"median": round(pct(ms,0.5),3), "p90": round(pct(ms,0.9),3),
            "max": round(max(ms),3), "mean": round(sum(ms)/len(ms),3)}


def player_and_frame(world):
    hits=[]
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.LevelSequenceActor):
        sequence=None
        try: sequence=actor.get_sequence()
        except Exception:
            try: sequence=actor.get_editor_property("level_sequence_asset")
            except Exception: pass
        if sequence and sequence.get_path_name().split(".")[0]==ROOT:
            player=actor.get_editor_property("sequence_player")
            if player: hits.append(player)
    if len(hits)!=1: raise RuntimeError("S3_PLAYER_COUNT|%d"%len(hits))
    current=hits[0].get_current_time(); rate=current.rate
    raw=float(current.time.frame_number.value)+float(current.time.sub_frame)
    frame=int(math.floor(raw*24.0*float(rate.denominator)/float(rate.numerator)+1e-6))
    return hits[0],frame


def figure_count(world):
    rows=[]
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        try: label=str(actor.get_actor_label())
        except Exception: label=str(actor.get_name())
        tags=[str(x) for x in actor.tags]
        if label.startswith("Shore0") or "P21.S3Crowd" in tags:
            try: hidden=bool(actor.is_hidden())
            except Exception: hidden=False
            root=actor.get_editor_property("root_component")
            visible=(not hidden) and (root is None or root.is_visible())
            rows.append({"label":label,"visible":visible,"tagged":"P21.S3Crowd" in tags})
    return sum(r["visible"] for r in rows),rows


def backup_record(run):
    directory=os.path.join(PROJECT,"Backups","PreS3CrowdBench-"+run)
    if os.path.exists(directory): raise RuntimeError("BACKUP_EXISTS|"+directory)
    os.makedirs(directory); manifest={"run":run,"record_existed":os.path.isfile(RECORD)}
    if os.path.isfile(RECORD):
        dst=os.path.join(directory,os.path.basename(RECORD)); shutil.copy2(RECORD,dst); manifest["backup_file"]=dst
    atomic_json(os.path.join(directory,"backup_manifest.json"),manifest)
    return directory


def finish(st):
    unreal.unregister_slate_post_tick_callback(st["handle"])
    if hasattr(builtins,HANDLE): delattr(builtins,HANDLE)
    if census()!=st["dirty_start"]: raise RuntimeError("DIRTY_CHANGED|start=%s|end=%s"%(st["dirty_start"],census()))
    if len(st["deltas"])<24: raise RuntimeError("TOO_FEW_SAMPLES|%d"%len(st["deltas"]))
    gpu_end=gpu_timeout_count(); count,actors=figure_count(st["world"])
    row={"run":st["run"],"window":st["window"],"range":st["range"],"samples":len(st["deltas"]),
         "dt_ms":stats(st["deltas"]),"gpu_timeout_lines_before":st["gpu_start"],
         "gpu_timeout_lines_after":gpu_end,"gpu_timeout_lines_new":max(0,gpu_end-st["gpu_start"]),
         "figure_count":count,"actors":actors,"dirty_before":st["dirty_start"],"dirty_after":census(),
         "measured_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
    record={"schema":"p21_s3_crowd_bench/1","baseline":{},"crowd":{}}
    if os.path.isfile(RECORD): record=json.load(open(RECORD,encoding="utf-8"))
    record.setdefault(st["stage"],{})[st["window"]]=row; record["last_backup"]=st["backup"]
    atomic_json(RECORD,record)
    s=row["dt_ms"]
    unreal.log("S3_CROWD_BENCH_APPLY_OK|run=%s|stage=%s|window=%s|figures=%d|samples=%d|median_ms=%.3f|p90_ms=%.3f|max_ms=%.3f|gpu_timeouts_new=%d|dirty_unchanged=1"%
               (st["run"],st["stage"],st["window"],count,row["samples"],s["median"],s["p90"],s["max"],row["gpu_timeout_lines_new"]))


def main():
    args=json.load(open(ARGS,encoding="utf-8")); run=str(args["run"]); mode=str(args["mode"]).upper(); RUN["value"]=run
    stage=str(args.get("stage","baseline")).lower(); window=str(args.get("window","establishing")).lower()
    if mode not in ("DRY","APPLY","REVERT"): raise RuntimeError("MODE|"+mode)
    if stage not in ("baseline","crowd") or window not in WINDOWS: raise RuntimeError("STAGE_OR_WINDOW")
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if mode=="REVERT":
        if args.get("confirm")!="REVERT S3CROWDBENCH": raise RuntimeError("CONFIRM_REQUIRED|REVERT S3CROWDBENCH")
        source_run=str(args.get("revert_run") or run); directory=os.path.join(PROJECT,"Backups","PreS3CrowdBench-"+source_run)
        manifest=json.load(open(os.path.join(directory,"backup_manifest.json"),encoding="utf-8"))
        park=os.path.join(PROJECT,"Backups","PreS3CrowdBenchRevert-"+run); os.makedirs(park)
        if os.path.isfile(RECORD): shutil.move(RECORD,os.path.join(park,os.path.basename(RECORD)))
        if manifest["record_existed"]: shutil.copy2(manifest["backup_file"],RECORD)
        unreal.log("S3_CROWD_BENCH_REVERT_OK|run=%s|source=%s|parked=%s"%(run,directory,park)); return
    if world is None: raise RuntimeError("NO_PIE")
    dirty=census(); player,frame=player_and_frame(world); count,actors=figure_count(world)
    unreal.log("S3_CROWD_BENCH_STATE|run=%s|stage=%s|window=%s|frame=%d|figures=%d|dirty=%s"%(run,stage,window,frame,count,dirty))
    if mode=="DRY":
        unreal.log("S3_CROWD_BENCH_DRY_OK|run=%s|stage=%s|window=%s|range=%s|frame=%d|figures=%d|writes=0"%
                   (run,stage,window,WINDOWS[window],frame,count)); return
    if args.get("confirm")!="APPLY S3CROWDBENCH": raise RuntimeError("CONFIRM_REQUIRED|APPLY S3CROWDBENCH")
    if hasattr(builtins,HANDLE): raise RuntimeError("BENCH_ALREADY_ARMED")
    existing={"schema":"p21_s3_crowd_bench/1","baseline":{},"crowd":{}}
    if os.path.isfile(RECORD): existing=json.load(open(RECORD,encoding="utf-8"))
    if window in existing.get(stage,{}): raise RuntimeError("MEASUREMENT_EXISTS|%s|%s"%(stage,window))
    if stage=="crowd" and any(w not in existing.get("baseline",{}) for w in WINDOWS):
        raise RuntimeError("BASELINE_BOTH_WINDOWS_REQUIRED")
    backup=backup_record(run); lo,hi=WINDOWS[window]
    st={"run":run,"stage":stage,"window":window,"range":[lo,hi],"world":world,"player":player,
        "deltas":[],"entered":False,"dirty_start":dirty,"gpu_start":gpu_timeout_count(),"backup":backup,"last_frame":frame}
    def tick(delta):
        state=getattr(builtins,HANDLE,None)
        if state is None: return
        try:
            if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None: raise RuntimeError("PIE_ENDED")
            current=state["player"].get_current_time(); rate=current.rate
            raw=float(current.time.frame_number.value)+float(current.time.sub_frame)
            frame=int(math.floor(raw*24.0*float(rate.denominator)/float(rate.numerator)+1e-6)); state["last_frame"]=frame
            if lo<=frame<hi: state["entered"]=True; state["deltas"].append(float(delta))
            elif state["entered"] and frame>=hi: finish(state)
        except Exception as exc:
            try: unreal.unregister_slate_post_tick_callback(state["handle"])
            finally:
                if hasattr(builtins,HANDLE): delattr(builtins,HANDLE)
            unreal.log_error("S3_CROWD_BENCH_FAILED|run=%s|%r|%s"%(run,exc,traceback.format_exc()[-600:].replace("\n"," / ")))
    setattr(builtins,HANDLE,st); st["handle"]=unreal.register_slate_post_tick_callback(tick)
    unreal.log("S3_CROWD_BENCH_ARMED|run=%s|stage=%s|window=%s|range=%s|start_or_continue_Play"%(run,stage,window,[lo,hi]))


try: main()
except Exception as exc:
    unreal.log_error("S3_CROWD_BENCH_FAILED|run=%s|%r|%s"%(RUN["value"],exc,traceback.format_exc()[-900:].replace("\n"," / ")))
