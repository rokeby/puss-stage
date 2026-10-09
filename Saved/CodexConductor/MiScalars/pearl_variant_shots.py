"""PIE-only pearl comparison stills via the CURRENT view-target camera (a SceneCapture can't be spawned/added from
Python in PIE: no begin_deferred_actor_spawn_from_class, no AActor.add_component_by_class [measured 8 Oct]).
Run after pvs_scrub (transport paused at Scene 3 frame 1800). A slate post-tick state machine (pattern:
scene_stills.py HighResShot + file wait) steps VARIANT x SHOT: apply PIE-only overrides, move + manually focus the view
camera on the pearl, wait SETTLE ticks, HighResShot, wait for the file. Then restores camera transform, focus settings,
aperture, materials, visibility and light intensity. Nothing is saved; the editor world is not touched.
Markers PVSHOT_OK|run=.. / PVSHOT_FAILED|run=..|reason."""
import datetime
import json
import math
import os

DIR = "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/"
PEARL, TWIN, GLOW = "S3 PearlClam Pearl", "S3 PearlClam Pearl Fade", "S3 Drama Pearl Glow"
GREEN = {"vectors": {"PaletteA": (0.72, 0.74, 0.48), "PaletteB": (-0.22, 0.10, 0.10), "PaletteC": (1.0, 1.0, 1.0),
                     "PaletteD": (0.0, 0.0, 0.0), "SubsurfaceBase": (0.92, 0.91, 0.87), "GlowColor": (1.0, 0.97, 0.92)},
         "scalars": {"IridStrength": 0.45, "SubsurfaceIrid": 0.45, "FresnelExponent": 2.0, "Glow": 0.03, "GlowIrid": 0.0}}
GREEN_STRONG = {"vectors": GREEN["vectors"], "scalars": dict(GREEN["scalars"], IridStrength=0.8, SubsurfaceIrid=0.7)}


def gs(**kw):
    return {"vectors": GREEN["vectors"], "scalars": dict(GREEN_STRONG["scalars"], **kw)}


GO = DIR + "MI_PearlClam_Pearl_v3_GreenOrange"
VARIANTS = [  # name, solid_visible, solid_mi, twin_visible, twin_mi, overrides, glow light ("off" | None = as keyed)
    ("f0_green_strong_ref", True, GO, False, None, gs(), "off"),
    ("f1_glow006", True, GO, False, None, gs(Glow=0.06, GlowIrid=0.6, GlowFalloff=2.0), "off"),
    ("f2_glow012", True, GO, False, None, gs(Glow=0.12, GlowIrid=0.6, GlowFalloff=2.0), "off"),
    ("f3_glow020", True, GO, False, None, gs(Glow=0.20, GlowIrid=0.6, GlowFalloff=2.0), "off"),
    ("f4_glow012_broadsheen", True, GO, False, None, gs(Glow=0.12, GlowIrid=0.6, FresnelExponent=1.2, IridScale=1.6), "off"),
]
# PVSHOT_SET="AS_AUTHORED": one variant that overrides NOTHING (materials, twin, glow light all as saved/keyed) -
# the post-APPLY proof shots (9 Oct PearlF4 + glow x0.15)
if globals().get("PVSHOT_SET") == "AS_AUTHORED":
    VARIANTS = [("as_authored", None, None, None, None, None, None)]
SHOTS = (("near", 200.0, 18.0, 75.0),)   # yaw from +X, elev, cm
RES = (1600, 900)
SETTLE_TICKS = 25
FILE_TIMEOUT_TICKS = 600


def main():
    import unreal as u
    run = "PVSHOT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        u.log_error("PVSHOT_FAILED|run=%s|no PIE" % run)
        return

    def find(label):
        hits = [a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor) if a.get_actor_label() == label]
        return hits[0] if len(hits) == 1 else None

    pearl, twin, glow = find(PEARL), find(TWIN), find(GLOW)
    pcon = u.GameplayStatics.get_player_controller(world, 0)
    cam = pcon.get_view_target() if pcon else None
    ccc = cam.get_cine_camera_component() if cam is not None and hasattr(cam, "get_cine_camera_component") else None
    if None in (pearl, twin, glow, ccc):
        u.log_error("PVSHOT_FAILED|run=%s|missing pearl=%s twin=%s glow=%s cinecam=%s"
                    % (run, pearl is not None, twin is not None, glow is not None, ccc is not None))
        return
    pc, tc = (a.get_component_by_class(u.StaticMeshComponent) for a in (pearl, twin))
    lc = glow.get_component_by_class(u.LightComponent)
    orig = {"cam_loc": cam.get_actor_location(), "cam_rot": cam.get_actor_rotation(),
            "focus": ccc.get_editor_property("focus_settings"), "aperture": float(ccc.get_editor_property("current_aperture")),
            "pearl_mat": pc.get_material(0), "twin_mat": tc.get_material(0),
            "pearl_hidden": bool(pearl.get_editor_property("hidden")), "twin_hidden": bool(twin.get_editor_property("hidden")),
            "glow": float(lc.get_editor_property("intensity")), "glow_vis": bool(lc.is_visible())}
    tgt = pearl.get_actor_location()
    out = os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor",
                       "Captures", run)
    os.makedirs(out, exist_ok=True)
    queue = [(v, s) for v in VARIANTS for s in SHOTS]
    st = {"i": 0, "phase": "setup", "wait": 0, "rows": [], "handle": None, "done": False}

    def apply_variant(v):
        name, sv, smi, tv, tmi, tov, gcd = v
        if sv is None:   # AS_AUTHORED: touch nothing
            return
        pearl.set_actor_hidden_in_game(not sv)
        twin.set_actor_hidden_in_game(not tv)
        if sv:
            pc.set_material(0, u.load_asset(smi))
            if tov and not tv:
                m2 = pc.create_dynamic_material_instance(0, u.load_asset(smi))
                for k, x in tov["scalars"].items():
                    m2.set_scalar_parameter_value(k, float(x))
                for k, c in tov.get("vectors", {}).items():
                    m2.set_vector_parameter_value(k, u.LinearColor(c[0], c[1], c[2], 1.0))
        if tv:
            mid = tc.create_dynamic_material_instance(0, u.load_asset(tmi))
            for k, c in tov["vectors"].items():
                mid.set_vector_parameter_value(k, u.LinearColor(c[0], c[1], c[2], 1.0))
            for k, x in tov["scalars"].items():
                mid.set_scalar_parameter_value(k, float(x))
            mid.set_scalar_parameter_value("Fade", float(tov["fade"]))
        if gcd == "off":
            lc.set_visibility(False, False)
        else:
            lc.set_visibility(True, False)
            lc.set_intensity(orig["glow"] if gcd is None else float(gcd))

    def aim(shot):
        _n, yaw_d, el_d, dist = shot
        yaw, el = math.radians(yaw_d), math.radians(el_d)
        loc = u.Vector(tgt.x + dist * math.cos(el) * math.cos(yaw), tgt.y + dist * math.cos(el) * math.sin(yaw),
                       tgt.z + dist * math.sin(el))
        cam.set_actor_location_and_rotation(loc, u.MathLibrary.find_look_at_rotation(loc, tgt), False, True)
        fs = ccc.get_editor_property("focus_settings")
        fs.set_editor_property("focus_method", u.CameraFocusMethod.MANUAL)
        fs.set_editor_property("manual_focus_distance", float(dist))
        ccc.set_editor_property("focus_settings", fs)
        ccc.set_editor_property("current_aperture", 5.6)

    def restore():
        pc.set_material(0, orig["pearl_mat"])
        tc.set_material(0, orig["twin_mat"])
        pearl.set_actor_hidden_in_game(orig["pearl_hidden"])
        twin.set_actor_hidden_in_game(orig["twin_hidden"])
        lc.set_visibility(orig["glow_vis"], False)
        lc.set_intensity(orig["glow"])
        cam.set_actor_location_and_rotation(orig["cam_loc"], orig["cam_rot"], False, True)
        ccc.set_editor_property("focus_settings", orig["focus"])
        ccc.set_editor_property("current_aperture", orig["aperture"])

    def finish(ok, reason=""):
        if st["done"]:
            return
        st["done"] = True
        try:
            restore()
        finally:
            if st["handle"] is not None:
                u.unregister_slate_post_tick_callback(st["handle"])
        if ok:
            u.log("PVSHOT_OK|run=%s|n=%d|dir=%s|glow_keyed=%.2f|%s" % (run, len(st["rows"]), out, orig["glow"],
                                                                      json.dumps(st["rows"])))
        else:
            u.log_error("PVSHOT_FAILED|run=%s|%s|restored=1" % (run, reason))

    def tick(_dt):
        try:
            if st["done"]:
                return
            if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is None:
                st["done"] = True
                u.unregister_slate_post_tick_callback(st["handle"])
                u.log_error("PVSHOT_FAILED|run=%s|PIE ended mid-run" % run)
                return
            if st["i"] >= len(queue):
                finish(True)
                return
            v, s = queue[st["i"]]
            path = os.path.join(out, "%s__%s.png" % (v[0], s[0])).replace("\\", "/")
            if st["phase"] == "setup":
                apply_variant(v)
                aim(s)
                st.update(phase="settle", wait=SETTLE_TICKS)
            elif st["phase"] == "settle":
                st["wait"] -= 1
                if st["wait"] <= 0:
                    u.SystemLibrary.execute_console_command(world, 'HighResShot %dx%d filename="%s"' % (RES[0], RES[1], path))
                    st.update(phase="file", wait=FILE_TIMEOUT_TICKS)
            elif st["phase"] == "file":
                st["wait"] -= 1
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    st["rows"].append({"variant": v[0], "shot": s[0], "bytes": os.path.getsize(path)})
                    st.update(i=st["i"] + 1, phase="setup")
                elif st["wait"] <= 0:
                    finish(False, "FILE_TIMEOUT|%s" % path)
        except Exception as exc:  # noqa: BLE001
            finish(False, "%s: %s" % (type(exc).__name__, exc))

    st["handle"] = u.register_slate_post_tick_callback(tick)
    u.log("PVSHOT_ARMED|run=%s|n=%d|dir=%s" % (run, len(queue), out))


main()
