"""Prepare and supervise an Unreal-native frame-sequence capture run."""
import ctypes
import ctypes.wintypes as wt
import datetime
import json
import pathlib
import time

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
ROOT = BASE / "LightingLooks"
CURRENT = BASE / "lighting_looks_current_run.json"
TITLE_PART = "Preview [NetMode: Standalone 0]"
user32 = ctypes.windll.user32


def write_json(path, value):
    pathlib.Path(path).write_text(json.dumps(value, indent=2), encoding="utf-8")


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


stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
run_dir = ROOT / stamp
(run_dir / "shots").mkdir(parents=True, exist_ok=False)
(run_dir / "sequence").mkdir(parents=True, exist_ok=False)
write_json(CURRENT, {
    "run_id": stamp,
    "run_dir": run_dir.as_posix(),
    "prepared_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "status": "capture_waiting_for_pie",
})

previous_foreground = user32.GetForegroundWindow()
hwnd = None
was_topmost = False
try:
    runtime_path = run_dir / "runtime_result.json"
    deadline = time.monotonic() + 90.0
    runtime = None
    while time.monotonic() < deadline:
        if runtime_path.is_file():
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            if runtime.get("pie_observed"):
                break
        time.sleep(0.1)
    if not runtime or not runtime.get("pie_observed"):
        raise RuntimeError("owned PIE was not observed")
    ready = {
        "status": "ready",
        "capture_backend": "unreal_highresshot_sequence",
        "video_only": True,
        "pie_surface": "owned_editor_pie",
        "capture_started_monotonic": time.monotonic(),
    }
    write_json(run_dir / "capture_ready.json", ready)
    deadline = time.monotonic() + 360.0
    while time.monotonic() < deadline and not (run_dir / "capture_stop.json").exists():
        time.sleep(0.1)
    if not (run_dir / "capture_stop.json").exists():
        raise RuntimeError("capture timed out before the owned driver ended PIE")
    write_json(run_dir / "capture_result.json", {
        **ready,
        "status": "complete",
        "finished_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    })
except Exception as exc:
    write_json(run_dir / "capture_failed.json", {
        "status": "failed",
        "finished_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "error": repr(exc),
    })
    raise
finally:
    if previous_foreground:
        user32.SetForegroundWindow(previous_foreground)
