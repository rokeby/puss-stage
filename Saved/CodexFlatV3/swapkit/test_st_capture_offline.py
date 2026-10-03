#!/usr/bin/env python3
"""Fake-Unreal/static offline test for the read-only ST capture contract."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
from pathlib import Path


HERE = Path(__file__).resolve().parent


class Vector:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class FakeMI:
    def __init__(self, textures):
        self.textures = textures


def install_modules(rows, mode="before"):
    unreal = types.ModuleType("unreal")
    unreal.Vector = Vector
    unreal.MaterialInstanceConstant = FakeMI
    unreal.Actor = type("Actor", (), {})
    actors = [types.SimpleNamespace(get_path_name=lambda value=value: value)
              for value in ("/Game/Map.A", "/Game/Map.B")]
    unreal.GameplayStatics = types.SimpleNamespace(
        get_all_actors_of_class=lambda _world, _kind: actors
    )
    sys.modules["unreal"] = unreal

    common = types.ModuleType("sk_common")
    common.HERE = str(HERE)
    common.KINDS = ("SkinColor", "SkinMask", "SkinNormal")
    common.CLEAN = {"content": [], "maps": []}
    assets = {}
    for row in rows:
        selected = row["old_textures"] if mode == "before" else row["new_textures"]
        assets[row["mi"]] = FakeMI(dict(selected))
    common.load_asset = lambda path, _kind=None: assets[path]
    common.mi_textures = lambda instance: dict(instance.textures)
    sys.modules["sk_common"] = common
    return unreal, common, assets


def load_capture():
    path = HERE / "st_capture.py"
    spec = importlib.util.spec_from_file_location("st_capture_offline_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_failure(callable_value, marker):
    try:
        callable_value()
    except Exception as exc:
        if marker not in str(exc):
            raise RuntimeError("WRONG_FAILURE|wanted=%s|actual=%s" % (marker, exc))
        return str(exc)
    raise RuntimeError("NEGATIVE_CONTROL_DID_NOT_FAIL|wanted=" + marker)


def main() -> int:
    cfg = json.loads((HERE / "run_sk.json").read_text(encoding="utf-8"))
    rows = [next(row for row in cfg["rows"] if row["passage"] == passage)
            for passage in ("P01", "P02", "P03", "P04", "P05", "P06")]
    unreal, common, assets = install_modules(rows, "before")
    capture = load_capture()
    state, per_passage = capture.classify({"rows": rows})
    if state != "before" or set(per_passage.values()) != {"before"}:
        raise RuntimeError("ST_FAKE_BEFORE_CLASSIFICATION_FAIL")
    for row in rows:
        assets[row["mi"]].textures = dict(row["new_textures"])
    state_after, _ = capture.classify({"rows": rows})
    if state_after != "after":
        raise RuntimeError("ST_FAKE_AFTER_CLASSIFICATION_FAIL")
    assets[rows[0]["mi"]].textures["SkinMask"] = "/Game/Fake/Mixed"
    mixed_failure = expect_failure(
        lambda: capture.classify({"rows": rows}), "ST_MI_STATE_MIXED"
    )
    jobs = capture.make_jobs(Vector)
    if len(jobs) != 12:
        raise RuntimeError("ST_JOB_COUNT_FAIL")
    p04_front = next(job for job in jobs
                     if job["passage"] == "P04" and job["view"] == "front_on_pair")
    if (p04_front["location"].x, p04_front["location"].y, p04_front["location"].z) != (3250.0, 240000.0, 500.0):
        raise RuntimeError("ST_P04_POSE_FAIL")
    if capture.actor_census(object()) != ["/Game/Map.A", "/Game/Map.B"]:
        raise RuntimeError("ST_ACTOR_CENSUS_FAIL")

    source = (HERE / "st_capture.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        "save_asset", "save_loaded_asset", "save_loaded_assets", "spawn_actor_from_class",
        "spawn_actor", "destroy_actor", "set_actor_location", "set_actor_transform",
    }
    found = sorted({node.attr for node in ast.walk(tree)
                    if isinstance(node, ast.Attribute) and node.attr in forbidden_calls})
    if found:
        raise RuntimeError("ST_FORBIDDEN_MUTATION_CALLS|" + json.dumps(found))
    if "auto_exposure" in source.lower() or "post_process" in source.lower():
        raise RuntimeError("ST_EXPOSURE_OVERRIDE_TOKEN_FOUND")
    if "DisableAllScreenMessages" not in source or "EnableAllScreenMessages" not in source:
        raise RuntimeError("ST_MESSAGE_TOGGLE_MISSING")
    if "_fv3_sys.modules" not in source:
        raise RuntimeError("ST_STALE_MODULE_PURGE_MISSING")

    report = {
        "schema_version": 1,
        "status": "PASS",
        "execution": {"offline": True, "unreal": False, "fake_unreal": True,
                      "mcp": False, "port_8010": False},
        "controls": {
            "before_classification": "PASS",
            "after_classification": "PASS",
            "mixed_state_fails": mixed_failure,
            "jobs_12": True,
            "p04_measured_pose": True,
            "read_only_ast": True,
            "no_exposure_override_tokens": True,
            "messages_off_and_restore": True,
            "actor_census_uses_gameplay_statics": True,
            "stale_module_purge": True,
        },
    }
    output = HERE / "test_st_capture_offline_report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "jobs": len(jobs),
                      "report": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

