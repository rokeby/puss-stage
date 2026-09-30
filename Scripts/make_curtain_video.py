"""Turn a rendered curtain clip (numbered PNGs) into a labelled real-time MP4 for Gary (30 Sep: "Please send through bake
test videos if they arrive so I can see curtain").

    python Scripts/make_curtain_video.py <clip_dir> <out.mp4> "<title>" [release_index] [hold_note]

Every frame gets:
  - a red banner with the title and "NOT A SHOW FRAME". These are Blender Workbench renders: no velvet, lanterns or
    exposure, so they show the motion and the fall, not the look;
  - a time-from-release counter (release_index = the clip frame of the release, 30 by default = 1 s in).
Frames before the release get the hold note (in the show that pose is frozen). The frames are stamped with PIL, not
ffmpeg drawtext, because this machine's ffmpeg crashes without fontconfig.
"""
import subprocess
import sys
from pathlib import Path
import os

from PIL import Image, ImageDraw, ImageFont

FFMPEG = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"


def main():
    clip, out, title = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    release = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    hold_note = sys.argv[5] if len(sys.argv) > 5 else "HOLD: in the show this pose is frozen"
    stamped = clip.with_name(clip.name + "_labelled")
    stamped.mkdir(exist_ok=True)
    big, small = ImageFont.load_default(size=26), ImageFont.load_default(size=22)
    frames = sorted(clip.glob("f*.png"))
    for n, p in enumerate(frames):
        im = Image.open(p).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, im.width, 56), fill=(170, 20, 20))
        d.text((16, 14), f"{title}. NOT A SHOW FRAME: Blender Workbench, no velvet, lanterns or exposure.",
               fill="white", font=big)
        t = (n - release) / 30.0
        d.text((16, im.height - 40), f"t = {t:+.2f} s from release" + (f"   ({hold_note})" if n < release else ""),
               fill="white", font=small)
        im.save(stamped / p.name)
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-framerate", "30", "-i", str(stamped / "f%04d.png"),
                    "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", str(out)],
                   check=True)
    print(f"VIDEO|{out}|frames={len(frames)}")


if __name__ == "__main__":
    main()
