"""S3 organic rect lights + brighter clam (Gary 8 Oct ~06:25): "the clam's light's lumens can actually increase by 40% as
the scene is now kind of dark. Can you give a flame like flicker to the rect lights too so they're a bit more organic?"
and "maybe the rect lights can light surfaces at 25%".
  1. S3 Drama Clam Key: every key value x1.4.
  2. Every S3 RectLight actor: diffuse_scale 0.1 -> 0.25 (specular stays 1.0).
  3. Flame flicker on every S3 RectLight with a non-zero curve:
     - keyed (an Intensity track in LS_DevScene_03, e.g. S3.WavesV3.Light): the existing curve is sampled every 2 frames
       from its first non-zero key to the end, multiplied by a deterministic flame factor and re-keyed (LINEAR); fades
       and the take dim-outs are preserved because the base curve is multiplied, not replaced;
     - un-keyed (e.g. Gary's Warm Side2/3/4): a new 'S3.Flame' Intensity track = its current intensity x flame.
     Flame factor (per-light phase): 0.82 + 0.10 sin(2pi 1.3t) + 0.06 sin(2pi 3.7t) + 0.04 sin(2pi 5.9t), with
     occasional gutter dips x0.7.  Lights whose curve is all zero (the strike group) are skipped.
Record (all before curves + scales) + Backups first; saves map + LS_DevScene_03.
Args s3_rect_flame_args.json {"mode":"DRY"|"APPLY","run":..}.  S3FLAME_<MODE>_OK / S3FLAME_FAILED."""
import json
import math
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
END = 6240
STEP = 2
DIFF = 0.25
CLAM_GAIN = 1.4
RUN = {"run": "?"}


def flame(f, phase):
    t = f / 24.0
    v = 0.82 + 0.10 * math.sin(2 * math.pi * 1.3 * t + phase) + 0.06 * math.sin(2 * math.pi * 3.7 * t + 1.7 * phase) \
        + 0.04 * math.sin(2 * math.pi * 5.9 * t + 2.3 * phase)
    if math.sin(2 * math.pi * 0.19 * t + phase) > 0.97:
        v *= 0.7
    return v


def curve_at(pts, f):
    if f <= pts[0][0]:
        return pts[0][1]
    if f >= pts[-1][0]:
        return pts[-1][1]
    for (f0, v0), (f1, v1) in zip(pts, pts[1:]):
        if f0 <= f <= f1:
            return v0 if f1 == f0 else v0 + (v1 - v0) * (f - f0) / float(f1 - f0)
    return pts[-1][1]


def main():
    import unreal
    a = json.load(open(HERE + "s3_rect_flame_args.json"))
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
    fr = lambda k: int(k.get_time().frame_number.value)
    w = ed.get_editor_world()
    rects = {str(x.get_actor_label()): x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
             if str(x.get_actor_label()).startswith("S3 ") and x.get_component_by_class(unreal.RectLightComponent)}
    seq = unreal.load_asset(SC)
    keyed, clam = {}, None
    for b in seq.get_bindings():
        p = b.get_parent()
        own = str(p.get_display_name()) if p is not None and p.is_valid() else ""
        for t in b.get_tracks():
            if "ntensity" not in str(t.get_property_name()) if hasattr(t, "get_property_name") else True:
                pass
            if t.get_class().get_name() != "MovieSceneFloatTrack":
                continue
            chs = [c for s in t.get_sections() for c in s.get_all_channels()]
            if len(chs) != 1:
                continue
            if own in rects:
                keyed.setdefault(own, []).append(chs[0])
            if own == "S3 Drama Clam Key" and str(t.get_display_name()) == "S3.Drama.Light":
                clam = chs[0]
    plan = {}
    for lab in sorted(rects):
        if lab in keyed:
            if len(keyed[lab]) != 1:
                raise RuntimeError("MULTI_TRACK|%s" % lab)
            pts = sorted((fr(k), float(k.get_value())) for k in keyed[lab][0].get_keys())
            if max(v for _, v in pts) <= 1e-6:
                continue
            plan[lab] = {"kind": "keyed", "pts": pts}
        else:
            i = rects[lab].get_component_by_class(unreal.RectLightComponent).intensity
            if i > 1e-6:
                plan[lab] = {"kind": "static", "intensity": i}
    if mode == "DRY":
        unreal.log("S3FLAME_DRY_OK|run=%s|rects=%d|flicker=%s|clam_keys=%s" % (
            run, len(rects), {k: v["kind"] for k, v in plan.items()}, clam.get_num_keys() if clam else None))
        return
    if clam is None:
        raise RuntimeError("NO_CLAM_TRACK")
    rec = {"run": run, "plan": plan, "diffuse_before": {k: x.get_component_by_class(unreal.RectLightComponent).get_editor_property("diffuse_scale") for k, x in rects.items()},
           "clam_before": [(fr(k), float(k.get_value())) for k in clam.get_keys()]}
    json.dump(rec, open(HERE + "s3_rect_flame_record_%s.json" % run, "w"))
    bd = "E:/PussStage/Backups/PreS3RectFlame-%s" % run
    os.makedirs(bd)
    for f in FILES:
        shutil.copy2(f, bd)
    seq.modify()
    for k in clam.get_keys():
        k.set_value(k.get_value() * CLAM_GAIN)
    for i, (lab, p) in enumerate(sorted(plan.items())):
        ph = i * 1.37
        if p["kind"] == "keyed":
            ch = keyed[lab][0]
            pts = p["pts"]
            start = next(f for f, v in pts if v > 1e-6)
            start = max(0, start - 2)
            for k in list(ch.get_keys()):
                if fr(k) >= start:
                    ch.remove_key(k)
            f = start
            while f <= END:
                ch.add_key(unreal.FrameNumber(f), curve_at(pts, f) * (flame(f, ph) if curve_at(pts, f) > 1e-6 else 1.0),
                           time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
                f += STEP
        else:
            comp = rects[lab].get_component_by_class(unreal.RectLightComponent)
            bb = seq.add_possessable(comp)
            t = bb.add_track(unreal.MovieSceneFloatTrack)
            t.set_property_name_and_path("Intensity", "Intensity")
            t.set_display_name("S3.Flame")
            s = t.add_section()
            s.set_range(0, END + 1)
            ch = list(s.get_all_channels())[0]
            f = 0
            while f <= END:
                ch.add_key(unreal.FrameNumber(f), p["intensity"] * flame(f, ph), time_unit=DR,
                           interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
                f += STEP
    for lab, x in rects.items():
        c = x.get_component_by_class(unreal.RectLightComponent)
        c.modify()
        c.set_editor_property("diffuse_scale", DIFF)
    if dirty() != ([SC], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or not lib.save_dirty_packages(True, False) or dirty() != ([], []):
        raise RuntimeError("SAVE|%s" % (dirty(),))
    unreal.log("S3FLAME_APPLY_OK|run=%s|flicker=%d|diffuse=%s|clam_x=%s" % (run, len(plan), DIFF, CLAM_GAIN))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3FLAME_FAILED|run=%s|%r" % (RUN["run"], exc))
