"""S2 ARRIVAL STRIKE (Gary 8 Oct ~19:00, his words): "the [hangar] should arrive in total darkness as before, and her
lights strike one by one" (and "why is our old S2 even in there?").

FINDINGS behind it (probe_s2_ours.py / probe_s2_arrival.py, 8 Oct):
  [meas] Inside the S2 hangar box, outside Klara's Japanese_Alley level, there are ONLY hangar actors (folder
         'Infinity Stage/Scene 02 Hangar') plus the I2 sleight lantern: no old S2 dressing.
  [meas] Japanese_Alley.umap and LS_NEW_SHRINE.uasset have the same mtime (8 Oct 05:00, her new package). The
         smoke emitter 'Humo_Par4' is HER actor.
  [inf]  So the pipes/smoke/candle set seen 0:05-0:15 is HER new shrine, lit by OUR hangar lights. Her env actors are
         hidden until her cut (hookin 'Hers Dark'), and our hangar lights are never switched off (hookin 'Ours Off'
         covers only the 4 Dusk env actors, from the cut).

WRITES (LS_DevScene_02 only; record s2_arrival_strike_record.json + Backups/PreS2Arrival-<run>; REVERT exact):
  1. OURS DARK: every light/emissive actor of ours in the S2 hangar is hidden over the WHOLE scene [0, END]:
     ghost light + bulb, practicals, uplights, lattice glows (labels below, tag RigAtmos.Scene2Hangar). Gary 7 Oct
     "Hers; ours off in her scenes". The Pinned Exposure PPV is kept.
  2. The 4 existing 'Klara Hookin - Ours Off:' sections (Dusk fog/sky/moon/sun, [376, END]) start at 0 (old ranges
     recorded).
  3. HER STRIKE: each of her local lights (+ her fires with the shrine spot) is hidden from 0 until its strike frame,
     one by one, low to high, the shrine spot and its fires last; RESTORE_STATE section [0, strike) so she is
     untouched from her strike onwards. Her env (sky/directional/fog/PPV) stays on the hookin 'Hers Dark' until the cut.
Conflicts: DRY lists every visibility track already on these actors in LS_DevScene_02 AND in the Hangar Fold
sub-sequence. APPLY refuses on any.
Args s2_arrival_strike_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S2ARRIVAL", "run": ..}.
Markers S2ARRIVAL_<MODE>_OK|run=.. / S2ARRIVAL_FAILED|.."""
import json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/KlaraIngest/"
REC = HERE + "s2_arrival_strike_record.json"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"
SCENE_FILE = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_02.uasset"
END = 3891
OURS_PREFIX = "S2 Arrival Ours Dark: "
HERS_PREFIX = "S2 Arrival Strike: "
HOOK_OURS = "Klara Hookin - Ours Off: "
OURS_TAG = "RigAtmos.Scene2Hangar"
OURS_WORDS = ("Ghost Light", "Practical", "Uplight", "Lattice Glow")       # 'S2 Ghost Light' + 'Bulb' (+ Stand kept)
# her strike order (Scene 2 frames @25; land ~104, cut 376): low practicals -> mid -> high rects -> top spots -> shrine
STRIKES = [(130, ["SpotLight3"]), (145, ["SpotLight2"]), (160, ["K_shrine_spot_3"]),
           (175, ["RectLight_Merged", "RectLight_Merged6"]), (190, ["SpotLight6"]),
           (205, ["RectLight_Merged2", "RectLight_Merged9", "RectLight_Merged10"]), (220, ["SpotLight17"]),
           (235, ["SpotLight24"]), (245, ["SpotLight4"]), (255, ["SpotLight23"]),
           (270, ["RectLight_Merged3", "RectLight_Merged4", "RectLight_Merged5", "RectLight_Merged7",
                  "RectLight_Merged8", "RectLight_Merged11"]),
           (290, ["RectLight_Merged12", "RectLight_Merged13"]), (305, ["SpotLight", "SpotLight5", "SpotLight7"]),
           (330, ["Spot_shrine", "P_Fire", "P_Fire2", "P_Fire3", "P_Fire4", "P_Fire5", "P_Fire6"])]
# F11 (Gary 8 Oct: the cloudy fog "should just be there when we arrive in her scene"): her smoke appears at the cut.
LATE = [(376, ["Humo_Par4"])]
# F15 (Gary 8 Oct: the fog "seems to be the last thing to be on and it doesn't really care about darkness ... a big white
# blob"): measured PIE 9 Oct 01:40, the white frame at S2 0.86 (frame ~3346) is Humo_Par4 in the exit camera -> hidden
# again from EXIT_HIDE to the scene end.
EXIT_HIDE = (3300, ["Humo_Par4"])


def _level(a):
    o = a.get_outer()
    return o.get_outer().get_name() if o and o.get_outer() else "?"


def _vis_tracks(seq, unreal):
    out = {}
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieSceneVisibilityTrack):
                out.setdefault(str(b.get_display_name()), []).append(
                    [[int(s.get_start_frame()) if s.has_start_frame() else None,
                      int(s.get_end_frame()) if s.has_end_frame() else None] for s in t.get_sections()])
    return out


def _add_vis(seq, unreal, actor, prefix, rng, hidden):
    b = seq.add_possessable(actor)
    b.set_display_name(prefix + str(actor.get_actor_label()))
    t = b.add_track(unreal.MovieSceneVisibilityTrack)
    # [decl] the visibility track binds AActor::bHidden and its channel stores VISIBLE (MovieScenePropertyTrack.h:53-56);
    # 'bHiddenInGame' tracks were measured inert in PIE (PIES2VIS-185717, fixed by s2_vis_fix.py).
    t.set_property_name_and_path("bHidden", "bHidden")
    if str(t.get_property_name()) != "bHidden":
        raise RuntimeError("VIS_PROPERTY|%r" % str(t.get_property_name()))
    s = t.add_section(); s.set_range(int(rng[0]), int(rng[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    ch = list(s.get_all_channels())[0]; ch.set_default(not bool(hidden))   # channel = visible
    return b


def main():
    import unreal
    a = json.load(open(HERE + "s2_arrival_strike_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    seq = unreal.load_asset(SCENE)
    if int(seq.get_playback_end()) != END: raise RuntimeError("SCENE_END|%d" % int(seq.get_playback_end()))
    w = ed.get_editor_world()
    acts = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor))
    ours = sorted([x for x in acts if OURS_TAG in [str(t) for t in x.tags] and any(k in str(x.get_actor_label()) for k in OURS_WORDS)
                   and "Stand" not in str(x.get_actor_label())], key=lambda x: str(x.get_actor_label()))
    hers_by = {str(x.get_actor_label()): x for x in acts if "Japanese_Alley" in _level(x)}
    plan_hers, missing = [], []
    for f, labels in STRIKES + LATE:
        for l in labels:
            (plan_hers.append((l, f)) if l in hers_by else missing.append(l))
    hook = [b for b in seq.get_bindings() if str(b.get_display_name()).startswith(HOOK_OURS)]
    # conflicts: existing visibility tracks on our targets in the scene and in the Hangar Fold sub-sequence
    vis_scene = _vis_tracks(seq, unreal)
    fold = None
    for t in seq.get_tracks():
        if str(t.get_display_name()) == "Hangar Fold":
            fold = t.get_sections()[0].get_sequence()
    vis_fold = _vis_tracks(fold, unreal) if fold else {}
    names = [str(x.get_actor_label()) for x in ours] + [l for l, _ in plan_hers]
    conflicts = {n: v for n, v in list(vis_scene.items()) + list(vis_fold.items())
                 if any(n.endswith(m) for m in names) and not n.startswith(OURS_PREFIX) and not n.startswith(HERS_PREFIX)}
    summary = {"ours": [str(x.get_actor_label()) for x in ours], "hers": plan_hers, "hers_missing": missing,
               "hook_ours_off": [str(b.get_display_name()) for b in hook], "fold": fold.get_path_name() if fold else None,
               "conflicts": conflicts}
    json.dump(summary, open(HERE + "s2_arrival_strike_dry.json", "w"), indent=1)
    if mode == "DRY":
        unreal.log("S2ARRIVAL_DRY_OK|run=%s|ours=%d|hers=%d|missing=%s|hook=%d|conflicts=%s" % (
            run, len(ours), len(plan_hers), missing, len(hook), json.dumps(conflicts)[:600]))
        return
    if a.get("confirm") != "%s S2ARRIVAL" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS2Arrival-%s" % run
    if mode == "APPLY":
        if os.path.exists(REC) or missing or conflicts or len(hook) != 4 or len(ours) < 30:
            raise RuntimeError("PRECONDITION|rec=%s|missing=%s|conflicts=%s|hook=%d|ours=%d" % (os.path.exists(REC), missing, list(conflicts), len(hook), len(ours)))
        os.makedirs(bd); shutil.copy2(SCENE_FILE, bd)
        rec = {"run": run, "backup": bd, "hook_before": {}, "added": []}
        for b in hook:
            secs = [s for t in b.get_tracks() for s in t.get_sections()]
            rec["hook_before"][str(b.get_display_name())] = [[int(s.get_start_frame()), int(s.get_end_frame())] for s in secs]
        json.dump(rec, open(REC, "w"), indent=1)
        for b in hook:
            for t in b.get_tracks():
                for s in t.get_sections():
                    s.set_range(0, int(s.get_end_frame()))
        for x in ours:
            _add_vis(seq, unreal, x, OURS_PREFIX, (0, END), True); rec["added"].append(OURS_PREFIX + str(x.get_actor_label()))
        for l, f in plan_hers:
            _add_vis(seq, unreal, hers_by[l], HERS_PREFIX, (0, f), True); rec["added"].append(HERS_PREFIX + l)
        for l in EXIT_HIDE[1]:
            # add_possessable on an already-bound actor returns THAT binding (live 9 Oct: it renamed the strike binding),
            # so the exit window is a second visibility track on the strike binding, not a new binding.
            b = [x for x in seq.get_bindings() if str(x.get_display_name()) == HERS_PREFIX + l][0]
            t = b.add_track(unreal.MovieSceneVisibilityTrack); t.set_property_name_and_path("bHidden", "bHidden")
            s_ = t.add_section(); s_.set_range(EXIT_HIDE[0], END); s_.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
            list(s_.get_all_channels())[0].set_default(False)                    # channel = visible -> False = hidden
        json.dump(rec, open(REC, "w"), indent=1)
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        rec = json.load(open(REC))
        os.makedirs(bd); shutil.copy2(SCENE_FILE, bd)
        for b in list(seq.get_bindings()):
            n = str(b.get_display_name())
            if n in rec["added"]:
                b.remove()
            elif n in rec["hook_before"]:
                rng = rec["hook_before"][n]
                for s, r in zip([s for t in b.get_tracks() for s in t.get_sections()], rng):
                    s.set_range(int(r[0]), int(r[1]))
    else:
        raise RuntimeError("MODE")
    c = census()
    if c != ([SCENE], []):   # get_name() of a package is its full path (/Game/...), not the short name
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (c,))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    names_now = [str(b.get_display_name()) for b in seq.get_bindings()]
    n_ours = len([n for n in names_now if n.startswith(OURS_PREFIX)]); n_hers = len([n for n in names_now if n.startswith(HERS_PREFIX)])
    hook_rng = sorted({tuple([int(s.get_start_frame()), int(s.get_end_frame())]) for b in seq.get_bindings()
                       if str(b.get_display_name()).startswith(HOOK_OURS) for t in b.get_tracks() for s in t.get_sections()})
    if mode == "APPLY" and (n_ours != len(ours) or n_hers != len(plan_hers) or hook_rng != [(0, END)]):
        raise RuntimeError("READBACK|ours=%d|hers=%d|hook=%s" % (n_ours, n_hers, hook_rng))
    if mode == "REVERT":
        if n_ours or n_hers or hook_rng != [(376, END)]: raise RuntimeError("READBACK|ours=%d|hers=%d|hook=%s" % (n_ours, n_hers, hook_rng))
        os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S2ARRIVAL_%s_OK|run=%s|ours=%d|hers=%d|hook=%s|backup=%s" % (mode, run, n_ours, n_hers, hook_rng, bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S2ARRIVAL_FAILED|%r" % (exc,))
