"""CURTAIN SLEIGHT (5 Oct, offline-written, NEVER RUN IN UNREAL): the Scene -> Passage curtain moment, owned by
the Interaction (option B of Docs/Conductor/CURTAIN_SLEIGHT_TRANSITION_PLAN_2026-10-05.md, Gary 5 Oct).

Gary's decisions (5 Oct, relayed by the conductor): the Interaction owns the moment; the hangar curtain is the SAME
red velvet drop as the mouth (GC_CurtainDrop_Opening, the drape's own hold sample); a fixed ~60 s shadow play, then a
GO HOLD on the closed curtain; S1-S5 -> I1-I5 (S6 not in scope); build and prove on I1 (S1 -> I1 -> P02) first.

Per Interaction N (frames are the Interaction's display frames; defaults at 25 fps for I1):
  0        cut 1 on "S<N> Sleight Hangar Camera" (level CineCamera on the S<N> hangar root): the hangar wide, from the
           Scene's dock seat.
  3-7 s    the hangar twin drape (a spawnable GeometryCacheActor: same cache, same HOLD sample as the mouth drape)
           flies in from the top of the hangar box; its twin lantern (same incidence direction as the mouth lantern,
           throw scaled to fit the hangar, candela scaled by s^2 = same illuminance at the centre) fades up.
  3-11 s   the hangar camera pushes in to the MATCHED framing (curtain fills the frame).
  7-67 s   shadow play (placeholder card "Shadow Card" on both curtains; no flipbook asset exists).
  10-40 s  fold-down PLACEHOLDER: every lit light under the S<N> hangar root keyed to 0 (no LS_S<N>_HangarFoldDown).
  50 s     THE SLEIGHT: cut 2 in the SAME cut track to "I<N> Sleight Mouth Camera", whose pose relative to the mouth
           drape equals the hangar camera's pose relative to the hangar drape (lens and focus equal).
  52 s     the hangar side strikes (twin drape/card despawn, twin lantern off), unseen.
  67 s     "GO <n> curtain" (HOLD by default in a Sequence cue): the transport settles one frame before it, on the
           still HOLD sample. On GO the existing mouth drape FALL plays (re-timed, not re-baked).
  67 s+    the walk-in (Look & camera's walkin_plan.py, unchanged) from the sleight seat to Passage N+1's start pose,
           ending exactly at the new Interaction end (= release + the old FALL length).
The Interaction is lengthened by this tool itself (the opening_sequence_apply.py method: set_playback_end, re-time,
rebuild the managed Master, MEASURE the Passage key carry and the segment shifts, save nothing on any miss), NOT by
extend_scene_playback.py: that path only extends cut tails and is followed by fit_transition_drapes.py, which
REMOVES every cut section and would destroy the sleight (fit_transition_drapes.py apply_one).

Modes (globals set by a runner):  CURTAIN_SLEIGHT_INTERACTION int 1..5 (required)
                                  CURTAIN_SLEIGHT_APPLY / CURTAIN_SLEIGHT_REVERT  True, else DRY
                                  CURTAIN_SLEIGHT_FIXUP_PILE_DRY / _FIXUP_PILE / _FIXUP_PILE_REVERT  True (I1 only)
                                  CURTAIN_SLEIGHT_RUN_ID optional
PILE (5 Oct, after the I1 apply): the mouth drape's post-release play is FALL [release, release + playable) then PILE
[that, end), a one-tick window at the cache's last tick (the Opening's mechanism, pile_row()). playable is computed
from the live cache length and the FALL's offset (fall_budget_frames()); check_sleight refuses any drape GC section
that would wrap (DRAPE_CACHE_WRAP). I1 was applied before this split: FIXUP_PILE inserts the PILE into the applied I1
drape and touches nothing else. Way out: FIXUP_PILE_REVERT FIRST, then the main REVERT (main_revert_gate enforces it).
Importing with no `unreal` (system Python) never touches Unreal: the pure planner, the checks and the snapshot model
are what test_curtain_sleight.py exercises.

Tiers per claim are in the comments: [decl] read in a file or header (cited), [prec] an in-repo precedent call (cited,
with whether that precedent has run), [inf] inferred. DRY prints an API table (API_TABLE|...) naming the tier of every
Unreal call this tool makes, and refuses nothing on [inf] alone; APPLY judges success only by read-back.
Markers: CURTAIN_SLEIGHT_DRY_OK / _APPLY_OK / _REVERT_OK |run=<id>|..., or CURTAIN_SLEIGHT_STOPPED|run=<id>|reason=...
Never Save All, never end PIE, never reload the level, no Sequencer UI, no unreal objects in module globals.
"""
import copy
import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SEQ_DIR = "/Game/InfinityStage/Interactions"
SEQS = {1: "LS_Interaction_01_WashingTheBoy", 2: "LS_Interaction_02_Turnips", 3: "LS_Interaction_03_ForgetsHisName",
        4: "LS_Interaction_04_GetsAName", 5: "LS_Interaction_05_BecomesKing"}   # fit_transition_drapes.py SEQS
GC_PATH = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
MOUTH_DRAPE = "Transition Drape (baked)"                                       # fit_transition_drapes.py DRAPE
STALLS_TAG = "InfinityStage.TransitionStalls"
MOUTH_TAG = "InfinityStage.Mouth.P%02d"
LANTERN_TAG = "RigAtmos.MouthLantern.P%02d"                                     # mouth_lanterns_apply.py:40,95
ROOT_LABEL = "S%d Hangar Root"
DOORS_RECORD = "hangar_exit_doors_record.json"
EXIT_BLOCK_RECORD = "scene_exit_block_record_S%d.json"
EXIT_BLOCK_PLAN = "scene_exit_block_plan_S%d.json"
HANGAR_PLAN = os.path.join("CodexStructure", "hangar_s%d_plan.json")
WALKIN_REGISTRY = os.path.join("CodexCameraPilot", "walkin_transitions.json")
WALKIN_PLANNER = os.path.join("CodexCameraPilot", "walkin_plan.py")
EXTEND_TOOL = os.path.join("CodexSoftGoods", "extend_scene_playback.py")
BAKE_DIR = os.path.join("CodexSoftGoods", "DropBake")
FOLD_SEQ = "/Game/InfinityStage/RigAtmos/LS_S%d_HangarFoldDown"
OVERRIDES_NAME = "curtain_sleight_overrides.json"
PLAN_PATTERN = "curtain_sleight_plan_I%d.json"
RECORD_PATTERN = "curtain_sleight_record_I%d.json"
DRY_PATTERN = "curtain_sleight_I%d_dry.json"
FIXUP_RECORD_PATTERN = "curtain_sleight_fixup_pile_record_I%d.json"   # exclusive to FIXUP_PILE; never the main record
FIXUP_DRY_PATTERN = "curtain_sleight_fixup_pile_I%d_dry.json"
FIXUP_INTERACTIONS = (1,)                                              # I1 was applied before the PILE split
WALK_TRACK = "WalkIn (Look & camera)"
TRACK_NAME = "CurtainSleight (Conductor)"
TAGS = ("CurtainSleight", "CurtainSleight.I%d")
LABELS = {"hangar_camera": "S%d Sleight Hangar Camera",      # never "... Handoff Camera" (builder .cpp:96-109)
          "mouth_camera": "I%d Sleight Mouth Camera",
          "lantern": "S%d Sleight Twin Lantern"}
BINDING_NAMES = {"hangar_drape": "Sleight Hangar Drape", "hangar_card": "Sleight Hangar Shadow Card",
                 "mouth_card": "Sleight Mouth Shadow Card"}
MARKER_PREFIX = "CST "
CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
CARD_MATERIAL = "/Engine/BasicShapes/BasicShapeMaterial"                         # scene_exit_block.py:103 (placeholder)
CACHE_FPS = 30.0                                                                 # fit_transition_drapes.py CACHE_FPS
SHOW_TICKS_PER_S = 24000.0
ROOT_TOLERANCE_CM = 0.5
ROOT_TOLERANCE_DEG = 0.05
POSE_CHANNELS = {"Location.X": 1, "Location.Y": 2, "Location.Z": 3,           # scene_exit_block.py:753-754
                 "Rotation.X": 6, "Rotation.Y": 4, "Rotation.Z": 5}             # key = (f, x, y, z, pitch, yaw, roll)

DEFAULTS = {
    "extra_tail_frames": 0,         # frames added after the drape fall so the walk-in can start after the GO
    "wide_local_cm": None,          # None = the Scene's dock seat from hangar_s<N>_plan.json, in the root frame
    "wide_focal_mm": 28.0,
    "wide_pitch_deg": 0.0,
    "curtain_from_door_cm": 400.0,  # hangar drape hang plane = door face - this (root x)
    "sleight_distance_cm": 1200.0,  # camera to the drape's hang plane (drape-frame x = 0)
    "sleight_eye_z_cm": 510.0,      # drape frame (the floor under the drape is z = 0)
    "sleight_focal_mm": 35.0,
    "sleight_pitch_deg": 0.0,
    "fly_in_start_s": 3.0, "fly_in_s": 4.0,
    "push_start_s": 3.0, "push_s": 8.0,
    "play_start_s": 7.0, "play_s": 60.0,   # Gary 5 Oct: fixed ~60 s, then a GO hold
    "sleight_s": 50.0,
    "fold_start_s": 10.0, "fold_end_s": 40.0, "fold_margin_s": 2.0,
    "strike_after_s": 2.0,
    "ready_frames": 25,             # the mouth is fully posed this many frames before the cut, and nothing changes
                                    # on either side within this many frames of it
    "card_w_cm": 480.0, "card_h_cm": 270.0, "card_t_cm": 1.0, "card_gap_cm": 1.0, "card_frame_margin_cm": 10.0,
    "cover_margin_cm": 30.0,        # the frame must sit this far inside the drape's hang AABB
    "raise_margin_cm": 50.0,        # flown hem above the wide frame's top edge
    "box_margin_cm": 10.0,
    "lantern_scale": None,          # None = the largest throw <= the mouth's that fits the hangar box (x lantern_fit)
    "lantern_fit": 0.98,
    "go_number": None,              # None = "<N>0"; Cueing owns the numbering (cue_list_tool.py lints duplicates)
    "go_label": "curtain",
    "match_tol_cm": 0.5, "match_tol_deg": 0.05,
    "card_material": CARD_MATERIAL,
    "allow_long_scene": False,      # B: the Scene must be back at its content end first
}


class PlanError(ValueError):
    pass


# =====================================================================================================================
# Pure geometry (yaw-only frames: every frame here has zero pitch and roll; the gatherer refuses tilted roots/drapes)
# =====================================================================================================================

def wrap(deg):
    return (float(deg) + 180.0) % 360.0 - 180.0


def rot_z(v, yaw_deg):
    r = math.radians(float(yaw_deg))
    c, s = math.cos(r), math.sin(r)
    return [v[0] * c - v[1] * s, v[0] * s + v[1] * c, float(v[2])]


def to_world(frame, p):
    d = rot_z(p, frame["yaw"])
    return [frame["loc"][i] + d[i] for i in range(3)]


def to_local(frame, p):
    d = [float(p[i]) - frame["loc"][i] for i in range(3)]
    return rot_z(d, -frame["yaw"])


def compose(parent, local):
    """Frame (loc, yaw) of `local` expressed in `parent`, in parent's parent."""
    return {"loc": to_world(parent, local["loc"]), "yaw": float(parent["yaw"]) + float(local["yaw"])}


def pose_world(frame, rel):
    return {"loc": to_world(frame, rel["loc"]), "pitch": float(rel["pitch"]),
            "yaw": wrap(float(frame["yaw"]) + float(rel["yaw"])), "roll": float(rel["roll"])}


def pose_local(frame, pose):
    return {"loc": to_local(frame, pose["loc"]), "pitch": float(pose["pitch"]),
            "yaw": wrap(float(pose["yaw"]) - float(frame["yaw"])), "roll": float(pose["roll"])}


def direction(pitch, yaw):
    p, y = math.radians(pitch), math.radians(yaw)
    return [math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)]


def frames(seconds, fps):
    return int(round(float(seconds) * float(fps)))


def smoothstep(u):
    u = max(0.0, min(1.0, float(u)))
    return u * u * (3.0 - 2.0 * u)


def half_extent(distance_cm, focal_mm, filmback_mm):
    return (distance_cm * filmback_mm[0] / 2.0 / focal_mm, distance_cm * filmback_mm[1] / 2.0 / focal_mm)


def key_at(keys, frame, index):
    """Linear evaluation of keyed tuples (frame first) at a frame (keys are LINEAR; hold outside)."""
    keys = sorted(keys, key=lambda k: k[0])
    if frame <= keys[0][0]:
        return float(keys[0][index])
    for a, b in zip(keys, keys[1:]):
        if a[0] <= frame <= b[0]:
            if b[0] == a[0]:
                return float(b[index])
            u = (frame - a[0]) / float(b[0] - a[0])
            return float(a[index]) + (float(b[index]) - float(a[index])) * u
    return float(keys[-1][index])


def pose_at(keys, frame):
    return {"loc": [key_at(keys, frame, i) for i in (1, 2, 3)], "pitch": key_at(keys, frame, 4),
            "yaw": key_at(keys, frame, 5), "roll": key_at(keys, frame, 6)}


def bool_at(keys, frame, default=False):
    """Bool channel: constant keys [(frame, value)]."""
    value = default
    for f, v in sorted(keys):
        if f <= frame:
            value = bool(v)
    return value


def parse_go_label(text):
    """Port of InfinityStageGoCues::ParseMarkerLabel (InfinityStageTransportController.cpp:601-645) [decl]:
    upper-case GO, a cue number of digits and dots with at least one digit, optional upper-case HOLD/PASS.
    Returns (number, label, mode) with mode -1 default / 1 HOLD / 0 PASS, or None."""
    words = str(text).strip().split()
    if len(words) < 2 or words[0] != "GO":
        return None
    cand = words[1]
    if not any(ch.isdigit() for ch in cand) or any(not (ch.isdigit() or ch == ".") for ch in cand):
        return None
    mode, start = -1, 2
    if len(words) > 2 and words[2] == "HOLD":
        mode, start = 1, 3
    elif len(words) > 2 and words[2] == "PASS":
        mode, start = 0, 3
    return cand, " ".join(words[start:]), mode


def box_in_frame(center, size):
    lo = [center[i] - size[i] / 2.0 for i in range(3)]
    hi = [center[i] + size[i] / 2.0 for i in range(3)]
    return lo, hi


def inside_hangar(lo, hi, hangar, margin):
    """Root-frame hangar interior: x in [0, door face], |y| <= half_w, z in [floor, height]. Failing axes."""
    bad = []
    if lo[0] < 0.0 + margin or hi[0] > hangar["door_face_x"] + 1.0e-6:
        bad.append("x")
    if lo[1] < -hangar["half_w"] + margin or hi[1] > hangar["half_w"] - margin:
        bad.append("y")
    if lo[2] < hangar["floor_z"] - 1.0e-6 or hi[2] > hangar["height"] - margin:
        bad.append("z")
    return bad


def oriented_box_in_root(root, world_frame, local_lo, local_hi):
    """Corners of a box given in its own (yaw-only) world frame, mapped into the ROOT frame. The oriented guard:
    a world AABB inflates on S2's rotated hangar (scene_exit_block.py:914-916, hangar_exit_doors.py)."""
    pts = []
    for x in (local_lo[0], local_hi[0]):
        for y in (local_lo[1], local_hi[1]):
            for z in (local_lo[2], local_hi[2]):
                pts.append(to_local(root, to_world(world_frame, [x, y, z])))
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def world_aabb(world_frame, local_lo, local_hi):
    pts = [to_world(world_frame, [x, y, z]) for x in (local_lo[0], local_hi[0])
           for y in (local_lo[1], local_hi[1]) for z in (local_lo[2], local_hi[2])]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


# =====================================================================================================================
# Pure planner
# =====================================================================================================================

def ticks_per_frame(tick_rate, fps):
    return float(tick_rate) / float(fps)


def fall_budget_frames(dur_ticks, start_off, end_off, tick_rate, fps):
    """Display frames a GC section can play from `start_off` before UE wraps it. The section window is
    dur - start_off - end_off ticks; MapTimeToAnimation fmods the elapsed time by that window [decl
    MovieSceneGeometryCacheSection.h:71 declares MapTimeToAnimation(ComponentDuration, ...); the fmod itself is
    INFERRED, no private .cpp in UE_5.8, memory ue58-engine-source-limits]. Same rule as
    interaction_walkin_ready.py:185 (fall_cache_budget_frames) and fit_transition_drapes.py:125-126 ('it would LOOP'),
    and the Opening's 250-frame FALL from offset 23200 (opening_sequence_plan.py:235)."""
    return int(math.floor((int(dur_ticks) - int(start_off) - int(end_off)) / ticks_per_frame(tick_rate, fps) + 1.0e-9))


def pile_row(fall_end, end, dur_ticks):
    """The Opening's PILE, exactly: a ONE-TICK window at the cache's last tick (start offset dur - 1, end offset 0),
    looped for the whole section, so it shows the final sample however long the section is.
    Precedent: opening_sequence_plan.py:244 [fall_end, end_frame, dur_ticks - 1, 0]; live read-back
    [299, 375, 263999, 0] (Saved/CodexSoftGoods/opening_hold_at_release_final13.json "after") [measured, read-back
    only]; first authored by curtain_place_opening_and_transitions.py:146-148 (PILE 300-375 at dur - one frame)."""
    return [int(fall_end), int(end), int(dur_ticks) - 1, 0]


def split_fall(release, end, fall_so, fall_eo, dur_ticks, tick_rate, fps):
    """Post-release drape play -> FALL [release, release + playable) + PILE [that, end) holding the last sample.
    PILE is None when the FALL already fits the cache. Returns (fall_row, pile_row_or_None, playable_frames)."""
    playable = fall_budget_frames(dur_ticks, fall_so, fall_eo, tick_rate, fps)
    if playable < 1:
        raise PlanError("DRAPE_CACHE_EMPTY: offsets %d/%d leave no playable frame in a %d-tick cache"
                        % (fall_so, fall_eo, dur_ticks))
    fall_end = min(int(end), int(release) + playable)
    fall = [int(release), fall_end, int(fall_so), int(fall_eo)]
    return fall, (pile_row(fall_end, end, dur_ticks) if fall_end < int(end) else None), playable


def gc_wrap_frame(row, dur_ticks, tick_rate, fps):
    """None if the GC section [a, b) never wraps inside the cache, else the display frame where it wraps.
    A window of <= 1 tick is a HOLD by design (HOLD/PILE loop one sample: fit_transition_drapes.py:151-152)."""
    a, b, so, eo = [int(v) for v in row]
    window = int(dur_ticks) - so - eo
    if window <= 1:
        return None
    tpf = ticks_per_frame(tick_rate, fps)
    if (b - a) * tpf <= window:
        return None
    return a + window / tpf


def drape_gc_rows(mouth_drape):
    rows = [list(mouth_drape["hold"]), list(mouth_drape["fall"])]
    if mouth_drape.get("pile"):
        rows.append(list(mouth_drape["pile"]))
    return rows


def drape_section_failures(mouth_drape, end, dur_ticks, tick_rate, fps, extra_rows=()):
    """The PILE gates, shared by check_sleight and check_fixup. extra_rows: (name, row) of other drape GC sections
    (the hangar twin) that must not wrap either."""
    fail = []
    hold, fall, pile = mouth_drape["hold"], mouth_drape["fall"], mouth_drape.get("pile")
    rows = [("mouth HOLD", hold), ("mouth FALL", fall)] + ([("mouth PILE", pile)] if pile else []) + list(extra_rows)
    for name, row in rows:
        if int(dur_ticks) - int(row[2]) - int(row[3]) <= 0:
            fail.append("DRAPE_CACHE_WINDOW_EMPTY: %s %r (cache %d ticks)" % (name, list(row), dur_ticks))
            continue
        w = gc_wrap_frame(row, dur_ticks, tick_rate, fps)
        if w is not None:
            fail.append("DRAPE_CACHE_WRAP: %s [%d, %d) wraps back to its first sample at frame %.1f (cache %d ticks, "
                        "offsets %d/%d)" % (name, row[0], row[1], w, dur_ticks, row[2], row[3]))
    playable = fall_budget_frames(dur_ticks, fall[2], fall[3], tick_rate, fps)
    if pile:
        if int(pile[0]) != int(fall[1]):
            fail.append("PILE_NOT_ON_FALL_END: PILE starts %d, FALL ends %d" % (pile[0], fall[1]))
        if int(pile[1]) != int(end):
            fail.append("PILE_END: PILE ends %d, playback %d" % (pile[1], end))
        if [int(pile[2]), int(pile[3])] != [int(dur_ticks) - 1, 0]:
            fail.append("PILE_NOT_LAST_SAMPLE: offsets %d/%d, want %d/0 (one tick at the cache end)"
                        % (pile[2], pile[3], int(dur_ticks) - 1))
        if int(fall[1]) - int(fall[0]) != playable:
            fail.append("PILE_EARLY: FALL plays %d frames, the cache allows %d (the cloth would jump to the end sample)"
                        % (int(fall[1]) - int(fall[0]), playable))
    elif int(fall[1]) != int(end):
        fail.append("DRAPE_END: FALL ends %d, playback %d, no PILE" % (fall[1], end))
    return fail


def merged_params(params):
    out = dict(DEFAULTS)
    unknown = sorted(set(params or {}) - set(DEFAULTS))
    if unknown:
        raise PlanError("UNKNOWN_PARAMS: %r" % unknown)
    out.update(params or {})
    return out


def load_walk_planner(path):
    """walkin_plan.py is pure (no Unreal); exec'd into a dict as key_walkin_i1_p02.py:239-246 does [prec, ran DRY]."""
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    ns = {"__name__": "puss_walkin_plan_for_sleight", "__file__": path}
    exec(compile(source, path, "exec"), ns)  # noqa: S102 - Look & camera's reviewed project file.
    if "plan_walk" not in ns or "check_plan" not in ns:
        raise PlanError("WALK_PLANNER_API: plan_walk/check_plan missing")
    ns["SOURCE_SHA256"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return ns


def lantern_twin(lantern, hangar, drape_local, params):
    """The mouth lantern in the drape frame -> the hangar twin, root frame. Same incidence direction at the same
    point on the hang plane; throw scaled by s to fit the hangar box; candela * s^2 keeps the illuminance at that
    point (E = I cos(theta) / d^2). [inf] the gradient across the frame differs: M1 measures it."""
    loc, d = [float(v) for v in lantern["rel_loc"]], [float(v) for v in lantern["rel_dir"]]
    if abs(d[0]) < 1.0e-6 or d[0] <= 0.0:
        raise PlanError("LANTERN_NOT_FACING_THE_DRAPE: rel_dir %r" % d)
    t = -loc[0] / d[0]                      # ray to the hang plane x = 0
    hit = [loc[i] + t * d[i] for i in range(3)]
    margin = float(params["box_margin_cm"])

    def root_point(s):
        p = [hit[i] - s * t * d[i] for i in range(3)]
        return to_world(drape_local, p), p

    if params["lantern_scale"] is not None:
        s = float(params["lantern_scale"])
    else:
        lo_s, hi_s = 0.0, 1.0
        for _ in range(60):                 # bisection on "inside the box"
            mid = (lo_s + hi_s) / 2.0
            rp, _ = root_point(mid)
            if inside_hangar(rp, rp, hangar, margin):
                hi_s = mid
            else:
                lo_s = mid
        s = 1.0 if not inside_hangar(root_point(1.0)[0], root_point(1.0)[0], hangar, margin) else lo_s
        s *= float(params["lantern_fit"]) if s < 1.0 else 1.0
    rp, rel = root_point(s)
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, d[2]))))
    yaw = math.degrees(math.atan2(d[1], d[0]))
    return {"scale": s, "throw_mouth_cm": t, "throw_twin_cm": s * t, "hit_drape_cm": hit,
            "rel_drape": {"loc": rel, "pitch": pitch, "yaw": yaw, "roll": 0.0},
            "root": {"loc": rp, "pitch": pitch, "yaw": wrap(yaw + drape_local["yaw"]), "roll": 0.0},
            "candela": float(lantern["candela"]) * s * s}


def plan_sleight(inputs, params, walk_ns):
    """Everything the tool writes, as data. Deterministic: same inputs + params -> same plan (digest)."""
    p = merged_params(params)
    n, fps = int(inputs["n"]), float(inputs["fps"])
    hangar = inputs["hangar"]
    drape = inputs["drape"]
    aabb = inputs["cache"]["hang_aabb_cm"]
    film = [float(v) for v in inputs["filmback_mm"]]
    old_end = int(inputs["old_end"])
    hold_a, hold_b, hold_so, hold_eo = [int(v) for v in drape["hold"]]
    fall_a, fall_b, fall_so, fall_eo = [int(v) for v in drape["fall"]]
    if hold_a != 0 or hold_b != fall_a or fall_b != old_end:
        raise PlanError("DRAPE_SECTIONS_UNEXPECTED: hold %r fall %r end %d" % (drape["hold"], drape["fall"], old_end))
    fall_len = fall_b - fall_a

    # ---- timeline
    f = {"fly0": frames(p["fly_in_start_s"], fps)}
    f["fly1"] = f["fly0"] + frames(p["fly_in_s"], fps)
    f["push0"] = frames(p["push_start_s"], fps)
    f["push1"] = f["push0"] + frames(p["push_s"], fps)
    f["play0"] = frames(p["play_start_s"], fps)
    f["play1"] = f["play0"] + frames(p["play_s"], fps)
    f["sleight"] = frames(p["sleight_s"], fps)
    f["fold0"] = frames(p["fold_start_s"], fps)
    f["fold1"] = frames(p["fold_end_s"], fps)
    f["strike"] = f["sleight"] + frames(p["strike_after_s"], fps)
    f["release"] = f["play1"]                       # GO frame; the HOLD section ends here
    new_end = f["release"] + fall_len + int(p.get("extra_tail_frames", 0))
    f["end"] = new_end
    delta = new_end - old_end
    if delta <= 0:
        raise PlanError("NOT_LONGER: new end %d <= old end %d (Sequence cues can only be lengthened, "
                        "extend_scene_playback.py:282-283)" % (new_end, old_end))

    # ---- frames of reference
    root = {"loc": [float(v) for v in hangar["root"]["loc"]], "yaw": float(hangar["root"]["rot"][2])}
    drape_local = {"loc": [hangar["door_face_x"] - float(p["curtain_from_door_cm"]), 0.0, hangar["floor_z"]],
                   "yaw": 0.0}
    hangar_drape = compose(root, drape_local)                         # world
    mouth = {"loc": [float(v) for v in drape["frame"]["loc"]], "yaw": float(drape["frame"]["yaw"])}

    # ---- matched camera (drape frame)
    cam_rel = {"loc": [-float(p["sleight_distance_cm"]), 0.0, float(p["sleight_eye_z_cm"])],
               "pitch": float(p["sleight_pitch_deg"]), "yaw": 0.0, "roll": 0.0}
    front_x = float(aabb["x"][0])
    focus_matched = front_x - cam_rel["loc"][0]
    focal_matched = float(p["sleight_focal_mm"])
    matched_root = pose_world(drape_local, cam_rel)                   # root frame (the hangar camera is attached)
    matched_mouth_world = pose_world(mouth, cam_rel)
    wide_loc = p["wide_local_cm"] if p["wide_local_cm"] is not None else hangar["dock_local"]
    wide_root = {"loc": [float(v) for v in wide_loc], "pitch": float(p["wide_pitch_deg"]), "yaw": 0.0, "roll": 0.0}
    focus_wide = (drape_local["loc"][0] + front_x) - wide_root["loc"][0]
    focal_wide = float(p["wide_focal_mm"])

    def cam_key(frame, pose, focal, focus):
        return (int(frame), pose["loc"][0], pose["loc"][1], pose["loc"][2], pose["pitch"], pose["yaw"], pose["roll"],
                float(focal), float(focus))

    hangar_keys = [cam_key(0, wide_root, focal_wide, focus_wide), cam_key(f["push0"], wide_root, focal_wide, focus_wide)]
    for frame in range(f["push0"] + 1, f["push1"] + 1):
        u = smoothstep((frame - f["push0"]) / float(f["push1"] - f["push0"]))
        loc = [wide_root["loc"][i] + (matched_root["loc"][i] - wide_root["loc"][i]) * u for i in range(3)]
        pitch = wide_root["pitch"] + (matched_root["pitch"] - wide_root["pitch"]) * u
        focal = focal_wide * (focal_matched / focal_wide) ** u                      # log-linear (walkin_plan.py:123)
        focus = 1.0 / (1.0 / focus_wide + (1.0 / focus_matched - 1.0 / focus_wide) * u)   # diopters (:127)
        hangar_keys.append(cam_key(frame, {"loc": loc, "pitch": pitch, "yaw": 0.0, "roll": 0.0}, focal, focus))
    hangar_keys.append(cam_key(f["strike"], matched_root, focal_matched, focus_matched))

    # ---- hangar twin drape: fly-in from the top of the box
    top_hung = hangar["floor_z"] + float(aabb["z"][1])
    raise_cm = (hangar["height"] - float(p["box_margin_cm"])) - top_hung
    if raise_cm <= 0.0:
        raise PlanError("NO_FLY_SPACE: the hung drape top %.1f is already at the box top" % top_hung)

    def drape_pose(dz):
        w = to_world(hangar_drape, [0.0, 0.0, dz])
        return (w[0], w[1], w[2], 0.0, hangar_drape["yaw"], 0.0)

    drape_keys = [(f["fly0"],) + drape_pose(raise_cm)]
    for frame in range(f["fly0"] + 1, f["fly1"] + 1):
        u = smoothstep((frame - f["fly0"]) / float(f["fly1"] - f["fly0"]))
        drape_keys.append((frame,) + drape_pose(raise_cm * (1.0 - u)))
    drape_keys.append((f["strike"],) + drape_pose(0.0))

    # ---- shadow cards (drape frame): just in front of the front-most fold, centred on the matched eye line
    card_rel = [front_x - float(p["card_gap_cm"]) - float(p["card_t_cm"]) / 2.0, 0.0, cam_rel["loc"][2]]
    card_size = [float(p["card_t_cm"]), float(p["card_w_cm"]), float(p["card_h_cm"])]
    hangar_card_keys = []
    for key in drape_keys:
        dz = key[3] - hangar_drape["loc"][2]
        w = to_world(hangar_drape, [card_rel[0], card_rel[1], card_rel[2] + dz])
        hangar_card_keys.append((key[0], w[0], w[1], w[2], 0.0, hangar_drape["yaw"], 0.0))
    mouth_card_w = to_world(mouth, card_rel)
    mouth_card_keys = [(0, mouth_card_w[0], mouth_card_w[1], mouth_card_w[2], 0.0, wrap(mouth["yaw"]), 0.0),
                       (f["release"], mouth_card_w[0], mouth_card_w[1], mouth_card_w[2], 0.0, wrap(mouth["yaw"]), 0.0)]

    # ---- twin lantern
    twin = lantern_twin(inputs["lantern"], hangar, drape_local, p)
    lantern_keys = [(0, 0.0), (f["fly0"], 0.0), (f["fly1"], twin["candela"]), (f["strike"], twin["candela"]),
                    (f["strike"] + 1, 0.0)]

    # ---- fold-down placeholder: hangar lights to 0
    lights = []
    for row in sorted(inputs.get("hangar_lights", []), key=lambda r: r["label"]):
        v = float(row["intensity"])
        if v <= 0.0:
            continue                                     # already dark (the lattice glow rests at 0 cd)
        lights.append({"label": row["label"], "keys": [(0, v), (f["fold0"], v), (f["fold1"], 0.0)]})

    # ---- the walk-in from the sleight seat (Look & camera's planner, unchanged)
    landed_s = f["release"] / fps + float(inputs["walk"]["landed_after_release_s"])
    seat = {"x": matched_mouth_world["loc"][0], "y": matched_mouth_world["loc"][1], "z": matched_mouth_world["loc"][2],
            "pitch": matched_mouth_world["pitch"], "yaw": matched_mouth_world["yaw"], "roll": 0.0}
    nxt = inputs["next"]
    target = dict(nxt["start_pose"])
    walk_keys, walk_report = walk_ns["plan_walk"](seat, target, float(nxt["v_end"]), 1.0, new_end / fps, fps,
                                                  focal_matched, float(nxt["focal"]), focus_matched,
                                                  float(nxt["focus"]), landed_s, float(inputs["walk"]["pile_edge_cm"]))
    walk_failures = walk_ns["check_plan"](walk_keys, walk_report, target, float(nxt["v_end"]), landed_s,
                                          float(inputs["walk"]["pile_edge_cm"]))
    walk_start = int(math.floor(walk_report["start_s"] * fps + 1.0e-9))
    mouth_keys = [cam_key(0, matched_mouth_world, focal_matched, focus_matched)]
    for key in walk_keys:
        frame = int(round(key[0] * fps))
        if frame >= max(1, walk_start - 1):
            mouth_keys.append((frame,) + tuple(float(v) for v in key[1:]))

    # ---- mouth drape re-time (not re-baked): the HOLD now ends on the GO frame; the post-release play is FALL for as
    # long as the cache lasts from the FALL's own offset, then PILE holds the last sample (the Opening's mechanism)
    dur_ticks, tick_rate = int(inputs["cache"]["duration_ticks"]), float(inputs["tick_rate"])
    fall_row, pile, playable = split_fall(f["release"], new_end, fall_so, fall_eo, dur_ticks, tick_rate, fps)
    f["fall_end"] = fall_row[1]
    mouth_drape = {"hold": [0, f["release"], hold_so, hold_eo], "fall": fall_row, "pile": pile}
    drape_cache = {"duration_ticks": dur_ticks, "tick_rate": tick_rate, "playable_frames": playable,
                   "fall_end": fall_row[1], "pile": pile}

    go_number = str(p["go_number"]) if p["go_number"] is not None else "%d0" % n
    go_label = "GO %s %s" % (go_number, p["go_label"])
    markers = [(MARKER_PREFIX + "wide", 0), (MARKER_PREFIX + "curtain in", f["fly0"]),
               (MARKER_PREFIX + "curtain hung", f["fly1"]), (MARKER_PREFIX + "play start", f["play0"]),
               (MARKER_PREFIX + "fold start", f["fold0"]), (MARKER_PREFIX + "fold end", f["fold1"]),
               (MARKER_PREFIX + "sleight", f["sleight"]), (MARKER_PREFIX + "hangar strike", f["strike"]),
               (MARKER_PREFIX + "drop", f["release"]), (MARKER_PREFIX + "walk start", walk_start)]
    plan = {
        "n": n, "fps": fps, "frames": f, "old_end": old_end, "new_end": new_end, "delta": delta,
        "delta_s": round(delta / fps, 3),
        "frames_of_reference": {"root": root, "drape_local": drape_local, "hangar_drape_world": hangar_drape,
                                "mouth_drape_world": mouth},
        "hangar_camera": {"label": LABELS["hangar_camera"] % n, "level_rel": wide_root, "keys": hangar_keys,
                          "attached_to": ROOT_LABEL % n},
        "mouth_camera": {"label": LABELS["mouth_camera"] % n, "level_world": matched_mouth_world, "keys": mouth_keys},
        "hangar_drape": {"name": BINDING_NAMES["hangar_drape"], "keys": drape_keys, "raise_cm": raise_cm,
                         "spawn": [[f["fly0"], True], [f["strike"], False]],
                         "gc": [f["fly0"], f["strike"], hold_so, hold_eo], "cache": drape["cache"]},
        "hangar_card": {"name": BINDING_NAMES["hangar_card"], "keys": hangar_card_keys, "size": card_size,
                        "rel_drape": card_rel, "spawn": [[f["fly0"], True], [f["strike"], False]],
                        "material": p["card_material"]},
        "mouth_card": {"name": BINDING_NAMES["mouth_card"], "keys": mouth_card_keys, "size": card_size,
                       "rel_drape": card_rel, "spawn": [[0, True], [f["release"], False]], "material": p["card_material"]},
        "lantern": dict(twin, label=LABELS["lantern"] % n, keys=lantern_keys,
                        copy={k: inputs["lantern"][k] for k in ("outer_deg", "inner_deg", "kelvin", "radius_cm",
                                                                 "shadows")}),
        "lights": lights,
        "fold": {"mode": "placeholder_lights", "sequence": FOLD_SEQ % n},
        "mouth_drape": mouth_drape,
        "drape_cache": drape_cache,
        "cuts":[{"camera": "hangar_camera", "range": [0, f["sleight"]]},
                 {"camera": "mouth_camera", "range": [f["sleight"], new_end]}],
        "markers": markers, "go": [go_label, f["release"]],
        "lens": {"matched_focal_mm": focal_matched, "matched_focus_cm": focus_matched, "filmback_mm": film,
                 "wide_focal_mm": focal_wide, "wide_focus_cm": focus_wide},
        "cam_rel_drape": cam_rel,
        "walk": {"report": walk_report, "failures": walk_failures, "start_frame": walk_start, "landed_s": landed_s,
                 "planner_sha256": walk_ns.get("SOURCE_SHA256")},
        "params": p,
    }
    plan["digest"] = plan_digest(plan)
    return plan


def plan_digest(plan):
    body = {k: v for k, v in plan.items() if k != "digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


# =====================================================================================================================
# Pure checks (every one is falsifiable; test_curtain_sleight.py runs a -control for each)
# =====================================================================================================================

def check_sleight(plan, inputs):
    p, f, fps = plan["params"], plan["frames"], plan["fps"]
    fail = []
    ready = int(p["ready_frames"])
    hangar = inputs["hangar"]
    aabb = inputs["cache"]["hang_aabb_cm"]
    film = plan["lens"]["filmback_mm"]
    ref = plan["frames_of_reference"]
    root, mouth = ref["root"], ref["mouth_drape_world"]

    # 1. timeline order
    order = [("fly0", "fly1"), ("fly1", "play0"), ("play0", "sleight"), ("sleight", "play1")]
    for a, b in order:
        if not f[a] < f[b] and not (a == "fly1" and f[a] == f[b]):
            fail.append("TIMELINE: %s (%d) is not before %s (%d)" % (a, f[a], b, f[b]))
    if f["play1"] - f["play0"] != frames(p["play_s"], fps):
        fail.append("TIMELINE: shadow play is not %.1f s" % p["play_s"])
    if f["push1"] + ready > f["sleight"]:
        fail.append("READY: the hangar camera reaches the matched framing at %d, < %d frames before the cut %d"
                    % (f["push1"], ready, f["sleight"]))
    if f["strike"] < f["sleight"] + ready:
        fail.append("READY: the hangar side strikes at %d, within %d frames after the cut" % (f["strike"], ready))
    if plan["new_end"] != (f["release"] + (inputs["drape"]["fall"][1] - inputs["drape"]["fall"][0])
                           + int(plan.get("params", {}).get("extra_tail_frames", 0))):
        fail.append("TIMELINE: new end is not release + the FALL length + extra_tail_frames")

    # 2. the cut track: exactly one camera change, on one frame, no gap, no overlap
    cuts = sorted(plan["cuts"], key=lambda c: c["range"][0])
    cursor = 0
    for c in cuts:
        a, b = c["range"]
        if a > cursor:
            fail.append("CUT_GAP: [%d, %d) has no cut" % (cursor, a))
        if a < cursor:
            fail.append("CUT_OVERLAP: [%d, %d)" % (a, cursor))
        if b <= a:
            fail.append("CUT_EMPTY: %r" % c)
        cursor = max(cursor, b)
    if cursor != plan["new_end"]:
        fail.append("CUT_GAP: cuts end at %d, playback at %d" % (cursor, plan["new_end"]))
    changes = [cuts[i + 1]["range"][0] for i in range(len(cuts) - 1) if cuts[i]["camera"] != cuts[i + 1]["camera"]]
    if changes != [f["sleight"]] or [c["camera"] for c in cuts] != ["hangar_camera", "mouth_camera"]:
        fail.append("CUT_NOT_ONE_SLEIGHT: camera changes at %r, want exactly [%d] hangar->mouth" % (changes, f["sleight"]))

    # 3. the match, evaluated AT THE CUT FRAME from the keys each side will actually play
    s = f["sleight"]
    hangar_root_pose = pose_at([k[:7] for k in plan["hangar_camera"]["keys"]], s)
    hangar_world = pose_world(root, hangar_root_pose)
    mouth_world_pose = pose_at([k[:7] for k in plan["mouth_camera"]["keys"]], s)
    drape_world_at_s = pose_at(plan["hangar_drape"]["keys"], s)
    hangar_drape_frame = {"loc": drape_world_at_s["loc"], "yaw": drape_world_at_s["yaw"]}
    rel_h = pose_local(hangar_drape_frame, hangar_world)
    rel_m = pose_local(mouth, mouth_world_pose)
    dl = max(abs(rel_h["loc"][i] - rel_m["loc"][i]) for i in range(3))
    da = max(abs(wrap(rel_h[k] - rel_m[k])) for k in ("pitch", "yaw", "roll"))
    if dl > float(p["match_tol_cm"]) or da > float(p["match_tol_deg"]):
        fail.append("MATCH_POSE: relative poses differ by %.3f cm / %.4f deg at the cut (tol %.2f cm / %.2f deg)"
                    % (dl, da, p["match_tol_cm"], p["match_tol_deg"]))
    hk = [k for k in plan["hangar_camera"]["keys"]]
    mk = [k for k in plan["mouth_camera"]["keys"]]
    for idx, name in ((7, "focal"), (8, "focus")):
        if abs(key_at(hk, s, idx) - key_at(mk, s, idx)) > 1.0e-3:
            fail.append("MATCH_LENS: %s %.4f vs %.4f at the cut" % (name, key_at(hk, s, idx), key_at(mk, s, idx)))
    gc, hold = plan["hangar_drape"]["gc"], plan["mouth_drape"]["hold"]
    if gc[2:] != hold[2:]:
        fail.append("MATCH_SAMPLE: hangar drape offsets %r != mouth HOLD offsets %r" % (gc[2:], hold[2:]))
    if plan["hangar_drape"]["cache"] != inputs["drape"]["cache"]:
        fail.append("MATCH_CACHE: %s != %s" % (plan["hangar_drape"]["cache"], inputs["drape"]["cache"]))
    if not (gc[0] <= s < gc[1]):
        fail.append("MATCH_SAMPLE: the hangar drape's GC section [%d, %d) does not cover the cut" % (gc[0], gc[1]))
    hc, mc = plan["hangar_card"], plan["mouth_card"]
    if hc["size"] != mc["size"] or hc["material"] != mc["material"] or hc["rel_drape"] != mc["rel_drape"]:
        fail.append("MATCH_CARD: the two shadow cards differ")
    hcard = pose_at(hc["keys"], s)
    mcard = pose_at(mc["keys"], s)
    dcard = max(abs(to_local(hangar_drape_frame, hcard["loc"])[i] - to_local(mouth, mcard["loc"])[i]) for i in range(3))
    if dcard > float(p["match_tol_cm"]):
        fail.append("MATCH_CARD: card positions relative to their drapes differ by %.3f cm at the cut" % dcard)
    lt = plan["lantern"]
    lam = inputs["lantern"]
    e_mouth = float(lam["candela"]) / (lt["throw_mouth_cm"] / 100.0) ** 2
    e_twin = float(key_at(lt["keys"], s, 1)) / (lt["throw_twin_cm"] / 100.0) ** 2
    if abs(e_twin - e_mouth) > 0.01 * e_mouth:
        fail.append("MATCH_LIGHT: twin illuminance %.4f vs mouth %.4f at the cut" % (e_twin, e_mouth))
    if max(abs(lt["rel_drape"]["loc"][i] - (lt["hit_drape_cm"][i] - lt["scale"] * lt["throw_mouth_cm"]
                                                * direction(lt["rel_drape"]["pitch"], lt["rel_drape"]["yaw"])[i]))
           for i in range(3)) > 0.5:
        fail.append("MATCH_LIGHT: twin lantern is not on the mouth lantern's ray")

    # 4. the curtain covers the whole frame at the cut, on BOTH sides (each from its own world pose)
    for side, cam_world, frame_world in (("hangar", hangar_world, hangar_drape_frame), ("mouth", mouth_world_pose, mouth)):
        rel = pose_local(frame_world, cam_world)
        dist = float(aabb["x"][0]) - rel["loc"][0]
        if dist < 100.0:
            fail.append("COVER_%s: the drape front is %.1f cm from the camera" % (side.upper(), dist))
            continue
        if abs(rel["pitch"]) > 1.0e-6 or abs(rel["yaw"]) > 1.0e-6:
            # tilted views: the frame rectangle is not axis-aligned on the plane; refuse rather than approximate
            fail.append("COVER_%s: camera not square to its drape (pitch %.3f yaw %.3f)" % (side.upper(), rel["pitch"], rel["yaw"]))
            continue
        hw, hh = half_extent(dist, float(key_at(hk if side == "hangar" else mk, s, 7)), film)
        m = float(p["cover_margin_cm"])
        if (rel["loc"][1] - hw < float(aabb["y"][0]) + m or rel["loc"][1] + hw > float(aabb["y"][1]) - m
                or rel["loc"][2] - hh < float(aabb["z"][0]) + m or rel["loc"][2] + hh > float(aabb["z"][1]) - m):
            fail.append("COVER_%s: the frame (%.0f x %.0f cm at %.0f cm) is not inside the drape's hang AABB "
                        "with %.0f cm margin" % (side.upper(), 2 * hw, 2 * hh, dist, m))
    if abs(drape_world_at_s["loc"][2] - ref["hangar_drape_world"]["loc"][2]) > 1.0e-6:
        fail.append("COVER_HANGAR: the hangar drape is not hung (still flying) at the cut")
    if not bool_at(plan["hangar_drape"]["spawn"], s) or not bool_at(plan["mouth_card"]["spawn"], s):
        fail.append("COVER: a drape/card is not spawned at the cut")

    # 5. the GO hold
    go_label, go_frame = plan["go"]
    parsed = parse_go_label(go_label)
    if parsed is None or parsed[2] == 0:
        fail.append("GO_PARSE: %r is not a HOLD GO for the transport parser" % go_label)
    if go_frame < f["play1"]:
        fail.append("GO_BEFORE_PLAY_END: GO at %d, shadow play ends at %d (a HOLD freezes the puppets)" % (go_frame, f["play1"]))
    if go_frame != plan["mouth_drape"]["hold"][1] or plan["mouth_drape"]["fall"][0] != go_frame:
        fail.append("GO_NOT_ON_RELEASE: GO %d, HOLD ends %d, FALL starts %d" % (go_frame, plan["mouth_drape"]["hold"][1],
                                                                            plan["mouth_drape"]["fall"][0]))
    for vamp in inputs.get("vamps", []):
        if vamp[0] <= go_frame <= vamp[1]:
            fail.append("GO_IN_VAMP: %d inside %r (demoted to PASS, .cpp:1023-1037)" % (go_frame, vamp))

    # 6. the mouth is ready before the cut and nothing changes on either side near it
    lo, hi = s - ready, s + ready
    if inputs["drape"]["spawn"][0] > lo:
        fail.append("READY_MOUTH: the mouth drape spawns at %d" % inputs["drape"]["spawn"][0])
    if plan["mouth_drape"]["hold"][0] > lo or plan["mouth_drape"]["hold"][1] <= hi:
        fail.append("READY_MOUTH: the mouth HOLD %r does not span [%d, %d]" % (plan["mouth_drape"]["hold"], lo, hi))
    first_card = min(fr for fr, v in plan["mouth_card"]["spawn"] if v)
    if first_card > lo:
        fail.append("READY_MOUTH: the mouth card spawns at %d (> %d)" % (first_card, lo))
    if plan["mouth_camera"]["keys"][0][0] != 0:
        fail.append("READY_MOUTH: the mouth camera has no frame-0 key")
    for name, keys in (("mouth camera", plan["mouth_camera"]["keys"]), ("mouth card", plan["mouth_card"]["keys"]),
                       ("hangar drape", plan["hangar_drape"]["keys"]), ("hangar card", plan["hangar_card"]["keys"])):
        a, b = pose_at([k[:7] for k in keys], lo), pose_at([k[:7] for k in keys], hi)
        if max(abs(a["loc"][i] - b["loc"][i]) for i in range(3)) > 1.0e-6 or abs(a["pitch"] - b["pitch"]) > 1.0e-6:
            fail.append("STATE_CHANGES_ACROSS_CUT: %s moves within [%d, %d]" % (name, lo, hi))
    for name, spawn in (("hangar drape", plan["hangar_drape"]["spawn"]), ("hangar card", plan["hangar_card"]["spawn"]),
                        ("mouth card", plan["mouth_card"]["spawn"])):
        if any(lo <= fr <= hi for fr, _ in spawn):
            fail.append("STATE_CHANGES_ACROSS_CUT: %s spawn edge within [%d, %d]" % (name, lo, hi))
    lk = plan["lantern"]["keys"]
    if any(lo < k[0] < hi for k in lk) or abs(key_at(lk, lo, 1) - key_at(lk, hi, 1)) > 1.0e-9:
        fail.append("STATE_CHANGES_ACROSS_CUT: the twin lantern changes within [%d, %d]" % (lo, hi))
    if plan["walk"]["start_frame"] < go_frame:
        fail.append("WALK_BEFORE_GO: the walk starts at %d, before the GO hold %d" % (plan["walk"]["start_frame"], go_frame))
    still =[k for k in plan["mouth_camera"]["keys"][1:] if k[0] < plan["walk"]["start_frame"] - 1]
    if still:
        fail.append("WALK_BEFORE_GO: mouth camera keys before the walk block: %r" % [k[0] for k in still][:3])
    fail.extend("WALK_PLAN: " + text for text in plan["walk"]["failures"])

    # 7. the oriented inside-box guard (root frame), hung and flown
    margin = float(p["box_margin_cm"])
    hdw = ref["hangar_drape_world"]
    aabb_lo = [float(aabb["x"][0]), float(aabb["y"][0]), float(aabb["z"][0])]
    aabb_hi = [float(aabb["x"][1]), float(aabb["y"][1]), float(aabb["z"][1])]
    for dz in (0.0, plan["hangar_drape"]["raise_cm"]):
        lo3, hi3 = oriented_box_in_root(root, hdw, [aabb_lo[0], aabb_lo[1], aabb_lo[2] + dz],
                                        [aabb_hi[0], aabb_hi[1], aabb_hi[2] + dz])
        bad = inside_hangar(lo3, hi3, hangar, margin)
        if bad:
            fail.append("BOX: hangar drape (dz=%.0f) leaves the hangar on %s" % (dz, ",".join(bad)))
        clo, chi = box_in_frame([plan["hangar_card"]["rel_drape"][0], plan["hangar_card"]["rel_drape"][1],
                                 plan["hangar_card"]["rel_drape"][2] + dz], plan["hangar_card"]["size"])
        lo3, hi3 = oriented_box_in_root(root, hdw, clo, chi)
        bad = inside_hangar(lo3, hi3, hangar, margin)
        if bad:
            fail.append("BOX: hangar card (dz=%.0f) leaves the hangar on %s" % (dz, ",".join(bad)))
    lp = plan["lantern"]["root"]["loc"]
    bad = inside_hangar(lp, lp, hangar, margin)
    if bad:
        fail.append("BOX: twin lantern leaves the hangar on %s" % ",".join(bad))
    mr = pose_at([k[:7] for k in plan["hangar_camera"]["keys"]], plan["frames"]["push1"])["loc"]
    bad = inside_hangar(mr, mr, hangar, margin)
    if bad:
        fail.append("BOX: matched hangar camera leaves the hangar on %s" % ",".join(bad))
    front_root = ref["drape_local"]["loc"][0] + float(aabb["x"][0])
    for k in plan["hangar_camera"]["keys"]:
        if k[1] > front_root - 100.0:
            fail.append("CAMERA_PATH: hangar camera within 1 m of the drape front at frame %d" % k[0])
            break

    # 8. the flown drape is out of the wide frame when it spawns
    wide = pose_at([k[:7] for k in plan["hangar_camera"]["keys"]], f["fly0"])
    dist = front_root - wide["loc"][0]
    _, hh = half_extent(dist, key_at(plan["hangar_camera"]["keys"], f["fly0"], 7), film)
    hem_flown = ref["drape_local"]["loc"][2] + float(aabb["z"][0]) + plan["hangar_drape"]["raise_cm"]
    if hem_flown < wide["loc"][2] + hh + float(p["raise_margin_cm"]):
        fail.append("FLY_IN_VISIBLE_IN_WIDE: flown hem %.0f, wide frame top %.0f (+%.0f margin)"
                    % (hem_flown, wide["loc"][2] + hh, p["raise_margin_cm"]))

    # 9. the fold is dark before the cut
    limit = f["sleight"] - frames(p["fold_margin_s"], fps)
    for row in plan["lights"]:
        reach = min([k[0] for k in row["keys"] if k[1] == 0.0] or [10 ** 9])
        if reach > limit:
            fail.append("FOLD_LATE: %s reaches 0 at %d, after %d (cut - %.1f s)" % (row["label"], reach, limit, p["fold_margin_s"]))
    if f["fold1"] > limit:
        fail.append("FOLD_LATE: fold end %d after %d" % (f["fold1"], limit))

    # 10. markers
    names = [m[0] for m in plan["markers"]]
    if len(set(names)) != len(names) or any(not m.startswith(MARKER_PREFIX) for m in names):
        fail.append("MARKERS: not unique / not prefixed")
    for label, frame in inputs.get("existing_markers", []):
        parsed_existing = parse_go_label(label)
        if parsed_existing and parse_go_label(go_label) and parsed_existing[0] == parse_go_label(go_label)[0]:
            fail.append("GO_DUPLICATE: %r already in the sequence at %d" % (label, frame))

    # 11. the drape cache: no section wraps; PILE starts where FALL ends and holds the last sample. The cache length
    # and tick rate come from the live inputs (never the plan's own copy), so a stale plan is judged on today's cache.
    fail.extend(drape_section_failures(plan["mouth_drape"], plan["new_end"], int(inputs["cache"]["duration_ticks"]),
                                       float(inputs["tick_rate"]), fps,
                                       extra_rows=[("hangar drape", plan["hangar_drape"]["gc"])]))
    return fail


def live_gates(inputs, params, state):
    """Refusals that come from the live state (no geometry). The harness feeds synthetic inputs."""
    p = merged_params(params)
    refusals, warnings = [], []
    if state == "applied":
        refusals.append("ALREADY_APPLIED: record exists; REVERT first (DRY never plans a second sleight)")
    if state == "orphan":
        refusals.append("ORPHAN_SLEIGHT_STATE: sleight bindings/markers/actors present without an applied record")
    if inputs.get("exit_block_applied"):
        refusals.append("EXIT_BLOCK_STILL_APPLIED: run scene_exit_block_revert_S%d.py first" % inputs["n"])
    scene = inputs.get("scene", {})
    if scene.get("live_end") is not None and scene.get("content_end") is not None \
            and scene["live_end"] != scene["content_end"] and not p["allow_long_scene"]:
        refusals.append("SCENE_STILL_LONG: Scene %d ends at %d, content end %d (option B: shorten it first with "
                        "extend_scene_playback.py new_end_frame=%d)" % (inputs["n"], scene["live_end"],
                                                                       scene["content_end"], scene["content_end"]))
    if inputs.get("external_sound", "").upper().find("UNPAUSABLE") >= 0:
        refusals.append("GO_WOULD_BE_DEMOTED: the Interaction cue is DeclaredUnpausable (.cpp:958-981)")
    if inputs.get("walkin_tracks"):
        refusals.append("WALKIN_PRESENT: %r (revert_walkin_i1_p02.py first; the sleight keys its own walk)"
                        % inputs["walkin_tracks"])
    if inputs.get("nested"):
        refusals.append("NESTED_SEQUENCES_IN_INTERACTION: %r (nested cuts outrank root cuts)" % inputs["nested"])
    if inputs.get("fold_sequence_exists"):
        refusals.append("FOLD_SEQUENCE_EXISTS: %s exists; the nest step is not written (precedent "
                        "Saved/CodexStructure/nest_apply.py:82-85) - extend this tool before APPLY" % (FOLD_SEQ % inputs["n"]))
    for label in inputs.get("bound_lights", []):
        refusals.append("LIGHT_ALREADY_BOUND_IN_INTERACTION: %s" % label)
    for label in inputs.get("existing_labels", []):
        refusals.append("ACTOR_EXISTS: %s" % label)
    if inputs.get("use_sequence_length") is False:
        refusals.append("USE_SEQUENCE_LENGTH_OFF: the Show would not see the longer Interaction")
    if inputs.get("reveal_when_covered"):
        warnings.append("REVEAL_WHEN_COVERED_TRUE: inert while explicit cuts exist (.cpp:1612-1618), but a hand "
                        "edit that removes the cuts would arm it (G6)")
    if inputs.get("external_sound_unread"):
        warnings.append("EXTERNAL_SOUND_UNREAD: could not read the cue's ExternalSound; the GO may be demoted")
    warnings.append("FOLD_PLACEHOLDER: no LS_S%d_HangarFoldDown; hangar lights are keyed to 0 instead (Rig owns the "
                    "real fold)" % inputs["n"])
    warnings.append("SHADOW_PLAY_PLACEHOLDER: plain cards, no flipbook/media asset exists "
                    "(Docs/ShadowPuppetCaptureSpec.md section 7); the mouth card pops off at the release")
    warnings.append("GO_NUMBER_PROVISIONAL: Cueing owns GO numbering; run cue_list_tool.py after APPLY")
    warnings.append("FIT_TOOLS_INCOMPATIBLE: never run fit_transition_drapes.py on this Interaction after APPLY (it "
                    "removes every cut section); verify_transition_fit.py will report it not-ok (cut range)")
    warnings.append("TEST_EXPECTS_STALLS: SavedFixturePIE asserts the Interaction 1 view is the P02 stalls camera "
                    "(InfinityStageEditorAutomationTests.cpp:1061-1062, 1148-1150, 1186-1189); it will FAIL after "
                    "APPLY until a held patch updates it")
    return refusals, warnings


# =====================================================================================================================
# Pure snapshot model (revert exactness). The live REVERT gate compares the same snapshot shape read from Unreal.
# =====================================================================================================================

def normalize_snapshot(snap):
    """Canonical order (bindings by name+guid, tracks by content, sections, cuts, markers, labels)."""
    out = copy.deepcopy(snap)
    for holder in out["bindings"]:
        for t in holder["tracks"]:
            t["sections"] = sorted(list(s) for s in t["sections"])
        holder["tracks"].sort(key=lambda t: json.dumps(t, sort_keys=True))
    out["bindings"].sort(key=lambda b: (b["name"], b["guid"]))
    for t in out["root_tracks"]:
        t["sections"] = sorted(list(s) for s in t["sections"])
    out["root_tracks"].sort(key=lambda t: json.dumps(t, sort_keys=True))
    out["cuts"] = sorted(list(c) for c in out["cuts"])
    out["markers"] = sorted(list(m) for m in out["markers"])
    out["level_labels"] = sorted(out["level_labels"])
    return out


def snapshot_diff(a, b):
    out = []
    for key in sorted(set(a) | set(b)):
        if key not in a or key not in b:
            out.append("%s only in %s" % (key, "after" if key in b else "before"))
        elif json.dumps(a[key], sort_keys=True) != json.dumps(b[key], sort_keys=True):
            out.append("%s differs" % key)
    return out


def _range(a, b):
    return [int(a), int(b)]


def apply_model(snap, plan, guids):
    """The snapshot APPLY must produce from `snap` (Unreal read-back compares the live snapshot with this).
    guids: binding name -> guid of what APPLY created (from the live sequence)."""
    out = copy.deepcopy(snap)
    end, old_end, delta = plan["new_end"], plan["old_end"], plan["delta"]
    out["playback"] = [snap["playback"][0], end]
    for b in out["bindings"]:
        for t in b["tracks"]:
            for s in t["sections"]:
                if b["name"] == MOUTH_DRAPE and t["class"] == "MovieSceneGeometryCacheTrack":
                    continue
                if s[1] in (old_end, old_end + 1):
                    s[1] += delta
        if b["name"] == MOUTH_DRAPE:
            for t in b["tracks"]:
                if t["class"] == "MovieSceneGeometryCacheTrack":
                    t["sections"] = drape_gc_rows(plan["mouth_drape"])     # HOLD, FALL (+ PILE)
    for t in out["root_tracks"]:
        for s in t["sections"]:
            if t["class"] != "MovieSceneCameraCutTrack" and s[1] in (old_end, old_end + 1):
                s[1] += delta
    span = _range(0, end + 1)
    new = [
        (plan["hangar_camera"]["label"], None, [["MovieScene3DTransformTrack", TRACK_NAME, [span]]]),
        (plan["hangar_camera"]["label"] + "/CameraComponent", plan["hangar_camera"]["label"],
         [["MovieSceneFloatTrack", TRACK_NAME, [span]], ["MovieSceneFloatTrack", TRACK_NAME, [span]]]),
        (plan["mouth_camera"]["label"], None, [["MovieScene3DTransformTrack", TRACK_NAME, [span]]]),
        (plan["mouth_camera"]["label"] + "/CameraComponent", plan["mouth_camera"]["label"],
         [["MovieSceneFloatTrack", TRACK_NAME, [span]], ["MovieSceneFloatTrack", TRACK_NAME, [span]]]),
        (plan["lantern"]["label"], None, []),
        (plan["lantern"]["label"] + "/LightComponent", plan["lantern"]["label"], [["MovieSceneFloatTrack", TRACK_NAME, [span]]]),
        (plan["hangar_drape"]["name"], None, [["MovieSceneSpawnTrack", "", [span]],
                                              ["MovieSceneGeometryCacheTrack", "", [list(plan["hangar_drape"]["gc"])]],
                                              ["MovieScene3DTransformTrack", TRACK_NAME, [span]]]),
        (plan["hangar_card"]["name"], None, [["MovieSceneSpawnTrack", "", [span]],
                                             ["MovieScene3DTransformTrack", TRACK_NAME, [span]]]),
        (plan["mouth_card"]["name"], None, [["MovieSceneSpawnTrack", "", [span]],
                                            ["MovieScene3DTransformTrack", TRACK_NAME, [span]]]),
    ]
    for row in plan["lights"]:
        new.append((row["label"], None, []))
        new.append((row["label"] + "/LightComponent", row["label"], [["MovieSceneFloatTrack", TRACK_NAME, [span]]]))
    for name, parent, tracks in new:
        out["bindings"].append({"name": name, "guid": guids[name], "parent": guids[parent] if parent else "",
                                "tracks": [{"class": c, "name": nm, "sections": [list(s) for s in secs]}
                                           for c, nm, secs in tracks]})
    out["cuts"] = sorted([[guids[plan["hangar_camera"]["label"]], 0, plan["frames"]["sleight"], True],
                          [guids[plan["mouth_camera"]["label"]], plan["frames"]["sleight"], end, True]])
    out["markers"] = sorted(out["markers"] + [[m[0], int(m[1])] for m in plan["markers"]]
                            + [[plan["go"][0], int(plan["go"][1])]])
    out["level_labels"] = sorted(out["level_labels"] + [plan["hangar_camera"]["label"], plan["mouth_camera"]["label"],
                                                        plan["lantern"]["label"]])
    return normalize_snapshot(out)


def revert_model(snap_after, record, skip=()):
    """What REVERT does, on the snapshot shape: drop what the record says APPLY created, restore what it changed."""
    out = copy.deepcopy(snap_after)
    ours = set(record["created_binding_guids"])
    out["bindings"] = [b for b in out["bindings"] if b["guid"] not in ours]
    orig = record["snapshot_before"]
    if "sections" not in skip:
        by_guid = {b["guid"]: b for b in orig["bindings"]}
        for b in out["bindings"]:
            if b["guid"] in by_guid:
                b["tracks"] = copy.deepcopy(by_guid[b["guid"]]["tracks"])
        out["root_tracks"] = copy.deepcopy(orig["root_tracks"])
    if "cuts" not in skip:
        out["cuts"] = copy.deepcopy(orig["cuts"])
    if "markers" not in skip:
        ours_m = {(m[0], m[1]) for m in record["created_markers"]}
        out["markers"] = sorted([m for m in out["markers"] if (m[0], m[1]) not in ours_m])
    if "actors" not in skip:
        out["level_labels"] = sorted([lab for lab in out["level_labels"] if lab not in set(record["created_labels"])])
    if "playback" not in skip:
        out["playback"] = list(orig["playback"])
    return normalize_snapshot(out)


# =====================================================================================================================
# FIXUP_PILE (I1 only): the applied record's HOLD/FALL -> HOLD/FALL/PILE on the SAME drape binding. Nothing else moves.
# Order on the way out: FIXUP_PILE_REVERT first, then the main REVERT (main_revert_gate refuses otherwise).
# =====================================================================================================================

def _drape_binding_guid(snap):
    rows = [b for b in snap["bindings"] if b["name"] == MOUTH_DRAPE]
    if len(rows) != 1:
        raise PlanError("FIXUP_DRAPE_BINDING_COUNT: %d" % len(rows))
    return rows[0]["guid"]


def _with_drape_gc(snap, guid, rows):
    out = copy.deepcopy(snap)
    hit = 0
    for b in out["bindings"]:
        if b["guid"] == guid:
            for t in b["tracks"]:
                if t["class"] == "MovieSceneGeometryCacheTrack":
                    t["sections"] = [list(r) for r in rows]
                    hit += 1
    if hit != 1:
        raise PlanError("FIXUP_DRAPE_GC_TRACK_COUNT: %d" % hit)
    return normalize_snapshot(out)


def _drape_gc_of(snap, guid):
    for b in snap["bindings"]:
        if b["guid"] == guid:
            for t in b["tracks"]:
                if t["class"] == "MovieSceneGeometryCacheTrack":
                    return [list(s) for s in t["sections"]]
    return None


def plan_fixup_pile(record, dur_ticks, tick_rate, fps):
    """Pure. From the APPLIED main record (its plan and snapshot_after) and the LIVE cache length / rates."""
    n = int(record.get("interaction", 0))
    if n not in FIXUP_INTERACTIONS:
        raise PlanError("FIXUP_PILE_I1_ONLY: interaction %d" % n)
    if not record.get("applied"):
        raise PlanError("FIXUP_MAIN_NOT_APPLIED")
    plan = record["plan"]
    md = plan["mouth_drape"]
    if md.get("pile"):
        raise PlanError("FIXUP_NOT_NEEDED: the main plan already has a PILE")
    end = int(plan["new_end"])
    hold, fall = [int(v) for v in md["hold"]], [int(v) for v in md["fall"]]
    if fall[1] != end or hold[1] != fall[0]:
        raise PlanError("FIXUP_SECTIONS_UNEXPECTED: hold %r fall %r end %d" % (hold, fall, end))
    guid = _drape_binding_guid(record["snapshot_after"])
    if _drape_gc_of(record["snapshot_after"], guid) != [hold, fall]:
        raise PlanError("FIXUP_RECORD_INCONSISTENT: snapshot_after drape GC %r != plan %r"
                        % (_drape_gc_of(record["snapshot_after"], guid), [hold, fall]))
    new_fall, pile, playable = split_fall(fall[0], end, fall[2], fall[3], dur_ticks, tick_rate, fps)
    if pile is None:
        raise PlanError("FIXUP_NOT_NEEDED: FALL [%d, %d) fits the %d-tick cache" % (fall[0], fall[1], dur_ticks))
    fix = {"interaction": n, "sequence": record["sequence"], "cue_guid": record["cue_guid"],
           "main_run": record["run"], "main_plan_digest": record["plan_digest"], "drape_binding_guid": guid,
           "end": end, "before_rows": [hold, fall], "after_rows": [hold, new_fall, pile],
           "mouth_drape": {"hold": hold, "fall": new_fall, "pile": pile},
           "fall_end": new_fall[1], "pile": pile, "playable_frames": playable,
           "cache_duration_ticks": int(dur_ticks), "tick_rate": float(tick_rate), "fps": float(fps),
           "wrap_frame_before": gc_wrap_frame(fall, dur_ticks, tick_rate, fps)}
    fix["digest"] = hashlib.sha256(json.dumps(fix, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    return fix


def fixup_model(snap_after, fix):
    """The snapshot FIXUP_PILE must produce: only the drape's GC track changes."""
    return _with_drape_gc(snap_after, fix["drape_binding_guid"], fix["after_rows"])


def fixup_revert_model(snap_fixed, fix):
    return _with_drape_gc(snap_fixed, fix["drape_binding_guid"], fix["before_rows"])


def _without_drape_gc(snap, guid):
    out = copy.deepcopy(snap)
    for b in out["bindings"]:
        if b["guid"] == guid:
            b["tracks"] = [t for t in b["tracks"] if t["class"] != "MovieSceneGeometryCacheTrack"]
    return out


def check_fixup(fix, snap_before, snap_expected):
    """Every FIXUP gate (the harness runs a -control for each)."""
    fail = list(drape_section_failures(fix["mouth_drape"], fix["end"], fix["cache_duration_ticks"], fix["tick_rate"],
                                       fix["fps"]))
    guid = fix["drape_binding_guid"]
    if snapshot_diff(_without_drape_gc(snap_before, guid), _without_drape_gc(snap_expected, guid)):
        fail.append("FIXUP_TOUCHES_MORE: %r changes besides the drape GC track"
                    % snapshot_diff(_without_drape_gc(snap_before, guid), _without_drape_gc(snap_expected, guid)))
    if _drape_gc_of(snap_expected, guid) != fix["after_rows"]:
        fail.append("FIXUP_MODEL: expected drape GC %r != %r" % (_drape_gc_of(snap_expected, guid), fix["after_rows"]))
    if _drape_gc_of(snap_before, guid) != fix["before_rows"]:
        fail.append("FIXUP_BEFORE: live drape GC %r != record %r" % (_drape_gc_of(snap_before, guid), fix["before_rows"]))
    if fix["after_rows"][0] != fix["before_rows"][0] or fix["after_rows"][1][0] != fix["before_rows"][1][0] \
            or fix["after_rows"][1][2:] != fix["before_rows"][1][2:]:
        fail.append("FIXUP_MOVES_HOLD_OR_RELEASE: HOLD / FALL start / FALL offsets must not change")
    return fail


def fixup_gate(live_snap, record, fixrec):
    """Refusals for FIXUP_PILE (live state vs records)."""
    out = []
    if int(record.get("interaction", 0)) not in FIXUP_INTERACTIONS:
        out.append("FIXUP_PILE_I1_ONLY")
    if not record.get("applied"):
        out.append("FIXUP_MAIN_NOT_APPLIED: curtain_sleight_record_I%s.json is not applied" % record.get("interaction"))
        return out
    if fixrec.get("applied"):
        out.append("FIXUP_ALREADY_APPLIED: run curtain_sleight_fixup_pile_revert_I1.py first")
        return out
    drift = snapshot_diff(live_snap, record["snapshot_after"])
    if drift:
        out.append("STATE_DRIFTED_SINCE_APPLY: %r (the fixup only runs on exactly what APPLY saved)" % drift)
    return out


def fixup_revert_gate(live_snap, fixrec):
    if not fixrec.get("applied"):
        return ["FIXUP_NOT_APPLIED: no applied curtain_sleight_fixup_pile_record"]
    drift = snapshot_diff(live_snap, fixrec["snapshot_after"])
    return ["STATE_DRIFTED_SINCE_FIXUP: %r (restore from %s instead)" % (drift, fixrec.get("backup"))] if drift else []


def main_revert_gate(live_snap, record, fixrec):
    """The main REVERT runs only on exactly what APPLY saved; an applied FIXUP_PILE must be reverted first."""
    if fixrec.get("applied"):
        return ["FIXUP_PILE_APPLIED: run curtain_sleight_fixup_pile_revert_I%s.py first, then this REVERT"
                % record.get("interaction")]
    drift = snapshot_diff(live_snap, record["snapshot_after"])
    return ["STATE_DRIFTED_SINCE_APPLY|%r (a hand edit or another tool; restore from %s instead)"
            % (drift, record.get("backup"))] if drift else []


# =====================================================================================================================
# DRY report (pure part)
# =====================================================================================================================

def build_dry_report(inputs, params, walk_ns, state):
    refusals, warnings = live_gates(inputs, params, state)
    report = {"state": state, "inputs_digest": hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str)
                                                              .encode("utf-8")).hexdigest()[:20]}
    if state == "applied":
        report.update({"refusals": refusals, "warnings": warnings, "apply_ready": False, "plan": None})
        return report
    try:
        plan = plan_sleight(inputs, params, walk_ns)
    except PlanError as exc:
        refusals.append("PLAN_REFUSED: %s" % exc)
        report.update({"refusals": refusals, "warnings": warnings, "apply_ready": False, "plan": None})
        return report
    failures = check_sleight(plan, inputs)
    refusals.extend("CHECK: " + text for text in failures)
    lt = plan["lantern"]
    if lt["scale"] < 1.0:
        warnings.append("TWIN_LANTERN_SCALED: throw %.0f -> %.0f cm (s=%.3f), %.1f -> %.1f cd; same direction and "
                        "centre illuminance, the falloff across the frame differs (M1 measures)"
                        % (lt["throw_mouth_cm"], lt["throw_twin_cm"], lt["scale"], inputs["lantern"]["candela"],
                           lt["candela"]))
    dc = plan["drape_cache"]
    if dc["pile"]:
        warnings.append("DRAPE_PILE: FALL [%d, %d) is the cache's %d playable frames from offset %d; PILE [%d, %d) "
                        "holds the last sample (tick %d), as the Opening does" % (
                            plan["mouth_drape"]["fall"][0], dc["fall_end"], dc["playable_frames"],
                            plan["mouth_drape"]["fall"][2], dc["pile"][0], dc["pile"][1], dc["pile"][2]))
    warnings.append("SHOW_GROWS: Interaction %d grows by %.2f s (%d frames); later segments shift by that"
                    % (plan["n"], plan["delta_s"], plan["delta"]))
    report.update({"refusals": refusals, "warnings": warnings, "apply_ready": not refusals, "plan": plan,
                   "plan_digest": plan["digest"]})
    return report


# =====================================================================================================================
# Unreal side. Every call carries its tier; the DRY prints the table. NEVER RUN YET.
# =====================================================================================================================

API_TABLE = [
    # (call, tier, citation)
    ("EditorLoadingAndSavingUtils.get_dirty_*_packages", "prec", "scene_exit_block.py:528-532 (applied 4 Oct)"),
    ("UnrealEditorSubsystem.get_game_world/get_editor_world", "prec", "scene_exit_block.py:1122-1127"),
    ("LevelSequenceEditorBlueprintLibrary.get_current_level_sequence", "prec", "scene_exit_block.py:1128"),
    ("Show cues / cue_guid / scene.sequence", "prec", "scene_exit_block.py:615-621, extend_scene_playback.py:265-283"),
    ("cue.scene external_sound", "inf", "InfinityStageTypes field ExternalSound; python name assumed"),
    ("cue.scene reveal_next_passage_when_covered", "inf", "InfinityStageTypes.h:830-875; python name assumed"),
    ("seq.get_bindings/get_display_name/get_id/get_tracks/get_sections", "prec", "fit_transition_drapes.py, scene_exit_block.py:558"),
    ("binding.get_object_template + root relative_location/rotation", "prec", "fit_transition_drapes.py apply_one (applied 30 Sep); reading relative_rotation: inf"),
    ("GC section params start/end_frame_offset (get/set)", "prec", "opening_sequence_apply.py set_gc (applied 4 Oct)"),
    ("GC track add_section + params asset/offsets/play_rate + set_completion_mode(KEEP_STATE) (the PILE)", "prec",
     "curtain_place_opening_and_transitions.py:146-160 (ran 29 Sep); rows read back opening_hold_at_release_final13.json"),
    ("GC track remove_section (FIXUP_PILE_REVERT, main REVERT of a PILE)", "inf",
     "same MovieSceneTrackExtensions.remove_section as the cut track (curtain_sleight APPLY 5 Oct); never on a GC track"),
    ("cache asset_import_data.get_first_filename / start_frame / end_frame", "prec", "fit_transition_drapes.py release_in_cache_s"),
    ("seq.set_playback_end", "prec", "opening_sequence_apply.py:719 (applied 4 Oct); decl MovieSceneSequenceExtensions.h:228"),
    ("section.set_range", "prec", "scene_exit_block.py:761, opening_sequence_apply.py:724; decl MovieSceneSectionExtensions.h:145"),
    ("EditorActorSubsystem.spawn_actor_from_class(CineCameraActor/SpotLight)", "prec", "scene_exit_block.py:897, opening_sequence_apply.py:662"),
    ("actor.attach_to_actor + set_actor_relative_*", "prec", "scene_exit_block.py:741-745"),
    ("CineCameraComponent current_focal_length / focus_settings", "prec", "scene_exit_block.py:906-910"),
    ("CineCameraComponent filmback.sensor_width/height (read)", "inf", "decl CineCameraComponent.h:38, CineCameraSettings.h:21,25"),
    ("SpotLightComponent intensity/temperature/cones/radius/cast_shadows", "prec", "opening_sequence_apply.py:676-684, mouth_lanterns_apply.py:158-177"),
    ("actor.get_component_by_class(LightComponent)", "prec", "scene_exit_block.py:708 (StaticMeshComponent)"),
    ("seq.add_possessable + set_parent", "prec", "scene_exit_block.py:936-941 (applied 4 Oct)"),
    ("seq.add_spawnable_from_class(GeometryCacheActor) + template GC props", "prec", "fit_transition_drapes.py apply_one (applied 30 Sep)"),
    ("seq.add_spawnable_from_class(StaticMeshActor) + template static_mesh/override_materials", "inf",
     "decl StaticMeshComponent.h:131-133 (EditAnywhere StaticMesh), MeshComponent.h:30-31 (OverrideMaterials); deprecated "
     "5.5 but present MovieSceneSequenceExtensions.h:433-435"),
    ("MovieSceneSpawnTrack bool channel default + add_key(False)", "prec", "fit_transition_drapes.py (True at 0); False key: inf, decl MovieSceneScriptingBool.h:79"),
    ("binding.add_track(MovieScene3DTransformTrack) on a SPAWNABLE", "inf", "same proxy call as possessables (scene_exit_block.py:758)"),
    ("MovieSceneFloatTrack set_property_name_and_path (focal/focus/Intensity)", "prec", "key_walkin_i1_p02.py, opening_sequence_apply.py:517-523"),
    ("channel.add_key(time_unit=DISPLAY_RATE, interpolation=LINEAR)", "prec", "scene_exit_block.py:768-770"),
    ("cut track remove_section / add_section / set_camera_binding_id(get_binding_id)", "prec",
     "fit_transition_drapes.py (remove_section, applied); scene_exit_block.py:962-964 (applied)"),
    ("marked frames get_from_sequence/add_to_sequence/delete/sort", "prec", "scene_exit_block.py:726-729, 965-972; opening :291-323"),
    ("binding.remove()", "inf", "decl MovieSceneBindingExtensions.h:144; scene_exit_block REVERT never ran"),
    ("binding.remove_track (returns None)", "prec", "opening_sequence_apply.py:507-513 (measured 4 Oct)"),
    ("InfinityStageSequenceBuilderLibrary.rebuild_managed_master", "prec", "opening_sequence_apply.py:803"),
    ("InfinityStageCameraPilotLibrary.get_passage_frame_range/get_passage_camera_pose", "prec", "key_walkin_i1_p02.py:137-150"),
    ("EditorAssetLibrary.save_asset / EditorLoadingAndSavingUtils.save_map", "prec", "opening_sequence_apply.py:848-852"),
    ("EditorAssetLibrary.does_asset_exist", "prec", "Saved/CodexCameraPilot/key_scene4_score.py:82"),
    ("EditorActorSubsystem.destroy_actor", "prec", "opening_sequence_apply.py:787"),
    ("PostProcessVolume settings read", "prec", "mouth_lanterns_apply.py:100-113"),
    ("MathLibrary.transform_location / inverse_transform_location", "prec", "scene_exit_block.py:916-925"),
]


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _saved():
    return os.path.dirname(_here())


def _load_json(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise PlanError("missing " + path)
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)


def _stop(run, reason):
    unreal.log_error("CURTAIN_SLEIGHT_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    return {"content": sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _content_file(path, ext=".uasset"):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ext


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _by_label(actors):
    index = {}
    for a in actors:
        index.setdefault(str(a.get_actor_label()), []).append(a)
    return index


def _one(index, label, run):
    rows = index.get(label, [])
    if len(rows) != 1:
        _stop(run, "ACTOR_COUNT|label=%s|count=%d" % (label, len(rows)))
    return rows[0]


def _span(section, start, end):
    a = section.get_start_frame() if section.has_start_frame() else start
    b = section.get_end_frame() if section.has_end_frame() else end
    return int(a), int(b)


def _read_markers(seq):
    raw = seq.get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE)  # scene_exit_block.py:728
    return [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)] for m in raw]


def _gc_row(section):
    prm = section.get_editor_property("params")
    return [int(section.get_start_frame()), int(section.get_end_frame()),
            int(prm.get_editor_property("start_frame_offset").value), int(prm.get_editor_property("end_frame_offset").value)]


def _track_rows(tracks, start, end):
    rows = []
    for t in tracks:
        cls = t.get_class().get_name()
        secs = []
        for s in t.get_sections():
            if cls == "MovieSceneGeometryCacheTrack":
                secs.append(_gc_row(s))
            elif cls == "MovieSceneCameraCutTrack":
                continue
            else:
                secs.append(list(_span(s, start, end)))
        rows.append({"class": cls, "name": str(t.get_display_name()) if cls in ("MovieScene3DTransformTrack",
                                                                               "MovieSceneFloatTrack") else "",
                     "sections": sorted(secs)})
    rows.sort(key=lambda t: json.dumps(t, sort_keys=True))
    return rows


def _snapshot(seq, n):
    """The stable fingerprint revert exactness is judged on (same shape as the pure model)."""
    start, end = seq.get_playback_start(), seq.get_playback_end()
    bindings = []
    for b in seq.get_bindings():
        parent = b.get_parent()
        bindings.append({"name": str(b.get_display_name()), "guid": _guid(b.get_id()),
                         "parent": _guid(parent.get_id()) if parent is not None and parent.is_valid() else "",
                         "tracks": _track_rows(b.get_tracks(), start, end)})
    bindings.sort(key=lambda b: (b["name"], b["guid"]))
    cuts = []
    for t in seq.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for s in t.get_sections():
            a, b = _span(s, start, end)
            cuts.append([_guid(s.get_camera_binding_id().get_editor_property("guid")), a, b, bool(s.is_active())])
    labels = sorted(str(a.get_actor_label()) for a in _actors() if a.actor_has_tag(TAGS[1] % n))
    return normalize_snapshot({"playback": [int(start), int(end)], "bindings": bindings,
                               "root_tracks": _track_rows([t for t in seq.get_tracks()
                                                           if t.get_class().get_name() != "MovieSceneCameraCutTrack"],
                                                          start, end),
                               "cuts": cuts, "markers": _read_markers(seq), "level_labels": labels})


def _ext_helpers(run):
    """extend_scene_playback.py helpers, loaded from source without its trailing main() (opening_sequence_apply.py:117-125)."""
    path = os.path.join(_saved(), EXTEND_TOOL)
    with open(path, "r", encoding="utf-8") as handle:
        src = handle.read()
    if not src.rstrip().endswith("\nmain()"):
        _stop(run, "EXTEND_TOOL_SHAPE: extend_scene_playback.py no longer ends with main()")
    ns = {"__name__": "extend_scene_playback_helpers_for_sleight", "__file__": path}
    exec(compile(src.rstrip()[:-len("main()")], path, "exec"), ns)  # noqa: S102
    for need in ("cut_coverage", "compiled_segments", "show_master_match", "segment_deltas",
                 "passage_keys_section_relative", "key_carry_failures"):
        if need not in ns:
            _stop(run, "EXTEND_HELPER_MISSING|" + need)
    return ns


def _scene_bool(scene, *names):
    for name in names:  # memory puss-python-api-gotchas: bools are renamed in Python
        try:
            return bool(scene.get_editor_property(name))
        except Exception:  # noqa: BLE001
            continue
    return None


def _bake_facts(cache, hold_start_off, tick_rate, run):
    """fit_transition_drapes.py release_in_cache_s: the cache's own import chain -> DropBake/<bake_id>.json, then the
    checkpoint of the HELD sample (memory puss-bake-facts-from-artifact-chain)."""
    src = os.path.basename(cache.get_editor_property("asset_import_data").get_first_filename())
    stem = GC_PATH.split("/")[-1] + "_"
    if not (src.startswith(stem) and src.endswith(".abc")):
        _stop(run, "BAKE_UNTRACEABLE|source=%s" % src)
    bake_id = src[len(stem):-4]
    bake = _load_json(os.path.join(_saved(), BAKE_DIR, bake_id + ".json"))
    sample = int(bake["show_start"]) + int(round(hold_start_off / float(tick_rate) * CACHE_FPS))
    cp = bake.get("checkpoints", {}).get(str(sample))
    if not cp:
        _stop(run, "HOLD_SAMPLE_HAS_NO_CHECKPOINT|bake=%s|sample=%d" % (bake_id, sample))
    a = cp["aabb_m"]
    # [inf from rig_limits: downstage_min_y -2.026 m <-> unreal X_min -203 cm] Unreal X = bake y; Unreal Y = +/- bake x
    # (the sign is not recorded, so the y range is the symmetric INNER range, valid for either sign).
    yi = min(abs(a["x"][0]), abs(a["x"][1]))
    dur = int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / CACHE_FPS * tick_rate))
    return {"bake_id": bake_id, "hold_sample_bake_frame": sample, "duration_ticks": dur,
            "hang_aabb_cm": {"x": [a["y"][0] * 100.0, a["y"][1] * 100.0], "y": [-yi * 100.0, yi * 100.0],
                             "z": [a["z"][0] * 100.0, a["z"][1] * 100.0]}}


def _light_component(actor):
    comp = actor.get_component_by_class(unreal.LightComponent)
    return comp


def _ancestors(actor, depth=8):
    out = []
    cur = actor.get_attach_parent_actor()
    while cur is not None and len(out) < depth:
        out.append(cur)
        cur = cur.get_attach_parent_actor()
    return out


def _ppv_rows(actors, point):
    rows = []
    for v in actors:
        if not isinstance(v, unreal.PostProcessVolume):
            continue
        unbound = bool(v.get_editor_property("unbound"))
        o, e = v.get_actor_bounds(False)
        inside = unbound or (abs(point[0] - o.x) <= e.x and abs(point[1] - o.y) <= e.y and abs(point[2] - o.z) <= e.z)
        if not inside:
            continue
        st = v.get_editor_property("settings")   # mouth_lanterns_apply.py:100-113
        rows.append({"ppv": str(v.get_actor_label()), "unbound": unbound, "priority": v.get_editor_property("priority"),
                     "enabled": bool(v.get_editor_property("enabled")),
                     "method": str(st.get_editor_property("auto_exposure_method"))
                     if st.get_editor_property("override_auto_exposure_method") else None,
                     "bias": st.get_editor_property("auto_exposure_bias")
                     if st.get_editor_property("override_auto_exposure_bias") else None,
                     "min_ev": st.get_editor_property("auto_exposure_min_brightness")
                     if st.get_editor_property("override_auto_exposure_min_brightness") else None,
                     "max_ev": st.get_editor_property("auto_exposure_max_brightness")
                     if st.get_editor_property("override_auto_exposure_max_brightness") else None})
    return rows


def _segment_hits(actors, a, b, skip_labels):
    """Actors whose world AABB the segment a->b crosses (slab test). Conservative: a warning, never a refusal."""
    hits, unchecked = [], []
    for actor in actors:
        label = str(actor.get_actor_label())
        if label in skip_labels or isinstance(actor, (unreal.Light, unreal.PostProcessVolume)) or \
                isinstance(actor, unreal.CameraActor):
            continue
        o, e = actor.get_actor_bounds(False)
        if max(e.x, e.y) > 10000.0:
            unchecked.append(label)
            continue
        t0, t1, ok = 0.0, 1.0, True
        for i, (oi, ei) in enumerate(((o.x, e.x), (o.y, e.y), (o.z, e.z))):
            d = b[i] - a[i]
            lo, hi = oi - ei, oi + ei
            if abs(d) < 1.0e-9:
                if a[i] < lo or a[i] > hi:
                    ok = False
                    break
                continue
            u0, u1 = (lo - a[i]) / d, (hi - a[i]) / d
            t0, t1 = max(t0, min(u0, u1)), min(t1, max(u0, u1))
            if t0 > t1:
                ok = False
                break
        if ok:
            hits.append(label)
    return hits, unchecked[:20]


def _gather(n, run):
    """Every live fact the planner needs, as plain data (+ a dict of unreal handles for APPLY/REVERT)."""
    here, saved = _here(), _saved()
    actors = _actors()
    index = _by_label(actors)
    if any(label.startswith("ZZ_") for label in index):
        _stop(run, "ZZ_ACTORS_PRESENT")              # memory puss-benches-are-level-activity
    show = unreal.load_asset(SHOW_PATH)
    prefix = "Interaction %d — " % n
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")).startswith(prefix) and c.get_editor_property("enabled")]
    if len(cues) != 1:
        _stop(run, "INTERACTION_CUE_COUNT|prefix=%s|count=%d" % (prefix, len(cues)))
    cue = cues[0]
    if str(cue.get_editor_property("type")) != str(unreal.InfinityCueType.SEQUENCE):
        _stop(run, "INTERACTION_NOT_SEQUENCE_CUE|%s" % cue.get_editor_property("type"))
    cue_label = str(cue.get_editor_property("label"))
    scene_struct = cue.get_editor_property("scene")
    seq = scene_struct.get_editor_property("sequence")
    seq_path = seq.get_path_name().split(".")[0] if seq is not None else None
    if seq_path != "%s/%s" % (SEQ_DIR, SEQS[n]):
        _stop(run, "INTERACTION_SEQUENCE_UNEXPECTED|%s" % seq_path)
    rate = seq.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    tick = seq.get_tick_resolution()
    tick_rate = tick.numerator / float(tick.denominator)
    start, old_end = int(seq.get_playback_start()), int(seq.get_playback_end())
    if start != 0:
        _stop(run, "INTERACTION_START_NOT_ZERO|%d" % start)
    ext_sound = None
    try:
        ext_sound = str(scene_struct.get_editor_property("external_sound"))
    except Exception:  # noqa: BLE001
        pass

    # mouth drape (fit_transition_drapes.py layout)
    drapes = [b for b in seq.get_bindings() if str(b.get_display_name()) == MOUTH_DRAPE]
    if len(drapes) != 1:
        _stop(run, "MOUTH_DRAPE_COUNT|%d" % len(drapes))
    gct = [t for t in drapes[0].get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"]
    spt = [t for t in drapes[0].get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"]
    if len(gct) != 1 or len(spt) != 1:
        _stop(run, "MOUTH_DRAPE_TRACKS|gc=%d|spawn=%d" % (len(gct), len(spt)))
    gsecs = sorted(gct[0].get_sections(), key=lambda s: s.get_start_frame())
    ssecs = list(spt[0].get_sections())
    if len(gsecs) != 2 or len(ssecs) != 1:
        _stop(run, "MOUTH_DRAPE_SECTIONS|gc=%d|spawn=%d (expected HOLD+FALL and one spawn)" % (len(gsecs), len(ssecs)))
    hold, fall = _gc_row(gsecs[0]), _gc_row(gsecs[1])
    cache = gsecs[1].get_editor_property("params").get_editor_property("geometry_cache_asset")
    if cache is None or cache.get_path_name().split(".")[0] != GC_PATH:
        _stop(run, "MOUTH_DRAPE_CACHE|%s" % (cache.get_path_name() if cache else None))
    tmpl = drapes[0].get_object_template()
    troot = tmpl.get_editor_property("root_component")
    tl = troot.get_editor_property("relative_location")
    tr = troot.get_editor_property("relative_rotation")
    if abs(tr.pitch) > 1.0e-3 or abs(tr.roll) > 1.0e-3:
        _stop(run, "MOUTH_DRAPE_TILTED|%r" % ((tr.roll, tr.pitch, tr.yaw),))
    mouth = {"loc": [float(tl.x), float(tl.y), float(tl.z)], "yaw": float(tr.yaw)}
    cache_facts = _bake_facts(cache, hold[2], tick_rate, run)

    # the stalls cut (replaced) and the cut track
    cut_tracks = list(seq.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    names = {_guid(b.get_id()): str(b.get_display_name()) for b in seq.get_bindings()}
    cut_rows = [[_guid(s.get_camera_binding_id().get_editor_property("guid")), list(_span(s, 0, old_end)), bool(s.is_active())]
                for t in cut_tracks for s in t.get_sections()]

    # hangar (doors record = the landed root, memory puss-level-saved-landed-frame-trap)
    doors = _load_json(os.path.join(here, DOORS_RECORD))
    if doors.get("world") != EXPECTED_WORLD or not doors.get("applied"):
        _stop(run, "DOORS_RECORD_CONTEXT")
    rows = [r for r in doors["plan"]["scenes"] if int(r["scene"]) == n]
    if len(rows) != 1:
        _stop(run, "DOORS_ROW|scene=%d" % n)
    pieces = {pc["role"]: pc for pc in rows[0]["pieces"]}
    leaf = pieces["leaf"]
    dims = rows[0]["hangar_dimensions"]
    root_actor = _one(index, ROOT_LABEL % n, run)
    rl, rr = root_actor.get_actor_location(), root_actor.get_actor_rotation()
    live_root = {"loc": [float(rl.x), float(rl.y), float(rl.z)], "rot": [float(rr.roll), float(rr.pitch), float(rr.yaw)]}
    rec = doors["root_before"][str(n)]
    dl = max(abs(a - b) for a, b in zip(live_root["loc"], rec["location"]))
    dr = max(abs(wrap(a - b)) for a, b in zip(live_root["rot"], rec["rotation"]))
    if dl > ROOT_TOLERANCE_CM or dr > ROOT_TOLERANCE_DEG:
        _stop(run, "ROOT_NOT_LANDED|scene=%d|live=%r|recorded=%r" % (n, live_root, rec))
    if abs(live_root["rot"][0]) > 1.0e-3 or abs(live_root["rot"][1]) > 1.0e-3:
        _stop(run, "ROOT_TILTED|%r" % live_root["rot"])
    root_frame = {"loc": live_root["loc"], "yaw": live_root["rot"][2]}
    hplan = _load_json(os.path.join(saved, HANGAR_PLAN % n))
    dock_local = to_local(root_frame, hplan["dock"]["loc"])
    hangar = {"root": live_root, "half_w": float(dims["half_w"]), "height": float(dims["height"]),
              "depth": float(dims["depth"]),
              "door_face_x": float(leaf["location_cm"][0]) - float(leaf["size_cm"][0]) / 2.0,
              "floor_z": float(leaf["location_cm"][2]) - float(leaf["size_cm"][2]) / 2.0 - 0.5,   # scene_exit_move.door_geometry
              "dock_local": dock_local}

    # mouth lantern
    lanterns = [a for a in actors if a.actor_has_tag(LANTERN_TAG % (n + 1))]
    if len(lanterns) != 1:
        _stop(run, "MOUTH_LANTERN_COUNT|%d" % len(lanterns))
    la = lanterns[0]
    lc = la.get_editor_property("spot_light_component")
    ll, lr = la.get_actor_location(), la.get_actor_rotation()
    rel_dir = rot_z(direction(lr.pitch, lr.yaw), -mouth["yaw"])
    lantern = {"label": str(la.get_actor_label()), "rel_loc": to_local(mouth, [ll.x, ll.y, ll.z]), "rel_dir": rel_dir,
               "candela": float(lc.get_editor_property("intensity")), "kelvin": float(lc.get_editor_property("temperature")),
               "outer_deg": float(lc.get_editor_property("outer_cone_angle")),
               "inner_deg": float(lc.get_editor_property("inner_cone_angle")),
               "radius_cm": float(lc.get_editor_property("attenuation_radius")),
               "shadows": bool(lc.get_editor_property("cast_shadows")),
               "units": str(lc.get_editor_property("intensity_units"))}

    # next Passage start (key_walkin_i1_p02.py:120-160)
    nlabel = "Passage %d" % (n + 1)
    psets = [ps for ps in show.get_editor_property("passage_settings") if str(ps.get_editor_property("label")) == nlabel]
    if len(psets) != 1:
        _stop(run, "NEXT_PASSAGE_COUNT|%s|%d" % (nlabel, len(psets)))
    pguid = psets[0].get_editor_property("passage_guid")
    lib = unreal.InfinityStageCameraPilotLibrary

    def unwrap(result, count, label):
        if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
            if not result[0]:
                _stop(run, label + " returned false")
            result = result[1:]
        if not isinstance(result, tuple) or len(result) != count:
            _stop(run, "%s returned %r" % (label, result))
        return result

    start_tick, _ = unwrap(lib.get_passage_frame_range(show, pguid), 2, "get_passage_frame_range")
    view, focal1, focus1 = unwrap(lib.get_passage_camera_pose(show, pguid, int(start_tick)), 3, "get_passage_camera_pose")
    view2, _, _ = unwrap(lib.get_passage_camera_pose(show, pguid, int(start_tick) + 960), 3, "get_passage_camera_pose+960")
    tloc, trot = view.translation, view.rotation.rotator()
    v_end = (view2.translation - tloc).length() / (960.0 / SHOW_TICKS_PER_S)
    nxt = {"label": nlabel, "start_pose": {"x": float(tloc.x), "y": float(tloc.y), "z": float(tloc.z),
                                           "pitch": float(trot.pitch), "yaw": float(trot.yaw), "roll": float(trot.roll)},
           "focal": float(focal1), "focus": float(focus1), "v_end": float(v_end)}

    # walk registry (Look & camera)
    reg = _load_json(os.path.join(saved, WALKIN_REGISTRY)).get("I%d" % n, {})
    if reg.get("landed_s") is None or reg.get("pile_edge_cm") is None:
        _stop(run, "WALKIN_NOT_READY|I%d|%s" % (n, reg.get("readiness_note")))
    walk = {"landed_after_release_s": float(reg["landed_s"]) - fall[0] / fps, "pile_edge_cm": float(reg["pile_edge_cm"])}

    # filmback: the stalls camera's (APPLY asserts both new cameras read back the same)
    stalls = [a for a in actors if a.actor_has_tag(STALLS_TAG) and a.actor_has_tag(MOUTH_TAG % (n + 1))]
    film = [23.76, 13.365]
    if len(stalls) == 1:
        fb = stalls[0].get_cine_camera_component().get_editor_property("filmback")
        film = [float(fb.get_editor_property("sensor_width")), float(fb.get_editor_property("sensor_height"))]

    # hangar lights (attached under the root), lights already bound in this Interaction
    bound_names = set(names.values())
    lights, bound_lights = [], []
    for a in actors:
        if not isinstance(a, unreal.Light) or root_actor not in _ancestors(a):
            continue
        label = str(a.get_actor_label())
        if label.startswith("S%d Sleight" % n):
            continue
        comp = _light_component(a)
        if comp is None:
            continue
        if label in bound_names:
            bound_lights.append(label)
        lights.append({"label": label, "intensity": float(comp.get_editor_property("intensity"))})

    # markers, vamps, walk tracks, nested, labels, scene state
    markers = _read_markers(seq)
    vs = sorted(f for l, f in markers if l.strip() == "InfinityStage.VampStart")
    ve = sorted(f for l, f in markers if l.strip() == "InfinityStage.VampEnd")
    walk_tracks = [str(b.get_display_name()) for b in seq.get_bindings() for t in b.get_tracks()
                   if str(t.get_display_name()) == WALK_TRACK]
    nested = []
    for tt in (unreal.MovieSceneCinematicShotTrack, unreal.MovieSceneSubTrack):
        for t in seq.find_tracks_by_type(tt):
            nested.extend(str(s.get_sequence().get_path_name()) for s in t.get_sections() if s.get_sequence() is not None)
    own_labels = [LABELS["hangar_camera"] % n, LABELS["mouth_camera"] % n, LABELS["lantern"] % n]
    existing_labels = [lab for lab in own_labels if lab in index]
    scue = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")) == "Scene %d — External Sound" % n]
    scene_state = {"live_end": None, "content_end": None}
    if len(scue) == 1 and scue[0].get_editor_property("scene").get_editor_property("sequence") is not None:
        scene_state["live_end"] = int(scue[0].get_editor_property("scene").get_editor_property("sequence").get_playback_end())
    ebplan = _load_json(os.path.join(here, EXIT_BLOCK_PLAN % n), required=False)
    if ebplan:
        scene_state["content_end"] = int(ebplan["content_end"])
    inputs = {
        "n": n, "fps": fps, "tick_rate": tick_rate, "cue_guid": _guid(cue.get_editor_property("cue_guid")),
        "cue_label": cue_label, "sequence": seq_path, "old_end": old_end,
        "drape": {"frame": mouth, "hold": hold, "fall": fall, "spawn": list(_span(ssecs[0], 0, old_end)),
                  "cache": GC_PATH},
        "cache": cache_facts, "hangar": hangar, "lantern": lantern, "next": nxt, "walk": walk, "filmback_mm": film,
        "hangar_lights": lights, "bound_lights": bound_lights, "existing_markers": markers,
        "vamps": [list(x) for x in zip(vs, ve)], "walkin_tracks": walk_tracks, "nested": nested,
        "existing_labels": existing_labels, "scene": scene_state,
        "exit_block_applied": os.path.isfile(os.path.join(here, EXIT_BLOCK_RECORD % n)),
        "external_sound": ext_sound or "", "external_sound_unread": ext_sound is None,
        "use_sequence_length": _scene_bool(scene_struct, "use_sequence_length", "b_use_sequence_length"),
        "reveal_when_covered": _scene_bool(scene_struct, "reveal_next_passage_when_covered",
                                           "b_reveal_next_passage_when_covered"),
        "fold_sequence_exists": bool(unreal.EditorAssetLibrary.does_asset_exist(FOLD_SEQ % n)),
        "cut_rows": [[g, names.get(g, "?"), r, act] for g, r, act in cut_rows],
    }
    handles = {"show": show, "cue": cue, "seq": seq, "root": root_actor, "lantern": la, "drape": drapes[0],
               "gc_sections": gsecs, "gc_track": gct[0], "spawn_section": ssecs[0], "cut_tracks": cut_tracks, "stalls": stalls,
               "actors": actors, "index": index}
    return inputs, handles


def _state(n, inputs, seq):
    record = _load_json(os.path.join(_here(), RECORD_PATTERN % n), required=False)
    if record.get("applied"):
        return "applied", record
    ours = [b for b in seq.get_bindings() if str(b.get_display_name()) in BINDING_NAMES.values()]
    marks = [m for m in inputs["existing_markers"] if m[0].startswith(MARKER_PREFIX)]
    if ours or marks or inputs["existing_labels"]:
        return "orphan", record
    return "pre", record


def _diagnostics(inputs, plan, handles):
    """Read-only extras for the DRY: exposure volumes at both cameras, possible occluders, lights near the mouth."""
    actors = handles["actors"]
    out = {}
    if plan is None:
        return out
    root = plan["frames_of_reference"]["root"]
    h_cam = pose_world(root, pose_at([k[:7] for k in plan["hangar_camera"]["keys"]], plan["frames"]["sleight"]))
    m_cam = plan["mouth_camera"]["level_world"]
    out["ppv_hangar_camera"] = _ppv_rows(actors, h_cam["loc"])
    out["ppv_mouth_camera"] = _ppv_rows(actors, m_cam["loc"])
    hd = plan["frames_of_reference"]["hangar_drape_world"]
    md = plan["frames_of_reference"]["mouth_drape_world"]
    eye = plan["cam_rel_drape"]["loc"][2]
    skip = {LABELS["hangar_camera"] % plan["n"], LABELS["mouth_camera"] % plan["n"]}
    out["occluders_hangar_view"], out["unchecked_hangar_view"] = _segment_hits(actors, h_cam["loc"], to_world(hd, [-100.0, 0.0, eye]), skip)
    out["occluders_mouth_view"], out["unchecked_mouth_view"] = _segment_hits(actors, m_cam["loc"], to_world(md, [-100.0, 0.0, eye]), skip)
    near = []
    centre = to_world(md, [0.0, 0.0, eye])
    for a in actors:
        if not isinstance(a, unreal.Light):
            continue
        comp = _light_component(a)
        try:
            radius = float(comp.get_editor_property("attenuation_radius"))
        except Exception:  # noqa: BLE001
            continue
        loc = a.get_actor_location()
        if math.dist([loc.x, loc.y, loc.z], centre) <= radius:
            near.append({"label": str(a.get_actor_label()), "intensity": float(comp.get_editor_property("intensity"))})
    out["lights_reaching_mouth_curtain"] = near
    return out


def _api_probe():
    """hasattr checks only (no call): the DRY prints what the INFERRED calls resolve to in this editor."""
    seq_cls = unreal.LevelSequence
    return {
        "LevelSequence.add_spawnable_from_class": hasattr(seq_cls, "add_spawnable_from_class"),
        "LevelSequence.get_marked_frames_from_sequence": hasattr(seq_cls, "get_marked_frames_from_sequence"),
        "MovieSceneBindingProxy.remove": hasattr(unreal.MovieSceneBindingProxy, "remove"),
        "MovieSceneBindingProxy.get_object_template": hasattr(unreal.MovieSceneBindingProxy, "get_object_template"),
        "GeometryCacheActor class": hasattr(unreal, "GeometryCacheActor"),
        "MovieSceneSpawnTrack class": hasattr(unreal, "MovieSceneSpawnTrack"),
        "CameraFilmbackSettings struct": hasattr(unreal, "CameraFilmbackSettings"),
        "LightComponent class": hasattr(unreal, "LightComponent"),
    }


def run_dry(n, run, params):
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE_DRY|" + json.dumps(_census()))
    inputs, handles = _gather(n, run)
    state, record = _state(n, inputs, handles["seq"])
    walk_ns = load_walk_planner(os.path.join(_saved(), WALKIN_PLANNER))
    report = build_dry_report(inputs, params, walk_ns, state)
    report["diagnostics"] = _diagnostics(inputs, report.get("plan"), handles)
    if report["diagnostics"].get("occluders_hangar_view") or report["diagnostics"].get("occluders_mouth_view"):
        report["warnings"].append("VIEW_MAY_BE_OCCLUDED (world AABB, conservative): hangar %r mouth %r"
                                  % (report["diagnostics"].get("occluders_hangar_view"),
                                     report["diagnostics"].get("occluders_mouth_view")))
    report["api_table"] = [{"call": c, "tier": t, "cite": s} for c, t, s in API_TABLE]
    report["api_probe"] = _api_probe()
    report["inputs"] = inputs
    report["cue_guid"] = inputs["cue_guid"]
    out = os.path.join(_here(), DRY_PATTERN % n)
    _write_json(out, report)
    if report.get("plan") is not None and state == "pre":
        _write_json(os.path.join(_here(), PLAN_PATTERN % n),
                    {"interaction": n, "run": run, "cue_guid": inputs["cue_guid"], "plan_digest": report["plan_digest"],
                     "inputs_digest": report["inputs_digest"], "params": params, "new_end": report["plan"]["new_end"],
                     "old_end": inputs["old_end"]})
    for row in API_TABLE:
        if row[1] == "inf":
            unreal.log("CURTAIN_SLEIGHT_API_INFERRED|run=%s|%s|%s" % (run, row[0], row[2]))
    unreal.log("CURTAIN_SLEIGHT_API_PROBE|run=%s|%s" % (run, json.dumps(report["api_probe"], sort_keys=True)))
    for text in report["refusals"]:
        unreal.log_warning("CURTAIN_SLEIGHT_REFUSAL|run=%s|%s" % (run, text))
    for text in report["warnings"]:
        unreal.log("CURTAIN_SLEIGHT_WARNING|run=%s|%s" % (run, text))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    plan = report.get("plan") or {}
    unreal.log("CURTAIN_SLEIGHT_DRY_OK|run=%s|interaction=%d|cue_guid=%s|mutated=0|state=%s|old_end=%d|new_end=%s|"
               "sleight=%s|go=%s|apply_ready=%d|refusals=%d|warnings=%d|digest=%s|report=%s"
               % (run, n, inputs["cue_guid"], state, inputs["old_end"], plan.get("new_end"),
                  (plan.get("frames") or {}).get("sleight"), plan.get("go"), int(report["apply_ready"]),
                  len(report["refusals"]), len(report["warnings"]), report.get("plan_digest"), out))


# ---------------------------------------------------------------------------------------------------------------- APPLY

def _key_pose(binding, keys, end, run, label, scale=(1.0, 1.0, 1.0)):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    if track is None:
        _stop(run, "ADD_TRANSFORM_TRACK|%s|NOTHING SAVED; Don't-Save restart" % label)
    track.set_display_name(TRACK_NAME)
    section = track.add_section()
    section.set_range(0, end + 1)
    ch = {str(c.channel_name): c for c in section.get_all_channels()}
    missing = sorted((set(POSE_CHANNELS) | {"Scale.X", "Scale.Y", "Scale.Z"}) - set(ch))
    if missing:
        _stop(run, "CHANNELS_MISSING|%s|%r|NOTHING SAVED; Don't-Save restart" % (label, missing))
    for name, value in zip(("Scale.X", "Scale.Y", "Scale.Z"), scale):
        ch[name].set_default(float(value))            # unkeyed scale would evaluate 0 (scene_exit_block.py:775)
    for key in keys:
        for name, idx in POSE_CHANNELS.items():
            if ch[name].add_key(unreal.FrameNumber(int(key[0])), float(key[idx]),
                                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=unreal.MovieSceneKeyInterpolation.LINEAR) is None:
                _stop(run, "ADD_KEY_NONE|%s|%s|%d|NOTHING SAVED; Don't-Save restart" % (label, name, key[0]))
    return section


def _key_float(binding, prop, path, keys, end, run, label):
    track = binding.add_track(unreal.MovieSceneFloatTrack)
    if track is None:
        _stop(run, "ADD_FLOAT_TRACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, path))
    track.set_property_name_and_path(unreal.Name(prop), path)
    track.set_display_name(TRACK_NAME)
    section = track.add_section()
    section.set_range(0, end + 1)
    chans = list(section.get_all_channels())
    if len(chans) != 1:
        _stop(run, "FLOAT_CHANNELS|%s|%d|NOTHING SAVED; Don't-Save restart" % (label, len(chans)))
    for frame, value in keys:
        if chans[0].add_key(unreal.FrameNumber(int(frame)), float(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                            interpolation=unreal.MovieSceneKeyInterpolation.LINEAR) is None:
            _stop(run, "ADD_KEY_NONE|%s|%s|%d|NOTHING SAVED; Don't-Save restart" % (label, path, frame))
    return section


def _spawn_track(binding, spawn_keys, end):
    # UE creates a spawn track itself when a spawnable is added (measured 5 Oct: a second, tool-added track made
    # PRESAVE_SNAPSHOT_MISMATCH). Reuse that one, with exactly one section, instead of adding another.
    existing = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"]
    st = existing[0] if existing else binding.add_track(unreal.MovieSceneSpawnTrack)
    for extra in existing[1:]:
        binding.remove_track(extra)
    for old in list(st.get_sections()):
        st.remove_section(old)
    ss = st.add_section()
    ss.set_range(0, end + 1)
    ch = ss.get_all_channels()[0]
    ch.set_default(False)
    for frame, value in spawn_keys:
        ch.add_key(unreal.FrameNumber(int(frame)), bool(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return ss


def _camera_actor(subsystem, label, tags, attach_to, rel_or_world, focal, focus):
    rot = unreal.Rotator(roll=float(rel_or_world["roll"]), pitch=float(rel_or_world["pitch"]), yaw=float(rel_or_world["yaw"]))
    cam = subsystem.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(*rel_or_world["loc"]), rot, False)
    cam.set_actor_label(label)
    cam.tags = [unreal.Name(t) for t in tags]
    if attach_to is not None:
        cam.attach_to_actor(attach_to, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                            unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
        cam.set_actor_relative_location(unreal.Vector(*rel_or_world["loc"]), False, True)
        cam.set_actor_relative_rotation(rot, False, True)
    comp = cam.get_cine_camera_component()
    comp.set_editor_property("current_focal_length", float(focal))
    fs = comp.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    fs.set_editor_property("manual_focus_distance", float(focus))
    comp.set_editor_property("focus_settings", fs)
    return cam, comp


def _add_pile_section(track, row, cache, run):
    """The Opening's PILE section, copied call for call from curtain_place_opening_and_transitions.py:146-160 [prec,
    ran 29 Sep; the live rows read back 30 Sep, opening_hold_at_release_final13.json "after"]: add_section, set_range,
    params asset + start/end offsets + play_rate 1.0, write params back, KEEP_STATE completion if the call exists.
    Returns (section, completion_mode_set)."""
    if cache is None or cache.get_path_name().split(".")[0] != GC_PATH:
        _stop(run, "PILE_CACHE|%s|NOTHING SAVED; Don't-Save restart" % (cache.get_path_name() if cache else None))
    s = track.add_section()
    if s is None:
        _stop(run, "PILE_ADD_SECTION_NONE|NOTHING SAVED; Don't-Save restart")
    s.set_range(int(row[0]), int(row[1]))
    p = s.get_editor_property("params")
    p.set_editor_property("geometry_cache_asset", cache)
    p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(row[2])))
    p.set_editor_property("end_frame_offset", unreal.FrameNumber(int(row[3])))
    p.set_editor_property("play_rate", 1.0)
    s.set_editor_property("params", p)
    completion = False
    try:
        s.set_completion_mode(unreal.MovieSceneCompletionMode.KEEP_STATE)
        completion = True
    except Exception:  # noqa: BLE001 - the Opening tolerated its absence too
        pass
    return s, completion


def _drape_gc_assets(seq):
    """Asset path of every mouth-drape GC section (read-back: the PILE must play the same cache)."""
    out = []
    for b in seq.get_bindings():
        if str(b.get_display_name()) != MOUTH_DRAPE:
            continue
        for t in b.get_tracks():
            if t.get_class().get_name() == "MovieSceneGeometryCacheTrack":
                for s in t.get_sections():
                    a = s.get_editor_property("params").get_editor_property("geometry_cache_asset")
                    out.append(a.get_path_name().split(".")[0] if a is not None else None)
    return out


def _static_spawnable(seq, name, mesh, material, size, keys, spawn_keys, end, run):
    b = seq.add_spawnable_from_class(unreal.StaticMeshActor)          # [inf] see API_TABLE
    if b is None or not b.is_valid():
        _stop(run, "SPAWNABLE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % name)
    b.set_display_name(name)
    tmpl = b.get_object_template()
    comp = tmpl.get_editor_property("static_mesh_component")
    comp.set_editor_property("static_mesh", mesh)
    comp.set_editor_property("override_materials", [material])
    k0 = keys[0]
    root = tmpl.get_editor_property("root_component")
    root.set_editor_property("relative_location", unreal.Vector(k0[1], k0[2], k0[3]))
    root.set_editor_property("relative_rotation", unreal.Rotator(roll=k0[6], pitch=k0[4], yaw=k0[5]))
    scale = [float(v) / 100.0 for v in size]
    root.set_editor_property("relative_scale3d", unreal.Vector(*scale))
    _spawn_track(b, spawn_keys, end)
    _key_pose(b, keys, end, run, name, scale=scale)
    if comp.get_editor_property("static_mesh") is None:
        _stop(run, "TEMPLATE_MESH_NOT_SET|%s|NOTHING SAVED; Don't-Save restart" % name)
    return b


def _bind_light(seq, actor, run):
    b = seq.add_possessable(actor)
    if b is None or not b.is_valid():
        _stop(run, "BIND_LIGHT|%s|NOTHING SAVED; Don't-Save restart" % actor.get_actor_label())
    b.set_display_name(str(actor.get_actor_label()))
    kb = seq.add_possessable(_light_component(actor))
    if kb is None or not kb.is_valid():
        _stop(run, "BIND_LIGHT_COMPONENT|%s|NOTHING SAVED; Don't-Save restart" % actor.get_actor_label())
    kb.set_parent(b)
    kb.set_display_name(str(actor.get_actor_label()) + "/LightComponent")
    return b, kb


def run_apply(n, run, params, overrides):
    if not (str(overrides.get("decided_by") or "").strip() and n in [int(x) for x in overrides.get("interactions", [])]):
        _stop(run, "NOT_DECIDED|curtain_sleight_overrides.json needs decided_by and interactions containing %d" % n)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|" + json.dumps(_census()))
    inputs, h = _gather(n, run)
    state, _ = _state(n, inputs, h["seq"])
    walk_ns = load_walk_planner(os.path.join(_saved(), WALKIN_PLANNER))
    report = build_dry_report(inputs, params, walk_ns, state)
    if report["refusals"]:
        _stop(run, "REFUSED|" + " || ".join(report["refusals"]))
    plan = report["plan"]
    plan_file = _load_json(os.path.join(_here(), PLAN_PATTERN % n), required=False)
    if plan_file.get("plan_digest") != plan["digest"] or plan_file.get("cue_guid") != inputs["cue_guid"]:
        _stop(run, "PLAN_CHANGED_SINCE_DRY|dry=%s|now=%s|cue %s vs %s|rerun DRY"
              % (plan_file.get("plan_digest"), plan["digest"], plan_file.get("cue_guid"), inputs["cue_guid"]))
    seq, show, root = h["seq"], h["show"], h["root"]
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    ext = _ext_helpers(run)
    master = unreal.load_asset(MASTER_PATH)
    seq_path = inputs["sequence"]

    # 0. backups + record (BEFORE any mutation)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreCurtainSleight-I%d-%s" % (n, run))
    os.makedirs(backup, exist_ok=False)
    copied = []
    for src in (_content_file(seq_path), _content_file(MASTER_PATH), _content_file(SHOW_PATH),
                _content_file(EXPECTED_WORLD, ".umap")):
        if not os.path.isfile(src):
            _stop(run, "BACKUP_SOURCE_MISSING|" + src)
        dst = os.path.join(backup, os.path.basename(src))
        shutil.copy2(src, dst)
        if os.path.getsize(dst) != os.path.getsize(src):
            _stop(run, "BACKUP_SIZE_MISMATCH|" + src)
        copied.append(dst)
    snap0 = _snapshot(seq, n)
    segs0 = ext["compiled_segments"](show)
    keys0 = ext["passage_keys_section_relative"](master)
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    record = {"schema_version": 1, "run": run, "interaction": n, "cue_guid": inputs["cue_guid"], "cue_label": inputs["cue_label"],
              "sequence": seq_path, "world": EXPECTED_WORLD, "backup": backup, "backup_files": copied, "applied": False,
              "plan_digest": plan["digest"], "plan": plan, "root_pose": inputs["hangar"]["root"],
              "snapshot_before": snap0, "decided_by": overrides.get("decided_by")}
    _write_json(record_path, record)

    # 1. lengthen + re-time what exists (opening_sequence_apply.py:716-725 method)
    old_end, end, delta = plan["old_end"], plan["new_end"], plan["delta"]
    tails = []
    for b in seq.get_bindings():
        for t in b.get_tracks():
            cls = t.get_class().get_name()
            if str(b.get_display_name()) == MOUTH_DRAPE and cls == "MovieSceneGeometryCacheTrack":
                continue
            for s in t.get_sections():
                if s.has_end_frame() and s.get_end_frame() in (old_end, old_end + 1):
                    tails.append((s, int(s.get_start_frame()) if s.has_start_frame() else 0, int(s.get_end_frame()) + delta))
    for t in seq.get_tracks():
        if t.get_class().get_name() == "MovieSceneCameraCutTrack":
            continue
        for s in t.get_sections():
            if s.has_end_frame() and s.get_end_frame() in (old_end, old_end + 1):
                tails.append((s, int(s.get_start_frame()) if s.has_start_frame() else 0, int(s.get_end_frame()) + delta))
    seq.modify()
    seq.set_playback_end(end)
    for s, a, b in tails:
        s.set_range(a, b)
    for s, row in zip(h["gc_sections"], (plan["mouth_drape"]["hold"], plan["mouth_drape"]["fall"])):
        s.set_range(int(row[0]), int(row[1]))
        prm = s.get_editor_property("params")
        prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(row[2])))
        prm.set_editor_property("end_frame_offset", unreal.FrameNumber(int(row[3])))
        s.set_editor_property("params", prm)
    pile_completion = None
    if plan["mouth_drape"].get("pile"):
        _, pile_completion = _add_pile_section(h["gc_track"], plan["mouth_drape"]["pile"],
                                               h["gc_sections"][1].get_editor_property("params")
                                               .get_editor_property("geometry_cache_asset"), run)

    # 2. level actors, composed against the LIVE landed root
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    tags = [TAGS[0], TAGS[1] % n]
    hc = plan["hangar_camera"]
    hcam, hcomp = _camera_actor(subsystem, hc["label"], tags, root, hc["level_rel"],
                                plan["lens"]["wide_focal_mm"], plan["lens"]["wide_focus_cm"])
    mc = plan["mouth_camera"]
    mcam, mcomp = _camera_actor(subsystem, mc["label"], tags, None, mc["level_world"],
                                plan["lens"]["matched_focal_mm"], plan["lens"]["matched_focus_cm"])
    lt = plan["lantern"]
    lrot = unreal.Rotator(roll=0.0, pitch=float(lt["root"]["pitch"]), yaw=float(lt["root"]["yaw"]))
    lant = subsystem.spawn_actor_from_class(unreal.SpotLight, root.get_actor_location(), root.get_actor_rotation(), False)
    lant.set_actor_label(lt["label"])
    lant.tags = [unreal.Name(t) for t in tags]
    lant.attach_to_actor(root, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                         unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    lant.set_actor_relative_location(unreal.Vector(*lt["root"]["loc"]), False, True)
    lant.set_actor_relative_rotation(lrot, False, True)
    lcomp = lant.get_editor_property("spot_light_component")
    lcomp.set_mobility(unreal.ComponentMobility.MOVABLE)
    lcomp.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    lcomp.set_editor_property("intensity", 0.0)          # dark wherever the Interaction is not driving it
    lcomp.set_editor_property("use_temperature", True)
    for prop, key in (("temperature", "kelvin"), ("outer_cone_angle", "outer_deg"), ("inner_cone_angle", "inner_deg"),
                      ("attenuation_radius", "radius_cm")):
        lcomp.set_editor_property(prop, float(lt["copy"][key]))
    lcomp.set_editor_property("cast_shadows", bool(lt["copy"]["shadows"]))
    # oriented inside-box guard on what was actually placed (root frame)
    root_xf = root.get_actor_transform()
    for actor, label in ((lant, "lantern"), (hcam, "hangar camera")):
        local = unreal.MathLibrary.inverse_transform_location(root_xf, actor.get_actor_location())
        bad = inside_hangar([local.x, local.y, local.z], [local.x, local.y, local.z], inputs["hangar"],
                            float(plan["params"]["box_margin_cm"])) if label == "lantern" else []
        if bad:
            _stop(run, "SPAWNED_OUTSIDE_HANGAR_BOX|%s|%r|NOTHING SAVED; Don't-Save restart" % (label, bad))
    for comp, label in ((hcomp, "hangar"), (mcomp, "mouth")):
        fb = comp.get_editor_property("filmback")
        got = [float(fb.get_editor_property("sensor_width")), float(fb.get_editor_property("sensor_height"))]
        if max(abs(a - b) for a, b in zip(got, plan["lens"]["filmback_mm"])) > 1.0e-3:
            _stop(run, "FILMBACK_MISMATCH|%s|%r vs plan %r|NOTHING SAVED; Don't-Save restart"
                  % (label, got, plan["lens"]["filmback_mm"]))

    # 3. spawnables: hangar twin drape (fit_transition_drapes.py apply_one layout), the two cards
    cache = unreal.load_asset(GC_PATH)
    cube = unreal.load_asset(CUBE_PATH)
    card_mi = unreal.load_asset(plan["mouth_card"]["material"])
    if cache is None or cube is None or card_mi is None:
        _stop(run, "ASSET_LOAD|cache=%s|cube=%s|card=%s|NOTHING SAVED; Don't-Save restart" % (cache, cube, card_mi))
    hd = plan["hangar_drape"]
    db = seq.add_spawnable_from_class(unreal.GeometryCacheActor)
    db.set_display_name(hd["name"])
    tmpl = db.get_object_template()
    k0 = hd["keys"][0]
    troot = tmpl.get_editor_property("root_component")
    troot.set_editor_property("relative_location", unreal.Vector(k0[1], k0[2], k0[3]))
    troot.set_editor_property("relative_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=k0[5]))
    gcomp = tmpl.get_editor_property("geometry_cache_component")
    gcomp.set_editor_property("geometry_cache", cache)
    gcomp.set_editor_property("running", True)       # running=False freezes frame 0 (fit_transition_drapes.py)
    gcomp.set_editor_property("looping", False)
    _spawn_track(db, hd["spawn"], end)
    gt = db.add_track(unreal.MovieSceneGeometryCacheTrack)
    gs = gt.add_section()
    gs.set_range(int(hd["gc"][0]), int(hd["gc"][1]))
    prm = gs.get_editor_property("params")
    prm.set_editor_property("geometry_cache_asset", cache)
    prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(hd["gc"][2])))
    prm.set_editor_property("end_frame_offset", unreal.FrameNumber(int(hd["gc"][3])))
    gs.set_editor_property("params", prm)
    _key_pose(db, hd["keys"], end, run, hd["name"])
    hcb = _static_spawnable(seq, plan["hangar_card"]["name"], cube, card_mi, plan["hangar_card"]["size"],
                            plan["hangar_card"]["keys"], plan["hangar_card"]["spawn"], end, run)
    mcb = _static_spawnable(seq, plan["mouth_card"]["name"], cube, card_mi, plan["mouth_card"]["size"],
                            plan["mouth_card"]["keys"], plan["mouth_card"]["spawn"], end, run)

    # 4. possessables: cameras (transform + lens), lantern, hangar lights
    created = {}
    for cam, comp, data, label in ((hcam, hcomp, hc, hc["label"]), (mcam, mcomp, mc, mc["label"])):
        cb = seq.add_possessable(cam)
        cb.set_display_name(label)
        kb = seq.add_possessable(comp)
        kb.set_parent(cb)
        kb.set_display_name(label + "/CameraComponent")
        _key_pose(cb, [k[:7] for k in data["keys"]], end, run, label)
        _key_float(kb, "CurrentFocalLength", "CurrentFocalLength", [(k[0], k[7]) for k in data["keys"]], end, run, label)
        _key_float(kb, "ManualFocusDistance", "FocusSettings.ManualFocusDistance", [(k[0], k[8]) for k in data["keys"]],
                   end, run, label)
        created[label], created[label + "/CameraComponent"] = cb, kb
    lb, lkb = _bind_light(seq, lant, run)
    _key_float(lkb, "Intensity", "Intensity", lt["keys"], end, run, lt["label"])
    created[lt["label"]], created[lt["label"] + "/LightComponent"] = lb, lkb
    idx = _by_label(_actors())
    for row in plan["lights"]:
        b, kb = _bind_light(seq, _one(idx, row["label"], run), run)
        _key_float(kb, "Intensity", "Intensity", row["keys"], end, run, row["label"])
        created[row["label"]], created[row["label"] + "/LightComponent"] = b, kb
    created[hd["name"]], created[plan["hangar_card"]["name"]], created[plan["mouth_card"]["name"]] = db, hcb, mcb

    # 5. the cut track: the stalls cut out, the two sleight sections in (one track)
    if len(h["cut_tracks"]) != 1:
        _stop(run, "CUT_TRACK_COUNT|%d|NOTHING SAVED; Don't-Save restart" % len(h["cut_tracks"]))
    ct = h["cut_tracks"][0]
    for s in list(ct.get_sections()):
        ct.remove_section(s)
    if list(ct.get_sections()):
        _stop(run, "CUT_REMOVE_LEFT_SECTIONS|NOTHING SAVED; Don't-Save restart")
    for row in plan["cuts"]:
        s = ct.add_section()
        s.set_camera_binding_id(seq.get_binding_id(created[plan[row["camera"]]["label"]]))
        s.set_range(int(row["range"][0]), int(row["range"][1]))   # ONE call; [a, b)

    # 6. markers (CST + the GO)
    for label, frame in list(plan["markers"]) + [tuple(plan["go"])]:
        mf = unreal.MovieSceneMarkedFrame()
        mf.set_editor_property("label", label)
        mf.set_editor_property("frame_number", unreal.FrameNumber(int(frame)))
        seq.add_marked_frame_to_sequence(mf, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    seq.sort_marked_frames()
    guids = {name: _guid(b.get_id()) for name, b in created.items()}
    record.update({"created_binding_guids": sorted(guids.values()), "binding_guids": guids,
                   "created_markers": [list(m) for m in plan["markers"]] + [list(plan["go"])],
                   "created_labels": [hc["label"], mc["label"], lt["label"]]})
    _write_json(record_path, record)

    # 7. Master rebuild + measured carry (opening_sequence_apply.py:803-829)
    result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    if not result:
        _stop(run, "REBUILD_FAILED|%r|NOTHING SAVED; Don't-Save restart; backup %s" % (result, backup))
    segs1 = ext["compiled_segments"](show)
    rows, bad = ext["segment_deltas"](segs0, segs1, inputs["cue_label"], round(delta / plan["fps"], 3))
    if bad:
        _stop(run, "SEGMENT_SHIFTS|%r|NOTHING SAVED; Don't-Save restart" % bad[:3])
    carry = ext["key_carry_failures"](keys0, ext["passage_keys_section_relative"](master))
    if carry:
        _stop(run, "KEY_CARRY|%r|NOTHING SAVED; Don't-Save restart" % carry[:3])
    cov = ext["cut_coverage"](seq)
    if cov["gaps"]:
        _stop(run, "CUT_GAPS|%r|NOTHING SAVED; Don't-Save restart" % cov["gaps"])
    expected = apply_model(snap0, plan, guids)
    diff = snapshot_diff(_snapshot(seq, n), expected)
    if diff:
        _stop(run, "PRESAVE_SNAPSHOT_MISMATCH|%r|NOTHING SAVED; Don't-Save restart" % diff)
    if any(str(a.get_actor_label()).startswith("ZZ_") for a in _actors()):
        _stop(run, "ZZ_ACTORS_PRESENT|NOTHING SAVED")
    census = _census()
    stray = [p for p in census["content"] if p not in (seq_path, MASTER_PATH, SHOW_PATH)] + \
            [p for p in census["maps"] if p != EXPECTED_WORLD]
    if stray or seq_path not in census["content"] or EXPECTED_WORLD not in census["maps"]:
        _stop(run, "UNEXPECTED_DIRTY|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))

    # 8. narrow saves
    saves = {}
    for path in (seq_path, MASTER_PATH, SHOW_PATH):
        if path in census["content"]:
            saves[path] = bool(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=True))
    saves[EXPECTED_WORLD] = bool(unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD))
    if not all(saves.values()):
        _stop(run, "SAVE_FAILED|%r" % saves)

    # 9. read-back (asserted; UE return values are not trusted)
    problems = []
    if _census() != {"content": [], "maps": []}:
        problems.append("dirty after save %r" % _census())
    seq = unreal.load_asset(seq_path)
    snap1 = _snapshot(seq, n)
    diff = snapshot_diff(snap1, expected)
    if diff:
        problems.append("snapshot %r" % diff)
    sm = ext["show_master_match"](unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH))
    if not sm["match"]:
        problems.append("show/master %r" % sm)
    marks = _read_markers(seq)
    go = [m for m in marks if parse_go_label(m[0])]
    if [m for m in go if m[0] == plan["go"][0]] != [list(plan["go"])]:
        problems.append("GO marker %r" % go)
    idx = _by_label(_actors())
    for label, want in ((hc["label"], hc["level_rel"]["loc"]), (lt["label"], lt["root"]["loc"])):
        a = _one(idx, label, run)
        rel = list(a.root_component.get_editor_property("relative_location").to_tuple())
        if a.get_attach_parent_actor() != root or max(abs(x - y) for x, y in zip(rel, want)) > 0.1:
            problems.append("actor %s rel %r want %r" % (label, rel, want))
    for b in seq.get_bindings():
        if str(b.get_display_name()) in (plan["hangar_card"]["name"], plan["mouth_card"]["name"]):
            comp = b.get_object_template().get_editor_property("static_mesh_component")
            mesh = comp.get_editor_property("static_mesh")
            mats = list(comp.get_editor_property("override_materials"))
            if mesh is None or mesh.get_path_name().split(".")[0] != CUBE_PATH.split(".")[0] or not mats or mats[0] is None:
                problems.append("card template %s mesh=%s mats=%r" % (b.get_display_name(), mesh, mats))
    gc_assets = _drape_gc_assets(seq)
    if gc_assets != [GC_PATH] * len(drape_gc_rows(plan["mouth_drape"])):
        problems.append("mouth drape GC assets %r" % gc_assets)
    if problems:
        _stop(run, "READBACK_FAILED_AFTER_SAVE|%r|restore from %s" % (problems, backup))
    record.update({"applied": True, "snapshot_after": snap1, "saves": saves, "segment_rows": rows,
                   "pile_completion_keep_state": pile_completion})
    _write_json(record_path, record)
    unreal.log("CURTAIN_SLEIGHT_APPLY_OK|run=%s|interaction=%d|cue_guid=%s|end=%d->%d|sleight=%d|go=%s@%d|backup=%s|"
               "record=%s|tests_required_singly=InfinityStage.Editor.SavedMasterMatchesShow,"
               "InfinityStage.Editor.SceneCutBindingsResolve" % (run, n, inputs["cue_guid"], old_end, end,
                                                                 plan["frames"]["sleight"], plan["go"][0], plan["go"][1],
                                                                 backup, record_path))


# --------------------------------------------------------------------------------------------------------------- REVERT

def run_revert(n, run):
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    record = _load_json(record_path)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or int(record["interaction"]) != n:
        _stop(run, "REVERT_RECORD_CONTEXT")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|" + json.dumps(_census()))
    show = unreal.load_asset(SHOW_PATH)
    master = unreal.load_asset(MASTER_PATH)
    cues = [c for c in show.get_editor_property("cues") if _guid(c.get_editor_property("cue_guid")) == record["cue_guid"]]
    if len(cues) != 1:
        _stop(run, "CUE_GUID_NOT_FOUND|%s" % record["cue_guid"])
    seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
    if seq is None or seq.get_path_name().split(".")[0] != record["sequence"]:
        _stop(run, "SEQUENCE_CHANGED")
    fixrec = _load_json(os.path.join(_here(), FIXUP_RECORD_PATTERN % n), required=False)
    refusals = main_revert_gate(_snapshot(seq, n), record, fixrec)
    if refusals:
        _stop(run, "|".join(refusals))
    ext = _ext_helpers(run)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreCurtainSleight-I%d-%s-revert" % (n, run))
    os.makedirs(backup, exist_ok=False)
    for src in (_content_file(record["sequence"]), _content_file(MASTER_PATH), _content_file(SHOW_PATH),
                _content_file(EXPECTED_WORLD, ".umap")):
        shutil.copy2(src, os.path.join(backup, os.path.basename(src)))
    plan, before = record["plan"], record["snapshot_before"]
    segs0 = ext["compiled_segments"](show)
    keys0 = ext["passage_keys_section_relative"](master)
    seq.modify()
    # cuts: ours out, the original back (same binding guid, same range)
    ours = set(record["created_binding_guids"])
    tracks = list(seq.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(tracks) != 1:
        _stop(run, "CUT_TRACK_COUNT|%d|NOTHING SAVED; Don't-Save restart" % len(tracks))
    removed = 0
    for s in list(tracks[0].get_sections()):
        if _guid(s.get_camera_binding_id().get_editor_property("guid")) in ours:
            tracks[0].remove_section(s)
            removed += 1
    if removed != 2:
        _stop(run, "REVERT_CUT_COUNT|%d|NOTHING SAVED; Don't-Save restart" % removed)
    by_guid = {_guid(b.get_id()): b for b in seq.get_bindings()}
    for guid, a, b, active in before["cuts"]:
        if guid not in by_guid:
            _stop(run, "ORIGINAL_CUT_BINDING_GONE|%s|NOTHING SAVED; Don't-Save restart" % guid)
        s = tracks[0].add_section()
        s.set_camera_binding_id(seq.get_binding_id(by_guid[guid]))
        s.set_range(int(a), int(b))
    # bindings: children before parents
    created = record["binding_guids"]
    for name in sorted(created, key=lambda k: (0 if "/" in k else 1, k)):
        for b in seq.get_bindings():
            if _guid(b.get_id()) == created[name]:
                b.remove()
    left = [g for g in ours if g in {_guid(b.get_id()) for b in seq.get_bindings()}]
    if left:
        _stop(run, "BINDINGS_SURVIVED|%r|NOTHING SAVED; Don't-Save restart" % left)
    # markers
    mine = {(m[0], int(m[1])) for m in record["created_markers"]}
    marks = _read_markers(seq)
    for i in sorted([i for i, m in enumerate(marks) if (m[0], m[1]) in mine], reverse=True):
        seq.delete_marked_frame(i)
    # sections back to the snapshot ranges (mouth drape GC, tails), then the length
    seq.set_playback_end(int(before["playback"][1]))
    end_new, old_end, delta = plan["new_end"], plan["old_end"], plan["delta"]
    for b in seq.get_bindings():
        for t in b.get_tracks():
            cls = t.get_class().get_name()
            if str(b.get_display_name()) == MOUTH_DRAPE and cls == "MovieSceneGeometryCacheTrack":
                want = [r for r in before["bindings"] if r["name"] == MOUTH_DRAPE][0]
                rows = [tr for tr in want["tracks"] if tr["class"] == cls][0]["sections"]
                live = sorted(t.get_sections(), key=lambda x: x.get_start_frame())
                for extra in live[len(rows):]:          # an APPLY-made PILE (the snapshot before had HOLD + FALL)
                    t.remove_section(extra)
                for s, row in zip(live, rows):
                    s.set_range(int(row[0]), int(row[1]))
                    prm = s.get_editor_property("params")
                    prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(row[2])))
                    prm.set_editor_property("end_frame_offset", unreal.FrameNumber(int(row[3])))
                    s.set_editor_property("params", prm)
                continue
            for s in t.get_sections():
                if s.has_end_frame() and s.get_end_frame() in (end_new, end_new + 1):
                    s.set_range(int(s.get_start_frame()) if s.has_start_frame() else 0, int(s.get_end_frame()) - delta)
    for t in seq.get_tracks():
        if t.get_class().get_name() == "MovieSceneCameraCutTrack":
            continue
        for s in t.get_sections():
            if s.has_end_frame() and s.get_end_frame() in (end_new, end_new + 1):
                s.set_range(int(s.get_start_frame()) if s.has_start_frame() else 0, int(s.get_end_frame()) - delta)
    # level actors (tag-guarded)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    idx = _by_label(_actors())
    for label in record["created_labels"]:
        a = _one(idx, label, run)
        if not a.actor_has_tag(TAGS[1] % n):
            _stop(run, "REVERT_ACTOR_TAG|%s|NOTHING SAVED; Don't-Save restart" % label)
        subsystem.destroy_actor(a)
    result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    if not result:
        _stop(run, "REBUILD_FAILED|NOTHING SAVED; Don't-Save restart")
    rows, bad = ext["segment_deltas"](segs0, ext["compiled_segments"](show), record["cue_label"],
                                      round(-delta / plan["fps"], 3))
    if bad:
        _stop(run, "SEGMENT_SHIFTS|%r|NOTHING SAVED; Don't-Save restart" % bad[:3])
    carry = ext["key_carry_failures"](keys0, ext["passage_keys_section_relative"](master))
    if carry:
        _stop(run, "KEY_CARRY|%r|NOTHING SAVED; Don't-Save restart" % carry[:3])
    diff = snapshot_diff(_snapshot(seq, n), before)
    if diff:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart" % diff)
    census = _census()
    stray = [p for p in census["content"] if p not in (record["sequence"], MASTER_PATH, SHOW_PATH)] + \
            [p for p in census["maps"] if p != EXPECTED_WORLD]
    if stray:
        _stop(run, "UNEXPECTED_DIRTY|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))
    saves = {}
    for path in (record["sequence"], MASTER_PATH, SHOW_PATH):
        if path in census["content"]:
            saves[path] = bool(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=True))
    saves[EXPECTED_WORLD] = bool(unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD))
    if not all(saves.values()):
        _stop(run, "SAVE_FAILED|%r" % saves)
    seq = unreal.load_asset(record["sequence"])
    diff = snapshot_diff(_snapshot(seq, n), before)
    if diff or _census() != {"content": [], "maps": []}:
        _stop(run, "REVERT_READBACK|%r|census=%r|restore from %s" % (diff, _census(), record["backup"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("CURTAIN_SLEIGHT_REVERT_OK|run=%s|interaction=%d|cue_guid=%s|end=%d|backup=%s|record=%s"
               % (run, n, record["cue_guid"], before["playback"][1], backup, archived))


# ----------------------------------------------------------------------------------------------- FIXUP_PILE (I1 only)

def _fixup_live(n, run):
    """Read-only: records, sequence, live snapshot, drape GC track + sections, live cache length. Refuses on any gate."""
    if n not in FIXUP_INTERACTIONS:
        _stop(run, "FIXUP_PILE_I1_ONLY|%d" % n)
    record = _load_json(os.path.join(_here(), RECORD_PATTERN % n))
    if record.get("world") != EXPECTED_WORLD or int(record.get("interaction", 0)) != n:
        _stop(run, "FIXUP_RECORD_CONTEXT")
    fix_path = os.path.join(_here(), FIXUP_RECORD_PATTERN % n)
    fixrec = _load_json(fix_path, required=False)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|" + json.dumps(_census()))
    if any(str(a.get_actor_label()).startswith("ZZ_") for a in _actors()):
        _stop(run, "ZZ_ACTORS_PRESENT")
    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues") if _guid(c.get_editor_property("cue_guid")) == record["cue_guid"]]
    if len(cues) != 1:
        _stop(run, "CUE_GUID_NOT_FOUND|%s" % record["cue_guid"])
    seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
    if seq is None or seq.get_path_name().split(".")[0] != record["sequence"]:
        _stop(run, "SEQUENCE_CHANGED")
    rate, tick = seq.get_display_rate(), seq.get_tick_resolution()
    fps, tick_rate = rate.numerator / float(rate.denominator), tick.numerator / float(tick.denominator)
    snap = _snapshot(seq, n)
    return record, fix_path, fixrec, show, seq, fps, tick_rate, snap


def _fixup_drape_track(seq, guid, run):
    bs = [b for b in seq.get_bindings() if _guid(b.get_id()) == guid and str(b.get_display_name()) == MOUTH_DRAPE]
    if len(bs) != 1:
        _stop(run, "FIXUP_DRAPE_BINDING|%s|%d" % (guid, len(bs)))
    gts = [t for t in bs[0].get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"]
    if len(gts) != 1:
        _stop(run, "FIXUP_DRAPE_GC_TRACKS|%d" % len(gts))
    return gts[0], sorted(gts[0].get_sections(), key=lambda s: s.get_start_frame())


def _cache_ticks(cache, tick_rate):
    """Same formula as _bake_facts / fit_transition_drapes.py / opening_sequence_apply.py:228."""
    return int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame"))
                     / CACHE_FPS * tick_rate))


def _fixup_plan_live(record, seq, tick_rate, fps, run):
    guid = _drape_binding_guid(record["snapshot_after"])
    track, secs = _fixup_drape_track(seq, guid, run)
    cache = secs[-1].get_editor_property("params").get_editor_property("geometry_cache_asset") if secs else None
    if cache is None or cache.get_path_name().split(".")[0] != GC_PATH:
        _stop(run, "FIXUP_CACHE|%s" % (cache.get_path_name() if cache else None))
    dur = _cache_ticks(cache, tick_rate)
    try:
        fix = plan_fixup_pile(record, dur, tick_rate, fps)
    except PlanError as exc:
        _stop(run, "FIXUP_PLAN_REFUSED|%s" % exc)
    if [_gc_row(s) for s in secs] != fix["before_rows"]:
        _stop(run, "FIXUP_LIVE_SECTIONS|%r != %r" % ([_gc_row(s) for s in secs], fix["before_rows"]))
    return fix, track, secs, cache


def _backup_seq(tag, n, run, seq_path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "%s-I%d-%s" % (tag, n, run))
    os.makedirs(backup, exist_ok=False)
    src = _content_file(seq_path)
    dst = os.path.join(backup, os.path.basename(src))
    shutil.copy2(src, dst)
    if os.path.getsize(dst) != os.path.getsize(src):
        _stop(run, "BACKUP_SIZE_MISMATCH|" + src)
    return backup, [dst]


def _save_seq_only(seq_path, run):
    census = _census()
    if census != {"content": [seq_path], "maps": []}:
        _stop(run, "UNEXPECTED_DIRTY|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))
    ok = bool(unreal.EditorAssetLibrary.save_asset(seq_path, only_if_is_dirty=True))
    if not ok:
        _stop(run, "SAVE_FAILED|%s" % seq_path)
    return {seq_path: ok}


def run_fixup_pile(n, run, dry):
    record, fix_path, fixrec, show, seq, fps, tick_rate, snap0 = _fixup_live(n, run)
    refusals = fixup_gate(snap0, record, fixrec)
    if refusals:
        _stop(run, "FIXUP_REFUSED|" + " || ".join(refusals))
    ext = _ext_helpers(run)
    master = unreal.load_asset(MASTER_PATH)
    sm0 = ext["show_master_match"](show, master)
    if not sm0["match"]:
        _stop(run, "SHOW_MASTER_MISMATCH_BEFORE|%r" % sm0)
    fix, track, secs, cache = _fixup_plan_live(record, seq, tick_rate, fps, run)
    expected = fixup_model(snap0, fix)
    failures = check_fixup(fix, snap0, expected)
    if failures:
        _stop(run, "FIXUP_CHECK|" + " || ".join(failures))
    if dry:
        out = os.path.join(_here(), FIXUP_DRY_PATTERN % n)
        _write_json(out, {"run": run, "interaction": n, "fix": fix, "expected_drape_gc": fix["after_rows"],
                          "live_drape_gc": fix["before_rows"], "unapplied_fixup_record_present": bool(fixrec)})
        if _census() != {"content": [], "maps": []}:
            _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
        unreal.log("CURTAIN_SLEIGHT_FIXUP_PILE_DRY_OK|run=%s|interaction=%d|mutated=0|cache_ticks=%d|playable=%d|"
                   "wraps_at=%.1f|fall_end=%d|pile=[%d,%d)|digest=%s|report=%s"
                   % (run, n, fix["cache_duration_ticks"], fix["playable_frames"], fix["wrap_frame_before"],
                      fix["fall_end"], fix["pile"][0], fix["pile"][1], fix["digest"], out))
        return
    if fixrec:                                    # unapplied leftover: the drift gate proved nothing was half-written
        os.rename(fix_path, fix_path + ".unapplied-" + run)
    seq_path = record["sequence"]
    backup, files = _backup_seq("PreCurtainSleightFixupPile", n, run, seq_path)
    fixrec = {"schema_version": 1, "run": run, "interaction": n, "sequence": seq_path, "world": EXPECTED_WORLD,
              "cue_guid": record["cue_guid"], "main_record": RECORD_PATTERN % n, "main_run": record["run"],
              "backup": backup, "backup_files": files, "applied": False, "fix": fix,
              "snapshot_before": snap0, "snapshot_expected": expected}
    _write_json(fix_path, fixrec)
    seq.modify()
    fall_sec = secs[1]
    fall_sec.set_range(int(fix["after_rows"][1][0]), int(fix["after_rows"][1][1]))
    _, completion = _add_pile_section(track, fix["pile"], cache, run)
    diff = snapshot_diff(_snapshot(seq, n), expected)
    if diff:
        _stop(run, "PRESAVE_SNAPSHOT_MISMATCH|%r|NOTHING SAVED; Don't-Save restart" % diff)
    if _drape_gc_assets(seq) != [GC_PATH] * 3:
        _stop(run, "PRESAVE_GC_ASSETS|%r|NOTHING SAVED; Don't-Save restart" % _drape_gc_assets(seq))
    saves = _save_seq_only(seq_path, run)
    problems = []
    if _census() != {"content": [], "maps": []}:
        problems.append("dirty after save %r" % _census())
    seq = unreal.load_asset(seq_path)
    snap1 = _snapshot(seq, n)
    if snapshot_diff(snap1, expected):
        problems.append("snapshot %r" % snapshot_diff(snap1, expected))
    if _drape_gc_assets(seq) != [GC_PATH] * 3:
        problems.append("gc assets %r" % _drape_gc_assets(seq))
    sm1 = ext["show_master_match"](unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH))
    if not sm1["match"]:
        problems.append("show/master %r" % sm1)
    if problems:
        _stop(run, "FIXUP_READBACK_FAILED_AFTER_SAVE|%r|restore from %s" % (problems, backup))
    fixrec.update({"applied": True, "snapshot_after": snap1, "saves": saves, "pile_completion_keep_state": completion})
    _write_json(fix_path, fixrec)
    unreal.log("CURTAIN_SLEIGHT_FIXUP_PILE_OK|run=%s|interaction=%d|fall_end=%d|pile=[%d,%d)|pile_offsets=%d/%d|"
               "playable=%d|keep_state=%d|backup=%s|record=%s"
               % (run, n, fix["fall_end"], fix["pile"][0], fix["pile"][1], fix["pile"][2], fix["pile"][3],
                  fix["playable_frames"], int(completion), backup, fix_path))


def run_fixup_pile_revert(n, run):
    record, fix_path, fixrec, show, seq, fps, tick_rate, snap0 = _fixup_live(n, run)
    refusals = fixup_revert_gate(snap0, fixrec)
    if refusals:
        _stop(run, "FIXUP_REVERT_REFUSED|" + " || ".join(refusals))
    fix = fixrec["fix"]
    track, secs = _fixup_drape_track(seq, fix["drape_binding_guid"], run)
    if [_gc_row(s) for s in secs] != fix["after_rows"]:
        _stop(run, "FIXUP_REVERT_LIVE_SECTIONS|%r != %r" % ([_gc_row(s) for s in secs], fix["after_rows"]))
    want = fixup_revert_model(snap0, fix)
    if snapshot_diff(want, fixrec["snapshot_before"]):
        _stop(run, "FIXUP_REVERT_MODEL|%r" % snapshot_diff(want, fixrec["snapshot_before"]))
    seq_path = fixrec["sequence"]
    backup, _ = _backup_seq("PreCurtainSleightFixupPile", n, run + "-revert", seq_path)
    seq.modify()
    track.remove_section(secs[2])                 # the PILE (sorted by start: HOLD, FALL, PILE)
    secs[1].set_range(int(fix["before_rows"][1][0]), int(fix["before_rows"][1][1]))
    diff = snapshot_diff(_snapshot(seq, n), fixrec["snapshot_before"])
    if diff:
        _stop(run, "FIXUP_REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart" % diff)
    saves = _save_seq_only(seq_path, run)
    seq = unreal.load_asset(seq_path)
    diff = snapshot_diff(_snapshot(seq, n), fixrec["snapshot_before"])
    if diff or _census() != {"content": [], "maps": []}:
        _stop(run, "FIXUP_REVERT_READBACK|%r|census=%r|restore from %s" % (diff, _census(), fixrec["backup"]))
    archived = fix_path + ".reverted-" + run
    os.rename(fix_path, archived)
    unreal.log("CURTAIN_SLEIGHT_FIXUP_PILE_REVERT_OK|run=%s|interaction=%d|fall=[%d,%d)|saves=%r|backup=%s|record=%s|"
               "next=main REVERT allowed (state == main snapshot_after)"
               % (run, n, fix["before_rows"][1][0], fix["before_rows"][1][1], saves, backup, archived))


def main():
    run = str(globals().get("CURTAIN_SLEIGHT_RUN_ID") or datetime.datetime.now().strftime("CST-%Y%m%d-%H%M%S"))
    n = int(globals().get("CURTAIN_SLEIGHT_INTERACTION", 0))
    apply = bool(globals().get("CURTAIN_SLEIGHT_APPLY"))
    revert = bool(globals().get("CURTAIN_SLEIGHT_REVERT"))
    fixup = bool(globals().get("CURTAIN_SLEIGHT_FIXUP_PILE"))
    fixup_dry = bool(globals().get("CURTAIN_SLEIGHT_FIXUP_PILE_DRY"))
    fixup_revert = bool(globals().get("CURTAIN_SLEIGHT_FIXUP_PILE_REVERT"))
    if n not in SEQS:
        _stop(run, "INTERACTION_NOT_SET")
    if sum((apply, revert, fixup, fixup_dry, fixup_revert)) > 1:
        _stop(run, "MORE_THAN_ONE_MODE_SET")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")                    # never end PIE; refuse
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")                    # an open Sequencer evaluates and dirties the map
    if revert:
        run_revert(n, run)
        return
    if fixup or fixup_dry:
        run_fixup_pile(n, run, dry=fixup_dry)
        return
    if fixup_revert:
        run_fixup_pile_revert(n, run)
        return
    overrides = _load_json(os.path.join(_here(), OVERRIDES_NAME), required=False)
    params = dict(overrides.get("params", {}))
    params.update(overrides.get("interaction_params", {}).get(str(n), {}))
    try:
        if apply:
            run_apply(n, run, params, overrides)
        else:
            run_dry(n, run, params)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
