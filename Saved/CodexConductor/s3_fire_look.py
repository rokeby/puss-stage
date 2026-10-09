"""S3 FIRE LOOK (Gary 8 Oct ~19:50: "make the fires more visible albeit a bit less bright, and remove the smoke ... fast
and too regular looking"; F21: ghost light "smoke actor on the stick ... very bad", flame "could flicker a bit more").
[meas] probe_p_fire: every S3 fire is an Emitter with P_Fire; its material slots are 0/1 M_Fire_SubUV, 2 M_smoke_subUV,
3/4 M_Radial_Gradient, 5 M_Heat_Distortion.  P_Fire's emitters are protected from Python, so the smoke is removed per
COMPONENT: slot 2 -> M_FX_Invisible (new, create-only: translucent, opacity 0, used with particle sprites).
WRITES (record s3_fire_look_record.json + Backups/PreS3FireLook-<run>; REVERT exact):
  1. 'S3 Fire A/B/C' + 'S3 Ghost Light Flame': slot 2 override -> M_FX_Invisible.
  2. 'S3 Fire A/B/C' actor scale 0.32 -> FIRE_SCALE (bigger, more readable flames).
  3. 'S3 Fire A/B/C Light' 'S3.Fire.Light' intensity keys x LIGHT_GAIN (150 -> ~100 cd).
  4. Ghost flicker: 'S3.Opening.Ghost' keys from GHOST_FROM: v -> mean + GHOST_AMP*(v - mean), floor 0.
Saves M_FX_Invisible (create), the map, LS_DevScene_03.  Args s3_fire_look_args.json
{"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3FIRELOOK", "run"}.  S3FIRELOOK_<MODE>_OK / _FAILED."""
import json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_fire_look_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
INVIS_DIR, INVIS_NAME = "/Game/Scenes/Effects", "M_FX_Invisible"
INVIS = INVIS_DIR + "/" + INVIS_NAME
FIRES = ["S3 Fire A", "S3 Fire B", "S3 Fire C"]
FLAMES = FIRES + ["S3 Ghost Light Flame"]
SMOKE_SLOT = 2
FIRE_SCALE = 0.5
LIGHT_GAIN = 0.67
GHOST_FROM, GHOST_AMP = 197, 1.6
FIRE_TRACK, GHOST_TRACK = "S3.Fire.Light", "S3.Opening.Ghost"


def _channels(seq, name, unreal):
    out = []
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if str(t.get_display_name()) == name:
                for s in t.get_sections():
                    out.append((str(b.get_display_name()), list(s.get_all_channels())[0]))
    return out


def _make_invisible(unreal):
    if unreal.EditorAssetLibrary.does_asset_exist(INVIS):
        return unreal.load_asset(INVIS), False
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    m = tools.create_asset(INVIS_NAME, INVIS_DIR, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("used_with_particle_sprites", True)
    m.set_editor_property("used_with_beam_trails", True)
    mel = unreal.MaterialEditingLibrary
    c = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -300, 0)
    c.set_editor_property("r", 0.0)
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_OPACITY)
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    return m, True


def main():
    import unreal
    a = json.load(open(HERE + "s3_fire_look_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    acts = {str(x.get_actor_label()): x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    missing = [n for n in FLAMES + [f + " Light" for f in FIRES] if n not in acts]
    if missing: raise RuntimeError("MISSING|%s" % missing)
    seq = unreal.load_asset(SCENE)
    fire_ch = _channels(seq, FIRE_TRACK, unreal)
    ghost_ch = _channels(seq, GHOST_TRACK, unreal)
    psc = {n: acts[n].get_component_by_class(unreal.ParticleSystemComponent) for n in FLAMES}
    slot = {n: (psc[n].get_material(SMOKE_SLOT).get_path_name() if psc[n].get_material(SMOKE_SLOT) else None) for n in FLAMES}
    if any("smoke" not in str(v).lower() and INVIS_NAME not in str(v) for v in slot.values()): raise RuntimeError("SLOT2_NOT_SMOKE|%s" % slot)
    if mode == "DRY":
        unreal.log("S3FIRELOOK_DRY_OK|run=%s|slot2=%s|fire_channels=%d|ghost_channels=%d|scales=%s" % (
            run, {k: v.split("/")[-1] for k, v in slot.items()}, len(fire_ch), len(ghost_ch),
            {n: round(acts[n].get_actor_scale3d().x, 3) for n in FIRES}))
        return
    if a.get("confirm") != "%s S3FIRELOOK" % mode: raise RuntimeError("CONFIRM")
    if len(fire_ch) != 3 or len(ghost_ch) != 1: raise RuntimeError("CHANNELS|fire=%d|ghost=%d" % (len(fire_ch), len(ghost_ch)))
    bd = "E:/PussStage/Backups/PreS3FireLook-%s" % run
    created = False
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        os.makedirs(bd)
        for f in FILES: shutil.copy2(f, bd)
        rec = {"run": run, "backup": bd,
               "slot_materials": {n: [(psc[n].get_material(i).get_path_name() if psc[n].get_material(i) else None) for i in range(psc[n].get_num_materials())] for n in FLAMES},
               "scales": {n: [acts[n].get_actor_scale3d().x, acts[n].get_actor_scale3d().y, acts[n].get_actor_scale3d().z] for n in FIRES},
               "fire_keys": {b: [[int(k.get_time().frame_number.value), float(k.get_value())] for k in c.get_keys()] for b, c in fire_ch},
               "ghost_keys": [[int(k.get_time().frame_number.value), float(k.get_value())] for k in ghost_ch[0][1].get_keys()]}
        json.dump(rec, open(REC, "w"), indent=1)
        invis, created = _make_invisible(unreal)
        rec["created_invisible"] = created; json.dump(rec, open(REC, "w"), indent=1)
        for n in FLAMES:
            acts[n].modify(); psc[n].modify(); psc[n].set_material(SMOKE_SLOT, invis)
        for n in FIRES:
            acts[n].modify(); acts[n].set_actor_scale3d(unreal.Vector(FIRE_SCALE, FIRE_SCALE, FIRE_SCALE))
        for _b, c in fire_ch:
            for k in c.get_keys(): k.set_value(float(k.get_value()) * LIGHT_GAIN)
        gk = [k for k in ghost_ch[0][1].get_keys() if int(k.get_time().frame_number.value) >= GHOST_FROM]
        mean = sum(float(k.get_value()) for k in gk) / max(1, len(gk))
        for k in gk: k.set_value(max(0.0, mean + GHOST_AMP * (float(k.get_value()) - mean)))
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        rec = json.load(open(REC))
        os.makedirs(bd)
        for f in FILES: shutil.copy2(f, bd)
        for n in FLAMES:
            acts[n].modify(); psc[n].modify()
            orig = rec["slot_materials"][n][SMOKE_SLOT]                       # emitter_materials is not exposed to Python
            psc[n].set_material(SMOKE_SLOT, unreal.load_asset(orig) if orig else None)
        for n in FIRES:
            acts[n].modify(); acts[n].set_actor_scale3d(unreal.Vector(*rec["scales"][n]))
        for b, c in fire_ch:
            old = dict((f, v) for f, v in rec["fire_keys"][b])
            for k in c.get_keys(): k.set_value(old[int(k.get_time().frame_number.value)])
        old = dict((f, v) for f, v in rec["ghost_keys"])
        for k in ghost_ch[0][1].get_keys(): k.set_value(old[int(k.get_time().frame_number.value)])
    else:
        raise RuntimeError("MODE")
    c = census()
    want_content = sorted([SCENE] + ([INVIS] if created else []))
    if c != (want_content, [MAP]): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (c,))
    for p in want_content:
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False): raise RuntimeError("SAVE|" + p)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    got = {n: (psc[n].get_material(SMOKE_SLOT).get_path_name().split(".")[-1] if psc[n].get_material(SMOKE_SLOT) else None) for n in FLAMES}
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3FIRELOOK_%s_OK|run=%s|slot2=%s|scales=%s|created_invisible=%s|backup=%s" % (
        mode, run, got, {n: round(acts[n].get_actor_scale3d().x, 3) for n in FIRES}, created, bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3FIRELOOK_FAILED|%r" % (exc,))
