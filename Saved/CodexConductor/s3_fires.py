"""S3 FIRES (Gary 8 Oct evening): "can the ghostlight be a flame like a torch instead of what feels like a small garden
electric light? And maybe we can have more of those" -> "quick one now and add torch pole to render queue"; "one with
each cluster as if huddling sounds good, also sanctions more fire like lighting to light the glinting fingermarks".
Writes (map + LS_DevScene_03 only; record + Backups/PreS3Fires-<run>; tag S3Fire; REVERT exact):
  1. Ghost light -> flame: hides "S3 Ghost Light Bulb" (bHidden, recorded), spawns an Emitter (P_Fire) on the stand
     top, attached to the ghost light's parent; the light goes 1900 K, source radius 4; its existing
     'S3.Opening.Ghost' intensity keys are kept up to the ramp end and FLICKER keys are added after it (recorded).
  2. One fire per crowd cluster (A/B/C; positions = live PIE cluster centres 8 Oct [measured]), ground level, offset
     toward the camera side: an Emitter (P_Fire) + a PointLight 1900 K with an 'S3.Fire.Light' flicker track.
  3. Every emitter gets a Visibility track: hidden until its ignition frame (no glow in the dark spawn).
Flicker = deterministic sum of 3 sines + hashed jitter, one key every 2 Scene frames (24 fps), per-fire phase.
Args s3_fires_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3FIRES", "run": ..}.
Markers S3FIRES_<MODE>_OK|run=.. / S3FIRES_FAILED."""
import json, math, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_fires_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
FIRE = "/Game/StarterContent/Particles/P_Fire"
TAG = "S3Fire"
FOLDER = "RigAtmos/S3Fire"
FIRE_TRACK = "S3.Fire.Light"
GHOST_TRACK = "S3.Opening.Ghost"
VIS_TRACK = "S3.Fire.Visible"
END = 6240
CLUSTERS = {"A": (14600.0, 160220.0, 230), "B": (14520.0, 160700.0, 260), "C": (13420.0, 160550.0, 290)}
FIRE_CD, RAMP = 150.0, 24   # 350 -> 150 (Gary 8 Oct 19:00: "yes, remake them")
# Fire A sat 3 m in front of the low B03 camera (Cine Camera Actor 1 at (14219,160277,13) yaw -14.4, CAMPROBE
# 8 Oct [measured]) -> moved to the FAR side of cluster A; B/C keep the camera-side offset.
OFFSET = {"A": (110.0, -20.0), "B": (-90.0, -60.0), "C": (-90.0, -60.0)}


def flicker(base, start, end, phase):
    out = []
    for f in range(start, end + 1, 2):
        t = f / 24.0
        j = (math.sin(f * 12.9898 + phase * 78.233) * 43758.5453) % 1.0 - 0.5
        g = 1.0 + 0.16 * math.sin(2 * math.pi * t / 0.47 + phase) + 0.09 * math.sin(2 * math.pi * t / 0.19 + 2 * phase) \
            + 0.05 * math.sin(2 * math.pi * t / 1.3 + 3 * phase) + 0.08 * j
        out.append((f, round(base * max(0.55, g), 3)))
    return out


def main():
    import unreal
    a = json.load(open(HERE + "s3_fires_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    w = ed.get_editor_world()
    acts = {str(x.get_actor_label()): x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)}
    scene = unreal.load_asset(SCENE)
    fire_sys = unreal.load_asset(FIRE)
    ghost, bulb, stand = acts.get("S3 Ghost Light"), acts.get("S3 Ghost Light Bulb"), acts.get("S3 Ghost Light Stand")
    ours = [x for x in acts.values() if unreal.Name(TAG) in list(x.tags)]
    gch = None
    for b in scene.get_bindings():
        for t in b.get_tracks():
            if str(t.get_display_name()) == GHOST_TRACK: gch = list(t.get_sections()[0].get_all_channels())[0]
    if mode == "DRY":
        keys = sorted((int(k.get_time().frame_number.value), float(k.get_value())) for k in gch.get_keys()) if gch else None
        unreal.log("S3FIRES_DRY_OK|run=%s|fire_asset=%s|ghost=%s|bulb=%s|stand=%s|ours=%d|ghost_keys=%s" % (
            run, fire_sys is not None, ghost is not None, bulb is not None, stand is not None, len(ours), keys))
        return
    if mode == "APPLY":
        if a.get("confirm") != "APPLY S3FIRES" or os.path.exists(REC) or ours: raise RuntimeError("CONFIRM_OR_RECORD_OR_EXISTING")
        if None in (fire_sys, ghost, bulb, stand, gch): raise RuntimeError("MISSING")
        gkeys = sorted((int(k.get_time().frame_number.value), float(k.get_value())) for k in gch.get_keys())
        gcomp = ghost.get_component_by_class(unreal.LightComponent)
        rec = {"run": run, "ghost_keys_before": gkeys, "bulb_hidden_before": bool(bulb.get_editor_property("hidden")),
               "ghost_temp_before": float(gcomp.get_editor_property("temperature")),
               "ghost_radius_before": float(gcomp.get_editor_property("source_radius")), "created": []}
        json.dump(rec, open(REC, "w"), indent=1)
        bd = "E:/PussStage/Backups/PreS3Fires-%s" % run; os.makedirs(bd)
        for f in FILES: shutil.copy2(f, bd)
        scene.modify()

        def spawn_fire(label, loc, scale, parent, ignite):
            em = eas.spawn_actor_from_class(unreal.Emitter, unreal.Vector(*loc), unreal.Rotator(0, 0, 0), False)
            if em is None: raise RuntimeError("SPAWN_EMITTER|%s|NOTHING SAVED; Don't-Save restart" % label)
            em.set_actor_label(label); em.set_editor_property("tags", [unreal.Name(TAG)]); em.set_folder_path(FOLDER)
            psc = em.get_component_by_class(unreal.ParticleSystemComponent)
            psc.set_template(fire_sys)
            em.set_actor_scale3d(unreal.Vector(scale, scale, scale))
            if parent is not None:
                em.attach_to_actor(parent, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
            vb = scene.add_possessable(em)
            vt = vb.add_track(unreal.MovieSceneVisibilityTrack); vt.set_display_name(VIS_TRACK)
            vs = vt.add_section(); vs.set_range(0, END + 1)
            vc = list(vs.get_all_channels())[0]
            vc.add_key(unreal.FrameNumber(0), False, time_unit=DR); vc.add_key(unreal.FrameNumber(int(ignite)), True, time_unit=DR)
            rec["created"].append(label); json.dump(rec, open(REC, "w"), indent=1)
            return em

        # 1. ghost light -> flame
        first_lit = min(f for f, v in gkeys if v > 0.0)
        ghost_on = max(f for f, v in gkeys if f < first_lit)          # the last zero key before the ramp (183)
        ramp_end = first_lit
        bulb.modify(); bulb.set_actor_hidden_in_game(True)
        gp = ghost.get_attach_parent_actor()
        bl = bulb.get_actor_location()
        spawn_fire("S3 Ghost Light Flame", (bl.x, bl.y, bl.z - 12.0), 0.16, gp, ghost_on)
        gcomp.modify(); gcomp.set_editor_property("temperature", 1900.0); gcomp.set_editor_property("use_temperature", True)
        gcomp.set_editor_property("source_radius", 4.0)
        # 8 Oct: the ghost track ALREADY flickers (S3 flame pass, keys every 2 frames from 195) -> keys untouched.
        # 2. cluster fires
        for i, (n, (cx, cy, ig)) in enumerate(sorted(CLUSTERS.items())):
            fx, fy = cx + OFFSET[n][0], cy + OFFSET[n][1]
            spawn_fire("S3 Fire %s" % n, (fx, fy, 2.0), 0.32, None, ig)
            lt = eas.spawn_actor_from_class(unreal.PointLight, unreal.Vector(fx, fy, 55.0), unreal.Rotator(0, 0, 0), False)
            lt.set_actor_label("S3 Fire %s Light" % n); lt.set_editor_property("tags", [unreal.Name(TAG)]); lt.set_folder_path(FOLDER)
            lc = lt.get_component_by_class(unreal.LightComponent); lc.modify()
            lc.set_mobility(unreal.ComponentMobility.MOVABLE)
            lc.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS); lc.set_editor_property("intensity", 0.0)
            lc.set_editor_property("use_temperature", True); lc.set_editor_property("temperature", 1900.0)
            lc.set_editor_property("source_radius", 10.0); lc.set_editor_property("attenuation_radius", 1100.0)
            lc.set_editor_property("cast_shadows", True)
            rec["created"].append("S3 Fire %s Light" % n); json.dump(rec, open(REC, "w"), indent=1)
            b = scene.add_possessable(lc)
            t = b.add_track(unreal.MovieSceneFloatTrack); t.set_property_name_and_path("Intensity", "Intensity"); t.set_display_name(FIRE_TRACK)
            s = t.add_section(); s.set_range(0, END + 1); ch = list(s.get_all_channels())[0]
            ch.add_key(unreal.FrameNumber(0), 0.0, time_unit=DR); ch.add_key(unreal.FrameNumber(ig), 0.0, time_unit=DR)
            for f, v in flicker(FIRE_CD, ig + RAMP, END, 1.9 + i * 2.3):
                ch.add_key(unreal.FrameNumber(f), v, time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        if census() != (sorted([SCENE]), [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
        ok1 = unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False)
        ok2 = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
        if not (ok1 and ok2) or census() != ([], []): raise RuntimeError("SAVE|%s" % (census(),))
        rec["state"] = "applied"; json.dump(rec, open(REC, "w"), indent=1)
        unreal.log("S3FIRES_APPLY_OK|run=%s|created=%d|ghost_flicker_from=%d|backup=%s" % (run, len(rec["created"]), ramp_end + 2, bd))
    elif mode == "REVERT":
        if a.get("confirm") != "REVERT S3FIRES" or not os.path.exists(REC): raise RuntimeError("CONFIRM_OR_NO_RECORD")
        rec = json.load(open(REC)); scene.modify()
        for b in list(scene.get_bindings()):
            if any(str(t.get_display_name()) in (FIRE_TRACK, VIS_TRACK) for t in b.get_tracks()): b.remove()
        for x in ours: eas.destroy_actor(x)
        for k in list(gch.get_keys()): gch.remove_key(k)
        for f, v in rec["ghost_keys_before"]: gch.add_key(unreal.FrameNumber(f), v, time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        gcomp = ghost.get_component_by_class(unreal.LightComponent); gcomp.modify()
        gcomp.set_editor_property("temperature", rec["ghost_temp_before"]); gcomp.set_editor_property("source_radius", rec["ghost_radius_before"])
        bulb.modify(); bulb.set_actor_hidden_in_game(rec["bulb_hidden_before"])
        unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False)
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
        if census() != ([], []): raise RuntimeError("REVERT_SAVE|%s" % (census(),))
        os.rename(REC, REC + ".reverted-" + run)
        unreal.log("S3FIRES_REVERT_OK|run=%s" % run)


try:
    main()
except Exception as e:
    import unreal
    unreal.log_error("S3FIRES_FAILED|%r" % (e,))
