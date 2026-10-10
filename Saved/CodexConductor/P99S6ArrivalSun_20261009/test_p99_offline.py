import importlib.util, json, math, os, re
HERE=os.path.dirname(os.path.abspath(__file__))
s=importlib.util.spec_from_file_location("p99_core",os.path.join(HERE,"p99_core.py")); C=importlib.util.module_from_spec(s); s.loader.exec_module(C)
passed=failed=positive_passed=negative_passed=0
def check(name,ok):
    global passed,failed,positive_passed,negative_passed
    negative=("negative" in name or name in ("direction behind","no bHiddenInGame","no editor control",
                                               "cycle authority preserved","no attachment move"))
    if ok:
        passed+=1
        if negative: negative_passed+=1
        else: positive_passed+=1
        print("PASS",name)
    else: failed+=1; print("FAIL",name)
def raises(fn,token):
    try: fn(); return False
    except Exception as e: return token in str(e)

check("enum plain",C.enum_name("LIGHT")=="LIGHT")
check("enum qualified",C.enum_name("<InfinityAttachmentKind.LIGHT: 1>")=="LIGHT")
check("guid digits",C.guid32("{12345678-1234-1234-1234-1234567890ab}")=="123456781234123412341234567890AB")
check("guid negative",raises(lambda:C.guid32("bad"),"GUID_NORMALIZE"))
check("legacy sun maths remains",C.sun_pitch_for_elevation(7)==-173)
check("legacy sun maths range",raises(lambda:C.sun_pitch_for_elevation(30),"SUN_ELEVATION_RANGE"))
v=C.direction_uv([1,0,0],[0,1,0],[0,0,1],[1,0,0],60,16/9)
check("direction centre",v["inside"] and all(abs(x-.5)<1e-9 for x in v["uv"]))
check("direction behind",not C.direction_uv([1,0,0],[0,1,0],[0,0,1],[-1,0,0],60,16/9)["inside"])
check("structure provenance",C.classify_provenance("Passage 06 Structure","StructureFixtures","SM_Lantern_ParCan",[],[],{})["tool"].startswith("MeshyFixtures"))
check("puss provenance",C.classify_provenance("PussFollowSpot","","",[],[],None)["tool"]=="puss_shadow_spot.py")
base=json.load(open(os.path.join(HERE,"p99_args.json"),encoding="utf-8"))
check("dry args",C.validate_args(base)["mode"]=="DRY")
check("apply confirm negative",raises(lambda:C.validate_args(dict(base,mode="APPLY")),"APPLY_CONFIRM"))
good=dict(base,mode="APPLY",confirm="APPLY JOB126 P06 ARRIVAL SUN",dry_report="x",dry_report_sha256="a"*64,
          pie_probe_report="y",pie_probe_report_sha256="b"*64,
          obstruction_action="HIDE_ACTORS_P06",obstruction_actor_labels=["P06 ParCan"])
check("apply hide",C.validate_args(good)["obstruction_action"]=="HIDE_ACTORS_P06")
check("apply missing PIE probe negative",raises(lambda:C.validate_args(dict(good,pie_probe_report="")),"PIE_PROBE_REPORT_REQUIRED"))
check("apply unset negative",raises(lambda:C.validate_args(dict(good,obstruction_action="UNSET")),"CHOOSE_OBSTRUCTION_ACTION"))
check("move route removed negative",raises(lambda:C.validate_args(dict(good,obstruction_action="MOVE_SHOW_ATTACHMENT")),"OBSTRUCTION_ACTION"))
check("empty actor list negative",raises(lambda:C.validate_args(dict(good,obstruction_actor_labels=[])),"OBSTRUCTION_ACTOR_LABELS"))
check("wrong passage negative",raises(lambda:C.validate_args(dict(good,passage_label="Scene 6")),"PASSAGE_SCOPE"))
check("revert confirm negative",raises(lambda:C.validate_args(dict(base,mode="REVERT")),"REVERT_CONFIRM"))
check("revert confirm",C.validate_args(dict(base,mode="REVERT",confirm="REVERT JOB126 P06 ARRIVAL SUN"))["mode"]=="REVERT")
source=open(os.path.join(HERE,"p99_s6_arrival_sun.py"),encoding="utf-8").read()
check("bHidden exact",'set_property_name_and_path("bHidden","bHidden")' in source)
check("no bHiddenInGame", "bHiddenInGame" not in source)
check("LinearColor trap not present", "set_light_color" not in source)
check("no editor control",not any(x in source for x in ("editor_request_end_play","quit_editor","open_level_sequence","SequencerTools.get_bound_objects")))
check("normalizers used","C.guid32" in source and "C.enum_name" in source)
check("backup before writes",source.index("pre=backup(run,packages)") < source.index("spawn_actor_from_class", source.index("def apply")))
check("success markers",all(x in source for x in ("JOB126_P06_DRY_OK","JOB126_P06_APPLY_OK","JOB126_P06_REVERT_OK")))
check("non-PIE DRY and separate PIE probe",'def dry_editor' in source and 'def pie_probe' in source and
      'if args["mode"]=="DRY": return dry_editor' in source and "JOB126_P06_PIE_PROBE_OK" in source)
check("save narrow","save_asset(p,only_if_is_dirty=True)" in source and "save_dirty_packages" not in source)
check("structure exact ids",all(x in source for x in ("cue_guid","attachment_guid","instance_index")))
check("P06 only",'seg_label==args["passage_label"]' in source and '"NOT_PASSAGE_6|' in source)
check("P06 Master range","def p06_scope" in source and 's.set_range(start,end)' in source)
check("cycle authority preserved","MovieScene3DTransformTrack" not in source and '"Intensity"' not in source)
check("sky runtime gate",'bSuppressForeignEnvironmentLighting' in source and '"bVisible"' in source)
check("no attachment move","set_tf(" not in source[source.index("def apply"):source.index("def remove_owned")])
check("track identity readback",'identity=(C.guid32(b.get_id()),t.get_class().get_name(),tuple(prop))' in source and
      'remove_owned(seq,rec["owned_tracks"])' in source)
print("JOB126_HARNESS|positive=%d|negative=%d|pass=%d|fail=%d"%(positive_passed,negative_passed,passed,failed))
raise SystemExit(1 if failed else 0)
