"""Live Unreal snapshot/executor adapter for P45.

Imported only by the guarded runner.  Planning remains in breath_insert.py and
uses plain dictionaries.  This adapter deliberately refuses external At/GO rows
because they are not named packages in the P45 transaction.
"""
import csv
import json
import os

import unreal


MANAGED = {
    "MovieSceneInfinityPassageTrack",
    "MovieSceneInfinitySceneTrack",
    "MovieSceneInfinityChoreoTrack",
    "MovieSceneInfinityAudioTrack",
    "MovieSceneInfinityCueTrack",
}


def guid(value):
    return str(value).replace("-", "").replace("{", "").replace("}", "").upper()


def rate(value):
    return float(value.numerator) / float(value.denominator)


def frame(value):
    return int(value.value if hasattr(value, "value") else value)


def asset_path(value):
    if value is None:
        return ""
    if hasattr(value, "load_synchronous"):
        value = value.load_synchronous()
    return str(value.get_path_name()).split(".", 1)[0] if value is not None else ""


def ticks(seconds, tick):
    return int(round(float(seconds) * float(tick)))


def section_range(section, tick, origin=0):
    if not section.has_start_frame() or not section.has_end_frame():
        raise RuntimeError("UNBOUNDED_SECTION|%s" % section.get_path_name())
    return [ticks(section.get_start_frame_seconds(), tick) - origin,
            ticks(section.get_end_frame_seconds(), tick) - origin]


def channel_rows(section, origin=0):
    out = {}
    for channel in section.get_all_channels():
        name = str(channel.get_editor_property("channel_name"))
        rows = []
        for key in channel.get_keys():
            when = frame(key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number) - origin
            try:
                value = float(key.get_value())
            except Exception as error:
                raise RuntimeError("NON_NUMERIC_CHANNEL|%s|%s" % (name, error))
            rows.append([when, value])
        out[name] = sorted(rows, key=lambda row: row[0])
    return out


def all_tracks(sequence):
    rows = [("root", "", index, track) for index, track in enumerate(sequence.get_tracks())]
    for binding in sequence.get_bindings():
        rows += [("binding", guid(binding.get_id()), index, track)
                 for index, track in enumerate(binding.get_tracks())]
    return rows


def track_row(package, host, binding_guid, track_index, track, classification, tick, origin=0):
    sections = []
    for section_index, section in enumerate(track.get_sections()):
        sections.append({
            "class": track.get_class().get_name(),
            "range": section_range(section, tick, origin),
            "channels": [{"name": name, "keys": rows} for name, rows in
                         sorted(channel_rows(section, origin).items())],
            "locator": {"package": package, "host": host, "binding_guid": binding_guid,
                        "track_index": track_index, "section_index": section_index},
        })
    return {"classification": classification, "class": track.get_class().get_name(), "sections": sections}


def markers(sequence, origin, classification):
    rows = []
    for marker in sequence.get_marked_frames():
        locked = False
        try:
            locked = bool(marker.get_editor_property("locked"))
        except Exception:
            pass
        rows.append({"classification": classification, "label": str(marker.get_editor_property("label")),
                     "frame": frame(marker.get_editor_property("frame_number")) - origin, "locked": locked})
    return rows


def segments(show):
    transport = unreal.new_object(unreal.InfinityStageTransportController)
    transport.build_segments(show)
    return [{"label": str(row.get_editor_property("label")),
             "start": frame(row.get_editor_property("start_frame")),
             "end": frame(row.get_editor_property("end_frame"))}
            for row in transport.get_editor_property("segments")]


def passage_facts(show, compiled):
    cues = list(show.get_editor_property("cues"))
    cue_by_guid = {guid(row.get_editor_property("cue_guid")): index for index, row in enumerate(cues)}
    compiled_by_label = {row["label"]: row for row in compiled}
    output, origins = [], []
    for settings in show.get_editor_property("passage_settings"):
        label = str(settings.get_editor_property("label"))
        if label not in compiled_by_label:
            raise RuntimeError("PASSAGE_SEGMENT_MISSING|%s" % label)
        first = cue_by_guid.get(guid(settings.get_editor_property("first_cue_guid")))
        last = cue_by_guid.get(guid(settings.get_editor_property("last_cue_guid")))
        if first is None or last is None or last < first:
            raise RuntimeError("PASSAGE_CUE_RANGE|%s" % label)
        wings = cues[first:last + 1]
        wing_guids = [guid(row.get_editor_property("cue_guid")) for row in wings]
        seg = compiled_by_label[label]
        cursor = seg["start"]
        lead = frame(settings.get_editor_property("lead_in_frames"))
        spans = [{"kind": "lead_in", "index": 0, "start": cursor, "end": cursor + lead,
                  "duration": lead, "wing_before_guid": wing_guids[0], "wing_after_guid": wing_guids[0]}]
        cursor += lead
        for index, cue in enumerate(wings[:-1]):
            wing = cue.get_editor_property("wing_pair")
            duration = frame(wing.get_editor_property("interval_to_next"))
            spans.append({"kind": "interval", "index": index, "start": cursor, "end": cursor + duration,
                          "duration": duration, "wing_before_guid": wing_guids[index],
                          "wing_after_guid": wing_guids[index + 1]})
            cursor += duration
        tail = frame(settings.get_editor_property("tail_frames"))
        spans.append({"kind": "tail", "index": 0, "start": cursor, "end": cursor + tail, "duration": tail,
                      "wing_before_guid": wing_guids[-1], "wing_after_guid": wing_guids[-1]})
        if cursor + tail != seg["end"]:
            raise RuntimeError("PASSAGE_SPAN_SUM|%s" % label)
        output.append({"guid": guid(settings.get_editor_property("passage_guid")), "label": label,
                       "start": seg["start"], "end": seg["end"], "linear_spans": spans})
        for cue in wings:
            wing = cue.get_editor_property("wing_pair")
            mechanism = wing.get_editor_property("mechanism")
            explicit = "EXPLICIT" in str(mechanism.get_editor_property("phase_origin")).upper()
            origins.append({"classification": "mechanism_origin", "cue_guid": guid(cue.get_editor_property("cue_guid")),
                            "explicit": explicit, "frame": frame(mechanism.get_editor_property("explicit_origin_frame"))})
    return output, origins


def find_passage_section(master, passage_guid):
    hits = []
    for track in master.get_tracks():
        if track.get_class().get_name() != "MovieSceneInfinityPassageTrack":
            continue
        for section in track.get_sections():
            if guid(section.get_editor_property("passage_guid")) == passage_guid:
                hits.append(section)
    if len(hits) != 1:
        raise RuntimeError("PASSAGE_SECTION_COUNT|%s|%d" % (passage_guid, len(hits)))
    return hits[0]


def _external_cue_rows_must_be_empty():
    path = os.path.join(os.path.abspath(unreal.Paths.project_dir()), "Docs", "CueSheet", "working.csv")
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    active = [row for row in rows if str(row.get("At", "")).strip() or str(row.get("GO", "")).strip()]
    if active:
        raise RuntimeError("EXTERNAL_CUE_AT_GO_ROWS_REQUIRE_NAMED_FILE_TRANSACTION|%d" % len(active))
    return []


def snapshot_provider(_ue, args):
    show = unreal.load_asset(args["show_package"])
    master = unreal.load_asset(args["master_package"])
    choreo = unreal.load_asset(args["choreo_package"])
    wrapper = unreal.load_asset(args["render_wrapper_package"])
    if None in (show, master, choreo, wrapper):
        raise RuntimeError("NAMED_ASSET_LOAD_FAILED")
    tick = rate(show.get_editor_property("tick_resolution"))
    if abs(rate(master.get_tick_resolution()) - tick) > 1.0e-9 or abs(rate(choreo.get_tick_resolution()) - tick) > 1.0e-9:
        raise RuntimeError("TICK_RESOLUTION_MISMATCH")
    compiled = segments(show)
    passages, origins = passage_facts(show, compiled)
    target_guid = args["passage_guid"]
    passage_sections = {}
    target_section = find_passage_section(master, target_guid)
    passage_sections[target_guid] = {
        "range": section_range(target_section, tick), "channels": channel_rows(target_section),
        "pinned_passage_frames": [frame(x) for x in target_section.get_editor_property("pinned_passage_frames")],
        "pinned_wing_cue_guids": sorted(guid(x) for x in target_section.get_editor_property("pinned_wing_cue_guids")),
    }
    show_guid = guid(show.get_editor_property("show_guid"))
    root_tracks, binding_tracks, cuts, managed_sections, music_sections = [], [], [], [], []
    for host, binding_guid, index, track in all_tracks(master):
        cls = track.get_class().get_name()
        is_managed = False
        if host == "root" and cls in MANAGED:
            try:
                is_managed = guid(track.get_editor_property("owner_guid")) == show_guid
            except Exception:
                is_managed = False
        if is_managed:
            for section in track.get_sections():
                block = guid(section.get_editor_property("block_guid"))
                classification = "master_managed" if block == target_guid else "later_passage_managed"
                row = {"classification": classification, "passage_guid": block,
                       "range": section_range(section, tick)}
                managed_sections.append(row)
                if cls == "MovieSceneInfinityAudioTrack":
                    music_sections.append(row["range"])
            continue
        if cls == "MovieSceneCameraCutTrack":
            row = track_row(args["master_package"], host, binding_guid, index, track,
                            "master_camera_cut", tick)
            cuts += [dict(section, classification="master_camera_cut") for section in row["sections"]]
            continue
        classification = "master_artist_root" if host == "root" else "master_artist_binding"
        target = root_tracks if host == "root" else binding_tracks
        target.append(track_row(args["master_package"], host, binding_guid, index, track,
                                classification, tick))
    choreo_tracks = []
    for host, binding_guid, index, track in all_tracks(choreo):
        choreo_tracks.append(track_row(args["choreo_package"], host, binding_guid, index, track,
                                       "changed_choreo_track", tick))
    wrapper_cuts, wrapper_sources = [], []
    for host, binding_guid, index, track in all_tracks(wrapper):
        if track.get_class().get_name() == "MovieSceneCameraCutTrack":
            row = track_row(args["render_wrapper_package"], host, binding_guid, index, track,
                            "render_wrapper_cut", tick)
            wrapper_cuts += [dict(section, classification="render_wrapper_cut") for section in row["sections"]]
        elif track.get_class().get_name() == "MovieSceneSubTrack":
            row = track_row(args["render_wrapper_package"], host, binding_guid, index, track,
                            "render_wrapper_cut", tick)
            wrapper_sources += [{"range": section["range"], "locator": section["locator"]}
                                for section in row["sections"]]
    target_setting = [row for row in show.get_editor_property("passage_settings")
                      if guid(row.get_editor_property("passage_guid")) == target_guid]
    if len(target_setting) != 1:
        raise RuntimeError("PASSAGE_SETTING_COUNT|%d" % len(target_setting))
    binding = target_setting[0].get_editor_property("music")
    rail_guid = guid(binding.get_editor_property("primary_rail_guid"))
    rails = list(show.get_editor_property("music_rails"))
    rail_hits = [(index, row) for index, row in enumerate(rails)
                 if guid(row.get_editor_property("rail_guid")) == rail_guid]
    if len(rail_hits) != 1:
        raise RuntimeError("MUSIC_RAIL_COUNT|%d" % len(rail_hits))
    rail_index, rail = rail_hits[0]
    analysis = unreal.load_asset(args["analysis_map_path"])
    sound = unreal.load_asset(args["rendered_sound_path"])
    if analysis is None or sound is None:
        raise RuntimeError("RENDERED_SOUND_OR_ANALYSIS_MISSING")
    with open(args["audio_apply_record"], "r", encoding="utf-8") as handle:
        audio_record = json.load(handle)
    wav_states = [state for path, state in audio_record.get("target_after", {}).items()
                  if path.lower().endswith(".wav")]
    if len(wav_states) != 1:
        raise RuntimeError("AUDIO_RECORD_WAV_COUNT|%d" % len(wav_states))
    wav_hash = str(wav_states[0].get("sha256", ""))
    analysis_sound = asset_path(analysis.get_editor_property("sound"))
    analysis_hash = str(analysis.get_editor_property("source_sha256"))
    existing = []
    speed = passage_sections[target_guid]["channels"].get("Camera.SpeedMultiplier", [])
    zeros = [time for time, value in speed if abs(float(value)) <= 1.0e-6]
    if len(zeros) >= 2:
        existing = [{"start": zeros[index], "end": zeros[index + 1], "source": "speed-zero-keys"}
                    for index in range(0, len(zeros) - 1, 2)]
    holders = [{"classification": name} for name in (
        "changed_passage_channels", "changed_passage_pins", "later_passage_managed", "master_managed",
        "master_artist_root", "master_artist_binding", "master_camera_cut", "master_marker",
        "changed_choreo_track", "changed_choreo_marker", "mechanism_origin", "managed_music",
        "cue_at_go", "render_wrapper_cut")]
    return {
        "tick_resolution": tick, "display_rate": rate(show.get_editor_property("display_rate")),
        "passages": passages, "passage_sections": passage_sections,
        "master": {"playback": [ticks(master.get_playback_start_seconds(), tick),
                                  ticks(master.get_playback_end_seconds(), tick)],
                   "root_tracks": root_tracks, "binding_tracks": binding_tracks, "camera_cuts": cuts,
                   "markers": markers(master, 0, "master_marker"), "managed_sections": managed_sections},
        "changed_choreo": {"package": args["choreo_package"],
                           "playback": [ticks(choreo.get_playback_start_seconds(), tick),
                                        ticks(choreo.get_playback_end_seconds(), tick)],
                           "tracks": choreo_tracks, "markers": markers(choreo, 0, "changed_choreo_marker")},
        "mechanism_origins": origins, "cue_rows": _external_cue_rows_must_be_empty(),
        "managed_music": {"classification": "managed_music", "rail_index": rail_index,
                          "sound": asset_path(rail.get_editor_property("sound")),
                          "analysis": asset_path(rail.get_editor_property("analysis_map")),
                          "sections": music_sections,
                          "import_validation": {"sound": asset_path(sound), "analysis": asset_path(analysis),
                              "audio_record_run": audio_record.get("run_id"), "rendered_wav_sha256": wav_hash,
                              "analysis_source_wav_sha256": analysis_hash,
                              "stale": analysis_sound != asset_path(sound) or analysis_hash != wav_hash}},
        "render_wrapper": {"package": args["render_wrapper_package"],
                           "playback": [ticks(wrapper.get_playback_start_seconds(), tick),
                                        ticks(wrapper.get_playback_end_seconds(), tick)],
                           "source_sections": wrapper_sources, "cuts": wrapper_cuts},
        "existing_breaths": existing, "holders": holders,
    }


def _sequence(package):
    value = unreal.load_asset(package)
    if value is None:
        raise RuntimeError("SEQUENCE_LOAD_FAILED|%s" % package)
    return value


def _resolve_section(locator):
    sequence = _sequence(locator["package"])
    if locator["host"] == "root":
        tracks = list(sequence.get_tracks())
    else:
        bindings = [row for row in sequence.get_bindings() if guid(row.get_id()) == locator["binding_guid"]]
        if len(bindings) != 1:
            raise RuntimeError("BINDING_LOCATOR|%s" % locator)
        tracks = list(bindings[0].get_tracks())
    try:
        return sequence, tracks[int(locator["track_index"])].get_sections()[int(locator["section_index"])]
    except Exception as error:
        raise RuntimeError("SECTION_LOCATOR|%s|%s" % (locator, error))


def _channel(section, name):
    rows = [row for row in section.get_all_channels()
            if str(row.get_editor_property("channel_name")) == name]
    if len(rows) != 1:
        raise RuntimeError("CHANNEL_COUNT|%s|%d" % (name, len(rows)))
    return rows[0]


def _move_keys(section, threshold, delta):
    for channel in section.get_all_channels():
        for key in channel.get_keys():
            old = frame(key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number)
            if old >= threshold:
                key.set_time(unreal.FrameNumber(old + delta), sub_frame=0.0,
                             time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)


def _set_section_range(section, row, tick):
    section.set_range_seconds(float(row[0]) / tick, float(row[1]) / tick)


def _set_marker(sequence, label, new_frame):
    index = sequence.find_marked_frame_by_label(label)
    if int(index) < 0:
        raise RuntimeError("MARKER_NOT_FOUND|%s" % label)
    rows = list(sequence.get_marked_frames())
    marker = rows[int(index)]
    sequence.delete_marked_frame(int(index))
    marker.set_editor_property("frame_number", unreal.FrameNumber(int(new_frame)))
    sequence.add_marked_frame(marker)


def _replace_channels(section, desired):
    live = {str(row.get_editor_property("channel_name")): row for row in section.get_all_channels()}
    if set(live) != set(desired):
        raise RuntimeError("RESTORE_CHANNEL_SET|live=%s|wanted=%s" % (sorted(live), sorted(desired)))
    for name, rows in desired.items():
        channel = live[name]
        for key in list(channel.get_keys()):
            channel.remove_key(key)
        for when, value in rows:
            channel.add_key(unreal.FrameNumber(int(when)), float(value),
                            time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
                            interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)


def _restore_track_rows(track_rows, tick):
    for track in track_rows:
        for wanted in track.get("sections", []):
            _sequence_obj, section = _resolve_section(wanted["locator"])
            _set_section_range(section, wanted["range"], tick)
            _replace_channels(section, {row["name"]: row.get("keys", []) for row in wanted.get("channels", [])})


def _restore_markers(sequence, wanted):
    current = {str(row.get_editor_property("label")) for row in sequence.get_marked_frames()}
    labels = {row["label"] for row in wanted}
    if current != labels:
        raise RuntimeError("RESTORE_MARKER_LABEL_SET|live=%s|wanted=%s" % (sorted(current), sorted(labels)))
    for row in wanted:
        _set_marker(sequence, row["label"], row["frame"])


def _restore_snapshot(snapshot, args):
    show = unreal.load_asset(args["show_package"])
    master = unreal.load_asset(args["master_package"])
    choreo = unreal.load_asset(args["choreo_package"])
    wrapper = unreal.load_asset(args["render_wrapper_package"])
    tick = rate(show.get_editor_property("tick_resolution"))
    wanted_passage = [row for row in snapshot["passages"] if row["guid"] == args["passage_guid"]][0]
    settings = [row for row in show.get_editor_property("passage_settings")
                if guid(row.get_editor_property("passage_guid")) == args["passage_guid"]][0]
    spans = wanted_passage["linear_spans"]
    settings.set_editor_property("lead_in_frames", unreal.FrameNumber([row for row in spans if row["kind"] == "lead_in"][0]["duration"]))
    settings.set_editor_property("tail_frames", unreal.FrameNumber([row for row in spans if row["kind"] == "tail"][0]["duration"]))
    cues = list(show.get_editor_property("cues"))
    first_guid = guid(settings.get_editor_property("first_cue_guid"))
    first = [index for index, row in enumerate(cues) if guid(row.get_editor_property("cue_guid")) == first_guid][0]
    for row in [value for value in spans if value["kind"] == "interval"]:
        wing = cues[first + int(row["index"])].get_editor_property("wing_pair")
        wing.set_editor_property("interval_to_next", unreal.FrameNumber(int(row["duration"])))
    target = snapshot["passage_sections"][args["passage_guid"]]
    section = find_passage_section(master, args["passage_guid"])
    _replace_channels(section, target["channels"])
    _set_section_range(section, target["range"], tick)
    section.set_editor_property("pinned_passage_frames", [unreal.FrameNumber(int(x)) for x in target["pinned_passage_frames"]])
    by_guid = {guid(row.get_editor_property("cue_guid")): row.get_editor_property("cue_guid") for row in cues}
    section.set_editor_property("pinned_wing_cue_guids", [by_guid[text] for text in target["pinned_wing_cue_guids"]])
    _restore_track_rows(snapshot["master"]["root_tracks"], tick)
    _restore_track_rows(snapshot["master"]["binding_tracks"], tick)
    _restore_track_rows([{"sections": snapshot["master"]["camera_cuts"]}], tick)
    _restore_markers(master, snapshot["master"]["markers"])
    _restore_track_rows(snapshot["changed_choreo"]["tracks"], tick)
    _restore_markers(choreo, snapshot["changed_choreo"]["markers"])
    choreo.set_playback_start_seconds(float(snapshot["changed_choreo"]["playback"][0]) / tick)
    choreo.set_playback_end_seconds(float(snapshot["changed_choreo"]["playback"][1]) / tick)
    for row in snapshot["mechanism_origins"]:
        if row.get("explicit"):
            hit = [cue for cue in cues if guid(cue.get_editor_property("cue_guid")) == row["cue_guid"]][0]
            hit.get_editor_property("wing_pair").get_editor_property("mechanism").set_editor_property(
                "explicit_origin_frame", unreal.FrameNumber(int(row["frame"])))
    rail_index = int(snapshot["managed_music"]["rail_index"])
    rails = list(show.get_editor_property("music_rails"))
    rails[rail_index].set_editor_property("sound", unreal.load_asset(snapshot["managed_music"]["sound"]))
    rails[rail_index].set_editor_property("analysis_map", unreal.load_asset(snapshot["managed_music"]["analysis"]))
    analysis = unreal.load_asset(args["analysis_map_path"])
    analysis.modify()
    analysis.set_editor_property("sound", unreal.load_asset(args["rendered_sound_path"]))
    _restore_track_rows([{"sections": snapshot["render_wrapper"]["cuts"]}], tick)
    for row in snapshot["render_wrapper"]["source_sections"]:
        _sequence_obj, source = _resolve_section(row["locator"])
        _set_section_range(source, row["range"], tick)
    wrapper.set_playback_start_seconds(float(snapshot["render_wrapper"]["playback"][0]) / tick)
    wrapper.set_playback_end_seconds(float(snapshot["render_wrapper"]["playback"][1]) / tick)
    return {"restored_snapshot": True}


def edit_executor(_ue, edits, args):
    show = unreal.load_asset(args["show_package"])
    master = unreal.load_asset(args["master_package"])
    choreo = unreal.load_asset(args["choreo_package"])
    wrapper = unreal.load_asset(args["render_wrapper_package"])
    tick = rate(show.get_editor_property("tick_resolution"))
    passage = find_passage_section(master, args["passage_guid"])
    if len(edits) == 1 and edits[0].get("op") == "restore_snapshot":
        return _restore_snapshot(edits[0]["snapshot"], args)
    for edit in edits:
        op = edit["op"]
        if op == "extend_show_timing_span":
            settings = [row for row in show.get_editor_property("passage_settings")
                        if guid(row.get_editor_property("passage_guid")) == edit["passage_guid"]][0]
            if edit["kind"] == "lead_in":
                settings.set_editor_property("lead_in_frames", unreal.FrameNumber(edit["new"]))
            elif edit["kind"] == "tail":
                settings.set_editor_property("tail_frames", unreal.FrameNumber(edit["new"]))
            else:
                cues = list(show.get_editor_property("cues"))
                first_guid = guid(settings.get_editor_property("first_cue_guid"))
                first = [i for i, row in enumerate(cues) if guid(row.get_editor_property("cue_guid")) == first_guid][0]
                wing = cues[first + int(edit["index"])].get_editor_property("wing_pair")
                wing.set_editor_property("interval_to_next", unreal.FrameNumber(edit["new"]))
        elif op == "ripple_passage_channel":
            channel = _channel(passage, edit["channel"])
            for key in channel.get_keys():
                old = frame(key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number)
                if old >= edit["threshold"]:
                    key.set_time(unreal.FrameNumber(old + edit["delta"]), sub_frame=0.0,
                                 time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
        elif op == "add_breath_channel_keys":
            channel = _channel(passage, edit["channel"])
            wanted = {int(row[0]) for row in edit["keys"]}
            for key in list(channel.get_keys()):
                old = frame(key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number)
                if old in wanted:
                    channel.remove_key(key)
            for when, value in edit["keys"]:
                channel.add_key(unreal.FrameNumber(int(when)), float(value),
                                time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
                                interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        elif op == "ripple_relative_pins":
            values = [frame(x) for x in passage.get_editor_property("pinned_passage_frames")]
            passage.set_editor_property("pinned_passage_frames", [unreal.FrameNumber(x + edit["delta"] if x >= edit["threshold"] else x)
                                                                  for x in values])
        elif op == "ensure_bounding_wing_pins":
            pins = list(passage.get_editor_property("pinned_wing_cue_guids"))
            cues = list(show.get_editor_property("cues"))
            by_text = {guid(row.get_editor_property("cue_guid")): row.get_editor_property("cue_guid") for row in cues}
            for text in edit["guids"]:
                if text not in by_text:
                    raise RuntimeError("BOUNDING_WING_GUID_MISSING|%s" % text)
                if text not in {guid(row) for row in pins}:
                    pins.append(by_text[text])
            passage.set_editor_property("pinned_wing_cue_guids", pins)
        elif op in ("move_section", "extend_and_ripple_section"):
            _seq, section = _resolve_section(edit["locator"])
            old = section_range(section, tick)
            if op == "move_section":
                _move_keys(section, -10**30, edit["delta"])
                _set_section_range(section, [old[0] + edit["delta"], old[1] + edit["delta"]], tick)
            else:
                _move_keys(section, edit["threshold"], edit["delta"])
                _set_section_range(section, [old[0], old[1] + edit["delta"]], tick)
        elif op == "move_marker_by_label":
            sequence = master if edit["scope"] == "master" else choreo
            _set_marker(sequence, edit["label"], edit["to"])
        elif op == "extend_choreo_playback":
            choreo.set_playback_end_seconds(choreo.get_playback_end_seconds() + edit["delta"] / tick)
        elif op == "move_explicit_mechanism_origin":
            cues = list(show.get_editor_property("cues"))
            hits = [row for row in cues if guid(row.get_editor_property("cue_guid")) == edit["cue_guid"]]
            if len(hits) != 1:
                raise RuntimeError("MECHANISM_CUE_COUNT|%d" % len(hits))
            mechanism = hits[0].get_editor_property("wing_pair").get_editor_property("mechanism")
            mechanism.set_editor_property("explicit_origin_frame", unreal.FrameNumber(edit["to"]))
        elif op == "move_cue_row":
            raise RuntimeError("CUE_ROW_EDIT_UNSUPPORTED_AFTER_NONEMPTY_CENSUS")
        elif op == "set_managed_music":
            rails = list(show.get_editor_property("music_rails"))
            settings = [row for row in show.get_editor_property("passage_settings")
                        if guid(row.get_editor_property("passage_guid")) == args["passage_guid"]][0]
            target = guid(settings.get_editor_property("music").get_editor_property("primary_rail_guid"))
            hits = [row for row in rails if guid(row.get_editor_property("rail_guid")) == target]
            if len(hits) != 1:
                raise RuntimeError("MUSIC_RAIL_COUNT|%d" % len(hits))
            hits[0].set_editor_property("sound", unreal.load_asset(edit["sound"]))
            hits[0].set_editor_property("analysis_map", unreal.load_asset(edit["analysis"]))
            analysis = unreal.load_asset(args["analysis_map_path"])
            analysis.modify()
            analysis.set_editor_property("sound", unreal.load_asset(edit["sound"]))
        elif op == "rebuild_render_wrapper":
            _sequence_obj, source = _resolve_section(edit["source_locator"])
            _set_section_range(source, edit["source_range"], tick)
            wrapper.set_playback_start_seconds(float(edit["playback"][0]) / tick)
            wrapper.set_playback_end_seconds(float(edit["playback"][1]) / tick)
        elif op in ("rebuild_managed_master", "materialize_changed_passage", "check_adjacent_handoffs"):
            pass  # performed and checked by UnrealBackend
        else:
            raise RuntimeError("UNKNOWN_EDIT_OP|%s" % op)
    return {"executed_edits": len(edits)}
