"""Undo trial_apply.py: restore each trial MI's parent and parameter overrides from
trial_rollback.json, then save only those packages."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL

wm.editor_ready()
before = wm.dirty()  # other streams may hold unsaved level work; add nothing to it
snap = wm.read_json("trial_rollback.json")
for path, state in snap.items():
    mi = unreal.EditorAssetLibrary.load_asset(path)
    MEL.clear_all_material_instance_parameters(mi)
    MEL.set_material_instance_parent(mi, unreal.EditorAssetLibrary.load_asset(state["parent"]))
    for name, value in state["textures"]:
        MEL.set_material_instance_texture_parameter_value(mi, name, unreal.EditorAssetLibrary.load_asset(value))
    for name, value in state["scalars"]:
        MEL.set_material_instance_scalar_parameter_value(mi, name, value)
    for name, value in state["vectors"]:
        MEL.set_material_instance_vector_parameter_value(mi, name, unreal.LinearColor(*value))
    MEL.update_material_instance(mi)
    wm.require(wm.pkg(mi.get_editor_property("parent")) == state["parent"], f"{path} parent not restored")
dirty = wm.dirty()
wm.require(set(dirty) <= set(snap) | set(before), f"Unexpected dirty packages: {dirty}")
for p in set(dirty) - set(before):
    wm.require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True), f"save failed {p}")
wm.require(set(wm.dirty()) <= set(before), f"Dirty after save: {wm.dirty()}")
unreal.log(f"PUSS_WING_TRIAL_REVERT_SUCCESS|mis={len(snap)}|dirty=0")
