"""S3 HESSIAN RESIDENT (Gary 8 Oct ~21:00: "yes make the hessian textures stay loaded"; earlier: "some of the hessian
materials have not rendered in time or fully").  Collects every texture used by the materials on the crowd figures'
cloth (all non-Body/Face components of the 15 'P21.S3Crowd' copies + the Shore figures), keeps those whose path or
name looks like the shroud fabric (KEYWORDS), and sets Texture.never_stream = True (record old value; REVERT exact).
Saves only those textures.  Args s3_hessian_resident_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3HESSIAN"}.
Markers S3HESSIAN_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_hessian_resident_record.json"
KEYWORDS = ("hessian", "burlap", "sack", "shroud", "jute", "cloth", "fabric", "weave", "stain")


def main():
    import unreal
    a = json.load(open(HERE + "s3_hessian_resident_args.json")); mode = a["mode"]
    run = datetime.datetime.now().strftime("S3HESSIAN-%Y%m%d-%H%M%S")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    figs = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if ("P21.S3Crowd" in [str(t) for t in x.tags] and "Camera" not in x.get_class().get_name())
            or (str(x.get_actor_label()).startswith("Shore0") and str(x.get_actor_label()).endswith("Clam"))]
    mats, texs = {}, {}
    for x in figs:
        for c in x.get_components_by_class(unreal.MeshComponent):
            if c.get_name() in ("Body", "Face"): continue
            for i in range(c.get_num_materials()):
                m = c.get_material(i)
                if m is None: continue
                mats[m.get_path_name()] = m
    mel = unreal.MaterialEditingLibrary
    def used(m):
        out = []
        if isinstance(m, unreal.MaterialInstance):
            for n in mel.get_texture_parameter_names(m):
                t = mel.get_material_instance_texture_parameter_value(m, n)
                if t: out.append(t)
            base = m.get_base_material()
            if base: out += list(mel.get_used_textures(base))
        elif isinstance(m, unreal.Material):
            out += list(mel.get_used_textures(m))
        return out
    for mp, m in mats.items():
        for t in used(m):
            p = t.get_path_name()
            if "/Sack/" in p:            # the shroud only (MI_Sackcloth_OldGrey_Cloth_v3 -> T_Sack_Hessian230_*), not MH garments
                texs[p] = t
    json.dump({"materials": sorted(mats), "textures": sorted(texs)}, open(HERE + "s3_hessian_resident_dry.json", "w"), indent=1)
    if mode == "DRY":
        unreal.log("S3HESSIAN_DRY_OK|figures=%d|materials=%d|textures=%s" % (len(figs), len(mats),
                   json.dumps({p.split(".")[-1]: bool(t.get_editor_property("never_stream")) for p, t in texs.items()})))
        return
    if a.get("confirm") != "%s S3HESSIAN" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3Hessian-%s" % run; os.makedirs(bd)
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        want = {p: True for p in texs}
        json.dump({"run": run, "backup": bd, "before": {p: bool(t.get_editor_property("never_stream")) for p, t in texs.items()}}, open(REC, "w"), indent=1)
    elif mode == "REVERT":
        want = json.load(open(REC))["before"]
    else:
        raise RuntimeError("MODE")
    changed = []
    for p, v in want.items():
        t = unreal.load_asset(p)
        fp = unreal.SystemLibrary.get_system_path(t)
        if fp and os.path.exists(fp): shutil.copy2(fp, bd)
        if bool(t.get_editor_property("never_stream")) != bool(v):
            t.modify(); t.set_editor_property("never_stream", bool(v)); changed.append(p.split(".")[0])
    c = census()
    if sorted(c[0]) != sorted(changed) or c[1]: raise RuntimeError("CENSUS|%s vs %s|NOTHING SAVED; Don't-Save restart" % (c, changed))
    for p in changed:
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False): raise RuntimeError("SAVE|" + p)
    if census() != ([], []): raise RuntimeError("SAVE_CENSUS|%s" % (census(),))
    bad = [p for p, v in want.items() if bool(unreal.load_asset(p).get_editor_property("never_stream")) != bool(v)]
    if bad: raise RuntimeError("READBACK|%s" % bad)
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3HESSIAN_%s_OK|run=%s|changed=%d|backup=%s" % (mode, run, len(changed), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3HESSIAN_FAILED|%r" % (exc,))
