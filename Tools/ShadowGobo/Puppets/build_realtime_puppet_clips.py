"""Build the offline 25 fps boy/Puss gobo review artifacts.

Modes are deliberately explicit:

* DRY: print the named-output plan; write nothing.
* APPLY: require ``APPLY_PUPPET_RT_<run-id>``; back up/record first, then write
  only the named artifacts and verify their hashes.
* REVERT: require ``REVERT_PUPPET_RT_<run-id>``; move current artifacts to a
  recoverable Backups folder and restore the recorded predecessors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
PROJECT_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOL_DIR))

import boy_rig  # noqa: E402
import cat_rig  # noqa: E402
import gobo_twin  # noqa: E402
import pack_rig_flipbook  # noqa: E402


DEFAULT_PARAMS = {"BorderDepth": 1.0, "BorderAspect": 1.88, "Scale": 0.7071, "Defocus": 0.25}
BOY_ROOT = HERE / "clip_rub_rt"
CAT_ROOT = HERE / "clip_puss_rt"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")


def git_census():
    result = subprocess.run(["git", "status", "--short"], cwd=PROJECT_ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    packages = [line for line in dirty if line.lower().endswith((".uasset", ".umap"))]
    return {"dirty_packages": packages, "dirty_package_count": len(packages), "source_dirty": dirty,
            "git_status_exit": result.returncode}


def output_plan():
    return {
        "boy": ["atlas/T_Gobo_BoyRubRT_<grid>.png", "atlas/manifest.json",
                "atlas/cells_contact.png", "twin_ue.gif", "softness_compare_015_025_035.png"],
        "puss": ["atlas/T_Gobo_PussRT_<grid>.png", "atlas/manifest.json", "atlas/cells_contact.png"],
        "display_fps": 25.0,
        "unreal_packages_saved": [],
        "unreal_apply": False,
    }


def add_render_metadata(manifest_path, result, max_cells, face_swap, tear_speed=None):
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    data["clip_render"] = {
        "display_fps": data["display_fps"],
        "move_frames": {str(key): value for key, value in result.move_frames.items()},
        "original_move_frames": {str(key): value for key, value in result.original_move_frames.items()},
        "max_cells": max_cells,
        "reductions": result.reductions,
        "quantization": {"angles_and_targets": 0.01},
        "face_swap": face_swap,
        "tear_speed": tear_speed,
        "handheld_wobble_baked": False,
    }
    Path(manifest_path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_softness_comparison(manifest_path, out_path, at=3.8):
    panels = []
    for defocus in (0.15, 0.25, 0.35):
        params = dict(DEFAULT_PARAMS, Defocus=defocus)
        frames, _band, _fps = gobo_twin.render_images(manifest_path, params=params, times=[at])
        panel = frames[0].convert("RGB")
        ImageDraw.Draw(panel).rectangle((0, 0, 150, 28), fill=(245, 235, 220))
        ImageDraw.Draw(panel).text((8, 7), "Defocus %.2f" % defocus, fill=(25, 22, 22))
        panels.append(panel)
    sheet = Image.new("RGB", (sum(panel.width for panel in panels), max(panel.height for panel in panels)), "white")
    x = 0
    for panel in panels:
        sheet.paste(panel, (x, 0))
        x += panel.width
    sheet.save(out_path)


def build_scratch(root, atlas, max_cells, cell_px):
    boy_frames = root / "boy_frames"
    boy_atlas = root / "boy" / "atlas"
    cat_frames = root / "cat_frames"
    cat_atlas = root / "cat" / "atlas"

    boy_keys, boy_length = boy_rig.rubbing_eyes_clip()
    boy_result = boy_rig.render_clip(boy_keys, boy_length, boy_frames, fps=25.0,
                                     cell_px=cell_px, max_cells=max_cells,
                                     tear_speed=0.45, face_swap=0.5)
    boy_manifest = pack_rig_flipbook.pack(boy_frames, boy_atlas, "BoyRubRT", 25.0,
                                          atlas_px=atlas, preview=True)
    add_render_metadata(boy_atlas / "manifest.json", boy_result, max_cells, 0.5, 0.45)

    cat_keys, cat_length = cat_rig.realtime_clip()
    cat_result = cat_rig.render_realtime_clip(cat_keys, cat_length, cat_frames, fps=25.0,
                                              cell_px=cell_px, max_cells=max_cells, face_swap=0.5)
    cat_manifest = pack_rig_flipbook.pack(cat_frames, cat_atlas, "PussRT", 25.0,
                                          atlas_px=atlas, preview=True)
    add_render_metadata(cat_atlas / "manifest.json", cat_result, max_cells, 0.5)

    twin_frames, _band, twin_fps = gobo_twin.render_images(
        boy_atlas / "manifest.json", params=DEFAULT_PARAMS, fps=25.0, px=520,
    )
    twin_path = root / "boy" / "twin_ue.gif"
    twin_frames[0].save(twin_path, save_all=True, append_images=twin_frames[1:],
                        duration=int(round(1000.0 / twin_fps)), loop=0)
    softness_path = root / "boy" / "softness_compare_015_025_035.png"
    make_softness_comparison(boy_atlas / "manifest.json", softness_path)

    files = [
        (boy_atlas / boy_manifest["atlas"]["file"], BOY_ROOT / "atlas" / boy_manifest["atlas"]["file"]),
        (boy_atlas / "manifest.json", BOY_ROOT / "atlas" / "manifest.json"),
        (boy_atlas / "cells_contact.png", BOY_ROOT / "atlas" / "cells_contact.png"),
        (twin_path, BOY_ROOT / "twin_ue.gif"),
        (softness_path, BOY_ROOT / "softness_compare_015_025_035.png"),
        (cat_atlas / cat_manifest["atlas"]["file"], CAT_ROOT / "atlas" / cat_manifest["atlas"]["file"]),
        (cat_atlas / "manifest.json", CAT_ROOT / "atlas" / "manifest.json"),
        (cat_atlas / "cells_contact.png", CAT_ROOT / "atlas" / "cells_contact.png"),
    ]
    return files, {"boy": boy_manifest, "puss": cat_manifest}


def record_path(run_id):
    return PROJECT_ROOT / "Backups" / ("PrePuppetRealtimeMoves-" + run_id) / "record.json"


def apply(run_id, confirm, atlas, max_cells, cell_px):
    expected = "APPLY_PUPPET_RT_" + run_id
    if confirm != expected:
        raise SystemExit("confirmation mismatch; expected %s" % expected)
    with tempfile.TemporaryDirectory(prefix="puppet_rt_build_") as temp:
        scratch = Path(temp)
        files, manifests = build_scratch(scratch, atlas, max_cells, cell_px)
        backup_root = record_path(run_id).parent
        if backup_root.exists():
            raise SystemExit("backup run already exists: %s" % backup_root)
        backup_root.mkdir(parents=True)
        record = {
            "schema_version": 1,
            "run_id": run_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "mode": "APPLY",
            "confirm": expected,
            "census": git_census(),
            "unreal_access": False,
            "unreal_packages_saved": [],
            "targets": [],
            "success_marker": None,
        }
        for _source, target in files:
            entry = {"path": relative(target), "existed": target.is_file(),
                     "pre_sha256": sha256(target) if target.is_file() else None}
            if target.is_file():
                saved = backup_root / "files" / relative(target)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
                entry["backup"] = relative(saved)
            record["targets"].append(entry)
        record_path(run_id).write_text(json.dumps(record, indent=2), encoding="utf-8")

        for source, target in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        expected_hashes = {relative(target): sha256(source) for source, target in files}
        actual_hashes = {relative(target): sha256(target) for _source, target in files}
        if expected_hashes != actual_hashes:
            raise SystemExit("read-back hash mismatch")
        marker = "PUPPET_RT_APPLY_OK|run=%s|files=%d|dirty_packages=%d" % (
            run_id, len(files), record["census"]["dirty_package_count"])
        record["post_sha256"] = actual_hashes
        record["cell_budget"] = {
            name: manifest["cell_budget"] for name, manifest in manifests.items()
        }
        record["success_marker"] = marker
        record_path(run_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
        reread = json.loads(record_path(run_id).read_text(encoding="utf-8"))
        if reread["success_marker"] != marker:
            raise SystemExit("record read-back failed")
        print(marker)


def revert(run_id, confirm):
    expected = "REVERT_PUPPET_RT_" + run_id
    if confirm != expected:
        raise SystemExit("confirmation mismatch; expected %s" % expected)
    path = record_path(run_id)
    if not path.is_file():
        raise SystemExit("record not found: %s" % path)
    record = json.loads(path.read_text(encoding="utf-8"))
    stash = PROJECT_ROOT / "Backups" / ("RevertedPuppetRealtimeMoves-" + run_id)
    if stash.exists():
        raise SystemExit("revert stash already exists: %s" % stash)
    stash.mkdir(parents=True)
    for entry in record["targets"]:
        target = PROJECT_ROOT / entry["path"]
        if target.is_file():
            saved_current = stash / "replaced" / entry["path"]
            saved_current.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(target, saved_current)
        if entry["existed"]:
            original = PROJECT_ROOT / entry["backup"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
    marker = "PUPPET_RT_REVERT_OK|run=%s|files=%d" % (run_id, len(record["targets"]))
    (stash / "revert_record.json").write_text(json.dumps({"run_id": run_id, "marker": marker}, indent=2),
                                               encoding="utf-8")
    print(marker)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("DRY", "APPLY", "REVERT"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--atlas", type=int, default=8192, choices=(4096, 8192))
    parser.add_argument("--max-cells", type=int, default=196)
    parser.add_argument("--source-cell-px", type=int, default=640)
    args = parser.parse_args(argv)
    if args.mode == "DRY":
        print(json.dumps({"mode": "DRY", "run_id": args.run_id, "plan": output_plan(),
                          "census": git_census(), "apply_confirm": "APPLY_PUPPET_RT_" + args.run_id,
                          "revert_confirm": "REVERT_PUPPET_RT_" + args.run_id}, indent=2))
        print("PUPPET_RT_DRY_OK|run=%s" % args.run_id)
    elif args.mode == "APPLY":
        apply(args.run_id, args.confirm, args.atlas, args.max_cells, args.source_cell_px)
    else:
        revert(args.run_id, args.confirm)


if __name__ == "__main__":
    main()
