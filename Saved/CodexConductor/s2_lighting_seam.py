"""P43 S2 lighting seam/dark-shot infrastructure (offline-authored).

PROBE is read-only.  It lists every P02 Show-owned light at the terminal side
and every bound S2 light/post-process/fog value at the first two seconds and at
each active S2 shot.  DRY plans only explicit args adjustments.  APPLY/REVERT
own only newly-created P43 float tracks on LS_DevScene_02, with record, backup,
exact census, named save, reload/read-back and run-id markers.

The tool never claims a rendered match: PROBE/DRY are infrastructure for Gary's
review.  Visibility channels are interpreted by the UE 5.8 project rule:
AActor::bHidden track ("bHidden","bHidden"), channel True means SHOWN.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None

SEQ_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LEVEL_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TRACK_PREFIX = "P43 S2 Lighting"
RECORD_NAME = "s2_lighting_seam_record.json"
ARGS_NAME = "s2_lighting_seam_args.json"
MODES = ("PROBE", "DRY", "APPLY", "REVERT")
FLOAT_TOL = 1.0e-4

DEFAULTS = {
    "mode": "PROBE", "confirm": "PROBE P43S2LIGHT", "expected_probe_digest": "",
    "boundary_window_s": 2.0, "sample_step_frames": 1,
    # Each explicit row: binding, property (Intensity/AutoExposureBias/FogDensity),
    # factor, offset, start_frame and end_frame.  No wildcard selectors.
    "adjustments": [],
}


class P43Error(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise P43Error(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def validate_args(raw):
    require(isinstance(raw, dict), "ARGS_NOT_OBJECT")
    require(not (set(raw) - set(DEFAULTS)), "ARGS_UNKNOWN|%s" % sorted(set(raw) - set(DEFAULTS)))
    out = copy.deepcopy(DEFAULTS); out.update(copy.deepcopy(raw))
    out["mode"] = str(out["mode"]).upper()
    require(out["mode"] in MODES, "MODE")
    require(out["confirm"] == "%s P43S2LIGHT" % out["mode"], "CONFIRM")
    require(float(out["boundary_window_s"]) > 0.0, "BOUNDARY_WINDOW")
    require(isinstance(out["sample_step_frames"], int) and out["sample_step_frames"] >= 1, "SAMPLE_STEP")
    require(isinstance(out["adjustments"], list), "ADJUSTMENTS")
    cleaned = []
    for index, row in enumerate(out["adjustments"]):
        require(isinstance(row, dict) and set(row) == {"binding", "property", "factor", "offset",
                                                     "start_frame", "end_frame"},
                "ADJUSTMENT_KEYS|%d" % index)
        prop = str(row["property"])
        require(prop in ("Intensity", "AutoExposureBias", "FogDensity"), "ADJUSTMENT_PROPERTY|" + prop)
        item = {"binding": str(row["binding"]).strip(), "property": prop,
                "factor": float(row["factor"]), "offset": float(row["offset"]),
                "start_frame": int(row["start_frame"]), "end_frame": int(row["end_frame"])}
        require(item["binding"] and item["end_frame"] > item["start_frame"] >= 0, "ADJUSTMENT_RANGE|%d" % index)
        require(0.0 <= item["factor"] <= 8.0 and -10.0 <= item["offset"] <= 10.0,
                "ADJUSTMENT_FACTOR|%d" % index)
        cleaned.append(item)
    out["adjustments"] = cleaned
    if out["mode"] == "APPLY":
        require(len(str(out["expected_probe_digest"])) == 64, "EXPECTED_PROBE_DIGEST")
    return out


def aggregate(rows):
    lights = [r for r in rows if r.get("kind") == "light"]
    fog = [r for r in rows if r.get("kind") in ("height_fog", "local_fog")]
    pp = [r for r in rows if r.get("kind") == "post_process"]
    return {"light_count": len(lights), "visible_light_count": sum(bool(r.get("visible")) for r in lights),
            "visible_intensity_sum": sum(float(r.get("intensity") or 0.0) for r in lights if r.get("visible")),
            "shadow_casting_count": sum(bool(r.get("cast_shadows")) for r in lights),
            "exposure_bias_values": sorted(float(r["exposure_bias"]) for r in pp if r.get("exposure_bias") is not None),
            "fog_density_values": sorted(float(r["fog_density"]) for r in fog if r.get("fog_density") is not None)}


def analyse_probe(p02_rows, samples, negative_frames=()):
    require(samples, "NO_S2_SAMPLES")
    p02 = aggregate(p02_rows)
    ordered = sorted(samples, key=lambda row: (row["frame"], row.get("shot", "")))
    for sample in ordered:
        sample["aggregate"] = aggregate(sample["rows"])
    first = ordered[0]["aggregate"]
    keys = ("light_count", "visible_light_count", "visible_intensity_sum", "shadow_casting_count")
    delta = {key: first[key] - p02[key] for key in keys}
    p02_window = [{"frame": int(frame), "rows": copy.deepcopy(p02_rows), "aggregate": copy.deepcopy(p02),
                   "source": "Show terminal state repeated; Passage runtime drama is not evaluated offline"}
                  for frame in sorted(negative_frames)]
    return {"p02_terminal": {"rows": p02_rows, "aggregate": p02}, "p02_window": p02_window,
            "s2_samples": ordered,
            "seam_delta": delta,
            "seam_label_overlap": sorted(set(r["label"] for r in p02_rows) &
                                         set(r["label"] for r in ordered[0]["rows"])),
            "shot_summaries": [{"shot": row.get("shot"), "frame": row["frame"],
                                 "aggregate": row["aggregate"]} for row in ordered if row.get("shot_sample")],
            "proof_boundary": "P02 is serialized Show terminal state; S2 is serialized property/channel evaluation; Passage runtime drama and rendered acceptance are not measured"}


def build_adjustment_plan(probe, args, baselines):
    rows = []
    for spec in args["adjustments"]:
        key = (spec["binding"], spec["property"])
        require(key in baselines, "ADJUSTMENT_TARGET_MISSING|%s|%s" % key)
        base = float(baselines[key])
        target = base * spec["factor"] + spec["offset"]
        require(target >= 0.0 or spec["property"] == "AutoExposureBias", "ADJUSTMENT_NEGATIVE|%s" % (key,))
        rows.append(dict(spec, baseline=base, target=target,
                         display="%s | %s | %s" % (TRACK_PREFIX, spec["binding"], spec["property"]),
                         keys=[[spec["start_frame"], target], [spec["end_frame"] - 1, target]]))
    return {"probe_digest": digest(probe), "adjustments": rows, "count": len(rows),
            "smallest_change_rule": "only exact args bindings/properties; no wildcard or automatic creative choice"}


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, default=str); handle.flush(); os.fsync(handle.fileno())


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _world(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE")
    world = editor.get_editor_world()
    require(world and world.get_path_name().split(".")[0] == LEVEL_PATH, "WRONG_WORLD")
    require(_census() == {"content": [], "maps": []}, "DIRTY_PRE|%s" % _census())
    return world


def _eval(seq, channel, frame, label):
    values = list(channel.evaluate_keys(seq.make_range(int(frame), 1), seq.get_display_rate()))
    require(len(values) == 1, "EVALUATE_COUNT|%s|frame=%d|got=%d" % (label, frame, len(values)))
    return values[0]


def _track_prop(track):
    try:
        return str(track.get_property_name()), str(track.get_property_path())
    except Exception:
        return "", ""


def _binding_value(seq, binding, prop, frame, fallback):
    tracks = [t for t in binding.get_tracks() if _track_prop(t)[0] == prop]
    if not tracks:
        return fallback
    require(len(tracks) == 1, "PROPERTY_TRACK_COUNT|%s|%s|%d" % (binding.get_display_name(), prop, len(tracks)))
    sections = [s for s in tracks[0].get_sections() if s.is_active() and
                (not s.has_start_frame() or s.get_start_frame() <= frame) and
                (not s.has_end_frame() or frame < s.get_end_frame())]
    if not sections:
        return fallback
    require(len(sections) == 1, "PROPERTY_SECTION_OVERLAP|%s|%s" % (binding.get_display_name(), prop))
    channels = list(sections[0].get_all_channels()); require(len(channels) == 1, "PROPERTY_CHANNEL_COUNT")
    return _eval(seq, channels[0], frame, str(binding.get_display_name()))


def _row_for_object(seq, binding, obj, frame):
    name = str(binding.get_display_name())
    cls = obj.get_class().get_name()
    actor = obj.get_owner() if hasattr(obj, "get_owner") else obj
    visible = True
    if hasattr(actor, "is_hidden_ed"):
        try:
            visible = not bool(actor.is_hidden_ed())
        except Exception:
            visible = True
    # Project rule: channel stores VISIBLE despite binding to bHidden.
    visible = bool(_binding_value(seq, binding, "bHidden", frame, visible))
    # Some sequences possess the actor only; include its component state rather
    # than silently omitting that light/fog from "every".
    if "LightComponent" not in cls and hasattr(actor, "get_component_by_class"):
        component = actor.get_component_by_class(unreal.LightComponentBase)
        if component is not None:
            obj, cls = component, component.get_class().get_name()
    if "LightComponent" in cls:
        base = float(obj.get_editor_property("intensity"))
        return {"label": name, "object": str(obj.get_path_name()), "kind": "light", "visible": visible,
                "intensity": float(_binding_value(seq, binding, "Intensity", frame, base)),
                "cast_shadows": bool(obj.get_editor_property("cast_shadows")),
                "cast_volumetric_shadow": bool(obj.get_editor_property("cast_volumetric_shadow"))}
    if "PostProcess" in cls:
        settings = obj.get_editor_property("settings")
        base = float(settings.get_editor_property("auto_exposure_bias"))
        return {"label": name, "object": str(obj.get_path_name()), "kind": "post_process", "visible": visible,
                "exposure_bias": float(_binding_value(seq, binding, "AutoExposureBias", frame, base))}
    if "ExponentialHeightFogComponent" not in cls and hasattr(actor, "get_component_by_class"):
        component = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
        if component is not None:
            obj, cls = component, component.get_class().get_name()
    if "ExponentialHeightFogComponent" in cls:
        base = float(obj.get_editor_property("fog_density"))
        return {"label": name, "object": str(obj.get_path_name()), "kind": "height_fog", "visible": visible,
                "fog_density": float(_binding_value(seq, binding, "FogDensity", frame, base))}
    if "LocalFogVolume" in cls:
        radial = float(obj.get_editor_property("radial_fog_extinction"))
        height = float(obj.get_editor_property("height_fog_extinction"))
        return {"label": name, "object": str(obj.get_path_name()), "kind": "local_fog", "visible": visible,
                "fog_density": radial + height, "radial_fog_extinction": radial, "height_fog_extinction": height}
    return None


def _shot_points(seq, window_frames, step):
    points = [(f, "S2 boundary %+d" % f, False) for f in range(0, window_frames + 1, step)]
    for track in seq.get_tracks():
        if track.get_class().get_name() not in ("MovieSceneCinematicShotTrack", "MovieSceneSubTrack"):
            continue
        for index, section in enumerate(track.get_sections(), 1):
            if not section.is_active() or not section.has_start_frame() or not section.has_end_frame():
                continue
            a, b = int(section.get_start_frame()), int(section.get_end_frame())
            label = "%s/%02d" % (track.get_display_name(), index)
            for frame in sorted({a, (a + b - 1) // 2, b - 1}):
                points.append((frame, str(label), True))
    return sorted(set(points), key=lambda row: (row[0], row[1]))


def _collect_s2(seq, world, args):
    fps = seq.get_display_rate().numerator / float(seq.get_display_rate().denominator)
    bindings = list(seq.get_bindings())
    samples = []
    baselines = {}
    for frame, shot, shot_sample in _shot_points(seq, int(round(args["boundary_window_s"] * fps)),
                                                  args["sample_step_frames"]):
        rows = []
        for binding in bindings:
            objects = list(seq.locate_bound_objects(binding, world))
            for obj in objects:
                row = _row_for_object(seq, binding, obj, frame)
                if row is not None:
                    rows.append(row)
                    for prop, field in (("Intensity", "intensity"), ("AutoExposureBias", "exposure_bias"),
                                        ("FogDensity", "fog_density")):
                        if field in row and row[field] is not None:
                            baselines.setdefault((str(binding.get_display_name()), prop), float(row[field]))
        # A component can be reached by an actor and a child binding.  Report it once.
        unique = {(row["kind"], row["object"]): row for row in rows}
        samples.append({"frame": frame, "seconds": frame / fps, "shot": shot,
                        "shot_sample": shot_sample,
                        "rows": sorted(unique.values(), key=lambda r: (r["kind"], r["label"], r["object"]))})
    return samples, baselines, fps


def _p02_rows(show):
    rows = []
    settings = [row for row in show.get_editor_property("passage_settings")
                if str(row.get_editor_property("label")) == "Passage 2"]
    require(len(settings) == 1, "P02_SETTINGS_COUNT|%d" % len(settings))
    passage_guid = settings[0].get_editor_property("passage_guid")
    guid_text = lambda value: str(value.export_text()).replace("-", "").upper()
    wanted = {guid_text(value) for value in show.get_wing_pair_cue_guids_in_passage(passage_guid)}
    for cue in list(show.get_editor_property("cues")):
        if guid_text(cue.get_editor_property("cue_guid")) not in wanted:
            continue
        pair = cue.get_editor_property("wing_pair")
        for att in list(pair.get_editor_property("attachments")):
            if "LIGHT" not in str(att.get_editor_property("kind")).upper(): continue
            lighting = att.get_editor_property("lighting")
            rows.append({"label": str(att.get_editor_property("label")), "kind": "light",
                         "visible": bool(att.get_editor_property("enabled")),
                         "intensity": float(lighting.get_editor_property("intensity")),
                         "cast_shadows": bool(lighting.get_editor_property("cast_shadows")),
                         "cast_volumetric_shadow": bool(lighting.get_editor_property("cast_volumetric_shadow"))})
    require(rows, "P02_LIGHTS_EMPTY")
    return rows


def _asset_file():
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.join(root, SEQ_PATH[len("/Game/"):].replace("/", os.sep) + ".uasset")


def _backup(run, suffix=""):
    source = _asset_file(); require(os.path.isfile(source), "BACKUP_SOURCE")
    root = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                        "Backups", "PreS2LightingSeam%s-%s" % (suffix, run))
    os.makedirs(root, exist_ok=False); target = os.path.join(root, os.path.basename(source)); shutil.copy2(source, target)
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    require(sha(source) == sha(target), "BACKUP_HASH")
    return {"root": root, "source": source, "backup": target, "sha256": sha(source)}


def _binding(seq, name):
    rows = [b for b in seq.get_bindings() if str(b.get_display_name()) == name]
    require(len(rows) == 1, "BINDING_COUNT|%s|%d" % (name, len(rows))); return rows[0]


def _write_tracks(seq, plan):
    made = []
    for row in plan["adjustments"]:
        binding = _binding(seq, row["binding"])
        conflicts = [t for t in binding.get_tracks() if _track_prop(t)[0] == row["property"]]
        require(not conflicts, "PROPERTY_TRACK_EXISTS|%s|%s" % (row["binding"], row["property"]))
        path = {"Intensity": "Intensity", "FogDensity": "FogDensity",
                "AutoExposureBias": "Settings.AutoExposureBias"}[row["property"]]
        track = binding.add_track(unreal.MovieSceneFloatTrack); track.set_property_name_and_path(
            unreal.Name(row["property"]), path); track.set_display_name(row["display"])
        section = track.add_section(); section.set_range(row["start_frame"], row["end_frame"])
        channel = list(section.get_all_channels())[0]
        for frame, value in row["keys"]:
            channel.add_key(unreal.FrameNumber(frame), float(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                            interpolation=unreal.MovieSceneKeyInterpolation.CONSTANT)
        made.append({"binding": row["binding"], "property": row["property"], "display": row["display"]})
    return sorted(made, key=lambda row: (row["binding"], row["property"]))


def _owned(seq):
    rows = []
    for binding in seq.get_bindings():
        for track in binding.get_tracks():
            if str(track.get_display_name()).startswith(TRACK_PREFIX):
                rows.append({"binding": str(binding.get_display_name()), "property": _track_prop(track)[0],
                             "display": str(track.get_display_name())})
    return sorted(rows, key=lambda r: (r["binding"], r["property"]))


def run(raw=None):
    require(unreal is not None, "UNREAL_REQUIRED")
    args = validate_args(raw or {})
    run_id = datetime.datetime.now().strftime("P43S2-%Y%m%d-%H%M%S")
    world = _world(run_id); seq = unreal.load_asset(SEQ_PATH); show = unreal.load_asset(SHOW_PATH)
    require(seq is not None and show is not None, "ASSET_LOAD")
    record_path = os.path.join(_here(), RECORD_NAME)
    if args["mode"] == "REVERT":
        require(os.path.isfile(record_path), "REVERT_RECORD_MISSING")
        record = json.load(open(record_path, encoding="utf-8")); require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS")
        require(_owned(seq) == record["owned_after"], "REVERT_DRIFT")
        backup = _backup(run_id, "Revert")
        for binding in seq.get_bindings():
            for track in list(binding.get_tracks()):
                if str(track.get_display_name()).startswith(TRACK_PREFIX): binding.remove_track(track)
        require(_census() == {"content": [SEQ_PATH], "maps": []}, "REVERT_CENSUS|%s" % _census())
        require(unreal.EditorAssetLibrary.save_asset(SEQ_PATH, only_if_is_dirty=False), "REVERT_SAVE")
        require(_census() == {"content": [], "maps": []} and not _owned(unreal.load_asset(SEQ_PATH)), "REVERT_READBACK")
        archived = record_path + ".reverted-" + run_id; os.rename(record_path, archived)
        unreal.log("P43_S2_LIGHTING_REVERT_OK|run=%s|saved=%s|readback=1|backup=%s" % (run_id, SEQ_PATH, backup["root"])); return
    samples, baselines, fps = _collect_s2(seq, world, args)
    window = int(round(args["boundary_window_s"] * fps))
    probe = analyse_probe(_p02_rows(show), samples, range(-window, 0, args["sample_step_frames"])); probe.update({"run": run_id, "fps": fps, "census": _census()})
    probe["digest"] = digest({k: v for k, v in probe.items() if k not in ("run", "digest")})
    if args["mode"] == "PROBE":
        require(_census() == {"content": [], "maps": []}, "PROBE_DIRTIED")
        path = os.path.join(_here(), "s2_lighting_probe_%s.json" % run_id); _write(path, probe)
        unreal.log("P43_S2_LIGHTING_PROBE_OK|run=%s|p02_lights=%d|s2_samples=%d|shots=%d|digest=%s|mutated=0|report=%s" %
                   (run_id, probe["p02_terminal"]["aggregate"]["light_count"], len(samples),
                    len(probe["shot_summaries"]), probe["digest"], path)); return
    plan = build_adjustment_plan(probe, args, baselines)
    report = {"run": run_id, "mode": args["mode"], "probe": probe, "plan": plan, "mutated": False}
    path = os.path.join(_here(), "s2_lighting_%s_%s.json" % (args["mode"].lower(), run_id))
    if args["mode"] == "DRY":
        require(_census() == {"content": [], "maps": []}, "DRY_DIRTIED"); _write(path, report)
        unreal.log("P43_S2_LIGHTING_DRY_OK|run=%s|adjustments=%d|probe_digest=%s|mutated=0|report=%s" %
                   (run_id, plan["count"], probe["digest"], path)); return
    require(args["expected_probe_digest"] == probe["digest"], "PROBE_DRIFT")
    require(plan["count"] > 0, "APPLY_EMPTY_PLAN")
    require(not os.path.exists(record_path), "ACTIVE_RECORD")
    backup = _backup(run_id); record = {"run": run_id, "status": "recorded_before_mutation", "plan": plan,
                                        "probe_digest": probe["digest"], "backup": backup, "owned_before": _owned(seq)}
    require(not record["owned_before"], "OWNED_TRACKS_PREEXIST"); _write(record_path, record, exclusive=True)
    made = _write_tracks(seq, plan); record.update(status="mutated", made=made); _write(record_path, record)
    require(_census() == {"content": [SEQ_PATH], "maps": []}, "APPLY_CENSUS|%s" % _census())
    require(unreal.EditorAssetLibrary.save_asset(SEQ_PATH, only_if_is_dirty=False), "APPLY_SAVE")
    seq2 = unreal.load_asset(SEQ_PATH); owned = _owned(seq2); require(owned == made and _census() == {"content": [], "maps": []}, "APPLY_READBACK")
    record.update(status="saved_readback_verified", owned_after=owned, dirty_after=_census()); _write(record_path, record)
    unreal.log("P43_S2_LIGHTING_APPLY_OK|run=%s|adjustments=%d|saved=%s|readback=1|backup=%s|record=%s" %
               (run_id, len(made), SEQ_PATH, backup["root"], record_path))


if unreal is not None and __name__ in ("__main__", "__s2_lighting_seam_runner__"):
    path = os.path.join(_here(), ARGS_NAME)
    run(json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {})
