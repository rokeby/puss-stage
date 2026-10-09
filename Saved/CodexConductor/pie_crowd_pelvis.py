"""PIE-only probe (no saves): S3 + t; for the 15 crowd copies + 5 Shore figures: actor root/yaw, root component name,
every SkeletalMeshComponent (name, attach parent, relative location/rotation) and the 'pelvis' socket world location +
yaw on the first skeletal component that has it.  pie_crowd_pelvis.json.  PIE_CROWDPELVIS_OK / _FAILED."""
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
                p, r = a.get_actor_location(), a.get_actor_rotation()
                comps, pelvis = [], None
                for c in a.get_components_by_class(u.SkeletalMeshComponent):
                    par = c.get_attach_parent()
                    rl, rr = c.get_editor_property("relative_location"), c.get_editor_property("relative_rotation")
                    comps.append({"name": c.get_name(), "parent": par.get_name() if par else None,
                                  "rel_loc": [round(rl.x, 1), round(rl.y, 1), round(rl.z, 1)], "rel_rot": [round(rr.roll, 1), round(rr.pitch, 1), round(rr.yaw, 1)]})
                    if pelvis is None and c.does_socket_exist("pelvis"):
                        sl, sr = c.get_socket_location("pelvis"), c.get_socket_rotation("pelvis")
                        hl = c.get_socket_location("head") if c.does_socket_exist("head") else None
                        feet = [round(c.get_socket_location(b).z, 1) for b in ("foot_l", "foot_r", "ball_l", "ball_r") if c.does_socket_exist(b)]
                        pelvis = {"comp": c.get_name(), "loc": [round(sl.x), round(sl.y), round(sl.z)], "rot": [round(sr.roll, 1), round(sr.pitch, 1), round(sr.yaw, 1)],
                                  "head": [round(hl.x), round(hl.y), round(hl.z)] if hl else None, "feet_z": feet}
                rc = a.root_component
                rows.append({"label": l, "root": [round(p.x, 1), round(p.y, 1), round(p.z, 1)], "yaw": round(r.yaw, 2),
                             "root_comp": rc.get_name() if rc else None, "skel": comps, "pelvis": pelvis})
            json.dump({"t": t, "rows": rows}, open("E:/PussStage/Saved/CodexConductor/pie_crowd_pelvis.json", "w"), indent=1)
            u.log("PIE_CROWDPELVIS_OK|t=%s|n=%d" % (t, len(rows)))
        except Exception as exc:  # noqa: BLE001
            u.unregister_slate_post_tick_callback(st["h"]); u.log_error("PIE_CROWDPELVIS_FAILED|%r" % (exc,))

    st["h"] = u.register_slate_post_tick_callback(tick)


main()
