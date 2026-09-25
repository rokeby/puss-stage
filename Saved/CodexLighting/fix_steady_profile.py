import unreal
mel = unreal.MaterialEditingLibrary
mi = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Lighting/MI_LF_Flicker_Steady")
before = mel.get_material_instance_scalar_parameter_value(mi, "Depth")
mel.set_material_instance_scalar_parameter_value(mi, "Depth", 0.0); mel.update_material_instance(mi)
saved = unreal.EditorAssetLibrary.save_asset("/Game/InfinityStage/Lighting/MI_LF_Flicker_Steady", only_if_is_dirty=False)
unreal.log(f"STEADY_PROFILE_FIXED|depth_before={before}|depth_after={mel.get_material_instance_scalar_parameter_value(mi, 'Depth')}|saved={saved}")
