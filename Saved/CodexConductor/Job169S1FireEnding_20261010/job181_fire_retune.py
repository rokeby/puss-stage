"""Guarded Job 181 retune of the already-owned Job 169 corner-wing fire."""
import importlib.util
import json
import os

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "job181_fire_retune_args.json")
PLAN = os.path.join(HERE, "job181_fire_retune_plan.json")
RECORD = os.path.join(HERE, "job181_fire_retune_record.json")
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
SHOW_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def _helper():
    path = os.path.join(HERE, "job169_s1_fire_ending.py")
    spec = importlib.util.spec_from_file_location("job181_fire_retune_helpers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_args():
    with open(ARGS, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _bindings(seq, helper):
    rows = {str(binding.get_display_name()): binding for binding in seq.get_spawnables()}
    wanted = (helper.FIRE_NAME, helper.LIGHT_NAME)
    if any(name not in rows for name in wanted):
        raise RuntimeError("OWNED_SPAWNABLE_MISSING|%s" % [name for name in wanted if name not in rows])
    if any(sum(str(binding.get_display_name()) == name for binding in seq.get_spawnables()) != 1 for name in wanted):
        raise RuntimeError("OWNED_SPAWNABLE_NOT_UNIQUE")
    return rows[helper.FIRE_NAME], rows[helper.LIGHT_NAME]


def _state(seq, helper):
    unreal.log("JOB181_FIRE_RETUNE_PROGRESS|state=bindings_begin")
    fire, light = _bindings(seq, helper)
    unreal.log("JOB181_FIRE_RETUNE_PROGRESS|state=bindings_ok")
    tracks = [track for track in fire.get_tracks()
              if track.get_class().get_name() == "MovieScene3DTransformTrack"]
    if len(tracks) != 1 or len(list(tracks[0].get_sections())) != 1:
        raise RuntimeError("FIRE_TRANSFORM_TRACK_SHAPE")
    section = list(tracks[0].get_sections())[0]
    channels = {helper._channel_name(channel): channel for channel in section.get_all_channels()}
    scale = {}
    for axis in "XYZ":
        name = "Scale." + axis
        if name not in channels:
            raise RuntimeError("FIRE_SCALE_CHANNEL_MISSING|%s" % name)
        scale[name] = [{"frame": int(key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                                            .frame_number.value),
                        "value": float(key.get_value())}
                       for key in channels[name].get_keys()]
    template = light.get_object_template()
    component = template.get_editor_property("point_light_component")
    unreal.log("JOB181_FIRE_RETUNE_PROGRESS|state=target_tracks_ok")
    return {"fire_guid": helper._guid(fire.get_id()), "light_guid": helper._guid(light.get_id()),
            "scale": scale, "intensity_lm": float(component.get_editor_property("intensity")),
            "owned": helper._owned_state(seq), "timeline": helper._timeline_state(seq)}


def _assert_expected(state, args):
    expected = float(args["expected_scale"])
    for name, keys in state["scale"].items():
        frames = [int(row["frame"]) for row in keys]
        values = [float(row["value"]) for row in keys]
        if frames != [3570, 3590, 3900] or abs(values[0] - 0.01) > 0.0001 or any(
                abs(value - expected) > 0.0001 for value in values[1:]):
            raise RuntimeError("FIRE_SCALE_DRIFT|%s|frames=%s|values=%s" % (name, frames, values))
    if abs(state["intensity_lm"] - float(args["expected_intensity_lm"])) > 0.001:
        raise RuntimeError("FIRE_INTENSITY_DRIFT|live=%s|expected=%s" %
                           (state["intensity_lm"], args["expected_intensity_lm"]))


def _preflight(helper, mode, args):
    if args.get("confirm") != "%s JOB181 FIRE RETUNE" % mode:
        raise RuntimeError("CONFIRM_MISMATCH")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if helper._census() != {"content": [], "maps": []}:
        raise RuntimeError("DIRTY_AT_START|%s" % helper._census())
    world_path = editor.get_editor_world().get_path_name().split(".", 1)[0]
    if world_path != SHOW_WORLD:
        raise RuntimeError("WRONG_WORLD|%s" % world_path)
    if mode in ("DRY", "APPLY") and os.path.isfile(RECORD):
        raise RuntimeError("APPLIED_RECORD_EXISTS|%s" % RECORD)


def _write(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)


def run(args):
    unreal.log("JOB181_FIRE_RETUNE_PROGRESS|state=helper_begin")
    helper = _helper()
    unreal.log("JOB181_FIRE_RETUNE_PROGRESS|state=helper_ok")
    mode = str(args["mode"]).upper()
    _preflight(helper, mode, args)
    unreal.log("JOB181_FIRE_RETUNE_PROGRESS|state=preflight_ok")
    seq = unreal.load_asset(SCENE)
    unreal.log("JOB181_FIRE_RETUNE_PROGRESS|state=sequence_loaded")
    before = _state(seq, helper)
    unreal.log("JOB181_FIRE_RETUNE_PROGRESS|state=state_ok")
    _assert_expected(before, args)
    plan = {"run": args["run_id"], "scene": SCENE, "before": before,
            "target_scale": float(args["target_scale"]),
            "target_intensity_lm": float(args["target_intensity_lm"]),
            "before_digest": helper.stable_digest(before)}
    if mode == "DRY":
        _write(PLAN, plan)
        unreal.log("JOB181_FIRE_RETUNE_DRY_OK|run=%s|scale=%.3f->%.3f|intensity_lm=%.1f->%.1f|mutated=0|dirty=0+0|plan=%s" %
                   (args["run_id"], args["expected_scale"], args["target_scale"],
                    args["expected_intensity_lm"], args["target_intensity_lm"], PLAN))
        return plan
    if mode != "APPLY":
        raise RuntimeError("MODE_INVALID|%s" % mode)
    with open(PLAN, "r", encoding="utf-8") as handle:
        reviewed = json.load(handle)
    if reviewed.get("before_digest") != plan["before_digest"]:
        raise RuntimeError("CHANGED_SINCE_DRY")
    backup = helper._backup(args["run_id"], "Job181FireRetune")
    transaction = os.path.join(HERE, "job181_fire_retune_transaction_%s.json" % args["run_id"])
    record = dict(plan, applied=False, written_before_mutation=True, backup=backup)
    _write(transaction, record)
    fire, light = _bindings(seq, helper)
    seq.modify()
    track = [row for row in fire.get_tracks() if row.get_class().get_name() == "MovieScene3DTransformTrack"][0]
    channels = {helper._channel_name(channel): channel for channel in list(track.get_sections())[0].get_all_channels()}
    for axis in "XYZ":
        keys = list(channels["Scale." + axis].get_keys())
        keys[1].set_value(float(args["target_scale"]))
        keys[2].set_value(float(args["target_scale"]))
    component = light.get_object_template().get_editor_property("point_light_component")
    component.modify()
    component.set_editor_property("intensity", float(args["target_intensity_lm"]))
    after = _state(seq, helper)
    expected_after = dict(args, expected_scale=args["target_scale"],
                          expected_intensity_lm=args["target_intensity_lm"])
    _assert_expected(after, expected_after)
    if before["timeline"] != after["timeline"]:
        raise RuntimeError("TIMELINE_SCOPE_CHANGED|NOTHING SAVED")
    if helper._census() != {"content": [SCENE], "maps": []}:
        raise RuntimeError("DIRTY_SCOPE|%s|NOTHING SAVED" % helper._census())
    record.update({"after": after, "after_digest": helper.stable_digest(after), "applied": True})
    _write(transaction, record)
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=True):
        raise RuntimeError("SAVE_FAILED|%s" % SCENE)
    if helper._census() != {"content": [], "maps": []}:
        raise RuntimeError("DIRTY_AFTER_SAVE|%s" % helper._census())
    readback = _state(unreal.load_asset(SCENE), helper)
    if readback != after:
        raise RuntimeError("SAVED_READBACK_MISMATCH|restore=%s" % backup["root"])
    record.update({"saved_readback": readback, "saved_readback_digest": helper.stable_digest(readback),
                   "census_after": helper._census()})
    _write(RECORD, record)
    _write(transaction, dict(record, transaction_complete=True))
    unreal.log("JOB181_FIRE_RETUNE_APPLY_OK|run=%s|saved=%s|scale=%.3f|intensity_lm=%.1f|backup=%s|readback=%s|klara_saved=0|levels_saved=0" %
               (args["run_id"], SCENE, args["target_scale"], args["target_intensity_lm"],
                backup["root"], record["saved_readback_digest"][:16]))
    return record


try:
    run(_load_args())
except Exception as exc:
    unreal.log_error("JOB181_FIRE_RETUNE_STOPPED|%r" % exc)
    raise
