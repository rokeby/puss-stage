"""Harness for build_sackcloth.py --mode skin: a synthetic stand-in for the UE body export (Blender 4.4, headless).

    blender -b --factory-startup --python Tools/S3Sackcloth/make_synthetic_rig.py -- <out_dir>

Writes <out_dir>/Synth01/{Synth01_Body,Synth01_Face,Synth01_Anim}.fbx and <out_dir>/export_manifest.json in the SAME
shape as Saved/CodexConductor/s3_shore_export_bodies.py writes, so skin mode can be exercised before the real export.
The rig mimics the MetaHuman names the skin chain uses (root, pelvis, spine_01..05, neck_01/02, head, clavicle_*,
upperarm_*, lowerarm_*, hand_*, thigh_*, calf_*) plus one FACIAL_ bone on the face rig. The anim bends the spine
forward and turns the head, and its armature has DIFFERENT rest proportions from the body (spine 5% longer), the way
metahuman_base_skel differs from a fitted body: copy_pose must still land the head where the anim puts it.
It is a stand-in: it proves the code path and the checks, not the look. FBX files are written at cm scale like UE.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else Path.cwd() / "synth"
FID = "Synth01"
FPS = 30

CHAIN = [("root", None, (0, 0, 0), (0, 0, 0.1)), ("pelvis", "root", (0, 0, 0.95), (0, 0, 1.05)),
         ("spine_01", "pelvis", (0, 0, 1.05), (0, 0, 1.13)), ("spine_02", "spine_01", (0, 0, 1.13), (0, 0, 1.21)),
         ("spine_03", "spine_02", (0, 0, 1.21), (0, 0, 1.29)), ("spine_04", "spine_03", (0, 0, 1.29), (0, 0, 1.37)),
         ("spine_05", "spine_04", (0, 0, 1.37), (0, 0, 1.45)), ("neck_01", "spine_05", (0, 0, 1.45), (0, 0, 1.50)),
         ("neck_02", "neck_01", (0, 0, 1.50), (0, 0, 1.55)), ("head", "neck_02", (0, 0, 1.55), (0, 0, 1.75)),
         ("clavicle_l", "spine_05", (0.03, 0, 1.42), (0.18, 0, 1.43)), ("upperarm_l", "clavicle_l", (0.18, 0, 1.43), (0.22, 0, 1.15)),
         ("lowerarm_l", "upperarm_l", (0.22, 0, 1.15), (0.24, 0, 0.90)), ("hand_l", "lowerarm_l", (0.24, 0, 0.90), (0.25, 0, 0.80)),
         ("clavicle_r", "spine_05", (-0.03, 0, 1.42), (-0.18, 0, 1.43)), ("upperarm_r", "clavicle_r", (-0.18, 0, 1.43), (-0.22, 0, 1.15)),
         ("lowerarm_r", "upperarm_r", (-0.22, 0, 1.15), (-0.24, 0, 0.90)), ("hand_r", "lowerarm_r", (-0.24, 0, 0.90), (-0.25, 0, 0.80)),
         ("thigh_l", "pelvis", (0.1, 0, 0.95), (0.1, 0, 0.5)), ("calf_l", "thigh_l", (0.1, 0, 0.5), (0.1, 0, 0.05)),
         ("thigh_r", "pelvis", (-0.1, 0, 0.95), (-0.1, 0, 0.5)), ("calf_r", "thigh_r", (-0.1, 0, 0.5), (-0.1, 0, 0.05))]


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = FPS


def armature(name, extra=(), spine_scale=1.0):
    data = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    for n, parent, h, t in list(CHAIN) + list(extra):
        b = data.edit_bones.new(n)
        k = spine_scale if n.startswith(("spine", "neck", "head", "clav", "upper", "lower", "hand", "FACIAL")) else 1.0
        lift = (k - 1.0) * 0.45      # stretch everything above the pelvis
        hz = h[2] + (lift if h[2] > 1.0 else 0.0)
        tz = t[2] + (lift if t[2] > 1.0 else 0.0)
        b.head, b.tail = Vector((h[0], h[1], hz)), Vector((t[0], t[1], tz))
        if parent:
            b.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    return ob


def skinned_mesh(name, arm, kind):
    if kind == "body":
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.17, depth=1.5, location=(0, 0, 0.75))
        ob = bpy.context.active_object
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.subdivide(number_cuts=12)
        bpy.ops.object.mode_set(mode="OBJECT")
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(0, 0.01, 1.66))
        ob = bpy.context.active_object
    ob.name = name
    ob.parent = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(o in (ob, arm))
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    return ob


def export(path, objs, anim=False):
    for o in bpy.context.view_layer.objects:
        o.select_set(o in objs)
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={"ARMATURE", "MESH"},
                             add_leaf_bones=False, bake_anim=anim, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False, global_scale=100.0, apply_unit_scale=False)


def main():
    d = OUT / FID
    d.mkdir(parents=True, exist_ok=True)
    clear()
    body_arm = armature("BodyRig")
    export(d / f"{FID}_Body.fbx", [body_arm, skinned_mesh("BodyMesh", body_arm, "body")])
    clear()
    face_arm = armature("FaceRig", extra=[("FACIAL_jaw", "head", (0, 0.05, 1.60), (0, 0.10, 1.58))])
    export(d / f"{FID}_Face.fbx", [face_arm, skinned_mesh("FaceMesh", face_arm, "face")])
    clear()
    anim_arm = armature("AnimRig", spine_scale=1.05)
    anim_arm.animation_data_create()
    act = bpy.data.actions.new("SynthSway")
    anim_arm.animation_data.action = act
    pb = anim_arm.pose.bones
    for bone in ("spine_03", "spine_04", "spine_05", "neck_01", "head"):
        pb[bone].rotation_mode = "XYZ"
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 61
    for f in (1, 31, 61):
        ang = math.radians(12.0) * (f - 1) / 60.0
        for bone in ("spine_03", "spine_04", "spine_05"):
            pb[bone].rotation_euler = (ang, 0, 0)
            pb[bone].keyframe_insert("rotation_euler", frame=f)
        pb["head"].rotation_euler = (ang, 0, math.radians(20.0) * (f - 1) / 60.0)
        pb["head"].keyframe_insert("rotation_euler", frame=f)
    pose_t = 1.0    # seconds = Blender frame 31
    sc.frame_set(31)
    head = anim_arm.matrix_world @ pb["head"].head
    export(d / f"{FID}_Anim.fbx", [anim_arm], anim=True)
    row = {"id": FID, "anim_fps_n_over_len": float(FPS), "pose_source_seconds": pose_t,
           "pose_head_cm": [head.x * 100.0, -head.y * 100.0, head.z * 100.0],
           "body_fbx": {"file": str(d / f"{FID}_Body.fbx")}, "face_fbx": {"file": str(d / f"{FID}_Face.fbx")},
           "anim_fbx": {"file": str(d / f"{FID}_Anim.fbx")}, "note": "SYNTHETIC harness rig, not a shore figure"}
    (OUT / "export_manifest.json").write_text(json.dumps({"run": "synthetic", "figures": [row]}, indent=2),
                                              encoding="utf-8")
    print("SYNTH_RIG_OK|" + str(OUT / "export_manifest.json") + "|head_cm=" + ",".join("%.1f" % c for c in row["pose_head_cm"]))


main()
