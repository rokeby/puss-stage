"""Offline structural/fake-unreal checks for build_billboard_master_v2.py."""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys
import types


HERE = pathlib.Path(__file__).resolve().parent
BUILDER = HERE / "build_billboard_master_v2.py"
V1 = {
    "/Game/Scenes/Wings/PaintedSurface/Billboard/M_Wing_Billboard_Master",
    "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front",
    "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap",
}
V2 = {
    "/Game/Scenes/Wings/PaintedSurface/Billboard/M_Wing_Billboard_Master_v2",
    "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front_v2",
    "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap_v2",
}


class StaticFailure(RuntimeError):
    pass


def call_name(node):
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def enclosing_function(parents, node):
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
    return None


def check(source):
    try:
        tree = ast.parse(source, filename=str(BUILDER))
    except SyntaxError as exc:
        raise StaticFailure("parse failed: %s" % exc) from exc
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    failures = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node)
        if "delete" in name.lower():
            failures.append("delete call at line %d: %s" % (node.lineno, name))
        if name == "reload":
            failures.append("reload call at line %d" % node.lineno)
        if name == "link":
            if len(node.args) != 4 or node.keywords:
                failures.append("unnamed/incomplete graph connection at line %d" % node.lineno)
            elif any(isinstance(value, ast.Constant) and value.value is None
                     for value in (node.args[1], node.args[3])):
                failures.append("None graph pin at line %d" % node.lineno)
        if name == "save_asset" and enclosing_function(parents, node) != "save_v2":
            failures.append("save_asset outside save_v2 at line %d" % node.lineno)

    required = (
        "V1_READ_ONLY",
        "V2_WRITABLE",
        "assert_v2_write_path(path)",
        "path not in V1_READ_ONLY",
        '"PGloss": 0.18',
        '("MatteRoughMin", 0.75',
        '("MatteRoughMax", 0.85',
        '("GlossRoughMin", 0.35',
        '("GlossRoughMax", 0.50',
        '("PeelRoughnessMin", 0.85',
        '("RoughnessFloor", 0.30',
        '"Specular": 0.30',
        '"04 Gloss"',
        "glossHash",
        "SheetHash",
        "max(RoughnessFloor, 0.30)",
        "compile_check=pending_20s",
    )
    for text in required:
        if text not in source:
            failures.append("required contract text missing: " + text)
    if "assert_v2_write_path(path)" not in source.split("def save_v2(path):", 1)[-1].split("\ndef ", 1)[0]:
        failures.append("save_v2 does not runtime-guard its destination")
    if failures:
        raise StaticFailure("; ".join(failures))
    return tree


def fake_unreal_import():
    fake = types.ModuleType("unreal")
    previous = sys.modules.get("unreal")
    sys.modules["unreal"] = fake
    try:
        spec = importlib.util.spec_from_file_location("_gloss_builder_fake", BUILDER)
        if spec is None or spec.loader is None:
            raise StaticFailure("fake-unreal import spec failed")
        module = importlib.util.module_from_spec(spec)
        module.WM_IMPORT_ONLY = True
        spec.loader.exec_module(module)
        if set(module.V1_READ_ONLY) != V1:
            raise StaticFailure("fake-unreal import found wrong v1 path set")
        if set(module.V2_WRITABLE) != V2:
            raise StaticFailure("fake-unreal import found wrong v2 path set")
        if module.V1_READ_ONLY & module.V2_WRITABLE:
            raise StaticFailure("fake-unreal import found v1/v2 overlap")
    finally:
        if previous is None:
            sys.modules.pop("unreal", None)
        else:
            sys.modules["unreal"] = previous


def main():
    source = BUILDER.read_text(encoding="utf-8")
    check(source)
    fake_unreal_import()

    planted = source + "\nunreal.MaterialEditingLibrary.delete_material_expression(None, None)\n"
    negative_failed = False
    try:
        check(planted)
    except StaticFailure as exc:
        negative_failed = "delete_material_expression" in str(exc)
    if not negative_failed:
        raise StaticFailure("negative control did not reject planted delete_material_expression")

    print("PASS parse")
    print("PASS every graph link supplies explicit source/output/target/input arguments")
    print("PASS no delete or reload calls")
    print("PASS v1/v2 paths disjoint and all save_asset calls guarded by save_v2")
    print("PASS fake-unreal import with WM_IMPORT_ONLY")
    print("PASS negative control rejected planted delete_material_expression")


if __name__ == "__main__":
    main()
