"""PIE-only probe (no saves): scrub the Master to Scene 2 + each offset, pause, wait, and log for named actors their
hidden-in-game flag, light component visibility/intensity.  PIES2VIS_ROW / PIES2VIS_OK / PIES2VIS_FAILED."""
import datetime
OFFS = [1.0, 8.0, 14.0, 16.0]
NAMES = ["S2 Lattice Glow 1-1", "S2 Ghost Light", "S2 Practical L3", "Infinity Stage - Moon", "SpotLight3", "Spot_shrine",
         "P_Fire", "DirectionalLight", "SkyLight2"]
SETTLE = 20


def main():
    import unreal as u
    run = "PIES2VIS-" + datetime.datetime.now().strftime("%H%M%S")
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if w is None:
        u.log_error("PIES2VIS_FAILED|run=%s|no PIE" % run); return
    root = list(u.GameplayStatics.get_all_actors_of_class(w, u.InfinityStageShowRoot))[0]
    tr, player = root.transport, root.sequence_player
    seg = [s for s in list(tr.segments) if str(s.label).startswith("Scene 2")][0]
    acts = {}
    for a in u.GameplayStatics.get_all_actors_of_class(w, u.Actor):
        l = str(a.get_actor_label())
        if l in NAMES and l not in acts: acts[l] = a
    st = {"i": 0, "wait": -1, "done": False, "h": None}

    def tick(_dt):
        try:
            if st["done"]: return
            if st["i"] >= len(OFFS):
                st["done"] = True; u.unregister_slate_post_tick_callback(st["h"]); u.log("PIES2VIS_OK|run=%s|found=%s" % (run, sorted(acts))); return
            t = OFFS[st["i"]]
            if st["wait"] < 0:
                player.pause(); tr.scrub_to_master_frame(u.FrameNumber(int(seg.start_frame.value + t * 24000))); st["wait"] = SETTLE
            elif st["wait"] == 0:
                out = []
                for n in NAMES:
                    a = acts.get(n)
                    if a is None: out.append("%s=MISSING" % n); continue
                    lc = a.get_component_by_class(u.LightComponentBase)
                    li = ("vis=%s,int=%.2f" % (lc.is_visible(), float(lc.get_editor_property("intensity")))) if lc else "nolight"
                    out.append("%s=hidden:%s,%s" % (n, a.get_editor_property("hidden"), li))
                u.log("PIES2VIS_ROW|run=%s|t=%.1f|%s" % (run, t, ";".join(out)))
                st["i"] += 1; st["wait"] = -1
            else:
                st["wait"] -= 1
        except Exception as exc:  # noqa: BLE001
            st["done"] = True; u.unregister_slate_post_tick_callback(st["h"]); u.log_error("PIES2VIS_FAILED|run=%s|%r" % (run, exc))

    st["h"] = u.register_slate_post_tick_callback(tick)
    u.log("PIES2VIS_ARMED|run=%s" % run)


main()
