"""Encode and verify the Unreal-native P04 frame sequence and six stills."""
import json
import pathlib
import shutil
import subprocess
import time

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
current = json.loads((BASE / "lighting_looks_current_run.json").read_text(encoding="utf-8"))
run_dir = pathlib.Path(current["run_dir"])
runtime = json.loads((run_dir / "runtime_result.json").read_text(encoding="utf-8"))
capture = json.loads((run_dir / "capture_result.json").read_text(encoding="utf-8"))
if runtime.get("status") != "passed" or runtime.get("final_status") != "passed":
    raise RuntimeError("runtime did not pass")
if runtime.get("dirty_maps_after") or runtime.get("dirty_content_after"):
    raise RuntimeError("post-PIE census was not clean")
if not runtime.get("screen_messages_restored"):
    raise RuntimeError("screen messages were not restored")
if len(runtime.get("shots", [])) != 6:
    raise RuntimeError("expected exactly six shot records")
if len(runtime.get("sequence_frames", [])) < 24:
    raise RuntimeError("expected at least 24 sequence frame records")

expected = [pathlib.Path(row["path_requested"]) for row in runtime["shots"]]
expected += [pathlib.Path(row["path_requested"]) for row in runtime["sequence_frames"]]
deadline = time.monotonic() + 30.0
while time.monotonic() < deadline and any(not path.is_file() for path in expected):
    time.sleep(0.25)
missing = [path.as_posix() for path in expected if not path.is_file() or path.stat().st_size <= 0]
if missing:
    raise RuntimeError("missing/empty captures: %r" % missing)

ffmpeg = shutil.which("ffmpeg") or str(pathlib.Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe")
ffprobe = shutil.which("ffprobe") or str(pathlib.Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffprobe.exe")
frames = runtime["sequence_frames"]
filters = []
start = 0
while start < len(frames):
    label = frames[start]["label"]
    end = start
    while end + 1 < len(frames) and frames[end + 1]["label"] == label:
        end += 1
    safe = label.replace("'", "\\'").replace(":", "\\:")
    filters.append(
        "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='%s':x=36:y=36:fontsize=30:fontcolor=white:"
        "box=1:boxcolor=black@0.65:boxborderw=12:enable='between(t,%d,%d)'"
        % (safe, start, end + 1)
    )
    start = end + 1
filters.append("fps=30")
final_video = run_dir / (current["run_id"] + "_P04_lighting_looks.mp4")
subprocess.run([
    ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-framerate", "1",
    "-i", str(run_dir / "sequence" / "frame_%04d.png"), "-vf", ",".join(filters),
    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
    "-movflags", "+faststart", str(final_video),
], check=True)
probe = json.loads(subprocess.check_output([
    ffprobe, "-v", "error", "-select_streams", "v:0",
    "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames:format=duration,size",
    "-of", "json", str(final_video),
], text=True))

sample_md5 = subprocess.check_output([
    ffmpeg, "-v", "error", "-i", str(final_video), "-vf", "fps=1",
    "-map", "0:v:0", "-fps_mode", "passthrough", "-f", "framemd5", "-",
], text=True)
hashes = [line.rsplit(",", 1)[-1].strip() for line in sample_md5.splitlines()
          if line and not line.startswith("#") and "," in line]
identical = sum(left == right for left, right in zip(hashes, hashes[1:]))
identical_fraction = identical / max(1, len(hashes) - 1)
if identical_fraction >= 0.98:
    raise RuntimeError("video appears frozen: sampled identical fraction %.6f" % identical_fraction)

stills = [pathlib.Path(row["path_requested"]).as_posix() for row in runtime["shots"]]
verification = {
    "status": "passed",
    "capture_backend": capture["capture_backend"],
    "video": final_video.as_posix(),
    "video_only": True,
    "probe": probe,
    "sampled_frames": len(hashes),
    "sampled_identical_consecutive_fraction": identical_fraction,
    "sampled_moving_consecutive_fraction": 1.0 - identical_fraction,
    "source_sequence_frames": len(frames),
    "stills": stills,
    "shot_max_late_frames": max(row["error_frames"] for row in runtime["shots"]),
    "census": {"maps": runtime["dirty_maps_after"], "content": runtime["dirty_content_after"]},
    "screen_messages_restored": runtime["screen_messages_restored"],
}
(run_dir / "verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
print(json.dumps(verification, indent=2))
