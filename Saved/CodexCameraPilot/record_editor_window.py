"""Host-side, not Unreal: record the Unreal Editor window in real time with ffmpeg gdigrab. (30 Sep)

For Gary's as-played arrival clip: P04's last ~10 s through Scene 4 +10 s, played by the transport in PIE,
recorded as the machine plays it (stutter included). Run it just BEFORE arming the PIE take; it records
for --seconds and exits. It only reads the screen and touches nothing in the engine.

Instrument in the answer: encoding competes with the editor for CPU and could itself cause hitches. So it
uses x264 "ultrafast" at a fixed frame rate, and the report carries ffmpeg's own dup/drop counts. A take
whose drop count is large is suspect; don't judge smoothness from it.

Usage: python record_editor_window.py --seconds 26 --out <file.mp4> [--fps 30] [--dry]
--dry only finds the window and prints the ffmpeg command (records nothing).
Gary must not move or cover the editor window during a take.
"""
import argparse
import json
import re
import subprocess
import sys
import time


def editor_window_title():
    ps = ("Get-Process UnrealEditor -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } | "
          "Select-Object -First 1 -ExpandProperty MainWindowTitle")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
    title = out.stdout.strip()
    if not title:
        raise SystemExit("No Unreal Editor window found")
    return title


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    title = editor_window_title()
    command = ["ffmpeg", "-hide_banner", "-y", "-f", "gdigrab", "-framerate", str(args.fps), "-draw_mouse", "0",
               "-i", "title=%s" % title, "-t", str(args.seconds),
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", args.out]
    if args.dry:
        print(json.dumps({"title": title, "command": command}, ensure_ascii=False))
        return
    started = time.time()
    run = subprocess.run(command, capture_output=True, text=True)
    stats = re.findall(r"dup=(\d+) drop=(\d+)", run.stderr)
    report = {"title": title, "out": args.out, "returncode": run.returncode,
              "wall_s": round(time.time() - started, 2),
              "dup_drop": [int(x) for x in stats[-1]] if stats else None,
              "stderr_tail": run.stderr[-400:]}
    print(json.dumps(report, ensure_ascii=False))
    sys.exit(run.returncode)


main()
