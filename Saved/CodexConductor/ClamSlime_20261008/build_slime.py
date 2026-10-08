"""HEADLESS BLENDER 4.4 (CPU only, NO rendering): build SK_PearlClam_Slime (ligament + mucus strands), its skeleton,
weights and the AnimSequence A_PearlClam_SlimeOpen from the design file; export the FBX files; re-import them and check
the round trip.

    python slime_design.py                                     (system Python: numpy + scipy -> build/slime_design.npz)
    "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup --python build_slime.py

Inputs:  build/slime_design.npz (verts, faces, slots, UVs, dense weights, bone rest matrices, per-frame bone pose
         matrices for anim frames 0..4794, all Blender cm).  Blender's bundled Python has no scipy, so the design (which
         measures against the shells with scipy) is made outside and only READ here.
Outputs (build/):
  SK_PearlClam_Slime.fbx        skeletal mesh + skeleton, NO animation  (UE IMPORT, part "mesh")
  A_PearlClam_SlimeOpen.fbx     same armature + mesh + the baked action (UE IMPORT, part "anim": animation only)
  slime_build.blend             the rig scene (render_slime_previews.py renders from it LATER: GPU paused 8 Oct)
  slime_build.npz / .json       rest + evaluated vertices (rig and FBX re-import) at sample frames, the re-imported
                                lid angle at EVERY frame, bone table, checks; validate_slime.py reads them.
Marker: BUILD_SLIME_OK|... or BUILD_SLIME_FAILED|<reason> (stdout).

FBX CONVENTION = the clam exports [meas: SM_PearlClam_Bottom/Lid.fbx parsed 8 Oct: UpAxis 1 (Y), FrontAxis 2,
CoordAxis 0, UnitScaleFactor 100, Model Lcl Rotation (-90,0,0)] = Blender's FBX exporter defaults on a metre scene:
axis_forward -Z, axis_up Y on a metre scene, apply_unit_scale True + apply_scale_options FBX_SCALE_UNITS (raw metres, UnitScaleFactor 100, as the clam).  The scene here is in METRES (Blender units), design math in cm.
Armature object "Armature" (FBX Null) holding the bones (root; every other bone is root's child); add_leaf_bones
False; primary/secondary bone axis Y/X (no bone-axis correction, so the lid bone's rest rotation stays identity).
"""
import json
import math
import os
import sys
import time
import traceback

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = "E:/PussStage/Saved/CodexConductor/ClamSlime_20261008/"
sys.path.insert(0, HERE)
import slime_design as d         # noqa: E402  (numpy only here)

OUT = HERE + "build/"
FBX_MESH = OUT + d.MESH_NAME + ".fbx"
FBX_ANIM = OUT + d.ANIM_NAME + ".fbx"
BLEND = OUT + "slime_build.blend"
NPZ = OUT + "slime_build.npz"
JSON = OUT + "slime_build.json"
CM = 0.01


def make_material(name, rgba, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = rough
    m.diffuse_color = rgba
    return m


def build_rig(A):
    """Bones from the design's rest matrices (armature space, cm -> m).  Every bone's parent is root."""
    arm_data = bpy.data.armatures.new(d.ARMATURE_OBJECT)
    arm = bpy.data.objects.new(d.ARMATURE_OBJECT, arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    made = {}
    for j, b in enumerate(A["bones"]):
        R = np.array(A["rest"][j], float)
        c, Y, Z = R[:3, 3] * CM, R[:3, 1], R[:3, 2]
        ln = 0.05 if b in ("root", "lid") else (0.03 if b.startswith("lig_") else 0.005)
        e = eb.new(b)
        e.head, e.tail = tuple(c), tuple(c + Y * ln)
        e.align_roll(Vector(tuple(Z)))
        made[b] = e
    for b, e in made.items():
        if b != "root":
            e.parent, e.use_connect = made["root"], False
    bpy.ops.object.mode_set(mode="OBJECT")
    worst = 0.0
    for j, b in enumerate(A["bones"]):
        want = np.array(A["rest"][j], float)
        want[:3, 3] *= CM
        worst = max(worst, float(np.abs(np.array(arm_data.bones[b].matrix_local) - want).max()))
    return arm, worst


def build_mesh(A, arm):
    me = bpy.data.meshes.new(d.MESH_NAME)
    me.from_pydata([tuple(v * CM) for v in A["verts"]], [], A["faces"])
    me.update()
    ob = bpy.data.objects.new(d.MESH_NAME, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(make_material(d.SLOT_LIGAMENT, (0.09, 0.055, 0.03, 1.0), 0.2))
    me.materials.append(make_material(d.SLOT_SLIME, (0.62, 0.68, 0.6, 1.0), 0.05))
    me.polygons.foreach_set("material_index", [int(x) for x in A["face_mat"]])
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    uvl = me.uv_layers.new(name="UVMap")
    loop_v = np.zeros(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", loop_v)
    uvl.data.foreach_set("uv", A["uv"][loop_v].astype(np.float32).ravel())
    W = A["weights"]
    for j, b in enumerate(A["bones"]):
        g = ob.vertex_groups.new(name=b)
        for vi in np.nonzero(W[:, j] > 0)[0]:
            g.add([int(vi)], float(W[vi, j]), "REPLACE")
    ob.parent = arm
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    return ob


def build_action(A, arm):
    """One action: every bone keyed at every frame from the design's pose matrices (basis = rest^-1 pose)."""
    act = bpy.data.actions.new(d.ANIM_NAME)
    poses = A["poses"]
    n = poses.shape[0]
    fr = np.arange(n, dtype=np.float64)
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    for j, b in enumerate(A["bones"]):
        R = np.array(A["rest"][j], float)
        R[:3, 3] *= CM
        Rinv = np.linalg.inv(R)
        locs, quats, scs = np.zeros((n, 3)), np.zeros((n, 4)), np.ones((n, 3))
        prev = None
        for i in range(n):
            P = np.array(poses[i, j], float)
            P[:3, 3] *= CM
            B = Rinv @ P
            sc = np.linalg.norm(B[:3, :3], axis=0)
            q = Matrix([list(r) for r in (B[:3, :3] / sc)]).to_quaternion()
            q = np.array([q.w, q.x, q.y, q.z])
            if prev is not None and np.dot(q, prev) < 0:
                q = -q                                   # quaternion hemisphere continuity
            prev = q
            locs[i], quats[i], scs[i] = B[:3, 3], q, sc
        for path, arr in (("location", locs), ("rotation_quaternion", quats), ("scale", scs)):
            for k in range(arr.shape[1]):
                fc = act.fcurves.new('pose.bones["%s"].%s' % (b, path), index=k, action_group=b)
                fc.keyframe_points.add(n)
                co = np.empty(2 * n)
                co[0::2], co[1::2] = fr, arr[:, k]
                fc.keyframe_points.foreach_set("co", co)
                fc.update()
    # assign AFTER the curves exist; Blender 4.4 slotted actions: bind the slot the legacy fcurves API created
    ad = arm.animation_data_create()
    ad.action = act
    if hasattr(ad, "action_slot") and getattr(ad, "action_slot", None) is None and len(getattr(act, "slots", [])):
        ad.action_slot = act.slots[0]
    return act


def evaluated_cm(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    mw = np.array(ev.matrix_world)
    ev.to_mesh_clear()
    v = co.reshape(-1, 3)
    v = v @ mw[:3, :3].T + mw[:3, 3]
    return v / CM


def lid_angle_from_pose(arm):
    M = np.array(arm.matrix_world) @ np.array(arm.pose.bones["lid"].matrix)
    # the lid bone's world rotation is a rotation about +X by -deg  ->  deg = -atan2(R[2,1], R[1,1])
    return -math.degrees(math.atan2(M[2, 1], M[1, 1]))


def export(path, arm, ob, anim):
    for o in bpy.context.scene.objects:
        o.select_set(o in (arm, ob))
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"ARMATURE", "MESH"}, add_leaf_bones=False,
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0, axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE",
        use_armature_deform_only=False, armature_nodetype="NULL", primary_bone_axis="Y", secondary_bone_axis="X",
        use_mesh_modifiers=False, bake_anim=anim, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True, bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0)


def fbx_summary(path):
    """Global axis settings + node names from the written binary FBX (same parser the clam measurements used)."""
    import struct
    sys.path.insert(0, HERE + "../S3Millstone")
    import fbx_top_measure as ftm
    meta = ftm.parse(path)
    with open(path, "rb") as f:
        buf = memoryview(f.read())
    wide = struct.unpack_from("<I", buf, 23)[0] >= 7500
    models, curves, stacks = [], 0, []
    for name, _p, (a, b) in ftm._nodes(buf, 27, len(buf), wide):
        if name != "Objects":
            continue
        for n2, p2, _r in ftm._nodes(buf, a, b, wide):
            if n2 == "Model" and len(p2) > 2:
                models.append((p2[1].split(b"\x00")[0].decode("ascii", "replace"), p2[2].decode("ascii", "replace")))
            elif n2 == "AnimationCurve":
                curves += 1
            elif n2 == "AnimationStack":
                stacks.append(p2[1].split(b"\x00")[0].decode("ascii", "replace"))
    return {"global": meta["global"], "models": models, "anim_curves": curves, "anim_stacks": stacks,
            "bytes": os.path.getsize(path)}


def reimport(path, sample, all_frames):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = d.FPS, 1.0
    bpy.ops.import_scene.fbx(filepath=path, ignore_leaf_bones=False, automatic_bone_orientation=False, anim_offset=0.0,
                             use_anim=True)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    assert len(arms) == 1 and len(meshes) == 1, (len(arms), len(meshes))
    arm, ob = arms[0], meshes[0]
    out = {"bones": {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones},
           "armature_object": arm.name, "mesh_object": ob.name,
           "materials": [s.material.name if s.material else None for s in ob.material_slots],
           "action": arm.animation_data.action.name if arm.animation_data and arm.animation_data.action else None}
    if out["action"]:
        out["action_range"] = list(arm.animation_data.action.frame_range)
    verts = []
    for f in sample:
        sc.frame_set(int(f))
        verts.append(evaluated_cm(ob))
    lid = []
    if all_frames:
        ob.hide_viewport = True
        for f in range(all_frames):
            sc.frame_set(f)
            lid.append(lid_angle_from_pose(arm))
    return out, np.asarray(verts), np.asarray(lid)


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    checks = {}
    A = d.load_design()
    angles = A["angles"]
    bf = [int(x) for x in A["break_frames"]]
    checks["design_bones_are_all_bones"] = A["bones"] == d.all_bones()
    checks["design_frames"] = A["poses"].shape[0] == d.ANIM_LAST + 1
    print("BUILD_SLIME|design loaded verts=%d faces=%d bones=%d frames=%d" % (
        len(A["verts"]), len(A["faces"]), len(A["bones"]), len(angles)))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length = "METRIC", 1.0
    sc.render.fps, sc.render.fps_base = d.FPS, 1.0
    sc.frame_start, sc.frame_end = 0, d.ANIM_LAST
    arm, rest_err = build_rig(A)
    checks["bone_rest_matrices_equal_design"] = rest_err < 1e-5
    ob = build_mesh(A, arm)
    checks["vertex_count"] = len(ob.data.vertices) == len(A["verts"])
    build_action(A, arm)
    print("BUILD_SLIME|rig+action %.1fs" % (time.time() - t0))

    sample = sorted(set([0, 50, 150, 220, 300, 600, d.ANIM_LAST] + [b - 1 for b in bf] + bf +
                        [b + 12 for b in bf] + [b + 48 for b in bf]))
    rig, lid_rig = [], []
    for f in sample:
        sc.frame_set(f)
        rig.append(evaluated_cm(ob))
        lid_rig.append(lid_angle_from_pose(arm))
    checks["rig_lid_angle_matches_curve"] = bool(max(abs(a - angles[f]) for a, f in zip(lid_rig, sample)) < 1e-4)
    sc.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    arm.data.pose_position = "REST"          # the mesh FBX carries the REST pose in its nodes as well as its bind pose
    bpy.context.view_layer.update()
    export(FBX_MESH, arm, ob, anim=False)
    arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    export(FBX_ANIM, arm, ob, anim=True)
    print("BUILD_SLIME|export %.1fs" % (time.time() - t0))

    sm, sa = fbx_summary(FBX_MESH), fbx_summary(FBX_ANIM)
    want_global = {"UpAxis": 1, "UpAxisSign": 1, "FrontAxis": 2, "FrontAxisSign": 1, "CoordAxis": 0,
                   "CoordAxisSign": 1, "UnitScaleFactor": 100.0}
    for nm, s in (("mesh", sm), ("anim", sa)):
        checks["fbx_%s_axes_like_clam" % nm] = all(s["global"].get(k) == v for k, v in want_global.items())
        names = [m[0] for m in s["models"]]
        checks["fbx_%s_has_every_bone" % nm] = set(d.all_bones()) <= set(names)
        checks["fbx_%s_armature_null" % nm] = (d.ARMATURE_OBJECT, "Null") in s["models"]
    checks["fbx_mesh_has_no_anim_curves"] = sm["anim_curves"] == 0
    checks["fbx_anim_has_curves"] = sa["anim_curves"] > 0

    info_m, rv_m, _ = reimport(FBX_MESH, [0], 0)
    want_tree = {b: (None if b == "root" else "root") for b in d.all_bones()}
    checks["reimport_mesh_bones_and_parents"] = info_m["bones"] == want_tree
    checks["reimport_mesh_materials"] = info_m["materials"] == [d.SLOT_LIGAMENT, d.SLOT_SLIME]
    rest_rt = float(np.abs(rv_m[0] - A["verts"]).max())
    checks["reimport_mesh_rest_equal_cm"] = rest_rt < 1e-3
    info_a, rv_a, lid_a = reimport(FBX_ANIM, sample, d.ANIM_LAST + 1)
    checks["reimport_anim_bones_and_parents"] = info_a["bones"] == want_tree
    checks["reimport_anim_frame_range"] = info_a.get("action_range") == [0.0, float(d.ANIM_LAST)]
    rt = float(np.abs(rv_a - np.asarray(rig)).max())
    checks["reimport_anim_vertices_within_0p02cm_of_rig"] = rt < 0.02
    lid_err = float(np.abs(lid_a - angles).max())
    checks["reimport_lid_angle_within_1e-3_deg"] = lid_err < 1e-3

    np.savez_compressed(NPZ, rest_cm=A["verts"], frames=np.array(sample), rig_cm=np.asarray(rig),
                        reimport_cm=rv_a, reimport_lid_deg=lid_a, angles=angles)
    rep = {"tool": "build_slime", "blender": bpy.app.version_string, "seconds": round(time.time() - t0, 1),
           "fbx_mesh": FBX_MESH, "fbx_anim": FBX_ANIM, "blend": BLEND,
           "fbx_mesh_summary": dict(sm, models=len(sm["models"])), "fbx_anim_summary": dict(sa, models=len(sa["models"])),
           "bones": A["bones"], "vertices": int(len(A["verts"])), "faces": int(len(A["faces"])),
           "anim": {"name": d.ANIM_NAME, "frames": int(len(angles)), "last_frame": d.ANIM_LAST, "fps": d.FPS,
                    "scene_start_frame": d.OPEN_START, "scene_end_frame_exclusive": d.OPEN_START + d.ANIM_LAST,
                    "open_frames": [0, d.OPEN_END - d.OPEN_START], "open_deg": d.OPEN_DEG},
           "strand_breaks": [{"strand": i, "x_cm": s["x"], "break_deg": s["break_deg"], "anim_frame": bf[i],
                              "scene_frame": d.OPEN_START + bf[i], "angle_at_break_frame": round(float(angles[bf[i]]), 4)}
                             for i, s in enumerate(d.STRANDS)],
           "reimport": {"mesh": info_m, "anim": info_a}, "max_rest_reimport_cm": rest_rt,
           "max_rig_vs_reimport_cm": rt, "max_reimport_lid_err_deg": lid_err, "bone_rest_err_m": rest_err,
           "sample_frames": sample, "checks": checks}
    with open(JSON, "w", encoding="utf-8") as h:
        json.dump(rep, h, indent=1, default=str)
    bad = [k for k, v in checks.items() if not v]
    if bad:
        print("BUILD_SLIME_FAILED|checks=%s|json=%s" % (bad, JSON))
    else:
        print("BUILD_SLIME_OK|verts=%d|bones=%d|frames=%d|breaks_scene=%s|roundtrip_cm=%.5f|lid_err_deg=%.2e|%.0fs" % (
            len(A["verts"]), len(A["bones"]), len(angles), [d.OPEN_START + b for b in bf], rt, lid_err,
            time.time() - t0))


try:
    main()
except Exception:  # noqa: BLE001
    print("BUILD_SLIME_FAILED|" + traceback.format_exc().replace("\n", " | "))
