"""S3 CROWD BODY FIX (Gary 8 Oct ~19:40: the 15 copies render "outside of the box/stage/fire area"; his editor moves
"reverted ... when they saved"; the sway reads as "moving up and down").
[meas] pie_crowd_bodies / pie_crowd_pelvis (t=30): each MetaHuman's 'Body' SkeletalMeshComponent carries a RELATIVE
offset of 7-9 m inside its actor (e.g. rel_loc (634.7, -609.5, -39), yaw -90).  The copies inherited it from Shore04/06,
so their pelvises sit ~7.5 m from their roots, at world y 161150-161600, past the marble wall (y 160999).
The P21C additive roll pivots on the ROOT, so a 2.5 deg roll lifts a body 7.5 m away by ~33 cm [inf: 750*sin(2.5)].
[meas] The copies' LS_Clams transform track has an ABSOLUTE section of constant defaults (no keys) over [0, 6263],
which re-poses them on every evaluation, overriding any editor move.
WRITES (map + LS_Clams; record s3_crowd_body_fix_record.json + Backups/PreS3CrowdBody-<run>; REVERT exact):
  COPIES (tag P21.S3Crowd, not cameras): Body relative X/Y -> 0 (Z, rotation kept), so the body stands on the root,
    i.e. the planned cluster spot; their ABSOLUTE transform section is REMOVED (defaults recorded) and the actor's level
    transform is set to those defaults, so Gary's editor moves persist.  Additive roll sections kept.
  HEROES with an offset > 20 cm (Shore01_M56, Shore04_F55, Shore06_F25): Body relative X/Y -> 0, and every ABSOLUTE
    section's Location.X/Y default + keys in LS_Clams are shifted by the world offset, so the BODY stays where it is.
Args s3_crowd_body_fix_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3CROWDBODY", "run"}.
Markers S3CROWDBODY_<MODE>_OK|run=.. / S3CROWDBODY_FAILED."""
import json, math, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_crowd_body_fix_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CLAMS = "/Game/Scenes/LS_Clams"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap", "E:/PussStage/Content/Scenes/LS_Clams.uasset"]
TAG = "P21.S3Crowd"
MIN_OFF = 20.0


def _body(a, unreal):
    for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
        if c.get_name() == "Body":
            return c
    return None


def _abs_sections(binding, unreal):
    out = []
    for t in binding.get_tracks():
        if isinstance(t, unreal.MovieScene3DTransformTrack):
            for s in t.get_sections():
                bt = s.get_blend_type()          # MovieSceneBlendTypeField (s3_crowd_structure.py _blend_snapshot) [prec]
                v = str(bt.get_editor_property("blend_type")).upper() if bt.get_editor_property("is_valid") else "UNSET"
                if "ADDITIVE" not in v and "RELATIVE" not in v:
                    out.append((t, s))
    return out


def _chans(s):
    return {str(c.get_name()).split("_")[0]: c for c in s.get_all_channels()}       # Location.X_183 -> Location.X


def main():
    import unreal
    a = json.load(open(HERE + "s3_crowd_body_fix_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    clams = unreal.load_asset(CLAMS)
    crec = json.load(open(HERE + "s3_crowd_structure_record.json"))           # label -> LS_Clams binding guid [meas record]
    gid = {c["label"]: c["actor_binding_guid"] for c in crec["copies"]}
    by_guid = {b.get_id().export_text(): b for b in clams.get_bindings()}     # s3_crowd_structure.py:796 [prec]
    bind_by = {lab: by_guid.get(g) for lab, g in gid.items()}
    # heroes: the record's hero binding_guid is the ANIMATION binding (8 Oct APPLY shifted nothing, measured); the
    # transform lives on the binding whose display name starts with the figure id ('Shore01_M56 Shore...').
    for h in crec["heroes"]:
        hits = [b for b in clams.get_bindings() if str(b.get_display_name()).startswith(h["id"])
                and any(isinstance(t, unreal.MovieScene3DTransformTrack) for t in b.get_tracks())]
        if len(hits) == 1: bind_by[h["id"] + " Clam"] = hits[0]
    acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    figs = [x for x in acts if (TAG in [str(t) for t in x.tags] and "Camera" not in x.get_class().get_name())
            or (str(x.get_actor_label()).startswith("Shore0") and str(x.get_actor_label()).endswith("Clam"))]
    plan = []
    for x in figs:
        lab = str(x.get_actor_label()); body = _body(x, unreal)
        if body is None: raise RuntimeError("NO_BODY|" + lab)
        rl = body.get_editor_property("relative_location")
        if math.hypot(rl.x, rl.y) < MIN_OFF: continue
        yaw = math.radians(x.get_actor_rotation().yaw)
        off = [rl.x * math.cos(yaw) - rl.y * math.sin(yaw), rl.x * math.sin(yaw) + rl.y * math.cos(yaw)]
        copy = TAG in [str(t) for t in x.tags]
        b = bind_by.get(lab)
        if b is None: raise RuntimeError("NO_CLAMS_BINDING|" + lab)
        secs = _abs_sections(b, unreal)
        if copy and len(secs) != 1: raise RuntimeError("COPY_ABS_SECTIONS|%s|%d" % (lab, len(secs)))
        plan.append({"label": lab, "copy": copy, "rel": [rl.x, rl.y, rl.z], "world_off": [round(off[0], 2), round(off[1], 2)], "abs_sections": len(secs)})
    if mode == "DRY":
        unreal.log("S3CROWDBODY_DRY_OK|run=%s|n=%d|copies=%d|heroes=%s" % (run, len(plan), sum(p["copy"] for p in plan),
                   [(p["label"], p["world_off"]) for p in plan if not p["copy"]]))
        return
    if a.get("confirm") != "%s S3CROWDBODY" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3CrowdBody-%s" % run
    xby = {str(x.get_actor_label()): x for x in figs}
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        os.makedirs(bd)
        for f in FILES: shutil.copy2(f, bd)
        rec = {"run": run, "backup": bd, "rows": []}
        for p in plan:
            x = xby[p["label"]]; body = _body(x, unreal); b = bind_by[p["label"]]
            row = dict(p)
            x.modify(); body.modify()
            body.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, p["rel"][2]))
            if p["copy"]:
                t, s = _abs_sections(b, unreal)[0]
                ch = _chans(s)
                d = {k: float(c.get_default()) for k, c in ch.items() if c.has_default()}
                row["removed_section"] = {"defaults": d, "range": [int(s.get_start_frame()), int(s.get_end_frame())]}
                x.set_actor_location_and_rotation(unreal.Vector(d["Location.X"], d["Location.Y"], d["Location.Z"]),
                                                  unreal.Rotator(roll=d["Rotation.X"], pitch=d["Rotation.Y"], yaw=d["Rotation.Z"]), False, True)
                t.remove_section(s)
            else:
                row["shifted"] = []
                for t, s in _abs_sections(b, unreal):
                    ch = _chans(s)
                    for k, dv in (("Location.X", p["world_off"][0]), ("Location.Y", p["world_off"][1])):
                        c = ch[k]
                        if c.has_default(): c.set_default(float(c.get_default()) + dv)
                        for key in c.get_keys(): key.set_value(float(key.get_value()) + dv)
                    row["shifted"].append(str(s.get_name()))
            rec["rows"].append(row)
        json.dump(rec, open(REC, "w"), indent=1)
    elif mode == "HERO_SHIFT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        rec = json.load(open(REC))
        os.makedirs(bd)
        for f in FILES: shutil.copy2(f, bd)
        for row in rec["rows"]:
            if row["copy"] or row.get("shifted"): continue
            b = bind_by[row["label"]]; row["shifted"] = []
            for t, s in _abs_sections(b, unreal):
                ch = _chans(s)
                for k, dv in (("Location.X", row["world_off"][0]), ("Location.Y", row["world_off"][1])):
                    c = ch[k]
                    if c.has_default(): c.set_default(float(c.get_default()) + dv)
                    for key in c.get_keys(): key.set_value(float(key.get_value()) + dv)
                row["shifted"].append(str(s.get_name()))
            if not row["shifted"]: raise RuntimeError("HERO_NO_ABS|%s|NOTHING SAVED; Don't-Save restart" % row["label"])
        json.dump(rec, open(REC, "w"), indent=1)
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        rec = json.load(open(REC))
        os.makedirs(bd)
        for f in FILES: shutil.copy2(f, bd)
        for row in rec["rows"]:
            x = xby[row["label"]]; body = _body(x, unreal); b = bind_by[row["label"]]
            x.modify(); body.modify()
            body.set_editor_property("relative_location", unreal.Vector(*row["rel"]))
            if row["copy"]:
                t = [t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)][0]
                s = t.add_section(); s.set_range(*row["removed_section"]["range"])
                s.set_blend_type(unreal.MovieSceneBlendType.ABSOLUTE)
                ch = _chans(s)
                for k, v in row["removed_section"]["defaults"].items(): ch[k].set_default(v)
            else:
                for t, s in _abs_sections(b, unreal):
                    ch = _chans(s)
                    for k, dv in (("Location.X", row["world_off"][0]), ("Location.Y", row["world_off"][1])):
                        c = ch[k]
                        if c.has_default(): c.set_default(float(c.get_default()) - dv)
                        for key in c.get_keys(): key.set_value(float(key.get_value()) - dv)
    else:
        raise RuntimeError("MODE")
    c = census()
    want = ([CLAMS], []) if mode == "HERO_SHIFT" else ([CLAMS], [MAP])
    if c != want: raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (c,))
    ok1 = unreal.EditorAssetLibrary.save_asset(CLAMS, only_if_is_dirty=False)
    ok2 = True if mode == "HERO_SHIFT" else unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    if not (ok1 and ok2) or census() != ([], []): raise RuntimeError("SAVE|%s" % (census(),))
    left = [str(x.get_actor_label()) for x in figs if math.hypot(*[getattr(_body(x, unreal).get_editor_property("relative_location"), k) for k in "xy"]) >= MIN_OFF]
    if mode == "APPLY" and left: raise RuntimeError("READBACK|offsets_left=%s" % left)
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3CROWDBODY_%s_OK|run=%s|rows=%d|offsets_left=%d|backup=%s" % (mode, run, len(rec["rows"]), len(left), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3CROWDBODY_FAILED|%r" % (exc,))
