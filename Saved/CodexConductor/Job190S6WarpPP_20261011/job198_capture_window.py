"""Capture the foreground floating PIE client for Job 198 using ffmpeg ddagrab."""
import ctypes
import ctypes.wintypes as wt
import json
import pathlib
import shutil
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path("E:/PussStage/Saved/CodexConductor/ApplyPass_20261010/198_S6_warp_60to70_A2_raw.mp4")
READY = HERE / "job198_capture_A2_ready.json"
RESULT = HERE / "job198_capture_A2_result.json"
STDERR = HERE / "job198_capture_A2_ffmpeg_stderr.txt"
FFMPEG = shutil.which("ffmpeg")
if not FFMPEG:
    raise RuntimeError("ffmpeg not found")
if OUT.exists() or READY.exists() or RESULT.exists():
    raise RuntimeError("Job 198 capture output already exists")

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

def windows():
    rows = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                rows.append((hwnd, buf.value))
        return True
    user32.EnumWindows(cb, 0)
    return rows

deadline = time.monotonic() + 30
matches = []
while time.monotonic() < deadline:
    preview = [(h, t) for h, t in windows() if "Preview [NetMode: Standalone 0]" in t]
    editor = [(h, t) for h, t in windows() if t == "PussStage - Unreal Editor"]
    matches = preview if preview else editor
    if len(matches) == 1:
        break
    if len(matches) > 1:
        raise RuntimeError("multiple PIE windows %r" % matches)
    time.sleep(0.1)
if len(matches) != 1:
    raise RuntimeError("PIE preview or PussStage editor window not found")
hwnd, title = matches[0]
user32.ShowWindow(hwnd, 9)
user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
user32.BringWindowToTop(hwnd)
user32.SetForegroundWindow(hwnd)
time.sleep(0.25)
client = wt.RECT()
if not user32.GetClientRect(hwnd, ctypes.byref(client)):
    raise ctypes.WinError()
point = wt.POINT(0, 0)
if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
    raise ctypes.WinError()
x, y = point.x, point.y
width, height = client.right - client.left, client.bottom - client.top
screen_width = user32.GetSystemMetrics(0)
screen_height = user32.GetSystemMetrics(1)
if x < 0:
    width += x
    x = 0
if y < 0:
    height += y
    y = 0
width = min(width, screen_width - x)
height = min(height, screen_height - y)
width -= width % 2
height -= height % 2
grab = "ddagrab=output_idx=0:framerate=30:offset_x=%d:offset_y=%d:video_size=%dx%d:draw_mouse=0" % (x, y, width, height)
command = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-filter_complex",
           grab + ",hwdownload,format=bgra,scale=1280:720:flags=bicubic,format=yuv420p[v]",
           "-map", "[v]", "-t", "18", "-c:v", "h264_nvenc", "-preset", "p5", "-movflags", "+faststart", str(OUT)]
started = time.monotonic()
stderr_handle = STDERR.open("w", encoding="utf-8")
process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=stderr_handle, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
READY.write_text(json.dumps({"status": "ready", "capture_started_monotonic": started,
                             "window_title": title, "client_rect": [x, y, width, height],
                             "output": OUT.as_posix(), "command": command}, indent=2), encoding="utf-8")
process.wait()
stderr_handle.close()
stderr = STDERR.read_text(encoding="utf-8")
success = process.returncode == 0 and OUT.exists() and OUT.stat().st_size > 0
result = {"status": "complete" if success else "failed", "capture_started_monotonic": started,
          "capture_finished_monotonic": time.monotonic(), "output": OUT.as_posix(),
          "bytes": OUT.stat().st_size if OUT.exists() else 0, "returncode": process.returncode,
          "stderr": STDERR.as_posix()}
RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
if not success:
    raise RuntimeError("ffmpeg failed %d %s" % (process.returncode, stderr))
user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
print(json.dumps(result))
