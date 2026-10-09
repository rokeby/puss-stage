"""Shadow-cat SILHOUETTE catalogue bench (Gary 9 Oct: "the silhouette contact sheet is a good idea").

EDITOR world, PIE must be OFF.  Spawns TRANSIENT bench actors (spawn_actor_from_class(..., transient=True)) far
above the set: one SkeletalMeshActor with the show's cat mesh (SK_Cat_R, the same mesh the Passage camera rig's
shadow cat uses) and one SceneCapture2D in SHOW-ONLY mode (only the cat is rendered, so the set and lights don't
matter). For every CLIP x FRACTION x VIEW, a slate post-tick state machine poses the cat (single-node animation,
SetPosition), waits SETTLE ticks, captures, reads the 8-bit render target and writes a raw PGM mask source
(R,G,B,A per pixel -> <out>/<clip>__<view>__<k>.rgba).  Then it DESTROYS the bench actors and checks the dirty census.
The contact sheet is built offline by make_sheet.py.  Nothing is saved.
Markers CATSIL_ARMED|run=.., CATSIL_OK|run=..|n=..|census_before=..|census_after=..|dir=.., CATSIL_FAILED|run=..|reason.
"""
import datetime
import json
import math
import os

MESH = "/Game/CharacterPacks/AnimX/Cats/Realistic/Mesh/SK_Cat_R.SK_Cat_R"
ANIM = "/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/"
CLIPS = [
    "Move/A_Cat_Move_Walk_F", "Idle/A_Cat_Idle_Base", "Idle/A_Cat_Idle_Stretching", "Idle/A_Cat_Idle_Look",
    "Idle/A_Cat_Idle_LookSite", "Idle/A_Cat_Idle_LookDown", "Idle/A_Cat_Idle_Yaw", "Action/A_Cat_Action_Shaking",
    "Action/A_Cat_Action_SharpensClaws", "Action/A_Cat_Action_Licking_sit", "Rest/A_Cat_Rest_Sit_to",
    "Rest/A_Cat_Rest_Lie_to", "Rest/A_Cat_Rest_Sleep_to", "Combat/A_Cat_Combat_Damage_FL",
    "Combat/A_Cat_Combat_Damage_SL", "Combat/A_Cat_Combat_Damage_BL", "Jump/A_Cat_Jump_InPlace",
    "Combat/A_Cat_Combat_Attack_Paw_L", "Crouch/A_Cat_Move_Crouch_F", "Move/A_Cat_Move_Trot_F",
]
FRACTIONS = (0.1, 0.35, 0.6, 0.85)
VIEWS = (("side", 90.0), ("threequarter", 45.0))      # degrees between the cat's body axis and the view
BENCH_LOC = (0.0, 0.0, 200000.0)                       # 2 km up: nothing of the set in a show-only capture anyway
RES = (480, 270)
DIST_CM = 260.0
FOV = 40.0
SETTLE = 4
HERE = "E:/PussStage/Saved/CodexConductor/CatSilhouettes_20261009/"


def main():
    import unreal as u
    run = "CATSIL-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        u.log_error("CATSIL_FAILED|run=%s|PIE running" % run)
        return
    lib = u.EditorLoadingAndSavingUtils

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    c0 = census()
    world = ed.get_editor_world()
    eas = u.get_editor_subsystem(u.EditorActorSubsystem)
    out = HERE + run + "/"
    os.makedirs(out, exist_ok=True)
    mesh = u.load_asset(MESH)
    anims = {}
    for c in CLIPS:
        a = u.load_asset(ANIM + c)
        if a is not None:
            anims[c] = a
    if mesh is None or not anims:
        u.log_error("CATSIL_FAILED|run=%s|mesh=%s anims=%d" % (run, mesh is not None, len(anims)))
        return
    loc = u.Vector(*BENCH_LOC)
    cat = eas.spawn_actor_from_class(u.SkeletalMeshActor, loc, u.Rotator(0, 0, 0), True)
    cap = eas.spawn_actor_from_class(u.SceneCapture2D, loc, u.Rotator(0, 0, 0), True)
    st = {"q": [], "i": 0, "phase": "pose", "wait": 0, "h": None, "done": False, "rows": []}

    def cleanup():
        for x in (cap, cat):
            try:
                if x is not None:
                    eas.destroy_actor(x)
            except Exception:  # noqa: BLE001
                pass

    def finish(ok, why=""):
        if st["done"]:
            return
        st["done"] = True
        if st["h"] is not None:
            u.unregister_slate_post_tick_callback(st["h"])
        cleanup()
        c1 = census()
        json.dump({"run": run, "rows": st["rows"], "res": RES, "census_before": c0, "census_after": c1,
                   "clips_missing": [c for c in CLIPS if c not in anims]}, open(out + "manifest.json", "w"), indent=1)
        if ok:
            u.log("CATSIL_OK|run=%s|n=%d|census_before=%s|census_after=%s|dir=%s" % (
                run, len(st["rows"]), json.dumps(c0), json.dumps(c1), out))
        else:
            u.log_error("CATSIL_FAILED|run=%s|%s|census_after=%s|dir=%s" % (run, why, json.dumps(c1), out))

    try:
        sk = cat.skeletal_mesh_component
        sk.set_skeletal_mesh_asset(mesh) if hasattr(sk, "set_skeletal_mesh_asset") else sk.set_skeletal_mesh(mesh)
        sk.set_update_animation_in_editor(True)
        sk.set_animation_mode(u.AnimationMode.ANIMATION_SINGLE_NODE)
        o, e = cat.get_actor_bounds(False)
        body_yaw = 0.0 if e.x >= e.y else 90.0            # long horizontal axis of the bind pose
        centre = u.Vector(o.x, o.y, o.z)
        cc = cap.capture_component2d
        rt = u.RenderingLibrary.create_render_target2d(world, RES[0], RES[1], u.TextureRenderTargetFormat.RTF_RGBA8)
        cc.set_editor_property("texture_target", rt)
        cc.set_editor_property("primitive_render_mode", u.SceneCapturePrimitiveRenderMode.PRIM_RENDER_MODE_USE_SHOW_ONLY_LIST)
        cc.set_editor_property("capture_source", u.SceneCaptureSource.SCS_SCENE_COLOR_HDR)
        cc.set_editor_property("capture_every_frame", False)
        cc.set_editor_property("capture_on_movement", False)
        cc.set_editor_property("fov_angle", FOV)
        cc.show_only_actor_components(cat)
        for c, a in anims.items():
            length = float(a.get_editor_property("sequence_length")) if hasattr(a, "get_editor_property") else 1.0
            for vname, vdeg in VIEWS:
                for k, fr in enumerate(FRACTIONS):
                    st["q"].append((c, a, length, vname, vdeg, k, fr))
    except Exception as exc:  # noqa: BLE001
        finish(False, "setup %s: %s" % (type(exc).__name__, exc))
        return

    def place_camera(vdeg):
        yaw = math.radians(body_yaw + vdeg)
        p = u.Vector(centre.x + DIST_CM * math.cos(yaw), centre.y + DIST_CM * math.sin(yaw), centre.z + 10.0)
        cap.set_actor_location_and_rotation(p, u.MathLibrary.find_look_at_rotation(p, centre), False, True)

    def tick(dt):
        try:
            if st["i"] >= len(st["q"]):
                finish(True)
                return
            c, a, length, vname, vdeg, k, fr = st["q"][st["i"]]
            if st["phase"] == "pose":
                sk.set_animation(a)
                sk.set_position(fr * length, False)
                sk.set_play_rate(0.0)
                place_camera(vdeg)
                st["phase"], st["wait"] = "settle", SETTLE
            elif st["phase"] == "settle":
                st["wait"] -= 1
                if st["wait"] <= 0:
                    cc.capture_scene()
                    st["phase"], st["wait"] = "read", 2
            elif st["phase"] == "read":
                st["wait"] -= 1
                if st["wait"] <= 0:
                    px = u.RenderingLibrary.read_render_target(world, rt, False)
                    name = "%s__%s__%d" % (c.split("/")[-1], vname, k)
                    with open(out + name + ".rgba", "wb") as fh:
                        fh.write(bytes(b for p in px for b in (p.r, p.g, p.b, p.a)))
                    st["rows"].append({"clip": c, "view": vname, "k": k, "fraction": fr, "length_s": length,
                                       "file": name + ".rgba", "n": len(px)})
                    st["i"] += 1
                    st["phase"] = "pose"
        except Exception as exc:  # noqa: BLE001
            finish(False, "tick %s: %s" % (type(exc).__name__, exc))

    st["h"] = u.register_slate_post_tick_callback(tick)
    u.log("CATSIL_ARMED|run=%s|clips=%d|shots=%d|body_yaw=%.0f|dir=%s" % (run, len(anims), len(st["q"]), body_yaw, out))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("CATSIL_FAILED|%s: %s" % (type(exc).__name__, exc))
