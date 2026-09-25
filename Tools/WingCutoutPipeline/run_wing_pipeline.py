#!/usr/bin/env python3
"""Friendly launcher for the Blender stage-wing batch generator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
BLENDER_SCRIPT = HERE / "blender_png_to_wing.py"


def find_blender(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    discovered = shutil.which("blender")
    if discovered:
        candidates.append(Path(discovered))
    if platform.system() == "Darwin":
        candidates.extend(
            [
                Path("/Applications/Blender v5-2.app/Contents/MacOS/Blender"),
                Path("/Applications/Blender.app/Contents/MacOS/Blender"),
                Path("/Applications/Blender v4-21.app/Contents/MacOS/Blender"),
            ]
        )
    elif platform.system() == "Windows":
        candidates.extend(Path("C:/Program Files/Blender Foundation").glob("Blender */blender.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Blender executable not found; pass --blender /path/to/blender")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--height-m", type=float, default=6.0)
    parser.add_argument("--thickness-cm", type=float, default=5.0)
    parser.add_argument("--ue-panel-scale", type=float, default=5.0)
    parser.add_argument("--ue-yaw-deg", type=float, default=90.0)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--blender")
    parser.add_argument("--alpha-threshold", type=float, default=0.5)
    parser.add_argument("--trace-max-size", type=int, default=1024)
    parser.add_argument("--simplify-px", type=float, default=1.5)
    parser.add_argument("--min-island-px", type=int, default=64)
    parser.add_argument("--min-loop-area-px", type=float, default=24.0)
    parser.add_argument("--islands", choices=("largest", "all"), default="largest")
    parser.add_argument("--no-save-blend", action="store_true")
    parser.add_argument("--no-export-fbx", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 2.0 <= args.height_m <= 8.0:
        raise SystemExit("--height-m must be between 2 and 8 metres")
    if not 0.001 <= args.ue_panel_scale <= 100.0:
        raise SystemExit("--ue-panel-scale must be between 0.001 and 100")
    if not -360.0 <= args.ue_yaw_deg <= 360.0:
        raise SystemExit("--ue-yaw-deg must be between -360 and 360 degrees")
    blender = find_blender(args.blender)
    command = [
        str(blender),
        "--background",
        "--factory-startup",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        "--output-dir",
        str(args.output_dir.resolve()),
        "--height-m",
        str(args.height_m),
        "--thickness-cm",
        str(args.thickness_cm),
        "--ue-panel-scale",
        str(args.ue_panel_scale),
        "--ue-yaw-deg",
        str(args.ue_yaw_deg),
        "--alpha-threshold",
        str(args.alpha_threshold),
        "--trace-max-size",
        str(args.trace_max_size),
        "--simplify-px",
        str(args.simplify_px),
        "--min-island-px",
        str(args.min_island_px),
        "--min-loop-area-px",
        str(args.min_loop_area_px),
        "--islands",
        args.islands,
    ]
    if args.input:
        command.extend(["--input", str(args.input.resolve())])
    else:
        command.extend(["--input-dir", str(args.input_dir.resolve())])
    if args.manifest:
        command.extend(["--manifest", str(args.manifest.resolve())])
    if args.no_save_blend:
        command.append("--no-save-blend")
    if args.no_export_fbx:
        command.append("--no-export-fbx")
    print(json.dumps(command, indent=2))
    if args.dry_run:
        return 0
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
