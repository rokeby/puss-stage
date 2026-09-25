import unreal


PATH = "/Game/Wings/Passage02_AnimalsToShrineV2/Materials/Instances/MI_P02_SET01_L_Relief"
instance = unreal.EditorAssetLibrary.load_asset(PATH)
if instance is None:
    raise RuntimeError(f"Missing material instance: {PATH}")

for property_name in (
    "texture_parameter_values",
    "scalar_parameter_values",
    "vector_parameter_values",
):
    try:
        values = list(instance.get_editor_property(property_name))
        unreal.log(f"MI_PROPERTY|name={property_name}|count={len(values)}")
        for value in values:
            unreal.log(f"MI_VALUE|property={property_name}|value={value}")
    except Exception as exc:
        unreal.log_warning(f"MI_PROPERTY_UNAVAILABLE|name={property_name}|error={exc}")

unreal.log("MI_PROPERTY_INSPECTION_SUCCESS")
