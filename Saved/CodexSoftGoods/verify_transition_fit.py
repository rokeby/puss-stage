"""READ-ONLY read-back (30 Sep) of fit_transition_drapes.py's saved result in the five Interaction sequences. It reloads
each saved sequence and checks the following:
  - the "Transition Drape (baked)" spawnable: its cache, running=True, location and yaw;
  - the spawn range [0, end);
  - HOLD [0, end - 150) with the end offset dur_ticks - 1 (one tick), and FALL [end - 150, end);
  - the camera cut [0, end), bound to that mouth's tagged stalls camera;
  - the old rig's bCurtainActive keyed False.
Writes verify_transition_fit.json. Logs PUSS_SOFTGOODS_FIT_VERIFY|ok=... Writes nothing to Unreal; everything is
inside main()."""
import json
import os

import unreal

SEQ_DIR = "/Game/InfinityStage/Interactions"
SEQS = {1: "LS_Interaction_01_WashingTheBoy", 2: "LS_Interaction_02_Turnips", 3: "LS_Interaction_03_ForgetsHisName",
        4: "LS_Interaction_04_GetsAName", 5: "LS_Interaction_05_BecomesKing"}
GC = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def main():
    fit = json.load(open(os.path.join(HERE, "fit_transition_drapes.json"), encoding="utf-8"))
    mouths = {r["interaction"]: r["mouth"] for r in fit["rows"]}
    # The fit records the sections it planned (HOLD at the first sample or one frame before the release); older runs
    # without that record are checked against the legacy layout.
    planned = {r["interaction"]: r.get("sections_planned") for r in fit["rows"]}
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_outermost().get_name()
    if world != "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice":
        unreal.log(f"PUSS_SOFTGOODS_FIT_VERIFY|ok=False|refusing: open world is {world}")
        return
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    cache = unreal.load_asset(GC)
    rows, ok = [], True
    for n, name in SEQS.items():
        seq = unreal.load_asset(f"{SEQ_DIR}/{name}")
        rate = seq.get_display_rate()
        fps = rate.numerator / rate.denominator
        tick = seq.get_tick_resolution()
        dur_ticks = int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / 30.0
                              * tick.numerator / tick.denominator))
        end = seq.get_playback_end()
        fall_start = max(0, end - int(round(5.0 * fps)))
        row = {"interaction": n, "end": end, "checks": {}}
        c = row["checks"]
        drape = [b for b in seq.get_bindings() if str(b.get_display_name()) == "Transition Drape (baked)"]
        c["one_drape_binding"] = len(drape) == 1
        if drape:
            tmpl = drape[0].get_object_template()
            comp = tmpl.get_editor_property("geometry_cache_component")
            loc, rot, m = tmpl.get_actor_location(), tmpl.get_actor_rotation(), mouths[n]
            root = tmpl.get_editor_property("root_component")
            rl, rr = root.get_editor_property("relative_location"), root.get_editor_property("relative_rotation")
            row["template"] = {"actor_location": [loc.x, loc.y, loc.z], "actor_yaw": rot.yaw,
                               "root": root.get_name(), "root_relative_location": [rl.x, rl.y, rl.z],
                               "root_relative_yaw": rr.yaw, "mouth": m}
            c["cache"] = comp.get_editor_property("geometry_cache").get_path_name().split(".")[0] == GC
            c["running"] = bool(comp.get_editor_property("running"))
            c["location_within_1cm"] = abs(rl.x - m["x"]) < 1 and abs(rl.y - m["y"]) < 1 and abs(rl.z - m["z"]) < 1
            c["yaw_within_0.01"] = abs(((rr.yaw - m["yaw"] + 180) % 360) - 180) < 0.01
            tracks = {t.get_class().get_name(): t for t in drape[0].get_tracks()}
            spawn = tracks.get("MovieSceneSpawnTrack")
            c["spawn_range"] = bool(spawn) and [(s.get_start_frame(), s.get_end_frame()) for s in spawn.get_sections()] == [(0, end)]
            gct = tracks.get("MovieSceneGeometryCacheTrack")
            secs = []
            for s in (gct.get_sections() if gct else []):
                p = s.get_editor_property("params")
                secs.append([s.get_start_frame(), s.get_end_frame(), p.get_editor_property("start_frame_offset").value,
                             p.get_editor_property("end_frame_offset").value])
            row["gc_sections"] = secs
            want = planned.get(n) or [[0, fall_start, 0, dur_ticks - 1], [fall_start, end, 0, 0]]
            row["gc_sections_expected"] = want
            c["hold_fall"] = secs == want
        cuts = [t for t in seq.get_tracks() if t.get_class().get_name() == "MovieSceneCameraCutTrack"]
        c["one_cut_track"] = len(cuts) == 1
        if cuts:
            cs = cuts[0].get_sections()
            c["cut_range"] = [(s.get_start_frame(), s.get_end_frame()) for s in cs] == [(0, end)]
            want = cs[0].get_camera_binding_id() if cs else None
            row["cut_binding_id"] = str(want)
            proxy = seq.resolve_binding_id(want) if want is not None else None
            labels = [str(proxy.get_display_name())] if proxy is not None and proxy.is_valid() else []
            bound = [a for a in actors if labels and a.get_actor_label() == labels[0]]
            row["cut_camera"] = labels
            tag = f"InfinityStage.Mouth.P{n + 1:02d}"
            c["cut_camera_is_mouth_stalls"] = len(bound) == 1 and bound[0].actor_has_tag("InfinityStage.TransitionStalls") \
                and bound[0].actor_has_tag(tag)
        rig = [b for b in seq.get_bindings() if str(b.get_display_name()) == "Curtain Rig - Fire Safety Curtain"]
        if rig:
            keys = []
            for t in rig[0].get_tracks():
                if str(t.get_display_name()) == "bCurtainActive":
                    for s in t.get_sections():
                        keys += [(k.get_time().frame_number.value, k.get_value()) for k in s.get_all_channels()[0].get_keys()]
            row["rig_bCurtainActive_keys"] = keys
            c["rig_off"] = keys == [(0, False)]
        row["ok"] = all(v for v in c.values())
        ok = ok and row["ok"]
        rows.append(row)
        del seq
    del actors, cache
    out = os.path.join(HERE, "verify_transition_fit.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump({"ok": ok, "rows": rows}, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_FIT_VERIFY|ok={ok}|" + ";".join(f"I{r['interaction']}={r['ok']}" for r in rows))


main()
