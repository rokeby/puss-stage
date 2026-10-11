"""Guarded Job 185 S1 camera fade: DRY/APPLY/READBACK, LS_DevScene_01 only."""
import datetime
import hashlib
import json
import os
import shutil
import unreal

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
OWNER = "JOB185 S1 Lights Out Fade [OWNED]"
KEYS = [[0, 0.0], [3800, 0.0], [3850, 0.50], [3870, 0.90], [3880, 0.985], [3899, 1.0], [3900, 1.0]]
HERE = os.path.dirname(__file__)
ARGS = os.path.join(HERE, "args.json")
PLAN = os.path.join(HERE, "plan.json")
ACTIVE = os.path.join(HERE, "ACTIVE.json")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def asset_file():
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()).rstrip("/\\")
    return os.path.join(root, "InfinityStage", "Dev", "Sequences", "LS_DevScene_01.uasset")


def backup(run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip("/\\")
    root = os.path.join(project, "Backups", "PreJob185S1Fade-" + run)
    os.makedirs(root, exist_ok=False)
    source = asset_file()
    destination = os.path.join(root, "LS_DevScene_01.uasset")
    shutil.copy2(source, destination)
    require(sha(source) == sha(destination), "BACKUP_HASH")
    return {"root": root, "file": destination, "bytes": os.path.getsize(source), "sha256": sha(source)}


def context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_ACTIVE")
    require(editor.get_editor_world().get_outermost().get_name() == WORLD, "WRONG_WORLD")
    require(census() == {"content": [], "maps": []}, "PRE_DIRTY|" + json.dumps(census(), sort_keys=True))
    seq = unreal.load_asset(SCENE)
    require(seq is not None, "SCENE_LOAD")
    require(int(seq.get_playback_start()) == 0, "PLAYBACK_START|%d" % int(seq.get_playback_start()))
    require(int(seq.get_playback_end()) == 3900, "PLAYBACK_END|%d" % int(seq.get_playback_end()))
    return seq


def fades(seq):
    return [track for track in seq.get_tracks() if track.get_class().get_name() == "MovieSceneFadeTrack"]


def rewrite(channel):
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    for frame, value in KEYS:
        channel.add_key(unreal.FrameNumber(int(frame)), float(value),
                        time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                        interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)


def keys_match(got):
    return (len(got) == len(KEYS) and
            all(int(a[0]) == int(b[0]) and abs(float(a[1]) - float(b[1])) < 0.0001
                for a, b in zip(got, KEYS)))


def state(seq):
    tracks = fades(seq)
    require(len(tracks) == 1, "FADE_TRACK_COUNT|%d" % len(tracks))
    track = tracks[0]
    require(str(track.get_display_name()) == OWNER, "FADE_OWNER|" + str(track.get_display_name()))
    sections = list(track.get_sections())
    require(len(sections) == 1, "FADE_SECTION_COUNT")
    section = sections[0]
    channels = list(section.get_all_channels())
    require(len(channels) == 1, "FADE_CHANNEL_COUNT")
    keys = [[int(key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value), float(key.get_value())]
            for key in channels[0].get_keys()]
    return {"track_index": list(seq.get_tracks()).index(track), "class": track.get_class().get_name(),
            "display": str(track.get_display_name()),
            "range": [int(section.get_start_frame()), int(section.get_end_frame())],
            "completion": str(section.get_completion_mode()), "keys": keys}


def main():
    with open(ARGS, encoding="utf-8") as handle:
        args = json.load(handle)
    mode = str(args["mode"]).upper()
    require(mode in ("DRY", "APPLY", "TUNE", "READBACK"), "MODE")
    seq = context()
    run = "J185S1-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if mode == "DRY":
        require(not fades(seq), "FADE_TRACK_ALREADY_EXISTS")
        require(not os.path.exists(ACTIVE), "ACTIVE_RECORD_EXISTS")
        plan = {"run": run, "mode": "DRY", "package": SCENE, "playback": [0, 3900], "keys": KEYS,
                "intent": "fade begins at 3800, bright corner fire should remain last readable source near 3870, black by 3899",
                "dirty_after": census()}
        with open(PLAN, "w", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2, sort_keys=True)
        unreal.log("JOB185_S1_FADE_DRY_OK|run=%s|keys=%d|fade=3800:3899|package=%s|mutated=0|dirty=0+0" %
                   (run, len(KEYS), SCENE))
        return
    if mode == "APPLY":
        require(args.get("confirm") == "APPLY JOB185 S1 FADE", "CONFIRM")
        require(not fades(seq), "FADE_TRACK_ALREADY_EXISTS")
        require(not os.path.exists(ACTIVE), "ACTIVE_RECORD_EXISTS")
        back = backup(run)
        record = {"status": "prepared", "run": run, "backup": back, "package": SCENE, "keys": KEYS}
        with open(ACTIVE, "x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
        seq.modify()
        track = seq.add_track(unreal.MovieSceneFadeTrack)
        track.set_display_name(OWNER)
        section = track.add_section()
        section.set_range(0, 3901)
        section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
        channels = list(section.get_all_channels())
        require(len(channels) == 1, "NEW_FADE_CHANNEL_COUNT")
        rewrite(channels[0])
        require(census() == {"content": [SCENE], "maps": []}, "DIRTY_SCOPE|" + json.dumps(census(), sort_keys=True))
        before_save = state(seq)
        require(keys_match(before_save["keys"]), "IN_MEMORY_KEYS|got=" + json.dumps(before_save["keys"]))
        require(unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=True), "SAVE_SCENE")
        require(census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY")
        after = state(seq)
        require(after == before_save, "POST_SAVE_DRIFT")
        record.update(status="applied", track=after, dirty_after=census())
        with open(ACTIVE, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
        unreal.log("JOB185_S1_FADE_APPLY_OK|run=%s|keys=%d|fade=3800:3899|black=3899|saved_scene=1|readback=1|dirty=0+0|backup=%s" %
                   (run, len(KEYS), back["root"]))
        return
    require(os.path.isfile(ACTIVE), "ACTIVE_RECORD_MISSING")
    with open(ACTIVE, encoding="utf-8") as handle:
        record = json.load(handle)
    require(record.get("status") == "applied", "RECORD_STATUS")
    got = state(seq)
    require(got == record["track"], "TRACK_DRIFT")
    if mode == "TUNE":
        require(args.get("confirm") == "TUNE JOB185 S1 FADE", "CONFIRM")
        back = backup(run + "-Tune")
        track = fades(seq)[0]
        channel = list(track.get_sections()[0].get_all_channels())[0]
        seq.modify()
        rewrite(channel)
        require(census() == {"content": [SCENE], "maps": []}, "TUNE_DIRTY_SCOPE|" + json.dumps(census(), sort_keys=True))
        before_save = state(seq)
        require(keys_match(before_save["keys"]), "TUNE_IN_MEMORY_KEYS|got=" + json.dumps(before_save["keys"]))
        require(unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=True), "TUNE_SAVE_SCENE")
        require(census() == {"content": [], "maps": []}, "TUNE_POST_SAVE_DIRTY")
        after = state(seq)
        require(after == before_save, "TUNE_POST_SAVE_DRIFT")
        record.setdefault("tune_history", []).append({"run": run, "backup": back, "before": got, "after": after})
        record.update(keys=KEYS, track=after, dirty_after=census())
        with open(ACTIVE, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
        unreal.log("JOB185_S1_FADE_TUNE_OK|run=%s|fire_last=3870|fade3870=0.900|fade3880=0.985|black=3899|saved_scene=1|readback=1|dirty=0+0|backup=%s" %
                   (run, back["root"]))
        return
    require(census() == {"content": [], "maps": []}, "READBACK_DIRTIED")
    unreal.log("JOB185_S1_FADE_READBACK_OK|run=%s|keys=%d|black=3899|range=%d:%d|dirty=0+0" %
               (run, len(got["keys"]), got["range"][0], got["range"][1]))


main()
