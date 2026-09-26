"""Record a phone-friendly clip of the Puss PIE window (or any window) with ffmpeg.

Usage:
  python record_clip.py --seconds 90 --label "B seed104 cycle" [--title "Preview"] [--width 960]

- Finds the first visible window whose title contains --title (default: the PIE window; falls back
  to the Puss editor), captures just that window's rectangle with Desktop Duplication (ddagrab),
  and encodes H.264 on the GPU (NVENC) at about 1 Mbit/s, which is roughly Telegram/WhatsApp
  "compressed" quality: ~5-10 MB for 60-90 s at 960 px wide.
- Writes E:/PussStage/Saved/Conductor/Clips/<UTC stamp>_<label>.mp4 plus a .json sidecar (label, start,
  seconds, window), so take_report.py and the Takes page can match clips to takes.
- Needs the display awake and unlocked (Desktop Duplication captures what is on screen).
Owner: the conductor session. Records only; drives nothing in the engine.
"""
import argparse, ctypes, ctypes.wintypes as wt, datetime, json, os, re, shutil, subprocess, sys

CLIPS = r"E:\PussStage\Saved\Conductor\Clips"
FFMPEG = shutil.which("ffmpeg") or os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Links\ffmpeg.exe")

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # true pixel coordinates
except Exception:
    pass


def windows():
    out = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, _):
        if user32.IsWindowVisible(h):
            n = user32.GetWindowTextLengthW(h)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1); user32.GetWindowTextW(h, buf, n + 1)
                out.append((h, buf.value))
        return True
    user32.EnumWindows(cb, 0)
    return out


def find(title_parts):
    ws = windows()
    for part in title_parts:
        for h, t in ws:
            if part.lower() in t.lower():
                return h, t
    return None, None


def rect(h):
    r = wt.RECT(); user32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--label", default="take")
    ap.add_argument("--title", default=None, help="substring of the window title to capture")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--bitrate", default="1M")
    a = ap.parse_args()

    parts = [a.title] if a.title else ["Preview [NetMode", "PussStage - Unreal Editor"]
    h, title = find(parts)
    if not h:
        sys.exit(f"no visible window matching {parts}")
    x, y, w, hgt = rect(h)
    x, y = max(0, x), max(0, y)
    w, hgt = w - (w % 2), hgt - (hgt % 2)
    os.makedirs(CLIPS, exist_ok=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", a.label).strip("_")[:60]
    out = os.path.join(CLIPS, f"{stamp}_{safe}.mp4")
    grab = f"ddagrab=output_idx=0:framerate={a.fps}:offset_x={x}:offset_y={y}:video_size={w}x{hgt}:draw_mouse=0"
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-filter_complex", f"{grab},hwdownload,format=bgra,scale={a.width}:-2:flags=bicubic,format=yuv420p[v]",
           "-map", "[v]", "-t", str(a.seconds),
           "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-b:v", a.bitrate, "-maxrate", "1.5M", "-bufsize", "3M",
           "-g", str(a.fps * 2), "-movflags", "+faststart", out]
    started = datetime.datetime.now(datetime.UTC).isoformat()
    r = subprocess.run(cmd)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit(f"ffmpeg failed ({r.returncode})")
    meta = {"label": a.label, "start_utc": started, "seconds": a.seconds, "window": title,
            "rect": [x, y, w, hgt], "file": out, "bytes": os.path.getsize(out)}
    json.dump(meta, open(out[:-4] + ".json", "w"), indent=1)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
