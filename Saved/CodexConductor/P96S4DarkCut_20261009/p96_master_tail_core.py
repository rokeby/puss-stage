"""Pure contract for the P04-tail -> S4-cut Master-owned darkness bridge."""
from __future__ import annotations

import hashlib
import json
import math

MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SOURCE_GROUP = "hangar_lights_and_emissives"
EXPECTED_COUNT = 67
COMPILED_S4_CUT_TICK = 29317440


class PlanError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def inventory_from_p96(record):
    plan = record.get("plan") or {}
    rows = [dict(path=row.get("path"), label=row.get("label"))
            for row in plan.get("visibility", []) if row.get("group") == SOURCE_GROUP]
    rows.sort(key=lambda row: (str(row["label"]), str(row["path"])))
    if len(rows) != EXPECTED_COUNT:
        raise PlanError("P96_HANGAR_INVENTORY_COUNT|got=%d|want=%d" % (len(rows), EXPECTED_COUNT))
    if any(not row["path"] or not row["label"] for row in rows):
        raise PlanError("P96_HANGAR_INVENTORY_FIELDS")
    if len({row["path"] for row in rows}) != EXPECTED_COUNT:
        raise PlanError("P96_HANGAR_INVENTORY_DUPLICATE")
    return rows


def master_window(tick_rate, display_rate, tail_frames=2, release_frames=1,
                  cut_tick=COMPILED_S4_CUT_TICK):
    tick_rate, display_rate = float(tick_rate), float(display_rate)
    tail_frames, release_frames = int(tail_frames), int(release_frames)
    if tick_rate <= 0 or display_rate <= 0 or tail_frames not in (1, 2) or release_frames != 1:
        raise PlanError("MASTER_WINDOW_ARGS")
    ticks_per_frame = tick_rate / display_rate
    cut_exact = float(cut_tick) / ticks_per_frame
    cut_frame = int(math.ceil(cut_exact - 1.0e-9))
    start = cut_frame - tail_frames
    release = cut_frame + release_frames
    return {"compiled_cut_tick": int(cut_tick), "cut_frame_exact": cut_exact,
            "cut_frame": cut_frame, "tail_start_frame": start, "release_frame": release,
            "hidden_range": [start, release], "fade_section_range": [start, release + 1],
            "fade_keys": [[start, 0.0], [cut_frame, 1.0], [release, 0.0]],
            "tail_frames": tail_frames, "release_frames": release_frames,
            "tick_rate": tick_rate, "display_rate": display_rate}


def build_plan(record, tick_rate, display_rate, args):
    inventory = inventory_from_p96(record)
    window = master_window(tick_rate, display_rate, args.get("tail_frames", 2),
                           args.get("release_frames", 1), args.get("compiled_s4_cut_tick", COMPILED_S4_CUT_TICK))
    return {"schema": 1, "master": MASTER, "world": WORLD, "source_p96_run": record.get("run"),
            "inventory": inventory, "inventory_count": len(inventory),
            "inventory_digest": digest(inventory), "window": window,
            "ownership": "Master-owned bHidden bridge plus one Master fade; S4-local P96 tracks remain authoritative after release"}
