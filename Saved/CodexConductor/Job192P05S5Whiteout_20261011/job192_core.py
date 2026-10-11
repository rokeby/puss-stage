"""Pure validation/planning for Job 192. No Unreal dependency."""

from __future__ import annotations

import hashlib
import json
import math
import re


RUN_RE = re.compile(r"^J192-[A-Z0-9][A-Z0-9_-]{2,63}$")
CONFIRM = {
    "APPLY": "APPLY JOB192 P05 S5 WHITEOUT",
    "REVERT": "REVERT JOB192 P05 S5 WHITEOUT",
}


def stable_digest(value):
    blob = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def finite(value, label):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("%s must be finite" % label)
    return result


def validate_args(raw):
    mode = str(raw.get("mode", "DRY")).upper()
    run = str(raw.get("run", "J192-DRY-001"))
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise ValueError("mode must be DRY, APPLY, or REVERT")
    if not RUN_RE.match(run):
        raise ValueError("run must match %s" % RUN_RE.pattern)
    if mode in CONFIRM and raw.get("confirm") != CONFIRM[mode]:
        raise ValueError("%s requires exact confirm %r" % (mode, CONFIRM[mode]))
    if mode in CONFIRM and not str(raw.get("decided_by", "")).strip():
        raise ValueError("%s requires decided_by" % mode)
    record = str(raw.get("record", ""))
    if mode == "REVERT" and not record:
        raise ValueError("REVERT requires record")
    return {"mode": mode, "run": run, "confirm": str(raw.get("confirm", "")),
            "decided_by": str(raw.get("decided_by", "")), "record": record}


def compile_score(document):
    if int(document.get("schema", 0)) != 1:
        raise ValueError("score schema must be 1")
    threshold = finite(document.get("seam_mean_luminance_threshold", 0.95), "threshold")
    if not 0.95 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0.95, 1]")
    release = finite(document.get("fade_from_white_seconds", 1.8), "fade_from_white_seconds")
    if not 0.25 <= release <= 6.0:
        raise ValueError("fade_from_white_seconds must be in [0.25, 6]")
    raw = document.get("whiteout_keys")
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError("whiteout_keys needs at least three rows")
    rows = []
    previous = -1.0e30
    for index, item in enumerate(raw):
        if set(item) != {"seconds_from_seam", "amount"}:
            raise ValueError("score row %d fields must be seconds_from_seam and amount" % index)
        second = finite(item["seconds_from_seam"], "row %d seconds" % index)
        amount = finite(item["amount"], "row %d amount" % index)
        if second <= previous:
            raise ValueError("score times must be strictly increasing")
        if not 0.0 <= amount <= 1.0:
            raise ValueError("score amounts must stay in [0, 1]")
        previous = second
        rows.append({"seconds_from_seam": second, "amount": amount})
    at_seam = [row for row in rows if row["seconds_from_seam"] == 0.0]
    if len(at_seam) != 1 or at_seam[0]["amount"] != 1.0:
        raise ValueError("score needs exactly one amount=1 key at the seam")
    if rows[0]["seconds_from_seam"] >= 0 or rows[-1]["seconds_from_seam"] <= 0:
        raise ValueError("score must span both sides of the seam")
    if rows[-1]["seconds_from_seam"] != release or rows[-1]["amount"] != 0.0:
        raise ValueError("last key must release to zero at fade_from_white_seconds")
    return {"threshold": threshold, "release_seconds": release, "rows": rows}


def key_plan(score, seam_tick, tick_rate):
    rate = finite(tick_rate, "tick_rate")
    if rate <= 0:
        raise ValueError("tick_rate must be positive")
    keys = [[int(round(int(seam_tick) + row["seconds_from_seam"] * rate)), row["amount"]]
            for row in score["rows"]]
    if keys[0][0] < 0 or any(left[0] >= right[0] for left, right in zip(keys, keys[1:])):
        raise ValueError("score quantizes to invalid key times")
    return keys


def plan_digest(args, score):
    return stable_digest({"run": args["run"], "score": score})
