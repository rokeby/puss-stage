"""Read-only: verify every change in the last rollout against the plan, from a fresh load."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL
wm.editor_ready()
before = wm.dirty()
plan = wm.read_json("rollout_plan.json")["plan"]
res = wm.read_json("rollout_apply_result.json")
want_p, want_f = set(res["passages"]), set(res["families"])
fails, checked = [], 0
for it in plan:
    if it["family"] not in want_f or not (want_p & set(it["passages"])):
        continue
    for ch in it["changes"]:
        mi = unreal.EditorAssetLibrary.load_asset(ch["mi"])
        checked += 1
        if wm.pkg(mi.get_editor_property("parent")) != ch["parent"]:
            fails.append(f"{ch['mi']}: parent"); continue
        for n, v in ch.get("textures", {}).items():
            if wm.pkg(MEL.get_material_instance_texture_parameter_value(mi, n)) != v:
                fails.append(f"{ch['mi']}: {n}")
        for n, v in ch.get("switches", {}).items():
            if MEL.get_material_instance_static_switch_parameter_value(mi, n) != v:
                fails.append(f"{ch['mi']}: switch {n}")
        for n, v in ch.get("scalars", {}).items():
            if abs(MEL.get_material_instance_scalar_parameter_value(mi, n) - float(v)) > 1e-3 * max(1.0, abs(v)):
                fails.append(f"{ch['mi']}: {n}")
old = []
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        for m in comp.get_materials():
            if m and wm.pkg(m.get_base_material()).endswith("M_StageOpeningV2_Relief_Master"):
                old.append(actor.get_actor_label()[:10])
wm.require(wm.dirty() == before, "dirty changed")
wm.write_json("verify_rollout_result.json", {"checked": checked, "fails": fails, "still_on_old_relief": old, "dirty": before})
unreal.log(f"PUSS_WING_ROLLOUT_VERIFY_SUCCESS|checked={checked}|fails={len(fails)}|old_relief_slots={len(old)}|dirty={len(before)}")
