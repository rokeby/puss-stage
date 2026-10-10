"""Pure planning for job 104: P06 must play Cameron's complete 125 s track."""
from __future__ import annotations

import hashlib
import json
import math


OLD_TRACK_S = 110.561125
DELIVERED_TRACK_S = 125.0
P06_GUID = "9BFC29C45D47911FF7836BB8537230D2"
INTO_VOID = "/Game/InfinityStage/Audio/Passages/SW_P06_IntoVoid"
CAMERON = "/Game/InfinityStage/Audio/PassageMusic/Cameron_20261005/SW_P06_Walking6_Cameron"
WAV = "DerivedAssets/Audio/WalkingMusic_Cameron_20261005/P06_Walking6.wav"
WAV_SHA256 = "10b2b017fef21308e06b1a197be8c19ee91cf3448ddb8cd8542b460da100c6dc"
DECIDED_BY = "Gary 9 Oct E27"


class PlanError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise PlanError(str(message))


def close(a, b, tolerance=0.02):
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=float(tolerance))


def stable_hash(value):
    wire = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


def validate_args(raw):
    mode = str(raw.get("mode") or "").upper()
    require(mode in ("DRY", "APPLY", "REVERT", "RESUME"), "MODE_INVALID")
    require(raw.get("confirm") == "%s P06 FULL 125" % mode, "CONFIRM_MISMATCH")
    require(raw.get("decided_by") == DECIDED_BY, "DECIDED_BY_MUST_EQUAL_GARY_E27")
    if mode in ("APPLY", "RESUME"):
        require(len(str(raw.get("reviewed_plan_sha256") or "")) == 64, "REVIEW_HASH_REQUIRED")
    return mode


def validate_resume(record, facts):
    """Refuse to repeat import/length work unless the saved partial state is exact."""
    require(record.get("tool") == "p104" and record.get("status") == "prepared",
            "RESUME_RECORD_CONTEXT")
    require(record.get("stage") == "length_applied", "RESUME_STAGE_NOT_LENGTH_APPLIED")
    require(record.get("audio_record") and record.get("length_record"), "RESUME_SUBRECORDS_MISSING")
    plan = record.get("plan") or {}
    decision = plan.get("decision") or {}
    require(decision.get("action") == "IMPORT_AND_SWAP", "RESUME_ORIGINAL_DECISION")
    require(decision.get("target_sound") == CAMERON, "RESUME_TARGET_SOUND")
    require(close(plan.get("target_track_s", 0.0), DELIVERED_TRACK_S, 1.0e-6),
            "RESUME_PLAN_TARGET")
    require(facts.get("assigned_sound") == CAMERON, "RESUME_AUDIO_RAIL_NOT_WALKING6")
    require(bool(facts.get("cameron_asset_exists")), "RESUME_WALKING6_ASSET_MISSING")
    require(close(facts.get("cameron_duration_s", 0.0), DELIVERED_TRACK_S),
            "RESUME_WALKING6_DURATION")
    require(close(facts.get("delivered_wav_duration_s", 0.0), DELIVERED_TRACK_S, 1.0e-6),
            "RESUME_DELIVERED_WAV_DURATION")
    require(close(facts.get("p06_length_s", 0.0), facts.get("cameron_duration_s", 0.0)),
            "RESUME_P06_LENGTH_NOT_WALKING6")
    require(int(facts.get("chain_a_rows", 0)) == int(plan.get("chain_a_rows", -1)),
            "RESUME_CHAIN_A_DRIFT")
    require(int(facts.get("chain_b_rows", 0)) == int(plan.get("chain_b_rows", -1)),
            "RESUME_CHAIN_B_DRIFT")
    require(bool(facts.get("p37_sequence_present")), "RESUME_P37_SEQUENCE_MISSING")
    return plan


def audio_decision(into_void_s, delivered_s, assigned_sound, cameron_exists, cameron_s=None, tolerance=0.02):
    require(close(delivered_s, DELIVERED_TRACK_S, 1.0e-6), "DELIVERED_WAV_NOT_125")
    require(assigned_sound in (INTO_VOID, CAMERON), "P06_ASSIGNED_SOUND_UNEXPECTED|%r" % assigned_sound)
    if assigned_sound == CAMERON:
        require(cameron_exists and close(cameron_s, delivered_s, tolerance), "ASSIGNED_CAMERON_DURATION_WRONG")
        return {"action": "LENGTHEN_ONLY", "target_sound": CAMERON,
                "reason": "Cameron's 125.000 s SoundWave is already imported and assigned"}
    if close(into_void_s, delivered_s, tolerance):
        require(assigned_sound == INTO_VOID or (assigned_sound == CAMERON and cameron_exists),
                "ASSIGNED_CAMERON_ASSET_MISSING")
        return {"action": "LENGTHEN_ONLY", "target_sound": assigned_sound,
                "reason": "SW_P06_IntoVoid already matches the delivered 125.000 s WAV"}
    require(close(into_void_s, OLD_TRACK_S, 0.08), "INTO_VOID_DURATION_UNEXPECTED|%.6f" % into_void_s)
    require(not cameron_exists, "CAMERON_ASSET_EXISTS_BUT_IS_NOT_ASSIGNED|dedupe/reconcile before import")
    return {"action": "IMPORT_AND_SWAP", "target_sound": CAMERON,
            "reason": "SW_P06_IntoVoid is %.6f s, not the delivered 125.000 s WAV" % float(into_void_s)}


def policy_rows(scale):
    return [
        {"item": "P06 Passage length", "policy": "TARGET_TRACK", "old_s": OLD_TRACK_S,
         "new_s": DELIVERED_TRACK_S, "reason": "Gary E27 requires the full delivered track"},
        {"item": "Job 42 celestial sunset/dusk", "policy": "SCALE", "scale": scale,
         "reason": "cycle duration was proportionally fitted to the 110.56 s P06"},
        {"item": "Job 42 car drive-by temporal fields", "policy": "SCALE", "scale": scale,
         "reason": "segment-relative seconds were fitted by p06_retime"},
        {"item": "Job 42 bee-glint keys/ranges", "policy": "SCALE", "scale": scale,
         "reason": "P06-relative Sequencer frames were fitted by p06_retime"},
        {"item": "TOPPLE chain A", "policy": "SCALE", "scale": scale,
         "reason": "one-shot phase clock is fitted to P06-relative creak/impact times"},
        {"item": "TOPPLE chain B mechanisms", "policy": "SCALE", "scale": scale,
         "reason": "108.6 s final slam was fitted to the 110.56 s end"},
        {"item": "P37 domino dust and slam sequence", "policy": "SCALE", "scale": scale,
         "reason": "owned section ranges, trigger keys and audio section use P06-relative frames"},
        {"item": "P06 FX attachment set", "policy": "KEEP_ABSOLUTE", "scale": 1.0,
         "reason": "fire/motes are view-distance activated; wing burn uses route distance, not time"},
        {"item": "Job 85 P06 chandelier staging", "policy": "KEEP_ABSOLUTE", "scale": 1.0,
         "reason": "P06 part is spatial staging only and owns zero P06 sequence tracks"},
    ]


def build_plan(facts):
    decision = audio_decision(facts["into_void_duration_s"], facts["delivered_wav_duration_s"],
                              facts["assigned_sound"], facts["cameron_asset_exists"],
                              facts.get("cameron_duration_s"))
    require(110.50 <= float(facts["p06_length_s"]) <= 110.65, "P06_NOT_AT_EXPECTED_110_6|%.6f" % facts["p06_length_s"])
    require(int(facts.get("chain_a_rows", 0)) > 0, "CHAIN_A_ACTIVE_ROWS_MISSING")
    require(int(facts.get("chain_b_rows", 0)) > 0, "CHAIN_B_ACTIVE_ROWS_MISSING")
    require(bool(facts.get("p37_sequence_present")), "P37_SEQUENCE_MISSING")
    scale = DELIVERED_TRACK_S / OLD_TRACK_S
    plan = {"schema": 1, "decision": decision, "old_track_s": OLD_TRACK_S,
            "target_track_s": DELIVERED_TRACK_S, "scale": scale,
            "old_passage_s": float(facts["p06_length_s"]),
            "passage_scale": DELIVERED_TRACK_S / float(facts["p06_length_s"]),
            "chain_a_rows": int(facts["chain_a_rows"]), "chain_b_rows": int(facts["chain_b_rows"]),
            "policies": policy_rows(scale), "facts": facts,
            "decided_by": DECIDED_BY,
            "proof_limits": ["offline-authored; live DRY must verify all facts",
                             "saved read-back is not rendered acceptance"]}
    plan["plan_sha256"] = stable_hash(plan)
    return plan


def scale_frame(frame, scale):
    return int(round(int(frame) * float(scale)))


def scale_span(span, scale):
    """Scale finite section bounds and preserve infinite ends as infinite."""
    require(isinstance(span, (list, tuple)) and len(span) == 2, "SECTION_SPAN_SHAPE")
    return [None if value is None else scale_frame(value, scale) for value in span]


def retime_phase(rate, offset, old_pass_s, new_pass_s, scale):
    """Preserve p_new(t*scale)==p_old(t) when the phase origin's pass time also moves."""
    new_rate = float(rate) / float(scale)
    new_offset = float(offset) + (float(new_pass_s) / float(scale) - float(old_pass_s)) * float(rate)
    return new_rate, new_offset
