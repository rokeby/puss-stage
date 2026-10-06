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
SKIN_BONES = ["head", "neck_01", "neck_02", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05",
              "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r"]
HESSIAN_TILE_M = 0.269          # Poly Haven hessian_230 declared dimensions 268.75 x 267.2 mm (api.polyhaven.com/info)


# ----------------------------------------------------------------------------------------------- parameters
def build_parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dry-run", action="store_true", help="validate and print the plan; no Blender")
    p.add_argument("--mode", choices=("drape", "pile", "skin"), default="drape")
    p.add_argument("--out-id", default="sack_scout")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--seed", type=int, default=20261006)
    # fabric
    p.add_argument("--size-x", type=float, default=1.8, help="sheet width, m (Gary, 6 Oct: 1.8 x 1.8)")
    p.add_argument("--size-y", type=float, default=1.8, help="sheet length, m (Gary, 6 Oct: 1.8 x 1.8); Y = front-back")
    p.add_argument("--quad", type=float, default=None, help="sim edge length, m (2 cm: ~3.7k verts at 1.2 m)")
    p.add_argument("--thickness", type=float, default=0.007, help="solidify thickness, m (Gary: heft; 6-8 mm)")
    p.add_argument("--solver-mass", type=float, default=13.4,
                   help="Blender SOLVER areal mass, kg/m2 (NOT the fabric's: real sacking 0.3-0.6 kg/m2 floats in "
                        "Blender's default stiffness/damping; 13.4 = the approved curtain, 0.1111 kg per 9.1 cm vertex)")
    p.add_argument("--bend", type=float, default=None,
                   help="bending stiffness; default drape/skin 1.0, pile 2.0 (velvet curtain 5)")
    p.add_argument("--tension", type=float, default=None, help="curtain default 40")
    p.add_argument("--shear", type=float, default=None)
    p.add_argument("--vertex-mass", type=float, default=None,
                   help="Blender kg PER VERTEX; overrides --solver-mass. Blender's presets (and so its stiffness "
                        "units) assume ~0.3-1 kg per vertex; 0 = use --solver-mass x vertex area")
    p.add_argument("--hem-gate", type=float, default=0.85, help="gate: outer-hem median height above the feet, m")
    p.add_argument("--radial-gate", type=float, default=0.65, help="gate: max horizontal cloth distance from the body axis, m")
    p.add_argument("--gap-gate", type=float, default=0.10,
                   help="INFO only: p75 cloth-to-body distance, m (a crouched figure's tent to the ground fails it "
                        "without ballooning: Shore02 0.25 m)")
    p.add_argument("--balloon-gate", type=float, default=0.85,
                   help="gate: max horizontal bbox side of the cloth, m (balloon run 1.10 m; hanging runs 0.53-0.73 m)")
    p.add_argument("--no-hip-proxy", action="store_true",
                   help="skin: do not add the torso collider proxy (the exported MetaHuman body has its outfit-covered "
                        "faces removed: no torso or hips between the thigh tops and the neck)")
    p.add_argument("--no-dna", action="store_true", help="skin: use the cut Body FBX even if a full BodyDNA FBX was exported")
    p.add_argument("--textured", action="store_true", help="render stills with the hessian_230 material (EEVEE/Cycles)")
    p.add_argument("--compression", type=float, default=None,
                   help="default drape/skin 20 (4 crumpled the drape into a cap, synthetic A/B 6 Oct), pile 4")
    p.add_argument("--air-damping", type=float, default=None,
                   help="default drape/skin 6 (a quasi-static settle: at 1 the far edges flipped back over the head, "
                        "synthetic rig 6 Oct), pile 1")
    p.add_argument("--self-dist", type=float, default=None, help="self-collision distance, m (~thickness)")
    p.add_argument("--friction", type=float, default=None, help="default drape/skin 2, pile 8")
    p.add_argument("--quality", type=int, default=None, help="default drape/skin 10, pile 20 (anti-swell)")
    p.add_argument("--collision-quality", type=int, default=8)
    p.add_argument("--fray-depth", type=float, default=0.035, help="torn-edge depth into the sheet, m")
    p.add_argument("--fray-holes", type=int, default=3, help="small worn holes per m2")
    # drape
    p.add_argument("--collider", default="", help="posed body: .fbx (armature ok) / .obj / .abc, any units")
    p.add_argument("--collider-scale", type=float, default=0.0, help="force a scale; 0 = auto (cm -> m)")
    p.add_argument("--crown", default="auto",
                   help="'auto' (top of collider), 'head' (highest collider point within 25 cm of the posed head "
                        "bone; default in skin mode, right for bowed figures) or 'x,y,z' in metres, world")
    p.add_argument("--pin-offset", default="0,0", help="pin point on the sheet from its centre, m (x,y)")
    p.add_argument("--pin-radius", type=float, default=0.06, help="pinned disc radius on the sheet, m")
    p.add_argument("--yaw", type=float, default=0.0,
                   help="sheet yaw about Z, degrees (skin: relative to the figure's facing; 45 = corners front/back)")
    p.add_argument("--pin-forward", type=float, default=0.0,
                   help="skin: move the sheet this far FORWARD of the crown pin (more cloth over the face/front), m")
    p.add_argument("--lift", type=float, default=0.02, help="start height above the crown, m")
    p.add_argument("--head-bone", default="", help="hook the pin disc to this armature bone (animated drape)")
    p.add_argument("--target-hem-z", type=float, default=0.0,
                   help="m above the collider's feet the hem should reach below (crotch ~0.45 x height); 0 = auto")
    # skin (route D): pose the exported body, drape, transfer weights, export a skeletal mesh
    p.add_argument("--figure", default="", help="skin: figure id, e.g. Shore01_M56 (reads the export manifest)")
    p.add_argument("--manifest", default=str(DEFAULT_OUT / "bodies" / "export_manifest.json"),
                   help="skin: written by Saved/CodexConductor/s3_shore_export_bodies.py")
    p.add_argument("--pose-seconds", type=float, default=-1.0, help="skin: override the manifest's pose time (source s)")
    p.add_argument("--skin-bones", default=",".join(SKIN_BONES), help="skin: allowed deform bones (chain)")
    p.add_argument("--skin-fallback", default="spine_01", help="skin: bone for weights with no allowed ancestor")
    p.add_argument("--max-influences", type=int, default=4)
    p.add_argument("--pose-copy", choices=("auto", "matrix", "rotation"), default="auto",
                   help="skin: 'matrix' = full bone transforms from the anim; 'rotation' = anim rotations on the "
                        "body's own bone offsets; auto = whichever puts the head nearest the UE motion record")
    p.add_argument("--skin-smooth", type=int, default=3, help="skin: weight smoothing passes")
    p.add_argument("--head-tolerance", type=float, default=0.03,
                   help="skin: posed head-bone z must match the UE motion record within this, m")
    # pile
    p.add_argument("--pieces", type=int, default=9)
    p.add_argument("--piece-min", type=float, default=0.45, help="m, shortest piece side")
    p.add_argument("--piece-max", type=float, default=1.3, help="m, longest piece side")
    p.add_argument("--mound-radius", type=float, default=0.9, help="m")
    p.add_argument("--mound-height", type=float, default=0.18, help="m")
    p.add_argument("--crumple", type=float, default=0.08, help="pre-crumple amplitude, m")
    # run
    p.add_argument("--frames", type=int, default=None, help="settle frames at 30 fps; default drape/skin 240, pile 120")
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
    if a.mode == "skin":
        if not a.figure:
            err.append("--figure is required in skin mode (e.g. Shore01_M56)")
        elif Path(a.manifest).is_file():
            try:
                rows = {r["id"]: r for r in json.loads(Path(a.manifest).read_text(encoding="utf-8"))["figures"]}
                row = rows.get(a.figure)
                if row is None:
                    err.append(f"figure {a.figure} not in {a.manifest}")
                else:
                    for key in ("body_fbx", "face_fbx", "anim_fbx"):
                        if not Path(row[key]["file"]).is_file():
                            err.append(f"{key} missing: {row[key]['file']}")
            except (ValueError, KeyError) as e:
                err.append(f"manifest unreadable: {e}")
        elif not a.dry_run:
            err.append(f"manifest not found: {a.manifest} (run the UE export first)")
        else:
            warn.append(f"manifest not found yet: {a.manifest} (dry run continues)")
        if a.crown == "auto":
            a.crown = "head"
        bad = [b for b in a.skin_bones.split(",") if not b.strip()]
        if bad or a.skin_fallback not in a.skin_bones.split(","):
            err.append("--skin-fallback must be one of --skin-bones")
        rng("max-influences", a.max_influences, 1, 8)
    if a.mode in ("drape", "skin"):
        n = (int(round(a.size_x / a.quad)) + 1) * (int(round(a.size_y / a.quad)) + 1)
        if min(a.size_x, a.size_y) / a.quad < 20:
            err.append("fewer than 20 quads across the sheet: folds will be knife-edged (curtain lesson)")
        if a.mode == "drape" and not a.dry_run and not a.collider:
            err.append("--collider is required in drape mode (a posed body exported from UE; plan step 2)")
        if a.collider and Path(a.collider).suffix.lower() not in (".fbx", ".obj", ".abc"):
            err.append(f"collider must be .fbx/.obj/.abc: {a.collider}")
        if a.collider and not a.dry_run and not Path(a.collider).is_file():
            err.append(f"collider not found: {a.collider}")
        if a.head_bone and a.collider and Path(a.collider).suffix.lower() != ".fbx":
            err.append("--head-bone needs an FBX armature collider")
        if a.crown not in ("auto", "head"):
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
    mass_per_vertex = a.vertex_mass if a.vertex_mass else a.solver_mass * area / max(1, n)
    # Cost (INFERRED from the curtain bakes, Docs/ChaosClothCurtain.md: 15.7k verts ~1 s/frame, 42.9k ~2-5 s/frame,
    # both at quality 10-20). A body collider adds an unknown amount; the smoke test is the first real number.
    s_per_frame = max(0.05, n / 15700.0)
    plan = {"mode": a.mode, "vertices_est": n, "area_m2": round(area, 3),
            "mass_per_vertex_kg": round(mass_per_vertex, 6), "frames": a.frames,
            "est_seconds_per_frame_INFERRED": round(s_per_frame, 2),
            "est_minutes_INFERRED": round(s_per_frame * a.frames / 60.0, 1),
            "uv0": f"metres (material tile {HESSIAN_TILE_M} m)", "coverage_arithmetic_INFERRED": cover}
    return err, warn, plan



# ----------------------------------------------------------------------------------------------- textured stills
TEX_DIR = DEFAULT_OUT / "textures" / "hessian_230"


def textured_setup(scene, sack, bodies, feet_z):
    """Old-grey hessian look for review stills only (UE builds its own material). Returns the engine used."""
    import bpy
    def img(name, colour):
        im = bpy.data.images.load(str(TEX_DIR / name), check_existing=True)
        im.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        return im

    def sack_mat(name, darken):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1 / HESSIAN_TILE_M, 1 / HESSIAN_TILE_M, 1)
        nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])

        def tex(name, colour):
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = img(name, colour)
            nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
            return t
        diff, rough, nor = tex("hessian_230_diff_2k.png", True), tex("hessian_230_rough_2k.png", False), \
            tex("hessian_230_nor_dx_2k.png", False)
        hs = nt.nodes.new("ShaderNodeHueSaturation")
        hs.inputs["Saturation"].default_value = 0.25          # "old grey worn sack" (Gary, 6 Oct)
        nt.links.new(diff.outputs["Color"], hs.inputs["Color"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        tint = (0.62 * darken, 0.60 * darken, 0.56 * darken, 1.0)
        mix.inputs["B"].default_value = tint
        nt.links.new(hs.outputs["Color"], mix.inputs["A"])
        nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
        nt.links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        comb = nt.nodes.new("ShaderNodeCombineColor")
        nt.links.new(nor.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs[1], inv.inputs[1])                # DirectX -> OpenGL: flip green
        nt.links.new(sep.outputs[0], comb.inputs[0])
        nt.links.new(inv.outputs[0], comb.inputs[1])
        nt.links.new(sep.outputs[2], comb.inputs[2])
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.uv_map = "UVMap"
        nt.links.new(comb.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        bsdf.inputs["Specular IOR Level"].default_value = 0.3
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        return m

    front, back = sack_mat("Sack_Front", 1.0), sack_mat("Sack_Back", 0.7)
    edge = sack_mat("Sack_Edge", 1.1)
    for i, m in enumerate((front, back, edge)):
        if i < len(sack.data.materials):
            sack.data.materials[i] = m
    skin = bpy.data.materials.new("ReviewSkin")
    skin.use_nodes = True
    b = next(n for n in skin.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.42, 0.33, 0.28, 1.0)
    b.inputs["Roughness"].default_value = 0.6
    for o in bodies:
        o.data.materials.clear()
        o.data.materials.append(skin)
        for poly in o.data.polygons:
            poly.material_index = 0
            poly.use_smooth = True
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0, 0, feet_z))
    floor = bpy.context.active_object
    fm = bpy.data.materials.new("ReviewFloor")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.35, 0.32, 0.27, 1)
    floor.data.materials.append(fm)
    sun = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    scene.collection.objects.link(sun)
    rim = bpy.data.objects.new("Rim", bpy.data.lights.new("Rim", "SUN"))
    rim.data.energy = 1.5
    rim.rotation_euler = (math.radians(60), 0, math.radians(200))
    scene.collection.objects.link(rim)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.25, 0.25, 0.26, 1)
    bg.inputs["Strength"].default_value = 0.6
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 24
        scene.cycles.device = "CPU"
    scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in
        scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Standard"
    return scene.render.engine


# ----------------------------------------------------------------------------------------------- skin mode helpers
def _import_fbx(path):
    import bpy
    objs0, acts0 = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True, ignore_leaf_bones=False,
                             automatic_bone_orientation=False)
    return [o for o in bpy.data.objects if o not in objs0], [x for x in bpy.data.actions if x not in acts0]


def _one(objs, kind, what):
    hits = [o for o in objs if o.type == kind]
    if len(hits) != 1:
        raise SystemExit(f"SACK_FAIL|{what}: expected 1 {kind}, got {len(hits)}")
    return hits[0]


def copy_pose(src, dst, mode="matrix"):
    """Give dst's bones the ARMATURE-SPACE matrices of src's same-named bones, parents first.

    Copying full matrices (not the action's rest-relative deltas) makes the result independent of the two rigs'
    rest poses: the anim FBX's armature carries the skeleton's reference pose, the body FBX the mesh's own
    (MetaHuman bodies differ in proportions). Unmatched dst bones (facial bones) keep their rest pose.
    """
    import bpy
    depth = {}

    def d(b):
        if b.name not in depth:
            depth[b.name] = 0 if b.parent is None else d(b.parent) + 1
        return depth[b.name]

    names = sorted((b.name for b in dst.data.bones if b.name in src.pose.bones), key=lambda n: d(dst.data.bones[n]))
    to_dst = dst.matrix_world.inverted() @ src.matrix_world
    level = None
    for n in names:
        if d(dst.data.bones[n]) != level:
            bpy.context.view_layer.update()
            level = d(dst.data.bones[n])
        sp, db = src.pose.bones[n], dst.data.bones[n]
        if mode == "matrix" or db.parent is None or sp.parent is None:
            dst.pose.bones[n].matrix = to_dst @ sp.matrix
        else:
            # rotation from the anim, translation (bone offset) from the BODY's own rest: UE's "Skeleton"
            # translation-retargeting reading of the same keys
            local = sp.parent.matrix.inverted() @ sp.matrix
            rest_local = db.parent.matrix_local.inverted() @ db.matrix_local
            m = local.to_quaternion().to_matrix().to_4x4()
            m.translation = rest_local.translation
            dst.pose.bones[n].matrix = dst.pose.bones[db.parent.name].matrix @ m
    bpy.context.view_layer.update()
    return len(names)


def pose_figure(a, scene, report):
    """Import the UE export (body, face, anim FBX), pose body + face at the pose frame, return static colliders."""
    import bpy
    from mathutils import Matrix
    rows = {r["id"]: r for r in json.loads(Path(a.manifest).read_text(encoding="utf-8"))["figures"]}
    row = rows[a.figure]
    fps = float(row["anim_fps_n_over_len"])
    scene.render.fps = max(1, int(round(fps)))
    scene.render.fps_base = scene.render.fps / fps          # exact rate, so seconds map to frames 1:1
    use_dna = bool(row.get("body_dna_fbx")) and not a.no_dna
    body_objs, _ = _import_fbx((row["body_dna_fbx"] if use_dna else row["body_fbx"])["file"])
    report["body_source"] = "BodyDNA (full body)" if use_dna else "Body (outfit-covered faces removed)"
    face_objs, _ = _import_fbx(row["face_fbx"]["file"])
    anim_objs, actions = _import_fbx(row["anim_fbx"]["file"])
    A = _one(body_objs, "ARMATURE", "body FBX")
    F = _one(face_objs, "ARMATURE", "face FBX")
    C = _one(anim_objs, "ARMATURE", "anim FBX")
    body_meshes = [o for o in body_objs if o.type == "MESH"]
    face_meshes = [o for o in face_objs if o.type == "MESH"]
    for o in anim_objs:                                     # a preview mesh, if the exporter wrote one
        if o.type == "MESH":
            bpy.data.objects.remove(o)
    if not body_meshes or not face_meshes:
        raise SystemExit("SACK_FAIL|body or face FBX has no mesh")
    act = C.animation_data.action if C.animation_data else (actions[0] if actions else None)
    if act is None:
        raise SystemExit("SACK_FAIL|anim FBX imported no action")
    # units: UE writes cm; whatever the importer did, measure the REST body and rescale all three rigs together
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    zs = [(o.matrix_world @ v.co).z for o in body_meshes + face_meshes for v in o.evaluated_get(dg).data.vertices]
    rest_h = max(zs) - min(zs)
    scale = a.collider_scale or (0.01 if rest_h > 20.0 else 1.0)
    if scale != 1.0:
        for o in body_objs + face_objs + [C]:
            if o.parent is None:
                o.matrix_world = Matrix.Scale(scale, 4) @ o.matrix_world
        bpy.context.view_layer.update()
        rest_h *= scale
    if not 1.3 <= rest_h <= 2.1:
        raise SystemExit(f"SACK_FAIL|rest body height {rest_h:.3f} m after scale {scale}")
    # the pose frame: action start + source seconds x fps
    t = a.pose_seconds if a.pose_seconds >= 0 else float(row["pose_source_seconds"])
    frame = act.frame_range[0] + t * fps
    scene.frame_set(int(frame), subframe=frame - int(frame))
    rec = [c / 100.0 for c in row["pose_head_cm"]]
    trials = {}
    for mode in (("matrix", "rotation") if a.pose_copy == "auto" else (a.pose_copy,)):
        n_body = copy_pose(C, A, mode)
        trials[mode] = (A.matrix_world @ A.pose.bones["head"].head).z - rec[2]
    best = min(trials, key=lambda k: abs(trials[k]))
    n_body = copy_pose(C, A, best)
    n_face = copy_pose(C, F, best)
    head = A.matrix_world @ A.pose.bones["head"].head
    dz = head.z - rec[2]
    report["pose"] = {"figure": a.figure, "pose_source_seconds": t, "blender_frame": frame, "fps": fps,
                      "action": act.name, "action_range": list(act.frame_range), "bones_posed_body": n_body,
                      "bones_posed_face": n_face, "head_bone_m": [round(c, 4) for c in head],
                      "record_head_m_ue_component": rec, "head_dz_m": round(dz, 4),
                      "head_xy_norm_m": [round(math.hypot(head.x, head.y), 4), round(math.hypot(rec[0], rec[1]), 4)],
                      "import_scale_applied": scale, "pose_copy_used": best,
                      "pose_copy_trials_dz_m": {k: round(v, 4) for k, v in trials.items()}}
    report["checks"]["pose_head_z_matches_record"] = abs(dz) < a.head_tolerance
    # static posed copies (keep vertex groups: names live on the mesh since Blender 3.0) = colliders + skin source
    dg = bpy.context.evaluated_depsgraph_get()
    posed = []
    for o in body_meshes + face_meshes:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        c = bpy.data.objects.new(o.name + "_Posed", me)
        scene.collection.objects.link(c)
        c.matrix_world = o.matrix_world.copy()
        posed.append(c)
        o.hide_set(True)
        o.hide_render = True
    bpy.data.objects.remove(C)
    weight_sources = list(posed)
    if not a.no_hip_proxy and not use_dna:
        posed.extend(hip_proxy(A, posed[0], scene, report))
    return {"colliders": posed, "weight_sources": weight_sources, "body_arm": A, "face_arm": F,
            "rest_height_m": rest_h, "row": row}


def hip_proxy(A, body, scene, report):
    """Collider-only TORSO proxy: four ellipsoids along the posed spine (never exported, never a weight source).

    Measured 6 Oct on Shore01/02: the exported body mesh has NO vertices dominated by pelvis/spine bones above
    0.79 m in the rest pose; the torso and hips are cut away where the outfit (DefaultGarment shirt + short) covers
    them [meas: Blender probe of Shore01_M56_Body.fbx; inf: MetaHuman removes garment-hidden faces]. Without this
    the sack falls into the empty torso. Sized from the posed bones: hip width from the thighs, chest width from
    the upper arms; depths are fixed (gaunt chest, pot belly) [inf]. Replace with the full DNA body when exported.
    """
    import bmesh
    import bpy
    from mathutils import Matrix, Vector
    pw = A.matrix_world
    P = lambda n: pw @ A.pose.bones[n].head
    need = ("pelvis", "spine_02", "spine_04", "spine_05", "neck_01", "thigh_l", "thigh_r", "upperarm_l", "upperarm_r")
    if any(n not in A.pose.bones for n in need):
        report["torso_proxy"] = {"skipped": "bones missing"}
        return []
    hip_lat = P("thigh_l") - P("thigh_r")
    sh_lat = P("upperarm_l") - P("upperarm_r")
    hip_w = hip_lat.length / 2 + 0.085
    sh_w = sh_lat.length / 2 - 0.02
    chain = [("pelvis", "spine_02", hip_w, 0.11, hip_lat), ("spine_02", "spine_04", 0.5 * (hip_w + sh_w), 0.135, hip_lat.lerp(sh_lat, 0.5)),
             ("spine_04", "spine_05", sh_w, 0.115, sh_lat), ("spine_05", "neck_01", sh_w * 0.95, 0.10, sh_lat)]
    out, rows = [], []
    for a_name, b_name, w, d, lat in chain:
        pa, pb = P(a_name), P(b_name)
        up = (pb - pa)
        half_len = max(0.06, up.length * 0.65)
        up.normalize()
        x = (lat - up * lat.dot(up)).normalized()
        y = up.cross(x).normalized()
        centre = (pa + pb) / 2
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=1.0)
        me = bpy.data.meshes.new("TorsoProxy")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("TorsoProxy_" + a_name, me)
        scene.collection.objects.link(ob)
        rot = Matrix((x, y, up)).transposed().to_4x4()
        ob.matrix_world = Matrix.Translation(centre) @ rot @ Matrix.Diagonal((w, d, half_len, 1.0))
        out.append(ob)
        rows.append({"segment": a_name + "-" + b_name, "half_width_m": round(w, 3), "half_depth_m": d,
                     "half_length_m": round(half_len, 3)})
    report["torso_proxy"] = rows
    return out


def skin_and_export(a, scene, settled, skin, stem, report):
    """Weights from the posed body+face onto the settled sack; bind in the posed frame; export a skeletal FBX."""
    import bpy
    A, F = skin["body_arm"], skin["face_arm"]
    allowed = [b.strip() for b in a.skin_bones.split(",") if b.strip()]
    missing = [b for b in allowed if b not in A.data.bones]
    if missing:
        raise SystemExit("SACK_FAIL|skin bones not in the body armature: " + ",".join(missing))

    def activate(ob, *others):
        for o in bpy.context.view_layer.objects:
            o.select_set(o is ob or o in others)
        bpy.context.view_layer.objects.active = ob

    # 1. one source object with every posed vertex group (body + face)
    copies = []
    for c in skin["weight_sources"]:
        d = c.copy()
        d.data = c.data.copy()
        d.modifiers.clear()
        scene.collection.objects.link(d)
        copies.append(d)
    activate(copies[0], *copies[1:])
    if len(copies) > 1:
        bpy.ops.object.join()
    src = bpy.context.view_layer.objects.active
    src.name = "SkinSource"
    # 2. transfer (nearest face, interpolated), then remap every weight to its nearest ALLOWED ancestor bone
    m = settled.modifiers.new("SkinXfer", "DATA_TRANSFER")
    m.object, m.use_object_transform = src, True
    m.use_vert_data, m.data_types_verts = True, {"VGROUP_WEIGHTS"}
    m.vert_mapping = "POLYINTERP_NEAREST"
    m.layers_vgroup_select_src, m.layers_vgroup_select_dst = "ALL", "NAME"
    activate(settled)
    bpy.ops.object.datalayout_transfer(modifier=m.name)
    bpy.ops.object.modifier_apply(modifier=m.name)
    parents = {}
    for arm in (A, F):
        for b in arm.data.bones:
            parents.setdefault(b.name, b.parent.name if b.parent else None)

    def target(name):
        n = name
        while n is not None:
            if n in allowed:
                return n
            n = parents.get(n)
        return a.skin_fallback

    names = {g.index: g.name for g in settled.vertex_groups}
    acc = []
    for v in settled.data.vertices:
        w = {}
        for ge in v.groups:
            if ge.weight > 1e-5 and names[ge.group] in parents:     # bone groups only ("Pin" etc. dropped)
                t = target(names[ge.group])
                w[t] = w.get(t, 0.0) + ge.weight
        acc.append(w)
    nbrs = [[] for _ in settled.data.vertices]
    for e in settled.data.edges:
        i, j = e.vertices
        nbrs[i].append(j)
        nbrs[j].append(i)
    for _ in range(a.skin_smooth):          # Laplacian blend 50/50 with the edge neighbours' mean
        nxt = []
        for i, w in enumerate(acc):
            if not nbrs[i]:
                nxt.append(w)
                continue
            mean = {}
            for j in nbrs[i]:
                for b, x in acc[j].items():
                    mean[b] = mean.get(b, 0.0) + x / len(nbrs[i])
            keys = set(w) | set(mean)
            nxt.append({b: 0.5 * w.get(b, 0.0) + 0.5 * mean.get(b, 0.0) for b in keys})
        acc = nxt
    settled.vertex_groups.clear()
    groups = {b: settled.vertex_groups.new(name=b) for b in allowed}
    unweighted, usage = 0, {b: 0 for b in allowed}
    for i, w in enumerate(acc):
        if not w:
            w, unweighted = {a.skin_fallback: 1.0}, unweighted + 1
        top = sorted(w.items(), key=lambda kv: -kv[1])[:a.max_influences]
        total = sum(x for _, x in top)
        for b, x in top:
            groups[b].add([i], x / total, "REPLACE")
            usage[b] += 1
    smooth_ok = f"{a.skin_smooth} Laplacian passes before the top-{a.max_influences} cut and normalise"
    # 3. bind armature = the body rig with the POSE APPLIED AS REST (so the sack's bind pose is the drape pose)
    A.name = "BodyArmature_Source"
    B = A.copy()
    B.data = A.data.copy()
    B.animation_data_clear()
    scene.collection.objects.link(B)
    B.name = "Armature"            # UE treats an FBX node named "Armature" as the rig node, not a bone [inf]
    activate(B)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    world = settled.matrix_world.copy()
    settled.parent = B
    settled.matrix_world = world
    mod = settled.modifiers.new("Armature", "ARMATURE")
    mod.object = B
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = settled.evaluated_get(dg).data
    rest_err = max((settled.matrix_world @ v.co - settled.matrix_world @ e.co).length
                   for v, e in zip(settled.data.vertices, ev.vertices))
    # 4. export, then RE-IMPORT and compare (catches unit/axis/bind surprises before UE does)
    path = str(stem) + "_SK.fbx"
    activate(B, settled)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"ARMATURE", "MESH"},
                             add_leaf_bones=False, bake_anim=False, apply_unit_scale=True, mesh_smooth_type="FACE",
                             use_armature_deform_only=False, armature_nodetype="NULL",
                             primary_bone_axis="Y", secondary_bone_axis="X")
    back, _ = _import_fbx(path)
    rb_arm = _one(back, "ARMATURE", "re-import")
    rb_mesh = _one(back, "MESH", "re-import")
    bpy.context.view_layer.update()
    head_b = B.matrix_world @ B.data.bones["head"].head_local
    head_r = rb_arm.matrix_world @ rb_arm.data.bones["head"].head_local
    dg = bpy.context.evaluated_depsgraph_get()

    def bbox(ob):
        pts = [ob.matrix_world @ v.co for v in ob.evaluated_get(dg).data.vertices]
        return [min(p[i] for p in pts) for i in range(3)] + [max(p[i] for p in pts) for i in range(3)]

    bb_src, bb_back = bbox(settled), bbox(rb_mesh)
    bb_err = max(abs(x - y) for x, y in zip(bb_src, bb_back))
    for o in back:
        bpy.data.objects.remove(o)
    report["skin"] = {"fbx": path, "bones": allowed, "fallback": a.skin_fallback, "unweighted_vertices": unweighted,
                      "vertices": len(acc), "usage": usage, "smooth": smooth_ok, "bind_rest_error_m": rest_err,
                      "roundtrip_head_error_m": (head_b - head_r).length, "roundtrip_bbox_error_m": bb_err,
                      "exported_bones": len(B.data.bones)}
    report["checks"]["skin_unweighted_under_1pct"] = unweighted <= 0.01 * len(acc)
    report["checks"]["skin_bind_is_identity"] = rest_err < 1e-4
    report["checks"]["skin_roundtrip_within_5mm"] = (head_b - head_r).length < 0.005 and bb_err < 0.005
    return path

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
        s.mass = a.vertex_mass if a.vertex_mass > 0 else a.solver_mass * vertex_area
        # Air damping acts per vertex like the mass, so it scales with vertex area too; reference = the curtain's
        # 27.4 cm scout spacing, where AIR_DAMPING 1.0 was set (bake_curtain_drop.py finish_cloth).
        s.air_damping = a.air_damping if a.vertex_mass > 0 else a.air_damping * vertex_area / (0.274 * 0.274)
        s.quality = a.quality
        s.bending_model = "ANGULAR"
        s.tension_stiffness, s.compression_stiffness = a.tension, a.compression
        s.shear_stiffness, s.bending_stiffness = a.shear, a.bend
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
    skin = None
    if a.mode == "skin":
        # ---- posed MetaHuman body + face from the UE export (s3_shore_export_bodies.py), as static colliders
        skin = pose_figure(a, scene, report)
        imported = meshes = skin["colliders"]
        arm = skin["body_arm"]
    elif a.mode == "drape":
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
    if a.mode in ("drape", "skin"):
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
        bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0, 0, feet_z))
        ground = bpy.context.active_object
        ground.name = "GroundCollider"
        make_collider(ground, 0.01)
        ground.hide_render = True
        if a.crown == "auto":
            top_z = max(zs)
            cap = [p for p in pts if p.z > top_z - 0.03]
            crown = Vector((sum(p.x for p in cap) / len(cap), sum(p.y for p in cap) / len(cap), top_z))
        elif a.crown == "head":
            if arm is None or "head" not in arm.pose.bones:
                raise SystemExit("SACK_FAIL|--crown head needs an armature with a 'head' bone")
            hb = arm.matrix_world @ arm.pose.bones["head"].head
            near = [p for p in pts if (p - hb).length < 0.25]
            if not near:
                raise SystemExit("SACK_FAIL|no collider vertex within 25 cm of the head bone")
            top = max(near, key=lambda p: p.z)
            crown = Vector((top.x, top.y, top.z))
        else:
            crown = Vector(parse_vec(a.crown, 3))
        report["collider"] = {"objects": [o.name for o in meshes], "height_m": round(height, 3),
                              "scale_applied": scale, "crown": [round(c, 4) for c in crown],
                              "armature": arm.name if arm else None}
        # ---- the sheet, flat, centred so that its pin point sits over the crown
        ox, oy = parse_vec(a.pin_offset, 2)
        base_yaw = 0.0
        if skin:
            # facing = horizontal direction from the head bone to the nose tip (the face vertex farthest out
            # horizontally between 2 and 12 cm above the head bone)
            hb = arm.matrix_world @ arm.pose.bones["head"].head
            face = skin["weight_sources"][-1]
            cand = [face.matrix_world @ v.co for v in face.data.vertices]
            cand = [q for q in cand if 0.02 < q.z - hb.z < 0.12]
            nose = max(cand, key=lambda q: math.hypot(q.x - hb.x, q.y - hb.y))
            fwd = Vector((nose.x - hb.x, nose.y - hb.y, 0.0)).normalized()
            base_yaw = math.degrees(math.atan2(fwd.y, fwd.x)) - 90.0     # sheet +Y -> facing
            oy -= a.pin_forward
            report["facing"] = {"forward_xy": [round(fwd.x, 3), round(fwd.y, 3)], "sheet_yaw_deg": round(base_yaw + a.yaw, 1)}
        bm = bmesh.new()
        make_piece(bm, a.size_x, a.size_y, (0.0, 0.0, 0.0), rnd.random())
        sheet = new_obj(f"Sack_{a.out_id}", bm)
        report["islands_removed"] = keep_largest_island(sheet)
        sheet.matrix_world = (Matrix.Translation(crown + Vector((0, 0, a.lift)))
                              @ Matrix.Rotation(math.radians(base_yaw + a.yaw), 4, "Z") @ Matrix.Translation((-ox, -oy, 0)))
        report["pin_xy_on_sheet_m"] = [ox, oy]
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
    # the HEM = outer boundary only: boundary vertices far (in the flat pattern, UV0 metres) from the pin point.
    # Worn holes and tears near the crown are boundaries too and must not count (6 Oct: they made the hem read
    # ~0.3 m high on every run).
    uvl = bm.loops.layers.uv.get("UVMap")
    if a.mode in ("drape", "skin") and uvl is not None:
        ox, oy = report.get("pin_xy_on_sheet_m") or parse_vec(a.pin_offset, 2)
        pin_uv = (a.size_x / 2 + ox, a.size_y / 2 + oy)
        reach = 0.7 * min(a.size_x, a.size_y) / 2
        boundary = []
        for v in bm.verts:
            if v.is_boundary and v.link_loops:
                u, w = v.link_loops[0][uvl].uv
                if math.hypot(u - pin_uv[0], w - pin_uv[1]) > reach:
                    boundary.append(settled.matrix_world @ v.co)
    else:
        boundary = [settled.matrix_world @ v.co for v in bm.verts if v.is_boundary]
    bm.free()

    def pct(vals, p):
        s = sorted(vals)
        return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]

    if a.mode in ("drape", "skin"):
        h = skin["rest_height_m"] if skin else report["collider"]["height_m"]
        target = a.target_hem_z or 0.45 * h            # crotch ~0.45 x stature (INFERRED anthropometric rule)
        hem = [p.z - feet_z for p in boundary]
        report["metrics"] = {"hem_z_p10_m": round(pct(hem, 10), 3), "hem_z_p50_m": round(pct(hem, 50), 3),
                             "hem_z_p90_m": round(pct(hem, 90), 3), "target_hem_z_m": round(target, 3),
                             "hem_fraction_below_target": round(sum(1 for z in hem if z < target) / len(hem), 3)}
        # body axis: vertical through the posed pelvis (skin) or the collider's centre of mass (drape)
        if skin:
            ax = skin["body_arm"].matrix_world @ skin["body_arm"].pose.bones["pelvis"].head
        else:
            ax = sum(pts, Vector()) / len(pts)
        rad = [math.hypot(p.x - ax.x, p.y - ax.y) for p in co]
        core_d = None
        if skin:
            A_ = skin["body_arm"]
            line = [A_.matrix_world @ A_.pose.bones[n].head for n in
                    ("pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01", "neck_02", "head")
                    if n in A_.pose.bones]
            line.append(A_.matrix_world @ A_.pose.bones["head"].tail)

            def seg_d(p, a0, b0):
                ab = b0 - a0
                t = max(0.0, min(1.0, (p - a0).dot(ab) / max(1e-9, ab.dot(ab))))
                q = a0 + ab * t
                return math.hypot(p.x - q.x, p.y - q.y)     # horizontal offset from the nearest core point
            core_d = [min(seg_d(p, line[i], line[i + 1]) for i in range(len(line) - 1)) for p in co]
            rad = core_d
        from mathutils.bvhtree import BVHTree
        dgm = bpy.context.evaluated_depsgraph_get()
        trees = [BVHTree.FromObject(o, dgm) for o in meshes]
        inv = [o.matrix_world.inverted() for o in meshes]

        def gap(p):
            best = 9.0
            for t, o, iv in zip(trees, meshes, inv):
                hit = t.find_nearest(iv @ p)
                if hit[0] is not None:
                    best = min(best, ((o.matrix_world @ hit[0]) - p).length)
            return best

        gaps = [gap(p) for p in co[::3]]
        xs, ys = [p.x for p in co], [p.y for p in co]
        report["metrics"].update({
            "radial_max_m": round(max(rad), 3), "radial_p99_m": round(pct(rad, 99), 3),
            "radial_basis": "horizontal offset from the nearest point of the posed pelvis-head bone chain" if core_d
            else "horizontal distance from the collider centroid axis",
            "bbox_xy_m": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)],
            "lowest_cloth_z_m": round(min(p.z for p in co) - feet_z, 3),
            "gap_p50_m": round(pct(gaps, 50), 3), "gap_p75_m": round(pct(gaps, 75), 3),
            "gap_p95_m": round(pct(gaps, 95), 3)})
        report["checks"]["hem_median_le_gate"] = report["metrics"]["hem_z_p50_m"] <= a.hem_gate
        report["checks"]["radial_max_le_gate"] = report["metrics"]["radial_max_m"] <= a.radial_gate
        report["checks"]["no_balloon_bbox"] = max(report["metrics"]["bbox_xy_m"]) <= a.balloon_gate
        report["metrics"]["gap_p75_le_gap_gate_INFO"] = report["metrics"]["gap_p75_m"] <= a.gap_gate
        report["checks"]["no_vertex_below_feet"] = min(p.z for p in co) > feet_z - 0.01
    else:
        xs, ys, zs = [p.x for p in co], [p.y for p in co], [p.z for p in co]
        report["metrics"] = {"footprint_x_m": round(pct(xs, 95) - pct(xs, 5), 3),
                             "footprint_y_m": round(pct(ys, 95) - pct(ys, 5), 3),
                             "height_p95_m": round(pct(zs, 95), 3), "height_max_m": round(max(zs), 3)}
        report["checks"]["pile_settled_low"] = report["metrics"]["height_max_m"] < a.mound_height + 1.0
    report["checks"]["finite"] = all(math.isfinite(c) for p in co for c in p)

    for poly in settled.data.polygons:
        poly.use_smooth = True
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
                                 mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)   # FACE = per-face smooth flags
        report["fbx"] = str(stem) + ".fbx"
    if skin:
        report["skin_fbx"] = skin_and_export(a, scene, settled, skin, stem, report)
    if a.export_abc:
        for o in bpy.context.view_layer.objects:
            o.select_set(o is cloth_obj)
        bpy.ops.wm.alembic_export(filepath=str(stem) + ".abc", start=1, end=a.frames, selected=True,
                                  uvs=True, normals=True, face_sets=False)
        report["abc"] = str(stem) + ".abc"
    if a.render:
        scene.render.engine = "BLENDER_WORKBENCH"
        if a.textured:
            report["render_engine"] = textured_setup(scene, settled, [o for o in meshes if not o.name.startswith("TorsoProxy")]
                                                     if a.mode in ("drape", "skin") else [], feet_z)
        for o in bpy.data.objects:
            if o.name.startswith(("HipProxy", "TorsoProxy", "GroundCollider")):
                o.hide_render = True
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
    # drape/skin: the 6 Oct recipe measured on the real Shore01/02 bodies (Docs/Conductor/S3_SACKCLOTH_PLAN §9):
    # Blender-scale vertex mass (0.6 kg) so gravity beats the springs; low compression so it folds instead of
    # standing; the old 13.4 kg/m2 x 4 cm-vertex mass (0.005-0.02 kg) made a stiff 1.1 m wide "boulder".
    soft = {"bend": 1.0, "compression": 5.0, "friction": 5.0, "quality": 12, "air_damping": 1.0, "frames": 300,
            "vertex_mass": 0.6, "tension": 40.0, "shear": 10.0, "self_dist": 0.005, "quad": 0.03}
    hard = {"bend": 2.0, "compression": 4.0, "friction": 8.0, "quality": 20, "air_damping": 1.0, "frames": 120,
            "vertex_mass": 0.0, "tension": 40.0, "shear": 20.0, "self_dist": 0.006, "quad": 0.02}
    for k, v in (hard if a.mode == "pile" else soft).items():
        if getattr(a, k) is None:
            setattr(a, k, v)
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
