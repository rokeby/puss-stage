"""Job 178B: measure the P06 end-window and fit/show the production sun disc.

DRY samples the authored Passage camera at arrival and near the end without
opening/scrubbing Sequencer. Angular opening dimensions come from bounded
Visibility traces. APPLY sizes the disc to 80% of the chosen window's smaller
dimension, centres the existing dusk cycle within a strict retime budget, and
shows the existing production SkyAtmosphere only for the P06 Master section.
"""
from __future__ import annotations
import datetime, hashlib, importlib.util, json, math, os, shutil
try: import unreal
except ModuleNotFoundError: unreal=None
HERE=os.path.dirname(os.path.abspath(__file__));PROJECT=os.path.normpath(os.path.join(HERE,"..","..",".."))
ARGS=os.path.join(HERE,"job178_p06_sun_disc_args.json");ACTIVE=os.path.join(HERE,"job178b_ACTIVE.json")
WORLD="/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice";SHOW="/Game/InfinityStage/Dev/DA_InfinityStage_V1Show";MASTER="/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
OWNER="JOB178 P06 Sun Disc [OWNED]"
spec=importlib.util.spec_from_file_location("job178b_core",os.path.join(HERE,"job178_p06_sun_disc_core.py"));C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
def require(v,m):C.require(v,m)
def asset_id(v):
 try:s=str(v.get_path_name())
 except Exception:s=str(v)
 return s.split(".",1)[0]
def guid(v):
 try:s=str(unreal.GuidLibrary.conv_guid_to_string(v))
 except Exception:s=str(v)
 s="".join(c for c in s if c in "0123456789abcdefABCDEF");require(len(s)==32,"GUID|"+str(v));return s.upper()
def parse_guid(text):
 res=unreal.GuidLibrary.parse_string_to_guid(text);g,ok=(res if isinstance(res,tuple) else (res,True));require(bool(ok) and guid(g)==text,"GUID_PARSE|"+text);return g
def label(a):return str(a.get_actor_label())
def actors():return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
def census():
 u=unreal.EditorLoadingAndSavingUtils;return {"content":sorted(asset_id(x) for x in u.get_dirty_content_packages()),"maps":sorted(asset_id(x) for x in u.get_dirty_map_packages())}
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def write(p,v,exclusive=False):
 with open(p,"x" if exclusive else "w",encoding="utf-8") as f:json.dump(v,f,indent=2,sort_keys=True,default=str);f.flush();os.fsync(f.fileno())
def package_file(pkg):
 base=os.path.join(PROJECT,"Content",*pkg[6:].split("/"))
 for e in (".uasset",".umap"):
  if os.path.isfile(base+e):return base+e
 raise C.ContractError("PACKAGE_FILE|"+pkg)
def backup(run,suffix,packages,facts):
 root=os.path.join(PROJECT,"Backups","PreJob178BP06SunDisc%s-%s"%(suffix,run));os.makedirs(root,exist_ok=False);rows=[]
 for pkg in packages:
  src=package_file(pkg);dst=os.path.join(root,"Content",pkg[6:].replace("/",os.sep)+os.path.splitext(src)[1]);os.makedirs(os.path.dirname(dst),exist_ok=True);shutil.copy2(src,dst);require(sha(src)==sha(dst),"BACKUP_HASH|"+pkg);rows.append({"package":pkg,"source":src,"backup":dst,"sha256":sha(dst),"bytes":os.path.getsize(dst)})
 out={"run":run,"packages":rows,"facts":facts};write(os.path.join(root,"manifest.json"),out,True);out["root"]=root;return out
def unwrap(value,count,name):
 if isinstance(value,tuple) and len(value)==count+1 and isinstance(value[0],bool):require(value[0],name+"_FALSE");value=value[1:]
 require(isinstance(value,tuple) and len(value)==count,name+"_SHAPE");return value
def actor_one(name,cls=None):
 hits=[a for a in actors() if label(a)==name and (cls is None or a.get_class().get_name()==cls)];require(len(hits)==1,"ACTOR_COUNT|%s|%d"%(name,len(hits)));return hits[0]
def context():
 ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);require(ed.get_game_world() is None,"PIE_ACTIVE");require(asset_id(ed.get_editor_world())==WORLD,"WRONG_WORLD");require(unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is None,"SEQUENCER_OPEN");require(census()=={"content":[],"maps":[]},"DIRTY_BEFORE|"+json.dumps(census()));return ed.get_editor_world()
def cycle_rows(show):
 out=[]
 for p in show.get_editor_property("passage_settings"):
  c=p.get_editor_property("celestial_cycle");out.append({"label":str(p.get_editor_property("label")),"guid":guid(p.get_editor_property("passage_guid")),"animate":bool(c.get_editor_property("animate")),"cycle_duration_seconds":float(c.get_editor_property("cycle_duration_seconds")),"cycle_rate_multiplier":float(c.get_editor_property("cycle_rate_multiplier")),"entry_phase_offset_cycles":float(c.get_editor_property("entry_phase_offset_cycles"))})
 return out
def set_cycle(show,guid_text,values):
 rows=list(show.get_editor_property("passage_settings"));hits=[i for i,p in enumerate(rows) if guid(p.get_editor_property("passage_guid"))==guid_text];require(len(hits)==1,"PASSAGE_GUID_COUNT");p=rows[hits[0]];c=p.get_editor_property("celestial_cycle")
 for k in ("animate","cycle_duration_seconds","cycle_rate_multiplier","entry_phase_offset_cycles"):c.set_editor_property(k,bool(values[k]) if k=="animate" else float(values[k]))
 p.set_editor_property("celestial_cycle",c);rows[hits[0]]=p;show.modify();show.set_editor_property("passage_settings",rows)
def p06_scope(show,master,args):
 ps=[p for p in show.get_editor_property("passage_settings") if guid(p.get_editor_property("passage_guid"))==args["passage_guid"]];require(len(ps)==1,"P06_PASSAGE_COUNT");sections=[]
 for t in master.get_tracks():
  if "InfinityPassage" not in t.get_class().get_name():continue
  for s in t.get_sections():
   try:g=guid(s.get_editor_property("passage_guid"))
   except Exception:continue
   if g==args["passage_guid"]:sections.append(s)
 require(len(sections)==1,"P06_MASTER_SECTION_COUNT");c=ps[0].get_editor_property("celestial_cycle")
 return {"start_frame":int(sections[0].get_start_frame()),"end_frame":int(sections[0].get_end_frame()),"cycle":{"animate":bool(c.get_editor_property("animate")),"cycle_duration_seconds":float(c.get_editor_property("cycle_duration_seconds")),"cycle_rate_multiplier":float(c.get_editor_property("cycle_rate_multiplier")),"entry_phase_offset_cycles":float(c.get_editor_property("entry_phase_offset_cycles"))}}
def pose_row(show,args,t_seconds):
 pg=parse_guid(args["passage_guid"]);lib=unreal.InfinityStageCameraPilotLibrary;start,end=unwrap(lib.get_passage_frame_range(show,pg),2,"FRAME_RANGE");tick=int(round(int(start)+t_seconds*args["camera_ticks_per_second"]));view,focal,focus=unwrap(lib.get_passage_camera_pose(show,pg,tick),3,"CAMERA_POSE");rot=view.rotation.rotator();f=unreal.MathLibrary.get_forward_vector(rot);r=unreal.MathLibrary.get_right_vector(rot);u=unreal.MathLibrary.get_up_vector(rot)
 return {"seconds":t_seconds,"tick":tick,"range_ticks":[int(start),int(end)],"location":[float(view.translation.x),float(view.translation.y),float(view.translation.z)],"rotation_rpy_deg":[float(rot.roll),float(rot.pitch),float(rot.yaw)],"focal_mm":float(focal),"focus_cm":float(focus),"forward":[f.x,f.y,f.z],"right":[r.x,r.y,r.z],"up":[u.x,u.y,u.z]}
def unit(v):
 n=math.sqrt(sum(x*x for x in v));return [x/n for x in v]
def ray_dir(p,h,v):
 h=math.tan(math.radians(h));v=math.tan(math.radians(v));return unit([p["forward"][i]+h*p["right"][i]+v*p["up"][i] for i in range(3)])
def trace_hit(world,p,h,v,args):
 d=ray_dir(p,h,v);a=unreal.Vector(*p["location"]);b=unreal.Vector(*(p["location"][i]+d[i]*args["trace_distance_cm"] for i in range(3)));tt=unreal.SystemLibrary.convert_to_trace_type(unreal.CollisionChannel.ECC_VISIBILITY);res=unreal.SystemLibrary.line_trace_single(world,a,b,tt,True,[],unreal.DrawDebugTrace.NONE,True)
 hit=res[1] if isinstance(res,tuple) and res[0] else None
 if hit is None:return None
 vals=hit.to_tuple();actor=vals[9] if len(vals)>9 else None;return {"actor":label(actor) if actor else None,"distance_cm":float(vals[3]) if len(vals)>3 else None}
def clearance(world,p,args):
 require(trace_hit(world,p,0,0,args) is None,"WINDOW_CENTRE_OCCLUDED")
 out={};details={}
 for name,axis,sign in (("left","h",-1),("right","h",1),("down","v",-1),("up","v",1)):
  last=0.0;boundary=None
  steps=int(args["trace_limit_deg"]/args["trace_step_deg"])
  for i in range(1,steps+1):
   angle=sign*i*args["trace_step_deg"];hit=trace_hit(world,p,angle if axis=="h" else 0,angle if axis=="v" else 0,args)
   if hit is not None:boundary={"angle_deg":abs(angle),"hit":hit};break
   last=abs(angle)
  require(boundary is not None,"WINDOW_UNBOUNDED|"+name);out[name]=last;details[name]=boundary
 win=C.opening_from_clearance(out);win["boundary_hits"]=details;return win
def world_direction(p,h,v):return ray_dir(p,h,v)
def project(p,d):
 dot=lambda a,b:sum(a[i]*b[i] for i in range(3));f=dot(d,p["forward"]);return {"h_deg":math.degrees(math.atan2(dot(d,p["right"]),f)),"v_deg":math.degrees(math.atan2(dot(d,p["up"]),math.hypot(f,dot(d,p["right"])))),"forward_dot":f}
def sun_dir(az,elev):
 a,e=math.radians(az),math.radians(elev);return [math.cos(e)*math.cos(a),math.cos(e)*math.sin(a),math.sin(e)]
def gather(world,args):
 show=unreal.load_asset(SHOW);master=unreal.load_asset(MASTER);require(show and master,"SHOW_OR_MASTER");scope=p06_scope(show,master,args);cycles=cycle_rows(show);p06=[x for x in cycles if x["guid"]==args["passage_guid"]][0];require(p06["animate"] and p06["cycle_rate_multiplier"]==1.0,"P06_CYCLE_AUTHORITY");require(not [x for x in cycles if x["guid"]!=args["passage_guid"] and x["animate"]],"OTHER_PASSAGE_ANIMATED")
 rigs=[a for a in actors() if a.get_class().get_name()=="InfinityStageCelestialRig"];require(len(rigs)==1,"RIG_COUNT");rig=rigs[0];az=float(rig.get_editor_property("sun_azimuth_degrees"));sun=actor_one(args["sun_actor_label"],"DirectionalLight");sky=actor_one(args["sky_actor_label"],"SkyAtmosphere");sun_comp=sun.get_component_by_class(unreal.DirectionalLightComponent);sky_comp=sky.get_component_by_class(unreal.SkyAtmosphereComponent);require(sun_comp and sky_comp,"SUN_SKY_COMPONENT")
 start,end=unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show,parse_guid(args["passage_guid"])),2,"FRAME_RANGE");duration=(int(end)-int(start))/args["camera_ticks_per_second"];times={"arrival":args["arrival_seconds"],"near_end":duration-args["near_end_margin_seconds"]};require(times["near_end"]>times["arrival"],"SAMPLE_ORDER")
 samples={}
 for name,t in times.items():
  p=pose_row(show,args,t);w=clearance(world,p,args);phase=(p06["entry_phase_offset_cycles"]+t/p06["cycle_duration_seconds"])%1.0;elev=C.phase_elevation(phase);d=sun_dir(az,elev);samples[name]={"camera":p,"window":w,"sun":{"phase":phase,"elevation_deg":elev,"azimuth_deg":az,"projection":project(p,d),"direction":d},"centre_ray_occluded":trace_hit(world,p,w["center_h_deg"],w["center_v_deg"],args) is not None}
 fit=samples[args["fit_sample"]]["window"];size=C.target_size(fit,args["fit_fraction"]);cs=samples[args["center_sample"]];target=world_direction(cs["camera"],cs["window"]["center_h_deg"],cs["window"]["center_v_deg"]);center=C.center_plan(p06,target,times[args["center_sample"]],p06["cycle_duration_seconds"],args["max_sunset_shift_seconds"])
 return {"show":show,"master":master,"rig":rig,"sun":sun,"sun_comp":sun_comp,"sky":sky,"sky_comp":sky_comp,"scope":scope,"cycles":cycles,"p06":p06,"samples":samples,"times":times,"target_size_deg":size,"center":center,"current_source_angle_deg":float(sun_comp.get_editor_property("light_source_angle")),"sky_hidden":bool(sky.is_hidden()),"sky_component_visible":bool(sky_comp.get_editor_property("visible"))}
def bindings_for(seq,obj,world):
 want=str(obj.get_path_name());out=[]
 for b in seq.get_bindings():
  try:
   if any(str(x.get_path_name())==want for x in seq.locate_bound_objects(b,world)):out.append(b)
  except Exception:pass
 return out
def binding_for(seq,obj,world,name,created):
 hits=bindings_for(seq,obj,world);require(len(hits)<=1,"MULTIBOUND|"+name)
 if hits:return hits[0]
 before={guid(x.get_id()) for x in seq.get_bindings()};b=seq.add_possessable(obj)
 if guid(b.get_id()) not in before:b.set_display_name(name);created.append(guid(b.get_id()))
 return b
def add_track(seq,obj,world,name,created,start,end,prop,value,cls):
 b=binding_for(seq,obj,world,name,created);require(not any(str(t.get_property_name())==prop for t in b.get_tracks()),"TRACK_CONFLICT|"+prop);t=b.add_track(cls);t.set_property_name_and_path(prop,prop);t.set_display_name(OWNER+" "+name+" "+prop);s=t.add_section();s.set_range(start,end);s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE);ch=list(s.get_all_channels());require(len(ch)==1,"TRACK_CHANNEL|"+prop);ch[0].set_default(value);return {"binding":guid(b.get_id()),"class":t.get_class().get_name(),"property":[prop,prop],"display":str(t.get_display_name()),"value":value,"range":[start,end]}
def add_visibility(seq,actor,world,name,created,start,end):
 b=binding_for(seq,actor,world,name,created);require(not any(t.get_class().get_name()=="MovieSceneVisibilityTrack" for t in b.get_tracks()),"VIS_TRACK_CONFLICT");t=b.add_track(unreal.MovieSceneVisibilityTrack);t.set_property_name_and_path("bHidden","bHidden");t.set_display_name(OWNER+" "+name);s=t.add_section();s.set_range(start,end);s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE);ch=list(s.get_all_channels());require(len(ch)==1,"VIS_CHANNEL");ch[0].set_default(True);return {"binding":guid(b.get_id()),"class":t.get_class().get_name(),"property":["bHidden","bHidden"],"display":str(t.get_display_name()),"value":True,"range":[start,end]}
def remove_tracks(seq,specs,created):
 wanted={(x["binding"],x["class"],tuple(x["property"])) for x in specs};removed=0
 for b in seq.get_bindings():
  for t in list(b.get_tracks()):
   try:key=(guid(b.get_id()),t.get_class().get_name(),(str(t.get_property_name()),str(t.get_property_path())))
   except Exception:continue
   if key in wanted:b.remove_track(t);removed+=1
 require(removed==len(specs),"REMOVE_TRACKS|%d/%d"%(removed,len(specs)))
 for b in list(seq.get_bindings()):
  if guid(b.get_id()) in set(created) and not list(b.get_tracks()):b.remove()
def save_named(packages):
 expected={"content":sorted(x for x in packages if x!=WORLD),"maps":[WORLD] if WORLD in packages else []};require(census()==expected,"DIRTY_SCOPE|"+json.dumps(census()))
 for p in packages:
  if p==WORLD:require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(),"SAVE_LEVEL")
  else:require(unreal.EditorAssetLibrary.save_asset(p,only_if_is_dirty=True),"SAVE|"+p)
 require(census()=={"content":[],"maps":[]},"POST_SAVE_DIRTY")
def run_dry(args,run,g):
 out={k:v for k,v in g.items() if k not in ("show","master","rig","sun","sun_comp","sky","sky_comp")};out.update({"schema":"job178b_dry_v1","run":run,"mode":"DRY","mutated":0,"dirty_before":census(),"dirty_after":census(),"visibility_diagnosis":{"sun_inside_camera_at_arrival":g["samples"]["arrival"]["sun"]["projection"]["forward_dot"]>0,"sun_occluded_at_window_centre":g["samples"]["arrival"]["centre_ray_occluded"],"production_sky_actor_hidden":g["sky_hidden"],"production_sky_component_visible":g["sky_component_visible"],"source_conclusion":"disc cannot render while the production SkyAtmosphere actor/component is hidden"}});out["plan_hash"]=C.stable_hash(out);path=os.path.join(HERE,"job178b_dry_%s.json"%run);write(path,out,True);require(census()==out["dirty_before"],"DRY_DIRTIED")
 for name in ("arrival","near_end"):
  x=g["samples"][name];unreal.log("JOB178B_MEASURE|run=%s|sample=%s|window_h=%.3f|window_v=%.3f|window_small=%.3f|current_disc=%.3f|sun_h=%.3f|sun_v=%.3f"%(run,name,x["window"]["horizontal_deg"],x["window"]["vertical_deg"],x["window"]["smaller_deg"],g["current_source_angle_deg"],x["sun"]["projection"]["h_deg"],x["sun"]["projection"]["v_deg"]))
 unreal.log("JOB178B_P06_SUN_DISC_DRY_OK|run=%s|arrival_window=%.3fx%.3f|near_end_window=%.3fx%.3f|current_disc=%.3f|target_disc=%.3f|fit=%.2f|sky_hidden=%d|mutated=0|dirty=0+0|report=%s"%(run,g["samples"]["arrival"]["window"]["horizontal_deg"],g["samples"]["arrival"]["window"]["vertical_deg"],g["samples"]["near_end"]["window"]["horizontal_deg"],g["samples"]["near_end"]["window"]["vertical_deg"],g["current_source_angle_deg"],g["target_size_deg"],args["fit_fraction"],g["sky_hidden"],path))
def run_apply(args,run,g,world):
 require(not os.path.exists(ACTIVE),"ACTIVE_RECORD_EXISTS");packages=[SHOW,MASTER,WORLD];pre=backup(run,"",packages,{"samples":g["samples"],"target_size":g["target_size_deg"],"center":g["center"]});record={"schema":"job178b_active_v1","status":"prepared","run":run,"backup":pre,"packages":packages,"before":{"cycle":g["p06"],"sun_azimuth_degrees":float(g["rig"].get_editor_property("sun_azimuth_degrees"))},"tracks":[],"created_bindings":[]};write(ACTIVE,record,True)
 after=dict(g["p06"],entry_phase_offset_cycles=g["center"]["entry_phase_offset_cycles"]);set_cycle(g["show"],args["passage_guid"],after);g["rig"].modify();g["rig"].set_editor_property("sun_azimuth_degrees",g["center"]["sun_azimuth_degrees"]);s,e=g["scope"]["start_frame"],g["scope"]["end_frame"]
 record["tracks"].append(add_visibility(g["master"],g["sky"],world,"Production Sky Visible",record["created_bindings"],s,e));record["tracks"].append(add_track(g["master"],g["sky_comp"],world,"Production Sky Component",record["created_bindings"],s,e,"bVisible",True,unreal.MovieSceneBoolTrack));record["tracks"].append(add_track(g["master"],g["rig"],world,"Foreign Sky Suppression",record["created_bindings"],s,e,"bSuppressForeignEnvironmentLighting",False,unreal.MovieSceneBoolTrack));record["tracks"].append(add_track(g["master"],g["sun_comp"],world,"Sun Disc Size",record["created_bindings"],s,e,"LightSourceAngle",g["target_size_deg"],unreal.MovieSceneFloatTrack));write(ACTIVE,record)
 expected_cycle=[x for x in cycle_rows(g["show"]) if x["guid"]==args["passage_guid"]][0];require(abs(expected_cycle["entry_phase_offset_cycles"]-after["entry_phase_offset_cycles"])<1e-6,"CYCLE_READBACK");require(abs(float(g["rig"].get_editor_property("sun_azimuth_degrees"))-g["center"]["sun_azimuth_degrees"])<1e-4,"AZIMUTH_READBACK");require(C.disc_fits(g["target_size_deg"],g["samples"][args["fit_sample"]]["window"],args["fit_fraction"]),"DISC_FIT_READBACK");require(not g["samples"][args["center_sample"]]["centre_ray_occluded"],"CENTER_OCCLUDED");save_named(packages);record["status"]="applied";record["after"]={"cycle":expected_cycle,"sun_azimuth_degrees":float(g["rig"].get_editor_property("sun_azimuth_degrees")),"source_angle_track":g["target_size_deg"]};record["dirty_after"]=census();write(ACTIVE,record);unreal.log("JOB178B_P06_SUN_DISC_APPLY_OK|run=%s|window_small=%.3f|disc=%.3f|fit=%.2f|centered=1|occluded=0|sky_p06_visible_track=1|backup=%s|readback=1|dirty=0+0|record=%s"%(run,g["samples"][args["fit_sample"]]["window"]["smaller_deg"],g["target_size_deg"],args["fit_fraction"],pre["root"],ACTIVE))
def run_revert(args,run,g,world):
 rec=json.load(open(ACTIVE,encoding="utf-8"));require(rec.get("status")=="applied","RECORD_STATUS");live=[x for x in cycle_rows(g["show"]) if x["guid"]==args["passage_guid"]][0];require(abs(live["entry_phase_offset_cycles"]-rec["after"]["cycle"]["entry_phase_offset_cycles"])<1e-6,"CYCLE_DRIFT");require(abs(float(g["rig"].get_editor_property("sun_azimuth_degrees"))-rec["after"]["sun_azimuth_degrees"])<1e-4,"AZIMUTH_DRIFT");pre=backup(run,"Revert",rec["packages"],{"apply_run":rec["run"]});remove_tracks(g["master"],rec["tracks"],rec["created_bindings"]);set_cycle(g["show"],args["passage_guid"],rec["before"]["cycle"]);g["rig"].modify();g["rig"].set_editor_property("sun_azimuth_degrees",rec["before"]["sun_azimuth_degrees"]);save_named(rec["packages"]);arch=ACTIVE+".reverted-"+run;os.replace(ACTIVE,arch);unreal.log("JOB178B_P06_SUN_DISC_REVERT_OK|run=%s|apply_run=%s|tracks=%d|backup=%s|dirty=0+0|record=%s"%(run,rec["run"],len(rec["tracks"]),pre["root"],arch))
def main():
 run="JOB178B-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S");args=C.validate_args(json.load(open(ARGS,encoding="utf-8")),os.path.exists(ACTIVE));world=context();g=gather(world,args);unreal.log("JOB178B_P06_SUN_DISC_START|run=%s|mode=%s"%(run,args["mode"]));{"DRY":lambda:run_dry(args,run,g),"APPLY":lambda:run_apply(args,run,g,world),"REVERT":lambda:run_revert(args,run,g,world)}[args["mode"]]()
if __name__=="__main__" and unreal is not None:main()
