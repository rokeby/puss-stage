"""Guarded Job 185 P06 production-sun intensity track APPLY/READBACK."""
import datetime
import hashlib
import json
import os
import shutil
import unreal

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SUN_LABEL = "Infinity Stage - Dusk Sun"
OWNER = "JOB185 P06 Sun Disc [OWNED]"
INTENSITY = 1.5
HERE = os.path.dirname(__file__)
ARGS = os.path.join(HERE, "intensity_args.json")
RECORD = os.path.join(HERE, "intensity_ACTIVE.json")
JOB178 = os.path.join(os.path.dirname(HERE), "Job178P06SunDisc_20261010", "job178b_ACTIVE.json")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def gid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def backup(run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip("/\\")
    source = os.path.join(project, "Content", "InfinityStage", "Dev", "Sequences", "LS_InfinityStage_V1Master.uasset")
    root = os.path.join(project, "Backups", "PreJob185P06SunIntensity-" + run)
    os.makedirs(root, exist_ok=False)
    destination = os.path.join(root, "LS_InfinityStage_V1Master.uasset")
    shutil.copy2(source, destination)
    require(sha(source) == sha(destination), "BACKUP_HASH")
    return {"root": root, "file": destination, "bytes": os.path.getsize(source), "sha256": sha(source)}


def context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_ACTIVE")
    world = editor.get_editor_world()
    require(world.get_outermost().get_name() == WORLD, "WRONG_WORLD")
    actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if str(a.get_actor_label()) == SUN_LABEL]
    require(len(actors) == 1, "SUN_COUNT|%d" % len(actors))
    comp = actors[0].get_component_by_class(unreal.DirectionalLightComponent)
    require(comp is not None, "SUN_COMPONENT")
    require(bool(comp.get_editor_property("atmosphere_sun_light")), "NOT_ATMOSPHERE_SUN")
    seq = unreal.load_asset(MASTER)
    require(seq is not None, "MASTER_LOAD")
    bindings = []
    wanted = str(comp.get_path_name())
    for binding in seq.get_bindings():
        try:
            if any(str(obj.get_path_name()) == wanted for obj in seq.locate_bound_objects(binding, world)):
                bindings.append(binding)
        except Exception:
            pass
    require(len(bindings) == 1, "SUN_COMPONENT_BINDINGS|%d" % len(bindings))
    return seq, bindings[0]


def owned_tracks(binding):
    return [track for track in binding.get_tracks() if str(track.get_display_name()) == OWNER]


def track_state(binding):
    tracks = owned_tracks(binding)
    require(len(tracks) == 1, "OWNED_TRACK_COUNT|%d" % len(tracks))
    track = tracks[0]
    require(str(track.get_property_name()) == "Intensity" and str(track.get_property_path()) == "Intensity", "PROPERTY")
    sections = list(track.get_sections())
    require(len(sections) == 1, "SECTION_COUNT")
    channels = list(sections[0].get_all_channels())
    require(len(channels) == 1, "CHANNEL_COUNT")
    return {"binding": gid(binding.get_id()), "class": track.get_class().get_name(),
            "display": str(track.get_display_name()), "property": [str(track.get_property_name()), str(track.get_property_path())],
            "default": float(channels[0].get_default()), "range": [int(sections[0].get_start_frame()), int(sections[0].get_end_frame())],
            "completion": str(sections[0].get_completion_mode())}


def main():
    with open(ARGS, encoding="utf-8") as handle:
        args = json.load(handle)
    mode = str(args["mode"]).upper()
    require(mode in ("APPLY", "READBACK"), "MODE")
    require(census() == {"content": [], "maps": []}, "PRE_DIRTY|" + json.dumps(census(), sort_keys=True))
    seq, binding = context()
    run = "J185SUN-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if mode == "APPLY":
        require(args.get("confirm") == "APPLY JOB185 P06 SUN INTENSITY", "CONFIRM")
        require(not os.path.exists(RECORD), "ACTIVE_RECORD_EXISTS")
        require(not owned_tracks(binding), "OWNED_TRACK_EXISTS")
        with open(JOB178, encoding="utf-8") as handle:
            source = json.load(handle)
        require(source.get("status") == "applied", "JOB178_NOT_APPLIED")
        source_angle = [t for t in source["tracks"] if t["property"] == ["LightSourceAngle", "LightSourceAngle"]]
        require(len(source_angle) == 1, "JOB178_SOURCE_TRACK")
        start, end = [int(v) for v in source_angle[0]["range"]]
        back = backup(run)
        track = binding.add_track(unreal.MovieSceneFloatTrack)
        track.set_property_name_and_path("Intensity", "Intensity")
        track.set_display_name(OWNER)
        section = track.add_section()
        section.set_range(start, end)
        section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
        channels = list(section.get_all_channels())
        require(len(channels) == 1, "NEW_CHANNEL_COUNT")
        channels[0].set_default(INTENSITY)
        require(census() == {"content": [MASTER], "maps": []}, "DIRTY_SCOPE|" + json.dumps(census(), sort_keys=True))
        state = track_state(binding)
        require(abs(state["default"] - INTENSITY) < 0.0001 and state["range"] == [start, end], "IN_MEMORY_READBACK")
        record = {"status": "prepared", "run": run, "backup": back, "track": state, "source_job178": JOB178}
        with open(RECORD, "x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
        require(unreal.EditorAssetLibrary.save_asset(MASTER, only_if_is_dirty=True), "SAVE_MASTER")
        require(census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY")
        state = track_state(binding)
        record.update(status="applied", track=state, dirty_after=census())
        with open(RECORD, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
        unreal.log("JOB185_P06_SUN_INTENSITY_APPLY_OK|run=%s|intensity=%.3f|range=%d:%d|saved_master=1|readback=1|dirty=0+0|backup=%s" %
                   (run, INTENSITY, start, end, back["root"]))
        return
    require(os.path.isfile(RECORD), "ACTIVE_RECORD_MISSING")
    with open(RECORD, encoding="utf-8") as handle:
        record = json.load(handle)
    require(record.get("status") == "applied", "RECORD_STATUS")
    state = track_state(binding)
    require(state == record["track"], "TRACK_DRIFT")
    require(census() == {"content": [], "maps": []}, "READBACK_DIRTIED")
    unreal.log("JOB185_P06_SUN_INTENSITY_READBACK_OK|run=%s|intensity=%.3f|range=%d:%d|dirty=0+0" %
               (run, state["default"], state["range"][0], state["range"][1]))


main()
