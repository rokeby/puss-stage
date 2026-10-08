"""READ-ONLY: S3 opening timeline + every sky/sun light in the world and who keys it.
Writes probe_s3_opening.json; marker PROBE_S3_OPENING_OK|run=.. / PROBE_S3_OPENING_FAILED. No modify, no save."""
import json
import time

OUT = "E:/PussStage/Saved/CodexConductor/probe_s3_opening.json"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_%02d"
MASTER_GLOB = "/Game/InfinityStage"


def _sec(ms, f):
    return round(ms.get_tick_resolution().denominator * f / float(ms.get_tick_resolution().numerator), 3) \
        if hasattr(ms, "get_tick_resolution") else None


def main():
    import unreal
    run = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    lib = unreal.EditorLoadingAndSavingUtils
    c0 = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    out = {"run": run}

    def tick(seq):
        r = seq.get_tick_resolution()
        return r.numerator / float(r.denominator)

    def dump_seq(sp, kinds=None):
        seq = unreal.load_asset(sp)
        if seq is None:
            return "LOAD_NONE"
        tr = tick(seq)
        dr = seq.get_display_rate()
        rows = []
        for b in seq.get_bindings():
            par = b.get_parent()
            owner = str(par.get_display_name()) if par is not None and par.is_valid() else ""
            for t in b.get_tracks():
                cls = t.get_class().get_name()
                for s in t.get_sections():
                    rng = [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None]
                    times = set()
                    vals = []
                    for ch in s.get_all_channels():
                        try:
                            ks = ch.get_keys()
                        except Exception:
                            continue
                        for k in ks:
                            times.add(k.get_time().frame_number.value)
                        if cls in ("MovieSceneVisibilityTrack", "MovieSceneFloatTrack") or "ntensity" in str(t.get_display_name()):
                            vals.append([(round(k.get_time().frame_number.value / tr, 3), round(float(k.get_value()), 3)) for k in ks][:8])
                    rows.append({"binding": str(b.get_display_name()), "owner": owner, "track": str(t.get_display_name()),
                                 "cls": cls, "range_display": rng,
                                 "key_s": [round(x / tr, 3) for x in sorted(times)][:3] + ["..."] + [round(x / tr, 3) for x in sorted(times)][-3:] if times else [],
                                 "vals": vals[:2]})
        # master tracks (subsections)
        subs = []
        for mt in seq.get_tracks():
            for s in mt.get_sections():
                d = {"track": str(mt.get_display_name()), "cls": mt.get_class().get_name(),
                     "range_display": [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None]}
                try:
                    d["sub"] = s.get_sequence().get_path_name()
                except Exception:
                    pass
                subs.append(d)
        return {"tick": tr, "display": [dr.numerator, dr.denominator], "playback": [seq.get_playback_start(), seq.get_playback_end()],
                "rows": rows, "master": subs}

    out["rise"] = dump_seq(RISE)
    out["scene3"] = dump_seq(SCENE % 3)
    # sky / sun census
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    w = ed.get_editor_world()
    sky = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        cls = a.get_class().get_name()
        hit = isinstance(a, (unreal.SkyLight, unreal.DirectionalLight, unreal.SkyAtmosphere)) or "Sky" in cls or "Cloud" in cls
        if not hit:
            continue
        row = {"label": str(a.get_actor_label()), "cls": cls, "level": a.get_outermost().get_name(),
               "hidden_game": bool(a.get_editor_property("hidden")) if True else None}
        lcs = a.get_components_by_class(unreal.LightComponentBase)
        row["lights"] = [{"comp": c.get_name(), "cls": c.get_class().get_name(), "intensity": c.get_editor_property("intensity"),
                          "visible": c.is_visible(), "affects_world": c.get_editor_property("affects_world")} for c in lcs]
        sky.append(row)
    out["sky"] = sky
    # which scene sequences bind sky actors
    labels = set(r["label"] for r in sky)
    binders = {}
    for n in range(1, 7):
        seq = unreal.load_asset(SCENE % n)
        if seq is None:
            continue
        for b in seq.get_bindings():
            nm = str(b.get_display_name())
            if nm in labels or "Sky" in nm or "Sun" in nm:
                binders.setdefault(SCENE % n, []).append([nm, [str(t.get_display_name()) for t in b.get_tracks()]])
    out["sky_binders"] = binders
    c1 = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    out["census"] = [c0, c1]
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    unreal.log("PROBE_S3_OPENING_OK|run=%s|sky=%d|census_unchanged=%s" % (run, len(sky), c0 == c1))


try:
    main()
except Exception as exc:
    import unreal, traceback
    unreal.log_error("PROBE_S3_OPENING_FAILED|%r|%s" % (exc, traceback.format_exc().replace("\n", " / ")[-600:]))
