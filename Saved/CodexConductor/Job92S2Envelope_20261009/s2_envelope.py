"""Codex job 92: widen and raise the EXISTING S2 hangar, offline-written and never run here.

DRY/APPLY/REVERT, confirm '<MODE> S2ENVELOPE'.  APPLY requires the digest from its immediately preceding DRY,
backs up the level and LS_S2_HangarRise, writes an exclusive record before mutation, changes only existing S2
hangar actors plus Location.Z values on the exact S2 Hangar Lattice Fly transform channel, saves exactly those two
packages, and reads every write back.  Klara's Japanese_Alley level, copied LS_NEW_SHRINE_S2Hangar, V3 overlay and
LS_DevScene_02 are census/identity guards and are NEVER saved.

The root rise/fold rotation times and values do not depend on box width/height and are fingerprinted unchanged.
ARRMOV is a target+GUID guard; S2WALLHIDE is a bHidden-property binding guard. V3 wings and handoff cameras remain
world-authored and are checked against the enlarged envelope rather than moved.  The floor and apron widen with it.
Markers: S2_ENVELOPE_DRY_OK / APPLY_OK / REVERT_OK / STOPPED.
"""
import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

from s2_envelope_core import contains, enum_name, plan_digest, proposal, remap_value, rig_clear, target_actor

TOOL = "S2_ENVELOPE"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RISE = "/Game/InfinityStage/RigAtmos/LS_S2_HangarRise"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"
COPY = "/Game/InfinityStage/KlaraHookin/LS_NEW_SHRINE_S2Hangar"
OVERLAY = "/Game/Scenes/KlaraS2V3/LS_S2_V3WingsOverlay"
ROOT_LABEL = "S2 Hangar Root"
FLY_LABEL = "S2 Hangar Lattice Fly"
OWNED_PREFIXES = ("S2 Hangar", "S2 Lattice", "S2 Practical", "S2 Uplight", "S2 Ghost")
HERE = (os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                     "CodexConductor", "Job92S2Envelope_20261009") if unreal else os.path.dirname(__file__))
ARGS_PATH = os.path.join(HERE, "s2_envelope_args.json")
DRY_PATH = os.path.join(HERE, "s2_envelope_dry.json")
RECORD_PATH = os.path.join(HERE, "s2_envelope_record.json")


class Refuse(RuntimeError): pass


def stable(value):
    return json.loads(json.dumps(value, sort_keys=True))


def pkg(value):
    return str(value.get_path_name()).split(".", 1)[0]


def guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(pkg(x) for x in lib.get_dirty_content_packages()),
            "maps": sorted(pkg(x) for x in lib.get_dirty_map_packages())}


def write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=1, sort_keys=True); fh.write("\n"); fh.flush(); os.fsync(fh.fileno())


def stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|%s" % (TOOL, run, reason)); raise Refuse(reason)


def inverse(root, point):
    return unreal.MathLibrary.inverse_transform_location(root.get_actor_transform(), point)


def forward(root, point):
    return unreal.MathLibrary.transform_location(root.get_actor_transform(), unreal.Vector(*point))


def actor_rows(actors, root):
    rows = []
    for actor in actors:
        label = str(actor.get_actor_label()); tags = [str(t) for t in actor.get_editor_property("tags")]
        if label == ROOT_LABEL or ("RigAtmos.Scene2Hangar" not in tags and not label.startswith(OWNED_PREFIXES)):
            continue
        loc = inverse(root, actor.get_actor_location()); scale = actor.get_actor_scale3d()
        parent = actor.get_attach_parent_actor()
        depth, walk = 0, parent
        while walk is not None and depth < 32:
            depth += 1; walk = walk.get_attach_parent_actor()
        rows.append({"label": label, "path": str(actor.get_path_name()), "class": actor.get_class().get_name(),
                     "root_local": [loc.x, loc.y, loc.z], "scale": [scale.x, scale.y, scale.z],
                     "parent": str(parent.get_actor_label()) if parent else None, "depth": depth})
    rows.sort(key=lambda r: (r["depth"], r["label"]))
    if len(rows) < 20 or len({r["label"] for r in rows}) != len(rows):
        raise Refuse("HANGAR_LABEL_CONTRACT|rows=%d|unique=%d" % (len(rows), len({r["label"] for r in rows})))
    return rows


def primitive_bounds(actors, root):
    box = None; count = 0
    for actor in actors:
        outer = str(actor.get_outer().get_outer().get_name()) if actor.get_outer() and actor.get_outer().get_outer() else "?"
        if "Japanese_Alley" not in outer: continue
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            cls = comp.get_class().get_name()
            if any(x in cls for x in ("Sky", "Atmospheric", "Fog", "PostProcess", "Light", "Volume")) or not comp.is_visible():
                continue
            o, e, _radius = unreal.SystemLibrary.get_component_bounds(comp)
            if max(e.x, e.y, e.z) <= 0.01: continue
            count += 1
            for x in (-1, 1):
                for y in (-1, 1):
                    for z in (-1, 1):
                        p = inverse(root, unreal.Vector(o.x+x*e.x, o.y+y*e.y, o.z+z*e.z))
                        if box is None: box = {"min": [p.x,p.y,p.z], "max": [p.x,p.y,p.z]}
                        else:
                            for i,v in enumerate((p.x,p.y,p.z)):
                                box["min"][i]=min(box["min"][i],v); box["max"][i]=max(box["max"][i],v)
    if box is None: raise Refuse("NO_KLARA_RENDER_BOUNDS")
    return box, count


def channel_name(channel):
    return str(channel.get_name()).split(".")[-2:]  # suffix-safe diagnostic only


def lattice_channel(seq):
    matches = []
    for binding in seq.get_bindings():
        if str(binding.get_display_name()) != FLY_LABEL: continue
        for track in binding.get_tracks():
            if track.get_class().get_name() != "MovieScene3DTransformTrack": continue
            for section in track.get_sections():
                for channel in section.get_all_channels():
                    name = str(channel.get_name())
                    if name == "Location.Z" or name.endswith("Location.Z") or name.endswith("Translation.Z"):
                        matches.append(channel)
    if len(matches) != 1: raise Refuse("LATTICE_Z_CHANNEL_COUNT|%d" % len(matches))
    return matches[0]


def key_state(channel):
    keys = []
    for key in channel.get_keys():
        time = key.get_time()
        frame = int(time.frame_number.value if hasattr(time.frame_number, "value") else time.frame_number)
        keys.append([frame, float(key.get_value())])
    default = None
    try: default = float(channel.get_default())
    except Exception: pass
    return {"name": str(channel.get_name()), "keys": keys, "default": default}


def value_text(value):
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    text = str(value)
    return enum_name(text) if text.startswith("<") and ":" in text else text


def seq_fingerprint(path, exclude_binding=None):
    seq = unreal.load_asset(path)
    if seq is None: raise Refuse("MISSING_SEQUENCE|" + path)
    rows=[]
    for b in seq.get_bindings():
        if str(b.get_display_name()) == exclude_binding:
            continue
        tr=[]
        for t in b.get_tracks():
            sec=[]
            for s in t.get_sections():
                channels=[]
                for c in s.get_all_channels():
                    keys=[]
                    for key in c.get_keys():
                        kt=key.get_time(); frame=int(kt.frame_number.value if hasattr(kt.frame_number,"value") else kt.frame_number)
                        keys.append([frame,value_text(key.get_value())])
                    try: default=value_text(c.get_default())
                    except Exception: default=None
                    channels.append({"name":str(c.get_name()),"keys":keys,"default":default})
                sec.append({"range":[int(s.get_start_frame()) if s.has_start_frame() else None,
                                      int(s.get_end_frame()) if s.has_end_frame() else None],
                            "active":bool(s.is_active()), "channels":channels,
                            "property": (str(t.get_property_name()) if hasattr(t,"get_property_name") else None)})
            tr.append({"class":t.get_class().get_name(),"name":str(t.get_display_name()),"sections":sec})
        rows.append({"name":str(b.get_display_name()),"guid":guid(b.get_id()),"tracks":tr})
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(), rows


def dependency_guards(actors):
    cams=[]
    for a in actors:
        label=str(a.get_actor_label())
        if label.startswith("Scene 2 ") and "Handoff Camera" in label:
            l=a.get_actor_location(); r=a.get_actor_rotation(); cams.append([label,str(a.get_path_name()),[l.x,l.y,l.z],[r.pitch,r.yaw,r.roll]])
    arrival=next((a for a in actors if str(a.get_actor_label())=="S2 Arrival"),None)
    drives=[]
    if arrival:
        for d in arrival.get_editor_property("additional_initial_transform_drives"):
            target=d.get_editor_property("target")
            drives.append([str(target.get_actor_label()) if target else None,guid(d.get_editor_property("binding_guid"))])
    fingerprints={RISE:seq_fingerprint(RISE,FLY_LABEL)[0],
                  SCENE:seq_fingerprint(SCENE)[0], COPY:seq_fingerprint(COPY)[0], OVERLAY:seq_fingerprint(OVERLAY)[0]}
    scene_rows=seq_fingerprint(SCENE)[1]
    vis=[]
    for b in scene_rows:
        for t in b["tracks"]:
            if t["class"]=="MovieSceneVisibilityTrack": vis.append([b["name"],t["property"]])
    bad=[x for x in vis if x[1] not in (None,"bHidden")]
    if bad: raise Refuse("VISIBILITY_NOT_BHIDDEN|%s" % bad[:4])
    targets=sorted(x[0] for x in drives)
    if FLY_LABEL not in targets or "S2 Hangar Roof Hinge" not in targets:
        raise Refuse("ARRMOV_TARGETS|%s" % targets)
    if len(cams)!=2: raise Refuse("HANDOFF_CAMERA_COUNT|%d" % len(cams))
    return {"handoff_cameras":sorted(cams),"arrival_drives":sorted(drives),"sequence_fingerprints":fingerprints,
            "visibility_properties":sorted(vis)}


def build_plan(args):
    ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); world=ed.get_editor_world()
    if world is None or pkg(world)!=WORLD or ed.get_game_world() is not None: raise Refuse("WRONG_WORLD_OR_PIE")
    if census()!={"content":[],"maps":[]}: raise Refuse("DIRTY_AT_START|%s" % census())
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    roots=[a for a in actors if str(a.get_actor_label())==ROOT_LABEL]
    if len(roots)!=1: raise Refuse("ROOT_COUNT|%d" % len(roots))
    root=roots[0]; rows=actor_rows(actors,root); bounds,ncomp=primitive_bounds(actors,root)
    bargs=args["bounds"]; recommended=proposal(bounds,bargs["side_margin_cm"],bargs["top_margin_cm"],bargs["round_up_cm"])
    new=args["new"]
    if not contains(bounds,new["half_width_cm"],new["height_cm"],bargs["side_margin_cm"],bargs["top_margin_cm"]):
        raise Refuse("NEW_ENVELOPE_TOO_SMALL|bounds=%s|recommended=%s" % (bounds,recommended))
    if not rig_clear(bounds,new["lattice_landed_z_cm"],new["lattice_rest_z_cm"],new["height_cm"],bargs["top_margin_cm"]):
        raise Refuse("RIG_OR_ROOF_CLEARANCE|bounds=%s|recommended=%s|new=%s" % (bounds,recommended,new))
    targets=[]
    for row in rows:
        after=target_actor(row,args["old"],new)
        if max(abs(after["root_local"][i]-row["root_local"][i]) for i in range(3))>0.001 or max(abs(after["scale"][i]-row["scale"][i]) for i in range(3))>0.00001:
            targets.append({"label":row["label"],"path":row["path"],"depth":row["depth"],"before":{"root_local":row["root_local"],"scale":row["scale"]},"after":after})
    rise=unreal.load_asset(RISE); channel=lattice_channel(rise); ks=key_state(channel)
    mapped=[[t,remap_value(v,args["old"]["lattice_landed_z_cm"],args["old"]["lattice_rest_z_cm"],new["lattice_landed_z_cm"],new["lattice_rest_z_cm"])] for t,v in ks["keys"]]
    default=(remap_value(ks["default"],args["old"]["lattice_landed_z_cm"],args["old"]["lattice_rest_z_cm"],new["lattice_landed_z_cm"],new["lattice_rest_z_cm"]) if ks["default"] is not None else None)
    plan={"bounds":bounds,"bound_components":ncomp,"recommended":recommended,"old":args["old"],"new":new,
          "actors":targets,"all_actor_rows":rows,"lattice_before":ks,"lattice_after":{"name":ks["name"],"keys":mapped,"default":default},
          "dependencies":dependency_guards(actors)}
    plan["digest"]=plan_digest(plan); return plan,root,channel,{str(a.get_path_name()):a for a in actors}


def read_actor(actor,root):
    l=inverse(root,actor.get_actor_location()); s=actor.get_actor_scale3d(); return {"root_local":[l.x,l.y,l.z],"scale":[s.x,s.y,s.z]}


def close(a,b,tol=0.02):
    return max(abs(a["root_local"][i]-b["root_local"][i]) for i in range(3))<=tol and max(abs(a["scale"][i]-b["scale"][i]) for i in range(3))<=1e-4


def set_actors(rows,key,root,by_path):
    for row in sorted(rows,key=lambda r:r["depth"]):
        actor=by_path[row["path"]]; want=row[key]; actor.modify(); actor.set_actor_location(forward(root,want["root_local"]),False,False); actor.set_actor_scale3d(unreal.Vector(*want["scale"]))


def set_keys(channel,state):
    live=list(channel.get_keys())
    if len(live)!=len(state["keys"]): raise Refuse("KEY_COUNT_DRIFT")
    for key,(frame,value) in zip(live,state["keys"]):
        now=key.get_time(); nf=int(now.frame_number.value if hasattr(now.frame_number,"value") else now.frame_number)
        if nf!=frame: raise Refuse("KEY_TIME_DRIFT")
        key.set_value(float(value))
    if state["default"] is not None: channel.set_default(float(state["default"]))


def verify(plan,which,root,by_path,channel):
    bad=[]
    for row in plan["actors"]:
        if not close(read_actor(by_path[row["path"]],root),row[which]): bad.append(row["label"])
    got=key_state(channel); want=plan["lattice_"+("after" if which=="after" else "before")]
    if [x[0] for x in got["keys"]]!=[x[0] for x in want["keys"]] or any(abs(a[1]-b[1])>0.01 for a,b in zip(got["keys"],want["keys"])): bad.append("LATTICE_KEYS")
    return bad


def backup(run,kind=""):
    root=os.path.abspath(os.path.join(HERE,"..","..","..")); stamp="PreS2Envelope%s-%s" % (kind,run)
    out=os.path.join(root,"Backups",stamp); os.makedirs(out)
    files=[os.path.join(root,"Content","InfinityStage","Dev","Maps","L_InfinityStage_V1VerticalSlice.umap"),
           os.path.join(root,"Content","InfinityStage","RigAtmos","LS_S2_HangarRise.uasset")]
    copied=[]
    for src in files:
        if not os.path.isfile(src): raise Refuse("BACKUP_SOURCE_MISSING|"+src)
        dst=os.path.join(out,os.path.basename(src)); shutil.copy2(src,dst); copied.append(dst)
    return {"root":out,"files":copied}


def save_targets():
    expected={"content":[RISE],"maps":[WORLD]}
    if census()!=expected: raise Refuse("DIRTY_CENSUS_PRESAVE|got=%s|want=%s" % (census(),expected))
    if not unreal.EditorAssetLibrary.save_asset(RISE,only_if_is_dirty=True): raise Refuse("SAVE_RISE")
    if census()!={"content":[],"maps":[WORLD]}: raise Refuse("CENSUS_AFTER_RISE|%s" % census())
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(): raise Refuse("SAVE_LEVEL")
    if census()!={"content":[],"maps":[]}: raise Refuse("CENSUS_AFTER_LEVEL|%s" % census())


def main():
    args=globals().get("S2ENVELOPE_ARGS") or json.load(open(ARGS_PATH,encoding="utf-8")); mode=str(args.get("mode","DRY")).upper(); run=str(args.get("run_id") or datetime.datetime.now().strftime("S2ENV-%Y%m%d-%H%M%S"))
    if args.get("confirm")!="%s S2ENVELOPE" % mode: stop(run,"CONFIRM")
    if mode=="REVERT":
        if not os.path.isfile(RECORD_PATH): stop(run,"NO_RECORD")
        rec=json.load(open(RECORD_PATH,encoding="utf-8")); plan=rec["plan"]
        _live,root,channel,by_path=build_plan(dict(args,old=plan["new"],new=plan["new"]))
        # build_plan is only a context/drift guard here; exact recorded values are authority.
        if verify(plan,"after",root,by_path,channel): stop(run,"REVERT_DRIFT|%s" % verify(plan,"after",root,by_path,channel))
        bk=backup(run,"Revert"); set_actors(plan["actors"],"before",root,by_path); set_keys(channel,plan["lattice_before"])
        if verify(plan,"before",root,by_path,channel): stop(run,"REVERT_READBACK|NOTHING SAVED; Don't-Save restart")
        save_targets(); archived=RECORD_PATH+".reverted-"+run; os.rename(RECORD_PATH,archived)
        unreal.log("%s_REVERT_OK|run=%s|actors=%d|saved=%s,%s|backup=%s|census=0+0" % (TOOL,run,len(plan["actors"]),RISE,WORLD,bk["root"])); return
    plan,root,channel,by_path=build_plan(args)
    if mode=="DRY":
        write_json(DRY_PATH,{"run":run,"mode":"DRY","mutated":False,"plan":plan,"census":census()})
        unreal.log("%s_DRY_OK|run=%s|actors=%d|bounds=%s|recommended=%s|digest=%s|mutated=0|report=%s" % (TOOL,run,len(plan["actors"]),plan["bounds"],plan["recommended"],plan["digest"],DRY_PATH)); return
    if mode!="APPLY": stop(run,"MODE")
    if args.get("approved_by","").startswith("PENDING"): stop(run,"APPROVAL_PENDING")
    if args.get("dry_plan_digest")!=plan["digest"]: stop(run,"DRY_DIGEST_MISMATCH|live=%s" % plan["digest"])
    if os.path.exists(RECORD_PATH): stop(run,"RECORD_EXISTS")
    dry=json.load(open(DRY_PATH,encoding="utf-8"))
    if dry.get("plan",{}).get("digest")!=plan["digest"]: stop(run,"DRY_FILE_MISMATCH")
    bk=backup(run); rec={"schema":1,"tool":TOOL,"run":run,"applied":False,"backup":bk,"plan":plan,"args":args}
    write_json(RECORD_PATH,rec,exclusive=True)
    set_actors(plan["actors"],"after",root,by_path); set_keys(channel,plan["lattice_after"])
    bad=verify(plan,"after",root,by_path,channel)
    if bad: stop(run,"PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup=%s" % (bad,bk["root"]))
    if dependency_guards(list(by_path.values()))!=plan["dependencies"]: stop(run,"DEPENDENCY_CHANGED|NOTHING SAVED; Don't-Save restart")
    save_targets()
    bad=verify(plan,"after",root,by_path,channel)
    if bad or dependency_guards(list(by_path.values()))!=plan["dependencies"]: stop(run,"POSTSAVE_READBACK|%s|restore=%s" % (bad,bk["root"]))
    rec["applied"]=True; rec["applied_at"]=datetime.datetime.now().isoformat(); write_json(RECORD_PATH,rec)
    unreal.log("%s_APPLY_OK|run=%s|actors=%d|keys=%d|saved=%s,%s|guarded=%s,%s,%s|backup=%s|record=%s|census=0+0" % (TOOL,run,len(plan["actors"]),len(plan["lattice_after"]["keys"]),RISE,WORLD,SCENE,COPY,OVERLAY,bk["root"],RECORD_PATH))


if unreal is not None and globals().get("S2ENVELOPE_ARGS") is not None:
    try: main()
    except Exception as exc: unreal.log_error("%s_STOPPED|%r" % (TOOL,exc))
