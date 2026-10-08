#!/usr/bin/env python3
"""P15 offline video-placeholder and LED display-profile tool.

This tool never imports ``unreal`` and never touches Content.  It owns only an
explicit output directory under the project root.  DRY is read-only; APPLY
creates a recoverable backup and record before replacing any owned file; REVERT
moves the applied files into that backup before restoring the prior bytes.

Markers:
  P15VIDEO_DRY_OK|run=...
  P15VIDEO_APPLY_OK|run=...|record=...
  P15VIDEO_REVERT_OK|run=...|record=...
  P15VIDEO_STOPPED|run=...|reason=...
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("DerivedAssets/P15VideoTransitions")
APPLY_CONFIRM = "APPLY P15VIDEO"
REVERT_CONFIRM = "REVERT P15VIDEO"
SCENE_FRAMES = {
    "S1": 6176,
    "S2": 2025,
    "S3": 6500,
    "S4": 4890,
    "S5": 1225,
    "S6": 5489,
}
AUDIO_OWNERS = {"ue_muxed", "desk"}


class Stop(RuntimeError):
    pass


def utc_run() -> str:
    return "P15VIDEO-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise Stop("ARGS_NOT_OBJECT")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def under_root(path: Path, root: Path = PROJECT_ROOT) -> Path:
    resolved = path.resolve()
    base = root.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise Stop("PATH_OUTSIDE_PROJECT:%s" % resolved) from exc
    return resolved


def output_path(value: str | os.PathLike[str]) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return under_root(path)


def horizontal_fov_deg(sensor_width_mm: float, focal_mm: float) -> float:
    if sensor_width_mm <= 0 or focal_mm <= 0:
        raise Stop("BAD_CAMERA_GEOMETRY")
    return math.degrees(2.0 * math.atan(sensor_width_mm / (2.0 * focal_mm)))


def presentation_geometry(
    content_width: int,
    content_height: int,
    led_width: int,
    led_height: int,
    fit_mode: str,
) -> dict:
    values = (content_width, content_height, led_width, led_height)
    if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in values):
        raise Stop("BAD_DISPLAY_DIMENSIONS")
    if fit_mode not in {"fit", "fill", "native"}:
        raise Stop("BAD_FIT_MODE:%s" % fit_mode)
    ca = content_width / content_height
    la = led_width / led_height
    if fit_mode == "native" and (content_width, content_height) != (led_width, led_height):
        raise Stop("NATIVE_REQUIRES_MATCHING_PIXELS")
    scale = (1.0 if fit_mode == "native" else
             min(led_width / content_width, led_height / content_height)
             if fit_mode == "fit" else
             max(led_width / content_width, led_height / content_height))
    shown_w = content_width * scale
    shown_h = content_height * scale
    side_bar = max(0.0, (led_width - shown_w) / 2.0)
    top_bar = max(0.0, (led_height - shown_h) / 2.0)
    crop_x = max(0.0, (shown_w - led_width) / shown_w / 2.0)
    crop_y = max(0.0, (shown_h - led_height) / shown_h / 2.0)
    return {
        "content_aspect": ca,
        "led_aspect": la,
        "fit_mode": fit_mode,
        "scaled_content_px": [round(shown_w, 3), round(shown_h, 3)],
        "pillarbox_each_px": round(side_bar, 3),
        "letterbox_each_px": round(top_bar, 3),
        "crop_each_fraction": [round(crop_x, 8), round(crop_y, 8)],
    }


def build_display_profile(config: dict) -> dict:
    render = config.get("render", {})
    width = int(render.get("width", 1920))
    height = int(render.get("height", 1080))
    fps = int(render.get("fps", 25))
    if width <= 0 or height <= 0 or fps <= 0 or width % 2 or height % 2:
        raise Stop("BAD_RENDER_PROFILE")
    led = config.get("led", {})
    pixel_w, pixel_h = led.get("pixel_width"), led.get("pixel_height")
    geometry = None
    if pixel_w is not None or pixel_h is not None:
        if pixel_w is None or pixel_h is None:
            raise Stop("LED_PIXEL_PAIR_REQUIRED")
        geometry = presentation_geometry(width, height, int(pixel_w), int(pixel_h), led.get("fit_mode", "fit"))
    sensor_w = float(config.get("camera_sensor_width_mm", 23.76))
    native_sensor_h = sensor_w * height / width
    return {
        "schema": 1,
        "render": {"width": width, "height": height, "fps": fps},
        "content_aspect": width / height,
        "presentation": geometry,
        "game_launch_args": ["-ResX=%d" % width, "-ResY=%d" % height, "-Fullscreen"],
        "mrq_output_resolution": [width, height],
        "camera_policy": {
            "default": "preserve_horizontal_fov_and_fit",
            "sensor_width_mm": sensor_w,
            "sensor_height_mm_for_native_aspect": native_sensor_h,
            "note": "Changing sensor height is a framing decision; DRY/report only until Gary approves.",
        },
    }


def master_to_media_frame(master_frame: int, scene_start: int, media_frames: int, loop: bool) -> int | None:
    if media_frames <= 0:
        raise Stop("BAD_MEDIA_FRAME_COUNT")
    local = master_frame - scene_start
    if local < 0:
        return None
    if loop:
        return local % media_frames
    return local if local < media_frames else None


def validate_audio_owner(owner: str, has_video_audio: bool, external_audio_enabled: bool) -> None:
    if owner not in AUDIO_OWNERS:
        raise Stop("BAD_AUDIO_OWNER:%s" % owner)
    if owner == "ue_muxed" and not has_video_audio:
        raise Stop("UE_MUXED_WITHOUT_VIDEO_AUDIO")
    if owner == "ue_muxed" and external_audio_enabled:
        raise Stop("DOUBLE_AUDIO")
    if owner == "desk" and has_video_audio:
        raise Stop("DESK_OWNER_REQUIRES_VIDEO_ONLY")


def run_checked(command: list[str]) -> None:
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode:
        tail = (result.stderr or result.stdout)[-1200:].replace("\n", " / ")
        raise Stop("COMMAND_FAILED:%s" % tail)


def ffprobe(path: Path, executable: str) -> dict:
    result = subprocess.run(
        [executable, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise Stop("FFPROBE_FAILED:%s" % path.name)
    return json.loads(result.stdout)


def _safe_area_filter() -> str:
    # Avoid drawtext/fontconfig: the moving testsrc2 pattern itself makes stalls visible.
    return (
        "drawbox=x=96:y=54:w=1728:h=972:color=white@0.55:t=2,"
        "drawbox=x=192:y=108:w=1536:h=864:color=white@0.35:t=2"
    )


def generate_with_ffmpeg(out: Path, config: dict, ffmpeg_exe: str, ffprobe_exe: str) -> dict:
    profile = build_display_profile(config)
    width = profile["render"]["width"]
    height = profile["render"]["height"]
    fps = profile["render"]["fps"]
    seconds = float(config.get("placeholder_seconds", 8.0))
    if seconds <= 0:
        raise Stop("BAD_PLACEHOLDER_DURATION")
    video = out / "P15_PLACEHOLDER_1080p25_video_only.mp4"
    audio = out / "P15_PLACEHOLDER_1kHz_48k_s24.wav"
    muxed = out / "P15_PLACEHOLDER_1080p25_review_muxed.mp4"
    preview = out / "P15_PLACEHOLDER_preview.png"
    run_checked([
        ffmpeg_exe, "-y", "-f", "lavfi", "-i",
        "testsrc2=size=%dx%d:rate=%d" % (width, height, fps),
        "-vf", _safe_area_filter(), "-t", str(seconds), "-an",
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-crf", "12", "-g", str(fps),
        "-keyint_min", str(fps), "-sc_threshold", "0", "-movflags", "+faststart", str(video),
    ])
    run_checked([
        ffmpeg_exe, "-y", "-f", "lavfi", "-i",
        "sine=frequency=1000:sample_rate=48000:duration=%s" % seconds,
        "-af", "pan=stereo|c0=c0|c1=c0", "-c:a", "pcm_s24le", str(audio),
    ])
    run_checked([
        ffmpeg_exe, "-y", "-i", str(video), "-i", str(audio), "-c:v", "copy",
        "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", str(muxed),
    ])
    run_checked([ffmpeg_exe, "-y", "-ss", "1", "-i", str(video), "-frames:v", "1", str(preview)])
    video_probe = ffprobe(video, ffprobe_exe)
    audio_probe = ffprobe(audio, ffprobe_exe)
    muxed_probe = ffprobe(muxed, ffprobe_exe)
    vstreams = [s for s in video_probe["streams"] if s.get("codec_type") == "video"]
    if len(vstreams) != 1 or any(s.get("codec_type") == "audio" for s in video_probe["streams"]):
        raise Stop("VIDEO_ONLY_STREAM_CONTRACT")
    vs = vstreams[0]
    if (int(vs["width"]), int(vs["height"])) != (width, height) or vs.get("r_frame_rate") != "%d/1" % fps:
        raise Stop("VIDEO_GEOMETRY_CONTRACT")
    astreams = [s for s in audio_probe["streams"] if s.get("codec_type") == "audio"]
    if len(astreams) != 1 or int(astreams[0].get("sample_rate", 0)) != 48000:
        raise Stop("WAV_CONTRACT")
    mux_types = {s.get("codec_type") for s in muxed_probe["streams"]}
    if mux_types != {"video", "audio"}:
        raise Stop("MUXED_CONTRACT")
    return {
        "kind": "mp4",
        "video": video,
        "audio": audio,
        "muxed": muxed,
        "preview": preview,
        "media_frames": int(round(seconds * fps)),
    }


def _png_frame(path: Path, width: int, height: int, fps: int, frame: int) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise Stop("NO_FFMPEG_AND_NO_PIL") from exc
    colors = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0),
              (192, 0, 192), (192, 0, 0), (0, 0, 192)]
    image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(image)
    band = width / len(colors)
    for index, color in enumerate(colors):
        draw.rectangle((round(index * band), 0, round((index + 1) * band), height), fill=color)
    draw.rectangle((round(width * 0.05), round(height * 0.05), round(width * 0.95), round(height * 0.95)), outline="white", width=2)
    draw.rectangle((round(width * 0.10), round(height * 0.10), round(width * 0.90), round(height * 0.90)), outline="white", width=2)
    total_s = frame / fps
    text = "PUSSSTAGE P15 PLACEHOLDER  %02d:%02d:%02d:%02d  F%d" % (
        total_s // 3600, total_s // 60 % 60, total_s % 60, frame % fps, frame)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", max(18, height // 24))
    except OSError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), text, font=font)
    x = (width - (box[2] - box[0])) // 2
    y = height - (box[3] - box[1]) - height // 14
    draw.rectangle((x - 12, y - 8, x + box[2] - box[0] + 12, y + box[3] - box[1] + 8), fill="black")
    draw.text((x, y), text, font=font, fill="white")
    image.save(path)


def generate_fallback_sequence(out: Path, config: dict) -> dict:
    profile = build_display_profile(config)
    width, height, fps = profile["render"]["width"], profile["render"]["height"], profile["render"]["fps"]
    frames = int(round(float(config.get("placeholder_seconds", 8.0)) * fps))
    if frames <= 0:
        raise Stop("BAD_PLACEHOLDER_DURATION")
    frame_dir = out / "P15_PLACEHOLDER_ImgMedia"
    frame_dir.mkdir(parents=True, exist_ok=True)
    for frame in range(frames):
        _png_frame(frame_dir / ("P15_PLACEHOLDER_%06d.png" % frame), width, height, fps, frame)
    audio = out / "P15_PLACEHOLDER_1kHz_48k_s24.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(48000)
        samples = bytearray()
        for index in range(round(frames / fps * 48000)):
            value = int(math.sin(2.0 * math.pi * 1000.0 * index / 48000.0) * 0.25 * 8388607)
            packed = struct.pack("<i", value)[:3]
            samples.extend(packed)
            samples.extend(packed)
        wav.writeframes(bytes(samples))
    preview = out / "P15_PLACEHOLDER_preview.png"
    preview_frame = min(fps, frames - 1)
    shutil.copy2(frame_dir / ("P15_PLACEHOLDER_%06d.png" % preview_frame), preview)
    return {
        "kind": "imgmedia",
        "sequence": frame_dir / "P15_PLACEHOLDER_%06d.png",
        "audio": audio,
        "preview": preview,
        "media_frames": frames,
    }


def owned_relative_paths(kind: str) -> list[Path]:
    common = [Path("P15_PLACEHOLDER_1kHz_48k_s24.wav"), Path("P15_PLACEHOLDER_preview.png"),
              Path("display_profile.json"), Path("placeholder_current.json"), Path("p15_apply_record.json")]
    if kind == "mp4":
        return common + [Path("P15_PLACEHOLDER_1080p25_video_only.mp4"),
                         Path("P15_PLACEHOLDER_1080p25_review_muxed.mp4")]
    return common + [Path("P15_PLACEHOLDER_ImgMedia")]


def snapshot_before(out: Path, backup: Path, relpaths: list[Path], run: str, plan: dict) -> dict:
    before = []
    (backup / "before").mkdir(parents=True, exist_ok=False)
    for rel in relpaths:
        target = under_root(out / rel)
        row = {"relative": rel.as_posix(), "existed": target.exists()}
        if target.is_file():
            row["sha256"] = sha256(target)
            destination = backup / "before" / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
        elif target.is_dir():
            destination = backup / "before" / rel
            shutil.copytree(target, destination)
            row["files"] = sorted(str(p.relative_to(target)).replace("\\", "/") for p in target.rglob("*") if p.is_file())
        before.append(row)
    preflight = {"schema": 1, "tool": "p15_video_package", "run": run,
                 "output": str(out), "backup": str(backup), "before": before, "plan": plan}
    write_json(backup / "preflight_record.json", preflight)
    return preflight


def registry(profile: dict, media: dict, owner: str, out: Path) -> dict:
    if owner == "ue_muxed" and media["kind"] != "mp4":
        raise Stop("UE_MUXED_REQUIRES_FFMPEG")
    validate_audio_owner(owner, owner == "ue_muxed", False)
    relative = lambda p: str(Path(p).relative_to(out)).replace("\\", "/")
    scenes = {}
    for scene, frames in SCENE_FRAMES.items():
        row = {
            "status": "PLACEHOLDER",
            "scene_frames_expected": frames,
            "fps": profile["render"]["fps"],
            "loop": True,
            "audio_owner": owner,
            "audio": relative(media["audio"]),
            "media_frames": media["media_frames"],
        }
        if media["kind"] == "mp4":
            row["video"] = relative(media["video"])
            row["review_muxed"] = relative(media["muxed"])
            row["playback_file"] = row["review_muxed"] if owner == "ue_muxed" else row["video"]
        else:
            row["imgmedia_pattern"] = relative(media["sequence"])
            row["playback_file"] = row["imgmedia_pattern"]
        scenes[scene] = row
    return {"schema": 2, "kind": media["kind"], "display_profile": "display_profile.json", "scenes": scenes}


def plan(config: dict, run: str) -> dict:
    profile = build_display_profile(config)
    owner = str(config.get("audio_owner", "ue_muxed"))
    if owner not in AUDIO_OWNERS:
        raise Stop("BAD_AUDIO_OWNER:%s" % owner)
    ffmpeg_exe, ffprobe_exe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    kind = "mp4" if ffmpeg_exe and ffprobe_exe else "imgmedia"
    requested_owner = owner
    owner_fallback = None
    if kind == "imgmedia" and owner == "ue_muxed":
        owner = "desk"
        owner_fallback = "ImgMedia has no embedded audio; use the generated separate WAV at the desk."
    out = output_path(config.get("output_dir", str(DEFAULT_OUTPUT)))
    return {
        "run": run,
        "mode": str(config.get("mode", "DRY")).upper(),
        "output": str(out),
        "kind": kind,
        "ffmpeg": ffmpeg_exe,
        "ffprobe": ffprobe_exe,
        "audio_owner": owner,
        "requested_audio_owner": requested_owner,
        "audio_owner_fallback": owner_fallback,
        "display_profile": profile,
        "scene_frames": SCENE_FRAMES,
        "owned_paths": [p.as_posix() for p in owned_relative_paths(kind)],
        "unreal_changes": 0,
    }


def apply(config: dict, p: dict) -> Path:
    run = p["run"]
    if config.get("confirm") != APPLY_CONFIRM:
        raise Stop("CONFIRM_REQUIRED:%s" % APPLY_CONFIRM)
    out = Path(p["output"])
    backup = under_root(PROJECT_ROOT / "Backups" / ("PreP15VideoTransitions-" + run))
    if backup.exists():
        raise Stop("BACKUP_ALREADY_EXISTS:%s" % backup)
    relpaths = [Path(value) for value in p["owned_paths"]]
    preflight = snapshot_before(out, backup, relpaths, run, p)
    out.mkdir(parents=True, exist_ok=True)
    media = (generate_with_ffmpeg(out, config, p["ffmpeg"], p["ffprobe"])
             if p["kind"] == "mp4" else generate_fallback_sequence(out, config))
    profile = p["display_profile"]
    write_json(out / "display_profile.json", profile)
    write_json(out / "placeholder_current.json", registry(profile, media, p["audio_owner"], out))
    results = []
    for rel in relpaths:
        target = out / rel
        if target.is_file():
            results.append({"relative": rel.as_posix(), "sha256": sha256(target), "bytes": target.stat().st_size})
        elif target.is_dir():
            files = [x for x in target.rglob("*") if x.is_file()]
            results.append({"relative": rel.as_posix(), "files": len(files), "bytes": sum(x.stat().st_size for x in files)})
    record = dict(preflight)
    record.update({"applied": True, "results": results, "media_frames": media["media_frames"]})
    write_json(backup / "apply_record.json", record)
    write_json(out / "p15_apply_record.json", record)
    return out / "p15_apply_record.json"


def revert(config: dict, run: str) -> Path:
    if config.get("confirm") != REVERT_CONFIRM:
        raise Stop("CONFIRM_REQUIRED:%s" % REVERT_CONFIRM)
    record_value = config.get("record")
    if not record_value:
        raise Stop("REVERT_RECORD_REQUIRED")
    record_path = output_path(record_value)
    record = read_json(record_path)
    if record.get("tool") != "p15_video_package" or not record.get("applied"):
        raise Stop("BAD_REVERT_RECORD")
    out = under_root(Path(record["output"]))
    backup = under_root(Path(record["backup"]))
    if not (backup / "preflight_record.json").is_file():
        raise Stop("BACKUP_INCOMPLETE")
    reverted = backup / ("Reverted-" + run)
    if reverted.exists():
        raise Stop("REVERT_ARCHIVE_EXISTS")
    (reverted / "applied").mkdir(parents=True)
    actions = []
    for row in record["before"]:
        rel = Path(row["relative"])
        target = under_root(out / rel)
        archive = reverted / "applied" / rel
        if target.exists():
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(archive))
            actions.append("archived:" + rel.as_posix())
        source = backup / "before" / rel
        if row["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
            actions.append("restored:" + rel.as_posix())
    result = {"schema": 1, "tool": "p15_video_package", "mode": "REVERT", "run": run,
              "apply_run": record["run"], "archive": str(reverted), "actions": actions}
    path = reverted / "revert_record.json"
    write_json(path, result)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args", default="Tools/InfinityStage/p15_video_package_args.json")
    parser.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"))
    parser.add_argument("--confirm", help="Exact APPLY/REVERT confirmation string")
    parsed = parser.parse_args(argv)
    config = read_json(output_path(parsed.args))
    if parsed.mode:
        config["mode"] = parsed.mode
    if parsed.confirm is not None:
        config["confirm"] = parsed.confirm
    run = str(config.get("run_id") or utc_run())
    try:
        mode = str(config.get("mode", "DRY")).upper()
        if mode == "REVERT":
            record = revert(config, run)
            print("P15VIDEO_REVERT_OK|run=%s|record=%s" % (run, record))
            return 0
        p = plan(config, run)
        print(json.dumps(p, indent=2, sort_keys=True))
        if mode == "DRY":
            print("P15VIDEO_DRY_OK|run=%s|kind=%s|output=%s" % (run, p["kind"], p["output"]))
            return 0
        if mode != "APPLY":
            raise Stop("BAD_MODE:%s" % mode)
        record = apply(config, p)
        print("P15VIDEO_APPLY_OK|run=%s|record=%s" % (run, record))
        return 0
    except Stop as exc:
        print("P15VIDEO_STOPPED|run=%s|reason=%s" % (run, str(exc)), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
