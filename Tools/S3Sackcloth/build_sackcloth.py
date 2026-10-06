"""S3 sackcloth: drape a heavy hessian sheet over a posed body, or drop a rag pile on a sand mound (Blender 4.4).

Plan and reasons: Docs/Conductor/S3_SACKCLOTH_PLAN_2026-10-06.md. Written 6 Oct 2026; the Blender path has had
only a coarse smoke test (see the plan, section 7). Nothing here touches Unreal.

    # validate parameters only, no Blender needed (plain Python 3):
    python Tools/S3Sackcloth/build_sackcloth.py --dry-run --mode drape --collider X.fbx
    # real run (headless):
    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b --factory-startup ^
        --python Tools/S3Sackcloth/build_sackcloth.py -- --mode drape --collider <body.fbx> --out-id shore01_a

MODES
  drape  One sheet, SIZE_X x SIZE_Y m, laid flat above the collider's crown and pinned there in a small disc, then
         settled under gravity onto the body. With an ANIMATED FBX armature collider and --head-bone, the pin disc
         is hooked to that bone, so the sheet rides the head (route B of the plan; frames = --frames).
  pile   N torn pieces, pre-crumpled, dropped in a stack onto a generated sand mound and settled into a heap.
         All pieces are ONE mesh object (islands), so self-collision makes them collide with each other
         (Blender cloth objects do not collide with OTHER cloth objects).

OUTPUT (<out-dir>/<out-id>.*)
  .json    parameters, metrics (hem heights / pile footprint), timings, and the PASS/FAIL checks
  .fbx     the settled sheet/pile with SOLIDIFY applied (thickness, rim strip), material slots
           Sack_Front / Sack_Back / Sack_Edge (the Wing V2 slot idea); pile mode also exports the mound (Sand)
  .abc     only with --export-abc (animated drape): the simulated sheet, no solidify (UE gets thickness from
           the material / a later pass; see the curtain's 5.5 GB lesson)
  UV0      flat-pattern METRES (u = x_m, v = y_m): the material divides by its tile size (Poly Haven hessian_230
           is 0.269 m), so the weave runs along the fabric through every fold
  UV1      x = distance to the torn edge in metres (fray/opacity and dirt masks), y = per-piece random 0..1

TRAPS CARRIED OVER (memory puss-blender-cloth-drop-traps; Docs/ChaosClothCurtain.md "28 Sep (night)")
  - Any data change to the cloth object AFTER simulating resets its in-memory cache. So the settled shape is
    copied to a NEW object (new_from_object) and solidify/materials go on the copy, never on the cloth object.
  - Blender cloth mass is per VERTEX and stiffness is not normalised by mass: a PHYSICAL sacking mass
    (0.5 kg/m2) floats in place (measured in this tool's smoke test, 6 Oct: the hem stayed at the crown).
    So mass = --solver-mass (kg/m2, default = the approved curtain's) x vertex area, and air damping is scaled
    by vertex area the same way.
  - The modelled mesh is the rest shape: drape sheets start FLAT (flat rest, as Gary's curtain); rag pieces are
    pre-crumpled on purpose (rags keep their creases).
  - Under-stepping makes piles swell after collapse: QUALITY 20 / COLLISION_QUALITY 8 by default (measured fix).
  - Pin weight 0.99 + pin stiffness, never >= 0.999 (hard snap).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "DerivedAssets" / "S3Sackcloth"
HESSIAN_TILE_M = 0.269          # Poly Haven hessian_230 declared dimensions 268.75 x 267.2 mm (api.polyhaven.com/info)


# ----------------------------------------------------------------------------------------------- parameters
def build_parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dry-run", action="store_true", help="validate and print the plan; no Blender")
    p.add_argument("--mode", choices=("drape", "pile"), default="drape")
    p.add_argument("--out-id", default="sack_scout")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--seed", type=int, default=20261006)
    # fabric
    p.add_argument("--size-x", type=float, default=1.2, help="sheet width, m (Gary: 1.2)")
    p.add_argument("--size-y", type=float, default=1.2, help="sheet length, m (Gary: 1.2); Y runs front-back")
    p.add_argument("--quad", type=float, default=0.02, help="sim edge length, m (2 cm: ~3.7k verts at 1.2 m)")
    p.add_argument("--thickness", type=float, default=0.007, help="solidify thickness, m (Gary: heft; 6-8 mm)")
    p.add_argument("--solver-mass", type=float, default=13.4,
                   help="Blender SOLVER areal mass, kg/m2 (NOT the fabric's: real sacking 0.3-0.6 kg/m2 floats in "
                        "Blender's default stiffness/damping; 13.4 = the approved curtain, 0.1111 kg per 9.1 cm vertex)")
    p.add_argument("--bend", type=float, default=2.0, help="bending stiffness (jute holds round folds; velvet 5)")
    p.add_argument("--tension", type=float, default=40.0, help="curtain default 40")
    p.add_argument("--compression", type=float, default=4.0, help="low: heavy cloth must buckle, not stand")
    p.add_argument("--air-damping", type=float, default=1.0)
    p.add_argument("--self-dist", type=float, default=0.006, help="self-collision distance, m (~thickness)")
    p.add_argument("--friction", type=float, default=8.0)
    p.add_argument("--quality", type=int, default=20)
    p.add_argument("--collision-quality", type=int, default=8)
    p.add_argument("--fray-depth", type=float, default=0.035, help="torn-edge depth into the sheet, m")
    p.add_argument("--fray-holes", type=int, default=3, help="small worn holes per m2")
    # drape
    p.add_argument("--collider", default="", help="posed body: .fbx (armature ok) / .obj / .abc, any units")
    p.add_argument("--collider-scale", type=float, default=0.0, help="force a scale; 0 = auto (cm -> m)")
    p.add_argument("--crown", default="auto", help="'auto' (top of collider) or 'x,y,z' in metres, world")
    p.add_argument("--pin-offset", default="0,0", help="pin point on the sheet from its centre, m (x,y)")
    p.add_argument("--pin-radius", type=float, default=0.06, help="pinned disc radius on the sheet, m")
    p.add_argument("--yaw", type=float, default=0.0, help="sheet yaw about Z, degrees")
    p.add_argument("--lift", type=float, default=0.02, help="start height above the crown, m")
    p.add_argument("--head-bone", default="", help="hook the pin disc to this armature bone (animated drape)")
    p.add_argument("--target-hem-z", type=float, default=0.0,
                   help="m above the collider's feet the hem should reach below (crotch ~0.45 x height); 0 = auto")
    # pile
    p.add_argument("--pieces", type=int, default=9)
    p.add_argument("--piece-min", type=float, default=0.45, help="m, shortest piece side")
    p.add_argument("--piece-max", type=float, default=1.3, help="m, longest piece side")
    p.add_argument("--mound-radius", type=float, default=0.9, help="m")
    p.add_argument("--mound-height", type=float, default=0.18, help="m")
    p.add_argument("--crumple", type=float, default=0.08, help="pre-crumple amplitude, m")
    # run
    p.add_argument("--frames", type=int, default=120, help="settle frames at 30 fps (animated: the clip length)")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--export-abc", action="store_true")
    p.add_argument("--no-fbx", action="store_true")
    p.add_argument("--render", action="store_true", help="two Workbench stills of the settled result")
    return p


def parse_vec(text, n):
    vals = [float(v) for v in text.split(",")]
    if len(vals) != n:
        raise ValueError(f"expected {n} comma-separated numbers, got {text!r}")
    return vals


def validate(a):
    """Return (errors, warnings, plan). Pure Python: runs in --dry-run without Blender."""
    err, warn = [], []

    def rng(name, v, lo, hi):
        if not (lo <= v <= hi):
            err.append(f"{name}={v} outside [{lo}, {hi}]")

    rng("size-x", a.size_x, 0.3, 3.0)
    rng("size-y", a.size_y, 0.3, 3.0)
    rng("quad", a.quad, 0.008, 0.10)
    rng("thickness", a.thickness, 0.002, 0.02)
    rng("solver-mass", a.solver_mass, 0.5, 60.0)
    rng("bend", a.bend, 0.01, 200.0)
    rng("compression", a.compression, 0.1, 100.0)
    rng("quality", a.quality, 5, 40)
    rng("collision-quality", a.collision_quality, 2, 20)
    rng("frames", a.frames, 10, 20000)
    rng("fray-depth", a.fray_depth, 0.0, 0.15)
    if a.mode == "drape":
        n = (int(round(a.size_x / a.quad)) + 1) * (int(round(a.size_y / a.quad)) + 1)
        if min(a.size_x, a.size_y) / a.quad < 20:
            err.append("fewer than 20 quads across the sheet: folds will be knife-edged (curtain lesson)")
        if not a.dry_run and not a.collider:
            err.append("--collider is required in drape mode (a posed body exported from UE; plan step 2)")
        if a.collider and Path(a.collider).suffix.lower() not in (".fbx", ".obj", ".abc"):
            err.append(f"collider must be .fbx/.obj/.abc: {a.collider}")
        if a.collider and not a.dry_run and not Path(a.collider).is_file():
            err.append(f"collider not found: {a.collider}")
        if a.head_bone and a.collider and Path(a.collider).suffix.lower() != ".fbx":
            err.append("--head-bone needs an FBX armature collider")
        if a.crown != "auto":
            try:
                parse_vec(a.crown, 3)
            except ValueError as e:
                err.append(f"--crown: {e}")
        try:
            ox, oy = parse_vec(a.pin_offset, 2)
            if abs(ox) > a.size_x / 2 - a.pin_radius or abs(oy) > a.size_y / 2 - a.pin_radius:
                err.append("--pin-offset puts the pin disc off the sheet")
        except ValueError as e:
            err.append(f"--pin-offset: {e}")
        rng("pin-radius", a.pin_radius, 0.02, 0.2)
        area = a.size_x * a.size_y
        # Coverage arithmetic (inferred, plan section 3.4): centred and hanging, the hem reaches roughly
        # 0.8 x half-side below the crown at the edge midpoints and 0.8 x half-diagonal at the corners.
        cover = {"edge_mid_drop_m": round(0.8 * min(a.size_x, a.size_y) / 2, 2),
                 "corner_drop_m": round(0.8 * math.hypot(a.size_x, a.size_y) / 2, 2)}
    else:
        n_side = (a.piece_min + a.piece_max) / 2 / a.quad + 1
        n = int(a.pieces * n_side * n_side * 0.8)
        area = a.pieces * ((a.piece_min + a.piece_max) / 2) ** 2 * 0.8
        rng("pieces", a.pieces, 1, 40)
        if a.piece_min > a.piece_max:
            err.append("piece-min > piece-max")
        rng("mound-radius", a.mound_radius, 0.2, 5.0)
        rng("mound-height", a.mound_height, 0.0, 1.0)
        cover = None
    ratio = a.self_dist / a.quad
    if ratio > 0.35:
        warn.append(f"self-collision {a.self_dist} m is {ratio:.2f} x the edge (the approved curtain used 0.33)")
    if a.thickness > 2.5 * a.self_dist:
        warn.append("solidify thickness is much larger than the self-collision distance: layers may interpenetrate "
                    "visually after solidify (raise --self-dist toward the thickness)")
    mass_per_vertex = a.solver_mass * area / max(1, n)
    # Cost (INFERRED from the curtain bakes, Docs/ChaosClothCurtain.md: 15.7k verts ~1 s/frame, 42.9k ~2-5 s/frame,
    # both at quality 10-20). A body collider adds an unknown amount; the smoke test is the first real number.
    s_per_frame = max(0.05, n / 15700.0)
    plan = {"mode": a.mode, "vertices_est": n, "area_m2": round(area, 3),
            "mass_per_vertex_kg": round(mass_per_vertex, 6), "frames": a.frames,
            "est_seconds_per_frame_INFERRED": round(s_per_frame, 2),
            "est_minutes_INFERRED": round(s_per_frame * a.frames / 60.0, 1),
            "uv0": f"metres (material tile {HESSIAN_TILE_M} m)", "coverage_arithmetic_INFERRED": cover}
    return err, warn, plan


# ----------------------------------------------------------------------------------------------- Blender side
def blender_main(a):
    import bmesh
    import bpy
    from mathutils import Matrix, Vector

    t0 = time.time()
    rnd = random.Random(a.seed)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = a.fps
    scene.frame_start, scene.frame_end = 1, a.frames

    # ---- the cloth grid in the flat pattern (z = 0), UVs in metres, torn border, worn holes
    def make_piece(bm, sx, sy, origin, piece_rand):
        nx, ny = max(2, int(round(sx / a.quad))), max(2, int(round(sy / a.quad)))
        uv0 = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
        uv1 = bm.loops.layers.uv.get("FrayMask") or bm.loops.layers.uv.new("FrayMask")
        # aperiodic torn edge: per-side low-frequency bite depth + per-vertex jitter
        phases = [rnd.uniform(0, 6.283) for _ in range(8)]

        def bite(t, side):
            return a.fray_depth * (0.5 + 0.35 * math.sin(7.1 * t + phases[side]) + 0.15 * math.sin(23.0 * t + phases[side + 4]))

        grid = {}
        for j in range(ny + 1):
            for i in range(nx + 1):
                x, y = -sx / 2 + sx * i / nx, -sy / 2 + sy * j / ny
                d = min(x + sx / 2 - bite(y / sy, 0), sx / 2 - x - bite(y / sy, 1),
                        y + sy / 2 - bite(x / sx, 2), sy / 2 - y - bite(x / sx, 3))
                if d < -0.5 * a.quad:            # bitten away: the torn edge
                    continue
                jitter = 0.25 * a.quad if d < a.quad else 0.0
                v = bm.verts.new((origin[0] + x + rnd.uniform(-jitter, jitter),
                                  origin[1] + y + rnd.uniform(-jitter, jitter), origin[2]))
                grid[(i, j)] = (v, x, y, max(0.0, d))
        holes = [(rnd.uniform(-sx / 2.6, sx / 2.6), rnd.uniform(-sy / 2.6, sy / 2.6), rnd.uniform(0.012, 0.035))
                 for _ in range(int(a.fray_holes * sx * sy))]
        for j in range(ny):
            for i in range(nx):
                q = [grid.get(k) for k in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))]
                if any(c is None for c in q):
                    continue
                cx, cy = sum(c[1] for c in q) / 4, sum(c[2] for c in q) / 4
                if any(math.hypot(cx - hx, cy - hy) < hr for hx, hy, hr in holes):
                    continue
                f = bm.faces.new([c[0] for c in q])
                for loop, c in zip(f.loops, q):
                    loop[uv0].uv = (c[1] + sx / 2, c[2] + sy / 2)
                    loop[uv1].uv = (c[3], piece_rand)
        return grid

    def keep_largest_island(obj):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        seen, islands = set(), []
        for v in bm.verts:
            if v in seen:
                continue
            stack, isl = [v], []
            seen.add(v)
            while stack:
                w = stack.pop()
                isl.append(w)
                for e in w.link_edges:
                    o = e.other_vert(w)
                    if o not in seen:
                        seen.add(o)
                        stack.append(o)
            islands.append(isl)
        islands.sort(key=len, reverse=True)
        for isl in islands[1:]:
            bmesh.ops.delete(bm, geom=isl, context="VERTS")
        bm.to_mesh(obj.data)
        bm.free()
        return len(islands) - 1

    def new_obj(name, bm):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        scene.collection.objects.link(ob)
        return ob

    def add_cloth(ob, pin_group=None):
        cl = ob.modifiers.new("Cloth", "CLOTH")
        s = cl.settings
        area = sum(p.area for p in ob.data.polygons)
        vertex_area = area / max(1, len(ob.data.vertices))
        s.mass = a.solver_mass * vertex_area
        # Air damping acts per vertex like the mass, so it scales with vertex area too; reference = the curtain's
        # 27.4 cm scout spacing, where AIR_DAMPING 1.0 was set (bake_curtain_drop.py finish_cloth).
        s.air_damping = a.air_damping * vertex_area / (0.274 * 0.274)
        s.quality = a.quality
        s.bending_model = "ANGULAR"
        s.tension_stiffness, s.compression_stiffness = a.tension, a.compression
        s.shear_stiffness, s.bending_stiffness = 20.0, a.bend
        s.tension_damping = s.compression_damping = s.shear_damping = 5.0
        s.bending_damping = 0.5
        if pin_group:
            s.vertex_group_mass = pin_group
            s.pin_stiffness = 50.0
        c = cl.collision_settings
        c.use_collision, c.distance_min, c.collision_quality = True, 0.005, a.collision_quality
        c.use_self_collision, c.self_distance_min, c.self_friction = True, a.self_dist, a.friction
        cl.point_cache.frame_start, cl.point_cache.frame_end = 1, a.frames
        return cl

    def make_collider(ob, thickness=0.008):
        m = ob.modifiers.new("Collision", "COLLISION")
        ob.collision.thickness_outer = thickness
        ob.collision.cloth_friction = a.friction
        return m

    report = {"args": vars(a), "blender": bpy.app.version_string, "checks": {}}
    feet_z = 0.0
    if a.mode == "drape":
        # ---- collider (posed or animated body)
        ext = Path(a.collider).suffix.lower()
        before = set(bpy.data.objects)
        if ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=a.collider)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=a.collider)
        else:
            bpy.ops.wm.alembic_import(filepath=a.collider)
        imported = [o for o in bpy.data.objects if o not in before]
        meshes = [o for o in imported if o.type == "MESH"]
        arm = next((o for o in imported if o.type == "ARMATURE"), None)
        if not meshes:
            raise SystemExit("SACK_FAIL|collider has no mesh")
        scene.frame_set(1)
        dg = bpy.context.evaluated_depsgraph_get()
        pts = [o.matrix_world @ v.co for o in meshes for v in o.evaluated_get(dg).data.vertices]
        zs = [p.z for p in pts]
        height = max(zs) - min(zs)
        scale = a.collider_scale or (0.01 if height > 20.0 else 1.0)
        if scale != 1.0:
            top = [o for o in imported if o.parent is None]
            for o in top:
                o.matrix_world = Matrix.Scale(scale, 4) @ o.matrix_world
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            pts = [o.matrix_world @ v.co for o in meshes for v in o.evaluated_get(dg).data.vertices]
            zs = [p.z for p in pts]
            height = max(zs) - min(zs)
        if not 0.6 <= height <= 2.3:
            raise SystemExit(f"SACK_FAIL|collider height {height:.2f} m after scale {scale}; pass --collider-scale")
        feet_z = min(zs)
        for o in meshes:
            make_collider(o)
        if a.crown == "auto":
            top_z = max(zs)
            cap = [p for p in pts if p.z > top_z - 0.03]
            crown = Vector((sum(p.x for p in cap) / len(cap), sum(p.y for p in cap) / len(cap), top_z))
        else:
            crown = Vector(parse_vec(a.crown, 3))
        report["collider"] = {"objects": [o.name for o in meshes], "height_m": round(height, 3),
                              "scale_applied": scale, "crown": [round(c, 4) for c in crown],
                              "armature": arm.name if arm else None}
        # ---- the sheet, flat, centred so that its pin point sits over the crown
        ox, oy = parse_vec(a.pin_offset, 2)
        bm = bmesh.new()
        make_piece(bm, a.size_x, a.size_y, (0.0, 0.0, 0.0), rnd.random())
        sheet = new_obj(f"Sack_{a.out_id}", bm)
        report["islands_removed"] = keep_largest_island(sheet)
        sheet.matrix_world = (Matrix.Translation(crown + Vector((0, 0, a.lift)))
                              @ Matrix.Rotation(math.radians(a.yaw), 4, "Z") @ Matrix.Translation((-ox, -oy, 0)))
        vg = sheet.vertex_groups.new(name="Pin")
        for v in sheet.data.vertices:
            r = math.hypot(v.co.x - ox, v.co.y - oy)
            if r < a.pin_radius:
                vg.add([v.index], 0.99 if r < 0.6 * a.pin_radius else 0.99 * (a.pin_radius - r) / (0.4 * a.pin_radius), "REPLACE")
        if a.head_bone:
            if not arm or a.head_bone not in arm.data.bones:
                raise SystemExit(f"SACK_FAIL|armature bone {a.head_bone!r} not found")
            empty = bpy.data.objects.new("HeadPin", None)
            scene.collection.objects.link(empty)
            empty.matrix_world = sheet.matrix_world
            con = empty.constraints.new("CHILD_OF")
            con.target, con.subtarget = arm, a.head_bone
            con.set_inverse_pending = True
            hook = sheet.modifiers.new("HeadHook", "HOOK")     # BEFORE the cloth: pins follow the hooked mesh
            hook.object, hook.vertex_group = empty, "Pin"
        cloth_obj, cloth = sheet, add_cloth(sheet, "Pin")
    else:
        # ---- sand mound (collider + exported) and a stack of torn, pre-crumpled pieces
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=a.mound_radius * 3.2)
        mound = bpy.context.active_object
        mound.name = "Sand"
        bumps = [(rnd.uniform(-0.4, 0.4) * a.mound_radius, rnd.uniform(-0.4, 0.4) * a.mound_radius,
                  rnd.uniform(0.25, 0.6) * a.mound_radius, rnd.uniform(0.15, 0.45)) for _ in range(5)]
        for v in mound.data.vertices:
            r = math.hypot(v.co.x, v.co.y) / a.mound_radius
            h = a.mound_height * math.exp(-2.2 * r * r)
            h += sum(a.mound_height * w * math.exp(-((v.co.x - bx) ** 2 + (v.co.y - by) ** 2) / (br * br))
                     for bx, by, br, w in bumps)
            v.co.z = h
        make_collider(mound, 0.01)
        bm = bmesh.new()
        z = a.mound_height + 0.25
        for k in range(a.pieces):
            sx, sy = rnd.uniform(a.piece_min, a.piece_max), rnd.uniform(a.piece_min, a.piece_max)
            before_v = len(bm.verts)
            make_piece(bm, sx, sy, (0.0, 0.0, 0.0), rnd.random())
            bm.verts.ensure_lookup_table()
            new_verts = [bm.verts[i] for i in range(before_v, len(bm.verts))]
            ang, tilt = rnd.uniform(0, 6.283), rnd.uniform(-0.5, 0.5)
            off = Vector((rnd.uniform(-0.35, 0.35) * a.mound_radius, rnd.uniform(-0.35, 0.35) * a.mound_radius, z))
            ph = [rnd.uniform(0, 6.283) for _ in range(4)]
            rot = Matrix.Rotation(ang, 3, "Z") @ Matrix.Rotation(tilt, 3, "X")
            for v in new_verts:
                x, y = v.co.x, v.co.y
                cz = a.crumple * (math.sin(x * 9.0 + ph[0]) * math.sin(y * 7.0 + ph[1]) + 0.5 * math.sin((x + y) * 17.0 + ph[2]))
                v.co = rot @ Vector((x, y, cz)) + off
            z += max(0.08, 2.5 * a.crumple)
        pile = new_obj(f"RagPile_{a.out_id}", bm)
        cloth_obj, cloth = pile, add_cloth(pile)
        report["mound"] = {"radius_m": a.mound_radius, "height_m": a.mound_height}

    # ---- simulate (frame by frame; the cache must run from frame 1)
    t_sim = time.time()
    per = []
    for f in range(1, a.frames + 1):
        t = time.time()
        scene.frame_set(f)
        per.append(time.time() - t)
    report["timing"] = {"sim_seconds": round(time.time() - t_sim, 1),
                        "s_per_frame_p50": round(sorted(per)[len(per) // 2], 3), "frames": a.frames}

    # ---- copy the settled shape to a NEW object (never touch the cloth object after the sim)
    dg = bpy.context.evaluated_depsgraph_get()
    settled_me = bpy.data.meshes.new_from_object(cloth_obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    settled = bpy.data.objects.new(cloth_obj.name + "_Settled", settled_me)
    scene.collection.objects.link(settled)
    settled.matrix_world = cloth_obj.matrix_world.copy()
    co = [settled.matrix_world @ v.co for v in settled.data.vertices]

    # ---- metrics
    bm = bmesh.new()
    bm.from_mesh(settled.data)
    boundary = [settled.matrix_world @ v.co for v in bm.verts if v.is_boundary]
    bm.free()

    def pct(vals, p):
        s = sorted(vals)
        return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]

    if a.mode == "drape":
        h = report["collider"]["height_m"]
        target = a.target_hem_z or 0.45 * h            # crotch ~0.45 x stature (INFERRED anthropometric rule)
        hem = [p.z - feet_z for p in boundary]
        report["metrics"] = {"hem_z_p10_m": round(pct(hem, 10), 3), "hem_z_p50_m": round(pct(hem, 50), 3),
                             "hem_z_p90_m": round(pct(hem, 90), 3), "target_hem_z_m": round(target, 3),
                             "hem_fraction_below_target": round(sum(1 for z in hem if z < target) / len(hem), 3)}
        report["checks"]["hem_median_below_target"] = report["metrics"]["hem_z_p50_m"] < target
        report["checks"]["no_vertex_below_feet"] = min(p.z for p in co) > feet_z - 0.01
    else:
        xs, ys, zs = [p.x for p in co], [p.y for p in co], [p.z for p in co]
        report["metrics"] = {"footprint_x_m": round(pct(xs, 95) - pct(xs, 5), 3),
                             "footprint_y_m": round(pct(ys, 95) - pct(ys, 5), 3),
                             "height_p95_m": round(pct(zs, 95), 3), "height_max_m": round(max(zs), 3)}
        report["checks"]["pile_settled_low"] = report["metrics"]["height_max_m"] < a.mound_height + 1.0
    report["checks"]["finite"] = all(math.isfinite(c) for p in co for c in p)

    # ---- thickness on the COPY: solidify with rim; slots Front / Back / Edge
    for name in ("Sack_Front", "Sack_Back", "Sack_Edge"):
        settled.data.materials.append(bpy.data.materials.get(name) or bpy.data.materials.new(name))
    sol = settled.modifiers.new("Thickness", "SOLIDIFY")
    sol.thickness, sol.offset, sol.use_rim = a.thickness, 0.0, True
    sol.material_offset, sol.material_offset_rim = 1, 2
    bpy.context.view_layer.objects.active = settled
    for o in bpy.context.view_layer.objects:
        o.select_set(o is settled)
    bpy.ops.object.modifier_apply(modifier="Thickness")
    report["exported_vertices"] = len(settled.data.vertices)

    stem = out_dir / a.out_id
    if not a.no_fbx:
        export = [settled] + ([bpy.data.objects["Sand"]] if a.mode == "pile" else [])
        for o in bpy.context.view_layer.objects:
            o.select_set(o in export)
        bpy.ops.export_scene.fbx(filepath=str(stem) + ".fbx", use_selection=True, apply_unit_scale=True,
                                 mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
        report["fbx"] = str(stem) + ".fbx"
    if a.export_abc:
        for o in bpy.context.view_layer.objects:
            o.select_set(o is cloth_obj)
        bpy.ops.wm.alembic_export(filepath=str(stem) + ".abc", start=1, end=a.frames, selected=True,
                                  uvs=True, normals=True, face_sets=False)
        report["abc"] = str(stem) + ".abc"
    if a.render:
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.resolution_x, scene.render.resolution_y = 900, 1200
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
        c = sum(co, Vector()) / len(co)
        for tag, off in (("34", Vector((2.2, -2.2, 0.9))), ("side", Vector((3.0, 0.0, 0.3)))):
            cam.location = c + off
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
            scene.render.filepath = f"{stem}_{tag}.png"
            bpy.ops.render.render(write_still=True)
    report["seconds_total"] = round(time.time() - t0, 1)
    ok = all(report["checks"].values())
    (Path(str(stem) + ".json")).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(("SACK_OK|" if ok else "SACK_CHECK_FAILED|") + f"id={a.out_id}|mode={a.mode}|json={stem}.json|"
          + json.dumps(report["checks"]))


def main(argv):
    a = build_parser().parse_args(argv)
    err, warn, plan = validate(a)
    for w in warn:
        print("SACK_WARNING|" + w)
    if err:
        for e in err:
            print("SACK_INVALID|" + e)
        return 2
    if a.dry_run:
        print("SACK_DRY_RUN_OK|" + json.dumps(plan))
        return 0
    try:
        import bpy  # noqa: F401
    except ModuleNotFoundError:
        print("SACK_INVALID|not running inside Blender; use --dry-run or launch with blender -b --python")
        return 2
    blender_main(a)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    code = main(argv)
    if code and "bpy" not in sys.modules:
        sys.exit(code)
