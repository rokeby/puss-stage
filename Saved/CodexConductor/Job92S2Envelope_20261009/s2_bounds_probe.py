"""JOB 92 READ-ONLY S2 BOUNDS PROBE.  No property writes, saves, Sequencer opens or time changes.

Measures every PrimitiveComponent in Klara's streamed Japanese_Alley level, transforms all eight world-AABB
corners into the S2 Hangar Root frame, and reports both the complete envelope and a renderable-geometry envelope.
Also inventories the S2 hangar, rise, ARRMOV targets, S2WALLHIDE tracks, V3 overlay, floor/apron and handoff cameras.
Output: s2_bounds_<run>.json. Marker: S2_BOUNDS_OK. Klara's level is never saved.
"""
import datetime
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor", "Job92S2Envelope_20261009")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HER_LEVEL = "Japanese_Alley"
RISE = "/Game/InfinityStage/RigAtmos/LS_S2_HangarRise"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"
COPY = "/Game/InfinityStage/KlaraHookin/LS_NEW_SHRINE_S2Hangar"
OVERLAY = "/Game/Scenes/KlaraS2V3/LS_S2_V3WingsOverlay"


def pkg(value):
    return str(value.get_path_name()).split(".", 1)[0]


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(pkg(x) for x in lib.get_dirty_content_packages()),
            "maps": sorted(pkg(x) for x in lib.get_dirty_map_packages())}


def guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def bounds_corners(origin, extent):
    return [unreal.Vector(origin.x + x * extent.x, origin.y + y * extent.y, origin.z + z * extent.z)
            for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]


def grow(box, point):
    if box is None:
        return {"min": [point.x, point.y, point.z], "max": [point.x, point.y, point.z]}
    for i, v in enumerate((point.x, point.y, point.z)):
        box["min"][i] = min(box["min"][i], v); box["max"][i] = max(box["max"][i], v)
    return box


def seq_rows(path):
    seq = unreal.load_asset(path)
    if seq is None:
        return {"path": path, "missing": True}
    bindings = []
    for b in seq.get_bindings():
        tracks = []
        for t in b.get_tracks():
            sections = []
            for s in t.get_sections():
                channels = []
                for c in s.get_all_channels():
                    channels.append(str(c.get_name()))  # suffixes retained; consumers normalise semantically
                sections.append({"range": [int(s.get_start_frame()) if s.has_start_frame() else None,
                                             int(s.get_end_frame()) if s.has_end_frame() else None],
                                 "active": bool(s.is_active()), "channels": channels})
            prop = None
            try: prop = str(t.get_property_name())
            except Exception: pass
            tracks.append({"class": t.get_class().get_name(), "name": str(t.get_display_name()),
                           "property": prop, "sections": sections})
        bindings.append({"name": str(b.get_display_name()), "guid": guid(b.get_id()), "tracks": tracks})
    return {"path": path, "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
            "bindings": bindings}


def main():
    run = datetime.datetime.now().strftime("S2BOUNDS-%Y%m%d-%H%M%S")
    before = census()
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if world is None or pkg(world) != WORLD or ed.get_game_world() is not None:
        raise RuntimeError("WRONG_WORLD_OR_PIE")
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    roots = [a for a in actors if str(a.get_actor_label()) == "S2 Hangar Root"]
    if len(roots) != 1:
        raise RuntimeError("ROOT_COUNT|%d" % len(roots))
    root = roots[0]; inverse = root.get_actor_transform().inverse()
    rows, all_box, render_box = [], None, None
    excluded_classes = ("Sky", "Atmospheric", "Fog", "PostProcess", "Light", "Volume")
    for actor in actors:
        outer = str(actor.get_outer().get_outer().get_name()) if actor.get_outer() and actor.get_outer().get_outer() else "?"
        if HER_LEVEL not in outer:
            continue
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(comp)
            if max(extent.x, extent.y, extent.z) <= 0.01:
                continue
            local = [inverse.transform_location(p) for p in bounds_corners(origin, extent)]
            for point in local: all_box = grow(all_box, point)
            cls = comp.get_class().get_name()
            renderable = not any(word in cls for word in excluded_classes) and bool(comp.is_visible())
            if renderable:
                for point in local: render_box = grow(render_box, point)
            rows.append({"actor": str(actor.get_actor_label()), "actor_path": str(actor.get_path_name()),
                         "component": str(comp.get_name()), "class": cls, "renderable": renderable,
                         "local_min": [min(p.x for p in local), min(p.y for p in local), min(p.z for p in local)],
                         "local_max": [max(p.x for p in local), max(p.y for p in local), max(p.z for p in local)]})
    if render_box is None:
        raise RuntimeError("NO_RENDERABLE_KLARA_BOUNDS")
    hangar = []
    for a in actors:
        label = str(a.get_actor_label())
        tags = [str(t) for t in a.get_editor_property("tags")]
        if "RigAtmos.Scene2Hangar" not in tags and not label.startswith("S2 Hangar") and not label.startswith("S2 Lattice"):
            continue
        loc = inverse.transform_location(a.get_actor_location()); sc = a.get_actor_scale3d()
        hangar.append({"label": label, "path": str(a.get_path_name()), "class": a.get_class().get_name(),
                       "root_local": [loc.x, loc.y, loc.z], "scale": [sc.x, sc.y, sc.z], "tags": tags,
                       "parent": str(a.get_attach_parent_actor().get_actor_label()) if a.get_attach_parent_actor() else None})
    cams = []
    for a in actors:
        label = str(a.get_actor_label())
        if label.startswith("Scene 2 ") and "Handoff Camera" in label:
            loc = inverse.transform_location(a.get_actor_location())
            cams.append({"label": label, "path": str(a.get_path_name()), "root_local": [loc.x, loc.y, loc.z]})
    arrival = next((a for a in actors if str(a.get_actor_label()) == "S2 Arrival"), None)
    drives = []
    if arrival is not None:
        for d in list(arrival.get_editor_property("additional_initial_transform_drives")):
            target = d.get_editor_property("target")
            drives.append({"target": str(target.get_actor_label()) if target else None,
                           "guid": guid(d.get_editor_property("binding_guid"))})
    report = {"schema": 1, "tool": "s2_bounds_probe", "run": run, "world": pkg(world), "mutated": False,
              "census_before": before, "content_bounds_all": all_box, "content_bounds_renderable": render_box,
              "components": rows, "hangar_actors": hangar, "handoff_cameras": cams, "arrival_drives": drives,
              "sequences": {p: seq_rows(p) for p in (RISE, SCENE, COPY, OVERLAY)}}
    out = os.path.join(HERE, "s2_bounds_%s.json" % run)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1); fh.flush(); os.fsync(fh.fileno())
    after = census()
    if after != before:
        raise RuntimeError("PROBE_DIRTIED|before=%s|after=%s" % (before, after))
    unreal.log("S2_BOUNDS_OK|run=%s|components=%d|render_min=%s|render_max=%s|hangar=%d|cams=%d|mutated=0|report=%s" %
               (run, len(rows), [round(v, 1) for v in render_box["min"]], [round(v, 1) for v in render_box["max"]],
                len(hangar), len(cams), out))


try:
    main()
except Exception as exc:  # noqa: BLE001
    unreal.log_error("S2_BOUNDS_FAILED|%r" % (exc,))
