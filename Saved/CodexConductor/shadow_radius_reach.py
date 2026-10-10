"""Job 111: passage shadow-light radius census / APPLY / REVERT.

Offline-authored; run later through ExecuteProjectPythonFile.  DRY is read-only.
APPLY writes only attenuation radius, never lowers it, and skips lights whose
radius is keyed by Sequencer.  Fog/VSM findings are report-only.

Evidence used while authoring:
  declaration-proven: FInfinityStageLightSettings::AttenuationRadiusCm,
  VolumetricScatteringIntensity, bCastShadows, bCastVolumetricShadow,
  bUseInverseSquaredFalloff and SourceRadiusCm are declared in
  InfinityStageTypes.h:217-225,239-243,282-295.  Managed attachment identity is
  the tag InfinityStage.Attachment.<cue>|<attachment> in
  InfinityStagePassageActor.cpp:1010-1017.  MaterializedPanels is the live panel
  census in InfinityStagePassageActor.h:87-104.
  inferred: a scattering light without volumetric shadows, or with a source
  radius at/above the configurable threshold, is only a *likely* milky-fog
  contributor.  Increasing local-light radii can increase VSM page pressure;
  station overlap counts are a geometric prediction, not a GPU measurement.
"""
from __future__ import annotations

import copy
import csv
import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import struct

try:
    import unreal  # type: ignore
except ImportError:  # offline harness
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "SHADOWRADIUSREACH"
CONFIRM = {"APPLY": "APPLY SHADOWRADIUSREACH", "REVERT": "REVERT SHADOWRADIUSREACH"}
RECORD = os.path.join(HERE, "shadow_radius_reach_record.json")
PASSAGES = tuple("P%02d" % n for n in range(1, 7))
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
TAG_PREFIX = "InfinityStage.Attachment."
FLOAT_TOL = 0.01

DEFAULTS = {
    "passages": list(PASSAGES),
    "margin_cm": 300.0,
    "cap_cm": None,
    "large_source_radius_cm": 20.0,
    "membership_radius_cm": 5000.0,
    "sequence_roots": ["/Game"],
}


class ReachError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ReachError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def f32(value):
    return struct.unpack("f", struct.pack("f", float(value)))[0]


def finite(value, name):
    value = float(value)
    require(math.isfinite(value), "%s_NOT_FINITE|%r" % (name, value))
    return value


def enum_name(value):
    return str(value).split(".")[-1].split(":")[0].strip().strip("> ").upper()


def object_path(value):
    if value is None:
        return None
    fn = getattr(value, "get_path_name", None)
    return str(fn()) if callable(fn) else str(value)


def asset_id(value):
    path = value.get_path_name() if hasattr(value, "get_path_name") else str(value)
    return str(path).split(":", 1)[0].split(".", 1)[0]


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def dist(a, b, planar=False):
    count = 2 if planar else 3
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(count)))


def guid_text(value):
    if unreal is not None:
        try:
            return str(unreal.GuidLibrary.conv_guid_to_string(value)).upper()
        except Exception:
            pass
    return re.sub(r"[^0-9A-F]", "", str(value).upper())


def check_args(raw):
    raw = dict(raw or {})
    mode = str(raw.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE_INVALID|" + mode)
    if mode != "DRY":
        require(raw.get("confirm") == CONFIRM[mode],
                "CONFIRM_MISSING|need='%s'" % CONFIRM[mode])
    params = copy.deepcopy(DEFAULTS)
    params.update(raw.get("params") or {})
    require(isinstance(params["passages"], list) and params["passages"], "PASSAGES_EMPTY")
    require(all(p in PASSAGES for p in params["passages"]), "PASSAGES_INVALID")
    params["passages"] = sorted(set(params["passages"]))
    params["margin_cm"] = finite(params["margin_cm"], "MARGIN")
    require(params["margin_cm"] >= 0.0, "MARGIN_NEGATIVE")
    params["large_source_radius_cm"] = finite(params["large_source_radius_cm"], "SOURCE_THRESHOLD")
    require(params["large_source_radius_cm"] >= 0.0, "SOURCE_THRESHOLD_NEGATIVE")
    params["membership_radius_cm"] = finite(params["membership_radius_cm"], "MEMBERSHIP_RADIUS")
    require(params["membership_radius_cm"] > 0.0, "MEMBERSHIP_RADIUS_NONPOSITIVE")
    if params["cap_cm"] is not None:
        params["cap_cm"] = finite(params["cap_cm"], "CAP")
        require(params["cap_cm"] > 0.0, "CAP_NONPOSITIVE")
    expected = raw.get("expected_changes")
    require(expected is None or isinstance(expected, int) and expected >= 0, "EXPECTED_CHANGES_INVALID")
    if mode == "APPLY":
        require(expected is not None, "EXPECTED_CHANGES_REQUIRED")
    return {"mode": mode, "confirm": raw.get("confirm"), "params": params,
            "expected_changes": expected, "allow_dirty": list(raw.get("allow_dirty") or [])}


def fog_flags(row, threshold):
    reasons = []
    if float(row.get("volumetric_scattering_intensity", 0.0)) > 0.0:
        if not bool(row.get("cast_volumetric_shadow", False)):
            reasons.append("SCATTERS_WITHOUT_VOLUMETRIC_SHADOW")
        if float(row.get("source_radius_cm", 0.0)) >= float(threshold):
            reasons.append("LARGE_SOURCE_RADIUS")
    return bool(reasons), reasons


def nearest_station(location, stations):
    require(stations, "NO_STATIONS")
    return min(stations, key=lambda s: (dist(location, s["center"]), s["id"]))


def needed_radius(location, station, margin):
    # The wing line is vertical: XY distance is the shortest 3-D distance to it.
    far = max(dist(location, station["left"], True), dist(location, station["right"], True))
    return far + float(margin), far


def plan_census(rows, stations_by_passage, params, keyed_ids=()):
    keyed = set(keyed_ids)
    output = []
    cap = params.get("cap_cm")
    for original in rows:
        row = copy.deepcopy(original)
        passage = row["passage"]
        station = nearest_station(row["location"], stations_by_passage[passage])
        needed, far = needed_radius(row["location"], station, params["margin_cm"])
        current = float(row["attenuation_radius_cm"]) if row.get("attenuation_radius_cm") is not None else None
        keyed_radius = row["id"] in keyed
        applicable = current is not None and bool(row.get("radius_editable", True))
        desired = needed if cap is None else min(needed, float(cap))
        after = current
        reason = "ALREADY_REACHES"
        if not bool(row["cast_shadows"]):
            reason = "NOT_SHADOW_CASTING"
        elif keyed_radius:
            reason = "SEQUENCER_KEYS_RADIUS_REPORT_ONLY"
        elif not applicable:
            reason = ("NO_DURABLE_AUTHORITY" if current is not None else "NO_ATTENUATION_RADIUS")
        elif desired > current + FLOAT_TOL:
            after = desired
            reason = "RAISE" if cap is None or needed <= float(cap) else "RAISE_CAPPED_UNDERREACH"
        fog, fog_reasons = fog_flags(row, params["large_source_radius_cm"])
        row.update({
            "station_id": station["id"], "station_center": station["center"],
            "station_half_width_cm": station["half_width_cm"],
            "far_wing_distance_cm": far, "margin_cm": params["margin_cm"],
            "needed_radius_cm": needed, "planned_radius_cm": after,
            "radius_keyed_by_sequencer": keyed_radius,
            "will_change": reason.startswith("RAISE"), "decision": reason,
            "likely_milky_fog_contributor": fog, "milky_fog_reasons": fog_reasons,
        })
        output.append(row)
    output.sort(key=lambda r: (r["passage"], r["label"], r["id"]))
    return output


def overlap_prediction(planned, stations_by_passage):
    points = []
    for passage in sorted(stations_by_passage):
        local = [r for r in planned if r["passage"] == passage and r["cast_shadows"]
                 and r.get("attenuation_radius_cm") is not None]
        for station in stations_by_passage[passage]:
            before = sum(dist(r["location"], station["center"]) <= float(r["attenuation_radius_cm"])
                         for r in local)
            after = sum(dist(r["location"], station["center"]) <= float(r["planned_radius_cm"])
                        for r in local)
            points.append({"passage": passage, "point": station["id"], "location": station["center"],
                           "shadow_lights_before": before, "shadow_lights_after": after,
                           "delta": after - before})
    return points


def tiered_report(planned, stations_by_passage, sequence_tracks):
    shadows = [r for r in planned if r["cast_shadows"]]
    changes = [r for r in shadows if r["will_change"]]
    fog = [r for r in shadows if r["likely_milky_fog_contributor"]]
    keyed = [r for r in shadows if r["radius_keyed_by_sequencer"]]
    capped = [r for r in shadows if r["decision"] == "RAISE_CAPPED_UNDERREACH"]
    unsupported = [r for r in shadows if r["decision"] in ("NO_ATTENUATION_RADIUS", "NO_DURABLE_AUTHORITY")]
    overlaps = overlap_prediction(planned, stations_by_passage)
    per_passage = {}
    for passage in sorted(stations_by_passage):
        local = [r for r in shadows if r["passage"] == passage]
        per_passage[passage] = {
            "shadow_casters": len(local),
            "will_raise": sum(r["will_change"] for r in local),
            "sequencer_keyed_report_only": sum(r["radius_keyed_by_sequencer"] for r in local),
            "likely_milky_fog_contributors": sum(r["likely_milky_fog_contributor"] for r in local),
            "max_overlap_before": max([p["shadow_lights_before"] for p in overlaps if p["passage"] == passage] or [0]),
            "max_overlap_after": max([p["shadow_lights_after"] for p in overlaps if p["passage"] == passage] or [0]),
        }
    return {
        "tier_0_verdict": {
            "shadow_casters": len(shadows), "will_raise": len(changes),
            "already_reach": sum(r["decision"] == "ALREADY_REACHES" for r in shadows),
            "sequencer_keyed_report_only": len(keyed), "capped_underreach": len(capped),
            "unsupported_no_radius": len(unsupported), "likely_milky_fog_contributors": len(fog),
            "overlap_points_increased": sum(p["delta"] > 0 for p in overlaps),
            "max_overlap_delta": max([p["delta"] for p in overlaps] or [0]),
            "per_passage": per_passage,
        },
        "tier_1_actionable": {
            "raise": [{k: r[k] for k in ("passage", "label", "class", "attenuation_radius_cm",
                       "needed_radius_cm", "planned_radius_cm", "decision")} for r in changes],
            "sequencer_keyed": [{"passage": r["passage"], "label": r["label"],
                                  "tracks": r.get("sequencer_radius_tracks", [])} for r in keyed],
            "fog_report_only": [{"passage": r["passage"], "label": r["label"],
                                  "reasons": r["milky_fog_reasons"]} for r in fog],
        },
        "tier_2_per_light": planned,
        "tier_3_overlap_prediction": overlaps,
        "tier_4_all_radius_tracks": sequence_tracks,
        "claim_tiers": {
            "per_light_live_properties": "measured",
            "show_field_declarations": "declaration-proven",
            "milky_fog_flags": "inferred",
            "overlap_and_vsm_pressure": "inferred",
        },
        "lighting_notes": [
            {"tier": "inferred", "note": "More overlapping shadow-casting local lights can increase VSM page pressure; coloured rectangles are an overflow symptom, not predicted by this census alone."},
            {"tier": "inferred", "note": "Radius reach does not guarantee a readable shaft; shafts still need suitable back/side-light and haze."},
        ],
    }


def parse_attachment_tag(actor):
    for tag in actor.tags:
        text = str(tag)
        if text.startswith(TAG_PREFIX) and "|" in text:
            cue, attachment = text[len(TAG_PREFIX):].split("|", 1)
            return guid_text(cue), guid_text(attachment)
    return None


def load_helper():
    path = os.path.join(HERE, "lighting_looks_apply.py")
    spec = importlib.util.spec_from_file_location("_shadow_radius_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dirty_census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def world_facts(args):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None and asset_id(world) == EXPECTED_WORLD,
            "WORLD_MISMATCH|" + (world.get_path_name() if world else "None"))
    require(editor.get_game_world() is None, "PIE_OR_SIMULATE")
    seq_lib = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    require(seq_lib is None or seq_lib.get_current_level_sequence() is None, "SEQUENCER_IS_OPEN")
    census = dirty_census()
    allowed = set(args["allow_dirty"])
    require(allowed <= {SHOW_PATH, EXPECTED_WORLD}, "ALLOW_DIRTY_OUT_OF_SCOPE")
    require(set(census["content"] + census["maps"]) <= allowed, "DIRTY_BEFORE|" + canonical(census))
    return world, census


def passage_key(label):
    match = re.search(r"Passage\s+0?([1-6])(?:\D|$)", str(label), re.I)
    return "P%02d" % int(match.group(1)) if match else None


def live_transform(ref):
    comp = ref.get_editor_property("component")
    index = int(ref.get_editor_property("instance_index"))
    if comp is not None and index >= 0:
        try:
            return comp.get_instance_transform(index, True)
        except Exception:
            pass
    return ref.get_editor_property("base_world_transform")


def gather_stations(passage, key):
    grouped = {}
    for ref in passage.get_editor_property("materialized_panels"):
        side = enum_name(ref.get_editor_property("side"))
        if side not in ("LEFT", "RIGHT"):
            continue
        cue = guid_text(ref.get_editor_property("cue_guid"))
        grouped.setdefault(cue, {})[side] = vec(live_transform(ref).translation)
    stations = []
    for cue, sides in grouped.items():
        if "LEFT" not in sides or "RIGHT" not in sides:
            continue
        left, right = sides["LEFT"], sides["RIGHT"]
        center = [(left[i] + right[i]) * 0.5 for i in range(3)]
        stations.append({"id": cue, "passage": key, "left": left, "right": right, "center": center,
                         "half_width_cm": dist(left, right) * 0.5})
    require(stations, "NO_LIVE_WING_STATIONS|" + key)
    stations.sort(key=lambda s: (s["center"][0], s["center"][1], s["id"]))
    return stations


def light_components(actor):
    classes = [getattr(unreal, name, None) for name in ("LightComponentBase", "LightComponent")]
    for cls in classes:
        if cls is not None:
            values = actor.get_components_by_class(cls)
            if values:
                return list(values)
    return []


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def component_row(actor, comp, passage, owner, source, cue=None, attachment=None, editable=True):
    radius = prop(comp, "attenuation_radius")
    material = prop(comp, "light_function_material")
    identity = ("SHOW|%s|%s|%s" % (passage, cue, attachment) if source == "SHOW_ATTACHMENT"
                else "%s|%s" % (actor.get_path_name(), comp.get_name()))
    return {
        "id": identity,
        "passage": passage, "label": actor.get_actor_label(), "class": comp.get_class().get_name(),
        "actor_path": actor.get_path_name(), "component_name": comp.get_name(),
        "source": source, "cue_guid": cue, "attachment_guid": attachment,
        "radius_editable": bool(editable),
        "location": vec(comp.get_world_location()), "intensity": float(prop(comp, "intensity", 0.0)),
        "attenuation_radius_cm": None if radius is None else float(radius),
        "volumetric_scattering_intensity": float(prop(comp, "volumetric_scattering_intensity", 0.0)),
        "cast_shadows": bool(prop(comp, "cast_shadows", False)),
        "cast_volumetric_shadow": bool(prop(comp, "cast_volumetric_shadow", False)),
        "use_inverse_squared_falloff": prop(comp, "use_inverse_squared_falloff"),
        "source_radius_cm": float(prop(comp, "source_radius", 0.0)),
        "light_function": object_path(material), "owner_passage_actor": owner,
    }


def scan_radius_tracks(roots):
    tracks = []
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    query = unreal.ARFilter(
        class_paths=[unreal.TopLevelAssetPath("/Script/LevelSequence", "LevelSequence")],
        package_paths=list(roots), recursive_paths=True)
    assets = sorted(registry.get_assets(query), key=lambda data: str(data.package_name))
    for data in assets:
        asset = data.get_asset()
        if asset is None:
            continue
        bindings = list(asset.get_bindings())
        for binding in bindings:
            leaf = str(binding.get_display_name())
            parent_name = None
            try:
                parent = binding.get_parent()
                if parent is not None and parent.is_valid():
                    parent_name = str(parent.get_display_name())
            except Exception:
                pass
            binding_path = "%s/%s" % (parent_name, leaf) if parent_name else leaf
            for track in binding.get_tracks():
                pname = str(track.get_property_name()) if hasattr(track, "get_property_name") else ""
                ppath = str(track.get_property_path()) if hasattr(track, "get_property_path") else ""
                combined = (pname + " " + ppath + " " + str(track.get_display_name())).lower().replace("_", "")
                if "attenuationradius" in combined:
                    tracks.append({"sequence": str(data.package_name), "binding": binding_path,
                                   "property_name": pname, "property_path": ppath,
                                   "track_class": track.get_class().get_name()})
    return tracks


def attach_tracks(rows, tracks):
    keyed = []
    for row in rows:
        actor = row["label"].lower()
        component = row["component_name"].lower()
        hits = [t for t in tracks if actor in t["binding"].lower()
                or t["binding"].lower().split("/")[-1] == component]
        row["sequencer_radius_tracks"] = hits
        if hits:
            keyed.append(row["id"])
    return keyed


def gather_live(args):
    world, census = world_facts(args)
    actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    passages = {}
    for actor in actors:
        key = passage_key(actor.get_actor_label())
        if key in args["params"]["passages"] and prop(actor, "materialized_panels") is not None:
            require(key not in passages, "PASSAGE_ACTOR_DUPLICATE|" + key)
            passages[key] = actor
    require(set(passages) == set(args["params"]["passages"]), "PASSAGE_ACTORS_MISSING|" + canonical(sorted(passages)))
    stations = {key: gather_stations(actor, key) for key, actor in passages.items()}
    managed = {}
    for key, passage in passages.items():
        for actor in passage.get_editor_property("managed_attachment_actors"):
            identity = parse_attachment_tag(actor)
            if identity:
                managed[actor.get_path_name()] = (key, passage.get_actor_label(), identity[0], identity[1])
    rows = []
    for actor in actors:
        comps = light_components(actor)
        if not comps:
            continue
        if actor.get_path_name() in managed:
            key, owner, cue, attachment = managed[actor.get_path_name()]
            for index, comp in enumerate(comps):
                # The C++ contract applies Show settings to the first Light Component only
                # (InfinityStageTypes.h:189-191). Extra custom-class components are censused
                # but cannot be durably edited here without changing their Blueprint authority.
                source = "SHOW_ATTACHMENT" if index == 0 else "MANAGED_EXTRA_COMPONENT"
                rows.append(component_row(actor, comp, key, owner, source, cue, attachment,
                                          editable=index == 0))
            continue
        for comp in comps:
            explicit = passage_key(actor.get_actor_label())
            candidates = [(dist(vec(comp.get_world_location()), s["center"]), key)
                          for key, values in stations.items() for s in values]
            if not candidates:
                continue
            nearest_distance, key = min(candidates)
            if explicit in stations:
                key = explicit
            elif nearest_distance > args["params"]["membership_radius_cm"]:
                continue
            rows.append(component_row(actor, comp, key, passages[key].get_actor_label(), "LEVEL_ACTOR"))
    tracks = scan_radius_tracks(args["params"]["sequence_roots"])
    keyed = attach_tracks(rows, tracks)
    return {"world": world, "census": census, "passages": passages, "stations": stations,
            "rows": rows, "tracks": tracks, "keyed": keyed}


def report_paths(mode, run):
    stem = os.path.join(HERE, "shadow_radius_reach_report_%s_%s" % (mode, run))
    return stem + ".json", stem + ".csv"


CSV_FIELDS = ("passage", "label", "class", "intensity", "cast_shadows", "attenuation_radius_cm", "needed_radius_cm",
              "planned_radius_cm", "volumetric_scattering_intensity", "cast_volumetric_shadow",
              "use_inverse_squared_falloff", "light_function", "radius_keyed_by_sequencer",
              "source_radius_cm", "likely_milky_fog_contributor", "milky_fog_reasons", "decision")


def write_report(report, mode, run):
    json_path, csv_path = report_paths(mode, run)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in report["tiers"]["tier_2_per_light"]:
            cooked = dict(row)
            cooked["milky_fog_reasons"] = ";".join(row["milky_fog_reasons"])
            writer.writerow(cooked)
    return json_path, csv_path


def show_index(show):
    out = {}
    for cue_index, cue in enumerate(show.get_editor_property("cues")):
        cue_id = guid_text(cue.get_editor_property("cue_guid"))
        if enum_name(cue.get_editor_property("type")) not in ("WINGPAIR", "WING_PAIR"):
            continue
        pair = cue.get_editor_property("wing_pair")
        for att_index, attachment in enumerate(pair.get_editor_property("attachments")):
            out[(cue_id, guid_text(attachment.get_editor_property("attachment_guid")))] = (
                cue_index, att_index, cue, pair, attachment)
    return out


def resolve_level_component(row, actors):
    hits = [a for a in actors if a.get_path_name() == row["actor_path"]]
    require(len(hits) == 1, "LEVEL_ACTOR_RESOLVE|" + row["actor_path"])
    comps = [c for c in hits[0].get_components_by_class(unreal.ActorComponent) if c.get_name() == row["component_name"]]
    require(len(comps) == 1, "LEVEL_COMPONENT_RESOLVE|" + row["id"])
    return comps[0]


def set_show_radius(show, target, value, expected, strict=True):
    index = show_index(show)
    key = (target["cue_guid"], target["attachment_guid"])
    require(key in index, "SHOW_TARGET_RESOLVE|" + canonical(key))
    cue_index, att_index, cue, pair, attachment = index[key]
    lighting = attachment.get_editor_property("lighting")
    live = float(lighting.get_editor_property("attenuation_radius_cm"))
    if strict:
        require(abs(live - float(expected)) <= FLOAT_TOL,
                "SHOW_RADIUS_DRIFT|%s|%s|%s" % (target["label"], live, expected))
    lighting.set_editor_property("attenuation_radius_cm", float(value))
    attachment.set_editor_property("lighting", lighting)
    attachments = list(pair.get_editor_property("attachments"))
    attachments[att_index] = attachment
    pair.set_editor_property("attachments", attachments)
    cue.set_editor_property("wing_pair", pair)
    cues = list(show.get_editor_property("cues"))
    cues[cue_index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def apply_values(live, targets, side, strict=True):
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    require(show is not None, "SHOW_MISSING")
    actors = list(unreal.GameplayStatics.get_all_actors_of_class(live["world"], unreal.Actor))
    for target in targets:
        before, after = target["attenuation_radius_cm"], target["planned_radius_cm"]
        want, expected = (after, before) if side == "after" else (before, after)
        if target["source"] == "SHOW_ATTACHMENT":
            set_show_radius(show, target, want, expected, strict)
        else:
            comp = resolve_level_component(target, actors)
            current = float(comp.get_editor_property("attenuation_radius"))
            if strict:
                require(abs(current - float(expected)) <= FLOAT_TOL,
                        "LEVEL_RADIUS_DRIFT|%s|%s|%s" % (target["label"], current, expected))
            comp.set_editor_property("attenuation_radius", float(want))
    affected = sorted({t["passage"] for t in targets if t["source"] == "SHOW_ATTACHMENT"})
    for key in affected:
        require(bool(live["passages"][key].materialize_passage()), "MATERIALIZE_FAILED|" + key)
    return affected


def save_narrow(targets):
    census = dirty_census()
    require(not (set(census["content"]) - {SHOW_PATH})
            and not (set(census["maps"]) - {EXPECTED_WORLD}),
            "OUT_OF_SCOPE_DIRTY_BEFORE_SAVE|" + canonical(census))
    if any(t["source"] == "SHOW_ATTACHMENT" for t in targets):
        require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=True), "SHOW_SAVE_FAILED")
    if EXPECTED_WORLD in census["maps"]:
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
    require(dirty_census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE")


def verify_targets(live, targets, side):
    fresh = gather_live({"params": live["args"]["params"], "allow_dirty": [SHOW_PATH, EXPECTED_WORLD]})
    by_id = {r["id"]: r for r in fresh["rows"]}
    bad = []
    for target in targets:
        expected = target["planned_radius_cm"] if side == "after" else target["attenuation_radius_cm"]
        got = by_id.get(target["id"], {}).get("attenuation_radius_cm")
        if got is None or abs(float(got) - float(expected)) > FLOAT_TOL:
            bad.append({"id": target["id"], "expected": expected, "got": got})
    require(not bad, "READBACK_RADIUS|" + canonical(bad)[:4000])


def run(raw):
    args = check_args(raw)
    mode = args["mode"]
    run_id = datetime.datetime.now().strftime("SRR-%Y%m%d-%H%M%S")
    report = {"schema_version": 1, "ok": False, "mode": mode, "run": run_id,
              "args": args, "saved": False}
    try:
        if mode == "REVERT":
            require(os.path.isfile(RECORD), "REVERT_RECORD_ABSENT")
            with open(RECORD, encoding="utf-8") as handle:
                record = json.load(handle)
            require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS")
            live = gather_live(args)
            live["args"] = args
            targets = record["targets"]
            helper = load_helper()
            backup = helper._backup("PreShadowRadiusReachRevert-", run_id)
            apply_values(live, targets, "before")
            save_narrow(targets)
            report["saved"] = True
            verify_targets(live, targets, "before")
            require(dirty_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY")
            archive = RECORD + ".reverted-" + run_id
            record.update({"status": "reverted", "revert_run": run_id, "revert_backup": backup})
            with open(RECORD, "w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2, sort_keys=True)
            os.replace(RECORD, archive)
            report.update({"ok": True, "backup": backup, "record_archived": archive,
                           "tiers": record["tiers"]})
            write_report(report, mode, run_id)
            unreal.log("%s_REVERT_OK|run=%s|rows=%d|readback=1|archived=%s" %
                       (MARK, run_id, len(targets), archive))
            return report

        live = gather_live(args)
        live["args"] = args
        planned = plan_census(live["rows"], live["stations"], args["params"], live["keyed"])
        tiers = tiered_report(planned, live["stations"], live["tracks"])
        report.update({"tiers": tiers, "dirty_before": live["census"]})
        changes = [r for r in planned if r["will_change"]]
        if mode == "DRY":
            require(dirty_census() == live["census"], "DRY_DIRTY_CHANGED")
            report["ok"] = True
            paths = write_report(report, mode, run_id)
            unreal.log("%s_DRY_OK|run=%s|shadow=%d|raise=%d|keyed=%d|fog=%d|reports=%s" %
                       (MARK, run_id, tiers["tier_0_verdict"]["shadow_casters"], len(changes),
                        tiers["tier_0_verdict"]["sequencer_keyed_report_only"],
                        tiers["tier_0_verdict"]["likely_milky_fog_contributors"], paths[0]))
            return report
        require(len(changes) == args["expected_changes"],
                "EXPECTED_CHANGES|expected=%d|live=%d" % (args["expected_changes"], len(changes)))
        if not changes:
            report.update({"ok": True, "saved": False, "no_op": True})
            write_report(report, mode, run_id)
            unreal.log("%s_APPLY_OK|run=%s|rows=0|NO_OP|nothing_saved=1" % (MARK, run_id))
            return report
        require(not os.path.exists(RECORD), "ACTIVE_RECORD_EXISTS")
        helper = load_helper()
        backup = helper._backup("PreShadowRadiusReach-", run_id)
        record = {"schema_version": 1, "status": "prepared", "run": run_id,
                  "backup": backup, "args": args, "targets": changes, "tiers": tiers}
        with open(RECORD, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
        try:
            affected = apply_values(live, changes, "after")
        except Exception as apply_error:
            rollback_error = None
            try:
                apply_values(live, changes, "before", strict=False)
            except Exception as error:
                rollback_error = "%s: %s" % (type(error).__name__, error)
            record.update({"status": "failed_rolled_back_in_memory" if rollback_error is None else "failed_rollback",
                           "apply_error": "%s: %s" % (type(apply_error).__name__, apply_error),
                           "rollback_error": rollback_error})
            with open(RECORD, "w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2, sort_keys=True)
            failed_record = RECORD + ".failed-" + run_id
            os.replace(RECORD, failed_record)
            raise ReachError("APPLY_FAILED|rollback=%s|record=%s|%s" %
                             ("OK" if rollback_error is None else rollback_error, failed_record, apply_error))
        save_narrow(changes)
        report["saved"] = True
        verify_targets(live, changes, "after")
        post = dirty_census()
        require(post == {"content": [], "maps": []}, "POST_SAVE_DIRTY|" + canonical(post))
        record.update({"status": "saved_readback_verified", "affected_passages": affected,
                       "saved_census": post})
        with open(RECORD, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
        report.update({"ok": True, "backup": backup, "record": RECORD,
                       "affected_passages": affected, "saved_census": post})
        write_report(report, mode, run_id)
        unreal.log("%s_APPLY_OK|run=%s|rows=%d|passages=%s|readback=1|record=%s" %
                   (MARK, run_id, len(changes), ",".join(affected), RECORD))
        return report
    except Exception as error:
        report["error"] = "%s: %s" % (type(error).__name__, error)
        try:
            write_report(report, mode, run_id)
        except Exception:
            pass
        if unreal is not None:
            unreal.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s" %
                             (MARK, run_id, mode, int(report["saved"]), report["error"],
                              "" if report["saved"] else "|NOTHING SAVED"))
        raise


def main():
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    raw = globals().get("SHADOW_RADIUS_REACH_ARGS")
    require(isinstance(raw, dict), "ARGS_MISSING")
    return run(raw)


if __name__ == "__main__":
    main()
