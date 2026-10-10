"""Read-only final validator for Job 169.  It never saves."""
import hashlib
import importlib.util
import json
import os

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"


def _load_job_module():
    path = os.path.join(HERE, "job169_s1_fire_ending.py")
    spec = importlib.util.spec_from_file_location("job169_validate_helpers", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def _extend_helpers():
    path = os.path.normpath(os.path.join(HERE, "..", "..", "CodexSoftGoods", "extend_scene_playback.py"))
    source = open(path, "r", encoding="utf-8").read()
    if not source.rstrip().endswith("\nmain()"):
        raise RuntimeError("EXTEND_TOOL_SHAPE")
    namespace = {"__name__": "job169_extend_helpers", "__file__": path}
    exec(compile(source.rstrip()[:-len("main()")], path, "exec"), namespace)
    return namespace


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    path = lambda value: value.get_path_name().split(".", 1)[0]
    return {"content": sorted(path(p) for p in lib.get_dirty_content_packages()),
            "maps": sorted(path(p) for p in lib.get_dirty_map_packages())}


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args):
    helper, ext = _load_job_module(), _extend_helpers()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if _census() != {"content": [], "maps": []}:
        raise RuntimeError("DIRTY_AT_START|%s" % _census())
    seq, show, master = unreal.load_asset(SCENE), unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    plan = helper.timing_plan(args); failures = []
    if int(seq.get_playback_end()) != plan["new_end"]:
        failures.append("PLAYBACK_END|%d" % int(seq.get_playback_end()))
    timeline, owned = helper._timeline_state(seq), helper._owned_state(seq)
    spawnables = [r for r in owned if r["spawnable"]]
    if sorted(r["name"] for r in spawnables) != sorted((helper.CAMERA_NAME, helper.FIRE_NAME, helper.LIGHT_NAME)):
        failures.append("OWNED_SPAWNABLES|%s" % [r["name"] for r in spawnables])
    shots = timeline["shots"]
    if (len(shots) != 2 or shots[0]["range"] != [594, plan["camera_pan"][0]] or
            shots[1]["range"] != [plan["camera_pan"][0], plan["new_end"]] or
            shots[1]["bias"] != int(args["camera_hierarchical_bias"])):
        failures.append("KLARA_SHOT_SPLIT|%s" % shots)
    cuts = [row for row in timeline["cuts"] if row["camera"] == helper.CAMERA_NAME]
    if len(cuts) != 1 or cuts[0]["range"] != [plan["camera_pan"][0], plan["new_end"]]:
        failures.append("CAMERA_CUT|%s" % cuts)
    for name in (helper.FIRE_NAME, helper.LIGHT_NAME):
        rows = [row for row in owned if row["name"] == name]
        if len(rows) != 1:
            failures.append("OWNED_BINDING|%s|%d" % (name, len(rows)))
            continue
        vis = [t for t in rows[0]["tracks"] if t["class"] == "MovieSceneVisibilityTrack"]
        spawn = [t for t in rows[0]["tracks"] if t["class"] == "MovieSceneSpawnTrack"]
        if (len(vis) != 1 or tuple(vis[0]["property"]) != ("bHidden", "bHidden") or len(spawn) != 1):
            failures.append("HIDDEN_OUTSIDE_WINDOW|%s|vis=%s|spawn=%s" % (name, vis, spawn))
    match = ext["show_master_match"](show, master)
    if not match["match"]:
        failures.append("SHOW_MASTER|%s" % match)
    segments = ext["compiled_segments"](show)
    indices = [i for i, row in enumerate(segments) if row["label"] == args["cue_label"]]
    neighbours = []
    if len(indices) != 1:
        failures.append("S1_SEGMENT_COUNT|%d" % len(indices))
    else:
        i = indices[0]; neighbours = segments[max(0, i - 1):min(len(segments), i + 2)]
    record_path = os.path.join(HERE, helper.RECORD_NAME)
    if not os.path.isfile(record_path):
        failures.append("CAMERA_FIRE_RECORD_MISSING"); record = None
    else:
        record = json.load(open(record_path, "r", encoding="utf-8"))
        for asset, guard in record["report"]["guards"].items():
            if _sha(guard["file"]) != guard["sha256"]:
                failures.append("KLARA_GUARD_CHANGED|%s" % asset)
    rig_path = os.path.join(HERE, "s1_rig_fade_record.json")
    if not os.path.isfile(rig_path):
        failures.append("LIGHTS_OUT_RECORD_MISSING"); lights = None
    else:
        lights = json.load(open(rig_path, "r", encoding="utf-8"))
        if lights.get("plan", {}).get("target_switch_frame") != plan["lights_out"][1]:
            failures.append("LIGHTS_OUT_TARGET|%s" % lights.get("plan", {}).get("target_switch_frame"))
    hold_labels = {"S1 Hangar Root", "S1 Hangar Roof Hinge", "S1 Hangar Lattice Fly"}; held = {}
    for binding in seq.get_bindings():
        label = str(binding.get_display_name())
        if label not in hold_labels:
            continue
        held[label] = [helper._section_range(s, seq) for t in binding.get_tracks()
                       if t.get_class().get_name() == "MovieScene3DTransformTrack"
                       for s in t.get_sections() if s.is_active()]
    for label in sorted(hold_labels):
        if not any(span[0] <= 775 and span[1] == plan["new_end"] for span in held.get(label, [])):
            failures.append("HANGAR_HOLD|%s|%s" % (label, held.get(label)))
    if _census() != {"content": [], "maps": []}:
        failures.append("VALIDATE_DIRTIED|%s" % _census())
    claims = ("pre-pan continuity", "pan/fire reveal", "pan settling", "fire hold",
              "lights-out begins; fire remains", "last valid S1 frame; fire is last light")
    report_out = {"schema": 1, "run": args["run_id"], "ok": not failures, "failures": failures,
                  "plan": plan, "timeline": timeline, "owned": owned, "hangar_hold": held,
                  "show_master": match, "s1_neighbours": neighbours, "camera_fire_record": record,
                  "lights_out_record": lights, "census": _census(),
                  "pie_stills_plan": [{"frame": int(frame), "claim": claim}
                                      for frame, claim in zip(args["stills_frames"], claims)],
                  "boundary_check": {"exclusive_end": plan["new_end"],
                                     "verify_next_cue_camera_owner": True}}
    path = os.path.join(HERE, "job169_validate_%s.json" % args["run_id"])
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report_out, handle, indent=2, sort_keys=True, default=str)
    if failures:
        raise RuntimeError("VALIDATION_FAILED|%s|report=%s" % (failures[:8], path))
    unreal.log("JOB169_VALIDATE_OK|run=%s|camera_cut=%s|fire=%s|lights=%s|end=%d|hangar=3|show_master=1|klara_saved=0|levels_saved=0|report=%s" %
               (args["run_id"], plan["camera_pan"], plan["fire_window"], plan["lights_out"],
                plan["new_end"], path))
    return report_out
