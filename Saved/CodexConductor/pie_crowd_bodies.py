"""PIE-only probe (no saves): S3 + offset; for the 15 'P21.S3Crowd' copies and the 5 Shore figures: actor root location vs
each visible primitive component's world bounds centre (skeletal / geometry cache / static), so a body rendered away from
its root shows.  Args: offset seconds in pie_crowd_bodies_args.json {"t": 30}.  PIE_CROWDBODIES_OK / _FAILED."""
import json


def main():
    import unreal as u
    t = json.load(open("E:/PussStage/Saved/CodexConductor/pie_crowd_bodies_args.json")).get("t", 30)
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    root = list(u.GameplayStatics.get_all_actors_of_class(w, u.InfinityStageShowRoot))[0]
    tr, player = root.transport, root.sequence_player
    seg = [s for s in list(tr.segments) if str(s.label).startswith("Scene 3")][0]
    st = {"wait": -1, "h": None}

    def tick(_dt):
        try:
            if st["wait"] < 0:
                player.pause(); tr.scrub_to_master_frame(u.FrameNumber(int(seg.start_frame.value + t * 24000))); st["wait"] = 40; return
            if st["wait"] > 0:
                st["wait"] -= 1; return
            u.unregister_slate_post_tick_callback(st["h"])
            rows = []
            for a in u.GameplayStatics.get_all_actors_of_class(w, u.Actor):
                l = str(a.get_actor_label()); tags = [str(x) for x in a.tags]
                if not (("P21.S3Crowd" in tags and "Camera" not in a.get_class().get_name()) or (l.startswith("Shore0") and l.endswith("Clam"))):
                    continue
                p = a.get_actor_location()
                comps = []
                for c in a.get_components_by_class(u.PrimitiveComponent):
                    if not c.is_visible(): continue
                    o, e, _r = u.SystemLibrary.get_component_bounds(c)
                    if e.x + e.y > 5: comps.append([c.get_class().get_name()[:18], round(o.x), round(o.y), round(o.z), round(e.x), round(e.y)])
                rows.append({"label": l[:30], "root": [round(p.x), round(p.y), round(p.z)], "comps": comps[:4]})
            json.dump({"t": t, "rows": rows}, open("E:/PussStage/Saved/CodexConductor/pie_crowd_bodies.json", "w"), indent=1)
            u.log("PIE_CROWDBODIES_OK|t=%s|n=%d" % (t, len(rows)))
        except Exception as exc:  # noqa: BLE001
            u.unregister_slate_post_tick_callback(st["h"]); u.log_error("PIE_CROWDBODIES_FAILED|%r" % (exc,))

    st["h"] = u.register_slate_post_tick_callback(tick)


main()
