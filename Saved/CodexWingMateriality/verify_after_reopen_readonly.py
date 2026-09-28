"""Read-only after the crash/reopen: editor state, trial MIs intact, per-instance custom data live."""
import importlib.util, os, collections
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
before = wm.dirty()
out = {"dirty": before}
trial = wm.read_json("trial_apply_result.json")["parents"]
out["trial"] = {p.rsplit("/", 1)[-1]: [wm.pkg(unreal.EditorAssetLibrary.load_asset(p).get_editor_property("parent")) == want]
                for p, want in trial.items()}
floats = collections.Counter()
seeds = {}
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    label = actor.get_actor_label()[:10]
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        if "InfinityStage.Managed" not in [str(t) for t in comp.get_editor_property("component_tags")]:
            continue
        n = comp.get_editor_property("num_custom_data_floats")
        floats[(label, n)] += 1
        if n >= 4 and label not in seeds:
            data = list(comp.get_editor_property("per_instance_sm_custom_data"))
            seeds[label] = {"mesh": wm.pkg(comp.get_editor_property("static_mesh")).rsplit("/", 1)[-1],
                            "slots_first_instances": [data[i:i + 4] for i in range(0, min(len(data), 16), 4)]}
out["num_custom_data_floats"] = {f"{k[0]}|{k[1]}": v for k, v in sorted(floats.items())}
out["seed_samples"] = seeds
wm.require(wm.dirty() == before, f"dirty changed {wm.dirty()}")
wm.write_json("verify_after_reopen.json", out)
unreal.log(f"PUSS_WING_REOPEN_VERIFY_SUCCESS|dirty={len(before)}")
