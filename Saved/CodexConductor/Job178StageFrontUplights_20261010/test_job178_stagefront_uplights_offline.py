import importlib.util, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("core", os.path.join(HERE, "job178_stagefront_uplights_core.py"))
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
results=[]
def check(name, value, control):
    ok=bool(value); results.append((name,ok,control)); print(("PASS" if ok else "FAIL")+"|"+control+"|"+name)
def refused(fn):
    try: fn(); return False
    except C.ContractError: return True
args=C.validate_args(json.load(open(os.path.join(HERE,"job178_stagefront_uplights_args.json"),encoding="utf-8")))
check("dry confirm",args["mode"]=="DRY","positive")
check("wrong apply confirm refused",refused(lambda:C.validate_args(dict(args,mode="APPLY",confirm="yes"))),"negative")
check("apply active record refused",refused(lambda:C.validate_args(dict(args,mode="APPLY",confirm=C.CONFIRM["APPLY"]),True)),"negative")
check("revert requires record",refused(lambda:C.validate_args(dict(args,mode="REVERT",confirm=C.CONFIRM["REVERT"]),False)),"negative")
style={"intensity":350.0,"temperature_kelvin":3200.0,"inner_cone_angle_degrees":16.0,
"outer_cone_angle_degrees":24.0,"attenuation_radius_cm":1800.0,"light_falloff_exponent":12.0,
"volumetric_scattering_intensity":0.3,"color_rgb_linear":[1.0,.78,.54],"cast_shadows":False,
"cast_volumetric_shadow":False,"use_temperature":True,"use_inverse_squared_falloff":False}
pieces=[]
for i,(key,label,y,frac) in enumerate(C.PIECES):
    pieces.append({"label":label,"path":"/Map/A%d"%i,"tags":["PussStage.StageFront3D","PussStage.StageFront3D."+key.split("_")[0]],
                   "bounds_center_cm":[-300.0,y,700.0],"bounds_extent_cm":[100.0,100.0,700.0]})
plan=C.plan(pieces,style,args)
check("eight pieces and eight lights",len(plan["pieces"])==len(plan["lights"])==8,"positive")
check("every light maps one piece",{x["piece_label"] for x in plan["lights"]}==set(C.EXPECTED_LABELS),"positive")
check("all on stage lip",all(x["location_cm"][0]==-440.0 and x["location_cm"][2]==45.0 for x in plan["lights"]),"positive")
check("source style copied",all(x["style"]==style for x in plan["lights"]),"positive")
check("no shadows",all(not x["style"]["cast_shadows"] for x in plan["lights"]),"positive")
check("missing piece refused",refused(lambda:C.plan(pieces[:-1],style,args)),"negative")
bad=json.loads(json.dumps(pieces)); bad[0]["tags"]=[]
check("missing tag refused",refused(lambda:C.plan(bad,style,args)),"negative")
check("readback exact",C.compare_light(style,style)==[],"positive")
mut=dict(style,intensity=351.0)
check("readback drift detected",C.compare_light(mut,style)==["intensity"],"negative")
check("plan hash stable",plan["hash"]==C.plan(pieces,style,args)["hash"],"positive")
fails=[x for x in results if not x[1]]
pos=sum(x[2]=="positive" for x in results); neg=sum(x[2]=="negative" for x in results)
print("JOB178A_OFFLINE_%s|pass=%d|fail=%d|positive=%d|negative=%d"%("OK" if not fails else "FAILED",len(results)-len(fails),len(fails),pos,neg))
sys.exit(1 if fails else 0)
