import unreal
unreal.log("MID_API_PROBE|MaterialLibrary=%s|create=%s|MID.create=%s" % (
    hasattr(unreal, "MaterialLibrary"),
    hasattr(getattr(unreal, "MaterialLibrary", object), "create_dynamic_material_instance"),
    hasattr(unreal.MaterialInstanceDynamic, "create")))
