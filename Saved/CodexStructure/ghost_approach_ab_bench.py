"""BENCH (level activity, restored; 30 Sep): does a hangar's REST-STATE light show from its
Passage approach? The plane trim opened the pits at S1, S5 and S6 (the box now hangs in a void
where a floor plane used to cover it). At rest every hangar light is 0 cd except the ghost
light (60 cd), so each approach frame is rendered with the ghost light at its rest value and at
0, and the two are diffed: any difference is that light, seen from the approach. S4 (void pit
all along) is the control.
Views, per scene, in its dock frame (the Entry Handoff Camera; docks along +X): level at 25 m
and 10 m before the stop and at the stop (hfov 37.5, the Passage camera), and at the stop looking
down 15 deg over the lip. No exposure override: each frame gets the show's exposure for where it
stands.
Bench discipline: every ghost light's intensity is written to BenchOriginals/ and the path logged
BEFORE anything changes; set_intensity (no Modify, no dirty flag); restored in a finally and
verified against the FILE. No save anywhere. Transient capture actors destroyed in a finally.
Writes Captures/GhostApproach/ and ghost_approach_ab.json. Lean: main()."""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "GhostApproach")
SCENES = (4, 1, 5, 6)
VIEWS = (("m25", -2500.0, 0.0), ("m10", -1000.0, 0.0), ("stop", 0.0, 0.0), ("stopdown", 0.0, -15.0))


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "dirty map"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    assert not any(a.get_actor_label().startswith("ZZ_") for a in actors), "bench actors (ZZ_) in the level"
    ghosts = {n: next(a for a in actors if a.get_actor_label() == f"S{n} Ghost Light") for n in SCENES}
    # Every OTHER light in these hangars must be dark at rest, or the A/B would miss a source.
    others_lit = []
    for n in SCENES:
        tag = unreal.Name(f"RigAtmos.Scene{n}Hangar")
        for a in actors:
            lc = a.get_component_by_class(unreal.LightComponent) if tag in a.tags else None
            if lc and a is not ghosts[n] and lc.get_editor_property("intensity") > 0.0:
                others_lit.append(a.get_actor_label())
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs(os.path.join(HERE, "BenchOriginals"), exist_ok=True)
    orig_path = os.path.join(HERE, "BenchOriginals", f"ghost_approach_{stamp}.json")
    with open(orig_path, "w", encoding="utf-8") as fh:
        json.dump({n: float(g.get_component_by_class(unreal.LightComponent).get_editor_property("intensity")) for n, g in ghosts.items()}, fh)
        fh.flush()
        os.fsync(fh.fileno())
    unreal.log(f"GHOST_AB_ORIGINALS|{orig_path}")
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 960, 540, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    shots = []
    try:
        for n in SCENES:
            cam = next(a for a in actors if a.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in a.get_actor_label())
            cl, yaw = cam.get_actor_location(), cam.get_actor_rotation().yaw
            assert abs(yaw) < 0.01, f"S{n}: dock is yawed"
            lc = ghosts[n].get_component_by_class(unreal.LightComponent)
            rest = float(lc.get_editor_property("intensity"))
            for name, dx, pitch in VIEWS:
                loc = unreal.Vector(cl.x + dx, cl.y, cl.z)
                for state, value in (("on", rest), ("off", 0.0)):
                    lc.set_intensity(value)
                    cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), True)
                    try:
                        comp = cap.capture_component2d
                        comp.set_editor_property("texture_target", rt)
                        comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                        comp.set_editor_property("fov_angle", 37.5)
                        for _ in range(3):
                            comp.capture_scene()
                        fname = f"S{n}_{name}_{state}.png"
                        unreal.RenderingLibrary.export_render_target(world, rt, OUT, fname)
                        shots.append(fname)
                    finally:
                        sub.destroy_actor(cap)
                lc.set_intensity(rest)
    finally:
        saved = json.load(open(orig_path, encoding="utf-8"))
        for n, g in ghosts.items():
            g.get_component_by_class(unreal.LightComponent).set_intensity(float(saved[str(n)]))
    now = {n: float(g.get_component_by_class(unreal.LightComponent).get_editor_property("intensity")) for n, g in ghosts.items()}
    restored_ok = all(abs(now[n] - float(saved[str(n)])) < 1e-4 for n in SCENES)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    json.dump({"scenes": SCENES, "views": VIEWS, "shots": shots, "others_lit_at_rest": others_lit, "restored_ok": restored_ok},
              open(os.path.join(HERE, "ghost_approach_ab.json"), "w"), indent=1)
    unreal.log(f"GHOST_AB_OK|shots={len(shots)}|others_lit_at_rest={len(others_lit)}|restored_ok={restored_ok}|dirty_after={c1}+{m1}")


main()
