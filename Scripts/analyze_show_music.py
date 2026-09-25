#!/usr/bin/env python3
"""Re-run Infinity Stage music analysis over the shared Sound drive.

Task 0.1: the maps in Saved/InfinityStage/MusicAnalysis were written by provider
0.2.1 and carry no expressive curves. The analyzer on disk is 0.3.0. Until these
are regenerated, Apply Music Analysis Curve has nothing to apply, which blocks
the music-driven lighting (E.3) and wing movement (H.4, H.6) work.

Reads the Drive folders directly and writes only into the project's Saved/ dir.
Nothing on the shared drive is modified.

    python3 Scripts/analyze_show_music.py                 # six passage rails
    python3 Scripts/analyze_show_music.py --scenes        # passages + scenes
    python3 Scripts/analyze_show_music.py --dry-run       # look, don't run

Set PUSS_SOUND_ROOT to the Sound folder to avoid the platform default — needed
on the PC, where the macOS CloudStorage path does not exist.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYZER = PROJECT_ROOT / "Tools" / "InfinityStage" / "music_analysis.py"
OUTPUT_ROOT = PROJECT_ROOT / "Saved" / "InfinityStage" / "MusicAnalysis"

PASSAGES_SUBDIR = "InfinityStage Passages"
SCENES_SUBDIR = "Scenes"
# Present on the drive and deliberately not analysed.
IGNORED_SUBDIRS = ("Tracks (Outdated, ignore)",)

MAC_DEFAULT_ROOT = (
    Path.home() / "Library/CloudStorage/GoogleDrive-gary@zhexi.info/Shared drives"
    / "GZZ Studio Drive/Projects/2026. SHS 3 Evenings/Sound"
)


def resolve_sound_root(explicit: Path | None) -> Path:
    for candidate, origin in (
        (explicit, "--sound-root"),
        (Path(os.environ["PUSS_SOUND_ROOT"]) if os.environ.get("PUSS_SOUND_ROOT") else None,
         "PUSS_SOUND_ROOT"),
        (MAC_DEFAULT_ROOT, "macOS Drive default"),
    ):
        if candidate is None:
            continue
        if candidate.is_dir():
            print(f"Sound root ({origin}): {candidate}")
            return candidate
        if origin != "macOS Drive default":
            raise SystemExit(f"Sound root from {origin} does not exist: {candidate}")
    raise SystemExit(
        "No Sound folder found. Pass --sound-root or set PUSS_SOUND_ROOT.\n"
        f"Tried: {MAC_DEFAULT_ROOT}"
    )


def report_existing(output_dir: Path) -> None:
    """Print the provider version already on disk, so the change is visible."""
    maps = sorted(output_dir.glob("*.analysis.json"))
    if not maps:
        print(f"  (no existing maps in {output_dir})")
        return
    for path in maps:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print(f"  {path.name}: unreadable")
            continue
        analyzer = data.get("analyzer", {})
        feature_curves = data.get("featureCurves") or {}
        curve_names = list((feature_curves.get("curves") or {}).keys())
        sections = len(data.get("expressiveSections") or [])
        print(
            f"  {path.stem[:-9]:<48} {analyzer.get('version', '?'):<8} "
            f"curves={len(curve_names)} samples={feature_curves.get('sampleCount', '-')} "
            f"sections={sections}"
        )


def wavs_in(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".wav")


def run_analyzer(drop_dir: Path, output_dir: Path, *, force: bool, dry_run: bool) -> int:
    command = [
        sys.executable, str(ANALYZER),
        "--drop-dir", str(drop_dir),
        "--output-dir", str(output_dir),
    ]
    if force:
        command.append("--force")
    print("\n$ " + " ".join(f'"{c}"' if " " in c else c for c in command))
    if dry_run:
        return 0
    return subprocess.call(command)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sound-root", type=Path, help="The shared Sound folder.")
    parser.add_argument("--scenes", action="store_true",
                        help="Also analyse Scenes/, into a separate output folder.")
    parser.add_argument("--force", action="store_true",
                        help="Re-analyse even when the audio and provider are unchanged.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan, run nothing.")
    args = parser.parse_args()

    if not ANALYZER.is_file():
        raise SystemExit(f"Analyzer not found: {ANALYZER}")
    try:
        import numpy  # noqa: F401
    except ImportError:
        raise SystemExit(
            "numpy is required by music_analysis.py and is not importable by "
            f"{sys.executable}. Note the engine's bundled Python does not ship it."
        )

    root = resolve_sound_root(args.sound_root)
    for name in IGNORED_SUBDIRS:
        if (root / name).is_dir():
            print(f"Ignoring: {name}")

    passages = wavs_in(root / PASSAGES_SUBDIR)
    if not passages:
        raise SystemExit(f"No WAVs in {root / PASSAGES_SUBDIR}")
    print(f"\nPassage rails ({len(passages)}):")
    for path in passages:
        print(f"  {path.name}")

    print("\nCurrent maps in Saved/InfinityStage/MusicAnalysis:")
    report_existing(OUTPUT_ROOT)

    # Passage numbers come from the previous analysis of the same filename, so
    # P01-P06 are preserved rather than reshuffled. Do not rename these files.
    exit_code = run_analyzer(root / PASSAGES_SUBDIR, OUTPUT_ROOT,
                             force=args.force, dry_run=args.dry_run)
    if exit_code != 0:
        return exit_code

    if args.scenes:
        scenes = wavs_in(root / SCENES_SUBDIR)
        if not scenes:
            print(f"\nNo WAVs in {root / SCENES_SUBDIR}; skipping scenes.")
        else:
            # Separate output dir on purpose. The analyzer numbers everything it
            # finds as P01, P02... and the Show has exactly six Passages, so
            # letting scenes share the folder would stamp the Shrine as "P07".
            scene_output = OUTPUT_ROOT / "Scenes"
            print(f"\nScene stems ({len(scenes)}) -> {scene_output}")
            for path in scenes:
                print(f"  {path.name}")
            exit_code = run_analyzer(root / SCENES_SUBDIR, scene_output,
                                     force=args.force, dry_run=args.dry_run)
            if exit_code != 0:
                return exit_code

    if args.dry_run:
        print("\nDry run: nothing was written.")
        return 0

    print("\nResulting maps:")
    report_existing(OUTPUT_ROOT)
    print(
        "\nEvery row above must read 0.3.0 with curves=7 before this counts as done.\n"
        "Then, in Unreal: Cue Desk > Actions > Link / Reimport Music Analysis."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
