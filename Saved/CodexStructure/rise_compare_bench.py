"""BENCH (level activity, restored; 30 Sep): frames for two questions only Gary can judge.
  set "speed": is Scene 5's rise thrilling or absurd? Strips at equal clock times, plus a
               "1-second exposure" (11 frames over +-0.5 s around the rise's peak speed,
               averaged offline), so the smear IS the distance travelled in a second.
  set "roof":  Scene 6 has no roof: what does the empty roof beat (18.5-24.5 s) look like?
               Frames from landing to the lattice's arrival, from a look-up at the stop and
               from the side; plus the roofless rise itself.
Poses come from the owner's own keys: LS_SN_HangarRise opened in Sequencer and scrubbed
(negative times too: the rise starts at -3.567 s). No exposure override (the show's frame).

Bench discipline (30 Sep rule): BEFORE Sequencer opens, every actor tagged
RigAtmos.SceneNHangar has its root relative transform and light intensity written to
Saved/CodexStructure/BenchOriginals/, and the path is logged. After Sequencer closes, the
level is compared with that file. Anything that differs is restored from the file and
reported. No save anywhere in this script. Transient capture actors are destroyed in a
finally.
Mode: rise_bench_mode.json {"scene": N, "set": "speed"|"roof"|"roofarc"|"lit"}. Writes Captures/RiseBench/.
Lean: main()."""
import datetime
import json
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "RiseBench")
FPS = 30
SETS = {"speed": {"strip": [(-3.0, ("side",)), (0.0, ("cam", "side")), (3.0, ("cam", "side")), (6.0, ("cam", "side")),
                            (9.0, ("cam", "side")), (12.0, ("cam", "side")), (16.0, ("cam", "side")), (20.0, ("cam", "side")),
                            (25.3, ("cam", "side"))], "smear": ("cam", "side")},
        "roof": {"strip": [(0.0, ("cam", "up")), (4.0, ("cam", "up")), (8.0, ("cam", "up")), (12.0, ("cam", "up")),
                           (16.0, ("up", "side")), (18.5, ("up", "side")), (20.5, ("up", "side")), (22.5, ("up", "side")),
                           (24.5, ("up", "side")), (26.5, ("up", "side")), (29.0, ("up", "side"))], "smear": ()},
        # The whole roof arc (hinge on the far wall's top, up to height + depth when upright).
        "roofarc": {"strip": [(t, ("arc",)) for t in (12.0, 16.0, 18.5, 20.5, 22.5, 24.5, 26.5, 29.0)], "smear": ()},
        # Matched PHASES, not clock times: Scene 4's beats x the hangar's own K (landing, uplights
        # on, roof shut, end), so a big hall is compared after ITS lights have come on. cam5 is the
        # stop view with the exposure bias overridden to +5: the room is there, the light is not.
        "lit": {"strip": [(t, ("cam", "cam5", "wide", "up")) for t in (16.0, 20.0, 25.0, 30.9)], "smear": (), "k_scale": True}}


def state_of(actors):
    rows = {}
    for a in actors:
        rc = a.root_component
        if rc is None:
            continue
        loc, rot, sc = rc.get_editor_property("relative_location"), rc.get_editor_property("relative_rotation"), rc.get_editor_property("relative_scale3d")
        row = {"loc": [loc.x, loc.y, loc.z], "rot": [rot.roll, rot.pitch, rot.yaw], "scale": [sc.x, sc.y, sc.z]}
        lc = a.get_component_by_class(unreal.LightComponent)
        if lc:
            row["intensity"] = float(lc.get_editor_property("intensity"))
        rows[a.get_actor_label()] = row
    return rows


def differs(a, b):
    if any(abs(x - y) > 1e-3 for k in ("loc", "rot", "scale") for x, y in zip(a[k], b[k])):
        return True
    return abs(a.get("intensity", 0.0) - b.get("intensity", 0.0)) > 1e-4


def main():
    mode = json.load(open(os.path.join(HERE, "rise_bench_mode.json"), encoding="utf-8"))
    n, which = int(mode["scene"]), mode["set"]
    cfg = SETS[which]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "dirty content"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "dirty map"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    assert not any(a.get_actor_label().startswith("ZZ_") for a in actors), "bench actors (ZZ_) in the level"
    tag = unreal.Name(f"RigAtmos.Scene{n}Hangar")
    mine = [a for a in actors if tag in a.tags]
    # 1. Originals to a file, path logged, BEFORE anything can change.
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    orig_dir = os.path.join(HERE, "BenchOriginals")
    os.makedirs(orig_dir, exist_ok=True)
    orig_path = os.path.join(orig_dir, f"rise_S{n}_{which}_{stamp}.json")
    originals = state_of(mine)
    with open(orig_path, "w", encoding="utf-8") as fh:
        json.dump({"scene": n, "set": which, "written": stamp, "actors": originals}, fh)
        fh.flush()
        os.fsync(fh.fileno())
    unreal.log(f"RISE_BENCH_ORIGINALS|S{n}|{len(originals)} actors|{orig_path}")
    # 2. Views, in the dock frame of the Scene's Entry Handoff Camera.
    rec = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8")) if n != 4 else None
    h = rec["hangar"] if rec else {"depth": 6000.0, "half_w": 1000.0, "height": 3000.0, "apron": 500.0}
    root = next(a for a in mine if a.get_actor_label() == f"S{n} Hangar Root")
    cam = next(a for a in actors if a.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in a.get_actor_label())
    cc = cam.get_cine_camera_component()
    fov = math.degrees(2.0 * math.atan(cc.get_editor_property("filmback").sensor_width / (2.0 * cc.get_editor_property("current_focal_length"))))
    yaw = cam.get_actor_rotation().yaw
    dock = unreal.Transform(location=unreal.Vector(cam.get_actor_location().x, cam.get_actor_location().y, 0.0),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    d, w, ht, apron = h["depth"], h["half_w"], h["height"], h["apron"]
    side = dock.transform_location(unreal.Vector(apron + d * 0.45, -(w + max(3000.0, 1.2 * d)), ht * 0.6))
    look = dock.transform_location(unreal.Vector(apron + d * 0.45, 0.0, -d * 0.15))
    views = {"cam": (cam.get_actor_location(), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), fov),
             "cam5": (cam.get_actor_location(), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), fov, 5.0),
             "wide": (cam.get_actor_location(), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), 100.0),
             "up": (cam.get_actor_location(), unreal.Rotator(roll=0.0, pitch=25.0, yaw=yaw), 90.0),
             "side": (side, unreal.MathLibrary.find_look_at_rotation(side, look), 70.0)}
    # arc: frames the box AND the roof's whole swing (the region x apron..apron+d, z 0..ht+d),
    # from a 3/4 side, 10 deg up, far enough that its bounding sphere fits a 43 deg vertical FOV.
    centre = unreal.Vector(apron + d / 2.0, 0.0, (ht + d) / 2.0)
    radius = math.hypot(d / 2.0, (ht + d) / 2.0)
    dist = radius / math.sin(math.radians(20.0))
    toward = unreal.Vector(-0.35, -0.92, 0.18)
    toward = toward * (1.0 / toward.length())
    arc = dock.transform_location(centre + toward * dist)
    views["arc"] = (arc, unreal.MathLibrary.find_look_at_rotation(arc, dock.transform_location(centre)), 70.0)
    # The rise's own keys give its peak-speed moment (AUTO two-key = smoothstep: peak at mid).
    seq = unreal.load_asset(f"/Game/InfinityStage/RigAtmos/LS_S{n}_HangarRise")
    binding = next(b for b in seq.get_bindings() if str(b.get_display_name()) == f"S{n} Hangar Root")
    track = next(t for t in binding.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack))
    keys = [k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value / FPS
            for k in track.get_sections()[0].get_all_channels()[4].get_keys()]
    start, land = keys[0], keys[-1]
    peak = (start + land) / 2.0
    k = float(rec["k"]) if rec and cfg.get("k_scale") else 1.0
    shots = [(t * k, v, f"S{n}_{which}_{v}_{'m' if t < 0 else 'p'}{abs(t * k):05.2f}.png") for t, vs in cfg["strip"] for v in vs]
    shots += [(peak + (i - 5) * 0.1, v, f"S{n}_smear_{v}_{i:02d}.png") for v in cfg["smear"] for i in range(11)]
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 960, 540, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    log, restored = [], 0
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    try:
        last_t = None
        for t, v, fname in shots:
            if t != last_t:
                unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(int(round(t * FPS)))
                unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
                log.append(f"{t:.2f}:{root.root_component.get_editor_property('relative_rotation').pitch:.2f}")
                last_t = t
            loc, rot, f = views[v][:3]
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot, True)
            try:
                comp = cap.capture_component2d
                if len(views[v]) > 3:
                    pps = comp.get_editor_property("post_process_settings")
                    pps.set_editor_property("override_auto_exposure_bias", True)
                    pps.set_editor_property("auto_exposure_bias", views[v][3])
                    comp.set_editor_property("post_process_settings", pps)
                    comp.set_editor_property("post_process_blend_weight", 1.0)
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                comp.set_editor_property("fov_angle", f)
                for _ in range(2):
                    comp.capture_scene()
                unreal.RenderingLibrary.export_render_target(world, rt, OUT, fname)
            finally:
                sub.destroy_actor(cap)
    finally:
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
        # 3. Verify against the FILE (not a variable); restore anything that differs.
        saved = json.load(open(orig_path, encoding="utf-8"))["actors"]
        now = state_of([a for a in sub.get_all_level_actors() if tag in a.tags])
        for label, want in saved.items():
            if label in now and differs(now[label], want):
                a = next(x for x in sub.get_all_level_actors() if x.get_actor_label() == label)
                rc = a.root_component
                rc.set_editor_property("relative_location", unreal.Vector(*want["loc"]))
                rc.set_editor_property("relative_rotation", unreal.Rotator(roll=want["rot"][0], pitch=want["rot"][1], yaw=want["rot"][2]))
                rc.set_editor_property("relative_scale3d", unreal.Vector(*want["scale"]))
                if "intensity" in want:
                    a.get_component_by_class(unreal.LightComponent).set_editor_property("intensity", want["intensity"])
                restored += 1
    json.dump({"scene": n, "set": which, "start": start, "land": land, "peak": peak, "depth": d, "height": ht,
               "pitches": log, "shots": [s[2] for s in shots]}, open(os.path.join(OUT, f"S{n}_{which}_meta.json"), "w"), indent=1)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"RISE_BENCH_OK|S{n}|{which}|rise {start:.3f}->{land:.3f} peak {peak:.3f}|shots={len(shots)}|restored_from_file={restored}"
               f"|dirty_after={c1}+{m1}|pitches={' '.join(log)}")


main()
