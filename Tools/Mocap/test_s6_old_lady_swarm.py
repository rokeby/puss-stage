#!/usr/bin/env python3
"""Offline +/- harness for the S6 old-lady swarm curve and UE authoring tools."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("s6_swarm", Path(__file__).with_name("s6_old_lady_swarm.py"))
S = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(S)
passed = failed = 0


def check(name, value, control):
    global passed, failed
    if value:
        passed += 1; print("PASS|%s|%s" % (control, name))
    else:
        failed += 1; print("FAIL|%s|%s" % (control, name))


def raises(fn, text):
    try: fn()
    except Exception as exc: return text in str(exc)
    return False


def fixture(seconds=8.0):
    rows=[]
    for i in range(int(seconds*S.FPS)+1):
        t=i/S.FPS; burst=math.exp(-((t-2.2)/.16)**2)+.9*math.exp(-((t-5.4)/.20)**2)
        left=[100+18*math.sin(t), 50+55*burst*math.sin(18*t), 150+25*burst]
        right=[140-15*math.sin(t), 50-70*burst*math.sin(18*t), 150-20*burst]
        rows.append({"s6_seconds":4.16+t,"source_seconds":t,
                     "left_hand_world_cm":[left[0]+29339.2835,left[1]+399920,left[2]+135],
                     "right_hand_world_cm":[right[0]+29339.2835,right[1]+399920,right[2]+135]})
    return {"source":{"animation":"HARNESS_FIXTURE_NOT_OLD_LADY_DATA"},"samples":rows}


def args():
    return S.parser().parse_args(["in.json","--json","out.json","--png","out.png"])


def run(write_preview=False):
    a=args(); rec=S.generate(fixture(),a)
    check("24 fps key count",rec["key_count"]==193,"POSITIVE")
    check("bat peaks detected",rec["batting_peak_count"]>=2,"POSITIVE")
    check("each hand has scalar speed",all(isinstance(k["left_hand_speed_cm_s"],float) for k in rec["keys"]),"POSITIVE")
    check("world to nested-local conversion",abs(rec["keys"][0]["swarm_world_cm"][0]-rec["keys"][0]["swarm_local_cm"][0]-29339.2835)<.01,"POSITIVE")
    check("batting disperses and lowers density",min(k["concentration_density"] for k in rec["keys"])<.7,"POSITIVE")
    with tempfile.TemporaryDirectory() as td:
        png=Path(td)/"x.png"; S.render_png(rec,png)
        check("PNG dimensions",png.is_file() and S.Image.open(png).size==(1800,720),"POSITIVE")
    check("too few samples rejected",raises(lambda:S.generate({"samples":[]},a),"TOO_FEW"),"NEGATIVE")
    bad=fixture(); bad["samples"][3]["s6_seconds"]+=.01
    check("non-24fps time rejected",raises(lambda:S.generate(bad,a),"NOT_24FPS"),"NEGATIVE")
    bad=fixture(); bad["samples"][2]["left_hand_world_cm"]=[1,2]
    check("bad hand vectors rejected",raises(lambda:S.generate(bad,a),"BAD_VECTOR"),"NEGATIVE")

    ue=(ROOT/"Saved/CodexConductor/S6OldLadySwarm/swarm_sequence.py").read_text(encoding="utf-8")
    sample=(ROOT/"Saved/CodexConductor/S6OldLadySwarm/sample_hands.py").read_text(encoding="utf-8")
    check("UE tool exposes DRY APPLY REVERT",all('mode=="'+m+'"' in ue for m in ("DRY","APPLY","REVERT")),"STATIC")
    check("record and backup precede duplicate",ue.index("write_record_before(run,record)")<ue.index("duplicate_asset(SOURCE,TARGET)"),"STATIC")
    check("cue GUID normalized from export text",'value.export_text()' in ue and '"cue":cue' in ue,"STATIC")
    check("suffixed channel names normalized",'re.sub(r"_\\d+$", "", raw)' in ue,"STATIC")
    check("exact dirty census and named saves",'DIRTY_AT_START' in ue and 'saved_packages' in ue and 'save_asset(package' in ue,"STATIC")
    check("no destructive/delete or Save All route",all(token not in ue for token in ("delete_asset(","save_all","load_level(")),"NEGATIVE")
    check("sampler is read-only",all(token not in sample for token in ("save_asset(","save_current_level","duplicate_asset(","set_editor_property(")),"STATIC")
    check("sampler reports animation offset/rate",'start_frame_offset' in sample and 'play_rate' in sample,"STATIC")

    if write_preview:
        out=ROOT/"DerivedAssets/S6OldLadySwarm"; out.mkdir(parents=True,exist_ok=True)
        preview=out/"s6_old_lady_swarm_response_SYNTHETIC_PREVIEW.png"
        S.render_png(rec,preview)
        image=S.Image.open(preview); draw=S.ImageDraw.Draw(image)
        draw.rectangle((1080,20,1710,62),fill=(125,20,20)); draw.text((1095,34),"SYNTHETIC HARNESS - NOT OLD LADY DATA",fill="white",font=S.ImageFont.load_default()); image.save(preview)
        manifest={"state":"SYNTHETIC_DESIGN_PREVIEW_ONLY","not_performance_data":True,
                  "expected_real_output":"s6_old_lady_swarm_drive.json after editor hand sampling",
                  "design":rec["design"],"key_count":rec["key_count"],"batting_peak_count":rec["batting_peak_count"]}
        (out/"s6_old_lady_swarm_preview_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("S6_SWARM_HARNESS|pass=%d|fail=%d"%(passed,failed))
    return 0 if failed==0 else 1


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--write-preview",action="store_true")
    raise SystemExit(run(p.parse_args().write_preview))
