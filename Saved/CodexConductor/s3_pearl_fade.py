"""Pearl disappears at the take with Gary's revised two-second fade.
A TRANSLUCENT twin "S3 PearlClam Pearl Fade"
(finishing touches, patch 2026-10-08_pearl_fade_twin: MI_PearlClam_Pearl_Fade, scalar "Fade" -> Opacity, slot 0,
hidden in game by default, attached to S3 PearlClam).  Writes in LS_DevScene_03:
  * a False key at 4992 on the SOLID pearl's existing Visibility track (float-hold binding; earlier keys untouched);
  * twin: Visibility track False from 0, True at 4992, False at 5040;
  * twin: component-material track slot 0, scalar "Fade": 1 until 4992, linear to 0 at 5040 (2 seconds).
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
TWIN = "S3 PearlClam Pearl Fade"
PARAM = "Fade"
FPS = 24
F1 = 5040                # Keep the reviewed/current vanish frame (~3:30).
FADE_SECONDS = 2
F0 = F1 - FPS * FADE_SECONDS  # 48 frames: 4992 -> 5040 at 24 fps.
LEGACY_F0 = 4944          # Pass-1/live four-second fade start; migrate narrowly.
TRACK_NAME = "S3.Pearl.Fade"
RUN = {"run": "?"}


def _expected_twin_vis(start=F0):
    return [(0, False), (start, True), (F1, False)]


def _expected_fade(start=F0):
    return [(0, 1.0), (start, 1.0), (F1, 0.0)]


def adoption_plan(state):
    """Pure fail-closed classifier for fresh or already-authored fade tracks."""
    errors = []
    solid = state.get("solid_visibility") or []
    twin = state.get("twin_visibility") or []
    material = state.get("material_fade") or []
    if len(solid) != 1:
        errors.append("SOLID_VISIBILITY_COUNT|%d" % len(solid))
    else:
        row = solid[0]
        if (row.get("property"), row.get("path")) not in (("bHidden", "bHidden"),
                ("bHiddenInGame", "bHiddenInGame"), ("None", "None"), ("", "")):
            errors.append("SOLID_VISIBILITY_PROPERTY|%s|%s" % (row.get("property"), row.get("path")))
        at_f0 = [value for frame, value in row.get("keys", []) if int(frame) == F0]
        if at_f0 not in ([], [False]):
            errors.append("SOLID_VISIBILITY_F0|%s" % at_f0)
    if len(twin) > 1:
        errors.append("TWIN_VISIBILITY_COUNT|%d" % len(twin))
    elif twin:
        row = twin[0]
        if (row.get("property"), row.get("path")) not in (("bHidden", "bHidden"),
                                                           ("None", "None"), ("", "")):
            errors.append("TWIN_VISIBILITY_PROPERTY|%s|%s" % (row.get("property"), row.get("path")))
        if row.get("active_sections") != 1 or row.get("keys") not in (_expected_twin_vis(), _expected_twin_vis(LEGACY_F0)):
            errors.append("TWIN_VISIBILITY_SHAPE|sections=%s|keys=%s" %
                          (row.get("active_sections"), row.get("keys")))
    if len(material) > 1:
        errors.append("MATERIAL_FADE_COUNT|%d" % len(material))
    elif material:
        row = material[0]
        if row.get("class") != "MovieSceneComponentMaterialTrack" or row.get("active_sections") != 1 or \
                row.get("keys") not in (_expected_fade(), _expected_fade(LEGACY_F0)):
            errors.append("MATERIAL_FADE_SHAPE|class=%s|sections=%s|keys=%s" %
                          (row.get("class"), row.get("active_sections"), row.get("keys")))
    if errors:
        raise RuntimeError("ADOPTION_REFUSED|" + ";".join(errors))
    return {"solid": "reuse", "solid_bind_bHidden": solid[0]["property"] != "bHidden",
            "solid_add_f0": not any(int(frame) == F0 for frame, _value in solid[0]["keys"]),
            "solid_remove_legacy_f0": any(int(frame) == LEGACY_F0 and value is False
                                           for frame, value in solid[0]["keys"]),
            "twin_visibility": "reuse" if twin else "create",
            "twin_bind_bHidden": not twin or twin[0]["property"] != "bHidden",
            "twin_retime_legacy": bool(twin and twin[0]["keys"] == _expected_twin_vis(LEGACY_F0)),
            "material_fade": "reuse" if material else "create",
            "material_retime_legacy": bool(material and material[0]["keys"] == _expected_fade(LEGACY_F0))}


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
    allact = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor))
    pearl = [x for x in allact if str(x.get_actor_label()) == PEARL]
    twin = [x for x in allact if str(x.get_actor_label()) == TWIN]
    if len(pearl) != 1:
        raise RuntimeError("PEARL_COUNT|%d" % len(pearl))
    if mode != "DRY" and len(twin) != 1:
        raise RuntimeError("TWIN_COUNT|%d" % len(twin))
    if not twin:
        unreal.log("S3PFADE_DRY_OK|run=%s|twin=MISSING (waiting for CLAM_PEARL_TWIN)" % run)
        return
    smc = twin[0].get_component_by_class(unreal.StaticMeshComponent)
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
    def bound_to(obj):
        rows = []
        want = obj.get_path_name()
        for binding in scene.get_bindings():
            try:
                resolved = [x.get_path_name() for x in scene.locate_bound_objects(binding, w)]
            except Exception:
                resolved = []
            if want in resolved:
                rows.append(binding)
        if len(rows) > 1:
            raise RuntimeError("BINDING_AMBIGUOUS|%s|%d" % (want, len(rows)))
        return rows[0] if rows else None

    def visibility_rows(binding):
        rows = []
        for track in ([] if binding is None else binding.get_tracks()):
            if track.get_class().get_name() != "MovieSceneVisibilityTrack":
                continue
            active = [section for section in track.get_sections() if section.is_active()]
            keys = []
            if len(active) == 1 and len(active[0].get_all_channels()) == 1:
                keys = sorted((int(k.get_time().frame_number.value), bool(k.get_value()))
                              for k in active[0].get_all_channels()[0].get_keys())
            rows.append({"track": track, "property": str(track.get_property_name()),
                         "path": str(track.get_property_path()), "active_sections": len(active), "keys": keys})
        return rows

    def material_rows():
        rows = []
        for binding in scene.get_bindings():
            for track in binding.get_tracks():
                if str(track.get_display_name()) != TRACK_NAME:
                    continue
                active = [section for section in track.get_sections() if section.is_active()]
                keys = []
                if len(active) == 1 and len(active[0].get_all_channels()) == 1:
                    keys = sorted((int(k.get_time().frame_number.value), round(float(k.get_value()), 3))
                                  for k in active[0].get_all_channels()[0].get_keys())
                rows.append({"binding": binding, "track": track, "class": track.get_class().get_name(),
                             "active_sections": len(active), "keys": keys})
        return rows

    pearl_binding = bound_to(pearl[0])
    twin_binding = bound_to(twin[0])
    component_binding = bound_to(smc)
    solid_rows = visibility_rows(pearl_binding)
    twin_rows = visibility_rows(twin_binding)
    mat_rows = material_rows()
    public_state = {"solid_visibility": [{k: v for k, v in row.items() if k != "track"} for row in solid_rows],
                    "twin_visibility": [{k: v for k, v in row.items() if k != "track"} for row in twin_rows],
                    "material_fade": [{k: v for k, v in row.items() if k not in ("track", "binding")}
                                      for row in mat_rows]}
    plan = adoption_plan(public_state)
    if mode == "DRY":
        unreal.log("S3PFADE_DRY_OK|run=%s|apply_ready=1|material=%s|has_fade=%s|api=%s|adoption=%s" % (
            run, mat.get_path_name() if mat else None, has_fade, api, plan))
        return
    if a.get("confirm") != "APPLY S3PFADE" or not has_fade or not all(api.values()):
        raise RuntimeError("PRECONDITION|has_fade=%s|api=%s" % (has_fade, api))
    rec = HERE + "s3_pearl_fade_record_%s.json" % run
    json.dump({"run": run, "state_before": public_state, "adoption": plan,
               "material": mat.get_path_name()}, open(rec, "x"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3PearlFade-%s" % run
    os.makedirs(bdir)
    shutil.copy2(UASSET, bdir)
    scene.modify()
    if plan["material_fade"] == "create":
        b = component_binding or scene.add_possessable(smc)
        t = b.add_track(unreal.MovieSceneComponentMaterialTrack)
        t.set_material_index(0); t.set_display_name(TRACK_NAME)
        s = t.add_section(); s.set_range(0, int(scene.get_playback_end()) + 1)
        info = unreal.MaterialParameterInfo(); info.set_editor_property("name", unreal.Name(PARAM))
        tpf = int(round(scene.get_tick_resolution().numerator / float(scene.get_display_rate().numerator)))
        for fr, v in _expected_fade():
            s.add_scalar_parameter_key(info, unreal.FrameNumber(fr * tpf), v, "", "", unreal.MovieSceneKeyInterpolation.LINEAR)
    if plan["solid_bind_bHidden"]:
        solid_rows[0]["track"].set_property_name_and_path("bHidden", "bHidden")
    vch = [s for s in solid_rows[0]["track"].get_sections() if s.is_active()][0].get_all_channels()[0]
    if plan["solid_remove_legacy_f0"]:
        for key in list(vch.get_keys()):
            if int(key.get_time(time_unit=DR).frame_number.value) == LEGACY_F0:
                key.remove()
    if plan["solid_add_f0"]:
        vch.add_key(unreal.FrameNumber(F0), False, time_unit=DR)                  # solid pearl off at the take
    vk = sorted((int(k.get_time().frame_number.value), bool(k.get_value())) for k in vch.get_keys())
    if (F0, False) not in vk:
        raise RuntimeError("VIS_READBACK|%s|NOTHING SAVED; Don't-Save restart" % vk)
    if plan["twin_visibility"] == "create":
        tb = twin_binding or scene.add_possessable(twin[0])
        tv = tb.add_track(unreal.MovieSceneVisibilityTrack)
        tv.set_property_name_and_path("bHidden", "bHidden")
        tvs = tv.add_section(); tvs.set_range(0, int(scene.get_playback_end()) + 1)
        tch = list(tvs.get_all_channels())[0]
        for fr, v in _expected_twin_vis():
            tch.add_key(unreal.FrameNumber(fr), v, time_unit=DR)
    else:
        tv = twin_rows[0]["track"]
        if plan["twin_bind_bHidden"]:
            tv.set_property_name_and_path("bHidden", "bHidden")
        tch = [s for s in tv.get_sections() if s.is_active()][0].get_all_channels()[0]
        if plan["twin_retime_legacy"]:
            for key in tch.get_keys():
                if int(key.get_time(time_unit=DR).frame_number.value) == LEGACY_F0:
                    key.set_time(unreal.FrameNumber(F0), time_unit=DR)
    tk = sorted((int(k.get_time().frame_number.value), bool(k.get_value())) for k in tch.get_keys())
    if tk != [(0, False), (F0, True), (F1, False)]:
        raise RuntimeError("TWIN_VIS_READBACK|%s|NOTHING SAVED; Don't-Save restart" % tk)
    fade_track = t if plan["material_fade"] == "create" else mat_rows[0]["track"]
    fade_sections = [section for section in fade_track.get_sections() if section.is_active()]
    if plan["material_retime_legacy"] and len(fade_sections) == 1:
        for key in fade_sections[0].get_all_channels()[0].get_keys():
            if int(key.get_time(time_unit=DR).frame_number.value) == LEGACY_F0:
                key.set_time(unreal.FrameNumber(F0), time_unit=DR)
    fade_keys = [] if len(fade_sections) != 1 else sorted(
        (int(k.get_time().frame_number.value), round(float(k.get_value()), 3))
        for k in fade_sections[0].get_all_channels()[0].get_keys())
    if fade_keys != _expected_fade():
        raise RuntimeError("FADE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % fade_keys)
    if str(solid_rows[0]["track"].get_property_name()) != "bHidden" or \
            str(tv.get_property_name()) != "bHidden":
        raise RuntimeError("VISIBILITY_BINDING_READBACK|solid=%s|twin=%s|NOTHING SAVED; Don't-Save restart" %
                           (solid_rows[0]["track"].get_property_name(), tv.get_property_name()))
    if dirty() != ([SCENE], []):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or dirty() != ([], []):
        raise RuntimeError("SAVE")
    unreal.log("S3PFADE_APPLY_OK|run=%s|fade=%d->%d|vis_off=%d" % (run, F0, F1, F1))


if __name__ in ("__main__", "<run_path>"):
    try:
        main()
    except Exception as exc:
        import unreal
        unreal.log_error("S3PFADE_FAILED|run=%s|%r" % (RUN["run"], exc))
