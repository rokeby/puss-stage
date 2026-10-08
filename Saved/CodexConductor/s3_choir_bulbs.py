"""S3 choir: visible bare bulbs instead of bare point lights (Gary 8 Oct: the glint lights are "strictly not the kind
that helps with reflections"; answer "Yes, bulbs").  The 8 'S3 Choir Glint' PointLights (S3CHOIR-20261008-050333) each
get a hanging bulb mesh so the wet floor, marble and grease reflect a SOURCE, not just a highlight:
  * new MI /Game/InfinityStage/Dev/Generated/S3Drama/MI_S3_ChoirBulb_Glow (parent M_Fixture_Glow, Intensity 40;
    the fixture default is 1.5 [measured probe_bulb_mi]), create-only;
  * per glint light: StaticMeshActor SM_Bulb_A60_Frost, scale 3.2 (the fixtures' current bulb scale), pivot at the
    light (the mesh hangs below its pivot, min z -11 cm [measured]), slot 0 overridden with the bright MI, attached to
    the light (KEEP_WORLD), tag S3ChoirBulb, label 'S3 Choir Bulb <side><n>';
  * Visibility track in LS_DevScene_03 per bulb: hidden 0 -> 3072, shown 3072 (chorus 2:08) -> 4584, hidden after;
  * the glint lights' keys scaled x0.16 (2500 -> 400 cd): the bulb now carries the look, the light just lights its
    surroundings a little (diffuse_scale stays 0.15).
Saves map + LS_DevScene_03 + the new MI.  Record s3_choir_bulbs_record.json + Backups/PreS3ChoirBulbs-<run> first.
Args s3_choir_bulbs_args.json {"mode":"DRY"|"APPLY","confirm":"APPLY S3BULBS","run":..}.  S3BULBS_<MODE>_OK / _FAILED."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_choir_bulbs_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
MESH = "/Game/InfinityStage/Lighting/Fixtures/Meshes/SM_Bulb_A60_Frost"
PARENT = "/Game/InfinityStage/Lighting/Fixtures/Materials/M_Fixture_Glow"
MI_DIR, MI_NAME = "/Game/InfinityStage/Dev/Generated/S3Drama", "MI_S3_ChoirBulb_Glow"
MI_PATH = MI_DIR + "/" + MI_NAME
GLOW = 40.0
SCALE = 3.2
LIGHT_GAIN = 0.16
TAG, FOLDER = "S3ChoirBulb", "RigAtmos/S3Drama"
VIS_KEYS = [(0, False), (3072, True), (4584, False)]
RUN = {"run": "?"}


def main():
    import unreal
    a = json.load(open(HERE + "s3_choir_bulbs_args.json"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise RuntimeError("SEQUENCER_OPEN")
    lib = unreal.EditorLoadingAndSavingUtils
    eal = unreal.EditorAssetLibrary
    dirty = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    w = ed.get_editor_world()
    allact = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor))
    glints = sorted([x for x in allact if str(x.get_actor_label()).startswith("S3 Choir Glint ")], key=lambda x: str(x.get_actor_label()))
    ours = [x for x in allact if unreal.Name(TAG) in list(x.tags)]
    scene = unreal.load_asset(SCENE)
    glint_ch = {}
    for b in scene.get_bindings():
        p = b.get_parent()
        own = str(p.get_display_name()) if p is not None and p.is_valid() else ""
        for t in b.get_tracks():
            if str(t.get_display_name()) == "S3.Choir.Glint" and own.startswith("S3 Choir Glint "):
                glint_ch[own] = list(t.get_sections()[0].get_all_channels())[0]
    mesh = unreal.load_asset(MESH)
    if mode == "DRY":
        unreal.log("S3BULBS_DRY_OK|run=%s|glints=%d|tracks=%d|existing=%d|mesh=%s|mi_exists=%s" % (
            run, len(glints), len(glint_ch), len(ours), mesh is not None, eal.does_asset_exist(MI_PATH)))
        return
    if a.get("confirm") != "APPLY S3BULBS" or os.path.exists(REC) or ours or len(glints) != 8 or len(glint_ch) != 8 or mesh is None:
        raise RuntimeError("PRECONDITION|glints=%d|tracks=%d|ours=%d" % (len(glints), len(glint_ch), len(ours)))
    fr = lambda k: int(k.get_time().frame_number.value)
    rec = {"run": run, "state": "applying", "glint_before": {o: [(fr(k), float(k.get_value())) for k in ch.get_keys()] for o, ch in glint_ch.items()},
           "created": [], "mi_created": False}
    json.dump(rec, open(REC, "w"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3ChoirBulbs-%s" % run
    os.makedirs(bdir)
    for f in FILES:
        shutil.copy2(f, bdir)
    want_content = [SCENE]
    if not eal.does_asset_exist(MI_PATH):
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mi = tools.create_asset(MI_NAME, MI_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        unreal.MaterialEditingLibrary.set_material_instance_parent(mi, unreal.load_asset(PARENT))
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Intensity", GLOW)
        if abs(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(mi, "Intensity") - GLOW) > 1e-3:
            raise RuntimeError("MI_READBACK|NOTHING SAVED; Don't-Save restart")
        rec["mi_created"] = True
        want_content.append(MI_PATH)
    mi = unreal.load_asset(MI_PATH)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    scene.modify()
    for g in glints:
        lab = str(g.get_actor_label()).replace("Glint", "Bulb")
        x = eas.spawn_actor_from_class(unreal.StaticMeshActor, g.get_actor_location(), unreal.Rotator(0, 0, 0), False)
        x.set_actor_label(lab)
        x.set_editor_property("tags", [unreal.Name(TAG)])
        x.set_folder_path(FOLDER)
        x.set_actor_scale3d(unreal.Vector(SCALE, SCALE, SCALE))
        smc = x.static_mesh_component
        smc.set_mobility(unreal.ComponentMobility.MOVABLE)
        smc.set_static_mesh(mesh)
        smc.set_material(0, mi)
        smc.set_collision_profile_name("NoCollision")
        smc.set_editor_property("cast_shadow", False)
        x.attach_to_actor(g, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, False)
        rec["created"].append(x.get_path_name())
        json.dump(rec, open(REC, "w"), indent=1)
        bb = scene.add_possessable(x)
        t = bb.add_track(unreal.MovieSceneVisibilityTrack)
        s = t.add_section()
        s.set_range(0, int(scene.get_playback_end()) + 1)
        ch = list(s.get_all_channels())[0]
        for f, v in VIS_KEYS:
            ch.add_key(unreal.FrameNumber(f), v, time_unit=DR)
        if sorted((fr(k), bool(k.get_value())) for k in ch.get_keys()) != VIS_KEYS:
            raise RuntimeError("VIS_READBACK|%s|NOTHING SAVED; Don't-Save restart" % lab)
        if smc.get_material(0) != mi or x.get_attach_parent_actor() != g:
            raise RuntimeError("BULB_READBACK|%s|NOTHING SAVED; Don't-Save restart" % lab)
    for o, ch in glint_ch.items():
        for k in ch.get_keys():
            k.set_value(k.get_value() * LIGHT_GAIN)
    c1 = dirty()
    if c1 != (sorted(want_content), [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (c1,))
    for p in want_content:
        if not eal.save_asset(p, only_if_is_dirty=False):
            raise RuntimeError("SAVE|%s" % p)
    if not lib.save_dirty_packages(True, False) or dirty() != ([], []):
        raise RuntimeError("SAVE_MAP|%s" % (dirty(),))
    rec["state"] = "applied"
    json.dump(rec, open(REC, "w"), indent=1)
    unreal.log("S3BULBS_APPLY_OK|run=%s|bulbs=%d|glow=%s|light_gain=%s" % (run, len(rec["created"]), GLOW, LIGHT_GAIN))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3BULBS_FAILED|run=%s|%r" % (RUN["run"], exc))
