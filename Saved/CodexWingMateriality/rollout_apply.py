"""Execute rollout_plan.json for chosen passages. Reparents MIs only; saves only MI packages.

rollout_request.json:
  {"passages": ["P01", "P02", "P06"], "families": ["V2", "GroupA", "GroupB"], "dry_run": true}

A mesh used in several passages shares its MIs, so choosing P01 also changes that
mesh wherever else it appears; those passages are listed as collateral in the result.
Before any write, each touched MI's exact prior state goes to a new
rollout_rollback_<stamp>.json, which trial_revert-style restore can replay.
Do not run for real until Gary has accepted the two-panel trial.
"""
import datetime, importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL


def snapshot(mi):
    def infos(prop):
        out = []
        for p in mi.get_editor_property(prop):
            v = p.get_editor_property("parameter_value")
            if hasattr(v, "get_path_name"):
                v = wm.pkg(v)
            elif isinstance(v, unreal.LinearColor):
                v = [v.r, v.g, v.b, v.a]
            out.append([str(p.get_editor_property("parameter_info").get_editor_property("name")), v])
        return out
    return {"parent": wm.pkg(mi.get_editor_property("parent")), "scalars": infos("scalar_parameter_values"),
            "vectors": infos("vector_parameter_values"), "textures": infos("texture_parameter_values")}


def apply_change(ch):
    mi = unreal.EditorAssetLibrary.load_asset(ch["mi"])
    wm.require(isinstance(mi, unreal.MaterialInstanceConstant), f"{ch['mi']} is not an MIC")
    if ch.get("clear"):
        MEL.clear_all_material_instance_parameters(mi)
    MEL.set_material_instance_parent(mi, unreal.EditorAssetLibrary.load_asset(ch["parent"]))
    for name, path in ch.get("textures", {}).items():
        MEL.set_material_instance_texture_parameter_value(mi, name, unreal.EditorAssetLibrary.load_asset(path))
        got = wm.pkg(MEL.get_material_instance_texture_parameter_value(mi, name))
        wm.require(got == path, f"{ch['mi']}.{name} = {got}, wanted {path}")
    for name, value in ch.get("switches", {}).items():
        MEL.set_material_instance_static_switch_parameter_value(mi, name, value)
        wm.require(MEL.get_material_instance_static_switch_parameter_value(mi, name) == value, f"{ch['mi']}.{name}")
    for name, value in ch.get("scalars", {}).items():
        MEL.set_material_instance_scalar_parameter_value(mi, name, float(value))
    MEL.update_material_instance(mi)
    wm.require(wm.pkg(mi.get_editor_property("parent")) == ch["parent"], f"{ch['mi']} parent did not take")


wm.editor_ready()
req = wm.read_json("rollout_request.json")
before = wm.dirty()
if not req.get("dry_run", True):
    # Real runs need a clean editor: another stream's unsaved level work must never ride along.
    wm.require(before == [], f"Refusing to write with dirty packages present: {before}")
plan = wm.read_json("rollout_plan.json")["plan"]
want_p, want_f = set(req["passages"]), set(req["families"])
chosen = [it for it in plan if it["family"] in want_f and want_p & set(it["passages"])]
collateral = sorted({p for it in chosen for p in it["passages"]} - want_p)
changes = [ch for it in chosen for ch in it["changes"]]
summary = {"passages": sorted(want_p), "families": sorted(want_f), "meshes": len(chosen),
           "mi_changes": len(changes), "collateral_passages": collateral, "dry_run": bool(req.get("dry_run", True))}
if summary["dry_run"]:
    wm.require(wm.dirty() == before, f"dry run changed the dirty set: {wm.dirty()}")
    wm.write_json("rollout_apply_result.json", {**summary, "would_change": [c["mi"] for c in changes]})
    unreal.log(f"PUSS_WING_ROLLOUT_DRYRUN_SUCCESS|meshes={len(chosen)}|mis={len(changes)}|collateral={collateral}")
else:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    wm.write_json(f"rollout_rollback_{stamp}.json",
                  {c["mi"]: snapshot(unreal.EditorAssetLibrary.load_asset(c["mi"])) for c in changes})
    for ch in changes:
        apply_change(ch)
    dirty = wm.dirty()
    touched = {c["mi"] for c in changes}
    wm.require(set(dirty) <= touched, f"Unexpected dirty packages: {sorted(set(dirty) - touched)}")
    for p in dirty:
        wm.require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True), f"save failed {p}")
    wm.require(wm.dirty() == [], f"Dirty after save: {wm.dirty()}")
    wm.write_json("rollout_apply_result.json", {**summary, "rollback": f"rollout_rollback_{stamp}.json"})
    unreal.log(f"PUSS_WING_ROLLOUT_APPLY_SUCCESS|meshes={len(chosen)}|mis={len(changes)}|dirty=0")
