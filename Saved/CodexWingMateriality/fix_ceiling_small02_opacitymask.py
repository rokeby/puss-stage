"""Fix MI_CloudCeilingSmall_02_C_Relief: OpacityMask pointed at its own _N normal map.

The relief master feeds OpacityMask.A to Opacity Mask. A BC5 normal map has no alpha
(reads 1.0), so the panel's painted cut-out was ignored and only the mesh outline
shaped it. Point OpacityMask at the panel's own BaseColor texture, as every other
V2 relief MI does. Saves only this MI package.
Backup: Backups/PreWingMateriality-20260925-193234.
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)

MI = "/Game/Scenes/Wings/Passage05_BirdToMountain/Materials/Instances/MI_CloudCeilingSmall_02_C_Relief"
WRONG = "/Game/Scenes/Wings/Passage05_BirdToMountain/Textures/T_CloudCeilingSmall_02_C_N"
RIGHT = "/Game/Scenes/Wings/Passage05_BirdToMountain/Textures/T_CloudCeilingSmall_02_C"

wm.editor_ready()
before = wm.dirty()
wm.require(before in ([], [MI]), f"Refusing to write with other dirty packages present: {before}")
mi = unreal.EditorAssetLibrary.load_asset(MI)
wm.require(isinstance(mi, unreal.MaterialInstanceConstant), "MI did not load as a MaterialInstanceConstant")
base = wm.pkg(wm.MEL.get_material_instance_texture_parameter_value(mi, "BaseColor"))
wm.require(base == RIGHT, f"BaseColor is {base}, expected {RIGHT}")
current = wm.pkg(wm.MEL.get_material_instance_texture_parameter_value(mi, "OpacityMask"))
if current != RIGHT:
    wm.require(current == WRONG, f"OpacityMask is {current}, expected the known-wrong {WRONG}")
    # The setter's bool is unreliable in 5.8 (returns False after a successful set),
    # so verify the value instead of trusting the return.
    wm.MEL.set_material_instance_texture_parameter_value(mi, "OpacityMask", unreal.EditorAssetLibrary.load_asset(RIGHT))
    wm.require(wm.pkg(wm.MEL.get_material_instance_texture_parameter_value(mi, "OpacityMask")) == RIGHT, "Set did not take")
names = [str(p.get_editor_property("parameter_info").get_editor_property("name"))
         for p in mi.get_editor_property("texture_parameter_values")]
wm.require(names.count("OpacityMask") == 1, f"Duplicate OpacityMask overrides: {names}")
wm.MEL.update_material_instance(mi)
if wm.dirty() == [MI]:
    wm.require(unreal.EditorAssetLibrary.save_asset(MI, only_if_is_dirty=True), "save_asset failed")
after = wm.dirty()
wm.require(after == [], f"Dirty after save: {after}")
readback = wm.pkg(wm.MEL.get_material_instance_texture_parameter_value(unreal.EditorAssetLibrary.load_asset(MI), "OpacityMask"))
wm.require(readback == RIGHT, f"Read-back mismatch: {readback}")
wm.write_json("fix_ceiling_small02_result.json", {"mi": MI, "before": WRONG, "after": readback, "dirty_after": after})
unreal.log(f"PUSS_WING_CEILING_MASK_FIX_SUCCESS|before={WRONG.rsplit('/',1)[-1]}|after={readback.rsplit('/',1)[-1]}|dirty=0")
