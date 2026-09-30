"""Read-only: price the exposure change at the end of Passage 4 as three options, in
pictures, WITHOUT touching the hangar's PostProcessVolume (30 Sep).

Today the "S4 Hangar Pinned Exposure" volume (EV100 0.5) starts 1 m before the camera's
stop (face x 10568.5, blend radius 1 m), inside P04's unbound EV100 -3: walking in, the
frame darkens 3.5 stops over the last 2 m, on top of the backcloth crossing (x 10450). A volume blends its settings linearly by
weight (1 inside, falling to 0 at BlendRadius outside the face), and the EV100 min/max
blend linearly with it, so the EV at any camera position can be computed and pinned in
a capture. Options:
  A instant  - the volume as it is (its own face and blend radius, read live);
  B 26 m     - face moved to x 10600 (just before the camera's stop), blend radius 2531.5 (from x 8068.5);
  C 10 m     - face at x 10600, blend radius 1000 (it coincides with the backcloth's
               release-to-crossing stretch, x 9775 -> 10450).
Camera positions along the route at 1.8 m, level, 35 mm (the passage rig's lens).
Transient captures, destroyed in a finally; dirty must not change. Writes
Captures/ExposureBlend/ and exposure_blend.json. Lean: all work in main()."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "ExposureBlend")
POSITIONS = (6000.0, 8068.5, 8800.0, 9500.0, 9775.0, 10100.0, 10450.0, 10668.5)
PASSAGE_EV, Y, Z = -3.0, 240000.0, 180.0
CLOTH_X, RELEASE_X = 10450.0, 9775.0     # the recommended backcloth line and the camera's x at its release (proxy: the
                                         # transition drape cache, hanging; 19 m wide against the 12 m the real one needs)


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    ppv = next(a for a in sub.get_all_level_actors() if a.get_actor_label() == "S4 Hangar Pinned Exposure")
    o, e = ppv.get_actor_bounds(False)
    face = o.x - e.x
    radius = float(ppv.get_editor_property("blend_radius"))
    st = ppv.get_editor_property("settings")
    hangar_ev = float(st.get_editor_property("auto_exposure_min_brightness"))
    info = {"face_x": face, "far_x": o.x + e.x, "blend_radius": radius, "blend_weight": ppv.get_editor_property("blend_weight"),
            "priority": ppv.get_editor_property("priority"), "hangar_ev": hangar_ev,
            "hangar_ev_max": float(st.get_editor_property("auto_exposure_max_brightness")),
            "method": str(st.get_editor_property("auto_exposure_method"))}
    options = {"A_instant": (face, max(radius, 1.0)), "B_26m": (10600.0, 2531.5), "C_10m": (10600.0, 1000.0)}

    def ev_at(x, opt):
        f, r = options[opt]
        w = 1.0 if x >= f else max(0.0, 1.0 - (f - x) / r)
        return PASSAGE_EV + w * (hangar_ev - PASSAGE_EV), w

    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 960, 540, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    rows = []
    temps = []
    try:
        cloth = sub.spawn_actor_from_class(unreal.GeometryCacheActor, unreal.Vector(CLOTH_X, Y, 0.0), unreal.Rotator(0.0, 0.0, 0.0), True)
        temps.append(cloth)
        gcc = cloth.get_component_by_class(unreal.GeometryCacheComponent)
        gcc.set_editor_property("geometry_cache", unreal.load_asset("/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"))
        gcc.set_editor_property("running", False)
        for opt in options:
            for x in POSITIONS:
                ev, w = ev_at(x, opt)
                cloth.set_actor_hidden_in_game(x >= RELEASE_X)     # from the release on it is falling: not simulated here
                cloth.get_component_by_class(unreal.GeometryCacheComponent).set_visibility(x < RELEASE_X)
                cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(x, Y, Z), unreal.Rotator(0.0, 0.0, 0.0), True)
                temps.append(cap)
                comp = cap.capture_component2d
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                comp.set_editor_property("fov_angle", 37.5)
                pp = comp.post_process_settings
                for k, val in (("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM), ("auto_exposure_min_brightness", ev),
                               ("auto_exposure_max_brightness", ev), ("auto_exposure_bias", 0.0)):
                    pp.set_editor_property("override_" + k, True)
                    pp.set_editor_property(k, val)
                comp.set_editor_property("post_process_settings", pp)
                for _ in range(2):
                    comp.capture_scene()
                name = f"{opt}_x{int(x)}.png"
                unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)
                rows.append({"option": opt, "x": x, "to_stop_m": round((10668.5 - x) / 100.0, 1), "weight": round(w, 3), "ev100": round(ev, 3), "file": name})
                sub.destroy_actor(cap)
                temps.remove(cap)
    finally:
        for t in temps:
            sub.destroy_actor(t)
    json.dump({"ppv": info, "options": {k: {"face_x": f, "blend_cm": r} for k, (f, r) in options.items()}, "rows": rows},
              open(os.path.join(HERE, "exposure_blend.json"), "w"), indent=1)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"EXPOSURE_BLEND_OK|ppv={info}|captures={len(rows)}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
