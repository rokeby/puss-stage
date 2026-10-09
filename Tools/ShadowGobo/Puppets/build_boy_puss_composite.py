"""Build PG5's offline boy + Puss composite gobo review artifacts.

DRY writes nothing. APPLY requires ``APPLY_BOY_PUSS_<run-id>``, records the
exact git/package census and backs up every predecessor before replacing any
named output. REVERT is recoverable and requires ``REVERT_BOY_PUSS_<run-id>``.
No Unreal, MCP, or Blender code is imported or called.
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

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
PROJECT_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOL_DIR))

import boy_rig  # noqa: E402
import cat_rig  # noqa: E402
import clip_render  # noqa: E402
import gobo_twin  # noqa: E402
import pack_rig_flipbook  # noqa: E402


OUTPUT_ROOT = HERE / "clip_boy_puss_rub"
DISPLAY_FPS = 25.0
CLIP_LENGTH = 9.0
GUTTER_PX = 8
LIGHT_PARAMS = {
    "BorderDepth": 1.0, "BorderAspect": 1.88, "Scale": 0.7071,
    "Defocus": 0.25,
}
VISIBLE_BAND = {
    "aspect": 1.88,
    "top": 0.5 - 0.5 / 1.88,
    "bottom": 0.5 + 0.5 / 1.88,
}

# Gary's review values: ordinary dictionaries, deliberately not hidden in the
# renderer. Source coordinates are mapped uniformly into the square atlas cell.
BOY_HEAD_TARGET_Y = VISIBLE_BAND["top"] + 0.08 / 1.88
BOY_KNEE_SOURCE_Y = 1250.0  # just above the knee of the SHORTENED legs (1130 = hem, legs end ~1418; review 9 Oct)
BOY_SCALE = (VISIBLE_BAND["bottom"] + 0.006 - BOY_HEAD_TARGET_Y) / (BOY_KNEE_SOURCE_Y - 182.0)
BOY_PLACEMENT = {
    "anchor_world": (540.0, 182.0),
    "anchor_cell": (0.30, BOY_HEAD_TARGET_Y),
    "scale": BOY_SCALE,
}

PUSS_SIT_TOP_Y = 96.31408575
PUSS_SIT_BOTTOM_Y = 1029.99005309
PUSS_VISIBLE_HEIGHT = 0.45 * (VISIBLE_BAND["bottom"] - BOY_HEAD_TARGET_Y)
PUSS_SCALE = PUSS_VISIBLE_HEIGHT / (PUSS_SIT_BOTTOM_Y - PUSS_SIT_TOP_Y)
PUSS_PLACEMENT = {
    "anchor_world": (500.0, PUSS_SIT_BOTTOM_Y),
    "anchor_cell": (0.75, VISIBLE_BAND["bottom"]),
    "scale": PUSS_SCALE,
}

FEATURE_LOOK = {
    "minimum_px": 2.0,
    "boy_rod_world": 5.0,
    "boy_narrowest_slit_world": 4.0,
}
CURTAIN_LOOK = dict(gobo_twin.CURTAIN_DEFAULTS)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")


def git_census():
    result = subprocess.run(["git", "status", "--short"], cwd=PROJECT_ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    packages = [line for line in dirty if line.lower().endswith((".uasset", ".umap"))]
    return {"dirty_packages": packages, "dirty_package_count": len(packages),
            "source_dirty": dirty, "git_status_exit": result.returncode}


def boy_keys():
    return boy_rig.rubbing_eyes_clip()[0]


def puss_keys():
    """Upright -> look up at the whimper -> stretch -> look up."""
    return [
        (0.0, cat_rig.make_pose("sit_upright"), 0.0, "snap"),
        (1.2, cat_rig.make_pose("sit_look_up"), 0.44, "ease_in_out"),
        (6.65, cat_rig.make_pose("stretch"), 0.64, "ease_in_out"),
        (8.05, cat_rig.make_pose("sit_look_up"), 0.56, "ease_in_out"),
    ]


def placement_view(placement, render_px):
    scale = float(placement["scale"])
    source_x, source_y = placement["anchor_world"]
    cell_x, cell_y = placement["anchor_cell"]
    return {
        "x0": source_x - cell_x / scale,
        "y0": source_y - cell_y / scale,
        "scale": scale * render_px,
        "w": int(render_px),
        "h": int(render_px),
    }


def composite_tracks(render_px, puss_placement=None):
    puss_placement = dict(PUSS_PLACEMENT if puss_placement is None else puss_placement)
    boy_view = placement_view(BOY_PLACEMENT, render_px)
    puss_view = placement_view(puss_placement, render_px)
    return [
        clip_render.CompositeTrack(
            "boy", boy_keys(),
            lambda pose, _placement: boy_rig.render_pose(pose, ss=2, view=boy_view),
            dict(BOY_PLACEMENT), point_keys=("near_hand_on_head", "far_hand_on_head"),
            point_resolver=boy_rig.hand_target_for_pose, tear_speed=0.45,
        ),
        clip_render.CompositeTrack(
            "puss", puss_keys(),
            lambda pose, _placement: cat_rig.render_pose(pose, view=puss_view, ss=2),
            puss_placement, tear_speed=0.0,
        ),
    ]


def render_composite_frames(out_dir, render_px, max_cells):
    return clip_render.render_composite_clip(
        composite_tracks(render_px), CLIP_LENGTH, out_dir,
        fps=DISPLAY_FPS, max_cells=max_cells,
    )


def map_point(point, placement):
    source = np.asarray(placement["anchor_world"], dtype=float)
    target = np.asarray(placement["anchor_cell"], dtype=float)
    return target + (np.asarray(point, dtype=float) - source) * float(placement["scale"])


def framing_report():
    boy_pose = boy_rig.P()
    boy_parts, _rods = boy_rig.pose_parts(boy_pose)
    boy_head = np.concatenate([np.asarray(outline) for outline, _cuts, z in boy_parts if z == 2])
    boy_head_top = float(map_point((0.0, boy_head[:, 1].min()), BOY_PLACEMENT)[1])
    boy_knee = float(map_point((0.0, BOY_KNEE_SOURCE_Y), BOY_PLACEMENT)[1])
    boy_all = np.concatenate([np.asarray(outline) for outline, _cuts, _z in boy_parts])
    current_full_height = float((boy_all[:, 1].max() - boy_all[:, 1].min()) / 1450.0)
    visible_height = VISIBLE_BAND["bottom"] - boy_head_top

    puss_pose = cat_rig.make_pose("sit_look_up")
    puss_parts, _rods, _whiskers = cat_rig.pose_parts(puss_pose)
    head = np.concatenate([np.asarray(outline) for name, outline, _cuts, _z in puss_parts if name == "head"])
    puss_head_top = float(map_point((0.0, head[:, 1].min()), PUSS_PLACEMENT)[1])
    boy_mid = boy_head_top + visible_height * 0.5
    return {
        "visible_band_cell": dict(VISIBLE_BAND),
        "boy": {
            "placement": dict(BOY_PLACEMENT),
            "head_top_cell_y": boy_head_top,
            "head_inset_fraction_of_band": (boy_head_top - VISIBLE_BAND["top"]) * 1.88,
            "declared_knee_source_y": BOY_KNEE_SOURCE_Y,
            "knee_cell_y": boy_knee,
            "visible_height_cell": visible_height,
            "visible_extent_factor_vs_current_full_puppet": visible_height / current_full_height,
            "source_scale_factor_vs_current_window": BOY_SCALE / (1.0 / 1450.0),
            "centre_cell_x": BOY_PLACEMENT["anchor_cell"][0],
        },
        "puss": {
            "placement": dict(PUSS_PLACEMENT),
            "head_top_cell_y": puss_head_top,
            "boy_halfway_cell_y": boy_mid,
            "visible_height_ratio_to_boy": (VISIBLE_BAND["bottom"] - puss_head_top) / visible_height,
            "centre_cell_x": PUSS_PLACEMENT["anchor_cell"][0],
        },
        "claims": [
            {"tier": "declaration-proven", "claim": "The authored visible band is the middle 1/1.88 of a square cell.",
             "evidence": "Tools/ShadowGobo/Puppets/build_boy_puss_composite.py:43-47"},
            {"tier": "measured", "claim": "Boy head, knee and Puss head positions are transformed from rig geometry.",
             "evidence": "Tools/ShadowGobo/Puppets/build_boy_puss_composite.py:157-194"},
        ],
    }


def feature_report(inner_px):
    features = {}
    for name, world in (("boy_rod", FEATURE_LOOK["boy_rod_world"]),
                        ("boy_narrowest_slit", FEATURE_LOOK["boy_narrowest_slit_world"])):
        width = float(world) * BOY_SCALE * int(inner_px)
        minimum_world = FEATURE_LOOK["minimum_px"] / (BOY_SCALE * int(inner_px))
        features[name] = {
            "world_width": world,
            "cell_px": width,
            "meets_2px": width + 1e-9 >= FEATURE_LOOK["minimum_px"],
            "warning": pack_rig_flipbook.feature_width_warning(width, label=name),
            "proposed_world_width_if_failed": None if width >= FEATURE_LOOK["minimum_px"] else minimum_world,
        }
    return {
        "inner_px": int(inner_px), "minimum_px": FEATURE_LOOK["minimum_px"], "features": features,
        "claims": [
            {"tier": "declaration-proven", "claim": "Boy rod width is 5 world units and the narrowest active slit is 4.",
             "evidence": "Tools/ShadowGobo/Puppets/boy_rig.py:295,94,103"},
            {"tier": "measured", "claim": "Feature widths are projected through PG5's boy placement into atlas-cell pixels.",
             "evidence": "Tools/ShadowGobo/Puppets/build_boy_puss_composite.py:197-216"},
        ],
    }


def add_manifest_metadata(path, result, framing, features, max_cells, render_scale):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["composite_clip"] = {
        "display_fps": DISPLAY_FPS,
        "length_s": CLIP_LENGTH,
        "product_transmissions": True,
        "tracks": {
            name: {
                "move_frames": {str(k): v for k, v in track.move_frames.items()},
                "original_move_frames": {str(k): v for k, v in track.original_move_frames.items()},
            }
            for name, track in result.track_results.items()
        },
        "max_cells": max_cells,
        "reductions": result.reductions,
        "quantization": {"angles_and_targets": 0.01},
        "handheld_wobble_baked": False,
        "render_scale": float(render_scale),
        "placements": {"boy": dict(BOY_PLACEMENT), "puss": dict(PUSS_PLACEMENT)},
    }
    data["framing"] = framing
    data["minimum_feature_widths"] = features
    data["curtain_preview_look"] = dict(CURTAIN_LOOK)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_curtain_artifacts(manifest_path, out_dir, frame_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_dir.mkdir(parents=True, exist_ok=True)
    prepared = gobo_twin.prepare_render(
        manifest_path, params=LIGHT_PARAMS, fps=DISPLAY_FPS, px=1920,
        curtain=True, curtain_params=CURTAIN_LOOK,
    )
    frame_paths = []
    for index in range(int(round(CLIP_LENGTH * DISPLAY_FPS))):
        image = gobo_twin.render_prepared(prepared, index / DISPLAY_FPS)
        path = frame_dir / ("f%04d.png" % index)
        image.quantize(colors=128, method=Image.Quantize.MEDIANCUT).save(path)
        frame_paths.append(path)

    def gif_frames():
        for path in frame_paths[1:]:
            with Image.open(path) as image:
                yield image.copy()

    with Image.open(frame_paths[0]) as first:
        first.copy().save(
            out_dir / "curtain_preview_defocus025.gif", save_all=True,
            append_images=gif_frames(), duration=40, loop=0, optimize=True,
        )

    panels = []
    still_time = 7.45
    for defocus in (0.15, 0.25, 0.35):
        still_prepared = gobo_twin.prepare_render(
            manifest_path, params=dict(LIGHT_PARAMS, Defocus=defocus), px=1920,
            curtain=True, curtain_params=CURTAIN_LOOK,
        )
        panel = gobo_twin.render_prepared(still_prepared, still_time).convert("RGB")
        draw = ImageDraw.Draw(panel)
        draw.rectangle((0, 0, 220, 38), fill=(28, 22, 20))
        draw.text((12, 11), "Defocus %.2f" % defocus, fill=(248, 224, 190))
        panel.save(out_dir / ("curtain_still_defocus%03d.png" % round(defocus * 100)))
        panels.append(panel)
    comparison = Image.new("RGB", (1920 * 3, panels[0].height), (20, 15, 14))
    for index, panel in enumerate(panels):
        comparison.paste(panel, (index * 1920, 0))
    comparison.save(out_dir / "curtain_stills_015_025_035.png")


def stretch_preview(path):
    render_px = 1200
    image = cat_rig.render_pose(cat_rig.make_pose("stretch"),
                                view=placement_view(PUSS_PLACEMENT, render_px), ss=2)
    top = int(round(VISIBLE_BAND["top"] * render_px))
    bottom = int(round(VISIBLE_BAND["bottom"] * render_px))
    transmission = np.asarray(image.crop((0, top, render_px, bottom)), dtype=np.float64) / 255.0
    warm = np.asarray((244, 180, 112), dtype=np.float64)
    rgb = warm[None, None, :] * (0.24 + 0.76 * transmission[..., None])
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(path)


def run_harness(manifest, report_path):
    command = [sys.executable, str(HERE / "test_boy_puss_composite_offline.py"),
               "--manifest", str(manifest), "--report", str(report_path)]
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError("composite harness failed:\n" + result.stdout)
    return result.stdout.strip()


def build_scratch(root, atlas_px, max_cells, probe_px, render_scale, spread, wide):
    probe = render_composite_frames(root / "probe_frames", probe_px, max_cells)
    budget = pack_rig_flipbook.atlas_budget(probe.unique_cells, atlas_px)
    target_inner = budget["cell_px"] - 2 * GUTTER_PX
    render_px = clip_render.scaled_render_size(target_inner, render_scale)
    final = render_composite_frames(root / "frames", render_px, max_cells)
    if final.unique_cells != probe.unique_cells:
        raise RuntimeError("probe/final unique-cell drift %d -> %d" %
                           (probe.unique_cells, final.unique_cells))

    atlas_dir = root / "deliver" / "atlas"
    manifest = pack_rig_flipbook.pack(
        root / "frames", atlas_dir, "BoyPussRub", DISPLAY_FPS,
        atlas_px=atlas_px, gutter_px=GUTTER_PX, preview=True,
        sdf=True, spread=spread, wide=wide,
    )
    framing = framing_report()
    features = feature_report(manifest["atlas"]["inner_px"])
    manifest_path = atlas_dir / "manifest.json"
    add_manifest_metadata(manifest_path, final, framing, features, max_cells, render_scale)

    deliver = root / "deliver"
    stretch_preview(deliver / "stretch_pose_preview.png")
    save_curtain_artifacts(manifest_path, deliver, root / "curtain_frames")
    harness_output = run_harness(manifest_path, deliver / "offline_harness_report.json")
    report = {
        "schema_version": 1,
        "claims": [
            {"tier": "measured", "claim": "PG5 composite was rendered, SDF-packed, read back and tested offline.",
             "evidence": "Tools/ShadowGobo/Puppets/clip_boy_puss_rub/report.json"},
            {"tier": "inferred", "claim": "Curtain pleat, haze and spot defaults are a review proposal, not rendered UE acceptance.",
             "evidence": "Gary must judge curtain_preview_defocus025.gif and the three stills."},
        ],
        "rendered_frames": final.rendered_frames,
        "unique_cells": final.unique_cells,
        "atlas": manifest["atlas"],
        "cell_budget": manifest["cell_budget"],
        "framing": framing,
        "minimum_feature_widths": features,
        "curtain_preview": {"width_px": 1920, "fps": DISPLAY_FPS, "look": CURTAIN_LOOK,
                            "defocus_demo": 0.25, "still_defocus": [0.15, 0.25, 0.35]},
        "harness_stdout": harness_output,
    }
    (deliver / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    files = [path for path in deliver.rglob("*") if path.is_file()]
    return files, report


def record_path(run_id):
    return PROJECT_ROOT / "Backups" / ("PreBoyPussComposite-" + run_id) / "record.json"


def output_plan():
    return {
        "root": relative(OUTPUT_ROOT),
        "files": [
            "atlas/T_Gobo_BoyPussRub_<grid>.png", "atlas/manifest.json", "atlas/cells_contact.png",
            "curtain_preview_defocus025.gif", "curtain_still_defocus015.png",
            "curtain_still_defocus025.png", "curtain_still_defocus035.png",
            "curtain_stills_015_025_035.png", "stretch_pose_preview.png",
            "offline_harness_report.json", "report.json",
        ],
        "unreal_access": False, "unreal_packages_saved": [],
    }


def apply(run_id, confirm, atlas_px, max_cells, probe_px, render_scale, spread, wide):
    expected = "APPLY_BOY_PUSS_" + run_id
    if confirm != expected:
        raise SystemExit("confirmation mismatch; expected %s" % expected)
    with tempfile.TemporaryDirectory(prefix="boy_puss_composite_") as temp:
        scratch = Path(temp)
        files, report = build_scratch(scratch, atlas_px, max_cells, probe_px, render_scale, spread, wide)
        backup_root = record_path(run_id).parent
        if backup_root.exists():
            raise SystemExit("backup run already exists: %s" % backup_root)
        backup_root.mkdir(parents=True)
        record = {
            "schema_version": 1, "run_id": run_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "mode": "APPLY", "confirm": expected, "census": git_census(),
            "unreal_access": False, "unreal_packages_saved": [], "targets": [],
            "success_marker": None,
        }
        for source in files:
            rel = source.relative_to(scratch / "deliver")
            target = OUTPUT_ROOT / rel
            entry = {"path": relative(target), "existed": target.is_file(),
                     "pre_sha256": sha256(target) if target.is_file() else None}
            if target.is_file():
                saved = backup_root / "files" / relative(target)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
                entry["backup"] = relative(saved)
            record["targets"].append(entry)
        record_path(run_id).write_text(json.dumps(record, indent=2), encoding="utf-8")

        for source in files:
            target = OUTPUT_ROOT / source.relative_to(scratch / "deliver")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        expected_hashes = {relative(OUTPUT_ROOT / source.relative_to(scratch / "deliver")): sha256(source)
                           for source in files}
        actual_hashes = {path: sha256(PROJECT_ROOT / path) for path in expected_hashes}
        if expected_hashes != actual_hashes:
            raise SystemExit("read-back hash mismatch")
        marker = "BOY_PUSS_COMPOSITE_APPLY_OK|run=%s|files=%d|cells=%d|dirty_packages=%d" % (
            run_id, len(files), report["unique_cells"], record["census"]["dirty_package_count"])
        record["post_sha256"] = actual_hashes
        record["success_marker"] = marker
        record["budget"] = report["cell_budget"]
        record_path(run_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
        reread = json.loads(record_path(run_id).read_text(encoding="utf-8"))
        if reread["success_marker"] != marker:
            raise SystemExit("record read-back failed")
        print(marker)


def revert(run_id, confirm):
    expected = "REVERT_BOY_PUSS_" + run_id
    if confirm != expected:
        raise SystemExit("confirmation mismatch; expected %s" % expected)
    path = record_path(run_id)
    if not path.is_file():
        raise SystemExit("record not found: %s" % path)
    record = json.loads(path.read_text(encoding="utf-8"))
    stash = PROJECT_ROOT / "Backups" / ("RevertedBoyPussComposite-" + run_id)
    if stash.exists():
        raise SystemExit("revert stash already exists: %s" % stash)
    stash.mkdir(parents=True)
    for entry in record["targets"]:
        target = PROJECT_ROOT / entry["path"]
        if target.is_file():
            saved = stash / "replaced" / entry["path"]
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(target, saved)
        if entry["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT / entry["backup"], target)
    marker = "BOY_PUSS_COMPOSITE_REVERT_OK|run=%s|files=%d" % (run_id, len(record["targets"]))
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
    parser.add_argument("--probe-px", type=int, default=520)
    parser.add_argument("--render-scale", type=float, default=2.0)
    parser.add_argument("--spread", type=float, default=6.0)
    parser.add_argument("--wide", type=float, default=4.0)
    args = parser.parse_args(argv)
    if args.mode == "DRY":
        print(json.dumps({"mode": "DRY", "run_id": args.run_id, "plan": output_plan(),
                          "census": git_census(),
                          "apply_confirm": "APPLY_BOY_PUSS_" + args.run_id,
                          "revert_confirm": "REVERT_BOY_PUSS_" + args.run_id}, indent=2))
        print("BOY_PUSS_COMPOSITE_DRY_OK|run=%s" % args.run_id)
    elif args.mode == "APPLY":
        apply(args.run_id, args.confirm, args.atlas, args.max_cells, args.probe_px,
              args.render_scale, args.spread, args.wide)
    else:
        revert(args.run_id, args.confirm)


if __name__ == "__main__":
    main()
