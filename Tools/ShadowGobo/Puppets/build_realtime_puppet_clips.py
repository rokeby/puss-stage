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
SDF_BOY_ROOT = HERE / "clip_rub_rt_sdf"
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


def output_plan(sdf=False):
    if sdf:
        return {
            "boy_sdf": ["atlas/T_Gobo_BoyRubRT_SDF_<grid>.png", "atlas/manifest.json",
                        "atlas/cells_contact.png", "twin_ue.gif", "edge_zoom_comparison.png",
                        "minimum_feature_widths.json"],
            "display_fps": 25.0,
            "unreal_packages_saved": [],
            "unreal_apply": False,
        }
    return {
        "boy": ["atlas/T_Gobo_BoyRubRT_<grid>.png", "atlas/manifest.json",
                "atlas/cells_contact.png", "twin_ue.gif", "softness_compare_015_025_035.png"],
        "puss": ["atlas/T_Gobo_PussRT_<grid>.png", "atlas/manifest.json", "atlas/cells_contact.png"],
        "display_fps": 25.0,
        "unreal_packages_saved": [],
        "unreal_apply": False,
    }


def add_render_metadata(manifest_path, result, max_cells, face_swap, tear_speed=None,
                        render_scale=1.0, target_inner_px=None):
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
    if target_inner_px is not None:
        data["clip_render"]["render_scale"] = float(render_scale)
        data["clip_render"]["target_inner_px"] = int(target_inner_px)
        data["clip_render"]["source_frame_px"] = int(round(target_inner_px * render_scale))
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


def make_edge_zoom_comparison(sdf_manifest_path, out_path, at=3.8):
    """Compare the current hard atlas with the new SDF at the same boy pose."""
    cases = [
        ("Current hard 8192 | Softness 0.08", BOY_ROOT / "atlas" / "manifest.json",
         dict(DEFAULT_PARAMS, Defocus=0.0, Softness=0.08)),
        ("SDF 8192 | Softness 0.02", sdf_manifest_path,
         dict(DEFAULT_PARAMS, Defocus=0.0, Softness=0.02)),
        ("SDF 8192 | Softness 0.02 | Defocus 0.25", sdf_manifest_path,
         dict(DEFAULT_PARAMS, Defocus=0.25, Softness=0.02)),
    ]
    panels = []
    for label, manifest, params in cases:
        frames, _band, _fps = gobo_twin.render_images(manifest, params=params, times=[at], px=1800)
        image = frames[0].convert("RGB")
        crop = image.crop((int(image.width * 0.38), 0, int(image.width * 0.76), int(image.height * 0.72)))
        crop = crop.resize((760, 760), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(crop)
        draw.rectangle((0, 0, 760, 34), fill=(20, 20, 20))
        draw.text((8, 9), label, fill=(255, 255, 255))
        panels.append(crop)
    sheet = Image.new("RGB", (760 * len(panels), 760), (20, 20, 20))
    for index, panel in enumerate(panels):
        sheet.paste(panel, (index * 760, 0))
    sheet.save(out_path)


def boy_feature_report(actual_inner_px, atlas_px, gutter_px=8, planning_cells=196):
    """Declared construction widths projected into the atlas-cell interior."""
    window_world = 1450.0
    features = {"main_and_arm_rods": 5.0, "narrowest_clip_slit": 4.0}

    def projection(inner_px):
        result = {}
        for name, world_width in features.items():
            width_px = world_width * inner_px / window_world
            result[name] = {
                "world_width": world_width,
                "cell_px": round(width_px, 4),
                "meets_2px": width_px + 1e-9 >= 2.0,
                "warning": pack_rig_flipbook.feature_width_warning(width_px, label=name),
            }
        return result

    planning_budget = pack_rig_flipbook.atlas_budget(planning_cells, atlas_px)
    planning_inner = planning_budget["cell_px"] - 2 * gutter_px
    return {
        "schema_version": 1,
        "claims": [
            {"tier": "declaration-proven", "claim": "Boy rods are authored at width 5 world units.",
             "evidence": "Tools/ShadowGobo/Puppets/boy_rig.py:295"},
            {"tier": "declaration-proven", "claim": "The narrowest slit used by the rub clip is width 4 world units.",
             "evidence": "Tools/ShadowGobo/Puppets/boy_rig.py:94,103,440-454"},
            {"tier": "measured", "claim": "Widths below are projected into cell pixels from the 1450-unit clip window.",
             "evidence": "Tools/ShadowGobo/Puppets/boy_rig.py:503-508"},
        ],
        "minimum_required_px": 2.0,
        "actual_clip": {"atlas_px": atlas_px, "inner_px": actual_inner_px,
                        "features": projection(actual_inner_px)},
        "planning_case": {"cells": planning_cells, "cols": planning_budget["cols"],
                          "cell_px": planning_budget["cell_px"], "inner_px": planning_inner,
                          "features": projection(planning_inner)},
    }


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


def build_sdf_scratch(root, atlas, max_cells, cell_px, render_scale, spread, wide):
    probe_frames = root / "boy_probe_frames"
    boy_frames = root / "boy_sdf_frames"
    boy_root = root / "boy_sdf"
    boy_atlas = boy_root / "atlas"
    boy_keys, boy_length = boy_rig.rubbing_eyes_clip()

    probe = boy_rig.render_clip(boy_keys, boy_length, probe_frames, fps=25.0,
                                cell_px=cell_px, max_cells=max_cells,
                                tear_speed=0.45, face_swap=0.5)
    budget = pack_rig_flipbook.atlas_budget(probe.unique_cells, atlas)
    target_inner = budget["cell_px"] - 16
    boy_result = boy_rig.render_clip(boy_keys, boy_length, boy_frames, fps=25.0,
                                     cell_px=target_inner, render_scale=render_scale,
                                     max_cells=max_cells, tear_speed=0.45, face_swap=0.5)
    if boy_result.unique_cells != probe.unique_cells:
        raise RuntimeError("SDF render changed unique-cell count (%d -> %d)" %
                           (probe.unique_cells, boy_result.unique_cells))
    boy_manifest = pack_rig_flipbook.pack(
        boy_frames, boy_atlas, "BoyRubRT_SDF", 25.0, atlas_px=atlas, preview=True,
        sdf=True, spread=spread, wide=wide,
    )
    add_render_metadata(boy_atlas / "manifest.json", boy_result, max_cells, 0.5, 0.45,
                        render_scale=render_scale, target_inner_px=target_inner)

    twin_frames, _band, twin_fps = gobo_twin.render_images(
        boy_atlas / "manifest.json", params=DEFAULT_PARAMS, fps=25.0, px=520,
    )
    twin_path = boy_root / "twin_ue.gif"
    twin_frames[0].save(twin_path, save_all=True, append_images=twin_frames[1:],
                        duration=int(round(1000.0 / twin_fps)), loop=0)
    comparison_path = boy_root / "edge_zoom_comparison.png"
    make_edge_zoom_comparison(boy_atlas / "manifest.json", comparison_path)
    feature_path = boy_root / "minimum_feature_widths.json"
    feature_path.write_text(json.dumps(boy_feature_report(target_inner, atlas), indent=2), encoding="utf-8")

    files = [
        (boy_atlas / boy_manifest["atlas"]["file"], SDF_BOY_ROOT / "atlas" / boy_manifest["atlas"]["file"]),
        (boy_atlas / "manifest.json", SDF_BOY_ROOT / "atlas" / "manifest.json"),
        (boy_atlas / "cells_contact.png", SDF_BOY_ROOT / "atlas" / "cells_contact.png"),
        (twin_path, SDF_BOY_ROOT / "twin_ue.gif"),
        (comparison_path, SDF_BOY_ROOT / "edge_zoom_comparison.png"),
        (feature_path, SDF_BOY_ROOT / "minimum_feature_widths.json"),
    ]
    return files, {"boy_sdf": boy_manifest}


def record_path(run_id, sdf=False):
    prefix = "PrePuppetRealtimeSDF-" if sdf else "PrePuppetRealtimeMoves-"
    return PROJECT_ROOT / "Backups" / (prefix + run_id) / "record.json"


def apply(run_id, confirm, atlas, max_cells, cell_px, sdf=False, render_scale=2.0, spread=6.0, wide=4.0):
    expected = ("APPLY_PUPPET_RT_SDF_" if sdf else "APPLY_PUPPET_RT_") + run_id
    if confirm != expected:
        raise SystemExit("confirmation mismatch; expected %s" % expected)
    with tempfile.TemporaryDirectory(prefix="puppet_rt_build_") as temp:
        scratch = Path(temp)
        files, manifests = (build_sdf_scratch(scratch, atlas, max_cells, cell_px, render_scale, spread, wide)
                            if sdf else build_scratch(scratch, atlas, max_cells, cell_px))
        backup_root = record_path(run_id, sdf).parent
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
        record_path(run_id, sdf).write_text(json.dumps(record, indent=2), encoding="utf-8")

        for source, target in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        expected_hashes = {relative(target): sha256(source) for source, target in files}
        actual_hashes = {relative(target): sha256(target) for _source, target in files}
        if expected_hashes != actual_hashes:
            raise SystemExit("read-back hash mismatch")
        marker_prefix = "PUPPET_RT_SDF_APPLY_OK" if sdf else "PUPPET_RT_APPLY_OK"
        marker = marker_prefix + "|run=%s|files=%d|dirty_packages=%d" % (
            run_id, len(files), record["census"]["dirty_package_count"])
        record["post_sha256"] = actual_hashes
        record["cell_budget"] = {
            name: manifest["cell_budget"] for name, manifest in manifests.items()
        }
        record["success_marker"] = marker
        record_path(run_id, sdf).write_text(json.dumps(record, indent=2), encoding="utf-8")
        reread = json.loads(record_path(run_id, sdf).read_text(encoding="utf-8"))
        if reread["success_marker"] != marker:
            raise SystemExit("record read-back failed")
        print(marker)


def revert(run_id, confirm, sdf=False):
    expected = ("REVERT_PUPPET_RT_SDF_" if sdf else "REVERT_PUPPET_RT_") + run_id
    if confirm != expected:
        raise SystemExit("confirmation mismatch; expected %s" % expected)
    path = record_path(run_id, sdf)
    if not path.is_file():
        raise SystemExit("record not found: %s" % path)
    record = json.loads(path.read_text(encoding="utf-8"))
    prefix = "RevertedPuppetRealtimeSDF-" if sdf else "RevertedPuppetRealtimeMoves-"
    stash = PROJECT_ROOT / "Backups" / (prefix + run_id)
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
    marker_prefix = "PUPPET_RT_SDF_REVERT_OK" if sdf else "PUPPET_RT_REVERT_OK"
    marker = marker_prefix + "|run=%s|files=%d" % (run_id, len(record["targets"]))
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
    parser.add_argument("--sdf", action="store_true")
    parser.add_argument("--render-scale", type=float, default=2.0)
    parser.add_argument("--spread", type=float, default=6.0)
    parser.add_argument("--wide", type=float, default=4.0)
    args = parser.parse_args(argv)
    if args.mode == "DRY":
        confirm_stem = "PUPPET_RT_SDF_" if args.sdf else "PUPPET_RT_"
        print(json.dumps({"mode": "DRY", "run_id": args.run_id, "sdf": args.sdf,
                          "render_scale": args.render_scale, "spread": args.spread, "wide": args.wide,
                          "plan": output_plan(args.sdf), "census": git_census(),
                          "apply_confirm": "APPLY_" + confirm_stem + args.run_id,
                          "revert_confirm": "REVERT_" + confirm_stem + args.run_id}, indent=2))
        marker = "PUPPET_RT_SDF_DRY_OK" if args.sdf else "PUPPET_RT_DRY_OK"
        print(marker + "|run=%s" % args.run_id)
    elif args.mode == "APPLY":
        apply(args.run_id, args.confirm, args.atlas, args.max_cells, args.source_cell_px,
              args.sdf, args.render_scale, args.spread, args.wide)
    else:
        revert(args.run_id, args.confirm, args.sdf)


if __name__ == "__main__":
    main()
