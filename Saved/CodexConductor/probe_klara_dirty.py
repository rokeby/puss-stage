"""Read-only diagnosis: what dirties Klara's streamed levels during a Passage materialize. NOTHING SAVED.
Snapshots every actor in Klara levels (L_Animals, L_KK_children, Japanese_Alley, L_KK_Void) - transform, hidden flags,
attach parent - and the dirty census; materializes ONE passage (args: passage label contains); snapshots again; logs the
census and every per-actor difference. Marker KLARADIRTY|... . If anything is dirty after, the conductor does a
Don't-Save restart."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
ARGS = json.load(open(os.path.join(HERE, "probe_klara_dirty_args.json"), encoding="utf-8"))
KLARA = ("L_Animals", "L_KK_children", "Japanese_Alley", "L_KK_Void")


def census():
    return {"content": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def snap():
    out = {}
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        lvl = a.get_outermost().get_name().split("/")[-1]
        if lvl not in KLARA:
            continue
        t = a.get_actor_transform()
        par = a.get_attach_parent_actor()
        out["%s|%s" % (lvl, a.get_path_name().split(".")[-1])] = {
            "loc": [round(t.translation.x, 2), round(t.translation.y, 2), round(t.translation.z, 2)],
            "rot": [round(v, 3) for v in (t.rotation.rotator().roll, t.rotation.rotator().pitch, t.rotation.rotator().yaw)],
            "scale": [round(t.scale3d.x, 4), round(t.scale3d.y, 4), round(t.scale3d.z, 4)],
            "hidden": bool(a.get_editor_property("hidden")), "hidden_ed": bool(a.is_hidden_ed()),
            "parent": par.get_actor_label() if par else None}
    return out


c0 = census()
s0 = snap()
unreal.log("KLARADIRTY_BEFORE|census=%s|klara_actors=%d" % (json.dumps(c0), len(s0)))
acts = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        if a.get_class().get_name() == "InfinityStagePassageActor" and ARGS["passage"] in str(a.get_actor_label())]
if len(acts) != 1:
    raise RuntimeError("KLARADIRTY_PASSAGES=%d" % len(acts))
ok = bool(acts[0].materialize_passage()) if ARGS.get("materialize", True) else None
if ARGS.get("evaluate_master_frame") is not None:
    f = ARGS["evaluate_master_frame"]
    if f == "p06_mid":
        show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
        tr = unreal.new_object(unreal.InfinityStageTransportController)
        tr.build_segments(show)
        seg = [x for x in tr.get_editor_property("segments") if str(x.get_editor_property("label")) == "Passage 6"][0]
        f = (seg.get_editor_property("start_frame").value + seg.get_editor_property("end_frame").value) // 2
    ARGS["evaluate_master_frame"] = f
    ev = bool(acts[0].evaluate_mechanisms_at_master_frame(unreal.FrameNumber(int(f))))
    unreal.log("KLARADIRTY_EVAL|frame=%s|ok=%s|census=%s" % (ARGS["evaluate_master_frame"], ev, json.dumps(census())))
c1 = census()
s1 = snap()
diff = {k: {"before": s0.get(k), "after": s1.get(k)} for k in set(s0) | set(s1) if s0.get(k) != s1.get(k)}
unreal.log("KLARADIRTY_AFTER|passage=%s|materialize=%s|census=%s|changed=%d" % (ARGS["passage"], ok, json.dumps(c1), len(diff)))
unreal.log("KLARADIRTY_DIFF|%s" % json.dumps(dict(list(diff.items())[:25])))
