"""READ-ONLY S3 white probe (PIE). Phase from s3_white_probe_args.json:
  "scrub": pause + scrub the Master to FRAME (the PIE transport only; nothing in the editor world is touched)
  "read":  write camera pose, every PostProcessVolume (exposure fields, does it contain the camera) and the
           brightest lights near the camera to Saved/CodexConductor/s3_white_probe_<run>.json
Marker: S3WHITE_PROBE_OK|run=<id>|... or S3WHITE_PROBE_FAILED|run=<id>|reason=...
No save, no level write. UE wrappers live only inside main() (memory: no UE objects in module globals)."""
import json


def main():
    import unreal
    here = "E:/PussStage/Saved/CodexConductor/"
    args = json.load(open(here + "s3_white_probe_args.json", encoding="utf-8"))
    run = args["run"]
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        unreal.log_error("S3WHITE_PROBE_FAILED|run=%s|reason=NO_PIE" % run)
        return
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    if len(roots) != 1:
        unreal.log_error("S3WHITE_PROBE_FAILED|run=%s|reason=ROOTS_%d" % (run, len(roots)))
        return
    root = roots[0]
    if args["phase"] == "scrub":
        root.sequence_player.pause()
        for f in ([int(args["via"])] if args.get("via") else []) + [int(args["frame"])]:
            res = root.transport.scrub_to_master_frame(unreal.FrameNumber(f))
            if res != unreal.InfinityTransportResult.SUCCEEDED:
                unreal.log_error("S3WHITE_PROBE_FAILED|run=%s|phase=scrub|target=%d|result=%s" % (run, f, res))
                return
        landed = int(root.transport.get_current_master_frame().value)
        if landed != int(args["frame"]):
            unreal.log_error("S3WHITE_PROBE_FAILED|run=%s|phase=scrub|landed=%d" % (run, landed))
            return
        unreal.log("S3WHITE_PROBE_OK|run=%s|phase=scrub|frame=%d" % (run, landed))
        return

    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    cam = pc.player_camera_manager
    cl = cam.get_camera_location()
    cloc = [cl.x, cl.y, cl.z]
    out = {"run": run, "frame": int(root.transport.get_current_master_frame().value), "camera": cloc,
           "view_target": str(pc.get_view_target().get_actor_label()) if pc.get_view_target() else None,
           "ppv": [], "camera_pp": None, "lights": []}

    def pp_fields(s):
        d = {}
        for n in ("auto_exposure_method", "auto_exposure_bias", "auto_exposure_min_brightness",
                  "auto_exposure_max_brightness", "auto_exposure_apply_physical_camera_exposure",
                  "camera_iso", "camera_shutter_speed", "depth_of_field_fstop", "bloom_intensity"):
            try:
                d[n] = str(s.get_editor_property(n))
                ov = "override_" + n
                d[ov] = bool(s.get_editor_property(ov))
            except Exception:
                pass
        return d

    vt = pc.get_view_target()
    if vt is not None:
        for comp in vt.get_components_by_class(unreal.CameraComponent):
            out["camera_pp"] = {"comp": comp.get_name(), "weight": comp.post_process_blend_weight,
                                "fields": pp_fields(comp.post_process_settings)}
    for v in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PostProcessVolume):
        o, e = v.get_actor_bounds(False)
        inside = all(abs(cloc[i] - [o.x, o.y, o.z][i]) <= [e.x, e.y, e.z][i] for i in range(3))
        out["ppv"].append({"label": str(v.get_actor_label()), "enabled": bool(v.enabled),
                           "unbound": bool(v.unbound), "priority": v.priority, "blend_weight": v.blend_weight,
                           "hidden": bool(v.is_hidden_ed()) if hasattr(v, "is_hidden_ed") else None,
                           "bounds_contains_camera": inside, "fields": pp_fields(v.settings)})
    rows = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        for lc in a.get_components_by_class(unreal.LightComponent):
            loc = lc.get_world_location()
            dist = ((loc.x - cloc[0]) ** 2 + (loc.y - cloc[1]) ** 2 + (loc.z - cloc[2]) ** 2) ** 0.5
            directional = isinstance(lc, unreal.DirectionalLightComponent)
            if not directional and dist > 6000:
                continue
            rows.append({"actor": str(a.get_actor_label()), "comp": lc.get_name(), "class": lc.get_class().get_name(),
                         "intensity": lc.intensity, "visible": bool(lc.is_visible()), "dist_cm": round(dist),
                         "level": a.get_outermost().get_name()})
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SkyLight):
        lc = a.light_component
        rows.append({"actor": str(a.get_actor_label()), "comp": lc.get_name(), "class": "SkyLightComponent",
                     "intensity": lc.intensity, "visible": bool(lc.is_visible()), "dist_cm": None,
                     "level": a.get_outermost().get_name()})
    rows.sort(key=lambda r: -(r["intensity"] if r["visible"] else 0))
    out["lights"] = rows[:60]
    out["light_count_considered"] = len(rows)
    path = here + "s3_white_probe_%s.json" % run
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    unreal.log("S3WHITE_PROBE_OK|run=%s|phase=read|ppv=%d|lights=%d|path=%s" % (run, len(out["ppv"]), len(rows), path))


try:
    main()
except Exception as exc:  # assert, don't print: a failure is a marker, not silence
    import unreal
    unreal.log_error("S3WHITE_PROBE_FAILED|reason=EXC|%r" % (exc,))
