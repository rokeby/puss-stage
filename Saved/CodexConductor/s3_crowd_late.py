"""S3 CROWD LATE (Gary 8 Oct ~20:15, his words):
  (3) "the chorus is quiet between verses in between frame 3766 and 3808, during the shadow shot. It'd be nice if that
      part the swaying could slow so it begins with the new verse."
  (4) "DURING the wall shot, I'd like to move a bunch of the figures INTO the ocean, to the left of the clam's space and in
      the space behind, maybe 9 figures total, so they look like they've been washed away. They should be in FRENZY
      mode here. So after the wall shot, we see them in the background."
All in LS_Clams (frames = Scene frames + 22, s3_crowd_structure plan scene_to_ls_clams_frames).
SWAY CALM: every additive Rotation.X (sway roll) key of the 20 figures in Scene [CALM_A, CALM_D] is scaled by an
  envelope: 1 -> CALM_FLOOR over [CALM_A, CALM_B], CALM_FLOOR to CALM_C, back to 1 over [CALM_C, CALM_D].
OCEAN FRENZY (9 copies, OCEAN below), from Scene frame T_SWAP (inside the wall shot S3 Shot B06 [4188, 4548],
  plan handprint_trim):
  - a new ABSOLUTE transform section [T_SWAP+22, END] at the ocean spot (constant defaults; before it the level
    placement by the fire holds);
  - their additive sway sections end at T_SWAP+22;
  - every animation section ending after T_SWAP+22 is trimmed to it (sections starting after it are deactivated, not
    deleted), and ONE section [T_SWAP+22, END] plays the source's FRENZY span (plan sources[*].frenzy_span) at 0.6x,
    looping (the section is longer than the span).
  z: dune grid surface + source hero offset - 2 cm, precomputed offline into s3_crowd_late_z.json (as regather).
Record s3_crowd_late_record.json + Backups/PreS3CrowdLate-<run>; saves LS_Clams only.  REVERT exact (keys, ranges,
actives; added sections removed).  Args s3_crowd_late_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3LATE",
"run", "parts": ["calm", "ocean"]}.  S3LATE_<MODE>_OK / _FAILED."""
import json, math, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_crowd_late_record.json"
CLAMS = "/Game/Scenes/LS_Clams"
CLAMS_FILE = "E:/PussStage/Content/Scenes/LS_Clams.uasset"
OFF = 22
CALM_A, CALM_B, CALM_C, CALM_D, CALM_FLOOR = 3754, 3774, 3804, 3828, 0.2
T_SWAP = 4210
END = 6263
OCEAN = {   # world cm (x, y, yaw); left of the clam (y > 160530) and behind it (x 15850-16100), clam (15484, 160169) r 360
    "S3 Crowd 01": (15480.0, 160640.0, 200.0), "S3 Crowd 03": (15650.0, 160790.0, 160.0),
    "S3 Crowd 05": (15420.0, 160880.0, 215.0), "S3 Crowd 07": (15770.0, 160600.0, 175.0),
    "S3 Crowd 08": (15900.0, 159450.0, 150.0), "S3 Crowd 10": (16000.0, 159800.0, 190.0),
    "S3 Crowd 12": (15880.0, 160090.0, 205.0), "S3 Crowd 13": (16050.0, 160420.0, 170.0),
    "S3 Crowd 15": (15950.0, 160760.0, 195.0)}


def _env(f):
    if f <= CALM_A or f >= CALM_D: return 1.0
    if f < CALM_B: return 1.0 - (1.0 - CALM_FLOOR) * (f - CALM_A) / float(CALM_B - CALM_A)
    if f <= CALM_C: return CALM_FLOOR
    return CALM_FLOOR + (1.0 - CALM_FLOOR) * (f - CALM_C) / float(CALM_D - CALM_C)


def _blend(s):
    bt = s.get_blend_type()
    return str(bt.get_editor_property("blend_type")).upper() if bt.get_editor_property("is_valid") else "UNSET"


def _chans(s):
    return {str(c.get_name()).split("_")[0]: c for c in s.get_all_channels()}


def _rate_get(p):
    v = p.get_editor_property("play_rate")
    return float(v.to_fixed_play_rate()) if hasattr(v, "to_fixed_play_rate") else float(v)


def main():
    import unreal
    a = json.load(open(HERE + "s3_crowd_late_args.json"))
    run, mode, parts = a["run"], a["mode"], a.get("parts", ["calm", "ocean"])
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    clams = unreal.load_asset(CLAMS)
    plan = json.load(open(HERE + "s3_crowd_structure_plan.json"))
    srcs = plan["sources"]
    crec = json.load(open(HERE + "s3_crowd_structure_record.json"))
    by_guid = {b.get_id().export_text(): b for b in clams.get_bindings()}
    copies = {c["label"]: by_guid.get(c["actor_binding_guid"]) for c in crec["copies"]}
    heroes = {}
    for b in clams.get_bindings():
        n = str(b.get_display_name())
        if n.startswith("Shore0") and any(isinstance(t, unreal.MovieScene3DTransformTrack) for t in b.get_tracks()):
            heroes[n] = b
    figures = {**{k: v for k, v in copies.items() if v is not None}, **heroes}
    children = {}
    for b in clams.get_bindings():
        par = b.get_parent()
        if par is not None and par.get_id().export_text() in [f.get_id().export_text() for f in figures.values()]:
            children.setdefault(par.get_id().export_text(), []).append(b)
    zfile = json.load(open(HERE + "s3_crowd_late_z.json"))["root_z"] if os.path.exists(HERE + "s3_crowd_late_z.json") else {}
    # ---- plan
    calm_rows, ocean_rows = [], []
    if "calm" in parts:
        for n, b in figures.items():
            for t in b.get_tracks():
                if not isinstance(t, unreal.MovieScene3DTransformTrack): continue
                for s in t.get_sections():
                    if "ADDITIVE" not in _blend(s): continue
                    rx = _chans(s)["Rotation.X"]
                    ks = [k for k in rx.get_keys() if CALM_A + OFF < int(k.get_time().frame_number.value) < CALM_D + OFF]
                    if ks: calm_rows.append({"figure": n, "section": str(s.get_name()), "n": len(ks)})
    if "ocean" in parts:
        # Gary 8 Oct ~20:40: "the figures should be starting to frenzy here but appear to be unmoving" -> EVERY figure
        # (15 copies + the 5 Shore heroes, not M53) plays FRENZY from the swap; only the OCEAN 9 also move.
        ocean_labels = {}
        for short, (x, y, yaw) in OCEAN.items():
            lab = [k for k in copies if k.startswith(short + " (")]
            if len(lab) != 1 or copies[lab[0]] is None: raise RuntimeError("OCEAN_MEMBER|" + short)
            ocean_labels[lab[0]] = (x, y, yaw)
        for lab, b in sorted(figures.items()):
            if lab.startswith("Shore05"): continue
            src = lab.split("(from ")[1].rstrip(")") if "(from " in lab else lab.split(" ")[0]
            fz = srcs[src]["frenzy_span"]
            anim_tracks = [t for c in children.get(b.get_id().export_text(), []) for t in c.get_tracks()
                           if isinstance(t, unreal.MovieSceneSkeletalAnimationTrack)]
            if len(anim_tracks) != 1: raise RuntimeError("ANIM_TRACK|%s|%d" % (lab, len(anim_tracks)))
            xyz = None
            if lab in ocean_labels:
                z = zfile.get(lab)
                if z is None: raise RuntimeError("NO_Z|" + lab)
                xyz = [ocean_labels[lab][0], ocean_labels[lab][1], z, ocean_labels[lab][2]]
            ocean_rows.append({"label": lab, "src": src, "xyzyaw": xyz, "frenzy": [fz["source_in_seconds"], fz["source_out_seconds"]],
                               "anim_sections": len(anim_tracks[0].get_sections())})
    if mode == "DRY":
        json.dump({"calm": calm_rows, "ocean": ocean_rows}, open(HERE + "s3_crowd_late_dry.json", "w"), indent=1)
        unreal.log("S3LATE_DRY_OK|run=%s|calm_sections=%d|calm_keys=%d|ocean=%d|figures=%d" % (
            run, len(calm_rows), sum(r["n"] for r in calm_rows), len(ocean_rows), len(figures)))
        return
    if a.get("confirm") != "%s S3LATE" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3CrowdLate-%s" % run
    tick = clams.get_tick_resolution(); tps = float(tick.numerator) / float(tick.denominator)
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        os.makedirs(bd); shutil.copy2(CLAMS_FILE, bd)
        rec = {"run": run, "backup": bd, "parts": parts, "calm": [], "ocean": []}
        json.dump(rec, open(REC, "w"), indent=1)
        if "calm" in parts:
            for n, b in figures.items():
                for t in b.get_tracks():
                    if not isinstance(t, unreal.MovieScene3DTransformTrack): continue
                    for s in t.get_sections():
                        if "ADDITIVE" not in _blend(s): continue
                        for k in _chans(s)["Rotation.X"].get_keys():
                            f = int(k.get_time().frame_number.value) - OFF
                            e = _env(f)
                            if e < 1.0:
                                rec["calm"].append([n, str(s.get_name()), f + OFF, float(k.get_value())])
                                k.set_value(float(k.get_value()) * e)
        if "ocean" in parts:
            for row in ocean_rows:
                b = figures[row["label"]]; o = {"label": row["label"], "sway_ends": [], "anim_trim": [], "added": {}}
                tt = [t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)][0]
                for s in tt.get_sections():
                    if "ADDITIVE" in _blend(s) and int(s.get_end_frame()) > T_SWAP + OFF:
                        o["sway_ends"].append([str(s.get_name()), int(s.get_start_frame()), int(s.get_end_frame())])
                        s.set_end_frame(T_SWAP + OFF)
                if row["xyzyaw"] is not None:
                    ns = tt.add_section(); ns.set_range(T_SWAP + OFF, END); ns.set_blend_type(unreal.MovieSceneBlendType.ABSOLUTE)
                    x, y, z, yaw = row["xyzyaw"]
                    ch = _chans(ns)
                    for k, v in (("Location.X", x), ("Location.Y", y), ("Location.Z", z), ("Rotation.X", 0.0), ("Rotation.Y", 0.0),
                                 ("Rotation.Z", yaw), ("Scale.X", 1.0), ("Scale.Y", 1.0), ("Scale.Z", 1.0)):
                        ch[k].set_default(float(v))
                    o["added"]["transform"] = str(ns.get_name())
                at = [t for c in children[b.get_id().export_text()] for t in c.get_tracks() if isinstance(t, unreal.MovieSceneSkeletalAnimationTrack)][0]
                tmpl = None
                for s in at.get_sections():
                    st, en = int(s.get_start_frame()), int(s.get_end_frame())
                    if en <= T_SWAP + OFF: continue
                    tmpl = tmpl or s
                    if st >= T_SWAP + OFF:
                        o["anim_trim"].append([str(s.get_name()), st, en, bool(s.is_active()), "deactivated"]); s.set_is_active(False)
                    else:
                        o["anim_trim"].append([str(s.get_name()), st, en, bool(s.is_active()), "trimmed"]); s.set_end_frame(T_SWAP + OFF)
                if tmpl is None: raise RuntimeError("NO_ANIM_AFTER_SWAP|%s|NOTHING SAVED; Don't-Save restart" % row["label"])
                anim = tmpl.get_editor_property("params").get_editor_property("animation")
                fs = at.add_section(); p = fs.get_editor_property("params")
                p.set_editor_property("animation", anim)
                p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(round(row["frenzy"][0] * tps))))
                length = float(anim.get_play_length())
                p.set_editor_property("end_frame_offset", unreal.FrameNumber(int(round(max(0.0, length - row["frenzy"][1]) * tps))))
                rate = p.get_editor_property("play_rate")
                if hasattr(rate, "set_fixed_play_rate"):
                    rate.set_fixed_play_rate(0.6); p.set_editor_property("play_rate", rate)
                else:
                    p.set_editor_property("play_rate", 0.6)
                fs.set_editor_property("params", p); fs.set_range(T_SWAP + OFF, END); fs.set_row_index(tmpl.get_row_index())
                if abs(_rate_get(fs.get_editor_property("params")) - 0.6) > 1e-6: raise RuntimeError("RATE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % row["label"])
                o["added"]["anim"] = str(fs.get_name())
                rec["ocean"].append(o)
        json.dump(rec, open(REC, "w"), indent=1)
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        rec = json.load(open(REC))
        os.makedirs(bd); shutil.copy2(CLAMS_FILE, bd)
        for n, sname, f, v in rec["calm"]:
            for t in figures[n].get_tracks():
                for s in t.get_sections():
                    if str(s.get_name()) == sname:
                        for k in _chans(s)["Rotation.X"].get_keys():
                            if int(k.get_time().frame_number.value) == f: k.set_value(v)
        for o in rec["ocean"]:
            b = figures[o["label"]]
            tt = [t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)][0]
            for s in list(tt.get_sections()):
                if str(s.get_name()) == o["added"].get("transform"): tt.remove_section(s)
            for sname, st, en in o["sway_ends"]:
                for s in tt.get_sections():
                    if str(s.get_name()) == sname: s.set_end_frame(en)
            at = [t for c in children[b.get_id().export_text()] for t in c.get_tracks() if isinstance(t, unreal.MovieSceneSkeletalAnimationTrack)][0]
            for s in list(at.get_sections()):
                if str(s.get_name()) == o["added"]["anim"]: at.remove_section(s)
            for sname, st, en, act, how in o["anim_trim"]:
                for s in at.get_sections():
                    if str(s.get_name()) == sname:
                        s.set_end_frame(en); s.set_is_active(act)
    else:
        raise RuntimeError("MODE")
    if census() != ([CLAMS], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(CLAMS, only_if_is_dirty=False) or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3LATE_%s_OK|run=%s|calm_keys=%d|ocean=%d|backup=%s" % (mode, run, len(rec["calm"]), len(rec["ocean"]), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3LATE_FAILED|%r" % (exc,))
