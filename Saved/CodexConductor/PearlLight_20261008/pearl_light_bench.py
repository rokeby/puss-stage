"""PEARL LIGHT BENCH: non-saving A/B of how to light the S3 pearl (Gary 8 Oct: "5 is nice. The other part is how best
to light it"). Pattern: look_bench.py (Python can't spawn actors into a running PIE world, so a temp pool is spawned
into the EDITOR world first; PIE duplicates it; the PIE side only moves / shows / sets properties).

MODES (global PL_MODE via the runner files):
  PREPARE  editor world, no PIE, census must be clean, no ZZ_PEARLLIGHT_* present. Writes pearl_light_prepare.json
           (labels + census, fsynced, re-read) BEFORE the first spawn; spawns 3 lights labelled ZZ_PEARLLIGHT_KEY (Rect),
           _PING (Point), _RIM (Spot), tagged ZZ_PEARLLIGHT, hidden in game, 0 intensity, lighting channel 1 ONLY,
           Movable. Dirties the map: expected; this bench never saves -> PEARLLIGHT_NEEDS_DONT_SAVE_RESTART.
  CAPTURE  PIE, transport paused at S3 frame 1800 (run MiScalars/pvs_scrub first). Records originals to
           pearl_light_originals_<run>.json first; puts the f4 look on the solid pearl (PIE MID), gives the pearl
           channels 0+1, hides "S3 Drama Pearl Glow" (component visibility; its intensity is track-driven), places the
           three lights relative to the pearl and the view camera, and shoots STATES via HighResShot (slate tick
           machine). Restores every original at the end, success or not.
  CLEANUP  editor world, no PIE: destroys the tagged ZZ_PEARLLIGHT_* actors WITHOUT saving. A Don't-Save restart
           + editor_sky_toggle.py is still required (the map stays dirty).
Markers PEARLLIGHT_<MODE>_OK|run=.. / PEARLLIGHT_FAILED|run=..|reason. No save call exists in this file.
Units: intensities are the lights' own default units (cd for point/spot in this project, as the drama lights).
"""
import datetime
import json
import math
import os

HERE = "E:/PussStage/Saved/CodexConductor/PearlLight_20261008/"
PREFIX, TAG = "ZZ_PEARLLIGHT_", "ZZ_PEARLLIGHT"
PEARL, GLOW = "S3 PearlClam Pearl", "S3 Drama Pearl Glow"
GO_MI = "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/MI_PearlClam_Pearl_v3_GreenOrange"
F4 = {"scalars": {"IridStrength": 0.8, "SubsurfaceIrid": 0.7, "Glow": 0.12, "GlowIrid": 0.6, "FresnelExponent": 1.2,
                  "IridScale": 1.6}}
# Placement in the pearl frame: f = unit vector pearl -> camera (horizontal), r = right of it, z = up. Distances in cm.
RIG = {
    "KEY":  {"cls": "RectLight", "at": (35.0, 12.0, 30.0), "kelvin": 4500.0, "source": (20.0, 20.0), "radius": None},
    "PING": {"cls": "PointLight", "at": (60.0, -6.0, 8.0), "kelvin": 5200.0, "source": None, "radius": 0.5},
    "RIM":  {"cls": "SpotLight", "at": (-40.0, -15.0, 30.0), "kelvin": 6000.0, "source": None, "radius": 1.0,
             "cone": (10.0, 25.0)},
}
STATES = [  # name, {light: intensity}
    ("s0_f4_no_rig", {"KEY": 0.0, "PING": 0.0, "RIM": 0.0}),
    ("s1_key_only", {"KEY": 4.0, "PING": 0.0, "RIM": 0.0}),
    ("s2_rig_low", {"KEY": 4.0, "PING": 2.0, "RIM": 5.0}),
    ("s3_rig_high", {"KEY": 10.0, "PING": 5.0, "RIM": 12.0}),
]
RES, SETTLE_TICKS, FILE_TIMEOUT_TICKS = (1600, 900), 25, 600


def rig_positions(pearl, cam):
    """Pure: world positions for RIG from pearl and camera locations (x, y, z tuples)."""
    fx, fy = cam[0] - pearl[0], cam[1] - pearl[1]
    n = math.hypot(fx, fy) or 1.0
    fx, fy = fx / n, fy / n
    rx, ry = -fy, fx
    out = {}
    for k, spec in RIG.items():
        a, b, c = spec["at"]
        out[k] = (pearl[0] + a * fx + b * rx, pearl[1] + a * fy + b * ry, pearl[2] + c)
    return out


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    with open(path, encoding="utf-8") as fh:
        if json.load(fh) != json.loads(json.dumps(payload)):
            raise RuntimeError("record did not read back: %s" % path)


def _census(u):
    els = u.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_path_name()) for p in els.get_dirty_content_packages()),
            "maps": sorted(str(p.get_path_name()) for p in els.get_dirty_map_packages())}


def prepare(u, run):
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE running")
    asub = u.get_editor_subsystem(u.EditorActorSubsystem)
    if any(a.get_actor_label().startswith(PREFIX) for a in asub.get_all_level_actors()):
        raise RuntimeError("ZZ_PEARLLIGHT_* already present (run CLEANUP + Don't-Save restart)")
    c0 = _census(u)
    if c0["content"] or c0["maps"]:
        raise RuntimeError("census not clean %s" % c0)
    _write(HERE + "pearl_light_prepare.json", {"run": run, "labels": [PREFIX + k for k in RIG], "census_before": c0,
                                              "written": datetime.datetime.now().isoformat(timespec="seconds")})
    for k, spec in RIG.items():
        a = asub.spawn_actor_from_class(getattr(u, spec["cls"]), u.Vector(0, 0, -100000), u.Rotator(0, 0, 0))
        a.set_actor_label(PREFIX + k)
        a.tags = [TAG]
        a.set_actor_hidden_in_game(True)
        lc = a.get_component_by_class(u.LightComponent)
        lc.set_intensity(0.0)
        lc.set_editor_property("lighting_channels", u.LightingChannels(channel0=False, channel1=True, channel2=False))
        lc.set_mobility(u.ComponentMobility.MOVABLE)
    u.log("PEARLLIGHT_PREPARE_OK|run=%s|temps=%d|PEARLLIGHT_NEEDS_DONT_SAVE_RESTART" % (run, len(RIG)))


def cleanup(u, run):
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE running")
    asub = u.get_editor_subsystem(u.EditorActorSubsystem)
    gone = 0
    for a in list(asub.get_all_level_actors()):
        if a.get_actor_label().startswith(PREFIX) and TAG in [str(t) for t in a.tags]:
            gone += int(bool(asub.destroy_actor(a)))
    u.log("PEARLLIGHT_CLEANUP_OK|run=%s|destroyed=%d|map stays dirty: Don't-Save restart + editor_sky_toggle.py" % (run, gone))


def capture(u, run):
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError("no PIE")
    by_label = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
    lights = {k: by_label.get(PREFIX + k) for k in RIG}
    pearl, glow = by_label.get(PEARL), by_label.get(GLOW)
    pcon = u.GameplayStatics.get_player_controller(world, 0)
    cam = pcon.get_view_target() if pcon else None
    if None in list(lights.values()) + [pearl, glow, cam]:
        raise RuntimeError("missing: %s" % [k for k, v in list(lights.items()) + [("pearl", pearl), ("glow", glow),
                                                                                    ("cam", cam)] if v is None])
    pc = pearl.get_component_by_class(u.StaticMeshComponent)
    gc = glow.get_component_by_class(u.LightComponent)
    lcs = {k: a.get_component_by_class(u.LightComponent) for k, a in lights.items()}
    orig = {"pearl_mat": pc.get_material(0), "pearl_channels": pc.get_editor_property("lighting_channels"),
            "glow_visible": bool(gc.is_visible())}
    _write(HERE + "pearl_light_originals_%s.json" % run,
           {"run": run, "pearl_mat": orig["pearl_mat"].get_path_name() if orig["pearl_mat"] else None,
            "pearl_channels": [bool(orig["pearl_channels"].get_editor_property(n)) for n in ("channel0", "channel1", "channel2")],
            "glow_visible": orig["glow_visible"]})
    p, cl = pearl.get_actor_location(), cam.get_actor_location()
    pos = rig_positions((p.x, p.y, p.z), (cl.x, cl.y, cl.z))
    out = os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor", "Captures", run)
    os.makedirs(out, exist_ok=True)
    st = {"i": 0, "phase": "setup", "wait": 0, "rows": [], "handle": None, "done": False}

    def setup_once():
        mid = pc.create_dynamic_material_instance(0, u.load_asset(GO_MI))
        for k, x in F4["scalars"].items():
            mid.set_scalar_parameter_value(k, float(x))
        pc.set_editor_property("lighting_channels", u.LightingChannels(channel0=True, channel1=True, channel2=False))
        gc.set_visibility(False, False)
        for k, a in lights.items():
            spec, loc = RIG[k], u.Vector(*pos[k])
            a.set_actor_location_and_rotation(loc, u.MathLibrary.find_look_at_rotation(loc, p), False, True)
            a.set_actor_hidden_in_game(False)
            lc = lcs[k]
            lc.set_editor_property("use_temperature", True)
            lc.set_editor_property("temperature", spec["kelvin"])
            if spec["source"]:
                lc.set_editor_property("source_width", spec["source"][0])
                lc.set_editor_property("source_height", spec["source"][1])
            if spec["radius"] is not None:
                lc.set_editor_property("source_radius", spec["radius"])
            if spec.get("cone"):
                lc.set_editor_property("inner_cone_angle", spec["cone"][0])
                lc.set_editor_property("outer_cone_angle", spec["cone"][1])
            lc.set_editor_property("attenuation_radius", 300.0)

    def restore():
        pc.set_material(0, orig["pearl_mat"])
        pc.set_editor_property("lighting_channels", orig["pearl_channels"])
        gc.set_visibility(orig["glow_visible"], False)
        for k, a in lights.items():
            lcs[k].set_intensity(0.0)
            a.set_actor_hidden_in_game(True)

    def finish(ok, reason=""):
        if st["done"]:
            return
        st["done"] = True
        try:
            restore()
        finally:
            u.unregister_slate_post_tick_callback(st["handle"])
        if ok:
            u.log("PEARLLIGHT_CAPTURE_OK|run=%s|n=%d|dir=%s|pos=%s" % (run, len(st["rows"]), out, json.dumps(pos)))
        else:
            u.log_error("PEARLLIGHT_FAILED|run=%s|%s|restored=1" % (run, reason))

    def tick(_dt):
        try:
            if st["done"]:
                return
            if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is None:
                st["done"] = True
                u.unregister_slate_post_tick_callback(st["handle"])
                u.log_error("PEARLLIGHT_FAILED|run=%s|PIE ended mid-run" % run)
                return
            if st["i"] >= len(STATES):
                finish(True)
                return
            name, levels = STATES[st["i"]]
            path = os.path.join(out, name + ".png").replace("\\", "/")
            if st["phase"] == "setup":
                for k, v in levels.items():
                    lcs[k].set_intensity(float(v))
                st.update(phase="settle", wait=SETTLE_TICKS)
            elif st["phase"] == "settle":
                st["wait"] -= 1
                if st["wait"] <= 0:
                    u.SystemLibrary.execute_console_command(world, 'HighResShot %dx%d filename="%s"' % (RES[0], RES[1], path))
                    st.update(phase="file", wait=FILE_TIMEOUT_TICKS)
            elif st["phase"] == "file":
                st["wait"] -= 1
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    st["rows"].append({"state": name, "bytes": os.path.getsize(path)})
                    st.update(i=st["i"] + 1, phase="setup")
                elif st["wait"] <= 0:
                    finish(False, "FILE_TIMEOUT|%s" % path)
        except Exception as exc:  # noqa: BLE001
            finish(False, "%s: %s" % (type(exc).__name__, exc))

    setup_once()
    st["handle"] = u.register_slate_post_tick_callback(tick)
    u.log("PEARLLIGHT_ARMED|run=%s|states=%d" % (run, len(STATES)))


def main():
    import unreal as u
    mode = globals().get("PL_MODE", "PREPARE")
    run = "PEARLLIGHT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        {"PREPARE": prepare, "CAPTURE": capture, "CLEANUP": cleanup}[mode](u, run)
    except Exception as exc:  # noqa: BLE001
        u.log_error("PEARLLIGHT_FAILED|run=%s|mode=%s|%s: %s" % (run, mode, type(exc).__name__, exc))


if "unreal" in __import__("sys").modules and globals().get("PL_MODE"):
    main()
