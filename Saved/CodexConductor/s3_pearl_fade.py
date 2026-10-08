"""Pearl disappears at the take (Gary 8 Oct: "it should disappear with a fade over 4s, leaving 1s of a glow halo").
Needs Pearl_v4 (finishing touches: scalar "Fade", 1 = solid, 0 = gone; slot 0 of S3 PearlClam Pearl's StaticMeshComponent).
Writes in LS_DevScene_03:
  * a component-material track on the pearl's StaticMeshComponent, slot 0, scalar "Fade": 1 until 4800, linear to 0 at
    4896 (3:20 -> 3:24), held;
  * a False key at 4896 on the pearl's existing Visibility track (the float-hold binding; keys before stay untouched).
The halo light was keyed separately (S3KM-20261008-023655halo).
DRY additionally probes the Python API names this needs and prints which exist (MovieSceneComponentMaterialTrack,
set_material_index / material_index property, add_scalar_parameter_key or channel access) [inferred until DRY].
Args s3_pearl_fade_args.json {"mode":"DRY"|"APPLY","confirm":"APPLY S3PFADE","run":..}.
Record + Backups/PreS3PearlFade-<run> first; saves LS_DevScene_03 only.  Markers S3PFADE_<MODE>_OK / S3PFADE_FAILED."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
UASSET = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
PEARL = "S3 PearlClam Pearl"
PARAM = "Fade"
F0, F1 = 4800, 4896
TRACK_NAME = "S3.Pearl.Fade"
RUN = {"run": "?"}


def main():
    import unreal
    a = json.load(open(HERE + "s3_pearl_fade_args.json"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    w = ed.get_editor_world()
    pearl = [x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor) if str(x.get_actor_label()) == PEARL]
    if len(pearl) != 1:
        raise RuntimeError("PEARL_COUNT|%d" % len(pearl))
    smc = pearl[0].get_component_by_class(unreal.StaticMeshComponent)
    mat = smc.get_material(0)
    has_fade = False
    try:
        names = [str(n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(mat)]
        has_fade = PARAM in names
    except Exception:
        names = []
    api = {"ComponentMaterialTrack": hasattr(unreal, "MovieSceneComponentMaterialTrack"),
           "set_material_index": hasattr(getattr(unreal, "MovieSceneComponentMaterialTrack", object), "set_material_index"),
           "material_param_section": hasattr(unreal, "MovieSceneParameterSection")}
    scene = unreal.load_asset(SCENE)
    vis = []
    for b in scene.get_bindings():
        nm = str(b.get_display_name())
        if nm.endswith(PEARL):
            for t in b.get_tracks():
                if t.get_class().get_name() == "MovieSceneVisibilityTrack":
                    for s in t.get_sections():
                        for ch in s.get_all_channels():
                            vis.append((nm, ch, [(int(k.get_time().frame_number.value), bool(k.get_value())) for k in ch.get_keys()]))
    existing = [b for b in scene.get_bindings() for t in b.get_tracks() if str(t.get_display_name()) == TRACK_NAME]
    if mode == "DRY":
        unreal.log("S3PFADE_DRY_OK|run=%s|material=%s|has_fade=%s|api=%s|vis=%s|existing=%d" % (
            run, mat.get_path_name() if mat else None, has_fade, api, [(n, k) for n, _, k in vis], len(existing)))
        return
    if a.get("confirm") != "APPLY S3PFADE" or not has_fade or existing or len(vis) != 1 or not all(api.values()):
        raise RuntimeError("PRECONDITION|has_fade=%s|existing=%d|vis=%d|api=%s" % (has_fade, len(existing), len(vis), api))
    rec = HERE + "s3_pearl_fade_record_%s.json" % run
    json.dump({"run": run, "vis_before": vis[0][2], "material": mat.get_path_name()}, open(rec, "w"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3PearlFade-%s" % run
    os.makedirs(bdir)
    shutil.copy2(UASSET, bdir)
    scene.modify()
    b = scene.add_possessable(smc)
    t = b.add_track(unreal.MovieSceneComponentMaterialTrack)
    t.set_material_index(0)
    t.set_display_name(TRACK_NAME)
    s = t.add_section()
    s.set_range(0, int(scene.get_playback_end()) + 1)
    for fr, v in ((0, 1.0), (F0, 1.0), (F1, 0.0)):
        s.add_scalar_parameter_key(unreal.Name(PARAM), unreal.FrameNumber(fr), v)
    got = []
    for ch in s.get_all_channels():
        got.append(sorted((int(k.get_time().frame_number.value), round(k.get_value(), 3)) for k in ch.get_keys()))
    if got != [[(0, 1.0), (F0, 1.0), (F1, 0.0)]]:
        raise RuntimeError("FADE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % got)
    _n, vch, _k = vis[0]
    vch.add_key(unreal.FrameNumber(F1), False, time_unit=DR)
    vk = sorted((int(k.get_time().frame_number.value), bool(k.get_value())) for k in vch.get_keys())
    if (F1, False) not in vk:
        raise RuntimeError("VIS_READBACK|%s|NOTHING SAVED; Don't-Save restart" % vk)
    if dirty() != ([SCENE], []):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or dirty() != ([], []):
        raise RuntimeError("SAVE")
    unreal.log("S3PFADE_APPLY_OK|run=%s|fade=%d->%d|vis_off=%d" % (run, F0, F1, F1))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3PFADE_FAILED|run=%s|%r" % (RUN["run"], exc))
