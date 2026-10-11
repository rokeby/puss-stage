#!/usr/bin/env python3
"""Offline AST preflight for Unreal Engine 5.8 Python tools.

The checker is deliberately conservative: known live failures are DENY findings,
surfaces exercised by successful 10 Oct APPLY runs are ALLOW findings, and direct
``unreal.*`` surfaces in neither set are UNKNOWN.  UNKNOWN is informational;
DENY is the only finding that makes the process exit 1.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable


# Mined from the accepted Job 169/177, Job 178B/184, Job 182/184, P56/176,
# P52/177, P75 and Job 144 APPLY paths cited in APPLY_PASS_REPORT_2026-10-10.md.
ALLOW_CHAINS = {
    "unreal.Actor",
    "unreal.AttachmentRule.KEEP_WORLD",
    "unreal.BlueprintEditorLibrary.get_blueprint_parent_class",
    "unreal.CineCameraActor",
    "unreal.EditorActorSubsystem",
    "unreal.EditorAssetLibrary.does_asset_exist",
    "unreal.EditorAssetLibrary.load_blueprint_class",
    "unreal.EditorAssetLibrary.save_asset",
    "unreal.EditorAssetLibrary.save_loaded_asset",
    "unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages",
    "unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages",
    "unreal.EditorLoadingAndSavingUtils",
    "unreal.FrameNumber",
    "unreal.GameplayStatics.get_all_actors_of_class",
    "unreal.GameplayStatics.get_player_camera_manager",
    "unreal.GameplayStatics.get_player_controller",
    "unreal.GuidLibrary.conv_guid_to_string",
    "unreal.GuidLibrary.parse_string_to_guid",
    "unreal.GroomLibrary",
    "unreal.GroomLibrary.create_new_groom_binding_asset_with_path",
    "unreal.MathLibrary.compose_transforms",
    "unreal.MathLibrary.dot_vector_vector",
    "unreal.MathLibrary.find_look_at_rotation",
    "unreal.MathLibrary.get_forward_vector",
    "unreal.MathLibrary.get_right_vector",
    "unreal.MathLibrary.get_up_vector",
    "unreal.MathLibrary.inverse_transform_location",
    "unreal.MathLibrary.inverse_transform_rotation",
    "unreal.MovieSceneBindingProxy",
    "unreal.MovieScene3DTransformTrack",
    "unreal.MovieSceneBoolTrack",
    "unreal.MovieSceneCompletionMode.RESTORE_STATE",
    "unreal.MovieSceneFadeTrack",
    "unreal.MovieSceneFloatTrack",
    "unreal.MovieSceneKeyInterpolation.AUTO",
    "unreal.MovieSceneKeyInterpolation.LINEAR",
    "unreal.MovieSceneTimeUnit.DISPLAY_RATE",
    "unreal.MovieSceneVisibilityTrack",
    "unreal.MovieSceneSpawnTrack",
    "unreal.Name",
    "unreal.NiagaraComponent",
    "unreal.NiagaraActor",
    "unreal.NiagaraSystem",
    "unreal.Paths.convert_relative_path_to_full",
    "unreal.Paths.project_content_dir",
    "unreal.Paths.project_dir",
    "unreal.Paths.project_saved_dir",
    "unreal.PointLight",
    "unreal.PointLightComponent",
    "unreal.Quat",
    "unreal.Rotator",
    "unreal.StaticMeshActor",
    "unreal.StaticMeshComponent",
    "unreal.ComponentMobility.MOVABLE",
    "unreal.DirectionalLightComponent",
    "unreal.DrawDebugTrace.NONE",
    "unreal.InfinityStageCameraPilotLibrary",
    "unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range",
    "unreal.InfinityStageShowRoot",
    "unreal.LevelEditorSubsystem",
    "unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence",
    "unreal.LightUnits.CANDELAS",
    "unreal.LightUnits.LUMENS",
    "unreal.RichCurveTangentMode.RCTM_AUTO",
    "unreal.SkyAtmosphereComponent",
    "unreal.SubobjectDataBlueprintFunctionLibrary",
    "unreal.SubobjectDataSubsystem",
    "unreal.Text",
    "unreal.TraceTypeQuery.TRACE_TYPE_QUERY1",
    "unreal.Transform",
    "unreal.UnrealEditorSubsystem",
    "unreal.Vector",
    "unreal.get_editor_subsystem",
    "unreal.get_engine_subsystem",
    "unreal.load_asset",
    "unreal.log",
    "unreal.log_error",
    "unreal.log_warning",
    "unreal.register_slate_post_tick_callback",
    "unreal.unregister_slate_post_tick_callback",
    "unreal.SystemLibrary.execute_console_command",
    "unreal.SystemLibrary.line_trace_single",
}

ALLOW_METHODS = {
    "add_key",
    "add_possessable",
    "add_section",
    "add_spawnable_from_class",
    "add_track",
    "get_all_channels",
    "get_editor_property",
    "get_name",
    "get_path_name",
    "modify",
    "quaternion",
    "remove_key",
    "remove_track",
    "set_binding_asset",
    "set_editor_property",
    "set_groom_asset",
}


@dataclass(frozen=True)
class Rule:
    replacement: str
    reason: str


DENY_CHAINS = {
    "unreal.DateTime.now": Rule(
        "use Python datetime.datetime.now()/utcnow()",
        "UE 5.8 DateTime has no now wrapper",
    ),
    "unreal.EditorAssetLibrary.get_dirty_content_packages": Rule(
        "use unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()",
        "dirty-package census is not on EditorAssetLibrary",
    ),
    "unreal.EditorAssetLibrary.get_dirty_map_packages": Rule(
        "use unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()",
        "dirty-package census is not on EditorAssetLibrary",
    ),
    "unreal.MovieSceneKeyInterpolation.CUBIC": Rule(
        "use unreal.MovieSceneKeyInterpolation.AUTO",
        "CUBIC is not exposed by UE 5.8 Python",
    ),
    "unreal.SystemLibrary.convert_to_trace_type": Rule(
        "use unreal.TraceTypeQuery.TRACE_TYPE_QUERY1 for Visibility",
        "convert_to_trace_type is not exposed by UE 5.8 Python",
    ),
    "unreal.EngineTypes": Rule(
        "use the concrete exported enum/type (for example unreal.TraceTypeQuery)",
        "the unreal.EngineTypes namespace is not exposed",
    ),
    "unreal.GroomBlueprintLibrary": Rule(
        "use unreal.GroomLibrary and the UE 5.8 split groom/binding setters",
        "GroomBlueprintLibrary is not the UE 5.8 Python surface",
    ),
}

DENY_METHODS = {
    "add_master_track": Rule(
        "call sequence.add_track(track_class)",
        "LevelSequence.add_master_track is absent",
    ),
    "get_channels": Rule(
        "call section.get_all_channels()",
        "MovieScene sections expose get_all_channels in UE 5.8",
    ),
    "get_relative_location": Rule(
        'call component.get_editor_property("relative_location")',
        "SceneComponent.get_relative_location is absent",
    ),
    "get_root_component": Rule(
        'call actor.get_editor_property("root_component")',
        "Actor/StaticMeshActor.get_root_component is absent",
    ),
    "is_child_of": Rule(
        "for Blueprints, call unreal.BlueprintEditorLibrary.get_blueprint_parent_class(bp) and compare identities",
        "BlueprintGeneratedClass.is_child_of is absent",
    ),
    "is_hidden": Rule(
        'call actor.get_editor_property("hidden")',
        "Actor subclasses used on 10 Oct did not expose is_hidden",
    ),
    "post_edit_change": Rule(
        "write editor properties, call modify(), verify them before save, then save explicitly",
        "Texture2D.post_edit_change is absent",
    ),
}


@dataclass(frozen=True)
class Finding:
    status: str
    path: Path
    line: int
    column: int
    surface: str
    detail: str = ""


def _chain(node: ast.AST, unreal_aliases: set[str]) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name) and current.id in unreal_aliases:
        return "unreal." + ".".join(reversed(parts))
    return None


def _literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


class Scanner(ast.NodeVisitor):
    def __init__(self, path: Path, tree: ast.AST) -> None:
        self.path = path
        self.tree = tree
        self.parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[child] = parent
        self.unreal_aliases = {"unreal"}
        self.types: dict[str, str] = {}
        self.findings: list[Finding] = []
        self._emitted: set[tuple[int, int, str, str]] = set()

    def emit(self, node: ast.AST, status: str, surface: str, detail: str = "") -> None:
        key = (getattr(node, "lineno", 0), getattr(node, "col_offset", 0), status, surface)
        if key in self._emitted:
            return
        self._emitted.add(key)
        self.findings.append(Finding(status, self.path, key[0], key[1] + 1, surface, detail))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "unreal":
                self.unreal_aliases.add(alias.asname or "unreal")

    def _infer_expr_type(self, node: ast.AST) -> str | None:
        chain = _chain(node, self.unreal_aliases)
        if chain == "unreal.Transform":
            return "Transform"
        if chain == "unreal.Rotator":
            return "Rotator"
        if chain == "unreal.Quat":
            return "Quat"
        if isinstance(node, ast.Call):
            call_chain = _chain(node.func, self.unreal_aliases)
            if call_chain in {"unreal.Transform", "unreal.MathLibrary.compose_transforms"}:
                return "Transform"
            if call_chain == "unreal.Rotator":
                return "Rotator"
            if call_chain == "unreal.Quat":
                return "Quat"
            if call_chain == "unreal.MovieSceneSequencePlaybackSettings":
                return "MovieSceneSequencePlaybackSettings"
            if call_chain == "unreal.EditorAssetLibrary.load_blueprint_class":
                return "UClass"
            if isinstance(node.func, ast.Attribute) and node.func.attr == "quaternion":
                return "Quat"
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get_editor_property" and node.args:
                prop = _literal_string(node.args[0])
                if prop == "camera_component":
                    return "CineCameraComponent"
                if prop == "root_component":
                    return "SceneComponent"
        if isinstance(node, ast.Name):
            return self.types.get(node.id)
        if isinstance(node, ast.Attribute):
            owner = self._infer_expr_type(node.value)
            if owner == "Transform" and node.attr == "rotation":
                return "Quat"
        return None

    def visit_Assign(self, node: ast.Assign) -> None:
        inferred = self._infer_expr_type(node.value)
        if inferred:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.types[target.id] = inferred
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None and isinstance(node.target, ast.Name):
            inferred = self._infer_expr_type(node.value)
            if inferred:
                self.types[node.target.id] = inferred
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        if (isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Attribute) and node.iter.func.attr == "get_keys"):
            self.types[node.target.id] = "MovieSceneScriptingKey"
        self.generic_visit(node)

    def _classify_direct(self, node: ast.AST, chain: str) -> None:
        rule = DENY_CHAINS.get(chain)
        if rule is None:
            for denied, candidate in DENY_CHAINS.items():
                if chain.startswith(denied + "."):
                    rule = candidate
                    break
        if rule:
            self.emit(node, "DENY", chain, f"{rule.reason}; {rule.replacement}")
        elif chain in ALLOW_CHAINS:
            self.emit(node, "ALLOW", chain, "live-success allow-list")
        else:
            self.emit(node, "UNKNOWN", chain, "not in the UE 5.8 deny- or allow-list")

    def _classify_method(self, node: ast.Call, method: str, receiver: ast.AST) -> None:
        if method in DENY_METHODS:
            rule = DENY_METHODS[method]
            self.emit(node.func, "DENY", "*." + method, f"{rule.reason}; {rule.replacement}")
            return
        receiver_type = self._infer_expr_type(receiver)
        if method == "rotator" and receiver_type == "Transform":
            self.emit(node.func, "DENY", "Transform.rotator", "use transform.rotation.rotator(); Transform has no rotator()")
        elif method == "rotate_vector" and receiver_type == "Rotator":
            self.emit(node.func, "DENY", "Rotator.rotate_vector", "use rotator.quaternion().rotate_vector(vector)")
        elif method == "get_actor_label" and receiver_type == "CineCameraComponent":
            self.emit(node.func, "DENY", "CineCameraComponent.get_actor_label", "components are not actors; use get_name() or the owning actor label")
        elif method == "set_actor_transform" and len(node.args) < 2 and not any(k.arg == "sweep" for k in node.keywords):
            self.emit(node.func, "DENY", "Actor.set_actor_transform", "UE 5.8 requires sweep; pass sweep=False (and teleport explicitly where required)")
        elif method == "set_groom_asset" and len(node.args) > 1:
            self.emit(node.func, "DENY", "GroomComponent.set_groom_asset(groom,binding,...)", "use separate set_groom_asset(groom) and set_binding_asset(binding) calls")
        elif method == "remove" and receiver_type == "MovieSceneScriptingKey":
            self.emit(node.func, "DENY", "MovieSceneScriptingKey.remove", "call the owning channel.remove_key(key)")

    def visit_Call(self, node: ast.Call) -> None:
        chain = _chain(node.func, self.unreal_aliases)
        if chain:
            self._classify_direct(node.func, chain)
        if isinstance(node.func, ast.Attribute):
            self._classify_method(node, node.func.attr, node.func.value)

            if node.func.attr == "set_property_name_and_path":
                values = {_literal_string(arg) for arg in node.args}
                if "CurrentFocalLength" in values:
                    self.emit(
                        node.func,
                        "DENY",
                        'MovieSceneFloatTrack("CurrentFocalLength")',
                        "the 10 Oct camera tool could not expose/create this track; keep focal length constant and author a transform-only dolly",
                    )

        if chain == "unreal.MovieSceneSequencePlaybackSettings":
            if any(keyword.arg == "restore_state" for keyword in node.keywords):
                self.emit(node.func, "DENY", "MovieSceneSequencePlaybackSettings(restore_state=...)", "restore_state is not exposed; snapshot/read back and restore state explicitly")
        if isinstance(node.func, ast.Name) and node.func.id == "isinstance" and len(node.args) >= 2:
            if self._infer_expr_type(node.args[1]) == "UClass":
                self.emit(node.func, "DENY", "isinstance(..., UClass)", "reflected UClass values are not Python types; compare Blueprint parent/object identities")

        # Visit arguments and receiver expressions, but not node.func: it was
        # already classified as one complete surface and would otherwise emit
        # every prefix as a duplicate finding.
        if isinstance(node.func, ast.Attribute):
            self.visit(node.func.value)
        for arg in node.args:
            self.visit(arg)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        parent = self.parents.get(node)
        if isinstance(parent, ast.Attribute) and parent.value is node:
            self.generic_visit(node)
            return
        if isinstance(parent, ast.Call) and parent.func is node:
            return
        if node.attr == "restore_state" and self._infer_expr_type(node.value) == "MovieSceneSequencePlaybackSettings":
            self.emit(node, "DENY", "MovieSceneSequencePlaybackSettings.restore_state", "the property is not exposed; snapshot/read back and restore state explicitly")
            return
        chain = _chain(node, self.unreal_aliases)
        if chain:
            self._classify_direct(node, chain)
            return
        self.generic_visit(node)


def scan_file(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    scanner = Scanner(path, tree)
    scanner.visit(tree)
    return sorted(scanner.findings, key=lambda item: (item.line, item.column, item.status, item.surface))


def python_files(targets: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for target in targets:
        if target.is_file() and target.suffix.lower() == ".py":
            found.add(target.resolve())
        elif target.is_dir():
            found.update(path.resolve() for path in target.rglob("*.py") if path.is_file())
        else:
            raise FileNotFoundError(str(target))
    return sorted(found, key=lambda path: str(path).lower())


def run(targets: Iterable[Path]) -> tuple[list[Finding], list[tuple[Path, str]]]:
    findings: list[Finding] = []
    errors: list[tuple[Path, str]] = []
    for path in python_files(targets):
        try:
            findings.extend(scan_file(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append((path, str(exc)))
    return findings, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", type=Path, help="Python file or directory to scan recursively")
    args = parser.parse_args(argv)
    try:
        findings, errors = run(args.targets)
    except FileNotFoundError as exc:
        print(f"ERROR missing target: {exc}", file=sys.stderr)
        return 2

    for finding in findings:
        suffix = f" - {finding.detail}" if finding.detail else ""
        print(f"{finding.status} {finding.path}:{finding.line}:{finding.column} {finding.surface}{suffix}")
    for path, error in errors:
        print(f"ERROR {path}: {error}", file=sys.stderr)

    counts = {status: sum(item.status == status for item in findings) for status in ("DENY", "UNKNOWN", "ALLOW")}
    print("SUMMARY files=%d deny=%d unknown=%d allow=%d errors=%d" %
          (len(python_files(args.targets)), counts["DENY"], counts["UNKNOWN"], counts["ALLOW"], len(errors)))
    if errors:
        return 2
    return 1 if counts["DENY"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
