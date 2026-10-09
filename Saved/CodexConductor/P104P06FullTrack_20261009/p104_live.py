"""Live DRY/APPLY/REVERT for job 104. Offline-authored; never runs on import."""
from __future__ import annotations

import copy
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import wave

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.dirname(HERE)
PROJECT = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
ROOT = os.path.dirname(SAVED)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p104_core as C  # noqa: E402

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
GLINTS = "/Game/InfinityStage/Effects/LS_P06_BeeGlints"
CHOREO = "/Game/InfinityStage/Choreo/LS_Choreo_Passage_6"
DOMINO = "/Game/InfinityStage/Effects/LS_P06_DominoFinale"
MARK = "P104_P06_FULL_125"
DRY_PATH = os.path.join(HERE, "p104_dry.json")
RECORD_PATH = os.path.join(HERE, "p104_record_ACTIVE.json")
P33_RECORD = "passages_to_music_record_P06_125_E27.json"
P33_DRY = "passages_to_music_dry_P06_125_E27.json"


def require(value, message):
    if not value:
        raise C.PlanError(str(message))


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())


def load_module(name, relative, flag):
    path = os.path.join(SAVED, *relative.split("/"))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec and spec.loader, "MODULE_LOAD|" + path)
    module = importlib.util.module_from_spec(spec)
    setattr(module, flag, True)
    spec.loader.exec_module(module)
    return module


def asset_path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def rate(value):
    return float(value.numerator) / float(value.denominator)


def census():
    io = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(asset_path(x) for x in io.get_dirty_content_packages()),
            "maps": sorted(asset_path(x) for x in io.get_dirty_map_packages())}


def guard():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    require(asset_path(editor.get_editor_world()) == WORLD, "WRONG_WORLD")
    require(unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is None, "SEQUENCER_OPEN")
    require(census() == {"content": [], "maps": []}, "DIRTY_BEFORE|" + json.dumps(census()))


def package_file(package):
    base = os.path.join(PROJECT, "Content", *package[len("/Game/"):].split("/"))
    for extension in (".uasset", ".umap"):
        if os.path.isfile(base + extension):
            return base + extension
    raise C.PlanError("PACKAGE_FILE_MISSING|" + package)


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup(run, suffix, packages):
    root = os.path.join(PROJECT, "Backups", "PreP104P06Full125%s-%s" % (suffix, run))
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in packages:
        source = package_file(package)
        target = os.path.join(root, os.path.relpath(source, os.path.join(PROJECT, "Content")))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)
        require(sha(source) == sha(target), "BACKUP_HASH|" + package)
        rows.append({"package": package, "source": source, "backup": target, "sha256": sha(source)})
    result = {"root": root, "packages": rows}
    write(os.path.join(root, "manifest.json"), result, exclusive=True)
    return result


def wav_duration():
    path = os.path.join(PROJECT, *C.WAV.split("/"))
    require(os.path.isfile(path), "DELIVERED_WAV_MISSING|" + path)
    require(sha(path) == C.WAV_SHA256, "DELIVERED_WAV_SHA256")
    with wave.open(path, "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def p06_and_rail(show):
    hits = [p for p in show.get_editor_property("passage_settings")
            if str(p.get_editor_property("label")) == "Passage 6" and guid(p.get_editor_property("passage_guid")) == C.P06_GUID]
    require(len(hits) == 1, "P06_SETTINGS_COUNT|%d" % len(hits))
    p = hits[0]
    binding = p.get_editor_property("music")
    rail_guid = guid(binding.get_editor_property("primary_rail_guid"))
    rails = [r for r in show.get_editor_property("music_rails") if guid(r.get_editor_property("rail_guid")) == rail_guid]
    require(len(rails) == 1, "P06_RAIL_COUNT|%d" % len(rails))
    sound = rails[0].get_editor_property("sound")
    if sound is not None and hasattr(sound, "load_synchronous"):
        sound = sound.load_synchronous()
    return p, rails[0], asset_path(sound)


def p06_length(show):
    transport = unreal.new_object(unreal.InfinityStageTransportController)
    transport.build_segments(show)
    rows = [x for x in transport.get_editor_property("segments") if str(x.get_editor_property("label")) == "Passage 6"]
    require(len(rows) == 1, "P06_SEGMENT_COUNT")
    return (int(rows[0].get_editor_property("end_frame").value) -
            int(rows[0].get_editor_property("start_frame").value)) / rate(show.get_editor_property("tick_resolution"))


def chain_records():
    a_root = os.path.join(PROJECT, "Saved", "CodexFlatV3", "topple")
    a_pointer = read(os.path.join(a_root, "topple_originals_ACTIVE.json"))
    a_apply = read(os.path.join(a_root, "topple_apply_%s.json" % a_pointer["run_id"]))
    a_rows = [r["cue_guid"] for r in (a_apply.get("chain_timing") or {}).get("rows", [])]
    b_root = os.path.join(HERE, "..", "P37P06DominoFinale_20261009", "records", "B")
    b_registry = read(os.path.normpath(os.path.join(b_root, "domino_chain_B_ACTIVE.json")))
    b_rows = list(b_registry["row_guids"])
    require(set(a_rows).isdisjoint(b_rows), "TOPPLE_CHAIN_OVERLAP")
    return {"a": a_rows, "b": b_rows, "a_run": a_pointer["run_id"], "b_run": b_registry["apply_run"]}


def passage_frames(show):
    P = load_module("p104_passage_base", "CodexConductor/passage_retime_to_music.py", "RETIME_IMPORT_ONLY")
    facts = P._passage_facts(show, "Passage 6")
    tick = rate(show.get_editor_property("tick_resolution"))
    frame = int(facts["lead"])
    out = {}
    for cue_guid, interval in zip(facts["wing_cues"], facts["intervals"]):
        out[cue_guid] = frame / tick
        frame += int(interval)
    return out


def gather_facts():
    show = unreal.load_asset(SHOW)
    require(show is not None, "SHOW_LOAD")
    _p, _r, assigned = p06_and_rail(show)
    into = unreal.load_asset(C.INTO_VOID)
    cameron = unreal.load_asset(C.CAMERON)
    chains = chain_records()
    return {"into_void_duration_s": float(into.get_editor_property("duration")) if into else None,
            "delivered_wav_duration_s": wav_duration(), "assigned_sound": assigned,
            "cameron_asset_exists": cameron is not None,
            "cameron_duration_s": float(cameron.get_editor_property("duration")) if cameron else None,
            "p06_length_s": p06_length(show), "chain_a_rows": len(chains["a"]),
            "chain_b_rows": len(chains["b"]), "chain_a_run": chains["a_run"], "chain_b_run": chains["b_run"],
            "p37_sequence_present": unreal.EditorAssetLibrary.does_asset_exist(DOMINO),
            "fx_policy_evidence": "P06 FX record fields are distance/view activated",
            "chandelier_policy_evidence": "P75 p06 owned_sequence_writes=[]"}


def walking_args():
    args = read(os.path.join(SAVED, "walking_music_swap_args.json"))
    args.update({"mode": "APPLY", "confirm": "APPLY WALKING MUSIC", "apply_passages": ["6"],
                 "decided_by": C.DECIDED_BY, "mapping_confirmed_by": C.DECIDED_BY,
                 "run_id": None, "delete_assets": False})
    return args


def apply_audio(run):
    W = load_module("p104_walking", "CodexConductor/walking_music_swap.py", "WALKING_MUSIC_SWAP_IMPORT_ONLY")
    args = walking_args()
    W.run_apply(args, run + "-AUDIO")
    return os.path.join(SAVED, W.record_name(["6"]))


def p33_args(target_sound, mode):
    args = read(os.path.join(SAVED, "passages_to_music_args.json"))
    args.update({"mode": mode, "confirm": "%s PASSAGES TO MUSIC" % mode,
                 "run_id": None, "hold_passages": ["1", "2", "3", "4", "5"],
                 "decided_by": C.DECIDED_BY})
    args["per_passage"]["6"].update({"music_s": None, "sound": target_sound,
                                      "duration_source": "LIVE_SOUNDWAVE", "expected": None})
    return args


def apply_length(run, target_sound):
    P = load_module("p104_passages", "CodexConductor/passages_to_music.py", "PASSAGES_TO_MUSIC_IMPORT_ONLY")
    P.RECORD_NAME, P.DRY_NAME, P.P06_LIVE_SOUND = P33_RECORD, P33_DRY, target_sound
    args = p33_args(target_sound, "DRY")
    report, _snap, _show, _master, _facts = P._gather(args)
    require(not report["refusals"], "P33_DRY_REFUSALS|" + repr(report["refusals"][:8]))
    args.update({"mode": "APPLY", "confirm": "APPLY PASSAGES TO MUSIC"})
    args["review"]["inventory_sha256"] = report["reviewInventorySha256"]
    for key, row in report["per"].items():
        args["per_passage"][key]["expected"] = {"old_len_ticks": row["plan"]["old_ticks"],
                                                   "new_len_ticks": row["plan"]["new_ticks"],
                                                   "music_ticks": row["music"]["selectedTicks"]}
    P.run_apply(args, run + "-LENGTH")
    return os.path.join(SAVED, P33_RECORD)


def mechanism_state(show, guids):
    wanted = set(guids)
    out = {}
    for cue in show.get_editor_property("cues"):
        g = guid(cue.get_editor_property("cue_guid"))
        if g not in wanted:
            continue
        mech = cue.get_editor_property("wing_pair").get_editor_property("mechanism")
        out[g] = {"rate": float(mech.get_editor_property("cycle_rate_hz")),
                  "offset": float(mech.get_editor_property("phase_offset_cycles")),
                  "export": mech.export_text()}
    require(set(out) == wanted, "TOPPLE_GUID_READBACK")
    return out


def write_mechanisms(show, values):
    cues = list(show.get_editor_property("cues"))
    for index, cue in enumerate(cues):
        g = guid(cue.get_editor_property("cue_guid"))
        if g not in values:
            continue
        pair = cue.get_editor_property("wing_pair")
        mech = pair.get_editor_property("mechanism")
        mech.set_editor_property("cycle_rate_hz", float(values[g]["rate"]))
        mech.set_editor_property("phase_offset_cycles", float(values[g]["offset"]))
        pair.set_editor_property("mechanism", mech)
        cue.set_editor_property("wing_pair", pair)
        cues[index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def sequence_state(sequence, choreo):
    rows = []
    for bi, binding in enumerate(sequence.get_bindings()):
        for ti, track in enumerate(binding.get_tracks()):
            for si, section in enumerate(track.get_sections()):
                keys = []
                for ci, channel in enumerate(section.get_all_channels()):
                    for ki, key in enumerate(channel.get_keys()):
                        keys.append([ci, ki, int(key.get_time().frame_number.value), str(key.get_value())])
                rows.append({"kind": "binding", "binding_index": bi, "track_index": ti,
                             "owner": str(binding.get_display_name()), "track": str(track.get_display_name()),
                             "section": si, "range": [int(section.get_start_frame()), int(section.get_end_frame())],
                             "keys": keys})
    for ti, track in enumerate(sequence.get_tracks()):
        for si, section in enumerate(track.get_sections()):
            rows.append({"kind": "root", "track_index": ti, "owner": "ROOT", "track": str(track.get_display_name()), "section": si,
                         "range": [int(section.get_start_frame()), int(section.get_end_frame())], "keys": []})
    sub = []
    for track in choreo.get_tracks():
        for section in track.get_sections():
            if asset_path(section.get_sequence()) == DOMINO:
                sub.append([int(section.get_start_frame()), int(section.get_end_frame())])
    return {"playback": [int(sequence.get_playback_start()), int(sequence.get_playback_end())],
            "rows": rows, "subtrack": sub}


def scale_sequence(sequence, choreo, factor):
    sequence.modify(); choreo.modify()
    sequence.set_playback_start(C.scale_frame(sequence.get_playback_start(), factor))
    sequence.set_playback_end(C.scale_frame(sequence.get_playback_end(), factor))
    tracks = [t for b in sequence.get_bindings() for t in b.get_tracks()] + list(sequence.get_tracks())
    for track in tracks:
        for section in track.get_sections():
            start, end = int(section.get_start_frame()), int(section.get_end_frame())
            section.set_range(C.scale_frame(start, factor), C.scale_frame(end, factor))
            for channel in section.get_all_channels():
                for key in channel.get_keys():
                    key.set_time(unreal.FrameNumber(C.scale_frame(key.get_time().frame_number.value, factor)), 0.0,
                                 unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    for track in choreo.get_tracks():
        for section in track.get_sections():
            if asset_path(section.get_sequence()) == DOMINO:
                section.set_range(C.scale_frame(section.get_start_frame(), factor),
                                  C.scale_frame(section.get_end_frame(), factor))


def scaled_sequence_state(before, factor):
    out = copy.deepcopy(before)
    out["playback"] = [C.scale_frame(x, factor) for x in before["playback"]]
    out["subtrack"] = [[C.scale_frame(x, factor) for x in span] for span in before["subtrack"]]
    for row in out["rows"]:
        row["range"] = [C.scale_frame(x, factor) for x in row["range"]]
        for key in row["keys"]:
            key[2] = C.scale_frame(key[2], factor)
    return out


def chandelier_state():
    rows = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label = str(actor.get_actor_label())
        if not label.startswith("P75 P06"):
            continue
        tr = actor.get_actor_transform()
        rows.append({"label": label,
                     "location": [float(tr.translation.x), float(tr.translation.y), float(tr.translation.z)],
                     "rotation": [float(tr.rotation.x), float(tr.rotation.y), float(tr.rotation.z), float(tr.rotation.w)],
                     "scale": [float(tr.scale3d.x), float(tr.scale3d.y), float(tr.scale3d.z)]})
    return sorted(rows, key=lambda row: row["label"])


def restore_sequence(sequence, choreo, state):
    sequence.modify(); choreo.modify()
    sequence.set_playback_start(int(state["playback"][0])); sequence.set_playback_end(int(state["playback"][1]))
    bindings, roots = list(sequence.get_bindings()), list(sequence.get_tracks())
    for row in state["rows"]:
        track = (list(bindings[row["binding_index"]].get_tracks())[row["track_index"]]
                 if row["kind"] == "binding" else roots[row["track_index"]])
        section = list(track.get_sections())[row["section"]]
        section.set_range(int(row["range"][0]), int(row["range"][1]))
        channels = list(section.get_all_channels())
        for ci, ki, frame, _value in row["keys"]:
            key = list(channels[ci].get_keys())[ki]
            key.set_time(unreal.FrameNumber(int(frame)), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    owned = []
    for track in choreo.get_tracks():
        for section in track.get_sections():
            if asset_path(section.get_sequence()) == DOMINO:
                owned.append(section)
    require(len(owned) == len(state["subtrack"]), "RESTORE_SUBTRACK_COUNT")
    for section, span in zip(owned, state["subtrack"]):
        section.set_range(int(span[0]), int(span[1]))


def apply_custom(run, plan, old_pass_frames):
    R = load_module("p104_job42", "CodexConductor/p06_retime.py", "P06_RETIME_IMPORT_ONLY")
    live = R._live()
    show = live["show"]
    new_pass_frames = passage_frames(show)
    chains = chain_records(); all_guids = chains["a"] + chains["b"]
    before_mech = mechanism_state(show, all_guids)
    after_mech = {}
    for g, row in before_mech.items():
        require(g in old_pass_frames and g in new_pass_frames, "TOPPLE_PASS_FRAME_MISSING|" + g)
        nr, no = C.retime_phase(row["rate"], row["offset"], old_pass_frames[g], new_pass_frames[g], plan["scale"])
        after_mech[g] = {"rate": nr, "offset": no}
    before = {"sunset": live["plain"]["sunset"], "car": live["plain"]["car"],
              "bee": live["plain"]["bee"], "fx": live["plain"]["fx"],
              "chandelier": chandelier_state(), "mechanisms": before_mech}
    after = {"sunset": copy.deepcopy(before["sunset"]), "car": R.scaled_car(before["car"], plan["scale"]),
             "bee": R.scaled_bee(before["bee"], plan["scale"], round(C.DELIVERED_TRACK_S * before["bee"]["fps"])),
             "mechanisms": after_mech}
    after["sunset"]["cycle_duration_seconds"] *= plan["scale"]
    sequence, choreo = unreal.load_asset(DOMINO), unreal.load_asset(CHOREO)
    before["domino"] = sequence_state(sequence, choreo)
    after["fx"] = copy.deepcopy(before["fx"]); after["chandelier"] = copy.deepcopy(before["chandelier"])
    after["domino"] = scaled_sequence_state(before["domino"], plan["scale"])
    custom_backup = backup(run, "Retime", [SHOW, WORLD, GLINTS, CHOREO, DOMINO])
    record = read(RECORD_PATH)
    require(record.get("status") == "prepared" and record.get("run") == run, "P104_COORDINATOR_RECORD_CONTEXT")
    record.update({"backup": custom_backup, "before": before, "after": after,
                   "old_pass_frames": old_pass_frames, "new_pass_frames": new_pass_frames,
                   "stage": "custom_recorded"})
    write(RECORD_PATH, record)
    R._write_sunset(show, after["sunset"]); R._write_car(live["car_actor"], after["car"])
    R._write_bee(live["glints"], live["bindings"], live["subsection"], after["bee"])
    write_mechanisms(show, after_mech); scale_sequence(sequence, choreo, plan["scale"])
    actor = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
             if a.get_class().get_name() == "InfinityStagePassageActor" and str(a.get_actor_label()).startswith("Passage 06")
             and a.get_editor_property("show_asset") == show]
    require(len(actor) == 1 and actor[0].materialize_passage(), "P06_MATERIALIZE")
    expected = {"content": sorted([SHOW, GLINTS, CHOREO, DOMINO]), "maps": [WORLD]}
    require(census() == expected, "CUSTOM_DIRTY_SCOPE|got=%s|want=%s" % (census(), expected))
    for package in (SHOW, GLINTS, CHOREO, DOMINO):
        require(unreal.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False), "SAVE_FAILED|" + package)
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "SAVE_WORLD")
    require(census() == {"content": [], "maps": []}, "DIRTY_AFTER_CUSTOM_SAVE")
    post = R._live()["plain"]
    require(not R.state_matches({"sunset": post["sunset"], "car": post["car"], "bee": post["bee"], "fx": post["fx"]},
                                {"sunset": after["sunset"], "car": after["car"], "bee": after["bee"], "fx": after["fx"]}),
            "JOB42_READBACK")
    require(all(abs(mechanism_state(unreal.load_asset(SHOW), all_guids)[g][k] - after_mech[g][k]) <= 1e-4
                for g in all_guids for k in ("rate", "offset")), "MECHANISM_READBACK")
    require(sequence_state(unreal.load_asset(DOMINO), unreal.load_asset(CHOREO)) == after["domino"],
            "P37_SEQUENCE_READBACK")
    require(chandelier_state() == after["chandelier"], "CHANDELIER_DRIFT")
    record.update({"status": "applied", "after": after, "dirty_after": census()})
    write(RECORD_PATH, record)
    return custom_backup


def restore_custom(run):
    R = load_module("p104_job42_revert", "CodexConductor/p06_retime.py", "P06_RETIME_IMPORT_ONLY")
    record = read(RECORD_PATH); require(record.get("status") == "applied", "CUSTOM_RECORD_NOT_APPLIED")
    live = R._live(); show = live["show"]
    all_guids = list(record["before"]["mechanisms"])
    current_plain = live["plain"]
    require(not R.state_matches({"sunset": current_plain["sunset"], "car": current_plain["car"],
                                 "bee": current_plain["bee"], "fx": current_plain["fx"]},
                                {"sunset": record["after"]["sunset"], "car": record["after"]["car"],
                                 "bee": record["after"]["bee"], "fx": record["after"]["fx"]}),
            "REVERT_STATE_DRIFT_JOB42_OR_FX")
    current_mech = mechanism_state(show, all_guids)
    require(all(abs(current_mech[g][key] - record["after"]["mechanisms"][g][key]) <= 1e-4
                for g in all_guids for key in ("rate", "offset")), "REVERT_STATE_DRIFT_TOPPLE")
    require(sequence_state(unreal.load_asset(DOMINO), unreal.load_asset(CHOREO)) == record["after"]["domino"],
            "REVERT_STATE_DRIFT_P37")
    require(chandelier_state() == record["after"]["chandelier"], "REVERT_STATE_DRIFT_CHANDELIER")
    backup(run, "Revert", [SHOW, WORLD, GLINTS, CHOREO, DOMINO])
    R._write_sunset(show, record["before"]["sunset"]); R._write_car(live["car_actor"], record["before"]["car"])
    R._write_bee(live["glints"], live["bindings"], live["subsection"], record["before"]["bee"])
    values = {g: {"rate": x["rate"], "offset": x["offset"]} for g, x in record["before"]["mechanisms"].items()}
    write_mechanisms(show, values)
    sequence, choreo = unreal.load_asset(DOMINO), unreal.load_asset(CHOREO)
    restore_sequence(sequence, choreo, record["before"]["domino"])
    actor = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
             if a.get_class().get_name() == "InfinityStagePassageActor" and str(a.get_actor_label()).startswith("Passage 06")
             and a.get_editor_property("show_asset") == show]
    require(len(actor) == 1 and actor[0].materialize_passage(), "REVERT_MATERIALIZE")
    expected = {"content": sorted([SHOW, GLINTS, CHOREO, DOMINO]), "maps": [WORLD]}
    require(census() == expected, "REVERT_CUSTOM_DIRTY_SCOPE")
    for package in (SHOW, GLINTS, CHOREO, DOMINO):
        require(unreal.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False), "REVERT_SAVE|" + package)
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "REVERT_SAVE_WORLD")
    require(census() == {"content": [], "maps": []}, "REVERT_DIRTY_AFTER")
    require(sequence_state(unreal.load_asset(DOMINO), unreal.load_asset(CHOREO)) == record["before"]["domino"],
            "REVERT_P37_NOT_EXACT")
    require(chandelier_state() == record["before"]["chandelier"], "REVERT_CHANDELIER_DRIFT")
    archive = RECORD_PATH.replace("_ACTIVE.json", "_REVERTED_%s.json" % run)
    record.update({"status": "reverted", "revert_run": run})
    write(RECORD_PATH, record); os.replace(RECORD_PATH, archive)
    return archive


def revert_length(run, target_sound):
    P = load_module("p104_passages_revert", "CodexConductor/passages_to_music.py", "PASSAGES_TO_MUSIC_IMPORT_ONLY")
    P.RECORD_NAME, P.P06_LIVE_SOUND = P33_RECORD, target_sound
    P.run_revert(p33_args(target_sound, "REVERT"), run + "-LENGTH")


def revert_audio(run):
    W = load_module("p104_walking_revert", "CodexConductor/walking_music_swap.py", "WALKING_MUSIC_SWAP_IMPORT_ONLY")
    args = walking_args(); args.update({"mode": "REVERT", "confirm": "REVERT WALKING MUSIC"})
    W.run_revert(args, run + "-AUDIO")


def main(raw):
    run = str(raw.get("run_id") or datetime.datetime.now().strftime("P104-%Y%m%d-%H%M%S"))
    mode = C.validate_args(raw); guard()
    unreal.log("%s_START|run=%s|mode=%s" % (MARK, run, mode))
    if mode == "DRY":
        plan = C.build_plan(gather_facts())
        report = {"run": run, "mode": mode, "apply_ready": True, "plan": plan,
                  "census_before": census(), "census_after": census(), "mutated": False}
        write(DRY_PATH, report)
        unreal.log("%s_DRY_OK|run=%s|decision=%s|old=%.6f|target=%.3f|scale=%.9f|A=%d|B=%d|mutated=0|census=clean|plan=%s" %
                   (MARK, run, plan["decision"]["action"], plan["old_track_s"], plan["target_track_s"], plan["scale"],
                    plan["chain_a_rows"], plan["chain_b_rows"], plan["plan_sha256"]))
        return
    if mode == "APPLY":
        require(not os.path.exists(RECORD_PATH), "P104_ACTIVE_RECORD_EXISTS")
        plan = C.build_plan(gather_facts())
        require(raw["reviewed_plan_sha256"] == plan["plan_sha256"], "PLAN_SHA256_CHANGED")
        old_frames = passage_frames(unreal.load_asset(SHOW))
        write(RECORD_PATH, {"schema": 1, "tool": "p104", "run": run, "status": "prepared",
                            "stage": "before_audio", "plan": plan, "old_pass_frames": old_frames,
                            "audio_record": None, "length_record": None}, exclusive=True)
        audio_record = None
        if plan["decision"]["action"] == "IMPORT_AND_SWAP":
            audio_record = apply_audio(run)
            coordinator = read(RECORD_PATH); coordinator.update({"audio_record": audio_record, "stage": "audio_applied"})
            write(RECORD_PATH, coordinator)
        length_record = apply_length(run, plan["decision"]["target_sound"])
        coordinator = read(RECORD_PATH); coordinator.update({"length_record": length_record, "stage": "length_applied"})
        write(RECORD_PATH, coordinator)
        custom_backup = apply_custom(run, plan, old_frames)
        record = read(RECORD_PATH)
        record.update({"audio_record": audio_record, "length_record": length_record,
                       "custom_backup": custom_backup, "ordered_steps": ["audio", "length", "retime"]})
        write(RECORD_PATH, record)
        unreal.log("%s_APPLY_OK|run=%s|decision=%s|length=125.000|scale=%.9f|A=%d|B=%d|p37=scaled|fx=kept|chandelier=kept|saved_readback=1|dirty=0+0|record=%s" %
                   (MARK, run, plan["decision"]["action"], plan["scale"], plan["chain_a_rows"],
                    plan["chain_b_rows"], RECORD_PATH))
        return
    require(os.path.isfile(RECORD_PATH), "P104_ACTIVE_RECORD_MISSING")
    record = read(RECORD_PATH); target = record["plan"]["decision"]["target_sound"]
    archive = None
    if record.get("status") == "applied":
        archive = restore_custom(run)
    else:
        require(record.get("status") == "prepared", "P104_RECORD_STATUS")
    if record.get("length_record"):
        revert_length(run, target)
    if record.get("audio_record"):
        revert_audio(run)
    if os.path.isfile(RECORD_PATH):
        current = read(RECORD_PATH)
        current.update({"status": "reverted", "revert_run": run, "partial_apply_recovery": True})
        write(RECORD_PATH, current)
        archive = RECORD_PATH.replace("_ACTIVE.json", "_REVERTED_%s.json" % run)
        os.replace(RECORD_PATH, archive)
    require(census() == {"content": [], "maps": []}, "REVERT_FINAL_CENSUS")
    unreal.log("%s_REVERT_OK|run=%s|ordered=retime,length,audio|dirty=0+0|record=%s" % (MARK, run, archive))
