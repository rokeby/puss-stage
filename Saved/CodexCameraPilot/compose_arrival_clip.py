"""Offline: turn the raw editor-window recording of the arrival take into the clip Gary watches. (30 Sep)

Usage: python compose_arrival_clip.py <raw.mp4> <harness json> <out.mp4> [--dup-drop D,P] [--trim-start S]

1. Crop to the viewport: the region whose pixels change over time. The editor's panels hardly change,
   and the PIE viewport does.
2. Align to the show's clock: the P04 -> Scene 4 cut is the largest frame-to-frame change near where the
   harness log (scene1_tail_view_pie.py) puts it. That frame is t = 0.
3. Stamp every frame with its time from the cut, and a caption stating what the clip is and isn't. All
   text is stamped with PIL (ffmpeg drawtext crashes here).
The caption's wording follows the conductor (30 Sep): "lights begin at the cut until patch P is built".
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageStat

CAPTION = [
    "As played: a real-time screen recording of PIE on this machine, the transport through P04 into Scene 4.",
    "Lights begin at the cut until patch P is built.  No settle yet: the camera arrives at walking pace.",
    "Camera bob as today (roll fix M not built).  %s",
]


def frames_of(video, folder, fps):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video, "-vf", "fps=%d" % fps,
                    os.path.join(folder, "f_%05d.png")], check=True)
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.startswith("f_"))


def viewport_box(paths):
    """Bounding box of pixels that change across the take (sampled), padded a little."""
    sample = [Image.open(p).convert("L").resize((480, 270)) for p in paths[:: max(1, len(paths) // 40)]]
    moving = Image.new("L", sample[0].size, 0)
    for a, b in zip(sample, sample[1:]):
        moving = ImageChops.lighter(moving, ImageChops.difference(a, b).point(lambda v: 255 if v > 12 else 0))
    box = moving.getbbox()
    if not box:
        return None
    full = Image.open(paths[0]).size
    sx, sy = full[0] / 480.0, full[1] / 270.0
    return (int(box[0] * sx), int(box[1] * sy), int(box[2] * sx), int(box[3] * sy))


def main():
    raw, log_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    dup_drop = next((a.split("=", 1)[1] for a in sys.argv[4:] if a.startswith("--dup-drop=")), "?")
    trim_start = float(next((a.split("=", 1)[1] for a in sys.argv[4:] if a.startswith("--trim-start=")), "2.0"))
    fps = 30
    with open(log_path, encoding="utf-8") as handle:
        log = json.load(handle)
    work = tempfile.mkdtemp()
    try:
        paths = frames_of(raw, work, fps)
        box = viewport_box(paths)
        diffs = [sum(ImageStat.Stat(ImageChops.difference(
            Image.open(a).convert("RGB").resize((320, 180)), Image.open(b).convert("RGB").resize((320, 180)))).mean)
            for a, b in zip(paths, paths[1:])]
        # The cut: the biggest single change. The log says it is lead_s after the scrub; the scrub itself is
        # the other big change, at the start, so look only after trim_start.
        start_index = int(trim_start * fps)
        cut_index = max(range(start_index, len(diffs)), key=lambda i: diffs[i]) + 1
        stamped = []
        for index, path in enumerate(paths):
            if index < start_index:
                continue
            frame = Image.open(path).convert("RGB")
            if box:
                frame = frame.crop(box)
            width = frame.width - frame.width % 2
            canvas = Image.new("RGB", (width, frame.height - frame.height % 2 + 78), (12, 12, 12))
            canvas.paste(frame.crop((0, 0, width, frame.height - frame.height % 2)), (0, 0))
            draw = ImageDraw.Draw(canvas)
            t = (index - cut_index) / float(fps)
            draw.rectangle([0, 0, 260, 26], fill=(0, 0, 0))
            draw.text((8, 7), "%+.2f s from the cut into Scene 4" % t, fill=(255, 230, 120))
            lines = list(CAPTION)
            lines[2] = lines[2] % ("Recorder dup/drop: %s." % dup_drop)
            draw.multiline_text((8, frame.height - frame.height % 2 + 8), "\n".join(lines), fill=(210, 210, 210), spacing=6)
            path_out = os.path.join(work, "s_%05d.png" % len(stamped))
            canvas.save(path_out)
            stamped.append(path_out)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(fps),
                        "-i", os.path.join(work, "s_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", out], check=True)
        print(json.dumps({"out": out, "frames": len(stamped), "viewport_box": box,
                          "cut_at_raw_s": round(cut_index / float(fps), 2),
                          "cut_diff": round(diffs[cut_index - 1], 1),
                          "next_biggest_diff": round(sorted(diffs[start_index:])[-2], 1),
                          "log_rows": len(log.get("rows", []))}))
    finally:
        shutil.rmtree(work)


main()
