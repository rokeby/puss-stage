"""Offline: build the arrival clip from PIE per-tick screenshots, at their TRUE times. (30 Sep, option B)

Real-time screen recording failed twice: the PIE viewport doesn't present new frames on screen while the
editor isn't the foreground app, though the engine ticks at 57 fps (take 1's log measured the ticks). A
`shot` screenshot forces a render, so per-tick screenshots hold the true show content. Each shot is placed at
its logged time from the cut, and held until the next one, then resampled to 25 fps. The screenshot stalls
lower the effective rate, which the caption states: this clip judges TIMING, not smoothness.

Usage: python compose_arrival_shots.py <harness json> <first ScreenShot number> <out.mp4>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "..", "Screenshots", "WindowsEditor")
FPS = 25
CAPTION = [
    "As played: the transport through P04 into Scene 4 in PIE; one screenshot per engine tick, at its true time.",
    "Lights begin at the cut until patch P is built.  No settle yet: the camera arrives at walking pace.",
    "Camera bob as today (roll fix M not built).  About %.0f frames/s captured: judge timing here, not smoothness.",
]


def main():
    log_path, first, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    with open(log_path, encoding="utf-8") as handle:
        run = json.load(handle)
    shots = run["crossing_shots_in_order"]
    files = [os.path.join(SHOTS, "ScreenShot%05d.png" % (first + i)) for i in range(len(shots))]
    missing = [f for f in files if not os.path.exists(f)]
    if missing:
        raise SystemExit("missing %d screenshots, first %s" % (len(missing), missing[0]))
    times = [s["relative_s"] for s in shots]
    span = times[-1] - times[0]
    rate = (len(times) - 1) / span if span > 0 else 0.0
    work = tempfile.mkdtemp()
    try:
        frame = 0
        t = times[0]
        index = 0
        while t <= times[-1] + 1e-9:
            while index + 1 < len(times) and times[index + 1] <= t + 1e-9:
                index += 1
            image = Image.open(files[index]).convert("RGB")
            width, height = image.width - image.width % 2, image.height - image.height % 2
            canvas = Image.new("RGB", (width, height + 78), (12, 12, 12))
            canvas.paste(image.crop((0, 0, width, height)), (0, 0))
            draw = ImageDraw.Draw(canvas)
            draw.rectangle([0, 0, 270, 26], fill=(0, 0, 0))
            draw.text((8, 7), "%+.2f s from the cut into Scene 4" % t, fill=(255, 230, 120))
            lines = list(CAPTION)
            lines[2] = lines[2] % rate
            draw.multiline_text((8, height + 8), "\n".join(lines), fill=(210, 210, 210), spacing=6)
            canvas.save(os.path.join(work, "c_%05d.png" % frame))
            frame += 1
            t += 1.0 / FPS
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS),
                        "-i", os.path.join(work, "c_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", out], check=True)
        print(json.dumps({"out": out, "shots": len(shots), "effective_fps": round(rate, 1),
                          "span_s": [times[0], times[-1]], "video_frames": frame}))
    finally:
        shutil.rmtree(work)


main()
