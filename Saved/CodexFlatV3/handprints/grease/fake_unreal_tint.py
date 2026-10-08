"""Fake `unreal` for the OFFLINE tint harness: fake_unreal.make() (actors, decals, level census) plus a material /
asset layer: assets as objects, content-package dirtiness, create_asset / save_asset, MaterialEditingLibrary,
material statistics that read 0 instructions in the call that built the material (the "a read in the same call
lies" rule) and > 0 in later calls, and a log file the verify stage can scan.

Fault hooks (state keys): fault_create=<asset name>, fault_save=<asset path>, fault_spawn_n=<int>,
fault_dirty_content_on_spawn=<package>, fault_destroy=<label>, ps_zero=True, pie=True, compile_fail=True.
"""
import os
import types

import fake_unreal


class Obj:
    def __init__(self, path, cls_name):
        self.path, self.cls_name, self.props = path, cls_name, {}

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]

    def get_name(self):
        return self.path.rsplit("/", 1)[1]

    def modify(self):
        pass

    def set_editor_property(self, k, v):
        self.props[k] = v

    def get_editor_property(self, k):
        return self.props.get(k)


def make(state):
    u = fake_unreal.make(state)
    state.setdefault("objs", {})
    state.setdefault("dirty_content", set())
    state.setdefault("call", 0)
    state.setdefault("created", [])
    state.setdefault("saved_assets", [])
    proj = state["project"]
    log_dir = proj + "/Saved/Logs"
    os.makedirs(log_dir, exist_ok=True)

    def _log(kind, m):
        u.logs.append((kind, m))
        with open(log_dir + "/PussStage.log", "a", encoding="utf-8") as fh:
            fh.write("[fake][%s] %s\n" % (kind, m))

    u.log = lambda m: _log("log", m)
    u.log_error = lambda m: _log("error", m)
    u.log_warning = lambda m: _log("warning", m)
    u.Paths = types.SimpleNamespace(convert_relative_path_to_full=lambda p: p,
                                    project_dir=lambda: proj + "/", project_log_dir=lambda: log_dir,
                                    project_saved_dir=lambda: proj + "/Saved")

    class Material(Obj):
        def __init__(self, path):
            super().__init__(path, "Material")
            self.exprs, self.inputs, self.built_call = [], {}, state["call"]

    class MaterialInstanceConstant(Obj):
        def __init__(self, path):
            super().__init__(path, "MaterialInstanceConstant")
            self.scalars = {}

    class Texture2D(Obj):
        def __init__(self, path):
            super().__init__(path, "Texture2D")

    u.Material, u.MaterialInstanceConstant, u.Texture2D = Material, MaterialInstanceConstant, Texture2D

    class Expr:
        def __init__(self, kind):
            self.kind, self.props, self.links = kind, {}, {}

        def set_editor_property(self, k, v):
            self.props[k] = v

        def get_editor_property(self, k):
            return self.props.get(k)

        def get_name(self):
            return self.kind

    for n in ("MaterialExpressionCustom", "MaterialExpressionScalarParameter", "MaterialExpressionVectorParameter",
              "MaterialExpressionTextureSampleParameter2D", "MaterialExpressionTextureCoordinate"):
        setattr(u, n, type(n, (), {"__name__": n}))
    u.CustomInput = lambda: types.SimpleNamespace(props={}, set_editor_property=lambda k, v: None)

    class CustomInput:
        def __init__(self):
            self.props = {}

        def set_editor_property(self, k, v):
            self.props[k] = v

    u.CustomInput = CustomInput
    u.CustomMaterialOutputType = types.SimpleNamespace(CMOT_FLOAT1=1, CMOT_FLOAT2=2, CMOT_FLOAT3=3)
    u.MaterialSamplerType = types.SimpleNamespace(SAMPLERTYPE_MASKS="MASKS", SAMPLERTYPE_NORMAL="NORMAL")
    u.BlendMode = types.SimpleNamespace(BLEND_TRANSLUCENT="BLEND_TRANSLUCENT")
    u.MaterialDomain = types.SimpleNamespace(MD_DEFERRED_DECAL="MD_DEFERRED_DECAL", MD_SURFACE="MD_SURFACE")
    u.MaterialProperty = types.SimpleNamespace(**{k: k for k in (
        "MP_BASE_COLOR", "MP_OPACITY", "MP_ROUGHNESS", "MP_NORMAL", "MP_METALLIC", "MP_SPECULAR", "MP_EMISSIVE_COLOR")})

    class LinearColor:
        def __init__(self, r=0.0, g=0.0, b=0.0, a=1.0):
            self.r, self.g, self.b, self.a = float(r), float(g), float(b), float(a)

    u.LinearColor = LinearColor
    u.MaterialFactoryNew = lambda: "MaterialFactoryNew"
    u.MaterialInstanceConstantFactoryNew = lambda: "MICFactoryNew"

    def dirty(path):
        state["dirty_content"].add(path)

    class AssetTools:
        def create_asset(self, name, folder, cls, factory):
            path = folder + "/" + name
            if state.get("fault_create") == name:
                return None
            if path in state["objs"]:
                return None
            obj = cls(path)
            state["objs"][path] = obj
            state["assets"].add(path)
            state["created"].append(path)
            dirty(path)
            return obj

    tools = AssetTools()
    u.AssetToolsHelpers = types.SimpleNamespace(get_asset_tools=lambda: tools)

    def save_asset(path, only_if_is_dirty=True):
        if state.get("fault_save") == path or path not in state["objs"]:
            return False
        state["dirty_content"].discard(path)
        state["saved_assets"].append(path)
        f = proj + "/Content/" + path[len("/Game/"):] + ".uasset"
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "wb") as fh:
            fh.write(b"FAKE-UASSET " + path.encode())
        return True

    u.EditorAssetLibrary = types.SimpleNamespace(does_asset_exist=lambda p: p in state["assets"], save_asset=save_asset)

    def load_asset(p):
        if p in state["objs"]:
            return state["objs"][p]
        return fake_unreal.Asset(p) if p in state["assets"] else None

    u.load_asset = load_asset
    u.SystemLibrary = types.SimpleNamespace(collect_garbage=lambda: None)
    u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        get_dirty_map_packages=lambda: [fake_unreal.Pkg(fake_unreal.WORLD_PATH)] if state.get("dirty") else [],
        get_dirty_content_packages=lambda: [fake_unreal.Pkg(p) for p in sorted(state["dirty_content"])])

    # ---------------------------------------------------------------- MaterialEditingLibrary
    def mel_create(mat, cls, x, y):
        e = Expr(cls.__name__)
        mat.exprs.append(e)
        dirty(mat.path)
        return e

    def mel_connect(a, a_out, b, b_in):
        b.links[b_in] = (a, a_out)
        return True

    def mel_prop(a, a_out, prop):
        for m in state["objs"].values():
            if isinstance(m, Material) and any(e is a for e in m.exprs):
                m.inputs[prop] = a
                return True
        return False

    def params(m, kind):
        while isinstance(m, MaterialInstanceConstant):
            m = m.props.get("parent")
        return [e for e in getattr(m, "exprs", []) if e.kind == kind]

    def stats(m):
        ps = 0 if (state.get("ps_zero") or m.built_call == state["call"]) else 312
        return types.SimpleNamespace(get_editor_property=lambda k: ps)

    def recompile(m):
        if state.get("compile_fail"):
            _log("error", "LogMaterial: Failed to compile Material %s for platform PCD3D_SM6" % m.get_name())
        return []

    def default_scalar(m, name):
        for e in params(m, "MaterialExpressionScalarParameter"):
            if e.props["parameter_name"] == name:
                return e.props["default_value"]
        return 0.0

    def default_vector(m, name):
        for e in params(m, "MaterialExpressionVectorParameter"):
            if e.props["parameter_name"] == name:
                return e.props["default_value"]
        return LinearColor()

    def mi_set_parent(mi, parent):
        mi.props["parent"] = parent
        dirty(mi.path)

    def mi_set_scalar(mi, k, v):
        mi.scalars[k] = float(v)
        dirty(mi.path)
        return True

    def mi_get_scalar(mi, k):
        return mi.scalars[k] if k in mi.scalars else default_scalar(mi, k)

    u.MaterialEditingLibrary = types.SimpleNamespace(
        create_material_expression=mel_create, connect_material_expressions=mel_connect,
        get_material_expression_input_names=lambda e: ["a", "b"], connect_material_property=mel_prop,
        layout_material_expressions=lambda m: None, recompile_material=recompile,
        get_scalar_parameter_names=lambda m: [e.props["parameter_name"] for e in params(m, "MaterialExpressionScalarParameter")],
        get_vector_parameter_names=lambda m: [e.props["parameter_name"] for e in params(m, "MaterialExpressionVectorParameter")],
        get_texture_parameter_names=lambda m: [e.props["parameter_name"] for e in params(m, "MaterialExpressionTextureSampleParameter2D")],
        get_material_default_scalar_parameter_value=default_scalar,
        get_material_default_vector_parameter_value=default_vector,
        get_material_property_input_node=lambda m, p: m.inputs.get(p),
        get_statistics=stats, set_material_instance_parent=mi_set_parent,
        set_material_instance_scalar_parameter_value=mi_set_scalar,
        get_material_instance_scalar_parameter_value=mi_get_scalar,
        get_material_instance_vector_parameter_value=lambda mi, k: default_vector(mi, k),
        update_material_instance=lambda mi: None)

    # ---------------------------------------------------------------- level faults / PIE
    sub = u.get_editor_subsystem(u.EditorActorSubsystem)
    orig_spawn = sub.spawn_actor_from_class
    state["spawn_n"] = 0

    def spawn(cls, loc, rot):
        state["spawn_n"] += 1
        if state.get("fault_spawn_n") == state["spawn_n"]:
            return None
        if state.get("fault_dirty_content_on_spawn") and state["spawn_n"] == 5:
            dirty(state["fault_dirty_content_on_spawn"])
        return orig_spawn(cls, loc, rot)

    sub.spawn_actor_from_class = spawn
    ued = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    ued.get_game_world = lambda: object() if state.get("pie") else None
    return u
