"""Read-only final validator for Job 168.  It never saves."""
import hashlib
import importlib.util
import json
import os

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
KLARA = "/Game/InfinityStage/KlaraHookin/LS_Animals_1_S1Hangar"


def _load_job_module():
    path = os.path.join(HERE, "job168_s1_ending.py")
    spec = importlib.util.spec_from_file_location("job168_validate_helpers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extend_helpers():
    path = os.path.normpath(os.path.join(HERE, "..", "..", "CodexSoftGoods", "extend_scene_playback.py"))
    source = open(path, "r", encoding="utf-8").read()
    if not source.rstrip().endswith("\nmain()"):
        raise RuntimeError("EXTEND_TOOL_SHAPE")
    namespace = {"__name__": "job168_extend_helpers", "__file__": path}
    exec(compile(source.rstrip()[:-len("main()")], path, "exec"), namespace)
    return namespace


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name() for p in lib.get_dirty_map_packages())}


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(args):
    helper = _load_job_module()
    ext = _extend_helpers()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if _census() != {"content": [], "maps": []}:
        raise RuntimeError("DIRTY_AT_START|%s" % _census())
    world = editor.get_editor_world()
    seq, show, master = unreal.load_asset(SCENE), unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    plan = helper.timing_plan(args)
    failures = []
    if int(seq.get_playback_end()) != plan["new_end"]:
        failures.append("PLAYBACK_END|%d" % int(seq.get_playback_end()))
    owned = helper._owned_state(seq, world, args["animal_labels"])
    if len(owned) != 3:
        failures.append("ANIMAL_OWNED_COUNT|%d" % len(owned))
    timeline = helper._root_timeline(seq)
    shots = timeline["shots"]
    if len(shots) != 1 or shots[0]["range"][1] != plan["exit_handoff"][0]:
        failures.append("KLARA_SHOT_END|%s" % shots)
    names = {helper._guid(b.get_id()): str(b.get_display_name()) for b in seq.get_bindings()}
    exit_rows = [row for row in timeline["camera_cuts"]
                 if "Exit Handoff Camera" in names.get(row.get("camera_guid"), "")]
    if len(exit_rows) != 1 or exit_rows[0]["range"] != plan["exit_handoff"]:
        failures.append("EXIT_HANDOFF|%s" % exit_rows)
    # s4_hangar_hold pattern: all three landed-pose tracks must reach the exclusive end.
    hold_labels = {"S1 Hangar Root", "S1 Hangar Roof Hinge", "S1 Hangar Lattice Fly"}
    held = {}
    for binding in seq.get_bindings():
        label = str(binding.get_display_name())
        if label not in hold_labels:
            continue
        spans = []
        for track in binding.get_tracks():
            if track.get_class().get_name() == "MovieScene3DTransformTrack":
                spans.extend(helper._section_range(s, seq) for s in track.get_sections() if s.is_active())
        held[label] = spans
    for label in sorted(hold_labels):
        if not any(span[0] <= 775 and span[1] == plan["new_end"] for span in held.get(label, [])):
            failures.append("HANGAR_HOLD|%s|%s" % (label, held.get(label)))
    match = ext["show_master_match"](show, master)
    if not match["match"]:
        failures.append("SHOW_MASTER|%s" % match)
    segments = ext["compiled_segments"](show)
    indices = [i for i, row in enumerate(segments) if row["label"] == args["cue_label"]]
    if len(indices) != 1:
        failures.append("S1_SEGMENT_COUNT|%d" % len(indices))
        neighbours = []
    else:
        i = indices[0]
        neighbours = segments[max(0, i - 1):min(len(segments), i + 2)]
    animal_record = json.load(open(os.path.join(HERE, "job168_animals_record.json"), "r", encoding="utf-8"))
    klara_guard = animal_record["report"]["klara_guard"]
    if _sha(klara_guard["file"]) != klara_guard["sha256"]:
        failures.append("KLARA_HASH_CHANGED")
    rig_record = os.path.join(HERE, "s1_rig_fade_record.json")
    if not os.path.isfile(rig_record):
        failures.append("LIGHTS_OUT_RECORD_MISSING")
        lights = None
    else:
        lights = json.load(open(rig_record, "r", encoding="utf-8"))
        target = lights.get("plan", {}).get("target_switch_frame")
        if target != plan["lights_out"][1]:
            failures.append("LIGHTS_OUT_TARGET|%s" % target)
    if _census() != {"content": [], "maps": []}:
        failures.append("VALIDATE_DIRTIED|%s" % _census())
    report = {"schema": 1, "run": args["run_id"], "ok": not failures, "failures": failures,
              "plan": plan, "animal_tracks": owned, "timeline": timeline, "hangar_hold": held,
              "show_master": match, "s1_neighbours": neighbours, "klara_guard": klara_guard,
              "lights_out_record": lights, "census": _census(),
              "pie_stills_plan": [{"frame": int(frame), "claim": claim} for frame, claim in zip(
                  args["stills_frames"],
                  ("fade in progress", "animals fully gone", "post-fade hold", "lights-out begins", "exclusive new end"))]}
    path = os.path.join(HERE, "job168_validate_%s.json" % args["run_id"])
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, default=str)
    if failures:
        raise RuntimeError("VALIDATION_FAILED|%s|report=%s" % (failures[:8], path))
    unreal.log("JOB168_VALIDATE_OK|run=%s|animals=3|fade=%s|lights=%s|handoff=%s|end=%d|hangar=3|show_master=1|klara_saved=0|levels_saved=0|report=%s" %
               (args["run_id"], plan["animal_fade"], plan["lights_out"], plan["exit_handoff"],
                plan["new_end"], path))
    return report
