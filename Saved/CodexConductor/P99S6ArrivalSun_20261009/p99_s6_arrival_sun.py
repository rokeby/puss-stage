"""Job 99 later-live tool. DRY is PIE read-only; APPLY/REVERT require editor world.

The tool never starts, stops, scrubs, or quits PIE. APPLY never deletes an
obstruction: it either adds an S6 bHidden visibility track or moves one exact
Show attachment row and records the original transform.
"""
from __future__ import annotations

import datetime
import glob
import hashlib
import importlib.util
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "p99_args.json")
ACTIVE = os.path.join(HERE, "p99_ACTIVE.json")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OWNER = "P99 S6 [OWNED]"
PARCAN = "/Game/InfinityStage/Lighting/Fixtures/Meshes/SM_Lantern_ParCan"
spec = importlib.util.spec_from_file_location("p99_core", os.path.join(HERE, "p99_core.py"))
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def require(v, m): C.require(v, m)
def path(obj):
    try: return str(obj.get_path_name())
    except Exception: return str(obj)
def asset_id(obj): return path(obj).split(".", 1)[0] if obj is not None else None
def label(actor):
    try: return str(actor.get_actor_label())
    except Exception: return str(actor.get_name())
def vec(v): return [float(v.x), float(v.y), float(v.z)]
def rot(v): return [float(v.roll), float(v.pitch), float(v.yaw)]
def run_id(): return "P99S6-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
def sha_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def write_json(p, v, exclusive=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "x" if exclusive else "w", encoding="utf-8") as f:
        json.dump(v,f,indent=2,sort_keys=True,default=str); f.flush(); os.fsync(f.fileno())


def census():
    x=unreal.EditorLoadingAndSavingUtils
    return {"content":sorted(asset_id(v) for v in x.get_dirty_content_packages()),
            "maps":sorted(asset_id(v) for v in x.get_dirty_map_packages())}


def project_root(): return os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
def package_file(pkg):
    base=os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),pkg[6:].replace("/",os.sep))
    for ext in (".uasset",".umap"):
        if os.path.isfile(base+ext): return os.path.normpath(base+ext)
    raise C.P99Error("PACKAGE_FILE_MISSING|"+pkg)


def backup(run, packages, suffix=""):
    root=os.path.join(project_root(),"Backups","PreP99S6ArrivalSun%s-%s"%(suffix,run)); os.makedirs(root,exist_ok=False)
    rows=[]
    for pkg in packages:
        src=package_file(pkg); dst=os.path.join(root,pkg[6:].replace("/",os.sep)+os.path.splitext(src)[1])
        os.makedirs(os.path.dirname(dst),exist_ok=True); shutil.copy2(src,dst)
        require(sha_file(src)==sha_file(dst),"BACKUP_HASH|"+pkg)
        rows.append({"package":pkg,"source":src,"backup":dst,"bytes":os.path.getsize(dst),"sha256":sha_file(dst)})
    out={"run":run,"packages":rows}; write_json(os.path.join(root,"manifest.json"),out,True); out["root"]=root; return out


def components(actor):
    rows=[]
    for comp in actor.get_components_by_class(unreal.ActorComponent):
        cls=comp.get_class().get_name(); mesh=None; instances=None
        try:
            sm=comp.get_editor_property("static_mesh"); mesh=asset_id(sm)
        except Exception: pass
        if "InstancedStaticMesh" in cls:
            try: instances=int(comp.get_instance_count())
            except Exception: pass
        if mesh or "Light" in cls or "SkyAtmosphere" in cls:
            rows.append({"path":path(comp),"name":str(comp.get_name()),"class":cls,"mesh":mesh,"instances":instances,
                         "tags":sorted(str(x) for x in comp.get_editor_property("component_tags"))})
    return rows


def hit_row(result, uv):
    if result is None: return None
    if isinstance(result,tuple):
        hr=next((x for x in result if isinstance(x,unreal.HitResult)),None)
        return hit_row(hr,uv) if hr else None
    try: t=result.to_tuple()
    except Exception: return None
    if not bool(t[0]): return None
    names=("blocking_hit","initial_overlap","time","distance","location","impact_point","normal","impact_normal",
           "phys_mat","hit_actor","hit_component","hit_bone_name","bone_name","hit_item","element_index","face_index",
           "trace_start","trace_end")
    fields=dict(zip(names,t))
    actor=fields.get("hit_actor"); comp=fields.get("hit_component")
    if actor is None: return None
    ints=[fields.get("hit_item"),fields.get("element_index"),fields.get("face_index")]
    item=fields.get("hit_item")
    try: hit_mesh=asset_id(comp.get_editor_property("static_mesh")) if comp else None
    except Exception: hit_mesh=None
    return {"uv":uv,"actor_label":label(actor),"actor_path":path(actor),"actor_class":actor.get_class().get_name(),
            "component_path":path(comp) if comp else None,"component_class":comp.get_class().get_name() if comp else None,
            "component_mesh":hit_mesh,
            "hit_item_candidates":ints,"hit_item":item,"actor_tags":sorted(str(x) for x in actor.get_editor_property("tags")),
            "components":components(actor)}


def fixture_instance_map(structure):
    """Mirror StructureActor.cpp:154-177; index is the StructureFixtures ISM item."""
    result=structure.gather_stations()
    if isinstance(result,tuple) and len(result)==3: ok,stations,error=result; require(bool(ok),"GATHER_STATIONS|%s"%error)
    elif isinstance(result,tuple) and len(result)==2: stations,error=result
    else: stations,error=result,""
    require(stations is not None and len(list(stations))>0,"GATHER_STATIONS_EMPTY|%s"%error)
    passage=structure.get_editor_property("passage"); show=passage.get_editor_property("show_asset")
    cues={C.guid32(q.get_editor_property("cue_guid")):q for q in show.get_editor_property("cues")}
    out=[]
    for station_index,station in enumerate(stations):
        cue_guid=C.guid32(station.get_editor_property("cue_guid")); cue=cues.get(cue_guid)
        if cue is None: continue
        wing=cue.get_editor_property("wing_pair")
        for a in wing.get_editor_property("attachments"):
            if not bool(a.get_editor_property("enabled")): continue
            if C.enum_name(a.get_editor_property("kind"))!="LIGHT" or C.enum_name(a.get_editor_property("anchor"))!="STATION": continue
            out.append({"instance_index":len(out),"station_index":station_index,"cue_guid":cue_guid,
                        "cue_label":str(cue.get_editor_property("label")),
                        "attachment_guid":C.guid32(a.get_editor_property("attachment_guid")),
                        "attachment_label":str(a.get_editor_property("label"))})
    return out


def record_hits(tokens):
    roots=[("puss_shadow_spot_record.json","puss_shadow_spot.py"),
           ("p06_rig_pattern_record.json","P06 rig pattern"),
           ("MeshyFixtures_20261007/meshy_swap_record_P06.json","MeshyFixtures P06 swap"),
           ("P01FloorPracticals_20261008/p06_addup_record.json","Job 35 ADD_UPLIGHTS"),
           ("opening_lighting_p13_record.json","Jobs 30/43 opening PARs"),
           ("p06_sunset_record.json","p06_sunset.py"),
           ("p18_sky_policy_record*.json","P18 sky policy")]
    base=os.path.join(project_root(),"Saved","CodexConductor"); hits=[]
    needles=[str(x) for x in tokens if x and len(str(x))>=8]
    for rel,tool in roots:
        for file in glob.glob(os.path.join(base,rel)):
            try:
                text=open(file,encoding="utf-8").read()
                matched=[n for n in needles if n in text]
                if matched: hits.append({"tool":tool,"record":os.path.relpath(file,project_root()).replace("\\","/"),"tokens":matched[:4]})
            except Exception: pass
    return hits


def sky_rows(world):
    rows=[]
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
        for comp in actor.get_components_by_class(unreal.ActorComponent):
            cls=comp.get_class().get_name()
            if cls not in ("SkyAtmosphereComponent","DirectionalLightComponent","SkyLightComponent","VolumetricCloudComponent"): continue
            row={"actor_label":label(actor),"actor_path":path(actor),"actor_class":actor.get_class().get_name(),
                 "component_path":path(comp),"component_class":cls,"actor_hidden":bool(actor.get_editor_property("hidden")),
                 "component_visible":bool(comp.is_visible()),"tags":sorted(str(x) for x in actor.get_editor_property("tags"))}
            for prop in ("intensity","light_source_angle","atmosphere_sun_light","atmosphere_sun_light_index"):
                try: row[prop]=comp.get_editor_property(prop)
                except Exception: pass
            if cls=="DirectionalLightComponent":
                row["rotation_deg"]=rot(actor.get_actor_rotation())
                forward=actor.get_actor_rotation().get_forward_vector()
                row["sun_direction_elevation_deg"]=math.degrees(math.asin(max(-1.0,min(1.0,-float(forward.z)))))
            rows.append(row)
    return rows


def binding_census(seq, world):
    rows=[]
    for b in seq.get_bindings():
        try: resolved=[path(x) for x in seq.locate_bound_objects(b,world)]
        except Exception: resolved=[]
        tracks=[]
        for t in b.get_tracks():
            try: prop=[str(t.get_property_name()),str(t.get_property_path())]
            except Exception: prop=["",""]
            tracks.append({"class":t.get_class().get_name(),"display":str(t.get_display_name()),"property":prop})
        if resolved or any("Hidden" in str(x) or "Sky" in str(x) or "Sun" in str(x) for x in tracks):
            rows.append({"binding":str(b.get_display_name()),"resolved":resolved,"tracks":tracks})
    return rows


def owned_track_snapshot(seq):
    rows=[]
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if not str(t.get_display_name()).startswith(OWNER): continue
            try: prop=[str(t.get_property_name()),str(t.get_property_path())]
            except Exception: prop=["",""]
            sections=[]
            for s in t.get_sections():
                channels=[]
                for ch in s.get_all_channels():
                    try: default=ch.get_default()
                    except Exception: default=None
                    keys=[]
                    for k in ch.get_keys():
                        try: time=int(k.get_time().frame_number.value)
                        except Exception: time=None
                        try: value=k.get_value()
                        except Exception: value=None
                        keys.append([time,str(value)])
                    try: channel_name=str(ch.channel_name)
                    except Exception: channel_name=str(ch.get_name())
                    channels.append({"name":channel_name,"default":str(default),"keys":keys})
                sections.append({"start":int(s.get_start_frame()) if s.has_start_frame() else None,
                                 "end":int(s.get_end_frame()) if s.has_end_frame() else None,
                                 "completion":str(s.get_completion_mode()),"channels":channels})
            rows.append({"binding":C.guid32(b.get_id()),"display":str(t.get_display_name()),
                         "class":t.get_class().get_name(),"property":prop,"sections":sections})
    return sorted(rows,key=lambda x:(x["binding"],x["display"]))


def parcan_instances_in_view(world, pc, viewport):
    sx,sy=float(viewport.x),float(viewport.y); rows=[]
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
        for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
            try: mesh=asset_id(comp.get_editor_property("static_mesh"))
            except Exception: continue
            if mesh!=PARCAN: continue
            mapping=fixture_instance_map(actor) if actor.get_class().get_name()=="InfinityStageStructureActor" else []
            for index in range(int(comp.get_instance_count())):
                tf=comp.get_instance_transform(index,True); loc=tf.translation
                result=unreal.GameplayStatics.project_world_to_screen(pc,loc,False)
                if result is None: continue
                if isinstance(result,tuple):
                    if len(result)>1 and isinstance(result[0],bool) and not result[0]: continue
                    screen=result[-1]
                else: screen=result
                u,v=float(screen.x)/sx,float(screen.y)/sy
                if not (0.0<=u<=1.0 and 0.0<=v<=1.0): continue
                row={"uv":[u,v],"centre_distance":math.hypot(u-.5,v-.5),"actor_label":label(actor),
                     "actor_path":path(actor),"actor_class":actor.get_class().get_name(),"actor_tags":sorted(str(x) for x in actor.get_editor_property("tags")),
                     "component_path":path(comp),"component_class":comp.get_class().get_name(),"component_mesh":mesh,
                     "instance_index":index,"world_location_cm":vec(loc),"structure_instance":mapping[index] if index<len(mapping) else None}
                tokens=[row["actor_label"],row["actor_path"],mesh]
                if row["structure_instance"]: tokens+=list(row["structure_instance"].values())
                rh=record_hits(tokens); row["provenance"]=C.classify_provenance(row["actor_label"],row["component_path"],mesh,row["actor_tags"],rh,row["structure_instance"])
                rows.append(row)
    return sorted(rows,key=lambda x:x["centre_distance"])


def dry_pie(args, run):
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); world=editor.get_game_world()
    require(world is not None,"DRY_REQUIRES_LIVE_PIE_AT_S6_ARRIVAL")
    dirty0=census(); root=list(unreal.GameplayStatics.get_all_actors_of_class(world,unreal.InfinityStageShowRoot))
    require(len(root)==1,"SHOW_ROOT_COUNT|%d"%len(root))
    tr=root[0].get_editor_property("transport"); master=int(tr.get_current_master_frame().value)
    segs=list(tr.get_editor_property("segments")); idx=int(tr.find_segment_at_frame(unreal.FrameNumber(master)))
    seg=segs[idx]; seg_label=str(seg.get_editor_property("label")); require(seg_label.startswith("Scene 6"),"NOT_SCENE_6|"+seg_label)
    show=unreal.load_asset(SHOW); tick=show.get_editor_property("tick_resolution"); tick_rate=float(tick.numerator)/float(tick.denominator)
    scene_s=(master-int(seg.start_frame.value))/tick_rate
    require(-0.05<=scene_s<=float(args["arrival_window_s"]),"NOT_S6_ARRIVAL_WINDOW|seconds=%.3f|max=%.3f"%(scene_s,args["arrival_window_s"]))
    pc=unreal.GameplayStatics.get_player_controller(world,0); pcm=unreal.GameplayStatics.get_player_camera_manager(world,0)
    require(pc is not None and pcm is not None,"CAMERA_MISSING")
    loc=pcm.get_camera_location(); cr=pcm.get_camera_rotation(); hfov=float(pcm.get_fov_angle())
    size=unreal.WidgetLayoutLibrary.get_viewport_size(world); aspect=float(size.x)/max(1.0,float(size.y))
    hits=[]
    for v in (0.42,0.5,0.58):
        for u in (0.42,0.5,0.58):
            vfov=math.degrees(2*math.atan(math.tan(math.radians(hfov)/2)/aspect))
            ray=unreal.Rotator(pitch=cr.pitch+(0.5-v)*vfov,yaw=cr.yaw+(u-0.5)*hfov,roll=0).get_forward_vector()
            res=unreal.SystemLibrary.line_trace_single(world,loc,loc+ray*200000.0,unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                        True,[],unreal.DrawDebugTrace.NONE,True)
            row=hit_row(res,[u,v])
            if row: hits.append(row)
    # Enrich collision hits, then independently project every ParCan ISM instance;
    # Structure fixture bodies are commonly NoCollision.
    for row in hits:
        if row.get("component_mesh")==PARCAN and row.get("hit_item") is not None:
            actor=next((a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor) if path(a)==row["actor_path"]),None)
            if actor and actor.get_class().get_name()=="InfinityStageStructureActor":
                mapping=fixture_instance_map(actor); item=row["hit_item"]
                if 0<=item<len(mapping): row["structure_instance"]=mapping[item]
        tokens=[row.get("actor_label"),row.get("actor_path"),row.get("component_mesh")]
        if row.get("structure_instance"): tokens += list(row["structure_instance"].values())
        rh=record_hits(tokens); row["provenance"]=C.classify_provenance(row.get("actor_label"),row.get("component_path"),
            row.get("component_mesh"),row.get("actor_tags",[]),rh,row.get("structure_instance"))
    projected_parcans=parcan_instances_in_view(world,pc,size)
    skies=sky_rows(world); sun=next((x for x in skies if x["actor_label"]==args["sun_actor_label"] and x["component_class"]=="DirectionalLightComponent"),None)
    sun_view=None
    if sun:
        actor=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor) if path(a)==sun["actor_path"])
        fwd=actor.get_actor_rotation().get_forward_vector(); d=[-fwd.x,-fwd.y,-fwd.z]
        sun_view=C.direction_uv(vec(cr.get_forward_vector()),vec(cr.get_right_vector()),vec(cr.get_up_vector()),d,hfov,aspect)
    seq=unreal.load_asset(args["scene_sequence"]); require(seq is not None,"SCENE_SEQUENCE_MISSING")
    selected=projected_parcans[0] if projected_parcans else next((x for x in hits if x.get("component_mesh")==PARCAN), hits[0] if hits else None)
    out={"schema":"p99_dry_v1","run":run,"mode":"DRY","segment":seg_label,"segment_index":idx,"master_frame":master,"scene_seconds":scene_s,
         "camera":{"location_cm":vec(loc),"rotation_deg":rot(cr),"hfov_deg":hfov,"viewport":[float(size.x),float(size.y)]},
         "central_frustum_hits":hits,"projected_parcan_instances":projected_parcans,"selected_obstruction":selected,"sky_sun_census":skies,"sun_in_camera":sun_view,
         "s6_binding_census":binding_census(seq,world),"dirty_before":dirty0,"dirty_after":census(),
         "diagnosis":{"sun_below_or_outside_frame":bool(sun_view and not sun_view["inside"]),
                      "sky_atmosphere_visible":any(x["component_class"]=="SkyAtmosphereComponent" and x["component_visible"] and not x["actor_hidden"] for x in skies),
                      "p06_record":"Saved/CodexConductor/p06_sunset_record.json",
                      "p18_pattern":"P18 hides foreign/editor skies; S6 sequence bHidden override is required"}}
    require(out["dirty_after"]==dirty0,"DRY_DIRTIED_PACKAGES|"+json.dumps(out["dirty_after"]))
    out["dry_sha256"]=C.stable_hash(out); report=os.path.join(HERE,"p99_report_DRY_%s.json"%run); write_json(report,out)
    selected_name=((selected.get("structure_instance") or {}).get("attachment_label") or selected.get("actor_label")) if selected else None
    unreal.log("P99_S6_DRY_OK|run=%s|segment=%s|scene_s=%.3f|hits=%d|parcans_in_view=%d|selected=%s|sun_inside=%s|sky_visible=%s|dirty_unchanged=1|report=%s"%
               (run,seg_label,scene_s,len(hits),len(projected_parcans),selected_name,
                sun_view.get("inside") if sun_view else None,out["diagnosis"]["sky_atmosphere_visible"],report))
    return out


def editor_context():
    ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); require(ed.get_game_world() is None,"PIE_ACTIVE")
    world=ed.get_editor_world(); require(asset_id(world)==WORLD,"WRONG_WORLD|"+str(asset_id(world)))
    require(census()=={"content":[],"maps":[]},"PRE_DIRTY|"+json.dumps(census())); return world


def actor_by_label(world,name):
    hits=[a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if label(a)==name]
    require(len(hits)==1,"ACTOR_LABEL_COUNT|%s|%d"%(name,len(hits))); return hits[0]


def bindings_for(seq,obj,world):
    want=path(obj); out=[]
    for b in seq.get_bindings():
        try:
            if any(path(x)==want for x in seq.locate_bound_objects(b,world)): out.append(b)
        except Exception: pass
    return out


def binding_for(seq,obj,world,name,created):
    hits=bindings_for(seq,obj,world); require(len(hits)<=1,"MULTIBOUND|"+name)
    if hits: return hits[0]
    before={C.guid32(x.get_id()) for x in seq.get_bindings()}; b=seq.add_possessable(obj)
    if C.guid32(b.get_id()) not in before: b.set_display_name(name); created.append(C.guid32(b.get_id()))
    return b


def add_visibility(seq,actor,world,name,created):
    b=binding_for(seq,actor,world,name,created)
    require(not any(str(t.get_display_name()).startswith(OWNER) for t in b.get_tracks()),"OWNED_TRACK_EXISTS|"+name)
    t=b.add_track(unreal.MovieSceneVisibilityTrack); t.set_property_name_and_path("bHidden","bHidden"); t.set_display_name(OWNER+" "+name)
    s=t.add_section(); s.set_range(seq.get_playback_start(),seq.get_playback_end()); s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    ch=list(s.get_all_channels()); require(len(ch)==1,"VIS_CHANNELS"); ch[0].set_default(True) # visible semantics
    return {"binding":C.guid32(b.get_id()),"track":str(t.get_display_name()),"property":[str(t.get_property_name()),str(t.get_property_path())]}


def add_sun_tracks(seq,sun,world,args,created):
    b=binding_for(seq,sun,world,args["sun_actor_label"],created)
    require(not any(str(t.get_display_name()).startswith(OWNER) for t in b.get_tracks()),"SUN_OWNED_TRACK_EXISTS")
    t=b.add_track(unreal.MovieScene3DTransformTrack); t.set_display_name(OWNER+" Sun Rotation")
    s=t.add_section(); s.set_range(seq.get_playback_start(),seq.get_playback_end()); s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    ch={str(x.channel_name):x for x in s.get_all_channels()}; tf=sun.get_actor_transform(); loc=vec(tf.translation); scale=vec(tf.scale3d)
    vals={"Location.X":loc[0],"Location.Y":loc[1],"Location.Z":loc[2],"Rotation.X":0.0,
          "Rotation.Y":args["sun_rotation_deg"][1],"Rotation.Z":args["sun_rotation_deg"][2],
          "Scale.X":scale[0],"Scale.Y":scale[1],"Scale.Z":scale[2]}
    for n,v in vals.items(): require(n in ch,"TRANSFORM_CHANNEL|"+n); ch[n].set_default(float(v))
    comp=sun.get_component_by_class(unreal.DirectionalLightComponent); require(comp is not None,"SUN_COMPONENT")
    cb=binding_for(seq,comp,world,args["sun_actor_label"]+" Component",created)
    rows=[]
    for prop,value in (("Intensity",args["sun_intensity_lux"]),("LightSourceAngle",args["sun_source_angle_deg"])):
        require(not any(t.get_class().get_name()=="MovieSceneFloatTrack" and str(t.get_property_name())==prop for t in cb.get_tracks()),
                "SUN_PROPERTY_TRACK_CONFLICT|"+prop)
        ft=cb.add_track(unreal.MovieSceneFloatTrack); ft.set_property_name_and_path(prop,prop); ft.set_display_name(OWNER+" "+prop)
        fs=ft.add_section(); fs.set_range(seq.get_playback_start(),seq.get_playback_end()); fs.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
        channel=list(fs.get_all_channels()); require(len(channel)==1,"FLOAT_CHANNEL|"+prop); channel[0].set_default(float(value)); rows.append(prop)
    return {"actor_binding":C.guid32(b.get_id()),"component_binding":C.guid32(cb.get_id()),"properties":rows,
            "rotation_xyz":args["sun_rotation_deg"]}


def find_attachment(show,cue_guid,attachment_guid):
    cg,ag=C.guid32(cue_guid),C.guid32(attachment_guid)
    for cue in show.get_editor_property("cues"):
        if C.guid32(cue.get_editor_property("cue_guid"))!=cg: continue
        for a in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if C.guid32(a.get_editor_property("attachment_guid"))==ag: return cue,a
    raise C.P99Error("ATTACHMENT_NOT_FOUND|%s|%s"%(cg,ag))


def tf_state(tf):
    r=tf.rotation.rotator(); return {"location":vec(tf.translation),"rotation":[float(r.roll),float(r.pitch),float(r.yaw)],"scale":vec(tf.scale3d)}
def set_tf(a,state):
    a.set_editor_property("relative_transform",unreal.Transform(unreal.Vector(*state["location"]),unreal.Rotator(*state["rotation"]),unreal.Vector(*state["scale"])))


def save_named(packages):
    require(census()=={"content":sorted(p for p in packages if p!=WORLD),"maps":[WORLD] if WORLD in packages else []},
            "DIRTY_SCOPE|"+json.dumps(census()))
    for p in packages:
        if p==WORLD: require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(),"SAVE_FAILED|"+p)
        else: require(unreal.EditorAssetLibrary.save_asset(p,only_if_is_dirty=True),"SAVE_FAILED|"+p)
    require(census()=={"content":[],"maps":[]},"DIRTY_AFTER_SAVE|"+json.dumps(census()))


def apply(args,run):
    world=editor_context(); dry_path=os.path.normpath(os.path.join(project_root(),str(args["dry_report"]).replace("/",os.sep)))
    require(os.path.isfile(dry_path),"DRY_REPORT_MISSING"); require(sha_file(dry_path)==args["dry_report_sha256"],"DRY_REPORT_SHA")
    dry=json.load(open(dry_path,encoding="utf-8")); require(dry.get("schema")=="p99_dry_v1" and dry.get("segment","").startswith("Scene 6"),"DRY_REPORT_SCOPE")
    require(not os.path.exists(ACTIVE),"ACTIVE_RECORD_EXISTS")
    seq=unreal.load_asset(args["scene_sequence"]); require(seq is not None,"SCENE_SEQUENCE_MISSING")
    sun=actor_by_label(world,args["sun_actor_label"])
    skies=[a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if label(a)==args["sky_actor_label"]]
    require(len(skies)<=1,"SKY_COUNT")
    created_actor=not bool(skies)
    require(not created_actor or args["create_sky_if_missing"],"SKY_MISSING")
    packages=[args["scene_sequence"]]
    if created_actor or args["obstruction_action"]=="MOVE_SHOW_ATTACHMENT": packages.append(WORLD)
    if args["obstruction_action"]=="MOVE_SHOW_ATTACHMENT": packages.insert(0,SHOW)
    pre=backup(run,packages)
    record={"schema":"p99_active_v1","status":"prepared","run":run,"args":args,"dry":dry,
        "backup":pre,"packages":packages,"created_sky_actor":created_actor,"created_bindings":[],"owned_tracks":[],"move":None}
    write_json(ACTIVE,record,True)
    if skies: sky=skies[0]
    else:
        sky=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.SkyAtmosphere,unreal.Vector(),unreal.Rotator())
        require(sky is not None,"SPAWN_SKY"); sky.set_actor_label(args["sky_actor_label"],mark_dirty=True); sky.set_actor_hidden_in_game(True); created_actor=True
    if args["obstruction_action"]=="HIDE_ACTOR_S6":
        obstruction=actor_by_label(world,args["obstruction_actor_label"])
        isms=sum((c.get_instance_count() for c in obstruction.get_components_by_class(unreal.InstancedStaticMeshComponent)),0)
        require(isms<=1,"REFUSE_WHOLE_MULTI_INSTANCE_ACTOR|instances=%d|use MOVE_SHOW_ATTACHMENT"%isms)
        # Visibility bool channels store VISIBLE: False hides.
        b=binding_for(seq,obstruction,world,args["obstruction_actor_label"],record["created_bindings"])
        t=b.add_track(unreal.MovieSceneVisibilityTrack); t.set_property_name_and_path("bHidden","bHidden"); t.set_display_name(OWNER+" Obstruction Hidden")
        s=t.add_section(); s.set_range(seq.get_playback_start(),seq.get_playback_end()); s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
        channel=list(s.get_all_channels()); require(len(channel)==1,"OBSTRUCTION_VIS_CHANNEL"); channel[0].set_default(False)
        record["owned_tracks"].append({"binding":C.guid32(b.get_id()),"display":str(t.get_display_name()),"property":["bHidden","bHidden"]})
    else:
        show=unreal.load_asset(SHOW); cue,a=find_attachment(show,args["obstruction_cue_guid"],args["obstruction_attachment_guid"])
        before=tf_state(a.get_editor_property("relative_transform")); after=json.loads(json.dumps(before))
        after["location"]=[before["location"][i]+float(args["obstruction_move_delta_cm"][i]) for i in range(3)]
        show.modify(); set_tf(a,after); record["move"]={"cue_guid":C.guid32(cue.get_editor_property("cue_guid")),
            "attachment_guid":C.guid32(a.get_editor_property("attachment_guid")),"label":str(a.get_editor_property("label")),"before":before,"after":after}
        passage=next(x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                     if x.get_class().get_name()=="InfinityStagePassageActor" and str(x.get_actor_label()).startswith("Passage 06"))
        structure=next(x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                       if x.get_class().get_name()=="InfinityStageStructureActor" and x.get_editor_property("passage")==passage)
        require(passage.materialize_passage(),"MATERIALIZE_PASSAGE"); require(structure.materialize_structure(),"MATERIALIZE_STRUCTURE")
    record["owned_tracks"].append(add_visibility(seq,sky,world,"Sky Visible",record["created_bindings"]))
    record["owned_tracks"].append(add_visibility(seq,sun,world,"Sun Visible",record["created_bindings"]))
    record["sun_tracks"]=add_sun_tracks(seq,sun,world,args,record["created_bindings"])
    expected={"content":sorted(p for p in packages if p!=WORLD),"maps":[WORLD] if WORLD in packages else []}; require(census()==expected,"APPLY_DIRTY_SCOPE|"+json.dumps(census()))
    save_named(packages); record["status"]="applied"; record["owned_track_snapshot"]=owned_track_snapshot(seq)
    require(record["owned_track_snapshot"],"OWNED_TRACK_READBACK_EMPTY")
    if record.get("move"):
        live_show=unreal.load_asset(SHOW); _cue,live_attachment=find_attachment(live_show,record["move"]["cue_guid"],record["move"]["attachment_guid"])
        require(C.stable_hash(tf_state(live_attachment.get_editor_property("relative_transform")))==C.stable_hash(record["move"]["after"]),"MOVE_SAVED_READBACK")
    record["readback"]={"dirty":census(),"tracks":binding_census(seq,world),"sky":sky_rows(world)}; write_json(ACTIVE,record)
    unreal.log("P99_S6_APPLY_OK|run=%s|obstruction=%s|sun_elev=%.2f|sky_created=%s|saved=%d|readback=1|dirty=0+0|record=%s"%
               (run,args["obstruction_action"],args["sun_elevation_deg"],created_actor,len(packages),ACTIVE)); return record


def remove_owned(seq):
    removed=0
    for b in seq.get_bindings():
        for t in list(b.get_tracks()):
            if str(t.get_display_name()).startswith(OWNER): b.remove_track(t); removed+=1
    return removed


def revert(args,run):
    world=editor_context(); require(os.path.isfile(ACTIVE),"ACTIVE_RECORD_MISSING"); rec=json.load(open(ACTIVE,encoding="utf-8"))
    require(rec.get("status")=="applied","ACTIVE_STATUS"); packages=rec["packages"]; pre=backup(run,packages,"Revert")
    seq=unreal.load_asset(rec["args"]["scene_sequence"])
    require(C.stable_hash(owned_track_snapshot(seq))==C.stable_hash(rec.get("owned_track_snapshot",[])),"REVERT_TRACK_DRIFT")
    removed=remove_owned(seq)
    if rec.get("move"):
        show=unreal.load_asset(SHOW); _cue,a=find_attachment(show,rec["move"]["cue_guid"],rec["move"]["attachment_guid"])
        live=tf_state(a.get_editor_property("relative_transform")); require(C.stable_hash(live)==C.stable_hash(rec["move"]["after"]),"REVERT_MOVE_DRIFT")
        show.modify(); set_tf(a,rec["move"]["before"])
        passage=next(x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if x.get_class().get_name()=="InfinityStagePassageActor" and str(x.get_actor_label()).startswith("Passage 06"))
        structure=next(x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if x.get_class().get_name()=="InfinityStageStructureActor" and x.get_editor_property("passage")==passage)
        require(passage.materialize_passage(),"REVERT_MATERIALIZE_PASSAGE"); require(structure.materialize_structure(),"REVERT_MATERIALIZE_STRUCTURE")
    if rec.get("created_sky_actor"):
        sky=actor_by_label(world,rec["args"]["sky_actor_label"]); require(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(sky),"DESTROY_OWNED_SKY")
    for guid in rec.get("created_bindings",[]):
        rows=[b for b in seq.get_bindings() if C.guid32(b.get_id())==guid]
        require(len(rows)==1,"REVERT_BINDING_COUNT|%s|%d"%(guid,len(rows))); rows[0].remove()
        require(not [b for b in seq.get_bindings() if C.guid32(b.get_id())==guid],"REVERT_BINDING_SURVIVED|"+guid)
    save_named(packages); archive=ACTIVE.replace("_ACTIVE.json","_REVERTED_%s.json"%run); rec.update({"status":"reverted","revert_run":run,"revert_backup":pre,"removed_tracks":removed}); write_json(ACTIVE,rec); os.replace(ACTIVE,archive)
    unreal.log("P99_S6_REVERT_OK|run=%s|tracks=%d|move=%s|sky_destroyed=%s|saved=%d|readback=1|dirty=0+0|record=%s"%
               (run,removed,bool(rec.get("move")),bool(rec.get("created_sky_actor")),len(packages),archive)); return rec


def main():
    run=run_id()
    try:
        args=C.validate_args(json.load(open(ARGS,encoding="utf-8")))
        if args["mode"]=="DRY": return dry_pie(args,run)
        if args["mode"]=="APPLY": return apply(args,run)
        return revert(args,run)
    except Exception as exc:
        unreal.log_error("P99_S6_FAILED|run=%s|%r"%(run,exc)); raise


if unreal is not None and __name__=="__main__": main()
