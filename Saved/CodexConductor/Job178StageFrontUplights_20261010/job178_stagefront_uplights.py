"""Job 178A live tool: one P87-matched uplight for each placed 3D stage-front piece.

DRY is the default and lists all eight label/tag matches plus their proposed
lights. APPLY and REVERT require exact confirms, backups, records, narrow saves,
read-back and run-id log markers. This file is only executed later by conductor.
"""
from __future__ import annotations

import datetime, hashlib, importlib.util, json, os, shutil, types

try: import unreal
except ModuleNotFoundError: unreal = None

HERE=os.path.dirname(os.path.abspath(__file__))
PROJECT=os.path.normpath(os.path.join(HERE,"..","..",".."))
ARGS=os.path.join(HERE,"job178_stagefront_uplights_args.json")
ACTIVE=os.path.join(HERE,"job178a_ACTIVE.json")
WORLD="/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW="/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
P01_PREFIX="Passage 01"
spec=importlib.util.spec_from_file_location("job178a_core",os.path.join(HERE,"job178_stagefront_uplights_core.py"))
C=importlib.util.module_from_spec(spec); spec.loader.exec_module(C)

def require(v,m): C.require(v,m)
def asset_id(v):
    if v is None:return None
    try:s=str(v.get_path_name())
    except Exception:s=str(v)
    return s.split(".",1)[0]
def guid(v):
    try: text=str(unreal.GuidLibrary.conv_guid_to_string(v))
    except Exception: text=str(v)
    text="".join(x for x in text if x in "0123456789abcdefABCDEF")
    require(len(text)==32,"GUID|"+str(v)); return text.upper()
def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()
def write(path,value,exclusive=False):
    with open(path,"x" if exclusive else "w",encoding="utf-8") as f:
        json.dump(value,f,indent=2,sort_keys=True,default=str);f.flush();os.fsync(f.fileno())
def census():
    u=unreal.EditorLoadingAndSavingUtils
    return {"content":sorted(asset_id(x) for x in u.get_dirty_content_packages()),
            "maps":sorted(asset_id(x) for x in u.get_dirty_map_packages())}
def actors(): return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
def label(a): return str(a.get_actor_label())
def tags(a): return sorted(str(x) for x in a.get_editor_property("tags"))
def package_file(pkg):
    base=os.path.join(PROJECT,"Content",*pkg[6:].split("/"))
    for ext in (".uasset",".umap"):
        if os.path.isfile(base+ext):return base+ext
    raise C.ContractError("PACKAGE_FILE|"+pkg)
def backup(run,suffix,packages,facts):
    root=os.path.join(PROJECT,"Backups","PreJob178AStageFrontUplights%s-%s"%(suffix,run));os.makedirs(root,exist_ok=False)
    rows=[]
    for pkg in packages:
        src=package_file(pkg);dst=os.path.join(root,"Content",pkg[6:].replace("/",os.sep)+os.path.splitext(src)[1])
        os.makedirs(os.path.dirname(dst),exist_ok=True);shutil.copy2(src,dst);require(sha(src)==sha(dst),"BACKUP_HASH|"+pkg)
        rows.append({"package":pkg,"source":src,"backup":dst,"bytes":os.path.getsize(dst),"sha256":sha(dst)})
    out={"run":run,"packages":rows,"facts":facts};write(os.path.join(root,"manifest.json"),out,True);out["root"]=root;return out

def context(mode):
    ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);world=ed.get_editor_world()
    require(ed.get_game_world() is None,"PIE_ACTIVE")
    require(asset_id(world)==WORLD,"WRONG_WORLD|"+str(asset_id(world)))
    require(unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is None,"SEQUENCER_OPEN")
    require(census()=={"content":[],"maps":[]},"DIRTY_BEFORE|"+json.dumps(census()))
    return world

def attachments(show):
    out=[]
    for i,q in enumerate(show.get_editor_property("cues")):
        try: rows=list(q.get_editor_property("wing_pair").get_editor_property("attachments"))
        except Exception: continue
        for a in rows: out.append((i,q,a))
    return out

def light_style(a):
    s=a.get_editor_property("lighting"); col=s.get_editor_property("color")
    return {"intensity":float(s.get_editor_property("intensity")),
            "temperature_kelvin":float(s.get_editor_property("temperature_kelvin")),
            "inner_cone_angle_degrees":float(s.get_editor_property("inner_cone_angle_degrees")),
            "outer_cone_angle_degrees":float(s.get_editor_property("outer_cone_angle_degrees")),
            "attenuation_radius_cm":float(s.get_editor_property("attenuation_radius_cm")),
            "light_falloff_exponent":float(s.get_editor_property("light_falloff_exponent")),
            "volumetric_scattering_intensity":float(s.get_editor_property("volumetric_scattering_intensity")),
            "color_rgb_linear":[float(col.r),float(col.g),float(col.b)],
            "cast_shadows":bool(s.get_editor_property("cast_shadows")),
            "cast_volumetric_shadow":bool(s.get_editor_property("cast_volumetric_shadow")),
            "use_temperature":bool(s.get_editor_property("use_temperature")),
            "use_inverse_squared_falloff":bool(s.get_editor_property("use_inverse_squared_falloff"))}

def gather(args):
    show=unreal.load_asset(SHOW);require(show is not None,"SHOW_MISSING")
    live=actors(); found=[]
    for wanted in C.EXPECTED_LABELS:
        hits=[a for a in live if label(a)==wanted and "PussStage.StageFront3D" in tags(a)]
        require(len(hits)==1,"PIECE_COUNT|%s|%d"%(wanted,len(hits)));a=hits[0]
        centre,extent=a.get_actor_bounds(False)
        found.append({"label":wanted,"path":str(a.get_path_name()),"tags":tags(a),
                      "bounds_center_cm":[float(centre.x),float(centre.y),float(centre.z)],
                      "bounds_extent_cm":[float(extent.x),float(extent.y),float(extent.z)]})
    p87=[(i,q,a) for i,q,a in attachments(show) if str(a.get_editor_property("label")).startswith(C.P87_PREFIX)]
    require(len(p87)==6,"P87_SOURCE_COUNT|%d"%len(p87));require(len({x[0] for x in p87})==1,"P87_SOURCE_CUE")
    style=light_style(p87[0][2]);require(not C.compare_light(light_style(p87[0][2]),style),"P87_STYLE")
    for _,_,a in p87[1:]:require(not C.compare_light(light_style(a),style),"P87_STYLE_DRIFT|"+str(a.get_editor_property("label")))
    # The live record is authority; these declared values catch an accidental wrong source family.
    expected={"intensity":350.0,"temperature_kelvin":3200.0,"inner_cone_angle_degrees":16.0,
              "outer_cone_angle_degrees":24.0,"attenuation_radius_cm":1800.0,"light_falloff_exponent":12.0,
              "volumetric_scattering_intensity":.3,"color_rgb_linear":[1.0,.78,.54],"cast_shadows":False,
              "cast_volumetric_shadow":False,"use_temperature":True,"use_inverse_squared_falloff":False}
    require(not C.compare_light(style,expected,1e-3),"P87_NOT_EXPECTED_STYLE|"+json.dumps(C.compare_light(style,expected,1e-3)))
    owned=[a for _,_,a in attachments(show) if str(a.get_editor_property("label")).startswith(C.OWNER_PREFIX)]
    return {"show":show,"pieces":found,"style":style,"target_index":p87[0][0],"owned":owned,
            "plan":C.plan(found,style,args)}

def load_p13():
    path=os.path.join(PROJECT,"Saved","CodexConductor","opening_lighting_p13.py")
    source=open(path,encoding="utf-8").read();tail='\nif unreal is not None:\n    main()\nelif __name__ == "__main__":\n    offline_preview_main()\n'
    require(tail in source,"P13_HELPER_TAIL_DRIFT");source=source.replace(tail,"\n")
    m=types.ModuleType("job178a_p13_helpers");m.__file__=path;exec(compile(source,path,"exec"),m.__dict__)
    return m

def fixture(row):
    s=row["style"]; roll,pitch,yaw=row["rotation_rpy_deg"]
    return {"label":row["label"],"relative_location_cm":row["location_cm"],"start_rotation_rpy_deg":[roll,pitch,yaw],
            "rotation_keys":[],"intensity_keys":[],"intensity_cd":s["intensity"],
            "inner_cone_deg":s["inner_cone_angle_degrees"],"outer_cone_deg":s["outer_cone_angle_degrees"],
            "falloff_exponent":s["light_falloff_exponent"],"source_radius_cm":2.0,"soft_source_radius_cm":6.0,
            "temperature_kelvin":s["temperature_kelvin"],"color_rgb_linear":s["color_rgb_linear"],
            "attenuation_cm":s["attenuation_radius_cm"],"volumetric_scattering":s["volumetric_scattering_intensity"],
            "cast_shadows":s["cast_shadows"],"cast_volumetric_shadows":s["cast_volumetric_shadow"]}

def materialize(show):
    hits=[a for a in actors() if a.get_class().get_name()=="InfinityStagePassageActor" and label(a).startswith(P01_PREFIX)
          and a.get_editor_property("show_asset")==show]
    require(len(hits)==1,"P01_ACTOR_COUNT|%d"%len(hits));require(bool(hits[0].materialize_passage()),"P01_MATERIALIZE")

def save_named():
    dirty=census();require(dirty=={"content":[SHOW],"maps":[WORLD]},"DIRTY_SCOPE|"+json.dumps(dirty))
    require(unreal.EditorAssetLibrary.save_asset(SHOW,only_if_is_dirty=True),"SAVE_SHOW")
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(),"SAVE_LEVEL")
    require(census()=={"content":[],"maps":[]},"POST_SAVE_DIRTY|"+json.dumps(census()))

def readback(g,ids):
    rows=[]
    for _,_,a in attachments(g["show"]):
        if guid(a.get_editor_property("attachment_guid")) not in ids:continue
        xf=a.get_editor_property("relative_transform");r=xf.rotation.rotator();state={"guid":guid(a.get_editor_property("attachment_guid")),
          "label":str(a.get_editor_property("label")),"location_cm":[float(xf.translation.x),float(xf.translation.y),float(xf.translation.z)],
          "rotation_rpy_deg":[float(r.roll),float(r.pitch),float(r.yaw)],"style":light_style(a)};rows.append(state)
    require(len(rows)==8,"READBACK_COUNT|%d"%len(rows));by={x["label"]:x for x in rows}
    for want in g["plan"]["lights"]:
        got=by.get(want["label"]);require(got is not None,"READBACK_LABEL|"+want["label"])
        require(not C.compare_light(got["style"],want["style"],1e-3),"READBACK_STYLE|"+want["label"])
        require(max(abs(a-b) for a,b in zip(got["location_cm"],want["location_cm"]))<=.01,"READBACK_LOCATION|"+want["label"])
    return sorted(rows,key=lambda x:x["label"])

def run_dry(args,run,g):
    require(not g["owned"],"OWNED_LIGHTS_EXIST")
    path=os.path.join(HERE,"job178a_dry_%s.json"%run);out={"schema":"job178a_dry_v1","run":run,"mode":"DRY",
      "dirty_before":census(),"pieces_found":g["pieces"],"p87_source_count":6,"source_style":g["style"],
      "lights_per_piece":g["plan"]["lights"],"plan_hash":g["plan"]["hash"],"mutated":0,"dirty_after":census()}
    require(out["dirty_before"]==out["dirty_after"],"DRY_DIRTIED");write(path,out,True)
    for row in out["lights_per_piece"]:unreal.log("JOB178A_PAIR|run=%s|piece=%s|tags=%s|light=%s|loc=%s|aim=%s"%(run,row["piece_label"],next(x["tags"] for x in g["pieces"] if x["label"]==row["piece_label"]),row["label"],row["location_cm"],row["target_cm"]))
    unreal.log("JOB178A_STAGE_FRONT_UPLIGHTS_DRY_OK|run=%s|pieces=8|lights=8|p87_source=6|mutated=0|dirty=0+0|report=%s"%(run,path))

def run_apply(args,run,g):
    require(not g["owned"],"OWNED_LIGHTS_EXIST");require(not os.path.exists(ACTIVE),"ACTIVE_RECORD_EXISTS")
    pre=backup(run,"",[SHOW,WORLD],{"plan_hash":g["plan"]["hash"],"pieces":g["pieces"],"style":g["style"]})
    record={"schema":"job178a_active_v1","status":"prepared","run":run,"plan":g["plan"],"backup":pre,"guids":[],"readback":[]};write(ACTIVE,record,True)
    p13=load_p13();added=p13._mint(g["show"],g["target_index"],{"fixtures":[fixture(x) for x in g["plan"]["lights"]]},run)
    ids={x["guid"] for x in added};require(len(ids)==8,"MINT_COUNT");record["guids"]=sorted(ids);write(ACTIVE,record)
    materialize(g["show"]);record["readback"]=readback(g,ids);save_named();record["status"]="applied";record["dirty_after"]=census();write(ACTIVE,record)
    unreal.log("JOB178A_STAGE_FRONT_UPLIGHTS_APPLY_OK|run=%s|pieces=8|lights=8|p87_style=1|backup=%s|readback=8|dirty=0+0|record=%s"%(run,pre["root"],ACTIVE))

def run_revert(args,run,g):
    require(os.path.isfile(ACTIVE),"ACTIVE_RECORD_REQUIRED");record=json.load(open(ACTIVE,encoding="utf-8"));require(record.get("status")=="applied","RECORD_STATUS")
    ids=set(record["guids"]);readback(g,ids);pre=backup(run,"Revert",[SHOW,WORLD],{"apply_run":record["run"],"guids":sorted(ids)})
    p13=load_p13();cues=list(g["show"].get_editor_property("cues"));rows=p13._pair_attachments(cues[g["target_index"]]);survivors=[a for a in rows if guid(a.get_editor_property("attachment_guid")) not in ids]
    require(len(rows)-len(survivors)==8,"REVERT_REMOVE_COUNT");p13._set_pair_attachments(g["show"],g["target_index"],survivors);materialize(g["show"])
    require(not [a for _,_,a in attachments(g["show"]) if guid(a.get_editor_property("attachment_guid")) in ids],"REVERT_SURVIVORS");save_named()
    archived=ACTIVE+".reverted-"+run;os.replace(ACTIVE,archived);unreal.log("JOB178A_STAGE_FRONT_UPLIGHTS_REVERT_OK|run=%s|apply_run=%s|removed=8|backup=%s|dirty=0+0|record=%s"%(run,record["run"],pre["root"],archived))

def main():
    run="JOB178A-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    raw=json.load(open(ARGS,encoding="utf-8"));args=C.validate_args(raw,os.path.exists(ACTIVE));context(args["mode"]);g=gather(args)
    unreal.log("JOB178A_STAGE_FRONT_UPLIGHTS_START|run=%s|mode=%s"%(run,args["mode"]))
    {"DRY":run_dry,"APPLY":run_apply,"REVERT":run_revert}[args["mode"]](args,run,g)

if __name__=="__main__" and unreal is not None:main()
