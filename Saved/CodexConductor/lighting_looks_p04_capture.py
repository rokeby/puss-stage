"""Capture the owned floating P04 lighting-look PIE window as video only."""
import ctypes
import ctypes.wintypes as wt
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
ROOT = BASE / "LightingLooks"
CURRENT = BASE / "lighting_looks_current_run.json"
FFMPEG = shutil.which("ffmpeg") or os.path.join(
    os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Links\ffmpeg.exe"
)
TITLE_PART = "Preview [NetMode: Standalone 0]"
CAPTURE_BACKEND = os.environ.get("PUSS_LIGHTING_CAPTURE_BACKEND", "ddagrab").lower()
if CAPTURE_BACKEND not in ("ddagrab", "gdigrab"):
    raise RuntimeError("unsupported capture backend: " + CAPTURE_BACKEND)

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

interactive_winsta = user32.OpenWindowStationW("WinSta0", False, 0x037F)
if not interactive_winsta or not user32.SetProcessWindowStation(interactive_winsta):
    raise ctypes.WinError()
input_desktop = user32.OpenInputDesktop(0, False, 0x01C1)
if not input_desktop or not user32.SetThreadDesktop(input_desktop):
    raise ctypes.WinError()


def windows():
    rows = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def callback(hwnd, _param):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                rows.append((hwnd, buffer.value))
        return True

    user32.EnumWindows(callback, 0)
    return rows


def find_window(deadline):
    while time.monotonic() < deadline:
        matches = [(hwnd, title) for hwnd, title in windows()
                   if TITLE_PART.lower() in title.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError("multiple PIE Preview windows found: %r" % (matches,))
        time.sleep(0.1)
    raise RuntimeError("floating PIE Preview window was not found")


def rect(hwnd):
    value = wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(value)):
        raise ctypes.WinError()
    return value.left, value.top, value.right - value.left, value.bottom - value.top


def write_json(path, value):
    pathlib.Path(path).write_text(json.dumps(value, indent=2), encoding="utf-8")


def encoder_name():
    probe = subprocess.run(
        [FFMPEG, "-hide_banner", "-encoders"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return "h264_nvenc" if "h264_nvenc" in probe.stdout else "libx264"


stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
run_dir = ROOT / stamp
(run_dir / "shots").mkdir(parents=True, exist_ok=False)
write_json(CURRENT, {
    "run_id": stamp,
    "run_dir": run_dir.as_posix(),
    "prepared_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "status": "capture_waiting_for_pie",
})

previous_foreground = user32.GetForegroundWindow()
hwnd = None
was_topmost = False
process = None
stderr_handle = None
try:
    hwnd, title = find_window(time.monotonic() + 90.0)
    original_rect = rect(hwnd)
    GWL_EXSTYLE = -20
    WS_EX_TOPMOST = 0x00000008
    was_topmost = bool(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)
    SW_RESTORE = 9
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_SHOWWINDOW = 0x0040
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)
    x, y, width, height = rect(hwnd)
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)
    if x < 0 or y < 0 or x + width > screen_width or y + height > screen_height:
        nx = max(0, min(x, max(0, screen_width - width)))
        ny = max(0, min(y, max(0, screen_height - height)))
        user32.SetWindowPos(hwnd, HWND_TOPMOST, nx, ny, 0, 0,
                            SWP_NOSIZE | SWP_SHOWWINDOW)
        x, y, width, height = rect(hwnd)
    width -= width % 2
    height -= height % 2
    codec = encoder_name()
    output = run_dir / (stamp + "_P04_lighting_looks_raw.mp4")
    if CAPTURE_BACKEND == "ddagrab":
        grab = (
            "ddagrab=output_idx=0:framerate=30:offset_x=%d:offset_y=%d:"
            "video_size=%dx%d:draw_mouse=0" % (x, y, width, height)
        )
        command = [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-filter_complex",
            grab + ",hwdownload,format=bgra,scale=960:-2:flags=bicubic,format=yuv420p[v]",
            "-map", "[v]", "-an",
        ]
    else:
        command = [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "gdigrab", "-framerate", "30", "-offset_x", str(x),
            "-offset_y", str(y), "-video_size", "%dx%d" % (width, height),
            "-draw_mouse", "0", "-i", "desktop", "-an",
            "-vf", "scale=960:-2:flags=bicubic,format=yuv420p",
        ]
    if codec == "h264_nvenc":
        command += ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr",
                    "-b:v", "1M", "-maxrate", "1.5M", "-bufsize", "3M"]
    else:
        command += ["-c:v", "libx264", "-preset", "veryfast", "-b:v", "1M",
                    "-maxrate", "1.5M", "-bufsize", "3M"]
    command += ["-g", "60", "-movflags", "+faststart", str(output)]
    stderr_path = run_dir / "ffmpeg_stderr.txt"
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    capture_started_monotonic = time.monotonic()
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=stderr_handle, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    time.sleep(1.5)
    if process.poll() is not None:
        raise RuntimeError("ffmpeg exited before capture ready with code %s" % process.returncode)
    ready = {
        "status": "ready",
        "ready_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "window_title": title,
        "window_rect": [x, y, width, height],
        "original_rect": list(original_rect),
        "codec": codec,
        "capture_backend": CAPTURE_BACKEND,
        "output": output.as_posix(),
        "capture_started_monotonic": capture_started_monotonic,
        "foreground_requested": True,
        "topmost_requested": True,
        "video_only": True,
    }
    write_json(run_dir / "capture_ready.json", ready)
    deadline = time.monotonic() + 360.0
    while time.monotonic() < deadline and not (run_dir / "capture_stop.json").exists():
        if process.poll() is not None:
            raise RuntimeError("ffmpeg exited during capture with code %s" % process.returncode)
        time.sleep(0.1)
    if not (run_dir / "capture_stop.json").exists():
        raise RuntimeError("capture timed out before the owned driver ended PIE")
    if process.poll() is None:
        process.stdin.write("q\n")
        process.stdin.flush()
        process.wait(timeout=20)
    if process.returncode != 0 or not output.exists():
        raise RuntimeError("ffmpeg failed with code %s" % process.returncode)
    write_json(run_dir / "capture_result.json", {
        **ready,
        "status": "complete",
        "finished_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "returncode": process.returncode,
        "bytes": output.stat().st_size,
    })
except Exception as exc:
    write_json(run_dir / "capture_failed.json", {
        "status": "failed",
        "finished_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "error": repr(exc),
    })
    if process is not None and process.poll() is None:
        try:
            process.stdin.write("q\n")
            process.stdin.flush()
            process.wait(timeout=10)
        except Exception:
            process.terminate()
    print(repr(exc), file=sys.stderr)
    raise
finally:
    if stderr_handle is not None:
        stderr_handle.close()
    if hwnd:
        HWND_NOTOPMOST = -2
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        if not was_topmost:
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
    if previous_foreground and user32.IsWindow(previous_foreground):
        user32.SetForegroundWindow(previous_foreground)
