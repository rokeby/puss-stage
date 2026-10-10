"""Job 130: diagnose and repair the Scene 2 shrine Niagara lifecycle.

Offline-authored. The conductor runs this file in the open UE 5.8 editor.
PROBE and DRY are read-only with respect to Unreal packages. APPLY/REVERT may
save only /Game/InfinityStage/Dev/Sequences/LS_DevScene_02. Klara maps/assets
are never saved.

Modes and exact confirmations:
  PROBE  "PROBE JOB130"
  DRY    "DRY JOB130"
  APPLY  "APPLY JOB130 S2 SHRINE FIRE"
  REVERT "REVERT JOB130 S2 SHRINE FIRE"
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


FOLDER = "Job130S2ShrineFire_20261010"
S2_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"
MASTER_CANDIDATES = (
    "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master",
    "/Game/InfinityStage/Dev/Sequences/LS_Master",
    "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_Master",
)
KLARA_LEVEL_TOKENS = ("SHRINE", "KK_S2", "JAPANESE_ALLEY")
CONFIRMS = {
    "PROBE": "PROBE JOB130",
    "DRY": "DRY JOB130",
    "APPLY": "APPLY JOB130 S2 SHRINE FIRE",
    "REVERT": "REVERT JOB130 S2 SHRINE FIRE",
}


class Stop(RuntimeError):
    pass


def _ue():
    if unreal is None:
        raise RuntimeError("UNREAL_MODULE_REQUIRED")
    return unreal


def _safe(obj, name, default=None):
    if obj is None:
        return default
    try:
        return obj.get_editor_property(name)
    except Exception:  # noqa: BLE001 - reflected properties vary by UE build.
        return default


def _call(obj, name, default=None, *args):
    try:
        return getattr(obj, name)(*args)
    except Exception:  # noqa: BLE001
        return default


def _path(obj):
    return _call(obj, "get_path_name", None) if obj is not None else None


def _guid(value):
    return str(_ue().GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def _enum(value):
    raw = str(getattr(value, "name", value)).strip("<>")
    return raw.split(":", 1)[0].rsplit(".", 1)[-1]


def _frame(value):
    try:
        return int(value.value)
    except Exception:  # noqa: BLE001
        try:
            return int(value)
        except Exception:  # noqa: BLE001
            return None


def _section_range(section):
    start = _call(section, "get_start_frame", None) if _call(section, "has_start_frame", False) else None
    end = _call(section, "get_end_frame", None) if _call(section, "has_end_frame", False) else None
    return [_frame(start), _frame(end)]


def _census():
    lib = _ue().EditorLoadingAndSavingUtils
    return {
        "content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
        "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages()),
    }


def _here():
    root = _ue().Paths.convert_relative_path_to_full(_ue().Paths.project_saved_dir())
    return os.path.join(root, "CodexConductor", FOLDER)


def _record_path():
    return os.path.join(_here(), "job130_record.json")


def _asset_file(asset_path):
    relative = asset_path.removeprefix("/Game/") + ".uasset"
    return os.path.join(_ue().Paths.convert_relative_path_to_full(_ue().Paths.project_content_dir()), relative)


def _write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


def _hash_json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def review_payload(probe):
    """Remove execution metadata while retaining every diagnosis/fix input."""
    return {k: v for k, v in probe.items() if k not in ("run", "mode", "probe_sha256", "dirty_census")}


def _level_name(actor):
    level = _call(actor, "get_level", None)
    return _path(level) or str(_call(actor, "get_outermost", "UNKNOWN"))


def _location(component):
    value = _call(component, "get_world_location", None)
    if value is None:
        owner = _call(component, "get_owner", None)
        value = _call(owner, "get_actor_location", None)
    if value is None:
        return None
    return [float(value.x), float(value.y), float(value.z)]


def _distance(a, b):
    if a is None or b is None:
        return None
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _asset_mentions_shrine(actor, tokens):
    hay = [str(_path(actor) or ""), str(_call(actor, "get_actor_label", "") or "")]
    for comp in _call(actor, "get_components_by_class", [], _ue().ActorComponent) or []:
        hay.append(str(_path(comp) or ""))
        for prop in ("static_mesh", "skeletal_mesh", "asset", "template"):
            hay.append(str(_path(_safe(comp, prop)) or ""))
    joined = "|".join(hay).upper()
    return any(str(token).upper() in joined for token in tokens)


def _anchor(actors, tokens):
    points = []
    owners = []
    for actor in actors:
        if _asset_mentions_shrine(actor, tokens):
            p = _location(_call(actor, "get_root_component", None))
            if p is not None:
                points.append(p)
                owners.append(_path(actor))
    if not points:
        raise Stop("SHRINE_ANCHOR_NOT_FOUND|tokens=%r" % (tokens,))
    centre = [sum(p[i] for p in points) / len(points) for i in range(3)]
    return centre, sorted(owners)


def _scalability_rows(system):
    rows = []
    effect = _safe(system, "effect_type")
    containers = []
    for source, obj, prop in (
        ("effect_type", effect, "system_scalability_settings"),
        ("system_override", system, "system_scalability_overrides"),
    ):
        value = _safe(obj, prop)
        settings = _safe(value, "settings", None)
        if settings is None:
            settings = _safe(value, "overrides", [])
        for setting in settings or []:
            containers.append((source, setting))
    for source, setting in containers:
        rows.append({
            "source": source,
            "cull_by_distance": _safe(setting, "cull_by_distance"),
            "max_distance_cm": _safe(setting, "max_distance"),
            "cull_when_not_rendered": _safe(setting, "cull_when_not_rendered"),
            "max_time_without_render_s": _safe(setting, "max_time_without_render"),
            "cull_by_instance_count": _safe(setting, "cull_max_instance_count"),
            "max_instances": _safe(setting, "max_instances"),
        })
    return {"effect_type": _path(effect), "settings": rows}


def _system_row(system):
    if system is None:
        return None
    fixed = _call(system, "get_fixed_bounds", None)
    return {
        "asset": _path(system),
        "fixed_bounds_enabled": _safe(system, "fixed_bounds", _safe(system, "b_fixed_bounds")),
        "fixed_bounds": str(fixed) if fixed is not None else None,
        "warmup_time_s": _call(system, "get_warmup_time", _safe(system, "warmup_time")),
        "warmup_tick_count": _call(system, "get_warmup_tick_count", _safe(system, "warmup_tick_count")),
        "warmup_tick_delta_s": _call(system, "get_warmup_tick_delta", _safe(system, "warmup_tick_delta")),
        "override_scalability": _safe(system, "override_scalability_settings"),
        "scalability": _scalability_rows(system),
    }


def _track_property(track):
    name = str(_call(track, "get_property_name", "") or "")
    path = str(_call(track, "get_property_path", "") or "")
    if name == "None":
        name = ""
    if path == "None":
        path = ""
    return name, path


def _track_row(track):
    cls = track.get_class().get_name()
    prop_name, prop_path = _track_property(track)
    sections = []
    for section in track.get_sections():
        row = {"range": _section_range(section), "active": bool(_call(section, "is_active", True))}
        if cls == "MovieSceneNiagaraSystemTrack":
            row.update({
                "start_behavior": _enum(_call(section, "get_section_start_behavior", None)),
                "evaluate_behavior": _enum(_call(section, "get_section_evaluate_behavior", None)),
                "end_behavior": _enum(_call(section, "get_section_end_behavior", None)),
                "allow_scalability": _call(section, "get_allow_scalability", None),
            })
        elif cls == "MovieSceneLevelVisibilityTrack":
            row.update({"level_names": [str(x) for x in (_safe(section, "level_names", []) or [])],
                        "visibility": _enum(_safe(section, "visibility"))})
        channels = []
        for channel in _call(section, "get_all_channels", []) or []:
            keys = []
            for key in _call(channel, "get_keys", []) or []:
                keys.append([_frame(_call(key, "get_time", None)), _call(key, "get_value", None)])
            channels.append({"name": str(_call(channel, "get_name", "")), "keys": keys})
        if channels:
            row["channels"] = channels
        sections.append(row)
    return {"class": cls, "name": str(_call(track, "get_display_name", _call(track, "get_name", ""))),
            "property_name": prop_name, "property_path": prop_path, "sections": sections}


def _binding_kind(binding):
    for name, kind in (("is_spawnable", "spawnable"), ("is_possessable", "possessable")):
        value = _call(binding, name, None)
        if value is True:
            return kind
    return "unknown"


def _walk_sequences(roots, world):
    queue = [(path, 0) for path in roots]
    seen = set()
    sequences = []
    object_tracks = {}
    streaming_tracks = []
    niagara_bindings = []
    while queue:
        path, depth = queue.pop(0)
        if path in seen or depth > 5:
            continue
        seen.add(path)
        seq = _ue().load_asset(path)
        if seq is None:
            continue
        seq_path = _path(seq).split(".", 1)[0]
        sequences.append(seq_path)
        for binding in seq.get_bindings():
            bound = _call(seq, "locate_bound_objects", [], binding, world) or []
            tracks = [_track_row(t) for t in binding.get_tracks()]
            b_row = {"sequence": seq_path, "binding": str(binding.get_display_name()),
                     "binding_guid": _guid(binding.get_id()), "kind": _binding_kind(binding),
                     "tracks": tracks}
            template = _call(binding, "get_object_template", None)
            if ("NIAGARA" in str(binding.get_display_name()).upper() or
                    any("Niagara" in t["class"] for t in tracks) or
                    (template is not None and "Niagara" in template.get_class().get_name())):
                niagara_bindings.append(dict(b_row, template=_path(template),
                                             resolved_objects=sorted(filter(None, (_path(x) for x in bound)))))
            for obj in bound:
                object_tracks.setdefault(_path(obj), []).append(b_row)
                owner = _call(obj, "get_owner", None)
                if owner is not None:
                    object_tracks.setdefault(_path(owner), []).append(b_row)
        for track in seq.get_tracks():
            cls = track.get_class().get_name()
            if cls == "MovieSceneLevelVisibilityTrack":
                streaming_tracks.append({"sequence": seq_path, "track": _track_row(track)})
            if cls in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
                for section in track.get_sections():
                    child = _call(section, "get_sequence", None)
                    if child is not None:
                        queue.append((_path(child).split(".", 1)[0], depth + 1))
    return {"sequences": sequences, "object_tracks": object_tracks,
            "level_visibility_tracks": streaming_tracks, "niagara_bindings": niagara_bindings}


def _streaming(world):
    rows = []
    for level in _call(world, "get_streaming_levels", []) or []:
        loaded = _call(level, "is_level_loaded", None)
        visible = _call(level, "is_level_visible", None)
        rows.append({
            "object": _path(level),
            "world_asset": str(_safe(level, "world_asset") or _safe(level, "world_asset_package_name") or ""),
            "should_be_loaded": _safe(level, "should_be_loaded"),
            "should_be_visible": _safe(level, "should_be_visible"),
            "loaded": loaded,
            "visible": visible,
        })
    return rows


def _range_contains(frame, section):
    bounds = section.get("range") or [None, None]
    start, end = bounds[0], bounds[1]
    return (start is None or frame >= start) and (end is None or frame < end)


def _lifecycle_off_at(track, frame):
    sections = [s for s in track.get("sections", []) if s.get("active", True)]
    if frame is None:
        return any(str(s.get("end_behavior", "")).upper() in ("DEACTIVATE", "SET_SYSTEM_INACTIVE", "SETSYSTEMINACTIVE") for s in sections)
    return not any(_range_contains(frame, section) for section in sections)


def rank_causes(components, streaming_rows, probe_frame=None):
    """Return evidence-weighted hypotheses; pure and covered by the harness."""
    klara = [r for r in streaming_rows if any(t in (str(r).upper()) for t in KLARA_LEVEL_TOKENS)]
    lifecycle = [t for c in components for b in c.get("bound_tracks", []) for t in b.get("tracks", [])
                 if t.get("class") in ("MovieSceneNiagaraSystemTrack", "MovieSceneSpawnTrack")]
    vis = [t for c in components for b in c.get("bound_tracks", []) for t in b.get("tracks", [])
           if t.get("class") == "MovieSceneVisibilityTrack"]
    scores = {
        "streamed level not visible in PIE": 100 if any(r.get("visible") is False or r.get("loaded") is False for r in klara) else 15,
        "deactivation track": 85 if any(_lifecycle_off_at(t, probe_frame) for t in lifecycle) else 10,
        "auto_activate off with no trigger": 80 if any(c.get("auto_activate") is False and not c.get("has_lifecycle_trigger_at_plus5", c.get("has_lifecycle_track")) for c in components) else 5,
        "inert visibility track": 75 if any(t.get("property_name") in ("", "bHiddenInGame") for t in vis) else 5,
        "scalability culling": 60 if any(c.get("allow_scalability") is not False and c.get("has_distance_cull") for c in components) else 10,
    }
    return [{"cause": cause, "score": score} for cause, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]


def collect_probe(args):
    u = _ue()
    if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is not None:
        raise Stop("PIE_RUNNING|use job130_s2_shrine_fire_pie.py")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    tokens = args.get("anchor_tokens") or ["/Game/KK_S2_Shrine/", "SHRINE"]
    anchor, anchor_owners = _anchor(actors, tokens)
    roots = [S2_SEQUENCE]
    roots.extend(path for path in MASTER_CANDIDATES if u.EditorAssetLibrary.does_asset_exist(path))
    seq_info = _walk_sequences(roots, world)
    s2 = u.load_asset(S2_SEQUENCE)
    rate = s2.get_display_rate()
    s2_plus5_frame = int(s2.get_playback_start() + round(5.0 * float(rate.numerator) / float(rate.denominator)))
    radius = float(args.get("radius_cm", 12000.0))
    components = []
    for actor in actors:
        for comp in _call(actor, "get_components_by_class", [], u.NiagaraComponent) or []:
            loc = _location(comp)
            distance = _distance(anchor, loc)
            if distance is None or distance > radius:
                continue
            system = _call(comp, "get_asset", _safe(comp, "asset"))
            bound = seq_info["object_tracks"].get(_path(comp), []) + seq_info["object_tracks"].get(_path(actor), [])
            lifecycle = [t for b in bound for t in b["tracks"] if t["class"] == "MovieSceneNiagaraSystemTrack"]
            root_lifecycle = [t for b in bound if b["sequence"] == S2_SEQUENCE for t in b["tracks"]
                              if t["class"] == "MovieSceneNiagaraSystemTrack"]
            sysrow = _system_row(system)
            culls = (sysrow or {}).get("scalability", {}).get("settings", [])
            components.append({
                "component": _path(comp), "owner": _path(actor), "owner_label": str(_call(actor, "get_actor_label", "")),
                "owner_level": _level_name(actor), "location": loc, "distance_to_shrine_cm": round(distance, 2),
                "system": sysrow, "auto_activate": _safe(comp, "auto_activate"),
                "is_active": _call(comp, "is_active", None), "allow_scalability": _call(comp, "get_allow_scalability", _safe(comp, "allow_scalability")),
                "visible": _call(comp, "is_visible", None), "hidden_in_game": _safe(comp, "hidden_in_game"),
                "owner_hidden": _safe(actor, "hidden"), "owner_hidden_editor": _call(actor, "is_hidden_ed", None),
                "bound_tracks": bound, "has_lifecycle_track": bool(lifecycle),
                "has_lifecycle_trigger_at_plus5": any(not _lifecycle_off_at(t, s2_plus5_frame) for t in root_lifecycle),
                "has_distance_cull": any(r.get("cull_by_distance") is True for r in culls),
            })
    components.sort(key=lambda row: (row["distance_to_shrine_cm"], row["component"]))
    streaming = _streaming(world)
    result = {
        "job": 130, "run": args["run"], "mode": args["mode"], "sequence_authority": S2_SEQUENCE,
        "anchor": anchor, "anchor_owners": anchor_owners, "radius_cm": radius,
        "s2_plus5_local_frame": s2_plus5_frame,
        "components": components, "streaming": streaming,
        "sequences_scanned": seq_info["sequences"], "level_visibility_tracks": seq_info["level_visibility_tracks"],
        "all_niagara_bindings": seq_info["niagara_bindings"],
        "ranked_causes": rank_causes(components, streaming, s2_plus5_frame), "dirty_census": _census(),
    }
    result["probe_sha256"] = _hash_json(review_payload(result))
    return result


def _find_binding(sequence, component, world):
    target = _path(component)
    for binding in sequence.get_bindings():
        for obj in _call(sequence, "locate_bound_objects", [], binding, world) or []:
            if _path(obj) == target:
                return binding, False
    before = {_guid(b.get_id()) for b in sequence.get_bindings()}
    binding = sequence.add_possessable(component)
    after = {_guid(b.get_id()) for b in sequence.get_bindings()}
    created = _guid(binding.get_id()) not in before and len(after - before) == 1
    if not created:
        raise Stop("ADD_POSSESSABLE_REUSED_UNRESOLVED_BINDING|component=%s" % target)
    return binding, True


def _find_component(path):
    u = _ue()
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        for comp in _call(actor, "get_components_by_class", [], u.NiagaraComponent) or []:
            if _path(comp) == path:
                return comp
    return None


def build_fix_plan(args, probe):
    targets = sorted(set(args.get("target_component_paths") or []))
    if not targets:
        return {"status": "NEEDS_REVIEWED_TARGETS", "candidates": [row["component"] for row in probe["components"]]}
    expected = str(args.get("reviewed_probe_sha256") or "")
    if expected != probe["probe_sha256"]:
        raise Stop("PROBE_HASH_MISMATCH|expected=%s|fresh=%s" % (expected, probe["probe_sha256"]))
    available = {row["component"]: row for row in probe["components"]}
    missing = [path for path in targets if path not in available]
    if missing:
        raise Stop("TARGETS_NOT_IN_FRESH_PROBE|%r" % missing)
    existing = [path for path in targets if available[path]["has_lifecycle_track"]]
    if existing:
        raise Stop("TARGET_ALREADY_HAS_LIFECYCLE_TRACK|%r" % existing)
    return {"status": "READY", "sequence_to_save": S2_SEQUENCE, "maps_to_save": [],
            "targets": targets, "section": "full S2 playback", "start": "ACTIVATE",
            "evaluate": "ACTIVATE_IF_INACTIVE", "end": "DEACTIVATE",
            "allow_scalability": bool(args.get("allow_scalability", False))}


def _configure_lifecycle(section, start, end, allow_scalability):
    u = _ue()
    section.set_range(start, end)
    section.set_section_start_behavior(u.NiagaraSystemSpawnSectionStartBehavior.ACTIVATE)
    section.set_section_evaluate_behavior(u.NiagaraSystemSpawnSectionEvaluateBehavior.ACTIVATE_IF_INACTIVE)
    section.set_section_end_behavior(u.NiagaraSystemSpawnSectionEndBehavior.DEACTIVATE)
    section.set_allow_scalability(bool(allow_scalability))


def _verify_owned(sequence, owned):
    by_guid = {_guid(b.get_id()): b for b in sequence.get_bindings()}
    for row in owned:
        binding = by_guid.get(row["binding_guid"])
        if binding is None:
            raise Stop("READBACK_BINDING_MISSING|%s" % row["binding_guid"])
        matches = []
        for track in binding.get_tracks():
            if track.get_class().get_name() != "MovieSceneNiagaraSystemTrack":
                continue
            for section in track.get_sections():
                if (_section_range(section) == row["range"] and
                        _enum(section.get_section_start_behavior()) == "ACTIVATE" and
                        _enum(section.get_section_evaluate_behavior()) == "ACTIVATE_IF_INACTIVE" and
                        _enum(section.get_section_end_behavior()) == "DEACTIVATE"):
                    matches.append(track)
        if len(matches) != 1:
            raise Stop("READBACK_OWNED_TRACK_COUNT|guid=%s|count=%d" % (row["binding_guid"], len(matches)))


def _backup(run, prefix="PreJob130S2ShrineFire"):
    source = _asset_file(S2_SEQUENCE)
    if not os.path.isfile(source):
        raise Stop("SEQUENCE_FILE_MISSING|%s" % source)
    directory = os.path.join(_ue().Paths.convert_relative_path_to_full(_ue().Paths.project_dir()),
                             "Backups", "%s-%s" % (prefix, run))
    if os.path.exists(directory):
        raise Stop("BACKUP_EXISTS|%s" % directory)
    os.makedirs(directory)
    dest = os.path.join(directory, os.path.basename(source))
    shutil.copy2(source, dest)
    digest = hashlib.sha256(open(dest, "rb").read()).hexdigest()
    _write_json(os.path.join(directory, "manifest.json"), {"source": source, "copy": dest, "sha256": digest})
    return {"directory": directory, "copy": dest, "sha256": digest}


def _apply(args, probe):
    if os.path.exists(_record_path()):
        raise Stop("ACTIVE_RECORD_EXISTS")
    plan = build_fix_plan(args, probe)
    if plan["status"] != "READY":
        raise Stop("NO_TARGET_COMPONENT_PATHS|copy exact component paths from reviewed PROBE")
    targets = plan["targets"]
    expected = str(args.get("reviewed_probe_sha256") or "")
    backup = _backup(args["run"])
    u = _ue()
    sequence = u.load_asset(S2_SEQUENCE)
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    start, end = int(sequence.get_playback_start()), int(sequence.get_playback_end())
    owned = []
    for path in targets:
        comp = _find_component(path)
        if comp is None:
            raise Stop("TARGET_COMPONENT_DISAPPEARED|%s" % path)
        binding, created = _find_binding(sequence, comp, world)
        existing = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieSceneNiagaraSystemTrack"]
        if existing:
            raise Stop("LIFECYCLE_TRACK_ALREADY_EXISTS|component=%s|count=%d" % (path, len(existing)))
        track = binding.add_track(u.MovieSceneNiagaraSystemTrack)
        section = track.add_section()
        _configure_lifecycle(section, start, end, args.get("allow_scalability", False))
        owned.append({"component": path, "binding_guid": _guid(binding.get_id()), "binding_created": created,
                      "range": [start, end], "allow_scalability": bool(args.get("allow_scalability", False))})
    record = {"job": 130, "apply_run": args["run"], "sequence": S2_SEQUENCE, "backup": backup,
              "reviewed_probe_sha256": expected, "owned": owned, "state": "prepared"}
    _write_json(_record_path(), record)
    dirty = _census()
    if dirty != {"content": [S2_SEQUENCE], "maps": []}:
        raise Stop("EXACT_DIRTY_CENSUS_REFUSED|got=%r|NOTHING_SAVED; Don't-Save restart" % dirty)
    _verify_owned(sequence, owned)
    if not u.EditorAssetLibrary.save_asset(S2_SEQUENCE, only_if_is_dirty=False):
        raise Stop("SAVE_FAILED|%s" % S2_SEQUENCE)
    if _census() != {"content": [], "maps": []}:
        raise Stop("POST_SAVE_DIRTY|%r" % _census())
    _verify_owned(u.load_asset(S2_SEQUENCE), owned)
    record["state"] = "applied"
    record["saved_readback"] = True
    _write_json(_record_path(), record)
    return record


def _revert(args):
    if not os.path.isfile(_record_path()):
        raise Stop("NO_ACTIVE_RECORD")
    with open(_record_path(), encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("state") != "applied" or record.get("sequence") != S2_SEQUENCE:
        raise Stop("RECORD_STATE_OR_SCOPE")
    u = _ue()
    sequence = u.load_asset(S2_SEQUENCE)
    revert_backup = _backup(args["run"], "PreJob130S2ShrineFireRevert")
    by_guid = {_guid(b.get_id()): b for b in sequence.get_bindings()}
    for row in record["owned"]:
        binding = by_guid.get(row["binding_guid"])
        if binding is None:
            raise Stop("REVERT_BINDING_MISSING|%s" % row["binding_guid"])
        matches = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieSceneNiagaraSystemTrack"
                   and any(_section_range(s) == row["range"] for s in t.get_sections())]
        if len(matches) != 1:
            raise Stop("REVERT_TRACK_COUNT|guid=%s|count=%d" % (row["binding_guid"], len(matches)))
        binding.remove_track(matches[0])
        if row["binding_created"]:
            sequence.remove_possessable(binding.get_id())
            remaining = {_guid(b.get_id()) for b in sequence.get_bindings()}
            if row["binding_guid"] in remaining:
                raise Stop("REVERT_REMOVE_POSSESSABLE_FAILED|%s" % row["binding_guid"])
    dirty = _census()
    if dirty != {"content": [S2_SEQUENCE], "maps": []}:
        raise Stop("EXACT_DIRTY_CENSUS_REFUSED|got=%r|NOTHING_SAVED; Don't-Save restart" % dirty)
    if not u.EditorAssetLibrary.save_asset(S2_SEQUENCE, only_if_is_dirty=False):
        raise Stop("REVERT_SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        raise Stop("REVERT_POST_SAVE_DIRTY|%r" % _census())
    archive = _record_path() + ".reverted-" + args["run"]
    os.rename(_record_path(), archive)
    return {"reverted": len(record["owned"]), "record_archive": archive,
            "apply_backup_retained": record["backup"], "revert_backup": revert_backup}


def run(args):
    mode = str(args.get("mode", "")).upper()
    if mode not in CONFIRMS:
        raise Stop("MODE|PROBE|DRY|APPLY|REVERT")
    if args.get("confirm") != CONFIRMS[mode]:
        raise Stop("CONFIRM|expected=%s" % CONFIRMS[mode])
    if not args.get("run") or not str(args["run"]).startswith("JOB130-"):
        raise Stop("RUN_ID_MUST_START_JOB130-")
    if _census() != {"content": [], "maps": []}:
        raise Stop("DIRTY_AT_START|%r" % _census())
    if mode == "REVERT":
        return {"mode": mode, "run": args["run"], "result": _revert(args)}
    probe = collect_probe(args)
    if probe["dirty_census"] != {"content": [], "maps": []} or _census() != {"content": [], "maps": []}:
        raise Stop("READ_ONLY_PROBE_DIRTIED_PACKAGES|before clean|after=%r" % _census())
    path = os.path.join(_here(), "job130_probe_%s.json" % args["run"])
    _write_json(path, probe)
    if mode in ("PROBE", "DRY"):
        result = {"mode": mode, "run": args["run"], "probe": path, "probe_sha256": probe["probe_sha256"],
                  "components": len(probe["components"]), "ranked_causes": probe["ranked_causes"]}
        if mode == "DRY":
            result["fix_plan"] = build_fix_plan(args, probe)
        return result
    return {"mode": mode, "run": args["run"], "probe": path, "result": _apply(args, probe)}


def main():
    args_path = os.path.join(_here(), "job130_args.json")
    with open(args_path, encoding="utf-8") as handle:
        args = json.load(handle)
    try:
        result = run(args)
        _write_json(os.path.join(_here(), "job130_result_%s.json" % args["run"]), result)
        _ue().log("JOB130_%s_OK|run=%s|%s" % (args["mode"], args["run"], json.dumps(result, sort_keys=True, default=str)))
    except Exception as exc:  # noqa: BLE001
        _ue().log_error("JOB130_FAILED|run=%s|mode=%s|%r" % (args.get("run"), args.get("mode"), exc))


if __name__ == "__main__":
    main()
