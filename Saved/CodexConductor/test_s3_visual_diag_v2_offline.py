"""Offline positive/negative harness for Codex job 109's read-only UE script."""
from __future__ import annotations

import ast
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
TARGET = HERE / "s3_visual_diag_20261009.py"

REQUIRED = (
    "EVALUATED_FRAMES = (300, 2400)",
    '"blend_mode"',
    '"shading_model"',
    '"two_sided"',
    '"opacity_mask_clip_value"',
    '"hidden_in_game"',
    '"render_in_main_pass"',
    '"visible"',
    "get_all_socket_names",
    "get_bone_index",
    "vertical_raycast",
    "create_level_sequence_player",
    "restore_state=True",
    "figure_state_census",
    "S3_VISUAL_DIAG_V2_SUCCESS",
)

FORBIDDEN_CALLS = {
    "save_asset", "save_loaded_asset", "save_current_level", "save_map", "save_all_dirty_packages",
    "modify", "set_editor_property", "set_actor_location", "set_actor_transform", "set_material",
    "add_actor", "spawn_actor_from_class", "editor_play_simulate", "editor_request_begin_play",
}


def validate(source: str) -> list[str]:
    errors = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["syntax: %s" % exc]
    for token in REQUIRED:
        if token not in source:
            errors.append("missing required token: %s" % token)
    if "LevelSequenceEditorBlueprintLibrary" in source:
        errors.append("editor Sequencer API is forbidden because opening/scrubbing can dirty the map")
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        calls.append(name)
    bad = sorted(set(calls) & FORBIDDEN_CALLS)
    if bad:
        errors.append("persistent mutation/save calls: %s" % bad)
    if "require(dirty_before == dirty_after" not in source or "require(actor_before == actor_after" not in source:
        errors.append("missing exact before/after census assertion")
    if "require(figure_state_before == figure_state_final" not in source:
        errors.append("missing restored figure-state assertion")
    return errors


def load_pure_function(source: str, name: str):
    tree = ast.parse(source)
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {"math": math}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(TARGET), "exec"), namespace)
    return namespace[name]


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    positive = [
        ("production source", source),
        ("comments do not affect policy", source + "\n# offline harness positive control\n"),
    ]
    negative = [
        ("save call", source + "\nunreal.EditorAssetLibrary.save_asset('/Game/Forbidden')\n"),
        ("missing visibility property", source.replace('"hidden_in_game"', '"omitted_hidden_flag"')),
        ("missing requested second frame", source.replace("EVALUATED_FRAMES = (300, 2400)", "EVALUATED_FRAMES = (300,)")),
        ("missing foot discovery", source.replace("get_all_socket_names", "omitted_socket_names")),
        ("missing material flag", source.replace('"shading_model"', '"omitted_shading_model"')),
    ]

    failures = []
    for label, candidate in positive:
        errors = validate(candidate)
        if errors:
            failures.append("POSITIVE %s unexpectedly failed: %s" % (label, errors))
    for label, candidate in negative:
        errors = validate(candidate)
        if not errors:
            failures.append("NEGATIVE %s unexpectedly passed" % label)
    raycast = load_pure_function(source, "vertical_raycast")
    triangle = (0.0, 10.0, 0.0, 10.0, ((0.0, 0.0, 10.0), (10.0, 0.0, 10.0), (0.0, 10.0, 10.0)))
    indexed = {"rows": [triangle], "cell_size_cm": 100.0, "bins": {(0, 0): [0]}, "overflow": []}
    if raycast(indexed, 2.0, 2.0, 100.0) != 10.0:
        failures.append("POSITIVE indexed downward ray did not hit the test triangle")
    if raycast(indexed, 20.0, 20.0, 100.0) is not None:
        failures.append("POSITIVE indexed downward miss incorrectly returned a surface")
    if failures:
        raise AssertionError("\n".join(failures))
    print("S3_VISUAL_DIAG_V2_HARNESS_PASS|positive=4/4|negative=5/5|total=9/9")


if __name__ == "__main__":
    main()
