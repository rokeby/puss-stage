"""BLOCKING (4 Oct, offline-written, NEVER RUN IN UNREAL): curtain + shadow-puppet
minute + door exit at the end of one Scene.

Gary, 4 Oct (Docs/Conductor/MORNING_SUMMARY_2026-10-04.md:81): "It's a door but
the curtain hangs over it and we have a 1min cat boy shadowpuppet scene on it
first, just block for now."  Plan and timing decision:
Docs/Conductor/SCENE_EXIT_BLOCK_PLAN_2026-10-04.md.

Placeholder level only, no creative finish.  Per Scene N, appended AFTER the
Scene's current content (the Scene must first be lengthened with Soft goods'
extend_scene_playback.py to the new_end this tool's DRY prints):

  [W0 = old end] hard cut to "S<N> Exit Block Camera" at option B's seat
  (9 m in front of the door), held while the puppet minute plays on the
  placeholder screen card hung on the placeholder curtain ->
  [+60 s] the curtain (and card) fly out, smoothstep, 3 s ->
  option B of scene_exit_move.py, unchanged: 1.5 s on the closed door, the
  leaf swings in, the camera walks through into the Exit Black ->
  [W1 = new_end - exit hold] the builder's retained Exit hold (black) ->
  [new_end] the Interaction.

Option B's planner is REUSED, not copied: its pure section (everything above
`def _here`) is parsed and executed into a fresh namespace with FPS set to the
Scene's display rate (S3 is 24 fps).  Never `import scene_exit_move`: its last
line runs main() inside Unreal, and the editor's module cache would serve a
stale copy (memory ue58-python-stale-module-cache).

Modes (globals set by a runner, like scene_exit_move.py):
  SCENE_EXIT_BLOCK_SCENE   int 1..6 (required)
  SCENE_EXIT_BLOCK_APPLY   True -> write (Scene sequence + level), else DRY
  SCENE_EXIT_BLOCK_REVERT  True -> remove exactly what the record lists
Importing with no `unreal` (system Python) never touches Unreal; the pure
planner and gates are what test_scene_exit_block.py exercises.

What APPLY writes (the Scene's own Level Sequence + the show level; the
Master and the Show must stay clean):
  * level, attached to "S<N> Hangar Root", composed root-relative against the
    LIVE root, which must equal the landed root recorded by the doors tool:
      - StaticMeshActor "S<N> Exit Block Curtain" (Cube, existing curtain MI),
      - StaticMeshActor "S<N> Exit Block Puppet Screen" (Cube card,
        placeholder material; tag ShadowPuppetScreen.S<N> = the media slot),
      - CineCameraActor "S<N> Exit Block Camera" saved at the FINAL pose.
    Tags SceneExitBlock / SceneExitBlock.S<N>; labels never look like a
    handoff camera (InfinityStageSceneHandoffBuilder.cpp:96-109).
  * Scene sequence: possessables for the camera (+ component), leaf, curtain,
    card; transform keys (root-relative, LINEAR), a focus track, ONE root
    camera cut [W0, W1), and marked frames "EXB ..." for the beats.
  * then match_named_scene_handoffs(show, [cue_guid], 1): the builder makes
    Entry [start, W0) and the retained Exit [W1, new_end) (builder
    .cpp:396-445).
Gates (DRY reports; APPLY refuses on any): NOT_DECIDED, SCENE_NOT_DECIDED,
NOT_EXTENDED / PLAYBACK_END_DRIFT, USE_SEQUENCE_LENGTH_OFF, ROOT_NOT_LANDED,
TAIL_GAP, every scene_exit_move gate (S3_BACKDROP_BEHIND_LEAF,
ROOT_CUT_OVERLAP, NESTED_CUTS_IN_WINDOW, RISE_OVERLAPS_WINDOW, PLAN_CHECK),
BLOCK_CHECK (curtain/card/box/frame), CURTAIN_SPACE_OCCUPIED,
SCENE_EXIT_MOVE_PRESENT, ACTOR_EXISTS, ALREADY_BOUND_IN_SCENE.
Success markers: SCENE_EXIT_BLOCK_DRY_OK / _APPLY_OK / _REVERT_OK, each only
after its asserts; any refusal logs SCENE_EXIT_BLOCK_STOPPED|run=..|reason=..
Never Save All, never end PIE, never reload the level.
"""
import ast
import datetime
import hashlib
import inspect
import json
import math
import os
import shutil
import types

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXIT_MOVE_NAME = "scene_exit_move.py"
DOORS_RECORD_NAME = "hangar_exit_doors_record.json"
OVERRIDES_NAME = "scene_exit_block_overrides.json"
PLAN_PATTERN = "scene_exit_block_plan_S%d.json"
RECORD_PATTERN = "scene_exit_block_record_S%d.json"
EXIT_MOVE_RECORD_PATTERN = "scene_exit_move_record_S%d.json"
HANGAR_PLAN_PATTERN = os.path.join("CodexStructure", "hangar_s%d_plan.json")
TRACK_NAME = "SceneExitBlock (Conductor)"
TAGS = ("SceneExitBlock", "SceneExitBlock.S%d")
SCREEN_TAG = "ShadowPuppetScreen.S%d"
LABELS = {"camera": "S%d Exit Block Camera",
          "curtain": "S%d Exit Block Curtain",
          "card": "S%d Exit Block Puppet Screen"}
EXIT_MOVE_CAMERA_LABEL = "S%d Exit Door Camera"
LEAF_LABEL_PATTERN = "S%d Hangar Exit Door Leaf"
ROOT_LABEL_PATTERN = "S%d Hangar Root"
CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
CUBE_SIZE_CM = 100.0
# Existing curtain look (the Opening drop's MI, Content/Scenes/Curtain/Baked).
# Its static-mesh usage flag is NOT verified offline; APPLY reads it live.
CURTAIN_MATERIAL = "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"
# No MediaTexture / flipbook material exists in Content/InfinityStage, Scenes
# or Materials (byte search, 4 Oct), and the puppet spec rules video out
# (Docs/ShadowPuppetCaptureSpec.md section 7).  Plain lit engine material.
CARD_MATERIAL = "/Engine/BasicShapes/BasicShapeMaterial"
MARKER_PREFIX = "EXB "
ROOT_TOLERANCE_CM = 0.5
ROOT_TOLERANCE_DEG = 0.05
SHOW_TICKS_PER_S = 24000.0

# The exit-move functions this tool calls, with their exact parameter lists.
REQUIRED_EXIT_MOVE = {
    "door_geometry": ("doors_plan_scene",),
    "plan_exit_move": ("geom", "eye_z_root", "scene_end_frame", "exit_hold_frames", "params"),
    "check_plan": ("plan", "geom", "params"),
    "gate_scene": ("geom", "params"),
    "gate_root_cuts": ("cuts", "window_start", "scene_end"),
    "gate_nested": ("nested_rows", "window_start", "scene_end"),
    "gate_rise": ("sub_rows", "window_start"),
    "looks_like_handoff_camera": ("label", "tags"),
    "smoothstep": ("u",),
}

BLOCK_DEFAULTS = {
    "puppet_hold_s": 60.0,          # Gary: "1min"
    "curtain_out_s": 3.0,           # fly-out, smoothstep
    "curtain_offset_cm": 60.0,      # curtain centre plane in front of the door face
    "curtain_width_cm": 700.0,
    "curtain_height_cm": 600.0,
    "curtain_thickness_cm": 2.0,
    "curtain_floor_gap_cm": 2.0,    # hem above the door floor
    "curtain_cover_margin_cm": 50.0,  # beyond each side/top of the opening
    "raise_margin_cm": 50.0,        # raised hem above door top AND frame top
    "card_width_cm": 480.0,         # 16:9 placeholder screen
    "card_height_cm": 270.0,
    "card_thickness_cm": 1.0,
    "card_gap_cm": 1.0,             # in front of the curtain's front face
    "card_frame_margin_cm": 10.0,
    "box_margin_cm": 10.0,
    "start_at_last_interior_end": False,
    "curtain_material": CURTAIN_MATERIAL,
    "card_material": CARD_MATERIAL,
}


class PlanError(ValueError):
    pass


# ----------------------------------------------------------------------------
# Loader for scene_exit_move.py's pure section
# ----------------------------------------------------------------------------

def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def load_exit_move(path, fps):
    """Execute scene_exit_move.py's statements above `def _here` into a fresh
    namespace, with FPS = the Scene's display rate.  Refuses on API drift."""
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    cut = [index for index, node in enumerate(tree.body)
           if isinstance(node, ast.FunctionDef) and node.name == "_here"]
    if len(cut) != 1:
        raise PlanError("EXIT_MOVE_SHAPE: expected one `def _here`, found %d" % len(cut))
    body = tree.body[:cut[0]]
    for node in body:
        if isinstance(node, ast.Expr) and not isinstance(getattr(node, "value", None), ast.Constant):
            raise PlanError("EXIT_MOVE_SIDE_EFFECT at line %d" % node.lineno)
        if isinstance(node, ast.If):
            raise PlanError("EXIT_MOVE_SIDE_EFFECT (if) at line %d" % node.lineno)
    tree.body = body
    module = types.ModuleType("_scene_exit_move_pure_for_block")
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - our own reviewed project file.
    drift = []
    for name, params in sorted(REQUIRED_EXIT_MOVE.items()):
        function = getattr(module, name, None)
        if not callable(function):
            drift.append(name + ":absent")
        elif tuple(inspect.signature(function).parameters) != params:
            drift.append("%s:params=%s" % (name, ",".join(inspect.signature(function).parameters)))
    for name in ("FPS", "DEFAULTS", "FILMBACK_MM"):
        if not hasattr(module, name):
            drift.append(name + ":absent")
    if drift:
        raise PlanError("EXIT_MOVE_API_DRIFT|" + ";".join(drift))
    module.FPS = float(fps)  # every planner function reads FPS at call time
    module.SOURCE_SHA256 = _sha256(raw)
    return module


def split_params(params, sem):
    """Block params vs exit-move params; unknown keys refuse (no silent typos)."""
    params = dict(params or {})
    block = dict(BLOCK_DEFAULTS)
    move = {}
    unknown = []
    for key, value in params.items():
        if key in BLOCK_DEFAULTS:
            block[key] = value
        elif key in sem.DEFAULTS:
            move[key] = value
        else:
            unknown.append(key)
    if unknown:
        raise PlanError("UNKNOWN_PARAMS: %r" % sorted(unknown))
    return block, move


# ----------------------------------------------------------------------------
# Pure geometry and timing (offline-tested)
# ----------------------------------------------------------------------------

def frames(seconds, fps):
    return int(round(float(seconds) * float(fps)))


def hold_frames_from_ticks(ticks, fps):
    return int(round(float(ticks) / SHOW_TICKS_PER_S * float(fps)))


def curtain_geometry(geom, eye_z_root, block):
    """Hung curtain and card boxes in the hangar-root frame (centre, size)."""
    door_face = geom["door_face_x"]
    floor = geom["floor_z"]
    t = float(block["curtain_thickness_cm"])
    cx = door_face - float(block["curtain_offset_cm"])
    w, h = float(block["curtain_width_cm"]), float(block["curtain_height_cm"])
    bottom = floor + float(block["curtain_floor_gap_cm"])
    curtain = {"center": [cx, geom["opening_center_y"], bottom + h / 2.0], "size": [t, w, h]}
    ct = float(block["card_thickness_cm"])
    card_x = cx - t / 2.0 - float(block["card_gap_cm"]) - ct / 2.0
    card = {"center": [card_x, geom["opening_center_y"], float(eye_z_root)],
            "size": [ct, float(block["card_width_cm"]), float(block["card_height_cm"])]}
    return {"curtain": curtain, "card": card, "curtain_front_x": cx - t / 2.0,
            "hem_hung_z": bottom}


def box_minmax(center, size, dz=0.0):
    lo = [center[i] - size[i] / 2.0 for i in range(3)]
    hi = [center[i] + size[i] / 2.0 for i in range(3)]
    lo[2] += dz
    hi[2] += dz
    return lo, hi


def frame_half_extent(distance_cm, focal_mm, filmback_mm):
    return (distance_cm * filmback_mm[0] / 2.0 / focal_mm,
            distance_cm * filmback_mm[1] / 2.0 / focal_mm)


def raise_distance(cg, geom, camera_keys, from_frame, focal_mm, filmback_mm, block):
    """Fly-out height: the hem must clear the door top (leaf swing) and every
    post-raise camera frame's top edge at the curtain plane, plus a margin."""
    need = geom["opening_z"][1]
    plane = cg["curtain_front_x"]
    for key in camera_keys:
        if key[0] < from_frame or key[1] >= plane:
            continue
        _, half_h = frame_half_extent(plane - key[1], focal_mm, filmback_mm)
        need = max(need, key[3] + half_h)
    return need + float(block["raise_margin_cm"]) - cg["hem_hung_z"]


def plan_block(sem, geom, eye_z_root, content_end, hold_frames, root_cuts, params=None):
    """Return the whole block: window, camera / leaf / curtain / card keys,
    markers and a report.  Frames are the Scene's display frames at sem.FPS."""
    block, move = split_params(params, sem)
    fps = float(sem.FPS)
    p_move = dict(sem.DEFAULTS)
    p_move.update(move)
    w0 = int(content_end)
    if block.get("start_at_last_interior_end"):
        interior_ends = [cut["end"] for cut in root_cuts
                         if cut.get("active", True) and not cut.get("handoff")]
        if interior_ends and max(interior_ends) < w0:
            w0 = int(max(interior_ends))
    hold_f = frames(block["puppet_hold_s"], fps)
    out_f = frames(block["curtain_out_s"], fps)
    if hold_f <= 0 or out_f <= 0:
        raise PlanError("puppet hold and curtain-out must be at least one frame")
    # Option B's own length: plan once at a dummy end, then place it.
    probe = sem.plan_exit_move(geom, eye_z_root, 10 ** 6, hold_frames, move)
    move_f = probe["report"]["window"][1] - probe["report"]["window"][0]
    move_start = w0 + hold_f + out_f
    w1 = move_start + move_f
    new_end = w1 + int(hold_frames)
    exit_plan = sem.plan_exit_move(geom, eye_z_root, new_end, hold_frames, move)
    if exit_plan["report"]["window"] != [move_start, w1]:
        raise PlanError("exit move did not land at [%d, %d]: %r" % (move_start, w1, exit_plan["report"]["window"]))
    seat = exit_plan["camera_keys"][0]
    camera_keys = [tuple([w0] + list(seat[1:]))] + list(exit_plan["camera_keys"])
    cg = curtain_geometry(geom, eye_z_root, block)
    raise_cm = raise_distance(cg, geom, exit_plan["camera_keys"], move_start,
                              float(p_move["focal_mm"]), sem.FILMBACK_MM, block)

    def lift_keys(piece):
        c = cg[piece]["center"]
        keys = [(w0, c[0], c[1], c[2], 0.0, 0.0, 0.0), (w0 + hold_f, c[0], c[1], c[2], 0.0, 0.0, 0.0)]
        for frame in range(w0 + hold_f + 1, move_start + 1):
            u = (frame - (w0 + hold_f)) / float(out_f)
            keys.append((frame, c[0], c[1], c[2] + raise_cm * sem.smoothstep(u), 0.0, 0.0, 0.0))
        keys.append((new_end, c[0], c[1], c[2] + raise_cm, 0.0, 0.0, 0.0))
        return keys

    markers = [(MARKER_PREFIX + "puppet start", w0),
               (MARKER_PREFIX + "curtain out", w0 + hold_f),
               (MARKER_PREFIX + "curtain gone", move_start),
               (MARKER_PREFIX + "door opens", exit_plan["report"]["door_start_frame"]),
               (MARKER_PREFIX + "through (exit hold)", w1)]
    report = {
        "fps": fps,
        "content_end": int(content_end),
        "w0": w0, "w1": w1, "new_end": new_end,
        "grow_frames": new_end - int(content_end),
        "grow_s": (new_end - int(content_end)) / fps,
        "puppet": [w0, w0 + hold_f], "curtain_out": [w0 + hold_f, move_start],
        "move": [move_start, w1], "exit_hold": [w1, new_end],
        "door_start_frame": exit_plan["report"]["door_start_frame"],
        "raise_cm": raise_cm,
        "curtain": cg["curtain"], "card": cg["card"],
        "exit_move_report": exit_plan["report"],
        "block_params": block, "move_params": p_move,
    }
    return {"camera_keys": camera_keys, "leaf_keys": exit_plan["leaf_keys"],
            "curtain_keys": lift_keys("curtain"), "card_keys": lift_keys("card"),
            "markers": markers, "exit_plan": exit_plan, "report": report, "cg": cg}


def inside_box(lo, hi, hangar, door_face_x, floor_z, margin):
    """The hangar interior in the root frame: x in [0, door face], |y| <=
    half_w, z in [floor, height].  Returns the failing axes."""
    bad = []
    if lo[0] < 0.0 + margin or hi[0] > door_face_x + 1.0e-6:
        bad.append("x")
    if lo[1] < -float(hangar["half_w"]) + margin or hi[1] > float(hangar["half_w"]) - margin:
        bad.append("y")
    if lo[2] < floor_z - 1.0e-6 or hi[2] > float(hangar["height"]) - margin:
        bad.append("z")
    return bad


def check_block(sem, plan, geom, hangar, params=None):
    """Every way the block can be wrong that is checkable offline.  [] = pass."""
    block, move = split_params(params, sem)
    p_move = dict(sem.DEFAULTS)
    p_move.update(move)
    rep, cg = plan["report"], plan["cg"]
    failures = ["exit move: " + text for text in sem.check_plan(plan["exit_plan"], geom, move)]
    fps = rep["fps"]
    if rep["new_end"] - rep["w0"] != (frames(block["puppet_hold_s"], fps) + frames(block["curtain_out_s"], fps)
                                      + (rep["move"][1] - rep["move"][0]) + (rep["exit_hold"][1] - rep["exit_hold"][0])):
        failures.append("segments do not add up to the window")
    if abs((rep["puppet"][1] - rep["puppet"][0]) / fps - float(block["puppet_hold_s"])) > 0.5 / fps:
        failures.append("puppet hold is not %.1f s" % float(block["puppet_hold_s"]))
    cam = plan["camera_keys"]
    seat = cam[1]
    if cam[0][0] != rep["w0"] or cam[0][1:] != seat[1:]:
        failures.append("the hold does not sit at option B's seat")
    if any(key[1:4] != seat[1:4] for key in cam if key[0] <= rep["move"][0]):
        failures.append("camera moves during the puppet hold")
    curtain = cg["curtain"]
    o_lo = geom["opening_center_y"] - geom["opening_half_w"]
    o_hi = geom["opening_center_y"] + geom["opening_half_w"]
    c_lo, c_hi = box_minmax(curtain["center"], curtain["size"])
    m = float(block["curtain_cover_margin_cm"])
    if c_lo[1] > o_lo - m or c_hi[1] < o_hi + m or c_hi[2] < geom["opening_z"][1] + m:
        failures.append("hung curtain does not cover the doorway with %.0f cm margin" % m)
    if c_lo[2] - geom["floor_z"] > 5.0:
        failures.append("hung curtain hem is %.1f cm off the floor" % (c_lo[2] - geom["floor_z"]))
    if c_hi[0] >= geom["door_face_x"]:
        failures.append("curtain is not in front of the door face")
    if seat[1] >= cg["curtain_front_x"] - 100.0:
        failures.append("seat is not at least 1 m in front of the curtain")
    # Card inside the seat's frame, on the curtain's front.
    k_lo, k_hi = box_minmax(cg["card"]["center"], cg["card"]["size"])
    half_w, half_h = frame_half_extent(k_lo[0] - seat[1], float(p_move["focal_mm"]), sem.FILMBACK_MM)
    fm = float(block["card_frame_margin_cm"])
    if (k_lo[1] < seat[2] - half_w + fm or k_hi[1] > seat[2] + half_w - fm
            or k_lo[2] < seat[3] - half_h + fm or k_hi[2] > seat[3] + half_h - fm):
        failures.append("puppet screen card is not inside the hold frame")
    if k_hi[0] > c_lo[0] + 1.0e-6:
        failures.append("card is behind the curtain's front face")
    if not (c_lo[1] <= k_lo[1] and k_hi[1] <= c_hi[1] and c_lo[2] <= k_lo[2] and k_hi[2] <= c_hi[2]):
        failures.append("card overhangs the curtain")
    # Fly-out.
    raise_cm = rep["raise_cm"]
    keys = plan["curtain_keys"]
    by_frame = {key[0]: key for key in keys}
    gone = by_frame.get(rep["move"][0])
    if gone is None or abs(gone[3] - (curtain["center"][2] + raise_cm)) > 1.0e-6:
        failures.append("curtain is not fully raised when the exit move starts")
    if rep["door_start_frame"] <= rep["move"][0]:
        failures.append("door starts before the curtain is gone")
    hem_raised = c_lo[2] + raise_cm
    if hem_raised < geom["opening_z"][1] + float(block["raise_margin_cm"]) - 1.0e-6:
        failures.append("raised hem does not clear the door top (leaf swing)")
    plane = cg["curtain_front_x"]
    for key in plan["exit_plan"]["camera_keys"]:
        if key[1] >= plane:
            if key[3] + 30.0 > hem_raised:
                failures.append("camera passes within 30 cm of the raised hem at frame %d" % key[0])
                break
            continue
        _, hh = frame_half_extent(plane - key[1], float(p_move["focal_mm"]), sem.FILMBACK_MM)
        if key[3] + hh > hem_raised - 1.0e-6:
            failures.append("raised curtain is in frame at frame %d" % key[0])
            break
    for (a, b) in zip(keys, keys[1:]):
        if b[0] <= a[0] or b[3] < a[3] - 1.0e-9:
            failures.append("curtain keys go backwards at frame %d" % b[0])
            break
    if keys[0][3] != curtain["center"][2] or keys[1][3] != curtain["center"][2] or keys[1][0] != rep["puppet"][1]:
        failures.append("curtain moves during the puppet hold")
    for piece, dz in (("curtain", 0.0), ("curtain", raise_cm), ("card", 0.0), ("card", raise_cm)):
        lo, hi = box_minmax(cg[piece]["center"], cg[piece]["size"], dz)
        bad = inside_box(lo, hi, hangar, geom["door_face_x"], geom["floor_z"], float(block["box_margin_cm"]))
        if bad:
            failures.append("%s (dz=%.0f) leaves the hangar box on %s" % (piece, dz, ",".join(bad)))
    names = [label for label, _ in plan["markers"]]
    if len(set(names)) != len(names) or any(not n.startswith(MARKER_PREFIX) for n in names):
        failures.append("markers are not unique / not prefixed")
    if [f for _, f in plan["markers"]] != sorted(f for _, f in plan["markers"]):
        failures.append("markers out of order")
    return failures


def gate_tail_gap(root_cuts, w0, block):
    """After the rematch the Entry ends at the FIRST interior start and the
    retained Exit starts at the LAST interior end (builder .cpp:396-445), so
    an interior root cut ending before W0 leaves [end, W0) uncovered."""
    ends = [cut["end"] for cut in root_cuts if cut.get("active", True) and not cut.get("handoff")]
    if ends and max(ends) < w0:
        return ["TAIL_GAP: the last interior root cut ends at %d, before the block starts at %d; [%d, %d) "
                "would have no cut after the rematch (Look & camera extends that cut, or set "
                "start_at_last_interior_end)" % (max(ends), w0, max(ends), w0)]
    return []


def playback_state(live_end, plan_file):
    """('pre', content_end) before the extension; ('extended', content_end)
    after it; ('drift', None) otherwise."""
    if not plan_file:
        return "pre", int(live_end)
    if int(live_end) == int(plan_file["new_end"]):
        return "extended", int(plan_file["content_end"])
    if int(live_end) == int(plan_file["content_end"]):
        return "pre", int(live_end)
    return "drift", None


def decided(overrides, n):
    return bool(str(overrides.get("decided_by") or "").strip()) and int(n) in [int(x) for x in overrides.get("scenes", [])]


def build_block_dry_report(sem, doors_row, hangar, eye_z_root, content_end, hold_frames,
                           root_cuts, nested_rows, params=None):
    geom = sem.door_geometry(doors_row)
    block, move = split_params(params, sem)
    plan = plan_block(sem, geom, eye_z_root, content_end, hold_frames, root_cuts, params)
    rep = plan["report"]
    refusals, warnings = sem.gate_scene(geom, move)
    failures = check_block(sem, plan, geom, hangar, params)
    overlaps = sem.gate_root_cuts(root_cuts, rep["w0"], rep["new_end"])
    nested = sem.gate_nested(nested_rows, rep["w0"], rep["new_end"])
    rise = sem.gate_rise(nested_rows, rep["w0"])
    if overlaps:
        refusals.append("ROOT_CUT_OVERLAP: " + "; ".join(overlaps))
    if nested:
        refusals.append("NESTED_CUTS_IN_WINDOW: " + "; ".join(nested))
    if rise:
        refusals.append("RISE_OVERLAPS_WINDOW: " + "; ".join(rise))
    refusals.extend(gate_tail_gap(root_cuts, rep["w0"], block))
    for kind, pattern in LABELS.items():
        if sem.looks_like_handoff_camera(pattern % geom["scene"], [TAGS[0], TAGS[1] % geom["scene"]]):
            refusals.append("LABEL_LOOKS_LIKE_HANDOFF: " + pattern % geom["scene"])
    refusals.extend("BLOCK_CHECK: " + text for text in failures)
    risers = [row["sequence"] for row in nested_rows
              if "HangarRise" in row["sequence"] and row.get("active") and row["in_parent"][1] < rep["new_end"]]
    if risers:
        warnings.append("RISE_SECTION_ENDS_BEFORE_BLOCK_END: %r; what the hangar (pose, keyed lights) shows after "
                        "the rise section ends is UNMEASURED (S1 has lived with it since 30 Sep)" % risers)
    if block["card_material"] == CARD_MATERIAL:
        warnings.append("CARD_IS_PLAIN_LIT: the placeholder screen is not emissive and nothing lights it; "
                        "it may read dark at the back of the hangar")
    warnings.append("SHOW_GROWS: this Scene grows by %.2f s" % rep["grow_s"])
    return {"geometry": geom, "plan": plan, "refusals": refusals, "warnings": warnings,
            "apply_ready": not refusals}


def extend_mode_for(cue_label, new_end):
    """The mode file Soft goods' extend_scene_playback.py takes (its :8-11)."""
    return {"scene_label": cue_label, "new_end_frame": int(new_end), "dry_run": True}


# ----------------------------------------------------------------------------
# Unreal side (DRAFT: every call has a cited precedent in scene_exit_move.py /
# hangar_exit_doors.py / opening_sequence_apply.py; this file has never run)
# ----------------------------------------------------------------------------

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _load_json(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise PlanError("missing " + path)
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)


def _stop(run, reason):
    unreal.log_error("SCENE_EXIT_BLOCK_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    def names(values):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in values)
    return {"content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _actors_by_label():
    index = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        index.setdefault(str(actor.get_actor_label()), []).append(actor)
    return index


def _one(index, label, run):
    rows = index.get(label, [])
    if len(rows) != 1:
        _stop(run, "ACTOR_COUNT|label=%s|count=%d" % (label, len(rows)))
    return rows[0]


def _content_file(path, ext=".uasset"):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ext


def _binding_names(sequence):
    return {_guid(binding.get_id()): str(binding.get_display_name()) for binding in sequence.get_bindings()}


def _section_span(section, start, end):
    a = section.get_start_frame() if section.has_start_frame() else start
    b = section.get_end_frame() if section.has_end_frame() else end
    return int(a), int(b)


def _root_cut_rows(sequence, names):
    start, end = sequence.get_playback_start(), sequence.get_playback_end()
    rows = []
    for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for section in track.get_sections():
            guid = _guid(section.get_camera_binding_id().get_editor_property("guid"))
            name = names.get(guid, "?" + guid)
            a, b = _section_span(section, start, end)
            rows.append({"label": name, "guid": guid, "start": a, "end": b, "active": bool(section.is_active()),
                         "handoff": ("Entry Handoff Camera" in name or "Exit Handoff Camera" in name)})
    return rows


def _nested_rows(sequence):
    start, end = sequence.get_playback_start(), sequence.get_playback_end()
    rows = []
    for track_type in (unreal.MovieSceneCinematicShotTrack, unreal.MovieSceneSubTrack):
        for track in sequence.find_tracks_by_type(track_type):
            for section in track.get_sections():
                sub = section.get_sequence()
                if sub is None:
                    continue
                cuts = [cut for cut_track in sub.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)
                        for cut in cut_track.get_sections() if cut.is_active()]
                rows.append({"track": track.get_class().get_name(), "sequence": sub.get_path_name().split(".")[0],
                             "in_parent": list(_section_span(section, start, end)),
                             "active": bool(section.is_active()), "sub_cut_count": len(cuts)})
    return rows


def _cut_gaps(sequence):
    start, end = sequence.get_playback_start(), sequence.get_playback_end()
    spans = sorted(_section_span(section, start, end)
                   for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)
                   for section in track.get_sections() if section.is_active())
    gaps, cursor, overlaps = [], start, []
    for a, b in spans:
        if a > cursor:
            gaps.append([cursor, a])
        if a < cursor:
            overlaps.append([a, min(b, cursor)])
        cursor = max(cursor, b)
    if cursor < end:
        gaps.append([cursor, end])
    return gaps, overlaps


def _scene_cue(show, n, run):
    label = "Scene %d — External Sound" % n
    cues = [cue for cue in show.get_editor_property("cues")
            if str(cue.get_editor_property("label")) == label and cue.get_editor_property("enabled")]
    if len(cues) != 1:
        _stop(run, "SCENE_CUE_COUNT|label=%s|count=%d" % (label, len(cues)))
    return cues[0], label


def _scene_bool(scene, run, *names):
    for name in names:  # memory puss-python-api-gotchas: bools are renamed in Python
        try:
            return bool(scene.get_editor_property(name))
        except Exception:  # noqa: BLE001
            continue
    _stop(run, "SCENE_BOOL_UNREADABLE|%r" % (names,))


def _pose(actor):
    rot = actor.get_actor_rotation()
    return {"location": [float(v) for v in actor.get_actor_location().to_tuple()],
            "rotation": [float(rot.roll), float(rot.pitch), float(rot.yaw)],
            "scale": [float(v) for v in actor.get_actor_scale3d().to_tuple()]}


def _root_landed(root, recorded, run, n):
    """The live root must be the landed root the doors tool recorded (3 Oct):
    composing against a REST/sunk root puts pieces ~35 m underground (memory
    puss-level-saved-landed-frame-trap)."""
    live = _pose(root)
    dl = max(abs(a - b) for a, b in zip(live["location"], recorded["location"]))
    dr = max(abs(((a - b) + 180.0) % 360.0 - 180.0) for a, b in zip(live["rotation"], recorded["rotation"]))
    if dl > ROOT_TOLERANCE_CM or dr > ROOT_TOLERANCE_DEG:
        _stop(run, "ROOT_NOT_LANDED|scene=%d|live=%r|recorded=%r" % (n, live, recorded))
    return live


def _gather(n, run):
    here = _here()
    doors = _load_json(os.path.join(here, DOORS_RECORD_NAME))
    if doors.get("world") != EXPECTED_WORLD or not doors.get("applied"):
        _stop(run, "DOORS_RECORD_CONTEXT")
    rows = [row for row in doors["plan"]["scenes"] if int(row["scene"]) == n]
    if len(rows) != 1:
        _stop(run, "DOORS_PLAN_ROW_COUNT|scene=%d" % n)
    hangar_plan = _load_json(os.path.join(os.path.dirname(here), HANGAR_PLAN_PATTERN % n))
    index = _actors_by_label()
    if any(label.startswith("ZZ_") for label in index):
        _stop(run, "ZZ_ACTORS_PRESENT")  # memory puss-benches-are-level-activity
    root = _one(index, ROOT_LABEL_PATTERN % n, run)
    root_pose = _root_landed(root, doors["root_before"][str(n)], run, n)
    leaf = _one(index, LEAF_LABEL_PATTERN % n, run)
    if leaf.get_attach_parent_actor() != root:
        _stop(run, "LEAF_NOT_ON_ROOT|scene=%d" % n)
    show = unreal.load_asset(SHOW_PATH)
    cue, cue_label = _scene_cue(show, n, run)
    scene = cue.get_editor_property("scene")
    sequence = scene.get_editor_property("sequence")
    if sequence is None:
        _stop(run, "SCENE_HAS_NO_SEQUENCE|scene=%d" % n)
    rate = sequence.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    if abs(fps - round(fps)) > 1.0e-6:
        _stop(run, "SCENE_FPS_NOT_INTEGRAL|%r" % fps)
    use_length = _scene_bool(scene, run, "use_sequence_length", "b_use_sequence_length")
    exit_cams = index.get("%s — Exit Handoff Camera" % cue_label, [])
    if len(exit_cams) != 1 or not exit_cams[0].actor_has_tag("InfinityStage.SceneRetainedHold"):
        _stop(run, "NOT_RETAINED_EXIT|scene=%d" % n)
    names = _binding_names(sequence)
    return {"doors_row": rows[0], "hangar": rows[0]["hangar_dimensions"], "root": root, "root_pose": root_pose,
            "leaf": leaf, "show": show, "cue": cue, "cue_label": cue_label, "sequence": sequence, "fps": fps,
            "use_sequence_length": use_length,
            "eye_z_root": float(hangar_plan["dock"]["loc"][2]) - float(root.get_actor_location().z),
            "live_end": int(sequence.get_playback_end()),
            "hold_frames": hold_frames_from_ticks(scene.get_editor_property("exit_handoff_hold_frames").value, fps),
            "root_cuts": _root_cut_rows(sequence, names), "nested": _nested_rows(sequence),
            "bound_names": set(names.values()), "exit_camera": exit_cams[0], "index": index}


def _space_occupants(n, root, cg, raise_cm):
    """Non-hangar actors whose bounds touch the curtain's swept box (hung to
    raised), in the root frame.  Huge conservative AABBs are listed apart."""
    lo, hi = box_minmax(cg["curtain"]["center"], cg["curtain"]["size"])
    hi = [hi[0], hi[1], hi[2] + raise_cm]
    root_xf = root.get_actor_transform()
    hits, unchecked = [], []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label = str(actor.get_actor_label())
        if label.startswith("S%d Hangar" % n) or label.startswith("S%d Exit Block" % n):
            continue
        # A light actor's bounds include its influence volume (cone/attenuation), not a body: 4 Oct every
        # Scene's back-wall uplight "occupied" the curtain slab this way. Skip pure lights; a light that
        # carries a mesh body (StaticMeshComponent) is still checked.
        if isinstance(actor, unreal.Light) and actor.get_component_by_class(unreal.StaticMeshComponent) is None:
            continue
        origin, extent = actor.get_actor_bounds(False)
        corners = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    world = unreal.Vector(origin.x + sx * extent.x, origin.y + sy * extent.y, origin.z + sz * extent.z)
                    local = unreal.MathLibrary.inverse_transform_location(root_xf, world)
                    corners.append((local.x, local.y, local.z))
        a = [min(c[i] for c in corners) for i in range(3)]
        b = [max(c[i] for c in corners) for i in range(3)]
        if any(b[i] < lo[i] or a[i] > hi[i] for i in range(3)):
            continue
        (unchecked if max(b[0] - a[0], b[1] - a[1]) > 20000.0 else hits).append(label)
    return hits, unchecked


def _read_markers(sequence):
    unit = unreal.MovieSceneTimeUnit
    raw = sequence.get_marked_frames_from_sequence(unit.DISPLAY_RATE)  # opening_sequence_apply.py:291-292
    return [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)] for m in raw]


def _spawn_box(subsystem, root, label, tags, mesh, material, center, size):
    """hangar_exit_doors.py:605-633, root-relative on the LIVE root."""
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, root.get_actor_location(),
                                             root.get_actor_rotation(), False)
    actor.set_actor_label(label)
    component = actor.get_editor_property("static_mesh_component")
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_static_mesh(mesh)
    component.set_material(0, material)
    actor.attach_to_actor(root, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    actor.set_actor_relative_location(unreal.Vector(*center), False, True)
    actor.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False, True)
    actor.set_actor_relative_scale3d(unreal.Vector(*[float(v) / CUBE_SIZE_CM for v in size]))
    actor.tags = [unreal.Name(tag) for tag in tags]
    return actor


# Channel names as scene_exit_move.py:690-691 (key_walkin_i1_p02.py:313-316);
# APPLY refuses on a missing name rather than guessing (memory
# ue58-sequencer-read-traps: names may carry suffixes).
POSE_CHANNELS = {"Location.X": 1, "Location.Y": 2, "Location.Z": 3,
                 "Rotation.X": 6, "Rotation.Y": 4, "Rotation.Z": 5}


def _key_pose_track(binding, actor, keys, section_range, run, label):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    track.set_display_name(TRACK_NAME)
    section = track.add_section()
    section.set_range(section_range[0], section_range[1])
    channels = {str(channel.channel_name): channel for channel in section.get_all_channels()}
    missing = sorted((set(POSE_CHANNELS) | {"Scale.X", "Scale.Y", "Scale.Z"}) - set(channels))
    if missing:
        _stop(run, "CHANNELS_MISSING|%s|%r|NOTHING SAVED" % (label, missing))
    for key in keys:
        for name, index in POSE_CHANNELS.items():
            made = channels[name].add_key(unreal.FrameNumber(int(key[0])), float(key[index]),
                                          time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                          interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
            if made is None:
                _stop(run, "ADD_KEY_NONE|%s|%s|%d|NOTHING SAVED" % (label, name, key[0]))
    scale = actor.root_component.get_editor_property("relative_scale3d")
    for name, value in (("Scale.X", scale.x), ("Scale.Y", scale.y), ("Scale.Z", scale.z)):
        channels[name].set_default(float(value))  # unkeyed scale would evaluate 0
    return section


def _readback_keys(section, keys, run, label):
    channels = {str(channel.channel_name): channel for channel in section.get_all_channels()}
    for name, index in POSE_CHANNELS.items():
        read = list(channels[name].get_keys())
        if len(read) != len(keys) or abs(float(read[-1].get_value()) - float(keys[-1][index])) > 1.0e-3:
            _stop(run, "READBACK_KEYS|%s|%s|n=%d/%d" % (label, name, len(read), len(keys)))


def _live_report(n, g, params, run):
    sem = load_exit_move(os.path.join(_here(), EXIT_MOVE_NAME), g["fps"])
    plan_path = os.path.join(_here(), PLAN_PATTERN % n)
    plan_file = _load_json(plan_path, required=False)
    state, content_end = playback_state(g["live_end"], plan_file)
    if state == "drift":
        _stop(run, "PLAYBACK_END_DRIFT|live_end=%d|plan=%r" % (g["live_end"], {k: plan_file.get(k) for k in ("content_end", "new_end")}))
    report = build_block_dry_report(sem, g["doors_row"], g["hangar"], g["eye_z_root"], content_end,
                                    g["hold_frames"], g["root_cuts"], g["nested"], params)
    report["state"] = state
    rep = report["plan"]["report"]
    if state == "extended" and rep["new_end"] != g["live_end"]:
        report["refusals"].append("PLAN_NEW_END_MISMATCH: params now give new_end %d but the Scene ends at %d "
                                  "(params changed after the extension?)" % (rep["new_end"], g["live_end"]))
    if not g["use_sequence_length"]:
        report["refusals"].append("USE_SEQUENCE_LENGTH_OFF: the Show would not see the longer Scene "
                                  "(InfinityStageCompiler.cpp:17-40)")
    if os.path.isfile(os.path.join(_here(), EXIT_MOVE_RECORD_PATTERN % n)) or \
            (EXIT_MOVE_CAMERA_LABEL % n) in g["index"]:
        report["refusals"].append("SCENE_EXIT_MOVE_PRESENT: revert scene_exit_move for S%d first" % n)
    for kind, pattern in LABELS.items():
        if (pattern % n) in g["index"]:
            report["refusals"].append("ACTOR_EXISTS: %s (revert first)" % (pattern % n))
    for label in [pattern % n for pattern in LABELS.values()] + [str(g["leaf"].get_actor_label())]:
        if label in g["bound_names"]:
            report["refusals"].append("ALREADY_BOUND_IN_SCENE: %s" % label)
    hits, unchecked = _space_occupants(n, g["root"], report["plan"]["cg"], rep["raise_cm"])
    report["curtain_space"] = {"occupants": hits, "unchecked_large": unchecked}
    if hits:
        report["refusals"].append("CURTAIN_SPACE_OCCUPIED: %r" % hits)
    if state == "pre":
        report["next_step"] = {"extend_scene_playback_mode": extend_mode_for(g["cue_label"], rep["new_end"]),
                               "note": "Run Soft goods' extend_scene_playback.py DRY then APPLY with this mode "
                                       "(its key gate, rematch and Master rebuild), then this tool again."}
    report["apply_ready"] = not report["refusals"] and state == "extended"
    report["exit_move_sha256"] = sem.SOURCE_SHA256
    return sem, report, plan_path, plan_file, state


def run_dry(n, run, params):
    g = _gather(n, run)
    sem, report, plan_path, plan_file, state = _live_report(n, g, params, run)
    rep = report["plan"]["report"]
    if state == "pre":
        _write_json(plan_path, {"scene": n, "run": run, "cue_label": g["cue_label"], "fps": g["fps"],
                                "content_end": rep["content_end"], "new_end": rep["new_end"],
                                "w0": rep["w0"], "w1": rep["w1"], "params": params,
                                "exit_move_sha256": sem.SOURCE_SHA256})
    out = os.path.join(_here(), "scene_exit_block_S%d_dry.json" % n)
    _write_json(out, {k: v for k, v in report.items() if k != "plan"} |
                {"report": rep, "markers": report["plan"]["markers"], "key_counts": {
                    k: len(report["plan"][k]) for k in ("camera_keys", "leaf_keys", "curtain_keys", "card_keys")}})
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("SCENE_EXIT_BLOCK_DRY_OK|run=%s|scene=%d|mutated=0|state=%s|content_end=%d|new_end=%d|grow_s=%.2f|"
               "apply_ready=%d|refusals=%d|warnings=%d|report=%s"
               % (run, n, state, rep["content_end"], rep["new_end"], rep["grow_s"], int(report["apply_ready"]),
                  len(report["refusals"]), len(report["warnings"]), out))


def run_apply(n, run, params, overrides):
    if not decided(overrides, n):
        _stop(run, "NOT_DECIDED|scene_exit_block_overrides.json needs decided_by and scenes containing %d" % n)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|" + json.dumps(_census()))
    g = _gather(n, run)
    sem, report, plan_path, plan_file, state = _live_report(n, g, params, run)
    if state != "extended":
        _stop(run, "NOT_EXTENDED|live_end=%d|run extend_scene_playback first" % g["live_end"])
    if plan_file.get("exit_move_sha256") != sem.SOURCE_SHA256:
        _stop(run, "EXIT_MOVE_CHANGED_SINCE_PLAN|rerun DRY")
    if report["refusals"]:
        _stop(run, "REFUSED|" + " || ".join(report["refusals"]))
    plan, rep = report["plan"], report["plan"]["report"]
    sequence, root, leaf = g["sequence"], g["root"], g["leaf"]
    seq_path = sequence.get_path_name().split(".")[0]
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreSceneExitBlock-S%d-%s" % (n, run))
    os.makedirs(backup, exist_ok=False)
    copied = []
    for source in (_content_file(seq_path), _content_file(EXPECTED_WORLD, ".umap"), _content_file(SHOW_PATH)):
        if not os.path.isfile(source):
            _stop(run, "BACKUP_SOURCE_MISSING|" + source)
        target = os.path.join(backup, os.path.basename(source))
        shutil.copy2(source, target)
        if os.path.getsize(target) != os.path.getsize(source):
            _stop(run, "BACKUP_SIZE_MISMATCH|" + source)
        copied.append(target)
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    record = {"schema_version": 1, "run": run, "scene": n, "world": EXPECTED_WORLD, "sequence": seq_path,
              "cue_guid": _guid(g["cue"].get_editor_property("cue_guid")), "backup": backup,
              "backup_files": copied, "applied": False, "report": rep, "root_pose": g["root_pose"],
              "root_cuts_before": g["root_cuts"], "markers_before": _read_markers(sequence),
              "decided_by": overrides.get("decided_by"), "decision": overrides.get("decision")}
    _write_json(record_path, record)  # written BEFORE any mutation

    # 1. Level actors on the live landed root.
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cube = unreal.load_asset(CUBE_PATH)
    curtain_mi = unreal.load_asset(rep["block_params"]["curtain_material"])
    card_mi = unreal.load_asset(rep["block_params"]["card_material"])
    if cube is None or curtain_mi is None or card_mi is None:
        _stop(run, "ASSET_LOAD|cube=%s|curtain=%s|card=%s|NOTHING SAVED" % (cube, curtain_mi, card_mi))
    tags = [TAGS[0], TAGS[1] % n]
    cg = plan["cg"]
    curtain = _spawn_box(subsystem, root, LABELS["curtain"] % n, tags, cube, curtain_mi,
                         cg["curtain"]["center"], cg["curtain"]["size"])
    card = _spawn_box(subsystem, root, LABELS["card"] % n, tags + [SCREEN_TAG % n], cube, card_mi,
                      cg["card"]["center"], cg["card"]["size"])
    final = plan["camera_keys"][-1]
    camera = subsystem.spawn_actor_from_class(unreal.CineCameraActor, root.get_actor_location(),
                                              root.get_actor_rotation(), False)
    camera.set_actor_label(LABELS["camera"] % n)
    camera.tags = [unreal.Name(tag) for tag in tags]
    camera.attach_to_actor(root, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                           unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    camera.set_actor_relative_location(unreal.Vector(final[1], final[2], final[3]), False, True)
    camera.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False, True)
    component = camera.get_cine_camera_component()
    component.set_editor_property("current_focal_length", float(final[7]))
    focus = component.get_editor_property("focus_settings")
    focus.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    focus.set_editor_property("manual_focus_distance", float(final[8]))
    component.set_editor_property("focus_settings", focus)
    # Inside-box guard on what was actually spawned (world bounds -> live root frame).
    root_xf = root.get_actor_transform()
    for actor, dz in ((curtain, 0.0), (card, 0.0), (curtain, rep["raise_cm"]), (card, rep["raise_cm"])):
        origin, extent = actor.get_actor_bounds(False)
        pts = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    local = unreal.MathLibrary.inverse_transform_location(
                        root_xf, unreal.Vector(origin.x + sx * extent.x, origin.y + sy * extent.y,
                                               origin.z + sz * extent.z))
                    pts.append((local.x, local.y, local.z + dz))
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        bad = inside_box(lo, hi, g["hangar"], report["geometry"]["door_face_x"], report["geometry"]["floor_z"],
                         float(rep["block_params"]["box_margin_cm"]))
        if bad:
            _stop(run, "SPAWNED_OUTSIDE_HANGAR_BOX|%s|dz=%.0f|axes=%s|NOTHING SAVED; Don't-Save restart"
                  % (actor.get_actor_label(), dz, bad))

    # 2. Bindings, keys, cut, markers.
    cam_binding = sequence.add_possessable(camera)
    comp_binding = sequence.add_possessable(component)
    comp_binding.set_parent(cam_binding)
    leaf_binding = sequence.add_possessable(leaf)
    curtain_binding = sequence.add_possessable(curtain)
    card_binding = sequence.add_possessable(card)
    w0, w1, new_end = rep["w0"], rep["w1"], rep["new_end"]
    cam_section = _key_pose_track(cam_binding, camera, plan["camera_keys"], (w0, new_end), run, "camera")
    leaf_section = _key_pose_track(leaf_binding, leaf, plan["leaf_keys"], (rep["door_start_frame"], new_end), run, "leaf")
    curtain_section = _key_pose_track(curtain_binding, curtain, plan["curtain_keys"], (w0, new_end), run, "curtain")
    card_section = _key_pose_track(card_binding, card, plan["card_keys"], (w0, new_end), run, "card")
    focus_track = comp_binding.add_track(unreal.MovieSceneFloatTrack)
    focus_track.set_property_name_and_path(unreal.Name("ManualFocusDistance"), "FocusSettings.ManualFocusDistance")
    focus_track.set_display_name(TRACK_NAME)
    focus_section = focus_track.add_section()
    focus_section.set_range(w0, new_end)
    focus_channels = list(focus_section.get_all_channels())
    if len(focus_channels) != 1:
        _stop(run, "FOCUS_CHANNELS|%d|NOTHING SAVED" % len(focus_channels))
    for key in plan["camera_keys"]:
        focus_channels[0].add_key(unreal.FrameNumber(int(key[0])), float(key[8]),
                                  time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                  interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    cut_tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(cut_tracks) != 1:
        _stop(run, "CUT_TRACK_COUNT|%d|NOTHING SAVED" % len(cut_tracks))
    cut = cut_tracks[0].add_section()
    cut.set_camera_binding_id(sequence.get_binding_id(cam_binding))
    cut.set_range(w0, w1)  # ONE call; [a, b)
    if [m for m in _read_markers(sequence) if m[0].startswith(MARKER_PREFIX)]:
        _stop(run, "MARKERS_EXIST|NOTHING SAVED")
    for label, frame in plan["markers"]:
        marked = unreal.MovieSceneMarkedFrame()
        marked.set_editor_property("label", label)
        marked.set_editor_property("frame_number", unreal.FrameNumber(int(frame)))
        sequence.add_marked_frame_to_sequence(marked, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    sequence.sort_marked_frames()
    record.update({"labels": {k: v % n for k, v in LABELS.items()},
                   "binding_guids": {"camera": _guid(cam_binding.get_id()), "component": _guid(comp_binding.get_id()),
                                     "leaf": _guid(leaf_binding.get_id()), "curtain": _guid(curtain_binding.get_id()),
                                     "card": _guid(card_binding.get_id())},
                   "cut_range": [w0, w1]})
    _write_json(record_path, record)

    # 3. The builder's own rematch: Entry [start, W0), retained Exit [W1, end).
    entry = _one(_actors_by_label(), "%s — Entry Handoff Camera" % g["cue_label"], run)
    entry_before = entry.get_actor_location()
    result = unreal.InfinityStageCameraPilotLibrary.match_named_scene_handoffs(
        g["show"], [g["cue"].get_editor_property("cue_guid")], 1)
    matched, match_report = result if isinstance(result, tuple) else (result, "")
    if not matched:
        _stop(run, "MATCH_FAILED|NOTHING SAVED; Don't-Save restart|" + str(match_report))
    if (entry.get_actor_location() - entry_before).length() > 0.5:
        _stop(run, "ENTRY_MOVED_ON_MATCH|NOTHING SAVED; Don't-Save restart")
    if (g["exit_camera"].get_actor_location() - camera.get_actor_location()).length() > 1.0:
        _stop(run, "EXIT_HOLD_NOT_FINAL_POSE|NOTHING SAVED; Don't-Save restart")
    gaps, overlaps = _cut_gaps(sequence)
    if gaps or overlaps:
        _stop(run, "CUT_COVERAGE|gaps=%r|overlaps=%r|NOTHING SAVED; Don't-Save restart" % (gaps, overlaps))
    census = _census()
    if census != {"content": [seq_path], "maps": [EXPECTED_WORLD]}:
        _stop(run, "UNEXPECTED_DIRTY|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))

    # 4. Save exactly the sequence and the level; read back.
    if not unreal.EditorAssetLibrary.save_loaded_asset(sequence, False):
        _stop(run, "SEQUENCE_SAVE_FAILED")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        _stop(run, "LEVEL_SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|" + json.dumps(_census()))
    names = _binding_names(sequence)
    missing = [k for k, guid in record["binding_guids"].items() if guid not in names]
    if missing:
        _stop(run, "READBACK_BINDING_MISSING|%r" % missing)
    for section, keys, label in ((cam_section, plan["camera_keys"], "camera"), (leaf_section, plan["leaf_keys"], "leaf"),
                                 (curtain_section, plan["curtain_keys"], "curtain"),
                                 (card_section, plan["card_keys"], "card")):
        _readback_keys(section, keys, run, label)
    rows = _root_cut_rows(sequence, names)
    exit_rows = [row for row in rows if "Exit Handoff Camera" in row["label"]]
    ours = [row for row in rows if row["guid"] == record["binding_guids"]["camera"]]
    if len(exit_rows) != 1 or exit_rows[0]["start"] != w1 or exit_rows[0]["end"] != new_end:
        _stop(run, "READBACK_EXIT_RANGE|%r" % exit_rows)
    if len(ours) != 1 or [ours[0]["start"], ours[0]["end"]] != [w0, w1]:
        _stop(run, "READBACK_BLOCK_CUT|%r" % ours)
    marks = [m for m in _read_markers(sequence) if m[0].startswith(MARKER_PREFIX)]
    if sorted(marks) != sorted([list(m) for m in plan["markers"]]):
        _stop(run, "READBACK_MARKERS|%r" % marks)
    index = _actors_by_label()
    for kind, center in (("curtain", cg["curtain"]["center"]), ("card", cg["card"]["center"])):
        actor = _one(index, LABELS[kind] % n, run)
        rel = list(actor.root_component.get_editor_property("relative_location").to_tuple())
        if actor.get_attach_parent_actor() != root or max(abs(a - b) for a, b in zip(rel, center)) > 0.1:
            _stop(run, "READBACK_ACTOR|%s|rel=%r|want=%r" % (kind, rel, center))
    record.update({"applied": True, "root_cuts_after": rows, "census_after": _census()})
    _write_json(record_path, record)
    unreal.log("SCENE_EXIT_BLOCK_APPLY_OK|run=%s|scene=%d|window=[%d,%d)|end=%d|backup=%s|record=%s|"
               "tests_required_singly=InfinityStage.Editor.SceneCutBindingsResolve,"
               "InfinityStage.Editor.SavedMasterMatchesShow" % (run, n, w0, w1, new_end, backup, record_path))


def run_revert(n, run):
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    record = _load_json(record_path)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or int(record["scene"]) != n:
        _stop(run, "REVERT_RECORD_CONTEXT")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|" + json.dumps(_census()))
    sequence = unreal.load_asset(record["sequence"])
    show = unreal.load_asset(SHOW_PATH)
    cue, _ = _scene_cue(show, n, run)
    if _guid(cue.get_editor_property("cue_guid")) != record["cue_guid"]:
        _stop(run, "CUE_GUID_CHANGED")
    names = _binding_names(sequence)
    wanted = set(record["binding_guids"].values())
    if not wanted <= set(names):
        _stop(run, "RECORDED_BINDINGS_MISSING|%r" % sorted(wanted - set(names)))
    index = _actors_by_label()
    actors = {kind: _one(index, label, run) for kind, label in record["labels"].items()}
    for kind, actor in actors.items():
        if not actor.actor_has_tag(TAGS[1] % n):
            _stop(run, "REVERT_ACTOR_TAG|%s" % kind)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreSceneExitBlock-S%d-%s-revert" % (n, run))
    os.makedirs(backup, exist_ok=False)
    for source in (_content_file(record["sequence"]), _content_file(EXPECTED_WORLD, ".umap")):
        shutil.copy2(source, os.path.join(backup, os.path.basename(source)))
    removed = 0
    for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for section in list(track.get_sections()):
            if _guid(section.get_camera_binding_id().get_editor_property("guid")) == record["binding_guids"]["camera"]:
                track.remove_section(section)
                removed += 1
    if removed != 1:
        _stop(run, "REVERT_CUT_COUNT|%d|NOTHING SAVED; Don't-Save restart" % removed)
    for kind in ("component", "camera", "leaf", "curtain", "card"):  # child before parent
        for binding in sequence.get_bindings():
            if _guid(binding.get_id()) == record["binding_guids"][kind]:
                binding.remove()  # every binding here was created by APPLY (ALREADY_BOUND gate)
    marks = _read_markers(sequence)
    for i in sorted([i for i, m in enumerate(marks) if m[0].startswith(MARKER_PREFIX)], reverse=True):
        sequence.delete_marked_frame(i)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.values():
        subsystem.destroy_actor(actor)
    result = unreal.InfinityStageCameraPilotLibrary.match_named_scene_handoffs(show, [cue.get_editor_property("cue_guid")], 1)
    if not (result[0] if isinstance(result, tuple) else result):
        _stop(run, "REVERT_MATCH_FAILED|NOTHING SAVED; Don't-Save restart")
    gaps, overlaps = _cut_gaps(sequence)
    if gaps or overlaps:
        _stop(run, "REVERT_CUT_COVERAGE|gaps=%r|overlaps=%r|NOTHING SAVED; Don't-Save restart" % (gaps, overlaps))
    after = _root_cut_rows(sequence, _binding_names(sequence))
    shape = lambda rows: sorted(({k: r[k] for k in ("label", "start", "end", "active")} for r in rows), key=json.dumps)
    if shape(after) != shape(record["root_cuts_before"]):
        _stop(run, "REVERT_CUTS_DIFFER|before=%r|now=%r|NOTHING SAVED; Don't-Save restart"
              % (shape(record["root_cuts_before"]), shape(after)))
    if sorted(_read_markers(sequence)) != sorted(record["markers_before"]):
        _stop(run, "REVERT_MARKERS_DIFFER|NOTHING SAVED; Don't-Save restart")
    census = _census()
    if census != {"content": [record["sequence"]], "maps": [EXPECTED_WORLD]}:
        _stop(run, "REVERT_UNEXPECTED_DIRTY|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))
    if not unreal.EditorAssetLibrary.save_loaded_asset(sequence, False):
        _stop(run, "SEQUENCE_SAVE_FAILED")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        _stop(run, "LEVEL_SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|" + json.dumps(_census()))
    left = [label for label in record["labels"].values() if label in _actors_by_label()]
    if left:
        _stop(run, "REVERT_ACTORS_REMAIN|%r" % left)
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("SCENE_EXIT_BLOCK_REVERT_OK|run=%s|scene=%d|backup=%s|record=%s|scene_still_long=1|"
               "to_shorten=extend_scene_playback new_end_frame=%d" % (run, n, backup, archived,
                                                                    record["report"]["content_end"]))


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    n = int(globals().get("SCENE_EXIT_BLOCK_SCENE", 0))
    apply = bool(globals().get("SCENE_EXIT_BLOCK_APPLY"))
    revert = bool(globals().get("SCENE_EXIT_BLOCK_REVERT"))
    if not 1 <= n <= 6:
        _stop(run, "SCENE_NOT_SET")
    if apply and revert:
        _stop(run, "APPLY_AND_REVERT_BOTH_SET")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")  # never end PIE; just refuse
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")  # an open Sequencer evaluates and dirties the map
    if revert:
        run_revert(n, run)
        return
    overrides = _load_json(os.path.join(_here(), OVERRIDES_NAME), required=False)
    params = dict(overrides.get("params", {}))
    params.update(overrides.get("scene_params", {}).get(str(n), {}))
    try:
        if apply:
            run_apply(n, run, params, overrides)
        else:
            run_dry(n, run, params)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
