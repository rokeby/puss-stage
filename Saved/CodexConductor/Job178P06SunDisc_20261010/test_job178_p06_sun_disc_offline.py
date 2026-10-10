import importlib.util,json,math,os,sys
HERE=os.path.dirname(os.path.abspath(__file__));spec=importlib.util.spec_from_file_location("core",os.path.join(HERE,"job178_p06_sun_disc_core.py"));C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
r=[]
def check(n,v,c):r.append((n,bool(v),c));print(("PASS" if v else "FAIL")+"|"+c+"|"+n)
def refused(fn):
 try:fn();return False
 except C.ContractError:return True
a=C.validate_args(json.load(open(os.path.join(HERE,"job178_p06_sun_disc_args.json"),encoding="utf-8")))
check("dry default",a["mode"]=="DRY","positive")
check("wrong apply confirm",refused(lambda:C.validate_args(dict(a,mode="APPLY",confirm="apply"))),"negative")
check("apply active record",refused(lambda:C.validate_args(dict(a,mode="APPLY",confirm=C.CONFIRM["APPLY"]),True)),"negative")
check("revert requires record",refused(lambda:C.validate_args(dict(a,mode="REVERT",confirm=C.CONFIRM["REVERT"]),False)),"negative")
w=C.opening_from_clearance({"left":2,"right":4,"down":3,"up":5})
check("window angular dimensions",w["horizontal_deg"]==6 and w["vertical_deg"]==8 and w["smaller_deg"]==6,"positive")
check("window centre",w["center_h_deg"]==1 and w["center_v_deg"]==1,"positive")
check("unbounded window refused",refused(lambda:C.opening_from_clearance({"left":0,"right":4,"down":3,"up":5})),"negative")
s=C.target_size(w,.8);check("80 percent smaller dimension",abs(s-4.8)<1e-9,"positive")
check("disc fits",C.disc_fits(s,w,.8),"positive")
check("oversize detected",not C.disc_fits(6.1,w,.8),"negative")
cur={"entry_phase_offset_cycles":C.setting_phase_for_elevation(7.0)};v=[math.cos(math.radians(7)),0,math.sin(math.radians(7))]
p=C.center_plan(cur,v,.25,1888.4,10)
check("centering preserves matching dusk",abs(p["sunset_shift_seconds"]+.25)<1e-5,"positive")
check("large sunset retime refused",refused(lambda:C.center_plan(cur,[1,0,0],.25,1888.4,10)),"negative")
check("setting phase mirror",abs(C.phase_elevation(C.setting_phase_for_elevation(7))-7)<1e-6,"positive")
live_source=open(os.path.join(HERE,"job178_p06_sun_disc.py"),encoding="utf-8").read()
check("UE58 visibility trace query", "TraceTypeQuery.TRACE_TYPE_QUERY1" in live_source and "convert_to_trace_type" not in live_source,"positive")
bad=[x for x in r if not x[1]];print("JOB178B_OFFLINE_%s|pass=%d|fail=%d|positive=%d|negative=%d"%("OK" if not bad else "FAILED",len(r)-len(bad),len(bad),sum(x[2]=="positive" for x in r),sum(x[2]=="negative" for x in r)));sys.exit(1 if bad else 0)
