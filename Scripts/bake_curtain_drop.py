"""Bake a dropped stage curtain with Blender cloth and MEASURE the settled pile (headless Blender 4.4).

    set CURTAIN_FULLNESS=2.0 & set DROP_ID=f20 & "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b --factory-startup --python Scripts/bake_curtain_drop.py

Why (28 Sep): Gary wants "heavy and physical", a WIDE pile, not "virtual silk falling into a thin
slice". Chaos cannot guide the fall (moving the component carries the cloth rigidly; see
Docs/ChaosClothCurtain.md) and he has approved baking the fall in Blender, which simulates in world space.

The curtain is built by the SAME pattern code as the Chaos curtain (Scripts/build_curtain_chaos_pattern.py,
imported, so fullness, pleats and resolution come from the same env vars): a flat pattern FULLNESS x the
17.77 m track, gathered into sine pleats, hanging 10 m from a pinned heading over a floor plane at z = 0.
At RELEASE_FRAME the heading pin is released (an animated Vertex Weight Mix above the Cloth modifier sets the
pin weights to 0), and the curtain falls under gravity alone.

THE METRIC (defined before any run; read from the settled mesh in metres, not from pixels):
  depth_m     front-to-back extent (y, P5-P95) of the fabric lying below 0.5 m: the pile's depth
  width_m     along-track extent (x, P5-P95) of the same
  height_m    P95 of z over the whole cloth after settling: how high the heap stands
  hang_depth_m  the same y P5-P95 of the hanging curtain at frame 1 (0.29 m-ish at fullness 1.25)
  depth_ratio   depth_m / hang_depth_m: a slab stays near 1, a heap is several times that
Also written: the heading's z after release (proves the release worked), per-frame solve time, and
Workbench renders (3/4 and side) of the settled frame, validated by eye against the numbers.

Env: CURTAIN_FULLNESS, CURTAIN_QUADS_PER_BOLT (5 = 27 cm scout, 9 = 15 cm), DROP_ID, BEND, SELF_DIST_M,
FLOOR_FRICTION, SELF_FRICTION, AIR_DAMPING, RELEASE_FRAME, FRAMES, QUALITY, OUT_DIR, EXPORT_ABC (1 to write Alembic).
Outputs: <OUT_DIR>/<DROP_ID>.json, <DROP_ID>_34.png, <DROP_ID>_side.png (+ .abc when asked).
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(os.environ.get("PUSS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
os.environ.setdefault("CURTAIN_RAGGED", "0")
os.environ.setdefault("CURTAIN_QUADS_PER_BOLT", "5")
DROP_ID = os.environ.get("DROP_ID", "scout")
BEND = float(os.environ.get("BEND", "5.0"))
SELF_DIST = float(os.environ.get("SELF_DIST_M", "0.01"))
# Self-collision distance vs edge length: a WARNING, not a rule (28 Sep). Keeping the self-collision distance well
# under the edge length is ordinary cloth-sim practice, but THIS PROJECT HAS NO EVIDENCE FOR IT AS A HARD LIMIT.
# It was briefly a hard refusal on the hypothesis that 3 cm shells on 9.1 cm edges (ratio 0.33) turned the pile
# into a pressurised foam that caused the landing "bounce". That hypothesis was REFUTED (bt0 at 0.33 vs bta at
# 0.16: the same swell, COM rise 0.106 vs 0.096 m). The real cause was solver under-stepping (fixed by QUALITY 20
# / COLLISION_QUALITY 8). The take Gary APPROVED uses ratio 0.33 and looks right. So: noticed, reported, never blocked.
SELF_DIST_MAX_RATIO = 0.2
COLLISION_QUALITY = int(os.environ.get("COLLISION_QUALITY", "4"))
# Collision impulse clamps (Blender default 0 = unlimited). A candidate for the post-collapse swell: unbounded
# push-out impulses inside the compressed pile (28 Sep). 0 keeps Blender's default.
SELF_IMPULSE_CLAMP = float(os.environ.get("SELF_IMPULSE_CLAMP", "0"))
IMPULSE_CLAMP = float(os.environ.get("IMPULSE_CLAMP", "0"))
FLOOR_FRICTION = float(os.environ.get("FLOOR_FRICTION", "10.0"))
SELF_FRICTION = float(os.environ.get("SELF_FRICTION", "10.0"))
AIR_DAMPING = float(os.environ.get("AIR_DAMPING", "1.0"))
RELEASE_FRAME = int(os.environ.get("RELEASE_FRAME", "10"))
# ADAPTIVE RELEASE (30 Sep). RELEASE_AUTO="min:max:limit_mm:window", e.g. "300:600:1.5:30". The hang SURGES (final9:
# 2.0-2.9 mm/frame for 10-20 frames between quiet spells of 0.4-0.6) and the show freezes sample R-1, so the release is
# placed where the cloth is genuinely still: at the first frame f >= min-1 whose last `window` per-frame moves were ALL
# under limit_mm, the release keys (pin stiffness, the rest switch, any bend-damping change) are MOVED from max to
# R = f + 1, and the export window, the at-rest window and the clip follow R. No quiet window by max: release at max.
# FRAMES is then R + (FRAMES - max), so the fall and pile keep their length. PROVEN on a coarse strip (30 Sep, 2 threads):
# keys moved mid-bake give a bit-identical result to keys placed there from the start (no cache reset).
RELEASE_AUTO = [float(x) for x in os.environ["RELEASE_AUTO"].split(":")] if os.environ.get("RELEASE_AUTO") else None
if RELEASE_AUTO:
    RELEASE_FRAME = int(RELEASE_AUTO[1])      # the fallback, and where the keys are built
# 28 Sep test: an animated Vertex Weight Mix does NOT release (cloth reads pin weights once, heading stayed at
# 10.02 m). "stiffness" pins at weight 0.99 (a spring; >= 0.999 is a hard snap) and keys pin stiffness to 0.
RELEASE_METHOD = os.environ.get("RELEASE_METHOD", "stiffness")
PIN_STIFFNESS = float(os.environ.get("PIN_STIFFNESS", "50.0"))
# 28 Sep: with the hem AT z = 0 the pleated sheet stood 10 m tall on its hem, pinned or not (compression 40 +
# bending 5 make it a corrugated column). The curtain now hangs LIFT_M clear, and compression is its own axis:
# real velvet resists stretch but buckles under compression.
LIFT_M = float(os.environ.get("LIFT_M", "0.2"))
TENSION = float(os.environ.get("TENSION", "40.0"))
COMPRESSION = float(os.environ.get("COMPRESSION", "40.0"))
# Blender cloth stiffness is not normalised by mass: the physical 0.8 kg/m2 gives ~0.06 kg per scout vertex,
# 5x lighter than Blender's presets, so the fabric out-stiffs gravity. VERTEX_MASS overrides it (kg).
VERTEX_MASS = float(os.environ["VERTEX_MASS"]) if os.environ.get("VERTEX_MASS") else None
# VERTEX_MASS_SCOUT: kg per vertex AT THE 27.4 cm SCOUT SPACING, scaled by vertex area, so a finer mesh keeps
# the same mass per square metre (a plain VERTEX_MASS would make a fine mesh far heavier).
if os.environ.get("VERTEX_MASS_SCOUT"):
    VERTEX_MASS = None
RENDER_STYLE = os.environ.get("RENDER_STYLE", "clay")   # "matte": no specular, cavity, subdiv + 6 mm solidify at render
FRAMES = int(os.environ.get("FRAMES", "210"))   # 5 s at 30 fps: release at 10, the fall takes ~1.5 s, then settling
QUALITY = int(os.environ.get("QUALITY", "10"))
DENSITY = 0.8                                   # kg/m2, as the Chaos curtain
OUT_DIR = Path(os.environ.get("OUT_DIR", str(ROOT / "Saved" / "CodexSoftGoods" / "DropBake")))
EXPORT_ABC = os.environ.get("EXPORT_ABC", "0") == "1"
ABC_START = int(os.environ.get("ABC_START", "1"))
# STAGE COLLIDERS (29 Sep, Gary chose option A, a raised boarded stage). "path|option", e.g.
# "Docs/StageFrontColliders_2026-09-28.json|A_raised_stage": boxes in UE world cm, mapped Bx = UE_Y/100,
# By = UE_X/100 (+upstage), Bz = UE_Z/100. They REPLACE the infinite floor plane, so cloth past the lip drapes
# down the fascia instead of lying on air. Posts and header are hidden from the SIDE views only (the near post
# would stand between the side camera and the curtain); they still collide.
COLLIDERS = os.environ.get("COLLIDERS", "")
# The flat SETUP sheet is 35 m wide, far wider than the portal, so fixed posts pierce it before the gather and the
# curtain ends up wrapped round a post (29 Sep smoke test). Posts are parked 40 m below until POSTS_FROM (the start of
# the show window), by which time the gathered curtain hangs inside them. A moving collider is not a data change.
POSTS_FROM = int(os.environ.get("POSTS_FROM", "0"))
# HEM GUIDE (30 Sep). The coarse long-settle hang showed that a FLAT cloth on the pinned ripplefold heading does not
# hold columns: the fine pleats die within ~1.5 m of the heading, and the rest merges into soft swags and a flare. Real
# curtains hold theirs with a weighted hem (lead tape) and by being trained. Blender cloth has no per-vertex mass, so
# the stand-in is a GUIDE: the lowest HEM_GUIDE_ROWS rows join the pin group at weight HEM_GUIDE_WEIGHT. That is a
# soft goal spring toward the column directly below each row's heading pleat (the Gathered key places every row under
# its heading position). It is released WITH the heading (pin stiffness keyed to 0), so the fall itself is
# unconstrained. 0 = off, as in every bake before this.
HEM_GUIDE_WEIGHT = float(os.environ.get("HEM_GUIDE_WEIGHT", "0"))
HEM_GUIDE_ROWS = int(os.environ.get("HEM_GUIDE_ROWS", "1"))
# A collider file for a site other than P01's stage front (world cm): "x,y,z" of the cloth line, subtracted from every box.
COLLIDER_ORIGIN_CM = [float(v) for v in os.environ["COLLIDER_ORIGIN_CM"].split(",")] if os.environ.get("COLLIDER_ORIGIN_CM") else None
# The hang-profile acceptance (30 Sep, the Conductor, for Gary's "structured hanging profile"). These are provisional
# targets, stated so the data can argue with them:
#   - flare = hem width / heading width at rest, at most FLARE_MAX (a strip bake converts its edge spread to the 17.77 m
#     Opening width);
#   - fold count retained at least FOLD_COUNT_MIN, and fold depth at least FOLD_DEPTH_MIN, of the heading's, at 75%,
#     50% and 25% of the height.
FLARE_MAX, FOLD_COUNT_MIN, FOLD_DEPTH_MIN, OPENING_TRACK_M = 1.15, 0.75, 0.5, 17.77
# Frames BEFORE SHOW_START over which stillness is also measured (to see the settle converge).
SETTLE_PROBE = int(os.environ.get("SETTLE_PROBE", "60"))
# Rig's limits apply to the frames the SHOW uses (the export window), not the setup gather.
SHOW_START = int(os.environ.get("SHOW_START", "0"))   # first exported frame (e.g. 1 s before the release): the show needs the hang + fall only
CLIP_STEP = int(os.environ.get("CLIP_STEP", "0"))   # >0: also render the fall every N frames, 3/4 and side, for a clip
CLIP_START = int(os.environ.get("CLIP_START", "1"))  # first frame of the clip (e.g. a second before the release)
LENS_34 = float(os.environ.get("LENS_34", "50"))      # 3/4 camera lens (mm); wider for the good run so a spill isn't cropped
RENDER_FRONT = os.environ.get("RENDER_FRONT", "0") == "1"   # extra orthographic FRONT view: the pile against the 17.8 m track
# 28 Sep (Gary: "it shouldn't keep the pleats when it falls"): Blender cloth takes the modelled mesh as its
# rest shape, so a curtain MODELLED pleated restores its pleats. REST=flat keeps the pleated start pose but
# gives the cloth the FLAT pattern as a rest shape key (cloth.rest_shape_key), as the real fabric is flat.
REST = os.environ.get("REST", "pleated")
# REST=flat (rest_shape_key) was TESTED and has NO EFFECT in 4.4 headless (a 1.5x rest key does not grow a patch).
# REST=gather is the working route: the mesh IS flat (so the rest shape is flat), the pinned heading is gathered
# from flat to the pleated track positions by a shape key over GATHER_FRAMES, the fabric drapes itself, then the
# heading is released. Pleats then exist only because the heading gathers them, as on a real curtain.
GATHER_FRAMES = int(os.environ.get("GATHER_FRAMES", "40"))
# REST=pleated_switch (30 Sep, for Gary's "structured hanging profile" AND "the good fall we already got"). The mesh
# IS the pleated pose, so the hang's rest shape holds columns from heading to hem, like a trained curtain. From
# RELEASE_FRAME a "Flat" shape key ramps the INPUT mesh to the flat pattern over REST_SWITCH_FRAMES, and the cloth's
# Dynamic Mesh option recomputes the rest lengths and bend angles from the input every frame. So the falling cloth
# has a FLAT rest shape and does not rebuild its pleats in the pile, which is what he rejected on 28 Sep. The pins are
# released at the same frame, so the input's move does not drag them.
REST_SWITCH_FRAMES = int(os.environ.get("REST_SWITCH_FRAMES", "15"))
# How far the rest shape goes toward flat (30 Sep, sw_b5_pswitch). The FULL switch (1.0) threw the pile flat: a cloth
# hanging in pleats its rest shape no longer wants stores bending energy, which the fall spends UNFOLDING it. Against
# the strip control that gave depth 1.34x, layers 0.7x, fold size 2.05x, and the COM was still sinking at 10 s. A
# partial switch keeps a little pleat memory (0.0 is the rejected corrugated rows) and stores less energy.
REST_SWITCH_AMOUNT = float(os.environ.get("REST_SWITCH_AMOUNT", "1.0"))
# UPSTAGE THROW (28 Sep; Gary's staging: the curtain falls UPSTAGE). The Chaos asset had 1.5 m/s upstage air; the
# first Blender port had none, so the pile centred on the curtain line and reached the footlights. The gathered
# heading is carried THROW_M metres UPSTAGE (+y) over the THROW_FRAMES before release at CONSTANT speed, so it is
# still moving when the pins let go and the top topples upstage. Blender gives that motion real inertia.
THROW_M = float(os.environ.get("THROW_M", "0"))
THROW_FRAMES = int(os.environ.get("THROW_FRAMES", "10"))

spec = importlib.util.spec_from_file_location("curtain_pattern", ROOT / "Scripts" / "build_curtain_chaos_pattern.py")
pattern = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pattern)                # reads CURTAIN_* env; its main() does not run


def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))]


def build_curtain():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, FRAMES
    bm = pattern.build_grid()
    flat = [v.co.copy() for v in bm.verts]
    pleats = pattern.Pleats(random.Random(pattern.SEED + 1))
    pattern.apply_start_pose(bm, pleats)
    gathered = [v.co.copy() for v in bm.verts]
    if REST == "gather":                  # simulate the FLAT sheet; the pleated pose becomes an animated key
        for v, co in zip(bm.verts, flat):
            v.co = co
    mesh = bpy.data.meshes.new(f"Curtain_{DROP_ID}")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"Curtain_{DROP_ID}", mesh)
    scene.collection.objects.link(obj)
    obj.location.z = LIFT_M
    if REST == "flat":
        obj.shape_key_add(name="Basis", from_mix=False)          # the pleated start pose (what is simulated)
        key = obj.shape_key_add(name="Flat", from_mix=False)
        for i, co in enumerate(flat):                            # bm.to_mesh keeps vertex order
            key.data[i].co = co
        key.value = 0.0
    top = [v.index for v in mesh.vertices if abs(v.co.z - pattern.DROP) < 1e-4]
    if REST == "gather":
        obj.shape_key_add(name="Basis", from_mix=False)          # flat: the cloth's rest shape
        key = obj.shape_key_add(name="Gathered", from_mix=False)
        for i, co in enumerate(gathered):
            key.data[i].co = co
        key.value = 0.0
        key.keyframe_insert("value", frame=1)
        key.value = 1.0
        key.keyframe_insert("value", frame=1 + GATHER_FRAMES)
        if THROW_M:
            # Relative to the FLAT basis: this key holds only the heading's upstage offset (the gathered pose
            # comes from the Gathered key), so the two add instead of doubling the gather.
            throw = obj.shape_key_add(name="Throw", from_mix=False)
            for i in top:
                throw.data[i].co = flat[i] + Vector((0.0, THROW_M, 0.0))
            start = RELEASE_FRAME - THROW_FRAMES
            for f in range(start, RELEASE_FRAME + 1):       # a key every frame = constant speed, moving at release
                throw.value = (f - start) / THROW_FRAMES
                throw.keyframe_insert("value", frame=f)
    if REST == "pleated_switch":
        obj.shape_key_add(name="Basis", from_mix=False)          # pleated: the hang's rest shape
        key = obj.shape_key_add(name="Flat", from_mix=False)
        for i, co in enumerate(flat):
            key.data[i].co = co
        key.value = 0.0
        key.keyframe_insert("value", frame=RELEASE_FRAME)
        key.value = REST_SWITCH_AMOUNT
        key.keyframe_insert("value", frame=RELEASE_FRAME + REST_SWITCH_FRAMES)
    pin = obj.vertex_groups.new(name="Pin")
    if RELEASE_METHOD != "none":        # "none": no pinned vertices at all (control: must fall from frame 1)
        pin.add(top, 0.99 if RELEASE_METHOD == "stiffness" else 1.0, "REPLACE")
    if HEM_GUIDE_WEIGHT > 0 and RELEASE_METHOD == "stiffness":
        levels = sorted({round(v.co.z, 4) for v in mesh.vertices})[:HEM_GUIDE_ROWS]
        guided = [v.index for v in mesh.vertices if round(v.co.z, 4) in levels]
        pin.add(guided, HEM_GUIDE_WEIGHT, "REPLACE")
        scene["hem_guided"] = len(guided)
    if RELEASE_METHOD == "weightmix":
        add_weightmix_release(obj)
    cloth = obj.modifiers.new("Cloth", "CLOTH")
    if REST == "flat":
        cloth.settings.rest_shape_key = obj.data.shape_keys.key_blocks["Flat"]
    if REST == "pleated_switch":
        cloth.settings.use_dynamic_mesh = True
    return finish_cloth(scene, obj, mesh, top, cloth)


def move_release_keys(obj, old_r, new_r):
    """Shift every key tied to the release (pin stiffness at R-1/R, the Flat rest switch at R and R+REST_SWITCH_FRAMES,
    a BEND_DAMPING_AFTER change at R-1/R) by new_r - old_r. Blender 4.4 keeps the object's and the shape keys' curves in
    one SLOTTED action, whose legacy .fcurves shows only the first slot, so the channelbags are walked."""
    d, moved, curves, seen = new_r - old_r, [], [], set()
    for owner in (obj, obj.data.shape_keys):
        ad = owner.animation_data if owner else None
        if not ad or not ad.action or ad.action.name in seen:
            continue
        seen.add(ad.action.name)
        for layer in ad.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    curves.extend(cb.fcurves)
    tied = {old_r - 1, old_r, old_r + REST_SWITCH_FRAMES}
    for fc in curves:
        if not any(k in fc.data_path for k in ("pin_stiffness", "Flat", "bending_damping")):
            continue
        for kp in fc.keyframe_points:
            if round(kp.co.x) in tied:
                moved.append([fc.data_path, round(kp.co.x), round(kp.co.x) + d])
                kp.co.x += d
                kp.handle_left.x += d
                kp.handle_right.x += d
        fc.update()
    return moved


def add_weightmix_release(obj):
    """Does not release in 4.4 (28 Sep release test). Kept so the negative can be re-checked."""
    mix = obj.modifiers.new("Release", "VERTEX_WEIGHT_MIX")
    mix.vertex_group_a = "Pin"
    mix.mix_mode = "SET"
    mix.mix_set = "A"
    mix.default_weight_b = 0.0
    mix.mask_constant = 0.0
    mix.keyframe_insert("mask_constant", frame=RELEASE_FRAME - 1)
    mix.mask_constant = 1.0
    mix.keyframe_insert("mask_constant", frame=RELEASE_FRAME)   # keys one frame apart: only whole frames are simulated


def add_render_modifiers(obj):
    """Render-only smoothing and 6 mm thickness, stacked AFTER the cloth and BEFORE simulating."""
    sub = obj.modifiers.new("RenderSubdiv", "SUBSURF")
    sub.levels, sub.render_levels = 0, 2
    sol = obj.modifiers.new("RenderThickness", "SOLIDIFY")
    sol.thickness, sol.show_viewport = 0.006, False


def ue_oriented_corners(o):
    """The 8 corners (UE cm) of an oriented box: centre, size (local X fwd, Y right, Z up), yaw about Z then pitch,
    using UE's FRotationMatrix axes with roll 0."""
    cy, sy = math.cos(math.radians(o["yaw_deg"])), math.sin(math.radians(o["yaw_deg"]))
    cp, sp = math.cos(math.radians(o["pitch_deg"])), math.sin(math.radians(o["pitch_deg"]))
    ax = (cp * cy, cp * sy, sp)
    ay = (-sy, cy, 0.0)
    az = (-sp * cy, -sp * sy, cp)
    hx, hy, hz = (v / 2.0 for v in o["size_cm"])
    c = o["centre_cm"]
    return [[c[k] + a * hx * ax[k] + b * hy * ay[k] + d * hz * az[k] for k in range(3)]
            for a in (-1, 1) for b in (-1, 1) for d in (-1, 1)]


def collider_from_corners(name, corners_ue, side_hide=False):
    """A convex box mesh from 8 UE-cm corners (a, b, d order from ue_oriented_corners), mapped to Blender metres."""
    verts = [(c[1] / 100.0, c[0] / 100.0, c[2] / 100.0) for c in corners_ue]      # Bx = UE_Y, By = UE_X, Bz = UE_Z
    idx = lambda a, b, d: (a * 4) + (b * 2) + d
    faces = [(idx(0, 0, 0), idx(0, 1, 0), idx(0, 1, 1), idx(0, 0, 1)), (idx(1, 0, 0), idx(1, 0, 1), idx(1, 1, 1), idx(1, 1, 0)),
             (idx(0, 0, 0), idx(0, 0, 1), idx(1, 0, 1), idx(1, 0, 0)), (idx(0, 1, 0), idx(1, 1, 0), idx(1, 1, 1), idx(0, 1, 1)),
             (idx(0, 0, 0), idx(1, 0, 0), idx(1, 1, 0), idx(0, 1, 0)), (idx(0, 0, 1), idx(0, 1, 1), idx(1, 1, 1), idx(1, 0, 1))]
    me = bpy.data.meshes.new(f"Collider_{name}")
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    o = bpy.data.objects.new(f"Collider_{name}", me)
    bpy.context.scene.collection.objects.link(o)
    o.modifiers.new("Collision", "COLLISION")
    o.collision.cloth_friction = FLOOR_FRICTION
    o.collision.thickness_outer = 0.01
    o["side_hide"] = side_hide
    m = bpy.data.materials.new(f"M_{o.name}")
    m.diffuse_color = (0.35, 0.33, 0.3, 1.0)
    o.data.materials.append(m)
    return o


def aabb_corners(box):
    lo, hi = box["min_cm"], box["max_cm"]
    return [[(lo, hi)[a][0], (lo, hi)[b][1], (lo, hi)[d][2]] for a in (0, 1) for b in (0, 1) for d in (0, 1)]


def add_stage_colliders():
    """Build Rig's stage colliders (Docs/StageFrontColliders_2026-09-28.json) in place of the infinite floor.
    v1 ("path|option"): options[option] axis-aligned boxes. v2 ("path|v2"): boxes + lamp_housings, the housings built
    from their exact ORIENTED box, whose corners must reproduce the file's own AABB to 1 cm (a convention check)."""
    path, option = COLLIDERS.split("|")
    spec = json.loads((ROOT / path).read_text(encoding="utf-8"))
    boxes = spec["options"][option] if option != "v2" else spec["boxes"]
    if COLLIDER_ORIGIN_CM:
        o = COLLIDER_ORIGIN_CM
        shift = lambda q: [q[k] - o[k] for k in range(3)]
        for b in list(boxes) + list(spec.get("lamp_housings", [])):
            b["min_cm"], b["max_cm"] = shift(b["min_cm"]), shift(b["max_cm"])
            if "oriented" in b:
                b["oriented"]["centre_cm"] = shift(b["oriented"]["centre_cm"])
    first, built = None, {"boxes": 0, "housings": 0}
    for box in boxes:
        o = collider_from_corners(box["name"], aabb_corners(box),       # hidden from the SIDE views only
                                  side_hide=any(k in box["name"] for k in ("Post", "Header", "Wing", "Border", "Gridiron",
                                                                          "Fixtures", "Lines")))
        built["boxes"] += 1
        # Anything standing where the wide FLAT setup sheet hangs is parked until POSTS_FROM: posts at the stage front,
        # wings at a passage end (30 Sep), or any box marked "park": true.
        if POSTS_FROM and (box["name"].startswith(("Post", "Wing")) or box.get("park")):
            o.location.z -= 40.0
            o.keyframe_insert("location", index=2, frame=POSTS_FROM - 1)
            o.location.z += 40.0
            o.keyframe_insert("location", index=2, frame=POSTS_FROM)
        first = first or o
    for h in (spec.get("lamp_housings", []) if option == "v2" else []):
        corners = ue_oriented_corners(h["oriented"]) if "oriented" in h else aabb_corners(h)
        lo = [min(c[k] for c in corners) for k in range(3)]
        hi = [max(c[k] for c in corners) for k in range(3)]
        err = max(max(abs(a - b) for a, b in zip(lo, h["min_cm"])), max(abs(a - b) for a, b in zip(hi, h["max_cm"])))
        if err > 1.0:
            raise SystemExit(f"COLLIDER_CONVENTION_MISMATCH|{h['name']}: oriented corners miss the file's AABB by {err:.1f} cm")
        collider_from_corners(h["name"], corners)
        built["housings"] += 1
    bpy.context.scene["colliders_built"] = json.dumps(built)
    print(f"CURTAIN_DROP_COLLIDERS|{json.dumps(built)}")
    return first


def finish_cloth(scene, obj, mesh, top, cloth):
    s = cloth.settings
    area = pattern.PATTERN_WIDTH * pattern.DROP
    s.air_damping = AIR_DAMPING
    if os.environ.get("VERTEX_MASS_SCOUT"):
        area_scale = (pattern.QUAD_X / (1.37 / 5)) ** 2
        s.mass = float(os.environ["VERTEX_MASS_SCOUT"]) * area_scale
        # Air damping acts per vertex too, so it must scale with vertex area like the mass. Unscaled, the
        # 9.1 cm run (1/9 the mass per vertex) fell through syrup: 2.3 m in the first second, not 4.9 (28 Sep).
        # At the 27.4 cm scout spacing the scale is exactly 1, so the scouts are unchanged.
        s.air_damping = AIR_DAMPING * area_scale
    else:
        s.mass = VERTEX_MASS if VERTEX_MASS else DENSITY * area / len(mesh.vertices)   # Blender cloth mass is per vertex, kg
    s.quality = QUALITY
    s.bending_model = "ANGULAR"
    s.tension_stiffness = TENSION
    s.compression_stiffness = COMPRESSION
    s.shear_stiffness = 20.0
    s.bending_stiffness = BEND
    s.tension_damping = s.compression_damping = s.shear_damping = 5.0
    s.bending_damping = float(os.environ.get("BEND_DAMPING", "0.5"))
    if os.environ.get("BEND_DAMPING_RAMP"):
        # "start:end:value": ramp bending damping from BEND_DAMPING to value between two frames (linear, a key per
        # frame), e.g. AT THE COLLAPSE only, so the fall and the thump keep the low damping and only the post-collapse
        # rebound is absorbed (28 Sep: damping 5 from release killed the swell but also slowed the whole fall).
        a, b, v = os.environ["BEND_DAMPING_RAMP"].split(":")
        a, b, v, base = int(a), int(b), float(v), float(os.environ.get("BEND_DAMPING", "0.5"))
        for f in range(a, b + 1):
            s.bending_damping = base + (v - base) * (f - a) / max(1, b - a)
            s.keyframe_insert("bending_damping", frame=f)
        s.bending_damping = base
    if os.environ.get("BEND_DAMPING_AFTER"):
        # Change bending damping only AT RELEASE, so the hang (and so the starting shape) matches the baseline.
        # 28 Sep: bending damping 5 from frame 1 stopped the drape forming in a 40-frame gather (hang_depth 0).
        s.keyframe_insert("bending_damping", frame=RELEASE_FRAME - 1)
        s.bending_damping = float(os.environ["BEND_DAMPING_AFTER"])
        s.keyframe_insert("bending_damping", frame=RELEASE_FRAME)
        s.bending_damping = float(os.environ.get("BEND_DAMPING", "0.5"))   # the value in force until release
    s.vertex_group_mass = "Pin"
    s.pin_stiffness = PIN_STIFFNESS if RELEASE_METHOD == "stiffness" else 1.0
    if RELEASE_METHOD == "stiffness":
        s.keyframe_insert("pin_stiffness", frame=RELEASE_FRAME - 1)
        s.pin_stiffness = 0.0
        s.keyframe_insert("pin_stiffness", frame=RELEASE_FRAME)
    c = cloth.collision_settings
    c.use_collision = True
    c.distance_min = 0.01
    c.collision_quality = COLLISION_QUALITY
    c.self_impulse_clamp = SELF_IMPULSE_CLAMP
    c.impulse_clamp = IMPULSE_CLAMP
    ratio = SELF_DIST / pattern.QUAD_X
    if ratio > SELF_DIST_MAX_RATIO:
        print(f"CURTAIN_DROP_WARNING|self-collision {SELF_DIST} m is {ratio:.2f} x the {pattern.QUAD_X:.3f} m edge "
              f"(> {SELF_DIST_MAX_RATIO}). Usual practice keeps it lower, but the approved take used 0.33 and the "
              f"'foam bounce' rationale was refuted; see the comment at SELF_DIST_MAX_RATIO.")
    c.use_self_collision = True
    c.self_distance_min = SELF_DIST
    c.self_friction = SELF_FRICTION
    cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, FRAMES
    if RENDER_STYLE == "matte":
        add_render_modifiers(obj)
    if COLLIDERS:
        floor = add_stage_colliders()
    else:
        bpy.ops.mesh.primitive_plane_add(size=60.0, location=(0.0, 0.0, 0.0))
        floor = bpy.context.active_object
        floor.name = "Floor"
        floor.modifiers.new("Collision", "COLLISION")
        floor.collision.cloth_friction = FLOOR_FRICTION
        floor.collision.thickness_outer = 0.01
    if RENDER_FRONT:
        # Track-end posts (upstage, out of the fall) so a spill past the 17.8 m track reads without explanation.
        for x in (-0.5 * pattern.TRACK_WIDTH, 0.5 * pattern.TRACK_WIDTH):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 4.0, 5.0))
            post = bpy.context.active_object
            post.name, post.scale = f"TrackEnd_{x:+.1f}", (0.06, 0.06, 10.0)
    # Materials now, not at render: touching the cloth's data after the sim resets its in-memory cache.
    for o, rgba in ((obj, (0.45, 0.02, 0.04, 1.0)), (floor, (0.35, 0.33, 0.3, 1.0))):
        if o.data.materials:
            continue
        m = bpy.data.materials.new(f"M_{o.name}")
        m.diffuse_color = rgba
        o.data.materials.append(m)
    return scene, obj, top, floor


def world_coords(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    return [ev.matrix_world @ v.co for v in ev.data.vertices]


def metrics(co, top):
    low = [p for p in co if p.z < 0.5]
    # 28 Sep v1 lesson: pile DEPTH alone rewards a curtain that TOPPLED and lies flat like a board. A heap
    # stacks many layers on a small footprint, so also measure the footprint (vertices below 1.5 m on a
    # grid of 1.25 x the vertex spacing, so a flat sheet fills its cells) and LAYERS = cloth area / footprint
    # (a lying sheet ~1-2, a heap several). Compare layers only between runs at the same resolution.
    cell = 1.25 * pattern.QUAD_X
    cells = {(math.floor(p.x / cell), math.floor(p.y / cell)) for p in co if p.z < 1.5}
    out = {"height_m": round(pct([p.z for p in co], 0.95), 3), "max_z_m": round(max(p.z for p in co), 3),
           "heading_mean_z_m": round(sum(co[i].z for i in top) / len(top), 3), "low_fraction": round(len(low) / len(co), 3)}
    out["mean_z_m"] = round(sum(p.z for p in co) / len(co), 3)
    # Full-extent AABB in Blender metres (x = along the track, +y = UPSTAGE, see the front camera at -y). For
    # Unreal (curtain yaw 90, upstage = +X): UE_X_cm = 100 * y, UE_Y_cm = 100 * x, UE_Z_cm = 100 * z.
    out["aabb_m"] = {"x": [round(min(p.x for p in co), 3), round(max(p.x for p in co), 3)],
                     "y": [round(min(p.y for p in co), 3), round(max(p.y for p in co), 3)],
                     "z": [round(min(p.z for p in co), 3), round(max(p.z for p in co), 3)]}
    if cells:
        footprint = len(cells) * cell * cell
        out["footprint_m2"] = round(footprint, 2)
        out["layers"] = round(pattern.PATTERN_WIDTH * pattern.DROP / footprint, 2)
    if low:
        out["depth_m"] = round(pct([p.y for p in low], 0.95) - pct([p.y for p in low], 0.05), 3)
        out["width_m"] = round(pct([p.x for p in low], 0.95) - pct([p.x for p in low], 0.05), 3)
        out["depth_centre_y_m"] = round(pct([p.y for p in low], 0.5), 3)
    return out


def row_folds(row):
    """Folds along one horizontal row of the grid (fabric order): its across-track depth y, detrended by a cubic over
    the row (so a flare's bow or tilt is not counted), then counted with 3 cm hysteresis. Two lobes make one fold."""
    import numpy as np
    y = row[:, 1]
    t = np.linspace(-1.0, 1.0, len(y))
    dy = y - np.polyval(np.polyfit(t, y, 3), t)
    lobes, state, peak = [], 0, 0.0
    for v in dy:
        s_ = 1 if v > 0.03 else (-1 if v < -0.03 else 0)
        if s_ and s_ != state:
            if state:
                lobes.append(peak)
            state, peak = s_, 0.0
        peak = max(peak, abs(v))
    if state:
        lobes.append(peak)
    return {"folds": round(len(lobes) / 2.0, 1), "mean_depth_m": round(2.0 * float(np.mean(lobes)), 3) if lobes else 0.0,
            "width_m": round(float(row[:, 0].max() - row[:, 0].min()), 3)}


def hang_profile(co):
    """The hang's structure at rest (the Conductor's test): the flare, and the folds kept at 75/50/25% of the height."""
    import numpy as np
    n_rows, n_cols = pattern.ROWS + 1, pattern.COLS + 1
    if len(co) != n_rows * n_cols:
        return {"skipped": f"{len(co)} vertices is not a plain {n_rows} x {n_cols} grid"}
    a = np.array([[p.x, p.y, p.z] for p in co]).reshape(n_rows, n_cols, 3)
    head, hem = a[0], a[-1]
    spread = [round(float(head[:, 0].min() - hem[:, 0].min()), 3), round(float(hem[:, 0].max() - head[:, 0].max()), 3)]
    out = {"flare_ratio": round(float((hem[:, 0].max() - hem[:, 0].min()) / (head[:, 0].max() - head[:, 0].min())), 3),
           "edge_spread_m": spread,
           "flare_at_opening_width": round((OPENING_TRACK_M + max(0.0, spread[0]) + max(0.0, spread[1])) / OPENING_TRACK_M, 3),
           "rows": {}}
    for label, frac in (("heading", 0.0), ("75%", 0.25), ("50%", 0.5), ("25%", 0.75), ("hem", 1.0)):
        out["rows"][label] = row_folds(a[int(round(frac * pattern.ROWS))])
    h = out["rows"]["heading"]
    ok = out["flare_at_opening_width"] <= FLARE_MAX
    for label in ("75%", "50%", "25%"):
        r = out["rows"][label]
        r["count_kept"] = round(r["folds"] / h["folds"], 2) if h["folds"] else None
        r["depth_kept"] = round(r["mean_depth_m"] / h["mean_depth_m"], 2) if h["mean_depth_m"] else None
        ok = ok and (r["count_kept"] or 0) >= FOLD_COUNT_MIN and (r["depth_kept"] or 0) >= FOLD_DEPTH_MIN
    out["targets"] = {"flare_max": FLARE_MAX, "fold_count_kept_min": FOLD_COUNT_MIN, "fold_depth_kept_min": FOLD_DEPTH_MIN}
    out["pass"] = bool(ok)
    return out


def fold_size(obj, crease_deg=45.0):
    """Characteristic fold size (m) = cloth area / total length of creased edges (dihedral > crease_deg).
    Fine crinkle has many creases (small), a plank few (large). Resolution-bound: compare at equal mesh size.
    NOT A BUG (30 Sep, sw_ps_a04_g07): gentle REGULAR ripples (pleat memory surviving the fall) bend less than
    crease_deg, so they count as no creases at all, and that pile scores COARSE (1.51x) although it looks rippled. The
    metric measures sharp creases, not waviness: read it beside the picture."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    area = sum(f.calc_area() for f in bm.faces)
    crease = sum(e.calc_length() for e in bm.edges
                 if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0) > math.radians(crease_deg))
    bm.free()
    ev.to_mesh_clear()
    return round(area / crease, 3) if crease > 0 else None


def render(obj, floor, name, loc, rot, ortho=None):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    if RENDER_STYLE == "matte":
        # Gary, 28 Sep: the clay render was "smooth and shiny". Matte, with cavity so crests read. (The
        # render-only subdivision + solidify are added in add_render_modifiers BEFORE the sim: adding a modifier
        # after simulating resets the in-memory cloth cache and the "final" render shows the unsimulated pose.)
        scene.display.shading.show_specular_highlight = False
        scene.display.shading.show_cavity = True
        scene.display.shading.cavity_type = "BOTH"
        scene.display.shading.cavity_ridge_factor = 1.0
        scene.display.shading.cavity_valley_factor = 1.0
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = LENS_34
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    cam = bpy.data.objects.new(name, cam_data)
    scene.collection.objects.link(cam)
    cam.location = loc
    if rot is not None:
        cam.rotation_euler = rot
    if rot is None:                       # aim at the pile
        target = bpy.data.objects.new(f"{name}_target", None)
        scene.collection.objects.link(target)
        target.location = (0.0, 0.0, 0.6)
        con = cam.constraints.new("TRACK_TO")
        con.target, con.track_axis, con.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    scene.camera = cam
    set_side_hide(name.startswith("side"))
    scene.render.filepath = str(OUT_DIR / f"{DROP_ID}_{name}.png")
    bpy.ops.render.render(write_still=True)
    return cam


def set_side_hide(side):
    """Posts/header hidden in side views only (render visibility is not geometry: it doesn't touch the cloth cache)."""
    for o in bpy.data.objects:
        if o.get("side_hide"):
            # At a passage site (COLLIDER_ORIGIN_CM) the wing cards stand between every camera and the cloth, so they are
            # hidden from ALL views there. They still collide: render visibility is not geometry.
            o.hide_render = side or bool(COLLIDER_ORIGIN_CM)


def main():
    global RELEASE_FRAME, SHOW_START, ABC_START, CLIP_START, FRAMES, SETTLE_PROBE
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if RELEASE_AUTO:
        if THROW_M or os.environ.get("BEND_DAMPING_RAMP"):
            raise SystemExit("RELEASE_AUTO refuses THROW_M and BEND_DAMPING_RAMP (their keys are not moved)")
        SHOW_START, SETTLE_PROBE = RELEASE_FRAME - int(RELEASE_AUTO[3]), RELEASE_FRAME   # record motion from frame 2
        ABC_START = CLIP_START = SHOW_START
    scene, obj, top, floor = build_curtain()
    report = {"id": DROP_ID, "rest": REST, "rest_switch_amount": REST_SWITCH_AMOUNT if REST == "pleated_switch" else None,
              "hem_guide_weight": HEM_GUIDE_WEIGHT, "hem_guide_rows": HEM_GUIDE_ROWS,
              "hem_guided_vertices": None, "fold_wavelength_m": pattern.FOLD_WAVELENGTH, "track_m": pattern.TRACK_WIDTH,
              "drop_m": pattern.DROP, "collider_origin_cm": COLLIDER_ORIGIN_CM, "release_method": RELEASE_METHOD, "colliders": COLLIDERS, "colliders_built": None, "posts_from": POSTS_FROM, "show_start": SHOW_START, "bend_damping_ramp": os.environ.get("BEND_DAMPING_RAMP", ""), "throw_m": THROW_M, "throw_frames": THROW_FRAMES, "render_style": RENDER_STYLE, "mass_per_vertex": None, "pin_stiffness": PIN_STIFFNESS, "fullness": pattern.FULLNESS, "quad_m": round(pattern.QUAD_X, 3), "vertices": len(obj.data.vertices),
              "vertex_mass": VERTEX_MASS, "bend": BEND, "tension": TENSION, "compression": COMPRESSION, "lift_m": LIFT_M, "self_dist_m": SELF_DIST, "floor_friction": FLOOR_FRICTION, "self_friction": SELF_FRICTION,
              "air_damping": AIR_DAMPING, "air_damping_applied": None, "release_frame": RELEASE_FRAME, "frames": FRAMES, "quality": QUALITY,
              "frame_seconds": [], "checkpoints": {}}
    report["mass_per_vertex"] = round(obj.modifiers["Cloth"].settings.mass, 4)
    report["colliders_built"] = json.loads(scene.get("colliders_built", "null"))
    # The collider FILE's bytes, not just its path: the file is shared and edited (30 Sep: Rig's upstage border), so two
    # bakes of one recipe across an edit simulate against different geometry and must not be compared as like for like.
    if COLLIDERS:
        import hashlib
        report["colliders_sha256"] = hashlib.sha256((ROOT / COLLIDERS.split("|")[0]).read_bytes()).hexdigest()
    report["hem_guided_vertices"] = scene.get("hem_guided")
    report["air_damping_applied"] = round(obj.modifiers["Cloth"].settings.air_damping, 4)
    cs = obj.modifiers["Cloth"].collision_settings
    report["self_dist_applied_m"] = round(cs.self_distance_min, 4)
    report["self_dist_edge_ratio"] = round(cs.self_distance_min / pattern.QUAD_X, 3)
    report["collision_quality_applied"] = cs.collision_quality
    report["bending_damping_applied"] = round(obj.modifiers["Cloth"].settings.bending_damping, 3)
    report["self_impulse_clamp_applied"] = round(cs.self_impulse_clamp, 3)
    report["impulse_clamp_applied"] = round(cs.impulse_clamp, 3)
    scene.frame_set(1)
    start = world_coords(obj)
    report["hang_depth_m"] = round(pct([p.y for p in start], 0.95) - pct([p.y for p in start], 0.05), 3)
    auto_post = FRAMES - RELEASE_FRAME if RELEASE_AUTO else None
    if RELEASE_AUTO:
        report["release_auto"] = {"min": int(RELEASE_AUTO[0]), "max": RELEASE_FRAME, "limit_mm": RELEASE_AUTO[2],
                                  "window": int(RELEASE_AUTO[3]), "chosen": None, "reason": None, "moved_keys": None}
    f = 0
    while f < FRAMES:
        f += 1
        t0 = time.perf_counter()
        scene.frame_set(f)
        report["frame_seconds"].append(round(time.perf_counter() - t0, 3))
        if f % 60 == 0:                   # progress, flushed: a loaded machine made "is it nearly done?" unanswerable
            print(f"CURTAIN_DROP_FRAME|{f}/{FRAMES}|{report['frame_seconds'][-1]}s", flush=True)
        if SHOW_START and SHOW_START - SETTLE_PROBE <= f < RELEASE_FRAME:
            # STILLNESS (30 Sep, Gary: the Opening drape was "weirdly bouncy and gathered a bit inwards at the top when it
            # should really be still"). final2 was exported 2.6 s after the gather, mid-swing: the hem moved 24 cm and
            # the cloth spread 55 cm a side before release. Measure the largest per-frame vertex move over the window
            # the audience sees before release (and a probe before it), so "at rest" is a number, not a judgement.
            co_s = world_coords(obj)
            prev = report.pop("_still_prev", None)
            if prev is not None:
                move = max((a_ - b_).length for a_, b_ in zip(co_s, prev))
                report.setdefault("still_mm", []).append([f, round(move * 1000, 2)])
            report["_still_prev"] = co_s
            ra = report.get("release_auto")
            if ra and ra["chosen"] is None and f >= ra["min"] - 1 and f < RELEASE_FRAME - 1:
                last = [m for f_, m in report.get("still_mm", []) if f_ > f - ra["window"]]
                if len(last) == ra["window"] and max(last) < ra["limit_mm"]:
                    r_new = f + 1
                    ra["moved_keys"] = move_release_keys(obj, RELEASE_FRAME, r_new)
                    ra.update({"chosen": r_new, "reason": f"quiet: frames {f - ra['window'] + 1}-{f} max {max(last):.2f} mm"})
                    RELEASE_FRAME = r_new
                    SHOW_START = ABC_START = CLIP_START = r_new - ra["window"]
                    FRAMES = r_new + auto_post
                    report.update({"release_frame": RELEASE_FRAME, "frames": FRAMES, "show_start": SHOW_START})
                    print(f"CURTAIN_DROP_RELEASE_AUTO|chosen={r_new}|{ra['reason']}", flush=True)
        # (adaptive release: from the earliest possible window, trimmed to the chosen one after the loop)
        if f > max(GATHER_FRAMES + 1, int(RELEASE_AUTO[0] - RELEASE_AUTO[3]) if RELEASE_AUTO else SHOW_START):
            # Rig's limits apply to the FURTHEST vertex in ANY frame of the hang and fall, not the settled pile
            # ("a cloth that billows through a post mid-fall is as broken as one that settles through it").
            # Blender metres: y = UE X / 100 (+ upstage), x = UE Y / 100, z = UE Z / 100 (relative to the curtain line).
            co = world_coords(obj)
            portal = [p for p in co if abs(p.y) <= 0.2]           # the portal band, UE X -20..+20 cm
            report.setdefault("extents", []).append([
                f, round(min(p.y for p in co), 3), round(max(p.y for p in co), 3),
                round(max((abs(p.x) for p in portal), default=0.0), 3), round(max((p.z for p in portal), default=0.0), 3),
                round(min(p.x for p in co), 3), round(max(p.x for p in co), 3)])
        if f >= RELEASE_FRAME - 1:        # per-frame centre of mass and top: the landing "bounce" is measured, not judged
            co = world_coords(obj)
            report.setdefault("com_z", []).append(round(sum(p.z for p in co) / len(co), 4))
            report.setdefault("top_z", []).append(round(max(p.z for p in co), 4))
        if f == RELEASE_FRAME - 1:
            report["_hang_profile"] = hang_profile(world_coords(obj))
        if f in (RELEASE_FRAME - 1, RELEASE_FRAME + 5, RELEASE_FRAME + 15, RELEASE_FRAME + 30, FRAMES - 30, FRAMES):
            report["checkpoints"][f] = metrics(world_coords(obj), top)
    if RELEASE_AUTO:
        ra = report["release_auto"]
        if ra["chosen"] is None:
            ra.update({"chosen": RELEASE_FRAME, "reason": "fallback: no quiet window before max"})
            print(f"CURTAIN_DROP_RELEASE_AUTO|chosen={RELEASE_FRAME}|fallback", flush=True)
        report["extents"] = [r for r in report.get("extents", []) if r[0] > SHOW_START]
    final = report["checkpoints"][FRAMES]
    final["fold_size_m"] = fold_size(obj)
    # Hanging depth = the hem's front-to-back spread just before release (frame 1 is flat for REST=gather).
    hang = report["checkpoints"].get(RELEASE_FRAME - 1, {})
    report["hang_profile"] = report.pop("_hang_profile", None)
    if hang.get("depth_m"):
        report["hang_depth_m"] = hang["depth_m"]
    if "depth_m" in final:
        final["depth_ratio"] = round(final["depth_m"] / max(report["hang_depth_m"], 1e-6), 2)
    ext = report.get("extents", [])
    if ext:
        def worst(col, fn):
            row = fn(ext, key=lambda r: r[col])
            return {"value_m": row[col], "frame": row[0], "phase": "hang" if row[0] < RELEASE_FRAME else "fall"}
        report["rig_limits"] = {                              # worst case over hang + fall, in Blender metres
            "downstage_min_y": worst(1, min), "upstage_max_y": worst(2, max),
            "portal_abs_x_max": worst(3, max), "portal_z_max": worst(4, max),
            "unreal_cm": {"X_min": round(100 * min(r[1] for r in ext)), "X_max": round(100 * max(r[2] for r in ext)),
                          "portal_absY_max": round(100 * max(r[3] for r in ext)), "portal_Z_max": round(100 * max(r[4] for r in ext)),
                          "Y_min": round(100 * min(r[5] for r in ext)), "Y_max": round(100 * max(r[6] for r in ext))}}
    report["released"] = report["checkpoints"][RELEASE_FRAME + 15]["heading_mean_z_m"] < pattern.DROP + LIFT_M - 0.5
    prev = report["checkpoints"].get(FRAMES - 30, {})
    report["settled"] = bool(prev) and abs(prev.get("height_m", 0) - final["height_m"]) < 0.05 and abs(prev.get("depth_m", 0) - final.get("depth_m", 0)) < 0.1
    report["solve_seconds_total"] = round(sum(report["frame_seconds"]), 1)
    # Final-frame renders FIRST, while the sim sits on its last frame; stepping back comes last (28 Sep: stepping
    # back and forward again showed the hang as the "result").
    cam34 = render(obj, floor, "34", Vector((-13.0, -19.0, 11.0)), None)
    camside = render(obj, floor, "side", Vector((-30.0, 0.0, 2.0)), (math.radians(90), 0.0, math.radians(-90)), ortho=8.0)
    if RENDER_FRONT:
        # From downstage (-y) looking upstage: 24 m wide, so the whole pile and any spill past the track show.
        render(obj, floor, "front", Vector((0.0, -40.0, 5.0)), (math.radians(90), 0.0, 0.0), ortho=24.0)
    scene.frame_set(RELEASE_FRAME - 1)                          # the hang just before release (a cache read)
    render(obj, floor, "hang34", Vector((-13.0, -19.0, 11.0)), None)
    if RENDER_FRONT:                                            # the hang from the front: columns or a flare
        render(obj, floor, "hangfront", Vector((0.0, -40.0, 5.0)), (math.radians(90), 0.0, 0.0), ortho=24.0)
    if CLIP_STEP > 0:
        # The cloth cache holds every simulated frame, so stepping back to render them is a cache read.
        # The clip's side camera is wider than the still's (19 m ortho) so the whole 10 m fall is in frame.
        clip_side = bpy.data.objects.new("clip_side", bpy.data.cameras.new("clip_side"))
        scene.collection.objects.link(clip_side)
        clip_side.data.type, clip_side.data.ortho_scale = "ORTHO", 19.0
        clip_side.location, clip_side.rotation_euler = (-30.0, 0.0, 5.0), (math.radians(90), 0.0, math.radians(-90))
        for tag, cam in (("34", cam34), ("side", clip_side)):
            clip_dir = OUT_DIR / f"{DROP_ID}_clip_{tag}"
            clip_dir.mkdir(parents=True, exist_ok=True)
            scene.camera = cam
            set_side_hide(tag == "side")
            for n, f in enumerate(range(CLIP_START, FRAMES + 1, CLIP_STEP)):
                scene.frame_set(f)
                scene.render.filepath = str(clip_dir / f"f{n:04d}.png")
                bpy.ops.render.render(write_still=True)
    if EXPORT_ABC:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        # VIEWPORT evaluation: the simulated cloth mesh only. The default (render) evaluation applied the render-only
        # subdivision + solidify: ~16x the geometry, 5.5 GB for one take (28 Sep). Unreal adds its own material.
        bpy.ops.wm.alembic_export(filepath=str(OUT_DIR / f"{DROP_ID}.abc"), start=ABC_START, end=FRAMES, selected=True,
                                  uvs=True, normals=True, face_sets=True, apply_subdiv=False, evaluation_mode="VIEWPORT")
    report.pop("_still_prev", None)
    if report.get("still_mm"):
        window = [m for f_, m in report["still_mm"] if f_ >= SHOW_START]
        report["still_window_max_mm"] = max(window) if window else None
        report["still_window_mean_mm"] = round(sum(window) / len(window), 2) if window else None
        # TIME TO 2 mm: the first frame from which EVERY later pre-release frame moves under 2 mm, in seconds after the
        # gather ends. It separates "never settles" from "its window opened too early" (the Conductor, 30 Sep).
        still = report["still_mm"]
        last_bad = max((f_ for f_, m in still if m >= 2.0), default=None)
        report["settle_to_2mm_s"] = (round((last_bad + 1 - (GATHER_FRAMES + 1)) / 30.0, 1) if last_bad is not None
                                     else round((still[0][0] - (GATHER_FRAMES + 1)) / 30.0, 1))
        report["settle_to_2mm_reached"] = last_bad is None or last_bad < still[-1][0]
    (OUT_DIR / f"{DROP_ID}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"CURTAIN_DROP_BAKE_DONE|{DROP_ID}|released={report['released']}|final={json.dumps(final)}"
          f"|hang_depth={report['hang_depth_m']}|solve_s={report['solve_seconds_total']}")


if __name__ == "__main__":      # Blender's --python runs this as __main__; importing it (close-up renders) does not bake
    main()
