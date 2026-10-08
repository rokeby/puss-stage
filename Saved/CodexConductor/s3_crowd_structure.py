"""P21C Scene 3 clustered crowd: preserve the originals' keyed Transform tracks.

Offline only in this Codex run. The conductor later invokes it through
ExecuteProjectPythonFile. APPLY leaves every original Transform key untouched,
adds only tool-owned additive-roll sections to those tracks, gives the 15 copies
fresh absolute/additive Transform tracks, authors LS_Clams animation, and rebuilds
root camera cuts around four new spawnable CineCameras. It never edits Klara's levels.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import traceback

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None

PROJECT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
HERE = os.path.join(PROJECT, "Saved", "CodexConductor")
ARGS = os.path.join(HERE, "s3_crowd_structure_args.json")
RECORD = os.path.join(HERE, "s3_crowd_structure_record.json")
BENCH = os.path.join(HERE, "s3_crowd_bench_record.json")
PLAN_DEFAULT = os.path.join(HERE, "s3_crowd_structure_plan.json")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
CLAMS = "/Game/Scenes/LS_Clams"
PACKAGES = sorted([WORLD, ROOT, CLAMS])
FILES = {
    WORLD: os.path.join(PROJECT, "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"),
    ROOT: os.path.join(PROJECT, "Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"),
    CLAMS: os.path.join(PROJECT, "Content/Scenes/LS_Clams.uasset"),
}
TAG = "P21.S3Crowd"
RUN = {"value": "?"}


class CrowdError(RuntimeError):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, data):
    temp = path + ".pending"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)


def baseline_gate(record, expected_visible=5):
    if not isinstance(record, dict) or record.get("schema") != "p21_s3_crowd_bench/1":
        return False, "BENCH_SCHEMA"
    baseline = record.get("baseline", {})
    missing = [w for w in ("establishing", "choir") if w not in baseline]
    if missing:
        return False, "BASELINE_WINDOWS_MISSING|" + ",".join(missing)
    for name, row in baseline.items():
        if int(row.get("figure_count", -1)) != int(expected_visible):
            return False, "BASELINE_FIGURE_COUNT|%s|got=%s|expected=%s" % (
                name, row.get("figure_count"), expected_visible)
        if int(row.get("samples", 0)) < 24 or row.get("dt_ms", {}).get("median") is None:
            return False, "BASELINE_SAMPLES|" + name
    return True, "OK"


def subtract_ranges(base, overrides):
    """Return half-open pieces of base not occupied by overrides."""
    pieces = [tuple(base)]
    for oa, ob in sorted(tuple(x) for x in overrides):
        next_pieces = []
        for a, b in pieces:
            if ob <= a or oa >= b:
                next_pieces.append((a, b)); continue
            if a < oa: next_pieces.append((a, oa))
            if ob < b: next_pieces.append((ob, b))
        pieces = next_pieces
    return [list(p) for p in pieces if p[1] > p[0]]


def coverage_gaps(rows, playback):
    intervals = sorted((max(playback[0], r[0]), min(playback[1], r[1])) for r in rows
                       if r[1] > playback[0] and r[0] < playback[1])
    gaps, cursor = [], playback[0]
    for a, b in intervals:
        if a > cursor: gaps.append([cursor, a])
        cursor = max(cursor, b)
    if cursor < playback[1]: gaps.append([cursor, playback[1]])
    return gaps


def frames_to_ranges(frames):
    """Compress integer frames to half-open ranges for concise refusal reports."""
    values = sorted(set(int(x) for x in frames))
    if not values: return []
    out=[]; start=previous=values[0]
    for frame in values[1:]:
        if frame != previous + 1:
            out.append([start,previous+1]); start=frame
        previous=frame
    out.append([start,previous+1]); return out


def snapshot_equal(a, b, tolerance=1e-4):
    """Structural equality with UE 5.8's measured float-channel tolerance."""
    if isinstance(a,bool) or isinstance(b,bool): return type(a) is type(b) and a==b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return abs(float(a)-float(b))<=float(tolerance)
    if isinstance(a,dict) and isinstance(b,dict):
        return set(a)==set(b) and all(snapshot_equal(a[k],b[k],tolerance) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(snapshot_equal(x,y,tolerance) for x,y in zip(a,b))
    return a==b


def transform_conflicts(track_rows, sway_windows, owned_section_names=()):
    """Find only authoring that can fight P21C additive roll.

    Absolute location/yaw keys, including Gary's teleport, are intentionally
    accepted. Existing additive sections not named in our record and absolute
    Rotation.X keys inside a sway window are hard conflicts.
    """
    owned=set(str(x) for x in owned_section_names); additive=[]; roll_frames=[]
    for track in track_rows:
        for section in track.get("sections",[]):
            blend=str(section.get("blend",{}).get("value","")).upper()
            name=str(section.get("name",""))
            if "ADDITIVE" in blend and name not in owned:
                additive.append({"track":track.get("name"),"section":name,"range":section.get("range")})
            if "ADDITIVE" in blend: continue
            for key in section.get("channels",{}).get("Rotation.X",{}).get("keys",[]):
                frame=int(key[0])
                if any(a <= frame < b for a,b in sway_windows): roll_frames.append(frame)
    return {"foreign_additive":additive,"roll_key_ranges":frames_to_ranges(roll_frames)}


def teleport_rows(position_rows, threshold_cm):
    """Report adjacent evaluated position samples that jump farther than threshold."""
    out=[]
    for before,after in zip(position_rows,position_rows[1:]):
        if int(after["frame"]) != int(before["frame"])+1: continue
        distance=math.sqrt(sum((float(after["xyz"][i])-float(before["xyz"][i]))**2 for i in range(3)))
        if distance >= float(threshold_cm):
            out.append({"range":[int(before["frame"]),int(after["frame"])+1],"distance_cm":round(distance,3),
                        "from":before["xyz"],"to":after["xyz"]})
    return out


def live_cut_mismatches(rows, expected):
    """Compare the active root cuts with the P21C ranges derived from the live census."""
    mismatches = []
    for camera, wanted in expected.items():
        actual = [r["range"] for r in rows if r.get("active") and r.get("camera") == camera]
        if actual != [wanted]:
            mismatches.append({"camera": camera, "expected": wanted, "actual": actual})
    return mismatches


def planned_cut_rows(before, plan):
    overrides = [s["range"] for s in plan["shots"]]
    rows = []
    for old in before:
        base = list(old["range"])
        if old["camera"] == plan["handprint_trim"]["camera"]:
            if base != plan["handprint_trim"]["expected_before"]:
                raise CrowdError("B06_RANGE_MISMATCH|got=%s|expected=%s" %
                                 (base, plan["handprint_trim"]["expected_before"]))
            base = list(plan["handprint_trim"]["after"])
        for piece in subtract_ranges(base, overrides):
            rows.append({**old, "range": piece})
    return rows


def build_source_schedule(member, source, scene_to_clams=22, blend=24):
    """Turn class bands into overlapping animation rows in LS_Clams frames."""
    spans = {
        "CALM": (float(source["calm_span"]["source_in"]), float(source["calm_span"]["source_out"]),
                 float(source["calm_span"]["play_rate"])),
        "MEDIUM": (float(source["medium_span"]["source_in_seconds"]),
                   float(source["medium_span"]["source_out_seconds"]), 0.6),
        "FRENZY": (float(source["frenzy_span"]["source_in_seconds"]),
                   float(source["frenzy_span"]["source_out_seconds"]), 0.6),
    }
    out = []
    for band in member["timeline"]:
        kind = band["class"]
        if kind == "ORIGINAL":
            # Original full take mapping: source at 0.6x, including the known +22 frame nested offset.
            a, b = band["range"]
            out.append({"class": kind, "range": [a + scene_to_clams - blend, b + scene_to_clams],
                        "source_in": max(0.0, (a + scene_to_clams - blend) / 24.0 * 0.6),
                        "source_out": 100000.0, "play_rate": 0.6,
                        "ease_in": blend, "ease_out": 0})
            continue
        start, end = band["range"]; src_a, src_b, rate = spans[kind]
        cursor = start + scene_to_clams
        end_local = end + scene_to_clams
        while cursor < end_local:
            duration = max(1, int(round((src_b - src_a) / rate * 24.0)))
            stop = min(end_local, cursor + duration)
            out.append({"class": kind, "range": [max(0,cursor-blend), stop],
                        "source_in": src_a, "source_out": src_b, "play_rate": rate,
                        "ease_in": blend, "ease_out": blend})
            if stop == end_local: break
            cursor = stop
            if len(out) > 100: raise CrowdError("SCHEDULE_DID_NOT_TERMINATE")
    return out


def planned_apply_order():
    return ["preflight", "record", "backup", "preserve_original_transforms", "duplicate", "bind", "animate", "sway",
            "cameras", "cuts", "census", "save_named", "readback", "commit"]


def execute_order(adapter):
    for step in planned_apply_order():
        getattr(adapter, step)()


def _frame_value(value):
    return int(value.value if hasattr(value, "value") else value)


def _get(obj, names):
    for name in names:
        try: return obj.get_editor_property(name)
        except Exception: pass
    raise CrowdError("PROPERTY_MISSING|" + "/".join(names))


def _set(obj, names, value):
    for name in names:
        try: obj.set_editor_property(name, value); return
        except Exception: pass
    raise CrowdError("PROPERTY_SET_FAILED|" + "/".join(names))


def _fixed_rate(params):
    value = _get(params, ("play_rate", "time_scale"))
    if hasattr(value, "to_fixed_play_rate"):   # UE 5.8 MovieSceneTimeWarpVariant [measured probe_playrate.py 8 Oct]
        return float(value.to_fixed_play_rate())
    for name in ("play_rate", "value"):
        try: return float(value.get_editor_property(name))
        except Exception: pass
    try: return float(value)
    except Exception as exc: raise CrowdError("PLAY_RATE_UNREADABLE") from exc


def _set_rate(params, rate):
    cur = _get(params, ("play_rate", "time_scale"))
    if hasattr(cur, "set_fixed_play_rate"):    # UE 5.8 MovieSceneTimeWarpVariant
        cur.set_fixed_play_rate(float(rate)); _set(params, ("play_rate", "time_scale"), cur)
        if abs(float(_get(params, ("play_rate", "time_scale")).to_fixed_play_rate()) - float(rate)) > 1e-6:
            raise CrowdError("PLAY_RATE_SET_READBACK|%s" % rate)
        return
    value = _get(params, ("play_rate", "time_scale"))
    for name in ("play_rate", "value"):
        try:
            value.set_editor_property(name, float(rate)); _set(params, ("play_rate", "time_scale"), value); return
        except Exception: pass
    _set(params, ("play_rate", "time_scale"), float(rate))


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _clean(label):
    c = _census()
    if c != {"content": [], "maps": []}: raise CrowdError(label + "_DIRTY|" + repr(c))


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _assert_world():
    world = _world(); path = world.get_path_name().split(".")[0] if world else "NONE"
    if path != WORLD: raise CrowdError("WORLD_MISMATCH|got=%s|expected=%s" % (path, WORLD))
    return world


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _label(actor): return str(actor.get_actor_label())


def _hidden(actor):
    try: game = bool(actor.get_actor_hidden_in_game())
    except Exception: game = bool(actor.get_editor_property("hidden"))
    try: editor = bool(actor.is_hidden_ed())
    except Exception: editor = False
    return game or editor


def _transform_snapshot(actor):
    location, rotation, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
    return {"location": [float(location.x), float(location.y), float(location.z)],
            "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "scale": [float(scale.x), float(scale.y), float(scale.z)]}


def _restore_transform(actor, snapshot):
    actor.set_actor_location(unreal.Vector(*snapshot["location"]), False, False)
    actor.set_actor_rotation(unreal.Rotator(roll=snapshot["rotation"][0],
                                            pitch=snapshot["rotation"][1],
                                            yaw=snapshot["rotation"][2]), False)
    actor.set_actor_scale3d(unreal.Vector(*snapshot["scale"]))


def _pose_matches(actor, member, tolerance=0.01):
    location, rotation = actor.get_actor_location(), actor.get_actor_rotation()
    target_x = float(member["local_xy_cm"][0]) + 10921.973
    target_y = float(member["local_xy_cm"][1]) + 160000.0
    yaw_delta = ((float(rotation.yaw) - float(member["yaw_deg"]) + 180.0) % 360.0) - 180.0
    return abs(float(location.x) - target_x) <= tolerance and abs(float(location.y) - target_y) <= tolerance and abs(yaw_delta) <= tolerance


def _component_signature(actor):
    rows = []
    for comp in actor.get_components_by_class(unreal.ActorComponent):
        cls, name = comp.get_class().get_name(), str(comp.get_name())
        if any(token in (cls + name).lower() for token in ("cloth", "sack", "skeletal", "body")):
            rows.append(cls + ":" + name)
    return sorted(rows)


def _binding_path(binding):
    names = [str(binding.get_display_name())]; parent = binding.get_parent()
    while parent is not None and parent.is_valid():
        names.append(str(parent.get_display_name())); parent = parent.get_parent()
    return "/".join(reversed(names))


def _channel_base(channel):
    name=str(channel.get_name())
    head,sep,tail=name.rpartition("_")
    return head if sep and tail.isdigit() else name


def _key_frame(key):
    value=key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return int(value.frame_number.value if hasattr(value,"frame_number") else value.value)


def _section_range(section):
    return [int(section.get_start_frame()) if section.has_start_frame() else None,
            int(section.get_end_frame()) if section.has_end_frame() else None]


def _blend_snapshot(section):
    """UE 5.8 returns MovieSceneBlendTypeField, not the enum directly."""
    value=section.get_blend_type()
    valid=bool(value.get_editor_property("is_valid"))
    blend=str(value.get_editor_property("blend_type")) if valid else "UNSET"
    return {"api_type":type(value).__name__,"valid":valid,"value":blend}


def _is_additive(section):
    return "ADDITIVE" in _blend_snapshot(section)["value"].upper()


def _channel_snapshot(channel):
    keys=sorted([[_key_frame(k),round(float(k.get_value()),6)] for k in channel.get_keys()])
    return {"default":round(float(channel.get_default()),6) if channel.has_default() else None,"keys":keys}


def _transform_track_snapshot(track, exclude_sections=()):
    excluded=set(str(x) for x in exclude_sections); sections=[]
    for section in track.get_sections():
        if str(section.get_name()) in excluded: continue
        channels={}
        for channel in section.get_all_channels():
            base=_channel_base(channel)
            if base in ("Location.X","Location.Y","Location.Z","Rotation.X","Rotation.Y","Rotation.Z",
                        "Scale.X","Scale.Y","Scale.Z"):
                channels[base]=_channel_snapshot(channel)
        sections.append({"name":str(section.get_name()),"range":_section_range(section),
                         "active":bool(section.is_active()),"blend":_blend_snapshot(section),"channels":channels})
    return {"name":str(track.get_name()),"display_name":str(track.get_display_name()),"sections":sections}


def _actor_transform_handles(body_binding):
    actor_binding=body_binding.get_parent() if body_binding.get_parent().is_valid() else body_binding
    tracks=[t for t in actor_binding.get_tracks() if t.get_class().get_name()=="MovieScene3DTransformTrack"]
    return actor_binding,tracks


def _actor_track_report(body_binding):
    actor_binding,transform_tracks=_actor_transform_handles(body_binding)
    rows=[]
    for track in actor_binding.get_tracks():
        row={"class":track.get_class().get_name(),"name":str(track.get_name()),
             "display_name":str(track.get_display_name())}
        if track in transform_tracks: row.update(_transform_track_snapshot(track))
        rows.append(row)
    return rows


def _anim_section_snapshot(section):
    p = section.get_editor_property("params"); anim = p.get_editor_property("animation")
    return {"name": str(section.get_name()), "range": [int(section.get_start_frame()), int(section.get_end_frame())],
            "animation": anim.get_path_name() if anim else None,
            "start_offset": _frame_value(p.get_editor_property("start_frame_offset")),
            "end_offset": _frame_value(p.get_editor_property("end_frame_offset")),
            "first_loop_offset": _frame_value(p.get_editor_property("first_loop_start_frame_offset")),
            "play_rate": round(_fixed_rate(p), 8), "row": int(section.get_row_index()),
            "active": bool(section.is_active()),
            "ease": {"weight_keys": _weight_keys(section)}}


def _find_source_binding(sequence, figure):
    candidates = []
    for binding in sequence.get_bindings():
        path = _binding_path(binding)
        if figure["id"] not in path: continue
        for track in binding.get_tracks():
            if track.get_class().get_name() != "MovieSceneSkeletalAnimationTrack": continue
            for section in track.get_sections():
                snap = _anim_section_snapshot(section)
                if snap["animation"] and snap["animation"].rsplit("/",1)[-1].split(".")[-1] == figure["animation"]:
                    candidates.append((binding, track, section, snap, path))
    if len(candidates) != 1: raise CrowdError("SOURCE_BINDING|%s|hits=%d" % (figure["id"], len(candidates)))
    return candidates[0]


def _discover(plan, clams):
    by_label = {}
    for actor in _actors(): by_label.setdefault(_label(actor), []).append(actor)
    rows = []
    for source in plan["sources"].values():
        hits = by_label.get(source["actor"], [])
        binding = _find_source_binding(clams, source)
        actor_binding,transform_tracks=_actor_transform_handles(binding[0])
        rows.append({"id": source["id"], "actor_label": source["actor"], "actor_hits": len(hits),
                     "actor": hits[0] if len(hits)==1 else None,
                     "hidden": _hidden(hits[0]) if len(hits)==1 else None,
                     "components": _component_signature(hits[0]) if len(hits)==1 else [],
                       "binding": binding[0], "track": binding[1], "section": binding[2],
                       "section_snapshot": binding[3], "binding_path": binding[4],
                       "actor_binding":actor_binding,"transform_tracks":transform_tracks,
                       "actor_tracks": _actor_track_report(binding[0])})
    return rows


def _primary_transform_track(row):
    tracks=row["transform_tracks"]
    if len(tracks)!=1: raise CrowdError("ORIGINAL_TRANSFORM_TRACK_COUNT|%s|%d"%(row["id"],len(tracks)))
    return tracks[0]


def _channel_value(channel, sequence, frame, cache, token=None):
    """Evaluate one UE 5.8 scripting channel at a display-rate frame, without writes."""
    token=token or ("channel",str(channel.get_name()))
    if token not in cache:
        keys=sorted((_key_frame(k),float(k.get_value())) for k in channel.get_keys())
        values=[]; first=keys[0][0] if keys else None; api_error=None
        if keys:
            try:
                values=[float(v) for v in channel.evaluate_keys(channel.compute_effective_range(),sequence.get_display_rate())]
            except Exception as exc:
                api_error=repr(exc)
        cache[token]={"keys":keys,"values":values,"first":first,"api_error":api_error,
                      "default":float(channel.get_default()) if channel.has_default() else None}
    row=cache[token]
    if row["api_error"] is not None:
        raise CrowdError("CHANNEL_EVALUATE_KEYS_API|"+row["api_error"])
    if row["values"]:
        index=int(frame)-int(row["first"])
        return row["values"][max(0,min(index,len(row["values"])-1))]
    if row["default"] is not None: return row["default"]
    raise CrowdError("CHANNEL_HAS_NO_VALUE|%s|frame=%d"%(_channel_base(channel),frame))


def _track_transform_at(track, actor, sequence, frame, cache):
    base=_transform_snapshot(actor); values={
        "Location.X":base["location"][0],"Location.Y":base["location"][1],"Location.Z":base["location"][2],
        "Rotation.X":base["rotation"][0],"Rotation.Y":base["rotation"][1],"Rotation.Z":base["rotation"][2],
        "Scale.X":base["scale"][0],"Scale.Y":base["scale"][1],"Scale.Z":base["scale"][2]}
    track_token=("sections",id(track))
    if track_token not in cache:
        cache[track_token]=[(section,_section_range(section),bool(section.is_active()),_is_additive(section))
                            for section in track.get_sections()]
    active=[]
    for section,span,is_active,is_additive in cache[track_token]:
        inside=(span[0] is None or frame>=span[0]) and (span[1] is None or frame<span[1])
        if is_active and inside and not is_additive: active.append(section)
    if len(active)!=1: raise CrowdError("ABSOLUTE_TRANSFORM_SECTION_COUNT|track=%s|frame=%d|count=%d"%
                                         (track.get_display_name(),frame,len(active)))
    section_name=str(active[0].get_name()); channel_token=("channels",id(active[0]))
    if channel_token not in cache: cache[channel_token]=list(active[0].get_all_channels())
    for channel in cache[channel_token]:
        name=_channel_base(channel)
        if name in values: values[name]=_channel_value(channel,sequence,frame,cache,("value",id(active[0]),name))
    return {"xyz":[round(values["Location.X"],4),round(values["Location.Y"],4),round(values["Location.Z"],4)],
            "rpy":[round(values["Rotation.X"],4),round(values["Rotation.Y"],4),round(values["Rotation.Z"],4)]}


def _sample_original(row, plan, clams):
    track=_primary_transform_track(row); offset=int(plan["existing_position_policy"]["scene_to_ls_clams_frames"])
    windows=plan["existing_position_policy"]["crowd_windows_scene"]; cache={}; reports=[]; all_rows=[]
    location_key_frames=sorted(set(k[0] for section in _transform_track_snapshot(track)["sections"]
                                   for channel_name,channel in section["channels"].items()
                                   if channel_name.startswith("Location.") for k in channel["keys"]))
    for name,scene_span in windows.items():
        local=[scene_span[0]+offset,scene_span[1]+offset]
        frames=sorted(set([local[0],local[1]-1]+[f for f in location_key_frames if local[0]<=f<local[1]]+
                          [f-1 for f in location_key_frames if local[0]<f<local[1]]))
        positions=[]
        for frame in frames:
            value=_track_transform_at(track,row["actor"],clams,frame,cache)
            positions.append({"frame":frame,"scene_frame":frame-offset,"xyz":value["xyz"],"rpy":value["rpy"]})
        teleports=teleport_rows(positions,plan["existing_position_policy"]["teleport_threshold_cm"])
        reports.append({"name":name,"scene_range":scene_span,"ls_clams_range":local,
                        "positions":positions,"teleports":teleports})
        all_rows.extend({**p,"window":name} for p in positions)
    return reports,all_rows


def _cut_snapshot(sequence):
    bindings = {b.get_id().export_text(): str(b.get_display_name()) for b in sequence.get_bindings()}
    tracks = [t for t in sequence.get_tracks() if t.get_class().get_name()=="MovieSceneCameraCutTrack"]
    if len(tracks)!=1: raise CrowdError("CUT_TRACK_COUNT|%d"%len(tracks))
    rows=[]
    for s in tracks[0].get_sections():
        guid=s.get_camera_binding_id().get_editor_property("guid").export_text()
        rows.append({"range":[int(s.get_start_frame()),int(s.get_end_frame())],"active":bool(s.is_active()),
                     "camera_guid":guid,"camera":bindings.get(guid,"<missing>")})
    return tracks[0],rows


def _camera_sources(root):
    actors={_label(a):a for a in _actors()}; out={}
    for binding in root.get_bindings():
        label=str(binding.get_display_name())
        tracks=[t for t in binding.get_tracks() if t.get_class().get_name()=="MovieScene3DTransformTrack"]
        actor=None
        try: actor=binding.get_object_template()
        except Exception: pass
        if actor is None: actor=actors.get(label)
        out[label]={"binding":binding,"actor":actor,"tracks":tracks}
    return out


def _track_has_absolute_at(track, frame):
    for section in track.get_sections():
        span=_section_range(section)
        if (bool(section.is_active()) and not _is_additive(section) and
                (span[0] is None or frame>=span[0]) and (span[1] is None or frame<span[1])):
            return True
    return False


def _camera_positions(scene_frame, root, cut_rows, plan, sources, cache):
    planned=[s for s in plan["shots"] if s["range"][0]<=scene_frame<s["range"][1]]
    if planned:
        return [{"camera":s["label"],"xyz":[float(s["location_local"][0])+10921.973,
                                                 float(s["location_local"][1])+160000.0,
                                                 float(s["location_local"][2])],"source":"planned"} for s in planned]
    rows=[]
    for cut in cut_rows:
        if not cut["active"] or not cut["range"][0]<=scene_frame<cut["range"][1]: continue
        source=sources.get(cut["camera"])
        if source is None or source["actor"] is None:
            rows.append({"camera":cut["camera"],"unreadable":"actor"}); continue
        candidates=[track for track in source["tracks"] if _track_has_absolute_at(track,scene_frame)]
        if not candidates:
            value={"xyz":_transform_snapshot(source["actor"])["location"]}
        elif len(candidates)==1:
            value=_track_transform_at(candidates[0],source["actor"],root,scene_frame,cache)
        else:
            rows.append({"camera":cut["camera"],"unreadable":"multiple_absolute_transform_tracks"}); continue
        rows.append({"camera":cut["camera"],"xyz":value["xyz"],"source":"live_root"})
    return rows


def _camera_path_samples(plan, root, cut_rows):
    sources=_camera_sources(root); cache={}; out={}
    for span in plan["existing_position_policy"]["crowd_windows_scene"].values():
        for scene_frame in range(int(span[0]),int(span[1])):
            out[scene_frame]=_camera_positions(scene_frame,root,cut_rows,plan,sources,cache)
    return out


def _camera_crossings(row, plan, clams, camera_path):
    offset=int(plan["existing_position_policy"]["scene_to_ls_clams_frames"])
    clearance=float(plan["existing_position_policy"]["camera_clearance_cm"])
    track=_primary_transform_track(row); figure_cache={}
    hits=[]; unreadable=set()
    for window,span in plan["existing_position_policy"]["crowd_windows_scene"].items():
        for scene_frame in range(int(span[0]),int(span[1])):
            figure=_track_transform_at(track,row["actor"],clams,scene_frame+offset,figure_cache)["xyz"]
            for camera in camera_path.get(scene_frame,[]):
                if "xyz" not in camera:
                    unreadable.add(camera["camera"]); continue
                distance=math.hypot(float(figure[0])-float(camera["xyz"][0]),float(figure[1])-float(camera["xyz"][1]))
                if distance<=clearance:
                    hits.append({"window":window,"scene_frame":scene_frame,"camera":camera["camera"],
                                 "xy_distance_cm":round(distance,3),"figure_xyz":figure,"camera_xyz":camera["xyz"]})
    groups=[]
    for key in sorted(set((h["window"],h["camera"]) for h in hits)):
        rows=[h for h in hits if (h["window"],h["camera"])==key]
        groups.append({"window":key[0],"camera":key[1],"scene_ranges":frames_to_ranges(h["scene_frame"] for h in rows),
                       "minimum_xy_distance_cm":min(h["xy_distance_cm"] for h in rows)})
    return {"clearance_cm":clearance,"crossings":groups,"unreadable_cameras":sorted(unreadable)}


def _nested_cut_report(clams):
    rows=[]
    for t in clams.get_tracks():
        if t.get_class().get_name()=="MovieSceneCameraCutTrack":
            for s in t.get_sections(): rows.append({"range":[s.get_start_frame(),s.get_end_frame()],"active":bool(s.is_active())})
    return rows


def _backup(run, prefix):
    directory=os.path.join(PROJECT,"Backups",prefix+"-"+run)
    if os.path.exists(directory): raise CrowdError("BACKUP_EXISTS|"+directory)
    os.makedirs(directory); manifest={"run":run,"files":[]}
    for package,path in FILES.items():
        dst=os.path.join(directory,os.path.basename(path)); shutil.copy2(path,dst)
        if sha256(dst)!=sha256(path): raise CrowdError("BACKUP_HASH|"+package)
        manifest["files"].append({"package":package,"source":path,"backup":dst,"sha256":sha256(dst)})
    atomic_json(os.path.join(directory,"backup_manifest.json"),manifest)
    return directory


# 8 Oct conductor: UE 5.8 Python exposes NO section easing (get/set_manual_ease_* absent; MovieSceneEasingSettings
# fields not reflected) [measured probe_section_api.py]. Crossfades key the skeletal section's own Weight_0 channel
# (MovieSceneScriptingFloatChannel, default 1.0) [measured probe_weight.py]; frames in DISPLAY rate.
def _weight_channel(section):
    chans = [c for c in section.get_all_channels() if str(c.get_name()).startswith("Weight")]
    if len(chans) != 1:
        raise CrowdError("WEIGHT_CHANNEL|%d" % len(chans))
    return chans[0]


def _weight_keys(section):
    ch = _weight_channel(section)
    return {"default": float(ch.get_default()) if ch.has_default() else None,
            "keys": [[int(k.get_time().frame_number.value), float(k.get_value())] for k in ch.get_keys()]}


def _ease(section, ease_in, ease_out):
    ch = _weight_channel(section)
    for k in list(ch.get_keys()):
        ch.remove_key(k)
    a, b = int(section.get_start_frame()), int(section.get_end_frame())
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    pts = []
    if ease_in: pts += [(a, 0.0), (a + int(ease_in), 1.0)]
    if ease_out: pts += [(b - int(ease_out), 1.0), (b, 0.0)]
    for f, v in sorted(set(pts)):
        ch.add_key(unreal.FrameNumber(f), float(v), time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
    if not pts:
        ch.set_default(1.0)


def _restore_ease(section, row):
    ch = _weight_channel(section)
    for k in list(ch.get_keys()):
        ch.remove_key(k)
    for f, v in row.get("weight_keys", {}).get("keys", []):
        ch.add_key(unreal.FrameNumber(int(f)), float(v), interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
    d = row.get("weight_keys", {}).get("default")
    if d is not None:
        ch.set_default(float(d))


def _make_anim(track, template, animation, sequence, row):
    section=track.add_section(); p=section.get_editor_property("params")
    p.set_editor_property("animation",animation)
    tick=sequence.get_tick_resolution(); tick_rate=float(tick.numerator)/float(tick.denominator)
    p.set_editor_property("start_frame_offset",unreal.FrameNumber(int(round(row["source_in"]*tick_rate))))
    length=float(animation.get_play_length()); end_offset=max(0,int(round(max(0.0,length-row["source_out"])*tick_rate)))
    p.set_editor_property("end_frame_offset",unreal.FrameNumber(end_offset))
    p.set_editor_property("first_loop_start_frame_offset",unreal.FrameNumber(0)); _set_rate(p,row["play_rate"])
    try: _set(p,("reverse","b_reverse"),False)
    except CrowdError: pass
    section.set_editor_property("params",p); section.set_range(*row["range"]); _ease(section,row["ease_in"],row["ease_out"])
    section.set_row_index(template.get_row_index() if template else 0)
    return section


def _add_copy_transform(binding, actor, run):
    track=binding.add_track(unreal.MovieScene3DTransformTrack); track.set_display_name("P21 Crowd Transform "+run)
    section=track.add_section(); section.set_range(0,6263)
    snapshot=_transform_snapshot(actor); wanted={
        "Location.X":snapshot["location"][0],"Location.Y":snapshot["location"][1],"Location.Z":snapshot["location"][2],
        "Rotation.X":snapshot["rotation"][0],"Rotation.Y":snapshot["rotation"][1],"Rotation.Z":snapshot["rotation"][2],
        "Scale.X":snapshot["scale"][0],"Scale.Y":snapshot["scale"][1],"Scale.Z":snapshot["scale"][2]}
    channels={_channel_base(c):c for c in section.get_all_channels()}
    missing=sorted(set(wanted)-set(channels))
    if missing: raise CrowdError("COPY_TRANSFORM_CHANNELS_MISSING|"+repr(missing))
    for name,value in wanted.items(): channels[name].set_default(float(value))
    return track,section


def _add_roll(track, member, run):
    created=[]; fps=24.0
    for a,b in member["transform_sway"]["windows"]:
        s=track.add_section(); s.set_blend_type(unreal.MovieSceneBlendType.ADDITIVE); s.set_range(a+22,b+22)
        blend=_blend_snapshot(s)
        if not blend["valid"] or "ADDITIVE" not in blend["value"].upper():
            raise CrowdError("ADDITIVE_BLEND_READBACK|%s|%s"%(member["label"],blend))
        chans={_channel_base(c):c for c in s.get_all_channels()}
        ch=chans.get("Rotation.X")
        if ch is None: raise CrowdError("ROLL_CHANNEL_MISSING|"+member["label"])
        phase=math.radians(member["phase_deg"]); step=12; f=a+22
        while f<=b+22:
            edge=min(1.0,(f-(a+22))/24.0,((b+22)-f)/24.0)
            value=member["transform_sway"]["roll_degrees"]*edge*math.sin(2*math.pi*((f-(a+22))/fps)/member["transform_sway"]["period_seconds"]+phase)
            ch.add_key(unreal.FrameNumber(f),value,time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                       interpolation=unreal.MovieSceneKeyInterpolation.AUTO); f+=step
        created.append(str(s.get_name()))
    return created


def _add_visibility(binding, first_visible):
    track=binding.add_track(unreal.MovieSceneVisibilityTrack); track.set_display_name("P21 Crowd Visibility")
    section=track.add_section(); section.set_range(0,6263)
    channels=list(section.get_all_channels())
    if len(channels)!=1: raise CrowdError("VISIBILITY_CHANNEL_COUNT|%d"%len(channels))
    channel=channels[0]
    channel.add_key(unreal.FrameNumber(0),False,time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    channel.add_key(unreal.FrameNumber(int(first_visible)),True,time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return track


def _camera(root, spec, run):
    binding=root.add_spawnable_from_class(unreal.CineCameraActor); binding.set_display_name(spec["label"])
    template=binding.get_object_template(); comp=template.get_component_by_class(unreal.CineCameraComponent)
    comp.set_editor_property("current_focal_length",float(spec["lens_mm"]))
    track=binding.add_track(unreal.MovieScene3DTransformTrack); track.set_display_name("P21 Camera Pose "+run)
    sec=track.add_section(); sec.set_range(*spec["range"])
    chans={str(c.get_name()).rsplit("_",1)[0]:c for c in sec.get_all_channels()}
    loc=spec["location_local"]; world=[loc[0]+10921.973,loc[1]+160000.0,loc[2]]; rot=spec["rotation_rpy_deg"]
    vals={"Location.X":world[0],"Location.Y":world[1],"Location.Z":world[2],
          "Rotation.X":rot[0],"Rotation.Y":rot[1],"Rotation.Z":rot[2],
          "Scale.X":1.0,"Scale.Y":1.0,"Scale.Z":1.0}
    for name,value in vals.items():
        if name in chans: chans[name].set_default(float(value))
    return binding


def _rewrite_cuts(root, track, before, plan, cameras):
    rows=planned_cut_rows(before,plan)
    bindings={b.get_id().export_text():b for b in root.get_bindings()}
    for s in list(track.get_sections()): track.remove_section(s)
    for row in rows:
        if row["camera_guid"] not in bindings: raise CrowdError("CUT_BINDING_MISSING|"+row["camera_guid"])
        s=track.add_section(); s.set_camera_binding_id(root.get_binding_id(bindings[row["camera_guid"]])); s.set_range(*row["range"]); s.set_is_active(row["active"])
    for spec in plan["shots"]:
        s=track.add_section(); s.set_camera_binding_id(root.get_binding_id(cameras[spec["label"]])); s.set_range(*spec["range"])
    active=[r["range"] for r in rows if r["active"]]+[s["range"] for s in plan["shots"]]
    gaps=coverage_gaps(active,plan["cut_policy"]["root_playback"])
    if gaps: raise CrowdError("CUT_COVERAGE_GAPS|"+repr(gaps))
    return rows


def _restore_cuts(root, snapshots):
    track,_=_cut_snapshot(root); bindings={b.get_id().export_text():b for b in root.get_bindings()}
    for s in list(track.get_sections()): track.remove_section(s)
    for row in snapshots:
        b=bindings.get(row["camera_guid"])
        if b is None: raise CrowdError("REVERT_CUT_BINDING_MISSING|"+row["camera_guid"])
        s=track.add_section(); s.set_camera_binding_id(root.get_binding_id(b)); s.set_range(*row["range"]); s.set_is_active(row["active"])


def _save_named():
    expected={"content":sorted([ROOT,CLAMS]),"maps":[WORLD]}
    got=_census()
    if got!=expected: raise CrowdError("APPLY_CENSUS|got=%s|expected=%s|NOTHING SAVED; Don't-Save restart"%(got,expected))
    for package in (CLAMS,ROOT):
        if not unreal.EditorAssetLibrary.save_asset(package,only_if_is_dirty=False): raise CrowdError("SAVE_FAILED|"+package)
    if not unreal.EditorLoadingAndSavingUtils.save_map(_world(),WORLD): raise CrowdError("SAVE_MAP_FAILED|"+WORLD)
    _clean("AFTER_SAVE")


def _remove_binding(sequence,guid):
    hits=[b for b in sequence.get_bindings() if b.get_id().export_text()==guid]
    if len(hits)!=1: raise CrowdError("BINDING_REMOVE_LOOKUP|%s|hits=%d"%(guid,len(hits)))
    hits[0].remove()


def _original_transform_readback(sequence, record):
    bindings={b.get_id().export_text():b for b in sequence.get_bindings()}; errors=[]
    for hero in record.get("heroes",[]):
        binding=bindings.get(hero.get("actor_binding_guid"))
        if binding is None:
            errors.append({"id":hero["id"],"reason":"actor_binding_missing"}); continue
        tracks=[t for t in binding.get_tracks() if str(t.get_name())==hero.get("transform_track_name")]
        if len(tracks)!=1:
            errors.append({"id":hero["id"],"reason":"transform_track_count","count":len(tracks)}); continue
        track=tracks[0]; names={str(s.get_name()):s for s in track.get_sections()}
        missing=[name for name in hero.get("sway_sections",[]) if name not in names]
        bad_blend=[name for name in hero.get("sway_sections",[]) if name in names and not _is_additive(names[name])]
        current=_transform_track_snapshot(track,hero.get("sway_sections",[]))
        if not snapshot_equal(current,hero.get("original_transform_track")):
            errors.append({"id":hero["id"],"reason":"original_transform_changed"})
        if missing or bad_blend:
            errors.append({"id":hero["id"],"reason":"owned_additive_sections","missing":missing,"bad_blend":bad_blend})
    return errors


def _copy_transform_readback(sequence, record):
    bindings={b.get_id().export_text():b for b in sequence.get_bindings()}; errors=[]
    for copy_row in record.get("copies",[]):
        binding=bindings.get(copy_row["actor_binding_guid"])
        tracks=[] if binding is None else [t for t in binding.get_tracks()
                                           if str(t.get_name())==copy_row["transform_track_name"]]
        if len(tracks)!=1:
            errors.append({"label":copy_row["label"],"reason":"transform_track_count","count":len(tracks)})
        elif not snapshot_equal(_transform_track_snapshot(tracks[0]),copy_row["transform_track"]):
            errors.append({"label":copy_row["label"],"reason":"transform_track_changed"})
    return errors


def _read_plan(args):
    path=args.get("plan_path",PLAN_DEFAULT)
    with open(path,encoding="utf-8") as f: plan=json.load(f)
    if plan.get("schema")!="p21c_s3_crowd_transforms/1": raise CrowdError("PLAN_SCHEMA")
    return path,plan


def main():
    if unreal is None: raise CrowdError("UNREAL_REQUIRED")
    with open(ARGS,encoding="utf-8") as f: args=json.load(f)
    run,mode=str(args["run"]),str(args["mode"]).upper(); RUN["value"]=run
    if mode not in ("DRY","APPLY","REVERT"): raise CrowdError("MODE|"+mode)
    ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise CrowdError("PIE_RUNNING")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None: raise CrowdError("SEQUENCER_OPEN")
    _assert_world(); _clean("START")
    plan_path,plan=_read_plan(args); root=unreal.load_asset(ROOT); clams=unreal.load_asset(CLAMS)
    nested=_nested_cut_report(clams)
    if any(r["active"] for r in nested): raise CrowdError("NESTED_CUT_ACTIVE|"+repr(nested))
    cut_track,cut_before=_cut_snapshot(root)

    if mode=="DRY" and os.path.isfile(RECORD):
        prior=json.load(open(RECORD,encoding="utf-8"))
        if prior.get("state")=="applied":
            actor_by_label={_label(a):a for a in _actors()}; actor_labels=set(actor_by_label)
            missing_a=[x for x in prior["created_actor_labels"] if x not in actor_labels]
            root_names={str(b.get_display_name()) for b in root.get_bindings()}
            camera_names=tuple(s["label"] for s in plan["shots"])
            missing_c=[x for x in camera_names if x not in root_names]
            clams_guids={b.get_id().export_text() for b in clams.get_bindings()}
            missing_b=[g for g in prior["created_clams_bindings"] if g not in clams_guids]
            gaps=coverage_gaps([r["range"] for r in cut_before if r["active"]],plan["cut_policy"]["root_playback"])
            missing_cut=[s["range"] for s in plan["shots"] if not any(r["active"] and r["camera"]==s["label"] and r["range"]==s["range"] for r in cut_before)]
            copies=[m for m in plan["members"] if m["role"]=="duplicate"]
            bad_pose=[m["label"] for m in copies if m["label"] not in actor_by_label or not _pose_matches(actor_by_label[m["label"]],m)]
            transform_errors=_original_transform_readback(clams,prior)
            copy_transform_errors=_copy_transform_readback(clams,prior)
            if missing_a or missing_c or missing_b or gaps or missing_cut or bad_pose or transform_errors or copy_transform_errors:
                raise CrowdError("APPLIED_READBACK|actors=%s|cameras=%s|bindings=%s|gaps=%s|cuts=%s|copy_poses=%s|original_transforms=%s|copy_transforms=%s"%
                                 (missing_a,missing_c,missing_b,gaps,missing_cut,bad_pose,transform_errors,copy_transform_errors))
            _clean("DRY_APPLIED")
            unreal.log("S3_CROWD_DRY_OK|run=%s|state=applied|actors=%d|cameras=%d|bindings=%d|copy_poses=15|original_keys_unchanged=5|owned_additive_sections=OK|cut_gaps=0|writes=0|dirty=0"%
                       (run,len(prior["created_actor_labels"]),len(camera_names),len(prior["created_clams_bindings"]))); return

    if mode=="REVERT":
        if args.get("confirm")!="REVERT S3CROWD": raise CrowdError("CONFIRM_REQUIRED|REVERT S3CROWD")
        if not os.path.isfile(RECORD): raise CrowdError("RECORD_MISSING")
        record=json.load(open(RECORD,encoding="utf-8"))
        if record.get("state")!="applied": raise CrowdError("RECORD_NOT_APPLIED|"+str(record.get("state")))
        present_labels={_label(a) for a in _actors()}
        missing=[x for x in record["created_actor_labels"] if x not in present_labels]
        root_names={str(b.get_display_name()) for b in root.get_bindings()}
        missing_c=[x for x in (s["label"] for s in plan["shots"]) if x not in root_names]
        if missing or missing_c: raise CrowdError("REVERT_STATE_MISMATCH|actors=%s|cameras=%s"%(missing,missing_c))
        backup=_backup(run,"PreS3CrowdRevert"); root.modify(); clams.modify()
        _restore_cuts(root,record["cuts_before"])
        for guid in record["created_root_bindings"]: _remove_binding(root,guid)
        for hero in record["heroes"]:
            binding=next(b for b in clams.get_bindings() if b.get_id().export_text()==hero["binding_guid"])
            track=next(t for t in binding.get_tracks() if str(t.get_name())==hero["track_name"])
            for name in hero["created_section_names"]:
                hits=[s for s in track.get_sections() if str(s.get_name())==name]
                if len(hits)==1: track.remove_section(hits[0])
            original=next(s for s in track.get_sections() if str(s.get_name())==hero["original"]["name"])
            original.set_range(*hero["original"]["range"])
            _restore_ease(original,hero["original"]["ease"])
            actor_binding=next(b for b in clams.get_bindings() if b.get_id().export_text()==hero["actor_binding_guid"])
            transform=next(t for t in actor_binding.get_tracks() if str(t.get_name())==hero["transform_track_name"])
            for name in hero["sway_sections"]:
                hits=[s for s in transform.get_sections() if str(s.get_name())==name]
                if len(hits)!=1: raise CrowdError("REVERT_SWAY_SECTION_LOOKUP|%s|%s|hits=%d"%(hero["id"],name,len(hits)))
                transform.remove_section(hits[0])
            if not snapshot_equal(_transform_track_snapshot(transform),hero["original_transform_track"]):
                raise CrowdError("REVERT_ORIGINAL_TRANSFORM_READBACK|"+hero["id"])
        for guid in reversed(record["created_clams_bindings"]): _remove_binding(clams,guid)
        subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        by_label={_label(a):a for a in _actors()}
        for label in record["created_actor_labels"]:
            actor=by_label.get(label)
            if actor is None or TAG not in [str(t) for t in actor.tags]: raise CrowdError("REVERT_ACTOR_MISSING_OR_UNTAGGED|"+label)
            subsystem.destroy_actor(actor)
        _save_named(); record.update({"state":"reverted","revert_run":run,"revert_backup":backup}); atomic_json(RECORD,record)
        unreal.log("S3_CROWD_REVERT_OK|run=%s|actors=%d|backup=%s|dirty=0"%(run,len(record["created_actor_labels"]),backup)); return

    discovered=_discover(plan,clams)
    actor_rows=[{"id":r["id"],"label":r["actor_label"],"exists":r["actor_hits"]==1,"hidden":r["hidden"],
                 "components":r["components"],"binding":r["binding_path"],"actor_tracks":r["actor_tracks"]} for r in discovered]
    # 8 Oct conductor: the shore figures are hidden in the EDITOR level by design (the S3 sequence reveals them), so
    # "present" (exactly one actor) is the right census, not editor visibility [measured DRY P21B-DRY-20261008-1].
    visible=[r for r in discovered if r["actor_hits"]==1]
    original_reports=[]; transform_conflict_rows=[]; camera_path=_camera_path_samples(plan,root,cut_before)
    for row in visible:
        member=next(m for m in plan["members"] if m["source_id"]==row["id"] and m["role"]=="existing")
        track=_primary_transform_track(row); track_report=_transform_track_snapshot(track)
        sway_windows=[[a+22,b+22] for a,b in member["transform_sway"]["windows"]]
        conflicts=transform_conflicts([track_report],sway_windows)
        windows,_=_sample_original(row,plan,clams)
        report={"id":row["id"],"actor":row["actor_label"],"track":track_report,
                "sway_windows_ls_clams":sway_windows,"conflicts":conflicts,"crowd_windows":windows,
                "camera_path":_camera_crossings(row,plan,clams,camera_path)}
        original_reports.append(report)
        if conflicts["foreign_additive"] or conflicts["roll_key_ranges"]:
            transform_conflict_rows.append({"id":row["id"],**conflicts})
    cut_mismatches=live_cut_mismatches(cut_before,plan["expected_live_cuts"])
    gate_ok,gate_reason=False,"BENCH_MISSING"
    if os.path.isfile(BENCH): gate_ok,gate_reason=baseline_gate(json.load(open(BENCH,encoding="utf-8")),len(visible))
    unreal.log("S3_CROWD_ACTORS|run=%s|%s"%(run,json.dumps(actor_rows)))
    unreal.log("S3_CROWD_ORIGINAL_TRANSFORMS|run=%s|%s"%(run,json.dumps(original_reports)))
    unreal.log("S3_CROWD_CUTS|run=%s|root=%s|nested=%s|live_layout=%s|mismatches=%s"%
               (run,json.dumps(cut_before),json.dumps(nested),"OK" if not cut_mismatches else "MISMATCH",json.dumps(cut_mismatches)))
    if mode=="DRY":
        teleports=sum(len(window["teleports"]) for row in original_reports for window in row["crowd_windows"])
        crossings=sum(len(row["camera_path"]["crossings"]) for row in original_reports)
        unreal.log("S3_CROWD_DRY_OK|run=%s|actors_found=%d|visible=%d|target=%d|duplicates=%d|clusters=%d|live_cut_layout=%s|existing_transform_tracks=5|transform_conflicts=%s|teleports_in_windows=%d|camera_path_crossings=%d|baseline_gate=%s|reason=%s|writes=0|dirty=0"%
                   (run,sum(r["actor_hits"]==1 for r in discovered),len(visible),plan["target_count"],plan["target_count"]-len(visible),
                    len(plan["clusters"]),"OK" if not cut_mismatches else "MISMATCH",json.dumps(transform_conflict_rows),teleports,crossings,gate_ok,gate_reason)); return
    if args.get("confirm")!="APPLY S3CROWD": raise CrowdError("CONFIRM_REQUIRED|APPLY S3CROWD")
    if not gate_ok: raise CrowdError("BASELINE_REQUIRED|"+gate_reason)
    if cut_mismatches: raise CrowdError("LIVE_CUT_LAYOUT_MISMATCH|"+repr(cut_mismatches))
    if len(visible)!=5 or any(r["actor_hits"]!=1 or r["hidden"] for r in discovered):
        raise CrowdError("SOURCE_ACTORS_MUST_BE_FIVE_VISIBLE|"+repr(actor_rows))
    if any(not r["components"] for r in visible): raise CrowdError("LIVE_CLOTH_COMPONENT_SIGNATURE_MISSING")
    if transform_conflict_rows: raise CrowdError("EXISTING_TRANSFORM_SWAY_CONFLICTS|"+repr(transform_conflict_rows))
    if os.path.exists(RECORD):
        old=json.load(open(RECORD,encoding="utf-8"))
        if old.get("state")!="reverted": raise CrowdError("RECORD_EXISTS|"+str(old.get("state")))
    duplicates_needed=plan["target_count"]-len(visible)
    if duplicates_needed<0 or duplicates_needed>len(plan["duplicate_placements"]): raise CrowdError("DUPLICATE_COUNT_UNSUPPORTED|%d"%duplicates_needed)
    record={"schema":"p21_s3_crowd_record/1","run":run,"state":"applying","plan_path":plan_path,
            "plan_run":plan["run"],"visible_sources":[r["id"] for r in visible],"actor_report":actor_rows,
             "cuts_before":cut_before,"created_actor_labels":[],"created_root_bindings":[],
             "created_clams_bindings":[],"heroes":[],"copies":[],
             "original_transform_report":original_reports,
             "dirty_before":_census()}
    atomic_json(RECORD,record); backup=_backup(run,"PreS3Crowd"); record["backup"]=backup; atomic_json(RECORD,record)
    root.modify(); clams.modify(); subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem); world=_world()
    source_by_id={r["id"]:r for r in discovered}; visible_by_id={r["id"]:r for r in visible}; members=[]
    # The five originals participate exactly where LS_Clams' existing Transform tracks put them.
    # Never touch their level transforms or any pre-existing Transform key.
    for i,row in enumerate(visible):
        member=dict(plan["members"][next(j for j,m in enumerate(plan["members"]) if m["source_id"]==row["id"] and m["role"]=="existing")])
        members.append((member,row["actor"],row["binding"],row["track"],row["section"],False,
                        _primary_transform_track(row)))
    for i,p in enumerate(plan["duplicate_placements"][:duplicates_needed]):
        if p["source_id"] not in visible_by_id: raise CrowdError("PLANNED_SOURCE_NOT_VISIBLE|"+p["source_id"])
        actual_source=p["source_id"]
        src=source_by_id[actual_source]
        actual_label="S3 Crowd %02d (from %s)"%(i+1,actual_source)
        base=src["actor"].get_actor_location(); target=unreal.Vector(p["local_xy_cm"][0]+10921.973,p["local_xy_cm"][1]+160000.0,base.z)
        actor=subsystem.duplicate_actor(src["actor"],world,unreal.Vector(target.x-base.x,target.y-base.y,target.z-base.z))
        if actor is None: raise CrowdError("DUPLICATE_ACTOR_FAILED|"+p["label"])
        actor.set_actor_label(actual_label); actor.set_editor_property("tags",list(actor.tags)+[unreal.Name(TAG),unreal.Name("S3Crowd.Source."+actual_source)])
        actor.set_actor_rotation(unreal.Rotator(roll=0.0,pitch=0.0,yaw=float(p["yaw_deg"])),False)
        if _component_signature(actor)!=src["components"]: raise CrowdError("DUPLICATE_COMPONENT_SIGNATURE|"+actual_label)
        ab=clams.add_possessable(actor); ab.set_display_name(actual_label)
        pose_track,_=_add_copy_transform(ab,actor,run)
        bodies=[c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if str(c.get_name())=="Body"]
        if len(bodies)!=1: raise CrowdError("DUPLICATE_BODY_COUNT|%s|%d"%(actual_label,len(bodies)))
        bb=clams.add_possessable(bodies[0]); bb.set_display_name(actual_label+"/Body"); bb.set_parent(ab)
        track=bb.add_track(unreal.MovieSceneSkeletalAnimationTrack); track.set_display_name("P21 Crowd Animation "+run)
        _add_visibility(ab,360+22)
        member=dict(plan["members"][len(visible)+i]); member["source_id"]=actual_source; member["label"]=actual_label
        if not _pose_matches(actor,member): raise CrowdError("DUPLICATE_POSE_SET_FAILED|"+actual_label)
        members.append((member,actor,bb,track,src["section"],True,pose_track))
        record["created_actor_labels"].append(actual_label); record["created_clams_bindings"].extend([ab.get_id().export_text(),bb.get_id().export_text()])
    # Animation and additive actor roll.
    for member,actor,binding,track,template,is_new,transform_track in members:
        source=plan["sources"][member["source_id"]]
        animation=template.get_editor_property("params").get_editor_property("animation")
        asset_name=animation.get_path_name().rsplit("/",1)[-1].split(".")[-1] if animation else ""
        if asset_name!=source["animation"]: raise CrowdError("ANIMATION_SOURCE_MISMATCH|%s|%s"%(member["source_id"],asset_name))
        original=None
        if not is_new:
            original=_anim_section_snapshot(template)
            template.set_range(original["range"][0],360+22)
            _ease(template, 0, 24)  # 8 Oct: weight-channel fade-out (no Python section easing in 5.8)
        created=[]
        for row in build_source_schedule(member,source): created.append(_make_anim(track,template,animation,clams,row))
        actor_binding=binding.get_parent() if binding.get_parent().is_valid() else binding
        original_transform_track=_transform_track_snapshot(transform_track) if not is_new else None
        sway_sections=_add_roll(transform_track,member,run)
        if not is_new:
            record["heroes"].append({"id":member["source_id"],"binding_guid":binding.get_id().export_text(),
                                      "track_name":str(track.get_name()),"original":original,
                                      "created_section_names":[str(s.get_name()) for s in created],
                                      "actor_binding_guid":actor_binding.get_id().export_text(),
                                      "transform_track_name":str(transform_track.get_name()),
                                      "original_transform_track":original_transform_track,
                                      "sway_sections":sway_sections})
        else:
            record["copies"].append({"label":member["label"],"actor_binding_guid":actor_binding.get_id().export_text(),
                                      "transform_track_name":str(transform_track.get_name()),
                                      "transform_track":_transform_track_snapshot(transform_track)})
    # New spawnable cameras and deterministic cut rewrite.
    camera_bindings={}
    for spec in plan["shots"]:
        b=_camera(root,spec,run); camera_bindings[spec["label"]]=b; record["created_root_bindings"].append(b.get_id().export_text())
    record["cuts_after_base"]=_rewrite_cuts(root,cut_track,cut_before,plan,camera_bindings)
    atomic_json(RECORD,record); _save_named()
    record["hashes_after"]={p:sha256(f) for p,f in FILES.items()}; record["state"]="applied"; atomic_json(RECORD,record)
    # Read back the named actors and all four cameras after save/reload.
    actor_by_label={_label(a):a for a in _actors()}; actor_labels=set(actor_by_label); missing=[x for x in record["created_actor_labels"] if x not in actor_labels]
    root2=unreal.load_asset(ROOT); names={str(b.get_display_name()) for b in root2.get_bindings()}
    missing_c=[s["label"] for s in plan["shots"] if s["label"] not in names]
    _,cuts_read=_cut_snapshot(root2); cut_ranges={tuple(r["range"]) for r in cuts_read if r["active"]}
    missing_cut=[s["range"] for s in plan["shots"] if tuple(s["range"]) not in cut_ranges]
    clams2=unreal.load_asset(CLAMS); clams_guids={b.get_id().export_text() for b in clams2.get_bindings()}
    missing_bind=[g for g in record["created_clams_bindings"] if g not in clams_guids]
    copies=[m for m in plan["members"] if m["role"]=="duplicate"]
    bad_pose=[m["label"] for m in copies if m["label"] not in actor_by_label or not _pose_matches(actor_by_label[m["label"]],m)]
    transform_errors=_original_transform_readback(clams2,record)
    copy_transform_errors=_copy_transform_readback(clams2,record)
    if missing or missing_c or missing_cut or missing_bind or bad_pose or transform_errors or copy_transform_errors:
        raise CrowdError("READBACK_MISSING|actors=%s|cameras=%s|cuts=%s|bindings=%s|copy_poses=%s|original_transforms=%s|copy_transforms=%s"%
                         (missing,missing_c,missing_cut,missing_bind,bad_pose,transform_errors,copy_transform_errors))
    unreal.log("S3_CROWD_APPLY_OK|run=%s|visible_before=%d|duplicates=%d|total=%d|clusters=%d|cameras=%d|copy_poses=15|original_keys_unchanged=5|owned_additive_sections=OK|packages=%s|backup=%s|dirty=0"%
               (run,len(visible),duplicates_needed,plan["target_count"],len(plan["clusters"]),len(plan["shots"]),PACKAGES,backup))


if __name__=="__main__" or unreal is not None:
    try: main()
    except Exception as exc:
        if unreal is None: raise
        unreal.log_error("S3_CROWD_FAILED|run=%s|%r|%s"%(RUN["value"],exc,traceback.format_exc()[-1200:].replace("\n"," / ")))
