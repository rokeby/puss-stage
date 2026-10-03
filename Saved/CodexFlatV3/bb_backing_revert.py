"""Revert the two billboard parent MIs' BackingColor/PrimerColor from bb_backing_originals.json. Saves only those 2."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
orig = json.load(open(os.path.join(BASE, "bb_backing_originals.json")))
MEL = unreal.MaterialEditingLibrary
for p, params in orig.items():
    mi = unreal.load_asset(p); mi.modify()
    for k, v in params.items():
        MEL.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*v))
    MEL.update_material_instance(mi)
    if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
        raise RuntimeError("BB_REVERT_SAVE_FAIL|" + p)
unreal.log("FLATV3_BB_BACKING_REVERTED saved_count=%d" % len(orig))
