"""Pure planning helpers for Job 191 nested-sequence range repair."""

from __future__ import annotations

import hashlib
import json
import math
import re


RUN_RE = re.compile(r"^J191-NEST-[A-Z0-9][A-Z0-9_-]{2,63}$")
MODES = ("DRY", "APPLY", "REVERT")
CONFIRMS = {mode: "CONFIRM_JOB191_NESTED_%s" % mode for mode in MODES}


def validate_args(args):
    mode = str(args.get("mode", "")).upper()
    run = str(args.get("run", ""))
    if mode not in MODES:
        raise ValueError("mode must be DRY, APPLY, or REVERT")
    if not RUN_RE.fullmatch(run):
        raise ValueError("run must match %s" % RUN_RE.pattern)
    if args.get("confirm") != CONFIRMS[mode]:
        raise ValueError("confirm must be %s" % CONFIRMS[mode])
    if mode == "APPLY" and not str(args.get("plan_sha256", "")):
        raise ValueError("APPLY requires plan_sha256 copied from DRY")
    if mode == "REVERT" and not str(args.get("record", "")):
        raise ValueError("REVERT requires an APPLY record")
    return mode, run


def canonical_digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _seconds(frames, fps):
    return float(frames) / float(fps)


def evaluate_row(row):
    """Mirror InfinityStageNestedSequenceTests.cpp and propose a range-only fix.

    Frame ranges exposed by Sequencer Python are display frames. Offsets are child
    tick-resolution frames, so their seconds use child_tick_fps.
    """
    parent_fps = float(row["parent_display_fps"])
    child_fps = float(row["child_display_fps"])
    child_tick_fps = float(row["child_tick_fps"])
    start, end = map(int, row["section_range"])
    parent_end = int(row["parent_playback"][1])
    child_start, child_end = map(int, row["child_playback"])
    rate = float(row["time_scale"])
    one_frame_s = 1.0 / parent_fps + 0.001

    start_s = _seconds(start, parent_fps)
    end_s = _seconds(end, parent_fps)
    parent_end_s = _seconds(parent_end, parent_fps)
    parent_overrun = end_s > parent_end_s + one_frame_s

    child_span_s = _seconds(child_end - child_start, child_fps)
    offset_s = (int(row["start_offset_ticks"]) + int(row["end_offset_ticks"])) / child_tick_fps
    content_s = max(0.0, child_span_s - offset_s) / rate if rate > 0 else math.inf
    section_s = end_s - start_s
    retimed = rate > 0.0 and not math.isclose(rate, 1.0, abs_tol=1.0e-4)
    retimed_short = bool(retimed and section_s < content_s - one_frame_s)

    result = dict(row)
    result.update({
        "parent_end_seconds": parent_end_s,
        "section_start_seconds": start_s,
        "section_end_seconds": end_s,
        "section_duration_seconds": section_s,
        "content_seconds_after_retime": content_s,
        "one_frame_tolerance_seconds": one_frame_s,
        "parent_overrun": parent_overrun,
        "retimed_content_short": retimed_short,
        "offending": bool(parent_overrun or retimed_short),
    })
    if not result["offending"]:
        result.update(action="none", new_range=[start, end], apply_allowed=False,
                      visible_outside="none")
        return result

    if "/KlaraHookin/" in row["parent_path"] or "/KlaraHookin/" in row["child_path"]:
        result.update(action="skip_klara", new_range=[start, end], apply_allowed=False,
                      visible_outside="not inspected; Klara-owned sequence is protected")
        return result

    new_end = end
    reasons = []
    if parent_overrun:
        new_end = parent_end
        reasons.append("trim_to_parent_end")
    if retimed_short:
        required_frames = int(math.ceil(content_s * parent_fps - 1.0e-9))
        new_end = max(new_end, start + required_frames)
        reasons.append("extend_for_retimed_content")

    if new_end > parent_end:
        result.update(action="blocked", new_range=[start, end], apply_allowed=False,
                      block_reason="required retimed content would exceed the parent playback end",
                      visible_outside="yes; extending the section would expose content or require a parent timing change")
        return result

    if new_end > end:
        result.update(action="blocked", new_range=[start, end], apply_allowed=False,
                      block_reason="a range extension would make previously trimmed child content play",
                      visible_outside="yes; the child playback range declares content beyond the current section")
        return result

    # A trimmed tail after the parent playback end is unreachable today. The
    # child still declares content there, so report it honestly as authored but
    # currently invisible rather than claiming the tail is empty.
    potential_tail_s = max(0.0, min(section_s, content_s) - max(0.0, parent_end_s - start_s))
    visible = ("authored child content exists for %.3f s beyond the parent, but it is already clipped "
               "by the parent playback end and is not currently visible" % potential_tail_s
               if potential_tail_s > 1.0e-6 else
               "no child playback content reaches the trimmed tail")
    result.update(action="+".join(reasons), new_range=[start, new_end], apply_allowed=True,
                  visible_outside=visible)
    return result


def build_plan(rows):
    evaluated = [evaluate_row(row) for row in rows]
    offenders = [row for row in evaluated if row["offending"]]
    repairs = [row for row in offenders if row["apply_allowed"]]
    skipped = [row for row in offenders if row["action"] == "skip_klara"]
    blocked = [row for row in offenders if row["action"] == "blocked"]
    plan = {
        "schema": 1,
        "sections_checked": len(evaluated),
        "offender_count": len(offenders),
        "repair_count": len(repairs),
        "skipped_klara_count": len(skipped),
        "blocked_count": len(blocked),
        "offenders": offenders,
        "repairs": repairs,
        "skipped_klara": skipped,
        "blocked": blocked,
    }
    plan["plan_sha256"] = canonical_digest({k: v for k, v in plan.items() if k != "plan_sha256"})
    return plan


def simulated_test_passes(plan):
    if plan["skipped_klara_count"] or plan["blocked_count"]:
        return False
    for row in plan["offenders"]:
        if not row["apply_allowed"]:
            return False
        changed = dict(row)
        changed["section_range"] = list(row["new_range"])
        if evaluate_row(changed)["offending"]:
            return False
    return True
