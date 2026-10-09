"""Offline positive/negative harness for P32 Scene 3 backdrop v3.

This harness never imports Unreal, never calls the production Real-ESRGAN path,
and creates only a tiny synthetic RGB fixture in a temporary directory.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
BUILDER_PATH = PROJECT / "Tools" / "FlatV3" / "build_scene3_backdrop_v3.py"
UE_PATH = HERE / "s3_backdrop_v3_ue.py"
REPORT_PATH = HERE / "test_s3_backdrop_v3_offline_report.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = load_module("p32_s3_backdrop_v3_builder", BUILDER_PATH)
ue = load_module("p32_s3_backdrop_v3_ue", UE_PATH)


positive = []
negative = []


def check(name, condition, detail=""):
    if not condition:
        raise AssertionError("%s: %s" % (name, detail))
    positive.append(name)


def rejects(name, function, expected):
    try:
        function()
    except Exception as exc:
        if expected not in str(exc):
            raise AssertionError("%s rejected for wrong reason: %s" % (name, exc))
        negative.append({"name": name, "reason": str(exc)})
        return
    raise AssertionError("negative control did not reject: " + name)


crop = builder.exact_two_by_three_crop(builder.EXPECTED_SOURCE_SIZE)
check("crop_box_exact", crop == (6, 1, 1690, 2527), crop)
check("crop_ratio_exact", (crop[2] - crop[0]) * 3 == (crop[3] - crop[1]) * 2)
builder.validate_pot_size((4096, 8192))
check("pot_contract_accepts", True)
rect = builder.leaf_uv_rect(builder.LOWERED_BACKDROP_BOTTOM_Z_CM)
builder.validate_lowered_leaf_rect(rect)
check("lowered_leaf_rect_exact",
      max(abs(a - b) for a, b in zip(rect, builder.EXPECTED_LEAF_RECT)) < 1.0e-12)
old_rect = builder.leaf_uv_rect(builder.ORIGINAL_BACKDROP_BOTTOM_Z_CM)
check("leaf_rect_shift_is_point05_v", abs((old_rect[1] - rect[1]) - 0.05) < 1.0e-12 and
      abs((old_rect[3] - rect[3]) - 0.05) < 1.0e-12)
plan = builder.build_plan(Path("fixture.jpg"), Path("out"), builder.EXPECTED_SOURCE_SIZE)
check("paint_as_is", plan["local_stroke_edits"] == 0)
check("production_plan_pot", plan["pot_output_size_px"] == [4096, 8192])
check("production_plan_uses_existing_upscaler", plan["upscale"]["function"].endswith(":realesrgan_2x"))

calls = []


def tiny_cpu_upscale(rgb):
    calls.append(rgb.shape)
    result = np.repeat(np.repeat(rgb, 2, axis=0), 2, axis=1)
    return result, {"device": "cpu-test-double", "delivered_scale": 2, "production_cuda_run": False}


with tempfile.TemporaryDirectory(prefix="p32-s3-backdrop-v3-") as temp:
    temp = Path(temp)
    fixture = np.zeros((36, 24, 3), dtype=np.uint8)
    fixture[:, :, 0] = np.arange(24, dtype=np.uint8)[None, :] * 7
    fixture[:, :, 1] = np.arange(36, dtype=np.uint8)[:, None] * 5
    fixture[:, :, 2] = 117
    source = temp / "tiny.jpg"
    Image.fromarray(fixture, "RGB").save(source, quality=96)
    output = temp / "output"
    report = builder.build(source, output, upscale_fn=tiny_cpu_upscale,
                           test_pot_size=(32, 64), test_leaf_size=(8, 16))
    check("tiny_cpu_upscaler_called_once", calls == [(36, 24, 3)], calls)
    check("tiny_pot_written", report["outputs"]["backdrop_texture"]["size_px"] == [32, 64])
    check("tiny_leaf_written", report["outputs"]["leaf_texture"]["size_px"] == [8, 16])
    check("qa_written", Path(report["plan"]["files"]["qa"]).is_file())


settings = {field: "fixture-" + field for field in ue.TEXTURE_SETTING_FIELDS}
state = {
    "world": ue.WORLD,
    "actors": {
        "backdrop": {
            "label": ue.BACKDROP_LABEL, "object_path": "/Game/Test.Backdrop",
            "component_name": "StaticMeshComponent0", "material": "/Game/Old/BackdropMI",
            "skin_color": "/Game/Old/BackdropTex", "texture_settings": settings,
            "hidden": False,
        },
        "leaf": {
            "label": ue.LEAF_LABEL, "object_path": "/Game/Test.Leaf",
            "component_name": "StaticMeshComponent0", "material": "/Game/Old/LeafMI",
            "skin_color": "/Game/Old/LeafTex", "texture_settings": settings,
            "hidden": True,
        },
    },
    "new_asset_exists": {path: False for path in ue.NEW_ASSETS},
}
contract = {
    "paths": {"backdrop_png": "backdrop.png", "leaf_png": "leaf.png"},
    "sha256": {"backdrop_texture": "a" * 64, "leaf_texture": "b" * 64},
    "leaf_uv_rect": ue.leaf_uv_rect(-155.0), "local_stroke_edits": 0,
}
ue_plan = ue.build_plan(state, contract)
check("ue_plan_four_create_only_assets", ue_plan["new_assets"] == list(ue.NEW_ASSETS))
check("backdrop_child_of_live_mi", ue_plan["actors"]["backdrop"]["new_material_parent"] == "/Game/Old/BackdropMI")
check("leaf_child_of_live_mi", ue_plan["actors"]["leaf"]["new_material_parent"] == "/Game/Old/LeafMI")
ue.validate_param_swap_only(ue_plan)
check("param_swap_only", all(row["texture_overrides"] == {"SkinColor": row["new_texture"]}
                              for row in ue_plan["actors"].values()))
check("dry_mode_default", ue.check_mode({}, False) == "DRY")
check("apply_confirm", ue.check_mode({"mode": "APPLY", "confirm": "APPLY S3BACKDROPV3"}, False) == "APPLY")
check("revert_confirm", ue.check_mode({"mode": "REVERT", "confirm": "REVERT S3BACKDROPV3"}, True) == "REVERT")


rejects("crop_ratio_mutation", lambda: builder.validate_crop_box((0, 0, 10, 14)), "not exactly 2:3")
rejects("pot_size_mutation", lambda: builder.validate_pot_size((4096, 8000)), "must be 4096x8192")


def mutate_param_swap():
    mutated = json.loads(json.dumps(ue_plan))
    mutated["actors"]["leaf"]["texture_overrides"]["SkinNormal"] = "/Game/Bad/Normal"
    ue.validate_param_swap_only(mutated)


rejects("param_swap_mutation", mutate_param_swap, "PARAM_SWAP_ONLY")


def use_pre_lowering_rect():
    mutated = dict(contract)
    mutated["leaf_uv_rect"] = ue.leaf_uv_rect(-5.0)
    ue.build_plan(state, mutated)


rejects("lowered_mural_offset_mutation", use_pre_lowering_rect, "LOWERED_LEAF_RECT")

source_text = UE_PATH.read_text(encoding="utf-8")
check("no_asset_deletion", "delete_asset" not in source_text and "destroy_actor" not in source_text)
check("import_is_create_only", '"replace_existing", False' in source_text)
check("all_three_modes_present", all(token in source_text for token in ('"DRY"', '"APPLY"', '"REVERT"')))

result = {
    "suite": "P32 S3 backdrop v3 offline",
    "positive_pass": len(positive),
    "negative_controls_pass": len(negative),
    "positive_cases": positive,
    "negative_controls": negative,
    "gpu_or_cuda_run": False,
    "unreal_or_mcp_run": False,
    "fixture": "24x36 synthetic RGB; injected CPU nearest-repeat 2x test double",
}
REPORT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print("S3_BACKDROP_V3_OFFLINE_OK|positive=%d|negative=%d|gpu=0|unreal=0|report=%s" %
      (len(positive), len(negative), REPORT_PATH))
