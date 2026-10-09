"""P33: make all six Passage lengths equal their selected music lengths.

[declaration-proven] The only Show fields written are LeadInFrames,
IntervalToNext, and TailFrames.  They are scaled by one factor and the final
rounding residual is absorbed in TailFrames; see plan_scaled_timing() and
_write_timing() in passage_retime_to_music.py.

[declaration-proven] The target is the P11 selected music duration, rounded up
to a whole Show display frame, plus an explicit per-Passage tail override.
Every shipped override is zero.  The live rail is checked, but P06 deliberately
uses the measured 110.561125 s interval rather than silently accepting its
unused 125 s WAV tail.

[declaration-proven] Passage-section channel keys are not scaled.  The managed
Master rebuild carries them with their section start; relative_key_carry_gate()
proves their local ticks and numeric values survive.  DRY lists every absolute
Passage key, plus every key, section, marker, pin, and Choreo item at or beyond
the proposed end.  Anything stranded requires an explicit KEEP_UNPLAYED action;
unmanaged Master content requires KEEP_ABSOLUTE.  APPLY must carry the exact DRY
review hash.  Relative pins cannot be accepted because the rebuild deletes pins
outside the new range.

[declaration-proven] APPLY and REVERT each back up Show + Master, create a
record before mutation, rebuild the Master exactly once, require the exact
dirty-package set, save only Show + Master, load/read back, and emit a run-id
success marker.  DRY mutates no Unreal package.  This file is offline-written;
the conductor runs it later through passages_to_music_run.py.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import math
import os
import shutil


def _load_legacy():
    """Load the proven retime readers/gates without running its Unreal main."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "passage_retime_to_music.py")
    spec = importlib.util.spec_from_file_location("_p33_passage_retime_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("LEGACY_HELPERS_UNAVAILABLE|%s" % path)
    module = importlib.util.module_from_spec(spec)
    module.RETIME_IMPORT_ONLY = True
    spec.loader.exec_module(module)
    return module


base = _load_legacy()
unreal = base.unreal
PlanError = base.PlanError

TOOL = "passages_to_music"
MARK = "PASSAGES_TO_MUSIC"
SHOW_PATH = base.SHOW_PATH
MASTER_PATH = base.MASTER_PATH
EXPECTED_WORLD = base.EXPECTED_WORLD
ARGS_NAME = "passages_to_music_args.json"
DRY_NAME = "passages_to_music_dry.json"
RECORD_NAME = "passages_to_music_record.json"
VALID_KEYS = ("1", "2", "3", "4", "5", "6")
CONFIRMS = {m: "%s PASSAGES TO MUSIC" % m for m in ("DRY", "APPLY", "REVERT")}
SONG_TOL_S = 0.002


def label_of(key):
    return "Passage %s" % key


def _number(value, minimum=0.0):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= minimum


def tail_override_s(args, key):
    return float((args.get("tail_overrides_s") or {}).get(key, 0.0))


def validate_args(args):
    out = []
    mode = str(args.get("mode") or "").upper()
    if mode not in CONFIRMS:
        out.append("MODE_INVALID: %r" % args.get("mode"))
    keys = args.get("passages")
    if keys != list(VALID_KEYS):
        out.append("PASSAGES_MUST_BE_ALL_SIX_IN_ORDER: %r" % keys)
        keys = []
    tails = args.get("tail_overrides_s") or {}
    if not isinstance(tails, dict) or any(k not in VALID_KEYS for k in tails):
        out.append("TAIL_OVERRIDES_INVALID: %r" % tails)
    else:
        for k in VALID_KEYS:
            if not _number(tails.get(k, 0.0)):
                out.append("TAIL_OVERRIDE_INVALID: P%s %r" % (k, tails.get(k)))
    per = args.get("per_passage") or {}
    for key in keys:
        row = per.get(key)
        if not isinstance(row, dict):
            out.append("PER_PASSAGE_MISSING: P%s" % key)
            continue
        if not str(row.get("guid") or "").strip():
            out.append("GUID_MISSING: P%s" % key)
        if not _number(row.get("music_s"), 0.001):
            out.append("MUSIC_SECONDS_INVALID: P%s %r" % (key, row.get("music_s")))
        if not str(row.get("sound") or "").startswith("/Game/"):
            out.append("SOUND_INVALID: P%s" % key)
        if mode == "APPLY":
            expected = row.get("expected") or {}
            for field in ("old_len_ticks", "new_len_ticks", "music_ticks"):
                if not isinstance(expected.get(field), int) or isinstance(expected.get(field), bool) or expected[field] <= 0:
                    out.append("EXPECTED_%s_MISSING: P%s" % (field.upper(), key))
    review = args.get("review") or {}
    if mode == "APPLY":
        if not str(review.get("inventory_sha256") or "").strip():
            out.append("REVIEW_HASH_MISSING")
        if not str(args.get("decided_by") or "").strip():
            out.append("DECIDED_BY_MISSING")
    actions = review.get("past_end_actions") or {}
    if not isinstance(actions, dict):
        out.append("PAST_END_ACTIONS_INVALID")
    return out


def target_ticks(music_s, extra_tail_s, tick_rate, fps_num, fps_den):
    return base.target_ticks(music_s, extra_tail_s, tick_rate, fps_num, fps_den)


def plan_scaled_timing(lead, intervals, tail, target):
    return base.plan_scaled_timing(lead, intervals, tail, target)


def compiled_length(lead, intervals, tail):
    return base.compiled_length(lead, intervals, tail)


def _value_tolerance(channel):
    name = str(channel).lower()
    return 0.001 if any(x in name for x in ("yaw", "pitch", "roll", "rotation", "degrees")) else 0.01


def _values_equal(channel, before, after):
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return abs(float(before) - float(after)) <= _value_tolerance(channel)
    return before == after


def relative_key_carry_gate(before, after, spans):
    """Prove local key ticks and float values survive; never hash rounded values."""
    failures = []
    if sorted(before) != sorted(after):
        return ["PASSAGE_SECTION_SET_CHANGED: %r -> %r" % (sorted(before), sorted(after))]
    for guid in sorted(before):
        old, new = before[guid], after[guid]
        shift = base.shift_at(old["start"], spans)
        if shift is None or int(new["start"]) != int(old["start"]) + int(shift):
            failures.append("PASSAGE_SECTION_START_WRONG: %s" % guid)
            continue
        if sorted(old.get("channels") or {}) != sorted(new.get("channels") or {}):
            failures.append("PASSAGE_CHANNEL_SET_CHANGED: %s" % guid)
            continue
        for channel in sorted(old.get("channels") or {}):
            a = old["channels"][channel]
            b = new["channels"][channel]
            if len(a) != len(b):
                failures.append("PASSAGE_KEY_COUNT_CHANGED: %s %s" % (guid, channel))
                continue
            for index, (left, right) in enumerate(zip(a, b)):
                old_local = int(left[0]) - int(old["start"])
                new_local = int(right[0]) - int(new["start"])
                if old_local != new_local:
                    failures.append("PASSAGE_KEY_LOCAL_TICK_CHANGED: %s %s #%d %d->%d" % (
                        guid, channel, index, old_local, new_local))
                if not _values_equal(channel, left[1], right[1]):
                    failures.append("PASSAGE_KEY_VALUE_CHANGED: %s %s #%d %r->%r tol=%g" % (
                        guid, channel, index, left[1], right[1], _value_tolerance(channel)))
        if list(old.get("pins_rel") or []) != list(new.get("pins_rel") or []):
            failures.append("PASSAGE_RELATIVE_PINS_CHANGED: %s" % guid)
        if sorted(old.get("wing_pins") or []) != sorted(new.get("wing_pins") or []):
            failures.append("PASSAGE_WING_PINS_CHANGED: %s" % guid)
    return failures


def _item_id(passage, kind, owner, tick, ordinal):
    clean = str(owner).replace("|", "/")
    return "%s|%s|%s|%s|%d" % (passage, kind, clean, str(tick), ordinal)


def build_inventory(passage, segment, section_keys, choreo, artist_rows, root_markers, managed, new_len):
    """Return a complete, plain-data inventory for the old tail cut by new_len."""
    start, old_end = int(segment["start"]), int(segment["end"])
    new_end = start + int(new_len)
    result = {
        "newEndInOldCoordinates": new_end,
        "absolutePassageKeys": [],
        "relativePins": [],
        "pastNewEnd": {
            "passageChannelKeys": [], "relativePins": [], "masterSections": [], "masterMarkers": [],
            "masterArtistKeys": [], "choreoKeys": [], "choreoSections": [], "choreoMarkers": []},
    }
    section_origin = int((section_keys or {}).get("start", start))
    for channel, rows in sorted(((section_keys or {}).get("channels") or {}).items()):
        for ordinal, pair in enumerate(rows):
            tick, value = int(pair[0]), pair[1]
            local = tick - section_origin
            row = {"id": _item_id(passage, "passage-key", channel, local, ordinal), "channel": channel,
                   "absoluteTick": tick, "sectionLocalTick": local, "value": value, "pastNewEnd": local >= int(new_len)}
            result["absolutePassageKeys"].append(row)
            if row["pastNewEnd"]:
                result["pastNewEnd"]["passageChannelKeys"].append(row)
    for ordinal, tick in enumerate((section_keys or {}).get("pins_rel") or []):
        row = {"id": _item_id(passage, "relative-pin", "PinnedPassageFrames", int(tick), ordinal),
               "localTick": int(tick), "pastNewEnd": int(tick) >= int(new_len)}
        result["relativePins"].append(row)
        if row["pastNewEnd"]:
            result["pastNewEnd"]["relativePins"].append(row)
    for name, bounds in sorted((managed or {}).items()):
        s, e = bounds
        overlaps = (s is None or int(s) < old_end) and (e is None or int(e) > new_end)
        if overlaps:
            result["pastNewEnd"]["masterSections"].append({
                "id": _item_id(passage, "managed-section", name, new_end, len(result["pastNewEnd"]["masterSections"])),
                "managed": True, "name": name, "start": s, "end": e, "expectedAction": "rebuilt-or-carried"})
    for row in artist_rows or []:
        owner = "%s/%s/%s" % (row.get("owner"), row.get("class"), row.get("track"))
        for ordinal, tick in enumerate(row.get("keys") or []):
            if new_end <= int(tick) < old_end:
                result["pastNewEnd"]["masterArtistKeys"].append({
                    "id": _item_id(passage, "artist-key", owner, int(tick), ordinal), "owner": owner,
                    "absoluteTick": int(tick), "passageLocalTick": int(tick) - start})
        for ordinal, bounds in enumerate(row.get("sections") or []):
            s, e = bounds
            overlaps = (s is None or int(s) < old_end) and (e is None or int(e) > new_end)
            if overlaps:
                result["pastNewEnd"]["masterSections"].append({
                    "id": _item_id(passage, "artist-section", owner, new_end, ordinal), "managed": False,
                    "owner": owner, "start": s, "end": e, "expectedAction": "absolute-not-rippled"})
    for ordinal, marker in enumerate(root_markers or []):
        label, tick = marker
        if new_end <= int(tick) < old_end:
            result["pastNewEnd"]["masterMarkers"].append({
                "id": _item_id(passage, "master-marker", label, int(tick), ordinal), "label": label,
                "absoluteTick": int(tick), "passageLocalTick": int(tick) - start})
    if choreo:
        choreo_end = int(choreo.get("start_offset", 0)) + int(new_len)
        for ordinal, pair in enumerate(choreo.get("keys") or []):
            where, tick = pair
            if int(tick) >= choreo_end:
                result["pastNewEnd"]["choreoKeys"].append({
                    "id": _item_id(passage, "choreo-key", where, int(tick), ordinal), "where": where,
                    "localTick": int(tick), "newChoreoEnd": choreo_end})
        for ordinal, section in enumerate(choreo.get("sections") or []):
            s, e = section.get("start"), section.get("end")
            if (s is not None and int(s) >= choreo_end) or (e is None) or (e is not None and int(e) > choreo_end):
                result["pastNewEnd"]["choreoSections"].append(dict(section, id=_item_id(
                    passage, "choreo-section", section.get("where"), s if s is not None else "open", ordinal),
                    newChoreoEnd=choreo_end))
        for ordinal, marker in enumerate(choreo.get("markers") or []):
            label, tick = marker
            if int(tick) >= choreo_end:
                result["pastNewEnd"]["choreoMarkers"].append({
                    "id": _item_id(passage, "choreo-marker", label, int(tick), ordinal), "label": label,
                    "localTick": int(tick), "newChoreoEnd": choreo_end})
    result["pastCount"] = sum(len(rows) for rows in result["pastNewEnd"].values())
    return result


def review_groups(passage, inventory):
    groups = {}
    late = inventory["pastNewEnd"]
    for row in late["passageChannelKeys"]:
        groups.setdefault("%s:passage_channel:%s" % (passage, row["channel"]), []).append(row["id"])
    if late["relativePins"]:
        groups["%s:relative_pins" % passage] = [r["id"] for r in late["relativePins"]]
    for category in ("masterMarkers", "masterArtistKeys", "choreoKeys", "choreoSections", "choreoMarkers"):
        if late[category]:
            groups["%s:%s" % (passage, category)] = [r["id"] for r in late[category]]
    unmanaged = [r for r in late["masterSections"] if not r.get("managed")]
    if unmanaged:
        groups["%s:masterArtistSections" % passage] = [r["id"] for r in unmanaged]
    return groups


def review_refusals(groups, actions):
    refusals, notes = [], []
    for group, ids in sorted(groups.items()):
        action = (actions or {}).get(group)
        if group.endswith(":relative_pins"):
            refusals.append("%s RELATIVE_PINS_MUST_BE_RESOLVED_BEFORE_APPLY: %s" % (group, ids))
            continue
        absolute = any(group.endswith(":" + suffix) for suffix in (
            "masterMarkers", "masterArtistKeys", "masterArtistSections"))
        wanted = "KEEP_ABSOLUTE" if absolute else "KEEP_UNPLAYED"
        if action != wanted:
            refusals.append("%s PAST_END_UNRESOLVED: %d item(s); set review.past_end_actions[%r] to "
                            "%s only after Gary reviews the DRY" % (group, len(ids), group, wanted))
        else:
            effect = "remain at absolute Master time" if absolute else "remain stored but outside the shorter range"
            notes.append("%s REVIEWED_%s: %d item(s) %s" % (group, wanted, len(ids), effect))
    return refusals, notes


def p05_height_options(inventory, tick_rate, music_s):
    rows = [r for r in inventory["pastNewEnd"]["passageChannelKeys"] if r["channel"] == "Camera.HeightOffsetCm"]
    max_local = max([r["sectionLocalTick"] for r in rows], default=None)
    min_tail = None
    if max_local is not None:
        min_tail = max(0.0, (max_local + 1) / float(tick_rate) - float(music_s))
    return {
        "status": "hazard" if rows else "clear",
        "lateKeys": rows,
        "options": [
            {"name": "MOVE_RETURN_TO_NEW_END", "supportedByThisTool": False,
             "effect": "author the return at/before the new end in a separate backed-up pass, then rerun DRY"},
            {"name": "PROPORTIONAL_RETIME", "supportedByThisTool": False,
             "effect": "scale this absolute curve only after explicit artistic approval; never silent"},
            {"name": "DELETE_LATE_KEYS", "supportedByThisTool": False,
             "effect": "destructive key edit requires a separate record/backup and fresh DRY"},
            {"name": "TAIL_OVERRIDE", "supportedByThisTool": True, "minimumApproxSeconds": min_tail,
             "effect": "keeps the keys playable but explicitly makes P05 longer than music"},
            {"name": "KEEP_UNPLAYED", "supportedByThisTool": True,
             "effect": "keys remain stored at the same local ticks but are outside the shortened Passage"},
        ]}


def inventory_sha256(per_rows):
    payload = {k: {"old": r["old"], "plan": r["plan"], "music": r["music"],
                   "inventory": r["inventory"], "p05HeightOffset": r.get("p05HeightOffset")}
               for k, r in sorted(per_rows.items())}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def source_policy(key, music, selected_s, row, review):
    refusals, notes = [], []
    if music is None:
        return ["P%s MUSIC_UNREADABLE" % key], notes, None
    if not any(x in str(music.get("mode") or "").upper() for x in base.PLAYING_MODES):
        refusals.append("P%s MUSIC_NOT_PLAYING: %s" % (key, music.get("mode")))
    if music.get("sound") != row.get("sound"):
        refusals.append("P%s SOUND_CHANGED: %s != %s" % (key, music.get("sound"), row.get("sound")))
    source_ticks = int(music.get("source_out") or 0) - int(music.get("source_in") or 0)
    if source_ticks <= 0:
        refusals.append("P%s SOURCE_RANGE_INVALID" % key)
        return refusals, notes, None
    source_s = source_ticks / float(music["tick_rate"])
    unused = source_s - float(selected_s)
    if unused < -SONG_TOL_S:
        refusals.append("P%s SELECTED_MUSIC_EXCEEDS_LIVE_RAIL: %.6f > %.6f" % (key, selected_s, source_s))
    elif unused > SONG_TOL_S:
        action = (review.get("past_end_actions") or {}).get("P0%s:source_tail" % key)
        if action != "KEEP_UNUSED":
            refusals.append("P%s SOURCE_TAIL_UNDECIDED: %.6f s live rail - %.6f s selected = %.6f s; "
                            "review action P0%s:source_tail must be KEEP_UNUSED" % (key, source_s, selected_s, unused, key))
        else:
            notes.append("P%s SOURCE_TAIL_REVIEWED_KEEP_UNUSED: %.6f s" % (key, unused))
    if int(music.get("offset") or 0) != 0:
        refusals.append("P%s RAIL_OFFSET_NONZERO: %s" % (key, music.get("offset")))
    return refusals, notes, {"selectedSeconds": float(selected_s), "liveRailSeconds": source_s,
                             "unusedSourceTailSeconds": max(0.0, unused), "fadeInTicks": music.get("fade_in"),
                             "fadeOutTicks": music.get("fade_out"), "sound": music.get("sound")}


def expected_refusals(key, row, expected, mode):
    if mode != "APPLY":
        return []
    checks = {"old_len_ticks": row["plan"]["old_ticks"], "new_len_ticks": row["plan"]["new_ticks"],
              "music_ticks": row["music"]["selectedTicks"]}
    return ["P%s %s_CHANGED_SINCE_DRY: live %r args %r" % (key, field.upper(), value, expected.get(field))
            for field, value in checks.items() if expected.get(field) != value]


def exact_census_gate(census, expected_content):
    got = sorted(census.get("content") or [])
    want = sorted(expected_content)
    out = []
    if got != want:
        out.append("DIRTY_CONTENT_NOT_EXACT: got %r want %r" % (got, want))
    if census.get("maps"):
        out.append("DIRTY_MAPS: %r" % census["maps"])
    return out


def live_gates(state):
    out = []
    mode = str(state.get("mode") or "").upper()
    if state.get("confirm") != CONFIRMS.get(mode):
        out.append("CONFIRM_MISMATCH: got %r want %r" % (state.get("confirm"), CONFIRMS.get(mode)))
    if state.get("pie"):
        out.append("PIE_OR_SIE_ACTIVE")
    if state.get("sequencer_open"):
        out.append("SEQUENCER_IS_OPEN")
    if state.get("census") != {"content": [], "maps": []}:
        out.append("DIRTY_CENSUS: %s" % json.dumps(state.get("census"), sort_keys=True))
    if mode == "APPLY" and state.get("record_exists"):
        out.append("RECORD_EXISTS: %s" % RECORD_NAME)
    if mode == "REVERT" and not state.get("record_applied"):
        out.append("NO_APPLIED_RECORD: %s" % RECORD_NAME)
    return out


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _backup(run, suffix=""):
    folder = os.path.join(_project(), "Backups", "PrePassagesToMusic%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    rows = []
    for asset in (SHOW_PATH, MASTER_PATH):
        source = base._content_file(asset)
        target = os.path.join(folder, os.path.basename(source))
        shutil.copy2(source, target)
        with open(source, "rb") as handle:
            source_hash = hashlib.sha256(handle.read()).hexdigest()
        with open(target, "rb") as handle:
            target_hash = hashlib.sha256(handle.read()).hexdigest()
        if source_hash != target_hash:
            _stop(run, "BACKUP_HASH_MISMATCH|%s" % asset)
        rows.append({"asset": asset, "source": source, "backup": target, "sha256": target_hash})
    manifest = os.path.join(folder, "manifest.json")
    with open(manifest, "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": rows}, handle, indent=1)
        handle.flush()
        os.fsync(handle.fileno())
    return folder


def _plain(snapshot):
    return {k: snapshot[k] for k in ("timing", "segments", "managed", "keys")}


def _gather(args):
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_DID_NOT_LOAD")
    keys = list(VALID_KEYS)
    snap = base._snapshot(show, master, keys)
    tick = snap["tick"]
    rate = show.get_editor_property("display_rate")
    fps = (rate.numerator, rate.denominator)
    segments = {s["label"]: s for s in snap["segments"]}
    review = args.get("review") or {}
    actions = review.get("past_end_actions") or {}
    per_rows, facts, refusals, warnings = {}, {}, [], []
    if snap["dup"]:
        refusals.append("MANAGED_BLOCK_DUPLICATED: %s" % snap["dup"])
    for key in keys:
        label = label_of(key)
        fact = base._passage_facts(show, label)
        facts[key] = fact
        if fact["guid"] != args["per_passage"][key]["guid"]:
            refusals.append("P%s GUID_CHANGED: %s != %s" % (key, fact["guid"], args["per_passage"][key]["guid"]))
        segment = segments.get(label)
        if segment is None:
            raise PlanError("SEGMENT_MISSING: %s" % label)
        old_len = int(segment["end"]) - int(segment["start"])
        compiled = compiled_length(fact["lead"], fact["intervals"], fact["tail"])
        if old_len != compiled:
            refusals.append("P%s COMPILE_MODEL_MISMATCH: %d != %d" % (key, compiled, old_len))
        selected_s = float(args["per_passage"][key]["music_s"])
        extra = tail_override_s(args, key)
        target = target_ticks(selected_s, extra, tick, fps[0], fps[1])
        plan = plan_scaled_timing(fact["lead"], fact["intervals"], fact["tail"], target)
        rail = base._rail(show, fact["music_binding"]["rail"])
        music = dict(rail, mode=fact["music_binding"]["mode"], offset=fact["music_binding"]["offset"], tick_rate=tick) if rail else None
        source_bad, source_notes, audio = source_policy(key, music, selected_s, args["per_passage"][key], review)
        refusals += source_bad
        warnings += source_notes
        section_keys = snap["keys"].get(fact["guid"]) or {"start": segment["start"], "channels": {}, "pins_rel": [], "wing_pins": []}
        if fact["guid"] not in snap["keys"]:
            refusals.append("P%s MASTER_PASSAGE_SECTION_MISSING" % key)
        choreo = base._choreo_facts(fact["choreo_obj"], master, fact["guid"], tick)
        inventory = build_inventory("P0%s" % key, segment, section_keys, choreo, snap["artist"], snap["markers"],
                                    snap["managed"], plan["new_ticks"])
        groups = review_groups("P0%s" % key, inventory)
        r_review, w_review = review_refusals(groups, actions)
        refusals += r_review
        warnings += w_review
        if any(int(pin) >= plan["new_ticks"] for pin in section_keys.get("pins_rel") or []):
            refusals.append("P%s RELATIVE_PIN_WOULD_BE_DELETED_BY_REBUILD" % key)
        refusals += base.mechanism_refusals(key, fact.get("origins") or [])
        old_speed = base.speeds(fact["lead"], fact["intervals"], fact["tail"], fact["lead_cm"], fact["gaps"],
                                fact["tail_cm"], tick, 0.0)
        new_speed = base.speeds(plan["lead_frames"], plan["intervals"], plan["tail_frames"], fact["lead_cm"],
                                fact["gaps"], fact["tail_cm"], tick, 0.0)
        threshold = float(args.get("speed_warning_cm_s", 500.0))
        if new_speed.get("bay_max") and new_speed["bay_max"] > threshold:
            warnings.append("P%s SPEED_WARNING: %.3f cm/s > %.3f" % (key, new_speed["bay_max"], threshold))
        music_row = {"selectedSeconds": selected_s, "selectedTicks": int(round(selected_s * tick)),
                     "targetRoundedTicks": target, "tailOverrideSeconds": extra, "live": audio}
        row = {"key": key, "label": label, "guid": fact["guid"], "old": {"lenTicks": old_len,
               "lenSeconds": old_len / tick, "lead": fact["lead"], "intervals": fact["intervals"], "tail": fact["tail"]},
               "plan": plan, "music": music_row, "speedsOld": old_speed, "speedsNew": new_speed,
               "inventory": inventory, "reviewGroups": groups, "choreo": choreo}
        if key == "5":
            row["p05HeightOffset"] = p05_height_options(inventory, tick, selected_s)
        per_rows[key] = row
        refusals += expected_refusals(key, row, args["per_passage"][key].get("expected") or {}, str(args["mode"]).upper())
    deltas = {label_of(k): per_rows[k]["plan"]["delta_ticks"] for k in keys}
    spans = base.retimed_spans(snap["segments"], deltas)
    earliest = min(x[0] for x in spans)
    old_end = snap["managed"]["Playback:master"][1]
    artist_bad, artist_notes = base.artist_refusals(snap["artist"], snap["markers"], earliest, old_end, sum(deltas.values()))
    # Whole-show coverage is an expected warning. Other absolute Master content remains a hard refusal.
    refusals += artist_bad
    warnings += artist_notes
    show_rows, master_rows = base._label_rows(master, snap["segments"], tick, base._guid_by_label(show))
    refusals += base.sync_gate(show_rows, master_rows)
    stale, handoff_report = base._handoffs(show)
    if stale is None:
        warnings.append("HANDOFF_CHECK_FAILED: %s" % handoff_report)
    review_hash = inventory_sha256(per_rows)
    if str(args["mode"]).upper() == "APPLY" and review.get("inventory_sha256") != review_hash:
        refusals.append("REVIEW_HASH_CHANGED: live %s args %r" % (review_hash, review.get("inventory_sha256")))
    report = {"tool": TOOL, "tickRate": tick, "displayRate": list(fps), "per": per_rows, "deltas": deltas,
              "segmentsPredicted": base.predict_segments(snap["segments"], deltas), "netDeltaTicks": sum(deltas.values()),
              "netDeltaSeconds": sum(deltas.values()) / tick, "oldShowEnd": old_end,
              "newShowEnd": old_end + sum(deltas.values()), "reviewInventorySha256": review_hash,
              "absoluteMasterContent": snap["artist"], "masterMarkers": snap["markers"],
              "handoffStaleBefore": stale, "handoffReport": handoff_report,
              "refusals": refusals, "warnings": warnings}
    return report, snap, show, master, facts


def _log_report(run, report):
    for key, row in sorted(report["per"].items()):
        unreal.log("%s_PLAN|run=%s|P0%s|old=%d(%.6fs)|new=%d(%.6fs)|music=%.6fs|tail_override=%.6fs|"
                   "past=%d|absolute_passage_keys=%d" % (
                       MARK, run, key, row["plan"]["old_ticks"], row["old"]["lenSeconds"],
                       row["plan"]["new_ticks"], row["plan"]["new_ticks"] / report["tickRate"],
                       row["music"]["selectedSeconds"], row["music"]["tailOverrideSeconds"],
                       row["inventory"]["pastCount"], len(row["inventory"]["absolutePassageKeys"])))
        if key == "5":
            unreal.log("%s_P05_HEIGHT_OFFSET|run=%s|%s" % (MARK, run, json.dumps(row["p05HeightOffset"], ensure_ascii=False)))
    for text in report["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, text))
    for text in report["warnings"]:
        unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, text))


def run_dry(args, run):
    report, _snap, _show, _master, _facts = _gather(args)
    expected = {k: {"old_len_ticks": row["plan"]["old_ticks"], "new_len_ticks": row["plan"]["new_ticks"],
                    "music_ticks": row["music"]["selectedTicks"]} for k, row in report["per"].items()}
    output = os.path.join(_here(), DRY_NAME)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(dict(report, mode="DRY", run=run, args=args, applyReady=not report["refusals"],
                       expectedForApplyArgs=expected), handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
    _log_report(run, report)
    if base._census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % json.dumps(base._census()))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|review=%s|net_s=%.6f|report=%s" % (
        MARK, run, int(not report["refusals"]), len(report["refusals"]), len(report["warnings"]),
        report["reviewInventorySha256"], report["netDeltaSeconds"], output))


def _post_gates(report, before, after, show):
    spans = base.retimed_spans(before["segments"], report["deltas"])
    failures = []
    failures += base.segment_shift_gate(before["segments"], after["segments"], report["deltas"])
    failures += base.managed_shift_gate(before["managed"], after["managed"], spans)
    failures += relative_key_carry_gate(before["keys"], after["keys"], spans)
    if after["dup"]:
        failures.append("MANAGED_BLOCK_DUPLICATED_AFTER: %s" % after["dup"])
    if after["artist"] != before["artist"] or after["markers"] != before["markers"]:
        failures.append("ABSOLUTE_MASTER_CONTENT_CHANGED")
    for key, row in report["per"].items():
        hit = [s for s in after["segments"] if s["label"] == label_of(key)]
        if len(hit) != 1 or int(hit[0]["end"]) - int(hit[0]["start"]) != row["plan"]["new_ticks"]:
            failures.append("P%s NEW_LENGTH_WRONG: %r" % (key, hit))
    if report["handoffStaleBefore"] is not None:
        stale, text = base._handoffs(show)
        failures += ["HANDOFF_CHECK_FAILED_AFTER: %s" % text] if stale is None else base.handoff_gate(
            report["handoffStaleBefore"], stale)
    return failures


def run_apply(args, run):
    report, before, show, master, facts = _gather(args)
    if report["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(report["refusals"]))
    record_path = os.path.join(_here(), RECORD_NAME)
    backup = _backup(run)
    timing = {k: {"lead": row["plan"]["lead_frames"], "intervals": row["plan"]["intervals"],
                  "tail": row["plan"]["tail_frames"]} for k, row in report["per"].items()}
    protected = base.protected_view(show)
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "backup": backup, "args": args,
              "passages": list(VALID_KEYS), "decidedBy": args.get("decided_by"), "applied": False,
              "reviewInventorySha256": report["reviewInventorySha256"], "deltas": report["deltas"],
              "plannedTiming": timing, "rowsByKey": {k: {"index": facts[k]["index"], "first": facts[k]["first"],
              "guid": facts[k]["guid"]} for k in VALID_KEYS}, "before": _plain(before), "rebuildCount": 0,
              "protectedView": protected,
              "written": datetime.datetime.now().isoformat(timespec="seconds")}
    base.write_record_exclusive(record_path, record)
    failures = []
    try:
        base._write_timing(show, record["rowsByKey"], timing)
        if base._read_timing(show, list(VALID_KEYS)) != base.timing_view(timing):
            failures.append("TIMING_READBACK_FAILED")
        diff = base.protected_diff(protected, base.protected_view(show))
        if diff:
            failures.append("PROTECTED_FIELDS_CHANGED: %s" % diff[:10])
    except Exception as exc:  # noqa: BLE001
        failures.append("WRITE_RAISED: %r" % exc)
    if not failures:
        ok, text = base._rebuild(show, master)
        record["rebuildCount"] += 1
        record["rebuildReport"] = text
        if not ok:
            failures.append("REBUILD_FAILED: %s" % text)
    if not failures:
        after = base._snapshot(show, master, list(VALID_KEYS))
        record["after"] = _plain(after)
        failures += _post_gates(report, before, after, show)
    if record["rebuildCount"] != 1:
        failures.append("REBUILD_COUNT: %d" % record["rebuildCount"])
    failures += exact_census_gate(base._census(), [SHOW_PATH, MASTER_PATH])
    if failures:
        base.update_record(record_path, dict(record, failed=failures))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|NOTHING_SAVED|backup=%s" % (failures[:10], backup))
    for asset in (SHOW_PATH, MASTER_PATH):
        if not unreal.EditorAssetLibrary.save_asset(asset, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s|backup=%s|record=%s" % (asset, backup, record_path))
    final = base._snapshot(unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH), list(VALID_KEYS))
    readback = ["POST_SAVE_%s_DIFFERS" % field for field in ("timing", "segments", "managed", "keys")
                if _plain(final)[field] != record["after"][field]]
    readback += exact_census_gate(base._census(), [])
    if readback:
        record["postSaveReadbackFailed"] = readback
        base.update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|backup=%s" % (readback, backup))
    record["applied"] = True
    record["postSaveCensus"] = base._census()
    base.update_record(record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|passages=6|rebuilds=1|net_s=%.6f|saved=%s,%s|backup=%s|record=%s" % (
        MARK, run, report["netDeltaSeconds"], SHOW_PATH, MASTER_PATH, backup, record_path))


def run_revert(args, run):
    record_path = os.path.join(_here(), RECORD_NAME)
    with open(record_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or not record.get("after"):
        _stop(run, "REVERT_RECORD_CONTEXT")
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    live = base._snapshot(show, master, list(VALID_KEYS))
    drift = base.drift_refusals(_plain(live), record)
    if _plain(live).get("keys") != record["after"].get("keys"):
        drift.append("STATE_DRIFTED_SINCE_APPLY: keys")
    if base.protected_view(show) != record.get("protectedView"):
        drift.append("STATE_DRIFTED_SINCE_APPLY: protected Show fields")
    if drift:
        _stop(run, "STATE_DRIFTED|%r|original_backup=%s" % (drift, record["backup"]))
    backup = _backup(run, "Revert")
    attempt_path = os.path.join(_here(), "passages_to_music_revert_record_%s.json" % run)
    attempt = {"schema": 1, "tool": TOOL, "mode": "REVERT", "run": run, "backup": backup,
               "sourceRecord": record_path, "beforeRevert": _plain(live), "complete": False, "rebuildCount": 0}
    base.write_record_exclusive(attempt_path, attempt)
    failures = []
    protected = base.protected_view(show)
    try:
        base._write_timing(show, record["rowsByKey"], record["before"]["timing"])
        if base._read_timing(show, list(VALID_KEYS)) != record["before"]["timing"]:
            failures.append("TIMING_READBACK_FAILED")
        diff = base.protected_diff(protected, base.protected_view(show))
        if diff:
            failures.append("PROTECTED_FIELDS_CHANGED: %s" % diff[:10])
    except Exception as exc:  # noqa: BLE001
        failures.append("WRITE_RAISED: %r" % exc)
    if not failures:
        ok, text = base._rebuild(show, master)
        attempt["rebuildCount"] += 1
        attempt["rebuildReport"] = text
        if not ok:
            failures.append("REBUILD_FAILED: %s" % text)
    if not failures:
        restored = _plain(base._snapshot(show, master, list(VALID_KEYS)))
        failures += base.revert_exact_gate(restored, record)
        attempt["afterRevert"] = restored
    if attempt["rebuildCount"] != 1:
        failures.append("REBUILD_COUNT: %d" % attempt["rebuildCount"])
    failures += exact_census_gate(base._census(), [SHOW_PATH, MASTER_PATH])
    if failures:
        attempt["failed"] = failures
        base.update_record(attempt_path, attempt)
        _stop(run, "REVERT_GATES|%r|NOTHING_SAVED|backup=%s" % (failures[:10], backup))
    for asset in (SHOW_PATH, MASTER_PATH):
        if not unreal.EditorAssetLibrary.save_asset(asset, only_if_is_dirty=False):
            _stop(run, "REVERT_SAVE_FAILED|%s|backup=%s" % (asset, backup))
    final = _plain(base._snapshot(unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH), list(VALID_KEYS)))
    failures = base.revert_exact_gate(final, record) + exact_census_gate(base._census(), [])
    if failures:
        attempt["postSaveReadbackFailed"] = failures
        base.update_record(attempt_path, attempt)
        _stop(run, "REVERT_READBACK|%r|backup=%s" % (failures, backup))
    attempt["complete"] = True
    base.update_record(attempt_path, attempt)
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|passages=6|rebuilds=1|saved=%s,%s|backup=%s|record=%s" % (
        MARK, run, SHOW_PATH, MASTER_PATH, backup, archived))


def main():
    args = globals().get("PASSAGES_TO_MUSIC_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("P33-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    record_path = os.path.join(_here(), RECORD_NAME)
    applied = False
    if os.path.exists(record_path):
        try:
            with open(record_path, "r", encoding="utf-8") as handle:
                applied = bool(json.load(handle).get("applied"))
        except (OSError, ValueError):
            applied = False
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": base._census(), "record_exists": os.path.exists(record_path), "record_applied": applied}
    early = live_gates(state)
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        if mode == "DRY":
            run_dry(args, run)
        elif mode == "APPLY":
            run_apply(args, run)
        else:
            run_revert(args, run)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|%s" % exc)


if unreal is not None and not globals().get("PASSAGES_TO_MUSIC_IMPORT_ONLY"):
    main()
