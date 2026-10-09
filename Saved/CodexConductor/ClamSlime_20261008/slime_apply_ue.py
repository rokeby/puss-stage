"""CLAM SLIME (Gary 8 Oct, his words: "how hard is it to get a hint of slime when the clam opens?" -> option 2 "A few
mucus strands that stretch and snap"; and "the clam hinge is not connected - in that the top hovers over the bottom a
little").  Unreal 5.8 tool, written OFFLINE 8 Oct.  NOT RUN.  Runner: ExecuteProjectPythonFile
relativeSavedPath "CodexConductor/ClamSlime_20261008/slime_apply_ue.py" (one mode per call; args slime_apply_args.json).

Tiers: [decl] declaration-proven (header / record we can read, cited), [prec] an in-repo call that RAN (cited),
[bin] DLL strings, [meas] intervention + read-back, [inf] inferred (why stated).  Every [inf] below is gated by a
read-back that fails closed with a named reason.

WHAT IT MAKES (sources: build/SK_PearlClam_Slime.fbx + build/A_PearlClam_SlimeOpen.fbx, build_slime.py):
  ONE skeletal mesh SK_PearlClam_Slime (ligament band filling the hinge slot + 5 mucus strands at the front lip),
  its own skeleton, the AnimSequence A_PearlClam_SlimeOpen (lid bone 0 -> -55 deg over anim frames 0..300 on the
  live clam_open curve, then held to frame 4794; the strands stretch, neck and snap at 8.6-30.2 deg), two create-only
  masters + MIs.  ONE SkeletalMeshActor "S3 PearlClam Slime" attached to "S3 PearlClam" at the IDENTITY relative
  transform (the slime's bone "root" = the bottom's origin, bone "lid" = the hinge pivot), hidden in game, revealed
  and animated by ONE new binding in LS_DevScene_03.

MODES (confirm "<MODE> CLAMSLIME" for IMPORT / APPLY / REVERT):
  DRY     read-only.  Guards, sources (sha256, design/build reports and their checks), assets present, the lid's live
          Rotation.X keys vs the design curve, root + twin + lid-binding snapshots, the full APPLY plan.
          Writes slime_dry_<run>.json.  CLAMSLIME_DRY_OK|apply_ready=0/1|...
  IMPORT  create-only, refuses if ANY target asset exists.  (1) mesh FBX -> SK_PearlClam_Slime + a NEW skeleton
          (Interchange override, pipeline pattern of s3_sack_install._pipeline [prec: s3_sack_install_import_record.json
          saved true]; no physics asset, materials, textures, morphs or animation); (2) anim FBX -> animation only on that
          skeleton; (3) masters M_PearlClam_Slime (MASKED) + M_PearlClam_Ligament (OPAQUE) and their MIs; (4) the mesh's
          two slots -> the MIs.  Gates (read back): stray-asset diff, bone tree == design (root first, every other bone
          root's child; an extra "Armature" bone refuses), slots, bounds == design (Y flipped), render verts, anim length,
          and the anim's lid bone vs the design curve at every 6th frame (sign included).  Saves exactly the created
          packages.  CLAMSLIME_IMPORT_OK.
  APPLY   record FIRST (exclusive), Backups/PreClamSlime-<run>/ (umap + LS_DevScene_03.uasset, sha256), then: spawn +
          attach + flags; binding "S3 PearlClam Slime" in LS_DevScene_03 with (a) a skeletal-animation section
          [1446, 6240) playing A_PearlClam_SlimeOpen from its frame 0 at rate 1 and (b) a visibility section [0, 6240)
          keyed hidden at 0 and visible at 1446 (the frame the anim starts; the slime is hidden inside the closed
          seam until then).  Census-exact save (map + Scene only), read back after the save: actor, attachment,
          binding resolves to the actor, both sections, the anim's lid curve vs the LIVE lid keys, and the lid binding
          + the 'Fade' pearl twin + the root bit-identical to the record.  CLAMSLIME_APPLY_OK.
  REVERT  exact inverse from the record; refuses on drift (actor moved / relabelled / re-attached, binding changed,
          sections changed, lid binding or twin changed).  Removes OUR binding (by GUID, after proving it resolves to
          our actor), destroys OUR actor; census-exact save; read back.  Assets stay (create-only; delete by hand if
          wanted).  CLAMSLIME_REVERT_OK.

REVEAL (checked against CLAM_APPLY, as asked): CLAM_APPLY made every clam part hidden in game and gave EACH its own copy
  of the stone's LS_S3_HangarRise visibility section [decl ../S3Millstone/s3_pearlclam_apply_record.json plan.reveal:
  targets Bottom/Lid/Mantle/Pearl, keys [[0,false],[139,true]] at 30 fps; s3_props_ue.py:55-56 "bHidden does not
  propagate to attached actors"]; the float hold then keeps them visible in LS_DevScene_03 over [744, 6240)
  [decl ../s3_hangar_float_hold_record.json rows "-/S3 PearlClam Lid/None" ... value true, bHiddenInGame].  The slime
  does NOT join the rise: it only needs to exist from the opening, so its single visibility section lives on its own
  LS_DevScene_03 binding (same Scene as the animation; one binding to REVERT).  Visibility channel true = visible
  [decl: the rise reveal keys false->true]; property path bHidden (NOT bHiddenInGame: inert, measured 8 Oct by Conductor 5) set when empty [prec klara_reveal.py:3131-3135
  via s4_hangar_hold.py:1128-1129, S3FLOATHOLD applied].  A visibility track keeps the display name "Visibility"
  [meas s4_hangar_hold.py:1024-1026].

INFERRED (each is gated or listed for the editor slot):
  * Interchange makes the skeleton root "root" and drops the FBX Null "Armature" [inf; a UTF-16 "armature" literal is
    in UnrealEditor-InterchangeFbxParser.dll [bin], purpose unknown].  Gate ROOT_HAS_PARENT / BONES.
  * The FBX -> UE frame maps Blender (x, y, z) -> UE (x, -y, z) for the skeletal mesh as it did for the clam statics
    [decl manifest "to_unreal" [inf] there; [meas] for the statics by IMPORT_MESH's Y_NOT_FLIPPED gate].  Gate BOUNDS.
  * The anim's lid bone, mirrored the same way, reads Roll = -deg like the live lid actor [inf: rot_x(-a) under
    diag(1,-1,1) is rot_x(+a), and FRotator Roll r is rot_x(-r) in UE's row-vector matrices].  Gate LID_CURVE (sign
    named LID_SIGN_FLIPPED).
  * Python write of MovieSceneSkeletalAnimationSection.params (get params struct, set "animation", write it back)
    [decl MovieSceneSkeletalAnimationSection.h:50-63,119-120; written by s3_chorus_sway.py:323-331 and
    s3_crowd_structure.py:361-368, neither proven RUN (no marker in Saved/Logs)].  Read back after write and save.
  * A skeletal-animation section longer than the anim LOOPS (FirstLoopStartFrameOffset exists,
    MovieSceneSkeletalAnimationSection.h:54-55 [decl]) -> the anim itself runs to the Scene end (4794 frames, held
    pose), and APPLY refuses a Scene whose playback end is past the anim (ANIM_SHORTER_THAN_SCENE).
  * The section is evaluated when LS_DevScene_03 plays as a sub-sequence of the Master/Show [inf: the lid's own keys
    on this Scene play (Gary watched the opening); a SkeletalMeshActor's default anim mode lets Sequencer drive it
    (bForceCustomMode false) [inf]].  Verify in PIE: README run order step 6.
  * SkeletalMesh.materials slot write (SkeletalMaterial.material_interface) [inf]; read back MATERIAL_SLOTS.

Crash rules (memory): no UE object at module level; no reloading the open level; locate_bound_objects only (never
SequencerTools.get_bound_objects); no material-node deletion (create-only); one import per FBX, GC after imports.
"""
import copy
import datetime
import hashlib
import json
import os
import re
import shutil

PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/ClamSlime_20261008/"
ARGS_FILE = HERE + "slime_apply_args.json"
IMPORT_RECORD = HERE + "slime_import_record.json"
APPLY_RECORD = HERE + "slime_apply_record.json"
DESIGN_JSON = HERE + "build/slime_design.json"
BUILD_JSON = HERE + "build/slime_build.json"
VALIDATE_JSON = HERE + "validate_slime_report.json"
FBX_MESH = HERE + "build/SK_PearlClam_Slime.fbx"
FBX_ANIM = HERE + "build/A_PearlClam_SlimeOpen.fbx"
CLAM_RECORD = PROJECT + "Saved/CodexConductor/S3Millstone/s3_pearlclam_apply_record.json"
CLAMOPEN_RECORD = PROJECT + "Saved/CodexConductor/ClamOpen_20261008/clam_open_record.json"

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
WORLD_NAME = "L_InfinityStage_V1VerticalSlice"
UMAP = PROJECT + "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
SCENE_FILE = PROJECT + "Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
BACKUP_ROOT = PROJECT + "Backups/PreClamSlime-"

ASSET_DIR = "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/Slime"
MESH = ASSET_DIR + "/SK_PearlClam_Slime"
SKELETON = ASSET_DIR + "/SK_PearlClam_Slime_Skeleton"          # Interchange naming "<mesh>_Skeleton" [inf; gated]
ANIM = ASSET_DIR + "/A_PearlClam_SlimeOpen"
M_SLIME, MI_SLIME = ASSET_DIR + "/M_PearlClam_Slime", ASSET_DIR + "/MI_PearlClam_Slime"
M_LIG, MI_LIG = ASSET_DIR + "/M_PearlClam_Ligament", ASSET_DIR + "/MI_PearlClam_Ligament"
SLOT_LIGAMENT, SLOT_SLIME = "M_PearlClam_Ligament", "M_PearlClam_Slime"
SLOT_MI = {SLOT_LIGAMENT: MI_LIG, SLOT_SLIME: MI_SLIME}

ROOT_LABEL = "S3 PearlClam"
LID_LABEL = "S3 PearlClam Lid"
TWIN_LABEL = "S3 PearlClam Pearl Fade"
LABEL = "S3 PearlClam Slime"
TAGS = ["RigAtmos.S3Props", "S3Props.PearlClam", "S3Props.PearlClam.Slime"]
FOLDER = "RigAtmos/S3Props"
LID_BINDING = "S3 Hangar Float Hold: S3 PearlClam Lid"
BINDING = LABEL
SKEL_TRACK, VIS_TRACK, XFORM_TRACK = "MovieSceneSkeletalAnimationTrack", "MovieSceneVisibilityTrack", \
    "MovieScene3DTransformTrack"
ROLL = "Rotation.X"

BONES_FIXED = ["root", "lid", "lig_1", "lig_2", "lig_3"]
STRANDS, STATIONS = 5, 6
BONES = BONES_FIXED + ["s%d_%s%d" % (i, h, k) for i in range(STRANDS) for h in ("lo", "up") for k in range(STATIONS)]
LID_PIVOT_BLENDER_CM = [0.0, 47.86, 30.02]
# AnimationLibrary.get_bone_pose_for_frame returned the imported local bone
# translation in authored Blender metres during batch 1f.  Mesh bounds remain
# centimetres.  Keep the units explicit so the two gates cannot be conflated.
LID_PIVOT_ANIM_M = [LID_PIVOT_BLENDER_CM[0] / 100.0,
                    -LID_PIVOT_BLENDER_CM[1] / 100.0,
                    LID_PIVOT_BLENDER_CM[2] / 100.0]

TOL_CM, TOL_DEG, TOL_REL = 0.05, 1e-3, 1e-3
BOUNDS_TOL_CM = 0.5
NS = "NOTHING SAVED; Don't-Save restart"
RUN = {"run": "?"}

DEFAULTS = {"mode": "DRY", "confirm": "", "run": None,
            "anim_start_frame": 1446, "reveal_frame": 1446, "expected_fps": 24.0, "expected_playback_end": 6240,
            "anim_last_frame": 4794, "require_validation_ok": True}


class Fail(Exception):
    pass


def _req(cond, msg):
    if not cond:
        raise Fail(msg)


# =====================================================================================================================
# Pure (offline-testable)
# =====================================================================================================================
def fresh_run(now=None):
    return "CLAMSLIME-" + (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")


def merged_args(raw):
    a = copy.deepcopy(DEFAULTS)
    a.update(raw or {})
    return a


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate_args(a):
    e = []
    if a.get("mode") not in ("DRY", "IMPORT", "APPLY", "REVERT"):
        e.append("MODE|%s" % a.get("mode"))
    elif a["mode"] != "DRY" and a.get("confirm") != "%s CLAMSLIME" % a["mode"]:
        e.append("CONFIRM|%s" % a.get("confirm"))
    for k in ("anim_start_frame", "reveal_frame", "expected_playback_end", "anim_last_frame"):
        if not _is_int(a.get(k)):
            e.append("NOT_INT|%s" % k)
    if not e and not (0 <= a["reveal_frame"] <= a["anim_start_frame"] < a["expected_playback_end"]):
        e.append("FRAMES|reveal %s <= start %s < end %s" % (a["reveal_frame"], a["anim_start_frame"],
                                                             a["expected_playback_end"]))
    return e


def channel_base(name):
    return re.sub(r"_\d+$", "", str(name))


def flip_y(v):
    return [v[0], -v[1], v[2]]


def expected_bounds_ue(design):
    """Blender cm rest bounds -> UE (x, -y, z) box."""
    lo, hi = design["rest_bounds_cm_blender"]["min"], design["rest_bounds_cm_blender"]["max"]
    return {"min": [lo[0], -hi[1], lo[2]], "max": [hi[0], -lo[1], hi[2]]}


def bounds_problems(got_origin, got_extent, design, tol=BOUNDS_TOL_CM):
    """Imported bounds (origin/extent) vs the design box.  A Y-UNflipped import names itself."""
    want = expected_bounds_ue(design)
    gmin = [o - e for o, e in zip(got_origin, got_extent)]
    gmax = [o + e for o, e in zip(got_origin, got_extent)]
    p = []
    ok = all(abs(a - b) <= tol for a, b in zip(gmin + gmax, want["min"] + want["max"]))
    if not ok:
        lo, hi = design["rest_bounds_cm_blender"]["min"], design["rest_bounds_cm_blender"]["max"]
        if all(abs(a - b) <= tol for a, b in zip(gmin + gmax, lo + hi)):
            p.append("Y_NOT_FLIPPED|%s..%s" % (gmin, gmax))
        else:
            p.append("BOUNDS|got %s..%s want %s..%s" % ([round(x, 2) for x in gmin], [round(x, 2) for x in gmax],
                                                       [round(x, 2) for x in want["min"]],
                                                       [round(x, 2) for x in want["max"]]))
    return p


def bone_tree_problems(tree):
    """tree {bone: parent}.  Want exactly BONES, root has no parent, every other bone's parent is root."""
    p = []
    if "Armature" in tree or "armature" in tree:
        p.append("ARMATURE_BONE_PRESENT|the FBX Null became a bone (re-export with armature_nodetype ROOT named root)")
    if tree.get("root", "MISSING") is not None:
        p.append("ROOT_HAS_PARENT|%s" % tree.get("root", "MISSING"))
    missing = sorted(set(BONES) - set(tree))
    extra = sorted(set(tree) - set(BONES))
    if missing or extra:
        p.append("BONES|missing=%s|extra=%s" % (missing[:5], extra[:5]))
    wrong = sorted(b for b in BONES if b != "root" and b in tree and tree[b] != "root")
    if wrong:
        p.append("PARENTS|%s" % wrong[:5])
    return p


def lid_curve_problems(rows, want, tol=TOL_DEG):
    """Validate AnimationLibrary lid rows; translations are authored metres.

    ``rows`` are ``(anim_frame, roll_deg, local_translation_m)``.  The FBX was
    built on a metre scene from a centimetre design, and batch 1f measured
    ``[0,-0.479,0.300]`` at every sampled frame.  That is the expected
    ``(x,-y,z)/100`` pivot, not a 100x-short mesh.
    """
    p = []
    if not rows:
        return ["LID_CURVE_EMPTY"]
    flipped = all(abs(r + want[f]) <= tol for f, r, _t in rows if f in want) and any(abs(want[f]) > 1.0 for f, _r, _t in rows
                                                                                       if f in want)
    for f, r, t in rows:
        if f not in want:
            p.append("LID_FRAME_UNPLANNED|%d" % f)
            continue
        if abs(r - want[f]) > tol:
            p.append("LID_CURVE|f=%d|anim %.5f|want %.5f" % (f, r, want[f]))
        if any(abs(a - b) > TOL_CM / 100.0 for a, b in zip(t, LID_PIVOT_ANIM_M)):
            p.append("LID_PIVOT_M|f=%d|got=%s|want=%s" %
                     (f, [round(x, 4) for x in t], [round(x, 4) for x in LID_PIVOT_ANIM_M]))
    if flipped:
        p.insert(0, "LID_SIGN_FLIPPED")
    return p[:8]


def design_want(design):
    """{anim_frame: roll_deg} from the design json (roll = -opening angle)."""
    return {int(f): -float(deg) for f, deg in design["anim"]["lid_open_deg_every_6th"]}


def live_want(roll_keys, start):
    """{anim_frame: roll} from the live lid Rotation.X keys at Scene frames start + k (k = 0, 6, ... 300) and the hold."""
    out = {}
    for k in roll_keys:
        f = int(k["frame"]) - int(start)
        if f >= 0 and k.get("sub", 0.0) == 0.0:
            out[f] = float(k["value"])
    return out


def anim_vs_lid_problems(rows, live_keys, design, start):
    """The anim's lid bone must match BOTH the design curve and the LIVE lid keys at every sampled frame."""
    lw = live_want(live_keys, start)
    dw = design_want(design)
    p = []
    missing = sorted(f for f in dw if f not in lw and f <= 300)
    if missing:
        p.append("LIVE_KEYS_MISSING|anim frames %s" % missing[:6])
    shared = {f: lw[f] for f in dw if f in lw}
    diff = [f for f in shared if abs(shared[f] - dw[f]) > TOL_DEG]
    if diff:
        p.append("DESIGN_VS_LIVE|frames %s (the live opening changed since the build: rebuild)" % diff[:6])
    p += lid_curve_problems([r for r in rows if r[0] in shared], shared)
    return p


def plan_apply(a, design, scene_fps, playback_end, root):
    """-> the APPLY plan (pure).  root = {"path", "world": {location, rotation, scale}}."""
    _req(abs(scene_fps - float(a["expected_fps"])) < 1e-9, "FPS|%s" % scene_fps)
    _req(int(playback_end) == int(a["expected_playback_end"]), "PLAYBACK_END|%s" % playback_end)
    start = int(a["anim_start_frame"])
    _req(start + int(a["anim_last_frame"]) >= int(playback_end), "ANIM_SHORTER_THAN_SCENE|%d+%d<%d" % (
        start, a["anim_last_frame"], playback_end))
    _req(int(design["anim"]["last_frame"]) == int(a["anim_last_frame"]), "DESIGN_ANIM_LENGTH|%s" % design["anim"]["last_frame"])
    _req(int(design["anim"]["scene_start"]) == start, "DESIGN_START|%s" % design["anim"]["scene_start"])
    return {"label": LABEL, "tags": list(TAGS), "folder": FOLDER, "mesh": MESH, "materials": dict(SLOT_MI),
            "parent_path": root["path"], "world": root["world"],
            "rel": {"location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            "hidden_in_game": True, "mobility": "MOVABLE",
            "binding": BINDING, "anim": ANIM, "anim_range": [start, int(playback_end)],
            "anim_params": {"start_frame_offset": 0, "end_frame_offset": 0, "first_loop_start_frame_offset": 0,
                            "play_rate": 1.0, "reverse": False},
            "vis_range": [0, int(playback_end)], "vis_keys": [[0, False], [int(a["reveal_frame"]), True]],
            "break_frames_scene": design.get("break_frames_scene")}


def section_rows_problems(got, plan):
    """got = {"skel": [ {range, anim, params} ], "vis": [ {range, keys, property_path} ], "other": [...]}."""
    p = []
    if len(got.get("skel", [])) != 1:
        return ["SKEL_SECTIONS|%d" % len(got.get("skel", []))]
    if len(got.get("vis", [])) != 1:
        return ["VIS_SECTIONS|%d" % len(got.get("vis", []))]
    if got.get("other"):
        p.append("OTHER_TRACKS|%s" % got["other"])
    s = got["skel"][0]
    if list(s["range"]) != list(plan["anim_range"]):
        p.append("SKEL_RANGE|%s" % s["range"])
    if s["anim"] != plan["anim"]:
        p.append("SKEL_ANIM|%s" % s["anim"])
    for k, v in plan["anim_params"].items():
        if s["params"].get(k) != v:
            p.append("SKEL_PARAM|%s=%s want %s" % (k, s["params"].get(k), v))
    v = got["vis"][0]
    if list(v["range"]) != list(plan["vis_range"]):
        p.append("VIS_RANGE|%s" % v["range"])
    if [list(x) for x in v["keys"]] != [list(x) for x in plan["vis_keys"]]:
        p.append("VIS_KEYS|%s" % v["keys"])
    if v.get("property_path") != "bHidden":
        p.append("VIS_PROPERTY|%s" % v.get("property_path"))
    return p


def actor_problems(got, plan):
    """got = actor read-back dict (see _actor_row)."""
    p = []
    for k in ("label", "folder", "mesh", "parent_path", "hidden_in_game", "mobility"):
        if got.get(k) != plan[k]:
            p.append("ACTOR_%s|%s" % (k.upper(), got.get(k)))
    if sorted(got.get("tags") or []) != sorted(plan["tags"]):
        p.append("ACTOR_TAGS|%s" % got.get("tags"))
    if got.get("materials") != plan["materials"]:
        p.append("ACTOR_MATERIALS|%s" % got.get("materials"))
    for k, tol in (("location", TOL_REL), ("rotation", TOL_REL), ("scale", 1e-6)):
        if any(abs(a - b) > tol for a, b in zip(got["rel"][k], plan["rel"][k])):
            p.append("ACTOR_REL_%s|%s" % (k.upper(), got["rel"][k]))
    return p


def snapshot_diff(want, got, prefix):
    """Bit-identical comparison of two JSON-able snapshots (lid binding, twin, root)."""
    if json.dumps(want, sort_keys=True) == json.dumps(got, sort_keys=True):
        return []
    return ["%s_CHANGED" % prefix]


def source_problems(design, build, validation, require_validation_ok):
    p = []
    if design is None:
        return ["NO_DESIGN_JSON"]
    if build is None:
        return ["NO_BUILD_JSON"]
    bad = [k for k, v in (build.get("checks") or {}).items() if not v]
    if bad or not build.get("checks"):
        p.append("BUILD_CHECKS|%s" % bad)
    if require_validation_ok:
        if validation is None:
            p.append("NO_VALIDATION_REPORT")
        elif validation.get("failures"):
            p.append("VALIDATION_FAILED|%s" % validation["failures"][:3])
    if [str(b) for b in build.get("bones", [])] != BONES:
        p.append("BUILD_BONES_DIFFER_FROM_TOOL")
    return p


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as h:
        return json.load(h)


def _write_exclusive(path, rec):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())
    _req(_read_json(path) == json.loads(json.dumps(rec, default=str)), "RECORD_READBACK")


def _rewrite(path, rec):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)


# --------------------------------------------------------------------------------------------- material specs (pure)
# Create-only masters + MIs in the style of ../S3Millstone/s3_props_ue.py material_specs() (that file is NOT edited):
# nodes {key: (kind, value)}, edges (src, out, dst, pin), props (src, out, MP_*), want_props, scalars, vectors.
# SLIME: BLEND_MASKED + a per-pixel dithered coverage (NOT translucent) because (1) a masked surface writes depth, casts
#   and receives shadows, gets Lumen/SSR reflections like the shells and sorts correctly against the TRANSLUCENT 'Fade'
#   pearl twin and the fog; a translucent skeletal strand would not write depth and its sorting against the twin is
#   undefined [inf]; (2) the snap is GEOMETRIC (the two halves are separate skinned tubes, the neck thins by bone
#   scale), so no alpha is needed for the break itself; (3) the coverage dither gives the thin film a see-through read
#   under TSR / MRQ temporal samples (same contract as Pearl_Dither: hard 0/1 step, so coverage == the value for any
#   clip in (0, 1]).  Thicker-looking at grazing angles (Fresnel) like a real mucus film.
# Custom-node reads of Parameters.WorldNormal / CameraVector / SvPosition and View.StateFrameIndex: the same reads
# compiled in M_PearlClam_Pearl_v2 and are used by Pearl_Dither [meas s3_pearl_v2_mat_check_S3PROPS-20261007-192645.json
# named_errors 0; s3_clam_look_mat_check_Pearl_Dither_S3PROPS-20261008-032112.json].
SLIME_COVERAGE_CODE = (
    "float f = pow(1.0 - saturate(dot(normalize(Parameters.WorldNormal), normalize(Parameters.CameraVector))), "
    "max(E, 0.01)); float a = saturate(O + R * f); "
    "float2 p = floor(Parameters.SvPosition.xy) + 5.588238 * (float)(View.StateFrameIndex % 64u); "
    "float d = clamp(frac(52.9829189 * frac(dot(p, float2(0.06711056, 0.00583715)))), 0.001953125, 0.998046875); "
    "return a >= d ? 1.0 : 0.0;")
SLIME_COLOR_CODE = "return lerp(C.rgb, D.rgb, saturate(pow(1.0 - saturate(dot(normalize(Parameters.WorldNormal), " \
                   "normalize(Parameters.CameraVector))), max(E, 0.01))));"
SLIME_SCALARS = {"Roughness": 0.04, "Specular": 0.9, "Opacity": 0.72, "RimOpacity": 0.28, "FresnelExponent": 3.0}
SLIME_VECTORS = {"SlimeColor": [0.50, 0.56, 0.47, 1.0],     # slight green-grey, linear
                 "SlimeRimColor": [0.70, 0.76, 0.68, 1.0]}  # paler at grazing angles (thin film)
LIG_SCALARS = {"Roughness": 0.2, "Specular": 0.6}
LIG_VECTORS = {"LigamentColor": [0.035, 0.022, 0.013, 1.0]}  # dark brown-black, linear
MASK_CLIP = 0.5


def material_specs():
    sn = {k: ("scalar", v) for k, v in SLIME_SCALARS.items()}
    sn.update({k: ("vector", v) for k, v in SLIME_VECTORS.items()})
    sn.update({"SlimeBase": ("custom", (SLIME_COLOR_CODE, ["C", "D", "E"], "F3")),
               "Coverage": ("custom", (SLIME_COVERAGE_CODE, ["O", "R", "E"], "F1"))})
    slime = {"nodes": sn, "shading_model": "MSM_DEFAULT_LIT", "blend_mode": "BLEND_MASKED", "two_sided": False,
             "opacity_mask_clip_value": MASK_CLIP, "used_with_skeletal_mesh": True,
             "edges": [("SlimeColor", "", "SlimeBase", "C"), ("SlimeRimColor", "", "SlimeBase", "D"),
                       ("FresnelExponent", "", "SlimeBase", "E"), ("Opacity", "", "Coverage", "O"),
                       ("RimOpacity", "", "Coverage", "R"), ("FresnelExponent", "", "Coverage", "E")],
             "props": [("SlimeBase", "", "MP_BASE_COLOR"), ("Roughness", "", "MP_ROUGHNESS"),
                       ("Specular", "", "MP_SPECULAR"), ("Coverage", "", "MP_OPACITY_MASK")],
             "want_props": {"MP_BASE_COLOR", "MP_ROUGHNESS", "MP_SPECULAR", "MP_OPACITY_MASK"},
             "scalars": dict(SLIME_SCALARS), "vectors": dict(SLIME_VECTORS)}
    ln = {k: ("scalar", v) for k, v in LIG_SCALARS.items()}
    ln.update({k: ("vector", v) for k, v in LIG_VECTORS.items()})
    lig = {"nodes": ln, "shading_model": "MSM_DEFAULT_LIT", "blend_mode": "BLEND_OPAQUE", "two_sided": False,
           "used_with_skeletal_mesh": True, "edges": [],
           "props": [("LigamentColor", "", "MP_BASE_COLOR"), ("Roughness", "", "MP_ROUGHNESS"),
                     ("Specular", "", "MP_SPECULAR")],
           "want_props": {"MP_BASE_COLOR", "MP_ROUGHNESS", "MP_SPECULAR"},
           "scalars": dict(LIG_SCALARS), "vectors": dict(LIG_VECTORS)}
    return {M_SLIME: slime, M_LIG: lig}


MI_SPECS = {MI_SLIME: {"parent": M_SLIME, "scalars": dict(SLIME_SCALARS), "vectors": dict(SLIME_VECTORS)},
            MI_LIG: {"parent": M_LIG, "scalars": dict(LIG_SCALARS), "vectors": dict(LIG_VECTORS)}}


def spec_problems(s):
    """Graph lint: edges name real nodes, each pin fed once, custom pins fed AND used, no orphan node, each property
    once and exactly want_props, mask <-> MASKED, parameter tables == nodes."""
    p = []
    nodes, edges, props = s["nodes"], s["edges"], s["props"]
    fed = {}
    for src, _o, dst, pin in edges:
        if src not in nodes or dst not in nodes:
            p.append("EDGE_NODE|%s->%s" % (src, dst))
        fed.setdefault((dst, pin), []).append(src)
    p += ["PIN_FED_TWICE|%s" % (k,) for k, v in fed.items() if len(v) != 1]
    for k, (kind, v) in nodes.items():
        if kind == "custom":
            code, ins, _t = v
            for pin in ins:
                if (k, pin) not in fed:
                    p.append("CUSTOM_PIN_UNFED|%s.%s" % (k, pin))
                if not re.search(r"\b%s\b" % re.escape(pin), code):
                    p.append("CUSTOM_PIN_UNUSED|%s.%s" % (k, pin))
    used = {e[0] for e in edges} | {x[0] for x in props}
    p += ["UNUSED_NODE|%s" % k for k in nodes if k not in used]
    mp = [x[2] for x in props]
    if len(set(mp)) != len(mp) or set(mp) != set(s["want_props"]):
        p.append("PROPS|%s" % sorted(mp))
    if ("MP_OPACITY_MASK" in s["want_props"]) != (s["blend_mode"] == "BLEND_MASKED"):
        p.append("MASK_BLEND|%s" % s["blend_mode"])
    if set(s["scalars"]) != {k for k, (kind, _v) in nodes.items() if kind == "scalar"}:
        p.append("SCALAR_TABLE")
    if set(s["vectors"]) != {k for k, (kind, _v) in nodes.items() if kind == "vector"}:
        p.append("VECTOR_TABLE")
    if not s.get("used_with_skeletal_mesh"):
        p.append("NOT_USED_WITH_SKELETAL_MESH")
    if any("CLEAR" in x[2] or "CUSTOM_DATA" in x[2] for x in props):
        p.append("CLEARCOAT_PIN")
    return p


def mi_problems(path, got_scalars, got_vectors, got_parent):
    want = MI_SPECS[path]
    p = []
    if got_parent != want["parent"]:
        p.append("MI_PARENT|%s|%s" % (path, got_parent))
    for k, v in want["scalars"].items():
        g = got_scalars.get(k)
        if g is None or abs(float(g) - v) > 1e-5:
            p.append("MI_SCALAR|%s|%s=%s" % (path, k, g))
    for k, v in want["vectors"].items():
        g = got_vectors.get(k)
        if g is None or any(abs(float(g[i]) - v[i]) > 1e-5 for i in range(3)):
            p.append("MI_VECTOR|%s|%s=%s" % (path, k, g))
    return p


def created_assets():
    return sorted([MESH, SKELETON, ANIM, M_SLIME, MI_SLIME, M_LIG, MI_LIG])


def interchange_wanted(asset_name, step, skeleton=None):
    """Pipeline values, by (sub-object, property).  Pattern of s3_sack_install.interchange_wanted [prec]."""
    common = {("pipeline", "asset_name"): asset_name, ("pipeline", "use_source_name_for_asset"): False,
              ("pipeline", "import_offset_uniform_scale"): 1.0,
              ("common_meshes", "import_lods"): False, ("common_meshes", "import_sockets"): False,
              ("common_skeletal", "use_t0_as_ref_pose"): False,
              ("common_skeletal", "try_auto_select_skeleton"): False,
              ("common_skeletal", "add_curve_metadata_to_skeleton"): False,
              ("mesh", "import_static_meshes"): False, ("mesh", "import_morph_targets"): False,
              ("mesh", "create_physics_asset"): False, ("mesh", "import_vertex_attributes"): False,
              ("material", "import_materials"): False, ("texture", "import_textures"): False}
    if step == "mesh":
        common.update({("common_skeletal", "import_only_animations"): False, ("mesh", "import_skeletal_meshes"): True,
                       ("mesh", "update_skeleton_reference_pose"): False, ("animation", "import_animations"): False})
    else:
        common.update({("common_skeletal", "skeleton"): skeleton, ("common_skeletal", "import_only_animations"): True,
                       ("mesh", "import_skeletal_meshes"): False, ("mesh", "update_skeleton_reference_pose"): False,
                       ("animation", "import_animations"): True})
    return common


def interchange_problems(wanted, got):
    p = []
    for k, v in wanted.items():
        g = got.get(k, "<absent>")
        ok = (g is v) if isinstance(v, bool) else (abs(float(g) - v) < 1e-6 if isinstance(v, float) and
                                                   isinstance(g, (int, float)) and not isinstance(g, bool) else g == v)
        if not ok:
            p.append("PIPELINE|%s.%s=%r want %r" % (k[0], k[1], g, v))
    return p


# =====================================================================================================================
# Unreal side (every UE access inside a function)
# =====================================================================================================================
def _ue():
    import unreal
    return unreal


def _path(o):
    return str(o.get_path_name()) if o is not None else None


def _pkg(o):
    return _path(o).split(".")[0] if o is not None else None


def _en(v):
    return str(getattr(v, "name", v)).split(".")[-1].split(":")[0].strip("<> ").upper()


def _v(x):
    return [float(x.x), float(x.y), float(x.z)]


def _r(rot):
    return [float(rot.roll), float(rot.pitch), float(rot.yaw)]


def _census(ue):
    lib = ue.EditorLoadingAndSavingUtils                        # pattern s3_drama_lights.py:84-89 [prec]
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def _guid(ue, g):
    return str(ue.GuidLibrary.conv_guid_to_string(g))           # [prec] s3_props_ue.py:2787-2788


def _world(ue):
    ed = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
    _req(ed.get_game_world() is None, "PIE_RUNNING")
    w = ed.get_editor_world()
    _req(w is not None and WORLD_NAME in str(w.get_name()), "WRONG_WORLD|%s" % (w.get_name() if w else None))
    return w


def _actors(ue, world, label):
    return [a for a in ue.GameplayStatics.get_all_actors_of_class(world, ue.Actor) if str(a.get_actor_label()) == label]


def _one(ue, world, label):
    rows = _actors(ue, world, label)
    _req(len(rows) == 1, "COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def _by_path(ue, world, path):
    rows = [a for a in ue.GameplayStatics.get_all_actors_of_class(world, ue.Actor) if _path(a) == path]
    return rows[0] if len(rows) == 1 else None


def _world_tf(a):
    return {"location": _v(a.get_actor_location()), "rotation": _r(a.get_actor_rotation()),
            "scale": _v(a.get_actor_scale3d())}


def _rel(a):
    c = a.get_editor_property("root_component")                # [prec] s3_props_ue.py:3860-3862
    return {"location": _v(c.get_editor_property("relative_location")),
            "rotation": _r(c.get_editor_property("relative_rotation")),
            "scale": _v(c.get_editor_property("relative_scale3d"))}


def _read_channel(ue, ch):
    rows = []
    for k in ch.get_keys():
        t = k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)
        row = {"frame": int(t.frame_number.value), "sub": float(getattr(t, "sub_frame", 0.0)), "value": k.get_value()}
        for nm, fn in (("interp", "get_interpolation_mode"), ("tmode", "get_tangent_mode")):
            if hasattr(k, fn):
                row[nm] = _en(getattr(k, fn)())
        rows.append(row)
    rows.sort(key=lambda r: (r["frame"], r["sub"]))
    return {"name": str(ch.get_name()), "keys": rows}


def _binding_snapshot(ue, seq, b):
    """Every track / section / channel key of a binding (used for the 'untouched' proofs)."""
    out = {"name": str(b.get_display_name()), "guid": _guid(ue, b.get_id()), "tracks": []}
    for t in b.get_tracks():
        tr = {"class": t.get_class().get_name(), "sections": []}
        for s in t.get_sections():
            sec = {"range": [s.get_start_frame() if s.has_start_frame() else None,
                             s.get_end_frame() if s.has_end_frame() else None], "channels": {}}
            for ch in s.get_all_channels():
                sec["channels"][channel_base(ch.get_name())] = _read_channel(ue, ch)["keys"]
            tr["sections"].append(sec)
        out["tracks"].append(tr)
    return out


def _lid_binding(ue, seq, world):
    bs = [b for b in seq.get_bindings() if str(b.get_display_name()) == LID_BINDING]
    _req(len(bs) == 1, "LID_BINDING_COUNT|%d" % len(bs))
    objs = list(seq.locate_bound_objects(bs[0], world))                    # [prec] s4_hangar_hold.py:978
    _req(len(objs) == 1 and str(objs[0].get_actor_label()) == LID_LABEL, "LID_BINDING_RESOLVES|%d" % len(objs))
    snap = _binding_snapshot(ue, seq, bs[0])
    xs = [t for t in snap["tracks"] if t["class"] == XFORM_TRACK]
    _req(len(xs) == 1 and len(xs[0]["sections"]) == 1, "LID_TRANSFORM_TRACK")
    roll = xs[0]["sections"][0]["channels"].get(ROLL)
    _req(roll, "LID_ROLL_CHANNEL")
    return snap, roll


def _twin_snapshot(ue, world):
    rows = _actors(ue, world, TWIN_LABEL)
    if not rows:
        return {"present": False}
    _req(len(rows) == 1, "TWIN_COUNT|%d" % len(rows))
    a = rows[0]
    c = a.get_editor_property("root_component")
    mats = []
    for comp in a.get_components_by_class(ue.StaticMeshComponent):
        mats.append([_path(comp.get_material(i)) for i in range(comp.get_num_materials())])
    p = a.get_attach_parent_actor()
    return {"present": True, "path": _path(a), "hidden": bool(a.get_editor_property("hidden")), "rel": _rel(a),
            "parent": _path(p), "materials": mats, "visible": bool(c.is_visible())}


def _root_row(ue, world):
    root = _one(ue, world, ROOT_LABEL)
    rec = _read_json(CLAM_RECORD) or {}
    want = (rec.get("actor_paths") or {}).get("Bottom")
    _req(want is not None and _path(root) == want, "ROOT_NOT_CLAM_APPLY_ROOT|%s|%s" % (_path(root), want))
    return root, {"path": _path(root), "world": _world_tf(root)}


def _gather(ue):
    world = _world(ue)
    _req(ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is None,
         "SEQUENCER_OPEN (run close_sequencer.py first)")                 # [prec] clam_open.py:464-465
    c0 = _census(ue)
    _req(c0 == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % json.dumps(c0))
    seq = ue.load_asset(SCENE)
    _req(seq is not None, "NO_SCENE")
    dr = seq.get_display_rate()
    root, root_row = _root_row(ue, world)
    lid_snap, roll = _lid_binding(ue, seq, world)
    return {"world": world, "seq": seq, "fps": float(dr.numerator) / float(dr.denominator),
            "playback_end": int(seq.get_playback_end()), "root": root, "root_row": root_row,
            "lid_snap": lid_snap, "lid_roll": roll, "twin": _twin_snapshot(ue, world),
            "ours": [_path(a) for a in _actors(ue, world, LABEL)],
            "our_bindings": [_guid(ue, b.get_id()) for b in seq.get_bindings() if str(b.get_display_name()) == BINDING]}


def _anim_lid_rows(ue, anim, frames):
    rows = []
    for f in frames:
        t = ue.AnimationLibrary.get_bone_pose_for_frame(anim, "lid", int(f), False)   # decl AnimationBlueprintLibrary.h:562
        rows.append((int(f), float(t.rotation.rotator().roll), _v(t.translation)))
    return rows


def _sources():
    d, b, v = _read_json(DESIGN_JSON), _read_json(BUILD_JSON), _read_json(VALIDATE_JSON)
    return d, b, v


# --------------------------------------------------------------------------------------------- DRY
def run_dry(ue, a, run):
    g = _gather(ue)
    design, build, val = _sources()
    sp = source_problems(design, build, val, a["require_validation_ok"])
    eal = ue.EditorAssetLibrary
    assets = {p: bool(eal.does_asset_exist(p)) for p in created_assets()}
    imported = all(assets.values())
    lid_p = []
    if imported and design is not None:
        anim = ue.load_asset(ANIM)
        frames = [int(f) for f, _d in design["anim"]["lid_open_deg_every_6th"]]
        lid_p = anim_vs_lid_problems(_anim_lid_rows(ue, anim, frames), g["lid_roll"], design, a["anim_start_frame"])
    plan, plan_err = None, None
    try:
        plan = plan_apply(a, design or {"anim": {}}, g["fps"], g["playback_end"], g["root_row"])
    except (Fail, KeyError, TypeError) as exc:
        plan_err = str(exc)
    rec = os.path.exists(APPLY_RECORD)
    c1 = _census(ue)
    prerequisite = None if imported else {"next_mode": "IMPORT", "confirm": "IMPORT CLAMSLIME",
                                           "reason": "generated slime assets and slime_import_record.json are absent"}
    out = {"run": run, "args": a, "fps": g["fps"], "playback_end": g["playback_end"], "root": g["root_row"],
           "twin": g["twin"], "lid_binding": g["lid_snap"], "assets": assets, "source_problems": sp,
           "anim_vs_live_lid": lid_p, "plan": plan, "plan_error": plan_err, "apply_record_exists": rec,
           "existing_actor": g["ours"], "existing_binding": g["our_bindings"], "census_after": c1,
           "missing_prerequisite": prerequisite,
           "fbx_sha256": {p: sha256_file(p) for p in (FBX_MESH, FBX_ANIM) if os.path.exists(p)}}
    with open(HERE + "slime_dry_%s.json" % run, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str)
    _req(c1 == {"content": [], "maps": []}, "DRY_DIRTIED|%s" % json.dumps(c1))
    ready = imported and not sp and not lid_p and plan is not None and not rec and not g["ours"] and \
        not g["our_bindings"]
    return "CLAMSLIME_DRY_OK|run=%s|apply_ready=%d|imported=%d|next=%s|sources=%s|lid=%s|plan=%s|record=%d|actor=%d|binding=%d" % (
        run, int(ready), int(imported), "APPLY" if ready else ("IMPORT" if not imported else "BLOCKED"),
        "OK" if not sp else sp[:2], "OK" if not lid_p else lid_p[:2], "OK" if plan else plan_err,
        int(rec), len(g["ours"]), len(g["our_bindings"]))


# --------------------------------------------------------------------------------------------- IMPORT
def _pipeline(ue, asset_name, step, skeleton_obj=None):
    p = ue.InterchangeGenericAssetsPipeline()
    subs = {"pipeline": p, "common_meshes": p.get_editor_property("common_meshes_properties"),
            "common_skeletal": p.get_editor_property("common_skeletal_meshes_and_animations_properties"),
            "mesh": p.get_editor_property("mesh_pipeline"), "animation": p.get_editor_property("animation_pipeline"),
            "material": p.get_editor_property("material_pipeline")}
    subs["texture"] = subs["material"].get_editor_property("texture_pipeline") if subs["material"] else None
    _req(all(v is not None for v in subs.values()), "PIPELINE_SUBOBJECTS")
    wanted = interchange_wanted(asset_name, step, SKELETON if step == "anim" else None)
    for (sub, prop), v in wanted.items():
        subs[sub].set_editor_property(prop, skeleton_obj if prop == "skeleton" else v)
    got = {}
    for (sub, prop) in wanted:
        gv = subs[sub].get_editor_property(prop)
        if prop == "skeleton":                       # soft pointer: object or path wrapper [inf, as the sack tool]
            text = _path(gv) if gv is not None and hasattr(gv, "get_path_name") else (str(gv) if gv else "")
            gv = SKELETON if text and (text == SKELETON or SKELETON + "." in text) else (text or None)
        got[(sub, prop)] = gv
    pr = interchange_problems(wanted, got)
    _req(not pr, "PIPELINE_READBACK|%s" % pr)
    ov = ue.InterchangePipelineStackOverride()
    ov.add_pipeline(p)
    return ov, {"%s.%s" % k: v for k, v in got.items()}


def _import(ue, fbx, name, step, skeleton_obj=None):
    ov, settings = _pipeline(ue, name, step, skeleton_obj)
    task = ue.AssetImportTask()
    for k, v in (("filename", fbx), ("destination_path", ASSET_DIR), ("destination_name", name), ("automated", True),
                 ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    task.set_editor_property("options", ov)
    ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return settings, [str(x) for x in (task.get_editor_property("imported_object_paths") or [])]


def _list_assets(ue, folder):
    eal = ue.EditorAssetLibrary
    if not eal.does_directory_exist(folder):
        return []
    return sorted(str(x).split(".", 1)[0] for x in eal.list_assets(folder, recursive=True, include_folder=False))


def _bone_tree(ue, mesh):
    sub = ue.SkeletalMeshEditorSubsystem                       # [prec] s3_sack_install.py:917-948
    tree, stack = {"root": None}, ["root"]
    parent = sub.get_bone_parent(mesh, "root")
    if parent is not None and str(parent) not in ("None", ""):
        tree["root"] = str(parent)
        tree[str(parent)] = None
    while stack:
        b = stack.pop()
        for k in sub.get_bone_children(mesh, b):
            k = str(k)
            _req(k not in tree, "BONE_CYCLE|%s" % k)
            tree[k] = b
            stack.append(k)
    return tree


def _mesh_slots(mesh):
    return [(str(m.get_editor_property("material_slot_name")), _pkg(m.get_editor_property("material_interface")))
            for m in (mesh.get_editor_property("materials") or [])]


def _mesh_readback(ue, mesh, design):
    b = mesh.get_imported_bounds()
    o, e = b.get_editor_property("origin"), b.get_editor_property("box_extent")
    rb = {"path": _pkg(mesh), "skeleton": _pkg(mesh.get_editor_property("skeleton")),
          "physics_asset": _pkg(mesh.get_editor_property("physics_asset")), "slots": _mesh_slots(mesh),
          "bounds_origin": _v(o), "bounds_extent": _v(e), "tree": _bone_tree(ue, mesh),
          "render_vertices": int(ue.get_editor_subsystem(ue.SkeletalMeshEditorSubsystem).get_num_verts(mesh, 0))}
    p = bone_tree_problems(rb["tree"]) + bounds_problems(rb["bounds_origin"], rb["bounds_extent"], design)
    if rb["skeleton"] != SKELETON:
        p.append("SKELETON|%s" % rb["skeleton"])
    if rb["physics_asset"] is not None:
        p.append("PHYSICS_ASSET|%s" % rb["physics_asset"])
    if [s for s, _m in rb["slots"]] != [SLOT_LIGAMENT, SLOT_SLIME]:
        p.append("SLOT_NAMES|%s" % rb["slots"])
    if not design["vertices"] <= rb["render_vertices"] <= 4 * design["vertices"]:
        p.append("RENDER_VERTS|%d vs %d" % (rb["render_vertices"], design["vertices"]))
    return rb, p


def _anim_readback(ue, anim, design):
    rb = {"path": _pkg(anim), "skeleton": _pkg(anim.get_editor_property("skeleton")),
          "length_s": float(anim.get_play_length()),                      # [prec] klara_preroll_s1.py:695
          "frames": int(ue.AnimationLibrary.get_num_frames(anim))}       # decl AnimationBlueprintLibrary.h:73
    want_len = design["anim"]["last_frame"] / float(design["anim"]["fps"])
    p = []
    if rb["skeleton"] != SKELETON:
        p.append("ANIM_SKELETON|%s" % rb["skeleton"])
    if abs(rb["length_s"] - want_len) > 0.5 / design["anim"]["fps"]:
        p.append("ANIM_LENGTH|%s want %s" % (rb["length_s"], want_len))
    if rb["frames"] not in (design["anim"]["last_frame"], design["anim"]["last_frame"] + 1):   # keys vs frames [inf]
        p.append("ANIM_FRAMES|%s" % rb["frames"])
    frames = [int(f) for f, _d in design["anim"]["lid_open_deg_every_6th"]]
    rows = _anim_lid_rows(ue, anim, frames)
    rb["lid_rows"] = rows
    p += lid_curve_problems(rows, design_want(design))
    return rb, p


def _build_material(ue, path, spec):
    eal, mel = ue.EditorAssetLibrary, ue.MaterialEditingLibrary
    _req(not eal.does_asset_exist(path), "MASTER_EXISTS|" + path)
    name = path.rsplit("/", 1)[1]
    mat = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, ASSET_DIR, ue.Material, ue.MaterialFactoryNew())
    _req(mat is not None, "MASTER_CREATE|" + path)
    mat.modify()
    flags = {"blend_mode": getattr(ue.BlendMode, spec["blend_mode"]),
             "shading_model": getattr(ue.MaterialShadingModel, spec["shading_model"]),
             "two_sided": spec["two_sided"], "used_with_skeletal_mesh": True}
    if spec["blend_mode"] == "BLEND_MASKED":
        flags["opacity_mask_clip_value"] = spec["opacity_mask_clip_value"]
    for k, v in flags.items():
        mat.set_editor_property(k, v)
    made, y = {}, 0
    for key, (kind, v) in spec["nodes"].items():
        y += 160
        if kind == "scalar":
            n = mel.create_material_expression(mat, ue.MaterialExpressionScalarParameter, -900, y)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("default_value", float(v))
        elif kind == "vector":
            n = mel.create_material_expression(mat, ue.MaterialExpressionVectorParameter, -900, y)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("default_value", ue.LinearColor(v[0], v[1], v[2], v[3]))
        else:
            code, ins, ot = v
            n = mel.create_material_expression(mat, ue.MaterialExpressionCustom, -400, y)
            n.set_editor_property("code", code)
            n.set_editor_property("description", key)
            n.set_editor_property("output_type", getattr(ue.CustomMaterialOutputType, "CMOT_FLOAT%s" % ot[1]))
            pins = []
            for nm in ins:
                ci = ue.CustomInput()
                ci.set_editor_property("input_name", nm)
                pins.append(ci)
            n.set_editor_property("inputs", pins)
            got = [str(c.get_editor_property("input_name")) for c in n.get_editor_property("inputs")]
            _req(got == list(ins), "CUSTOM_INPUTS|%s|%s" % (key, got))
        _req(n is not None, "NODE|%s" % key)
        made[key] = n
    for src, out, dst, pin in spec["edges"]:
        _req(mel.connect_material_expressions(made[src], out, made[dst], pin), "EDGE|%s->%s.%s" % (src, dst, pin))
    for src, out, prop in spec["props"]:
        _req(mel.connect_material_property(made[src], out, getattr(ue.MaterialProperty, prop)), "PROP|%s" % prop)
    for prop in spec["want_props"]:                                # read back each wired property
        node = mel.get_material_property_input_node(mat, getattr(ue.MaterialProperty, prop))
        _req(node is not None, "PROP_READBACK|%s" % prop)
    mel.recompile_material(mat)
    for k, v in flags.items():
        g = mat.get_editor_property(k)
        ok = (_en(g) == _en(v)) if k in ("blend_mode", "shading_model") else (abs(float(g) - float(v)) < 1e-6
                                                                               if isinstance(v, float) else bool(g) == bool(v))
        _req(ok, "FLAG_READBACK|%s|%s=%s" % (path, k, g))
    return mat


def _make_mi(ue, path, parent):
    eal, mel = ue.EditorAssetLibrary, ue.MaterialEditingLibrary
    _req(not eal.does_asset_exist(path), "MI_EXISTS|" + path)
    mi = ue.AssetToolsHelpers.get_asset_tools().create_asset(path.rsplit("/", 1)[1], ASSET_DIR,
                                                             ue.MaterialInstanceConstant,
                                                             ue.MaterialInstanceConstantFactoryNew())
    _req(mi is not None, "MI_CREATE|" + path)
    mi.modify()
    mel.set_material_instance_parent(mi, parent)
    spec = MI_SPECS[path]
    for k, v in spec["scalars"].items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))      # bool return unreliable: read back
    for k, v in spec["vectors"].items():
        mel.set_material_instance_vector_parameter_value(mi, k, ue.LinearColor(v[0], v[1], v[2], v[3]))
    mel.update_material_instance(mi)
    return mi


def _mi_readback(ue, path):
    mel = ue.MaterialEditingLibrary
    mi = ue.load_asset(path)
    sc = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in MI_SPECS[path]["scalars"]}
    vc = {}
    for k in MI_SPECS[path]["vectors"]:
        c = mel.get_material_instance_vector_parameter_value(mi, k)
        vc[k] = [float(c.r), float(c.g), float(c.b), float(c.a)]
    return mi_problems(path, sc, vc, _pkg(mi.get_editor_property("parent")))


def _set_slots(ue, mesh):
    mats = list(mesh.get_editor_property("materials") or [])
    mesh.modify()
    for m in mats:
        slot = str(m.get_editor_property("material_slot_name"))
        _req(slot in SLOT_MI, "SLOT_UNKNOWN|%s" % slot)
        m.set_editor_property("material_interface", ue.load_asset(SLOT_MI[slot]))
    mesh.set_editor_property("materials", mats)
    got = dict(_mesh_slots(mesh))
    _req(got == SLOT_MI, "MATERIAL_SLOTS|%s" % got)


def run_import(ue, a, run):
    _world(ue)
    eal = ue.EditorAssetLibrary
    _req(not os.path.exists(IMPORT_RECORD), "IMPORT_RECORD_EXISTS")
    taken = [p for p in created_assets() if eal.does_asset_exist(p)]
    _req(not taken, "TARGETS_EXIST|%s" % taken)
    c0 = _census(ue)
    _req(c0 == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % json.dumps(c0))
    design, build, val = _sources()
    sp = source_problems(design, build, val, a["require_validation_ok"])
    _req(not sp, "SOURCES|%s" % sp)
    lint = {p: spec_problems(s) for p, s in material_specs().items()}
    _req(not any(lint.values()), "MATERIAL_SPEC|%s" % lint)
    rec = {"schema": 1, "tool": "slime_apply_ue", "run": run, "state": "importing", "created": [],
           "fbx_sha256": {FBX_MESH: sha256_file(FBX_MESH), FBX_ANIM: sha256_file(FBX_ANIM)}}
    _write_exclusive(IMPORT_RECORD, rec)
    before = _list_assets(ue, ASSET_DIR)
    settings_m, objs_m = _import(ue, FBX_MESH, "SK_PearlClam_Slime", "mesh")
    mesh = ue.load_asset(MESH)
    _req(isinstance(mesh, ue.SkeletalMesh), "MESH_IMPORT|%s|%s" % (objs_m, NS))
    new = sorted(set(_list_assets(ue, ASSET_DIR)) - set(before))
    _req(new == sorted([MESH, SKELETON]), "STRAY_AFTER_MESH|%s|%s" % (new, NS))
    skel = ue.load_asset(SKELETON)
    settings_a, objs_a = _import(ue, FBX_ANIM, "A_PearlClam_SlimeOpen", "anim", skel)
    new = sorted(set(_list_assets(ue, ASSET_DIR)) - set(before))
    extra = sorted(set(new) - {MESH, SKELETON})
    _req(len(extra) == 1, "ANIM_IMPORT|%s|%s|%s" % (extra, objs_a, NS))
    if extra[0] != ANIM:                                    # Interchange may name it after the take [inf]
        _req(eal.rename_asset(extra[0], ANIM), "ANIM_RENAME|%s|%s" % (extra[0], NS))
    anim = ue.load_asset(ANIM)
    _req(anim is not None, "ANIM_LOAD|%s" % NS)
    for p, s in material_specs().items():
        _build_material(ue, p, s)
    for p, spec in MI_SPECS.items():
        _make_mi(ue, p, ue.load_asset(spec["parent"]))
    _set_slots(ue, mesh)
    mrb, mp = _mesh_readback(ue, mesh, design)
    arb, ap = _anim_readback(ue, anim, design)
    mip = _mi_readback(ue, MI_SLIME) + _mi_readback(ue, MI_LIG)
    _req(not (mp + ap + mip), "IMPORT_GATES|%s|%s" % ((mp + ap + mip)[:6], NS))
    new = sorted(set(_list_assets(ue, ASSET_DIR)) - set(before))
    _req(new == created_assets(), "STRAY_ASSETS|%s|%s" % (new, NS))
    c1 = _census(ue)
    _req(c1["maps"] == [] and set(c1["content"]) <= set(created_assets()) | {ASSET_DIR},
         "DIRTY_SCOPE|%s|%s" % (json.dumps(c1), NS))
    for p in created_assets():
        _req(eal.save_asset(p, only_if_is_dirty=False), "SAVE|%s" % p)
    c2 = _census(ue)
    _req(c2 == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % json.dumps(c2))
    mrb2, mp2 = _mesh_readback(ue, ue.load_asset(MESH), design)
    arb2, ap2 = _anim_readback(ue, ue.load_asset(ANIM), design)
    _req(not (mp2 + ap2), "IMPORT_GATES_AFTER_SAVE|%s" % (mp2 + ap2)[:6])
    rec.update({"state": "saved", "created": created_assets(), "mesh": mrb2, "anim": arb2,
                "pipeline": {"mesh": settings_m, "anim": settings_a}, "saved_at": datetime.datetime.now().isoformat()})
    _rewrite(IMPORT_RECORD, rec)
    ue.SystemLibrary.collect_garbage()
    return "CLAMSLIME_IMPORT_OK|run=%s|assets=%d|bones=%d|verts=%d|anim_s=%.3f|lid_curve=OK|saved=%d" % (
        run, len(created_assets()), len(mrb2["tree"]), mrb2["render_vertices"], arb2["length_s"], len(created_assets()))


# --------------------------------------------------------------------------------------------- APPLY
def _actor_row(ue, a):
    c = a.get_editor_property("skeletal_mesh_component")       # [prec] s3_sack_install.py:1476 (SkeletalMeshActor.h:38-39)
    p = a.get_attach_parent_actor()
    mats = {}
    mesh = c.get_skeletal_mesh_asset()
    for slot, _m in _mesh_slots(mesh) if mesh is not None else []:
        idx = c.get_material_index(slot)
        mats[slot] = _pkg(c.get_material(idx))
    return {"path": _path(a), "label": str(a.get_actor_label()), "folder": str(a.get_folder_path()),
            "tags": [str(t) for t in a.get_editor_property("tags")], "mesh": _pkg(mesh),
            "parent_path": _path(p), "hidden_in_game": bool(a.get_editor_property("hidden")),
            "mobility": _en(c.get_editor_property("mobility")), "rel": _rel(a), "materials": mats}


def _spawn(ue, plan, root):
    eas = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    w = plan["world"]
    a = eas.spawn_actor_from_class(ue.SkeletalMeshActor, ue.Vector(*w["location"]),
                                   ue.Rotator(roll=w["rotation"][0], pitch=w["rotation"][1], yaw=w["rotation"][2]),
                                   False)                     # pattern s3_props_ue.py:2968-2988 [prec]
    _req(a is not None, "SPAWN_FAILED")
    a.set_actor_label(plan["label"])
    c = a.get_editor_property("skeletal_mesh_component")
    c.set_mobility(getattr(ue.ComponentMobility, plan["mobility"]))
    mesh = ue.load_asset(plan["mesh"])
    _req(isinstance(mesh, ue.SkeletalMesh), "MESH_LOAD")
    try:
        c.set_editor_property("skeletal_mesh_asset", mesh)    # [prec] s3_sack_install.py:1622-1624
    except Exception:  # noqa: BLE001
        c.set_skeletal_mesh_asset(mesh)
    a.set_editor_property("tags", [ue.Name(t) for t in plan["tags"]])
    a.set_folder_path(plan["folder"])
    a.set_actor_hidden_in_game(bool(plan["hidden_in_game"]))
    rule = ue.AttachmentRule.KEEP_WORLD
    a.attach_to_actor(root, "", rule, rule, rule, False)       # [prec] s3_props_ue.py:3999-4000 (return not trusted)
    return a


def _add_binding(ue, seq, actor, plan, anim):
    b = seq.add_possessable(actor)                             # [prec] s4_hangar_hold.py:1098
    _req(b is not None and b.is_valid(), "ADD_POSSESSABLE")
    b.set_display_name(plan["binding"])
    t = b.add_track(ue.MovieSceneSkeletalAnimationTrack)       # [inf] (s3_crowd_structure.py:589, not proven run)
    _req(t is not None, "ADD_SKEL_TRACK")
    s = t.add_section()
    _req(s is not None, "ADD_SKEL_SECTION")
    s.set_range(int(plan["anim_range"][0]), int(plan["anim_range"][1]))   # display frames [prec s4_hangar_hold.py:516]
    p = s.get_editor_property("params")                        # decl MovieSceneSkeletalAnimationSection.h:119-120
    p.set_editor_property("animation", anim)                   # decl :50-51
    for k in ("start_frame_offset", "end_frame_offset", "first_loop_start_frame_offset"):
        p.set_editor_property(k, ue.FrameNumber(int(plan["anim_params"][k])))   # decl :54-63
    s.set_editor_property("params", p)
    vt = b.add_track(ue.MovieSceneVisibilityTrack)
    _req(vt is not None, "ADD_VIS_TRACK")
    if str(vt.get_property_name()) in ("None", ""):            # [prec] klara_reveal.py:3131-3135
        vt.set_property_name_and_path("bHidden", "bHidden")   # 8 Oct: bHiddenInGame tracks are INERT (UMovieSceneVisibilityTrack binds AActor::bHidden, VISIBLE semantics: Conductor 5, PIES2VIS-185717; KlaraIngest/vis_fix.py)
    vs = vt.add_section()
    vs.set_range(int(plan["vis_range"][0]), int(plan["vis_range"][1]))
    ch = list(vs.get_all_channels())
    _req(len(ch) == 1, "VIS_CHANNELS|%d" % len(ch))
    for f, v in plan["vis_keys"]:
        ch[0].add_key(ue.FrameNumber(int(f)), bool(v), time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE)   # [prec] _add_reveal
    return b


def _fixed_rate(p):
    try:
        return float(p.get_editor_property("play_rate").to_fixed_play_rate())   # [prec read] klara_preroll_s1.py:684
    except Exception:  # noqa: BLE001
        return None


def _reverse(p):
    for nm in ("reverse", "b_reverse"):
        try:
            return bool(p.get_editor_property(nm))
        except Exception:  # noqa: BLE001
            continue
    return None


def _our_sections(ue, b):
    out = {"skel": [], "vis": [], "other": []}
    for t in b.get_tracks():
        cls = t.get_class().get_name()
        for s in t.get_sections():
            rng = [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None]
            if cls == SKEL_TRACK:
                p = s.get_editor_property("params")
                out["skel"].append({"range": rng, "anim": _pkg(p.get_editor_property("animation")),
                                    "params": {"start_frame_offset": int(p.get_editor_property("start_frame_offset").value),
                                               "end_frame_offset": int(p.get_editor_property("end_frame_offset").value),
                                               "first_loop_start_frame_offset":
                                                   int(p.get_editor_property("first_loop_start_frame_offset").value),
                                               "play_rate": _fixed_rate(p), "reverse": _reverse(p)}})
            elif cls == VIS_TRACK:
                ch = list(s.get_all_channels())
                keys = [[int(k.get_time(time_unit=ue.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value),
                         bool(k.get_value())] for k in ch[0].get_keys()] if len(ch) == 1 else None
                out["vis"].append({"range": rng, "keys": keys, "property_path": str(t.get_property_path())})
            else:
                out["other"].append(cls)
    return out


def _our_binding(ue, seq, world, guid, actor_path):
    rows = [b for b in seq.get_bindings() if _guid(ue, b.get_id()) == guid]
    _req(len(rows) == 1, "BINDING_COUNT|%d" % len(rows))
    got = [_path(o) for o in seq.locate_bound_objects(rows[0], world)]
    _req(got == [actor_path], "BINDING_RESOLVES|%s" % got)
    return rows[0]


def _backup(run):
    d = BACKUP_ROOT + run
    os.makedirs(d)
    out = {}
    for src in (UMAP, SCENE_FILE):
        dst = os.path.join(d, os.path.basename(src))
        shutil.copy2(src, dst)
        h = sha256_file(src)
        _req(sha256_file(dst) == h, "BACKUP_HASH|%s" % dst)
        out[src] = h
    return d, out


def _save_scene_and_map(ue, world):
    c = _census(ue)
    _req(c == {"content": [SCENE], "maps": [WORLD]}, "CENSUS|%s|%s" % (json.dumps(c), NS))
    _req(not [a for a in ue.GameplayStatics.get_all_actors_of_class(world, ue.Actor)
              if str(a.get_actor_label()).startswith("ZZ_")], "ZZ_ACTORS_PRESENT|%s" % NS)
    _req(ue.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False), "SAVE_SCENE")
    _req(ue.EditorLoadingAndSavingUtils.save_map(world, WORLD), "SAVE_MAP")   # [prec] s3_props_ue.py:3033-3041
    c2 = _census(ue)
    _req(c2 == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % json.dumps(c2))


def _verify_applied(ue, g, rec, plan):
    world, seq = g["world"], g["seq"]
    a = _by_path(ue, world, rec["actor_path"])
    _req(a is not None, "ACTOR_MISSING")
    ap = actor_problems(_actor_row(ue, a), plan)
    b = _our_binding(ue, seq, world, rec["binding_guid"], rec["actor_path"])
    sp = section_rows_problems(_our_sections(ue, b), plan)
    anim = ue.load_asset(plan["anim"])
    design = _read_json(DESIGN_JSON)
    frames = [int(f) for f, _d in design["anim"]["lid_open_deg_every_6th"]]
    lp = anim_vs_lid_problems(_anim_lid_rows(ue, anim, frames), g["lid_roll"], design, plan["anim_range"][0])
    up = snapshot_diff(rec["lid_binding"], g["lid_snap"], "LID_BINDING") + \
        snapshot_diff(rec["twin"], g["twin"], "TWIN") + snapshot_diff(rec["root"], g["root_row"], "ROOT")
    return ap + sp + lp + up


def run_apply(ue, a, run):
    _req(not os.path.exists(APPLY_RECORD), "RECORD_EXISTS (REVERT first)")
    ir = _read_json(IMPORT_RECORD)
    _req(ir is not None and ir.get("state") == "saved", "NOT_IMPORTED")
    g = _gather(ue)
    _req(not g["ours"], "ACTOR_EXISTS|%s" % g["ours"])
    _req(not g["our_bindings"], "BINDING_EXISTS|%s" % g["our_bindings"])
    design, build, val = _sources()
    sp = source_problems(design, build, val, a["require_validation_ok"])
    _req(not sp, "SOURCES|%s" % sp)
    plan = plan_apply(a, design, g["fps"], g["playback_end"], g["root_row"])
    anim = ue.load_asset(ANIM)
    _req(anim is not None and isinstance(ue.load_asset(MESH), ue.SkeletalMesh), "ASSETS_MISSING")
    frames = [int(f) for f, _d in design["anim"]["lid_open_deg_every_6th"]]
    lp = anim_vs_lid_problems(_anim_lid_rows(ue, anim, frames), g["lid_roll"], design, plan["anim_range"][0])
    _req(not lp, "ANIM_VS_LID|%s" % lp[:4])
    _req(not os.path.exists(BACKUP_ROOT + run), "BACKUP_EXISTS|%s (use a fresh run id)" % (BACKUP_ROOT + run))
    rec = {"schema": 1, "tool": "slime_apply_ue", "run": run, "state": "applying", "args": a, "plan": plan,
           "root": g["root_row"], "twin": g["twin"], "lid_binding": g["lid_snap"], "actor_path": None,
           "binding_guid": None, "written": datetime.datetime.now().isoformat()}
    _write_exclusive(APPLY_RECORD, rec)                        # RECORD FIRST
    folder, hashes = _backup(run)
    rec.update({"backup": folder, "backup_sha256": hashes})
    _rewrite(APPLY_RECORD, rec)
    actor = _spawn(ue, plan, g["root"])
    rec["actor_path"] = _path(actor)
    _rewrite(APPLY_RECORD, rec)
    g["seq"].modify()
    b = _add_binding(ue, g["seq"], actor, plan, anim)
    rec["binding_guid"] = _guid(ue, b.get_id())
    rec["state"] = "written"
    _rewrite(APPLY_RECORD, rec)
    g2 = dict(g, lid_snap=_lid_binding(ue, g["seq"], g["world"])[0], twin=_twin_snapshot(ue, g["world"]),
              root_row=_root_row(ue, g["world"])[1])
    probs = _verify_applied(ue, g2, rec, plan)
    _req(not probs, "READBACK|%s|%s" % (probs[:6], NS))
    _save_scene_and_map(ue, g["world"])
    rec["state"] = "saved"
    _rewrite(APPLY_RECORD, rec)
    g3 = dict(g, seq=ue.load_asset(SCENE))
    g3.update(lid_snap=_lid_binding(ue, g3["seq"], g["world"])[0], twin=_twin_snapshot(ue, g["world"]),
              root_row=_root_row(ue, g["world"])[1])
    probs = _verify_applied(ue, g3, rec, plan)
    _req(not probs, "POST_SAVE_READBACK|%s (saved; REVERT CLAMSLIME available)" % probs[:6])
    rec.update({"state": "applied", "applied_at": datetime.datetime.now().isoformat(),
                "saved_sha256": {UMAP: sha256_file(UMAP), SCENE_FILE: sha256_file(SCENE_FILE)}})
    _rewrite(APPLY_RECORD, rec)
    return "CLAMSLIME_APPLY_OK|run=%s|actor=%s|binding=%s|anim=[%d,%d)|reveal=%d|breaks_scene=%s|saved=map+scene" % (
        run, rec["actor_path"], rec["binding_guid"], plan["anim_range"][0], plan["anim_range"][1],
        plan["vis_keys"][1][0], plan["break_frames_scene"])


# --------------------------------------------------------------------------------------------- REVERT
def run_revert(ue, a, run):
    rec = _read_json(APPLY_RECORD)
    _req(rec is not None, "NO_RECORD")
    _req(rec.get("state") in ("applied", "saved"), "RECORD_STATE|%s (partial APPLY: restore %s with the editor closed)" % (
        rec.get("state"), rec.get("backup")))
    g = _gather(ue)
    plan = rec["plan"]
    _req(g["ours"] == [rec["actor_path"]], "ACTOR_DRIFT|%s" % g["ours"])
    _req(g["our_bindings"] == [rec["binding_guid"]], "BINDING_DRIFT|%s" % g["our_bindings"])
    drift = _verify_applied(ue, g, rec, plan)
    _req(not drift, "DRIFT|%s" % drift[:6])
    world, seq = g["world"], g["seq"]
    b = _our_binding(ue, seq, world, rec["binding_guid"], rec["actor_path"])
    seq.modify()
    b.remove()                                                 # returns None even on success: re-list [prec]
    _req(not [x for x in seq.get_bindings() if _guid(ue, x.get_id()) == rec["binding_guid"]], "BINDING_SURVIVED|%s" % NS)
    actor = _by_path(ue, world, rec["actor_path"])
    _req(ue.get_editor_subsystem(ue.EditorActorSubsystem).destroy_actor(actor), "DESTROY|%s" % NS)  # [prec] :3125
    _req(_by_path(ue, world, rec["actor_path"]) is None, "DESTROY_SURVIVED|%s" % NS)
    _save_scene_and_map(ue, world)
    seq2 = ue.load_asset(SCENE)
    _req(not [x for x in seq2.get_bindings() if str(x.get_display_name()) == BINDING], "POST_SAVE_BINDING")
    _req(not _actors(ue, world, LABEL), "POST_SAVE_ACTOR")
    un = snapshot_diff(rec["lid_binding"], _lid_binding(ue, seq2, world)[0], "LID_BINDING") + \
        snapshot_diff(rec["twin"], _twin_snapshot(ue, world), "TWIN")
    _req(not un, "POST_SAVE_UNTOUCHED|%s" % un)
    os.replace(APPLY_RECORD, APPLY_RECORD + ".reverted-" + run)
    return "CLAMSLIME_REVERT_OK|run=%s|removed_binding=%s|destroyed=%s|saved=map+scene|assets_kept=%d" % (
        run, rec["binding_guid"], rec["actor_path"], len(created_assets()))


def main(args_path=None):
    """-> the marker (also logged).  Never raises."""
    ue = None
    try:
        ue = _ue()
        with open(args_path or ARGS_FILE, encoding="utf-8") as h:
            a = merged_args(json.load(h))
        RUN["run"] = str(a.get("run") or fresh_run())
        errs = validate_args(a)
        _req(not errs, "ARGS|%s" % errs)
        fn = {"DRY": run_dry, "IMPORT": run_import, "APPLY": run_apply, "REVERT": run_revert}[a["mode"]]
        marker = fn(ue, a, RUN["run"])
        ue.log(marker)
        return marker
    except Exception as exc:  # noqa: BLE001
        marker = "CLAMSLIME_FAILED|run=%s|%s" % (RUN["run"], exc if isinstance(exc, Fail) else repr(exc))
        try:
            (ue or _ue()).log_error(marker)
        except Exception:  # noqa: BLE001
            print(marker)
        return marker


if __name__ != "slime_apply_offline":
    main()
