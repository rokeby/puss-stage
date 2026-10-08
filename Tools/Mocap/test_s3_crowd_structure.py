#!/usr/bin/env python3
"""Offline positive/negative harness for the P21 crowd plan and editor helpers."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import math
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec)
    assert spec and spec.loader; sys.modules[name]=module; spec.loader.exec_module(module); return module


P=load("p21_s3_crowd_plan",HERE/"s3_crowd_structure.py")
E=load("p21_s3_crowd_editor",ROOT/"Saved/CodexConductor/s3_crowd_structure.py")
passed=failed=positive=negative=0


def check(name,condition,control):
    global passed,failed,positive,negative
    if control=="POS": positive+=1
    else: negative+=1
    if condition: passed+=1; print("PASS|%s|%s"%(control,name))
    else: failed+=1; print("FAIL|%s|%s"%(control,name))


def raises(fn,*args,contains="",**kwargs):
    try: fn(*args,**kwargs)
    except Exception as exc: return contains in str(exc)
    return False


def args(source):
    return argparse.Namespace(source_root=source,project_root=str(ROOT),run="HARNESS",target_count=20,seed=2103,
                              target_period=3.6,roll_degrees=2.5,camera_clearance_cm=185.0,
                              teleport_threshold_cm=250.0,mode="DRY",confirm="",revert_run="")


def main(source):
    plan=P.build_plan(args(source)); P.validate_plan(plan)
    check("20 total is five retained plus fifteen copies",len(plan["members"])==20 and
          sum(m["role"]=="existing" for m in plan["members"])==5 and len(plan["duplicate_placements"])==15,"POS")
    check("placement authority separates originals from copies",all(m["placement_authority"]==
          ("existing_transform_track" if m["role"]=="existing" else "new_transform_track") for m in plan["members"]),"POS")
    check("three live transform census windows declared",plan["existing_position_policy"]["crowd_windows_scene"]==
          {"establishing":[360,552],"frenzy":[552,2160],"choir":[2828,4488]},"POS")
    check("three clusters each contain five to eight",len(plan["clusters"])==3 and
          sorted(c["size"] for c in plan["clusters"])==[5,7,8],"POS")
    check("absolute main-tree inputs",all(str(v).replace("\\","/").startswith("E:/PussStage/DerivedAssets/")
          for k,v in plan["inputs"].items() if k in ("segments","sway")),"POS")
    check("deterministic clustered placement",P.build_cluster_layout(2103)==P.build_cluster_layout(2103),"POS")
    check("all twenty outside exclusions",all(not P.placement_violations(tuple(x["local_xy_cm"]))
          for x in plan["members"]),"POS")
    check("cluster centres outside exclusions",all(not P.placement_violations(tuple(x["centre_local_xy_cm"]))
          for x in plan["clusters"]),"POS")
    check("nearest neighbours are 0.8 to 1.5 metres apart",all(80<=P.nearest_cluster_spacing(plan["members"],m)<=150
          for m in plan["members"]),"POS")
    check("all figures face clam within yaw variation",all(abs((((math.degrees(math.atan2(
          P.CLAM_LOCAL[1]-m["local_xy_cm"][1],P.CLAM_LOCAL[0]-m["local_xy_cm"][0]))-m["yaw_deg"])+180)%360)-180)<=4.01
          for m in plan["members"]),"POS")
    check("removed Shore05 is never planned",all(m["source_id"]!="Shore05_M53" for m in plan["members"]),"POS")
    preferred=sum(x["source_id"] in ("Shore04_F55","Shore06_F25") for x in plan["duplicate_placements"])
    check("rhythmic sources preferred",preferred>=7,"POS")
    check("clusters offset by quarter period",[c["phase_base_deg"] for c in plan["clusters"]]==[0.0,90.0,180.0],"POS")
    check("timeline covers requested structure",all(m["timeline"][0]["range"][0]==360 and
          m["timeline"][-1]=={"class":"ORIGINAL","range":[4488,6240]} for m in plan["members"]),"POS")
    check("establishing ends where B03 resumes",plan["shots"][0]["range"]==[360,552] and
          plan["cut_policy"]["b03_starts_after_establishing"]==552,"POS")
    check("choir wide then two 50 mm closeups precede wall",[s["lens_mm"] for s in plan["shots"][1:]]==[35.0,50.0,50.0]
          and plan["shots"][-1]["range"][1]==plan["handprint_trim"]["after"][0],"POS")
    check("B06 is exactly fifteen seconds",plan["handprint_trim"]["after"][1]-plan["handprint_trim"]["after"][0]==360,"POS")
    check("B06 retains original final glint",plan["handprint_trim"]["after"][1]==plan["handprint_trim"]["expected_before"][1],"POS")
    check("three previews render",all(blob.startswith(b"\x89PNG\r\n\x1a\n") and len(blob)>10000 for blob in
          (P.render_placement(plan),P.render_timeline(plan),P.render_shots(plan))),"POS")
    bench={"schema":"p21_s3_crowd_bench/1","baseline":{
        "establishing":{"figure_count":5,"samples":192,"dt_ms":{"median":18.0}},
        "choir":{"figure_count":5,"samples":2200,"dt_ms":{"median":18.5}}}}
    check("measured baseline opens APPLY gate",E.baseline_gate(bench,5)==(True,"OK"),"POS")
    check("cut subtraction preserves both sides",E.subtract_ranges([0,100],[[20,30],[50,80]])==[[0,20],[30,50],[80,100]],"POS")
    check("coverage accepts overlapping full span",E.coverage_gaps([[0,95],[95,6216],[6216,6240]],[0,6240])==[],"POS")
    live_rows=[{"camera":"Scene 3 External Sound Entry Handoff Camera","range":[0,483],"active":True,"camera_guid":"entry"}]
    live_rows += [{"camera":camera,"range":span,"active":True,"camera_guid":camera} for camera,span in plan["expected_live_cuts"].items()]
    check("live cut census matches converted ranges",E.live_cut_mismatches(live_rows,plan["expected_live_cuts"])==[],"POS")
    planned=E.planned_cut_rows(live_rows,plan)
    affected=[r["range"] for r in planned if r["active"]]+[s["range"] for s in plan["shots"]]
    check("planned cuts cover affected live span with no gaps",E.coverage_gaps(affected,[0,4858])==[],"POS")
    b03=[r["range"] for r in planned if r["camera"]=="S3 Shot B03"]
    check("B03 resumes at establishing end",[552,860] in b03,"POS")
    schedule=E.build_source_schedule(plan["members"][0],plan["sources"][plan["members"][0]["source_id"]])
    check("schedule contains all four handoff classes",set(r["class"] for r in schedule)=={"CALM","MEDIUM","FRENZY","ORIGINAL"},"POS")
    class Fake:
        def __init__(self): self.calls=[]
        def __getattr__(self,name): return lambda:self.calls.append(name)
    fake=Fake(); E.execute_order(fake)
    check("mutation contract order",fake.calls==["preflight","record","backup","preserve_original_transforms","duplicate","bind",
          "animate","sway","cameras","cuts","census","save_named","readback","commit"],"POS")
    absolute={"name":"Transform","sections":[{"name":"Absolute","range":[0,6263],
              "blend":{"value":"ABSOLUTE"},"channels":{"Location.X":{"keys":[[1461,0.0],[1462,900.0]]},
              "Rotation.X":{"keys":[[1461,0.0]]}}}]}
    accepted=E.transform_conflicts([absolute],[[382,574],[2850,4510]])
    check("location teleport keys do not block additive sway",accepted=={"foreign_additive":[],"roll_key_ranges":[]},"POS")
    jumps=E.teleport_rows([{"frame":1461,"xyz":[0,0,0]},{"frame":1462,"xyz":[900,0,0]}],250.0)
    check("teleport inside a crowd window is reported",jumps and jumps[0]["range"]==[1461,1463],"POS")
    check("frame refusals compress to half-open ranges",E.frames_to_ranges([382,383,400])==[[382,384],[400,401]],"POS")
    check("float readback accepts UE tolerance",E.snapshot_equal({"v":[1.0]},{"v":[1.00009]}),"POS")

    check("target other than twenty refused",raises(P.build_cluster_layout,2103,19,contains="TARGET_COUNT_MUST_BE_20"),"NEG")
    check("clam placement detected",P.placement_violations(P.CLAM_LOCAL)==["clam"],"NEG")
    bad=copy.deepcopy(plan); bad["members"][1]["label"]=bad["members"][0]["label"]
    check("duplicate member label refused",raises(P.validate_plan,bad,contains="DUPLICATE_MEMBER_LABEL"),"NEG")
    bad=copy.deepcopy(plan); bad["clusters"][0]["size"]=4
    check("undersized cluster refused",raises(P.validate_plan,bad,contains="CLUSTER_COUNT_OR_SIZE"),"NEG")
    bad=copy.deepcopy(plan); bad["members"][1]["local_xy_cm"]=list(bad["members"][0]["local_xy_cm"])
    check("crowded spacing refused",raises(P.validate_plan,bad,contains="CLUSTER_SPACING_OUT_OF_RANGE"),"NEG")
    bad=copy.deepcopy(plan); bad["clusters"][1]["phase_base_deg"]=60.0
    check("non-quarter cluster phase refused",raises(P.validate_plan,bad,contains="CLUSTER_PHASE_OFFSET"),"NEG")
    bad=copy.deepcopy(plan); bad["handprint_trim"]["after"][0]+=1
    check("non-fifteen-second B06 refused",raises(P.validate_plan,bad,contains="HANDPRINT_NOT_FIFTEEN_SECONDS"),"NEG")
    bad=copy.deepcopy(plan); bad["handprint_trim"]["after"]=[4167,4527]
    check("moved final glint refused",raises(P.validate_plan,bad,contains="HANDPRINT_FINAL_GLINT_MOVED"),"NEG")
    bad=copy.deepcopy(plan); bad["shots"][0]["range"]=[360,551]
    check("wrong establishing range refused",raises(P.validate_plan,bad,contains="SHOT_LAYOUT_NOT_LIVE_ALIGNED"),"NEG")
    check("missing baseline window refused",not E.baseline_gate({"schema":"p21_s3_crowd_bench/1","baseline":{}},5)[0],"NEG")
    wrong=copy.deepcopy(bench); wrong["baseline"]["choir"]["figure_count"]=6
    check("baseline count mismatch refused",not E.baseline_gate(wrong,5)[0],"NEG")
    short=copy.deepcopy(bench); short["baseline"]["choir"]["samples"]=2
    check("short baseline refused",not E.baseline_gate(short,5)[0],"NEG")
    check("coverage gap detected",E.coverage_gaps([[0,100],[120,200]],[0,200])==[[100,120]],"NEG")
    wrong_cuts=copy.deepcopy(live_rows); next(r for r in wrong_cuts if r["camera"]=="S3 Shot B06")["range"]=[2798,4525]
    check("live B06 mismatch detected",bool(E.live_cut_mismatches(wrong_cuts,plan["expected_live_cuts"])),"NEG")
    roll=copy.deepcopy(absolute); roll["sections"][0]["channels"]["Rotation.X"]["keys"]=[[400,1.0],[401,2.0]]
    check("roll keys inside sway window refused",E.transform_conflicts([roll],[[382,574]])["roll_key_ranges"]==[[400,402]],"NEG")
    additive=copy.deepcopy(absolute); additive["sections"][0]["blend"]["value"]="ADDITIVE"
    check("foreign additive section refused",bool(E.transform_conflicts([additive],[[382,574]])["foreign_additive"]),"NEG")
    check("sub-threshold movement is not called teleport",E.teleport_rows(
          [{"frame":10,"xyz":[0,0,0]},{"frame":11,"xyz":[249.9,0,0]}],250.0)==[],"NEG")
    check("float readback rejects drift outside UE tolerance",not E.snapshot_equal({"v":1.0},{"v":1.00011}),"NEG")
    print("S3_CROWD_HARNESS|passed=%d|failed=%d|positive=%d|negative=%d"%(passed,failed,positive,negative))
    return 1 if failed else 0


if __name__=="__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else "E:/PussStage"))
