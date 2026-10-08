#!/usr/bin/env python3
"""Offline positive/negative harness for the P21 crowd plan and editor helpers."""
from __future__ import annotations

import argparse
import copy
import importlib.util
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
                              target_period=3.6,roll_degrees=2.5,mode="DRY",confirm="",revert_run="")


def main(source):
    plan=P.build_plan(args(source)); P.validate_plan(plan)
    check("20 members plus five-visible reserve",len(plan["members"])==20 and
          len(plan["duplicate_placements"])==15 and plan["placement_reserve_count"]==1,"POS")
    check("absolute main-tree inputs",all(str(v).replace("\\","/").startswith("E:/PussStage/DerivedAssets/")
          for k,v in plan["inputs"].items() if k in ("segments","sway")),"POS")
    check("deterministic placements",P.build_placements(2103)==P.build_placements(2103),"POS")
    check("all placements outside exclusions",all(not P.placement_violations(tuple(x["local_xy_cm"]))
          for x in plan["duplicate_placements"]),"POS")
    preferred=sum(x["source_id"] in ("Shore04_F55","Shore06_F25") for x in plan["duplicate_placements"])
    check("rhythmic sources preferred",preferred>=7,"POS")
    check("timeline covers requested structure",all(m["timeline"][0]["range"][0]==360 and
          m["timeline"][-1]=={"class":"ORIGINAL","range":[4488,6240]} for m in plan["members"]),"POS")
    check("B07 orbit untouched by closeups",all(s["range"][0]>=2880 for s in plan["shots"][1:]),"POS")
    check("B06 is exactly eight seconds",plan["handprint_trim"]["after"]==[3000,3192],"POS")
    check("three previews render",all(blob.startswith(b"\x89PNG\r\n\x1a\n") and len(blob)>10000 for blob in
          (P.render_placement(plan),P.render_timeline(plan),P.render_shots(plan))),"POS")
    bench={"schema":"p21_s3_crowd_bench/1","baseline":{
        "establishing":{"figure_count":5,"samples":192,"dt_ms":{"median":18.0}},
        "choir":{"figure_count":5,"samples":2200,"dt_ms":{"median":18.5}}}}
    check("measured baseline opens APPLY gate",E.baseline_gate(bench,5)==(True,"OK"),"POS")
    check("cut subtraction preserves both sides",E.subtract_ranges([0,100],[[20,30],[50,80]])==[[0,20],[30,50],[80,100]],"POS")
    check("coverage accepts overlapping full span",E.coverage_gaps([[0,95],[95,6216],[6216,6240]],[0,6240])==[],"POS")
    schedule=E.build_source_schedule(plan["members"][0],plan["sources"][plan["members"][0]["source_id"]])
    check("schedule contains all four handoff classes",set(r["class"] for r in schedule)=={"CALM","MEDIUM","FRENZY","ORIGINAL"},"POS")
    class Fake:
        def __init__(self): self.calls=[]
        def __getattr__(self,name): return lambda:self.calls.append(name)
    fake=Fake(); E.execute_order(fake)
    check("mutation contract order",fake.calls==E.planned_apply_order(),"POS")

    check("target below six refused",raises(P.build_placements,2103,5,contains="TARGET_COUNT_OUT_OF_RANGE"),"NEG")
    check("target above cells refused",raises(P.build_placements,2103,27,contains="TARGET_COUNT_OUT_OF_RANGE"),"NEG")
    check("clam placement detected",P.placement_violations(P.CLAM_LOCAL)==["clam"],"NEG")
    bad=copy.deepcopy(plan); bad["members"][1]["label"]=bad["members"][0]["label"]
    check("duplicate member label refused",raises(P.validate_plan,bad,contains="DUPLICATE_MEMBER_LABEL"),"NEG")
    bad=copy.deepcopy(plan); bad["shots"][1]["range"]=[2700,2800]
    check("B07 overlap refused",raises(P.validate_plan,bad,contains="B07_ORBIT_BROKEN"),"NEG")
    bad=copy.deepcopy(plan); bad["handprint_trim"]["after"]=[3000,3200]
    check("non-eight-second B06 refused",raises(P.validate_plan,bad,contains="HANDPRINT_NOT_EIGHT_SECONDS"),"NEG")
    check("missing baseline window refused",not E.baseline_gate({"schema":"p21_s3_crowd_bench/1","baseline":{}},5)[0],"NEG")
    wrong=copy.deepcopy(bench); wrong["baseline"]["choir"]["figure_count"]=6
    check("baseline count mismatch refused",not E.baseline_gate(wrong,5)[0],"NEG")
    short=copy.deepcopy(bench); short["baseline"]["choir"]["samples"]=2
    check("short baseline refused",not E.baseline_gate(short,5)[0],"NEG")
    check("coverage gap detected",E.coverage_gaps([[0,100],[120,200]],[0,200])==[[100,120]],"NEG")
    print("S3_CROWD_HARNESS|passed=%d|failed=%d|positive=%d|negative=%d"%(passed,failed,positive,negative))
    return 1 if failed else 0


if __name__=="__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else "E:/PussStage"))
