"""Burn per-bay labels into the P04 video and verify video motion plus six stills."""
import json
import pathlib
import shutil
import subprocess

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

ffmpeg = shutil.which("ffmpeg") or str(pathlib.Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe")
ffprobe = shutil.which("ffprobe") or str(pathlib.Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffprobe.exe")
raw_video = pathlib.Path(capture["output"])
capture_start = float(capture["capture_started_monotonic"])
events = runtime["label_events"]
filters = []
for index, event in enumerate(events):
    start = max(0.0, float(event["wall"]) - capture_start)
    if index + 1 < len(events):
        end = max(start + 0.001, float(events[index + 1]["wall"]) - capture_start)
    else:
        end = max(start + 0.001, float(runtime["ended_wall"]) - capture_start)
    label = event["label"].replace("'", "\\'").replace(":", "\\:")
    filters.append(
        "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='%s':x=36:y=36:fontsize=30:fontcolor=white:"
        "box=1:boxcolor=black@0.65:boxborderw=12:enable='between(t,%.6f,%.6f)'"
        % (label, start, end)
    )
final_video = run_dir / (current["run_id"] + "_P04_lighting_looks.mp4")
subprocess.run([
    ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw_video),
    "-vf", ",".join(filters), "-an", "-c:v", "libx264", "-preset", "veryfast",
    "-crf", "18", "-movflags", "+faststart", str(final_video),
], check=True)

probe = json.loads(subprocess.check_output([
    ffprobe, "-v", "error", "-select_streams", "v:0",
    "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames:format=duration,size",
    "-of", "json", str(final_video),
], text=True))
framemd5 = subprocess.check_output([
    ffmpeg, "-v", "error", "-i", str(final_video), "-map", "0:v:0",
    "-fps_mode", "passthrough", "-f", "framemd5", "-",
], text=True)
hashes = [line.rsplit(",", 1)[-1].strip() for line in framemd5.splitlines()
          if line and not line.startswith("#") and "," in line]
identical = sum(left == right for left, right in zip(hashes, hashes[1:]))
identical_fraction = identical / max(1, len(hashes) - 1)
if identical_fraction >= 0.98:
    raise RuntimeError("video appears frozen: identical fraction %.6f" % identical_fraction)

stills = []
for shot in runtime["shots"]:
    path = pathlib.Path(shot["path_requested"])
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError("missing/empty still %s" % path)
    stills.append(path.as_posix())

verification = {
    "status": "passed",
    "video": final_video.as_posix(),
    "raw_video": raw_video.as_posix(),
    "video_only": True,
    "probe": probe,
    "decoded_frames": len(hashes),
    "identical_consecutive_fraction": identical_fraction,
    "moving_consecutive_fraction": 1.0 - identical_fraction,
    "stills": stills,
    "shot_max_late_frames": max(row["error_frames"] for row in runtime["shots"]),
    "census": {"maps": runtime["dirty_maps_after"],
               "content": runtime["dirty_content_after"]},
    "screen_messages_restored": runtime["screen_messages_restored"],
}
(run_dir / "verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
print(json.dumps(verification, indent=2))
