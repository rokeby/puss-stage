"""Build the isolated billboard-paper gloss v2 master and its two parent MIs.

OFFLINE-AUTHORED; run once in the PussStage editor only after review.  The v1
master and parents are read-only sources.  This script writes and saves only the
three v2 packages named in V2_WRITABLE.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
BILLBOARD = "/Game/Scenes/Wings/PaintedSurface/Billboard"
V1_MASTER = BILLBOARD + "/M_Wing_Billboard_Master"
V1_FRONT = BILLBOARD + "/MI_Billboard_Front"
V1_FLAP = BILLBOARD + "/MI_Billboard_Flap"
V2_MASTER = BILLBOARD + "/M_Wing_Billboard_Master_v2"
V2_FRONT = BILLBOARD + "/MI_Billboard_Front_v2"
V2_FLAP = BILLBOARD + "/MI_Billboard_Flap_v2"
V1_READ_ONLY = frozenset((V1_MASTER, V1_FRONT, V1_FLAP))
V2_WRITABLE = frozenset((V2_MASTER, V2_FRONT, V2_FLAP))
TEXTURES = BILLBOARD + "/Textures"
TEXTURE_PATHS = {
    "T_BB_Colour": TEXTURES + "/T_BB_Colour",
    "T_BB_Mask": TEXTURES + "/T_BB_Mask",
    "T_BB_Normal": TEXTURES + "/T_BB_Normal",
}
GLOSS_DEFAULTS = {
    "PGloss": 0.18,
    "MatteRoughMin": 0.75,
    "MatteRoughMax": 0.85,
    "GlossRoughMin": 0.35,
    "GlossRoughMax": 0.50,
    "PeelRoughnessMin": 0.85,
    "RoughnessFloor": 0.30,
    "Specular": 0.30,
}
EXPECTED_CURRENT_COLOURS = {
    "BackingColor": (0.20, 0.06, 0.04, 1.0),
    "PrimerColor": (0.16, 0.13, 0.11, 1.0),
}
RESULT_PATH = pathlib.Path(
    "E:/PussStage/Saved/CodexFlatV3/gloss/build_billboard_master_v2_result.json"
)


ROUGHNESS_V1 = (
    "float rough = saturate(lerp(RoughMin, RoughMax, MaskRough) - "
    "PasteSoak * PasteGloss + fibreSigned * 0.05);"
)
ROUGHNESS_V2 = r"""
// A salted re-hash keeps the varnish pick per sheet while decoupling it from
// the under-layer pick, which uses SheetHash directly.
float glossHash = frac(sin((SheetHash + 0.314159) * 91.173) * 43758.5453);
float isGlossSheet = 1.0 - step(saturate(PGloss), glossHash);
float matteRough = lerp(MatteRoughMin, MatteRoughMax, saturate(MaskRough));
float glossRough = lerp(GlossRoughMin, GlossRoughMax, saturate(MaskRough));
float rangeLo = lerp(MatteRoughMin, GlossRoughMin, isGlossSheet);
float rangeHi = lerp(MatteRoughMax, GlossRoughMax, isGlossSheet);
float rough = lerp(matteRough, glossRough, isGlossSheet);
// Paste-soak and paper fibre vary the finish within, but never outside, the
// selected sheet's matte/varnished range. SkinN below retains wrinkle normals.
rough = clamp(rough - PasteSoak * PasteGloss + fibreSigned * 0.025, rangeLo, rangeHi);
float underLayerVisible = step(0.5, peelT);
rough = lerp(rough, max(rough, max(PeelRoughnessMin, 0.85)), underLayerVisible);
rough = max(rough, max(RoughnessFloor, 0.30));
""".strip()

GLOSS_INPUTS = (
    "SheetHash",
    "PGloss",
    "MatteRoughMin",
    "MatteRoughMax",
    "GlossRoughMin",
    "GlossRoughMax",
    "PeelRoughnessMin",
    "RoughnessFloor",
)
GLOSS_PARAMETER_ROWS = (
    ("PGloss", 0.18, 0),
    ("MatteRoughMin", 0.75, 1),
    ("MatteRoughMax", 0.85, 2),
    ("GlossRoughMin", 0.35, 3),
    ("GlossRoughMax", 0.50, 4),
    ("PeelRoughnessMin", 0.85, 5),
    ("RoughnessFloor", 0.30, 6),
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_path(value):
    if value is None:
        return None
    return str(value.get_path_name()).split(".", 1)[0]


def linear_tuple(value):
    return tuple(float(component) for component in (value.r, value.g, value.b, value.a))


def close_tuple(actual, expected, tolerance=1.0e-5):
    return len(actual) == len(expected) and all(
        abs(float(left) - float(right)) <= tolerance
        for left, right in zip(actual, expected)
    )


def assert_v2_write_path(path):
    require(path in V2_WRITABLE, "REFUSING_NON_V2_WRITE|" + str(path))
    require(path not in V1_READ_ONLY, "REFUSING_V1_WRITE|" + str(path))
    return path


def save_v2(path):
    assert_v2_write_path(path)
    require(
        unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False),
        "V2_SAVE_FAILED|" + path,
    )


def package_names(packages):
    return sorted(str(package.get_name()).split(".", 1)[0] for package in packages)


def package_census():
    return {
        "content": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def load_asset(path, expected_type=None):
    value = unreal.EditorAssetLibrary.load_asset(path)
    require(value is not None, "MISSING_ASSET|" + path)
    if expected_type is not None:
        require(isinstance(value, expected_type), "WRONG_ASSET_TYPE|" + path)
    return value


def editor_ready():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "NO_EDITOR_WORLD")
    require(str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_EDITOR_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")


def load_legacy_builder():
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.abspath(
        os.path.join(here, "..", "..", "CodexWingMateriality", "build_billboard_master.py")
    )
    require(os.path.isfile(source), "MISSING_V1_BUILDER|" + source)
    spec = importlib.util.spec_from_file_location("_billboard_v1_read_only", source)
    require(spec is not None and spec.loader is not None, "V1_BUILDER_SPEC_FAILED")
    module = importlib.util.module_from_spec(spec)
    module.WM_IMPORT_ONLY = True
    spec.loader.exec_module(module)
    require(module.MASTER == V1_MASTER, "V1_MASTER_PATH_DRIFT")
    require(module.MI_FRONT == V1_FRONT, "V1_FRONT_PATH_DRIFT")
    require(module.MI_FLAP == V1_FLAP, "V1_FLAP_PATH_DRIFT")
    return module


def install_gloss_graph(legacy):
    """Add only the gloss inputs/nodes while retaining v1's graph builder."""
    original_graph = legacy.B.Graph
    require(ROUGHNESS_V1 in legacy.CODE_SURFACE, "V1_ROUGHNESS_SOURCE_DRIFT")
    legacy.CODE_SURFACE = legacy.CODE_SURFACE.replace(ROUGHNESS_V1, ROUGHNESS_V2, 1)

    class GlossGraph(original_graph):
        def __init__(self, material):
            super().__init__(material)
            self._sheet_node = None

        def custom(self, x, y, description, code, inputs, output_type, extra_outputs=()):
            is_sheet = description == "UV1 sheet cells, hash, seams, and older-poster UV"
            is_surface = description == "Billboard skin, procedural print/fibre, variation, and burn"
            actual_inputs = list(inputs) + (list(GLOSS_INPUTS) if is_surface else [])
            node = super().custom(
                x, y, description, code, actual_inputs, output_type, extra_outputs
            )
            if is_sheet:
                self._sheet_node = node
            if is_surface:
                require(self._sheet_node is not None, "GLOSS_SHEET_NODE_MISSING")
                self.link(self._sheet_node, "SheetHash", node, "SheetHash")
                for index, (name, value, priority) in enumerate(GLOSS_PARAMETER_ROWS):
                    parameter = super().scalar(
                        name, value, "04 Gloss", -1700, 3650 + index * 100, priority
                    )
                    self.link(parameter, "", node, name)
            return node

        def scalar(self, name, value, group, x, y, prio=0):
            if name != "Specular":
                return super().scalar(name, value, group, x, y, prio)
            parameter = super().scalar(name, value, "04 Gloss", x, y, 7)
            cap = self.const(0.30, x + 170, y + 70)
            limited = self.node(unreal.MaterialExpressionMin, x + 350, y)
            self.link(parameter, "", limited, "A")
            self.link(cap, "", limited, "B")
            return limited

    legacy.B.Graph = GlossGraph


def create_or_load_v2_mi(path):
    assert_v2_write_path(path)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return load_asset(path, unreal.MaterialInstanceConstant)
    folder, name = path.rsplit("/", 1)
    value = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name,
        folder,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    require(value is not None, "CREATE_MI_FAILED|" + path)
    return value


def copy_parameter_values(source, destination):
    mel = unreal.MaterialEditingLibrary
    copied = {"scalar": {}, "vector": {}, "texture": {}, "static_switch": {}}
    for name in mel.get_scalar_parameter_names(source):
        key = str(name)
        value = float(mel.get_material_instance_scalar_parameter_value(source, name))
        mel.set_material_instance_scalar_parameter_value(destination, name, value)
        actual = float(mel.get_material_instance_scalar_parameter_value(destination, name))
        require(abs(actual - value) <= 1.0e-6, "SCALAR_COPY_MISMATCH|" + key)
        copied["scalar"][key] = value
    for name in mel.get_vector_parameter_names(source):
        key = str(name)
        value = mel.get_material_instance_vector_parameter_value(source, name)
        mel.set_material_instance_vector_parameter_value(destination, name, value)
        actual = mel.get_material_instance_vector_parameter_value(destination, name)
        require(close_tuple(linear_tuple(actual), linear_tuple(value)), "VECTOR_COPY_MISMATCH|" + key)
        copied["vector"][key] = list(linear_tuple(value))
    for name in mel.get_texture_parameter_names(source):
        key = str(name)
        value = mel.get_material_instance_texture_parameter_value(source, name)
        require(value is not None, "SOURCE_TEXTURE_NONE|" + key)
        mel.set_material_instance_texture_parameter_value(destination, name, value)
        actual = mel.get_material_instance_texture_parameter_value(destination, name)
        require(asset_path(actual) == asset_path(value), "TEXTURE_COPY_MISMATCH|" + key)
        copied["texture"][key] = asset_path(value)
    for name in mel.get_static_switch_parameter_names(source):
        key = str(name)
        value = bool(mel.get_material_instance_static_switch_parameter_value(source, name))
        mel.set_material_instance_static_switch_parameter_value(destination, name, value)
        actual = bool(mel.get_material_instance_static_switch_parameter_value(destination, name))
        require(actual == value, "SWITCH_COPY_MISMATCH|" + key)
        copied["static_switch"][key] = value
    return copied


def assert_current_v1_colours(source, source_path):
    mel = unreal.MaterialEditingLibrary
    for name, expected in EXPECTED_CURRENT_COLOURS.items():
        actual = linear_tuple(mel.get_material_instance_vector_parameter_value(source, name))
        require(close_tuple(actual, expected), "%s_CURRENT_VALUE_DRIFT|%s|%r" % (name, source_path, actual))
    specular = float(mel.get_material_instance_scalar_parameter_value(source, "Specular"))
    require(abs(specular - 0.30) <= 1.0e-6,
            "SPECULAR_CURRENT_VALUE_DRIFT|%s|%r" % (source_path, specular))


def build_v2_parent(source_path, destination_path):
    source = load_asset(source_path, unreal.MaterialInstanceConstant)
    assert_current_v1_colours(source, source_path)
    destination = create_or_load_v2_mi(destination_path)
    mel = unreal.MaterialEditingLibrary
    assert_v2_write_path(destination_path)
    mel.clear_all_material_instance_parameters(destination)
    mel.set_material_instance_parent(destination, load_asset(V2_MASTER, unreal.Material))
    require(asset_path(destination.get_editor_property("parent")) == V2_MASTER,
            "V2_PARENT_SET_FAILED|" + destination_path)
    copied = copy_parameter_values(source, destination)
    for name, value in GLOSS_DEFAULTS.items():
        mel.set_material_instance_scalar_parameter_value(destination, name, float(value))
        actual = float(mel.get_material_instance_scalar_parameter_value(destination, name))
        require(abs(actual - value) <= 1.0e-6, "GLOSS_DEFAULT_MISMATCH|" + name)
    destination.set_editor_property(
        "base_property_overrides", source.get_editor_property("base_property_overrides")
    )
    mel.update_material_instance(destination)
    return destination, copied


def main():
    editor_ready()
    require(V1_READ_ONLY.isdisjoint(V2_WRITABLE), "V1_V2_PATH_OVERLAP")
    before = package_census()
    owned_before = set(before["content"]) & set(V2_WRITABLE)
    unrelated_before = set(before["content"]) - set(V2_WRITABLE)

    legacy = load_legacy_builder()
    install_gloss_graph(legacy)
    legacy.MASTER = V2_MASTER
    require(legacy.MASTER not in V1_READ_ONLY, "LEGACY_BUILDER_STILL_TARGETS_V1")
    textures = {
        name: load_asset(path, unreal.Texture2D) for name, path in TEXTURE_PATHS.items()
    }
    material, wpo_property = legacy.build_master(textures)
    require(asset_path(material) == V2_MASTER, "BUILT_MASTER_PATH_MISMATCH")
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    save_v2(V2_MASTER)

    parent_copies = {}
    for source_path, destination_path in ((V1_FRONT, V2_FRONT), (V1_FLAP, V2_FLAP)):
        destination, copied = build_v2_parent(source_path, destination_path)
        require(asset_path(destination) == destination_path, "BUILT_MI_PATH_MISMATCH")
        save_v2(destination_path)
        parent_copies[destination_path] = {
            "source": source_path,
            "parameters": copied,
            "gloss_defaults": dict(GLOSS_DEFAULTS),
        }

    after = package_census()
    newly_dirty_unrelated = set(after["content"]) - unrelated_before - set(V2_WRITABLE)
    require(not newly_dirty_unrelated,
            "UNRELATED_PACKAGES_DIRTIED|" + json.dumps(sorted(newly_dirty_unrelated)))
    require(not (set(after["content"]) & set(V2_WRITABLE)),
            "V2_PACKAGES_STILL_DIRTY|" + json.dumps(sorted(set(after["content"]) & set(V2_WRITABLE))))
    require(after["maps"] == before["maps"], "MAP_DIRTY_CENSUS_CHANGED")

    result = {
        "status": "PASS",
        "proof_tier": "measured when run in editor; offline-authored until then",
        "assets_saved": [V2_MASTER, V2_FRONT, V2_FLAP],
        "v1_read_only": sorted(V1_READ_ONLY),
        "v2_owned_dirty_before": sorted(owned_before),
        "dirty_before": before,
        "dirty_after": after,
        "expressions": unreal.MaterialEditingLibrary.get_num_material_expressions(material),
        "max_wpo_property": wpo_property,
        "parent_copies": parent_copies,
        "compile_note": "Material compile is asynchronous; inspect the Unreal log about 20 seconds later.",
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    unreal.log(
        "PUSS_WING_BILLBOARD_MASTER_V2_BUILD_SUCCESS|assets=3|v1_touched=0|"
        "compile_check=pending_20s|dirty_content=%d|dirty_maps=%d"
        % (len(after["content"]), len(after["maps"]))
    )


if not globals().get("WM_IMPORT_ONLY"):
    main()
