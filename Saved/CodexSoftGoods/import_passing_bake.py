"""Import a curtain bake that PASSED the 30 Sep acceptance test, and optionally place it as a level actor.

Mode file: import_passing_bake_mode.json. For example, the Opening, replacing the cache that the Opening and all five
transitions already play:
  {"bake_id": "final6_columns", "gc_name": "GC_CurtainDrop_Opening", "sm_prefix": "SM_CurtainDrape",
   "mi_name": "MI_CurtainVelvet_DeepRed_Drop", "place": null, "dry_run": true}
The P04 backcloth, placed as a level actor for Rig's Arrival and LS_S4_HangarRise (G2):
  {"bake_id": "final8_backcloth_p04", "gc_name": "GC_CurtainBackcloth_P04", "sm_prefix": "SM_CurtainBackcloth_P04",
   "mi_name": "MI_CurtainVelvet_DeepRed_Backcloth",
   "place": {"label": "P04 Backcloth (baked)", "location": [10450, 240000, 0], "yaw": 0,
             "folder": "InfinityStage/Curtains"}, "dry_run": true}

Guards, before anything is imported:
  - REFUSES unless Saved/CodexSoftGoods/DropBake/acceptance.json marks the bake ALL = true. That file is written by
    Scripts/report_overnight_bakes.py, so a number, not a look, decides.
  - The expected world; no PIE; no dirty content. When placing, the map must also be clean, since it gets saved.
  - Every property name is probed first, so a wrong name fails before any import.
The axis check imports the bake's hang frame (release - 1) and its last frame as static meshes, and compares their
bounds with the bake's own checkpoint extents (Blender m to UE cm: X = 100 y, Y = 100 x, Z = 100 z) to TOL_CM. An
asymmetric pile cannot pass a flip or swap. If it fails, the cache is not imported and nothing is saved.
The placed actor is saved with manual_tick = true, running = true and looping = false (Rig, G2), so it never auto-plays
and a Restore State returns it to manual. All three are read back.
CROSS-STREAM CONTRACT: import_passing_bake.json's `plan.release_in_cache_s` (seconds from the cache's first sample
to the release, float) is READ by Rig's Saved/CodexStructure/p04_backcloth_section_apply.py, which refuses on
disagreement. Changing that field's name, meaning or units is a cross-stream change: tell Rig first.
Saves only its own assets, and the map when placing; backs up everything it replaces first. Logs
PUSS_SOFTGOODS_BAKE_IMPORT_SUCCESS or _STOPPED. Crash rules: everything inside main().
"""
import datetime
import hashlib
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
DEST = "/Game/Scenes/Curtain/Baked"
VELVET_PARENT = "/Game/Scenes/Curtain/Chaos/Materials/MI_CurtainVelvet_DeepRed"
CONV_SCALE, CONV_ROT = (100.0, -100.0, 100.0), (90.0, 0.0, 90.0)   # proven by the final2 axis check, 29 Sep
TOL_CM = 4.0
BOLT_M, QUADS_PER_BOLT = 1.37, 15


def project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def saved_dir():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def dirty_content():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())


def dirty_maps():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def content_file(asset_path, ext):
    return os.path.join(project(), "Content", *asset_path[len("/Game/"):].split("/")) + ext


def settings(kind, frame_start, frame_end):
    s = unreal.AbcImportSettings()
    s.set_editor_property("import_type", kind)
    conv = unreal.AbcConversionSettings()
    conv.set_editor_property("preset", unreal.AbcConversionPreset.CUSTOM)
    conv.set_editor_property("scale", unreal.Vector(*CONV_SCALE))
    conv.set_editor_property("rotation", unreal.Vector(*CONV_ROT))
    conv.set_editor_property("flip_u", False)
    conv.set_editor_property("flip_v", True)
    s.set_editor_property("conversion_settings", conv)
    samp = unreal.AbcSamplingSettings()
    samp.set_editor_property("sampling_type", unreal.AlembicSamplingType.PER_FRAME)
    samp.set_editor_property("frame_start", frame_start)
    samp.set_editor_property("frame_end", frame_end)
    samp.set_editor_property("skip_empty", False)
    s.set_editor_property("sampling_settings", samp)
    mat = unreal.AbcMaterialSettings()
    mat.set_editor_property("create_materials", False)
    mat.set_editor_property("find_materials", False)
    s.set_editor_property("material_settings", mat)
    if kind == unreal.AlembicImportType.GEOMETRY_CACHE:
        gc = unreal.AbcGeometryCacheSettings()
        gc.set_editor_property("flatten_tracks", True)
        gc.set_editor_property("apply_constant_topology_optimizations", True)
        gc.set_editor_property("motion_vectors", unreal.AbcGeometryCacheMotionVectorsImport.CALCULATE_MOTION_VECTORS_DURING_IMPORT)
        s.set_editor_property("geometry_cache_settings", gc)
    return s


def import_one(abc, name, kind, frame_start, frame_end):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", abc)
    task.set_editor_property("destination_path", DEST)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", settings(kind, frame_start, frame_end))
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.get_editor_property("imported_object_paths") or [])
    del task
    return paths


def bounds_cm(path):
    sm = unreal.load_asset(path)
    b = sm.get_bounds()
    o, e = b.origin, b.box_extent
    out = {"x": [round(o.x - e.x, 1), round(o.x + e.x, 1)], "y": [round(o.y - e.y, 1), round(o.y + e.y, 1)],
           "z": [round(o.z - e.z, 1), round(o.z + e.z, 1)]}
    del sm
    return out


def expected_cm(aabb_m):
    """Bake extents (Blender m) as UE cm: UE X = 100 * Blender y, UE Y = 100 * Blender x, UE Z = 100 * Blender z."""
    return {"x": [100 * aabb_m["y"][0], 100 * aabb_m["y"][1]], "y": [100 * aabb_m["x"][0], 100 * aabb_m["x"][1]],
            "z": [100 * aabb_m["z"][0], 100 * aabb_m["z"][1]]}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    here = saved_dir()
    with open(os.path.join(here, "import_passing_bake_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    report = {"ok": False, "cfg": cfg}
    out = os.path.join(here, "import_passing_bake.json")

    def finish(msg):
        report["message"] = msg
        with open(out, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(("PUSS_SOFTGOODS_BAKE_IMPORT_SUCCESS|" if report["ok"] else "PUSS_SOFTGOODS_BAKE_IMPORT_STOPPED|") + msg)

    bake_id, gc_name, sm_prefix, mi_name = cfg["bake_id"], cfg["gc_name"], cfg["sm_prefix"], cfg["mi_name"]
    place, dry = cfg.get("place"), bool(cfg.get("dry_run", True))
    bake_dir = os.path.join(here, "DropBake")
    acceptance = json.load(open(os.path.join(bake_dir, "acceptance.json"), encoding="utf-8"))
    verdict = acceptance.get(bake_id)
    report["verdict"] = verdict
    if not verdict or verdict.get("ALL") is not True:
        return finish(f"REFUSED: {bake_id} has not passed acceptance ({verdict})")
    src_json, src_abc = os.path.join(bake_dir, f"{bake_id}.json"), os.path.join(bake_dir, f"{bake_id}.abc")
    if not os.path.isfile(src_abc):
        return finish(f"missing {src_abc}")
    # THE VERDICT IS BOUND TO THE BYTES (30 Sep, adversarial review): the files must hash to what the acceptance test
    # judged, so a re-used bake id cannot import an untested replacement under a stale pass.
    judged = (verdict or {}).get("artifacts") or {}
    now_hash = {f"{bake_id}.json": sha256_file(src_json), f"{bake_id}.abc": sha256_file(src_abc)}
    report["artifacts"] = now_hash
    if any(judged.get(k) != v for k, v in now_hash.items()):
        return finish(f"REFUSED: {bake_id}'s files are not the ones that were judged (judged {judged}, now {now_hash})")
    bake = json.load(open(src_json, encoding="utf-8"))
    first, last = int(bake["show_start"]), int(bake["frames"])
    hang_f, pile_f = int(bake["release_frame"]) - 1, last
    exp = {f"{sm_prefix}_Hanging": (hang_f, expected_cm(bake["checkpoints"][str(hang_f)]["aabb_m"])),
           f"{sm_prefix}_Pile": (pile_f, expected_cm(bake["checkpoints"][str(pile_f)]["aabb_m"]))}
    cols = round(bake["track_m"] * bake["fullness"] / (BOLT_M / QUADS_PER_BOLT))
    mi_params = {"PatternWidthM": round(cols * BOLT_M / QUADS_PER_BOLT, 3), "DropM": float(bake["drop_m"]), "SeamWidthM": BOLT_M}
    report["plan"] = {"frames": [first, last], "release_in_cache_s": round((bake["release_frame"] - first) / 30.0, 3),
                      "axis_expect_cm": exp, "mi_params": mi_params}

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_name = world.get_outermost().get_name()
    if world_name != EXPECTED_WORLD or editor.get_game_world() is not None:
        return finish(f"unsafe editor state: world={world_name}, PIE={editor.get_game_world() is not None}")
    foreign = [p for p in dirty_content() if not p.startswith(DEST + "/")]
    if foreign:
        return finish(f"refusing: dirty content {foreign}")
    if place and dirty_maps():
        return finish(f"refusing to place: the map is dirty {dirty_maps()} and would be saved with it")
    try:                                        # probe every name before any import
        settings(unreal.AlembicImportType.STATIC_MESH, 0, 0)
        settings(unreal.AlembicImportType.GEOMETRY_CACHE, first, last)
        comp_cdo = unreal.GeometryCacheComponent.get_default_object()
        for prop in ("geometry_cache", "running", "looping", "manual_tick"):
            comp_cdo.get_editor_property(prop)
        if not unreal.load_asset(VELVET_PARENT):
            return finish(f"missing {VELVET_PARENT}")
    except Exception as exc:  # noqa: BLE001
        return finish(f"preflight failed before any import: {exc}")
    if dry:
        report["ok"] = True
        return finish(f"DRY RUN|{bake_id}->{DEST}/{gc_name}|frames={first}..{last}|mi={mi_params}|place={place}")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(project(), "Backups", f"PreBakeImport-{gc_name}-{stamp}")
    os.makedirs(backup, exist_ok=True)
    for name in (gc_name, f"{sm_prefix}_Hanging", f"{sm_prefix}_Pile", mi_name):
        f = content_file(f"{DEST}/{name}", ".uasset")
        if os.path.isfile(f):
            shutil.copy2(f, backup)
    if place:
        shutil.copy2(content_file(EXPECTED_WORLD, ".umap"), backup)
    report["backup"] = backup
    abc_dir = os.path.join(project(), "DerivedAssets", "CurtainCloth", "Baked")
    os.makedirs(abc_dir, exist_ok=True)
    abc = os.path.join(abc_dir, f"{gc_name}_{bake_id}.abc").replace("\\", "/")
    shutil.copy2(src_abc, abc)
    report["abc"] = abc

    # 1) axis check on two static meshes (a failure stops before the slow cache import; nothing is saved)
    report["static_meshes"], fails = {}, []
    for name, (frame, want) in exp.items():
        import_one(abc, name, unreal.AlembicImportType.STATIC_MESH, frame, frame)
        path = f"{DEST}/{name}"
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            return finish(f"static mesh import produced nothing for {name}; NOTHING saved")
        got = bounds_cm(path)
        report["static_meshes"][name] = {"frame": frame, "bounds_cm": got, "expected_cm": want}
        for ax in ("x", "y", "z"):                         # Z too: a vertical inversion or offset must not pass
            if abs(got[ax][0] - want[ax][0]) > TOL_CM or abs(got[ax][1] - want[ax][1]) > TOL_CM:
                fails.append(f"{name}.{ax} got {got[ax]} expected {[round(v, 1) for v in want[ax]]}")
    report["axis_check_failures"] = fails
    if fails:
        return finish("AXIS CHECK FAILED, cache not imported, NOTHING saved: " + "; ".join(fails))

    # 2) the material instance
    mi_path = f"{DEST}/{mi_name}"
    mi = unreal.load_asset(mi_path) if unreal.EditorAssetLibrary.does_asset_exist(mi_path) else \
        unreal.AssetToolsHelpers.get_asset_tools().create_asset(mi_name, DEST, unreal.MaterialInstanceConstant,
                                                               unreal.MaterialInstanceConstantFactoryNew())
    mel = unreal.MaterialEditingLibrary
    mel.set_material_instance_parent(mi, unreal.load_asset(VELVET_PARENT))
    for pname, value in mi_params.items():
        mel.set_material_instance_scalar_parameter_value(mi, pname, value)
    report["mi_params_read_back"] = {p: mel.get_material_instance_scalar_parameter_value(mi, p) for p in mi_params}
    for name in exp:
        sm = unreal.load_asset(f"{DEST}/{name}")
        for i in range(len(list(sm.get_editor_property("static_materials")))):
            sm.set_material(i, mi)
        del sm

    # 3) the GeometryCache (slow), replaced in place, so everything that plays it keeps its reference
    import_one(abc, gc_name, unreal.AlembicImportType.GEOMETRY_CACHE, first, last)
    gc_path = f"{DEST}/{gc_name}"
    if not unreal.EditorAssetLibrary.does_asset_exist(gc_path):
        del mi
        return finish("geometry cache import produced nothing; NOTHING saved (relaunch to discard)")
    gc = unreal.load_asset(gc_path)
    slots = max(1, len(list(gc.get_editor_property("materials"))))
    gc.set_editor_property("materials", [mi] * slots)
    report["gc"] = {"start_frame": gc.get_editor_property("start_frame"), "end_frame": gc.get_editor_property("end_frame")}

    # 4) the level actor, optional and idempotent (found by label)
    expected = {gc_path, mi_path} | {f"{DEST}/{n}" for n in exp}
    if place:
        actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                  if a.get_actor_label() == place["label"]]
        if len(actors) > 1:
            return finish(f"{len(actors)} actors labelled {place['label']}; NOTHING saved (relaunch to discard)")
        loc = unreal.Vector(*place["location"])
        rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(place.get("yaw", 0.0)))
        actor = actors[0] if actors else unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
            unreal.GeometryCacheActor, loc, rot)
        actor.set_actor_label(place["label"])
        actor.set_folder_path(place.get("folder", "InfinityStage/Curtains"))
        actor.set_actor_location(loc, False, False)
        actor.set_actor_rotation(rot, False)
        comp = actor.get_editor_property("geometry_cache_component")
        comp.set_editor_property("geometry_cache", gc)
        comp.set_editor_property("manual_tick", True)     # never auto-plays; Restore State returns it to manual (G2)
        comp.set_editor_property("running", True)         # running=false freezes any tick on frame 0 (29 Sep)
        comp.set_editor_property("looping", False)
        del actor, comp, actors
        expected.add(EXPECTED_WORLD)
    del gc, mi

    # 5) save exactly this script's packages
    now = dirty_content() + dirty_maps()
    report["dirty_before_save"] = now
    unexpected = [p for p in now if p not in expected]
    if unexpected:
        return finish(f"unexpected dirty packages {unexpected}; NOTHING saved (relaunch to discard; backup {backup})")
    saved = {p: unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False) for p in sorted(expected - {EXPECTED_WORLD})}
    if place:
        saved[EXPECTED_WORLD] = unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)
    report["saved"] = saved

    # 6) read back
    rb = {"gc_frames": None, "actor": None}
    gc = unreal.load_asset(gc_path)
    rb["gc_frames"] = [gc.get_editor_property("start_frame"), gc.get_editor_property("end_frame")]
    rb["gc_material"] = [m.get_path_name() for m in gc.get_editor_property("materials")]
    del gc
    ok_actor = True
    if place:
        hits = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                if a.get_actor_label() == place["label"]]
        if len(hits) == 1:
            c = hits[0].get_editor_property("geometry_cache_component")
            l, r = hits[0].get_actor_location(), hits[0].get_actor_rotation()
            rb["actor"] = {"location": [l.x, l.y, l.z], "yaw": r.yaw,
                           "cache": c.get_editor_property("geometry_cache").get_path_name().split(".")[0],
                           "manual_tick": c.get_editor_property("manual_tick"), "running": c.get_editor_property("running"),
                           "looping": c.get_editor_property("looping")}
            a = rb["actor"]
            ok_actor = (a["cache"] == gc_path and a["manual_tick"] and a["running"] and not a["looping"]
                        and all(abs(a["location"][k] - place["location"][k]) < 1.0 for k in range(3))
                        and abs(((a["yaw"] - place.get("yaw", 0.0) + 180) % 360) - 180) < 0.01)
            del c
        else:
            ok_actor = False
        del hits
    # The material is part of success, not a log line: the MI's parameters and the cache's slots must read back as set.
    mi = unreal.load_asset(mi_path)
    rb["mi_params"] = {k: unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(mi, k) for k in mi_params}
    del mi
    ok_material = (all(abs(rb["mi_params"][k] - v) < 1e-3 for k, v in mi_params.items())
                   and bool(rb["gc_material"]) and all(m.split(".")[0] == mi_path for m in rb["gc_material"]))
    report["read_back"] = rb
    report["dirty_final"] = dirty_content() + dirty_maps()
    report["ok"] = (all(saved.values()) and not report["dirty_final"] and rb["gc_frames"] == [first, last] and ok_actor
                    and ok_material)
    finish(f"{bake_id}->{gc_path}|saved={saved}|read_back={rb}|dirty_final={report['dirty_final']}|backup={backup}")


main()
