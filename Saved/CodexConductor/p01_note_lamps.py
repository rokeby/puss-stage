"""P01 note lamps: PLAN (offline) / DRY / APPLY / REVERT. Distant P01 lamps answer notable harp notes.

Gary, 7 Oct: as the camera looks down the P01 corridor, DISTANT lamps respond playfully to notable harp
notes of the walk music, "not completely indexical": a MIX - some glint and fade (~1 s), some bloom for a
few seconds, some come on and stay on until the camera passes them. ~25-35 notes, easy to adjust
(p01_note_lamps_config.json). Lamps may darken again as the camera approaches them.

Mechanism. HELD patch Scripts/patches/2026-10-04_LD_flash_events.draft.patch (unbuilt) adds to
FInfinityStageLightDrama: bFlash, FlashCameraOffsetsCm, FlashAttackCm, FlashDecayCm, FlashRestScale.
EvaluateFlash(Drama, CameraPastLampCm) = max over offsets of a pulse (linear attack over FlashAttackCm
BEFORE the offset, peak AT the offset, cubic decay over FlashDecayCm after), floored at FlashRestScale.
CameraPastLampCm = camera route distance - lamp route distance, lamp route distance = Wing.DistanceCm +
RelativeTransform.X (InfinityStagePassageActor.cpp:1653-1664, Station anchor only). A note at show time t
fires lamp L at its peak when offset = d(t) - d_L; negative = the lamp is AHEAD of the camera.
Attack/decay are camera travel, so seconds become cm through the local camera speed. One lamp may carry
several offsets but a single attack/decay, so the BEHAVIOUR is per lamp: a lamp only takes notes of the
behaviour it was first given.

Strike gating. The patch multiplies flash by the strike level ("Gated by any strike: an unstruck lamp
stays dark through its flashes", patch Evaluate hunk). Every P01 score lamp has strike_on_approach with
StrikeDistance 650-4700 cm (lighting_scores_record_P01.json, measured 5 Oct), so a lamp 15-45 m ahead is
unstruck and a flash there would be INVISIBLE. config strike_policy:
  flash_owns (default): chosen lamps get strike_on_approach=False (as lighting_events_apply.py
      phase_b_drama does); they rest at FlashRestScale (0 = off) except during their flashes, so a
      glint/bloom lamp is DARK when the camera reaches it (Gary allowed "darken again as the camera
      approaches"); a stay lamp's decay is long enough to hold >= hold_level_at_pass until it is passed.
  keep: strike untouched; the plan REFUSES (FLASH_GATED_BY_STRIKE) any offset beyond the lamp's strike.

Proof tiers (AGENTS.md), per claim:
* declaration-proven: EvaluateFlash / Evaluate / ApplyToLamp semantics (patch file, lines 1-66);
  FInfinityStageLightDrama strike fields (InfinityStageLightDrama.h:38-104); EvaluateStrike
  (InfinityStageLightDrama.cpp:24-60); route law EvaluateDistanceAtFrame piecewise-linear through
  (SegmentStart,0), (FirstPass, LeadInDistance), each wing (PassFrame, DistanceCm), (SegmentEnd, Total)
  (InfinityStageCompiler.cpp:254-288 builds, :380-411 evaluates); in the show the camera rig passes
  EvaluateDistanceAtFrame(DistanceMasterFrame) + CameraOffset.X + LocalOffsetCm.X
  (InfinityStageCameraRig.cpp:829-833, :439) - so SpeedMultiplier / LongitudinalOffset keys would bend it
  (the DRY refuses when those Passage channels are authored, p01_hallway_pingon.py precedent :516-525);
  helpers copied/loaded from p01_rig_pattern.py (live-proven APPLY 20261006-184409).
* measured (offline, files): notes/salience/peaks P01_notes.json (Tools/MusicNotes/harp_notes.py);
  P01 Master segment 2312640..4624705 ticks @24000 (walking_music_swap_record_P01.json); lamp labels,
  roles, intensities, strike distances (lighting_scores_record_P01.json after_rows, 5 Oct) overlaid with
  moved positions (p01_rig_pattern_record.json, 6 Oct).
* inferred (each says why): PLAN's route model (constant speed, 600 cm spacing; DRY replaces it with the
  live compiled law); the CameraOffset.X / gait LocalOffsetCm.X terms are ignored (not readable without
  PIE); Python names of the patch fields (flash, flash_camera_offsets_cm, ... - UE strips the b prefix and
  snake-cases, as strike_on_approach proves for bStrikeOnApproach); the ExportText key names used by the
  export mask; float32 storage of the flash floats (UPROPERTY float); visibility of 28-99 cd TOP lights
  at 15-45 m is unmeasured; bulb bodies follow their light's flash via UpdateBulbBodies (cpp :1781).

Modes / args (p01_note_lamps_args.json via p01_note_lamps_run.py, or python p01_note_lamps.py offline):
  {"mode": "PLAN"}  offline, no Unreal: writes p01_note_lamps_plan.json (+ preview PNG unless "preview": false)
  {"mode": "DRY"}   editor, read-only: live route + live lamps, plan, scope self-check, capability probe
  {"mode": "APPLY", "confirm": "APPLY P01NOTELAMPS", "expected_plan_sha256": "<DRY report plan_sha256>",
   "ack_records": [...], "allow_dirty": []}
  {"mode": "REVERT", "confirm": "REVERT P01NOTELAMPS"}
Markers: P01NOTELAMPS_PLAN_OK / _DRY_OK / _APPLY_OK / _REVERT_OK |run=<id>|...;
any stop P01NOTELAMPS_STOPPED|run=<id>|mode=<m>|saved=<0/1>|<reason> (APPLY on an unpatched engine:
...|ENGINE_LACKS_FLASH).
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import struct
import subprocess
import sys

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline PLAN / harness
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
CONFIG_PATH = os.path.join(HERE, "p01_note_lamps_config.json")
ARGS_PATH = os.path.join(HERE, "p01_note_lamps_args.json")
PLAN_PATH = os.path.join(HERE, "p01_note_lamps_plan.json")
PREVIEW_PATH = os.path.join(HERE, "p01_note_lamps_preview.png")
RECORD_PATH = os.path.join(HERE, "p01_note_lamps_record.json")
SCORES_RECORD_P01 = os.path.join(HERE, "lighting_scores_record_P01.json")
RIG_RECORD_P01 = os.path.join(HERE, "p01_rig_pattern_record.json")
RIG_TOOL_PATH = os.path.join(HERE, "p01_rig_pattern.py")
PREVIEW_TOOL = os.path.join(PROJECT, "Tools", "MusicNotes", "note_lamps_preview.py")
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"   # p01_hallway_pingon.py:64
VALID_MODES = ("PLAN", "DRY", "APPLY", "REVERT")
CONFIRM_TOKEN = "P01NOTELAMPS"
MARK = "P01NOTELAMPS"
PASSAGE_KEY = "P01"
PASSAGE_LABEL = "Passage 1"
PASSAGE_ACTOR_PREFIX = "Passage 01"
SCORE_LABEL = re.compile(r"^P01 SCORE B(\d{2}) \S+ (\S+)$")
BEHAVIOURS = ("glint", "bloom", "stay")
STRIKE_POLICIES = ("flash_owns", "keep")
# Python names of the patch's UPROPERTYs (inferred naming; the capability probe proves them live).
FLASH_FIELDS = ("flash", "flash_camera_offsets_cm", "flash_attack_cm", "flash_decay_cm", "flash_rest_scale")
FLASH_DEFAULTS = {"flash": False, "flash_camera_offsets_cm": [], "flash_attack_cm": 3.0,
                  "flash_decay_cm": 18.0, "flash_rest_scale": 0.0}   # patch header defaults
# Exactly the drama fields this tool may write; everything else must read back unchanged.
WRITABLE_DRAMA = FLASH_FIELDS + ("strike_on_approach",)
EXPORT_KEYS = ("bFlash", "FlashCameraOffsetsCm", "FlashAttackCm", "FlashDecayCm", "FlashRestScale",
               "bStrikeOnApproach")


class P01NoteLampsError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise P01NoteLampsError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def f32(value):
    """Round to the float32 a UPROPERTY float stores, so plan == read-back exactly."""
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _finite(value, label):
    number = float(value)
    require(math.isfinite(number), "%s_NOT_FINITE|%r" % (label, value))
    return number


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _load_attachment_state():
    spec = importlib.util.spec_from_file_location("_infinity_attachment_state_note_lamps",
                                                  os.path.join(HERE, "_infinity_attachment_state.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = _load_attachment_state()


# --------------------------------------------------------------------------
# Config.
# --------------------------------------------------------------------------
def load_config(path=CONFIG_PATH, overrides=None):
    config = _read_json(path)
    if overrides:
        config = copy.deepcopy(config)
        config.update(copy.deepcopy(overrides))
    return validate_config(config)


def validate_config(config):
    c = copy.deepcopy(config)
    require(c.get("schema_version") == 1, "CONFIG_SCHEMA_NOT_1")
    count = c.get("target_count")
    require(isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= 120,
            "TARGET_COUNT_INVALID|%r" % (count,))
    weights = c.get("behaviour_weights") or {}
    require(set(weights) <= set(BEHAVIOURS) and weights and all(float(v) >= 0.0 for v in weights.values())
            and sum(float(v) for v in weights.values()) > 0.0, "BEHAVIOUR_WEIGHTS_INVALID|%r" % (weights,))
    for name in BEHAVIOURS:
        spec = (c.get("behaviours") or {}).get(name)
        require(isinstance(spec, dict), "BEHAVIOUR_SPEC_MISSING|" + name)
        require(_finite(spec["attack_s"], name + "_ATTACK") > 0.0, "ATTACK_NOT_POSITIVE|" + name)
        if name == "stay":
            hold = _finite(spec["hold_level_at_pass"], "STAY_HOLD")
            require(0.0 < hold < 1.0, "STAY_HOLD_RANGE|%r" % hold)
            require(_finite(spec["pass_margin_m"], "STAY_MARGIN") >= 0.0, "STAY_MARGIN_NEGATIVE")
        else:
            require(_finite(spec["decay_s"], name + "_DECAY") > 0.0, "DECAY_NOT_POSITIVE|" + name)
        require(int(spec.get("max_notes_per_lamp", 1)) >= 1, "MAX_NOTES_PER_LAMP|" + name)
    lo, hi = [float(v) for v in c["lookahead_m"]]
    require(0.0 < lo < hi, "LOOKAHEAD_INVALID|%r" % (c["lookahead_m"],))
    require(c.get("strike_policy") in STRIKE_POLICIES, "STRIKE_POLICY_INVALID|%r" % (c.get("strike_policy"),))
    require(0.0 <= float(c.get("rest_scale", 0.0)) <= 1.0, "REST_SCALE_RANGE")
    require(isinstance(c.get("seed"), int) and not isinstance(c.get("seed"), bool), "SEED_NOT_INT")
    require(isinstance(c.get("roles"), list) and c["roles"], "ROLES_INVALID")
    for mark in c.get("must_include_show_s", []):
        require(isinstance(mark, (int, float)) or (isinstance(mark, list) and len(mark) == 2
                                                   and float(mark[0]) <= float(mark[1])),
                "MUST_INCLUDE_INVALID|%r" % (mark,))
    return c


# --------------------------------------------------------------------------
# Route law (port of FInfinityStageCompiler build :254-288 and EvaluateDistanceAtFrame :380-411).
# Times are Master seconds.
# --------------------------------------------------------------------------
def route_from_settings(segment_start_s, segment_end_s, tick_rate, lead_in_ticks, lead_in_cm,
                        tail_ticks, tail_cm, wings):
    """wings: [{"cue_guid", "cue_label", "interval_ticks", "gap_cm"}] in route order (last interval ignored)."""
    require(wings, "ROUTE_NO_WINGS")
    start_tick = int(round(float(segment_start_s) * float(tick_rate)))
    tick = start_tick + int(lead_in_ticks)
    distance = float(lead_in_cm)
    rows = []
    for index, wing in enumerate(wings):
        rows.append({"cue_guid": wing["cue_guid"], "cue_label": wing.get("cue_label"),
                     "pass_s": tick / float(tick_rate), "distance_cm": distance})
        if index + 1 < len(wings):
            require(int(wing["interval_ticks"]) > 0 and float(wing["gap_cm"]) > 0.0,
                    "ROUTE_NONPOSITIVE_STEP|%s" % wing.get("cue_label"))
            tick += int(wing["interval_ticks"])
            distance += float(wing["gap_cm"])
    end_tick = tick + int(tail_ticks)
    require(abs(end_tick - int(round(float(segment_end_s) * float(tick_rate)))) <= 1,
            "ROUTE_END_MISMATCH|show_end_tick=%d|master_end_s=%.6f" % (end_tick, float(segment_end_s)))
    return {"segment_start_s": start_tick / float(tick_rate), "segment_end_s": end_tick / float(tick_rate),
            "first_pass_s": rows[0]["pass_s"], "first_pass_cm": rows[0]["distance_cm"],
            "last_pass_s": rows[-1]["pass_s"], "last_pass_cm": rows[-1]["distance_cm"],
            "total_cm": distance + float(tail_cm), "wings": rows}


def route_from_model(model, cue_rows):
    """INFERRED constant-speed model for PLAN. cue_rows: [(cue_guid, cue_label)] in route order."""
    start = _finite(model["segment_start_s"], "SEG_START")
    end = _finite(model["segment_end_s"], "SEG_END")
    first = float(model["first_station_cm"])
    spacing = float(model["bay_spacing_cm"])
    require(len(cue_rows) == int(model["bay_count"]), "MODEL_BAY_COUNT|model=%s|rows=%d"
            % (model["bay_count"], len(cue_rows)))
    total = first + spacing * (len(cue_rows) - 1) + float(model["tail_cm"])
    speed = total / (end - start)
    rows = [{"cue_guid": g, "cue_label": label, "distance_cm": first + spacing * i,
             "pass_s": start + (first + spacing * i) / speed} for i, (g, label) in enumerate(cue_rows)]
    return {"segment_start_s": start, "segment_end_s": end, "first_pass_s": rows[0]["pass_s"],
            "first_pass_cm": rows[0]["distance_cm"], "last_pass_s": rows[-1]["pass_s"],
            "last_pass_cm": rows[-1]["distance_cm"], "total_cm": total, "wings": rows,
            "basis": "INFERRED_MODEL_CONSTANT_SPEED", "model_speed_cm_s": speed}


def _interp(t, a_t, a_d, b_t, b_d):
    if b_t <= a_t:
        return b_d
    alpha = min(1.0, max(0.0, (t - a_t) / (b_t - a_t)))
    return a_d + (b_d - a_d) * alpha


def distance_at(route, t):
    """EvaluateDistanceAtFrame, in seconds."""
    wings = route["wings"]
    if t <= route["first_pass_s"]:
        return _interp(t, route["segment_start_s"], 0.0, route["first_pass_s"], route["first_pass_cm"])
    for a, b in zip(wings, wings[1:]):
        if t <= b["pass_s"]:
            return _interp(t, a["pass_s"], a["distance_cm"], b["pass_s"], b["distance_cm"])
    return _interp(t, route["last_pass_s"], route["last_pass_cm"], route["segment_end_s"], route["total_cm"])


def speed_at(route, t, h=0.05):
    """Local camera speed (cm/s), centred difference of the route law."""
    a = max(route["segment_start_s"], t - h)
    b = min(route["segment_end_s"], t + h)
    require(b > a, "SPEED_WINDOW_EMPTY|t=%.3f" % t)
    return (distance_at(route, b) - distance_at(route, a)) / (b - a)


def station_by_cue(route):
    return {w["cue_guid"]: w["distance_cm"] for w in route["wings"]}


# --------------------------------------------------------------------------
# Drama ports (lighting_events_apply.py:172-216 = InfinityStageLightDrama.cpp + patch).
# --------------------------------------------------------------------------
def _smoothstep(x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return x * x * (3.0 - 2.0 * x)


def eval_strike(drama, ahead_cm):
    """EvaluateStrike without IgnitionStutter dips (they only ever lower the level during the ramp)."""
    unstruck = min(1.0, max(0.0, float(drama.get("unstruck_intensity_scale", 0.0))))
    start = max(0.0, float(drama["strike_distance_cm"]))
    level = unstruck
    if ahead_cm <= start:
        progress = min(1.0, max(0.0, (start - ahead_cm) / max(1.0, float(drama["strike_ramp_cm"]))))
        level = unstruck + (1.0 - unstruck) * _smoothstep(progress)
    past = -ahead_cm - max(0.0, float(drama.get("after_pass_distance_cm", 0.0)))
    after = str(drama.get("after_pass", "HOLD")).upper()
    if past > 0.0:
        if "EXTINGUISH" in after:
            level = unstruck
        elif "DECAY" in after:
            faded = min(1.0, max(0.0, past / max(1.0, float(drama["decay_distance_cm"]))))
            level = level + (unstruck - level) * faded
    return level


def eval_flash(drama, camera_past_lamp_cm):
    rest = min(1.0, max(0.0, float(drama.get("flash_rest_scale", 0.0))))
    attack = max(0.1, float(drama["flash_attack_cm"]))
    decay = max(0.1, float(drama["flash_decay_cm"]))
    level = rest
    for offset in drama["flash_camera_offsets_cm"]:
        d = camera_past_lamp_cm - float(offset)
        pulse = 0.0
        if -attack <= d < 0.0:
            pulse = (d + attack) / attack
        elif 0.0 <= d <= decay:
            pulse = (1.0 - d / decay) ** 3
        level = max(level, pulse)
    return level


def eval_drama(drama, lamp_route_cm, camera_route_cm):
    scale = 1.0
    if drama.get("strike_on_approach"):
        scale = eval_strike(drama, lamp_route_cm - camera_route_cm)
    if drama.get("flash"):
        scale *= eval_flash(drama, camera_route_cm - lamp_route_cm)
    return scale


# --------------------------------------------------------------------------
# Lamps.
# --------------------------------------------------------------------------
def _enum_tail(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


def lamp_from_row(row, cue_guid, cue_label, ordinal):
    """A plain attachment row -> lamp dict, or None if it is not a P01 SCORE light."""
    match = SCORE_LABEL.match(str(row["label"]))
    if not match or _enum_tail(row["kind"]) != "LIGHT":
        return None
    loc = row["relative_transform"]["location"]
    drama = row["lighting"]["drama"]
    return {"guid": row["guid"], "label": row["label"], "cue_guid": cue_guid, "cue_label": cue_label,
            "ordinal": int(ordinal), "bay_token": match.group(1), "role": match.group(2),
            "enabled": bool(row.get("enabled", True)), "anchor": _enum_tail(row["anchor"]),
            "x_cm": float(loc[0]), "y_cm": float(loc[1]), "z_cm": float(loc[2]),
            "side": "L" if float(loc[1]) < 0.0 else "R",
            "intensity": float(row["lighting"]["intensity"]),
            "drama_before": {k: copy.deepcopy(v) for k, v in drama.items()}}


def lamps_from_records(scores_record, rig_record=None):
    """Offline lamp census: scores after_rows (5 Oct) with rig-pattern moved locations (6 Oct) overlaid."""
    moved = {}
    if rig_record and rig_record.get("status") == "saved_readback_verified":
        for t in rig_record["plan"]["targets"]:
            moved[t["attachment_guid"]] = list(t["location_after"])
    lamps, cue_rows = [], []
    for target in sorted(scores_record["plan"]["targets"], key=lambda t: t["ordinal"]):
        cue_rows.append((target["cue_guid"], target["cue_label"]))
        for row in target["after_rows"]:
            row = copy.deepcopy(row)
            if row["guid"] in moved:
                row["relative_transform"]["location"] = moved[row["guid"]]
            lamp = lamp_from_row(row, target["cue_guid"], target["cue_label"], target["ordinal"])
            if lamp is not None:
                lamps.append(lamp)
    return lamps, cue_rows


def eligible_lamps(lamps, config):
    excluded = set() if config.get("allow_gary_bays") else set(config.get("exclude_cues") or [])
    roles = set(config["roles"])
    out = []
    for lamp in lamps:
        if (lamp["role"] in roles and lamp["enabled"] and lamp["anchor"] == "STATION"
                and lamp["intensity"] >= float(config.get("min_intensity", 0.0))
                and lamp["cue_label"] not in excluded):
            out.append(lamp)
    return sorted(out, key=lambda l: (l["ordinal"], l["role"], l["guid"]))


# --------------------------------------------------------------------------
# Note selection.
# --------------------------------------------------------------------------
def note_score(note, notes_doc, config):
    w = config["score"]
    run_start = False
    if "run" in note:
        run = notes_doc["runs"][note["run"]]
        run_start = abs(float(run["start_show_s"]) - float(note["show_s"])) < 1.0e-6
    return (float(w.get("salience", 1.0)) * float(note["salience"])
            + float(w.get("melodic_peak", 1.0)) * (1.0 if note.get("melodic_peak") else 0.0)
            + float(w.get("run_start", 1.0)) * (1.0 if run_start else 0.0))


def resolve_must(notes, config, window):
    """Gary's marks -> notes. A number = nearest notable note within tolerance (nearest any note if no
    notable one is that close); a [a, b] range = its best notable notes (padded), at least one."""
    tol = float(config.get("must_include_tolerance_s", 0.75))
    pad = float(config.get("must_range_pad_s", 0.25))
    cap = int(config.get("must_range_max_notes", 2))
    inside = [n for n in notes if window[0] <= n["show_s"] <= window[1]]
    out, rows = [], []
    for mark in config.get("must_include_show_s", []):
        if isinstance(mark, list):
            a, b = float(mark[0]) - pad, float(mark[1]) + pad
            hits = sorted([n for n in inside if n.get("notable") and a <= n["show_s"] <= b],
                          key=lambda n: (-float(n["salience"]), n["show_s"]))[:cap]
            if not hits:
                mid = 0.5 * (float(mark[0]) + float(mark[1]))
                hits = sorted(inside, key=lambda n: (abs(n["show_s"] - mid), n["show_s"]))[:1]
            for n in hits:
                out.append(n)
                rows.append({"mark": mark, "show_s": n["show_s"], "notable": bool(n.get("notable"))})
            require(hits, "MUST_INCLUDE_UNRESOLVED|%r" % (mark,))
            continue
        m = float(mark)
        near = [n for n in inside if abs(n["show_s"] - m) <= tol]
        notable = [n for n in near if n.get("notable")]
        pool = notable or near
        require(pool, "MUST_INCLUDE_UNRESOLVED|%r|tol=%.2f" % (mark, tol))
        hit = sorted(pool, key=lambda n: (abs(n["show_s"] - m), n["show_s"]))[0]
        out.append(hit)
        rows.append({"mark": mark, "show_s": hit["show_s"], "notable": bool(hit.get("notable"))})
    unique = {}
    for n in out:
        unique[n["show_s"]] = n
    return [unique[k] for k in sorted(unique)], rows


def rank_notes(notes_doc, config, window):
    notes = notes_doc["notes"]
    must, must_rows = resolve_must(notes, config, window)
    must_keys = {n["show_s"] for n in must}
    tol = float(config.get("exclude_tolerance_s", 0.15))
    excluded = [float(x) for x in config.get("exclude_show_s", [])]
    pool = []
    for n in notes:
        if not (window[0] <= n["show_s"] <= window[1]) or n["show_s"] in must_keys:
            continue
        if config.get("notable_only", True) and not n.get("notable"):
            continue
        if any(abs(n["show_s"] - x) <= tol for x in excluded):
            continue
        pool.append(n)
    pool.sort(key=lambda n: (-note_score(n, notes_doc, config), n["show_s"]))
    return must, must_rows, pool


# --------------------------------------------------------------------------
# Assignment (one seeded generator per draw; never two draws in one expression).
# --------------------------------------------------------------------------
def draw01(seed, show_s, purpose):
    rng = random.Random("%s|%.3f|%s" % (seed, float(show_s), purpose))
    value = rng.random()
    return value


def draw_behaviour(config, show_s):
    weights = config["behaviour_weights"]
    names = [b for b in BEHAVIOURS if float(weights.get(b, 0.0)) > 0.0]
    total = sum(float(weights[b]) for b in names)
    u = draw01(config["seed"], show_s, "behaviour") * total
    acc = 0.0
    for name in names:
        acc += float(weights[name])
        if u < acc:
            return name
    return names[-1]


def behaviour_cap(config, behaviour):
    return min(int(config["behaviours"][behaviour].get("max_notes_per_lamp", 1)),
               int(config.get("max_flashes_per_lamp", 2)))


def assign(selected, lamps, route, config):
    """Chronological; returns (events, failures). Deterministic for a fixed input."""
    lo, hi = [float(v) * 100.0 for v in config["lookahead_m"]]
    gap = float(config.get("min_same_lamp_gap_s", 3.0))
    station = station_by_cue(route)
    uses, behaviour_of, bay_count = {}, {}, {}
    events, failures = [], []
    last_side = None
    for note in sorted(selected, key=lambda n: n["show_s"]):
        t = float(note["show_s"])
        d = distance_at(route, t)
        drawn = draw_behaviour(config, t)
        order = [drawn] + [b for b in BEHAVIOURS if b != drawn and float(config["behaviour_weights"].get(b, 0)) > 0]
        chosen = None
        for behaviour in order:
            cands = []
            for lamp in lamps:
                lamp_cm = station[lamp["cue_guid"]] + lamp["x_cm"]
                ahead = lamp_cm - d
                if not (lo <= ahead <= hi):
                    continue
                if config["strike_policy"] == "keep" and lamp["drama_before"].get("strike_on_approach"):
                    # Flash is multiplied by strike: only a fully struck lamp can show it.
                    struck_cm = (float(lamp["drama_before"].get("strike_distance_cm", 0.0))
                                 - max(1.0, float(lamp["drama_before"].get("strike_ramp_cm", 0.0))))
                    if ahead > struck_cm:
                        continue
                prior = uses.get(lamp["guid"], [])
                if behaviour_of.get(lamp["guid"], behaviour) != behaviour:
                    continue
                if len(prior) >= behaviour_cap(config, behaviour):
                    continue
                if any(abs(t - p) < gap for p in prior):
                    continue
                weight = float(config["role_weights"].get(lamp["role"], 1.0))
                if last_side is not None and lamp["side"] == last_side:
                    weight *= float(config.get("same_side_weight", 0.35))
                weight *= float(config.get("bay_repeat_weight", 0.5)) ** bay_count.get(lamp["cue_guid"], 0)
                if weight > 0.0:
                    cands.append((lamp, weight, lamp_cm, ahead))
            if cands:
                total = sum(c[1] for c in cands)
                u = draw01(config["seed"], t, "lamp|" + behaviour) * total
                acc, pick = 0.0, cands[-1]
                for cand in cands:
                    acc += cand[1]
                    if u < acc:
                        pick = cand
                        break
                chosen = (behaviour, pick)
                break
        if chosen is None:
            failures.append({"show_s": t, "reason": "NO_ELIGIBLE_LAMP", "camera_cm": d})
            continue
        behaviour, (lamp, unused_weight, lamp_cm, ahead) = chosen
        uses.setdefault(lamp["guid"], []).append(t)
        behaviour_of[lamp["guid"]] = behaviour
        bay_count[lamp["cue_guid"]] = bay_count.get(lamp["cue_guid"], 0) + 1
        last_side = lamp["side"]
        events.append({"show_s": t, "song_s": note.get("song_s"), "midi": note.get("midi"),
                       "salience": note.get("salience"), "melodic_peak": bool(note.get("melodic_peak")),
                       "behaviour": behaviour, "behaviour_drawn": drawn, "lamp_guid": lamp["guid"],
                       "lamp_label": lamp["label"], "cue_label": lamp["cue_label"], "ordinal": lamp["ordinal"],
                       "role": lamp["role"], "side": lamp["side"], "camera_cm": d, "lamp_route_cm": lamp_cm,
                       "ahead_cm": ahead, "offset_cm": d - lamp_cm, "speed_cm_s": speed_at(route, t)})
    return events, failures


def select_and_assign(notes_doc, lamps, route, config):
    window = (route["segment_start_s"], min(route["segment_end_s"],
                                            float(notes_doc.get("show_offset_s", 0.0)) + float(notes_doc.get("duration_s", 1e9))))
    must, must_rows, pool = rank_notes(notes_doc, config, window)
    target = int(config["target_count"])
    min_gap = float(config.get("min_note_gap_s", 0.3))
    selected = list(must)
    dropped = []
    cursor = 0

    def fits(n, chosen):
        return all(abs(n["show_s"] - c["show_s"]) >= min_gap for c in chosen)

    while True:
        while len(selected) < target and cursor < len(pool):
            cand = pool[cursor]
            cursor += 1
            if fits(cand, selected):
                selected.append(cand)
        events, failures = assign(selected, lamps, route, config)
        if not failures:
            break
        # Each pass removes >= 1 note and only refills from the finite pool, so this terminates.
        must_keys = {n["show_s"] for n in must}
        bad_must = [f for f in failures if f["show_s"] in must_keys]
        bad = {f["show_s"] for f in failures if f["show_s"] not in must_keys}
        for f in bad_must:
            # A mark of Gary's lost its lamps to earlier notes: the nearest earlier non-mark note yields.
            earlier = [n for n in selected if n["show_s"] < f["show_s"] and n["show_s"] not in must_keys
                       and n["show_s"] not in bad]
            require(earlier, "MUST_INCLUDE_UNASSIGNABLE|%s" % _canonical(f))
            yielded = max(earlier, key=lambda n: n["show_s"])
            bad.add(yielded["show_s"])
            dropped.append({"show_s": yielded["show_s"], "reason": "YIELDED_TO_MUST|%.3f" % f["show_s"]})
        dropped.extend(f for f in failures if f["show_s"] not in must_keys)
        selected = [n for n in selected if n["show_s"] not in bad]
    return {"events": events, "must": must_rows, "dropped": dropped, "window_s": list(window),
            "pool_size": len(pool) + len(must)}


# --------------------------------------------------------------------------
# Plan.
# --------------------------------------------------------------------------
def lamp_settings(lamp_events, behaviour, config):
    spec = config["behaviours"][behaviour]
    v = sum(e["speed_cm_s"] for e in lamp_events) / len(lamp_events)
    require(v > 1.0, "CAMERA_STOPPED|speed=%.3f" % v)
    attack = float(spec["attack_s"]) * v
    if behaviour == "stay":
        hold = float(spec["hold_level_at_pass"])
        reach = max(e["ahead_cm"] for e in lamp_events) + float(spec["pass_margin_m"]) * 100.0
        decay = reach / (1.0 - hold ** (1.0 / 3.0))
    else:
        decay = float(spec["decay_s"]) * v
    return {"speed_cm_s": v, "attack_cm": f32(attack), "decay_cm": f32(decay)}


def build_plan(notes_doc, lamps_all, route, config, before_drama=None):
    """Pure. lamps_all: lamp dicts (lamp_from_row); route: route_from_settings/model."""
    lamps = eligible_lamps(lamps_all, config)
    require(lamps, "NO_ELIGIBLE_LAMPS")
    station = station_by_cue(route)
    missing = sorted({l["cue_label"] for l in lamps if l["cue_guid"] not in station})
    require(not missing, "LAMP_CUE_NOT_ON_ROUTE|%s" % missing)
    chosen = select_and_assign(notes_doc, lamps, route, config)
    events = chosen["events"]
    by_lamp = {}
    for e in events:
        by_lamp.setdefault(e["lamp_guid"], []).append(e)
    lamp_index = {l["guid"]: l for l in lamps}
    targets = []
    for guid in sorted(by_lamp, key=lambda g: (lamp_index[g]["ordinal"], lamp_index[g]["role"], g)):
        lamp = lamp_index[guid]
        evs = sorted(by_lamp[guid], key=lambda e: e["show_s"])
        behaviour = evs[0]["behaviour"]
        require(all(e["behaviour"] == behaviour for e in evs), "MIXED_BEHAVIOUR|" + guid)
        settings = lamp_settings(evs, behaviour, config)
        before = copy.deepcopy((before_drama or {}).get(guid) or lamp["drama_before"])
        for name in FLASH_FIELDS:
            before.setdefault(name, copy.deepcopy(FLASH_DEFAULTS[name]))
        after = {name: copy.deepcopy(before[name]) for name in WRITABLE_DRAMA}
        after.update({"flash": True,
                      "flash_camera_offsets_cm": [f32(e["offset_cm"]) for e in evs],
                      "flash_attack_cm": settings["attack_cm"], "flash_decay_cm": settings["decay_cm"],
                      "flash_rest_scale": f32(config.get("rest_scale", 0.0))})
        if config["strike_policy"] == "flash_owns":
            after["strike_on_approach"] = False
        else:
            # Fully struck only: inside the ramp the strike level (smoothstep) still scales the flash down.
            strike_cm = float(before.get("strike_distance_cm", 0.0)) - max(1.0, float(before.get("strike_ramp_cm", 0.0)))
            gated = [e["show_s"] for e in evs if before.get("strike_on_approach") and e["ahead_cm"] > strike_cm]
            require(not gated, "FLASH_GATED_BY_STRIKE|lamp=%s|strike_cm=%.0f|notes=%s"
                    % (lamp["label"], strike_cm, gated))
        targets.append({
            "attachment_guid": guid, "attachment_label": lamp["label"], "cue_guid": lamp["cue_guid"],
            "cue_label": lamp["cue_label"], "ordinal": lamp["ordinal"], "role": lamp["role"],
            "side": lamp["side"], "lamp_route_cm": station[lamp["cue_guid"]] + lamp["x_cm"],
            "x_cm": lamp["x_cm"], "y_cm": lamp["y_cm"], "intensity": lamp["intensity"],
            "behaviour": behaviour, "notes_show_s": [e["show_s"] for e in evs],
            "speed_cm_s": settings["speed_cm_s"],
            "attack_s_at_notes": [settings["attack_cm"] / e["speed_cm_s"] for e in evs],
            "decay_s_at_notes": [settings["decay_cm"] / e["speed_cm_s"] for e in evs],
            "drama_before": {name: before.get(name) for name in WRITABLE_DRAMA},
            "drama_after": after,
            "drama_context": {k: before.get(k) for k in ("strike_distance_cm", "strike_ramp_cm",
                                                          "unstruck_intensity_scale", "after_pass",
                                                          "after_pass_distance_cm", "decay_distance_cm")}})
    plan = {
        "passage": PASSAGE_KEY, "route_basis": route.get("basis", "LIVE_COMPILED_ROUTE_LAW"),
        "route": route, "config": config, "events": events, "targets": targets,
        "target_attachment_guids": sorted(t["attachment_guid"] for t in targets),
        "target_cue_guids": sorted({t["cue_guid"] for t in targets}),
        "must": chosen["must"], "dropped": chosen["dropped"], "window_s": chosen["window_s"],
        "selected_count": len(events), "requested_count": int(config["target_count"]),
        "behaviour_counts": {b: sum(1 for e in events if e["behaviour"] == b) for b in BEHAVIOURS},
        "lamp_behaviour_counts": {b: sum(1 for t in targets if t["behaviour"] == b) for b in BEHAVIOURS},
        "eligible_lamps": [{"guid": l["guid"], "label": l["label"], "ordinal": l["ordinal"], "role": l["role"],
                            "side": l["side"], "route_cm": station[l["cue_guid"]] + l["x_cm"], "y_cm": l["y_cm"]}
                           for l in lamps],
        "notes": [{"show_s": n["show_s"], "midi": n.get("midi"), "salience": n.get("salience"),
                   "notable": bool(n.get("notable")), "melodic_peak": bool(n.get("melodic_peak"))}
                  for n in notes_doc["notes"]],
        "warnings": [],
    }
    if len(events) < int(config["target_count"]):
        plan["warnings"].append("SHORTFALL|selected=%d|requested=%d" % (len(events), int(config["target_count"])))
    check_plan(plan)
    plan["plan_sha256"] = plan_hash(plan)
    return plan


def plan_hash(plan):
    return _sha256_text(_canonical([{"guid": t["attachment_guid"], "after": t["drama_after"]}
                                    for t in plan["targets"]]))


def check_plan(plan):
    """Self-checks every plan must pass (the harness also runs them on mutated plans)."""
    config = plan["config"]
    lo, hi = [float(v) * 100.0 for v in config["lookahead_m"]]
    gap = float(config.get("min_same_lamp_gap_s", 3.0))
    require(len(plan["events"]) <= int(config["target_count"]), "COUNT_EXCEEDED|%d" % len(plan["events"]))
    by_lamp = {}
    for e in plan["events"]:
        require(lo - 1e-6 <= e["ahead_cm"] <= hi + 1e-6, "LOOKAHEAD_VIOLATED|%s|%.0f" % (e["lamp_label"], e["ahead_cm"]))
        by_lamp.setdefault(e["lamp_guid"], []).append(e["show_s"])
    for guid, times in by_lamp.items():
        times = sorted(times)
        require(all(b - a >= gap - 1e-9 for a, b in zip(times, times[1:])), "LAMP_REFIRED_WITHIN_GAP|%s|%s" % (guid, times))
    musts = {m["show_s"] for m in plan["must"]}
    chosen = {e["show_s"] for e in plan["events"]}
    require(musts <= chosen, "MUST_NOT_SELECTED|%s" % sorted(musts - chosen))
    targets = {t["attachment_guid"]: t for t in plan["targets"]}
    route = plan["route"]
    for e in plan["events"]:
        t = targets[e["lamp_guid"]]
        drama = dict(t["drama_context"])
        drama.update(t["drama_after"])
        level = eval_drama(drama, t["lamp_route_cm"], distance_at(route, e["show_s"]))
        require(level >= 0.99, "FLASH_NOT_AT_PEAK|%s|t=%.3f|level=%.3f" % (t["attachment_label"], e["show_s"], level))
    for t in plan["targets"]:
        if t["behaviour"] == "stay":
            drama = dict(t["drama_context"])
            drama.update(t["drama_after"])
            hold = float(config["behaviours"]["stay"]["hold_level_at_pass"])
            level = eval_drama(drama, t["lamp_route_cm"], t["lamp_route_cm"])
            require(level >= hold - 1e-3, "STAY_DARK_AT_PASS|%s|level=%.3f" % (t["attachment_label"], level))
        unknown = set(t["drama_after"]) - set(WRITABLE_DRAMA)
        require(not unknown, "PLAN_WRITES_UNOWNED_FIELD|%s|%s" % (t["attachment_label"], sorted(unknown)))


# --------------------------------------------------------------------------
# Scope model (pure). all_rows = {cue_guid: [row]}; row["lighting"]["drama"] carries the flash fields too.
# --------------------------------------------------------------------------
def expected_rows(all_rows, plan, side):
    require(side in ("before", "after"), "SIDE_INVALID|" + str(side))
    out = copy.deepcopy(all_rows)
    by_guid = {t["attachment_guid"]: t for t in plan["targets"]}
    for rows in out.values():
        for row in rows:
            target = by_guid.get(row["guid"])
            if target is not None:
                row["lighting"]["drama"].update(copy.deepcopy(target["drama_" + side]))
    return out


def scope_differences(base_all, live_all, plan, side):
    """[] iff live == base with exactly the targets' writable drama fields set to plan[side]."""
    if set(base_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    want_all = expected_rows(base_all, plan, side)
    problems = []
    for cue_guid in sorted(want_all):
        want, got = want_all[cue_guid], live_all[cue_guid]
        if [r["guid"] for r in want] != [r["guid"] for r in got]:
            problems.append({"cue": cue_guid, "problem": "ROW_SET_OR_ORDER_CHANGED"})
            continue
        for w, g in zip(want, got):
            diffs = S.state_differences(w, g)
            if diffs:
                problems.append({"cue": cue_guid, "guid": w["guid"], "label": w["label"], "differences": diffs})
    return problems


def check_scope(base_all, live_all, plan, side):
    problems = scope_differences(base_all, live_all, plan, side)
    require(not problems, "SCOPE_CHANGED|side=%s|count=%d|%s" % (side, len(problems), _canonical(problems)[:3000]))


def apply_plain(all_rows, plan, side="after"):
    return expected_rows(all_rows, plan, side)


def revert_drifts(all_rows, record):
    drifts = []
    for target in record["plan"]["targets"]:
        hits = [r for rows in all_rows.values() for r in rows if r["guid"] == target["attachment_guid"]]
        if len(hits) != 1:
            drifts.append({"guid": target["attachment_guid"], "field": "<row>", "live": "count=%d" % len(hits)})
            continue
        live = hits[0]["lighting"]["drama"]
        for name, value in target["drama_after"].items():
            if live.get(name) != value:
                drifts.append({"guid": target["attachment_guid"], "label": target["attachment_label"],
                               "field": name, "record_after": value, "live": live.get(name)})
    return drifts


def check_engine(capabilities):
    require(bool(capabilities.get("drama_flash")), "ENGINE_LACKS_FLASH|patch 2026-10-04_LD_flash_events not built")


def check_record(record):
    require(record.get("passage") == PASSAGE_KEY, "RECORD_PASSAGE_MISMATCH|%s" % record.get("passage"))
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|" + str(record.get("status")))


# --------------------------------------------------------------------------
# Export-text mask (p01_rig_pattern.normalize_export idea): blank the writable drama keys of targets.
# --------------------------------------------------------------------------
_OWN_GUID = re.compile(r"[(,]AttachmentGuid=([0-9A-Fa-f]{32})")
_WRITABLE_KEY = re.compile(r"(?<![A-Za-z])(%s)=(\([^()]*\)|[^,()]*),?" % "|".join(EXPORT_KEYS))


def normalize_export(texts, target_guids):
    wanted = {g.upper() for g in target_guids}
    seen = {g: 0 for g in wanted}
    out = []
    for text in texts:
        marks = list(_OWN_GUID.finditer(text))
        pieces, cursor = [], 0
        for index, match in enumerate(marks):
            guid = match.group(1).upper()
            if guid not in wanted:
                continue
            end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
            pieces.append(text[cursor:match.start()])
            pieces.append(_WRITABLE_KEY.sub("", text[match.start():end]))
            cursor = end
            seen[guid] += 1
        pieces.append(text[cursor:])
        out.append("".join(pieces))
    require(all(c == 1 for c in seen.values()), "EXPORT_TARGET_COUNT|%s" % _canonical({g: c for g, c in seen.items() if c != 1}))
    return out


def export_hash(texts, target_guids):
    return _sha256_text("\n".join(normalize_export(texts, target_guids)))


# Self-diagnosing export comparison (7 Oct: live APPLY 20261007-014342 stopped on a bare
# EXPORT_OUTSIDE_SCOPE_CHANGED that named nothing). Pure; the texts are the rig._export_texts list.
_QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _close_paren_quoted(text, open_at):
    """Index of the ')' matching text[open_at] == '(', skipping quoted strings (labels may hold parens)."""
    depth, i, n = 0, open_at, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n - 1


def _first_label(segment):
    at = segment.find("Label=")
    if at < 0:
        return None
    m = None
    for m in _QUOTED.finditer(segment, at, min(len(segment), at + 400)):
        if segment[m.end():m.end() + 1] == ")":
            break
    return m.group(1) if m else None


def _export_segments(text):
    """[(key, segment)]: '<owner>' (the cue/passage text outside attachments) and one per AttachmentGuid.
    An attachment segment ends at its own closing paren when AttachmentGuid opens the struct
    (FInfinityCueAttachment, InfinityStageTypes.h:434), so trailing cue fields stay with the owner."""
    pieces, owner, cursor = [], [], 0
    for m in _OWN_GUID.finditer(text):
        if m.start() < cursor:
            continue
        if text[m.start()] == "(":
            end = _close_paren_quoted(text, m.start()) + 1
        else:
            nxt = _OWN_GUID.search(text, m.end())
            end = nxt.start() if nxt else len(text)
        owner.append(text[cursor:m.start()])
        pieces.append((m.group(1).upper(), text[m.start():end]))
        cursor = end
    owner.append(text[cursor:])
    return [("<owner>", "\x1f".join(owner))] + pieces


def export_changes(before_texts, after_texts, target_guids, context=60):
    """Every attachment/owner whose export differs once the targets' writable drama keys are masked.
    [] iff export_hash(before) == export_hash(after)."""
    wanted = {g.upper() for g in target_guids}
    nb, na = normalize_export(before_texts, target_guids), normalize_export(after_texts, target_guids)
    if len(nb) != len(na):
        return [{"text_index": "*", "problem": "TEXT_COUNT_CHANGED", "before": len(nb), "after": len(na)}]
    changes = []
    for index, (b, a) in enumerate(zip(nb, na)):
        if b == a:
            continue
        sb, sa = _export_segments(b), _export_segments(a)
        owner = _first_label(sb[0][1]) or _first_label(sa[0][1])
        db, da = dict(sb), dict(sa)
        if [k for k, _ in sb] != [k for k, _ in sa]:
            changes.append({"text_index": index, "owner": owner, "problem": "ATTACHMENT_SET_OR_ORDER_CHANGED",
                            "only_before": sorted(set(db) - set(da)), "only_after": sorted(set(da) - set(db))})
        for key, seg_b in sb:
            seg_a = da.get(key)
            if seg_a is None or seg_a == seg_b:
                continue
            at = next((i for i, (x, y) in enumerate(zip(seg_b, seg_a)) if x != y), min(len(seg_b), len(seg_a)))
            lo = max(0, at - context)
            changes.append({"text_index": index, "owner": owner, "guid": key,
                            "label": owner if key == "<owner>" else _first_label(seg_b),
                            "is_target": key in wanted, "offset": at,
                            "before": seg_b[lo:at + context], "after": seg_a[lo:at + context]})
    if not changes:   # differs only in the joins; never report a mismatch as clean
        changes.append({"text_index": "*", "problem": "UNATTRIBUTED_DIFFERENCE"})
    return changes


def check_export_unchanged(before_texts, after_texts, target_guids, token, log=None, limit=20):
    """Raise <token>|count=..|<first changes> when the masked exports differ; log one line per change."""
    if export_hash(after_texts, target_guids) == export_hash(before_texts, target_guids):
        return []
    changes = export_changes(before_texts, after_texts, target_guids)
    if log is not None:
        for c in changes[:limit]:
            log("%s_EXPORT_DIFF|%s|%s" % (MARK, token, _canonical(c)))
    raise P01NoteLampsError("%s|count=%d|%s" % (token, len(changes), _canonical(changes[:3])[:2500]))


# --------------------------------------------------------------------------
# Args.
# --------------------------------------------------------------------------
def check_args(args):
    args = dict(args or {})
    mode = str(args.get("mode", "PLAN")).upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode in ("APPLY", "REVERT"):
        require(args.get("confirm") == "%s %s" % (mode, CONFIRM_TOKEN),
                "CONFIRM_MISSING|mode=%s|need='%s %s'" % (mode, mode, CONFIRM_TOKEN))
    expected = args.get("expected_plan_sha256")
    require(expected is None or (isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected)),
            "EXPECTED_PLAN_SHA_INVALID|%r" % (expected,))
    return {"mode": mode, "confirm": args.get("confirm"), "expected_plan_sha256": expected,
            "config_overrides": dict(args.get("config_overrides") or {}),
            "ack_records": list(args.get("ack_records") or []), "allow_dirty": list(args.get("allow_dirty") or []),
            "allow_route_channels": bool(args.get("allow_route_channels", False)),
            "preview": bool(args.get("preview", True))}


# --------------------------------------------------------------------------
# PLAN (offline).
# --------------------------------------------------------------------------
def offline_inputs(config):
    notes_doc = _read_json(os.path.normpath(os.path.join(HERE, config["notes_path"])))
    scores = _read_json(SCORES_RECORD_P01)
    rig = _read_json(RIG_RECORD_P01) if os.path.isfile(RIG_RECORD_P01) else None
    lamps, cue_rows = lamps_from_records(scores, rig)
    route = route_from_model(config["route_model"], cue_rows)
    return notes_doc, lamps, route


def run_plan(args=None, plan_path=PLAN_PATH, preview_path=PREVIEW_PATH):
    args = check_args(args or {"mode": "PLAN"})
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    config = load_config(overrides=args["config_overrides"])
    notes_doc, lamps, route = offline_inputs(config)
    plan = build_plan(notes_doc, lamps, route, config)
    plan.update({"run": run, "mode": "PLAN", "lamp_source": "RECORDS (lighting_scores_record_P01 5 Oct + "
                 "p01_rig_pattern_record 6 Oct); the DRY re-reads the live Show"})
    _write_json(plan_path, plan)
    preview = None
    if args["preview"]:
        result = subprocess.run([sys.executable, PREVIEW_TOOL, plan_path, preview_path],
                                capture_output=True, text=True)
        require(result.returncode == 0, "PREVIEW_FAILED|%s" % (result.stderr or result.stdout)[-1500:])
        preview = preview_path
    print("%s_PLAN_OK|run=%s|selected=%d|requested=%d|lamps=%d|glint=%d|bloom=%d|stay=%d|must=%d|dropped=%d"
          "|route=%s|plan_sha256=%s|plan=%s|preview=%s"
          % (MARK, run, plan["selected_count"], plan["requested_count"], len(plan["targets"]),
             plan["behaviour_counts"]["glint"], plan["behaviour_counts"]["bloom"], plan["behaviour_counts"]["stay"],
             len(plan["must"]), len(plan["dropped"]), plan["route_basis"], plan["plan_sha256"], plan_path, preview))
    return plan


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a global.
# --------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _load_rig_module():
    """p01_rig_pattern.py (live-proven 6 Oct) without its trailing 'if unreal is not None: main()' guard;
    its own _is_main_guard checks the shape, so a changed tail refuses instead of running main()."""
    import ast
    import types
    with open(RIG_TOOL_PATH, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=RIG_TOOL_PATH)
    probe = types.ModuleType("_p01_rig_guard_probe")
    guard_src = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_dotted", "_is_main_guard")]
    require(len(guard_src) == 2, "RIG_TOOL_GUARD_FUNCS_MISSING")
    probe.__dict__["ast"] = ast   # the copied helpers use ast (NameError live, 7 Oct DRY)
    exec(compile(ast.Module(body=guard_src, type_ignores=[]), RIG_TOOL_PATH, "exec"), probe.__dict__)  # noqa: S102
    require(tree.body and probe._is_main_guard(tree.body[-1])
            and sum(1 for n in tree.body if probe._is_main_guard(n)) == 1, "RIG_TOOL_GUARD_SHAPE")
    tree.body = tree.body[:-1]
    module = types.ModuleType("_p01_rig_pattern_for_note_lamps")
    module.__file__ = RIG_TOOL_PATH
    exec(compile(tree, RIG_TOOL_PATH, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    return module


def _probe_capabilities():
    drama = unreal.InfinityStageLightDrama()
    try:
        for name in FLASH_FIELDS:
            drama.get_editor_property(name)
        return {"drama_flash": True}
    except Exception:  # noqa: BLE001 - absent on the unpatched build
        return {"drama_flash": False}


def _flash_state(drama, has_flash):
    if not has_flash:
        return {}
    return {"flash": bool(drama.get_editor_property("flash")),
            "flash_camera_offsets_cm": [float(v) for v in drama.get_editor_property("flash_camera_offsets_cm")],
            "flash_attack_cm": float(drama.get_editor_property("flash_attack_cm")),
            "flash_decay_cm": float(drama.get_editor_property("flash_decay_cm")),
            "flash_rest_scale": float(drama.get_editor_property("flash_rest_scale"))}


def _rows_with_flash(tool, attachments, has_flash):
    rows = tool._attachment_rows(attachments)
    for row, attachment in zip(rows, attachments):
        drama = attachment.get_editor_property("lighting").get_editor_property("drama")
        row["lighting"]["drama"].update(_flash_state(drama, has_flash))
    return rows


def _runtime_plain(tool, show, has_flash):
    cues = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        cues.append({"show_index": index, "guid": tool._guid_text(cue.get_editor_property("cue_guid")),
                     "label": str(cue.get_editor_property("label")),
                     "attachments": _rows_with_flash(tool, tool._pair_attachments(cue), has_flash)})
    return cues


def _all_rows(cues):
    return {c["guid"]: c["attachments"] for c in cues}


def _live_route(tool, show, allow_route_channels):
    """Compiled route law from the Show (lead-in, intervals, gaps, tail) + the Master P01 section."""
    rows = [s for s in show.get_editor_property("passage_settings") if str(s.get_editor_property("label")) == PASSAGE_LABEL]
    require(len(rows) == 1, "PASSAGE_ROW_COUNT|%d" % len(rows))
    settings = rows[0]
    passage_guid = tool._guid_text(settings.get_editor_property("passage_guid"))
    master = unreal.load_asset(MASTER_PATH)
    require(master is not None, "MASTER_MISSING")
    tick = show.get_editor_property("tick_resolution")
    tick_rate = float(tick.numerator) / float(tick.denominator)
    master_tick = master.get_tick_resolution()
    require(abs(tick_rate - float(master_tick.numerator) / float(master_tick.denominator)) < 1e-6, "TICK_RATE_MISMATCH")
    sections = []
    for track in master.get_tracks():
        if "InfinityPassage" not in track.get_class().get_name():
            continue
        for section in track.get_sections():
            if tool._guid_text(section.get_editor_property("passage_guid")) == passage_guid:
                sections.append(section)
    require(len(sections) == 1, "P01_SECTION_COUNT|%d" % len(sections))
    section = sections[0]
    authored = []
    for channel in section.get_all_channels():
        name = str(channel.get_editor_property("channel_name"))
        if name in ("Camera.SpeedMultiplier", "Camera.LongitudinalOffsetCm"):
            neutral = 1.0 if name == "Camera.SpeedMultiplier" else 0.0
            keys = list(channel.get_keys())
            default = float(channel.get_default()) if channel.has_default() else neutral
            if keys or abs(default - neutral) > 1e-6:
                authored.append({"channel": name, "keys": len(keys), "default": default})
    require(not authored or allow_route_channels, "ROUTE_CHANNEL_AUTHORED|%s" % _canonical(authored))
    cues = list(show.get_editor_property("cues"))
    bay_guids = [tool._guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(settings.get_editor_property("passage_guid"))]
    index = {tool._guid_text(c.get_editor_property("cue_guid")): c for c in cues}
    wings = []
    for guid in bay_guids:
        require(guid in index, "BAY_GUID_UNRESOLVED|" + guid)
        pair = index[guid].get_editor_property("wing_pair")
        wings.append({"cue_guid": guid, "cue_label": str(index[guid].get_editor_property("label")),
                      "interval_ticks": int(pair.get_editor_property("interval_to_next").value),
                      "gap_cm": float(pair.get_editor_property("gap_to_next_cm"))})
    route = route_from_settings(float(section.get_start_frame_seconds()), float(section.get_end_frame_seconds()),
                                tick_rate, int(settings.get_editor_property("lead_in_frames").value),
                                float(settings.get_editor_property("lead_in_distance_cm")),
                                int(settings.get_editor_property("tail_frames").value),
                                float(settings.get_editor_property("tail_distance_cm")), wings)
    route.update({"basis": "LIVE_COMPILED_ROUTE_LAW", "passage_guid": passage_guid, "authored_route_channels": authored})
    return route, bay_guids


def _live_lamps(cues, bay_guids):
    by_guid = {c["guid"]: c for c in cues}
    lamps = []
    for ordinal, guid in enumerate(bay_guids, start=1):
        cue = by_guid[guid]
        for row in cue["attachments"]:
            lamp = lamp_from_row(row, guid, cue["label"], ordinal)
            if lamp is not None:
                lamps.append(lamp)
    return lamps


def _export_texts(rig, show):
    return rig._export_texts(show)


def _write_drama(tool, show, plan, side, check_side=None):
    cues = list(show.get_editor_property("cues"))
    by_cue = {}
    for target in plan["targets"]:
        by_cue.setdefault(target["cue_guid"], []).append(target)
    for cue_guid, items in sorted(by_cue.items()):
        hits = [i for i, c in enumerate(cues) if tool._guid_text(c.get_editor_property("cue_guid")) == cue_guid]
        require(len(hits) == 1, "TARGET_CUE_RESOLVE|" + cue_guid)
        index = hits[0]
        require(str(cues[index].get_editor_property("label")) == items[0]["cue_label"], "TARGET_LABEL_DRIFT|" + cue_guid)
        attachments = tool._pair_attachments(cues[index])
        for item in items:
            found = [a for a in attachments if tool._guid_text(a.get_editor_property("attachment_guid")) == item["attachment_guid"]]
            require(len(found) == 1, "TARGET_ATTACHMENT_RESOLVE|" + item["attachment_guid"])
            attachment = found[0]
            lighting = attachment.get_editor_property("lighting")
            drama = lighting.get_editor_property("drama")
            if check_side is not None:
                live = _flash_state(drama, True)
                live["strike_on_approach"] = bool(drama.get_editor_property("strike_on_approach"))
                require(live == item["drama_" + check_side], "TARGET_DRAMA_DRIFT|%s|live=%s"
                        % (item["attachment_guid"], _canonical(live)))
            values = item["drama_" + side]
            drama.set_editor_property("strike_on_approach", bool(values["strike_on_approach"]))
            drama.set_editor_property("flash", bool(values["flash"]))
            drama.set_editor_property("flash_camera_offsets_cm", [float(v) for v in values["flash_camera_offsets_cm"]])
            drama.set_editor_property("flash_attack_cm", float(values["flash_attack_cm"]))
            drama.set_editor_property("flash_decay_cm", float(values["flash_decay_cm"]))
            drama.set_editor_property("flash_rest_scale", float(values["flash_rest_scale"]))
            lighting.set_editor_property("drama", drama)
            attachment.set_editor_property("lighting", lighting)
        tool._set_pair_attachments(show, index, attachments)


def _report_path(mode, run):
    return os.path.join(HERE, "p01_note_lamps_report_%s_%s.json" % (mode, run))


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = args["mode"]
    report = {"ok": False, "mode": mode, "run": run, "args": args, "saved": False}
    tool = None
    try:
        rig = _load_rig_module()
        scores, tool = rig.load_modules()
        ctx = rig._ctx_facts(tool)
        report["context"] = ctx
        rig.check_context(ctx, "DRY" if mode == "DRY" else mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        caps = _probe_capabilities()
        report["capabilities"] = caps
        if mode in ("APPLY", "REVERT"):
            check_engine(caps)   # before any backup, record or write
        has_flash = caps["drama_flash"]
        census_before = ctx["census"]
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        cues = _runtime_plain(tool, show, has_flash)
        before_all = _all_rows(cues)
        config = load_config(overrides=args["config_overrides"])
        if mode in ("DRY", "APPLY"):
            route, bay_guids = _live_route(tool, show, args["allow_route_channels"])
            notes_doc = _read_json(os.path.normpath(os.path.join(HERE, config["notes_path"])))
            plan = build_plan(notes_doc, _live_lamps(cues, bay_guids), route, config)
            if has_flash:
                check_scope(before_all, apply_plain(before_all, plan, "before"), plan, "before")   # model self-check
            foreign = scan_foreign_records_for(scores, plan)
            unacked = sorted({h["path"] for h in foreign} - set(args["ack_records"]))
            report.update({"plan": plan, "plan_sha256": plan["plan_sha256"], "foreign_records": foreign,
                           "unacknowledged_foreign_records": unacked})
            # Two exports, no write between: the DRY now exercises the export path the APPLY relies on
            # (before 7 Oct it never exported, so EXPORT_* failures could only surface mid-APPLY).
            export_a = _export_texts(rig, show)
            check_export_unchanged(export_a, _export_texts(rig, show), plan["target_attachment_guids"],
                                   "EXPORT_NONDETERMINISTIC", _log)
            report["export_selfcheck"] = {"texts": len(export_a), "deterministic": True,
                                          "hash": export_hash(export_a, plan["target_attachment_guids"])}
            if mode == "DRY":
                census_after = tool._dirty_census()
                require(census_after == census_before, "DRY_CENSUS_CHANGED")
                report.update({"ok": True, "mutated": False})
                path = _report_path(mode, run)
                _write_json(path, report)
                _log("%s_DRY_OK|run=%s|selected=%d|lamps=%d|engine_flash=%d|route=%s|plan_sha256=%s|foreign=%d|unacked=%d|mutated=0|report=%s"
                     % (MARK, run, plan["selected_count"], len(plan["targets"]), int(has_flash), plan["route_basis"],
                        plan["plan_sha256"], len(foreign), len(unacked), path))
                return report
            require(args["expected_plan_sha256"] == plan["plan_sha256"], "PLAN_SHA_MISMATCH|expected=%s|live=%s"
                    % (args["expected_plan_sha256"], plan["plan_sha256"]))
            require(not os.path.exists(RECORD_PATH), "ACTIVE_RECORD_EXISTS|" + RECORD_PATH)
            require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
            export_before = export_a
            texts_hash = export_hash(export_before, plan["target_attachment_guids"])
            backup = tool._backup("PreP01NoteLamps-", run)
            record = {"schema_version": 1, "status": "prepared", "run": run, "passage": PASSAGE_KEY,
                      "backup": backup, "args": args, "plan": plan, "export_hash_before": texts_hash,
                      "before_cue_rows": {g: before_all[g] for g in plan["target_cue_guids"]}}
            tool._write_json(RECORD_PATH, record, exclusive=True)
            _log("%s_RECORD_WRITTEN|run=%s|path=%s|lamps=%d" % (MARK, run, RECORD_PATH, len(plan["targets"])))
            try:
                _write_drama(tool, show, plan, "after", check_side="before")
                check_scope(before_all, _all_rows(_runtime_plain(tool, show, True)), plan, "after")
                check_export_unchanged(export_before, _export_texts(rig, show), plan["target_attachment_guids"],
                                       "EXPORT_OUTSIDE_SCOPE_CHANGED", _log)
            except Exception:
                _write_drama(tool, show, plan, "before")
                check_scope(before_all, _all_rows(_runtime_plain(tool, show, True)), plan, "before")
                record["status"] = "failed_rolled_back_in_memory"
                tool._write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
                raise
            record["status"] = "mutated_verified"
            tool._write_json(RECORD_PATH, record)
            materialized = rig._materialize(scores, show)
            tool._save_narrow()
            report["saved"] = True
            readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
            check_scope(before_all, _all_rows(_runtime_plain(tool, readback, True)), plan, "after")
            check_export_unchanged(export_before, _export_texts(rig, readback), plan["target_attachment_guids"],
                                   "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED", _log)
            record.update({"status": "saved_readback_verified", "materialized": materialized,
                           "saved_census": tool._dirty_census()})
            tool._write_json(RECORD_PATH, record)
            report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized})
            _write_json(_report_path(mode, run), report)
            _log("%s_APPLY_OK|run=%s|lamps=%d|notes=%d|show_saved=1|level_saved=1|readback=1|record=%s"
                 % (MARK, run, len(plan["targets"]), plan["selected_count"], RECORD_PATH))
            return report

        # REVERT
        require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT|" + RECORD_PATH)
        record = tool._read_json(RECORD_PATH)
        check_record(record)
        plan = record["plan"]
        drifts = revert_drifts(before_all, record)
        report["revert_drifts"] = drifts
        require(not drifts, "REVERT_DRIFT|count=%d|%s" % (len(drifts), _canonical(drifts)[:4000]))
        export_before = _export_texts(rig, show)
        check_export_unchanged(export_before, _export_texts(rig, show), plan["target_attachment_guids"],
                               "EXPORT_NONDETERMINISTIC", _log)
        backup = tool._backup("PreP01NoteLampsRevert-", run)
        try:
            _write_drama(tool, show, plan, "before", check_side="after")
            check_scope(before_all, _all_rows(_runtime_plain(tool, show, True)), _swap_sides(plan), "after")
            check_export_unchanged(export_before, _export_texts(rig, show), plan["target_attachment_guids"],
                                   "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED", _log)
        except Exception:
            _write_drama(tool, show, plan, "after")
            raise
        materialized = rig._materialize(scores, show)
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        check_scope(before_all, _all_rows(_runtime_plain(tool, readback, True)), _swap_sides(plan), "after")
        archived = RECORD_PATH + ".reverted-" + run
        record["status"] = "reverted"
        tool._write_json(RECORD_PATH, record)
        os.rename(RECORD_PATH, archived)
        report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized})
        _write_json(_report_path(mode, run), report)
        _log("%s_REVERT_OK|run=%s|lamps=%d|show_saved=1|level_saved=1|readback=1|archived=%s"
             % (MARK, run, len(plan["targets"]), archived))
        return report
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        _write_json(_report_path(mode, run), report)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s"
                         % (MARK, run, mode, int(report["saved"]), report["error"][:1500],
                            "" if report["saved"] else "|NOTHING SAVED"))
        raise


def _swap_sides(plan):
    """A plan whose 'after' is the original 'before' (revert scope = base rows -> before values)."""
    swapped = copy.deepcopy(plan)
    for t in swapped["targets"]:
        t["drama_before"], t["drama_after"] = t["drama_after"], t["drama_before"]
    return swapped


def scan_foreign_records_for(scores, plan, saved_dir=None):
    saved = saved_dir or os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    return scores.scan_foreign_records(roots, plan["target_attachment_guids"], exclude=[RECORD_PATH])


def main():
    args_in = globals().get("P01NOTELAMPS_ARGS")
    if unreal is None:
        if args_in is None and os.path.isfile(ARGS_PATH):
            args_in = _read_json(ARGS_PATH)
        args = check_args(args_in or {"mode": "PLAN"})
        require(args["mode"] == "PLAN", "OFFLINE_ONLY_PLAN|mode=%s" % args["mode"])
        return run_plan(args)
    try:
        args = check_args(args_in)
    except Exception as error:  # noqa: BLE001
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    if args["mode"] == "PLAN":
        return run_plan(args)
    return _run(args)


if unreal is not None or __name__ == "__main__":
    main()
