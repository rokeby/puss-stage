"""PIE-only probe (no saves): scrub to Scene 3 + t, then project actors into the player's view and log (a) small
mesh actors (bounds < 60 cm) near screen point CUBE_UV, (b) every visible light whose position or aim lands in the
lower-left quadrant.  Args pie_screen_find_args.json {"t":166.1,"cube_uv":[0.62,0.23]}.  SCREENFIND_OK / _FAILED."""
import json, math


def main():
    import unreal as u
    a = json.load(open("E:/PussStage/Saved/CodexConductor/pie_screen_find_args.json"))
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    root = list(u.GameplayStatics.get_all_actors_of_class(w, u.InfinityStageShowRoot))[0]
    tr, player = root.transport, root.sequence_player
    seg = [s for s in list(tr.segments) if str(s.label).startswith("Scene 3")][0]
    pc = u.GameplayStatics.get_player_controller(w, 0)
    st = {"wait": -1, "h": None}

    def tick(_dt):
        try:
            if st["wait"] < 0:
                player.pause(); r = tr.scrub_to_master_frame(u.FrameNumber(int(seg.start_frame.value + a["t"] * 24000)))
                u.log("SCREENFIND_SCRUB|%s" % r); st["wait"] = 40; return
            if st["wait"] > 0:
                st["wait"] -= 1; return
            u.unregister_slate_post_tick_callback(st["h"])
            vs = u.WidgetLayoutLibrary.get_viewport_size(w)          # pixels; PlayerController.get_viewport_size is an out-param
            sx, sy = float(vs.x), float(vs.y)
            cube, lights = [], []
            for act in u.GameplayStatics.get_all_actors_of_class(w, u.Actor):
                if act.get_editor_property("hidden"): continue
                o, e = act.get_actor_bounds(False)[0], act.get_actor_bounds(False)[1]
                res = u.GameplayStatics.project_world_to_screen(pc, o, False)
                if res is None: continue
                scr = res[-1] if isinstance(res, tuple) else res
                if isinstance(res, tuple) and len(res) > 1 and not res[0]: continue
                uvx, uvy = scr.x / float(sx), scr.y / float(sy)
                if not (0 <= uvx <= 1 and 0 <= uvy <= 1): continue
                lab = str(act.get_actor_label()); cls = act.get_class().get_name()
                lc = act.get_component_by_class(u.LightComponent)
                if lc is not None and lc.is_visible():
                    lights.append([lab, cls, round(uvx, 3), round(uvy, 3), round(float(lc.get_editor_property("intensity")), 1)])
                elif max(e.x, e.y, e.z) < 60 and math.hypot(uvx - a["cube_uv"][0], uvy - a["cube_uv"][1]) < 0.12:
                    cube.append([lab, cls, round(uvx, 3), round(uvy, 3), [round(e.x), round(e.y), round(e.z)]])
            cm = u.GameplayStatics.get_player_camera_manager(w, 0)
            l = cm.get_camera_location()
            json.dump({"t": a["t"], "cam": [round(l.x), round(l.y), round(l.z)], "viewport": [sx, sy], "cube_candidates": cube,
                       "lights_in_view": sorted(lights, key=lambda r: (r[3] < 0.5, r[2]))},
                      open("E:/PussStage/Saved/CodexConductor/pie_screen_find.json", "w"), indent=1)
            u.log("SCREENFIND_OK|cube=%d|lights=%d" % (len(cube), len(lights)))
        except Exception as exc:  # noqa: BLE001
            u.unregister_slate_post_tick_callback(st["h"]); u.log_error("SCREENFIND_FAILED|%r" % (exc,))

    st["h"] = u.register_slate_post_tick_callback(tick)


main()
