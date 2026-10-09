"""Small fake Unreal API for the industrial-master offline harness only."""
from __future__ import annotations

import json
import os
import types


def enum_space(**values):
    return types.SimpleNamespace(**values)


def make(project, faults=None):
    state = {"project": str(project), "faults": dict(faults or {}), "assets": {}, "dirty": set(),
             "saves": [], "logs": [], "delete_calls": 0}
    u = types.ModuleType("unreal")

    class Base:
        def __init__(self, path):
            self.path = path

        def get_path_name(self):
            return self.path + "." + self.path.rsplit("/", 1)[-1]

        def get_name(self):
            return self.path.rsplit("/", 1)[-1]

    class Texture2D(Base):
        pass

    class Expression:
        def __init__(self, material, index):
            self.material, self.props, self.connections = material, {}, {}
            self.name = "%s_%02d" % (self.__class__.__name__, index)

        def set_editor_property(self, key, value):
            if state["faults"].get("parameter_setter_lies") == key:
                return
            self.props[key] = value
            state["dirty"].add(self.material.path)

        def get_editor_property(self, key):
            return self.props[key]

        def get_name(self):
            return self.name

        def get_path_name(self):
            return self.material.get_path_name() + ":" + self.name

    class MaterialExpressionTextureCoordinate(Expression):
        pass

    class MaterialExpressionScalarParameter(Expression):
        pass

    class MaterialExpressionCustom(Expression):
        pass

    class MaterialExpressionTextureSampleParameter2D(Expression):
        pass

    class Material(Base):
        def __init__(self, path):
            super().__init__(path)
            self.props, self.expressions, self.property_inputs = {}, [], {}

        def set_editor_property(self, key, value):
            if state["faults"].get("material_setter_lies") == key:
                return
            self.props[key] = value
            state["dirty"].add(self.path)

        def get_editor_property(self, key):
            return self.props.get(key)

    class CustomInput:
        def __init__(self):
            self.props = {}

        def set_editor_property(self, key, value):
            self.props[key] = value

        def get_editor_property(self, key):
            return self.props[key]

    class MaterialFactoryNew:
        pass

    class Package:
        def __init__(self, path):
            self.path = path

        def get_name(self):
            return self.path

        def get_path_name(self):
            return self.path

    class UnrealEditorSubsystem:
        def get_game_world(self):
            return object() if state["faults"].get("pie") else None

    def content_file(path):
        return os.path.join(state["project"], "Content", *path[len("/Game/"):].split("/")) + ".uasset"

    def load(path):
        return state["assets"].get(str(path).split(".", 1)[0])

    for path in ("/Engine/EngineResources/WhiteSquareTexture", "/Engine/EngineMaterials/FlatNormal",
                 "/Game/Scenes/Wings/PaintedSurface/Textures/T_WingDetail_Grime"):
        state["assets"][path] = Texture2D(path)

    class AssetTools:
        def create_asset(self, name, folder, cls, factory):
            path = folder + "/" + name
            if path in state["assets"]:
                return None
            obj = cls(path)
            state["assets"][path] = obj
            state["dirty"].add(path)
            return obj

    def save_asset(path, only_if_is_dirty=False):
        obj = load(path)
        if obj is None:
            return False
        os.makedirs(os.path.dirname(content_file(path)), exist_ok=True)
        with open(content_file(path), "w", encoding="utf-8") as handle:
            json.dump({"path": path, "expressions": len(getattr(obj, "expressions", []))}, handle)
        state["dirty"].discard(path)
        state["saves"].append(path)
        return True

    class MEL:
        @staticmethod
        def create_material_expression(mat, cls, x, y):
            expression = cls(mat, len(mat.expressions))
            mat.expressions.append(expression)
            state["dirty"].add(mat.path)
            return expression

        @staticmethod
        def get_num_material_expressions(mat):
            return len(mat.expressions)

        @staticmethod
        def connect_material_expressions(source, output_name, target, input_name):
            target.connections[input_name] = (source, output_name)
            return True

        @staticmethod
        def get_material_expression_input_names(target):
            return [item.get_editor_property("input_name") for item in target.props.get("inputs", [])] or ["UVs"]

        @staticmethod
        def connect_material_property(source, output_name, prop):
            source.material.property_inputs[prop] = (source, output_name)
            return True

        @staticmethod
        def get_material_property_input_node(mat, prop):
            value = mat.property_inputs.get(prop)
            return value[0] if value else None

        @staticmethod
        def get_scalar_parameter_names(mat):
            return [e.props.get("parameter_name") for e in mat.expressions
                    if isinstance(e, MaterialExpressionScalarParameter) and e.props.get("parameter_name")]

        @staticmethod
        def get_texture_parameter_names(mat):
            return [e.props.get("parameter_name") for e in mat.expressions
                    if isinstance(e, MaterialExpressionTextureSampleParameter2D) and e.props.get("parameter_name")]

        @staticmethod
        def get_material_default_scalar_parameter_value(mat, name):
            return next(e.props["default_value"] for e in mat.expressions
                        if isinstance(e, MaterialExpressionScalarParameter) and e.props.get("parameter_name") == name)

        @staticmethod
        def get_material_default_texture_parameter_value(mat, name):
            return next(e.props["texture"] for e in mat.expressions
                        if isinstance(e, MaterialExpressionTextureSampleParameter2D)
                        and e.props.get("parameter_name") == name)

        @staticmethod
        def layout_material_expressions(mat):
            return None

        @staticmethod
        def recompile_material(mat):
            return list(state["faults"].get("compile_errors", []))

    u.Material = Material
    u.Texture2D = Texture2D
    u.MaterialFactoryNew = MaterialFactoryNew
    u.MaterialExpressionTextureCoordinate = MaterialExpressionTextureCoordinate
    u.MaterialExpressionScalarParameter = MaterialExpressionScalarParameter
    u.MaterialExpressionCustom = MaterialExpressionCustom
    u.MaterialExpressionTextureSampleParameter2D = MaterialExpressionTextureSampleParameter2D
    u.CustomInput = CustomInput
    u.UnrealEditorSubsystem = UnrealEditorSubsystem
    u.get_editor_subsystem = lambda cls: cls()
    u.load_asset = load
    u.AssetToolsHelpers = enum_space(get_asset_tools=lambda: AssetTools())
    u.EditorAssetLibrary = enum_space(does_asset_exist=lambda path: load(path) is not None,
                                      load_asset=load, save_asset=save_asset)
    u.EditorLoadingAndSavingUtils = enum_space(
        get_dirty_content_packages=lambda: [Package(path) for path in sorted(state["dirty"])],
        get_dirty_map_packages=lambda: [Package("/Game/Test/DirtyMap")] if state["faults"].get("dirty_map") else [])
    u.MaterialEditingLibrary = MEL
    u.BlendMode = enum_space(BLEND_OPAQUE="BLEND_OPAQUE")
    u.MaterialShadingModel = enum_space(MSM_DEFAULT_LIT="MSM_DEFAULT_LIT")
    u.CustomMaterialOutputType = enum_space(CMOT_FLOAT2="CMOT_FLOAT2")
    u.SamplerSourceMode = enum_space(SSM_WRAP_WORLD_GROUP_SETTINGS="SSM_WRAP_WORLD_GROUP_SETTINGS")
    u.MaterialSamplerType = enum_space(SAMPLERTYPE_COLOR="SAMPLERTYPE_COLOR",
                                       SAMPLERTYPE_NORMAL="SAMPLERTYPE_NORMAL",
                                       SAMPLERTYPE_LINEAR_GRAYSCALE="SAMPLERTYPE_LINEAR_GRAYSCALE")
    u.MaterialProperty = enum_space(MP_BASE_COLOR="MP_BASE_COLOR", MP_NORMAL="MP_NORMAL",
                                    MP_ROUGHNESS="MP_ROUGHNESS", MP_AMBIENT_OCCLUSION="MP_AMBIENT_OCCLUSION")
    u.Paths = enum_space(project_saved_dir=lambda: os.path.join(state["project"], "Saved") + os.sep,
                         project_content_dir=lambda: os.path.join(state["project"], "Content") + os.sep,
                         project_dir=lambda: state["project"] + os.sep,
                         convert_relative_path_to_full=lambda path: path)
    u.log = lambda message: state["logs"].append(("log", message))
    u.log_error = lambda message: state["logs"].append(("error", message))
    u._state = state
    u._content_file = content_file
    return u
