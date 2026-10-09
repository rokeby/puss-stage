"""Offline positive/negative harness for every P38 tool."""
from __future__ import annotations

import ast
import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path

import p38_core as core

HERE = Path(__file__).resolve().parent
RESULT = HERE / "harness_result.json"
EDITOR = HERE / "p38_editor.py"

groups = {name: {"positive": 0, "negative": 0, "failures": []}
          for name in ("ground_probe", "ground_fix", "handprints", "lid", "spoiler", "static")}


def check(group, polarity, condition, label):
    if condition:
        groups[group][polarity] += 1
    else:
        groups[group]["failures"].append("%s:%s" % (polarity,label))


def refuses(group, label, fn, token):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        check(group,"negative",token in str(exc),label+" wrong refusal "+str(exc))
    else:
        check(group,"negative",False,label+" accepted")


def ground_obs(**updates):
    value = {"dune":{"shadow_flags":{"cast_shadow":True,"cast_dynamic_shadow":True},
                     "materials":[{"two_sided":True}],"normal_samples":[]},
             "lights":[{"label":"B","location":[0,0,20],"surface_z_cm":0,"surface_tier":"measured",
                        "surface_method":"line_trace_dune","shadow_bias":0.5}],
             "figures":[]}
    value.update(updates)
    return value


def test_ground():
    ranked = core.rank_ground_candidates(ground_obs())
    check("ground_probe","positive",ranked["verdict"]=="UNCLEAR","clean observation stays unclear")
    flags = ground_obs(dune={"shadow_flags":{"cast_shadow":False,"cast_dynamic_shadow":True},
                             "materials":[{"two_sided":True}],"normal_samples":[]})
    check("ground_probe","positive",core.rank_ground_candidates(flags)["verdict"]=="PROVED:dune_shadow_flags","false flag proved")
    below = ground_obs(lights=[{"label":"B","location":[0,0,-5],"surface_z_cm":0,"surface_tier":"measured",
                               "surface_method":"line_trace_dune","shadow_bias":0.5}])
    check("ground_probe","positive",core.rank_ground_candidates(below)["verdict"]=="PROVED:light_origin:B","below surface proved")
    estimated = ground_obs(lights=[{"label":"B","location":[0,0,-5],"surface_z_cm":0,"surface_tier":"inferred",
                                   "surface_method":"dune_bounds_top","shadow_bias":0.5}])
    check("ground_probe","negative",core.rank_ground_candidates(estimated)["verdict"]=="UNCLEAR","bounds estimate not proof")
    one_sided = ground_obs(dune={"shadow_flags":{"cast_shadow":True,"cast_dynamic_shadow":True},
                                 "materials":[{"two_sided":False}],"normal_samples":[{"world_normal_z":-1.0}]})
    check("ground_probe","positive",core.rank_ground_candidates(one_sided)["verdict"]=="PROVED:material_two_sided","normal+material proof")
    no_normals = ground_obs(dune={"shadow_flags":{"cast_shadow":True,"cast_dynamic_shadow":True},
                                  "materials":[{"two_sided":False}],"normal_samples":[]})
    check("ground_probe","negative",core.rank_ground_candidates(no_normals)["verdict"]=="UNCLEAR","one sided alone not proof")
    foot = ground_obs(figures=[{"foot_gap_cm":50,"sequence_evaluated":False,"surface_method":"line_trace_dune"}])
    check("ground_probe","negative",not any(c["candidate"]=="figure_feet" and c["verdict"]=="SUPPORTED"
                                                for c in core.rank_ground_candidates(foot)["candidates"]),"unscrubbed foot ignored")

    below["ranking"] = core.rank_ground_candidates(below)
    check("ground_fix","positive",core.ground_fix_from_probe(below,"light_z_lift") is True,"proved light fix accepted")
    refuses("ground_fix","unproved bias",lambda:core.ground_fix_from_probe(below,"shadow_bias"),"NOT_PROVED")
    refuses("ground_fix","unknown fix",lambda:core.ground_fix_from_probe(below,"delete_mesh"),"FIX_KIND")
    refuses("ground_fix","confirm",lambda:core.require_confirm("ground_fix","APPLY","yes"),"CONFIRM_MISSING")
    check("ground_fix","positive",core.require_confirm("ground_fix","REVERT","REVERT P38 GROUND_FIX"),"revert confirm")


def hp_rows(n, wall="R"):
    return [{"label":"G%03d"%i,"wall_label":wall,"location":[float(i*10),100.0,50.0],"rotation":[0,0,0],
             "scale":[1,1,1],"wall_tangent":[1,0,0],"material":"M%d"%i,"decal_size":[8,10,10],
             "twin_label":"T%03d"%i} for i in range(n)]


def test_handprints():
    walls=[{"label":"L","centre":[0,-100,100],"extent":[500,5,100]},
           {"label":"R","centre":[0,100,100],"extent":[500,5,100]}]
    points=[[-50,96,100],[50,98,110]]
    sel=core.select_camera_wall(points,walls,25,100)
    check("handprints","positive",sel["selected"]=="R" and sel["margin_cm"]>100,"camera-derived right wall")
    refuses("handprints","ambiguous wall",lambda:core.select_camera_wall([[0,0,0],[1,0,0]],
            [{"label":"A","centre":[0,-10,0],"extent":[10,1,10]},{"label":"B","centre":[0,10,0],"extent":[10,1,10]}],50,5),"AMBIGUOUS")
    refuses("handprints","far wall",lambda:core.select_camera_wall([[0,0,0],[1,0,0]],
            [{"label":"A","centre":[0,1000,0],"extent":[10,1,10]},{"label":"B","centre":[0,2000,0],"extent":[10,1,10]}],50,5),"NOT_WALL_FOLLOWING")
    plan=core.plan_handprint_additions(hp_rows(5),"R",0.5,7)
    check("handprints","positive",plan["target_additions"]==3,"ceil 50 percent")
    again=core.plan_handprint_additions(hp_rows(5),"R",0.5,7)
    check("handprints","positive",plan["plan_digest"]==again["plan_digest"],"same seed deterministic")
    other=core.plan_handprint_additions(hp_rows(5),"R",0.5,8)
    check("handprints","negative",plan["plan_digest"]!=other["plan_digest"],"seed control diverges")
    refuses("handprints","bad fraction",lambda:core.plan_handprint_additions(hp_rows(5),"R",0.0,7),"FRACTION")
    refuses("handprints","empty selected wall",lambda:core.plan_handprint_additions(hp_rows(5,"L"),"R",0.5,7),"SOURCE_EMPTY")
    source=EDITOR.read_text(encoding="utf-8")
    check("handprints","positive","def write_topdown_png" in source and "zlib.compress" in source,"DRY PNG writer")
    # Run-51c regression: the old section-count guard rejects B06's base +
    # additive camera-shake sections; the composed pose passes; real drift
    # with two absolute owners at one time still refuses.
    old_logic_refuses = len([("ABSOLUTE", [10, 20, 30]), ("ADDITIVE", [1, -2, 0.5])]) != 1
    check("handprints", "negative", old_logic_refuses, "old one-section guard refuses logged state")
    got = __import__("p38_editor").compose_camera_layers(
        [("ABSOLUTE", [10, 20, 30]), ("ADDITIVE", [1, -2, 0.5])], "B06|frame=3200")
    check("handprints", "positive", got == [11, 18, 30.5], "base plus additive camera pose")
    refuses("handprints", "two absolute camera sections",
            lambda: __import__("p38_editor").compose_camera_layers(
                [("ABSOLUTE", [0, 0, 0]), ("ABSOLUTE", [1, 1, 1])], "B06|frame=3200"),
            "CAMERA_ABSOLUTE_SECTION_COUNT")


def test_lid():
    plan=core.lid_closed_plan([(0,-90),(100,-90),(200,0)])
    check("lid","positive",plan["after"]==[(0,0.0),(100,0.0),(200,0.0)] and plan["closed_source"]=="final key","final endpoint held")
    explicit=core.lid_closed_plan([(0,-90),(200,0)],-5)
    check("lid","positive",all(v==-5 for _,v in explicit["after"]),"explicit closed arg")
    refuses("lid","one key",lambda:core.lid_closed_plan([(0,0)]),"LT_2")
    refuses("lid","duplicate key",lambda:core.lid_closed_plan([(0,-90),(0,0)]),"DUPLICATE")
    check("lid","negative",plan["before"]!=plan["after"],"positive control changes open keys")


def test_spoiler():
    keys=core.spoiler_keys(0,6000,96)
    check("spoiler","positive",keys==[(0,True),(96,False)],"VISIBLE semantics")
    refuses("spoiler","cut at start",lambda:core.spoiler_keys(0,6000,0),"CUT_RANGE")
    refuses("spoiler","cut after end",lambda:core.spoiler_keys(0,6000,7000),"CUT_RANGE")
    source=EDITOR.read_text(encoding="utf-8")
    check("spoiler","positive","set_property_name_and_path(\"bHidden\", \"bHidden\")" in source,"exact actor property")
    check("spoiler","negative","bHiddenInGame" not in source,"inert property absent")
    before=source.index("find_or_plan_binding(seq, world, actor)")
    add=source.index("seq.add_possessable(actor)")
    check("spoiler","positive",before<add,"lookup precedes add_possessable")
    check("spoiler","positive","ADD_POSSESSABLE_RETURNED_EXISTING" in source,"existing-binding return refuses rename")


def test_static():
    for path in (HERE/"p38_core.py",EDITOR,HERE/"p38_preview.py",HERE/"p38_run.py",HERE/"s3_ground_probe.py"):
        py_compile.compile(str(path),doraise=True)
        check("static","positive",True,"compile "+path.name)
    source=EDITOR.read_text(encoding="utf-8")
    check("ground_fix","negative","GROUND_LIGHT_LABELS_REQUIRED_FROM_PROBE" in source,"light fix requires proved labels")
    for token in ("backup_packages(","write_json(rec_path, rec, exclusive=True)","require_census(","save_current_level()",
                  "EditorAssetLibrary.save_asset","P38_HANDPRINTS_APPLY_OK","P38_LID_APPLY_OK","P38_SPOILER_APPLY_OK"):
        check("static","positive",token in source,"contract token "+token)
    check("static","negative","save_dirty_packages" not in source and "save_all" not in source.lower(),"no broad save")
    check("static","negative","os.remove(" not in source and "unlink(" not in source,"no permanent file deletion")
    tree=ast.parse((HERE/"p38_core.py").read_text(encoding="utf-8"))
    draws=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="random"]
    check("static","positive",len(draws)==2,"random draws isolated to one-value helpers")


def main():
    test_ground(); test_handprints(); test_lid(); test_spoiler(); test_static()
    failures=sum(len(g["failures"]) for g in groups.values())
    for name in ("ground_probe","ground_fix","handprints","lid","spoiler","static"):
        g=groups[name]
        print("P38_%s_HARNESS|positive=%d|negative=%d|fail=%d" % (name.upper(),g["positive"],g["negative"],len(g["failures"])))
        for failure in g["failures"]: print("FAIL|%s|%s"%(name,failure))
    total=sum(g["positive"]+g["negative"] for g in groups.values())
    result={"schema":"p38_harness/1","total_pass":total,"total_fail":failures,"groups":groups}
    RESULT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("P38_HARNESS_RESULT|pass=%d|fail=%d|groups=%d|report=%s"%(total,failures,len(groups),RESULT))
    return 1 if failures else 0


if __name__=="__main__":
    raise SystemExit(main())
