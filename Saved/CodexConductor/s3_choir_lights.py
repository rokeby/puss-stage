"""S3 choir glints + darker take (Gary 8 Oct ~05:05 UTC): "some lighting over the long stretch of reflection footage
during the choir, which pans over the finger prints - I think I need more strong lights, and then a different, darker
lighting setting for when Puss takes the pearl."  (The wash "made everything look more ugly": these are GLINT sources.)

A. 8 'S3 Choir Glint' PointLights (tag S3ChoirGlint, folder RigAtmos/S3Drama, attached to S3 Hangar Root KEEP_WORLD):
   two lines 120 cm off each marble wall, x 12500/13800/15100/16400, z alternating 160/260.  Small bright sources
   (source radius 8 cm, 2500 cd, 5600 K) with diffuse_scale 0.15 / specular_scale 1.0, so they read as reflections in
   the wet floor, marble and grease rather than lighting the walls [inferred: DiffuseScale property availability is
   checked at DRY].  Keys: 0 until 3072 (chorus 2:08), full by 3144, held to 4488 (chorus ends 3:07), down to 0 by 4584.
B. Darker take (Puss decides 3:15 / takes 3:20): over 4560 -> 4680 the wave lights (S3.WavesV3.Light, shimmer keys) are
   scaled by 1 -> 0.35 and held; the wall grazes (S3 Drama Graze *) 3000 -> 1500 over the same window.  Keys after 4680
   are scaled, keys before 4560 untouched.  The pearl glow is handled separately (it never dims until stolen).
Saves map + LS_DevScene_03.  Record s3_choir_lights_record.json + Backups/PreS3Choir-<run> first.
Args s3_choir_lights_args.json {"mode":"DRY"|"APPLY","confirm":"APPLY S3CHOIR","run":..}.  S3CHOIR_<MODE>_OK / S3CHOIR_FAILED."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_choir_lights_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
TAG, FOLDER, TRACK = "S3ChoirGlint", "RigAtmos/S3Drama", "S3.Choir.Glint"
END = 6240
GLINT_KEYS = [(0, 0.0), (3072, 0.0), (3144, 1.0), (4488, 1.0), (4584, 0.0), (END, 0.0)]
TAKE_A, TAKE_B = 4560, 4680
WALL_L, WALL_R = 159001.0, 160999.0
RUN = {"run": "?"}


def glint_specs():
    out = []
    for side, y in (("L", WALL_L + 120.0), ("R", WALL_R - 120.0)):
        for i, x in enumerate((12500.0, 13800.0, 15100.0, 16400.0)):
            out.append({"label": "S3 Choir Glint %s%d" % (side, i + 1), "loc": (x, y, 160.0 if i % 2 == 0 else 260.0)})
    return out


def take_scale(f, lo):
    if f <= TAKE_A:
        return 1.0
    if f >= TAKE_B:
        return lo
    return 1.0 + (lo - 1.0) * (f - TAKE_A) / float(TAKE_B - TAKE_A)


def main():
    import unreal
    a = json.load(open(HERE + "s3_choir_lights_args.json"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise RuntimeError("SEQUENCER_OPEN")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    w = ed.get_editor_world()
    acts = {str(x.get_actor_label()): x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)}
    ours = [x for x in acts.values() if unreal.Name(TAG) in list(x.tags)]
    scene = unreal.load_asset(SCENE)
    fr = lambda k: int(k.get_time().frame_number.value)
    scaled = []    # (owner, channel, lo)
    for b in scene.get_bindings():
        p = b.get_parent()
        own = str(p.get_display_name()) if p is not None and p.is_valid() else str(b.get_display_name())
        for t in b.get_tracks():
            tn = str(t.get_display_name())
            if tn == "S3.WavesV3.Light" or (tn == "S3.Drama.Light" and own.startswith("S3 Drama Graze")):
                ch = list(t.get_sections()[0].get_all_channels())[0]
                scaled.append((own, ch, 0.35 if tn == "S3.WavesV3.Light" else 0.5))
    probe = unreal.PointLightComponent
    has_diffuse = "diffuse_scale" in dir(probe) or hasattr(probe, "diffuse_scale")
    summary = {"glints": len(glint_specs()), "existing": len(ours), "scaled_tracks": len(scaled),
               "waves": sum(1 for o, _, lo in scaled if lo == 0.35), "grazes": sum(1 for o, _, lo in scaled if lo == 0.5)}
    if mode == "DRY":
        unreal.log("S3CHOIR_DRY_OK|run=%s|%s|has_diffuse_scale=%s" % (run, json.dumps(summary), has_diffuse))
        return
    if a.get("confirm") != "APPLY S3CHOIR" or os.path.exists(REC) or ours or summary["waves"] != 7 or summary["grazes"] != 4:
        raise RuntimeError("PRECONDITION|%s" % summary)
    before = {o: [(fr(k), float(k.get_value())) for k in ch.get_keys()] for o, ch, _ in scaled}
    rec = {"run": run, "state": "applying", "scaled_before": before, "created": []}
    json.dump(rec, open(REC, "w"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3Choir-%s" % run
    os.makedirs(bdir)
    for f in FILES:
        shutil.copy2(f, bdir)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    root = acts["S3 Hangar Root"]
    scene.modify()
    for spec in glint_specs():
        x = eas.spawn_actor_from_class(unreal.PointLight, unreal.Vector(*spec["loc"]), unreal.Rotator(0, 0, 0), False)
        if x is None:
            raise RuntimeError("SPAWN|NOTHING SAVED; Don't-Save restart")
        x.set_actor_label(spec["label"])
        x.set_editor_property("tags", [unreal.Name(TAG)])
        x.set_folder_path(FOLDER)
        x.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, False)
        c = x.get_component_by_class(unreal.LightComponent)
        c.modify()
        c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        c.set_editor_property("intensity", 0.0)
        c.set_editor_property("source_radius", 8.0)
        c.set_editor_property("attenuation_radius", 1600.0)
        c.set_editor_property("use_temperature", True)
        c.set_editor_property("temperature", 5600.0)
        c.set_editor_property("specular_scale", 1.0)
        if has_diffuse:
            c.set_editor_property("diffuse_scale", 0.15)
        rec["created"].append(x.get_path_name())
        json.dump(rec, open(REC, "w"), indent=1)
        bb = scene.add_possessable(c)
        t = bb.add_track(unreal.MovieSceneFloatTrack)
        t.set_property_name_and_path("Intensity", "Intensity")
        t.set_display_name(TRACK)
        s = t.add_section()
        s.set_range(0, END + 1)
        ch = list(s.get_all_channels())[0]
        for f, v in GLINT_KEYS:
            ch.add_key(unreal.FrameNumber(f), 2500.0 * v, time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        if len(ch.get_keys()) != len(GLINT_KEYS):
            raise RuntimeError("GLINT_KEYS|NOTHING SAVED; Don't-Save restart")
    for o, ch, lo in scaled:
        for k in ch.get_keys():
            f = fr(k)
            if f > TAKE_A:
                k.set_value(k.get_value() * take_scale(f, lo))
        # make sure the ramp has its start and end points
        vals = {fr(k): k.get_value() for k in ch.get_keys()}
        for anchor in (TAKE_A, TAKE_B):
            if anchor not in vals:
                # value at the anchor from the original curve, piecewise linear between neighbours
                orig = before[o]
                prev = max((p for p in orig if p[0] <= anchor), key=lambda p: p[0])
                nxt = min((p for p in orig if p[0] >= anchor), key=lambda p: p[0])
                v = prev[1] if nxt[0] == prev[0] else prev[1] + (nxt[1] - prev[1]) * (anchor - prev[0]) / float(nxt[0] - prev[0])
                ch.add_key(unreal.FrameNumber(anchor), v * take_scale(anchor, lo), time_unit=DR,
                           interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    c1 = dirty()
    if c1 != ([SCENE], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (c1,))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or not lib.save_dirty_packages(True, False):
        raise RuntimeError("SAVE")
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AFTER|%s" % (dirty(),))
    rec["state"] = "applied"
    json.dump(rec, open(REC, "w"), indent=1)
    unreal.log("S3CHOIR_APPLY_OK|run=%s|%s|diffuse_scale=%s" % (run, json.dumps(summary), has_diffuse))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3CHOIR_FAILED|run=%s|%r" % (RUN["run"], exc))
