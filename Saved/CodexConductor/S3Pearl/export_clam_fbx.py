"""S3 pearl split, step 1: export the Fab "Clam with Pearl V2" meshes, skeleton, animation and textures. READ-ONLY.

Report: Docs/Conductor/S3_PEARL_SPLIT_2026-10-07.md. Gary, 7 Oct: "Surely blender could remove clam from pearl?"

Why an export: the original Fab download (glb/fbx) is not on this machine (searched E:, D:, C:\\Users 7 Oct, see
report), so the only source is the imported content under
/Game/Fab/Clam_with_Pearl_V2_-_Realistic_Scallop_Seashell_with_Gemstone/source/.

What it writes (DerivedAssets/S3Pearl/export/), nothing else:
  Clam_SM.fbx      static mesh   Clam_with_Pearl_Clam_with_Pearl_0          (StaticMeshExporterFBX)
  Clam_SK.fbx      skeletal mesh Clam_with_Pearl_002_Clam_with_Pearl_0       (SkeletalMeshExporterFBX; skeleton
                                                                              travels inside the FBX)
  Clam_Anim.fbx    AnimSequence  source_Anim (if it IS an AnimSequence)      (AnimSequenceExporterFBX)
  source_texture_N.png  the three textures                                    (by extension -> PNG exporter)
  export_manifest.json  paths, sha256, bounds, skeleton bone names, level actor transforms, census before/after

It never loads a LevelSequence (opening one dirties the map: memory ue58-sequencer-read-traps), never saves, never
touches PIE (refuses if PIE/SIE is active), keeps no UE objects at module level, and asserts the dirty-package census
is identical before and after.

API (declaration-proven, D:/Unreal Engine/UE_5.8/Engine/Source):
  UAssetExportTask (Runtime/Engine/Public/AssetExportTask.h), UExporter::RunAssetExportTask
  (Runtime/Engine/Classes/Exporters/Exporter.h); UFbxExportOption Collision (FbxExportOption.h:90),
  LevelOfDetail (:86), bExportPreviewMesh (:107); UStaticMeshExporterFBX (StaticMeshExporterFBX.h:16),
  USkeletalMeshExporterFBX (SkeletalMeshExporterFBX.h:16), UAnimSequenceExporterFBX (AnimSequenceExporterFBX.h:16).
  The same task/option pattern exported 18 figure FBXs on 6 Oct (measured: Saved/CodexConductor/
  s3_shore_export_bodies.py, DerivedAssets/S3Sackcloth/bodies/export_manifest.json run 20261006-133132).

Marker: S3PEARL_EXPORT_OK|run=<id>|files=<n>|census=<json>|manifest=<path>
        S3PEARL_EXPORT_FAILED|run=<id>|reason=<...>   (any refusal or failed assertion)
"""
import datetime
import hashlib
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FAB = "/Game/Fab/Clam_with_Pearl_V2_-_Realistic_Scallop_Seashell_with_Gemstone/source"
STATIC = FAB + "/StaticMeshes/Clam_with_Pearl_Clam_with_Pearl_0"
SKELETAL = FAB + "/SkeletalMeshes/Clam_with_Pearl_002_Clam_with_Pearl_0"
SKELETON = FAB + "/SkeletalMeshes/Clam_with_Pearl_002_Clam_with_Pearl_0_Skeleton"
ANIM = FAB + "/SkeletalMeshes/source_Anim"
MATERIAL = FAB + "/Materials/Clam_with_Pearl"
TEXTURES = [FAB + "/Textures/source_texture_%d" % i for i in range(3)]
ACTOR_LABELS = ["Clam_with_Pearl_Clam_with_Pearl_0", "source_Anim", "Clam_Pedastal"]
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(PROJECT, "DerivedAssets", "S3Pearl", "export")
MANIFEST = os.path.join(OUT, "export_manifest.json")


def census():
    def names(packages):
        return sorted(str(p.get_name()).split(".", 1)[0] for p in packages)
    return {"content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fbx_options(preview_mesh):
    o = unreal.FbxExportOption()
    wanted = {"ascii": False, "force_front_x_axis": False, "vertex_color": True, "level_of_detail": False,
              "collision": False, "export_morph_targets": False, "export_preview_mesh": preview_mesh,
              "map_skeletal_motion_to_root": False, "export_local_time": True}
    for k, v in wanted.items():
        o.set_editor_property(k, v)
    got = {k: bool(o.get_editor_property(k)) for k in wanted}   # setters can lie: gate on the read-back
    if got != wanted:
        raise RuntimeError("FBX_OPTION_READBACK|wanted=%s|got=%s" % (wanted, got))
    return o, got


def export(obj, filename, exporter_class_name, options, fbx=True):
    task = unreal.AssetExportTask()
    task.set_editor_property("object", obj)
    task.set_editor_property("filename", filename)
    task.set_editor_property("automated", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("selected", False)
    if options is not None:
        task.set_editor_property("options", options)
    cls = getattr(unreal, exporter_class_name, None) if exporter_class_name else None
    if exporter_class_name and cls is None:
        raise RuntimeError("EXPORTER_NOT_EXPOSED|" + exporter_class_name)
    if cls is not None:
        task.set_editor_property("exporter", cls())
    ok = unreal.Exporter.run_asset_export_task(task)
    errors = [str(e) for e in task.get_editor_property("errors")]
    if not ok or errors or not os.path.isfile(filename) or os.path.getsize(filename) < 1024:
        raise RuntimeError("EXPORT_FAILED|%s|ok=%s|errors=%s|exists=%s"
                           % (filename, ok, errors, os.path.isfile(filename)))
    with open(filename, "rb") as f:
        head = f.read(20)
    if fbx and not head.startswith(b"Kaydara FBX Binary"):
        raise RuntimeError("NOT_BINARY_FBX|%s|%r" % (filename, head))
    if not fbx and not head.startswith(b"\x89PNG"):
        raise RuntimeError("NOT_PNG|%s|%r" % (filename, head))
    return {"file": filename.replace("\\", "/"), "bytes": os.path.getsize(filename), "sha256": sha256(filename),
            "exporter": exporter_class_name or "by-extension"}


def load(path, cls):
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        raise RuntimeError("ASSET_MISSING|" + path)
    obj = unreal.load_asset(path)
    if obj is None or not isinstance(obj, cls):
        raise RuntimeError("ASSET_CLASS|%s|%s" % (path, None if obj is None else obj.get_class().get_name()))
    return obj


def xform(t):
    r = t.rotation.rotator()
    return {"location_cm": list(t.translation.to_tuple()), "rotation_rpy": [r.roll, r.pitch, r.yaw],
            "scale": list(t.scale3d.to_tuple())}


def bounds_of(mesh):
    b = mesh.get_bounds()
    return {"origin_cm": list(b.origin.to_tuple()), "extent_cm": list(b.box_extent.to_tuple()),
            "sphere_radius_cm": float(b.sphere_radius)}


def actor_rows(world):
    rows = {}
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    for a in actors:
        label = str(a.get_actor_label())
        if label in ACTOR_LABELS:
            comps = []
            for c in a.get_components_by_class(unreal.PrimitiveComponent):
                row = {"name": str(c.get_name()), "class": str(c.get_class().get_name()),
                       "world": xform(c.get_world_transform())}
                if isinstance(c, unreal.StaticMeshComponent):
                    m = c.get_editor_property("static_mesh")
                    row["mesh"] = m.get_path_name() if m else None
                if isinstance(c, unreal.SkeletalMeshComponent):
                    m = c.get_skeletal_mesh_asset()
                    row["mesh"] = m.get_path_name() if m else None
                comps.append(row)
            rows.setdefault(label, []).append({"path": a.get_path_name(), "class": str(a.get_class().get_name()),
                                               "world": xform(a.get_actor_transform()), "components": comps})
    return rows


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
            raise RuntimeError("WRONG_WORLD")
        if editor.get_game_world() is not None:
            raise RuntimeError("PIE_OR_SIE_ACTIVE")          # never end PIE: refuse instead
        before = census()
        os.makedirs(OUT, exist_ok=True)

        sm = load(STATIC, unreal.StaticMesh)
        sk = load(SKELETAL, unreal.SkeletalMesh)
        skel = load(SKELETON, unreal.Skeleton)
        if sk.get_editor_property("skeleton") != skel:
            raise RuntimeError("SKELETON_NOT_EXPECTED|%s" % sk.get_editor_property("skeleton").get_path_name())
        anim = unreal.load_asset(ANIM) if unreal.EditorAssetLibrary.does_asset_exist(ANIM) else None
        mat = load(MATERIAL, unreal.MaterialInterface)

        mesh_opt, mesh_rb = fbx_options(False)
        anim_opt, _ = fbx_options(False)
        files = {}
        files["static"] = export(sm, os.path.join(OUT, "Clam_SM.fbx"), "StaticMeshExporterFBX", mesh_opt)
        files["skeletal"] = export(sk, os.path.join(OUT, "Clam_SK.fbx"), "SkeletalMeshExporterFBX", mesh_opt)
        anim_info = {"path": ANIM, "class": None if anim is None else str(anim.get_class().get_name())}
        if isinstance(anim, unreal.AnimSequence):
            if anim.get_editor_property("skeleton") != skel:
                raise RuntimeError("ANIM_SKELETON_MISMATCH")
            anim_info["frames"] = int(unreal.AnimationLibrary.get_num_frames(anim))
            anim_info["seconds"] = float(unreal.AnimationLibrary.get_sequence_length(anim))
            files["anim"] = export(anim, os.path.join(OUT, "Clam_Anim.fbx"), "AnimSequenceExporterFBX", anim_opt)
        for tp in TEXTURES:
            tex = load(tp, unreal.Texture2D)
            name = tp.rsplit("/", 1)[-1]
            files[name] = export(tex, os.path.join(OUT, name + ".png"), None, None, fbx=False)
            files[name]["size"] = [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]
            files[name]["srgb"] = bool(tex.get_editor_property("srgb"))

        used = unreal.MaterialEditingLibrary.get_used_textures(mat)
        info = {
            "static_mesh": {"path": STATIC, "bounds": bounds_of(sm), "lods": int(sm.get_num_lods()),
                            "materials": [str(m.get_editor_property("material_slot_name"))
                                          for m in sm.get_editor_property("static_materials")]},
            "skeletal_mesh": {"path": SKELETAL, "bounds": bounds_of(sk),
                              "materials": [str(m.get_editor_property("material_slot_name"))
                                            for m in sk.get_editor_property("materials")]},
            "skeleton": {"path": SKELETON},
            "anim": anim_info,
            "material": {"path": MATERIAL, "class": str(mat.get_class().get_name()),
                         "used_textures": sorted(t.get_path_name() for t in used)},
        }
        actors = actor_rows(world)
        after = census()
        if after != before:
            raise RuntimeError("CENSUS_CHANGED|before=%s|after=%s" % (json.dumps(before), json.dumps(after)))
        manifest = {"run": run, "world": EXPECTED_WORLD, "mode": "read_only_export", "fbx_options_readback": mesh_rb,
                    "census_before": before, "census_after": after, "files": files, "assets": info,
                    "level_actors": actors}
        with open(MANIFEST, "w", encoding="utf-8") as h:
            json.dump(manifest, h, indent=2, sort_keys=True)
        unreal.log("S3PEARL_EXPORT_OK|run=%s|files=%d|census=%s|manifest=%s"
                   % (run, len(files), json.dumps(after, separators=(",", ":")), MANIFEST.replace("\\", "/")))
    except Exception as exc:   # noqa: BLE001 - one failure marker; nothing written to Content, nothing to roll back
        unreal.log_error("S3PEARL_EXPORT_FAILED|run=%s|reason=%s" % (run, str(exc).replace("\n", " ")))


main()
