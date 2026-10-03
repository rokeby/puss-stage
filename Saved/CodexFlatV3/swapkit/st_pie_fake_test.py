#!/usr/bin/env python3
"""Fake-Unreal tests for the Flat V3 owned-PIE still driver."""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


HERE = Path(__file__).resolve().parent


class FakeMI:
    def __init__(self, textures):
        self.textures = textures


class FakeWorld:
    def __init__(self, name):
        self.name = name

    def get_path_name(self):
        return self.name


class FakeCamera:
    def __init__(self, world):
        self.world = world

    def get_world(self):
        return self.world


class FakeEditor:
    def __init__(self, game_world=None):
        self.game_world = game_world

    def get_game_world(self):
        return self.game_world


def install_fake_modules(rows, state="before"):
    unreal = types.ModuleType("unreal")
    unreal.MaterialInstanceConstant = FakeMI
    unreal.Actor = type("Actor", (), {})
    unreal.UnrealEditorSubsystem = type("UnrealEditorSubsystem", (), {})
    editor = FakeEditor()
    unreal.get_editor_subsystem = lambda _kind: editor
    sys.modules["unreal"] = unreal

    common = types.ModuleType("sk_common")
    common.KINDS = ("SkinColor", "SkinMask", "SkinNormal")
    common.CLEAN = {"content": [], "maps": []}
    common.config = lambda: {"rows": rows}
    assets = {}
    for row in rows:
        selected = row["old_textures"] if state == "before" else row["new_textures"]
        assets[row["mi"]] = FakeMI(dict(selected))
    common.load_asset = lambda path, _kind=None: assets[path]
    common.mi_textures = lambda instance: dict(instance.textures)
    sys.modules["sk_common"] = common
    return unreal, common, editor, assets


def load_driver():
    spec = importlib.util.spec_from_file_location(
        "st_pie_stills_driver_fake", HERE / "st_pie_stills_driver.py"
    )
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


def rows_fixture():
    rows = []
    for passage in ("P01", "P02", "P03", "P04", "P05", "P06"):
        rows.append({
            "passage": passage,
            "mi": "/Game/Fake/MI_" + passage,
            "old_textures": {kind: "/Old/%s_%s" % (passage, kind)
                             for kind in ("SkinColor", "SkinMask", "SkinNormal")},
            "new_textures": {kind: "/New/%s_%s" % (passage, kind)
                             for kind in ("SkinColor", "SkinMask", "SkinNormal")},
        })
    return rows


def main():
    rows = rows_fixture()
    _unreal, _common, editor, assets = install_fake_modules(rows)
    driver = load_driver()

    capture_state, passages = driver.classify({"rows": rows})
    if capture_state != "before" or set(passages.values()) != {"before"}:
        raise RuntimeError("ST_PIE_BEFORE_CLASSIFICATION_FAIL")
    assets[rows[0]["mi"]].textures["SkinMask"] = "/Mixed/Mask"
    mixed = expect_failure(
        lambda: driver.classify({"rows": rows}), "ST_PIE_MI_STATE_MIXED"
    )

    jobs = []
    for number in range(1, 7):
        passage = "P%02d" % number
        start = number * 1_000_000
        end = start + 900_000
        cue_rows = [
            {"cue_index": number * 10 + i, "cue_guid": "%s-%d" % (passage, i),
             "cue_label": "%s Wing %03d" % (passage, i + 1),
             "interval_to_next": 120_000, "swapped": True}
            for i in range(6)
        ]
        jobs.extend(driver.derive_passage_jobs(passage, start, end, 60_000, cue_rows))
    if len(jobs) != 12 or {job["view"] for job in jobs} != {"walk", "front"}:
        raise RuntimeError("ST_PIE_POSITIVE_12_SHOTS_FAIL")
    if any(not (job["passage_range"][0] <= job["master_frame"] <= job["passage_range"][1])
           for job in jobs):
        raise RuntimeError("ST_PIE_FRAME_RANGE_FAIL")
    if driver.MAX_SHOT_ERROR_FRAMES != 624:
        raise RuntimeError("ST_PIE_26MS_TOLERANCE_FAIL")

    clean_before = {"content": [], "maps": []}
    clean_after = {"content": [], "maps": []}
    driver.assert_clean_package_census(clean_before, "BEFORE")
    driver.assert_clean_package_census(clean_after, "AFTER")

    game_world = FakeWorld("/Game/Map/UEDPIE_0_Map")
    editor_world = FakeWorld("/Game/Map/Map")
    expect_failure(
        lambda: driver.assert_game_camera(FakeCamera(editor_world), game_world, editor_world),
        "ST_PIE_CAMERA_NOT_GAME_WORLD",
    )
    driver.assert_game_camera(FakeCamera(game_world), game_world, editor_world)

    editor.game_world = game_world
    preexisting = expect_failure(
        lambda: driver.assert_no_preexisting_pie(editor),
        "ST_PIE_ALREADY_RUNNING",
    )

    source = (HERE / "st_pie_stills_driver.py").read_text(encoding="utf-8")
    required = [
        "DisableAllScreenMessages", "EnableAllScreenMessages", "HighResShot",
        "editor_request_end_play", "saved_count=0", "FLATV3_STB_OK", "FLATV3_STA_OK",
        "begin_deferred_actor_spawn_from_class", "assert_game_camera",
    ]
    missing = [token for token in required if token not in source]
    if missing:
        raise RuntimeError("ST_PIE_REQUIRED_SOURCE_TOKENS_MISSING|" + json.dumps(missing))
    if "EditorLevelLibrary.spawn_actor" in source:
        raise RuntimeError("ST_PIE_EDITOR_WORLD_SPAWN_TOKEN_FOUND")
    if "auto_exposure" in source.lower() or "post_process" in source.lower():
        raise RuntimeError("ST_PIE_EXPOSURE_OVERRIDE_TOKEN_FOUND")

    print(json.dumps({
        "status": "PASS",
        "execution": {"offline": True, "fake_unreal": True, "unreal": False,
                      "mcp": False, "port_8010": False},
        "positive": {"shots": len(jobs), "census_before": clean_before,
                     "census_after": clean_after},
        "negative": {"preexisting_pie": preexisting,
                     "editor_world_camera": "ST_PIE_CAMERA_NOT_GAME_WORLD",
                     "mixed_mi_state": mixed},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
