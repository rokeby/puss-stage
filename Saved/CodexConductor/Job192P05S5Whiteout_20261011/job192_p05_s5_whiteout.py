"""Job 192 live tool: P05->S5 whiteout and narrowly disabled S5 pre-arrival.

Offline-authored; DRY by default. APPLY/REVERT require exact confirmation,
back up every mutable file, save only Master/current map, and read back state.
Never saves the Show, S5 Scene sequence, Klara levels, or KlaraHookin assets.
"""

from __future__ import annotations

import datetime
import base64
import hashlib
import json
import math
import os
import shutil
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import job192_core as core

ARGS = os.path.join(HERE, "job192_args.json")
SCORE = os.path.join(HERE, "whiteout_score.json")
RECORDS = os.path.join(HERE, "records")
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
S5 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_05"
RISE = "/Game/InfinityStage/RigAtmos/LS_S5_HangarRise"
ARRIVAL_LABEL = "S5 Arrival"
TRACK_NAME = "JOB192 P05->S5 Whiteout [OWNED]"
PATCH_CVAR = "InfinityStage.VideoFallback.WhiteFadeSchema"
ZERO_GUID = "00000000000000000000000000000000"


class Stop(RuntimeError):
    pass


def stop(run, reason):
    unreal.log_error("JOB192_FAILED|run=%s|%s" % (run, reason))
    raise Stop(reason)


def read_json(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_new(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def replace_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_id(obj):
    return obj.get_path_name().split(".", 1)[0] if obj else None


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def parse_guid(text):
    result = unreal.GuidLibrary.parse_string_to_guid(str(text))
    guid, ok = result if isinstance(result, tuple) else (result, True)
    if not ok or guid_text(guid) != str(text).replace("-", "").upper():
        raise Stop("GUID_PARSE|%s" % text)
    return guid


def unwrap(result, count, label):
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        if not result[0]:
            raise Stop(label + " returned false")
        return result[1:]
    if isinstance(result, tuple) and len(result) == count:
        return result
    raise Stop("%s returned unexpected %r" % (label, result))


def rate(value):
    return value.numerator / float(value.denominator)


def dirty_census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def content_file(package, extension):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + extension)


def cue_video_contract():
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    cue = os.path.join(project, "Content", "InfinityStage", "CueSheet", "cue_director.txt")
    registry = os.path.join(project, "Renders", "Fallbacks", "current.json")
    result = {"cue_path": cue, "registry_path": registry, "cue_exists": os.path.isfile(cue),
              "registry_exists": os.path.isfile(registry), "s5_use_video": False,
              "s5_registry": None, "compiled_white_fade_schema": None}
    if result["cue_exists"]:
        for raw in open(cue, encoding="utf-8-sig"):
            clean = raw.split("#", 1)[0].strip()
            if "=" in clean:
                key, value = (part.strip() for part in clean.split("=", 1))
                if key.lower() == "use_video" and value.upper() == "S5":
                    result["s5_use_video"] = True
    if result["registry_exists"]:
        try:
            result["s5_registry"] = read_json(registry).get("scenes", {}).get("S5")
        except Exception as exc:
            result["registry_error"] = repr(exc)
    getter = getattr(unreal.SystemLibrary, "get_console_variable_string_value", None)
    if callable(getter):
        try:
            result["compiled_white_fade_schema"] = str(getter(PATCH_CVAR))
        except Exception as exc:
            result["compiled_white_fade_schema_error"] = repr(exc)
    return result


def owned_tracks(master):
    return [track for track in master.get_tracks()
            if track.get_class().get_name() == "MovieSceneFadeTrack"
            and str(track.get_display_name()) == TRACK_NAME]


def track_state(master):
    tracks = owned_tracks(master)
    if not tracks:
        return None
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        return {"invalid_count": len(tracks)}
    section = list(tracks[0].get_sections())[0]
    channels = list(section.get_all_channels())
    if len(channels) != 1:
        return {"invalid_channels": len(channels)}
    keys = sorted([[int(key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                    round(float(key.get_value()), 6)] for key in channels[0].get_keys()])
    colour = section.get_editor_property("fade_color")
    return {"keys": keys, "range_display": [int(section.get_start_frame()), int(section.get_end_frame())],
            "fade_color": [float(colour.r), float(colour.g), float(colour.b), float(colour.a)],
            "fade_audio": bool(section.get_editor_property("fade_audio"))}


def find_context(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or asset_id(world) != WORLD:
        stop(run, "WRONG_WORLD|%r" % asset_id(world))
    if editor.get_game_world() is not None:
        stop(run, "PIE_OR_SIE_ACTIVE")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        stop(run, "SEQUENCER_IS_OPEN")
    if dirty_census() != {"content": [], "maps": []}:
        stop(run, "DIRTY_BEFORE|%s" % json.dumps(dirty_census(), sort_keys=True))
    show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    if show is None or master is None:
        stop(run, "ASSET_LOAD")
    passages = [row for row in show.get_editor_property("passage_settings")
                if str(row.get_editor_property("label")).strip().lower().replace("passage 05", "passage 5").startswith("passage 5")]
    if len(passages) != 1:
        stop(run, "P05_ROW_COUNT|%d" % len(passages))
    pguid = passages[0].get_editor_property("passage_guid")
    psections = [section for track in master.get_tracks()
                 if track.get_class().get_name() == "MovieSceneInfinityPassageTrack"
                 for section in track.get_sections()
                 if guid_text(section.get_editor_property("passage_guid")) == guid_text(pguid)]
    if len(psections) != 1:
        stop(run, "P05_SECTION_COUNT|%d" % len(psections))
    frame_range = unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, pguid), 2, "P05_RANGE")
    cues = []
    for cue in show.get_editor_property("cues"):
        scene = cue.get_editor_property("scene")
        seq = scene.get_editor_property("sequence") if scene else None
        if asset_id(seq) == S5 and cue.get_editor_property("enabled"):
            cues.append(cue)
    if len(cues) != 1:
        stop(run, "S5_CUE_COUNT|%d" % len(cues))
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    arrivals = [actor for actor in actors if str(actor.get_actor_label()) == ARRIVAL_LABEL]
    if len(arrivals) != 1:
        stop(run, "S5_ARRIVAL_COUNT|%d" % len(arrivals))
    arrival = arrivals[0]
    motion = arrival.get_editor_property("motion_sequence")
    if asset_id(motion) != RISE:
        stop(run, "S5_ARRIVAL_MOTION|%r" % asset_id(motion))
    cue_guid = guid_text(cues[0].get_editor_property("cue_guid"))
    if guid_text(arrival.get_editor_property("scene_cue_guid")) not in (cue_guid, ZERO_GUID):
        stop(run, "S5_ARRIVAL_GUID_NOT_S5")
    tick_rate = rate(master.get_tick_resolution())
    display_rate = rate(master.get_display_rate())
    if abs(tick_rate - rate(show.get_editor_property("tick_resolution"))) > 1.0e-6:
        stop(run, "MASTER_SHOW_TICK_RATE_MISMATCH")
    return {"editor": editor, "world": world, "show": show, "master": master, "arrival": arrival,
            "cue_guid": cue_guid, "arrival_guid": guid_text(arrival.get_editor_property("scene_cue_guid")),
            "passage_guid": guid_text(pguid), "p05_start_tick": int(frame_range[0]),
            "seam_tick": int(frame_range[1]), "tick_rate": tick_rate, "display_rate": display_rate,
            "passage_section_range": [int(psections[0].get_start_frame()), int(psections[0].get_end_frame())],
            "media": cue_video_contract()}


def proposal(ctx, score):
    keys = core.key_plan(score, ctx["seam_tick"], ctx["tick_rate"])
    tpf = ctx["tick_rate"] / ctx["display_rate"]
    display_range = [int(math.floor(keys[0][0] / tpf)), int(math.ceil(keys[-1][0] / tpf)) + 1]
    return {"keys_tick": keys, "section_range_display": display_range,
            "p05_range_tick": [ctx["p05_start_tick"], ctx["seam_tick"]],
            "seam_tick": ctx["seam_tick"], "tick_rate": ctx["tick_rate"],
            "display_rate": ctx["display_rate"], "threshold": score["threshold"],
            "fade_from_white_seconds": score["release_seconds"],
            "presentation": "video" if ctx["media"]["s5_use_video"] else "3d",
            "save_packages": [MASTER, WORLD]}


def snapshot(ctx):
    driven = ctx["arrival"].get_editor_property("driven_actor")
    return {"arrival": {"path": ctx["arrival"].get_path_name(),
                         "scene_cue_guid": guid_text(ctx["arrival"].get_editor_property("scene_cue_guid")),
                         "motion_sequence": asset_id(ctx["arrival"].get_editor_property("motion_sequence")),
                         "motion_binding_guid": guid_text(ctx["arrival"].get_editor_property("motion_binding_guid")),
                         "driven_actor": str(driven.get_actor_label()) if driven else None},
            "fade_track": track_state(ctx["master"]), "media": cue_video_contract(), "dirty": dirty_census()}


def overlapping_fades(master, display_range):
    hits = []
    for track in master.get_tracks():
        if track.get_class().get_name() != "MovieSceneFadeTrack":
            continue
        for section in track.get_sections():
            span = [int(section.get_start_frame()), int(section.get_end_frame())]
            if span[0] < display_range[1] and span[1] > display_range[0]:
                hits.append({"track": str(track.get_display_name()), "range": span})
    return hits


def dry_path(run):
    return os.path.join(RECORDS, "job192_%s_dry.json" % run)


def apply_path(run):
    return os.path.join(RECORDS, "job192_%s_apply.json" % run)


def backup(run, media, force_registry=False):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = os.path.join(project, "Backups", "PreJob192P05S5Whiteout-%s-%s" % (run, stamp))
    os.makedirs(root, exist_ok=False)
    sources = [(MASTER, content_file(MASTER, ".uasset")), (WORLD, content_file(WORLD, ".umap"))]
    if media["s5_use_video"] or force_registry:
        sources.append(("current.json", media["registry_path"]))
    rows = []
    for name, source in sources:
        if not os.path.isfile(source):
            stop(run, "BACKUP_SOURCE_MISSING|%s" % source)
        target = os.path.join(root, os.path.basename(source))
        shutil.copy2(source, target)
        if os.path.getsize(source) != os.path.getsize(target) or sha256(source) != sha256(target):
            stop(run, "BACKUP_VERIFY|%s" % name)
        rows.append({"name": name, "source": source, "backup": target,
                     "bytes": os.path.getsize(target), "sha256": sha256(target)})
    return {"directory": root, "files": rows}


def update_registry(media, seconds):
    path = media["registry_path"]
    with open(path, "rb") as handle:
        original = handle.read()
    document = json.loads(original.decode("utf-8-sig"))
    scene = document.get("scenes", {}).get("S5")
    if not isinstance(scene, dict) or not scene.get("video"):
        raise Stop("S5_REGISTRY_ENTRY_INVALID")
    scene["fade_from_white_seconds"] = float(seconds)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    reread = read_json(path).get("scenes", {}).get("S5", {})
    if float(reread.get("fade_from_white_seconds", -1)) != float(seconds):
        raise Stop("REGISTRY_READBACK")
    return base64.b64encode(original).decode("ascii")


def add_fade(master, plan):
    master.modify()
    track = master.add_track(unreal.MovieSceneFadeTrack)
    track.set_display_name(TRACK_NAME)
    section = track.add_section()
    section.set_range(*plan["section_range_display"])
    section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    section.set_editor_property("fade_color", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    section.set_editor_property("fade_audio", False)
    channels = list(section.get_all_channels())
    if len(channels) != 1:
        raise Stop("FADE_CHANNEL_COUNT|%d" % len(channels))
    for tick, amount in plan["keys_tick"]:
        channels[0].add_key(unreal.FrameNumber(tick), float(amount),
                            time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
                            interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)


def save_named(run):
    census = dirty_census()
    if census != {"content": [MASTER], "maps": [WORLD]}:
        stop(run, "DIRTY_SCOPE|%s" % json.dumps(census, sort_keys=True))
    if not unreal.EditorAssetLibrary.save_asset(MASTER, only_if_is_dirty=True):
        stop(run, "SAVE_MASTER")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "SAVE_LEVEL")
    if dirty_census() != {"content": [], "maps": []}:
        stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(dirty_census(), sort_keys=True))


def run_dry(ctx, args, score, plan):
    before = snapshot(ctx)
    refusals = []
    if before["arrival"]["scene_cue_guid"] == ZERO_GUID:
        refusals.append("S5_ARRIVAL_ALREADY_DISABLED")
    if before["fade_track"] is not None:
        refusals.append("OWNED_FADE_ALREADY_EXISTS")
    for hit in overlapping_fades(ctx["master"], plan["section_range_display"]):
        refusals.append("MASTER_FADE_OVERLAP|%s" % json.dumps(hit, sort_keys=True))
    media = before["media"]
    if not media["cue_exists"]:
        refusals.append("CUE_DIRECTOR_MISSING_CANNOT_DETERMINE_S5_MODE")
    if media["s5_use_video"]:
        if not media["registry_exists"] or not media["s5_registry"]:
            refusals.append("S5_VIDEO_REGISTER_MISSING")
        if media.get("compiled_white_fade_schema") != "1":
            refusals.append("WHITE_FADE_PATCH_NOT_BUILT_OR_CVAR_OVERRIDDEN")
    report = {"schema": 1, "mode": "DRY", "run": args["run"], "args": args,
              "plan": plan, "plan_digest": core.plan_digest(args, score), "before": before,
              "refusals": refusals, "apply_ready": not refusals, "writes": 0}
    write_new(dry_path(args["run"]), report)
    if dirty_census() != {"content": [], "maps": []}:
        stop(args["run"], "DRY_DIRTIED_EDITOR")
    unreal.log("JOB192_DRY_OK|run=%s|apply_ready=%d|refusals=%d|presentation=%s|arrival=%s|seam_tick=%d|keys=%d|digest=%s|record=%s" %
               (args["run"], int(not refusals), len(refusals), plan["presentation"], ARRIVAL_LABEL,
                plan["seam_tick"], len(plan["keys_tick"]), report["plan_digest"], dry_path(args["run"])))
    for refusal in refusals:
        unreal.log_warning("JOB192_REFUSAL|run=%s|%s" % (args["run"], refusal))


def run_apply(ctx, args, score, plan):
    dry = read_json(dry_path(args["run"])) if os.path.isfile(dry_path(args["run"])) else {}
    digest = core.plan_digest(args, score)
    if not dry.get("apply_ready") or dry.get("plan_digest") != digest:
        stop(args["run"], "CURRENT_GREEN_DRY_REQUIRED_WITH_SAME_RUN_AND_SCORE")
    before = snapshot(ctx)
    if before["fade_track"] is not None or before["arrival"]["scene_cue_guid"] != ctx["cue_guid"]:
        stop(args["run"], "STATE_DRIFT_SINCE_DRY")
    if before["media"] != dry.get("before", {}).get("media"):
        stop(args["run"], "MEDIA_CONTRACT_DRIFT_SINCE_DRY")
    back = backup(args["run"], before["media"])
    path = apply_path(args["run"])
    record = {"schema": 1, "status": "PREPARED_BEFORE_MUTATION", "run": args["run"],
              "args": args, "plan": plan, "plan_digest": digest, "before": before,
              "backup": back, "save_packages": [MASTER, WORLD], "registry_original_b64": None}
    write_new(path, record)
    if before["media"]["s5_use_video"]:
        record["registry_original_b64"] = update_registry(before["media"], plan["fade_from_white_seconds"])
        replace_json(path, record)
    ctx["arrival"].modify()
    ctx["arrival"].set_editor_property("scene_cue_guid", parse_guid(ZERO_GUID))
    add_fade(ctx["master"], plan)
    expected = {"keys": [[row[0], round(float(row[1]), 6)] for row in plan["keys_tick"]],
                "range_display": plan["section_range_display"], "fade_color": [1.0, 1.0, 1.0, 1.0],
                "fade_audio": False}
    if track_state(ctx["master"]) != expected or guid_text(ctx["arrival"].get_editor_property("scene_cue_guid")) != ZERO_GUID:
        stop(args["run"], "PRE_SAVE_READBACK|NOTHING_SAVED_DONT_SAVE_RESTART")
    save_named(args["run"])
    after = snapshot(ctx)
    if after["fade_track"] != expected or after["arrival"]["scene_cue_guid"] != ZERO_GUID:
        stop(args["run"], "POST_SAVE_READBACK")
    if plan["presentation"] == "video":
        got = after["media"].get("s5_registry") or {}
        if float(got.get("fade_from_white_seconds", -1)) != plan["fade_from_white_seconds"]:
            stop(args["run"], "POST_SAVE_REGISTRY_READBACK")
    record.update({"status": "APPLIED_AND_READ_BACK", "after": after, "dirty_after": dirty_census()})
    replace_json(path, record)
    unreal.log("JOB192_APPLY_OK|run=%s|presentation=%s|arrival_drive_disabled=1|fade_keys=%d|seam_amount=1|saved=2|readback=1|record=%s|backup=%s" %
               (args["run"], plan["presentation"], len(plan["keys_tick"]), path, back["directory"]))


def run_revert(ctx, args):
    path = args["record"] if os.path.isabs(args["record"]) else os.path.join(HERE, args["record"])
    source = read_json(path)
    if source.get("schema") != 1 or source.get("status") != "APPLIED_AND_READ_BACK":
        stop(args["run"], "INCOMPLETE_APPLY_RECORD")
    current = snapshot(ctx)
    if len(owned_tracks(ctx["master"])) != 1 or current["arrival"]["scene_cue_guid"] != ZERO_GUID:
        stop(args["run"], "APPLIED_STATE_DRIFT")
    original_b64 = source.get("registry_original_b64")
    back = backup(args["run"] + "-Revert", current["media"], force_registry=original_b64 is not None)
    out = os.path.join(RECORDS, "job192_%s_revert.json" % args["run"])
    record = {"schema": 1, "status": "PREPARED_BEFORE_MUTATION", "run": args["run"],
              "source_record": path, "before_revert": current, "backup": back}
    write_new(out, record)
    ctx["master"].modify()
    ctx["master"].remove_track(owned_tracks(ctx["master"])[0])
    ctx["arrival"].modify()
    ctx["arrival"].set_editor_property("scene_cue_guid", parse_guid(source["before"]["arrival"]["scene_cue_guid"]))
    if original_b64 is not None:
        original = base64.b64decode(original_b64.encode("ascii"))
        with open(current["media"]["registry_path"], "wb") as handle:
            handle.write(original)
    if track_state(ctx["master"]) is not None or guid_text(ctx["arrival"].get_editor_property("scene_cue_guid")) != source["before"]["arrival"]["scene_cue_guid"]:
        stop(args["run"], "PRE_SAVE_REVERT_READBACK|NOTHING_SAVED_DONT_SAVE_RESTART")
    save_named(args["run"])
    after = snapshot(ctx)
    if after["fade_track"] is not None or after["arrival"]["scene_cue_guid"] != source["before"]["arrival"]["scene_cue_guid"]:
        stop(args["run"], "POST_SAVE_REVERT_READBACK")
    if original_b64 is not None:
        with open(current["media"]["registry_path"], "rb") as handle:
            if handle.read() != original:
                stop(args["run"], "REGISTRY_REVERT_READBACK")
    record.update({"status": "REVERTED_AND_READ_BACK", "after": after, "dirty_after": dirty_census()})
    replace_json(out, record)
    unreal.log("JOB192_REVERT_OK|run=%s|arrival_drive_restored=1|fade_removed=1|saved=2|readback=1|record=%s|backup=%s" %
               (args["run"], out, back["directory"]))


def main():
    raw = read_json(ARGS)
    try:
        args = core.validate_args(raw)
        score = core.compile_score(read_json(SCORE))
        ctx = find_context(args["run"])
        plan = proposal(ctx, score)
        if args["mode"] == "DRY":
            run_dry(ctx, args, score, plan)
        elif args["mode"] == "APPLY":
            run_apply(ctx, args, score, plan)
        else:
            run_revert(ctx, args)
    except Exception as exc:
        if not isinstance(exc, Stop):
            unreal.log_error("JOB192_FAILED|run=%s|%r" % (raw.get("run", "UNKNOWN"), exc))
        raise


if __name__ == "__main__":
    main()
