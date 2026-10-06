"""Re-export a sack _SK.fbx so its bone tree starts at a "root" bone, like UE's own MetaHuman export (Blender 4.4).

Why (measured 6 Oct, Saved/CodexConductor/s3_sack_install.py fbx_skeleton_summary on the finals):
  * UE's body export  bodies/<id>/<id>_Body.fbx : Z-up, cm; node "root" (FBX type Root, identity) -> "pelvis" ...
  * the sack finals   final_20261006/<id>_SK.fbx: Y-up, cm; Null node "Armature" (Lcl Rotation -90 X) -> "pelvis"
    (341 LimbNodes, no "root"). build_sackcloth.py named the armature object "Armature" on purpose so UE would not
    make it a bone [its own note: inferred].
  The figures' skeleton (metahuman_base_skel) is rooted at "root". A mesh whose bone tree is rooted at "pelvis"
  does not have the skeleton's parent chain, so importing it onto that skeleton is expected to be refused or to mint
  a NEW skeleton [inferred: USkeleton's compatibility .cpp is not in the UE 5.8 install]. This tool removes the
  question: same mesh, same weights, same bind, but the armature node is named "root", exported as an FBX Root
  node, Z-up / -Y forward (UE's own axis convention), so it matches the body export node for node.

Nothing is simulated again; the file is only re-written. The original _SK.fbx is never overwritten.

    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b --factory-startup --python ^
        Tools/S3Sackcloth/reexport_sk_root.py -- --src <id>_SK.fbx [--dst <id>_SK_root.fbx]

Checks (written to <dst>.json; the marker REEXPORT_OK only if every check passes):
  * the re-imported armature has the same 341 bone names and parents as the source;
  * vertex count, polygon count, UV layer names, material slot names and vertex-group names are identical;
  * every vertex lands within 0.1 mm of the source (world space, same order) and every weight within 1e-5;
  * every bone head lands within 0.1 mm of the source (world space);
  * bbox_world_m / head_world_m are recorded for the UE bounds gate;
  * the written FBX has a node "root" of FBX type Root whose child is "pelvis", UpAxis Z, unit cm
    (parsed from the binary file by s3_sack_install.fbx_skeleton_summary, the same parser the UE tool gates on).
"""
import argparse
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
INSTALL = os.path.join(ROOT, "Saved", "CodexConductor", "s3_sack_install.py")


def _install_module():
    spec = importlib.util.spec_from_file_location("_sack_install_pure", INSTALL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # unreal is absent in Blender: the module only defines pure helpers
    return mod


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True)
    p.add_argument("--dst", default="")
    a = p.parse_args(argv)
    if not a.dst:
        stem = a.src[:-len("_SK.fbx")] if a.src.endswith("_SK.fbx") else a.src[:-4]
        a.dst = stem + "_SK_root.fbx"
    if os.path.abspath(a.dst) == os.path.abspath(a.src):
        raise SystemExit("REEXPORT_FAILED|dst equals src (never overwrite the final)")
    return a


def _snapshot(bpy):
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if len(arms) != 1 or len(meshes) != 1:
        raise SystemExit("REEXPORT_FAILED|expected one armature and one mesh, got %d/%d" % (len(arms), len(meshes)))
    arm, mesh = arms[0], meshes[0]
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(dg).data
    mw = mesh.matrix_world
    names = {g.index: g.name for g in mesh.vertex_groups}
    return {
        "arm": arm, "mesh": mesh,
        "bones": {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones},
        "heads": {b.name: tuple(arm.matrix_world @ b.head_local) for b in arm.data.bones},
        "verts": [tuple(mw @ v.co) for v in ev.vertices],
        "polys": len(mesh.data.polygons),
        "uv": [u.name for u in mesh.data.uv_layers],
        "mats": [s.material.name if s.material else None for s in mesh.material_slots],
        "groups": sorted(g.name for g in mesh.vertex_groups),
        "weights": [{names[e.group]: e.weight for e in v.groups} for v in mesh.data.vertices],
    }


def main():
    import bpy
    a = _args()
    inst = _install_module()
    report = {"src": a.src, "dst": a.dst, "checks": {}}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=a.src, ignore_leaf_bones=False)
    src = _snapshot(bpy)
    arm, mesh = src["arm"], src["mesh"]
    report["source_armature_object"] = arm.name
    arm.name = "root"
    arm.data.name = "root"
    for o in bpy.data.objects:
        o.select_set(o in (arm, mesh))
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(filepath=a.dst, use_selection=True, object_types={"ARMATURE", "MESH"},
                             add_leaf_bones=False, bake_anim=False, apply_unit_scale=True, mesh_smooth_type="FACE",
                             use_armature_deform_only=False, armature_nodetype="ROOT",
                             primary_bone_axis="Y", secondary_bone_axis="X",
                             axis_forward="-Y", axis_up="Z")
    # re-import the written file into a clean scene and compare
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=a.dst, ignore_leaf_bones=False)
    back = _snapshot(bpy)
    c = report["checks"]
    c["bone_names_and_parents_identical"] = back["bones"] == src["bones"]
    c["vertex_count_identical"] = len(back["verts"]) == len(src["verts"])
    c["poly_count_identical"] = back["polys"] == src["polys"]
    c["uv_layers_identical"] = back["uv"] == src["uv"]
    c["material_slots_identical"] = back["mats"] == src["mats"]
    c["vertex_groups_identical"] = back["groups"] == src["groups"]
    dv = max((sum((p - q) ** 2 for p, q in zip(u, v)) ** 0.5 for u, v in zip(src["verts"], back["verts"])),
             default=9.0) if c["vertex_count_identical"] else 9.0
    dw = 0.0
    if c["vertex_count_identical"]:
        for w0, w1 in zip(src["weights"], back["weights"]):
            for k in set(w0) | set(w1):
                dw = max(dw, abs(w0.get(k, 0.0) - w1.get(k, 0.0)))
    dh = max((sum((p - q) ** 2 for p, q in zip(src["heads"][n], back["heads"][n])) ** 0.5
              for n in src["heads"] if n in back["heads"]), default=9.0)
    report["max_vertex_delta_m"], report["max_weight_delta"], report["max_bone_head_delta_m"] = dv, dw, dh
    # Blender world = the body's UE component space with Y negated (source JSON: pose.head_bone_m vs
    # pose.record_head_m_ue_component). s3_sack_install.py gates the UE imported bounds on this box.
    report["bbox_world_m"] = [[min(v[i] for v in src["verts"]) for i in range(3)],
                              [max(v[i] for v in src["verts"]) for i in range(3)]]
    report["head_world_m"] = list(src["heads"].get("head", (None, None, None)))
    c["vertices_within_0p1mm"] = dv <= 1e-4
    c["weights_within_1e-5"] = dw <= 1e-5
    c["bone_heads_within_0p1mm"] = dh <= 1e-4
    summary = inst.fbx_skeleton_summary(a.dst)
    report["fbx_summary"] = summary
    probs = inst.fbx_structure_problems(summary, root_bone="root", first_child="pelvis")
    report["fbx_structure_problems"] = probs
    c["fbx_root_bone_is_root_over_pelvis_zup_cm"] = not probs
    report["ok"] = all(c.values())
    with open(a.dst + ".json", "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    if not report["ok"]:
        print("REEXPORT_FAILED|%s|%s" % (a.dst, [k for k, v in c.items() if not v]))
        sys.exit(1)
    print("REEXPORT_OK|%s|vertex_delta_m=%.2e|bone_delta_m=%.2e" % (a.dst, dv, dh))


if __name__ == "__main__":
    main()
