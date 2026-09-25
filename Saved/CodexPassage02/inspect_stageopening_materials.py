import unreal


MASTER_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
EDGE_PATH = "/Game/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
INSTANCE_PATH = (
    "/Game/Wings/StageOpeningV2/Materials/Instances/"
    "MI_BambooScaffold_01_L_Relief"
)


def prop(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception as exc:
        return f"<unavailable:{exc}>"


master = unreal.load_asset(MASTER_PATH)
edge = unreal.load_asset(EDGE_PATH)
instance = unreal.load_asset(INSTANCE_PATH)
if master is None or edge is None or instance is None:
    raise RuntimeError("Reusable StageOpeningV2 materials did not load")

unreal.log(
    f"P02_MATERIAL_INSPECT|master={master.get_path_name()}|edge={edge.get_path_name()}"
    f"|instance={instance.get_path_name()}|parent={prop(instance, 'parent')}"
)

for property_name in (
    "texture_parameter_values",
    "scalar_parameter_values",
    "vector_parameter_values",
    "static_parameters",
):
    values = prop(instance, property_name)
    unreal.log(f"P02_MATERIAL_INSPECT|{property_name}={values}")

try:
    texture_names = unreal.MaterialEditingLibrary.get_texture_parameter_names(instance)
except Exception as exc:
    texture_names = [f"<error:{exc}>"]
try:
    scalar_names = unreal.MaterialEditingLibrary.get_scalar_parameter_names(instance)
except Exception as exc:
    scalar_names = [f"<error:{exc}>"]

unreal.log(
    "P02_MATERIAL_INSPECT_SUCCESS|texture_names="
    + ",".join(str(name) for name in texture_names)
    + "|scalar_names="
    + ",".join(str(name) for name in scalar_names)
)
