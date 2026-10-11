"""Pure argument, source, and gain validation for Job 195."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import wave


RUN_RE = re.compile(r"^J195-[A-Z0-9][A-Z0-9_-]{2,63}$")
CONFIRM = {
    "APPLY": "APPLY JOB195 ROOM TONE",
    "REVERT": "REVERT JOB195 ROOM TONE",
}
DEFAULT_DESTINATION = "/Game/InfinityStage/Audio/RoomTone"
DEFAULT_ASSET_NAME = "SW_Cameron_RoomTone"
DEFAULT_MPC = "/Game/InfinityStage/Effects/S6/MPC_S6Warp"


class PlanError(ValueError):
    pass


def stable_digest(value):
    blob = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def validate_args(raw):
    args = dict(raw)
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run", "J195-DRY-001")).upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise PlanError("mode must be DRY, APPLY, or REVERT")
    if not RUN_RE.match(run):
        raise PlanError("run must match %s" % RUN_RE.pattern)
    if mode in CONFIRM and args.get("confirm") != CONFIRM[mode]:
        raise PlanError("%s requires exact confirm %r" % (mode, CONFIRM[mode]))
    source = str(args.get("source_wav", "")).strip()
    if mode != "REVERT" and not source:
        raise PlanError("source_wav is required")
    destination = str(args.get("destination_path", DEFAULT_DESTINATION)).rstrip("/")
    asset_name = str(args.get("asset_name", DEFAULT_ASSET_NAME)).strip()
    if not destination.startswith("/Game/") or not asset_name or "/" in asset_name:
        raise PlanError("invalid destination_path or asset_name")
    record = str(args.get("record", "")).strip()
    if mode == "REVERT" and not record:
        raise PlanError("REVERT requires record")
    return {
        "mode": mode,
        "run": run,
        "confirm": args.get("confirm", ""),
        "source_wav": source,
        "destination_path": destination,
        "asset_name": asset_name,
        "asset_path": destination + "/" + asset_name,
        "mpc_path": str(args.get("mpc_path", DEFAULT_MPC)),
        "enable_s6_dip": bool(args.get("enable_s6_dip", True)),
        "record": record,
    }


def resolve_source(project_dir, source):
    candidate = os.path.normpath(source if os.path.isabs(source) else os.path.join(project_dir, source))
    if os.path.isdir(candidate):
        waves = sorted(os.path.join(candidate, name) for name in os.listdir(candidate)
                       if name.lower().endswith(".wav") and os.path.isfile(os.path.join(candidate, name)))
        if len(waves) != 1:
            return {"status": "EMPTY_DIRECTORY" if not waves else "AMBIGUOUS_DIRECTORY",
                    "path": candidate, "candidates": waves}
        candidate = waves[0]
    if not os.path.isfile(candidate):
        return {"status": "MISSING", "path": candidate, "candidates": []}
    if not candidate.lower().endswith(".wav"):
        return {"status": "NOT_WAV", "path": candidate, "candidates": []}
    try:
        with wave.open(candidate, "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
    except (OSError, wave.Error) as exc:
        return {"status": "INVALID_WAV", "path": candidate, "error": str(exc), "candidates": []}
    if rate <= 0 or frames <= 0:
        return {"status": "INVALID_WAV", "path": candidate, "error": "empty audio", "candidates": []}
    digest = hashlib.sha256()
    with open(candidate, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "status": "READY", "path": candidate, "sha256": digest.hexdigest(),
        "duration_s": frames / float(rate), "sample_rate": rate,
        "channels": channels, "sample_width_bytes": width, "candidates": [candidate],
    }


def gain_db(base_db, dip_db, weird, enabled=True):
    values = (float(base_db), float(dip_db), float(weird))
    if not all(math.isfinite(value) for value in values):
        raise PlanError("gain inputs must be finite")
    dip = min(0.0, values[1]) * min(1.0, max(0.0, values[2])) if enabled else 0.0
    return min(12.0, max(-80.0, values[0] + dip))

