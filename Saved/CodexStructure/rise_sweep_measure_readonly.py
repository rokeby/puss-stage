"""READ-ONLY measurement (30 Sep): does the LIVE rise sweep what its model says? The hangar-exit cost rests on a COMPUTED
claim (Docs/HangarExitCost_2026-09-30.md): the upright roof crosses ground level 114 m from the camera stop, 48 m past
the far wall (Scene 5: 100 m), and the box without the roof reaches 7 m past. This poses the saved rise sequence in
Sequencer (hangar_rise_capture.py's proven path: open, set time, refresh, close in a finally) every STEP_S seconds and
reads the WORLD corners of every static mesh under the hangar root, in the dock frame (origin on the Entry Handoff
Camera at floor level, +x ahead, the frame the builder used).

Reports, over the whole rise: the far wall's live x; the forward-most corner at or above ground level (z >= -1 cm), its
time and its actor; the same excluding the roof (the "box alone"); and the forward-most corner at any height (the pit
reach). Scene from SWEEP_SCENE (runner). Posing moves actors in memory only: Sequencer restores on close, the root pitch
must read back at its rest value and dirty must stay 0+0. Captures nothing, spawns nothing. Marker RISE_SWEEP|run=<id>.
Everything inside main()."""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
FPS = 30
STEP_S = 0.5


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    n = int(globals().get("SWEEP_SCENE", 1))
    rec = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or ed.get_game_world() is not None or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() \
            or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() or unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        unreal.log_error(f"RISE_SWEEP|refused|run={run}|PIE, dirty, or Sequencer open")
        return
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    root = next(a for a in actors if a.get_actor_label() == f"S{n} Hangar Root")
    roof_hinge = next((a for a in actors if a.get_actor_label() == f"S{n} Hangar Roof Hinge"), None)
    far = next(a for a in actors if a.get_actor_label() == f"S{n} Hangar Far Wall")

    def under(a, top):
        p = a.get_attach_parent_actor()
        while p is not None:
            if p == top:
                return True
            p = p.get_attach_parent_actor()
        return False

    meshes = []
    for a in actors:
        if not under(a, root) or not isinstance(a, unreal.StaticMeshActor):
            continue
        comp = a.static_mesh_component
        mesh = comp.static_mesh
        if mesh is None:
            continue
        b = mesh.get_bounds()
        o, e = b.origin, b.box_extent
        corners = [unreal.Vector(o.x + sx * e.x, o.y + sy * e.y, o.z + sz * e.z) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        meshes.append((a.get_actor_label(), comp, corners, roof_hinge is not None and under(a, roof_hinge)))
    d = rec["dock"]
    dock = unreal.Transform(location=unreal.Vector(d["loc"][0], d["loc"][1], 0.0), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=d["yaw"]))
    rest_pitch = root.root_component.get_editor_property("relative_rotation").pitch
    seq = unreal.load_asset(rec["sequence"])
    end_s = seq.get_playback_end_seconds() - 1.0 / FPS    # the exact end frame restores the rest pose (30 Sep, first run)
    best = {"all_above": (-1e9, None, None), "box_above": (-1e9, None, None), "any_height": (-1e9, None, None)}
    far_x = []
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    try:
        t = 0.0
        while True:
            t = min(t, end_s)
            unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(int(round(t * FPS)))
            unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            for label, comp, corners, is_roof in meshes:
                xf = comp.get_world_transform()
                for c in corners:
                    p = dock.inverse_transform_location(xf.transform_location(c))
                    if p.x > best["any_height"][0]:
                        best["any_height"] = (p.x, t, label)
                    if p.z >= -1.0:
                        if p.x > best["all_above"][0]:
                            best["all_above"] = (p.x, t, label)
                        if not is_roof and p.x > best["box_above"][0]:
                            best["box_above"] = (p.x, t, label)
            far_x.append(dock.inverse_transform_location(far.get_actor_location()).x)
            if t >= end_s:
                break
            t += STEP_S
    finally:
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    after = root.root_component.get_editor_property("relative_rotation").pitch
    dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    wall = far_x[-1] + rec["hangar"]["wall_t"] / 2.0          # outer face in the landed pose (last frame before the end)
    out = {"run": run, "scene": n, "step_s": STEP_S, "rise_end_s": end_s, "meshes": len(meshes), "far_wall_outer_x_cm": wall,
           "best": {k: {"x_cm": round(v[0], 1), "past_far_wall_m": round((v[0] - wall) / 100.0, 1), "t_s": v[1], "actor": v[2]} for k, v in best.items()},
           "root_pitch_rest": rest_pitch, "root_pitch_after_close": after, "dirty_after": dirty}
    with open(os.path.join(HERE, f"rise_sweep_s{n}_{run}.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    b = out["best"]
    unreal.log(f"RISE_SWEEP|run={run}|S{n}|meshes={len(meshes)}|far_wall_outer={wall / 100:.1f}m|"
               f"above_ground_max={b['all_above']['x_cm'] / 100:.1f}m (+{b['all_above']['past_far_wall_m']} m past, t={b['all_above']['t_s']}, {b['all_above']['actor']})|"
               f"box_alone_above={b['box_above']['x_cm'] / 100:.1f}m (+{b['box_above']['past_far_wall_m']} m)|any_height={b['any_height']['x_cm'] / 100:.1f}m|"
               f"root_pitch rest={rest_pitch:.1f} after_close={after:.1f}|dirty_after={dirty[0]}+{dirty[1]}")


main()
