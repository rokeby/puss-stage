"""Offline harness for velvet_v2_build.py and velvet_v2_bench.py (no Unreal, no MCP).

Runs the builder against a fake `unreal` module (fake MaterialEditingLibrary, asset registry, dirty packages) and checks:
  * the graph against an INDEPENDENT expectation written here (node descriptors are derived from the fake graph,
    not from the builder's own keys): every node, every connection, every parameter and default, flags, the MI;
  * refusals: target exists, PIE, dirty start, wrong texture type;
  * read-back gates: dropped/misrouted/extra edges, wrong output pin, missing terminal, ignored defaults,
    ignored shading model, MI setters that lie (False after success = must PASS) or silently fail (must FAIL),
    recompile errors, foreign dirty package, failed save;
  * static scans: no delete/destroy in the builder, no ClearCoat material property, no save beyond save_asset,
    no unreal at module level, HLSL inputs referenced, EDGES invariants;
  * the bench variants file and its capture plan.
Every gate is paired with a failing control that must be caught. Exit code 0 only if all pass.
Run: python Saved/CodexConductor/test_velvet_v2_build.py
"""
import ast
import copy
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDER = os.path.join(HERE, "velvet_v2_build.py")
BENCH = os.path.join(HERE, "velvet_v2_bench.py")
VARIANTS = os.path.join(HERE, "velvet_v2_bench_variants.json")

M_V2 = "/Game/Scenes/Curtain/Chaos/Materials/M_CurtainVelvet_v2"
MI_V2 = "/Game/Scenes/Curtain/Chaos/Materials/MI_CurtainVelvet_v2_DeepRed"
DROP_MI = "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"
PILE_N = "/Game/Scenes/Curtain/Chaos/Textures/T_CurtainVelourScan_N"
CRUSH_N = "/Game/Scenes/Curtain/Chaos/Textures/T_CurtainVelvetCrush_N"
DROP_VALUES = {"PatternWidthM": 37.629, "DropM": 10.0}   # measured 30 Sep, Saved/CodexSoftGoods/material_bench_params.json

RESULTS = []
TMP_ROOTS = set()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -- {detail}"))


# ============================================================================ fake unreal
class FakeEnumValue:
    def __init__(self, enum, name, idx):
        self.enum, self.name, self.idx = enum, name, idx

    def __str__(self):
        return f"<{self.enum}.{self.name}: {self.idx}>"

    __repr__ = __str__

    def __eq__(self, other):
        return isinstance(other, FakeEnumValue) and (self.enum, self.name) == (other.enum, other.name)

    def __hash__(self):
        return hash((self.enum, self.name))


def make_enum(enum, names):
    return types.SimpleNamespace(**{n: FakeEnumValue(enum, n, i) for i, n in enumerate(names)})


ATTR_PINS = ["BaseColor", "Metallic", "Specular", "Roughness", "Anisotropy", "EmissiveColor", "Opacity", "OpacityMask",
             "Normal", "Tangent", "WorldPositionOffset", "SubsurfaceColor", "ClearCoat", "ClearCoatRoughness",
             "AmbientOcclusion", "Refraction"] + [f"CustomizedUV{i}" for i in range(8)] + \
            ["PixelDepthOffset", "ShadingModel", "Displacement"]   # MaterialExpressionMakeMaterialAttributes.h:20-77
PINS = {
    "MaterialExpressionScalarParameter": [], "MaterialExpressionVectorParameter": [],
    "MaterialExpressionTextureCoordinate": [],
    "MaterialExpressionAppendVector": ["A", "B"], "MaterialExpressionMultiply": ["A", "B"],
    "MaterialExpressionDivide": ["A", "B"],
    "MaterialExpressionTextureSampleParameter2D": ["UVs", "Tex", "Apply View MipBias"],
    "MaterialExpressionFresnel": ["ExponentIn", "BaseReflectFractionIn", "Normal"],   # MaterialExpressionFresnel.h:26-44
    "MaterialExpressionMakeMaterialAttributes": ATTR_PINS,
}
OUTS = {
    "MaterialExpressionTextureSampleParameter2D": ["RGB", "R", "G", "B", "A", "RGBA"],
    "MaterialExpressionVectorParameter": ["", "R", "G", "B", "A"],
}


class FakeObject:
    _n = 0

    def __init__(self, cls_name, path=None):
        FakeObject._n += 1
        self._cls = cls_name
        self._name = f"{cls_name}_{FakeObject._n}"
        self._path = path
        self._props = {}

    def get_name(self):
        return self._name

    def get_path_name(self):
        return f"{self._path}.{self._path.rsplit('/', 1)[-1]}" if self._path else self._name

    def get_class(self):
        return types.SimpleNamespace(get_name=lambda: self._cls)

    def modify(self):
        return True

    def set_editor_property(self, key, value):
        self._props[key] = value

    def get_editor_property(self, key):
        return self._props[key]


class Fake:
    """Holds the whole fake editor state for one run, plus the injected faults."""

    def __init__(self, faults=(), tmp=None):
        self.faults = set(faults)
        self.tmp = tmp
        self.assets = {}
        self.dirty_content = set()
        self.dirty_maps = {"/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"}  # benches dirty the map
        self.saved = []
        self.created = []
        self.logs = []
        self.calls = []
        self.unreal = self._build_module()
        tex_n = self.unreal.TextureCompressionSettings
        pile = self.unreal.Texture2D(PILE_N)
        pile._props.update(compression_settings=tex_n.TC_NORMALMAP, srgb=False)
        crush = self.unreal.Texture2D(CRUSH_N)
        crush._props.update(compression_settings=tex_n.TC_DEFAULT if "bad_texture" in self.faults else tex_n.TC_NORMALMAP,
                            srgb=False)
        drop = self.unreal.MaterialInstanceConstant(DROP_MI)
        drop.overrides_s = dict(DROP_VALUES)
        for a in (pile, crush, drop):
            self.assets[a._path] = a
        if "exists" in self.faults:
            self.assets[M_V2] = self.unreal.Material(M_V2)
        if "dirty_start" in self.faults:
            self.dirty_content.add("/Game/Somewhere/Else")

    # ------------------------------------------------------------------ module
    def _build_module(self):
        fake = self
        u = types.ModuleType("unreal")
        u.MaterialSamplerType = make_enum("MaterialSamplerType", [
            "SAMPLERTYPE_COLOR", "SAMPLERTYPE_GRAYSCALE", "SAMPLERTYPE_ALPHA", "SAMPLERTYPE_NORMAL", "SAMPLERTYPE_MASKS",
            "SAMPLERTYPE_DISTANCE_FIELD_FONT", "SAMPLERTYPE_LINEAR_COLOR", "SAMPLERTYPE_LINEAR_GRAYSCALE"])
        u.TextureCompressionSettings = make_enum("TextureCompressionSettings",
                                                 ["TC_DEFAULT", "TC_NORMALMAP", "TC_MASKS", "TC_GRAYSCALE"])
        u.MaterialShadingModel = make_enum("MaterialShadingModel", ["MSM_UNLIT", "MSM_DEFAULT_LIT", "MSM_CLOTH"])
        u.MaterialProperty = make_enum("MaterialProperty", ["MP_BASE_COLOR", "MP_NORMAL", "MP_MATERIAL_ATTRIBUTES"])
        u.CustomMaterialOutputType = make_enum("CustomMaterialOutputType",
                                               ["CMOT_FLOAT1", "CMOT_FLOAT2", "CMOT_FLOAT3", "CMOT_FLOAT4"])

        class LinearColor:
            def __init__(self, r=0.0, g=0.0, b=0.0, a=1.0):
                self.r, self.g, self.b, self.a = float(r), float(g), float(b), float(a)

            def __repr__(self):
                return f"LinearColor({self.r},{self.g},{self.b},{self.a})"
        u.LinearColor = LinearColor

        class Texture2D(FakeObject):
            def __init__(self, path):
                super().__init__("Texture2D", path)
        u.Texture2D = Texture2D

        class Material(FakeObject):
            def __init__(self, path):
                super().__init__("Material", path)
                self.expressions = []
                self.terminals = {}
                self._props.update(shading_model=u.MaterialShadingModel.MSM_DEFAULT_LIT, two_sided=False,
                                   use_material_attributes=False, used_with_geometry_cache=False,
                                   used_with_skeletal_mesh=False, used_with_clothing=False)

            def set_editor_property(self, key, value):
                if key == "shading_model" and "shading_ignored" in fake.faults:
                    return
                super().set_editor_property(key, value)
                fake.dirty_content.add(self._path)
        u.Material = Material

        class MaterialInstanceConstant(FakeObject):
            def __init__(self, path):
                super().__init__("MaterialInstanceConstant", path)
                self._props["parent"] = None
                self.overrides_s, self.overrides_v, self.overrides_t = {}, {}, {}
        u.MaterialInstanceConstant = MaterialInstanceConstant

        class Expression(FakeObject):
            def __init__(self, cls_name, material):
                super().__init__(cls_name)
                self.material = material
                self.inputs = {}   # pin -> (source, output)

            def pin_names(self):
                if self._cls == "MaterialExpressionCustom":
                    return [str(c.get_editor_property("input_name")) for c in self._props.get("inputs", [])]
                return list(PINS[self._cls])

            def out_names(self):
                return OUTS.get(self._cls, [""])

            def set_editor_property(self, key, value):
                if key == "default_value" and "default_ignored" in fake.faults \
                        and self._props.get("parameter_name") == "CrushScale":
                    return
                super().set_editor_property(key, value)

        def expr_class(name):
            cls = type(name, (Expression,), {})
            cls._fake_name = name
            return cls
        for name in list(PINS) + ["MaterialExpressionCustom"]:
            setattr(u, name, expr_class(name))

        class CustomInput(FakeObject):
            def __init__(self):
                super().__init__("CustomInput")
        u.CustomInput = CustomInput
        u.MaterialFactoryNew = lambda: "MaterialFactoryNew"
        u.MaterialInstanceConstantFactoryNew = lambda: "MaterialInstanceConstantFactoryNew"

        class AssetTools:
            def create_asset(self, name, folder, cls, factory):
                path = f"{folder}/{name}"
                fake.calls.append(("create_asset", path))
                obj = cls(path)
                fake.assets[path] = obj
                fake.created.append(path)
                fake.dirty_content.add(path)
                return obj
        u.AssetToolsHelpers = types.SimpleNamespace(get_asset_tools=lambda: AssetTools())

        def save_asset(path, only_if_is_dirty=True):
            fake.calls.append(("save_asset", path))
            if "save_false" in fake.faults:
                return False
            fake.saved.append(path)
            fake.dirty_content.discard(path)
            return True
        u.EditorAssetLibrary = types.SimpleNamespace(
            does_asset_exist=lambda p: p in fake.assets,
            load_asset=lambda p: fake.assets.get(p),
            save_asset=save_asset)

        class Pkg:
            def __init__(self, p):
                self.p = p

            def get_path_name(self):
                return self.p
        u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
            get_dirty_content_packages=lambda: [Pkg(p) for p in sorted(fake.dirty_content)],
            get_dirty_map_packages=lambda: [Pkg(p) for p in sorted(fake.dirty_maps)])
        u.Paths = types.SimpleNamespace(project_saved_dir=lambda: fake.tmp, convert_relative_path_to_full=lambda p: p)
        u.UnrealEditorSubsystem = "UnrealEditorSubsystem"
        u.get_editor_subsystem = lambda cls: types.SimpleNamespace(
            get_game_world=lambda: object() if "pie" in fake.faults else None)
        u.log = lambda m: fake.logs.append(("log", m))
        u.log_error = lambda m: fake.logs.append(("error", m))
        u.log_warning = lambda m: fake.logs.append(("warning", m))
        u.MaterialEditingLibrary = self._build_mel(u)
        return u

    def _build_mel(self, u):
        fake = self

        def create_material_expression(material, cls, x=0, y=0):
            n = cls(cls._fake_name, material)
            material.expressions.append(n)
            fake.dirty_content.add(material._path)
            if "foreign_dirty" in fake.faults:
                fake.dirty_content.add(DROP_MI)
            return n

        def connect_material_expressions(a, a_out, b, b_in):
            fake.calls.append(("connect", a.get_name(), a_out, b.get_name(), b_in))
            names = b.pin_names()
            pin = b_in if b_in else (names[0] if names else None)
            if pin not in names or (a_out and a_out not in a.out_names()):
                return False
            if "drop_edge" in fake.faults and b._props.get("description") == "VV2_Base" and pin == "Fres":
                return True   # claims success, stores nothing
            if "wrong_pin" in fake.faults and pin == "Specular":
                pin = "Metallic"
            if "wrong_output" in fake.faults and a_out == "RGB":
                a_out = "R"
            b.inputs[pin] = (a, a_out)
            if "extra_edge" in fake.faults and pin == "Normal" and b._cls == "MaterialExpressionMakeMaterialAttributes":
                b.inputs["AmbientOcclusion"] = (a, a_out)
            return True

        def connect_material_property(a, a_out, prop):
            fake.calls.append(("connect_property", str(prop)))
            if "terminal_missing" in fake.faults:
                return True
            a.material.terminals[str(prop)] = (a, a_out)
            return True

        def get_material_expression_input_names(e):
            return list(e.pin_names())

        def get_inputs_for_material_expression(material, e):
            ups = [e.inputs.get(p, (None, ""))[0] for p in e.pin_names()]
            if "compact_inputs" in fake.faults:
                return [x for x in ups if x is not None]
            return ups

        def get_input_node_output_name_for_material_expression(e, src):
            for p in e.pin_names():
                if p in e.inputs and e.inputs[p][0] is src:
                    out = e.inputs[p][1]
                    return (True, out) if "tuple_out" in fake.faults else out
            return (False, "") if "tuple_out" in fake.faults else ""

        def get_material_property_input_node(material, prop):
            row = material.terminals.get(str(prop))
            return row[0] if row else None

        def params_of(material, kind):
            if isinstance(material, u.MaterialInstanceConstant):
                material = material.get_editor_property("parent")
            out = []
            for e in material.expressions:
                if e._cls == {"s": "MaterialExpressionScalarParameter", "v": "MaterialExpressionVectorParameter",
                              "t": "MaterialExpressionTextureSampleParameter2D"}[kind]:
                    out.append(e)
            return out

        def default_of(material, kind, name):
            for e in params_of(material, kind):
                if str(e._props.get("parameter_name")) == str(name):
                    return e._props.get("texture" if kind == "t" else "default_value", 0.0)
            raise KeyError(name)

        def mi_get(mi, kind, name):
            table = {"s": mi.overrides_s, "v": mi.overrides_v, "t": mi.overrides_t}[kind]
            if str(name) in table:
                return table[str(name)]
            return default_of(mi.get_editor_property("parent"), kind, name)

        def set_scalar(mi, name, value):
            fake.dirty_content.add(mi._path)
            if "setter_silent" in fake.faults:
                return True
            mi.overrides_s[str(name)] = float(value)
            return False if "setter_lie_false" in fake.faults else True

        def set_vector(mi, name, value):
            fake.dirty_content.add(mi._path)
            if "vector_off" in fake.faults:
                value = u.LinearColor(value.r + 0.01, value.g, value.b, value.a)
            mi.overrides_v[str(name)] = value
            return False if "setter_lie_false" in fake.faults else True

        def set_parent(mi, parent):
            mi._props["parent"] = parent
            fake.dirty_content.add(mi._path)

        def recompile(material):
            fake.calls.append(("recompile", material._path))
            return ["[SM6] error X3004: undeclared identifier 'Fres'"] if "recompile_errors" in fake.faults else []

        def get_statistics(material):
            n = 0 if "stats_zero" in fake.faults else 412
            return types.SimpleNamespace(get_editor_property=lambda k: n)

        return types.SimpleNamespace(
            create_material_expression=create_material_expression,
            connect_material_expressions=connect_material_expressions,
            connect_material_property=connect_material_property,
            get_material_expression_input_names=get_material_expression_input_names,
            get_inputs_for_material_expression=get_inputs_for_material_expression,
            get_input_node_output_name_for_material_expression=get_input_node_output_name_for_material_expression,
            get_material_property_input_node=get_material_property_input_node,
            get_num_material_expressions=lambda m: len(m.expressions),
            get_scalar_parameter_names=lambda m: [e._props["parameter_name"] for e in params_of(m, "s")],
            get_vector_parameter_names=lambda m: [e._props["parameter_name"] for e in params_of(m, "v")],
            get_texture_parameter_names=lambda m: [e._props["parameter_name"] for e in params_of(m, "t")],
            get_material_default_scalar_parameter_value=lambda m, n: float(default_of(m, "s", n)),
            get_material_default_vector_parameter_value=lambda m, n: default_of(m, "v", n),
            get_material_default_texture_parameter_value=lambda m, n: default_of(m, "t", n),
            get_material_instance_scalar_parameter_value=lambda mi, n: mi.overrides_s[str(n)] if mi._path == DROP_MI
            else float(mi_get(mi, "s", n)),
            get_material_instance_vector_parameter_value=lambda mi, n: mi_get(mi, "v", n),
            get_material_instance_texture_parameter_value=lambda mi, n: mi_get(mi, "t", n),
            set_material_instance_parent=set_parent,
            set_material_instance_scalar_parameter_value=set_scalar,
            set_material_instance_vector_parameter_value=set_vector,
            update_material_instance=lambda mi: None,
            is_material_instance_parameter_overridden=lambda mi, n: str(n) in mi.overrides_s or str(n) in mi.overrides_v
            or str(n) in mi.overrides_t,
            recompile_material=recompile,
            get_statistics=get_statistics,
        )


def load_builder():
    os.environ["VV2_NO_AUTORUN"] = "1"
    spec = importlib.util.spec_from_file_location("velvet_v2_build_under_test", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_builder(faults=(), mode="APPLY", fake=None):
    tmp = fake.tmp if fake else tempfile.mkdtemp(prefix="vv2_")
    TMP_ROOTS.add(tmp)
    os.makedirs(os.path.join(tmp, "CodexConductor"), exist_ok=True)
    with open(os.path.join(tmp, "CodexConductor", "velvet_v2_build_mode.json"), "w", encoding="utf-8") as h:
        json.dump({"mode": mode}, h)
    if fake is None:
        fake = Fake(faults, tmp)
    else:
        fake.faults = set(faults)
    sys.modules["unreal"] = fake.unreal
    try:
        result = load_builder().main()
    finally:
        sys.modules.pop("unreal", None)
    reports = sorted(f for f in os.listdir(os.path.join(tmp, "CodexConductor")) if f.startswith("velvet_v2_build_VV2-"))
    with open(os.path.join(tmp, "CodexConductor", reports[-1]), encoding="utf-8") as h:
        report = json.load(h)
    return result, report, fake


# ============================================================================ independent expectation
EXPECT_SCALARS = {"SheenAmount": 1.0, "RimLift": 0.35, "NapExponent": 3.0, "FoldDarken": 0.55, "Roughness": 0.88,
                  "Specular": 0.3, "PileNormalStrength": 0.6, "PileScale": 0.5, "CrushAmount": 0.35, "CrushScale": 0.6,
                  "CrushNormalStrength": 0.25, "PatternWidthM": 37.629, "DropM": 10.0}
EXPECT_VECTORS = {"BaseColour": (0.07, 0.004, 0.012), "SheenColour": (0.32, 0.03, 0.07)}
EXPECT_TEXTURES = {"PileNormal": PILE_N, "CrushNormal": CRUSH_N}
REQUIRED_BY_BRIEF = ["BaseColour", "SheenColour", "SheenAmount", "PileNormalStrength", "PileScale", "CrushAmount",
                     "CrushScale", "Roughness"]
EXPECT_CLASS_COUNTS = {"MaterialExpressionScalarParameter": 13, "MaterialExpressionVectorParameter": 2,
                       "MaterialExpressionTextureCoordinate": 1, "MaterialExpressionAppendVector": 1,
                       "MaterialExpressionMultiply": 1, "MaterialExpressionDivide": 2,
                       "MaterialExpressionTextureSampleParameter2D": 2, "MaterialExpressionFresnel": 1,
                       "MaterialExpressionCustom": 6, "MaterialExpressionMakeMaterialAttributes": 1}
UVM = "Multiply(UV0,AppendVector(PatternWidthM,DropM))"
PUV = f"Divide({UVM},PileScale)"
CUV = f"Divide({UVM},CrushScale)"
EXPECT_EDGES = {
    ("UV0", "", "Multiply", "A"), ("PatternWidthM", "", "AppendVector", "A"), ("DropM", "", "AppendVector", "B"),
    ("AppendVector(PatternWidthM,DropM)", "", "Multiply", "B"),
    (UVM, "", "Divide@PileScale", "A"), ("PileScale", "", "Divide@PileScale", "B"),
    (UVM, "", "Divide@CrushScale", "A"), ("CrushScale", "", "Divide@CrushScale", "B"),
    (PUV, "", "PileNormal", "UVs"), (CUV, "", "CrushNormal", "UVs"), (CUV, "", "VV2_Crush", "P"),
    ("NapExponent", "", "Fresnel", "ExponentIn"),
    ("BaseColour", "", "VV2_Base", "Base"), ("SheenColour", "", "VV2_Base", "Sheen"),
    ("VV2_Crush", "", "VV2_Base", "Crush"), ("CrushAmount", "", "VV2_Base", "CrushAmt"),
    ("Fresnel", "", "VV2_Base", "Fres"), ("FoldDarken", "", "VV2_Base", "FoldDarken"),
    ("RimLift", "", "VV2_Base", "RimLift"),
    ("SheenColour", "", "VV2_Fuzz", "Sheen"), ("VV2_Crush", "", "VV2_Fuzz", "Crush"),
    ("CrushAmount", "", "VV2_Fuzz", "CrushAmt"),
    ("SheenAmount", "", "VV2_Cloth", "SheenAmt"), ("VV2_Crush", "", "VV2_Cloth", "Crush"),
    ("CrushAmount", "", "VV2_Cloth", "CrushAmt"),
    ("Roughness", "", "VV2_Rough", "Rough"), ("VV2_Crush", "", "VV2_Rough", "Crush"),
    ("CrushAmount", "", "VV2_Rough", "CrushAmt"),
    ("PileNormal", "RGB", "VV2_Normal", "PileN"), ("PileNormalStrength", "", "VV2_Normal", "PileStr"),
    ("CrushNormal", "RGB", "VV2_Normal", "CrushN"), ("CrushNormalStrength", "", "VV2_Normal", "CrushStr"),
    ("VV2_Base", "", "Attrs", "BaseColor"), ("VV2_Fuzz", "", "Attrs", "SubsurfaceColor"),
    ("VV2_Cloth", "", "Attrs", "ClearCoat"), ("VV2_Rough", "", "Attrs", "Roughness"),
    ("Specular", "", "Attrs", "Specular"), ("VV2_Normal", "", "Attrs", "Normal"),
}


def describe(e, as_target=False):
    """A descriptor derived from the fake graph itself (parameter / description / structure), not the builder's keys."""
    c = e._cls
    if c in ("MaterialExpressionScalarParameter", "MaterialExpressionVectorParameter",
             "MaterialExpressionTextureSampleParameter2D"):
        return str(e._props["parameter_name"])
    if c == "MaterialExpressionCustom":
        return str(e._props["description"])
    if c == "MaterialExpressionTextureCoordinate":
        return "UV0"
    if c == "MaterialExpressionFresnel":
        return "Fresnel"
    if c == "MaterialExpressionMakeMaterialAttributes":
        return "Attrs"
    short = c.replace("MaterialExpression", "")
    if as_target:
        if short == "Divide":
            b = e.inputs.get("B")
            return f"Divide@{describe(b[0]) if b else '?'}"
        return short
    a, b = e.inputs.get("A"), e.inputs.get("B")
    return f"{short}({describe(a[0]) if a else '?'},{describe(b[0]) if b else '?'})"


def graph_of(material):
    edges = set()
    for e in material.expressions:
        for pin, (src, out) in e.inputs.items():
            edges.add((describe(src), out, describe(e, as_target=True), pin))
    return edges


def compare_graph(material, expected_edges):
    problems = []
    counts = {}
    for e in material.expressions:
        counts[e._cls] = counts.get(e._cls, 0) + 1
    if counts != EXPECT_CLASS_COUNTS:
        problems.append(f"node counts {counts}")
    got = graph_of(material)
    if got != expected_edges:
        problems.append(f"missing={sorted(expected_edges - got)} extra={sorted(got - expected_edges)}")
    term = material.terminals.get(str(FakeEnumValue("MaterialProperty", "MP_MATERIAL_ATTRIBUTES", 2)))
    if term is None or describe(term[0]) != "Attrs":
        problems.append("terminal not Attrs")
    sc = {str(e._props["parameter_name"]): float(e._props["default_value"]) for e in material.expressions
          if e._cls == "MaterialExpressionScalarParameter"}
    if set(sc) != set(EXPECT_SCALARS) or any(abs(sc[k] - v) > 1e-6 for k, v in EXPECT_SCALARS.items()):
        problems.append(f"scalars {sc}")
    vc = {str(e._props["parameter_name"]): e._props["default_value"] for e in material.expressions
          if e._cls == "MaterialExpressionVectorParameter"}
    if set(vc) != set(EXPECT_VECTORS) or any(
            any(abs(a - b) > 1e-6 for a, b in zip((vc[k].r, vc[k].g, vc[k].b), v)) for k, v in EXPECT_VECTORS.items()):
        problems.append(f"vectors {vc}")
    tx = {str(e._props["parameter_name"]): (e._props["texture"]._path, str(e._props["sampler_type"]))
          for e in material.expressions if e._cls == "MaterialExpressionTextureSampleParameter2D"}
    if tx != {k: (v, "<MaterialSamplerType.SAMPLERTYPE_NORMAL: 3>") for k, v in EXPECT_TEXTURES.items()}:
        problems.append(f"textures {tx}")
    customs = {str(e._props["description"]): [str(c.get_editor_property("input_name")) for c in e._props["inputs"]]
               for e in material.expressions if e._cls == "MaterialExpressionCustom"}
    for desc, ins in customs.items():
        wired = {p for (_, _, t, p) in expected_edges if t == desc}
        if set(ins) != wired:
            problems.append(f"{desc} inputs {ins} vs wired {sorted(wired)}")
    return problems


# ============================================================================ tests
def test_apply_and_graph():
    result, report, fake = run_builder()
    check("APPLY: status APPLIED", result == "applied" and report["status"] == "APPLIED", report.get("error"))
    check("APPLY: saved exactly the two new packages", fake.saved == [M_V2, MI_V2], fake.saved)
    check("APPLY: created exactly the two targets", fake.created == [M_V2, MI_V2], fake.created)
    check("APPLY: no content dirty after, map dirty set unchanged",
          not fake.dirty_content and fake.dirty_maps == {"/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"},
          (fake.dirty_content, fake.dirty_maps))
    check("APPLY: VV2_OK + VV2_COMPILE_CHECK markers carry the run id",
          any(m.startswith(f"VV2_OK|run={report['run']}") for _, m in fake.logs)
          and any(m.startswith(f"VV2_COMPILE_CHECK|run={report['run']}") for _, m in fake.logs), fake.logs)
    m = fake.assets[M_V2]
    problems = compare_graph(m, EXPECT_EDGES)
    check("GRAPH: every node, edge, parameter, default, texture, sampler, custom input matches the independent spec",
          not problems, problems)
    check("GRAPH: 38 edges + 1 terminal", len(graph_of(m)) == 38 and report["graph"]["edges"] == 38, report["graph"])
    props = m._props
    check("FLAGS: Cloth, two-sided, material attributes, GeometryCache/SkeletalMesh/Clothing usage",
          str(props["shading_model"]).endswith("MSM_CLOTH: 2>") and props["two_sided"] and props["use_material_attributes"]
          and props["used_with_geometry_cache"] and props["used_with_skeletal_mesh"] and props["used_with_clothing"], props)
    mi = fake.assets[MI_V2]
    check("MI: parent is the v2 master, PatternWidthM/DropM copied from the Drop MI, colours = plain oxblood B",
          mi.get_editor_property("parent") is m and mi.overrides_s == DROP_VALUES
          and {k: (v.r, v.g, v.b) for k, v in mi.overrides_v.items()} == EXPECT_VECTORS, (mi.overrides_s, mi.overrides_v))
    check("NO EDIT: the Drop MI was only read (no override written, never dirtied, never saved)",
          fake.assets[DROP_MI].overrides_s == DROP_VALUES and DROP_MI not in fake.saved, fake.saved)
    # comparator controls: it must be able to fail
    broken = set(EXPECT_EDGES)
    broken.discard(("Fresnel", "", "VV2_Base", "Fres"))
    check("CONTROL comparator: one expected edge removed -> caught", compare_graph(m, broken))
    saved_default = EXPECT_SCALARS["Roughness"]
    EXPECT_SCALARS["Roughness"] = 0.5
    caught = compare_graph(m, EXPECT_EDGES)
    EXPECT_SCALARS["Roughness"] = saved_default
    check("CONTROL comparator: one default changed -> caught", caught)
    # VERIFY on the saved state
    result, report, fake = run_builder(mode="VERIFY", fake=fake)
    check("VERIFY after APPLY: VERIFY_OK, nothing created or saved",
          result == "verify" and report["status"] == "VERIFY_OK" and fake.created == [M_V2, MI_V2]
          and fake.saved == [M_V2, MI_V2], report.get("error"))
    result, report, fake = run_builder(faults=("stats_zero",), mode="VERIFY", fake=fake)
    check("CONTROL VERIFY: zero shader instructions -> FAILED", report["status"] == "FAILED", report)
    fake.assets[MI_V2].overrides_s["DropM"] = 9.0
    result, report, fake = run_builder(mode="VERIFY", fake=fake)
    check("CONTROL VERIFY: tampered MI parameter -> FAILED", report["status"] == "FAILED", report)
    # create-only: a second APPLY over the built assets refuses
    result, report, fake = run_builder(mode="APPLY", fake=fake)
    check("CONTROL re-APPLY on existing targets -> refused, nothing new created",
          report["status"] == "FAILED" and "already exist" in report["error"] and fake.created == [M_V2, MI_V2], report)


def test_dry():
    result, report, fake = run_builder(mode="DRY")
    check("DRY: DRY_OK, zero creations, zero saves, zero connects",
          result == "dry" and report["status"] == "DRY_OK" and not fake.created and not fake.saved
          and not [c for c in fake.calls if c[0] in ("connect", "create_asset")], report)
    check("DRY: texture samplers reported as NORMAL",
          all("SAMPLERTYPE_NORMAL" in v["sampler"] for v in report["textures"].values()), report["textures"])


FAILING = [
    ("exists", "target exists -> refused before any creation", lambda f: not f.created and not f.saved),
    ("pie", "PIE active -> refused", lambda f: not f.created),
    ("dirty_start", "dirty content at start -> refused", lambda f: not f.created),
    ("bad_texture", "CrushNormal not TC_NORMALMAP -> refused", lambda f: not f.created),
    ("drop_edge", "connect claims success but stores nothing -> edge read-back fails", lambda f: not f.saved),
    ("wrong_pin", "edge stored on the wrong pin -> read-back fails", lambda f: not f.saved),
    ("wrong_output", "texture wired from R instead of RGB -> output-name read-back fails", lambda f: not f.saved),
    ("extra_edge", "unexpected extra connection -> live-input count fails", lambda f: not f.saved),
    ("terminal_missing", "material-attributes terminal not stored -> read-back fails", lambda f: not f.saved),
    ("default_ignored", "parameter default not applied -> parameter read-back fails", lambda f: not f.saved),
    ("shading_ignored", "shading model not applied -> flag read-back fails", lambda f: not f.saved),
    ("recompile_errors", "recompile returns errors -> fails before save", lambda f: not f.saved),
    ("setter_silent", "MI setter returns True but stores nothing -> MI read-back fails", lambda f: not f.saved),
    ("vector_off", "MI vector stored off by 0.01 -> MI read-back fails", lambda f: not f.saved),
    ("foreign_dirty", "an unrelated package (the Drop MI) gets dirty -> dirty-scope gate, nothing saved",
     lambda f: not f.saved),
    ("save_false", "save_asset returns False -> FAILED", lambda f: True),
]
PASSING = [
    ("setter_lie_false", "MI setters return False AFTER success -> read-back passes (setter-lie handling)"),
    ("compact_inputs", "get_inputs returns only connected nodes (unaligned) -> membership fallback passes"),
    ("tuple_out", "output-name getter returns (bool, str) -> accepted"),
]


def test_faults():
    for fault, label, extra in FAILING:
        result, report, fake = run_builder(faults=(fault,))
        ok = result == "failed" and report["status"] == "FAILED" and extra(fake) \
            and any(lvl == "error" and m.startswith(f"VV2_FAILED|run={report['run']}") for lvl, m in fake.logs)
        check(f"CONTROL {fault}: {label}", ok, report.get("error"))
    for fault, label in PASSING:
        result, report, fake = run_builder(faults=(fault,))
        check(f"POSITIVE {fault}: {label}", result == "applied" and fake.saved == [M_V2, MI_V2], report.get("error"))


# ---------------------------------------------------------------------------- static scans
def calls_and_attrs(src):
    tree = ast.parse(src)
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            names.add(n.attr)
        elif isinstance(n, ast.Name):
            names.add(n.id)
    return names


def scan_delete(src):
    return sorted(n for n in calls_and_attrs(src) if re.search(r"delete|destroy|remove", n, re.I))


def scan_clearcoat_property(src):
    hits = sorted(n for n in calls_and_attrs(src) if re.search(r"CLEAR_COAT|CUSTOM_DATA", n, re.I))
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "connect_material_property":
            prop = ast.unparse(n.args[2]) if len(n.args) > 2 else "?"
            if not prop.endswith("MP_MATERIAL_ATTRIBUTES"):
                hits.append(prop)
    return hits


def scan_saves(src, allowed=("save_asset",)):
    return sorted(n for n in calls_and_attrs(src) if n.startswith("save") and n not in allowed)


def scan_module_level_unreal(src):
    tree = ast.parse(src)
    hits = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            continue
        for n in ast.walk(node):
            if isinstance(n, (ast.Import, ast.ImportFrom)) and any("unreal" in (a.name or "") for a in n.names):
                hits.append("import unreal")
            if isinstance(n, ast.Name) and n.id == "unreal":
                hits.append("unreal.*")
    return hits


def lint_custom(custom):
    problems = []
    for key, (code, inputs, otype) in custom.items():
        for name in inputs:
            if not re.search(r"\b" + re.escape(name) + r"\b", code):
                problems.append(f"{key}: input {name} unused")
        if "return" not in code:
            problems.append(f"{key}: no return")
        for a, b in ("()", "{}", "[]"):
            if code.count(a) != code.count(b):
                problems.append(f"{key}: unbalanced {a}{b}")
        if "\\" in code:
            problems.append(f"{key}: backslash in HLSL")
        if otype not in ("F1", "F3"):
            problems.append(f"{key}: output type {otype}")
    return problems


def edge_invariants(edges, custom, params):
    problems = []
    pairs = [(s, d) for s, _, d, _ in edges]
    dup = sorted({p for p in pairs if pairs.count(p) > 1})
    if dup:
        problems.append(f"source feeds two pins of one node: {dup}")
    pins = [(d, p) for _, _, d, p in edges]
    if len(pins) != len(set(pins)):
        problems.append("a pin is wired twice")
    for key, (_, inputs, _) in custom.items():
        if sorted(p for d, p in pins if d == key) != sorted(inputs):
            problems.append(f"{key} inputs not each wired once")
    used = {s for s, _, _, _ in edges}
    orphans = sorted(set(params) - used)
    if orphans:
        problems.append(f"orphan parameters {orphans}")
    return problems


def test_static():
    src = open(BUILDER, encoding="utf-8").read()
    bench_src = open(BENCH, encoding="utf-8").read()
    mod = load_builder()
    check("SCAN builder: no delete/destroy/remove identifier anywhere", not scan_delete(src), scan_delete(src))
    check("CONTROL scan: a delete_material_expression call is caught",
          scan_delete("mel.delete_material_expression(m, n)\nmel.delete_all_material_expressions(m)"))
    check("SCAN builder: no ClearCoat/CustomData material property; connect_material_property only to MP_MATERIAL_ATTRIBUTES",
          not scan_clearcoat_property(src), scan_clearcoat_property(src))
    check("CONTROL scan: a ClearCoat property connect is caught",
          scan_clearcoat_property("mel.connect_material_property(n, '', unreal.MaterialProperty.MP_CLEAR_COAT)"))
    check("SCAN builder: the only save call is save_asset", not scan_saves(src), scan_saves(src))
    check("SCAN bench wrapper: no save call of any kind", not scan_saves(bench_src, allowed=()), scan_saves(bench_src, ()))
    check("CONTROL scan: save_dirty_packages is caught", scan_saves("unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)"))
    check("SCAN bench wrapper: no material delete/asset edit calls",
          not [n for n in calls_and_attrs(bench_src) if re.search(r"delete|set_material_instance|^save", n, re.I)],
          [n for n in calls_and_attrs(bench_src) if re.search(r"delete|set_material_instance|^save", n, re.I)])
    for label, s in (("builder", src), ("bench wrapper", bench_src)):
        check(f"SCAN {label}: no unreal at module level", not scan_module_level_unreal(s), scan_module_level_unreal(s))
    check("CONTROL scan: module-level 'import unreal' is caught", scan_module_level_unreal("import unreal\nX = unreal.Vector()"))
    check("HLSL lint: every Custom input referenced, returns, balanced, no backslashes",
          not lint_custom(mod.CUSTOM), lint_custom(mod.CUSTOM))
    bad_custom = copy.deepcopy(mod.CUSTOM)
    bad_custom["VV2_Base"] = (mod.CODE_BASE.replace("RimLift", "Rim"), bad_custom["VV2_Base"][1], "F3")
    check("CONTROL HLSL lint: an unreferenced input is caught", lint_custom(bad_custom))
    params = list(mod.SCALARS) + list(mod.VECTORS) + list(mod.TEX)
    check("EDGES invariants: no source on two pins of one node, every pin once, every custom input wired, no orphan param",
          not edge_invariants(mod.EDGES, mod.CUSTOM, params), edge_invariants(mod.EDGES, mod.CUSTOM, params))
    bad = [e for e in mod.EDGES if e[0] != "RimLift"] + [("Specular", "", "VV2_Base", "RimLift")]
    check("CONTROL EDGES invariants: orphan parameter caught", edge_invariants(bad, mod.CUSTOM, params))
    bad2 = list(mod.EDGES) + [("VV2_Crush", "", "Attrs", "AmbientOcclusion"), ("VV2_Crush", "", "Attrs", "Metallic")]
    check("CONTROL EDGES invariants: one source on two pins of one node caught", edge_invariants(bad2, mod.CUSTOM, params))
    missing = [p for p in REQUIRED_BY_BRIEF if p not in params]
    check("BRIEF: all eight required parameters exposed", not missing, missing)
    check("BRIEF: Roughness default within 0.8-0.95", 0.8 <= mod.SCALARS["Roughness"][0] <= 0.95, mod.SCALARS["Roughness"])
    check("CONTROL brief: a missing required parameter is caught",
          [p for p in REQUIRED_BY_BRIEF + ["SheenColor"] if p not in params])
    check("BRIEF: targets are new names in the curtain materials folder, distinct from the v1 assets",
          mod.TARGETS == [M_V2, MI_V2] and "M_CurtainVelvet" not in [t.rsplit("/", 1)[1] for t in mod.TARGETS])


def test_variants():
    os.environ["VV2_NO_AUTORUN"] = "1"
    spec = importlib.util.spec_from_file_location("velvet_v2_bench_under_test", BENCH)
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    doc = json.load(open(VARIANTS, encoding="utf-8"))
    problems = bench.validate_variants(doc)
    check("VARIANTS: shipped file valid against the builder's parameter list", not problems, problems)
    n = len(doc["variants"])
    check("VARIANTS: 4-5 v2 variants", 4 <= n <= 5, n)
    for label, mutate in (
            ("unknown parameter", lambda d: d["variants"]["V2B"]["scalars"].__setitem__("Glossiness", 0.2)),
            ("three-value vector", lambda d: d["variants"]["V2B"]["vectors"].__setitem__("BaseColour", [0.1, 0.0, 0.0])),
            ("roughness above 1", lambda d: d["variants"]["V2D"]["scalars"].__setitem__("Roughness", 1.4)),
            ("inner cone wider than outer", lambda d: d["lights"]["shadowplay_narrow"].__setitem__("inner_deg", 20.0)),
            ("zero PileScale", lambda d: d["variants"]["V2A"]["scalars"].__setitem__("PileScale", 0.0))):
        d = copy.deepcopy(doc)
        mutate(d)
        check(f"CONTROL variants: {label} is caught", bench.validate_variants(d))
    steps = doc["capture_plan"]["steps"]
    names = set(doc["variants"])
    bad = []
    for i, (tool, cfg) in enumerate(steps):
        if tool == "VB" and cfg["action"] == "variant" and cfg["name"] not in names:
            bad.append(f"step {i}: unknown variant {cfg['name']}")
        if cfg.get("action") == "capture":
            prev = steps[i - 1][1]
            if prev.get("action") not in ("variant",):
                bad.append(f"step {i}: capture not preceded by a variant call")
    on = [i for i, (_, c) in enumerate(steps) if c["action"] == "spot_on"]
    off = [i for i, (_, c) in enumerate(steps) if c["action"] == "spot_off"]
    cleanups = [i for i, (_, c) in enumerate(steps) if c["action"] == "cleanup"]
    if len(on) != len(off) or any(b <= a for a, b in zip(on, off)) or (off and off[-1] > cleanups[-1]):
        bad.append("spot_on/spot_off unpaired or spot left on at cleanup")
    tags = {(c.get("tag"), steps[i - 1][1].get("name")) for i, (_, c) in enumerate(steps) if c["action"] == "capture"}
    want = {(t, v) for t in ("stalls", "lantern", "spot") for v in ["B"] + sorted(names)}
    if tags != want:
        bad.append(f"capture matrix {sorted(want - tags)} missing")
    check("CAPTURE PLAN: every capture follows a variant; B + all v2 under stalls, lantern and spot; spot paired", not bad, bad)
    bad_steps = copy.deepcopy(steps)
    del bad_steps[[i for i, (_, c) in enumerate(bad_steps) if c["action"] == "spot_off"][0]]
    off2 = [i for i, (_, c) in enumerate(bad_steps) if c["action"] == "spot_off"]
    check("CONTROL capture plan: a missing spot_off is caught", len(on) != len(off2))


def main():
    test_static()
    test_dry()
    test_apply_and_graph()
    test_faults()
    test_variants()
    for t in TMP_ROOTS:
        shutil.rmtree(t, ignore_errors=True)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    controls = [r for r in RESULTS if r[0].startswith("CONTROL")]
    print(f"\nHARNESS: {passed} passed, {failed} failed of {len(RESULTS)} "
          f"(failing controls caught: {sum(1 for _, ok, _ in controls if ok)}/{len(controls)})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
