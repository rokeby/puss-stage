"""Live DRY/APPLY/REVERT transport for a reviewed P06 domino finale plan.

This file is offline-authored and has not been run in Unreal.  The checked-in
production plan is deliberately APPLY-refused because no physical >=2-row
right-side suffix reaches the end.  If a later DRY becomes valid, this tool:

* adopts Chain A read-only and gives B / optional A_RESTYLE separate record dirs;
* delegates only mechanism fields to the already field-scoped topple writer;
* creates a P06-relative child Level Sequence nested under LS_Choreo_Passage_6;
* triggers non-auto-activating Cascade dust with particle keys and keys one audio
  section at B's final impact;
* backs up and records before mutation, saves only named packages, reads back,
  and emits a run-id marker after an exact clean census.

Never opens/scrubs Sequencer, starts/stops PIE, Save Alls, or permanently deletes
assets/records.  REVERT empties and retains the owned sequence asset.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import sys

try:
    import unreal
except ModuleNotFoundError:  # Offline harness/import.
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PLAN_NAME = "domino_finale_plan.json"
ARGS_NAME = "domino_finale_live_args.json"
MARK = "P37_P06_DOMINO"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_REL = "Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset"
WORLD_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
TRACK_NAME = "P06 Domino Finale (P37)"
DUST_PREFIX = "P06 Domino B Dust "
AUDIO_TRACK_NAME = "P06 Domino B Final Slam"


class LiveError(RuntimeError):
    pass


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


C = _load("p37_domino_core_live", os.path.join(HERE, "domino_finale_core.py"))


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _asset_id(value):
    return str(value.get_path_name() if hasattr(value, "get_path_name") else value).split(".")[0]


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(_asset_id(x) for x in lib.get_dirty_content_packages()),
            "maps": sorted(_asset_id(x) for x in lib.get_dirty_map_packages())}


def _require_clean(label):
    got = _census()
    if got != {"content": [], "maps": []}:
        raise LiveError("%s_DIRTY|%s" % (label, json.dumps(got, sort_keys=True)))


def _guard_context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise LiveError("PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    name = str(world.get_outermost().get_name()) if world else None
    if name != WORLD:
        raise LiveError("WRONG_WORLD|%s" % name)
    _require_clean("START")


def _package_file(package):
    rel = package.removeprefix("/Game/")
    ext = ".umap" if package == WORLD else ".uasset"
    return os.path.join(PROJECT, "Content", *rel.split("/")) + ext


def _backup(run, packages, note):
    root = os.path.join(PROJECT, "Backups", "PreP06DominoFinale-%s" % run)
    if os.path.exists(root):
        raise LiveError("BACKUP_EXISTS|%s" % root)
    os.makedirs(root)
    rows = []
    for package in packages:
        source = _package_file(package)
        if not os.path.isfile(source):
            rows.append({"package": package, "source": source, "absent": True})
            continue
        dest = os.path.join(root, os.path.basename(source))
        shutil.copy2(source, dest)
        if _sha(source) != _sha(dest):
            raise LiveError("BACKUP_HASH|%s" % package)
        rows.append({"package": package, "source": source, "backup": dest, "sha256": _sha(source)})
    manifest = {"run": run, "made": datetime.datetime.now().isoformat(timespec="seconds"),
                "note": note, "packages": rows}
    _write(os.path.join(root, "manifest.json"), manifest, exclusive=True)
    return manifest


def _rate(rate):
    return float(rate.numerator) / float(rate.denominator)


def _frame(seconds, fps):
    return int(round(float(seconds) * float(fps)))


def _class_name(value):
    return value.get_class().get_name()


def _owned_subtracks(choreo, sequence_path):
    rows = []
    for track in choreo.get_tracks():
        if _class_name(track) != "MovieSceneSubTrack":
            continue
        sections = list(track.get_sections())
        paths = [_asset_id(s.get_sequence()) for s in sections]
        if str(track.get_display_name()) == TRACK_NAME or sequence_path in paths:
            rows.append((track, paths))
    return rows


def _sequence_state(sequence):
    bindings = []
    for binding in sequence.get_bindings():
        tracks = []
        for track in binding.get_tracks():
            sections = []
            for section in track.get_sections():
                channels = []
                for channel in section.get_all_channels():
                    values = []
                    try:
                        values = [[int(k.get_time().frame_number.value), str(k.get_value())] for k in channel.get_keys()]
                    except Exception:  # noqa: BLE001 - DRY reports unsupported channels via API probe.
                        pass
                    channels.append(values)
                sections.append(channels)
            tracks.append({"class": _class_name(track), "sections": sections})
        bindings.append({"name": str(binding.get_display_name()), "tracks": tracks})
    roots = [{"class": _class_name(t), "name": str(t.get_display_name()), "sections": len(t.get_sections())}
             for t in sequence.get_tracks()]
    return {"bindings": bindings, "root_tracks": roots,
            "playback": [int(sequence.get_playback_start()), int(sequence.get_playback_end())]}


def _api_probe():
    names = ("LevelSequence", "LevelSequenceFactoryNew", "Emitter", "ParticleKey", "MovieSceneSpawnTrack",
             "MovieSceneParticleTrack", "MovieScene3DTransformTrack", "MovieSceneAudioTrack", "MovieSceneSubTrack")
    return {name: hasattr(unreal, name) for name in names}


def _spawn_keys(binding, span, on, off):
    track = binding.add_track(unreal.MovieSceneSpawnTrack)
    section = track.add_section()
    section.set_range(int(span[0]), int(span[1]))
    channel = list(section.get_all_channels())[0]
    channel.set_default(False)
    channel.add_key(unreal.FrameNumber(int(on)), True, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    channel.add_key(unreal.FrameNumber(int(off)), False, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)


def _particle_trigger(binding, span, frame):
    track = binding.add_track(unreal.MovieSceneParticleTrack)
    section = track.add_section()
    section.set_range(int(span[0]), int(span[1]))
    channel = list(section.get_all_channels())[0]
    value = getattr(unreal.ParticleKey, "TRIGGER", None) if hasattr(unreal, "ParticleKey") else None
    if value is None:
        raise LiveError("PARTICLE_TRIGGER_ENUM_UNAVAILABLE")
    channel.add_key(unreal.FrameNumber(int(frame)), value, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)


def _transform(binding, span, location, scale):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(int(span[0]), int(span[1]))
    channels = {}
    for channel in section.get_all_channels():
        name = str(channel.channel_name if hasattr(channel, "channel_name") else channel.get_name())
        channels[name.rsplit("_", 1)[0] if name.rsplit("_", 1)[-1].isdigit() else name] = channel
    values = {"Location.X": location[0], "Location.Y": location[1], "Location.Z": location[2],
              "Rotation.X": 0.0, "Rotation.Y": 0.0, "Rotation.Z": 0.0,
              "Scale.X": scale, "Scale.Y": scale, "Scale.Z": scale}
    for name, value in values.items():
        if name not in channels:
            raise LiveError("TRANSFORM_CHANNEL_MISSING|%s" % name)
        channels[name].set_default(float(value))


def _build_fx(plan, run):
    args = plan["args"]
    choreo = unreal.load_asset(args["choreo"])
    if choreo is None:
        raise LiveError("CHOREO_LOAD")
    if _owned_subtracks(choreo, args["sequence"]):
        raise LiveError("OWNED_SUBTRACK_ALREADY_PRESENT")
    eal = unreal.EditorAssetLibrary
    if eal.does_asset_exist(args["sequence"]):
        sequence = unreal.load_asset(args["sequence"])
        state = _sequence_state(sequence)
        if state["bindings"] or state["root_tracks"]:
            raise LiveError("OWNED_SEQUENCE_NOT_EMPTY")
    else:
        folder, name = args["sequence"].rsplit("/", 1)
        sequence = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
        if sequence is None:
            raise LiveError("SEQUENCE_CREATE")
    sequence.set_tick_resolution(choreo.get_tick_resolution())
    sequence.set_display_rate(choreo.get_display_rate())
    fps = _rate(sequence.get_display_rate())
    end = _frame(float(plan["chain_b"]["timing"]["segment_end_s"]), fps)
    sequence.set_playback_start(0)
    sequence.set_playback_end(end)
    span = [0, end]
    dust_asset = unreal.load_asset(args["dust_asset"])
    sound = unreal.load_asset(args["slam_sound"])
    if dust_asset is None or sound is None:
        raise LiveError("FX_ASSET_LOAD|dust=%s|sound=%s" % (dust_asset is not None, sound is not None))
    for index, dust in enumerate(plan["dust_bursts"]):
        binding = sequence.add_spawnable_from_class(unreal.Emitter)
        binding.set_display_name(DUST_PREFIX + "%02d" % (index + 1))
        emitter = binding.get_object_template()
        emitter.set_editor_property("tags", [unreal.Name("P37_DOMINO_B"), unreal.Name("P37_SETTLE_DUST")])
        component = emitter.get_editor_property("particle_system_component")
        component.set_editor_property("template", dust_asset)
        component.set_editor_property("auto_activate", False)
        component.set_editor_property("cast_shadow", False)
        if bool(component.get_editor_property("auto_activate")) or bool(component.get_editor_property("cast_shadow")):
            raise LiveError("DUST_COMPONENT_UNSAFE|%d" % index)
        on = _frame(dust["impact_s"], fps)
        off = _frame(dust["end_s"], fps)
        _spawn_keys(binding, span, max(0, on - 1), off)
        _particle_trigger(binding, span, on)
        _transform(binding, span, dust["location_cm"], dust["scale"])
    audio = sequence.add_track(unreal.MovieSceneAudioTrack)
    audio.set_display_name(AUDIO_TRACK_NAME)
    section = audio.add_section()
    slam_frame = _frame(plan["chain_b"]["timing"]["final_impact_s"], fps)
    duration = float(plan["slam_sound"]["embedded_wave"]["duration_s"])
    section.set_range(slam_frame, _frame(plan["chain_b"]["timing"]["final_impact_s"] + duration, fps))
    section.set_sound(sound)
    subtrack = choreo.add_track(unreal.MovieSceneSubTrack)
    subtrack.set_display_name(TRACK_NAME)
    sub = subtrack.add_section()
    sub.set_sequence(sequence)
    sub.set_range(0, end)
    return choreo, sequence


def _save_fx(plan, choreo, sequence):
    args = plan["args"]
    expected = sorted([args["choreo"], args["sequence"]])
    census = _census()
    if census != {"content": expected, "maps": []}:
        raise LiveError("FX_DIRTY_SCOPE|got=%s|want=%s" % (json.dumps(census), expected))
    for package in (args["sequence"], args["choreo"]):
        if not unreal.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False):
            raise LiveError("FX_SAVE|%s" % package)
    _require_clean("FX_POST_SAVE")
    return _sequence_state(unreal.load_asset(args["sequence"]))


def _clear_fx(plan):
    args = plan["args"]
    choreo = unreal.load_asset(args["choreo"])
    sequence = unreal.load_asset(args["sequence"])
    owned = _owned_subtracks(choreo, args["sequence"])
    if len(owned) != 1:
        raise LiveError("REVERT_SUBTRACK_COUNT|%d" % len(owned))
    choreo.remove_track(owned[0][0])
    for binding in list(sequence.get_bindings()):
        if not str(binding.get_display_name()).startswith(DUST_PREFIX):
            raise LiveError("FOREIGN_SEQUENCE_BINDING|%s" % binding.get_display_name())
        binding.remove()
    for track in list(sequence.get_tracks()):
        if str(track.get_display_name()) != AUDIO_TRACK_NAME:
            raise LiveError("FOREIGN_SEQUENCE_TRACK|%s" % track.get_display_name())
        sequence.remove_track(track)
    if _sequence_state(sequence)["bindings"] or _sequence_state(sequence)["root_tracks"]:
        raise LiveError("REVERT_SEQUENCE_NOT_EMPTY")
    expected = sorted([args["choreo"], args["sequence"]])
    if _census() != {"content": expected, "maps": []}:
        raise LiveError("REVERT_FX_DIRTY_SCOPE|%s" % json.dumps(_census()))
    for package in (args["sequence"], args["choreo"]):
        if not unreal.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False):
            raise LiveError("REVERT_FX_SAVE|%s" % package)
    _require_clean("REVERT_FX_POST_SAVE")


def _topple_modules():
    folder = os.path.join(PROJECT, "Saved", "CodexFlatV3", "topple")
    top_core = _load("p37_legacy_topple_core", os.path.join(folder, "topple_core.py"))
    apply = _load("p37_legacy_topple_apply", os.path.join(folder, "topple_apply.py"))
    return top_core, apply


def _mechanism_hashes(ops, guids):
    return {guid: hashlib.sha256(ops.read_row(guid)["mech_text"].encode("utf-8")).hexdigest() for guid in guids}


def _legacy_chain_plan(plan):
    """Present Chain B through the field-scoped legacy writer's exact plan contract."""
    return {"parts": ["chain"], "still": [], "keeper": None, "chain": plan["chain_b"],
            "inputs": plan["inputs"], "inputs_hash": plan["inputs_hash"]}


def run_dry(args, plan, run):
    _guard_context()
    probe = _api_probe()
    assets = {path: unreal.EditorAssetLibrary.does_asset_exist(path) for path in
              (plan["args"]["dust_asset"], plan["args"]["slam_sound"], plan["args"]["choreo"])}
    requested_chain = args.get("chain_id", C.CHAIN_B)
    restyle_ready = bool(plan.get("chain_a_restyle_plan"))
    report = {"run": run, "mode": "DRY", "chain_id": requested_chain,
              "plan_apply_ready": (plan["apply_ready"] if requested_chain == C.CHAIN_B else restyle_ready),
              "plan_blockers": plan["blockers"], "api_probe": probe, "assets": assets,
              "census_before": {"content": [], "maps": []}, "census_after": _census(),
              "sequence_exists": unreal.EditorAssetLibrary.does_asset_exist(plan["args"]["sequence"])}
    requested_ready = plan["apply_ready"] if requested_chain == C.CHAIN_B else restyle_ready
    report["apply_ready"] = bool(requested_ready and all(probe.values()) and all(assets.values()) and
                                 report["census_after"] == {"content": [], "maps": []})
    _write(os.path.join(HERE, "domino_finale_dry_%s.json" % run), report)
    unreal.log("%s_DRY_OK|run=%s|apply_ready=%d|plan_blockers=%d|api=%d/%d|census=clean" %
               (MARK, run, int(report["apply_ready"]), len(plan["blockers"]), sum(probe.values()), len(probe)))


def run_apply_restyle(args, plan, run):
    _guard_context()
    subplan = plan.get("chain_a_restyle_plan")
    if not subplan:
        raise LiveError("CHAIN_A_RESTYLE_NOT_OPTED_IN")
    if args.get("confirm") != plan["chain_a_restyle_confirm"]:
        raise LiveError("CONFIRM_MISMATCH|want=%s" % plan["chain_a_restyle_confirm"])
    records = os.path.join(HERE, "records", C.CHAIN_A_RESTYLE)
    os.makedirs(records, exist_ok=True)
    pointer = os.path.join(records, C.active_record_name(C.CHAIN_A_RESTYLE))
    if os.path.exists(pointer) or os.path.exists(os.path.join(records, "topple_originals_ACTIVE.json")):
        raise LiveError("CHAIN_A_RESTYLE_ACTIVE_EXISTS")
    backup = _backup(run, [SHOW, WORLD], "Already-applied Chain A before opt-in curve restyle.")
    overall = os.path.join(HERE, "domino_finale_restyle_a_apply_%s.json" % run)
    record = {"schema": 1, "run": run, "chain_id": C.CHAIN_A_RESTYLE, "status": "prepared",
              "backup": backup, "decided_by": args["decided_by"]}
    _write(overall, record, exclusive=True)
    top_core, legacy = _topple_modules()
    ops = legacy.UnrealOps(top_core)
    legacy.run_apply(ops, top_core, {"override_flags": True, "pose_probe": args.get("pose_probe", True),
                                    "decided_by": args["decided_by"]}, subplan, run, records)
    guids = [r["cue_guid"] for r in subplan["chain"]["rows"]]
    registry = C.registry_entry(C.CHAIN_A_RESTYLE, run, guids, _mechanism_hashes(ops, guids),
                                os.path.join(records, "topple_originals_ACTIVE.json"), overall)
    _write(pointer, registry, exclusive=True)
    record.update(status="applied", after_hashes=registry["after_hashes"])
    _write(overall, record)
    unreal.log("%s_APPLY_OK|run=%s|chain=A_RESTYLE|rows=%d|saved=show,level|census=clean|backup=%s" %
               (MARK, run, len(guids), backup["packages"][0]["backup"]))


def run_apply(args, plan, run):
    _guard_context()
    if not plan.get("apply_ready"):
        raise LiveError("PLAN_NOT_APPLY_READY|%s" % " || ".join(plan.get("blockers") or []))
    if args.get("confirm") != plan["apply_confirm"]:
        raise LiveError("CONFIRM_MISMATCH|want=%s" % plan["apply_confirm"])
    if not str(args.get("cueing_ack") or "").strip():
        raise LiveError("CUEING_ACK_REQUIRED")
    if not args.get("ack_floor_intersection"):
        raise LiveError("FLOOR_INTERSECTION_ACK_REQUIRED")
    records = os.path.join(HERE, "records", C.CHAIN_B)
    os.makedirs(records, exist_ok=True)
    pointer = os.path.join(records, C.active_record_name(C.CHAIN_B))
    if os.path.exists(pointer):
        raise LiveError("CHAIN_B_ACTIVE_RECORD_EXISTS")
    if os.path.exists(os.path.join(records, "topple_originals_ACTIVE.json")):
        raise LiveError("LEGACY_CHAIN_B_ACTIVE_EXISTS")
    packages = [SHOW, WORLD, plan["args"]["choreo"], plan["args"]["sequence"]]
    backup = _backup(run, packages, "Show, level, Choreo, and owned FX sequence before Chain B + dust + slam.")
    overall_path = os.path.join(HERE, "domino_finale_apply_%s.json" % run)
    record = {"schema": 1, "run": run, "chain_id": C.CHAIN_B, "status": "prepared", "backup": backup,
              "plan_token": plan["confirm_token"], "plan_inputs_hash": plan["inputs_hash"],
              "decided_by": args["decided_by"], "cueing_ack": args["cueing_ack"], "fx_after": None}
    _write(overall_path, record, exclusive=True)
    top_core, legacy = _topple_modules()
    ops = legacy.UnrealOps(top_core)
    a_guids = plan["chain_a"]["row_guids"]
    a_before = _mechanism_hashes(ops, a_guids)
    legacy_plan = _legacy_chain_plan(plan)
    unreal.log("%s_B_POST_A_PLAN|run=%s|finale_hash=%s|legacy_hash=%s|rows=%d" % (
        MARK, run, plan["inputs_hash"], legacy_plan["inputs_hash"], len(legacy_plan["chain"]["rows"])))
    b_after = legacy.run_apply(
        ops, top_core, {"override_flags": True, "pose_probe": args.get("pose_probe", True),
                        "decided_by": args["decided_by"]}, legacy_plan, run, records)
    b_guids = [r["cue_guid"] for r in plan["chain_b"]["rows"]]
    if set(b_after) != set(b_guids):
        raise LiveError("CHAIN_B_WRITE_SET_MISMATCH|got=%s|want=%s" % (sorted(b_after), sorted(b_guids)))
    if _mechanism_hashes(ops, a_guids) != a_before:
        raise LiveError("CHAIN_A_CHANGED_BY_B_APPLY")
    unreal.log("%s_B_LEGACY_APPLY_OK|run=%s|written=%d|chain_a_bit_identical=1" % (
        MARK, run, len(b_after)))
    choreo, sequence = _build_fx(plan, run)
    fx_after = _save_fx(plan, choreo, sequence)
    record.update(status="applied", chain_a_hashes=a_before, fx_after=fx_after,
                  legacy_active=os.path.join(records, "topple_originals_ACTIVE.json"),
                  legacy_apply=os.path.join(records, "topple_apply_%s.json" % run))
    _write(overall_path, record)
    registry = C.registry_entry(C.CHAIN_B, run, [r["cue_guid"] for r in plan["chain_b"]["rows"]],
                                _mechanism_hashes(ops, [r["cue_guid"] for r in plan["chain_b"]["rows"]]),
                                record["legacy_active"], overall_path)
    _write(pointer, registry, exclusive=True)
    unreal.log("%s_APPLY_OK|run=%s|chain=B|rows=%d|dust=%d|slam=%.3f|saved=show,level,choreo,sequence|census=clean|backup=%s" %
               (MARK, run, len(plan["chain_b"]["rows"]), len(plan["dust_bursts"]),
                plan["chain_b"]["timing"]["final_impact_s"], backup["packages"][0]["backup"]))


def run_revert(args, plan, run):
    _guard_context()
    records = os.path.join(HERE, "records", C.CHAIN_B)
    pointer = os.path.join(records, C.active_record_name(C.CHAIN_B))
    if not os.path.isfile(pointer):
        raise LiveError("CHAIN_B_ACTIVE_RECORD_MISSING")
    registry = _read(pointer)
    if args.get("confirm") != C.confirm_for("REVERT", C.CHAIN_B, apply_run=registry["apply_run"]):
        raise LiveError("CONFIRM_MISMATCH|want=%s" % C.confirm_for("REVERT", C.CHAIN_B,
                                                                   apply_run=registry["apply_run"]))
    record = _read(registry["fx_record"])
    if record.get("status") != "applied":
        raise LiveError("APPLY_RECORD_NOT_APPLIED")
    _backup(run, [SHOW, WORLD, plan["args"]["choreo"], plan["args"]["sequence"]],
            "Before field-scoped Chain B and owned FX REVERT; owned sequence retained, not deleted.")
    top_core, legacy = _topple_modules()
    ops = legacy.UnrealOps(top_core)
    a_guids = plan["chain_a"]["row_guids"]
    a_pre_revert = _mechanism_hashes(ops, a_guids)
    _clear_fx(plan)
    legacy_active = _read(os.path.join(records, "topple_originals_ACTIVE.json"))
    originals = _read(legacy_active["originals"])
    legacy.run_revert(ops, top_core, args, originals, run, records)
    if _mechanism_hashes(ops, a_guids) != a_pre_revert:
        raise LiveError("CHAIN_A_CHANGED_BY_B_REVERT")
    archived = pointer + ".reverted-" + run
    os.replace(pointer, archived)
    record.update(status="reverted", revert_run=run, registry_archive=archived,
                  chain_a_pre_revert=a_pre_revert, chain_a_post_revert=_mechanism_hashes(ops, a_guids))
    _write(registry["fx_record"], record)
    _require_clean("REVERT_FINAL")
    unreal.log("%s_REVERT_OK|run=%s|chain=B|apply=%s|chain_a_bit_identical=1|sequence_retained=1|census=clean|record=%s" %
               (MARK, run, registry["apply_run"], registry["fx_record"]))


def run_revert_restyle(args, plan, run):
    _guard_context()
    records = os.path.join(HERE, "records", C.CHAIN_A_RESTYLE)
    pointer = os.path.join(records, C.active_record_name(C.CHAIN_A_RESTYLE))
    if not os.path.isfile(pointer):
        raise LiveError("CHAIN_A_RESTYLE_ACTIVE_MISSING")
    registry = _read(pointer)
    want = C.confirm_for("REVERT", C.CHAIN_A_RESTYLE, apply_run=registry["apply_run"])
    if args.get("confirm") != want:
        raise LiveError("CONFIRM_MISMATCH|want=%s" % want)
    _backup(run, [SHOW, WORLD], "Before restoring Chain A to its pre-restyle, already-applied state.")
    top_core, legacy = _topple_modules()
    ops = legacy.UnrealOps(top_core)
    legacy_active = _read(os.path.join(records, "topple_originals_ACTIVE.json"))
    originals = _read(legacy_active["originals"])
    legacy.run_revert(ops, top_core, args, originals, run, records)
    archived = pointer + ".reverted-" + run
    os.replace(pointer, archived)
    _require_clean("A_RESTYLE_REVERT_FINAL")
    unreal.log("%s_REVERT_OK|run=%s|chain=A_RESTYLE|apply=%s|restored=pre-restyle-A|census=clean" %
               (MARK, run, registry["apply_run"]))


def main():
    args = globals().get("P37_DOMINO_ARGS")
    if args is None:
        args = _read(os.path.join(HERE, ARGS_NAME))
    plan = _read(os.path.join(HERE, PLAN_NAME))
    run = str(args.get("run_id") or datetime.datetime.now().strftime("P37DOMINO-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "DRY").upper()
    if mode not in C.MODES:
        raise LiveError("MODE|%s" % mode)
    chain_id = args.get("chain_id", C.CHAIN_B)
    if chain_id not in (C.CHAIN_B, C.CHAIN_A_RESTYLE):
        raise LiveError("CHAIN_ID|%s" % chain_id)
    try:
        if mode == "DRY":
            run_dry(args, plan, run)
        elif mode == "APPLY":
            (run_apply if chain_id == C.CHAIN_B else run_apply_restyle)(args, plan, run)
        else:
            (run_revert if chain_id == C.CHAIN_B else run_revert_restyle)(args, plan, run)
    except Exception as exc:  # noqa: BLE001 - marker then rethrow to fail MCP transport.
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|reason=%s" % (MARK, run, mode, exc))
        raise


if unreal is not None and __name__ != "__p37_domino_import__":
    main()
