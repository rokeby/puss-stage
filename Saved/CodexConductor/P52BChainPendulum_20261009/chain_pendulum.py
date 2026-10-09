"""P52b guarded Unreal tool; offline-delivered and not executed in Unreal here.

This layer deliberately imports P52's sampling, ownership comparison, backup,
dirty census and narrow-save implementation instead of forking those contracts.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))
P52_DIR = os.path.normpath(os.path.join(HERE, "..", "P52PendulumSwing_20261009"))


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _module("p52b_chain_core", os.path.join(HERE, "chain_pendulum_core.py"))
P = _module("p52_shared_tool", os.path.join(P52_DIR, "pendulum_swing.py"))

MARK = "P52B_CHAIN_PENDULUM"
MODES = P.MODES
ACTIVE_RECORD = os.path.join(HERE, "chain_pendulum_ACTIVE.json")


def require(condition, message):
    if not condition:
        raise C.ChainPendulumError(message)


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)


def _schema_path(raw):
    value = str(raw.get("chain_json", "chandelier_chain_v1_fixture.json"))
    path = value if os.path.isabs(value) else os.path.join(HERE, value)
    path = os.path.normpath(path)
    require(os.path.commonpath((HERE, path)) == HERE, "CHAIN_JSON_OUTSIDE_TOOL_DIR")
    require(os.path.isfile(path), "CHAIN_JSON_MISSING|" + path)
    return path


def check_args(raw):
    raw = dict(raw or {})
    mode = str(raw.get("mode", "DRY")).upper()
    require(mode in MODES, "MODE_INVALID|" + mode)
    if mode not in ("DRY", "CHECK"):
        require(raw.get("confirm") == "%s %s" % (mode, MARK),
                "CONFIRM_MISMATCH|want='%s %s'" % (mode, MARK))
    path = _schema_path(raw)
    with open(path, encoding="utf-8") as handle:
        schema_raw = json.load(handle)
    schema = C.validate_schema(schema_raw, raw.get("null_link_mass_ratio", C.DEFAULT_NULL_LINK_MASS_RATIO))
    config = C.check_config(raw, schema)
    link_labels = [str(value).strip() for value in raw.get("link_actor_labels", [])]
    require(len(link_labels) == schema["count"] and all(link_labels),
            "LINK_ACTOR_LABEL_COUNT|want=%d|got=%d" % (schema["count"], len(link_labels)))
    require(len(set(link_labels)) == len(link_labels), "LINK_ACTOR_LABEL_DUPLICATE")
    body_label = str(raw.get("body_actor_label", "")).strip()
    require(body_label and body_label not in link_labels, "BODY_ACTOR_LABEL_INVALID")
    return dict(config, mode=mode, confirm=raw.get("confirm"), chain_json=path,
                schema_raw=schema_raw, schema=schema,
                passage_label=str(raw.get("passage_label", "Passage 1")),
                target_actor_label=body_label, body_actor_label=body_label,
                link_actor_labels=link_labels,
                allow_dirty=sorted(str(value) for value in (raw.get("allow_dirty") or [])))


def _load(args, world):
    ctx = P._load(args, world)
    actors = list(P._u().get_editor_subsystem(P._u().EditorActorSubsystem).get_all_level_actors())
    by_label = {}
    for actor in actors:
        by_label.setdefault(str(actor.get_actor_label()), []).append(actor)
    links = []
    for label in args["link_actor_labels"]:
        require(len(by_label.get(label, [])) == 1, "LINK_ACTOR_COUNT|%s|%d" % (label, len(by_label.get(label, []))))
        links.append(by_label[label][0])
    require(all(P._path(actor) != P._path(ctx["actor"]) for actor in links), "BODY_EQUALS_LINK_ACTOR")
    ctx.update(link_actors=links, body_actor=ctx["actor"])
    return ctx


def _input_facts(args, ctx):
    passage, _unused = P._input_facts(ctx)
    facts = {"passage": passage, "chain_schema": args["schema_raw"],
             "resolved_masses": args["schema"]["mass_inference"],
             "link_actor_labels": args["link_actor_labels"], "body_actor_label": args["body_actor_label"],
             "physics": {key: args[key] for key in ("damping_ratio", "fixed_step_hz", "idle_yaw_degrees",
                         "idle_pitch_degrees", "idle_period_seconds", "idle_phase_cycles", "max_angle_degrees",
                         "decimation_error_degrees", "null_link_mass_ratio", "stability_guard",
                         "max_angular_velocity_degrees_s")}}
    return facts, C.canonical_fingerprint(facts)


def _plan(args, ctx):
    start, end = ctx["range"]
    step_ticks = max(1, int(round(ctx["tick_rate"] / args["fixed_step_hz"])))
    ticks = list(range(start, end + 1, step_ticks))
    if ticks[-1] != end:
        end = ticks[-1]
    positions = []
    for tick in ticks:
        xyz = P._pose(ctx, tick)
        positions.append([(tick - start) / ctx["tick_rate"], xyz[0], xyz[1]])
    simulation = C.simulate_chain(positions, args["schema_raw"], args)

    def absolute(rows):
        return [[start + int(round(row[0] * ctx["tick_rate"])), row[1], row[2]] for row in rows]

    link_keys = [absolute(rows) for rows in simulation["link_keys"]]
    body_keys = absolute(simulation["body_keys"])
    return {"start_tick": start, "end_tick": end, "step_ticks": step_ticks, "sample_count": len(positions),
            "link_keys": link_keys, "body_keys": body_keys,
            "simulation": {"config": simulation["config"], "schema": simulation["schema"],
                           "compatibility_mode": simulation["compatibility_mode"],
                           "stability": simulation["stability"],
                           "max_reconstruction_error_degrees": simulation["max_reconstruction_error_degrees"]},
            "cue_times": P._cue_times(ctx, start)}


def _bindings(ctx, actor):
    target = P._path(actor)
    found = []
    for binding in ctx["master"].get_bindings():
        try:
            if any(P._path(obj) == target for obj in ctx["master"].locate_bound_objects(binding, ctx["world"])):
                found.append(binding)
        except Exception:
            pass
    return found


def _track_name(role):
    return "P52B Chain Pendulum %s [OWNED]" % role


def _owned(binding, role):
    name = _track_name(role)
    return [track for track in binding.get_tracks()
            if track.get_class().get_name() == "MovieScene3DTransformTrack"
            and str(track.get_display_name()) == name]


def _track_snapshot(binding, role):
    tracks = _owned(binding, role)
    if not tracks:
        return None
    require(len(tracks) == 1, "OWNED_TRACK_COUNT|%s|%d" % (role, len(tracks)))
    sections = list(tracks[0].get_sections())
    require(len(sections) == 1, "OWNED_SECTION_COUNT|%s|%d" % (role, len(sections)))
    channels = list(sections[0].get_all_channels())
    require(len(channels) >= 9, "TRANSFORM_CHANNEL_COUNT|%s|%d" % (role, len(channels)))
    pitch = P._channel_rows(channels[4])["keys"]
    yaw = P._channel_rows(channels[5])["keys"]
    require([row[0] for row in pitch] == [row[0] for row in yaw], "OWNED_TIME_MISMATCH|" + role)
    return [[p[0], p[1], y[1]] for p, y in zip(pitch, yaw)]


def _targets(args, ctx, plan):
    targets = []
    for index, actor in enumerate(ctx["link_actors"]):
        targets.append(("link:%d" % index, actor, plan["link_keys"][index]))
    targets.append(("body", ctx["body_actor"], plan["body_keys"]))
    return targets


def _write_tracks(args, ctx, plan, before):
    u = P._u()
    applied = {}
    binding_created = {}
    binding_guids = {}
    for role, actor, keys in _targets(args, ctx, plan):
        bindings = _bindings(ctx, actor)
        require(len(bindings) <= 1, "TARGET_BINDING_COUNT|%s|%d" % (role, len(bindings)))
        created = not bindings
        binding = bindings[0] if bindings else ctx["master"].add_possessable(actor)
        if created:
            binding.set_display_name(actor.get_actor_label())
        require(not _owned(binding, role), "OWNED_TRACK_EXISTS|" + role)
        other = [track for track in binding.get_tracks()
                 if track.get_class().get_name() == "MovieScene3DTransformTrack"]
        require(not other, "NON_OWNED_TRANSFORM_TRACK|%s|%d" % (role, len(other)))
        track = binding.add_track(u.MovieScene3DTransformTrack)
        track.set_display_name(_track_name(role))
        section = track.add_section()
        section.set_range(ctx["master"].get_playback_start(), ctx["master"].get_playback_end())
        channels = list(section.get_all_channels())
        require(len(channels) >= 9, "TRANSFORM_CHANNEL_COUNT|%s|%d" % (role, len(channels)))
        transform = before[role]
        for channel, value in zip(channels[:9], transform["location"] + transform["rotation"] + transform["scale"]):
            channel.set_default(float(value))
        rows = []
        for tick, pitch_delta, yaw_delta in keys:
            pitch = transform["rotation"][1] + pitch_delta
            yaw = transform["rotation"][2] + yaw_delta
            channels[4].add_key(u.FrameNumber(int(tick)), pitch, 0.0, u.MovieSceneTimeUnit.TICK_RESOLUTION,
                                u.MovieSceneKeyInterpolation.LINEAR)
            channels[5].add_key(u.FrameNumber(int(tick)), yaw, 0.0, u.MovieSceneTimeUnit.TICK_RESOLUTION,
                                u.MovieSceneKeyInterpolation.LINEAR)
            rows.append([int(tick), pitch, yaw])
        require(P.C.drift_matches(rows, _track_snapshot(binding, role)), "WRITE_READBACK|" + role)
        applied[role] = rows
        binding_created[role] = created
        binding_guids[role] = P._guid(binding.get_id())
    return applied, binding_created, binding_guids


def _live_tracks(args, ctx):
    live = {}
    targets = [("link:%d" % index, actor) for index, actor in enumerate(ctx["link_actors"])]
    targets.append(("body", ctx["body_actor"]))
    for role, actor in targets:
        bindings = _bindings(ctx, actor)
        require(len(bindings) == 1, "REVERT_BINDING_COUNT|%s|%d" % (role, len(bindings)))
        snapshot = _track_snapshot(bindings[0], role)
        require(snapshot is not None, "OWNED_TRACK_MISSING|" + role)
        live[role] = snapshot
    return live


def _remove_owned(args, ctx, record):
    live = _live_tracks(args, ctx)
    require(C.drift_matches_tracks(record["applied_keys"], live), "OWNED_KEYS_DRIFT")
    targets = [("link:%d" % index, actor) for index, actor in enumerate(ctx["link_actors"])]
    targets.append(("body", ctx["body_actor"]))
    for role, actor in targets:
        binding = _bindings(ctx, actor)[0]
        binding.remove_track(_owned(binding, role)[0])
        if record["binding_created"][role]:
            require(not list(binding.get_tracks()), "CREATED_BINDING_NOT_EMPTY|" + role)
            binding.remove()


def _before(args, ctx):
    values = {"link:%d" % index: P._base_transform(actor) for index, actor in enumerate(ctx["link_actors"])}
    values["body"] = P._base_transform(ctx["body_actor"])
    return values


def _report_path(mode, run):
    return os.path.join(HERE, "chain_pendulum_%s_%s.json" % (mode.lower(), run))


def run(raw):
    run_id = datetime.datetime.now().strftime("P52B-%Y%m%d-%H%M%S")
    try:
        args = check_args(raw)
        world, before_census = P._context(args)
        ctx = _load(args, world)
        facts, fingerprint = _input_facts(args, ctx)
        mode = args["mode"]
        if mode == "CHECK":
            require(os.path.isfile(ACTIVE_RECORD), "NO_ACTIVE_RECORD")
            with open(ACTIVE_RECORD, encoding="utf-8") as handle:
                record = json.load(handle)
            stale = record["input_fingerprint"] != fingerprint
            report = {"run": run_id, "mode": mode, "stale": stale,
                      "recorded": record["input_fingerprint"], "current": fingerprint,
                      "input": facts, "census": before_census}
            path = _report_path(mode, run_id)
            _write(path, report)
            P._u().log("%s_CHECK_OK|run=%s|stale=%d|recorded=%s|current=%s|report=%s" %
                       (MARK, run_id, int(stale), record["input_fingerprint"], fingerprint, path))
            return
        if mode == "DRY":
            plan = _plan(args, ctx)
            require(P._census() == before_census, "DRY_CENSUS_CHANGED")
            report = {"run": run_id, "mode": mode, "args": {k: v for k, v in args.items() if k not in ("schema_raw", "schema")},
                      "input": facts, "input_fingerprint": fingerprint, "plan": plan,
                      "apply_ready": not os.path.exists(ACTIVE_RECORD),
                      "active_record_exists": os.path.exists(ACTIVE_RECORD), "census": before_census}
            path = _report_path(mode, run_id)
            _write(path, report)
            P._u().log("%s_DRY_OK|run=%s|samples=%d|links=%d|body_keys=%d|dt=%.9f|dt_omega=%.6f|error=%.4f|fingerprint=%s|report=%s" %
                       (MARK, run_id, plan["sample_count"], len(plan["link_keys"]), len(plan["body_keys"]),
                        plan["simulation"]["stability"]["dt_seconds"],
                        plan["simulation"]["stability"]["dt_times_omega_max"],
                        plan["simulation"]["max_reconstruction_error_degrees"], fingerprint, path))
            return
        if mode == "APPLY":
            require(not os.path.exists(ACTIVE_RECORD), "ACTIVE_RECORD_EXISTS|revert or rebuild")
            plan = _plan(args, ctx)
            backup = P._backup(run_id, "APPLY P52b owned chain pendulum transform tracks")
            before = _before(args, ctx)
            record = {"version": 1, "status": "WRITING", "apply_run": run_id,
                      "args": {k: v for k, v in args.items() if k not in ("schema_raw", "schema")},
                      "target_actor_paths": {"link:%d" % index: P._path(actor) for index, actor in enumerate(ctx["link_actors"])},
                      "body_actor_path": P._path(ctx["body_actor"]), "input": facts,
                      "input_fingerprint": fingerprint, "plan": plan, "before_transform": before, "backup": backup}
            _write(ACTIVE_RECORD, record, exclusive=True)
            applied, created, guids = _write_tracks(args, ctx, plan, before)
            P._save_narrow()
            record.update(status="APPLIED", applied_keys=applied, binding_created=created, binding_guids=guids)
            _write(ACTIVE_RECORD, record)
            P._u().log("%s_APPLY_OK|run=%s|tracks=%d|fingerprint=%s|backup=%s|record=%s|census=clean" %
                       (MARK, run_id, len(applied), fingerprint, backup["root"], ACTIVE_RECORD))
            return
        require(os.path.isfile(ACTIVE_RECORD), "NO_ACTIVE_RECORD")
        with open(ACTIVE_RECORD, encoding="utf-8") as handle:
            record = json.load(handle)
        require(record.get("status") == "APPLIED", "RECORD_STATUS|%r" % record.get("status"))
        current_paths = {"link:%d" % index: P._path(actor) for index, actor in enumerate(ctx["link_actors"])}
        require(current_paths == record["target_actor_paths"] and P._path(ctx["body_actor"]) == record["body_actor_path"],
                "TARGET_CHANGED")
        backup = P._backup(run_id, mode + " P52b owned chain pendulum transform tracks")
        _remove_owned(args, ctx, record)
        if mode == "REVERT":
            P._save_narrow()
            archive = ACTIVE_RECORD.replace(".json", ".reverted-%s.json" % run_id)
            record.update(status="REVERTED", revert_run=run_id, revert_backup=backup)
            os.replace(ACTIVE_RECORD, archive)
            _write(archive, record)
            P._u().log("%s_REVERT_OK|run=%s|apply=%s|backup=%s|record=%s|census=clean" %
                       (MARK, run_id, record["apply_run"], backup["root"], archive))
            return
        plan = _plan(args, ctx)
        applied, created, guids = _write_tracks(args, ctx, plan, record["before_transform"])
        P._save_narrow()
        history = list(record.get("rebuild_history", []))
        history.append({"run": run_id, "from_fingerprint": record["input_fingerprint"],
                        "to_fingerprint": fingerprint, "backup": backup})
        record.update(args={k: v for k, v in args.items() if k not in ("schema_raw", "schema")},
                      input=facts, input_fingerprint=fingerprint, plan=plan,
                      applied_keys=applied, binding_created=created, binding_guids=guids,
                      rebuild_history=history, last_rebuild_run=run_id)
        _write(ACTIVE_RECORD, record)
        P._u().log("%s_REBUILD_OK|run=%s|tracks=%d|fingerprint=%s|backup=%s|record=%s|census=clean" %
                   (MARK, run_id, len(applied), fingerprint, backup["root"], ACTIVE_RECORD))
    except Exception as error:
        P._u().log_error("%s_STOPPED|run=%s|%s" % (MARK, run_id, error))
        raise


if __name__ == "__p52b_chain_pendulum_runner__":
    run(globals().get("P52B_CHAIN_PENDULUM_ARGS") or {})
