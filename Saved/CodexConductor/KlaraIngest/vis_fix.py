"""VISIBILITY FIX, any sequence (generalised from s2_vis_fix.py, 8 Oct; S2 APPLIED as VISFIX-20261008-1).
Args vis_fix_args.json add {"sequence": "/Game/...", "file": "E:/PussStage/Content/....uasset", "tag": "S1"}: fixes EVERY
visibility track bound to bHiddenInGame in that sequence (any binding name).  Record vis_fix_record_<tag>.json.
Original S2 notes: The Python-added visibility tracks in LS_DevScene_02 bind 'bHiddenInGame' with True=hidden.
[decl] UMovieSceneVisibilityTrack binds AActor::bHidden and its bool channel stores VISIBLE semantics
(MovieScenePropertyTrack.h:53-56).  [meas] PIE probe PIES2VIS-185717: none of them took effect (Moon visible at
S2+16 s under 'Ours Off' [376, END]; our lattice/ghost/practicals visible under 'S2 Arrival Ours Dark').
Fix, per visibility track on bindings named 'Klara Hookin - Ours Off:/Hers Dark:' and 'S2 Arrival Ours Dark:/Strike:':
property -> bHidden/bHidden, every section's channel default -> NOT old default (same intent: hidden), keys likewise.
Record s2_vis_fix_record.json (old property + defaults) + Backups/PreVisFix-<run>; REVERT exact.
Args vis_fix_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> VISFIX", "run"}.  VISFIX_<MODE>_OK / _FAILED."""
import json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/KlaraIngest/"
ARGS = json.load(open(HERE + "vis_fix_args.json"))
REC = HERE + "vis_fix_record_%s.json" % ARGS["tag"]
SCENE = ARGS["sequence"]
SCENE_FILE = ARGS["file"]


def _tracks(seq, unreal):
    for b in seq.get_bindings():
        n = str(b.get_display_name()) + " #" + str(b.get_id())
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieSceneVisibilityTrack) and str(t.get_property_name()) in ("bHiddenInGame", "bHidden"):
                yield n, t


def _state(t):
    out = []
    for s in t.get_sections():
        ch = list(s.get_all_channels())[0]
        out.append({"default": bool(ch.get_default()) if ch.has_default() else None,
                    "keys": [[int(k.get_time().frame_number.value), bool(k.get_value())] for k in ch.get_keys()]})
    return {"property": str(t.get_property_name()), "path": str(t.get_property_path()), "sections": out}


def main():
    import unreal
    a = ARGS
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    seq = unreal.load_asset(SCENE)
    rows = list(_tracks(seq, unreal))
    before = {n: _state(t) for n, t in rows}
    props = sorted({v["property"] for v in before.values()})
    if mode == "DRY":
        unreal.log("VISFIX_DRY_OK|run=%s|tracks=%d|properties=%s|sample=%s" % (run, len(rows), props, json.dumps(list(before.items())[:2])))
        return
    if a.get("confirm") != "%s VISFIX" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreVisFix-%s" % run
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        before = {n: v for n, v in before.items() if v["property"] == "bHiddenInGame"}   # only the inert ones
        if not before: raise RuntimeError("NOTHING_TO_FIX|%s" % props)
        os.makedirs(bd); shutil.copy2(SCENE_FILE, bd)
        json.dump({"run": run, "backup": bd, "before": before}, open(REC, "w"), indent=1)
        target = {n: ("bHidden", "bHidden", True) for n in before}
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        old = json.load(open(REC))["before"]
        os.makedirs(bd); shutil.copy2(SCENE_FILE, bd)
        target = {n: (old[n]["property"], old[n]["path"], True) for n in before if n in old}
    else:
        raise RuntimeError("MODE")
    for n, t in rows:
        if n not in target: continue
        p, path, flip = target[n]
        t.set_property_name_and_path(p, path)
        for s in t.get_sections():
            ch = list(s.get_all_channels())[0]
            if ch.has_default(): ch.set_default(not bool(ch.get_default()))
            for k in ch.get_keys(): k.set_value(not bool(k.get_value()))
    after = {n: _state(t) for n, t in _tracks(seq, unreal)}
    for n, b in before.items():
        if n not in target: continue
        x = after[n]
        want_p = target[n][0]
        if x["property"] != want_p or any(
                (sb["default"] is not None and sa["default"] != (not sb["default"])) or
                [[f, not v] for f, v in sb["keys"]] != sa["keys"] for sb, sa in zip(b["sections"], x["sections"])):
            raise RuntimeError("READBACK_BEFORE_SAVE|%s|%s|NOTHING SAVED; Don't-Save restart" % (n, x))
    if census() != ([SCENE], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("VISFIX_%s_OK|run=%s|tracks=%d|property=%s|backup=%s" % (mode, run, len(after), sorted({v["property"] for v in after.values()}), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("VISFIX_FAILED|%r" % (exc,))
