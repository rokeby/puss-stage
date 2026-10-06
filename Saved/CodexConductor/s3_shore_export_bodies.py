"""S3 sackcloth step 2: export the six shore bodies (mesh + mocap) as FBX for the Blender drape. READ-ONLY.

Plan: Docs/Conductor/S3_SACKCLOTH_PLAN_2026-10-06.md (step 2). Gary, 6 Oct: "Yes, export now".

What it does, per figure (Shore01_M56 .. Shore06_F25):
  - finds the level actor "<id> Clam" (class BP_<id>_Draped_C), reads its Body and Face SkeletalMeshComponents;
  - exports Body mesh, Face mesh and the figure's AnimSequence (the FULL take; its scene section is recorded)
    with AssetExportTask + FbxExportOption to DerivedAssets/S3Sackcloth/bodies/<id>/;
  - writes the representative pose (source seconds + frame) chosen offline from the motion record.
It never loads a LevelSequence (opening/scrubbing sequences dirties the map: memory ue58-sequencer-read-traps), never
saves, and asserts the dirty-package census is identical before and after.

API (declaration-proven, UE 5.8 headers, D:/Unreal Engine/UE_5.8/Engine/Source):
  - UAssetExportTask: Object, Exporter, Filename, bSelected, bReplaceIdentical, bPrompt, bAutomated, Options, Errors
    (Runtime/Engine/Public/AssetExportTask.h:20-65);
  - UExporter::RunAssetExportTask, a static BlueprintCallable (Runtime/Engine/Classes/Exporters/Exporter.h:254-255);
  - UFbxExportOption: bASCII, bForceFrontXAxis, VertexColor, LevelOfDetail, bExportMorphTargets, bExportPreviewMesh,
    MapSkeletalMotionToRoot, bExportLocalTime (Editor/UnrealEd/Classes/Exporters/FbxExportOption.h:69-115);
  - USkeletalMeshExporterFBX / UAnimSequenceExporterFBX exist (Editor/UnrealEd/Classes/Exporters/).
  The .cpp files are NOT in the install, so what the exporter writes (bind pose, units, axis) is INFERRED; the
  Blender side re-measures it (build_sackcloth.py --mode skin checks).

Why not a posed mesh directly: no exporter in the headers writes a skeletal mesh in an animated pose (the skeletal
mesh exporter writes the reference pose; the anim exporter writes skeleton + curves). So Blender poses it: import the
mesh FBX, import the anim FBX onto the same bone names, go to the pose frame, evaluate (build_sackcloth.py skin mode).

Marker: S3_SHORE_EXPORT_OK|run=<id>|figures=6|files=18..24 (24 with the _DNA bodies)|census=... (or S3_SHORE_EXPORT_FAILED|run=..|reason=..).
"""
import datetime
import hashlib
import json
import os
import statistics

try:
    import unreal
except ModuleNotFoundError:   # offline: python s3_shore_export_bodies.py  -> prints the pose picks only
    unreal = None

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FIGURES = ["Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore05_M53", "Shore06_F25"]
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
MOTION_RECORD = os.path.join(PROJECT, "Saved", "CodexMocap", "shore_gentle_motion_selection.json")
INTEGRATION_RECORD = os.path.join(PROJECT, "Saved", "CodexMocap", "shore_clam_integration.json")
OUT_ROOT = os.path.join(PROJECT, "DerivedAssets", "S3Sackcloth", "bodies")
MANIFEST = os.path.join(OUT_ROOT, "export_manifest.json")


# ------------------------------------------------------------------------- offline part (pure Python)
def pose_picks():
    """Representative frame per figure, from the motion record only (no Sequencer reads).

    The scene plays [start, start + duration] of the source take (record: shore_gentle_motion_selection.json,
    cross-checked against shore_clam_integration.json). Pick the 0.5 s sample INSIDE that window whose head height
    is closest to the window's median head height (a typical, not extreme, pose); ties -> nearer the window middle.
    """
    with open(MOTION_RECORD, encoding="utf-8") as h:
        motion = json.load(h)
    with open(INTEGRATION_RECORD, encoding="utf-8") as h:
        integ = {c["id"]: c for c in json.load(h)["characters"]}
    picks = {}
    for c in motion["characters"]:
        fid = c["id"]
        sel = c["selected"]
        start, dur = float(sel["start_seconds"]), float(sel["source_duration_seconds"])
        if abs(float(integ[fid]["source_start_seconds"]) - start) > 1e-6:
            raise RuntimeError("RECORD_MISMATCH|%s|motion start %s vs integration %s"
                               % (fid, start, integ[fid]["source_start_seconds"]))
        window = [s for s in c["source_samples"] if start <= float(s["time"]) <= start + dur]
        if len(window) < 5:
            raise RuntimeError("TOO_FEW_SAMPLES|%s|%d" % (fid, len(window)))
        med = statistics.median(s["bones"]["head"][2] for s in window)
        mid = start + dur / 2.0
        best = min(window, key=lambda s: (abs(s["bones"]["head"][2] - med), abs(float(s["time"]) - mid)))
        picks[fid] = {"animation": c["animation"], "section_start_s": start, "section_source_duration_s": dur,
                      "play_rate": float(sel["play_rate"]), "pose_source_seconds": float(best["time"]),
                      "pose_head_cm": best["bones"]["head"], "window_median_head_z_cm": med,
                      "window_samples": len(window)}
    missing = [f for f in FIGURES if f not in picks]
    if missing:
        raise RuntimeError("FIGURES_MISSING_IN_RECORD|" + ",".join(missing))
    return picks


# ------------------------------------------------------------------------- editor part
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


def fbx_options(export_mesh_with_anim=False):
    o = unreal.FbxExportOption()
    wanted = {"ascii": False, "force_front_x_axis": False, "vertex_color": True, "level_of_detail": False,
              "export_morph_targets": False, "export_preview_mesh": export_mesh_with_anim,
              "map_skeletal_motion_to_root": False, "export_local_time": True}
    for k, v in wanted.items():
        o.set_editor_property(k, v)
    got = {k: bool(o.get_editor_property(k)) for k in wanted}   # setters can lie: gate on the read-back
    if got != wanted:
        raise RuntimeError("FBX_OPTION_READBACK|wanted=%s|got=%s" % (wanted, got))
    return o, got


def export(obj, filename, exporter_class_name, options):
    task = unreal.AssetExportTask()
    task.set_editor_property("object", obj)
    task.set_editor_property("filename", filename)
    task.set_editor_property("automated", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("selected", False)
    task.set_editor_property("options", options)
    cls = getattr(unreal, exporter_class_name, None)   # explicit exporter if Python exposes it; else by extension
    if cls is not None:
        task.set_editor_property("exporter", cls())
    ok = unreal.Exporter.run_asset_export_task(task)
    errors = [str(e) for e in task.get_editor_property("errors")]
    if not ok or errors or not os.path.isfile(filename) or os.path.getsize(filename) < 1024:
        raise RuntimeError("EXPORT_FAILED|%s|ok=%s|errors=%s|exists=%s" % (filename, ok, errors, os.path.isfile(filename)))
    with open(filename, "rb") as f:
        head = f.read(20)
    if not head.startswith(b"Kaydara FBX Binary"):
        raise RuntimeError("NOT_BINARY_FBX|%s|%r" % (filename, head))
    return {"file": filename.replace("\\", "/"), "bytes": os.path.getsize(filename), "sha256": sha256(filename),
            "exporter": exporter_class_name if cls is not None else "by-extension"}


def anim_rate(anim):
    """(frames, seconds, fps) of an AnimSequence; several API spellings tried, each result asserted sane."""
    lib = unreal.AnimationLibrary
    n = int(lib.get_num_frames(anim))
    length = float(lib.get_sequence_length(anim))
    if n <= 1 or length <= 0:
        raise RuntimeError("ANIM_RATE_UNREADABLE|%s|frames=%s|length=%s" % (anim.get_path_name(), n, length))
    fps = n / length   # num frames over length; may be (n-1)/length depending on the key convention: both recorded
    return n, length, fps


def component(actor, name):
    hits = [c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if str(c.get_name()) == name]
    if len(hits) != 1:
        raise RuntimeError("COMPONENT_COUNT|%s|%s|%d" % (actor.get_actor_label(), name, len(hits)))
    return hits[0]


def xform(t):
    return {"location": list(t.translation.to_tuple()), "rotation_rpy": [t.rotation.rotator().roll,
            t.rotation.rotator().pitch, t.rotation.rotator().yaw], "scale": list(t.scale3d.to_tuple())}


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
            raise RuntimeError("WRONG_WORLD")
        if editor.get_game_world() is not None:
            raise RuntimeError("PIE_OR_SIE_ACTIVE")       # never end PIE: refuse instead
        before = census()
        picks = pose_picks()
        index = {}
        for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
            index.setdefault(str(a.get_actor_label()), []).append(a)
        mesh_opt, mesh_opt_rb = fbx_options(False)
        anim_opt, anim_opt_rb = fbx_options(False)
        rows, files = [], 0
        for fid in FIGURES:
            label = fid + " Clam"
            actors = index.get(label, [])
            if len(actors) != 1:
                raise RuntimeError("ACTOR_COUNT|%s|%d" % (label, len(actors)))
            actor = actors[0]
            cls = str(actor.get_class().get_name())
            if cls != "BP_%s_Draped_C" % fid:
                raise RuntimeError("ACTOR_CLASS|%s|%s" % (label, cls))
            body, face = component(actor, "Body"), component(actor, "Face")
            body_mesh, face_mesh = body.get_skeletal_mesh_asset(), face.get_skeletal_mesh_asset()
            anim = unreal.load_asset(picks[fid]["animation"].split(".")[0])
            if anim is None or not isinstance(anim, unreal.AnimSequence):
                raise RuntimeError("ANIM_MISSING|" + picks[fid]["animation"])
            if anim.get_editor_property("skeleton") != body_mesh.get_editor_property("skeleton"):
                raise RuntimeError("SKELETON_MISMATCH|%s" % fid)
            n, length, fps = anim_rate(anim)
            t = picks[fid]["pose_source_seconds"]
            out = os.path.join(OUT_ROOT, fid)
            os.makedirs(out, exist_ok=True)
            row = dict(picks[fid])
            row.update({
                "id": fid, "actor_label": label, "actor_path": actor.get_path_name(),
                "actor_world": xform(actor.get_actor_transform()),
                "body_component_world": xform(body.get_world_transform()),
                "body_mesh": body_mesh.get_path_name(), "face_mesh": face_mesh.get_path_name(),
                "skeleton": body_mesh.get_editor_property("skeleton").get_path_name(),
                "anim_frames": n, "anim_seconds": length, "anim_fps_n_over_len": fps,
                "pose_frame_index": int(round(t * fps)),
                "pose_note": "Blender: frame = action start + pose_source_seconds x the action's fps (set the scene "
                             "fps to anim_fps before the FBX import); verify head bone vs pose_head_cm (cm, component space)",
            })
            row["body_fbx"] = export(body_mesh, os.path.join(out, fid + "_Body.fbx"), "SkeletalMeshExporterFBX", mesh_opt)
            row["face_fbx"] = export(face_mesh, os.path.join(out, fid + "_Face.fbx"), "SkeletalMeshExporterFBX", mesh_opt)
            row["anim_fbx"] = export(anim, os.path.join(out, fid + "_Anim.fbx"), "AnimSequenceExporterFBX", anim_opt)
            files += 3
            # The assembled body mesh has the outfit-covered faces removed (no torso/hips: measured in Blender,
            # 6 Oct). The sibling "<body>_DNA" skeletal mesh is expected to be the full body [inf, by name]; export
            # it too when it exists and shares the skeleton, so the drape can collide with a real torso.
            dna_path = body_mesh.get_path_name().split(".")[0] + "_DNA"
            dna = unreal.load_asset(dna_path) if unreal.EditorAssetLibrary.does_asset_exist(dna_path) else None
            if isinstance(dna, unreal.SkeletalMesh) and dna.get_editor_property("skeleton") == body_mesh.get_editor_property("skeleton"):
                row["body_dna_fbx"] = export(dna, os.path.join(out, fid + "_BodyDNA.fbx"), "SkeletalMeshExporterFBX", mesh_opt)
                row["body_dna_mesh"] = dna.get_path_name()
                files += 1
            else:
                row["body_dna_fbx"] = None
                row["body_dna_note"] = "not exported: %s" % ("missing" if dna is None else
                                                             "class %s or different skeleton" % dna.get_class().get_name())
            rows.append(row)
        after = census()
        if after != before:
            raise RuntimeError("CENSUS_CHANGED|before=%s|after=%s" % (json.dumps(before), json.dumps(after)))
        manifest = {"run": run, "world": EXPECTED_WORLD, "mode": "read_only_export", "fbx_options_readback": mesh_opt_rb,
                    "census_before": before, "census_after": after, "figures": rows}
        with open(MANIFEST, "w", encoding="utf-8") as h:
            json.dump(manifest, h, indent=2, sort_keys=True)
        unreal.log("S3_SHORE_EXPORT_OK|run=%s|figures=%d|files=%d|census=%s|manifest=%s"
                   % (run, len(rows), files, json.dumps(after, separators=(",", ":")), MANIFEST.replace("\\", "/")))
    except Exception as exc:   # noqa: BLE001 - one failure marker, nothing to roll back (no writes to Content)
        unreal.log_error("S3_SHORE_EXPORT_FAILED|run=%s|reason=%s" % (run, str(exc).replace("\n", " ")))


if unreal is None:
    print(json.dumps(pose_picks(), indent=1))
else:
    main()
